"""Renders podcast covers (3000x3000) and one image per lesson (1400x1400) from art/template.html.

Uses the Edge (or Chrome) browser installed on the machine in headless mode, then saves JPEG.
Existing images are skipped; pass --force to redo them, or lesson ids to redo only those.
Run: python scripts/render_art.py [--force] [l1a2b3c ...]
"""
import os, re, subprocess, sys, tempfile, urllib.parse
from pathlib import Path
from PIL import Image

from common import ROOT, POD_BY_NAME, PODCASTS, lesson_id, load_catalog

TEMPLATE = (ROOT / 'art' / 'template.html').as_uri()
COVERS = ROOT / 'art' / 'covers'
LESSONS = ROOT / 'art' / 'lessons'

BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
]


def split_title(row):
    """'נח- מעשי האדם' -> ('פרשת נח', 'מעשי האדם'); 'המדינה היהודית (6)- גיור' -> ('המדינה היהודית · שיעור 6', 'גיור')."""
    title, pod = row['כותרת חדשה'].strip(), row['פודקאסט'].strip()
    m = re.match(r'(.+?)\s*\((\d+)\)\s*-\s*(.+)', title)
    if m:
        return f'{m.group(1)} · שיעור {m.group(2)}', m.group(3)
    if '- ' in title:
        head, rest = title.split('- ', 1)
        return (f'פרשת {head}' if pod == 'פשט ועומק בפרשת השבוע' else head), rest
    holiday = next((h for h in POD_BY_NAME[pod].get('topics', []) if h in title), None)
    return (row['עונה'].strip() or holiday or pod), title


def render(params, out, px, browser):
    """Screenshots the 1000px template at a device scale giving `px` pixels, saved as JPEG."""
    url = TEMPLATE + '#' + urllib.parse.urlencode(params)
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / 'a.png'
        subprocess.run([browser, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                        f'--force-device-scale-factor={px / 1000}', '--window-size=1000,1000',
                        '--virtual-time-budget=6000', f'--screenshot={png}', url],
                       check=True, capture_output=True)
        Image.open(png).convert('RGB').resize((px, px), Image.LANCZOS).save(out, 'JPEG', quality=88, optimize=True)


def main():
    args = sys.argv[1:]
    force = '--force' in args
    only = {a for a in args if a.startswith('l')}
    browser = next((b for b in BROWSERS if os.path.exists(b)), None)
    if not browser:
        sys.exit('Edge or Chrome not found')
    COVERS.mkdir(parents=True, exist_ok=True)
    LESSONS.mkdir(parents=True, exist_ok=True)
    if not only:
        for p in PODCASTS:
            out = COVERS / f'{p["key"]}.jpg'
            if force or not out.exists():
                render({'kind': 'cover', 'icon': p['icon'], 'big': p['name']}, out, 3000, browser)
                print('cover', out.name, flush=True)
    for r in load_catalog():
        lid = lesson_id(r)
        out = LESSONS / f'{lid}.jpg'
        if (only and lid not in only) or (not force and not only and out.exists()):
            continue
        small, big = split_title(r)
        render({'kind': 'episode', 'icon': POD_BY_NAME[r['פודקאסט'].strip()]['icon'], 'pod': r['פודקאסט'].strip(), 'small': small, 'big': big}, out, 1400, browser)
        print('lesson', out.name, big, flush=True)


if __name__ == '__main__':
    main()
