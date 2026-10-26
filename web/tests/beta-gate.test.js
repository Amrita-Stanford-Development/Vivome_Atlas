// The beta's sign-in (deploy/pages/beta-gate.js): who gets in, what the
// cookie proves, and what every page gains on the way out.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  COOKIE, EMAILS, SESSION_DAYS, onRequest, passwordMatches, safeNext, sessionEmail, sessionValue, signInPage,
  withBetaHeader,
} from '../../deploy/pages/beta-gate.js';

const PASSWORD = 'correct horse battery staple';
// scripts/beta_access.py's password_hash(PASSWORD, bytes.fromhex(...)), so the
// two sides agree (scripts/test_beta_access.py checks the same value).
const HASH = 'sha256$00112233445566778899aabbccddeeff$c61e9af5f5d5efcb41c31a256e2974cb74583fb334762c0c2b7f3f5a12d6703b';
const env = { BETA_PASSWORD_HASH: HASH, BETA_SESSION_KEY: 'ab'.repeat(32) };
const INVITED = 'owner@example.org';
EMAILS.push(INVITED); // the build writes the list into the module

const PAGE = '<html><head><title>x</title></head><body><header class="site-header glass"><div>'
  + '<a class="wordmark" href="index.html" aria-label="VivOME home">Viv<span class="cut">OME</span></a>'
  + '<nav class="site-nav" aria-label="Main"><a href="atlas.html">Atlas</a></nav></div></header>'
  + '<main><nav class="toc"><a href="#a">A</a></nav></main></body></html>';
const asset = (body = PAGE, type = 'text/html; charset=utf-8') => async () => new Response(body, {
  headers: { 'Content-Type': type, 'X-Frame-Options': 'DENY', 'Content-Length': String(body.length) },
});
const get = (path, headers = {}) => new Request(`https://vivome-atlas.pages.dev${path}`, { headers });
const signIn = (fields) => new Request('https://vivome-atlas.pages.dev/__beta/signin', {
  method: 'POST', body: new URLSearchParams(fields),
});
const cookieFrom = (response) => response.headers.get('Set-Cookie').split(';')[0];

test('the password check agrees with scripts/beta_access.py, and nothing else passes', async () => {
  assert.equal(await passwordMatches(PASSWORD, HASH), true);
  assert.equal(await passwordMatches(`${PASSWORD} `, HASH), false);
  assert.equal(await passwordMatches('', HASH), false);
  assert.equal(await passwordMatches(PASSWORD, 'plain$text'), false, 'an unknown scheme never matches');
  assert.equal(await passwordMatches(PASSWORD, undefined), false);
});

test('a page without a session is the sign-in form, marked not for search engines', async () => {
  const response = await onRequest({ request: get('/atlas?tab=data', { Accept: 'text/html' }), env, next: asset() });
  assert.equal(response.status, 401);
  assert.equal(response.headers.get('X-Robots-Tag'), 'noindex, nofollow');
  const html = await response.text();
  assert.match(html, /<form method="post" action="\/__beta\/signin">/);
  assert.match(html, /name="next" value="\/atlas\?tab=data"/);
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
});

test('a file or the service without a session is refused, never served', async () => {
  let served = false;
  const next = async () => { served = true; return new Response('x'); };
  for (const path of ['/data/profiles/index.json', '/api/project', '/js/panels.js']) {
    const response = await onRequest({ request: get(path), env, next });
    assert.equal(response.status, 401, path);
    assert.match(await response.text(), /sign in first/);
  }
  assert.equal(served, false);
});

test('an invited email with the password signs in for thirty days and returns to the page asked for', async () => {
  const response = await onRequest({
    request: signIn({ email: '  Owner@Example.org ', password: PASSWORD, next: '/atlas?tab=data' }), env, next: asset(),
  });
  assert.equal(response.status, 303);
  assert.equal(response.headers.get('Location'), '/atlas?tab=data');
  const cookie = response.headers.get('Set-Cookie');
  assert.match(cookie, new RegExp(`^${COOKIE}=`));
  for (const part of ['HttpOnly', 'Secure', 'SameSite=Lax', 'Path=/', `Max-Age=${SESSION_DAYS * 86400}`]) {
    assert.ok(cookie.includes(part), part);
  }
  const page = await onRequest({ request: get('/atlas', { Cookie: cookieFrom(response) }), env, next: asset() });
  assert.equal(page.status, 200);
  assert.match(await page.text(), /Sign out<\/a><\/nav>/);
});

test('a wrong password or an email not invited gets the form again, with no cookie', async () => {
  for (const fields of [{ email: INVITED, password: 'wrong password!' }, { email: 'other@example.org', password: PASSWORD }]) {
    const response = await onRequest({ request: signIn(fields), env, next: asset() });
    assert.equal(response.status, 401);
    assert.equal(response.headers.get('Set-Cookie'), null);
    assert.match(await response.text(), /do not match an invitation/);
  }
});

test('the cookie proves the session: forged, expired, uninvited or after a new password, it fails', async () => {
  const now = Date.UTC(2026, 9, 26);
  const value = await sessionValue(env, INVITED, now);
  const request = (v) => get('/', { Cookie: `other=1; ${COOKIE}=${v}` });
  assert.equal(await sessionEmail(request(value), env, EMAILS, now), INVITED);
  const [email, expires, mac] = value.split('.');
  assert.equal(await sessionEmail(request(`${email}.${Number(expires) + 86400}.${mac}`), env, EMAILS, now), null, 'longer');
  assert.equal(await sessionEmail(request(`${email}.${expires}.${'0'.repeat(64)}`), env, EMAILS, now), null, 'forged');
  assert.equal(await sessionEmail(request(value), env, EMAILS, now + (SESSION_DAYS + 1) * 86400 * 1000), null, 'expired');
  assert.equal(await sessionEmail(request(value), env, ['someone@else.org'], now), null, 'no longer invited');
  assert.equal(await sessionEmail(request(value), { ...env, BETA_PASSWORD_HASH: `${HASH}0` }, EMAILS, now), null,
    'a new password ends every session');
  assert.equal(await sessionEmail(request('%%%.x.y'), env, EMAILS, now), null, 'garbage');
  assert.equal(await sessionEmail(get('/'), env, EMAILS, now), null, 'no cookie');
});

test('signing out clears the cookie', async () => {
  const response = await onRequest({ request: get('/__beta/signout'), env, next: asset() });
  assert.equal(response.status, 303);
  assert.equal(response.headers.get('Location'), '/');
  assert.match(response.headers.get('Set-Cookie'), new RegExp(`^${COOKIE}=; .*Max-Age=0`));
});

test('after signing in, the way back stays on this site, and reaches the form escaped', async () => {
  assert.equal(safeNext('/atlas?x=1#y'), '/atlas?x=1#y');
  for (const bad of ['https://evil.example', '//evil.example', '/\\evil.example', 'atlas', '', null, '/__beta/signout']) {
    assert.equal(safeNext(bad), '/', String(bad));
  }
  const html = await signInPage({ next: '/"><script>alert(1)</script>' }).text();
  assert.ok(!html.includes('<script>'), 'the path is data, not markup');
  assert.match(html, /value="\/&quot;&gt;&lt;script&gt;/);
});

test('a deployment without its secrets lets nobody in', async () => {
  for (const partial of [{}, { BETA_PASSWORD_HASH: HASH }, { BETA_SESSION_KEY: env.BETA_SESSION_KEY }]) {
    const response = await onRequest({ request: get('/', { Accept: 'text/html' }), env: partial, next: asset() });
    assert.equal(response.status, 503);
  }
});

test('pages gain the Beta mark and Sign out in their own header only; other files pass untouched', async () => {
  const html = withBetaHeader(PAGE);
  assert.match(html, /<span class="cut">OME<\/span><\/a><span class="beta-mark">Beta<\/span>/);
  assert.match(html, /<a href="atlas.html">Atlas<\/a><a href="\/__beta\/signout">Sign out<\/a><\/nav><\/div><\/header>/);
  assert.match(html, /<nav class="toc"><a href="#a">A<\/a><\/nav>/, 'the page\'s other navs are left alone');
  assert.match(html, /<style>\.beta-mark\{[^<]*<\/style><\/head>/);
  assert.equal(withBetaHeader('<p>no header</p>'), '<p>no header</p>');
  const cookie = cookieFrom(await onRequest({ request: signIn({ email: INVITED, password: PASSWORD }), env, next: asset() }));
  const page = await onRequest({ request: get('/', { Cookie: cookie }), env, next: asset() });
  assert.equal(page.headers.get('X-Frame-Options'), 'DENY', 'the site\'s headers stay');
  assert.equal(page.headers.get('Content-Length'), null, 'the old length no longer fits');
  const shard = await onRequest({ request: get('/data/x.f32.gz', { Cookie: cookie }), env, next: asset('ab', 'application/gzip') });
  assert.equal(await shard.text(), 'ab');
  assert.equal(shard.headers.get('Content-Length'), '2');
});

test('the real pages carry the header the gate looks for', async () => {
  const { readFileSync, readdirSync } = await import('node:fs');
  const web = new URL('../', import.meta.url);
  const pages = ['index.html', 'atlas.html', 'workflow.html', 'manuscript.html', 'motion.html'];
  for (const name of pages) {
    const out = withBetaHeader(readFileSync(new URL(name, web), 'utf8'));
    assert.match(out, /class="beta-mark">Beta</, name);
    assert.match(out, /href="\/__beta\/signout">Sign out</, name);
  }
  const others = readdirSync(web).filter((n) => n.endsWith('.html') && !pages.includes(n));
  for (const name of others) {
    const html = readFileSync(new URL(name, web), 'utf8');
    if (html.includes('class="site-header')) assert.fail(`${name} has the site header: add it to this test's pages`);
  }
});
