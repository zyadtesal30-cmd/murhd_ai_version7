# -*- coding: utf-8 -*-
"""مساعد محلي (Offline) — بيفهم أسئلة الطالب بالعربي ويجاوب من بياناته ولائحة القسم من غير إنترنت.
مفيش نموذج ذكاء اصطناعي خارجي: فهم الأسئلة بالكلمات المفتاحية + مطابقة تقريبية لأسماء المواد،
والإجابات كلها محسوبة من نفس محرك التطبيق (المعدل، الخطة، المتطلبات، هدف المعدل)."""
import difflib
import re
from functools import lru_cache

import engine as E
import law

_DIAC = re.compile('[\u064B-\u065F\u0670\u0640]')
_PUNCT = re.compile(r'[^\w\s.+\-]', re.U)
_INTENT = set('تخرج اتخرج معدل معدلي ساعه ساعات فصل جاي قادم متبقي فاضل باقي شروط لائحه تقدير'.split())
_STOP = set('في من الي على عن ان هل ما ماذا ايه اي انا لو ده دي يا مع او ثم كل بعد قبل هو هي كام عايز عاوز اريد'.split())

SUGGEST = ['معدلي كام؟', 'فاضل لي كام ساعة؟', 'أسجل إيه الفصل الجاي؟', 'إيه أحسن مواد أحسّنها؟',
           'أقصى معدل أوصله كام؟', 'عايز أتخرج بمعدل 3.5', 'مواد الفصل الأول', 'المواد الاختيارية', 'مسارات الاختياري',
           'إيه اللي بيأخّرني؟', 'شروط التخرج', 'إيه هي مرتبة الشرف؟', 'اللائحة']


def norm(s):
    s = str(s).translate(E.AR_DIGITS).lower()
    s = _DIAC.sub('', s)
    for a, b in (('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ٱ', 'ا'), ('ى', 'ي'), ('ة', 'ه'), ('ؤ', 'و'), ('ئ', 'ي'),
                 ('٫', '.'), ('،', ' '), ('؟', ' ')):
        s = s.replace(a, b)
    return _PUNCT.sub(' ', s)


def toks(s):
    out = []
    for t in norm(s).split():
        if t.startswith('ال') and len(t) > 4:
            t = t[2:]
        out.append(t)
    return out


_CN = {c.code: set(toks(c.name)) for c in E.COURSES}
_CODE = {re.sub(r'\s+', '', c.code.lower()): c.code for c in E.COURSES}


def find_courses(text):
    """يرجّع (قايمة مواد مطابقة, هل الرقم اتحدد)."""
    n = norm(text)
    flat = re.sub(r'\s+', '', n)
    for k, code in _CODE.items():           # كود كامل مثل MREn 424 أو mren424
        if k in flat:
            return [E.C[code]], True
    m = re.search(r'\b(\d{3})\b', n)         # رقم المقرر بس: 424
    if m:
        hit = [c for c in E.COURSES if c.code.endswith(m.group(1))]
        if len(hit) == 1:
            return hit, True
    ut = [t for t in toks(text) if t not in _STOP]
    words = {t for t in ut if not t.isdigit() and len(t) >= 3 and t not in _INTENT}
    nums = {t for t in ut if t.isdigit() and len(t) == 1}
    if not words:
        return [], False
    scored = []
    for c in E.COURSES:
        ct = _CN[c.code]
        cw = {t for t in ct if not t.isdigit()}
        if not cw:
            continue
        hit = 0.0
        for w in words:
            if w in cw:
                hit += 1
            else:
                best = max((difflib.SequenceMatcher(None, w, x).ratio() for x in cw), default=0)
                if best >= 0.84:
                    hit += best
        if hit < 1:
            continue
        sc = hit / len(words) + 0.01 * hit / len(cw)      # نسبة كلمات سؤالك اللي لقيناها في اسم المادة
        cn = {t for t in ct if t.isdigit()}
        if nums and cn:
            sc += 0.5 if (nums & cn) else -0.3
        scored.append((sc, c))
    if not scored:
        return [], False
    scored.sort(key=lambda x: -x[0])
    top = scored[0][0]
    if top < 0.6:
        return [], False
    best = [c for sc, c in scored if sc >= top - 0.01]
    return best[:5], bool(nums) and len(best) == 1 or len(best) == 1


def _gpa_parts(p):
    an = p['an']
    if an.get('gpa_calc') is not None:
        return an['gpa_calc'] * an['gpa_hours'], an['gpa_hours']
    if an.get('gpa') is not None:
        h = float(sum(c.cr for c in E.COURSES if p['st'].passed(c.code)))
        return an['gpa'] * h, h
    return 0.0, 0.0


def _status(c, st):
    s = st.s(c.code)
    if s == 'done':
        g = st.g(c.code)
        return 'راسب (F)' if g == 'F' else ('خلّصتها' + (' بتقدير %s' % g if g else ''))
    if s == 'cur':
        return 'بتدرسها الآن'
    return 'لسه ما أخدتهاش'


def _term_credits(t):
    return sum(E.C[x].cr for x in t['codes'])


# ───────────── الإجابات ─────────────
def a_gpa(p):
    an = p['an']
    g = an['gpa']
    if g is None:
        return 'لسه مفيش تقديرات مدخلة. ادخل تقديراتك في «موادي» أو اكتب معدلك في «بياناتي» وأحسبهولك.'
    L = ['معدلك التراكمي: %.3f%s' % (g, ' (على %d ساعة)' % an['gpa_hours'] if an['gpa_hours'] else ' (مدخل يدوي)')]
    if an['probation']:
        L.append('⚠ معدلك أقل من 2.00 — إنت تحت الملاحظة والحد الأقصى للتسجيل %d ساعة.' % E.PROBATION_LOAD)
    elif g >= 3.3 and not an['fail']:
        L.append('✔ إنت في نطاق مرتبة الشرف (3.3 فأكثر بشرط عدم الرسوب في أي مقرر).')
    elif g >= 3.3:
        L.append('معدلك في نطاق الشرف لكن الرسوب في مقرر بيمنع مرتبة الشرف.')
    else:
        L.append('ناقصك %.3f نقطة عشان توصل لحد مرتبة الشرف (3.3).' % (3.3 - g))
    if an['fail']:
        L.append('راسب في: ' + '، '.join(c.name for c in an['fail']))
    return '\n'.join(L)


def a_grad(p):
    an, my = p['an'], p['my']
    done_h = an['counted'] + an['cur_hours']
    L = ['منجز %d ساعة من %d (%d%%) — فاضل %d ساعة.' % (done_h, E.TOTAL_REQUIRED, 100 * done_h // E.TOTAL_REQUIRED, an['remaining'])]
    if my is not None:
        if my['terms']:
            L.append('التخرج المتوقع: %s بعد %d فصل.' % (my['finish_label'], my['n_terms']))
        else:
            L.append('خلّصت متطلبات الخطة — راجع شروط التخرج (التدريب والمعدل).')
    return '\n'.join(L)


def a_next(p):
    my = p['my']
    if not my or not my['terms']:
        return 'مفيش مواد متبقية في الخطة الحالية.'
    t = my['terms'][0]
    L = ['الفصل الجاي (%s) — %d ساعة:' % (t['label'], _term_credits(t))]
    for code in t['codes']:
        c = E.C[code]
        L.append('• %s (%d)%s' % (c.name, c.cr, ' — إعادة' if p['st'].failed(code) else ''))
    L.append('تفاصيل أكتر وبدائل في تبويب «خطتي».')
    return '\n'.join(L)


def a_diag(p):
    kind = {'ok': '✔ ', 'warn': '⚠ ', 'bad': '✘ ', 'info': '• '}
    return '\n'.join(kind.get(k, '• ') + m for k, m in p['diag']) or 'مفيش حاجة بتأخّرك.'


def a_check(p):
    sym = {'ok': '✔', 'no': '✘', 'unk': '؟', 'wait': '…'}
    return '\n'.join('%s %s — %s' % (sym.get(s, '•'), t, d) for t, s, d in p['check'])


def a_course(c, p):
    st, cfg = p['st'], p['cfg']
    L = ['%s (%s)' % (c.name, c.code),
         '%d ساعة • %s • %s • الفصل المقترح %s' % (c.cr, 'إجباري' if c.kind == 'R' else 'اختياري', E.KIND_TXT[c.grp], c.sem or '—'),
         'حالتك: ' + _status(c, st)]
    pre = E.pre_of(c.code, cfg)
    if pre:
        L.append('المتطلبات السابقة:')
        for x in pre:
            L.append('  %s %s' % ('✔' if st.satisfied(x) else '✘', E.C[x].name))
    else:
        L.append('مفيش متطلبات سابقة.')
    nxt = [d.name for d in E.COURSES if c.code in E.pre_of(d.code, cfg)]
    if nxt:
        L.append('بتفتح لك: ' + '، '.join(nxt))
    if not st.passed(c.code) and not st.cur(c.code):
        row = [r for cc, r in p['elig'] if cc.code == c.code]
        if row:
            L.append('تقدر تسجلها دلوقتي ✔' if not row[0] else 'مش متاحة دلوقتي: ' + ' / '.join(row[0]))
    return '\n'.join(L)


def a_prereq(c, p):
    pre = E.pre_of(c.code, p['cfg'])
    if not pre:
        return '%s مالهاش متطلبات سابقة.' % c.name
    return 'متطلبات %s:\n' % c.name + '\n'.join('%s %s' % ('✔' if p['st'].satisfied(x) else '✘', E.C[x].name) for x in pre)


_LETTER = re.compile(r'(?<![a-z])([abcdf][+-]?)(?![a-z])')


def a_whatif(c, letter, p):
    pts = E.GRADES.get(letter.upper())
    if pts is None:
        return 'التقدير غير معروف. المتاح: ' + ' '.join(E.GRADE_LIST)
    num, den = _gpa_parts(p)
    st = p['st']
    if st.s(c.code) == 'done' and st.g(c.code) in E.GRADES:     # إعادة/تحسين: شيل التقدير القديم
        num -= E.GRADES[st.g(c.code)] * c.cr
        den -= c.cr
    if st.failed(c.code):
        pts = min(pts, E.RETAKE_CAP)
    new = (num + pts * c.cr) / (den + c.cr) if den + c.cr else None
    now = p['an']['gpa']
    out = 'لو جبت %s في %s (%d ساعة) معدلك هيبقى %.3f' % (letter.upper(), c.name, c.cr, new)
    if now is not None:
        out += ' بدل %.3f (%+.3f).' % (now, new - now)
    if st.failed(c.code):
        out += '\n(الراسب بيتحسب له C كحد أقصى عند الإعادة)'
    return out


def a_goal(target, p):
    r = E.goal_plan(p, target)
    if r['empty']:
        return 'مفيش مواد متبقية — معدلك النهائي %s.' % ('%.3f' % r['base_gpa'] if r['base_gpa'] is not None else '—')
    if not r['feasible']:
        return 'مش ممكن توصل %.3f — أقصى معدل %.3f لو جبت أعلى تقدير في كل الباقي.' % (target, r['max_gpa'])
    dist = {}
    for it in r['items']:
        n, h = dist.get(it['letter'], (0, 0))
        dist[it['letter']] = (n + 1, h + it['cr'])
    parts = ['%s في %d مادة' % (l, dist[l][0]) for l, _g in reversed(E.GRADE_STEPS) if l in dist]
    return ('ممكن توصل %.3f ✔\nمحتاج متوسط حوالي %.3f في باقي المواد (%d مادة = %d ساعة).\nالتوزيع: %s.\n'
            'تفاصيل كل مادة في «خطتي ← هدف المعدل».') % (target, r['need_avg'], r['n'], r['hours'], '، '.join(parts))



# ───────────── أسئلة بيانات الكتالوج والتحسين ─────────────
_ORD = {'اول': 1, 'ثاني': 2, 'تاني': 2, 'ثالث': 3, 'رابع': 4, 'خامس': 5, 'سادس': 6, 'سابع': 7, 'ثامن': 8, 'تامن': 8,
        'تاسع': 9, 'عاشر': 10, 'تالت': 3, 'تلات': 3}
_GRP = [('univ', ('جامعه', 'جامعة')), ('college', ('كليه',)), ('major', ('رئيسي', 'تخصص')), ('sub', ('فرعي', 'ميكاترونيكس', 'ميكاترونيات'))]


def _sem_of(n, raw):
    m = re.search(r'(?:فصل|ترم|سمستر|semester|term)\D{0,6}(\d{1,2})', n)
    if m:
        return int(m.group(1))
    if _has(n, 'فصل', 'ترم', 'سمستر'):
        for t in toks(raw):
            if t in _ORD:
                return _ORD[t]
    return None


def _lst(courses, st=None, limit=18):
    L = []
    for c in courses[:limit]:
        tag = ''
        if st is not None:
            s_ = st.s(c.code)
            tag = ' ✔' if (s_ == 'done' and not st.failed(c.code)) else (' ⏳' if s_ == 'cur' else (' ✘' if st.failed(c.code) else ''))
        L.append('• %s (%d)%s' % (c.name, c.cr, tag))
    if len(courses) > limit:
        L.append('… و%d مادة كمان' % (len(courses) - limit))
    return '\n'.join(L)


def a_sem(k, p):
    cs = [c for c in E.COURSES if c.sem == k and c.kind == 'R']
    if not cs:
        return 'مفيش مواد إجبارية مقترحة للفصل %d.' % k
    return 'مواد الفصل %d الإجبارية (%d ساعة) — ✔ خلّصتها ⏳ بتدرسها:\n%s' % (k, sum(c.cr for c in cs), _lst(cs, p['st']))


def a_group(grp, kind, p):
    cs = [c for c in E.COURSES if c.grp == grp and (kind is None or c.kind == kind)]
    nm = E.GROUP_NAME[grp] + (' — اختياري' if kind == 'E' else (' — إجباري' if kind == 'R' else ''))
    return '%s (%d مادة، %d ساعة):\n%s' % (nm, len(cs), sum(c.cr for c in cs), _lst(cs, p['st'], 22))


def a_groups(p):
    L = []
    for g, info in p['an']['groups'].items():
        line = '%s: إجباري %d/%d ساعة' % (E.GROUP_NAME[g], info['req_done'], info['req_total'])
        if 'e_min' in info:
            line += ' • اختياري %d/%d' % (min(info['e_done'], info['e_min']), info['e_min'])
            if info['e_need']:
                line += ' (ناقص %d)' % info['e_need']
        L.append('• ' + line)
    return 'تقدمك في كل مجموعة:\n' + '\n'.join(L)


def a_req_left(p):
    left = p['an']['req_left']
    if not left:
        return 'خلّصت كل الإجباري ✔'
    return 'الإجباري المتبقي (%d مادة، %d ساعة):\n%s' % (len(left), sum(c.cr for c in left), _lst(left, p['st'], 25))


def a_tracks(p):
    st = p['st']
    need = {g for g, i in p['an']['groups'].items() if i.get('e_need', 0) > 0}
    if not need:
        return 'خلّصت الاختياري المطلوب في كل الفئات ✔ — مفيش مسارات هتتقترح.'
    L = ['مسارات الاختياري (اقتراح من البرنامج، كل مسار بيكمّل ١٧٥ ساعة بالظبط):']
    for key, name, desc, codes in E.TRACKS:
        el = [c for c in codes if c in E.C and E.C[c].kind == 'E']
        todo = [c for c in el if not (st.passed(c) or st.cur(c)) and E.C[c].grp in need]
        if not todo:
            continue                      # المسار ده خلصته أو فئاته خلصت
        L.append('• %s — %s (أخدت %d من %d)' % (name, desc, len(el) - len(todo), len(el)))
    L.append('المقارنة والبدائل في «خطتي ← المسارات».')
    return '\n'.join(L)


def a_chain(c, p):
    seen, order = set(), []

    def go(code):
        for x in E.pre_of(code, p['cfg']):
            if x not in seen:
                seen.add(x)
                go(x)
                order.append(x)
    go(c.code)
    if not order:
        return '%s مالهاش متطلبات سابقة.' % c.name
    return 'سلسلة المتطلبات لحد %s (من الأول للآخر):\n' % c.name + '\n'.join(
        '%d. %s %s' % (i + 1, E.C[x].name, '✔' if p['st'].satisfied(x) else '✘') for i, x in enumerate(order))


def a_stats(p):
    st = p['st']
    rows = [(E.GRADES[st.g(c.code)], c) for c in E.COURSES if st.s(c.code) == 'done' and st.g(c.code) in E.GRADES]
    if not rows:
        return 'لسه مفيش تقديرات مدخلة.'
    rows.sort(key=lambda x: (-x[0], x[1].code))
    best = rows[:3]
    worst = sorted(rows, key=lambda x: (x[0], x[1].code))[:3]
    cnt = {}
    for _v, c in rows:
        cnt[st.g(c.code)] = cnt.get(st.g(c.code), 0) + 1
    dist = '، '.join('%s×%d' % (l, cnt[l]) for l, _g in reversed(E.GRADE_STEPS) if l in cnt)
    if 'F' in cnt:
        dist += '، F×%d' % cnt['F']
    return ('خلّصت %d مادة بتقدير.\nتوزيع تقديراتك: %s\nأعلى: %s\nأضعف: %s'
            % (len(rows), dist, '، '.join('%s (%s)' % (c.name, st.g(c.code)) for _v, c in best),
               '، '.join('%s (%s)' % (c.name, st.g(c.code)) for _v, c in worst)))


def a_plan_all(p):
    my = p['my']
    if not my or not my['terms']:
        return 'مفيش خطة متبقية.'
    L = ['خطتك لحد التخرج (%s):' % my['finish_label']]
    for t in my['terms']:
        L.append('• %s: %d ساعة — %d مواد' % (t['label'], _term_credits(t), len(t['codes'])))
    L.append('تفاصيل كل فصل في «خطتي».')
    return '\n'.join(L)


def a_elig(p):
    ok = [c for c, why in p['elig'] if not why and not p['st'].passed(c.code) and not p['st'].cur(c.code)]
    if not ok:
        return 'مفيش مواد متاحة دلوقتي (مراجعة المتطلبات السابقة).'
    return 'مواد تقدر تسجلها دلوقتي (%d):\n%s' % (len(ok), _lst(ok, None, 20))


def a_improve_rank(p, letter='A'):
    rk = E.improve_rank(p, letter)
    if not rk:
        return 'مفيش مواد تقدر تحسّنها (كلها A أو لسه مفيش تقديرات).'
    L = ['أكتر مواد تفرق في معدلك لو حسّنتها لـ %s:' % letter]
    for r in rk[:6]:
        L.append('• %s (%s ← %s): %+.3f' % (r['name'], r['old_l'], letter, r['gain']))
    L.append('جرّب نظام التحسين في «خطتي ← التحسين» واختار المواد بنفسك.')
    return '\n'.join(L)


def a_max(p):
    r = E.improve_calc(p, {})
    if r.get('none'):
        return 'ادخل تقديراتك الأول عشان أحسب أقصى معدل.'
    L = ['معدلك الحالي %.3f.' % r['now'], 'أقصى معدل لو حسّنت كل موادك لـ A: %.3f' % r['max_now']]
    if r['pending_hours']:
        L.append('وبعد ما تخلّص باقي الخطة (%d ساعة) بأعلى تقدير: من غير تحسين %.3f، ولو حسّنت كل حاجة %.3f.'
                 % (r['pending_hours'], r['final_no_improve'], r['final_all_a']))
    return '\n'.join(L)


def a_points():
    return 'نقاط التقدير:\n' + ' • '.join('%s = %.1f' % (l, g) for l, g in reversed(E.GRADE_STEPS)) + ' • F = 0'


def a_load(p):
    prob = p['an']['probation']
    return ('الحد الأقصى للتسجيل: %d ساعة في الخريف/الربيع و%d ساعات في الصيفي.%s'
            % (E.MAX_LOAD_DEFAULT, E.SUMMER_MAX, '\n⚠ إنت تحت الملاحظة فالحد %d ساعة.' % E.PROBATION_LOAD if prob else ''))


def a_electives(p):
    L = ['الاختياري المطلوب: جامعة %d + تخصص رئيسي %d + تخصص فرعي %d = %d ساعة.' % (
        E.ELEC_MIN['univ'], E.ELEC_MIN['major'], E.ELEC_MIN['sub'], sum(E.ELEC_MIN.values()))]
    for g, info in p['an']['groups'].items():
        if 'e_min' in info:
            L.append('• %s: أخدت %d من %d%s' % (E.GROUP_NAME[g], min(info['e_done'], info['e_min']), info['e_min'],
                                                 (' — ناقص %d' % info['e_need']) if info['e_need'] else ' ✔'))
    return '\n'.join(L)


# ───────────── قواعد اللائحة ─────────────
def _rules():
    out, cur = [], ''
    for ln in E.RULES_TEXT.splitlines():
        if ln.startswith('•'):
            if cur:
                out.append(cur)
            cur = ln[1:].strip()
        elif ln.startswith('  ') and cur:
            cur += ' ' + ln.strip()
        else:
            if cur:
                out.append(cur)
            cur = ''
    if cur:
        out.append(cur)
    return out


_RULES = _rules()
_SYN = {'غياب': 'حضور', 'حمل': 'ساعات', 'اعاده': 'اعيد', 'رسوب': 'راسب', 'امتياز': 'شرف', 'سنين': 'سنوات'}


def a_rules(text):
    q = {_SYN.get(t, t) for t in toks(text) if t not in _STOP and len(t) >= 3}
    best = []
    for r in _RULES:
        rt = set(toks(r))
        sc = sum(1 for t in q if any(t == x or (len(t) >= 4 and len(x) >= 4 and (t in x or x in t)) for x in rt))
        if sc:
            best.append((sc, r))
    best.sort(key=lambda x: -x[0])
    if not best:
        return None
    return '\n'.join('• ' + r for _s, r in best[:2])




# ───────────── إدخال المواد بالكتابة/الصوت (إدخال سريع) ─────────────
_NUMW = {'واحد': '1', 'اولي': '1', 'اول': '1', 'اتنين': '2', 'اثنين': '2', 'تاني': '2', 'ثاني': '2', 'تانيه': '2', 'ثانيه': '2',
         'ثلاثه': '3', 'تلاته': '3', 'ثالث': '3', 'تالت': '3', 'اربعه': '4', 'رابع': '4', 'خمسه': '5', 'خامس': '5'}
_VOCAB = None


def _vocab():
    global _VOCAB
    if _VOCAB is None:
        _VOCAB = {t for c in E.COURSES for t in toks(c.name) if not t.isdigit() and len(t) >= 3}
    return _VOCAB


def _is_word(w):
    v = _vocab()
    if w in v:
        return True
    return len(w) >= 4 and any(difflib.SequenceMatcher(None, w, x).ratio() >= 0.84 for x in v)


def split_phrases(raw):
    """يقسّم الكلام لمواد: بالفاصلة وبكلمة «و» («فيزياء وكيمياء» / «فيزياء و كيمياء»)."""
    out = []
    for piece in re.split(r'[,،؛;\n+]+', str(raw)):
        cur = []
        for w in piece.split():
            wn = norm(w).strip()
            if wn == 'و':
                if cur:
                    out.append(' '.join(cur))
                cur = []
                continue
            if len(wn) > 1 and wn.startswith('و') and wn[1:].isdigit():
                if cur:
                    out.append(' '.join(cur))
                cur = [wn[1:]]
                continue
            if len(wn) > 3 and wn.startswith('و') and (wn[1:] in _vocab() or (not _is_word(wn) and _is_word(wn[1:]))):
                if cur:
                    out.append(' '.join(cur))
                cur = [wn[1:]]
                continue
            cur.append(w)
        if cur:
            out.append(' '.join(cur))
    return [x for x in out if x.strip()]


def _numw(text):
    return ' '.join(_NUMW.get(t, t) if t in _NUMW else t for t in norm(text).split())


def find_many(raw):
    """يفهم جملة زي «فيزياء ١ و رياضيات ٢ وكيمياء» أو «خلصت لحد الفصل 4» أو «كل مواد الفصل 2 بتقدير B».
    يرجّع: sure (متأكد منها) / ambig (مواد ممكن تكون المقصودة) / unknown (ما لقيتهاش) / grade / upto / sems."""
    raw = str(raw)
    n = norm(raw)
    res = {'sure': [], 'ambig': [], 'unknown': [], 'grade': None, 'upto': None, 'sems': []}
    lm = _LETTER.search(raw.lower().translate(E.AR_DIGITS))
    if lm and lm.group(1).upper() in E.GRADES:
        res['grade'] = lm.group(1).upper()
    m = re.search(r'(?:لحد|حتي|الي|لغايه)\D{0,12}?(?:فصل|ترم)\D{0,6}?(\d{1,2})', n)
    if m:
        res['upto'] = int(m.group(1))
    else:
        m2 = re.search(r'(?:لحد|حتي|لغايه)\s+(?:الفصل|فصل|ترم|الترم)\s+(\S+)', n)
        if m2:
            g_ = m2.group(1)
            g_ = g_[2:] if g_.startswith('ال') else g_
            if g_ in _ORD:
                res['upto'] = _ORD[g_]
    if res['upto'] is None and _has(n, 'كل مواد', 'كل مقررات', 'كل') and _has(n, 'فصل', 'ترم'):
        k = _sem_of(n, raw)
        if k:
            res['sems'].append(k)
    if res['upto'] is not None or res['sems']:
        return res
    prev = ''
    seen = set()
    for ph in split_phrases(raw):
        txt = _numw(ph)
        words = [t for t in txt.split() if not t.isdigit()]
        if not words and prev:                       # «فيزياء 1 و 2» → الجزء الثاني بيورّث الاسم
            txt = prev + ' ' + txt
        courses, exact = find_courses(txt)
        if not courses and not words:
            continue
        if not courses:
            cand = rank_courses(txt, limit=5, floor=0.6)       # مفيش تطابق بالظبط → أقرب المواد وانت تختار
            grp = [c.code for s, c in cand if c.code not in seen]
            if grp:
                res['ambig'].append(grp)
                seen.update(grp)
            else:
                res['unknown'].append(ph)
            continue
        prev = ' '.join(t for t in txt.split() if not t.isdigit())
        if len(courses) == 1 or exact:
            if courses[0].code not in seen:
                res['sure'].append(courses[0].code)
                seen.add(courses[0].code)
        else:
            grp = [c.code for c in courses if c.code not in seen]
            if grp:
                res['ambig'].append(grp)
                seen.update(grp)
    return res


# ───────────── مطابقة تقريبية (للصوت والبحث والصور) ─────────────
# تشابه الحروف: «نقط» (ب ت ث ن ي / ج ح خ ...) بيلخبط الخط اليد والـOCR، و«نطق» (ث/س ، ذ/ز ، ق/ك ...) بيلخبط الصوت
_DOT = str.maketrans('تثنيجخذزشضظغق', 'ببببححدرسصطعف')
_PHO = str.maketrans('ثذظضطصقعحغء', 'سززدتسكاهخا')
_CW = {c.code: [t for t in toks(c.name) if not t.isdigit()] for c in E.COURSES}
_CD = {c.code: {t for t in toks(c.name) if t.isdigit()} for c in E.COURSES}


@lru_cache(maxsize=65536)
def _wr(a, b):
    r = difflib.SequenceMatcher(None, a, b).ratio()
    d = difflib.SequenceMatcher(None, a.translate(_DOT), b.translate(_DOT)).ratio() * 0.94
    p = difflib.SequenceMatcher(None, a.translate(_PHO), b.translate(_PHO)).ratio() * 0.94
    return max(r, d, p)


def rank_courses(text, limit=6, floor=0.5, pool=None):
    """أقرب المواد لكلامك حتى لو الحروف مش مظبوطة: [(درجة 0..1, مادة)] مرتبة."""
    ut = [t for t in toks(_numw(text)) if t not in _STOP]
    words = [t for t in ut if not t.isdigit() and len(t) >= 2]
    nums = {t for t in ut if t.isdigit() and len(t) <= 2}
    if not words:
        return []
    qj = ''.join(words)
    out = []
    for c in (pool if pool is not None else E.COURSES):
        cw = _CW.get(c.code)
        if not cw:
            continue
        per = sum(max(_wr(w, x) for x in cw) for w in words) / len(words)      # كل كلمة من كلامك لأقرب كلمة في الاسم
        cover = sum(max(_wr(w, x) for w in words) for x in cw) / len(cw)       # وكمان كلمات الاسم اللي اتذكرت
        sc = max(0.7 * per + 0.3 * cover, _wr(qj, ''.join(cw)) * 0.97)
        cn = _CD.get(c.code)
        if nums and cn:
            sc += 0.12 if (nums & cn) else -0.15
        if sc >= floor:
            out.append((min(sc, 1.0), c))
    out.sort(key=lambda x: (-x[0], x[1].sem or 99, x[1].code))
    return out[:limit]


_CODE_RX = re.compile(r'([a-z]{2,6})\s*[-_.]?\s*(\d{3})')


def _code_hits(line):
    n = norm(line)
    flat = re.sub(r'\s+', '', n)
    found = [code for k, code in _CODE.items() if k in flat]
    for m in _CODE_RX.finditer(n):
        pre, dg = m.group(1), m.group(2)
        hit = [c for c in E.COURSES if c.code.endswith(dg)]
        if not hit:
            continue
        best = max(hit, key=lambda c: difflib.SequenceMatcher(None, pre, re.match(r'[A-Za-z]+', c.code).group(0).lower()).ratio())
        r = difflib.SequenceMatcher(None, pre, re.match(r'[A-Za-z]+', best.code).group(0).lower()).ratio()
        if r >= (0.5 if len(hit) == 1 else 0.6) and best.code not in found:
            found.append(best.code)
    return found


def find_in_text(raw):
    """نص طالع من صورة (OCR): كل سطر (وكل عمود جواه) → كود مادة أو أقرب أسماء. بيتجاهل السطور اللي مالهاش علاقة.
    sure = متأكد، likely = أقرب مادة بثقة كويسة (بتتعلّم تلقائي وانت تقدر تشيلها)، ambig = أسماء قريبة تختار منها."""
    res = {'sure': [], 'likely': [], 'ambig': [], 'lines': 0}
    seen = set()
    for line in re.split(r'[\r\n]+', str(raw)):
        ln = line.strip()
        if len(ln) < 3:
            continue
        res['lines'] += 1
        codes = [c for c in _code_hits(ln) if c not in seen]
        if codes:
            for c in codes:
                res['sure'].append(c)
                seen.add(c)
            continue
        # صف جدول: أعمدة مفصولة بمسافات كبيرة / | / tab → كل عمود يتقرأ لوحده
        segs = [x.strip() for x in re.split(r'\t|\|{1}|\s{3,}', ln) if len(x.strip()) >= 3]
        for sg in (segs if len(segs) > 1 else [ln]):
            cand = [x for x in rank_courses(sg, limit=4, floor=0.65) if x[1].code not in seen]
            if not cand:
                continue
            top = cand[0][0]
            if top >= 0.93 and (len(cand) == 1 or top - cand[1][0] >= 0.08):
                res['sure'].append(cand[0][1].code)
                seen.add(cand[0][1].code)
                continue
            grp = [c.code for s, c in cand if s >= top - 0.2][:3]
            if not grp:
                continue
            if top >= 0.8 and (len(cand) == 1 or top - cand[1][0] >= 0.04):
                res['likely'].append(grp[0])
                grp = grp[1:]
            if grp:
                res['ambig'].append(grp)
            seen.update([x[1].code for x in cand[:3]])
        if len(res['ambig']) >= 60:
            break
    return res


def ocr_score(raw):
    r = find_in_text(raw)
    return len(r['sure']) + len(r['likely']) + 0.5 * len(r['ambig'])


# ───────────── اللائحة (بنك المعرفة) ─────────────
_LAW = None
_EXPLAIN = ('يعني ايه', 'معني', 'اشرح', 'شرح', 'ازاي', 'كيف', 'قاعده', 'قواعد', 'لايحه', 'قانون', 'بيقول', 'ينفع', 'مسموح',
            'ممنوع', 'يجوز', 'هل', 'ايه هو', 'ايه هي', 'ايه الفرق', 'شروط', 'فهمني', 'وضح', 'اعمل ايه', 'اتصرف', 'لو')


def _law_index():
    global _LAW
    if _LAW is None:
        _LAW = [(t, [norm(k) for k in t['kw']], norm(t['title'])) for t in law.TOPICS]
    return _LAW


def law_match(raw):
    """[(score, topic)] مرتبة. الكلمة المركّبة وزنها أعلى، وعنوان الموضوع بيدّي مكسب."""
    n = ' ' + norm(raw) + ' '
    out = []
    for i, (t, kws, title) in enumerate(_law_index()):
        sc = 0
        for k in kws:
            if k and (' ' + k + ' ' in n or (len(k) >= 4 and k in n)):
                sc += 3 if ' ' in k else 2
        if title and title in n:
            sc += 4
        if sc:
            out.append((sc, -i, t))
    out.sort(key=lambda x: (-x[0], -x[1]))
    return [(sc, t) for sc, _i, t in out]


def a_law(topic, p, more=()):
    txt = '📘 %s\n\n%s' % (topic['title'], topic['body'](p))
    return txt, ['اشرح: ' + t['title'] for t in more[:3]]


def a_law_index():
    L = ['أقدر أشرحلك أي بند في اللائحة. اختار موضوع (أو اسأل بكلامك):']
    for t in law.TOPICS:
        L.append('• ' + t['title'])
    L.append('\nكل شرح بيفرّق بين [لائحة] (منصوص) و[افتراض] (من البرنامج) و[شرح عام].')
    return '\n'.join(L), ['اشرح: ' + t['title'] for t in law.TOPICS[:6]]


# ───────────── الموجّه ─────────────
def _has(n, *words):
    return any(w in n for w in words)


def is_fallback(ans):
    """هل ده رد «مش فاهم»؟ (وقتها ChatGPT يجاوب لو متفعّل)"""
    return str(ans).startswith('مش متأكد فهمت سؤالك')


def answer(text, p):
    """(نص الرد, اقتراحات متابعة)."""
    raw = str(text).strip()
    n = norm(raw)
    if not n.strip():
        return 'اكتب سؤالك وأنا أجاوبك.', SUGGEST
    if _has(n, 'اهلا', 'مرحبا', 'السلام', 'هاي', 'صباح', 'مساء') and len(n.split()) <= 3:
        return 'أهلاً! أنا مساعدك الأكاديمي (بشتغل من غير إنترنت). اسألني عن معدلك أو خطتك أو أي مادة أو اللائحة.', SUGGEST
    if _has(n, 'ساعد', 'تقدر', 'بتعمل', 'بتعرف', 'help', 'ايه الاوامر'):
        return ('أقدر أجاوبك عن:\n• معدلك وحالتك (تحت الملاحظة/الشرف)\n• المتبقي والتخرج المتوقع\n• تسجّل إيه الفصل الجاي\n'
                '• أي مادة: متطلباتها وحالتك فيها\n• «لو جبت A في رياضيات 2 معدلي هيبقى كام؟»\n'
                '• «عايز أتخرج بمعدل 3.5» وأقولك تجيب كام في كل مادة\n• قواعد اللائحة (حضور، صيفي، إعادة...)'), SUGGEST

    courses, exact = find_courses(raw)
    lm = _LETTER.search(raw.lower().translate(E.AR_DIGITS))
    low = raw.translate(E.AR_DIGITS).replace('٫', '.').replace(',', '.')
    nums = [float(x) for x in re.findall(r'(?<![\d.])([1-4](?:\.\d{1,2})?)(?![\d])', low)]
    goal_words = _has(n, 'هدف', 'اتخرج', 'تخرج بمعدل', 'عايز', 'عاوز', 'محتاج', 'اجيب', 'وصل', 'ارفع', 'اوصل', 'شرف')
    cn = [x for x in nums if 1.0 <= x <= 4.0]

    # لو جبت X في مادة
    if lm and courses and _has(n, 'لو', 'اذا', 'جبت', 'اخد', 'هجيب', 'تقدير', 'حسن', 'تحسين', 'اعيد'):
        if len(courses) == 1:
            return a_whatif(courses[0], lm.group(1), p), []
        return 'تقصد أنهي مادة؟ ' + '، '.join(c.name for c in courses), []
    # هدف المعدل
    if goal_words and not courses and not cn and any(x > 4 or x < 1 for x in [float(v) for v in re.findall(r'\d+(?:\.\d+)?', low)]):
        return 'المعدل لازم يكون بين 1 و 4 (مثلاً: عايز أتخرج بمعدل 3.5).', []
    if cn and goal_words and not courses:
        return a_goal(cn[0], p), []
    if lm and goal_words and not courses and E.GRADES.get(lm.group(1).upper()):
        return a_goal(E.GRADES[lm.group(1).upper()], p), []
    # فهرس اللائحة + شرح البنود
    if _has(n, 'فهرس اللايحه', 'كل القواعد', 'مواضيع اللايحه', 'ايه في اللايحه', 'اللايحه') and \
            not any(sc >= 5 for sc, _t in law_match(raw)):
        return a_law_index()
    hits = law_match(raw)
    explain = _has(n, *_EXPLAIN)
    if hits and not (courses and hits[0][0] < 6) and not (_has(n, 'عايز', 'عاوز') and cn) and \
            (hits[0][0] >= 3 or (explain and hits[0][0] >= 2)):
        return a_law(hits[0][1], p, [t for _sc, t in hits[1:4]])
    if _has(n, 'شرف') and goal_words:
        return a_goal(3.3, p), []

    # ───── بيانات الكتالوج والتحسين ─────
    k = _sem_of(n, raw)
    if k and _has(n, 'مواد', 'مقررات', 'ايه', 'اي', 'كام'):
        return a_sem(k, p), []
    gkey = next((g for g, ws in _GRP if any(w in n for w in ws)), None)
    kind = 'E' if _has(n, 'اختيار') else ('R' if _has(n, 'اجبار') else None)
    if gkey and _has(n, 'مواد', 'مقررات', 'ايه', 'اي', 'قايمه') and not _has(n, 'مسار', 'تقدم', 'نسبه'):
        return a_group(gkey, kind, p), []
    if _has(n, 'مسار', 'تراك', 'track'):
        return a_tracks(p), []
    if _has(n, 'اختيار') and _has(n, 'مواد', 'مقررات', 'ساعات', 'كام', 'ناقص', 'فاضل'):
        return a_electives(p), []
    if _has(n, 'تقدم', 'نسبه', 'مجموعه', 'كل قسم'):
        return a_groups(p), []
    if _has(n, 'نقاط', 'نقطه') and _has(n, 'تقدير', 'درجات', 'درجه', 'حرف'):
        return a_points(), []
    if _has(n, 'احسن', 'افضل', 'اكتر', 'اهم') and _has(n, 'حسن', 'تحسين', 'اعيد', 'اعاده'):
        return a_improve_rank(p, lm.group(1).upper() if lm and lm.group(1).upper() in E.GRADES else 'A'), []
    if _has(n, 'اقصي معدل', 'اعلي معدل', 'اقصى معدل', 'اوصل', 'اكبر معدل') and not cn:
        return a_max(p), []
    if _has(n, 'تحسين', 'احسن معدل', 'ارفع معدل') and not courses:
        return a_improve_rank(p), []
    if _has(n, 'متبقي', 'فاضل', 'باقي') and _has(n, 'اجبار'):
        return a_req_left(p), []
    if _has(n, 'متاح', 'اقدر اسجل', 'اسجل ايه دلوقتي'):
        return a_elig(p), []
    if _has(n, 'احصايي', 'ملخص', 'تقديراتي', 'اعلي تقدير', 'اضعف'):
        return a_stats(p), []
    if _has(n, 'الخطه كلها', 'كل الفصول', 'خطتي', 'خطه التخرج', 'فصول متبقيه'):
        return a_plan_all(p), []
    if _has(n, 'اقصي', 'حمل') and _has(n, 'ساعات', 'تسجيل', 'حمل') and not _has(n, 'معدل'):
        return a_load(p), []
    if _has(n, 'مين عمل', 'مطور', 'المطور', 'عن التطبيق', 'مين صنع'):
        return '%s\nالمطوّر: %s\nالمساعد بيشتغل محلياً بدون إنترنت، إلا لو فعّلت ChatGPT من الإعدادات.' % (E.APP_TITLE, E.DEVELOPER), []

    if courses:
        if len(courses) > 1 and not exact:
            return 'تقصد أنهي مادة؟\n' + '\n'.join('• %s (%s)' % (c.name, c.code) for c in courses), []
        c = courses[0]
        if _has(n, 'سلسله', 'كل المتطلبات', 'تسلسل'):
            return a_chain(c, p), []
        if _has(n, 'متطلب', 'prereq', 'محتاج الاول', 'قبل'):
            return a_prereq(c, p), []
        return a_course(c, p), []

    if _has(n, 'راسب', 'رسبت', 'f '):
        f = p['an']['fail']
        return ('راسب في: ' + '، '.join(c.name for c in f) + '\nلازم تعيدها (وبتتحسب C كحد أقصى).') if f else 'مفيش مواد راسب فيها ✔', []
    if _has(n, 'بدرس', 'الحاليه', 'الحالي'):
        cur = p['an']['cur']
        return ('بتدرس دلوقتي:\n' + '\n'.join('• %s (%d)' % (c.name, c.cr) for c in cur)) if cur else 'مفيش مواد معلّمة «بدرسها الآن».', []
    if _has(n, 'معدل', 'gpa', 'تراكمي') and not _has(n, 'شروط'):
        return a_gpa(p), []
    if _has(n, 'شروط', 'شرط', 'متطلبات التخرج', 'اخلص', 'خلصت'):
        return a_check(p), []
    if _has(n, 'صيف'):
        r = a_rules(raw)
        if r:
            return r, []
    if _has(n, 'الفصل الجاي', 'الترم الجاي', 'الفصل القادم', 'اسجل', 'هسجل', 'ادرس ايه', 'اخد ايه', 'اخد اي', 'سجل'):
        return a_next(p), []
    if _has(n, 'ياخر', 'اتاخر', 'تاخير', 'ليه', 'مشكل', 'اخر'):
        return a_diag(p), []
    if _has(n, 'تخرج', 'فاضل', 'متبقي', 'باقي', 'ساعات', 'نسبه', 'انجاز'):
        return a_grad(p), []

    if hits:
        return a_law(hits[0][1], p, [t for _sc, t in hits[1:4]])
    r = a_rules(raw)
    if r:
        return r, []
    return ('مش متأكد فهمت سؤالك 🤔 جرّب تسأل عن: معدلك، المتبقي للتخرج، تسجّل إيه الفصل الجاي، أي مادة بالاسم، '
            'أو «عايز أتخرج بمعدل 3.5».'), SUGGEST
