"""Imports the per-episode totals exported from Spotify for Creators into the stats database.

Export: creators.spotify.com -> the show -> Analytics -> plays and downloads per episode, since
published (CSV with the columns: Episode name, Publish date, Plays & downloads).
Rows are matched to lessons by the original episode title. Importing again replaces the old
Spotify numbers, so run it with each new export.
Run: python scripts/import_spotify.py <export.csv>
"""
import csv, datetime, subprocess, sys, shutil
from pathlib import Path

from common import ROOT, load_catalog, lesson_id

SQL = ROOT / 'worker' / '.import.sql'


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    export = Path(sys.argv[1])
    as_of = datetime.date.fromtimestamp(export.stat().st_mtime).isoformat()
    ids = {r['כותרת מקורית'].strip(): lesson_id(r) for r in load_catalog()}
    rows = list(csv.DictReader(open(export, encoding='utf-8-sig')))
    values, unmatched = [], []
    for r in rows:
        name, plays = r['Episode name'].strip(), int(r['Plays & downloads'] or 0)
        if name in ids:
            values.append(f"('{ids[name]}', 'Spotify', {plays}, '{as_of}')")
        else:
            unmatched.append(name)
    if unmatched:
        sys.exit(f'no lesson matches these episodes, nothing imported: {unmatched}')
    SQL.write_text("DELETE FROM imported WHERE platform = 'Spotify';\n"
                   "INSERT INTO imported (lesson, platform, plays, as_of) VALUES\n" + ',\n'.join(values) + ';\n',
                   encoding='utf-8')
    npx = shutil.which('npx.cmd') or shutil.which('npx')
    res = subprocess.run([npx, '--yes', 'wrangler@latest', 'd1', 'execute', 'shiurim-stats', '--remote', f'--file={SQL}'],
                         cwd=ROOT / 'worker', capture_output=True, text=True, encoding='utf-8', errors='replace')
    SQL.unlink(missing_ok=True)
    if res.returncode:
        sys.exit(res.stderr[-600:] or res.stdout[-600:])
    print(f'imported {len(values)} episodes, {sum(int(v.split(", ")[2]) for v in values)} plays, as of {as_of}')


if __name__ == '__main__':
    main()
