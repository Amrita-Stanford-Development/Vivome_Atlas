// The Pages Function that plays media with byte ranges
// (deploy/pages/media.js): ranges read like a browser sends them, the parts
// cut right, 206 answers capped, a whole-file request streamed in order,
// and anything else left to the static files.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { MAX_RANGE, createHandler, parseRange, partPath, partsFor } from '../../deploy/pages/media.js';

const PART = 1000;
const DATA = Uint8Array.from({ length: 9_500_000 }, (_, i) => (i * 7) % 251);
const MEDIA = {
  '/motion/film/vivome.mp4': {
    size: DATA.length, part: PART * 1000, parts: '/motion/film/parts/vivome.mp4.', type: 'video/mp4', sha256: 'abc',
  },
};
const media = MEDIA['/motion/film/vivome.mp4'];

function fakeEnv() {
  const asked = [];
  return {
    asked,
    ASSETS: {
      async fetch(request) {
        const path = new URL(request.url).pathname;
        asked.push(path);
        const m = /\.(\d{4})$/.exec(path);
        if (!m || !path.startsWith(media.parts)) return new Response(`static ${path}`, { status: 200 });
        const i = Number(m[1]);
        return new Response(DATA.slice(i * media.part, (i + 1) * media.part));
      },
    },
  };
}

const call = (path, init = {}) => {
  const env = fakeEnv();
  return createHandler(MEDIA)({ request: new Request(`https://site.dev${path}`, init), env }).then((r) => ({ r, env }));
};

test('ranges read the way browsers send them', () => {
  assert.deepEqual(parseRange('bytes=0-1', 10), [0, 1]);
  assert.deepEqual(parseRange('bytes=5-', 10), [5, 9]);
  assert.deepEqual(parseRange('bytes=-3', 10), [7, 9]);
  assert.deepEqual(parseRange('bytes=8-99', 10), [8, 9]);
  assert.equal(parseRange('bytes=10-', 10), 'unsatisfiable');
  assert.equal(parseRange(null, 10), null);
  assert.equal(parseRange('items=1-2', 10), null);
  assert.equal(parseRange('bytes=5-2', 10), null);
});

test('the parts that hold a range are cut at its two ends', () => {
  assert.deepEqual(partsFor(5, 25, 10), [{ index: 0, from: 5, to: 10 }, { index: 1, from: 0, to: 10 }, { index: 2, from: 0, to: 6 }]);
  assert.deepEqual(partsFor(10, 19, 10), [{ index: 1, from: 0, to: 10 }]);
  assert.equal(partPath(media, 3), '/motion/film/parts/vivome.mp4.0003');
});

test('a ranged request gets 206 with exactly its bytes, across parts', async () => {
  const { r } = await call('/motion/film/vivome.mp4', { headers: { Range: 'bytes=999990-2000009' } });
  assert.equal(r.status, 206);
  assert.equal(r.headers.get('content-range'), `bytes 999990-2000009/${DATA.length}`);
  assert.equal(r.headers.get('accept-ranges'), 'bytes');
  assert.equal(r.headers.get('content-type'), 'video/mp4');
  assert.deepEqual(new Uint8Array(await r.arrayBuffer()), DATA.slice(999990, 2000010));
});

test('an open-ended range is answered in a capped piece', async () => {
  const { r, env } = await call('/motion/film/vivome.mp4', { headers: { Range: 'bytes=0-' } });
  assert.equal(r.status, 206);
  assert.equal(r.headers.get('content-range'), `bytes 0-${MAX_RANGE - 1}/${DATA.length}`);
  assert.equal((await r.arrayBuffer()).byteLength, MAX_RANGE);
  assert.ok(env.asked.length <= Math.ceil(MAX_RANGE / media.part) + 1);
});

test('the last bytes, a range past the end, and HEAD', async () => {
  const tail = await call('/motion/film/vivome.mp4', { headers: { Range: 'bytes=-10' } });
  assert.deepEqual(new Uint8Array(await tail.r.arrayBuffer()), DATA.slice(-10));
  const past = await call('/motion/film/vivome.mp4', { headers: { Range: `bytes=${DATA.length}-` } });
  assert.equal(past.r.status, 416);
  assert.equal(past.r.headers.get('content-range'), `bytes */${DATA.length}`);
  const head = await call('/motion/film/vivome.mp4', { method: 'HEAD' });
  assert.equal(head.r.status, 200);
  assert.equal(head.r.headers.get('content-length'), String(DATA.length));
  assert.equal(head.env.asked.length, 0, 'HEAD reads no part');
});

test('a whole-file request streams every part in order', async () => {
  const { r } = await call('/motion/film/vivome.mp4');
  assert.equal(r.status, 200);
  assert.deepEqual(new Uint8Array(await r.arrayBuffer()), DATA);
});

test('any other file in the folder is the static file', async () => {
  const { r, env } = await call('/motion/film/poster.webp', { headers: { Range: 'bytes=0-1' } });
  assert.equal(await r.text(), 'static /motion/film/poster.webp');
  assert.deepEqual(env.asked, ['/motion/film/poster.webp']);
});
