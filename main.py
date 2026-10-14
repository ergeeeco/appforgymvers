# Железный круг: Android-клиент на Python (Kivy). Бэкенд: тот же Supabase, что и у веб-версии.
import io, os, json, time, math, threading, webbrowser
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import requests, certifi
os.environ.setdefault('SSL_CERT_FILE', certifi.where())
from kivy.config import Config
Config.set('graphics', 'multisamples', '0')
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import (Color, Ellipse, Line, PopMatrix, PushMatrix, Rectangle, Rotate, RoundedRectangle,
                           StencilPop, StencilPush, StencilUnUse, StencilUse, Triangle)
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ColorProperty, ListProperty, NumericProperty, StringProperty
from kivy.utils import get_color_from_hex as hx, escape_markup as esc
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.carousel import Carousel
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.core.image import Image as CoreImage
from kivy.uix.image import AsyncImage, Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.stacklayout import StackLayout
from kivy.uix.widget import Widget
from kivy.uix.textinput import TextInput
try:
    from kivy.core.video import Video as _CV
    from kivy.uix.video import Video
    if _CV is None:
        Video = None
except Exception:
    Video = None
try:
    from plyer import filechooser
except Exception:
    filechooser = None

# ===== НАСТРОЙКА: Project URL и anon public key из Supabase (Settings → API) =====
try:
    from config import URL as SUPABASE_URL, KEY as SUPABASE_KEY  # файл config.py рядом с main.py
except Exception:
    SUPABASE_URL = 'https://XXXX.supabase.co'
    SUPABASE_KEY = 'ВСТАВЬТЕ_ANON_KEY'
# service_role ключ сюда вставлять НЕЛЬЗЯ: он даёт полный доступ к базе.
# =================================================================================
BASE = SUPABASE_URL.strip().rstrip('/')
KEY = SUPABASE_KEY.strip()
# ===== Дизайн-система M3: палитра генерируется из seed-цвета =====
SEEDS = [('Энергия', '#22B35A', '#FFB020'), ('Изумруд', '#0FA968', '#FF8A5C'), ('Лайм', '#8BC400', '#FF6B6B'),
         ('Мята', '#00B894', '#FF7AA2'), ('Хвоя', '#2E8B57', '#E0B345'), ('Фиолет', '#7C5CFF', '#FF5C8A'),
         ('Океан', '#2E7BFF', '#FFB020'), ('Закат', '#FF8A3D', '#B05CFF'), ('Роза', '#E0457B', '#45C7E0'),
         ('Лазурь', '#00A3C4', '#FF8A5C'), ('Индиго', '#4C5BD4', '#E0B345'), ('Графит', '#5E6A74', '#E0A35C')]
THEME = {'seed': 0, 'mode': 'dark', 'shape': 1.0}   # режимы: light, dark, oled
HX = {'acc': 'b7ff2a', 'mu': '99a1a8'}
_D = 6 / 29


def _lin(u):
    return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4


def _gam(u):
    return 12.92 * u if u <= 0.0031308 else 1.055 * u ** (1 / 2.4) - 0.055


def to_lch(rgb):
    r, g, b = (_lin(v) for v in rgb[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > _D ** 3 else t / (3 * _D * _D) + 4 / 29
    fx, fy, fz = f(x), f(y), f(z)
    a_, b_ = 500 * (fx - fy), 200 * (fy - fz)
    return 116 * fy - 16, math.hypot(a_, b_), math.degrees(math.atan2(b_, a_)) % 360


def lch_rgb(L, c, h):
    """Тон L (0..100, как tone в M3), хрома c, оттенок h -> RGBA; хрома уменьшается до попадания в sRGB."""
    if L <= 0:
        return (0, 0, 0, 1)
    if L >= 100:
        return (1, 1, 1, 1)
    finv = lambda t: t ** 3 if t > _D else 3 * _D * _D * (t - 4 / 29)
    while True:
        a_, b_ = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
        fy = (L + 16) / 116
        x, y, z = 0.95047 * finv(fy + a_ / 500), finv(fy), 1.08883 * finv(fy - b_ / 200)
        lin = (3.2406 * x - 1.5372 * y - 0.4986 * z, -0.9689 * x + 1.8758 * y + 0.0415 * z, 0.0557 * x - 0.2040 * y + 1.0570 * z)
        if c <= 0.3 or all(-0.001 <= v <= 1.001 for v in lin):
            return tuple(_gam(min(1, max(0, v))) for v in lin) + (1,)
        c -= 1.0


def harmonize(rgb, h_to):
    L, c, h = to_lch(rgb)
    diff = ((h_to - h + 540) % 360) - 180
    return lch_rgb(L, c, (h + min(15, abs(diff) * 0.5) * (1 if diff > 0 else -1)) % 360)


def make_scheme(seed1, seed3, mode):
    h1, h3 = to_lch(hx(seed1))[2], to_lch(hx(seed3))[2]
    P = lambda t: lch_rgb(t, 64, h1)
    S = lambda t: lch_rgb(t, 16, h1)
    T = lambda t: lch_rgb(t, 60, h3)
    N = lambda t: lch_rgb(t, 6, h1)
    V = lambda t: lch_rgb(t, 10, h1)
    d = mode != 'light'
    hi = N(22) if d else N(90)
    return dict(
        bg=(0, 0, 0, 1) if mode == 'oled' else N(6) if d else N(98),
        card=N(4) if mode == 'oled' else N(10) if d else N(96),
        hi=hi, tx=N(90) if d else N(10), mu=V(80) if d else V(30),
        pri=P(80) if d else P(40), onpri=P(20) if d else P(100),
        pric=P(30) if d else P(90), onpric=P(90) if d else P(10),
        sec=S(30) if d else S(90), onsec=S(90) if d else S(10),
        ter=T(80) if d else T(40), onter=T(20) if d else T(100),
        line=V(30) if d else V(80), like=harmonize(hx('#FF3D6E'), h1),
        heat=[hi] + ([P(25), P(40), P(60), P(80)] if d else [P(85), P(70), P(55), P(40)]))


def to_hex(c):
    return '%02x%02x%02x' % tuple(round(v * 255) for v in c[:3])


def compute_globals():
    global BG, CARD, CARD2, TX, MU, ACC, INK, PRC, ONPRC, SEC, ONSEC, TER, ONTER, LINE, LIKE, HEAT
    n, s1, s3 = SEEDS[THEME['seed']]
    sc = make_scheme(s1, s3, THEME['mode'])
    BG, CARD, CARD2, TX, MU = sc['bg'], sc['card'], sc['hi'], sc['tx'], sc['mu']
    ACC, INK, PRC, ONPRC = sc['pri'], sc['onpri'], sc['pric'], sc['onpric']
    SEC, ONSEC, TER, ONTER = sc['sec'], sc['onsec'], sc['ter'], sc['onter']
    LINE, LIKE, HEAT = sc['line'], sc['like'], sc['heat']
    HX['acc'], HX['mu'] = to_hex(ACC), to_hex(MU)


compute_globals()

# Шрифты дизайн-системы: положите файлы в папку fonts/ (см. README). Без них работает стандартный Roboto.
DISPLAY = ''


def setup_fonts():
    global DISPLAY
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    f = lambda n: os.path.join(d, n)
    try:
        if os.path.exists(f('Onest-Regular.ttf')):
            bold = f('Onest-SemiBold.ttf') if os.path.exists(f('Onest-SemiBold.ttf')) else f('Onest-Regular.ttf')
            LabelBase.register(name='Roboto', fn_regular=f('Onest-Regular.ttf'), fn_bold=bold)
        if os.path.exists(f('Unbounded-SemiBold.ttf')):
            LabelBase.register(name='Display', fn_regular=f('Unbounded-SemiBold.ttf'))
            DISPLAY = 'Display'
    except Exception:
        DISPLAY = ''


setup_fonts()


def dfont(text):
    return f'[font={DISPLAY}]{text}[/font]' if DISPLAY else f'[b]{text}[/b]'
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
            radius: [min(self.height / 2, app.r_btn)]
<Card>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(12)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: app.c_card
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [app.r_card]
<Plate>:
    size_hint: None, None
    size: dp(44), dp(44)
    bold: True
    color: app.c_onpric
    canvas.before:
        Color:
            rgba: app.c_pric
        Ellipse:
            pos: self.pos
            size: self.size
<Chip>:
    size_hint: None, None
    size: self.texture_size[0] + dp(20), dp(30)
    font_size: sp(12)
    bold: True
    color: app.c_onter if self.hot else app.tx
    canvas.before:
        Color:
            rgba: app.c_ter if self.hot else app.c_hi
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8) * app.shape]
<Pill>:
    canvas.before:
        Color:
            rgba: app.c_hi
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.height / 2]
<IconBtn>:
    canvas.before:
        Color:
            rgba: self.bgc
        Ellipse:
            pos: self.pos
            size: self.size
<ExRow>:
    size_hint_y: None
    height: dp(64)
    padding: dp(14), dp(8)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: app.c_sec if self.sel else app.c_hi
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
<Indicator>:
    size_hint: None, None
    size: dp(64), dp(32)
    canvas.before:
        Color:
            rgba: app.c_sec if self.on else (0, 0, 0, 0)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
'''


class L(Label):
    def on_text(self, inst, v):  # цвета-заглушки в разметке заменяются цветами текущей темы
        n = v.replace('b7ff2a', HX['acc']).replace('99a1a8', HX['mu'])
        if n != v:
            self.text = n
class LB(ButtonBehavior, L): pass
class Card(BoxLayout): pass
class Plate(ButtonBehavior, Label):
    c = ColorProperty([1, 1, 1, 1])
class Btn(Button):
    bg = ColorProperty([1, 1, 1, 1])
    fg = ColorProperty([0, 0, 0, 1])

    def __init__(self, **kw):
        kw.setdefault('bg', ACC)
        kw.setdefault('fg', INK)
        super().__init__(**kw)
class Thumb(ButtonBehavior, AsyncImage): pass
class CardB(ButtonBehavior, Card): pass
class Chip(Label):
    hot = BooleanProperty(False)


_TEX = {}
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
_ICON_TEX = {}


def icon_tex(name):
    """Иконка из icons/<имя>.png. Подходит любой одноцветный PNG: он перекрашивается в цвет темы.
    Если файла нет, возвращается None и рисуется встроенная иконка."""
    if name in _ICON_TEX:
        return _ICON_TEX[name]
    tex = None
    p = os.path.join(ICON_DIR, name + '.png')
    if os.path.exists(p):
        try:
            from PIL import Image as PI, ImageOps
            im = PI.open(p).convert('RGBA')
            alpha = im.split()[3]
            if alpha.getextrema()[0] == 255:       # нет прозрачности: чёрное на белом, берём яркость как маску
                alpha = ImageOps.invert(im.convert('L'))
            white = PI.new('RGBA', im.size, (255, 255, 255, 255))
            white.putalpha(alpha)
            buf = io.BytesIO()
            white.save(buf, 'PNG')
            buf.seek(0)
            tex = CoreImage(buf, ext='png').texture
        except Exception:
            try:
                tex = CoreImage(p).texture
            except Exception:
                tex = None
        if tex:
            tex.mag_filter = tex.min_filter = 'linear'
    _ICON_TEX[name] = tex
    return tex


_POOL = ThreadPoolExecutor(max_workers=4)


def load_tex(src, done):
    """Загружает картинку (адрес или файл) и вызывает done(текстура, размытая_текстура) в главном потоке.
    Скачивание и декодирование идут в фоне, в главном потоке остаётся только загрузка в видеопамять."""
    if src in _TEX:
        return done(*_TEX[src])

    def prepare():
        try:
            data = None
            if src.startswith('http'):
                r = requests.get(src, timeout=30)
                r.raise_for_status()
                data = r.content
            ext = os.path.splitext(src.split('?')[0])[1].lstrip('.') or 'jpg'
            ci = CoreImage(io.BytesIO(data), ext=ext) if data else CoreImage(src)
        except Exception:
            return None, None
        blur = None
        try:  # маленькая размытая копия: фон для фото, которые не влезли в рамку
            from PIL import Image as PI, ImageFilter
            im = PI.open(io.BytesIO(data) if data else src)
            im.draft('RGB', (96, 96))
            im = im.convert('RGB').resize((24, 24)).filter(ImageFilter.GaussianBlur(2))
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            blur = buf.getvalue()
        except Exception:
            pass
        return ci, blur

    def finish(res):
        ci, blur = res
        if ci is None:
            return done(None, None)
        try:
            tex = ci.texture
        except Exception:
            return done(None, None)
        bt = None
        if blur:
            try:
                bt = CoreImage(io.BytesIO(blur), ext='png').texture
                bt.mag_filter = bt.min_filter = 'linear'
            except Exception:
                bt = None
        if len(_TEX) > 60:
            _TEX.clear()
        _TEX[src] = (tex, bt)
        done(tex, bt)

    _POOL.submit(lambda: (lambda res: Clock.schedule_once(lambda dt_: finish(res)))(prepare()))


class Pill(BoxLayout): pass
class Indicator(FloatLayout):
    on = BooleanProperty(False)


class Icon(Widget):
    """Простые векторные иконки, нарисованные линиями (без шрифта иконок)."""
    name = StringProperty('home')
    color = ColorProperty([1, 1, 1, 1])
    filled = BooleanProperty(False)
    dot = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self.draw, size=self.draw, color=self.draw, name=self.draw, filled=self.draw, dot=self.draw)
        self.draw()

    def draw(self, *a):
        self.canvas.clear()
        x, y, w, h = self.x, self.y, self.width, self.height
        P = lambda u, v: (x + u * w, y + v * h)
        fl = lambda *pts: [c for p in pts for c in p]
        lw, n = dp(1.8), self.name
        with self.canvas:
            Color(*self.color)
            tex = (icon_tex(n + '-fill') if self.filled else None) or icon_tex(n)
            if tex:
                Rectangle(texture=tex, pos=self.pos, size=self.size)
                if self.dot:
                    Color(1, .23, .23, 1)
                    Ellipse(pos=P(.36, -.04), size=(.28 * w, .28 * h))
                return
            if n == 'home':
                Line(points=fl(P(.1, .48), P(.5, .92), P(.9, .48), P(.9, .1), P(.1, .1)), close=True, width=lw)
            elif n == 'search':
                Line(circle=(x + .42 * w, y + .58 * h, .3 * w), width=lw)
                Line(points=fl(P(.64, .36), P(.92, .08)), width=lw)
            elif n == 'add':
                Line(rounded_rectangle=(x + .08 * w, y + .08 * h, .84 * w, .84 * h, dp(6)), width=lw)
                Line(points=fl(P(.5, .3), P(.5, .7)), width=lw)
                Line(points=fl(P(.3, .5), P(.7, .5)), width=lw)
            elif n == 'rank':
                for u, v in ((.2, .5), (.5, .92), (.8, .3)):
                    Line(points=fl(P(u, .1), P(u, v)), width=dp(3))
            elif n == 'user':
                Line(circle=(x + .5 * w, y + .7 * h, .2 * w), width=lw)
                Line(circle=(x + .5 * w, y + .02 * h, .38 * w, -90, 90), width=lw)
            elif n == 'comment':
                Line(rounded_rectangle=(x + .06 * w, y + .22 * h, .88 * w, .68 * h, dp(6)), width=lw)
                Line(points=fl(P(.25, .22), P(.2, .04), P(.45, .22)), width=lw)
            elif n == 'trash':
                Line(points=fl(P(.12, .8), P(.88, .8)), width=lw)
                Line(points=fl(P(.38, .8), P(.38, .94), P(.62, .94), P(.62, .8)), width=lw)
                Line(points=fl(P(.2, .8), P(.27, .06), P(.73, .06), P(.8, .8)), width=lw)
                Line(points=fl(P(.42, .6), P(.42, .26)), width=lw)
                Line(points=fl(P(.58, .6), P(.58, .26)), width=lw)
            elif n in ('follow', 'following'):
                Line(circle=(x + .36 * w, y + .7 * h, .17 * w), width=lw)
                Line(circle=(x + .36 * w, y + .0 * h, .32 * w, -90, 90), width=lw)
                if n == 'follow':
                    Line(points=fl(P(.68, .74), P(.96, .74)), width=lw)
                    Line(points=fl(P(.82, .6), P(.82, .88)), width=lw)
                else:
                    Line(points=fl(P(.66, .72), P(.77, .6), P(.96, .86)), width=lw)
            elif n == 'send':
                Line(points=fl(P(.08, .88), P(.94, .5), P(.08, .12), P(.26, .5)), close=True, width=lw)
                Line(points=fl(P(.26, .5), P(.6, .5)), width=lw)
            elif n == 'close':
                Line(points=fl(P(.2, .2), P(.8, .8)), width=lw)
                Line(points=fl(P(.8, .2), P(.2, .8)), width=lw)
            elif n == 'barbell':
                Line(points=fl(P(.06, .5), P(.94, .5)), width=lw)
                for u0, u1, v0 in ((.2, .1, .22), (.32, .1, .3)):
                    Line(rounded_rectangle=(x + u0 * w, y + v0 * h, u1 * w, (1 - 2 * v0) * h, dp(2)), width=lw)
                    Line(rounded_rectangle=(x + (1 - u0 - u1) * w, y + v0 * h, u1 * w, (1 - 2 * v0) * h, dp(2)), width=lw)
            elif n == 'bell':
                Line(bezier=fl(P(.2, .32), P(.2, .9), P(.38, .96), P(.5, .96)), width=lw)
                Line(bezier=fl(P(.5, .96), P(.62, .96), P(.8, .9), P(.8, .32)), width=lw)
                Line(points=fl(P(.2, .32), P(.1, .22), P(.9, .22), P(.8, .32)), width=lw)
                Line(points=fl(P(.5, .96), P(.5, 1.0)), width=lw)
                if self.dot:
                    Color(1, .23, .23, 1)
                    Ellipse(pos=P(.36, -.04), size=(.28 * w, .28 * h))
                else:
                    Line(circle=(x + .5 * w, y + .1 * h, .1 * w, 90, 270), width=lw)
            elif n == 'heart':
                if self.filled:
                    Ellipse(pos=P(.04, .46), size=(.48 * w, .48 * h))
                    Ellipse(pos=P(.48, .46), size=(.48 * w, .48 * h))
                    Triangle(points=fl(P(.07, .58), P(.93, .58), P(.5, .05)))
                else:
                    for q in ((.5, .08, .08, .42, 0, .72, .25, .88), (.25, .88, .4, .98, .5, .9, .5, .78),
                              (.5, .78, .5, .9, .6, .98, .75, .88), (.75, .88, 1, .72, .92, .42, .5, .08)):
                        Line(bezier=fl(P(q[0], q[1]), P(q[2], q[3]), P(q[4], q[5]), P(q[6], q[7])), width=lw)


class ActionBtn(ButtonBehavior, BoxLayout):
    """Иконка и счётчик внутри «таблетки» действий карточки поста."""
    def __init__(self, icon, count, active=False, **kw):
        super().__init__(orientation='horizontal', spacing=dp(6), padding=[dp(14), 0], size_hint=(None, 1), **kw)
        self.icon = icon
        self.ic = Icon(name=icon, size_hint=(None, None), size=(dp(22), dp(22)), pos_hint={'center_y': .5})
        self.lb = Label(font_size=dp(13), bold=True, size_hint=(None, 1))
        self.lb.bind(texture_size=self._fit)
        self.add_widget(self.ic)
        self.add_widget(self.lb)
        self.set(active, count)

    def _fit(self, lb, ts):
        lb.width = ts[0]
        self.width = dp(28) + dp(22) + dp(6) + ts[0]

    def set(self, active, count):
        self.ic.filled = bool(active) and self.icon == 'heart'
        self.ic.color = LIKE if active else MU
        self.lb.color = LIKE if active else TX
        self.lb.text = str(count)


class NavItem(ButtonBehavior, BoxLayout):
    """Пункт M3 Navigation Bar: иконка в пилюле-индикаторе и подпись."""
    def __init__(self, text, icon, **kw):
        super().__init__(orientation='vertical', padding=[0, dp(12), 0, dp(8)], spacing=dp(4), **kw)
        self.ind = Indicator(pos_hint={'center_x': .5})
        self.ic = Icon(name=icon, size_hint=(None, None), size=(dp(24), dp(24)), pos_hint={'center_x': .5, 'center_y': .5})
        self.ind.add_widget(self.ic)
        self.lb = Label(text=text, font_size=dp(12), size_hint_y=None, height=dp(16))
        self.add_widget(self.ind)
        self.add_widget(self.lb)
        self.set_active(False)

    def set_active(self, on):
        self.ind.on = on
        self.ic.color = ONSEC if on else MU
        self.ic.filled = on   # активный пункт использует заполненный вариант иконки, если он есть
        self.lb.color = TX if on else MU
        self.lb.bold = on


class BellBtn(ButtonBehavior, FloatLayout):
    """Кнопка уведомлений: только колокольчик на круглой тональной подложке, красная точка = есть новое."""
    def __init__(self, **kw):
        super().__init__(size_hint=(None, None), size=(dp(44), dp(44)), **kw)
        self.ic = Icon(name='bell', size_hint=(None, None), size=(dp(26), dp(26)),
                       pos_hint={'center_x': .5, 'center_y': .55}, color=TX)
        self.add_widget(self.ic)


class Dumbbell(Widget):
    """Маленькая вращающаяся гантель: показывается, пока что-то загружается."""
    angle = NumericProperty(0)

    def __init__(self, **kw):
        kw.setdefault('size', (dp(44), dp(44)))
        super().__init__(size_hint=(None, None), **kw)
        self._rot = None
        self.bind(pos=self.draw, size=self.draw, angle=self._set_angle)
        self.draw()

    def on_parent(self, w, p):
        Animation.cancel_all(self)
        if p:
            self._spin()

    def _spin(self, *a):
        if not self.parent:
            return
        self.angle = 0
        an = Animation(angle=360, duration=1.1, t='in_out_quad')
        an.bind(on_complete=self._spin)
        an.start(self)

    def _set_angle(self, *a):   # поворот меняется у готовой инструкции, холст не перерисовывается
        if self._rot is not None:
            self._rot.angle = self.angle

    def draw(self, *a):
        self.canvas.clear()
        cx, cy = self.center
        k = min(self.size)
        with self.canvas:
            PushMatrix()
            self._rot = Rotate(angle=self.angle, origin=(cx, cy))
            Color(*MU)
            RoundedRectangle(pos=(cx - .36 * k, cy - .04 * k), size=(.72 * k, .08 * k), radius=[.04 * k])
            Color(*ACC)
            for sx in (-1, 1):
                RoundedRectangle(pos=(cx + sx * .24 * k - .06 * k, cy - .22 * k), size=(.12 * k, .44 * k), radius=[.04 * k])
                RoundedRectangle(pos=(cx + sx * .37 * k - .05 * k, cy - .15 * k), size=(.10 * k, .30 * k), radius=[.03 * k])
            PopMatrix()


class Photo(FloatLayout):
    """Фото как в соцсетях. Картинка рисуется прямо в этом виджете (без вложенных, поэтому не «съезжает»).
    fit='adaptive' (лента): рамка повторяет пропорции снимка в пределах от 4:5 до 1.91:1; если снимок ещё
    шире или выше, он вписывается целиком поверх размытого фона и ничего не обрезается.
    fit='cover': плитка с обрезкой по центру. fit='contain': вписать целиком."""
    def __init__(self, source='', fit='adaptive', ratio=None, **kw):
        super().__init__(**kw)
        self.fit, self.ratio, self.tex, self.blur = fit, ratio, None, None
        self._crops = {}
        self.dumb = Dumbbell(size=(dp(40), dp(40)), pos_hint={'center_x': .5, 'center_y': .5})
        self.bind(pos=self.draw, size=self.draw)
        if fit == 'adaptive':
            self.bind(width=self._adapt)
            self.height = (Window.width - dp(56)) / self._box_ratio()
        self.set(source)

    def _box_ratio(self):
        r = self.ratio or (self.tex.width / self.tex.height if self.tex else .8)
        return min(max(r, .8), 1.91)

    def _adapt(self, *a):
        if self.fit == 'adaptive' and self.width > 2:
            h = min(self.width / self._box_ratio(), Window.height * .72)
            if abs(self.height - h) > 1:
                self.height = h

    def set(self, source):
        if self.dumb.parent:
            self.remove_widget(self.dumb)
        self.tex = self.blur = None
        self._crops = {}
        self.draw()
        if source:
            self.add_widget(self.dumb)
            load_tex(source, self._got)

    def _got(self, tex, blur):
        self.tex, self.blur = tex, blur
        if self.dumb.parent:
            self.remove_widget(self.dumb)
        self._adapt()
        self.draw()

    def _crop(self, t, w, h):
        key = (id(t), round(w), round(h))
        c = self._crops.get(key)
        if c is None:
            if len(self._crops) > 6:
                self._crops.clear()
            ta, ba = t.width / t.height, w / h
            rw, rh = (t.height * ba, t.height) if ta > ba else (t.width, t.width / ba)
            c = self._crops[key] = t.get_region((t.width - rw) / 2, (t.height - rh) / 2, rw, rh)
        return c

    def draw(self, *a):
        self.canvas.before.clear()
        x, y, w, h = self.x, self.y, self.width, self.height
        if w < 2 or h < 2:
            return
        r = App.get_running_app().r_media or dp(16)
        t = self.tex
        with self.canvas.before:
            Color(*CARD2)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            if t:
                StencilPush()
                RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
                StencilUse()
                ta, ba = t.width / t.height, w / h
                Color(1, 1, 1, 1)
                if self.fit == 'cover' or (self.fit == 'adaptive' and abs(ta - ba) < .03):
                    Rectangle(texture=self._crop(t, w, h), pos=self.pos, size=self.size)
                else:
                    if self.fit == 'adaptive' and self.blur:
                        Color(.65, .65, .65, 1)
                        Rectangle(texture=self._crop(self.blur, w, h), pos=self.pos, size=self.size)
                        Color(1, 1, 1, 1)
                    dw, dh = (w, w / ta) if ta > ba else (h * ta, h)
                    Rectangle(texture=t, pos=(x + (w - dw) / 2, y + (h - dh) / 2), size=(dw, dh))
                StencilUnUse()
                RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
                StencilPop()


class PhotoB(ButtonBehavior, Photo): pass


class DayCell(Label):
    """День календаря: цвет по числу тренировок, рамка у сегодняшнего дня."""
    def __init__(self, day, n, in_month, today, **kw):
        super().__init__(text=str(day.day), size_hint_y=None, font_size=dp(14), **kw)
        self.lvl, self.is_today = (min(n, 4) if in_month else 0), today
        if self.lvl:
            c = HEAT[self.lvl]
            self.color = (0, 0, 0, 1) if .299 * c[0] + .587 * c[1] + .114 * c[2] > .5 else (1, 1, 1, 1)
            self.bold = True
        else:
            self.color = TX if in_month else (MU[0], MU[1], MU[2], .4)
        self.bind(width=lambda i, w: setattr(i, 'height', w), pos=self.draw, size=self.draw)

    def draw(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.lvl:
                Color(*HEAT[self.lvl])
                RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            if self.is_today:
                Color(*TX)
                Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(10)), width=dp(1.4))


class IconBtn(ButtonBehavior, FloatLayout):
    """Круглая кнопка-иконка. Стили: filled (акцент), tonal (спокойная), danger (удаление), plain (без фона)."""
    bgc = ColorProperty([0, 0, 0, 0])

    def __init__(self, icon, style='tonal', size=40, **kw):
        super().__init__(size_hint=(None, None), size=(dp(size), dp(size)), **kw)
        self.sz = size
        self.ic = Icon(name=icon, size_hint=(None, None), size=(dp(size * .52), dp(size * .52)),
                       pos_hint={'center_x': .5, 'center_y': .5})
        self.add_widget(self.ic)
        self.set(icon, style)

    def set(self, icon, style):
        self.ic.name = icon
        self.bgc, self.ic.color = {'filled': (ACC, INK), 'tonal': (CARD2, TX), 'danger': (CARD2, (1, .38, .38, 1)),
                                   'plain': ((0, 0, 0, 0), MU), 'ghost': ((0, 0, 0, 0), ACC),
                                   'ghostmuted': ((0, 0, 0, 0), MU)}[style]
        k = .62 if style.startswith('ghost') else .52   # без подложки значок крупнее
        self.ic.size = (dp(self.sz * k), dp(self.sz * k))

    def on_disabled(self, w, v):
        self.opacity = .4 if v else 1


class TopScroll(ScrollView):
    """ScrollView, который при изменении высоты содержимого сохраняет позицию относительно верха.
    Обычный ScrollView держит долю прокрутки, поэтому при переключении вкладок страница «уезжает»."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self._off, self._adj = 0.0, False
        self.bind(scroll_y=self._track)

    def _total(self):
        c = self.children[0] if self.children else None
        return (c.height - self.height) if c else 0

    def _track(self, *a):
        if not self._adj:
            self._off = max(0.0, (1 - self.scroll_y) * self._total())

    def fix(self, *a):
        t = self._total()
        self._adj = True
        self.scroll_y = (1 - min(self._off, t) / t) if t > 0 else 1
        self._adj = False


class D:  # состояние
    tok = rt = uid = None
    P, FO, PO, FM = {}, [], [], []
    LK, CM = [], []
    loading = False
    bests = {}
    busy = 0
    ptab = 'form'
    rev = 0
    fol, prs = set(), set()
    nfol, nfing, likes, cmts, byuser, formsby = {}, {}, {}, {}, {}, {}
    _notes, _notes_rev = [], -1
    scope = 'all'
    seen = ''
    known, known_init = set(), False


def sess_file():
    return os.path.join(App.get_running_app().user_data_dir, 'session.json')


def read_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def cache_file():
    return os.path.join(App.get_running_app().user_data_dir, 'cache.json')


def save_cache():
    try:
        txt = json.dumps({'uid': D.uid, 'P': D.P, 'FO': D.FO, 'PO': D.PO, 'FM': D.FM, 'LK': D.LK, 'CM': D.CM})
        with open(cache_file(), 'w') as fh:
            fh.write(txt)
    except Exception:
        pass


def refresh_token():
    sess = read_json(sess_file()) or {}
    if sess.get('at') and sess.get('exp', 0) - time.time() > 60 and sess['at'] != D.tok:
        D.tok, D.rt, D.uid = sess['at'], sess.get('rt') or D.rt, sess.get('uid') or D.uid
        return True  # токен уже обновила фоновая служба
    rt = sess.get('rt') or D.rt
    if not rt:
        return False
    try:
        r = requests.post(BASE + '/auth/v1/token?grant_type=refresh_token', json={'refresh_token': rt},
                          headers={'apikey': KEY}, timeout=20)
        if r.status_code >= 400:
            return False
        set_session(r.json())
        return True
    except Exception:
        return None  # нет сети: сессия не признана недействительной


def set_session(d):
    D.tok, D.rt, D.uid = d['access_token'], d['refresh_token'], d['user']['id']
    exp = d.get('expires_at') or time.time() + d.get('expires_in', 3600)
    try:
        with open(sess_file(), 'w') as f:
            json.dump({'rt': D.rt, 'uid': D.uid, 'at': D.tok, 'exp': exp}, f)
    except Exception:
        pass


def data_file(name):
    return os.path.join(App.get_running_app().user_data_dir, name)


def load_settings():
    return read_json(data_file('settings.json')) or {}


def save_settings(d):
    try:
        with open(data_file('settings.json'), 'w') as fh:
            json.dump(d, fh)
    except Exception:
        pass


def rq(method, path, _retry=True, **kw):
    h = {'apikey': KEY, 'Authorization': 'Bearer ' + (D.tok or KEY)}
    if 'json' in kw or 'data' in kw:
        h['Content-Type'] = 'application/json'   # для запросов без тела (удаление файла) заголовок не нужен
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


def bg(fn, ok=None, quiet=False):
    D.busy += 1
    app = App.get_running_app()
    if app:
        app.set_busy()

    def run():
        try:
            res, err = fn(), None
        except Exception as e:
            res, err = None, str(e)
        def done(dt):
            D.busy -= 1
            a_ = App.get_running_app()
            if a_:
                a_.set_busy()
            if err:
                if not quiet:
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
is_f = lambda u: u in D.fol
followers = lambda u: D.nfol.get(u, 0)
media_url = lambda p: BASE + '/storage/v1/object/public/media/' + p


def _load_catalog():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'exercises.json'), encoding='utf-8') as fh:
            d = json.load(fh)
        return d['exercises'], d.get('kinds', {})
    except Exception:
        return [], {}


EXLIST, EXKINDS = _load_catalog()
EXBY = {e['id']: e for e in EXLIST}
EXCATS = list(dict.fromkeys(e['category'] for e in EXLIST))
norm = lambda t: str(t).lower().replace('ё', 'е').strip()
EXNAME = {norm(e['name']): e['id'] for e in EXLIST}
# старые записи, где упражнение было написано вручную
EXNAME.update({'присед': 'squat', 'приседания': 'squat', 'жим': 'bench_press', 'становая': 'deadlift', 'жим стоя': 'overhead_press'})


def exid_of(w):
    """Идентификатор упражнения поста (для старых постов определяется по названию)."""
    return w.get('exercise_id') or EXNAME.get(norm(w.get('ex') or ''), '')


def fnum(t):
    try:
        v = float(str(t).replace(',', '.'))
        return v if v > 0 else 0
    except Exception:
        return 0


def e1rm(kg, reps):
    """Расчётный максимум на 1 повтор (формула Эпли), с шагом 0,5 кг."""
    return round((kg * (1 + reps / 30) if reps > 1 else kg) * 2) / 2


def fmt_sec(t):
    return f'{t // 60} мин {t % 60} сек' if t >= 60 else f'{t} сек'


def sets_of(w):
    sd = w.get('sets_data')
    if isinstance(sd, list) and sd:
        return sd
    if w.get('reps') or w.get('kg'):
        return [{'kg': w.get('kg') or 0, 'reps': w.get('reps') or 0}] * (w.get('sets') or 1)
    return []


def kind_of(w):
    return (EXBY.get(exid_of(w)) or {}).get('kind', 'weight')


def summary_cols(kind, sets):
    """Лучший подход для колонок kg, reps в базе (по ним строятся рекорды и рейтинги)."""
    if kind == 'weight':
        t = max(sets, key=lambda x: (x['kg'], x['reps']))
        return t['kg'], t['reps']
    if kind == 'bodyweight':
        t = max(sets, key=lambda x: (x['reps'], x['kg']))
        return t['kg'], t['reps']
    if kind == 'time':
        return 0, max(x['sec'] for x in sets)
    return 0, max(x['m'] for x in sets)


def summarize(kind, sets):
    if not sets:
        return '[color=99a1a8]Впишите хотя бы один подход[/color]'
    if kind == 'weight':
        t = max(sets, key=lambda x: (x['kg'], x['reps']))
        out = f"Лучший подход: [b]{g(t['kg'])} кг × {t['reps']}[/b]"
        if 1 < t['reps'] <= 15:
            out += f" · 1ПМ ≈ [b]{g(e1rm(t['kg'], t['reps']))} кг[/b]"
        return out + f" · объём {g(sum(x['kg'] * x['reps'] for x in sets))} кг"
    if kind == 'bodyweight':
        return f"Всего повторов: [b]{sum(x['reps'] for x in sets)}[/b]"
    if kind == 'time':
        return f"Всего: [b]{fmt_sec(sum(x['sec'] for x in sets))}[/b]"
    return f"Всего: [b]{g(sum(x['m'] for x in sets))} м[/b]"


def chips_of(w):
    k, sd, out = kind_of(w), sets_of(w), []
    if not sd:
        return out
    if k == 'weight':
        t = max(sd, key=lambda x: (x.get('kg', 0), x.get('reps', 0)))
        out.append(f"{g(t.get('kg', 0))} кг × {t.get('reps', 0)}")
        if len(sd) > 1:
            out.append(f'{len(sd)} подх.')
        vol = sum((x.get('kg') or 0) * (x.get('reps') or 0) for x in sd)
        if vol:
            out.append(f'объём {g(vol)} кг')
        if 1 < t.get('reps', 0) <= 15 and t.get('kg'):
            out.append(f"1ПМ ≈ {g(e1rm(t['kg'], t['reps']))} кг")
    elif k == 'bodyweight':
        out.append(f"{sum(x.get('reps', 0) for x in sd)} повт.")
        if len(sd) > 1:
            out.append(f'{len(sd)} подх.')
        extra = max((x.get('kg') or 0) for x in sd)
        if extra:
            out.append(f'до +{g(extra)} кг')
    elif k == 'time':
        out.append(fmt_sec(sum(x.get('sec', 0) for x in sd)))
        if len(sd) > 1:
            out.append(f'{len(sd)} подх.')
    else:
        out.append(f"{g(sum(x.get('m', 0) for x in sd))} м")
        tm = sum(x.get('sec', 0) for x in sd)
        if tm:
            out.append(fmt_sec(tm))
    return out


def sets_line(w):
    sd = sets_of(w)
    if kind_of(w) == 'weight' and len(sd) > 1:
        return 'Подходы: ' + ' · '.join(f"{g(x.get('kg', 0))}×{x.get('reps', 0)}" for x in sd[:12])
    return ''


def reindex():
    """Строит индексы по загруженным данным: вместо перебора всех списков на каждый пост (медленно)."""
    from collections import Counter, defaultdict
    D.rev += 1
    D.fol = {f['following'] for f in D.FO if f['follower'] == D.uid}
    D.nfol = Counter(f['following'] for f in D.FO)
    D.nfing = Counter(f['follower'] for f in D.FO)
    D.likes = defaultdict(list)
    for x in D.LK:
        D.likes[x['post_id']].append(x['user_id'])
    D.cmts = defaultdict(list)
    for x in D.CM:
        D.cmts[x['post_id']].append(x)
    for lst in D.cmts.values():
        lst.sort(key=lambda x: x['created_at'])
    D.byuser, D.formsby = defaultdict(list), defaultdict(list)
    for w in D.PO:
        D.byuser[w['user_id']].append(w)
    for w in D.FM:
        D.formsby[w['user_id']].append(w)
    D.prs = set()   # личные рекорды: вес больше всех прежних подходов к тому же упражнению
    grp = defaultdict(list)
    for w in D.PO:
        grp[(w['user_id'], exid_of(w) or w['ex'].lower())].append(w)
    for lst in grp.values():
        best = 0
        for i, w in enumerate(sorted(lst, key=lambda x: x['created_at'])):
            kg = w.get('kg') or 0
            if i and kg and kg > best:
                D.prs.add(w['id'])
            best = max(best, kg)
    D.bests = {}    # (пользователь, упражнение) -> лучший подход, расчётный максимум, число тренировок
    for w in D.PO:
        k = exid_of(w)
        if not k:
            continue
        kg, reps = w.get('kg') or 0, w.get('reps') or 0
        b = D.bests.setdefault((w['user_id'], k), {'kg': 0, 'reps': 0, 'e1rm': 0, 'n': 0})
        b['n'] += 1
        if (kg, reps) > (b['kg'], b['reps']) if kind_of(w) == 'weight' else reps > b['reps']:
            b['kg'], b['reps'] = kg, reps
        if kind_of(w) == 'weight':
            b['e1rm'] = max(b['e1rm'], e1rm(kg, reps))


def is_pr(w):
    return w['id'] in D.prs


def inp(hint, text='', num=False, **kw):
    return TextInput(hint_text=hint, text=text, multiline=False, size_hint_y=None, height=dp(44),
                     input_filter='float' if num else None, background_normal='', background_active='',
                     background_color=CARD2, foreground_color=TX, hint_text_color=MU, cursor_color=ACC,
                     padding=[dp(12), dp(12)], write_tab=False, **kw)


def scroll(children):
    gl = GridLayout(cols=1, spacing=dp(12), padding=[dp(16), dp(12)], size_hint_y=None)
    gl.bind(minimum_height=gl.setter('height'))
    for c in children:
        gl.add_widget(c)
    s = TopScroll()
    s.add_widget(gl)
    gl.bind(height=s.fix)
    return s


def plate(u, size=44):
    p = Plate(text=name_of(u)[:2].upper(), size=(dp(size), dp(size)), font_size=dp(size * .36))
    p.bind(on_release=lambda *a: App.get_running_app().go('user', u))
    return p


def follow_btn(u):
    if u == D.uid:
        return None
    on = is_f(u)
    b = IconBtn('following' if on else 'follow', 'ghostmuted' if on else 'ghost', pos_hint={'center_y': .5})
    b.bind(on_release=lambda x: toggle_follow(u, x))
    return b


def toggle_follow(u, btn=None):
    if is_f(u):
        D.FO = [f for f in D.FO if not (f['follower'] == D.uid and f['following'] == u)]
        fn = lambda: rq('DELETE', f'/rest/v1/follows?follower=eq.{D.uid}&following=eq.{u}')
    else:
        D.FO.append({'follower': D.uid, 'following': u})
        fn = lambda: rq('POST', '/rest/v1/follows', json={'follower': D.uid, 'following': u},
                        headers={'Prefer': 'return=minimal'})
    reindex()
    app = App.get_running_app()
    on = is_f(u)
    if btn:
        btn.set('following' if on else 'follow', 'ghostmuted' if on else 'ghost')
    if app.stack and app.stack[-1] == ('user', u):
        app.render()  # обновить счётчики подписчиков
    bg(fn)


def scope_bar():
    row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
    for k, t in (('all', 'Все'), ('sub', 'Мои подписки')):
        b = Btn(text=t, bg=SEC if D.scope == k else CARD2, fg=ONSEC if D.scope == k else TX, height=dp(40))
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
            s.add_widget(Photo(source=url, fit='contain'))
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


def post_card(w, cm=True):
    u = w['user_id']
    c = Card(padding=dp(12), spacing=dp(10))
    hd = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(12))
    hd.add_widget(plate(u, 40))
    col = BoxLayout(orientation='vertical')
    nm = LB(text=f'[b]{esc(name_of(u))}[/b]', font_size=dp(16), size_hint_y=1)
    nm.bind(on_release=lambda *a: App.get_running_app().go('user', u))
    col.add_widget(nm)
    col.add_widget(L(text=f"[color=99a1a8][size=12sp]{w['created_at'][:10]} · {esc(w['ex'])}[/size][/color]", size_hint_y=1))
    hd.add_widget(col)
    fb = follow_btn(u)
    if fb:
        hd.add_widget(fb)
    c.add_widget(hd)
    c.add_widget(L(text=f"[size=16sp][b]{esc(w['ex'])}[/b]" + (f" · {esc(w['note'])}" if w.get('note') else '') + '[/size]'))
    if w.get('media_path'):
        if w.get('media_type') == 'v':
            vb = Btn(text='Смотреть видео', bg=CARD2, fg=TX, height=dp(90))
            vb.bind(on_release=lambda *a: open_media([{**w, 'caption': w.get('note')}]))
            c.add_widget(vb)
        else:
            ph = PhotoB(source=media_url(w['media_path']), fit='adaptive', size_hint_y=None,
                        ratio=(w['media_w'] / w['media_h']) if w.get('media_w') and w.get('media_h') else None)
            ph.bind(on_release=lambda *a: open_media([{**w, 'caption': w.get('note')}]))   # по нажатию фото открывается целиком
            c.add_widget(ph)
    sl = StackLayout(size_hint_y=None, spacing=dp(6))
    sl.bind(minimum_height=sl.setter('height'))
    for t in chips_of(w):
        sl.add_widget(Chip(text=t))
    if is_pr(w):
        sl.add_widget(Chip(text='Личный рекорд', hot=True))
    c.add_widget(sl)
    sline = sets_line(w)
    if sline:
        c.add_widget(L(text=f'[color=99a1a8][size=12sp]{esc(sline)}[/size][/color]'))
    pid = w['id']
    likers = D.likes.get(pid, [])
    cms = D.cmts.get(pid, [])
    row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    pill = Pill(size_hint=(None, None), height=dp(40), pos_hint={'center_y': .5})
    pill.bind(minimum_width=pill.setter('width'))
    lb = ActionBtn('heart', len(likers), D.uid in likers)
    lb.bind(on_release=lambda x: toggle_like(w, x))
    pill.add_widget(lb)
    if cm:
        cb = ActionBtn('comment', len(cms))
        cb.bind(on_release=lambda *a: App.get_running_app().go('comments', pid))
        pill.add_widget(cb)
    row.add_widget(pill)
    row.add_widget(Widget())
    if u == D.uid:
        d = IconBtn('trash', 'tonal', pos_hint={'center_y': .5})
        d.bind(on_release=lambda *a: confirm('Удалить тренировку?', lambda: delete_post('posts', w)))
        row.add_widget(d)
    c.add_widget(row)
    if likers:
        c.add_widget(L(text=f"[size=13sp]Нравится [b]{esc(name_of(likers[0]))}[/b]" + (f" и ещё {len(likers) - 1}" if len(likers) > 1 else '') + '[/size]'))
    if cm and cms:
        last = cms[-1]
        c.add_widget(L(text=f"[color=99a1a8][size=13sp][b]{esc(name_of(last['user_id']))}[/b] {esc(last['body'][:90])}[/size][/color]"))
        more = LB(text=f"[color=b7ff2a][size=13sp]Все комментарии ({len(cms)})[/size][/color]")
        more.bind(on_release=lambda *a: App.get_running_app().go('comments', pid))
        c.add_widget(more)
    return c


def confirm(text, yes):
    mv = ModalView(size_hint=(.86, None), height=dp(180), background='', background_color=(0, 0, 0, .6))
    c = Card(padding=dp(16), spacing=dp(14), pos_hint={'center_x': .5, 'center_y': .5})
    c.add_widget(L(text=f'[size=16sp][b]{esc(text)}[/b][/size]', halign='center'))
    row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(18))
    no, ok = IconBtn('close', 'tonal', size=52), IconBtn('trash', 'danger', size=52)
    no.bind(on_release=lambda *a: mv.dismiss())
    ok.bind(on_release=lambda *a: (mv.dismiss(), yes()))
    for wgt in (Widget(), no, ok, Widget()):
        row.add_widget(wgt)
    c.add_widget(row)
    mv.add_widget(c)
    mv.open()


def delete_post(table, w):
    D.PO = [x for x in D.PO if x is not w]
    D.FM = [x for x in D.FM if x is not w]
    reindex()
    App.get_running_app().render()

    def f():
        rq('DELETE', f"/rest/v1/{table}?id=eq.{w['id']}")
        if w.get('media_path'):
            rq('DELETE', '/storage/v1/object/media/' + w['media_path'])
    bg(f)


def head(eyebrow, title, sub=''):
    return L(text=f'[color=b7ff2a][b][size=11sp]{esc(eyebrow.upper())}[/size][/b][/color]\n[size=28sp]{dfont(esc(title))}[/size]'
             + (f'\n[color=99a1a8]{esc(sub)}[/color]' if sub else ''))


def greeting():
    h = dt.datetime.now().hour
    return 'Доброй ночи' if h < 5 else 'Доброе утро' if h < 12 else 'Добрый день' if h < 18 else 'Добрый вечер'


def streak(u):
    days = sorted({w['created_at'][:10] for w in D.byuser.get(u, [])}, reverse=True)
    if not days:
        return 0
    cur = dt.date.fromisoformat(days[0])
    if (dt.date.today() - cur).days > 1:
        return 0
    n = 1
    for x in days[1:]:
        e = dt.date.fromisoformat(x)
        if (cur - e).days != 1:
            break
        n, cur = n + 1, e
    return n


def mini(label, value, note, cb=None):
    c = CardB(size_hint=(1, 1), padding=dp(12), spacing=dp(2))
    c.add_widget(L(text=f'[color=99a1a8][size=10sp][b]{esc(label.upper())}[/b][/size][/color]'))
    c.add_widget(L(text=f'[size=20sp][b]{esc(value)}[/b][/size]'))
    c.add_widget(L(text=f'[color=b7ff2a][size=11sp][b]{esc(note)}[/b][/size][/color]'))
    if cb:
        c.bind(on_release=lambda *a: cb())
    return c


def stat_card(v, t, cb=None):
    c = CardB(size_hint_y=1, padding=dp(8), spacing=dp(2))
    c.add_widget(L(text=f'[size=20sp][b][color=b7ff2a]{v}[/color][/b][/size]', halign='center'))
    c.add_widget(L(text=f'[color=99a1a8][size=10sp]{t}[/size][/color]', halign='center'))
    if cb:
        c.bind(on_release=lambda *a: cb())
    return c


# ----- экраны -----
def v_auth(_):
    app = App.get_running_app()
    up = app.mode == 'up'
    c = Card(spacing=dp(10))
    c.add_widget(L(text='[size=44sp][b]Железный круг[/b][/size]'))
    c.add_widget(L(text='[color=99a1a8]Сообщество русскоговорящих атлетов[/color]'))
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
                app.go('feed', root=True)
        bg(run, ok)
    go.bind(on_release=submit)
    c.add_widget(go)
    return scroll([c])


def paged(items, build, box, page=8):
    """Добавляет карточки порциями: сначала page штук, остальные по кнопке «Показать ещё» (экран не тормозит)."""
    pos = {'n': 0}
    more = Btn(text='Показать ещё', bg=CARD2, fg=TX)

    def add(*a):
        if more.parent:
            box.remove_widget(more)
        for w in items[pos['n']:pos['n'] + page]:
            box.add_widget(build(w))
        pos['n'] += page
        if pos['n'] < len(items):
            box.add_widget(more)
    more.bind(on_release=add)
    add()


def v_feed(_):
    app = App.get_running_app()
    comp = Card()
    r = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
    r.add_widget(plate(D.uid))
    r.add_widget(L(text='[b]Поделитесь тренировкой[/b]\n[color=99a1a8]Команда готова вас поддержать[/color]', size_hint_y=1))
    comp.add_widget(r)
    ab = Btn(text='Добавить тренировку')
    ab.bind(on_release=lambda *a: app.go('compose', 'post', root=True))
    comp.add_widget(ab)
    rows = sorted(((u, stat(p)[4]) for u, p in D.P.items() if stat(p)[3]), key=lambda x: -x[1])
    place = next((i for i, (u, _d) in enumerate(rows, 1) if u == D.uid), None)
    prs = [w for w in D.byuser.get(D.uid, []) if is_pr(w)]
    n = streak(D.uid)
    ex = prs[0]['ex'] if prs else ''
    minis = [mini('Серия', f'{n} дн.', 'Так держать' if n else 'Начните!', lambda: app.go('user', D.uid, root=True)),
             mini('Рейтинг', f'#{place}' if place else '—', f'Топ {max(1, round(place * 100 / len(rows)))}%' if place else 'Нет цифр'),
             mini('Рекорд', f"{g(prs[0]['kg'])} кг" if prs else '—', (ex[:10] + '…' if len(ex) > 11 else ex) if prs else 'Пока нет')]
    hs = BoxLayout(size_hint_y=None, height=dp(104), spacing=dp(8))
    for m in minis:
        hs.add_widget(m)
    items = [w for w in D.PO if D.scope == 'all' or w['user_id'] == D.uid or is_f(w['user_id'])]
    box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(12))
    box.bind(minimum_height=box.setter('height'))
    paged(items, post_card, box)
    ch = [comp, hs, scope_bar(), box]
    if not items:
        ch.append(L(text='[color=99a1a8]Здесь пока пусто. Добавьте тренировку или подпишитесь на атлетов.[/color]'))
    return scroll(ch)


def v_rank(_):
    ids = set(D.P) if D.scope == 'all' else {u for u in D.P if u == D.uid or is_f(u)}
    rows = sorted(((u, stat(D.P[u])) for u in ids if stat(D.P[u])[3]), key=lambda r: -r[1][4])
    ch = [head('Соревнуйтесь вместе', 'Рейтинг', 'Очки DOTS: сумма трёх движений с поправкой на вес тела и пол'), scope_bar()]
    for i, (u, s) in enumerate(rows, 1):
        c = Card()
        r = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        r.add_widget(L(text=f"[size=22sp][b][color={'b7ff2a' if i == 1 else '99a1a8'}]{i:02d}[/color][/b][/size]", size_hint_x=None, width=dp(36), size_hint_y=1))
        r.add_widget(plate(u))
        nm = LB(text=f'[b]{esc(name_of(u))}[/b]\n[color=99a1a8]{tier(s[4])[1]} · сумма {g(s[3])} кг[/color]', size_hint_y=1)
        nm.bind(on_release=lambda x, u=u: App.get_running_app().go('user', u))
        r.add_widget(nm)
        r.add_widget(L(text=f'[size=22sp][b][color=b7ff2a]{s[4]:.1f}[/color][/b][/size]\n[color=99a1a8]DOTS[/color]', size_hint_x=None, width=dp(60), size_hint_y=1))
        fb = follow_btn(u)
        if fb:
            r.add_widget(fb)
        c.add_widget(r)
        ch.append(c)
    if not rows:
        ch.append(L(text='[color=99a1a8]Пока никого нет. Внесите присед, жим и тягу в профиле' +
                    ('' if D.scope == 'all' else ' или подпишитесь на атлетов') + '.[/color]'))
    return scroll(ch)


def v_user(u):
    app = App.get_running_app()
    u = u or D.uid
    p = D.P.get(u) or {}
    sq, bp, dl, tot, d = stat(p)
    posts = D.byuser.get(u, [])
    forms = D.formsby.get(u, [])
    top = Card()
    r = BoxLayout(size_hint_y=None, height=dp(80))
    r.add_widget(Widget())
    r.add_widget(plate(u, 76))
    r.add_widget(Widget())
    top.add_widget(r)
    top.add_widget(L(text=f"[size=26sp][b]{esc(name_of(u))}[/b][/size]" + (f"\n[color=99a1a8]{esc(p['city'])}[/color]" if p.get('city') else ''), halign='center'))
    srow = BoxLayout(size_hint_y=None, height=dp(78), spacing=dp(8))
    srow.add_widget(stat_card(len(posts), 'Тренировки'))
    srow.add_widget(stat_card(streak(u), 'Серия, дн.'))
    srow.add_widget(stat_card(followers(u), 'Подписчики', lambda: app.go('people', (u, 'followers'))))
    srow.add_widget(stat_card(D.nfing.get(u, 0), 'Подписки', lambda: app.go('people', (u, 'following'))))
    if p.get('bio'):
        top.add_widget(L(text=esc(p['bio']), halign='center'))
    top.add_widget(L(text=(f"{tier(d)[1]} · {d:.1f} DOTS · сумма {g(tot)} кг" if tot else '[color=99a1a8]Пока без рейтинга[/color]'), halign='center'))
    lf = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
    for t, v in (('Присед', sq), ('Жим', bp), ('Тяга', dl)):
        lf.add_widget(L(text=f'[color=99a1a8]{t}[/color]\n[size=24sp][b]{g(v)}[/b][/size]', halign='center', size_hint_y=1))
    top.add_widget(lf)
    fb = follow_btn(u)
    if fb:
        fr = BoxLayout(size_hint_y=None, height=dp(44))
        fr.add_widget(Widget())
        fr.add_widget(fb)
        fr.add_widget(Widget())
        top.add_widget(fr)
    ch = [top, srow, heat_card(u)]
    info = [f"[color=99a1a8]{t.split(',')[0]}[/color]  {esc(g(p[k]) if n else p[k])}" for k, t, n in SPORT if p.get(k)]
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
        th = Btn(text='Студия темы', bg=CARD2, fg=TX)
        th.bind(on_release=lambda *a: app.go('theme'))
        pb = Btn(text='Фоновые уведомления: ' + ('вкл' if load_settings().get('push', True) else 'выкл'), bg=CARD2, fg=TX)
        pb.bind(on_release=lambda *a: app.toggle_push(pb))
        ch += [e, th, pb, o]
    # две вкладки профиля: актуальная форма и тренировки (содержимое меняется на месте, прокрутка не сбрасывается)
    sec = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(12))
    sec.bind(minimum_height=sec.setter('height'))

    def fill_form():
        if u == D.uid:
            ab = Btn(text='+ Добавить фото или видео формы')
            ab.bind(on_release=lambda *a: app.go('compose', 'form'))
            sec.add_widget(ab)
        if not forms:
            sec.add_widget(L(text='[color=99a1a8]Фото и короткие видео формы пока не добавлены.[/color]'))
            return
        # мозаика: две колонки, каждое фото в своей пропорции (от 4:5 до 1.91:1), ничего не обрезается
        cw = (Window.width - dp(32) - dp(8)) / 2
        cols = [BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8), pos_hint={'top': 1}) for _ in range(2)]
        for cl in cols:
            cl.bind(minimum_height=cl.setter('height'))
        est = [0.0, 0.0]
        for i, w in enumerate(forms):
            k = 0 if est[0] <= est[1] else 1
            if w['media_type'] == 'v':
                tile = FloatLayout(size_hint_y=None, height=cw)
                t = Btn(text='Видео', bg=CARD2, fg=TX, size_hint=(1, 1), font_size=dp(13))
                t.bind(on_release=lambda x, i=i: open_media(forms, i))
                tile.add_widget(t)
                est[k] += 1
            else:
                has = bool(w.get('media_w') and w.get('media_h'))
                ratio = (w['media_w'] / w['media_h']) if has else None
                tile = PhotoB(source=media_url(w['media_path']), fit='adaptive', ratio=ratio, size_hint_y=None)
                tile.bind(on_release=lambda x, i=i: open_media(forms, i))
                est[k] += 1 / min(max(ratio or 1.0, .8), 1.91)
            if u == D.uid:
                dbtn = IconBtn('trash', 'tonal', size=34, pos_hint={'right': .96, 'top': .96})
                dbtn.bind(on_release=lambda x, w=w: confirm('Удалить это фото формы?', lambda: delete_post('form_posts', w)))
                tile.add_widget(dbtn)
            cols[k].add_widget(tile)
        wrap = BoxLayout(size_hint_y=None, spacing=dp(8))
        wrap.bind(minimum_height=wrap.setter('height'))
        for cl in cols:
            wrap.add_widget(cl)
        sec.add_widget(wrap)

    def fill_posts():
        paged(posts, post_card, sec)
        if not posts:
            sec.add_widget(L(text='[color=99a1a8]Тренировок пока нет.[/color]'))

    tabs, tb = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8)), {}

    def show(k):
        D.ptab = k
        sec.clear_widgets()
        (fill_form if k == 'form' else fill_posts)()
        for kk, bt in tb.items():
            bt.bg, bt.fg = (SEC, ONSEC) if kk == k else (CARD2, TX)
    for k, t in (('form', f'Форма · {len(forms)}'), ('posts', f'Тренировки · {len(posts)}')):
        bt = Btn(text=t, height=dp(44))
        bt.bind(on_release=lambda x, k=k: show(k))
        tb[k] = bt
        tabs.add_widget(bt)
    show(D.ptab)
    ch += [tabs, sec]
    return scroll(ch)


def v_edit(_):
    app = App.get_running_app()
    p = D.P.get(D.uid) or {}
    c = Card()
    f = {}
    c.add_widget(L(text='[size=20sp][b]Профиль[/b][/size]'))
    for k, t, n in [('username', 'Ник', 0), ('city', 'Город', 0), ('bio', 'О себе (до 300 знаков)', 0)] + SPORT + LIFTS:
        c.add_widget(L(text=f'[color=99a1a8]{t}[/color]'))
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


def pick(cb, kind='image'):
    """Выбор из галереи, как в мессенджерах (системный выбор фото и видео). На ПК: окно выбора файла."""
    app = App.get_running_app()
    try:
        from androidstorage4kivy import Chooser, SharedStorage
    except Exception:
        Chooser = None
    if Chooser:
        def got(uris):
            if uris:
                bg(lambda: SharedStorage().copy_from_shared(uris[0]), lambda p: p and cb(p))
        app._chooser = Chooser(lambda uris: Clock.schedule_once(lambda dt_: got(uris)))
        try:
            app._chooser.choose_content(kind + '/*')
        except TypeError:
            app._chooser.choose_content(mime_type=kind + '/*')
        return
    if not filechooser:
        return app.toast('Выбор файлов недоступен')
    ext = ['*.mp4', '*.mov', '*.m4v'] if kind == 'video' else ['*.jpg', '*.jpeg', '*.png', '*.webp']
    filechooser.open_file(on_selection=lambda sel: sel and Clock.schedule_once(lambda dt_: cb(sel[0])), filters=[['Файлы'] + ext])


def upload(path, kind=None):
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    video = (kind == 'video') if kind else ext in VIDEO_EXT
    dims = (None, None)
    if video and ext not in VIDEO_EXT:
        ext = 'mp4'
    if video:
        if os.path.getsize(path) > 20 * 1024 * 1024:
            raise RuntimeError('Видео больше 20 МБ. Выберите ролик покороче.')
        data, ct, ext = open(path, 'rb').read(), 'video/quicktime' if ext == 'mov' else 'video/mp4', ext
    else:
        try:
            from PIL import Image, ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            im = Image.open(path).convert('RGB')
            im.thumbnail((1080, 1080))
            dims = im.size
            buf = io.BytesIO()
            im.save(buf, 'JPEG', quality=85)
            data, ct, ext = buf.getvalue(), 'image/jpeg', 'jpg'
        except Exception:
            # Pillow не смог открыть файл (например, WebP): отправляем как есть, размеры берёт Kivy
            if os.path.getsize(path) > 20 * 1024 * 1024:
                raise RuntimeError('Фото больше 20 МБ.')
            data, ct, ext = open(path, 'rb').read(), 'image/jpeg', 'jpg'
            try:
                ci = CoreImage(path)
                dims = (ci.width, ci.height)
            except Exception:
                pass
    name = f'{D.uid}/{int(time.time() * 1000)}.{ext}'
    rq('POST', '/storage/v1/object/media/' + name, data=data, headers={'Content-Type': ct})
    return name, 'v' if video else 'i', dims[0], dims[1]


class ExRow(ButtonBehavior, BoxLayout):
    sel = BooleanProperty(False)


def best_label(e):
    b = D.bests.get((D.uid, e['id']))
    if not b:
        return ''
    k = e['kind']
    if k == 'weight' and b['kg']:
        return f"{g(b['kg'])} кг"
    if k == 'bodyweight' and b['reps']:
        return f"{b['reps']} повт."
    if k == 'time' and b['reps']:
        return fmt_sec(b['reps'])
    if k == 'distance' and b['reps']:
        return f"{g(b['reps'])} м"
    return ''


def recent_exercises(n=6):
    out, seen = [], set()
    for w in sorted(D.byuser.get(D.uid, []), key=lambda x: x['created_at'], reverse=True):
        e = EXBY.get(exid_of(w))
        if e and e['id'] not in seen:
            seen.add(e['id'])
            out.append(e)
            if len(out) >= n:
                break
    return out


def ex_row(e, selected, on_pick):
    r = ExRow(sel=selected)
    sub = ', '.join(e['muscles'][:2]) + ' · ' + e['equipment']
    r.add_widget(L(text=f"[b]{esc(e['name'])}[/b]\n[color=99a1a8][size=12sp]{esc(sub)}[/size][/color]", size_hint_y=1))
    bl = best_label(e)
    if bl:
        r.add_widget(L(text=f'[color=b7ff2a][b]{esc(bl)}[/b][/color]', halign='right', size_hint=(None, 1), width=dp(84)))
    r.bind(on_release=lambda *a: on_pick(e))
    return r


def pick_exercise(cb, current=None):
    """Окно выбора упражнения: поиск, категории, недавние, личные рекорды рядом с названием."""
    mv = ModalView(size_hint=(.96, .9), background='', background_color=(0, 0, 0, .6))
    card = Card(padding=dp(14), spacing=dp(10), size_hint=(1, 1))
    hd = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
    hd.add_widget(L(text='[size=20sp][b]Выберите упражнение[/b][/size]', size_hint_y=1))
    cl = IconBtn('close', 'tonal', size=40, pos_hint={'center_y': .5})
    cl.bind(on_release=lambda *a: mv.dismiss())
    hd.add_widget(cl)
    card.add_widget(hd)
    q = inp('Поиск: присед, грудь, штанга…')
    card.add_widget(q)
    rec = recent_exercises()
    cats = ['Все'] + (['Недавние'] if rec else []) + EXCATS
    st = {'cat': 'Все'}
    chip_sv = ScrollView(size_hint_y=None, height=dp(42), do_scroll_y=False, bar_width=0)
    chip_box = BoxLayout(size_hint_x=None, spacing=dp(8))
    chip_box.bind(minimum_width=chip_box.setter('width'))
    chips = {}
    for c_ in cats:
        b = Btn(text=c_, size_hint=(None, None), size=(dp(28) + dp(8.2) * len(c_), dp(38)), font_size=dp(13))
        b.bind(on_release=lambda x, c_=c_: (st.update(cat=c_), q.__setattr__('text', ''), restyle(), fill()))
        chips[c_] = b
        chip_box.add_widget(b)
    chip_sv.add_widget(chip_box)
    card.add_widget(chip_sv)
    lst = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
    lst.bind(minimum_height=lst.setter('height'))
    sv = ScrollView()
    sv.add_widget(lst)
    card.add_widget(sv)

    def restyle():
        for c_, b in chips.items():
            b.bg, b.fg = (SEC, ONSEC) if c_ == st['cat'] else (CARD2, TX)

    def pick(e):
        mv.dismiss()
        cb(e)

    def fill(*a):
        lst.clear_widgets()
        qs = norm(q.text).split()
        if qs:
            hit = [e for e in EXLIST if all(t in norm(' '.join([e['name'], e['category'], e['equipment']] + e['muscles'])) for t in qs)]
            hit.sort(key=lambda e: (not norm(e['name']).startswith(qs[0]), e['name']))
            groups = [(f'Найдено: {len(hit)}', hit)]
        elif st['cat'] == 'Все':
            groups = ([('Недавние', rec)] if rec else []) + [(c_, [e for e in EXLIST if e['category'] == c_]) for c_ in EXCATS]
        elif st['cat'] == 'Недавние':
            groups = [('Недавние', rec)]
        else:
            groups = [(st['cat'], [e for e in EXLIST if e['category'] == st['cat']])]
        n = 0
        for title, exs in groups:
            if not exs:
                continue
            lst.add_widget(L(text=f'[color=99a1a8][size=12sp][b]{esc(title.upper())}[/b][/size][/color]'))
            for e in exs:
                lst.add_widget(ex_row(e, bool(current) and e['id'] == current['id'], pick))
                n += 1
        if not n:
            lst.add_widget(L(text='[color=99a1a8]Ничего не нашли. Попробуйте другое слово: название, мышцу или инвентарь.[/color]'))
    trig = Clock.create_trigger(fill, .15)
    q.bind(text=lambda *a: trig())
    restyle()
    fill()
    mv.add_widget(card)
    mv.open()


class SetsEditor(BoxLayout):
    """Подходы: строки вида «вес × повторы» (поля зависят от типа упражнения), расчёт лучшего подхода."""
    LABELS = {'weight': ('Вес, кг', 'Повторы'), 'bodyweight': ('Доп. вес, кг', 'Повторы'),
              'time': ('Секунды', None), 'distance': ('Дистанция, м', 'Время, мин')}

    def __init__(self, **kw):
        super().__init__(orientation='vertical', size_hint_y=None, spacing=dp(8), **kw)
        self.bind(minimum_height=self.setter('height'))
        self.kind, self.rows = 'weight', []
        self.hdr = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(8), padding=[dp(34), 0, dp(44), 0])
        self.ha, self.hb = L(text='', size_hint_y=1), L(text='', size_hint_y=1)
        self.box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
        self.box.bind(minimum_height=self.box.setter('height'))
        self.addb = Btn(text='Добавить подход', bg=CARD2, fg=TX, height=dp(44))
        self.addb.bind(on_release=lambda *a: self.add_row(True))
        self.sumL = L(text='')
        for w in (self.hdr, self.box, self.addb, self.sumL):
            self.add_widget(w)

    def set_kind(self, kind):
        self.kind, self.rows = kind, []
        self.box.clear_widgets()
        la, lb = self.LABELS[kind]
        self.hdr.clear_widgets()
        self.ha.text = f'[color=99a1a8][size=12sp]{la}[/size][/color]'
        self.hdr.add_widget(self.ha)
        if lb:
            self.hb.text = f'[color=99a1a8][size=12sp]{lb}[/size][/color]'
            self.hdr.add_widget(self.hb)
        self.add_row()

    def add_row(self, copy=False):
        if len(self.rows) >= 20:
            return App.get_running_app().toast('Не больше 20 подходов')
        prev = self.rows[-1] if self.rows else None
        two = self.LABELS[self.kind][1] is not None
        r = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        idx = L(text='', size_hint=(None, 1), width=dp(26))
        a = inp('', prev['a'].text if copy and prev else '', True, pos_hint={'center_y': .5})
        b = inp('', prev['b'].text if copy and prev and prev['b'] else '', True, pos_hint={'center_y': .5}) if two else None
        rm = IconBtn('close', 'plain', size=36, pos_hint={'center_y': .5})
        row = {'w': r, 'a': a, 'b': b, 'idx': idx}
        rm.bind(on_release=lambda *x: self.remove(row))
        for wgt in (idx, a, b, rm):
            if wgt:
                r.add_widget(wgt)
        for t in (a, b):
            if t:
                t.bind(text=lambda *x: self.refresh())
        self.rows.append(row)
        self.box.add_widget(r)
        self.refresh()

    def remove(self, row):
        if len(self.rows) > 1:
            self.rows.remove(row)
            self.box.remove_widget(row['w'])
            self.refresh()

    def values(self):
        out = []
        for r in self.rows:
            a, b = fnum(r['a'].text), fnum(r['b'].text) if r['b'] else 0
            if self.kind == 'weight' and a and b:
                out.append({'kg': a, 'reps': int(b)})
            elif self.kind == 'bodyweight' and b:
                out.append({'kg': a, 'reps': int(b)})
            elif self.kind == 'time' and a:
                out.append({'sec': int(a)})
            elif self.kind == 'distance' and a:
                out.append({'m': int(a), 'sec': int(b * 60)} if b else {'m': int(a)})
        return out

    def refresh(self):
        for i, r in enumerate(self.rows, 1):
            r['idx'].text = f'[color=99a1a8][b]{i}[/b][/color]'
        self.sumL.text = summarize(self.kind, self.values())


def v_compose(kind):
    app = App.get_running_app()
    form = kind == 'form'
    st = {'ex': None}
    chosen = {'p': None, 'k': None}
    cards = []
    ed = SetsEditor()
    if not form:
        ca = Card()
        ca.add_widget(head('Фиксируем победы', 'Новая тренировка', 'Выберите упражнение и впишите подходы'))
        tile = ExRow(height=dp(68))
        tile.add_widget(Icon(name='barbell', size_hint=(None, None), size=(dp(30), dp(30)), pos_hint={'center_y': .5}, color=ACC))
        tl = L(text='', size_hint_y=1)
        tile.add_widget(tl)

        def show():
            e = st['ex']
            tile.sel = bool(e)
            tl.text = (f"[b]{esc(e['name'])}[/b]\n[color=99a1a8][size=12sp]{esc(', '.join(e['muscles'][:2]))} · {esc(e['equipment'])} · {esc(EXKINDS.get(e['kind'], ''))}[/size][/color]"
                       if e else f"[b]Выбрать упражнение[/b]\n[color=99a1a8][size=12sp]Из списка: {len(EXLIST)} упражнений[/size][/color]")

        def choose(e):
            prev = st['ex']
            st['ex'] = e
            show()
            if not ed.parent:
                ca.add_widget(ed)
            if not prev or prev['kind'] != e['kind']:
                ed.set_kind(e['kind'])
        tile.bind(on_release=lambda *a: pick_exercise(choose, st['ex']))
        show()
        ca.add_widget(tile)
        rec = recent_exercises()
        if rec:
            ca.add_widget(L(text='[color=99a1a8][size=12sp]Недавние: нажмите, чтобы выбрать сразу[/size][/color]'))
            rsv = ScrollView(size_hint_y=None, height=dp(42), do_scroll_y=False, bar_width=0)
            rbox = BoxLayout(size_hint_x=None, spacing=dp(8))
            rbox.bind(minimum_width=rbox.setter('width'))
            for e in rec:
                b = Btn(text=e['name'], bg=CARD2, fg=TX, size_hint=(None, None), font_size=dp(13),
                        size=(dp(28) + dp(8.2) * len(e['name']), dp(38)))
                b.bind(on_release=lambda x, e=e: choose(e))
                rbox.add_widget(b)
            rsv.add_widget(rbox)
            ca.add_widget(rsv)
        cards.append(ca)
    c = Card()
    if form:
        c.add_widget(head('Покажите результат', 'Актуальная форма', 'Фото или короткое видео'))
    else:
        c.add_widget(L(text='[size=16sp][b]Фото или видео (по желанию)[/b][/size]'))
    mst = L(text='[color=99a1a8]Фото или видео из галереи (видео до 20 МБ)[/color]')
    prev = Photo(fit='contain', size_hint_y=None, height=0)

    def picked(p, k):
        chosen.update(p=p, k=k)
        mst.text = '[color=b7ff2a]Выбрано: ' + ('фото' if k == 'image' else 'видео') + '[/color]'
        prev.height = dp(200) if k == 'image' else 0
        prev.set(p if k == 'image' else '')
    mrow = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
    for k, t in (('image', 'Фото'), ('video', 'Видео')):
        gb = Btn(text=t + ' из галереи', bg=CARD2, fg=TX)
        gb.bind(on_release=lambda x, k=k: pick(lambda p, k=k: picked(p, k), k))
        mrow.add_widget(gb)
    c.add_widget(mrow)
    c.add_widget(mst)
    c.add_widget(prev)
    note = inp('Подпись')
    c.add_widget(note)
    go = Btn(text='Опубликовать')

    def submit(*a):
        if form and not chosen['p']:
            return app.toast('Выберите фото или видео')
        sets = []
        if not form:
            if not st['ex']:
                return app.toast('Выберите упражнение из списка')
            sets = ed.values()
            if not sets:
                return app.toast('Впишите хотя бы один подход')
        go.disabled, go.text = True, 'Публикуем…'

        def run():
            row = {'user_id': D.uid, 'note' if not form else 'caption': note.text.strip() or None}
            if chosen['p']:
                row['media_path'], row['media_type'], mw, mh = upload(chosen['p'], chosen['k'])
                if mw:
                    row['media_w'], row['media_h'] = mw, mh
            if not form:
                e = st['ex']
                kg, reps = summary_cols(e['kind'], sets)
                row.update(ex=e['name'], exercise_id=e['id'], sets_data=sets, kg=kg, reps=reps, sets=len(sets))
            tbl = '/rest/v1/form_posts' if form else '/rest/v1/posts'
            for attempt in range(2):
                try:
                    rq('POST', tbl, json=row, headers={'Prefer': 'return=minimal'})
                    break
                except Exception as e_:
                    # в базе ещё нет новых колонок (schema_v4.sql, schema_v6.sql): публикуем без них
                    miss = [col for col in ('media_w', 'media_h', 'exercise_id', 'sets_data') if col in str(e_) and col in row]
                    if not miss or attempt:
                        raise
                    for col in miss:
                        row.pop(col)

        def fin(_):
            app.load_all(first=False)
            app.go('user' if form else 'feed', D.uid if form else None, root=True)

        def reset(*a):
            go.disabled, go.text = False, 'Опубликовать'

        def guard():
            try:
                return run()
            except Exception:
                Clock.schedule_once(reset)   # при ошибке кнопка сразу снова доступна
                raise
        bg(guard, fin)
        Clock.schedule_once(reset, 60)
    go.bind(on_release=submit)
    c.add_widget(go)
    cards.append(c)
    return scroll(cards)


def user_row(u):
    s = stat(D.P.get(u) or {})
    c = Card()
    r = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
    r.add_widget(plate(u))
    sub = (f'{tier(s[4])[1]} · {s[4]:.1f} DOTS · ' if s[3] else '') + f'{followers(u)} подписчиков'
    nm = LB(text=f'[b]{esc(name_of(u))}[/b]\n[color=99a1a8]{sub}[/color]', size_hint_y=1)
    nm.bind(on_release=lambda *a: App.get_running_app().go('user', u))
    r.add_widget(nm)
    fb = follow_btn(u)
    if fb:
        r.add_widget(fb)
    c.add_widget(r)
    return c


def v_search(_):
    app = App.get_running_app()
    root = BoxLayout(orientation='vertical')
    f = inp('Поиск по нику', app.q)
    bar = BoxLayout(size_hint_y=None, height=dp(68), padding=dp(12))
    bar.add_widget(f)
    res = GridLayout(cols=1, spacing=dp(12), padding=[dp(16), dp(12)], size_hint_y=None)
    res.bind(minimum_height=res.setter('height'))
    sv = ScrollView()
    sv.add_widget(res)

    def fill(*a):
        app.q = f.text.strip()
        q = app.q.lower()
        res.clear_widgets()
        if q:
            ids = [u for u in D.P if q in name_of(u).lower()]
            ids.sort(key=lambda u: (not name_of(u).lower().startswith(q), -followers(u), name_of(u).lower()))
            res.add_widget(L(text=f'[color=99a1a8]Найдено: {len(ids)}[/color]'))
        else:
            ids = sorted(D.P, key=lambda u: (-followers(u), -stat(D.P[u])[4]))
            res.add_widget(L(text='[color=99a1a8]Популярные атлеты. Введите ник, чтобы найти нужного.[/color]'))
        for u in ids[:30]:
            res.add_widget(user_row(u))
        if q and not ids:
            res.add_widget(L(text='[color=99a1a8]Никого не нашли. Проверьте написание ника.[/color]'))
    f.bind(text=fill)
    fill()
    hb = BoxLayout(size_hint_y=None, height=dp(104), padding=[dp(14), dp(14), dp(14), 0])
    hb.add_widget(head('Найдите своих', 'Поиск', 'Атлеты по нику'))
    root.add_widget(hb)
    root.add_widget(bar)
    root.add_widget(sv)
    return root


def v_people(arg):
    u, kind = arg
    if kind == 'followers':
        ids, title = [f['follower'] for f in D.FO if f['following'] == u], 'Подписчики'
    else:
        ids, title = [f['following'] for f in D.FO if f['follower'] == u], 'Подписки'
    ids = [x for x in ids if x in D.P]
    ch = [head(name_of(u), title, f'Всего: {len(ids)}')]
    ch += [user_row(x) for x in ids] or [L(text='[color=99a1a8]Пока никого нет.[/color]')]
    return scroll(ch)


MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']


def heat_card(u):
    """Календарь тренировок: месяц с числами, дни с тренировками подсвечены, можно листать месяцы."""
    counts = {}
    for w in D.byuser.get(u, []):
        d = w['created_at'][:10]
        counts[d] = counts.get(d, 0) + 1
    today = dt.date.today()
    st = {'y': today.year, 'm': today.month}
    c = Card()
    c.add_widget(L(text='[size=18sp][b]История тренировок[/b][/size]'))
    nav = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
    pv = Btn(text='‹', bg=CARD2, fg=TX, size_hint=(None, None), size=(dp(40), dp(40)), font_size=dp(20))
    nx = Btn(text='›', bg=CARD2, fg=TX, size_hint=(None, None), size=(dp(40), dp(40)), font_size=dp(20))
    ttl = L(text='', halign='center', valign='middle', size_hint_y=1)
    for wgt in (pv, ttl, nx):
        nav.add_widget(wgt)
    c.add_widget(nav)
    info = L(text='', halign='center')
    c.add_widget(info)
    wk = GridLayout(cols=7, size_hint_y=None, height=dp(18), spacing=dp(4))
    for d in ('Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'):
        wk.add_widget(L(text=f'[color=99a1a8][size=12sp][b]{d}[/b][/size][/color]', halign='center', size_hint_y=1))
    c.add_widget(wk)
    grid = GridLayout(cols=7, size_hint_y=None, spacing=dp(4))
    grid.bind(minimum_height=grid.setter('height'))
    c.add_widget(grid)

    def fill(*a):
        y, m = st['y'], st['m']
        first = dt.date(y, m, 1)
        start = first - dt.timedelta(days=first.weekday())
        last = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
        grid.clear_widgets()
        for i in range(((last - start).days // 7 + 1) * 7):
            d = start + dt.timedelta(days=i)
            grid.add_widget(DayCell(d, counts.get(d.isoformat(), 0), d.month == m, d == today))
        pre = f'{y:04d}-{m:02d}'
        total = sum(v for k, v in counts.items() if k.startswith(pre))
        days = sum(1 for k in counts if k.startswith(pre))
        ttl.text = f'[size=17sp][b]{MONTHS[m - 1]} {y}[/b][/size]'
        info.text = f'[color=99a1a8][size=12sp]{total} трен. · активных дней {days} · серия {streak(u)} дн.[/size][/color]'
        nx.disabled = (y, m) >= (today.year, today.month)
        nx.opacity = .3 if nx.disabled else 1

    def move(delta):
        y, m = st['y'], st['m'] + delta
        st['y'], st['m'] = (y - 1, 12) if m < 1 else (y + 1, 1) if m > 12 else (y, m)
        fill()
    pv.bind(on_release=lambda *a: move(-1))
    nx.bind(on_release=lambda *a: move(1))
    fill()
    return c


def toggle_like(w, btn):
    pid = w['id']
    if D.uid in D.likes.get(pid, []):
        D.LK = [x for x in D.LK if not (x['post_id'] == pid and x['user_id'] == D.uid)]
        fn = lambda: rq('DELETE', f'/rest/v1/likes?post_id=eq.{pid}&user_id=eq.{D.uid}')
        on = False
    else:
        D.LK.append({'post_id': pid, 'user_id': D.uid, 'created_at': ''})
        fn = lambda: rq('POST', '/rest/v1/likes', json={'post_id': pid, 'user_id': D.uid}, headers={'Prefer': 'return=minimal'})
        on = True
    reindex()
    btn.set(on, len(D.likes.get(pid, [])))
    bg(fn)


def del_comment(cid):
    D.CM = [x for x in D.CM if x['id'] != cid]
    reindex()
    App.get_running_app().render()
    bg(lambda: rq('DELETE', f'/rest/v1/comments?id=eq.{cid}'))


def v_comments(pid):
    app = App.get_running_app()
    w = next((x for x in D.PO if x['id'] == pid), None)
    root = BoxLayout(orientation='vertical')
    gl = GridLayout(cols=1, spacing=dp(12), padding=[dp(16), dp(12)], size_hint_y=None)
    gl.bind(minimum_height=gl.setter('height'))
    if w:
        gl.add_widget(post_card(w, cm=False))
    cms = D.cmts.get(pid, [])
    gl.add_widget(L(text=f'[size=18sp][b]Комментарии[/b][/size]  [color=99a1a8]{len(cms)}[/color]'))
    for cmt in cms:
        c = Card()
        hd = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(10))
        hd.add_widget(plate(cmt['user_id'], 34))
        hd.add_widget(L(text=f"[b]{esc(name_of(cmt['user_id']))}[/b]\n[color=99a1a8][size=11sp]{cmt['created_at'][:10]}[/size][/color]", size_hint_y=1))
        if cmt['user_id'] == D.uid:
            dl = IconBtn('trash', 'plain', size=34, pos_hint={'center_y': .5})
            dl.bind(on_release=lambda x, cid=cmt['id']: confirm('Удалить комментарий?', lambda: del_comment(cid)))
            hd.add_widget(dl)
        c.add_widget(hd)
        c.add_widget(L(text=esc(cmt['body'])))
        gl.add_widget(c)
    if not cms:
        gl.add_widget(L(text='[color=99a1a8]Комментариев пока нет. Напишите первым.[/color]'))
    sv = ScrollView()
    sv.add_widget(gl)
    bar = BoxLayout(size_hint_y=None, height=dp(60), padding=dp(8), spacing=dp(8))
    f = inp('Написать комментарий')
    send = IconBtn('send', 'filled', size=44, pos_hint={'center_y': .5})

    def do(*a):
        body = f.text.strip()[:300]
        if not body:
            return
        send.disabled = True
        Clock.schedule_once(lambda dt_: setattr(send, 'disabled', False), 4)
        bg(lambda: rq('POST', '/rest/v1/comments', json={'post_id': pid, 'user_id': D.uid, 'body': body},
                      headers={'Prefer': 'return=minimal'}), lambda _: (setattr(f, 'text', ''), app.load_all()))
    send.bind(on_release=do)
    bar.add_widget(f)
    bar.add_widget(send)
    root.add_widget(sv)
    root.add_widget(bar)
    return root


def notes():
    if D._notes_rev != D.rev:   # пересчитывается только после изменения данных
        D._notes, D._notes_rev = _notes_build(), D.rev
    return D._notes


def _notes_build():
    mine = {w['id']: w for w in D.PO if w['user_id'] == D.uid}
    out = []
    for w in D.PO:
        if w['user_id'] != D.uid and is_f(w['user_id']):
            out.append((w['created_at'], f"[b]{esc(name_of(w['user_id']))}[/b] опубликовал(а) тренировку: {esc(w['ex'])}"
                        + (f", {g(w['kg'])} кг" if w.get('kg') else ''), ('comments', w['id'])))
    for l in D.LK:
        if l['post_id'] in mine and l['user_id'] != D.uid and l.get('created_at'):
            out.append((l['created_at'], f"[b]{esc(name_of(l['user_id']))}[/b] оценил(а) вашу тренировку: {esc(mine[l['post_id']]['ex'])}", ('comments', l['post_id'])))
    for c in D.CM:
        if c['post_id'] in mine and c['user_id'] != D.uid:
            out.append((c['created_at'], f"[b]{esc(name_of(c['user_id']))}[/b] прокомментировал(а): {esc(c['body'][:80])}", ('comments', c['post_id'])))
    for f in D.FO:
        if f['following'] == D.uid and f.get('created_at'):
            out.append((f['created_at'], f"[b]{esc(name_of(f['follower']))}[/b] подписался(ась) на вас", ('user', f['follower'])))
    out.sort(key=lambda x: x[0], reverse=True)
    return out[:60]


def unread_count():
    return sum(1 for n in notes() if n[0] > D.seen)


def seen_file():
    return os.path.join(App.get_running_app().user_data_dir, 'seen.json')


def save_seen():
    try:
        with open(seen_file(), 'w') as fh:
            json.dump({'t': D.seen}, fh)
    except Exception:
        pass


def load_seen():
    try:
        with open(seen_file()) as fh:
            D.seen = json.load(fh)['t']
    except Exception:
        D.seen = dt.datetime.now(dt.timezone.utc).isoformat()
        save_seen()


def v_notes(_):
    items, seen = notes(), D.seen
    D.seen = dt.datetime.now(dt.timezone.utc).isoformat()
    save_seen()
    ch = [head('Что нового', 'Уведомления', 'Новые тренировки подписок, оценки, комментарии и подписчики')]
    for t, text, target in items:
        c = CardB()
        c.add_widget(L(text=('[color=b7ff2a]● [/color]' if t > seen else '') + text + f"\n[color=99a1a8][size=11sp]{t[:10]}[/size][/color]"))
        c.bind(on_release=lambda x, tg=target: App.get_running_app().go(*tg))
        ch.append(c)
    if not items:
        ch.append(L(text='[color=99a1a8]Пока ничего нового.[/color]'))
    return scroll(ch)


def theme_file():
    return os.path.join(App.get_running_app().user_data_dir, 'theme.json')


def load_theme():
    try:
        with open(theme_file()) as fh:
            THEME.update(json.load(fh))
        THEME['seed'] = min(max(int(THEME['seed']), 0), len(SEEDS) - 1)
    except Exception:
        pass


def set_theme(**kw):
    THEME.update(kw)
    try:
        with open(theme_file(), 'w') as fh:
            json.dump(THEME, fh)
    except Exception:
        pass
    compute_globals()
    app = App.get_running_app()
    app.sync_theme()
    app.render()


def v_theme(_):
    ch = [head('Персонализация', 'Студия темы', 'Цвет, режим и форма. Применяется сразу')]
    c = Card()
    c.add_widget(L(text='[b]Цвет акцента[/b]'))
    gr = GridLayout(cols=3, spacing=dp(8), size_hint_y=None)
    gr.bind(minimum_height=gr.setter('height'))
    for i, (n, s1, s3) in enumerate(SEEDS):
        col = hx(s1)
        dark_text = .299 * col[0] + .587 * col[1] + .114 * col[2] > .55
        b = Btn(text=n + (' •' if THEME['seed'] == i else ''), bg=col, fg=(0, 0, 0, 1) if dark_text else (1, 1, 1, 1),
                height=dp(44), font_size=dp(13))
        b.bind(on_release=lambda x, i=i: set_theme(seed=i))
        gr.add_widget(b)
    c.add_widget(gr)
    ch.append(c)
    for title, key, opts in (('Режим', 'mode', (('light', 'Светлая'), ('dark', 'Тёмная'), ('oled', 'OLED'))),
                             ('Форма', 'shape', ((0.5, 'Острые'), (1.0, 'Стандарт'), (1.4, 'Круглые')))):
        c = Card()
        c.add_widget(L(text=f'[b]{title}[/b]'))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for val, name in opts:
            on = THEME[key] == val
            b = Btn(text=name, bg=SEC if on else CARD2, fg=ONSEC if on else TX, height=dp(44), font_size=dp(13))
            b.bind(on_release=lambda x, k=key, v=val: set_theme(**{k: v}))
            row.add_widget(b)
        c.add_widget(row)
        ch.append(c)
    ch.append(L(text='[color=99a1a8][size=12sp]Динамический цвет из обоев (Android 12+) доступен только в нативных приложениях. Здесь палитра строится из выбранного цвета по правилам Material You.[/size][/color]'))
    return scroll(ch)


def v_loading(text='Загружаем…'):
    fl = FloatLayout()
    box = BoxLayout(orientation='vertical', size_hint=(None, None), size=(dp(220), dp(110)), spacing=dp(10),
                    pos_hint={'center_x': .5, 'center_y': .55})
    box.add_widget(Dumbbell(size=(dp(64), dp(64)), pos_hint={'center_x': .5}))
    box.add_widget(L(text=f'[color=99a1a8]{text}[/color]', halign='center'))
    fl.add_widget(box)
    return fl


VIEWS = {'auth': v_auth, 'feed': v_feed, 'rank': v_rank, 'search': v_search, 'user': v_user, 'edit': v_edit, 'people': v_people, 'compose': v_compose, 'theme': v_theme, 'comments': v_comments, 'notes': v_notes}


class IronApp(App):
    tx = ListProperty(TX)
    c_bg, c_card, c_hi, c_line = ListProperty(BG), ListProperty(CARD), ListProperty(CARD2), ListProperty(LINE)
    c_pri, c_pric, c_onpric, c_sec = ListProperty(ACC), ListProperty(PRC), ListProperty(ONPRC), ListProperty(SEC)
    c_ter, c_onter = ListProperty(TER), ListProperty(ONTER)
    shape, r_card, r_media, r_btn = NumericProperty(1), NumericProperty(0), NumericProperty(0), NumericProperty(0)
    mode = 'in'
    q = ''
    paused = False

    def set_busy(self):
        """Маленькая гантель в шапке крутится, пока идёт любая загрузка."""
        if D.busy > 0 and not self.spin.parent:
            self.hd.add_widget(self.spin, index=1)
        elif D.busy <= 0 and self.spin.parent:
            self.hd.remove_widget(self.spin)

    def sync_theme(self):
        self.tx, self.c_bg, self.c_card, self.c_hi, self.c_line = list(TX), list(BG), list(CARD), list(CARD2), list(LINE)
        self.c_pri, self.c_pric, self.c_onpric, self.c_sec = list(ACC), list(PRC), list(ONPRC), list(SEC)
        self.c_ter, self.c_onter = list(TER), list(ONTER)
        sh = THEME['shape']
        self.shape, self.r_card, self.r_media = sh, dp(28) * sh, dp(16) * sh
        self.r_btn = dp(500) if sh >= 1 else dp(10)
        Window.clearcolor = BG
        if hasattr(self, 'bk'):
            self.bk.bg, self.bk.fg = BG, TX
            self.note.color = ACC

    def build(self):
        load_theme()
        compute_globals()
        self.sync_theme()
        Builder.load_string(KV)
        Window.clearcolor = BG
        Window.softinput_mode = 'below_target'
        Window.bind(on_keyboard=self.on_key)
        self.stack = []
        root = BoxLayout(orientation='vertical')
        self.hd = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(10), 0], spacing=dp(8))
        self.bk = Btn(text='‹', bg=BG, fg=TX, size_hint=(None, None), size=(dp(40), dp(40)), font_size=dp(26))
        self.bk.bind(on_release=lambda *a: self.back())
        self.ttl = L(text=f"[size=20sp]{dfont('Железный круг')}[/size]", size_hint_y=1, valign='middle')
        self.hd.add_widget(self.bk)
        self.hd.add_widget(self.ttl)
        self.bell = BellBtn(pos_hint={'center_y': .5})
        self.bell.bind(on_release=lambda *a: self.go('notes'))
        self.hd.add_widget(self.bell)
        self.spin = Dumbbell(size=(dp(30), dp(30)), pos_hint={'center_y': .5})
        self.note = L(text='', size_hint_y=None, height=0, color=ACC)
        self.body = BoxLayout()
        self.body.add_widget(v_loading())  # гантель видна с первого кадра, пока приложение готовится
        self.nav = BoxLayout(size_hint_y=None, height=dp(80))
        self.tabs = {}
        for t, n, a, ic in (('Главная', 'feed', None, 'home'), ('Поиск', 'search', None, 'search'),
                            ('Добавить', 'compose', 'post', 'add'), ('Рейтинг', 'rank', None, 'rank'),
                            ('Профиль', 'user', None, 'user')):
            b = NavItem(t, ic)
            b.bind(on_release=lambda x, n=n, a=a: self.go(n, a, root=True))
            self.tabs[n] = b
            self.nav.add_widget(b)
        for w in (self.hd, self.note, self.body, self.nav):
            root.add_widget(w)
        return root

    def on_start(self):
        load_seen()
        Clock.schedule_interval(lambda dt_: self.poll(), 60)
        Clock.schedule_interval(self._beat, 20)
        sess, cache = read_json(sess_file()), read_json(cache_file())
        if sess and sess.get('rt') and sess.get('uid') and cache and cache.get('uid') == sess['uid']:
            # мгновенный старт: показываем сохранённую ленту, а вход обновляем в фоне
            D.rt, D.uid = sess['rt'], sess['uid']
            D.P, D.FO, D.PO, D.FM = cache['P'], cache['FO'], cache['PO'], cache['FM']
            D.LK, D.CM = cache.get('LK', []), cache.get('CM', [])
            reindex()
            D.known, D.known_init = {w['id'] for w in D.PO}, True
            self.go('feed', root=True)
            self.start_push()
            bg(refresh_token, self._after_refresh, quiet=True)
        elif sess and sess.get('rt'):
            D.rt, D.loading = sess['rt'], True
            self.go('feed', root=True)
            bg(refresh_token, lambda ok: self.load_all(first=True) if ok else self._to_auth(), quiet=True)
        else:
            self.go('auth', root=True)

    def _after_refresh(self, ok):
        if ok:
            self.load_all(silent=True)
        elif ok is False:
            self.logout()
        else:
            self.toast('Нет сети: показаны сохранённые данные')

    def _to_auth(self):
        D.loading = False
        self.go('auth', root=True)

    def toast(self, msg):
        self.note.text, self.note.height = esc(str(msg)), dp(36)
        Clock.unschedule(self._clr)
        Clock.schedule_once(self._clr, 5)

    def _clr(self, dt):
        self.note.text, self.note.height = '', 0

    def refresh_bell(self):
        n = unread_count() if D.uid else 0
        self.bell.ic.dot = n > 0
        self.bell.ic.color = TX
        self.bell.opacity, self.bell.disabled = (1, False) if D.uid else (0, True)

    def notify(self, title, msg):
        self.toast(f'{title}: {msg}')
        try:
            from plyer import notification
            notification.notify(title=title, message=msg, app_name='Железный круг', timeout=8)
        except Exception:
            pass

    fcm_token = None
    push_note = ''

    def _fcm_begin(self):
        """Запускает получение токена Firebase. Вызывается только в главном потоке: Java-классы приложения
        (в том числе Firebase) не находятся из обычных потоков Python. Возвращает (задача, пояснение)."""
        try:
            from jnius import autoclass
        except Exception:
            return None, 'Это не Android: Firebase работает только на телефоне.'
        try:
            FirebaseApp = autoclass('com.google.firebase.FirebaseApp')
            Messaging = autoclass('com.google.firebase.messaging.FirebaseMessaging')
        except Exception as e:
            return None, ('Классы Firebase не найдены в приложении (' + str(e)[:150] + '). Либо установлена сборка без '
                          'Firebase, либо строки «Firebase push» в buildozer.spec не применились. Пересоберите приложение.')
        try:
            ctx = autoclass('org.kivy.android.PythonActivity').mActivity
            if FirebaseApp.initializeApp(ctx) is None:
                return None, ('Настройки Firebase не попали в сборку: нет firebase.xml. Выполните '
                              'tools/make_firebase_xml.py и проверьте строку android.add_resources в buildozer.spec.')
            return Messaging.getInstance().getToken(), 'ok'
        except Exception as e:
            return None, 'Ошибка Firebase: ' + str(e)[:200]

    def _register_push(self, done):
        """Получает токен (ожидание без блокировки интерфейса), сохраняет его на сервере и вызывает done(токен, пояснение)."""
        task, note = self._fcm_begin()
        if not task:
            return done(None, note)
        st = {'n': 0}

        def poll(dt):
            st['n'] += 1
            try:
                if not task.isComplete():
                    if st['n'] > 60:
                        done(None, 'Токен не получен: Google не ответил за 30 секунд. Проверьте интернет и сервисы Google Play.')
                        return False
                    return True
                if not task.isSuccessful():
                    exc = task.getException()
                    why = str(exc.getMessage()) if exc else 'неизвестная ошибка'
                    done(None, f'Токен не получен: {why}. На телефоне нужны сервисы Google Play и интернет.')
                    return False
                tok = task.getResult()
                tok = str(tok.toString()) if hasattr(tok, 'toString') else str(tok)
            except Exception as e:
                done(None, 'Ошибка Firebase: ' + str(e)[:200])
                return False
            self.fcm_token = tok

            def save():
                try:
                    rq('POST', '/rest/v1/push_tokens?on_conflict=token', json={'user_id': D.uid, 'token': tok},
                       headers={'Prefer': 'resolution=merge-duplicates,return=minimal'})
                    return None
                except Exception as e:
                    return str(e)[:200]
            bg(save, lambda err: done(tok, 'ok' if not err else 'Токен получен, но не сохранён на сервере: ' + err), quiet=True)
            return False
        Clock.schedule_interval(poll, .5)

    def start_push(self):
        """Включает уведомления при закрытом приложении: Firebase push, а если он не подключён, фоновая служба."""
        if not load_settings().get('push', True):
            return

        def done(tok, note):
            self.push_note = note
            if tok and note == 'ok':
                self.stop_service()  # push от сервера надёжнее фонового опроса
            else:
                self.start_service()
        self._register_push(done)

    def start_service(self):
        try:
            from android import AndroidService
            self._svc = AndroidService('Железный круг', 'Следим за новыми тренировками')
            self._svc.start('go')
        except Exception:
            return
        st = load_settings()
        if not st.get('asked_battery'):
            st['asked_battery'] = True
            save_settings(st)
            self.ask_battery()

    def stop_service(self):
        try:
            from android import AndroidService
            AndroidService('Железный круг', '').stop()
        except Exception:
            pass

    def stop_push(self):
        self.stop_service()
        tok = self.fcm_token
        if tok and D.tok:  # токен отвязывается от аккаунта, чтобы чужие уведомления не приходили на этот телефон
            h = {'Authorization': 'Bearer ' + D.tok}
            bg(lambda: rq('DELETE', f'/rest/v1/push_tokens?token=eq.{tok}', headers=h), quiet=True)
        self.fcm_token = None

    def ask_battery(self):
        """Просит не ограничивать приложение в фоне, иначе Android может усыплять службу."""
        try:
            from jnius import autoclass, cast
            act = autoclass('org.kivy.android.PythonActivity').mActivity
            pkg = act.getPackageName()
            pm = cast('android.os.PowerManager', act.getSystemService(autoclass('android.content.Context').POWER_SERVICE))
            if not pm.isIgnoringBatteryOptimizations(pkg):
                it = autoclass('android.content.Intent')(autoclass('android.provider.Settings').ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                it.setData(autoclass('android.net.Uri').parse('package:' + pkg))
                act.startActivity(it)
        except Exception:
            pass

    def toggle_push(self, btn):
        st = load_settings()
        st['push'] = not st.get('push', True)
        save_settings(st)
        btn.text = 'Фоновые уведомления: ' + ('вкл' if st['push'] else 'выкл')
        if st['push']:
            self.ask_notif()
            self.start_push()
        else:
            self.stop_push()

    def _beat(self, dt=None, off=False):
        """Отметка «приложение открыто»: пока она свежая, служба не дублирует уведомления."""
        try:
            with open(data_file('app_active.json'), 'w') as fh:
                json.dump({'t': 0 if (off or self.paused) else time.time()}, fh)
        except Exception:
            pass

    def on_stop(self):
        self._beat(off=True)

    def ask_notif(self):
        try:
            from android.permissions import request_permissions
            request_permissions(['android.permission.POST_NOTIFICATIONS'])
        except Exception:
            pass

    _sig = None

    def poll(self):
        """Раз в минуту спрашивает у сервера только время последних записей; всё загружает лишь при изменениях."""
        if not D.uid or self.paused or D.busy > 0:
            return

        def f():
            def last(t):
                try:
                    r = rq('GET', f'/rest/v1/{t}?select=created_at&order=created_at.desc&limit=1')
                    return r[0]['created_at'] if r else ''
                except Exception:
                    return '?'
            with ThreadPoolExecutor(max_workers=4) as pool:
                return tuple(pool.map(last, ('posts', 'likes', 'comments', 'follows')))

        def ok(sig):
            if sig != self._sig:
                self._sig = sig
                self.load_all(silent=True)
        bg(f, ok, quiet=True)

    def on_pause(self):
        self.paused = True
        self._beat()
        return True

    def on_resume(self):
        self.paused = False
        self._beat()
        if D.uid:
            self.load_all(silent=True)

    def load_all(self, first=False, silent=False):
        if not D.P:
            D.loading = True

        def f():
            q = lambda t, extra='': rq('GET', f'/rest/v1/{t}?select=*{extra}')

            def opt(t, extra=''):
                try:
                    return q(t, extra)
                except Exception:
                    return []  # лайки и комментарии появятся после schema_v3.sql
            try:
                with ThreadPoolExecutor(max_workers=6) as pool:
                    fs = [pool.submit(q, 'profiles'), pool.submit(q, 'follows'),
                          pool.submit(q, 'posts', '&order=created_at.desc&limit=120'),
                          pool.submit(q, 'form_posts', '&order=created_at.desc&limit=200'),
                          pool.submit(opt, 'likes', '&order=created_at.desc&limit=1500'), pool.submit(opt, 'comments', '&order=created_at.desc&limit=800')]
                    return tuple(x.result() for x in fs)
            except Exception:
                D.loading = False
                Clock.schedule_once(lambda dt_: self.render() if D.uid else self.go('auth', root=True))
                raise

        def ok(r):
            sig = lambda: (len(D.P), len(D.FO), len(D.PO), len(D.FM), len(D.LK), len(D.CM))
            before = sig()
            D.loading = False
            D.P = {p['id']: p for p in r[0]}
            D.FO, D.PO, D.FM, D.LK, D.CM = r[1], r[2], r[3], r[4], r[5]
            reindex()
            new = [w for w in D.PO if w['user_id'] != D.uid and is_f(w['user_id']) and w['id'] not in D.known]
            if D.known_init and new:
                if len(new) == 1:
                    self.notify(name_of(new[0]['user_id']), f"опубликовал(а): {new[0]['ex']}")
                else:
                    self.notify('Железный круг', f'Новых тренировок от подписок: {len(new)}')
            D.known |= {w['id'] for w in D.PO}
            D.known_init = True
            threading.Thread(target=save_cache, daemon=True).start()
            if first:
                self.ask_notif()
                self.start_push()
                self.go('feed', root=True)
            elif (not silent or sig() != before) and self.stack[-1][0] in ('feed', 'rank', 'user', 'comments', 'notes', 'people'):
                self.render()
            self.refresh_bell()
        bg(f, ok, quiet=silent)

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
        self.body.add_widget(v_loading() if D.loading and not D.P and n in ('feed', 'rank', 'search', 'user', 'notes', 'comments', 'people') else VIEWS[n](a))
        self.bk.opacity = 1 if len(self.stack) > 1 and D.uid else 0
        self.bk.disabled = not (len(self.stack) > 1 and D.uid)
        self.nav.height, self.nav.opacity = (dp(80), 1) if D.uid else (0, 0)
        self.nav.disabled = not D.uid
        self.refresh_bell()
        cur = self.stack[0][0]
        for k, b in self.tabs.items():
            b.set_active(k == cur)

    def on_key(self, w, key, *a):
        if key == 27 and len(self.stack) > 1:
            self.back()
            return True
        return False

    def logout(self):
        self.stop_push()
        for p in (sess_file(), cache_file(), data_file('push_state.json')):
            try:
                os.remove(p)
            except Exception:
                pass
        D.tok = D.rt = D.uid = None
        D.P, D.FO, D.PO, D.FM, D.LK, D.CM = {}, [], [], [], [], []
        reindex()
        D.known, D.known_init = set(), False
        self.q = ''
        self.go('auth', root=True)


if __name__ == '__main__':
    IronApp().run()
