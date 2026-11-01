"""Cleans the recordings in הקלטות/ (gentle noise reduction, low rumble filter, even loudness).

Originals are never touched: cleaned copies go to הקלטות/מנוקה/ under the same names.
Needs ffmpeg (winget install Gyan.FFmpeg). Run: python scripts/denoise_audio.py [part of a file name ...]
"""
import shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import AUDIO_DIR

OUT = AUDIO_DIR / 'מנוקה'
FILTER = 'highpass=f=80,afftdn=nr=10:nf=-40:tn=1,loudnorm=I=-16:TP=-1.5:LRA=11'


def ffmpeg():
    found = shutil.which('ffmpeg')
    if found:
        return found
    packages = Path.home() / 'AppData' / 'Local' / 'Microsoft' / 'WinGet' / 'Packages'
    return next(iter(packages.glob('Gyan.FFmpeg*/*/bin/ffmpeg.exe')), None)


def clean(src, exe):
    dst = OUT / src.name
    if dst.exists():
        return src.name, 'already done'
    tmp = dst.with_name(dst.stem + '.part' + dst.suffix)
    codec = 'libmp3lame' if src.suffix.lower() == '.mp3' else 'aac'
    res = subprocess.run([str(exe), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(src), '-af', FILTER,
                          '-c:a', codec, '-b:a', '128k', str(tmp)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if res.returncode:
        tmp.unlink(missing_ok=True)
        return src.name, 'FAILED: ' + res.stderr[-200:]
    tmp.rename(dst)
    return src.name, 'ok'


def main():
    exe = ffmpeg()
    if not exe:
        sys.exit('ffmpeg not found')
    OUT.mkdir(exist_ok=True)
    only = sys.argv[1:]
    files = [f for f in sorted([*AUDIO_DIR.glob('*.m4a'), *AUDIO_DIR.glob('*.mp3')]) if not only or any(o in f.name for o in only)]
    with ThreadPoolExecutor(3) as pool:
        for i, (name, status) in enumerate(pool.map(lambda f: clean(f, exe), files), 1):
            print(f'{i}/{len(files)} {status}  {name}', flush=True)


if __name__ == '__main__':
    main()
