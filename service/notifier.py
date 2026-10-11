"""Фоновая служба «Железного круга».

Работает отдельным процессом (Android foreground service), пока приложение закрыто: раз в минуту проверяет
новые посты тех, на кого вы подписаны, а также лайки, комментарии и подписчиков, и показывает системное
уведомление. Нажатие на уведомление открывает приложение.
Когда приложение открыто, оно само показывает уведомления, служба в это время молчит (чтобы не дублировать).
"""
import datetime
import json
import os
import re
import sys
import time

import certifi
import requests

os.environ.setdefault('SSL_CERT_FILE', certifi.where())
APP = os.environ.get('ANDROID_ARGUMENT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRIV = os.environ.get('ANDROID_PRIVATE', APP)
sys.path.insert(0, APP)
SESS, STATE, HB = (os.path.join(PRIV, n) for n in ('session.json', 'push_state.json', 'app_active.json'))
INTERVAL = 60


def read(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def write(path, data):
    try:
        with open(path, 'w') as fh:
            json.dump(data, fh)
    except Exception:
        pass


def load_cfg():
    try:
        from config import URL, KEY
        return URL.strip().rstrip('/'), KEY.strip()
    except Exception:
        pass
    try:  # запасной вариант: значения, вписанные прямо в main.py
        txt = open(os.path.join(APP, 'main.py'), encoding='utf-8').read()
        u = re.search(r"SUPABASE_URL\s*=\s*'([^']+)'", txt)
        k = re.search(r"SUPABASE_KEY\s*=\s*'([^']+)'", txt)
        return u.group(1).strip().rstrip('/'), k.group(1).strip()
    except Exception:
        return '', ''


BASE, KEY = load_cfg()


def token():
    """Токен доступа из общего файла сессии; обновляется, только если истёк (его же использует приложение)."""
    s = read(SESS) or {}
    if not s.get('rt') or not s.get('uid'):
        return None, None
    if s.get('at') and s.get('exp', 0) - time.time() > 60:
        return s['at'], s['uid']
    r = requests.post(BASE + '/auth/v1/token?grant_type=refresh_token', json={'refresh_token': s['rt']},
                      headers={'apikey': KEY}, timeout=20)
    if r.status_code >= 400:
        return None, s['uid']
    d = r.json()
    write(SESS, {'rt': d['refresh_token'], 'uid': d['user']['id'], 'at': d['access_token'],
                 'exp': d.get('expires_at') or time.time() + d.get('expires_in', 3600)})
    return d['access_token'], d['user']['id']


def api(tok, table, params):
    r = requests.get(BASE + '/rest/v1/' + table, params=params,
                     headers={'apikey': KEY, 'Authorization': 'Bearer ' + tok}, timeout=25)
    r.raise_for_status()
    return r.json()


def notify(title, text):
    try:
        from jnius import autoclass, cast
        ctx = autoclass('org.kivy.android.PythonService').mService
        Context = autoclass('android.content.Context')
        PendingIntent = autoclass('android.app.PendingIntent')
        Builder = autoclass('android.app.Notification$Builder')
        sdk = autoclass('android.os.Build$VERSION').SDK_INT
        nm = cast('android.app.NotificationManager', ctx.getSystemService(Context.NOTIFICATION_SERVICE))
        if sdk >= 26:
            Channel = autoclass('android.app.NotificationChannel')
            nm.createNotificationChannel(Channel('ironcircle_news', 'Новости', 3))
            b = Builder(ctx, 'ironcircle_news')
        else:
            b = Builder(ctx)
        b.setContentTitle(title)
        b.setContentText(text)
        b.setSmallIcon(ctx.getApplicationInfo().icon)
        b.setAutoCancel(True)
        launch = ctx.getPackageManager().getLaunchIntentForPackage(ctx.getPackageName())
        flags = PendingIntent.FLAG_UPDATE_CURRENT | (PendingIntent.FLAG_IMMUTABLE if sdk >= 23 else 0)
        b.setContentIntent(PendingIntent.getActivity(ctx, 0, launch, flags))
        nm.notify(int(time.time() * 1000) % 2147483647, b.build())
    except Exception as e:
        print('[service] notify:', title, text, '|', e)


def events(tok, uid, last):
    """Новые события после метки last: [(время, автор, текст)]."""
    out = []
    ids = [f['following'] for f in api(tok, 'follows', {'select': 'following', 'follower': 'eq.' + uid})]
    if ids:
        for p in api(tok, 'posts', {'select': 'id,user_id,ex,kg,created_at', 'user_id': 'in.(' + ','.join(ids) + ')',
                                    'created_at': 'gt.' + last, 'order': 'created_at.asc', 'limit': '20'}):
            kg = f", {p['kg']:g} кг" if p.get('kg') else ''
            out.append((p['created_at'], p['user_id'], 'опубликовал(а) тренировку: ' + p['ex'] + kg))
    mine = {p['id']: p['ex'] for p in api(tok, 'posts', {'select': 'id,ex', 'user_id': 'eq.' + uid})}
    if mine:
        pid = 'in.(' + ','.join(str(i) for i in mine) + ')'
        base = {'post_id': pid, 'user_id': 'neq.' + uid, 'created_at': 'gt.' + last, 'order': 'created_at.asc', 'limit': '20'}
        try:
            for x in api(tok, 'likes', {**base, 'select': 'post_id,user_id,created_at'}):
                out.append((x['created_at'], x['user_id'], 'оценил(а) вашу тренировку: ' + mine.get(x['post_id'], '')))
        except Exception:
            pass
        try:
            for x in api(tok, 'comments', {**base, 'select': 'post_id,user_id,body,created_at'}):
                out.append((x['created_at'], x['user_id'], 'прокомментировал(а): ' + x['body'][:80]))
        except Exception:
            pass
    try:
        for x in api(tok, 'follows', {'select': 'follower,created_at', 'following': 'eq.' + uid,
                                      'created_at': 'gt.' + last, 'order': 'created_at.asc', 'limit': '20'}):
            out.append((x['created_at'], x['follower'], 'подписался(ась) на вас'))
    except Exception:
        pass
    return sorted(out)


def poll():
    tok, uid = token()
    if not tok:
        return
    st = read(STATE) or {}
    if not st.get('last'):  # первый запуск: старые события не показываем
        write(STATE, {'last': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        return
    ev = events(tok, uid, st['last'])
    if not ev:
        return
    write(STATE, {'last': ev[-1][0]})
    if time.time() - (read(HB) or {}).get('t', 0) < 70:
        return  # приложение открыто: оно показывает уведомления само
    if len(ev) > 3:
        notify('Железный круг', f'Новых событий: {len(ev)}')
        return
    who = ','.join(sorted({e[1] for e in ev}))
    names = {p['id']: p['username'] for p in api(tok, 'profiles', {'select': 'id,username', 'id': 'in.(' + who + ')'})}
    for t, a, text in ev:
        notify(names.get(a, 'Атлет'), text)


def run():
    print('[service] notifier started')
    while True:
        try:
            poll()
        except Exception as e:
            print('[service] error:', e)
        time.sleep(INTERVAL)


if os.environ.get('IC_SERVICE_TEST') != '1':
    run()
