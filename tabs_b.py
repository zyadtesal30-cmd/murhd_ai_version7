# -*- coding: utf-8 -*-
"""الشاشات: ٤) القسم  ٥) تسجيل  ٦) خطتي"""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout

import engine as E
from engine import C, COURSES, PROBATION_LOAD, Student, pre_of, recommended_codes, term_label, term_offers
from tabs_a import KIND_TXT, lab_row, sec
from ui import (confirm_popup, PRIMARY, RED_BG, AMBER, AMBER_BG, BLUE, BLUE_BG, CARD2, DARK, GOLD, GREEN, GREEN_BG, INK, MUTED, PICK_BG, RED, SURFACE, TEAL,
                ON_PRIMARY, ALabel, ArInput, Btn, Card, RLabel, TapCard, chips, choice_popup, hrow, info_popup, open_popup, page, seg, stepper)

SUMMER_KEY = 'SUMMER*'
LEVEL_TXT = {'crit': 'لازم يتفتح', 'imp': 'يفضل يتفتح', 'ok': 'ممكن بديل'}
LEVEL_COL = {'crit': RED, 'imp': AMBER, 'ok': GREEN}
STATE_TXT = {'open': '✔ مفتوح', 'closed': '✘ مش مفتوح', 'unknown': '؟ لسه ما أعلنوش'}


class TabsB:
    # ───────────────── ٤) القسم ─────────────────
    def dept_scopes(self):
        s = self.set
        offers = s.setdefault('offers', {})
        out = []
        for typ, yr in E.term_sequence(s['start_type'], s['start_year'], 6, s.get('use_summer', True)):
            k = E.tkey(typ, yr)
            out.append((k, term_label(typ, yr, s['months']) + ('   ✔ معلن' if k in offers else '')))
        if s.get('use_summer', True):
            out.append((SUMMER_KEY, 'كل الصيفيات (افتراضي)' + ('   ✔' if s.get('summer_codes') is not None else '')))
        return out

    def load_dept_scope(self):
        s = self.set
        codes = s.get('summer_codes') if self.dept_key == SUMMER_KEY else s.setdefault('offers', {}).get(self.dept_key)
        self.dept_mode = 'auto' if codes is None else 'list'
        self.dept_sel = set(codes or [])

    def dept_save(self):
        s = self.set
        val = sorted(self.dept_sel) if self.dept_mode == 'list' else None
        if self.dept_key == SUMMER_KEY:
            s['summer_codes'] = val
        elif val is None:
            s.setdefault('offers', {}).pop(self.dept_key, None)
        else:
            s.setdefault('offers', {})[self.dept_key] = val
        self.changed()

    def dept_rows(self):
        st = Student(self.rec)
        q = self.dept_q.strip()
        self._dfz = False
        rank = None
        if q:             # بحث بالظبط الأول، ولو مفيش → أقرب المواد في الحروف/النطق (زي «موادي»)
            base = [c for c in COURSES if self.dept_view == 'ALL' or c.grp == self.dept_view]
            hits = self._exact_hits(q, base)
            if not hits:
                hits = self._fuzzy_hits(q, base)
                if hits:
                    self._dfz = True
                    rank = {c.code: i for i, c in enumerate(hits)}
            keep = {c.code for c in hits}
        rows = []
        for c in COURSES:
            if q and c.code not in keep:
                continue
            if self.dept_view != 'ALL' and c.grp != self.dept_view:
                continue
            passed = st.passed(c.code) and not st.low(c.code)
            missing = [p for p in pre_of(c.code, self.set) if not st.satisfied(p)]
            if self.dept_filter == 'avail' and (passed or st.cur(c.code) or missing):
                continue
            if self.dept_filter == 'req' and (c.kind != 'R' or passed or st.cur(c.code)):
                continue
            note = ('خلّصته' if passed else 'بتدرسه الآن' if st.cur(c.code) else
                    ('ناقص متطلب: ' + '، '.join(C[p].name for p in missing)) if missing else 'جاهز ليك ✔')
            rows.append((c, note))
        if rank is not None:
            rows.sort(key=lambda r: rank.get(r[0].code, 99))
        else:
            rows.sort(key=lambda r: (r[0].sem if r[0].sem else 99, 0 if r[0].kind == 'R' else 1, r[0].code))
        return rows

    def dept_cat_chips(self):
        items = []
        for key, nm in self.CATS:
            n = sum(1 for c in self.view_base(key) if c.code in self.dept_sel)
            items.append((key, nm + (' (%d)' % n if n else '')))
        return chips(items, self.dept_view, lambda k: (setattr(self, 'dept_view', k), self.show_tab(3, top=True)), h=38)

    def refresh_dept_chips(self):
        if self._dchips is not None and self.tab == 3:
            self._dchips.clear_widgets()
            self._dchips.add_widget(self.dept_cat_chips())

    def t_dept(self, box):
        scopes = self.dept_scopes()
        keys = [k for k, _ in scopes]
        if self.dept_key not in keys:
            self.dept_key = keys[0]
            self.load_dept_scope()
        label = dict(scopes)[self.dept_key]

        c = Card()
        c.add_widget(sec('الفصل اللي بتسجّل فيه'))
        b = Btn(label + '   ▼', bg=GOLD, fg=DARK, h=48)

        def pick_scope(k):
            self.dept_key = k
            self.load_dept_scope()
            self.show_tab(3, top=True)
        b.bind(on_release=lambda *a: choice_popup('اختار الفصل', scopes, pick_scope))
        c.add_widget(b)

        def set_mode(m):
            self.dept_mode = m
            self.dept_save()
            self.show_tab(3)
        c.add_widget(seg([('auto', 'لسه ما أعلنوش'), ('list', 'القسم أعلن مواد')], self.dept_mode, set_mode))
        if self.dept_mode == 'list':
            c.add_widget(ALabel('علّمت %d مادة مفتوحة. اختارهم من الأقسام تحت.' % len(self.dept_sel), size=13, bold=True,
                                color=GREEN))
        else:
            c.add_widget(ALabel('لو القسم أعلن، اختار «القسم أعلن مواد» وعلّم المواد المفتوحة من تحت.', size=12, color=MUTED))
        box.add_widget(c)

        # ── المواد المفتوحة (نفس أقسام «موادي» + الكل) — قبل أي حاجة طويلة عشان تظهر على طول ──
        box.add_widget(sec('المواد المفتوحة'))
        self._dchips = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(42))
        self._dchips.add_widget(self.dept_cat_chips())
        box.add_widget(self._dchips)
        box.add_widget(seg([('avail', 'المتاحة لي'), ('req', 'الإجباري المتبقي'), ('all', 'كل المواد')],
                           self.dept_filter, lambda k: (setattr(self, 'dept_filter', k), self.show_tab(3, top=True)), h=38))

        lst = self.list_box()
        state = {'rows': []}

        def fill(reset=False):
            if reset:
                self.limits.pop('dept', None)
            lst.clear_widgets()
            state['rows'] = self.dept_rows()
            if state['rows'] and getattr(self, '_dfz', False):
                lst.add_widget(ALabel('مفيش تطابق بالظبط — دي أقرب المواد لكلامك، اختار اللي تقصده:', size=12, bold=True, color=GOLD))
            self.paged(lst, 'dept', state['rows'], lambda r: self.dept_row(r[0], r[1]), fill)

        def on_q(v):
            self.dept_q = v
            self.debounce(lambda: fill(True))
        q = ArInput(text=self.dept_q, hint='بحث بالاسم أو الكود', on_text=on_q)
        q.ti.bind(on_text_validate=lambda *a: fill(True))
        go2 = Btn('بحث', bg=GOLD, fg=DARK, size=13, h=46, size_hint_x=None, width=dp(68))
        go2.bind(on_release=lambda *a: fill(True))
        pool = lambda: [c for c in COURSES if self.dept_view == 'ALL' or c.grp == self.dept_view]      # noqa
        mic = self.mic_btn(lambda texts: setattr(q.ti, 'text', self.best_search_text(texts, pool())))
        qb = Btn('إدخال سريع (كتابة / صوت / صورة)', bg=PRIMARY, fg=ON_PRIMARY, h=46, bold=True, size=13)
        qb.bind(on_release=lambda *a: self.quick_entry('dept'))
        box.add_widget(qb)
        box.add_widget(hrow(mic, go2, q, h=46))

        def all_():
            self.dept_mode = 'list'
            self.dept_sel |= {c.code for c, _ in self.dept_rows()}
            self.dept_save()
            self.show_tab(3)

        def clr():
            self.dept_sel = set()
            self.dept_save()
            self.show_tab(3)
        a = Btn('تحديد كل الظاهر', h=42, size=13)
        a.bind(on_release=lambda *x: all_())
        d = Btn('مسح التحديد', h=42, size=13)
        d.bind(on_release=lambda *x: clr())
        box.add_widget(hrow(d, a, h=42))
        box.add_widget(lst)
        fill()

        # ── إيه اللازم يتفتح؟ (مطوية افتراضياً) ──
        c = Card()
        tg = Btn('إيه اللازم يتفتح من القسم؟   ' + ('▲' if self.crit_open else '▼'), bg=CARD2, fg=GOLD, h=46)

        def toggle_crit(*a):
            self.crit_open = not self.crit_open
            self.show_tab(3)
        tg.bind(on_release=toggle_crit)
        c.add_widget(tg)
        if self.crit_open:
            c.add_widget(lab_row('أبحث في أول (عدد) فصول', stepper(self.set.get('look', 2), 1, 4,
                                                                  lambda v: (self.set.__setitem__('look', v), self.changed()))))
            go = Btn('اعرف إيه اللازم يتفتح', bg=GOLD, fg=DARK, h=48)
            go.bind(on_release=lambda *a: self.compute_crit())
            c.add_widget(go)
            self.show_crit(c)
        box.add_widget(c)

    def dept_lines(self, c, note, on):
        return [(('☑  ' if on else '☐  ') + c.name, GREEN if on else None, 15, True),
                ('%s • %d ساعة • فصل %s • %s — %s' % (c.code, c.cr, c.sem if c.sem else '—',
                                                    'إجباري' if c.kind == 'R' else 'اختياري', KIND_TXT[c.grp]), MUTED, 11),
                (note, TEAL if 'جاهز' in note else MUTED, 11)]

    def dept_row(self, c, note):
        on = c.code in self.dept_sel
        card = TapCard(bg=GREEN_BG if on else SURFACE, accent=GREEN if on else CARD2, pad=10, radius=14)
        rl = RLabel(self.dept_lines(c, note, on))
        card.add_widget(rl)

        def tap(*a):
            self.dept_mode = 'list'
            if c.code in self.dept_sel:
                self.dept_sel.discard(c.code)
            else:
                self.dept_sel.add(c.code)
            self.dept_save()
            on2 = c.code in self.dept_sel
            card.set_bg(GREEN_BG if on2 else SURFACE)
            card.set_accent(GREEN if on2 else CARD2)
            rl.set_lines(self.dept_lines(c, note, on2))
            self.refresh_dept_chips()
        card.bind(on_release=tap)
        return card

    def compute_crit(self):
        def with_p(p):
            look = self.set.get('look', 2)

            def done(res):
                self.crit_cache = res
                self.crit_open = True
                if self.tab == 3:
                    self.show_tab(3)
            self.run_async(lambda: E.critical_to_open(p['st'], p['cfg'], p['prefs'], look), done)
        self.with_pack(with_p)

    def show_crit(self, card):
        cr = self.crit_cache
        if cr is None:
            card.add_widget(ALabel('اضغط الزر عشان تعرف تطلب من القسم إيه.', size=12, color=MUTED))
            return
        if not cr or not cr['base'] or not cr['base']['terms']:
            card.add_widget(ALabel('مفيش مقررات متبقية تحتاج فتح من القسم.', size=13, color=GREEN))
            return
        items = cr['items']
        must = [i for i in items if i['level'] in ('crit', 'imp')]
        flex = [i for i in items if i['level'] == 'ok']
        closed = [i for i in must if i['level'] == 'crit' and i['state'] == 'closed']
        p = self.cache
        grad_h = cr['plan_hours'] - cr['retake_hours']
        lines = [('لو القسم فتح اللازم هتتخرج %s.' % cr['base']['finish_label'], GOLD, 14, True)]
        if p:
            have = p['an']['counted'] + p['an']['cur_hours']
            lines.append(('المطلوب منك بس: %d ساعة (خلّصت/بتدرس %d + باقي %d = %d ساعة تخرج).'
                          % (grad_h, have, grad_h, have + grad_h), TEAL, 12.5, True))
        else:
            lines.append(('المطلوب منك بس: %d ساعة لحد التخرج.' % grad_h, TEAL, 12.5, True))
        if cr['retake_hours']:
            lines.append(('(منها %d ساعة إعادة متطلبات سابقة)' % cr['retake_hours'], MUTED, 11))
        lines.append(('في أول فصول البحث: ' + ' • '.join('%s: %d ساعة' % (lb[:14], h) for lb, h, _n in cr['term_hours'][:len(cr['keys'])]),
                      MUTED, 11))
        if must:
            lines.append(('لازم يتفتح: %d • يفضل: %d' % (sum(1 for i in must if i['level'] == 'crit'),
                                                       sum(1 for i in must if i['level'] == 'imp')), RED, 13, True))
        else:
            lines.append(('مفيش مادة بالذات لازم تتفتح — أي مواد من خطتك هتخليك تتخرج في نفس الميعاد ✔', GREEN, 13, True))
        if closed:
            lines.append(('⚠ %d مادة لازم تتفتح والقسم مش فاتحها — اطلبها!' % len(closed), RED, 13, True))
        card.add_widget(RLabel(lines))

        def mk_item(i):
            cd = Card(bg=SURFACE, accent=LEVEL_COL[i['level']], pad=10, radius=12)
            cd.add_widget(RLabel([('%s — %s%s' % (i['code'], i['name'], ' (إعادة)' if i['retake'] else ''), None, 14, True),
                                  ('%s • %s • %s' % (i['label'], LEVEL_TXT[i['level']], STATE_TXT[i['state']]),
                                   LEVEL_COL[i['level']], 11),
                                  (i['why'], MUTED, 11)]))
            return cd
        for i in must:
            card.add_widget(mk_item(i))
        if flex:
            show = getattr(self, 'crit_all', False)
            tg = Btn('مواد ليها بديل (%d) — %s' % (len(flex), 'إخفاء' if show else 'عرض'), bg=CARD2, fg=MUTED, h=42, size=12)

            def toggle_flex(*a):
                self.crit_all = not getattr(self, 'crit_all', False)
                self.show_tab(3)
            tg.bind(on_release=toggle_flex)
            card.add_widget(tg)
            if show:
                for i in flex:
                    card.add_widget(mk_item(i))
        rq = Btn('نص الطلب الجاهز للقسم', bg=GOLD, fg=DARK, h=48)
        rq.bind(on_release=lambda *a: self.show_request())
        card.add_widget(rq)

    def show_request(self):
        def with_p(p):
            cr = self.crit_cache
            txt = E.dept_request_text(p['cfg'], cr['items'] if cr else [], p['cfg'].get('name', ''))
            if not txt:
                info_popup('طلب للقسم', 'مفيش مقررات حرجة أو مهمة محتاجة طلب خاص — أي مقررات متاحة هتنفع.', size=(0.88, 0.3))
                return
            info_popup('طلب للقسم', txt, [('نسخ', lambda: self.copy_text(txt)), ('مشاركة', lambda: self.share_text(txt))],
                       size=(0.94, 0.85))
        self.with_pack(with_p)

    # ───────────────── ٥) تسجيل ─────────────────
    def reg_key(self):
        return E.tkey(self.set['start_type'], self.set['start_year'])

    def reg_picks(self):
        return set(self.set.setdefault('picks', {}).get(self.reg_key(), [])) & self._reg_ok

    def reg_set_picks(self, s):
        self.set.setdefault('picks', {})[self.reg_key()] = sorted(s)
        self.schedule_save()

    def refresh_reg_total(self, p):
        cfg = p['cfg']
        picks = self.reg_picks()
        tot = sum(C[c].cr for c in picks)
        mx = cfg['cap']
        mn = min(int(cfg.get('min_load') or 0), mx)
        lim = 'الأدنى %d — الأقصى %d' % (mn, mx) if mn else 'الأقصى %d' % mx
        head = ('اخترت %d مادة = %d ساعة  (%s)' % (len(picks), tot, lim), None, 14, True)
        if not picks:
            tail, col = 'اضغط على مادة عشان تختارها', AMBER
        elif tot > mx:
            tail, col = '✘ زيادة %d ساعة عن الأقصى' % (tot - mx), RED
        elif tot < mn:
            tail, col = '⚠ ناقص %d ساعة عن الأدنى' % (mn - tot), AMBER
        else:
            tail, col = '✔ تمام', GREEN
        self._reg_tot.set_lines([head, (tail, col, 14, True)])
        sb = getattr(self, '_reg_sel_btn', None)
        if sb is not None:
            sb.set_text('اللي اخترته (%d)' % len(picks))

    def t_reg(self, box, p):
        cfg, my = p['cfg'], p['my']
        nxt = term_label(cfg['start_type'], cfg['start_year'], cfg.get('months'))
        rec, term = recommended_codes(p)
        valid_rec = term is not None and term['typ'] == cfg['start_type'] and term['year'] == cfg['start_year']
        recs = set(rec) if valid_rec else set()
        self._reg_recs = sorted(recs)
        self._reg_ok = {c.code for c, reasons in p['elig'] if not reasons}
        height = my['height'] if my else {}

        c = Card()
        c.add_widget(ALabel('الفصل اللي بتسجّل فيه: %s' % nxt, size=15, bold=True, color=GOLD))
        c.add_widget(ALabel('الموصى بيه: %d مادة (%d ساعة)' % (len(recs), sum(C[x].cr for x in recs)), size=13, color=TEAL))
        notes = []
        off = term_offers(cfg, cfg['start_type'], cfg['start_year'])
        if off is not None:
            notes.append('القسم فاتح %d مادة في الفصل ده — اختار منهم بس.' % len(off))
        if p['an']['probation']:
            notes.append('معدلك أقل من 2.00: أقصى حد %d ساعة.' % PROBATION_LOAD)
        if my and my['terms'] and not valid_rec:
            notes.append('خطتك ما فيهاش مواد في %s — شوف تبويب «خطتي».' % nxt)
        notes.append('أخضر = موصى بيها • أزرق = متاحة • رمادي = مش متاحة (مكتوب السبب).')
        c.add_widget(ALabel('\n'.join(notes), size=11, color=MUTED))
        box.add_widget(c)

        tc = Card(bg=CARD2)
        self._reg_tot = RLabel([('', None, 14, True)], halign='center')
        tc.add_widget(self._reg_tot)
        box.add_widget(tc)

        self._reg_sel_btn = Btn('اللي اخترته (%d)' % len(self.reg_picks()), bg=PRIMARY, fg=ON_PRIMARY, h=46, bold=True)
        self._reg_sel_btn.bind(on_release=lambda *x: self.show_picked(p))
        box.add_widget(self._reg_sel_btn)

        a = Btn('اختار الموصى بيه', bg=GOLD, fg=DARK, h=44, size=12)
        d = Btn('مسح اختياراتي', h=44, size=12)
        cp = Btn('نسخ / مشاركة', bg=TEAL, fg=INK, h=44, size=12, bold=True)

        def pick_rec(*x):
            self.reg_set_picks(set(self._reg_recs) & self._reg_ok)
            self.show_tab(4)

        def clear(*x):
            self.reg_set_picks(set())
            self.show_tab(4)
        a.bind(on_release=pick_rec)
        d.bind(on_release=clear)
        cp.bind(on_release=lambda *x: self.copy_register())
        box.add_widget(hrow(cp, d, a, h=44))

        picks = self.reg_picks()
        rows = []
        for cr_, reasons in p['elig']:
            if cr_.code in recs:
                state, order = 'rec', 0
            elif not reasons:
                state, order = 'ok', 1
            else:
                state, order = 'no', 2
            h = height.get(cr_.code, 0)
            prio = 'لازم' if h >= 4 else ('مهمة' if h >= 2 else '')
            why = '؛ '.join(reasons) if reasons else ('مطلوبة للتخرج' if cr_.kind == 'R' else (
                'ضمن اختيارات خطتك' if my and cr_.code in my['chosen'] else 'اختيارية'))
            if p['st'].failed(cr_.code):
                why = 'راسب فيها — لازم تعيدها. ' + why
                prio = 'لازم'
            rows.append((order, 0 if prio == 'لازم' else 1, cr_.sem, cr_.code, cr_, state, prio, why))
        rows.sort(key=lambda r: r[:4])
        self.paged(box, 'reg', rows, lambda r: self.reg_row(p, r[4], r[5], r[6], r[7], r[4].code in picks))
        self.refresh_reg_total(p)

    def reg_lines(self, c, state, prio, why, picked):
        sym = '☑' if picked else ('☐' if state != 'no' else '•')
        tag = {'rec': 'موصى بيها', 'ok': 'متاحة', 'no': 'مش متاحة'}[state]
        mc = {'rec': GREEN, 'ok': BLUE, 'no': MUTED}[state]
        return [(sym + '  ' + c.name, GOLD if picked else (MUTED if state == 'no' else None), 15, True),
                ('%s • %d ساعة • %s • %s — %s%s' % (c.code, c.cr, tag, 'إجباري' if c.kind == 'R' else 'اختياري',
                                                  KIND_TXT[c.grp], (' • أولوية: ' + prio) if prio else ''), mc, 11),
                (why, MUTED, 11)]

    def reg_row(self, p, c, state, prio, why, picked):
        bg = {'rec': GREEN_BG, 'ok': BLUE_BG, 'no': SURFACE}[state]
        acc = {'rec': GREEN, 'ok': BLUE, 'no': CARD2}[state]
        card = TapCard(bg=PICK_BG if picked else bg, accent=GOLD if picked else acc, pad=10, radius=14)
        rl = RLabel(self.reg_lines(c, state, prio, why, picked))
        card.add_widget(rl)
        if state == 'no':
            return card

        def tap(*a):
            s = self.reg_picks()
            s.symmetric_difference_update({c.code})
            self.reg_set_picks(s)
            on = c.code in s
            card.set_bg(PICK_BG if on else bg)
            card.set_accent(GOLD if on else acc)
            rl.set_lines(self.reg_lines(c, state, prio, why, on))
            self.refresh_reg_total(p)
        card.bind(on_release=tap)
        return card

    def show_picked(self, p):
        """نافذة بالمواد اللي اخترتها: الإجمالي + اضغط على مادة لإلغائها."""
        changed = [False]
        root = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(4))
        tot_lbl = RLabel([('', None, 14, True)], halign='center')
        tc = Card(bg=CARD2, pad=10)
        tc.add_widget(tot_lbl)
        root.add_widget(tc)
        sv, lst = page(pad=4, spacing=8)
        root.add_widget(sv)
        pop = open_popup('اللي اخترته', root, (0.94, 0.88))
        row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(8))
        cp = Btn('نسخ / مشاركة', bg=TEAL, fg=INK, h=46, size=13, bold=True)
        cl = Btn('إغلاق', h=46)
        cp.bind(on_release=lambda *a: self.copy_register())
        cl.bind(on_release=lambda *a: pop.dismiss())
        row.add_widget(cp)
        row.add_widget(cl)
        root.add_widget(row)

        def refresh():
            lst.clear_widgets()
            picks = sorted(self.reg_picks(), key=lambda x: (C[x].sem or 99, x))
            tot_lbl.set_lines([('%d مادة = %d ساعة  (الأقصى %d)' % (len(picks), sum(C[x].cr for x in picks), p['cfg']['cap']),
                                None, 14, True)])
            if not picks:
                lst.add_widget(ALabel('لسه ما اخترتش مواد.', size=13, color=MUTED, halign='center'))
                return
            lst.add_widget(ALabel('اضغط على المادة لإلغاء اختيارها.', size=11, color=MUTED))
            for code in picks:
                c = C[code]
                card = TapCard(bg=PICK_BG, accent=GOLD, pad=10, radius=14)
                card.add_widget(RLabel([('☑  ' + c.name, GOLD, 15, True),
                                        ('%s • %d ساعة • %s' % (c.code, c.cr, 'إجباري' if c.kind == 'R' else 'اختياري'), MUTED, 11.5)]))

                def drop(*a, code=code):
                    s = self.reg_picks()
                    s.discard(code)
                    self.reg_set_picks(s)
                    changed[0] = True
                    self.refresh_reg_total(p)
                    refresh()
                card.bind(on_release=drop)
                lst.add_widget(card)
        pop.bind(on_dismiss=lambda *a: self.show_tab(4) if changed[0] else None)
        refresh()

    def copy_register(self):
        codes = sorted(self.reg_picks()) or self._reg_recs
        if not codes:
            info_popup('تنبيه', 'لسه ما اخترتش مواد.', size=(0.85, 0.28))
            return
        txt = 'موادي للتسجيل:\n' + '\n'.join('%s — %s (%d)' % (c, C[c].name, C[c].cr) for c in codes)
        info_popup('موادي', txt, [('نسخ', lambda: self.copy_text(txt)), ('مشاركة', lambda: self.share_text(txt))],
                   size=(0.92, 0.75))

    # ───────────────── ٦) خطتي ─────────────────
    def t_plan(self, box):
        box.add_widget(seg([('plans', 'الخطط'), ('tracks', 'المسارات'), ('goal', 'الهدف'), ('improve', 'التحسين')], self.plan_sub,
                           lambda k: (setattr(self, 'plan_sub', k), self.show_tab(5, top=True))))
        if self.plan_sub == 'plans':
            self.t_plans(box)
        elif self.plan_sub == 'goal':
            self.t_goal(box)
        elif self.plan_sub == 'improve':
            self.t_improve(box)
        else:
            self.t_tracks(box)

    # ───────────────── هدف المعدل: أجيب كام في كل مادة؟ ─────────────────
    GOAL_PRESETS = [2.0, 2.5, 3.0, 3.3, 3.5, 3.7, 4.0]
    GOAL_LETTER = {2.0: 'C', 3.0: 'B', 3.3: 'B+', 3.7: 'A-', 4.0: 'A'}

    def t_goal(self, box):
        s = self.set
        goal = float(s.get('goal_gpa') or 3.3)
        c = Card()
        c.add_widget(sec('عايز تتخرج بمعدل كام؟'))
        c.add_widget(ALabel('اختار هدفك (A- = 3.7 • B+ = 3.3 وهو حد مرتبة الشرف) أو اكتب معدل تاني:', size=12, color=MUTED))
        sel = '%.2f' % goal
        c.add_widget(chips([('%.2f' % v, '%.1f%s' % (v, ('  ' + self.GOAL_LETTER[v]) if v in self.GOAL_LETTER else '')) for v in self.GOAL_PRESETS], sel,
                           lambda k: (s.__setitem__('goal_gpa', float(k)), self.schedule_save(), self.show_tab(5, top=True))))
        typed = {'v': ''}
        inp = ArInput(hint='معدل تاني (من 1 لـ 4) مثال: 3.45', numeric=True, on_text=lambda v: typed.__setitem__('v', v))

        def apply_custom(*a):
            try:
                v = float(typed['v'])
            except ValueError:
                info_popup('تنبيه', 'اكتب رقم صحيح بين 1 و 4.', size=(0.8, 0.25))
                return
            if not 1.0 <= v <= 4.0:
                info_popup('تنبيه', 'المعدل لازم يكون بين 1 و 4.', size=(0.8, 0.25))
                return
            s['goal_gpa'] = round(v, 2)
            self.schedule_save()
            self.show_tab(5, top=True)
        ok = Btn('احسب', bg=GOLD, fg=DARK, size=13, h=46, size_hint_x=None, width=dp(68))
        ok.bind(on_release=apply_custom)
        inp.ti.bind(on_text_validate=apply_custom)
        c.add_widget(hrow(ok, inp, h=46))
        c.add_widget(ALabel('هدفك الحالي: %.3f' % goal, size=15, bold=True, color=TEAL, halign='center'))
        box.add_widget(c)
        sv = self._sv
        self.with_pack(lambda p: self._goal_fill(box, sv, p, goal))

    def _goal_fill(self, box, sv, p, goal):
        if self.tab != 5 or sv is not self._sv or self.plan_sub != 'goal':
            return
        try:
            r = E.goal_plan(p, goal)
            self._goal_cards(box, p, r, goal)
        except Exception:
            import traceback
            box.add_widget(ALabel('حصل خطأ:\n' + traceback.format_exc()[-600:], size=11, color=RED))

    def _goal_cards(self, box, p, r, goal):
        base = r['base_gpa']
        if r['empty']:
            c = Card(bg=BLUE_BG, accent=BLUE)
            c.add_widget(ALabel('مفيش مواد متبقية في الخطة — معدلك النهائي ' + ('%.3f' % base if base is not None else '—') +
                                '. ' + ('✔ محقق هدفك.' if base is not None and base >= goal - 1e-9 else
                                        'مش هتقدر ترفعه غير بإعادة مواد (اتكلم مع المرشد الأكاديمي).'),
                                size=13, bold=True, color=GOLD))
            box.add_widget(c)
            return
        c = Card()
        c.add_widget(sec('وضعك الحالي'))
        lines = []
        if base is not None:
            lines.append(('معدلك الحالي: %.3f  (على %d ساعة%s)' % (base, r['base_hours'], ' — معدل مدخل يدوي' if r['manual'] else ''),
                          None, 14, True))
        else:
            lines.append(('لسه مفيش تقديرات مدخلة — الحساب هيبدأ من الصفر.', AMBER, 13, True))
        lines.append(('الباقي: %d مادة = %d ساعة (من خطتك الحالية + اللي بتدرسه الآن)' % (r['n'], r['hours']), MUTED, 12))
        lines.append(('أقصى معدل ممكن لو جبت أعلى تقدير في كل الباقي: %.3f' % r['max_gpa'], MUTED, 12))
        c.add_widget(RLabel(lines))
        box.add_widget(c)

        c = Card(bg=GREEN_BG if r['feasible'] else RED_BG, accent=GREEN if r['feasible'] else RED)
        if not r['feasible']:
            c.add_widget(RLabel([('✘ مش ممكن توصل %.3f' % goal, RED, 16, True),
                                 ('أقصى معدل تقدر توصله %.3f. جرّب هدف أقل. وفي كل الأحوال الراسب بيتحسب له C كحد أقصى لما يعيد.'
                                  % r['max_gpa'], MUTED, 12)]))
        else:
            na = r['need_avg']
            head = '✔ ممكن توصل %.3f' % goal
            if na <= 1.0:
                sub = 'أي نجاح في الباقي بيحققه — بس خلّي بالك من شرط C- للمواد المطلوبة كمتطلب سابق.'
            else:
                sub = 'محتاج متوسط حوالي %.3f نقطة في باقي المواد (يعني %s تقريباً).' % (na, self._letter_for(na))
            dist = {}
            for it in r['items']:
                n_, h_ = dist.get(it['letter'], (0, 0))
                dist[it['letter']] = (n_ + 1, h_ + it['cr'])
            order = [l for l, _g in reversed(E.GRADE_STEPS)]
            parts = ['%s في %d مادة (%d ساعة)' % (l, dist[l][0], dist[l][1]) for l in order if l in dist]
            c.add_widget(RLabel([(head, GREEN, 16, True), (sub, None, 13, False),
                                 ('التوزيع المطلوب (أقل حاجة تحقق هدفك):', GOLD, 13, True)] +
                                [('• ' + t, None, 13, False) for t in parts] +
                                [('المعدل المتوقع بالتوزيع ده: %.3f' % r['final_gpa'], TEAL, 13, True)]))
        box.add_widget(c)

        notes = ['ده أدنى توزيع يحقق هدفك — لو جبت أعلى في مادة، تقدر تنزل في مادة تانية.',
                 'المواد اللي متطلب لمواد تانية لازم C- على الأقل.',
                 'الراسب لما يعيد المقرر بيتحسب له C كحد أقصى (حسب اللائحة).']
        if goal >= 3.3 and p['an']['fail']:
            notes.append('⚠ مرتبة الشرف في اللائحة بشرط ما تكونش رسبت في أي مقرر — وإنت راسب في: ' +
                         '، '.join(x.name for x in p['an']['fail']))
        elif goal >= 3.3:
            notes.append('مرتبة الشرف (٣٫٣ فأكثر) بشرط ما ترسبش في أي مقرر.')
        nc = Card(bg=CARD2)
        nc.add_widget(RLabel([(t, MUTED, 11, False) for t in notes]))
        box.add_widget(nc)

        box.add_widget(sec('كام أجيب في كل مادة؟'))
        groups = []
        for it in r['items']:
            if not groups or groups[-1][0] != it['label']:
                groups.append((it['label'], []))
            groups[-1][1].append(it)
        for label, its in groups:
            cd = Card(accent=CARD2, pad=12)
            lines = [('%s  —  %d ساعة' % (label, sum(i['cr'] for i in its)), GOLD, 14, True)]
            for it in its:
                lines.append(('• %s (%d)%s   ←   %s' % (it['name'], it['cr'], ' (إعادة)' if it['retake'] else '', it['letter']),
                              None, 13, False))
            cd.add_widget(RLabel(lines))
            box.add_widget(cd)

    # ───────────────── نظام التحسين: لو حسّنت مواد، المعدل يوصل كام؟ ─────────────────
    IMP_TARGETS = [('A', 'A'), ('A-', 'A-'), ('B+', 'B+'), ('B', 'B')]

    def imp_state(self):
        d = self.set.get('imp')
        if not isinstance(d, dict):
            d = self.set['imp'] = {'sel': {}, 'target': 'A'}
        d.setdefault('sel', {})
        d.setdefault('target', 'A')
        return d

    def t_improve(self, box):
        d = self.imp_state()
        c = Card()
        c.add_widget(sec('نظام التحسين'))
        c.add_widget(ALabel('اختار المواد اللي هتعيدها عشان تحسّن تقديرها، وشوف معدلك هيبقى كام. حسب اللائحة بتتحسب '
                            'النقاط الفعلية للتقدير الجديد (يعني ممكن تزيد أو تقل).', size=12, color=MUTED))
        c.add_widget(ALabel('التقدير المتوقع في المواد المختارة:', size=13, bold=True))

        def set_target(k):
            d['target'] = k
            for code in list(d['sel']):
                d['sel'][code] = k
            self.schedule_save()
            self.show_tab(5)
        c.add_widget(seg(self.IMP_TARGETS, d['target'], set_target))
        box.add_widget(c)
        sv = self._sv
        self.with_pack(lambda p: self._imp_fill(box, sv, p))

    def _imp_fill(self, box, sv, p):
        if self.tab != 5 or sv is not self._sv or self.plan_sub != 'improve':
            return
        try:
            self._imp_cards(box, p)
        except Exception:
            import traceback
            box.add_widget(ALabel('حصل خطأ:\n' + traceback.format_exc()[-600:], size=11, color=RED))

    def _imp_cards(self, box, p):
        d = self.imp_state()
        sel = d['sel']
        res = E.improve_calc(p, sel)
        if res.get('none'):
            c = Card(bg=AMBER_BG, accent=AMBER)
            c.add_widget(ALabel('لازم تدخل تقديرات موادك الأول (من «موادي») عشان أحسب التحسين مادة مادة.', size=13, bold=True,
                                color=AMBER))
            box.add_widget(c)
            return
        c = Card(bg=GREEN_BG if sel else SURFACE, accent=GREEN if sel else CARD2)
        L = [('معدلك الحالي: %.3f  (على %d ساعة)' % (res['now'], res['hours']), None, 14, True)]
        if res['rows']:
            L.append(('بعد تحسين %d مادة (%d ساعة): %.3f  (%+.3f)' % (len(res['rows']), res['sel_hours'], res['after'], res['delta']),
                      GREEN if res['delta'] >= 0 else RED, 16, True))
            if res['honors_ok']:
                L.append(('✔ وصلت لنطاق مرتبة الشرف (3.3 فأكثر وبدون رسوب).', GREEN, 12.5, True))
            elif res['after'] < 3.3:
                L.append(('ناقصك %.3f لحد مرتبة الشرف (3.3).' % (3.3 - res['after']), MUTED, 12))
        else:
            L.append(('اختار مواد من تحت وهتشوف المعدل الجديد هنا.', MUTED, 12.5, False))
        L.append(('أقصى معدل ممكن لو حسّنت كل المواد لـ A: %.3f' % res['max_now'], TEAL, 12.5, False))
        if res['pending_hours']:
            L.append(('لو كملت باقي الخطة (%d ساعة) بأعلى تقدير:' % res['pending_hours'], GOLD, 12.5, True))
            L.append(('• من غير تحسين: %.3f' % res['final_no_improve'], None, 12.5, False))
            if res['rows']:
                L.append(('• مع تحسين اللي اخترته: %.3f' % res['final_with'], None, 12.5, False))
            L.append(('• لو حسّنت كل المواد لـ A: %.3f' % res['final_all_a'], None, 12.5, False))
        c.add_widget(RLabel(L))
        box.add_widget(c)

        self._imp_delta = {x['code']: x['delta'] for x in res['rows']}
        goal = float(self.set.get('goal_gpa') or 3.3)
        mp = E.improve_min_plans(p, goal, d['target'], 3)
        mc = Card(bg=BLUE_BG, accent=BLUE)
        mc.add_widget(ALabel('أقل تحسين يوصلني لهدفي (%.3f)' % goal, size=15, bold=True, color=GOLD))
        if mp.get('ok'):
            mc.add_widget(ALabel('✔ معدلك الحالي %.3f وصل لهدفك — مش محتاج تحسين.' % mp['now'], size=13, bold=True, color=GREEN))
        elif not mp.get('feasible'):
            mc.add_widget(ALabel('✘ حتى لو حسّنت كل المواد لـ %s أقصى معدل %.3f (غيّر الهدف من تبويب «الهدف» أو التقدير المتوقع).'
                                 % (d['target'], mp.get('max_now', 0)), size=12.5, color=RED))
        else:
            mc.add_widget(ALabel('أقل مواد تعيدها (بتقدير %s) عشان توصل %.3f — كل خطة بمواد مختلفة:' % (d['target'], goal),
                                 size=12, color=MUTED))
            for i, pl in enumerate(mp['plans']):
                names = '\n'.join('• %s (%s ← %s) %+.3f' % (r_['name'], r_['old_l'], r_['new_l'], r_['gain']) for r_ in pl['rows'])
                mc.add_widget(RLabel([('خطة %d: %d مادة • %d ساعة إعادة → معدل %.3f' % (i + 1, len(pl['rows']), pl['hours'], pl['after']),
                                       TEAL, 13, True), (names, None, 12, False)]))

                def choose(rows=pl['rows']):
                    d['sel'].clear()
                    for r_ in rows:
                        d['sel'][r_['code']] = r_['new_l']
                    self.schedule_save()
                    self.show_tab(5)
                bb = Btn('اختار الخطة %d' % (i + 1), bg=PRIMARY, h=40, size=12)
                bb.bind(on_release=lambda *a, f=choose: f())
                mc.add_widget(bb)
        box.add_widget(mc)
        if sel:
            ap = Btn('تم التحسين — حدّث تقديراتي بالمواد المختارة', bg=GREEN, fg=DARK, h=46, size=12, bold=True)
            ap.bind(on_release=lambda *a: confirm_popup('تأكيد', 'هيتسجل التقدير الجديد للمواد المختارة وما تتقترحش تاني. تكمّل؟',
                                                        self.apply_improvement))
            box.add_widget(ap)
        rank = E.improve_rank(p, d['target'])
        if not rank and not res['rows']:
            box.add_widget(ALabel('مفيش مواد تقدر تحسّنها — كلها A أو في خطتك.', size=13, color=GREEN))
            return

        def best(n):
            for r in rank[:n]:
                sel[r['code']] = d['target']
            self.schedule_save()
            self.show_tab(5)

        def clear():
            sel.clear()
            self.schedule_save()
            self.show_tab(5)
        b3 = Btn('أفضل ٣ مواد', h=42, size=13)
        b3.bind(on_release=lambda *a: best(3))
        b5 = Btn('أفضل ٥', h=42, size=13)
        b5.bind(on_release=lambda *a: best(5))
        bc = Btn('مسح', bg=CARD2, h=42, size=13)
        bc.bind(on_release=lambda *a: clear())
        box.add_widget(hrow(bc, b5, b3, h=42))
        box.add_widget(ALabel('مرتبة من الأكثر تأثيراً على معدلك. اضغط على المادة لاختيارها، وعلى التقدير لتغييره.', size=11, color=MUTED))

        lst = self.list_box()

        def fill(reset=False):
            if reset:
                self.limits.pop('imp', None)
            lst.clear_widgets()
            q = (getattr(self, 'imp_q', '') or '').strip().lower()
            have = {r['code'] for r in rank}
            extra = [{'code': x['code'], 'name': x['name'], 'cr': x['cr'], 'old_l': x['old_l'], 'gain': x['delta']}
                     for x in res['rows'] if x['code'] not in have]
            rows = [r for r in extra + rank if not q or q in r['name'].lower() or q in r['code'].lower()]
            self.paged(lst, 'imp', rows, self.imp_row, fill)
        qi = ArInput(text=getattr(self, 'imp_q', ''), hint='بحث بالاسم أو الكود',
                     on_text=lambda v: (setattr(self, 'imp_q', v), self.debounce(lambda: fill(True))))
        box.add_widget(qi)
        box.add_widget(lst)
        fill()

    def apply_improvement(self):
        d = self.imp_state()
        for code, letter in list(d['sel'].items()):
            if code in C:
                if self.rec.get(code, {}).get('g') == 'F' and E.GRADES.get(letter, 0) > E.RETAKE_CAP:
                    letter = 'C'
                self.rec[code] = {'s': 'done', 'g': letter, 'imp': 1}
        d['sel'].clear()
        self.changed()
        self.show_tab(5)

    def imp_row(self, r):
        d = self.imp_state()
        code = r['code']
        on = code in d['sel']
        letter = d['sel'].get(code, d['target'])
        card = TapCard(bg=GREEN_BG if on else SURFACE, accent=GREEN if on else CARD2, pad=10, radius=14)
        lines = [('%s  (%s)' % (r['name'], code), GREEN if on else None, 13.5, True),
                 ('تقديرك الحالي %s • %d ساعة • لو %s: %+.3f على المعدل' % (r['old_l'], r['cr'], letter, (getattr(self, '_imp_delta', {}).get(code, r['gain']) if on else r['gain'])), MUTED, 12, False)]
        card.add_widget(RLabel(lines))

        def tap(*a):
            if code in d['sel']:
                d['sel'].pop(code)
            else:
                d['sel'][code] = d['target']
            self.schedule_save()
            self.show_tab(5)
        card.bind(on_release=tap)
        if not on:
            return card
        row = BoxLayout(orientation='horizontal', size_hint_y=None, spacing=dp(6))
        row.bind(minimum_height=row.setter('height'))
        gb = Btn(letter, bg=PRIMARY, size=14, h=44, size_hint_x=None, width=dp(58), pos_hint={'center_y': .5})

        def pick(k):
            d['sel'][code] = k
            self.schedule_save()
            self.show_tab(5)
        gb.bind(on_release=lambda *a: choice_popup('التقدير الجديد في ' + r['name'], [(l, l) for l, _g in reversed(E.GRADE_STEPS)], pick, size=(0.7, 0.7)))
        row.add_widget(gb)
        row.add_widget(card)
        return row

    @staticmethod
    def _letter_for(avg):
        best = E.GRADE_STEPS[-1][0]
        for l, g in E.GRADE_STEPS:
            if g >= avg - 1e-9:
                return l
        return best

    def compute_plans(self):
        def with_p(p):
            def done(res):
                self.plans = res
                self._plans_tried = True
                self.plan_sel = res[0][0] if res else None
                if self.tab == 5:
                    self.show_tab(5)
            self.run_async(lambda: E.preset_plans(p['st'], p['cfg'], p['prefs']), done)
        self.with_pack(with_p)

    def t_plans(self, box):
        if not self.plans and not self._plans_tried:
            self.compute_plans()
            return
        b = Btn('إعادة حساب الخطط', bg=GOLD, fg=DARK, h=46)
        b.bind(on_release=lambda *a: self.compute_plans())
        box.add_widget(b)
        if not self.plans:
            box.add_widget(ALabel('تعذّر بناء خطط — راجع المقررات والإعدادات.', size=13, color=RED))
            return
        fast = next((x for x in self.plans if x[0] == 'fast'), None)
        nos = next((x for x in self.plans if x[0] == 'nosum'), None)
        txt = ''
        if fast and nos:
            fp, np_ = fast[4], nos[4]
            if not fp['terms']:
                txt = 'خلّصت كل المقررات — مفيش حاجة تتسجل.'
            elif fp['finish_key'] < np_['finish_key']:
                sm = ['%s (%s)' % (t['label'], '، '.join(C[c].name for c in t['codes'])) for t in fp['terms']
                      if t['typ'] == 'U' and t['codes']]
                txt = 'الصيفي هيخليك تتخرج %s بدل %s.\nالصيفي المطلوب: %s' % (fp['finish_label'], np_['finish_label'], ' | '.join(sm))
            else:
                txt = 'مش محتاج صيفي: بتتخرج %s بالحمل الأقصى سواء نزلت صيفي أو لأ.' % fp['finish_label']
        if txt:
            c = Card(bg=BLUE_BG, accent=BLUE)
            c.add_widget(ALabel(txt, size=13, bold=True, color=GOLD))
            box.add_widget(c)
        for k, n, cap, s_, pl in self.plans:
            on = k == self.plan_sel
            cd = TapCard(bg=GREEN_BG if on else SURFACE, accent=GOLD if on else CARD2, pad=12)
            cd.add_widget(RLabel([(n, GOLD if on else None, 15, True),
                                  ('التخرج: %s • %d فصل • %d صيفي' % (pl['finish_label'], pl['n_terms'], pl['n_summers']), MUTED, 12)]))
            cd.bind(on_release=lambda w, k=k: (setattr(self, 'plan_sel', k), self.show_tab(5)))
            box.add_widget(cd)
        sel = next((x for x in self.plans if x[0] == self.plan_sel), self.plans[0])
        pl = sel[4]
        box.add_widget(sec('جدول الفصول — ' + sel[1]))
        if not pl['terms']:
            box.add_widget(ALabel('خلّصت كل المتطلبات', size=13, color=GREEN))
            return
        for t in pl['terms']:
            cd = Card(bg=AMBER_BG if t['typ'] == 'U' else SURFACE, accent=AMBER if t['typ'] == 'U' else CARD2, pad=12)
            if not t['codes']:
                lines = [(t['label'], MUTED, 14, True),
                         ('فصل انتظار — مفيش مواد متاحة (بتتفتح في فصل تاني أو القسم مش فاتحها)', MUTED, 11)]
            else:
                lines = [('%s  —  %d ساعة' % (t['label'], t['credits']), GOLD, 14, True)]
                for c in t['codes']:
                    tag = (' (إعادة)' if c in t['retake'] else '') + (' (إضافي)' if c in t.get('extra', ()) else '')
                    lines.append(('• %s%s (%d)' % (C[c].name, tag, C[c].cr), None, 13, False))
            cd.add_widget(RLabel(lines))
            box.add_widget(cd)

    def compute_tracks(self):
        def with_p(p):
            def done(res):
                self.tracks = res
                self._tracks_tried = True
                self.track_sel = res[0]['key'] if res else None
                if self.tab == 5:
                    self.show_tab(5)
            self.run_async(lambda: E.track_report(p['st'], p['cfg']), done)
        self.with_pack(with_p)

    def t_tracks(self, box):
        cur = next((t[1] for t in E.TRACKS if t[0] == self.set.get('track', 'auto')), 'تلقائي (الأسرع)')
        box.add_widget(ALabel('المسار الحالي: ' + cur, size=13, bold=True, color=TEAL))
        b = Btn('قارن المسارات', bg=GOLD, fg=DARK, h=46)
        b.bind(on_release=lambda *a: self.compute_tracks())
        box.add_widget(b)
        if not self.tracks:
            if getattr(self, '_tracks_tried', False):
                c = Card(bg=GREEN_BG, accent=GREEN)
                c.add_widget(ALabel('✔ خلّصت الاختياري المطلوب في كل الفئات — مفيش مسارات أو مواد اختيارية هتتقترح.', size=13,
                                    bold=True, color=GREEN))
                box.add_widget(c)
            else:
                box.add_widget(ALabel('اضغط «قارن المسارات» عشان تشوف أسرع مسار اختياري ليك.', size=12, color=MUTED))
            return
        box.add_widget(ALabel('كل مسار فيه أقل اختياري يكمّل ١٧٥ ساعة بالظبط. المسارات المتشابهة اتدمجت، '
                              'و«بديل» معناه اختيارات مختلفة بتكمّل نفس المتطلبات.', size=11, color=MUTED))
        p = self.cache
        best = min(r['plan']['finish_key'] for r in self.tracks)
        if p and p['my'] and p['my']['chain']:
            box.add_widget(ALabel('المسار الحرج (أطول سلسلة متطلبات): %s = %d فصل على الأقل' % (
                E.chain_names(p['my']['chain']), len(p['my']['chain'])), size=11, color=MUTED))
        for r in self.tracks:
            pl = r['plan']
            on = r['key'] == self.track_sel
            cd = TapCard(bg=GREEN_BG if pl['finish_key'] == best else SURFACE, accent=GOLD if on else CARD2, pad=12)
            cd.add_widget(RLabel([(r['name'] + ('   ◀' if on else ''), GOLD if on else None, 15, True),
                                  ('التخرج: %s • %d فصل • %d صيفي' % (pl['finish_label'], pl['n_terms'], pl['n_summers']), MUTED, 12)]))
            cd.bind(on_release=lambda w, k=r['key']: (setattr(self, 'track_sel', k), self.show_tab(5)))
            box.add_widget(cd)
        r = next((x for x in self.tracks if x['key'] == self.track_sel), self.tracks[0])
        st = p['st'] if p else Student(self.rec)
        lines = [(r['name'], GOLD, 15, True), (r['desc'], MUTED, 12)]
        if r['courses']:
            lines.append(('مقررات المسار (اللي لسه ممكن تتقترح بس):', TEAL, 13, True))
            shown = 0
            for c in r['courses']:
                if c not in C or C[c].kind != 'E':
                    continue
                done_ = st.passed(c) or st.cur(c)
                inplan = c in r['plan']['chosen']
                if not (done_ or inplan or c in r.get('todo', [])):
                    continue            # فئته خلصت أو مش محتاجه — ما نقترحوش
                mark = '✔ خلصته' if done_ else ('● هتدرسه في الخطة' if inplan else '○ اختياري')
                lines.append(('%s  %s  (%d ساعة) — %s' % (mark, C[c].name, C[c].cr, KIND_TXT[C[c].grp]), None, 12, False))
                shown += 1
            if not shown:
                lines.append(('مفيش مواد من المسار ده محتاجها.', MUTED, 12, False))
        if r.get('same'):
            lines.append(('نفس اختيارات: ' + '، '.join(r['same']), MUTED, 11, False))
        lines.append(('الاختياري اللي هتدرسه في هذا المسار:', TEAL, 13, True))
        for c in r['chosen']:
            lines.append(('• %s (%d)' % (C[c].name, C[c].cr), None, 12, False))
        d = Card(bg=CARD2)
        d.add_widget(RLabel(lines))
        box.add_widget(d)
        ad = Btn('اعتمد المسار ده واحسب خطتي', bg=GOLD, fg=DARK, h=50)
        ad.bind(on_release=lambda *a: self.adopt_track(r['key']))
        box.add_widget(ad)

    def adopt_track(self, key):
        self.set['track'] = key
        self.changed()
        self.plan_sub = 'plans'
        self.show_tab(5)
