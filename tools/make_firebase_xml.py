"""Превращает google-services.json (из консоли Firebase) в firebase/firebase.xml для сборки приложения.

Запуск из папки проекта:   python tools/make_firebase_xml.py google-services.json
"""
import json
import os
import sys
from xml.sax.saxutils import escape

PACKAGE = 'org.ironcircle.ironcircle'
if len(sys.argv) < 2:
    sys.exit('Укажите путь к google-services.json')
d = json.load(open(sys.argv[1], encoding='utf-8'))
info = d['project_info']
client = next((c for c in d['client'] if c['client_info']['android_client_info']['package_name'] == PACKAGE), None)
if not client:
    names = [c['client_info']['android_client_info']['package_name'] for c in d['client']]
    sys.exit(f'В файле нет приложения {PACKAGE}. Есть: {names}. Добавьте Android-приложение с таким именем пакета в консоли Firebase.')
vals = {
    'google_app_id': client['client_info']['mobilesdk_app_id'],
    'gcm_defaultSenderId': info['project_number'],
    'google_api_key': client['api_key'][0]['current_key'],
    'google_crash_reporting_api_key': client['api_key'][0]['current_key'],
    'project_id': info['project_id'],
    'google_storage_bucket': info.get('storage_bucket', ''),
}
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, 'firebase', 'firebase.xml')
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w', encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n')
    for k, v in vals.items():
        f.write(f'    <string name="{k}" translatable="false">{escape(v)}</string>\n')
    f.write('</resources>\n')
print('Готово:', out)
