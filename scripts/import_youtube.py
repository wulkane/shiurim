"""Reads each lesson's public view count from YouTube and stores it in the stats database.

YouTube plays the audio from its own copy, so those views never reach our server. The counts are
taken from the public video pages (the videos found by scripts/collect_links.py). Run it again
whenever you want fresh numbers: it replaces the old YouTube row of every lesson.
Run: python scripts/import_youtube.py
"""
import datetime, json, re, shutil, subprocess, sys

from common import ROOT
from collect_links import get

SQL = ROOT / 'worker' / '.import_youtube.sql'


def views(url):
    video = re.search(r'v=([\w-]{11})', url).group(1)
    page = get(f'https://www.youtube.com/watch?v={video}')[0]
    at = page.find(f'"videoDetails":{{"videoId":"{video}"')
    m = re.search(r'"viewCount":"(\d+)"', page[at:at + 6000]) if at >= 0 else None
    return int(m.group(1)) if m else None


def main():
    links = json.loads((ROOT / 'data' / 'episode_links.json').read_text(encoding='utf-8'))
    today = datetime.date.today().isoformat()
    values, unreadable = [], []
    for lid, l in links.items():
        if 'youtube' not in l:
            continue
        n = views(l['youtube'])
        if n is None:
            unreadable.append(lid)
        else:
            values.append(f"('{lid}', 'YouTube', {n}, '{today}')")
    if unreadable:
        sys.exit(f'could not read the views of {unreadable}, nothing imported')
    SQL.write_text("DELETE FROM imported WHERE platform = 'YouTube';\n"
                   "INSERT INTO imported (lesson, platform, plays, as_of) VALUES\n" + ',\n'.join(values) + ';\n', encoding='utf-8')
    npx = shutil.which('npx.cmd') or shutil.which('npx')
    res = subprocess.run([npx, '--yes', 'wrangler@latest', 'd1', 'execute', 'shiurim-stats', '--remote', f'--file={SQL}'],
                         cwd=ROOT / 'worker', capture_output=True, text=True, encoding='utf-8', errors='replace')
    SQL.unlink(missing_ok=True)
    if res.returncode:
        sys.exit(res.stderr[-600:] or res.stdout[-600:])
    total = sum(int(v.split(', ')[2]) for v in values)
    print(f'imported {len(values)} lessons, {total} views, as of {today}')


if __name__ == '__main__':
    main()
