"""Builds one podcast RSS feed per podcast into docs/feeds/<key>.xml.

Spotify, Apple, YouTube and the other apps read these feeds. Audio and artwork are expected on the
media host (config media_url) under audio/<id>.<ext>, art/lessons/<id>.jpg and art/covers/<key>.jpg.
Lessons that came from the old Spotify feed keep their original guid and date, so after the
"אמת ואמונה" redirect listeners don't get duplicates.
Run: python scripts/build_feeds.py
"""
import json, sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from common import ROOT, PODCASTS, POD_BY_NAME, audio_file, lesson_id, load_catalog, load_config, season_of

OUT = ROOT / 'docs' / 'feeds'
SPOTIFY = json.loads((ROOT / 'data' / 'spotify_episodes.json').read_text(encoding='utf-8'))
MIME = {'.mp3': 'audio/mpeg', '.m4a': 'audio/x-m4a', '.mp4': 'audio/mp4', '.aac': 'audio/aac', '.ogg': 'audio/ogg'}


def cdata(s):
    return '<![CDATA[' + s.replace(']]>', ']]]]><![CDATA[>') + ']]>'


def seconds(dur):
    p = [int(x) for x in dur.split(':')]
    return sum(v * 60 ** i for i, v in enumerate(reversed(p)))


def pub_date(row):
    old = SPOTIFY.get(row['כותרת מקורית'].strip())
    if old:
        return old['pubDate']
    d = datetime.strptime(row['תאריך'], '%d/%m/%Y').replace(hour=20, tzinfo=timezone.utc)
    return format_datetime(d, usegmt=True)


def guid(row, lid):
    old = SPOTIFY.get(row['כותרת מקורית'].strip())
    return old['guid'] if old else f'shiurim-{lid}'


def build(pod, rows, cfg):
    media, site = cfg['media_url'].rstrip('/') + '/', cfg['site_url'].rstrip('/') + '/'
    feed_url = f'{site}feeds/{pod["key"]}.xml'
    seasons = []  # season names in catalog order
    for r in rows:
        if season_of(r) not in seasons:
            seasons.append(season_of(r))
    numbered = len(seasons) > 1 or seasons[0] != ''
    counter = {}
    items, missing = [], []
    for r in rows:
        lid, s = lesson_id(r), season_of(r)
        f = audio_file(lid)
        if not f:
            missing.append(lid)
            continue
        counter[s] = counter.get(s, 0) + 1
        season_tags = (f'\n      <itunes:season>{seasons.index(s) + 1}</itunes:season>'
                       f'\n      <podcast:season name="{escape(s, {chr(34): "&quot;"})}">{seasons.index(s) + 1}</podcast:season>'
                       f'\n      <itunes:episode>{counter[s]}</itunes:episode>') if numbered else ''
        items.append(f'''    <item>
      <title>{cdata(r['כותרת חדשה'].strip())}</title>
      <description>{cdata(r['תיאור'].strip())}</description>
      <link>{site}#{lid}</link>
      <guid isPermaLink="false">{escape(guid(r, lid))}</guid>
      <pubDate>{pub_date(r)}</pubDate>
      <enclosure url="{media}audio/{lid}{f.suffix.lower()}" length="{f.stat().st_size}" type="{MIME.get(f.suffix.lower(), 'audio/mpeg')}"/>
      <itunes:duration>{seconds(r['אורך'])}</itunes:duration>
      <itunes:image href="{media}art/lessons/{lid}.jpg"/>
      <itunes:episodeType>full</itunes:episodeType>{season_tags}
      <itunes:explicit>false</itunes:explicit>
    </item>''')
    owner_email = f'\n      <itunes:email>{escape(cfg["owner_email"])}</itunes:email>' if cfg.get('owner_email') else ''
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{cdata(pod['name'])}</title>
    <description>{cdata(pod['about'])}</description>
    <link>{site}#p-{pod['key']}</link>
    <atom:link href="{feed_url}" rel="self" type="application/rss+xml"/>
    <language>he</language>
    <copyright>{cdata(cfg['owner_name'])}</copyright>
    <itunes:author>{cdata(cfg['owner_name'])}</itunes:author>
    <itunes:owner>
      <itunes:name>{cdata(cfg['owner_name'])}</itunes:name>{owner_email}
    </itunes:owner>
    <itunes:image href="{media}art/covers/{pod['key']}.jpg"/>
    <image><url>{media}art/covers/{pod['key']}.jpg</url><title>{cdata(pod['name'])}</title><link>{site}</link></image>
    <itunes:category text="Religion &amp; Spirituality"><itunes:category text="Judaism"/></itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <podcast:locked>no</podcast:locked>
{chr(10).join(reversed(items))}
  </channel>
</rss>
'''
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{pod["key"]}.xml').write_text(xml, encoding='utf-8')
    return len(items), missing


def main():
    cfg = load_config()
    rows = load_catalog()
    ok = True
    for pod in PODCASTS:
        n, missing = build(pod, [r for r in rows if POD_BY_NAME[r['פודקאסט'].strip()] is pod], cfg)
        print(f'{pod["key"]}: {n} episodes' + (f', MISSING AUDIO: {missing}' if missing else ''))
        ok = ok and not missing
    if 'EXAMPLE' in cfg['site_url'] + cfg['media_url'] or not cfg.get('owner_email'):
        print('note: data/config.json still has placeholder addresses or no owner email; feeds are drafts')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
