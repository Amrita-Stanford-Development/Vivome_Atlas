// Talking to the projection service (web/js/atlas/service-client.js), with a
// fake transport: ready, busy, refused, unreachable and not ready, the
// timeout and cancelling, the remembered address, and what the visitor is
// told.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import {
  BUSY_RETRY_SECONDS, DEFAULT_SERVICE_URL, SERVICE_KEY, ServiceError, browserTransport, createServiceClient,
  explainFailure, parseRetryAfter, rememberServiceUrl, serviceUrlFrom,
} from '../js/atlas/service-client.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const workflow = JSON.parse(read('data/workflow.json'));
const OWN = 'http://127.0.0.1:8001';

// A transport that answers with `reply` (or calls it with the request) and
// records what it was asked.
function fake(reply) {
  const calls = [];
  const transport = async (request) => {
    calls.push(request);
    const r = typeof reply === 'function' ? await reply(request) : reply;
    return { status: r.status, headers: r.headers ?? {}, body: typeof r.body === 'string' ? r.body : JSON.stringify(r.body) };
  };
  return { calls, client: createServiceClient({ transport }) };
}

const READY = {
  status: 'ready', atlas_version: '0.6.0', model_version: 'v4.1 (...)', pipeline_version: 'v4.1',
  limits: { max_cells: 2000, max_upload_mb: 200.0, concurrent_projections: 1 },
};
const BUSY = {
  error: 'the service is busy with another upload',
  reason: 'It projects 1 at a time. Try again in about 30 seconds.',
};
const TOO_MANY = {
  error: 'the matrix has 2,500 cells; this service projects at most 2,000 per upload',
  reason: 'Split the cells at random into uploads of at most that many, so each is still a mix of cell types, '
    + 'or run the service yourself with VIVOME_MAX_UPLOAD_CELLS raised.',
};

async function failure(promise) {
  try {
    await promise;
  } catch (err) {
    assert.ok(err instanceof ServiceError, `a ServiceError, not ${err}`);
    return err;
  }
  assert.fail('expected a failure');
}

test('the default address is the live service the workflow data records', () => {
  assert.equal(DEFAULT_SERVICE_URL, workflow.service.url);
  // scripts/build_workflow.py reads it from this exact line.
  const src = read('js/atlas/service-client.js');
  assert.equal(src.match(/DEFAULT_SERVICE_URL = '([^']+)'/)[1], DEFAULT_SERVICE_URL);
  assert.match(src, /^export const DEFAULT_SERVICE_URL = '[^']+';$/m);
  assert.equal(SERVICE_KEY, 'vivome-service-address');
  // One copy: no page or other module keeps its own.
  const copies = [];
  const walk = (dir) => {
    for (const entry of readdirSync(new URL(`../${dir}`, import.meta.url), { withFileTypes: true })) {
      const rel = `${dir}${entry.name}`;
      if (entry.isDirectory()) walk(`${rel}/`);
      else if (/\.(html|js)$/.test(entry.name) && rel !== 'js/atlas/service-client.js'
        && read(rel).includes(DEFAULT_SERVICE_URL)) copies.push(rel);
    }
  };
  for (const page of readdirSync(new URL('..', import.meta.url))) {
    if (page.endsWith('.html') && read(page).includes(DEFAULT_SERVICE_URL)) copies.push(page);
  }
  walk('js/');
  assert.deepEqual(copies, [], 'only js/atlas/service-client.js names the address');
});

test('a typed address is remembered; the default is not', () => {
  const store = new Map();
  const storage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k),
  };
  assert.equal(serviceUrlFrom(storage), DEFAULT_SERVICE_URL);
  assert.equal(rememberServiceUrl(storage, ` ${OWN}/ `), OWN);
  assert.equal(store.get(SERVICE_KEY), OWN);
  assert.equal(serviceUrlFrom(storage), OWN);
  assert.equal(rememberServiceUrl(storage, DEFAULT_SERVICE_URL), DEFAULT_SERVICE_URL);
  assert.equal(store.has(SERVICE_KEY), false, 'the default is not stored');
  rememberServiceUrl(storage, OWN);
  assert.equal(rememberServiceUrl(storage, '   '), DEFAULT_SERVICE_URL, 'blank means the default');
  assert.equal(store.has(SERVICE_KEY), false);
  // No storage, or storage that throws (a private window, blocked site data).
  const throwing = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); }, removeItem() { throw new Error('denied'); } };
  assert.equal(serviceUrlFrom(null), DEFAULT_SERVICE_URL);
  assert.equal(serviceUrlFrom(throwing), DEFAULT_SERVICE_URL);
  assert.equal(rememberServiceUrl(null, OWN), OWN);
  assert.equal(rememberServiceUrl(throwing, OWN), OWN);
});

test('Retry-After in seconds or as a date', () => {
  assert.equal(parseRetryAfter('30'), 30);
  assert.equal(parseRetryAfter(' 5 '), 5);
  assert.equal(parseRetryAfter(null), null);
  assert.equal(parseRetryAfter(''), null);
  assert.equal(parseRetryAfter('soon'), null);
  assert.equal(parseRetryAfter('-4'), null);
  const now = Date.parse('Sat, 17 Oct 2026 10:00:00 GMT');
  assert.equal(parseRetryAfter('Sat, 17 Oct 2026 10:00:45 GMT', now), 45);
  assert.equal(parseRetryAfter('Sat, 17 Oct 2026 09:59:00 GMT', now), 0, 'a date already past');
});

test('status: ready, and the address it asked', async () => {
  const { calls, client } = fake({ status: 200, body: READY });
  assert.deepEqual(await client.status(`${OWN}//`), READY);
  assert.equal(calls[0].method, 'GET');
  assert.equal(calls[0].url, `${OWN}/api/status`);
  assert.ok(calls[0].signal, 'the transport gets a signal');
});

test('status: running but not ready, with its reason', async () => {
  const reason = 'missing artifact: service/model/v3_1/member_0.pt';
  for (const status of [503, 500, 200]) {
    const { client } = fake({ status, body: { status: 'unavailable', reason } });
    const err = await failure(client.status(OWN));
    assert.equal(err.kind, 'unavailable', String(status));
    assert.equal(err.status, status);
    assert.equal(err.reason, reason);
    assert.equal(explainFailure(err, OWN), `The service is running but cannot label yet: ${reason}.`);
  }
  const notFound = await failure(fake({ status: 404, body: { error: 'no such endpoint: /api/status' } }).client.status(OWN));
  assert.equal(notFound.kind, 'bad');
  const html = await failure(fake({ status: 200, body: '<html>a proxy page</html>' }).client.status(OWN));
  assert.equal(html.kind, 'bad');
});

test('project: the answer, the form sent and the upload progress', async () => {
  const answer = { n_cells: 1, cells: [{ cell_id: 'a' }] };
  const seen = [];
  const { calls, client } = fake((request) => {
    request.onUpload(0.5);
    request.onUpload(1);
    return { status: 200, body: answer };
  });
  const form = { fake: 'form' };
  assert.deepEqual(await client.project(DEFAULT_SERVICE_URL, form, { onUpload: (f) => seen.push(f) }), answer);
  assert.deepEqual([calls[0].method, calls[0].url, calls[0].body], ['POST', `${DEFAULT_SERVICE_URL}/api/project`, form]);
  assert.deepEqual(seen, [0.5, 1]);
  const empty = await failure(fake({ status: 200, body: { n_cells: 0 } }).client.project(OWN, form));
  assert.equal(empty.kind, 'bad');
});

test('project: busy, with Retry-After 30, or with the header hidden from the page', async () => {
  const withHeader = await failure(fake({ status: 503, headers: { 'Retry-After': '30' }, body: BUSY }).client.project(OWN, {}));
  assert.deepEqual([withHeader.kind, withHeader.status, withHeader.retryAfter], ['busy', 503, 30]);
  assert.equal(withHeader.reason, BUSY.reason);
  // A page on another origin cannot read Retry-After unless the service
  // exposes it; the reason names the wait too.
  const hidden = await failure(fake({ status: 503, body: { ...BUSY, reason: 'Try again in about 12 seconds.' } }).client.project(OWN, {}));
  assert.deepEqual([hidden.kind, hidden.retryAfter], ['busy', 12]);
  const bare = await failure(fake({ status: 503, body: { error: 'the service is busy with another upload' } }).client.project(OWN, {}));
  assert.equal(bare.retryAfter, BUSY_RETRY_SECONDS);
  const getter = await failure(fake({ status: 503, headers: (name) => (name === 'Retry-After' ? '7' : null), body: BUSY })
    .client.project(OWN, {}));
  assert.equal(getter.retryAfter, 7, 'headers as a getter, as the browser transport gives them');
  const text = explainFailure(withHeader, DEFAULT_SERVICE_URL);
  assert.match(text, /another file is being labelled/i);
  assert.match(text, /try again by itself in about 30 seconds/);
});

test('project: not ready yet (503 without Retry-After, or 500)', async () => {
  const body = { error: 'projection service not yet available', reason: 'missing artifact: x.pt', see: 'docs' };
  for (const status of [503, 500]) {
    const err = await failure(fake({ status, body }).client.project(OWN, {}));
    assert.deepEqual([err.kind, err.status, err.reason], ['unavailable', status, 'missing artifact: x.pt']);
  }
});

test('project: refused, 413 and 400, with the service’s own words', async () => {
  const big = await failure(fake({ status: 413, body: TOO_MANY }).client.project(OWN, {}));
  assert.deepEqual([big.kind, big.status, big.message, big.reason], ['refused', 413, TOO_MANY.error, TOO_MANY.reason]);
  assert.equal(explainFailure(big, OWN), `The service turned the file down: ${TOO_MANY.error}. ${TOO_MANY.reason}`);
  const bad = await failure(fake({ status: 400, body: { error: 'upload has 4 cell(s); at least 20 are required' } }).client.project(OWN, {}));
  assert.deepEqual([bad.kind, bad.status, bad.reason], ['refused', 400, null]);
  assert.equal(explainFailure(bad, OWN), 'The service turned the file down: upload has 4 cell(s); at least 20 are required.');
});

test('a network failure, and what the visitor is told for each address', async () => {
  const { client } = fake(() => {
    throw new TypeError('Failed to fetch');
  });
  const err = await failure(client.status(OWN));
  assert.equal(err.kind, 'network');
  assert.ok(err.cause instanceof TypeError);
  const own = explainFailure(err, OWN);
  assert.ok(own.includes(OWN));
  assert.match(own, /is it running/);
  assert.match(own, /VIVOME_ALLOWED_ORIGINS/);
  const hosted = explainFailure(err, `${DEFAULT_SERVICE_URL}/`);
  assert.ok(hosted.includes(DEFAULT_SERVICE_URL));
  assert.ok(!hosted.includes('VIVOME_ALLOWED_ORIGINS'), 'the hosted service is not the visitor’s to configure');
});

test('a timeout, and cancelling', async () => {
  const hang = () => new Promise(() => {});
  const late = await failure(fake(hang).client.status(OWN, { timeoutMs: 15 }));
  assert.equal(late.kind, 'timeout');
  assert.match(explainFailure(late, OWN), /did not answer in time/);

  // The transport sees its signal abort when the caller cancels.
  const controller = new AbortController();
  let sawAbort = false;
  const { client } = fake((request) => new Promise((_, reject) => {
    request.signal.addEventListener('abort', () => {
      sawAbort = true;
      reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
    });
    setTimeout(() => controller.abort(), 5);
  }));
  const cancelled = await failure(client.project(OWN, {}, { signal: controller.signal, timeoutMs: 5000 }));
  assert.equal(cancelled.kind, 'cancelled');
  assert.equal(sawAbort, true);
  assert.match(explainFailure(cancelled, OWN), /cancelled/);
  const early = await failure(client.status(OWN, { signal: AbortSignal.abort() }));
  assert.equal(early.kind, 'cancelled', 'already cancelled');
});

test('every explanation is one plain line, without an em dash', () => {
  const kinds = ['network', 'busy', 'unavailable', 'refused', 'timeout', 'cancelled', 'bad'];
  const lines = kinds.map((kind) => explainFailure(new ServiceError(kind, 'the error', { status: 400, reason: 'the reason', retryAfter: 30 }), OWN));
  assert.equal(new Set(lines).size, kinds.length, 'one line per kind');
  for (const line of lines) {
    assert.ok(!line.includes('—'), line);
    assert.ok(!line.includes('\n'), line);
    assert.match(line, /[.?]$/);
  }
  assert.equal(explainFailure(new Error('Something odd')), 'Something odd.');
  assert.equal(explainFailure(null), 'Something went wrong.');
});

test('the browser transport: fetch for the status, XMLHttpRequest for the upload', async () => {
  const saved = { fetch: globalThis.fetch, XMLHttpRequest: globalThis.XMLHttpRequest };
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, `${OWN}/api/status`);
      assert.ok(options.signal);
      return { status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), text: async () => JSON.stringify(READY) };
    };
    const sent = [];
    globalThis.XMLHttpRequest = class {
      constructor() {
        this.upload = {};
      }

      open(method, url) {
        this.method = method;
        this.url = url;
      }

      getResponseHeader(name) {
        return name === 'Retry-After' ? '30' : null;
      }

      send(body) {
        sent.push([this.method, this.url, body]);
        setTimeout(() => {
          this.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
          this.upload.onload?.();
          this.status = 503;
          this.responseText = JSON.stringify(BUSY);
          this.onload();
        }, 1);
      }

      abort() {
        this.onabort();
      }
    };
    const client = createServiceClient();
    assert.deepEqual(await client.status(OWN), READY);
    const progress = [];
    const err = await failure(client.project(OWN, 'the form', { onUpload: (f) => progress.push(f) }));
    assert.deepEqual([err.kind, err.retryAfter], ['busy', 30]);
    assert.deepEqual(sent, [['POST', `${OWN}/api/project`, 'the form']]);
    assert.deepEqual(progress, [0.5, 1]);
    // Called directly, the transport hands back the raw answer.
    const raw = await browserTransport({ method: 'POST', url: `${OWN}/api/project`, body: 'x' });
    assert.deepEqual([raw.status, raw.headers('Retry-After'), JSON.parse(raw.body)], [503, '30', BUSY]);
  } finally {
    Object.assign(globalThis, saved);
  }
});
