// The beta's sign-in: a Cloudflare Pages middleware, copied to
// functions/_middleware.js by scripts/build_pages_site.py, in front of every
// path of the site (its _routes.json sends every request through Functions),
// the /api door to the labelling service included.
//
// A visitor signs in with an invited email and the beta's one password.
// The invited emails are written into EMAILS at build time, from a local file
// outside the repository (~/.vivome-beta/emails.txt); the password's salted
// hash and the key that signs the session cookie are Pages secrets
// (BETA_PASSWORD_HASH, BETA_SESSION_KEY), set by scripts/beta_access.py. A
// session lasts SESSION_DAYS and ends early when the email leaves the list
// or the password changes. No email is verified: the owner's choice for a
// closed beta (2026-10-26). docs/web/hosting.md, "The beta sign-in".

export const EMAILS = [];
export const COOKIE = 'vivome_beta';
export const SESSION_DAYS = 30;
const SIGN_IN = '/__beta/signin';
const SIGN_OUT = '/__beta/signout';

const encoder = new TextEncoder();
const hex = (bytes) => [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, '0')).join('');
const fromHex = (text) => new Uint8Array((text.match(/../g) ?? []).map((h) => parseInt(h, 16)));
const toBase64Url = (text) => btoa(String.fromCharCode(...encoder.encode(text)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const fromBase64Url = (text) => new TextDecoder().decode(
  Uint8Array.from(atob(text.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0)));

// Equal strings, compared in time that does not depend on where they differ.
function same(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export const normalEmail = (email) => String(email ?? '').trim().toLowerCase();

// BETA_PASSWORD_HASH is "sha256$<salt, hex>$<SHA-256 of salt bytes then the
// password's UTF-8, hex>" (scripts/beta_access.py writes it). One hash, not a
// slow one: Workers on the free plan get 10 ms of CPU a request, and the hash
// lives only in a Cloudflare secret; a long password is the protection.
export async function passwordMatches(password, stored) {
  const [scheme, salt, digest] = String(stored ?? '').split('$');
  if (scheme !== 'sha256' || !salt || !digest) return false;
  const bytes = new Uint8Array([...fromHex(salt), ...encoder.encode(String(password ?? ''))]);
  return same(hex(await crypto.subtle.digest('SHA-256', bytes)), digest);
}

async function signature(env, email, expires) {
  const key = await crypto.subtle.importKey('raw', fromHex(env.BETA_SESSION_KEY), { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign']);
  // The password's hash is signed too, so a new password ends every session.
  const text = `${email}|${expires}|${env.BETA_PASSWORD_HASH}`;
  return hex(await crypto.subtle.sign('HMAC', key, encoder.encode(text)));
}

export async function sessionValue(env, email, now = Date.now()) {
  const expires = Math.floor(now / 1000) + SESSION_DAYS * 86400;
  return `${toBase64Url(email)}.${expires}.${await signature(env, email, expires)}`;
}

// The signed-in email, or null.
export async function sessionEmail(request, env, emails = EMAILS, now = Date.now()) {
  const cookie = (request.headers.get('Cookie') ?? '').split(/;\s*/).find((c) => c.startsWith(`${COOKIE}=`));
  if (!cookie) return null;
  const [encoded, expires, mac] = cookie.slice(COOKIE.length + 1).split('.');
  let email;
  try {
    email = fromBase64Url(encoded ?? '');
  } catch {
    return null;
  }
  if (!/^\d+$/.test(expires ?? '') || Number(expires) * 1000 <= now) return null;
  if (!emails.includes(email)) return null;
  return same(await signature(env, email, Number(expires)), mac) ? email : null;
}

// Where to go after signing in: a path on this site, never another site.
export function safeNext(next) {
  const path = String(next ?? '');
  return /^\/(?![/\\])/.test(path) && !path.startsWith('/__beta/') ? path : '/';
}

const escapeHtml = (value) => String(value).replace(/[&<>"']/g,
  (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);

export function signInPage({ next = '/', message = '', status = 401 } = {}) {
  const note = message ? `<p class="note" role="alert">${escapeHtml(message)}</p>` : '';
  return new Response(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Sign in · VivOME Atlas (beta)</title>
<style>
  body { margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         color: #1b2433; background: radial-gradient(circle at 30% 20%, #e8f0ff, #f6f8fc 60%); }
  form { width: min(360px, calc(100vw - 32px)); background: #fff; border-radius: 18px; padding: 32px 28px;
         box-shadow: 0 0 0 1px rgba(60, 110, 220, .12), 0 18px 48px rgba(60, 110, 220, .22); }
  h1 { margin: 0 0 4px; font-size: 1.5rem; } .sub { margin: 0 0 22px; color: #4a5568; }
  label { display: block; margin: 14px 0 6px; font-weight: 600; font-size: .95rem; }
  input { box-sizing: border-box; width: 100%; padding: 10px 12px; font: inherit; border: 1px solid #858585; border-radius: 10px; }
  input:focus-visible, button:focus-visible { outline: 3px solid #3c6edc; outline-offset: 2px; }
  button { margin-top: 22px; width: 100%; padding: 11px; font: inherit; font-weight: 600; color: #fff; background: #2f5fc9;
           border: 0; border-radius: 10px; cursor: pointer; }
  .note { margin: 14px 0 0; color: #a3261b; }
</style></head>
<body><form method="post" action="${SIGN_IN}">
  <h1>VivOME Atlas</h1><p class="sub">A closed beta. Sign in with your invited email.</p>
  <input type="hidden" name="next" value="${escapeHtml(safeNext(next))}">
  <label for="email">Email</label><input id="email" name="email" type="email" autocomplete="username" required autofocus>
  <label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required>
  ${note}<button type="submit">Sign in</button>
</form></body></html>
`, {
    status,
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow',
      'X-Frame-Options': 'DENY', 'Content-Security-Policy': "frame-ancestors 'none'" },
  });
}

const cookieHeader = (value, maxAge) => `${COOKIE}=${value}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`;
const redirect = (location, cookie) => new Response(null, {
  status: 303, headers: { Location: location, 'Cache-Control': 'no-store', ...(cookie ? { 'Set-Cookie': cookie } : {}) },
});

// Every page's header gains a Beta mark and a Sign out link, on the way out,
// so web/ itself stays free of the beta.
const BETA_STYLE = '<style>.beta-mark{margin-left:8px;padding:2px 8px;border-radius:999px;font-size:.72rem;font-weight:700;'
  + 'letter-spacing:.04em;text-transform:uppercase;color:#2f5fc9;background:rgba(47,95,201,.1);vertical-align:middle}</style>';
export function withBetaHeader(html) {
  const start = html.indexOf('<header class="site-header');
  const end = start < 0 ? -1 : html.indexOf('</header>', start);
  if (end < 0) return html;
  const header = html.slice(start, end)
    .replace(/(<a class="wordmark"[^>]*>[\s\S]*?<\/a>)/, '$1<span class="beta-mark">Beta</span>')
    .replace('</nav>', `<a href="${SIGN_OUT}">Sign out</a></nav>`);
  return (html.slice(0, start) + header + html.slice(end)).replace('</head>', `${BETA_STYLE}</head>`);
}

export async function onRequest({ request, env, next }) {
  const url = new URL(request.url);
  if (!env?.BETA_PASSWORD_HASH || !env?.BETA_SESSION_KEY || EMAILS.length === 0) {
    return new Response('The beta sign-in is not set up on this deployment (docs/web/hosting.md).', {
      status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
    });
  }
  if (url.pathname === SIGN_IN && request.method === 'POST') {
    const form = await request.formData().catch(() => null);
    const email = normalEmail(form?.get('email'));
    const target = safeNext(form?.get('next'));
    if (EMAILS.includes(email) && await passwordMatches(form?.get('password'), env.BETA_PASSWORD_HASH)) {
      return redirect(target, cookieHeader(await sessionValue(env, email), SESSION_DAYS * 86400));
    }
    return signInPage({ next: target, message: 'That email and password do not match an invitation.' });
  }
  if (url.pathname === SIGN_OUT) return redirect('/', cookieHeader('', 0));
  if (!(await sessionEmail(request, env))) {
    const page = (request.headers.get('Accept') ?? '').includes('text/html');
    if (page && (request.method === 'GET' || request.method === 'HEAD')) return signInPage({ next: url.pathname + url.search });
    return new Response(JSON.stringify({ error: 'sign in first', reason: 'This site is a closed beta.' }), {
      status: 401, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    });
  }
  const response = await next();
  if (response.status !== 200 || !(response.headers.get('Content-Type') ?? '').includes('text/html')) return response;
  const headers = new Headers(response.headers);
  headers.delete('Content-Length');
  headers.delete('Content-Encoding');
  return new Response(withBetaHeader(await response.text()), { status: 200, headers });
}
