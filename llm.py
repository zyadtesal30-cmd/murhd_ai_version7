# -*- coding: utf-8 -*-
"""ربط المساعد بنموذج ذكاء اصطناعي (Gemini أو OpenAI) — اختياري تماماً ومقفول افتراضياً.
المفتاح بيدخله الطالب بنفسه (مش جوه التطبيق) وبيتخزّن على الجهاز بس. بنبعت السؤال + (لو الطالب سمح) ملخص بياناته
عشان الرد يبقى مبني على حالته الحقيقية، وأي أرقام لازم تيجي من بيانات التطبيق مش من تخمين الموديل."""
import json
import ssl
import urllib.error
import urllib.request

import engine as E

ENDPOINT = 'https://api.openai.com/v1/chat/completions'
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent'
DEFAULT_MODEL = 'gpt-4o-mini'            # OpenAI
GEMINI_MODEL = 'gemini-3.8-flash'        # Gemini (الاسم بيتغيّر مع الإصدارات — قابل للتعديل من الإعدادات)
PROVIDERS = [('gemini', 'Google Gemini (حساب Gmail)'), ('openai', 'OpenAI / ChatGPT')]
HISTORY_TURNS = 8


def provider(cfg):
    return 'openai' if str((cfg or {}).get('ai_provider', 'gemini')) == 'openai' else 'gemini'


def model_for(cfg):
    """اسم الموديل المناسب للمزوّد الحالي (لو الاسم المحفوظ لمزوّد تاني بنرجع للافتراضي)."""
    m = str((cfg or {}).get('ai_model') or '').strip()
    if provider(cfg) == 'gemini':
        return m if m.lower().startswith('gemini') else GEMINI_MODEL
    return m if m and not m.lower().startswith('gemini') else DEFAULT_MODEL


def enabled(cfg):
    return bool(cfg.get('ai_on')) and len(str(cfg.get('ai_key', '')).strip()) >= 20


def _ctx():
    try:
        import certifi      # شهادات الأمان (أندرويد مش بيوفّرها لبايثون)
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:      # noqa
        return ssl.create_default_context()


def snapshot(p, local_answer=''):
    """ملخص بيانات الطالب كنص للموديل (من نتيجة محرك التطبيق)."""
    L = []
    try:
        an, my, st = p['an'], p['my'], p['st']
        done_h = an['counted'] + an['cur_hours']
        L.append('المعدل التراكمي: ' + ('%.3f' % an['gpa'] if an['gpa'] is not None else 'غير محسوب (مفيش تقديرات)'))
        L.append('الساعات: %d منجزة (شاملة اللي بيدرسها دلوقتي) من %d مطلوبة، والمتبقي %d ساعة' % (done_h, E.TOTAL_REQUIRED, an['remaining']))
        if an.get('probation'):
            L.append('الطالب تحت الملاحظة الأكاديمية (معدل أقل من 2.00)')
        if my:
            L.append('التخرج المتوقع: ' + ('خلّص الخطة' if not my['terms'] else '%s (فصول متبقية: %d)' % (my['finish_label'], my['n_terms'])))
        if an.get('fail'):
            L.append('راسب في: ' + '، '.join(c.name for c in an['fail']))
        if an.get('cur'):
            L.append('بيدرس دلوقتي: ' + '، '.join(c.name for c in an['cur']))
        passed = ['%s(%s)' % (c.name, st.g(c.code) or 'بدون تقدير') for c in E.COURSES if st.passed(c.code)]
        L.append('مواد خلّصها: ' + ('، '.join(passed) if passed else 'لسه مفيش'))
        left = [c.name for c in E.COURSES if c.kind == 'R' and not st.passed(c.code) and not st.cur(c.code)]
        L.append('الإجباري المتبقي (%d): %s' % (len(left), '، '.join(left[:60])))
        L.append('شروط التخرج: ' + ' | '.join('%s: %s' % (t, d) for t, _s, d in p['check']))
    except Exception:      # noqa
        pass
    if local_answer:
        L.append('إجابة محسوبة من محرك التطبيق (مرجع موثوق للأرقام):\n' + local_answer[:1800])
    return '\n'.join(L)[:6500]


_KB = {}


def catalog():
    """كل مواد الخطة (الكود/الاسم/الساعات/الفصل/النوع/المتطلبات) — نفس اللي بيعرفه المساعد المحلي."""
    if 'cat' not in _KB:
        L = []
        for c in E.COURSES:
            pre = '، '.join(E.C[x].name for x in c.pre if x in E.C)
            L.append('%s | %s | %dس | %s | %s%s' % (
                c.code, c.name, c.cr, E.GROUP_NAME.get(c.grp, c.grp) + (' (إجباري)' if c.kind == 'R' else ' (اختياري)'),
                ('فصل %d' % c.sem) if c.sem else 'بدون فصل محدد', (' | يحتاج: ' + pre) if pre else ''))
        _KB['cat'] = 'كل مواد الخطة (كود | اسم | ساعات | المجموعة | الفصل | المتطلب السابق):\n' + '\n'.join(L)
    return _KB['cat']


def law_text(p=None):
    """بنك اللائحة كامل (٢٦ موضوع) بنفس الشرح اللي المساعد المحلي بيجاوب بيه. بيتحسب كل مرة عشان فيه وضع الطالب الحالي."""
    if p is None:
        return ''
    try:
        import law
    except Exception:      # noqa
        return ''
    parts = []
    for t in law.TOPICS:
        try:
            body = str(t['body'](p)).strip()
        except Exception:      # noqa
            body = ''
        if body:
            parts.append('## ' + t['title'] + '\n' + body)
    return '\n\n'.join(parts)


def level_of(cfg):
    return 'full' if str((cfg or {}).get('ai_level', 'lite')) == 'full' else 'lite'


def _lite_snapshot(p, local_answer=''):
    """ملخص مختصر جداً (أرقام أساسية بس) عشان استهلاك الطلب يبقى قليل."""
    L = []
    try:
        an, my = p['an'], p['my']
        L.append('المعدل: ' + ('%.3f' % an['gpa'] if an['gpa'] is not None else 'غير محسوب'))
        L.append('المتبقي: %d ساعة من %d' % (an['remaining'], E.TOTAL_REQUIRED))
        if an.get('probation'):
            L.append('تحت الملاحظة')
        if my and my['terms']:
            L.append('التخرج المتوقع: ' + str(my['finish_label']))
    except Exception:      # noqa
        pass
    if local_answer:
        L.append('إجابة التطبيق:\n' + local_answer[:700])
    return '\n'.join(L)[:1000]


def build_messages(text, history, p=None, share=True, local_answer='', level='full'):
    if level == 'lite':
        msgs = [{'role': 'system', 'content': 'أنت مساعد أكاديمي في تطبيق «مرشد الطالب» (هندسة الميكاترونيات). رد بالعامية المصرية باختصار شديد. '
                                              'لا تخترع أرقام أو مواد؛ لو مش متأكد انصح بمراجعة المرشد الأكاديمي.'}]
        if share and p is not None:
            msgs.append({'role': 'system', 'content': _lite_snapshot(p, local_answer)})
        for role, t in list(history)[-4:]:
            msgs.append({'role': 'user' if role == 'u' else 'assistant', 'content': str(t)[:500]})
        msgs.append({'role': 'user', 'content': str(text)[:1000]})
        return msgs
    sysmsg = ('أنت مساعد أكاديمي ذكي جوه تطبيق «مرشد الطالب» لطالب هندسة الميكاترونيات. رد بالعامية المصرية المبسطة وباختصار ووضوح. '
              'اعتمد على بيانات الطالب ولائحة القسم المرفقة كمرجع وحيد للأرقام والمواد والقواعد، ولا تخترع مواد أو أرقام أو بنود لائحة مش موجودة. '
              'لو المعلومة مش موجودة قول إنك مش متأكد وانصحه يراجع المرشد الأكاديمي. تقدر تشرح وتقارن وتنصح وتساعد في تخطيط الفصول والتحسين.\n\n'
              'عندك نفس معرفة المساعد المحلي بالظبط: كتالوج المواد الكامل وبنك اللائحة وحالة الطالب، وكمان إجابة المساعد المحلي على نفس السؤال '
              '(لو اتبعتت) — اعتبرها مرجع الأرقام والحسابات، وانت تكمّل عليها بالشرح والمقارنة والنصيحة وتخطيط الفصول. '
              'لو الطالب سأل عن مادة اتكلم عليها، دوّر عنها في الكتالوج بالاسم أو الكود حتى لو كتبها بشكل تقريبي.\n\n'
              'ملخص اللائحة:\n' + str(E.RULES_TEXT)[:3500])
    msgs = [{'role': 'system', 'content': sysmsg}, {'role': 'system', 'content': catalog()}]
    lt = law_text(p) if p is not None else ''
    if lt:
        msgs.append({'role': 'system', 'content': 'بنك اللائحة التفصيلي (المصدر: المساعد المحلي):\n' + lt[:9000]})
    if share and p is not None:
        msgs.append({'role': 'system', 'content': 'بيانات الطالب الحالية:\n' + snapshot(p, local_answer)})
    for role, t in list(history)[-HISTORY_TURNS:]:
        msgs.append({'role': 'user' if role == 'u' else 'assistant', 'content': str(t)[:2000]})
    msgs.append({'role': 'user', 'content': str(text)})
    return msgs


def _gemini_body(messages):
    sys_txt, contents = [], []
    for m in messages:
        if m['role'] == 'system':
            sys_txt.append(m['content'])
            continue
        role = 'user' if m['role'] == 'user' else 'model'
        if contents and contents[-1]['role'] == role:
            contents[-1]['parts'][0]['text'] += '\n' + m['content']
        else:
            contents.append({'role': role, 'parts': [{'text': m['content']}]})
    body = {'contents': contents}
    if sys_txt:
        body['systemInstruction'] = {'parts': [{'text': '\n\n'.join(sys_txt)}]}
    return body


def chat(key, model, messages, timeout=60, url=None, prov='openai'):
    """بترجّع نص الرد، أو بترفع RuntimeError برسالة عربي مفهومة. prov = 'openai' أو 'gemini'."""
    key = str(key).strip()
    if prov == 'gemini':
        url = url or (GEMINI_URL % (model or GEMINI_MODEL))
        body = json.dumps(_gemini_body(messages)).encode('utf-8')
        headers = {'Content-Type': 'application/json', 'x-goog-api-key': key}
    else:
        url = url or ENDPOINT
        body = json.dumps({'model': model or DEFAULT_MODEL, 'messages': messages}).encode('utf-8')
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}
    req = urllib.request.Request(url, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            d = json.loads(r.read().decode('utf-8'))
        if prov == 'gemini':
            parts = d['candidates'][0]['content']['parts']
            return ''.join(str(x.get('text', '')) for x in parts).strip() or 'مفيش رد.'
        return str(d['choices'][0]['message']['content']).strip()
    except urllib.error.HTTPError as e:
        msg = ''
        try:
            msg = json.loads(e.read().decode('utf-8')).get('error', {}).get('message', '')
        except Exception:      # noqa
            pass
        if e.code == 401 or (prov == 'gemini' and e.code in (400, 403) and 'api key' in msg.lower()):
            raise RuntimeError('المفتاح غلط أو متوقف. تأكد منه في الإعدادات.')
        if e.code == 429:
            if prov == 'gemini':
                raise RuntimeError('وصلت للحد المسموح من جوجل (طلبات كتير). استنى شوية وجرّب تاني.')
            raise RuntimeError('الطلبات كتير أو رصيد الـAPI خلص. (اشتراك ChatGPT Plus مش بيشمل رصيد الـAPI، ده حساب منفصل.)')
        if e.code in (400, 404):
            raise RuntimeError('اسم الموديل مش متاح لحسابك أو الطلب مرفوض. غيّر الموديل من الإعدادات. ' + msg[:160])
        raise RuntimeError('خطأ من الخدمة (%s). %s' % (e.code, msg[:160]))
    except urllib.error.URLError:
        raise RuntimeError('مفيش اتصال بالإنترنت.')
    except (KeyError, IndexError, ValueError):
        raise RuntimeError('الرد رجع بشكل غير متوقع (ممكن يكون اتحجب). جرّب صياغة تانية.')
    except Exception as e:      # noqa
        raise RuntimeError('تعذّر الاتصال: %s' % e)
