// Talking to the projection service (docs/service/projection-api.md):
// where it is, asking whether it is ready, sending a file, and saying in
// plain words what went wrong. Pure at import: the browser transport
// touches fetch and XMLHttpRequest only when called, and node --test hands
// the client a fake one.

// The hosted service on Google Cloud Run (deploy/huggingface/PUBLISH.md).
// It answers only through the website: the site's /api door
// (deploy/pages/api-proxy.js) forwards there with the secret it checks.
// scripts/build_workflow.py and scripts/build_pages_site.py read this line.
export const DEFAULT_SERVICE_URL = 'https://vivome-atlas-577083340913.us-central1.run.app';

// The address pages use unless the visitor sets another: their own site,
// whose /api/... reaches the hosted service. Outside a browser (node --test)
// there is no site, so it is the hosted service's own address.
export function siteServiceUrl(where = globalThis.location) {
  const origin = where?.origin;
  return typeof origin === 'string' && /^https?:\/\//.test(origin) ? origin : DEFAULT_SERVICE_URL;
}

// An address the visitor typed is remembered, as a per-visitor convenience;
// the default is not, so changing it reaches every visitor who never typed
// one. Everything works without storage.
export const SERVICE_KEY = 'vivome-service-address';

// The service's own Retry-After for a busy answer (service/config.py,
// VIVOME_BUSY_RETRY_AFTER_SECONDS), used when the header cannot be read: a
// page reads it through its own site, but not from a copy on another origin
// unless that copy exposes it.
export const BUSY_RETRY_SECONDS = 30;

// The first status check after a quiet spell waits while the hosted
// service starts, which can take up to a minute.
export const STATUS_TIMEOUT_MS = 75 * 1000;
// Longer than the hosted service lets one request run (300 s), so its own
// answer comes first; a copy run at home has no limit of its own.
export const PROJECT_TIMEOUT_MS = 10 * 60 * 1000;

export const normaliseServiceUrl = (url) => String(url ?? '').trim().replace(/\/+$/, '');

// The address to use: the one the visitor typed before, or the site's own.
export function serviceUrlFrom(storage, where = globalThis.location) {
  try {
    const stored = normaliseServiceUrl(storage?.getItem(SERVICE_KEY));
    return stored || siteServiceUrl(where);
  } catch {
    return siteServiceUrl(where);
  }
}

// Remembers a typed address (forgets it when it is blank or the site's
// own) and returns the address to use.
export function rememberServiceUrl(storage, typed, where = globalThis.location) {
  const url = normaliseServiceUrl(typed);
  const site = siteServiceUrl(where);
  try {
    if (url && url !== site && url !== DEFAULT_SERVICE_URL) storage?.setItem(SERVICE_KEY, url);
    else storage?.removeItem(SERVICE_KEY);
  } catch { /* no storage */ }
  return url || site;
}

// A copy the visitor runs themselves, not the site's own service.
export const isOwnCopy = (url, where = globalThis.location) => {
  const u = normaliseServiceUrl(url);
  return u !== siteServiceUrl(where) && u !== DEFAULT_SERVICE_URL;
};

// kind: network (no answer), busy (every slot taken; try again after
// retryAfter seconds), unavailable (running, but cannot label yet: reason),
// refused (400 or 413: the file was turned down, with the service's own
// error and reason), timeout, cancelled, bad (an answer this page cannot
// read).
export class ServiceError extends Error {
  constructor(kind, message, { status = null, reason = null, retryAfter = null, cause } = {}) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = 'ServiceError';
    this.kind = kind;
    this.status = status;
    this.reason = reason;
    this.retryAfter = retryAfter;
  }
}

// A Retry-After header in seconds: a whole number of seconds, or an HTTP
// date counted from `now`. null when absent or unreadable.
export function parseRetryAfter(header, now = Date.now()) {
  if (header === null || header === undefined) return null;
  const text = String(header).trim();
  if (text === '') return null;
  if (/^\d+$/.test(text)) return Number(text);
  // An HTTP date names its day and month ("Sat, 17 Oct 2026 10:00:45 GMT").
  if (!/[a-z]/i.test(text)) return null;
  const at = Date.parse(text);
  if (!Number.isFinite(at)) return null;
  return Math.max(0, Math.ceil((at - now) / 1000));
}

// The busy answer names its wait in words too ("Try again in about 30
// seconds."), which a page on another origin can always read.
const retryFromReason = (reason) => {
  const m = /about (\d+) seconds?/i.exec(String(reason ?? ''));
  return m ? Number(m[1]) : null;
};

function headerOf(res, name) {
  const h = res?.headers;
  if (!h) return null;
  if (typeof h === 'function') return h(name) ?? null;
  if (typeof h.get === 'function') return h.get(name) ?? null;
  const key = Object.keys(h).find((k) => k.toLowerCase() === name.toLowerCase());
  return key === undefined ? null : h[key];
}

function parseJson(text) {
  try {
    const value = JSON.parse(text);
    return value && typeof value === 'object' ? value : null;
  } catch {
    return null;
  }
}

const abortError = () => Object.assign(new Error('The request was cancelled.'), { name: 'AbortError' });

// One request through the transport, with a timeout and the caller's
// signal. The answer settles when either fires, even from a transport that
// ignores its signal.
async function send(transport, request, { signal, timeoutMs }) {
  if (signal?.aborted) throw new ServiceError('cancelled', 'Cancelled before the service answered.');
  const controller = new AbortController();
  let timedOut = false;
  let stop;
  const stopped = new Promise((_, reject) => {
    stop = () => reject(abortError());
  });
  stopped.catch(() => {});
  const onAbort = () => {
    controller.abort();
    stop();
  };
  signal?.addEventListener('abort', onAbort, { once: true });
  const timer = timeoutMs > 0 ? setTimeout(() => {
    timedOut = true;
    onAbort();
  }, timeoutMs) : null;
  try {
    return await Promise.race([transport({ ...request, signal: controller.signal }), stopped]);
  } catch (err) {
    if (timedOut) {
      throw new ServiceError('timeout', `No answer within ${Math.round(timeoutMs / 1000)} seconds.`, { cause: err });
    }
    if (signal?.aborted || err?.name === 'AbortError') {
      throw new ServiceError('cancelled', 'Cancelled before the service answered.', { cause: err });
    }
    throw new ServiceError('network', 'The service could not be reached.', { cause: err });
  } finally {
    if (timer !== null) clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

// An answer that is not the one asked for, as a ServiceError.
function failureOf(res, payload) {
  const status = res.status;
  const error = payload?.error ?? null;
  const reason = payload?.reason ?? null;
  const header = parseRetryAfter(headerOf(res, 'Retry-After'));
  const busy = status === 429 || (status === 503 && (header !== null || /busy/i.test(String(error ?? ''))));
  if (busy) {
    const retryAfter = header ?? retryFromReason(reason) ?? BUSY_RETRY_SECONDS;
    return new ServiceError('busy', error ?? 'The service is busy with another upload.', { status, reason, retryAfter });
  }
  if ((status === 503 || status === 500) && payload) {
    const why = reason ?? error ?? 'it did not say why';
    return new ServiceError('unavailable', error ?? 'The service cannot label yet.', { status, reason: why });
  }
  if ((status === 400 || status === 413) && payload) {
    return new ServiceError('refused', error ?? `The service turned the file down (HTTP ${status}).`, { status, reason });
  }
  if (status === 408 || status === 504) return new ServiceError('timeout', 'The service took too long to answer.', { status });
  return new ServiceError('bad', `The service answered HTTP ${status}${payload ? '' : ' with no JSON'}.`, { status, reason });
}

export function createServiceClient({ transport = browserTransport } = {}) {
  return {
    // GET /api/status: the status record when the service is ready.
    async status(url, { signal, timeoutMs = STATUS_TIMEOUT_MS } = {}) {
      const res = await send(transport, { method: 'GET', url: `${normaliseServiceUrl(url)}/api/status` }, { signal, timeoutMs });
      const payload = parseJson(res.body);
      if (res.status === 200 && payload?.status === 'ready') return payload;
      if (payload?.status === 'unavailable' || (res.status === 200 && payload)) {
        throw new ServiceError('unavailable', 'The service cannot label yet.', {
          status: res.status, reason: payload.reason ?? payload.error ?? 'it did not say why',
        });
      }
      throw failureOf(res, payload);
    },

    // POST /api/project: the service's answer for every cell. onUpload gets
    // the fraction of the file sent, 1 when all of it is.
    async project(url, form, { signal, onUpload, timeoutMs = PROJECT_TIMEOUT_MS } = {}) {
      const res = await send(transport, {
        method: 'POST', url: `${normaliseServiceUrl(url)}/api/project`, body: form, onUpload,
      }, { signal, timeoutMs });
      const payload = parseJson(res.body);
      if (res.status === 200) {
        if (Array.isArray(payload?.cells)) return payload;
        throw new ServiceError('bad', 'The answer has no cells.', { status: 200 });
      }
      throw failureOf(res, payload);
    },
  };
}

// The browser's own requests: fetch for GET, XMLHttpRequest for POST, as
// only it reports upload progress. A listener on the upload makes the
// browser ask the service first (a CORS preflight), which it answers.
export function browserTransport({ method = 'GET', url, body = null, signal, onUpload }) {
  if (method === 'GET') {
    return fetch(url, { signal }).then(async (res) => ({
      status: res.status, headers: (name) => res.headers.get(name), body: await res.text(),
    }));
  }
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url);
    if (onUpload) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && e.total > 0) onUpload(e.loaded / e.total);
      };
      xhr.upload.onload = () => onUpload(1);
    }
    xhr.onload = () => resolve({ status: xhr.status, headers: (name) => xhr.getResponseHeader(name), body: xhr.responseText });
    xhr.onerror = () => reject(new TypeError('The request failed.'));
    xhr.onabort = () => reject(abortError());
    if (signal) {
      if (signal.aborted) {
        reject(abortError());
        return;
      }
      signal.addEventListener('abort', () => xhr.abort(), { once: true });
    }
    xhr.send(body);
  });
}

const sentence = (text) => {
  const t = String(text ?? '').trim();
  return t === '' || /[.!?]$/.test(t) ? t : `${t}.`;
};

// One plain sentence for the visitor about what went wrong.
export function explainFailure(err, url = DEFAULT_SERVICE_URL) {
  const address = normaliseServiceUrl(url) || DEFAULT_SERVICE_URL;
  switch (err?.kind) {
    case 'network':
      return isOwnCopy(address)
        ? `Could not reach the service at ${address}: is it running, and does its VIVOME_ALLOWED_ORIGINS list this page's address?`
        : `Could not reach the service at ${address}. Check the connection and try again.`;
    case 'busy':
      return `Another file is being labelled right now, so this page will try again by itself in about ${err.retryAfter ?? BUSY_RETRY_SECONDS} seconds.`;
    case 'unavailable':
      return sentence(`The service is running but cannot label yet: ${err.reason ?? err.message}`);
    case 'refused':
      return [sentence(`The service turned the file down: ${err.message}`), sentence(err.reason)].filter(Boolean).join(' ');
    case 'timeout':
      return `The service at ${address} did not answer in time, so this page stopped waiting.`;
    case 'cancelled':
      return 'The upload was cancelled before the service answered.';
    case 'bad':
      return `The service at ${address} answered in a way this page cannot read${err.status ? ` (HTTP ${err.status})` : ''}.`;
    default:
      return sentence(err?.message || 'Something went wrong.');
  }
}
