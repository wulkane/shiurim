"""Renames the recordings in הקלטות/ to the lesson titles shown on the site, and records the
names in data/audio_files.json. Safe to run again after editing titles in the catalog.
The media host keeps using the lesson id (audio/<id>.<ext>), so public links never change.
Run: python scripts/name_audio.py
"""
import json, re

from common import AUDIO_DIR, AUDIO_NAMES, audio_file, lesson_id, load_catalog


def safe_name(title):
    """Windows-safe file name: quotes become gershayim, other forbidden characters are dropped."""
    title = title.replace('"', '״').replace('/', '-')
    return re.sub(r'[<>:\\|?*]', '', title).strip(' .')


def main():
    names, renamed = {}, 0
    for r in load_catalog():
        lid = lesson_id(r)
        f = audio_file(lid)
        if not f:
            print('missing audio for', lid)
            continue
        new = AUDIO_DIR / (safe_name(r['כותרת חדשה'].strip()) + f.suffix)
        if new.exists() and new != f:
            new = new.with_name(f'{new.stem} ({lid}){new.suffix}')  # two lessons with the same title
        if new != f:
            f.rename(new)
            renamed += 1
        names[lid] = new.name
    AUDIO_NAMES.write_text(json.dumps(names, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{renamed} renamed, {len(names)} recorded in {AUDIO_NAMES.name}')


if __name__ == '__main__':
    main()
