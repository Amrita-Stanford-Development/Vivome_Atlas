// The site's door to the labelling service (deploy/pages/api-proxy.js, a
// Cloudflare Pages Function), run in Node with stand-ins for the Workers
// runtime: it forwards /api/... to the service with the secret, keeps the
// visitor's sign-in to itself, passes an upload on with its length, and
// says plainly when the service is missing or silent.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { SECRET_HEADER, onRequest } from '../../deploy/pages/api-proxy.js';

const ENV = { SERVICE_URL: 'https://service.example/', SERVICE_SECRET: 's3cret' };

// The Workers stream that sends a body with a known length; here an
// identity stream that remembers the length it was given.
const lengths = [];
globalThis.FixedLengthStream = class extends TransformStream {
  constructor(length) {
    super();
    lengths.push(length);
  }
};

function fakeFetch(reply = () => new Response('{"status":"ready"}', { status: 200, headers: { 'Retry-After': '12' } })) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init, body: init.body ? await new Response(init.body).text() : null });
    return reply(url, init);
  };
  return calls;
}

test('a status request goes to the service, with the secret and without the sign-in', async () => {
  const calls = fakeFetch();
  const request = new Request('https://vivome-atlas.pages.dev/api/status?x=1', {
    headers: { Cookie: 'CF_Authorization=abc', 'Cf-Access-Jwt-Assertion': 'jwt', Origin: 'https://vivome-atlas.pages.dev' },
  });
  const response = await onRequest({ request, env: ENV, params: { path: ['status'] } });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://service.example/api/status?x=1');
  const headers = calls[0].init.headers;
  assert.equal(headers.get(SECRET_HEADER), 's3cret');
  assert.equal(headers.get('cookie'), null, 'the sign-in cookie stays on the site');
  assert.equal(headers.get('cf-access-jwt-assertion'), null);
  assert.equal(headers.get('origin'), 'https://vivome-atlas.pages.dev');
  assert.equal(calls[0].init.body, undefined);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('retry-after'), '12', 'the service’s headers come back as they were');
  assert.deepEqual(await response.json(), { status: 'ready' });
});

test('an upload goes on with its length, so the service can read it', async () => {
  const calls = fakeFetch(() => new Response('{}', { status: 200 }));
  const form = 'x'.repeat(1000);
  const request = new Request('https://vivome-atlas.pages.dev/api/project', {
    method: 'POST', body: form, headers: { 'Content-Type': 'multipart/form-data; boundary=b', 'Content-Length': '1000' },
  });
  lengths.length = 0;
  await onRequest({ request, env: ENV, params: { path: ['project'] } });
  assert.deepEqual(lengths, [1000], 'a fixed-length stream of the upload’s own length');
  assert.equal(calls[0].url, 'https://service.example/api/project');
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(calls[0].body, form, 'every byte arrives');
  assert.equal(calls[0].init.headers.get('content-type'), 'multipart/form-data; boundary=b');
});

test('path parts are passed on safely', async () => {
  const calls = fakeFetch();
  await onRequest({
    request: new Request('https://vivome-atlas.pages.dev/api/a%2Fb/c'), env: ENV, params: { path: ['a/b', 'c'] },
  });
  assert.equal(calls[0].url, 'https://service.example/api/a%2Fb/c');
});

test('without its settings, or without an answer, the door says so plainly', async () => {
  fakeFetch();
  for (const env of [{}, { SERVICE_URL: ENV.SERVICE_URL }, { SERVICE_SECRET: 's' }]) {
    const response = await onRequest({ request: new Request('https://x/api/status'), env, params: { path: ['status'] } });
    assert.equal(response.status, 503);
    assert.match((await response.json()).error, /not connected/);
  }
  globalThis.fetch = async () => { throw new TypeError('network down'); };
  const response = await onRequest({ request: new Request('https://x/api/status'), env: ENV, params: { path: ['status'] } });
  assert.equal(response.status, 502);
  assert.match((await response.json()).reason, /network down/);
});

test('the secret header is the one the service checks', () => {
  const config = readFileSync(new URL('../../service/config.py', import.meta.url), 'utf8');
  assert.match(config, new RegExp(`PROXY_SECRET_HEADER = "${SECRET_HEADER}"`));
  const check = readFileSync(new URL('../../deploy/huggingface/check_space.py', import.meta.url), 'utf8');
  assert.match(check, new RegExp(`SECRET_HEADER = "${SECRET_HEADER}"`));
});

test('who the visitor is and where they are stay on the site too', async () => {
  const calls = fakeFetch();
  const request = new Request('https://vivome-atlas.pages.dev/api/status', {
    headers: {
      'Cf-Access-Authenticated-User-Email': 'visitor@example.org', 'Cf-Access-Client-Id': 'id',
      'CF-Connecting-IP': '203.0.113.7', 'True-Client-IP': '203.0.113.7', 'X-Forwarded-For': '203.0.113.7',
      'X-Real-IP': '203.0.113.7', Origin: 'https://vivome-atlas.pages.dev',
    },
  });
  await onRequest({ request, env: ENV, params: { path: ['status'] } });
  const headers = calls[0].init.headers;
  for (const name of ['cf-access-authenticated-user-email', 'cf-access-client-id', 'cf-connecting-ip', 'true-client-ip',
    'x-forwarded-for', 'x-real-ip']) {
    assert.equal(headers.get(name), null, name);
  }
  assert.equal(headers.get('origin'), 'https://vivome-atlas.pages.dev');
});
