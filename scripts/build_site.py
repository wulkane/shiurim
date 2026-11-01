"""Builds docs/data.js from the lesson catalog (קטלוג שיעורים.csv).

Until the media host is set in data/config.json, the site plays the audio from the old Spotify links.
Run: python scripts/build_site.py
"""
import html, json
from collections import Counter
from difflib import SequenceMatcher

from common import ROOT, PODCASTS, audio_info, lesson_id, load_catalog, load_config, season_of

OUT = ROOT / 'docs' / 'data.js'
OLD_FEED = 'https://anchor.fm/s/1080dfd28/podcast/rss'
EPISODE_LINKS = ROOT / 'data' / 'episode_links.json'   # optional: {lesson id: {platform: link to that lesson}}

# Intro for a season whose lessons don't share one blurb (new series, written once here).
SEASON_ABOUT = {
    'תפילה': 'עיונים ב"עבודה שבלב" - התפילה - במהותה, במקורותיה ובצדדיה השונים',
}


# A page per lesson with its own title, sentence and picture, so a link to it shows the lesson in a chat
# preview (WhatsApp reads these tags and ignores the #lesson part of an address). It sends the visitor
# on to the lesson on the site. The bot writes the same page for new lessons (bot/lib.js, sharePage).
SHARE_PAGE = '''<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:locale" content="he_IL">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{image}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary">
<meta http-equiv="refresh" content="0;url=../#{lid}">
<script>location.replace('../#{lid}');</script>
</head>
<body><p><a href="../#{lid}">{title}</a></p></body>
</html>
'''


def share_page(site, lid, title, desc, image):
    esc = lambda t: html.escape(t, quote=True)
    return SHARE_PAGE.format(title=esc(title), desc=esc(desc), image=esc(image), url=f'{site}l/{lid}', lid=lid)


def main():
    cfg = load_config()
    live = 'EXAMPLE' not in cfg['media_url'] + cfg['site_url']
    media, site = cfg['media_url'].rstrip('/') + '/', cfg['site_url'].rstrip('/') + '/'
    rows = load_catalog()
    episode_links = json.loads(EPISODE_LINKS.read_text(encoding='utf-8')) if EPISODE_LINKS.exists() else {}
    pods = {}
    for p in PODCASTS:
        rss = f'{site}feeds/{p["key"]}.xml' if live else (OLD_FEED if p['key'] == 'emuna' else None)
        pods[p['name']] = {**p, 'links': {**p['links'], 'rss': rss}, 'seasons': []}
    for r in rows:
        pod = pods[r['פודקאסט'].strip()]
        season, lid = season_of(r), lesson_id(r)
        if not pod['seasons'] or pod['seasons'][-1]['name'] != season:
            pod['seasons'].append({'name': season, 'about': '', 'lessons': []})
        info = audio_info(lid)
        pod['seasons'][-1]['lessons'].append({
            'id': lid, 'title': r['כותרת חדשה'].strip(), 'desc': r['תיאור'].strip(),
            'date': r['תאריך'], 'dur': r['אורך'],
            'audio': f'{media}audio/{lid}{info[0]}' if live and info else r['קישור לקובץ'],
            **({'links': episode_links[lid]} if lid in episode_links else {}),
        })
    # A series repeats its description on every lesson: show it once on the season.
    for pod in pods.values():
        for s in pod['seasons']:
            descs = [l['desc'] for l in s['lessons']]
            top, count = Counter(descs).most_common(1)[0]
            if len(descs) > 2 and count > len(descs) / 2:
                s['about'] = top.split(':')[0].strip()  # only the opening sentence, without the list of lessons
                for l in s['lessons']:
                    d = l['desc']
                    if d.startswith(top):
                        l['desc'] = d[len(top):].strip()
                    elif SequenceMatcher(None, d, top).ratio() > 0.9:  # same blurb, small spelling variant
                        l['desc'] = ''
            s['about'] = s['about'] or SEASON_ABOUT.get(s['name'], '')
    pages = OUT.parent / 'l'
    pages.mkdir(exist_ok=True)
    for pod in pods.values():
        for sn in pod['seasons']:
            for l in sn['lessons']:
                art = ROOT / 'art' / 'lessons' / f'{l["id"]}.jpg'
                image = f'{media}art/lessons/{l["id"]}.jpg' if art.exists() else f'{site}og/{pod["key"]}.jpg'
                page = share_page(site, l['id'], l['title'], l['desc'] or sn['about'] or pod['about'], image)
                target = pages / f'{l["id"]}.html'
                if not target.exists() or target.read_text(encoding='utf-8') != page:
                    target.write_bytes(page.encode('utf-8'))   # bytes, so the file keeps plain LF line ends
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text('window.DATA = ' + json.dumps(list(pods.values()), ensure_ascii=False, indent=1) + ';\n', encoding='utf-8')
    print(f'{len(rows)} lessons -> {OUT}')


if __name__ == '__main__':
    main()
