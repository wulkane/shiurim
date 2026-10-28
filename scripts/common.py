"""Shared helpers for the build scripts: paths, catalog loading, lesson ids and podcast settings."""
import csv, hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'קטלוג שיעורים.csv'
CONFIG = ROOT / 'data' / 'config.json'
AUDIO_DIR = ROOT / 'הקלטות'

# Podcast order (as on the site), file key, artwork icon, description and directory links.
# A missing link shows as "בקרוב" on the site.
PODCASTS = [
    {
        'name': 'פשט ועומק בפרשת השבוע', 'key': 'parasha', 'icon': 0,
        'about': 'עיון בפרשת השבוע מתוך פשט הפסוקים, דברי חז"ל והמפרשים, והמסרים העולים מהם לחיינו',
        'links': {'spotify': 'https://open.spotify.com/show/7KKnHKn48V0iwPmTfMdcry', 'apple': None, 'youtube': None},
    },
    {
        'name': 'אמת ואמונה', 'key': 'emuna', 'icon': 1,
        'about': 'עיונים ומחשבות על נושאי יסוד באמונה היהודית',
        'links': {'spotify': 'https://podcasters.spotify.com/pod/show/-25869', 'apple': None, 'youtube': None},
    },
    {
        'name': 'מועדי ישראל', 'key': 'moadim', 'icon': 2,
        'about': 'מהותם של חגי ישראל ומועדיו לאור פסוקי התורה ודברי חז"ל',
        'topics': ['ראש השנה', 'יום כיפור', 'סוכות', 'חנוכה', 'פורים', 'פסח', 'יום העצמאות', 'בין המצרים'],
        'links': {'spotify': 'https://open.spotify.com/show/4A5zOZawW3O0bZux3pJgY6', 'apple': None, 'youtube': None},
    },
]
POD_BY_NAME = {p['name']: p for p in PODCASTS}


def load_catalog():
    return list(csv.DictReader(open(CATALOG, encoding='utf-8-sig')))


def lesson_id(row):
    """Stable id from the original title, so links survive reordering, title edits and moving the audio."""
    return 'l' + hashlib.md5(row['כותרת מקורית'].strip().encode()).hexdigest()[:6]


def season_of(row):
    """Series lessons ('המדינה היהודית (6)- גיור') belong to the series named in the title; others to the עונה column."""
    m = re.match(r'(.+?)\s*\(\d+\)', row['כותרת חדשה'].strip())
    return m.group(1) if m else row['עונה'].strip()


def load_config():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


AUDIO_NAMES = ROOT / 'data' / 'audio_files.json'


def audio_names():
    """lesson id -> local file name in הקלטות/ (files are named after the lesson title)."""
    return json.loads(AUDIO_NAMES.read_text(encoding='utf-8')) if AUDIO_NAMES.exists() else {}


def audio_file(lid):
    """The local backup file for a lesson, or None. Falls back to a file still named by id."""
    name = audio_names().get(lid)
    if name and (AUDIO_DIR / name).exists():
        return AUDIO_DIR / name
    return next(AUDIO_DIR.glob(lid + '.*'), None)
