"""Builds docs/data.js from the lesson catalog (קטלוג שיעורים.csv).

Until the media host is set in data/config.json, the site plays the audio from the old Spotify links.
Run: python scripts/build_site.py
"""
import json
from collections import Counter
from difflib import SequenceMatcher

from common import ROOT, PODCASTS, audio_file, lesson_id, load_catalog, load_config, season_of

OUT = ROOT / 'docs' / 'data.js'
OLD_FEED = 'https://anchor.fm/s/1080dfd28/podcast/rss'

# Intro for a season whose lessons don't share one blurb (new series, written once here).
SEASON_ABOUT = {
    'תפילה': 'עיונים ב"עבודה שבלב" - התפילה - במהותה, במקורותיה ובצדדיה השונים',
}


def main():
    cfg = load_config()
    live = 'EXAMPLE' not in cfg['media_url'] + cfg['site_url']
    media, site = cfg['media_url'].rstrip('/') + '/', cfg['site_url'].rstrip('/') + '/'
    rows = load_catalog()
    pods = {}
    for p in PODCASTS:
        rss = f'{site}feeds/{p["key"]}.xml' if live else (OLD_FEED if p['key'] == 'emuna' else None)
        pods[p['name']] = {**p, 'links': {**p['links'], 'rss': rss}, 'seasons': []}
    for r in rows:
        pod = pods[r['פודקאסט'].strip()]
        season, lid = season_of(r), lesson_id(r)
        if not pod['seasons'] or pod['seasons'][-1]['name'] != season:
            pod['seasons'].append({'name': season, 'about': '', 'lessons': []})
        f = audio_file(lid)
        pod['seasons'][-1]['lessons'].append({
            'id': lid, 'title': r['כותרת חדשה'].strip(), 'desc': r['תיאור'].strip(),
            'date': r['תאריך'], 'dur': r['אורך'],
            'audio': f'{media}audio/{lid}{f.suffix.lower()}' if live and f else r['קישור לקובץ'],
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
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text('window.DATA = ' + json.dumps(list(pods.values()), ensure_ascii=False, indent=1) + ';\n', encoding='utf-8')
    print(f'{len(rows)} lessons -> {OUT}')


if __name__ == '__main__':
    main()
