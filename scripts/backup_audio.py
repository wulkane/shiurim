"""Downloads every recording in the catalog to the local folder הקלטות/.

Each file is saved under the lesson id, keeping the original extension; run name_audio.py
afterwards to rename them to the lesson titles. Lessons already downloaded are skipped.
Run: python scripts/backup_audio.py
"""
import sys, urllib.parse, urllib.request
from pathlib import Path

from common import AUDIO_DIR as OUT, audio_file, lesson_id, load_catalog


def ext_of(url):
    # anchor links wrap the real file url; its extension is at the very end
    path = urllib.parse.unquote(url).split('?')[0]
    return Path(path).suffix.lower() or '.mp3'


def main():
    OUT.mkdir(exist_ok=True)
    rows = load_catalog()
    failed = []
    for i, r in enumerate(rows, 1):
        url = r['קישור לקובץ']
        if audio_file(lesson_id(r)):  # already downloaded (possibly renamed to its title)
            continue
        dest = OUT / (lesson_id(r) + ext_of(url))
        tmp = dest.with_suffix(dest.suffix + '.part')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, 'wb') as f:
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
            tmp.replace(dest)
            print(f'{i}/{len(rows)} {dest.name} {dest.stat().st_size // 1_000_000}MB', flush=True)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            failed.append(dest.name)
            print(f'{i}/{len(rows)} FAILED {dest.name}: {e}', flush=True)
    print(f'done, {len(rows) - len(failed)}/{len(rows)} ok' + (f', failed: {failed}' if failed else ''))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
