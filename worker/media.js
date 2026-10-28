// Cloudflare Worker for the lessons:
//  - serves audio and artwork from the R2 bucket (bound as MEDIA), with range requests,
//    which podcast apps need for seeking and resuming;
//  - counts plays anonymously in the D1 database (bound as DB);
//  - answers the private stats page (docs/stats.html) at /stats/data and /stats/export.csv.
// The secret STATS_KEY protects the stats endpoints and salts the visitor hash.
// Deploy: cd worker && npx wrangler deploy

const SITE = 'https://wulkane.github.io';
const BOT = /bot|crawl|spider|validator|podbase|curl|wget|python|node-fetch|postman|headless|monitor/i;
const PLATFORMS = [
  ['Spotify', /spotify/i],
  ['Apple Podcasts', /podcasts\/|applecoremedia|itunes|apple podcasts/i],
  ['Pocket Casts', /pocket ?casts/i],
  ['Overcast', /overcast/i],
  ['Castbox', /castbox/i],
  ['Podcast Addict', /podcast ?addict/i],
  ['AntennaPod', /antennapod/i],
  ['Castro', /castro/i],
  ['YouTube', /youtube/i],
];

function platformOf(req) {
  const ref = req.headers.get('referer') || '';
  if (ref.startsWith(SITE)) return 'האתר';
  const ua = req.headers.get('user-agent') || '';
  for (const [name, re] of PLATFORMS) if (re.test(ua)) return name;
  return /mozilla/i.test(ua) ? 'דפדפן אחר' : 'אחר';
}

// A new play starts at the beginning of the file. Tiny probes ("bytes=0-1") and resumes in
// the middle of a file are not counted.
function isPlayStart(range) {
  if (!range) return true;
  const m = /^bytes=(\d+)-(\d*)$/.exec(range);
  if (!m || +m[1] !== 0) return false;
  return m[2] === '' || +m[2] >= 100000;
}

async function hash(text) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(d)].slice(0, 8).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function record(req, env, key) {
  try {
    const ua = req.headers.get('user-agent') || '';
    if (BOT.test(ua) || !isPlayStart(req.headers.get('range'))) return;
    const day = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Jerusalem' });
    const lesson = key.slice('audio/'.length).replace(/\.[^.]+$/, '');
    const visitor = await hash(`${req.headers.get('cf-connecting-ip') || ''}|${ua}|${day}|${(env.STATS_KEY || '').trim()}`);
    await env.DB.prepare(
      'INSERT INTO plays (day, lesson, platform, visitor, hits) VALUES (?1, ?2, ?3, ?4, 1) ' +
      'ON CONFLICT (day, lesson, platform, visitor) DO UPDATE SET hits = hits + 1'
    ).bind(day, lesson, platformOf(req), visitor).run();
  } catch (e) {
    // counting must never get in the way of playing
  }
}

// ---- stats endpoints (private) ----
const CORS = {
  'access-control-allow-origin': SITE,
  'access-control-allow-headers': 'authorization',
  'vary': 'origin',
};

function authorized(req, env) {
  const given = (req.headers.get('authorization') || '').replace(/^Bearer /, '');
  const want = (env.STATS_KEY || '').trim(); // a pasted secret may carry a trailing newline
  if (!want || given.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= given.charCodeAt(i) ^ want.charCodeAt(i);
  return diff === 0;
}

async function stats(req, env, url) {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
  if (!authorized(req, env)) return new Response('Unauthorized', { status: 401, headers: CORS });
  const days = Math.min(+url.searchParams.get('days') || 0, 3650);
  const since = days ? new Date(Date.now() - days * 864e5).toISOString().slice(0, 10) : '0000-00-00';
  const headers = { ...CORS, 'cache-control': 'no-store' };

  if (url.pathname === '/stats/export.csv') {
    const { results } = await env.DB.prepare(
      'SELECT day, lesson, platform, COUNT(*) AS listeners, SUM(hits) AS requests FROM plays ' +
      'WHERE day >= ?1 GROUP BY day, lesson, platform ORDER BY day, lesson'
    ).bind(since).all();
    const csv = ['day,lesson,platform,listeners,requests', ...results.map(r =>
      [r.day, r.lesson, r.platform, r.listeners, r.requests].join(','))].join('\n');
    return new Response('﻿' + csv, { headers: { ...headers, 'content-type': 'text/csv; charset=utf-8' } });
  }
  const [byLesson, byDay] = await Promise.all([
    env.DB.prepare('SELECT lesson, platform, COUNT(*) AS listeners FROM plays WHERE day >= ?1 GROUP BY lesson, platform').bind(since).all(),
    env.DB.prepare('SELECT day, COUNT(*) AS listeners FROM plays WHERE day >= ?1 GROUP BY day ORDER BY day').bind(since).all(),
  ]);
  return Response.json({ byLesson: byLesson.results, byDay: byDay.results }, { headers });
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (url.pathname.startsWith('/stats/')) return stats(req, env, url);

    if (req.method !== 'GET' && req.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405, headers: { allow: 'GET, HEAD' } });
    }
    const key = decodeURIComponent(url.pathname.slice(1));
    if (!key) return new Response('Not found', { status: 404 });

    const obj = req.method === 'HEAD'
      ? await env.MEDIA.head(key)
      : await env.MEDIA.get(key, { range: req.headers, onlyIf: req.headers });
    if (!obj) return new Response('Not found', { status: 404 });

    const headers = new Headers();
    obj.writeHttpMetadata(headers);
    headers.set('etag', obj.httpEtag);
    headers.set('accept-ranges', 'bytes');
    headers.set('access-control-allow-origin', '*');
    headers.set('cache-control', 'public, max-age=86400');

    if (req.method === 'HEAD') {
      headers.set('content-length', String(obj.size));
      return new Response(null, { headers });
    }
    if (!('body' in obj)) return new Response(null, { status: 304, headers }); // If-None-Match matched

    if (key.startsWith('audio/')) ctx.waitUntil(record(req, env, key));

    const r = obj.range;
    if (r && req.headers.has('range')) {
      // R2 reports every key of the range object, some as undefined, so test the values (not 'in')
      const start = r.suffix !== undefined ? obj.size - r.suffix : (r.offset ?? 0);
      const end = r.suffix !== undefined ? obj.size - 1 : start + (r.length ?? obj.size - start) - 1;
      headers.set('content-range', `bytes ${start}-${end}/${obj.size}`);
      headers.set('content-length', String(end - start + 1));
      return new Response(obj.body, { status: 206, headers });
    }
    headers.set('content-length', String(obj.size));
    return new Response(obj.body, { headers });
  },
};
