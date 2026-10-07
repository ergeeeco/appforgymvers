"""Скачивает иконки Phosphor (лицензия MIT) и превращает их в PNG для приложения.

Запуск из папки проекта:   python tools/get_icons.py
Нужно: git, интернет и    pip install cairosvg    (в Ubuntu/WSL ещё: sudo apt install libcairo2)

Что делает:
1. клонирует github.com/phosphor-icons/core в icons_src/phosphor-core (один раз);
2. берёт нужные SVG (список в tools/icons.json), переводит в PNG 96x96 и кладёт в icons/;
3. приложение само подхватывает icons/<имя>.png и перекрашивает в цвет темы.

Если иконку нужно подменить вручную: положите свой одноцветный PNG с прозрачным фоном в icons/ под тем же именем.
Параметры:  --weight bold  (regular, bold, light, thin)   --dry  (только показать план)   --size 128
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'icons_src')
CLONE = os.path.join(SRC, 'phosphor-core')
OUT = os.path.join(ROOT, 'icons')

ap = argparse.ArgumentParser()
ap.add_argument('--weight', default='regular')
ap.add_argument('--size', type=int, default=96)
ap.add_argument('--dry', action='store_true')
args = ap.parse_args()
icons = json.load(open(os.path.join(ROOT, 'tools', 'icons.json'), encoding='utf-8'))


def svg_path(name, weight):
    suffix = '' if weight == 'regular' else '-' + weight
    for p in (os.path.join(SRC, f'{name}{suffix}.svg'),                       # скачано вручную в icons_src/
              os.path.join(CLONE, 'assets', weight, f'{name}{suffix}.svg')):  # из клонированного репозитория
        if os.path.exists(p):
            return p
    return None


if not args.dry and not os.path.isdir(CLONE):
    os.makedirs(SRC, exist_ok=True)
    print('Клонирую phosphor-icons/core ...')
    subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/phosphor-icons/core', CLONE], check=False)

try:
    import cairosvg
except ImportError:
    cairosvg = None
    if not args.dry:
        sys.exit('Установите конвертер: pip install cairosvg  (и sudo apt install libcairo2)')

os.makedirs(OUT, exist_ok=True)
done, missing = 0, []
for internal, ph, weight, where in icons:
    w = weight or args.weight
    src = svg_path(ph, w)
    if args.dry:
        print(f'{internal:12s} <- {ph} ({w})  [{where}]  {"найден" if src else "нет файла"}')
        continue
    if not src:
        missing.append(f'{internal} ({ph}, {w})')
        continue
    cairosvg.svg2png(url=src, write_to=os.path.join(OUT, internal + '.png'), output_width=args.size, output_height=args.size)
    done += 1
if not args.dry:
    print(f'Готово: {done} иконок в icons/')
    if missing:
        print('Не нашлось (скачайте SVG вручную в icons_src/ и запустите снова):')
        for m in missing:
            print('  -', m)
