"""Uploads recordings, lesson images and covers to the R2 bucket with Wrangler.

Keys in the bucket: audio/<id>.<ext>, art/lessons/<id>.jpg, art/covers/<key>.jpg (the lesson id, not
the title, so public links never change). Files already uploaded with the same size are skipped,
tracked in data/uploaded.json, so it is safe to run again after adding a lesson.
Run: python scripts/upload_media.py
"""
import json, shutil, subprocess, sys

from common import ROOT, PODCASTS, audio_file, lesson_id, load_catalog

BUCKET = 'shiurim-media'
STATE = ROOT / 'data' / 'uploaded.json'
TYPES = {'.mp3': 'audio/mpeg', '.m4a': 'audio/x-m4a', '.mp4': 'audio/mp4', '.jpg': 'image/jpeg'}
NPX = shutil.which('npx.cmd') or shutil.which('npx')


def jobs():
    for r in load_catalog():
        lid = lesson_id(r)
        f = audio_file(lid)
        if f:
            yield f'audio/{lid}{f.suffix.lower()}', f
        img = ROOT / 'art' / 'lessons' / f'{lid}.jpg'
        if img.exists():
            yield f'art/lessons/{lid}.jpg', img
    for p in PODCASTS:
        cover = ROOT / 'art' / 'covers' / f'{p["key"]}.jpg'
        if cover.exists():
            yield f'art/covers/{p["key"]}.jpg', cover


def main():
    done = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    todo = [(k, f) for k, f in jobs() if done.get(k) != f.stat().st_size]
    print(f'{len(todo)} files to upload', flush=True)
    failed = []
    for i, (key, f) in enumerate(todo, 1):
        cmd = [NPX, '--yes', 'wrangler@latest', 'r2', 'object', 'put', f'{BUCKET}/{key}', '--remote',
               '--file', str(f), '--content-type', TYPES[f.suffix.lower()], '--cache-control', 'public, max-age=86400']
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            done[key] = f.stat().st_size
            STATE.write_text(json.dumps(done, indent=1), encoding='utf-8')
            print(f'{i}/{len(todo)} ok {key}', flush=True)
        else:
            failed.append(key)
            print(f'{i}/{len(todo)} FAILED {key}: {(res.stderr or res.stdout)[-300:]}', flush=True)
    print(f'done, {len(todo) - len(failed)} uploaded' + (f', failed: {failed}' if failed else ''))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
