"""Finds each lesson's own page on the podcast platforms and writes data/episode_links.json.

The site shows these under every lesson; a lesson without a link there opens the podcast's page instead.
Pocket Casts and YouTube are read from their public pages. Spotify needs a free developer key
(data/spotify_api.json: {"client_id": "...", "client_secret": "..."}, not committed).
Lessons are matched to platform episodes by title. Run it again after new lessons were published
(a platform lists a new episode a few hours after the feed changes), then: python scripts/build_site.py
Run: python scripts/collect_links.py
"""
import base64, gzip, json, re, sys, urllib.error, urllib.parse, urllib.request

from common import ROOT, PODCASTS, POD_BY_NAME, lesson_id, load_catalog

OUT = ROOT / 'data' / 'episode_links.json'
SPOTIFY_KEY = ROOT / 'data' / 'spotify_api.json'
UA = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'he', 'Accept-Encoding': 'gzip'}


def get(url, headers=None, data=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})}, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            body = gzip.decompress(body)
        return body.decode('utf-8'), r.geturl()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def redirect_target(url):
    """Where a short link points, without opening the page behind it."""
    try:
        urllib.request.build_opener(_NoRedirect).open(urllib.request.Request(url, headers=UA), timeout=30)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return e.headers['Location']
        raise
    raise RuntimeError(f'{url} did not redirect')


def norm(title):
    """Titles differ between platforms in quote marks and spacing only."""
    t = re.sub(r'[׳״"\'`‘’“”]', '', title)
    return re.sub(r'\s+', ' ', t).strip()


def pocketcasts(pod):
    short = pod['links'].get('pocketcasts')
    if not short:
        return {}
    uuid = redirect_target(short).rstrip('/').rsplit('/', 1)[-1]
    data = json.loads(get(f'https://podcast-api.pocketcasts.com/podcast/full/{uuid}')[0])
    return {norm(e['title']): f'https://pca.st/episode/{e["uuid"]}' for e in data['podcast']['episodes']}


def youtube(pod):
    url = pod['links'].get('youtube')
    if not url:
        return {}
    page = get(url)[0]
    initial = json.loads(re.search(r'var ytInitialData = (\{.*?\});</script>', page, re.S).group(1))
    found = {}

    def walk(node):
        if isinstance(node, dict):
            r = node.get('lockupViewModel')
            if r and r.get('contentId'):
                title = r['metadata']['lockupMetadataViewModel']['title']['content']
                found[norm(title)] = f'https://www.youtube.com/watch?v={r["contentId"]}&list={urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["list"][0]}'
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(initial)
    return found


def spotify(pod):
    url = pod['links'].get('spotify')
    if not url or not SPOTIFY_KEY.exists():
        return {}
    key = json.loads(SPOTIFY_KEY.read_text(encoding='utf-8'))
    basic = base64.b64encode(f'{key["client_id"]}:{key["client_secret"]}'.encode()).decode()
    token = json.loads(get('https://accounts.spotify.com/api/token', {'Authorization': 'Basic ' + basic},
                           b'grant_type=client_credentials')[0])['access_token']
    show = url.rstrip('/').rsplit('/', 1)[-1].split('?')[0]
    found, nxt = {}, f'https://api.spotify.com/v1/shows/{show}/episodes?limit=50&market=IL'
    while nxt:
        page = json.loads(get(nxt, {'Authorization': 'Bearer ' + token})[0])
        for e in page['items']:
            found[norm(e['name'])] = e['external_urls']['spotify']
        nxt = page.get('next')
    return found


def main():
    links = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    rows = load_catalog()
    for pod in PODCASTS:
        mine = [r for r in rows if POD_BY_NAME[r['פודקאסט'].strip()] is pod]
        for name, fetch in (('pocketcasts', pocketcasts), ('youtube', youtube), ('spotify', spotify)):
            try:
                found = fetch(pod)
            except Exception as e:
                print(f'{pod["key"]} {name}: failed ({e})')
                continue
            hits = 0
            for r in mine:
                url = found.get(norm(r['כותרת חדשה']))
                if url:
                    links.setdefault(lesson_id(r), {})[name] = url
                    hits += 1
            print(f'{pod["key"]} {name}: {hits}/{len(mine)} lessons matched' + ('' if found else ' (nothing found)'))
    OUT.write_text(json.dumps(links, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
