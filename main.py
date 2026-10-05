# Железный круг: Android-клиент на Python (Kivy). Бэкенд: тот же Supabase, что и у веб-версии.
import os, json, time, threading, webbrowser
import requests, certifi
os.environ.setdefault('SSL_CERT_FILE', certifi.where())
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, ListProperty
from kivy.utils import get_color_from_hex as hx, escape_markup as esc
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.carousel import Carousel
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
try:
    from kivy.uix.video import Video
except Exception:
    Video = None
try:
    from plyer import filechooser
except Exception:
    filechooser = None

# ===== НАСТРОЙКА: Project URL и anon public key из Supabase (Settings → API) =====
SUPABASE_URL = 'https://wogyusrdnccxahsjhjbq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndvZ3l1c3JkbmNjeGFoc2poamJxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTExODc4MDYsImV4cCI6MjEwNjc2MzgwNn0.wx-Z2zzNO32PAlG0yUzHKv8nb8ilnyVB98d7Wigss8g'
# service_role ключ сюда вставлять НЕЛЬЗЯ: он даёт полный доступ к базе.
# =================================================================================
BASE = SUPABASE_URL.strip().rstrip('/')
KEY = SUPABASE_KEY.strip()
BG, CARD, CARD2 = hx('#14151a'), hx('#1d1f26'), hx('#2c2f3a')
TX, MU, ACC, INK = hx('#e9e9ee'), hx('#8d90a0'), hx('#e5758a'), hx('#2a1016')
TIERS = [(400, 'Элита', '#e5758a'), (325, 'Мастер', '#4f86e0'), (250, 'Опытный', '#f2b705'),
         (150, 'Любитель', '#2e9e5b'), (0, 'Новичок', '#ffffff')]
SPORT = [('height', 'Рост, см', 1), ('bw', 'Вес тела, кг', 1), ('years', 'Стаж, лет', 1),
         ('category', 'Разряд / звание', 0), ('federation', 'Федерация', 0),
         ('coach', 'Тренер', 0), ('gym', 'Зал', 0), ('goal', 'Цель', 0)]
LIFTS = [('sq', 'Присед, кг', 1), ('bp', 'Жим лёжа, кг', 1), ('dl', 'Становая, кг', 1)]
VIDEO_EXT = ('mp4', 'mov', 'm4v')

KV = '''
<L>:
    color: app.tx
    font_size: sp(15)
    markup: True
    halign: 'left'
    valign: 'top'
    size_hint_y: None
    text_size: self.width, None
    height: self.texture_size[1]
<Btn>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    size_hint_y: None
    height: dp(46)
    bold: True
    color: self.fg
    canvas.before:
        Color:
            rgba: self.bg
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]
<Card>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(12)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: .114, .122, .149, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
<Plate>:
    size_hint: None, None
    size: dp(44), dp(44)
    bold: True
    color: 1, 1, 1, 1
    canvas.before:
        Color:
            rgba: self.c
        Ellipse:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0, 0, 0, .22
        Line:
            circle: self.center_x, self.center_y, self.width * .36
            width: dp(1.5)
        Color:
            rgba: .055, .059, .075, 1
        Ellipse:
            pos: self.center_x - self.width * .22, self.center_y - self.height * .22
            size: self.width * .44, self.height * .44
'''


class L(Label): pass
class LB(ButtonBehavior, L): pass
class Card(BoxLayout): pass
class Plate(ButtonBehavior, Label):
    c = ColorProperty([1, 1, 1, 1])
class Btn(Button):
    bg = ColorProperty(ACC)
    fg = ColorProperty(INK)
class Thumb(ButtonBehavior, AsyncImage): pass


class D:  # состояние
    tok = rt = uid = None
    P, FO, PO, FM = {}, [], [], []
    scope = 'all'


def sess_file():
    return os.path.join(App.get_running_app().user_data_dir, 'session.json')


def refresh_token():
    if not D.rt:
        return False
    try:
        r = requests.post(BASE + '/auth/v1/token?grant_type=refresh_token', json={'refresh_token': D.rt},
                          headers={'apikey': KEY}, timeout=20)
        if r.status_code >= 400:
            return False
        set_session(r.json())
        return True
    except Exception:
        return False


def set_session(d):
    D.tok, D.rt, D.uid = d['access_token'], d['refresh_token'], d['user']['id']
    try:
        with open(sess_file(), 'w') as f:
            json.dump({'rt': D.rt}, f)
    except Exception:
        pass


def rq(method, path, _retry=True, **kw):
    h = {'apikey': KEY, 'Authorization': 'Bearer ' + (D.tok or KEY), 'Content-Type': 'application/json'}
    extra = kw.pop('headers', {})
    h.update(extra)
    r = requests.request(method, BASE + path, headers=h, timeout=30, **kw)
    if r.status_code == 401 and _retry and refresh_token():
        return rq(method, path, False, headers=extra, **kw)
    if r.status_code >= 400:
        try:
            m = r.json()
            m = m.get('msg') or m.get('message') or m.get('error_description') or str(m)
        except Exception:
            m = r.text[:200]
        raise RuntimeError(m)
    return r.json() if r.content and 'json' in r.headers.get('content-type', '') else None


def bg(fn, ok=None):
    def run():
        try:
            res, err = fn(), None
        except Exception as e:
            res, err = None, str(e)
        def done(dt):
            if err:
                App.get_running_app().toast(err)
            elif ok:
                ok(res)
        Clock.schedule_once(done)
    threading.Thread(target=run, daemon=True).start()


def dots(bw, t, sex):
    if not bw or not t:
        return 0
    c = ([-57.96288, 13.6175032, -0.1126655495, 0.0005158568, -0.0000010706] if sex == 'f'
         else [-307.75076, 24.0900756, -0.1918759221, 0.0007391293, -0.000001093])
    b = min(max(bw, 40), 150 if sex == 'f' else 210)
    return 500 * t / (c[0] + c[1] * b + c[2] * b ** 2 + c[3] * b ** 3 + c[4] * b ** 4)


def stat(p):
    sq, bp, dl = [p.get(k) or 0 for k in ('sq', 'bp', 'dl')]
    tot = sq + bp + dl if sq and bp and dl else 0
    return sq, bp, dl, tot, dots(p.get('bw') or 0, tot, p.get('sex'))


def tier(d):
    return next(t for t in TIERS if d >= t[0])


g = lambda n: ('%g' % n) if n else '—'
name_of = lambda u: (D.P.get(u) or {}).get('username') or 'атлет'
is_f = lambda u: any(f['follower'] == D.uid and f['following'] == u for f in D.FO)
followers = lambda u: sum(1 for f in D.FO if f['following'] == u)
media_url = lambda p: BASE + '/storage/v1/object/public/media/' + p


def is_pr(w):
    if not w.get('kg'):
        return False
    pr = [o for o in D.PO if o['user_id'] == w['user_id'] and o['ex'].lower() == w['ex'].lower()
          and o['created_at'] < w['created_at']]
    return bool(pr) and not any((o.get('kg') or 0) >= w['kg'] for o in pr)


def inp(hint, text='', num=False, **kw):
    return TextInput(hint_text=hint, text=text, multiline=False, size_hint_y=None, height=dp(44),
                     input_filter='float' if num else None, background_normal='', background_active='',
                     background_color=CARD2, foreground_color=TX, hint_text_color=MU, cursor_color=ACC,
                     padding=[dp(12), dp(12)], write_tab=False, **kw)


def scroll(children):
    gl = GridLayout(cols=1, spacing=dp(10), padding=dp(12), size_hint_y=None)
    gl.bind(minimum_height=gl.setter('height'))
    for c in children:
        gl.add_widget(c)
    s = ScrollView()
    s.add_widget(gl)
    return s


def plate(u, size=44):
    p = Plate(text=name_of(u)[:1].upper(), size=(dp(size), dp(size)),
              c=hx(tier(stat(D.P.get(u) or {})[4])[2]) if stat(D.P.get(u) or {})[3] else [1, 1, 1, 1])
    p.bind(on_release=lambda *a: App.get_running_app().go('user', u))
    return p


def follow_btn(u):
    if u == D.uid:
        return None
    on = is_f(u)
    b = Btn(text='Вы подписаны' if on else 'Подписаться', size_hint=(None, None), size=(dp(130), dp(36)),
            bg=CARD2 if on else ACC, fg=TX if on else INK)
    b.bind(on_release=lambda *a: toggle_follow(u))
    return b


def toggle_follow(u):
    if is_f(u):
        D.FO = [f for f in D.FO if not (f['follower'] == D.uid and f['following'] == u)]
        fn = lambda: rq('DELETE', f'/rest/v1/follows?follower=eq.{D.uid}&following=eq.{u}')
    else:
        D.FO.append({'follower': D.uid, 'following': u})
        fn = lambda: rq('POST', '/rest/v1/follows', json={'follower': D.uid, 'following': u},
                        headers={'Prefer': 'return=minimal'})
    App.get_running_app().render()
    bg(fn)


def scope_bar():
    row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
    for k, t in (('all', 'Все'), ('sub', 'Мои подписки')):
        b = Btn(text=t, bg=CARD2 if D.scope == k else CARD, fg=TX)
        b.bind(on_release=lambda x, k=k: (setattr(D, 'scope', k), App.get_running_app().render()))
        row.add_widget(b)
    return row


def open_media(items, start=0):
    """Просмотр формы в стиле reels: свайп вверх, видео играет у текущего слайда."""
    if not items:
        return
    if not Video and items[start]['media_type'] == 'v':
        webbrowser.open(media_url(items[start]['media_path']))
        return
    mv = ModalView(size_hint=(1, 1), background_color=(0, 0, 0, .97), auto_dismiss=True)
    car = Carousel(direction='top', loop=False)
    for it in items:
        s = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))
        url = media_url(it['media_path'])
        if it['media_type'] == 'v' and Video:
            s.vid = Video(source=url, state='stop', options={'eos': 'loop'})
            s.add_widget(s.vid)
        else:
            s.add_widget(AsyncImage(source=url))
        s.add_widget(L(text=f"[b]{esc(name_of(it['user_id']))}[/b]  {esc(it.get('caption') or '')}", size_hint_y=None))
        car.add_widget(s)

    def sync(*a):
        for i, s in enumerate(car.slides):
            if getattr(s, 'vid', None):
                s.vid.state = 'play' if car.index == i else 'stop'
    car.bind(index=sync)
    mv.bind(on_dismiss=lambda *a: [setattr(s.vid, 'state', 'stop') for s in car.slides if getattr(s, 'vid', None)])
    mv.add_widget(car)
    mv.open()
    if start:
        car.load_slide(car.slides[start])
    Clock.schedule_once(sync, .4)


def post_card(w):
    u = w['user_id']
    c = Card()
    head = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
    head.add_widget(plate(u))
    col = BoxLayout(orientation='vertical')
    nm = LB(text=f'[b]{esc(name_of(u))}[/b]', size_hint_y=1)
    nm.bind(on_release=lambda *a: App.get_running_app().go('user', u))
    col.add_widget(nm)
    col.add_widget(L(text=f"[color=8d90a0]{w['created_at'][:10]}[/color]", size_hint_y=1))
    head.add_widget(col)
    fb = follow_btn(u)
    if fb:
        head.add_widget(fb)
    c.add_widget(head)
    if w.get('media_path'):
        if w.get('media_type') == 'v':
            b = Btn(text='▶  Смотреть видео', bg=CARD2, fg=TX, height=dp(90))
            b.bind(on_release=lambda *a: open_media([{**w, 'caption': w.get('note')}]))
            c.add_widget(b)
        else:
            c.add_widget(AsyncImage(source=media_url(w['media_path']), size_hint_y=None,
                                    height=Window.width - dp(48), allow_stretch=True))
    vol = f" · объём {g(w['kg'] * w['reps'] * w['sets'])} кг" if w.get('kg') and w.get('reps') and w.get('sets') else ''
    pr = '  [color=e5758a][b]личный рекорд[/b][/color]' if is_pr(w) else ''
    c.add_widget(L(text=f"[size=34sp][b]{g(w.get('kg'))} кг[/b][/size]  × {w.get('reps') or 0} × {w.get('sets') or 0}{vol}{pr}"))
    c.add_widget(L(text=f"[b]{esc(w['ex'])}[/b]" + (f" · {esc(w['note'])}" if w.get('note') else '')))
    if u == D.uid:
        d = Btn(text='Удалить', bg=CARD2, fg=MU, height=dp(34), size_hint_x=None, width=dp(100))
        d.bind(on_release=lambda *a: delete_post('posts', w))
        c.add_widget(d)
    return c


def delete_post(table, w):
    D.PO = [x for x in D.PO if x is not w]
    D.FM = [x for x in D.FM if x is not w]
    App.get_running_app().render()

    def f():
        rq('DELETE', f"/rest/v1/{table}?id=eq.{w['id']}")
        if w.get('media_path'):
            rq('DELETE', '/storage/v1/object/media/' + w['media_path'])
    bg(f)


# ----- экраны -----
def v_auth(_):
    app = App.get_running_app()
    up = app.mode == 'up'
    c = Card(spacing=dp(10))
    c.add_widget(L(text='[size=44sp][b]Железный круг[/b][/size]'))
    c.add_widget(L(text='[color=8d90a0]Сообщество русскоговорящих атлетов[/color]'))
    row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
    for k, t in (('in', 'Вход'), ('up', 'Регистрация')):
        b = Btn(text=t, bg=CARD2 if app.mode == k else CARD, fg=TX)
        b.bind(on_release=lambda x, k=k: (setattr(app, 'mode', k), app.render()))
        row.add_widget(b)
    c.add_widget(row)
    f = {'u': inp('Ник', ) if up else None, 'e': inp('Email'), 'p': inp('Пароль (от 8 символов)', password=True)}
    for w in f.values():
        if w:
            c.add_widget(w)
    go = Btn(text='Создать аккаунт' if up else 'Войти')

    def submit(*a):
        email, pw = f['e'].text.strip(), f['p'].text
        if not email or len(pw) < 8:
            return app.toast('Введите email и пароль от 8 символов')
        if up:
            un = f['u'].text.strip()
            if len(un) < 2:
                return app.toast('Придумайте ник (от 2 символов)')

        def run():
            if up:
                d = rq('POST', '/auth/v1/signup', json={'email': email, 'password': pw, 'data': {'username': un}})
                if 'access_token' not in d:
                    return 'confirm'
            else:
                d = rq('POST', '/auth/v1/token?grant_type=password', json={'email': email, 'password': pw})
            set_session(d)
            return 'ok'

        def ok(r):
            if r == 'confirm':
                app.mode = 'in'
                app.render()
                app.toast('Проверьте почту и подтвердите email, затем войдите')
            else:
                app.load_all(first=True)
        bg(run, ok)
    go.bind(on_release=submit)
    c.add_widget(go)
    return scroll([c])


def v_feed(_):
    items = [w for w in D.PO if D.scope == 'all' or w['user_id'] == D.uid or is_f(w['user_id'])]
    ch = [scope_bar()] + [post_card(w) for w in items[:40]]
    if not items:
        ch.append(L(text='[color=8d90a0]Здесь пока пусто. Нажмите «+» и опубликуйте тренировку.[/color]'))
    return scroll(ch)


def v_rank(_):
    ids = set(D.P) if D.scope == 'all' else {u for u in D.P if u == D.uid or is_f(u)}
    rows = sorted(((u, stat(D.P[u])) for u in ids if stat(D.P[u])[3]), key=lambda r: -r[1][4])
    ch = [scope_bar(), L(text='[color=8d90a0]Рейтинг по очкам DOTS: сумма трёх движений с поправкой на вес тела и пол.[/color]')]
    for i, (u, s) in enumerate(rows, 1):
        c = Card()
        r = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        r.add_widget(L(text=f'[size=26sp][b]{i}[/b][/size]', size_hint_x=None, width=dp(36), size_hint_y=1))
        r.add_widget(plate(u))
        nm = LB(text=f'[b]{esc(name_of(u))}[/b]\n[color=8d90a0]{tier(s[4])[1]} · сумма {g(s[3])} кг[/color]', size_hint_y=1)
        nm.bind(on_release=lambda x, u=u: App.get_running_app().go('user', u))
        r.add_widget(nm)
        r.add_widget(L(text=f'[size=22sp][b]{s[4]:.1f}[/b][/size]\n[color=8d90a0]DOTS[/color]', size_hint_x=None, width=dp(60), size_hint_y=1))
        c.add_widget(r)
        fb = follow_btn(u)
        if fb:
            c.add_widget(fb)
        ch.append(c)
    if not rows:
        ch.append(L(text='[color=8d90a0]Пока никого нет. Внесите присед, жим и тягу в профиле' +
                    ('' if D.scope == 'all' else ' или подпишитесь на атлетов') + '.[/color]'))
    return scroll(ch)


def v_user(u):
    app = App.get_running_app()
    u = u or D.uid
    p = D.P.get(u) or {}
    sq, bp, dl, tot, d = stat(p)
    posts = [w for w in D.PO if w['user_id'] == u]
    forms = [w for w in D.FM if w['user_id'] == u]
    top = Card()
    r = BoxLayout(size_hint_y=None, height=dp(80), spacing=dp(14))
    r.add_widget(plate(u, 76))
    r.add_widget(L(text=f"[b]{len(posts)}[/b]\nпостов\n[b]{followers(u)}[/b] подписчиков", size_hint_y=1))
    r.add_widget(L(text=f"[b]{sum(1 for f in D.FO if f['follower'] == u)}[/b]\nподписок\n[b]{len(forms)}[/b] в форме", size_hint_y=1))
    top.add_widget(r)
    top.add_widget(L(text=f"[size=24sp][b]{esc(name_of(u))}[/b][/size]" + (f"  [color=8d90a0]{esc(p['city'])}[/color]" if p.get('city') else '')))
    if p.get('bio'):
        top.add_widget(L(text=esc(p['bio'])))
    top.add_widget(L(text=(f"{tier(d)[1]} · {d:.1f} DOTS · сумма {g(tot)} кг" if tot else '[color=8d90a0]Пока без рейтинга[/color]')))
    lf = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
    for t, v in (('Присед', sq), ('Жим', bp), ('Тяга', dl)):
        lf.add_widget(L(text=f'[color=8d90a0]{t}[/color]\n[size=24sp][b]{g(v)}[/b][/size]', halign='center', size_hint_y=1))
    top.add_widget(lf)
    fb = follow_btn(u)
    if fb:
        top.add_widget(fb)
    ch = [top]
    info = [f"[color=8d90a0]{t.split(',')[0]}[/color]  {esc(g(p[k]) if n else p[k])}" for k, t, n in SPORT if p.get(k)]
    if info:
        sc = Card()
        sc.add_widget(L(text='[size=18sp][b]Спортивная информация[/b][/size]'))
        sc.add_widget(L(text='\n'.join(info)))
        ch.append(sc)
    if u == D.uid:
        e = Btn(text='Редактировать профиль', bg=CARD2, fg=TX)
        e.bind(on_release=lambda *a: app.go('edit'))
        o = Btn(text='Выйти из аккаунта', bg=CARD, fg=MU)
        o.bind(on_release=lambda *a: app.logout())
        ch += [e, o]
    ch.append(L(text='[size=20sp][b]Актуальная форма[/b][/size]'))
    if u == D.uid:
        a = Btn(text='+ Добавить фото или видео формы')
        a.bind(on_release=lambda *a: app.go('compose', 'form'))
        ch.append(a)
    if forms:
        cell = (Window.width - dp(24) - dp(8)) / 3
        gr = GridLayout(cols=3, spacing=dp(4), size_hint_y=None, row_force_default=True, row_default_height=cell)
        gr.bind(minimum_height=gr.setter('height'))
        for i, w in enumerate(forms):
            if w['media_type'] == 'v':
                t = Btn(text='▶', bg=CARD2, fg=TX)
                t.height = cell
            else:
                t = Thumb(source=media_url(w['media_path']), allow_stretch=True, keep_ratio=False)
            t.bind(on_release=lambda x, i=i: open_media(forms, i))
            gr.add_widget(t)
        ch.append(gr)
    else:
        ch.append(L(text='[color=8d90a0]Фото и короткие видео формы пока не добавлены.[/color]'))
    ch.append(L(text='[size=20sp][b]Тренировки[/b][/size]'))
    ch += [post_card(w) for w in posts[:15]] or [L(text='[color=8d90a0]Постов пока нет.[/color]')]
    return scroll(ch)


def v_edit(_):
    app = App.get_running_app()
    p = D.P.get(D.uid) or {}
    c = Card()
    f = {}
    c.add_widget(L(text='[size=20sp][b]Профиль[/b][/size]'))
    for k, t, n in [('username', 'Ник', 0), ('city', 'Город', 0), ('bio', 'О себе (до 300 знаков)', 0)] + SPORT + LIFTS:
        c.add_widget(L(text=f'[color=8d90a0]{t}[/color]'))
        f[k] = inp(t, '' if p.get(k) is None else (g(p[k]) if n else str(p[k])), bool(n))
        c.add_widget(f[k])
    sex = {'v': p.get('sex') or 'm'}
    sb = Btn(text='Пол: ' + ('женщина' if sex['v'] == 'f' else 'мужчина'), bg=CARD2, fg=TX)

    def flip(*a):
        sex['v'] = 'f' if sex['v'] == 'm' else 'm'
        sb.text = 'Пол: ' + ('женщина' if sex['v'] == 'f' else 'мужчина')
    sb.bind(on_release=flip)
    c.add_widget(sb)
    save = Btn(text='Сохранить')

    def do(*a):
        body = {'sex': sex['v']}
        for k, t, n in [('username', '', 0), ('city', '', 0), ('bio', '', 0)] + SPORT + LIFTS:
            v = f[k].text.strip().replace(',', '.') if n else f[k].text.strip()
            body[k] = (float(v) if v else None) if n else (v or None)
        body['username'] = body['username'] or name_of(D.uid)

        def ok(_):
            D.P[D.uid] = {**p, **body}
            app.toast('Сохранено')
            app.back()
        bg(lambda: rq('PATCH', f'/rest/v1/profiles?id=eq.{D.uid}', json=body, headers={'Prefer': 'return=minimal'}), ok)
    save.bind(on_release=do)
    c.add_widget(save)
    return scroll([c])


def pick(cb):
    if not filechooser:
        return App.get_running_app().toast('Выбор файлов недоступен')
    filechooser.open_file(on_selection=lambda s: s and Clock.schedule_once(lambda dt: cb(s[0])),
                          filters=[['Фото и видео', '*.jpg', '*.jpeg', '*.png', '*.webp', '*.mp4', '*.mov', '*.m4v']])


def upload(path):
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    video = ext in VIDEO_EXT
    if video:
        if os.path.getsize(path) > 20 * 1024 * 1024:
            raise RuntimeError('Видео больше 20 МБ. Выберите ролик покороче.')
        data, ct, ext = open(path, 'rb').read(), 'video/quicktime' if ext == 'mov' else 'video/mp4', ext
    else:
        from PIL import Image
        import io
        im = Image.open(path).convert('RGB')
        im.thumbnail((1080, 1080))
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=85)
        data, ct, ext = buf.getvalue(), 'image/jpeg', 'jpg'
    name = f'{D.uid}/{int(time.time() * 1000)}.{ext}'
    rq('POST', '/storage/v1/object/media/' + name, data=data, headers={'Content-Type': ct})
    return name, 'v' if video else 'i'


def v_compose(kind):
    app = App.get_running_app()
    form = kind == 'form'
    c = Card()
    c.add_widget(L(text='[size=20sp][b]' + ('Актуальная форма' if form else 'Новая тренировка') + '[/b][/size]'))
    chosen = {'p': None}
    pb = Btn(text='Выбрать фото или видео (видео до 20 МБ)', bg=CARD2, fg=TX)
    pb.bind(on_release=lambda *a: pick(lambda p: (chosen.update(p=p), setattr(pb, 'text', 'Выбрано: ' + os.path.basename(p)))))
    c.add_widget(pb)
    f = {}
    spec = [('note', 'Подпись')] if form else [('ex', 'Упражнение'), ('kg', 'Вес, кг'), ('reps', 'Повторы'), ('sets', 'Подходы'), ('note', 'Подпись')]
    for k, t in spec:
        f[k] = inp(t, num=k in ('kg', 'reps', 'sets'))
        c.add_widget(f[k])
    go = Btn(text='Опубликовать')

    def submit(*a):
        if form and not chosen['p']:
            return app.toast('Выберите фото или видео')
        if not form and not f['ex'].text.strip():
            return app.toast('Укажите упражнение')
        go.disabled, go.text = True, 'Публикуем…'
        n = lambda k: float((f[k].text or '0').replace(',', '.'))

        def run():
            row = {'user_id': D.uid, 'note' if not form else 'caption': f['note'].text.strip() or None}
            if chosen['p']:
                row['media_path'], row['media_type'] = upload(chosen['p'])
            if form:
                rq('POST', '/rest/v1/form_posts', json=row, headers={'Prefer': 'return=minimal'})
            else:
                row.update(ex=f['ex'].text.strip(), kg=n('kg'), reps=int(n('reps')), sets=int(n('sets')))
                rq('POST', '/rest/v1/posts', json=row, headers={'Prefer': 'return=minimal'})

        def fin(_):
            app.load_all(first=False)
            app.go('user' if form else 'feed', D.uid if form else None, root=True)
        bg(run, fin)
        Clock.schedule_once(lambda dt: setattr(go, 'disabled', False) or setattr(go, 'text', 'Опубликовать'), 30)
    go.bind(on_release=submit)
    c.add_widget(go)
    return scroll([c])


VIEWS = {'auth': v_auth, 'feed': v_feed, 'rank': v_rank, 'user': v_user, 'edit': v_edit, 'compose': v_compose}


class IronApp(App):
    tx = ListProperty(TX)
    mode = 'in'

    def build(self):
        Builder.load_string(KV)
        Window.clearcolor = BG
        Window.softinput_mode = 'below_target'
        Window.bind(on_keyboard=self.on_key)
        self.stack = []
        root = BoxLayout(orientation='vertical')
        self.hd = BoxLayout(size_hint_y=None, height=dp(52), padding=[dp(10), 0], spacing=dp(8))
        self.bk = Btn(text='‹', bg=BG, fg=TX, size_hint=(None, None), size=(dp(40), dp(40)), font_size=dp(26))
        self.bk.bind(on_release=lambda *a: self.back())
        self.ttl = L(text='[size=24sp][b]Железный круг[/b][/size]', size_hint_y=1, valign='middle')
        self.hd.add_widget(self.bk)
        self.hd.add_widget(self.ttl)
        self.note = L(text='', size_hint_y=None, height=0, color=ACC)
        self.body = BoxLayout()
        self.nav = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(4), padding=dp(4))
        for t, n, a in (('Лента', 'feed', None), ('Рейтинг', 'rank', None), ('+', 'compose', 'post'), ('Профиль', 'user', None)):
            b = Btn(text=t, bg=CARD, fg=TX if n != 'compose' else INK)
            if n == 'compose':
                b.bg = ACC
            b.bind(on_release=lambda x, n=n, a=a: self.go(n, a, root=True))
            self.nav.add_widget(b)
        for w in (self.hd, self.note, self.body, self.nav):
            root.add_widget(w)
        return root

    def on_start(self):
        self.go('auth', root=True)

        def restore():
            try:
                with open(sess_file()) as f:
                    D.rt = json.load(f)['rt']
            except Exception:
                return False
            return refresh_token()
        bg(restore, lambda ok: self.load_all(first=True) if ok else None)

    def toast(self, msg):
        self.note.text, self.note.height = esc(str(msg)), dp(36)
        Clock.unschedule(self._clr)
        Clock.schedule_once(self._clr, 5)

    def _clr(self, dt):
        self.note.text, self.note.height = '', 0

    def load_all(self, first=False):
        def f():
            q = lambda t, extra='': rq('GET', f'/rest/v1/{t}?select=*{extra}')
            return (q('profiles'), q('follows'), q('posts', '&order=created_at.desc&limit=200'),
                    q('form_posts', '&order=created_at.desc&limit=200'))

        def ok(r):
            D.P = {p['id']: p for p in r[0]}
            D.FO, D.PO, D.FM = r[1], r[2], r[3]
            if first:
                self.go('feed', root=True)
            elif self.stack[-1][0] in ('feed', 'rank', 'user'):
                self.render()
        bg(f, ok)

    def go(self, name, arg=None, root=False):
        if name == 'user' and arg is None:
            arg = D.uid
        if root:
            self.stack = []
        self.stack.append((name, arg))
        self.render()

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.render()

    def render(self):
        n, a = self.stack[-1]
        self.body.clear_widgets()
        self.body.add_widget(VIEWS[n](a))
        self.bk.opacity = 1 if len(self.stack) > 1 and D.uid else 0
        self.bk.disabled = not (len(self.stack) > 1 and D.uid)
        self.nav.height, self.nav.opacity = (dp(54), 1) if D.uid else (0, 0)

    def on_key(self, w, key, *a):
        if key == 27 and len(self.stack) > 1:
            self.back()
            return True
        return False

    def logout(self):
        try:
            os.remove(sess_file())
        except Exception:
            pass
        D.tok = D.rt = D.uid = None
        D.P, D.FO, D.PO, D.FM = {}, [], [], []
        self.go('auth', root=True)


if __name__ == '__main__':
    IronApp().run()
