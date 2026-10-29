// Helpers for publishing a lesson: the catalog CSV, the podcast feeds and the site data are edited
// in the GitHub repo exactly as scripts/build_feeds.py and scripts/build_site.py would write them.

export const PODCASTS = {
  parasha: 'פשט ועומק בפרשת השבוע',
  emuna: 'אמת ואמונה',
  moadim: 'מועדי ישראל',
};
export const CATALOG_PATH = 'קטלוג שיעורים.csv';

// MD5 of the original title gives the lesson id, the same as lesson_id() in scripts/common.py
export function md5hex(str) {
  const bytes = new TextEncoder().encode(str);
  const K = new Uint32Array(64);
  for (let i = 0; i < 64; i++) K[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32) >>> 0;
  const S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
  const n = bytes.length, padLen = (((n + 8) >> 6) + 1) << 6;
  const buf = new Uint8Array(padLen);
  buf.set(bytes);
  buf[n] = 0x80;
  const dv = new DataView(buf.buffer);
  dv.setUint32(padLen - 8, (n * 8) >>> 0, true);
  dv.setUint32(padLen - 4, Math.floor((n * 8) / 2 ** 32), true);
  let a0 = 0x67452301, b0 = 0xefcdab89, c0 = 0x98badcfe, d0 = 0x10325476;
  for (let off = 0; off < padLen; off += 64) {
    const M = new Uint32Array(16);
    for (let i = 0; i < 16; i++) M[i] = dv.getUint32(off + i * 4, true);
    let A = a0, B = b0, C = c0, D = d0;
    for (let i = 0; i < 64; i++) {
      let F, g;
      if (i < 16) { F = (B & C) | (~B & D); g = i; }
      else if (i < 32) { F = (D & B) | (~D & C); g = (5 * i + 1) % 16; }
      else if (i < 48) { F = B ^ C ^ D; g = (3 * i + 5) % 16; }
      else { F = C ^ (B | ~D); g = (7 * i) % 16; }
      F = (F + A + K[i] + M[g]) >>> 0;
      A = D; D = C; C = B;
      const s = S[(i >> 4) * 4 + (i % 4)];
      B = (B + ((F << s) | (F >>> (32 - s)))) >>> 0;
    }
    a0 = (a0 + A) >>> 0; b0 = (b0 + B) >>> 0; c0 = (c0 + C) >>> 0; d0 = (d0 + D) >>> 0;
  }
  const out = new DataView(new ArrayBuffer(16));
  [a0, b0, c0, d0].forEach((v, i) => out.setUint32(i * 4, v, true));
  return [...new Uint8Array(out.buffer)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export const lessonId = originalTitle => 'l' + md5hex(originalTitle.trim()).slice(0, 6);

// a series lesson ("תפילה (2)- ...") belongs to the series named in its title, as season_of() in common.py
export function seasonOf(title, seasonColumn) {
  const m = title.trim().match(/^(.+?)\s*\(\d+\)/);
  return m ? m[1] : seasonColumn.trim();
}

// ---- CSV: rows keep their offsets so a new row can be spliced in without touching the others ----
export function parseCsv(text) {
  const rows = [];
  let fields = [], field = '', quoted = false, start = text.charCodeAt(0) === 0xfeff ? 1 : 0, i = start;
  const endRow = next => { fields.push(field); rows.push({ fields, start, end: next }); fields = []; field = ''; start = next; };
  for (; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else quoted = false; }
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { fields.push(field); field = ''; }
    else if (c === '\r' || c === '\n') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      endRow(i + 1);
    } else field += c;
  }
  if (start < text.length) endRow(text.length);
  return rows;
}

export function csvLine(fields, eol) {
  return fields.map(f => /[",\r\n]/.test(f) ? '"' + f.replace(/"/g, '""') + '"' : f).join(',') + eol;
}

// ---- feed and site ----
const cdata = s => '<![CDATA[' + s.replace(/\]\]>/g, ']]]]><![CDATA[>') + ']]>';
const xmlAttr = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
export const MIME = { '.mp3': 'audio/mpeg', '.m4a': 'audio/x-m4a' };

export function feedItem({ lesson, site, media, seasonIndex, episode, numbered }) {
  const { id, title, desc, pubDate, ext, size, seconds, season } = lesson;
  const seasonTags = numbered
    ? `\n      <itunes:season>${seasonIndex}</itunes:season>`
      + `\n      <podcast:season name="${xmlAttr(season)}">${seasonIndex}</podcast:season>`
      + `\n      <itunes:episode>${episode}</itunes:episode>`
    : '';
  return `    <item>
      <title>${cdata(title)}</title>
      <description>${cdata(desc)}</description>
      <link>${site}#${id}</link>
      <guid isPermaLink="false">shiurim-${id}</guid>
      <pubDate>${pubDate}</pubDate>
      <enclosure url="${media}audio/${id}${ext}" length="${size}" type="${MIME[ext]}"/>
      <itunes:duration>${seconds}</itunes:duration>
      <itunes:episodeType>full</itunes:episodeType>${seasonTags}
      <itunes:explicit>false</itunes:explicit>
    </item>
`;
}

export const hms = s => [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map(v => String(v).padStart(2, '0')).join(':');

// ---- GitHub contents API ----
const b64decode = s => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, '')), c => c.charCodeAt(0)));
function b64encode(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

export class Repo {
  constructor(env) {
    this.base = `https://api.github.com/repos/${env.GITHUB_REPO}/contents/`;
    this.headers = {
      authorization: `Bearer ${env.GITHUB_TOKEN.trim()}`,
      accept: 'application/vnd.github+json',
      'user-agent': 'shiurim-bot',
    };
  }

  url(path) { return this.base + path.split('/').map(encodeURIComponent).join('/'); }

  async read(path) {
    const r = await fetch(this.url(path) + '?ref=main', { headers: this.headers });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error(`GitHub read ${path}: ${r.status}`);
    const j = await r.json();
    return { text: b64decode(j.content), sha: j.sha };
  }

  async write(path, text, sha, message) {
    const r = await fetch(this.url(path), {
      method: 'PUT',
      headers: this.headers,
      body: JSON.stringify({ message, content: b64encode(text), sha, branch: 'main' }),
    });
    if (!r.ok) throw new Error(`GitHub write ${path}: ${r.status} ${(await r.text()).slice(0, 200)}`);
  }
}
