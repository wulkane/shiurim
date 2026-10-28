// Cloudflare Worker that serves the audio and artwork stored in the R2 bucket (bound as MEDIA).
// Podcast apps need range requests (seeking, resuming), so those are answered with 206.
// Paste into the Cloudflare dashboard: Workers -> Create -> "Hello World" -> Edit code, then
// Settings -> Bindings -> add R2 bucket binding named MEDIA.

export default {
  async fetch(req, env) {
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405, headers: { allow: 'GET, HEAD' } });
    }
    const key = decodeURIComponent(new URL(req.url).pathname.slice(1));
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
