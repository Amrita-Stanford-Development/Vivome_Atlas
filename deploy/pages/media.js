// Media files the site plays (the Motion page's film), served with byte
// ranges: a Cloudflare Pages Function, copied by scripts/build_pages_site.py
// to the media file's own path. Pages answers a Range request for a static
// file with the whole file (200), and Safari and every iPhone browser will
// not play a video without 206 answers, so the build stores each media file
// as parts of PART bytes and this answers from the parts.
//
// The build replaces the MEDIA line with each file's size, part size, part
// path, type and sha256. A ranged answer is at most MAX_RANGE bytes, which
// an open-ended range (bytes=N-) allows; a whole-file request streams the
// parts in order.

export const MEDIA = {};

export const MAX_RANGE = 4 * 1024 * 1024;

// The first range of a Range header as [start, end], both inclusive; null
// for no header or one this does not read (the whole file is sent);
// 'unsatisfiable' when it starts past the end.
export function parseRange(header, size) {
  const m = /^bytes=(\d*)-(\d*)/.exec(String(header ?? '').trim());
  if (!m || (m[1] === '' && m[2] === '')) return null;
  if (m[1] === '') {
    const suffix = Number(m[2]);
    if (suffix === 0) return 'unsatisfiable';
    return [Math.max(0, size - suffix), size - 1];
  }
  const start = Number(m[1]);
  if (start >= size) return 'unsatisfiable';
  const end = m[2] === '' ? size - 1 : Math.min(Number(m[2]), size - 1);
  return end < start ? null : [start, end];
}

// The parts that hold bytes start..end, with where to cut the first and last.
export function partsFor(start, end, part) {
  const first = Math.floor(start / part);
  const last = Math.floor(end / part);
  const out = [];
  for (let i = first; i <= last; i += 1) {
    const from = i === first ? start - i * part : 0;
    const to = i === last ? end - i * part + 1 : part;
    out.push({ index: i, from, to });
  }
  return out;
}

export const partPath = (media, index) => `${media.parts}${String(index).padStart(4, '0')}`;

export function createHandler(table) {
  return async function onRequest({ request, env }) {
    const url = new URL(request.url);
    const media = table[url.pathname];
    if (!media || !['GET', 'HEAD'].includes(request.method)) return env.ASSETS.fetch(request);
    const part = (i) => env.ASSETS.fetch(new Request(new URL(partPath(media, i), url)));
    const headers = new Headers({
      'content-type': media.type,
      'accept-ranges': 'bytes',
      etag: `"${media.sha256}"`,
      'cache-control': 'public, max-age=3600',
    });
    const range = parseRange(request.headers.get('range'), media.size);
    if (range === 'unsatisfiable') {
      headers.set('content-range', `bytes */${media.size}`);
      return new Response(null, { status: 416, headers });
    }
    if (range === null) {
      // A streamed body carries no length of its own; HEAD states it.
      if (request.method === 'HEAD') {
        headers.set('content-length', String(media.size));
        return new Response(null, { status: 200, headers });
      }
      const count = Math.ceil(media.size / media.part);
      let next = 0;
      const body = new ReadableStream({
        async pull(controller) {
          if (next >= count) return controller.close();
          const response = await part(next);
          next += 1;
          controller.enqueue(new Uint8Array(await response.arrayBuffer()));
        },
      });
      return new Response(body, { status: 200, headers });
    }
    const [start] = range;
    const end = Math.min(range[1], start + MAX_RANGE - 1);
    headers.set('content-range', `bytes ${start}-${end}/${media.size}`);
    headers.set('content-length', String(end - start + 1));
    if (request.method === 'HEAD') return new Response(null, { status: 206, headers });
    const body = new Uint8Array(end - start + 1);
    let at = 0;
    for (const { index, from, to } of partsFor(start, end, media.part)) {
      const response = await part(index);
      if (!response.ok) return new Response('Media part missing', { status: 502 });
      const bytes = new Uint8Array(await response.arrayBuffer());
      body.set(bytes.subarray(from, to), at);
      at += to - from;
    }
    return new Response(body, { status: 206, headers });
  };
}

export const onRequest = createHandler(MEDIA);
