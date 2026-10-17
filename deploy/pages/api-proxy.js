// The site's door to the labelling service: a Cloudflare Pages Function,
// copied to functions/api/[[path]].js by scripts/build_pages_site.py. The
// site's pages call their own /api/...; this forwards each request to the
// service on Cloud Run (env.SERVICE_URL) with the secret the service checks
// (env.SERVICE_SECRET, set as a Pages secret), so the service answers only
// through this site, and so only to visitors past the site's sign-in.
//
// The service reads an upload by its Content-Length, so a body goes on with
// that length (FixedLengthStream, a Workers stream) rather than in chunks.

export const SECRET_HEADER = 'X-VivOME-Proxy-Secret';

// What the service never needs to see: the visitor's sign-in cookie and
// token stay on this site.
const DROPPED = ['cookie', 'cf-access-jwt-assertion', 'host'];

const answer = (status, body) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});

export async function onRequest({ request, env, params }) {
  if (!env?.SERVICE_URL || !env?.SERVICE_SECRET) {
    return answer(503, {
      error: 'the labelling service is not connected to this site',
      reason: 'The site has no SERVICE_URL or SERVICE_SECRET set (docs/web/hosting.md).',
    });
  }
  const path = [].concat(params?.path ?? []).map(encodeURIComponent).join('/');
  const target = `${String(env.SERVICE_URL).replace(/\/+$/, '')}/api/${path}${new URL(request.url).search}`;
  const headers = new Headers(request.headers);
  for (const name of DROPPED) headers.delete(name);
  headers.set(SECRET_HEADER, env.SERVICE_SECRET);
  const init = { method: request.method, headers, redirect: 'manual' };
  if (request.body && !['GET', 'HEAD'].includes(request.method)) {
    const length = Number(request.headers.get('content-length'));
    if (request.headers.has('content-length') && Number.isInteger(length) && length >= 0) {
      const { readable, writable } = new FixedLengthStream(length);
      request.body.pipeTo(writable).catch(() => {});
      init.body = readable;
    } else {
      init.body = request.body; // no length given: the service turns it down itself
    }
  }
  let response;
  try {
    response = await fetch(target, init);
  } catch (err) {
    return answer(502, { error: 'the labelling service did not answer', reason: String(err?.message ?? err) });
  }
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers });
}
