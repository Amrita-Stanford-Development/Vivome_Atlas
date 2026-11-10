// Captures the Docs section's screenshots into web/img/docs/, and writes
// web/img/docs/index.json beside them: what each one shows, which copy of
// the site it was taken from (live or the branch), and every number it holds,
// with the file and code that number came from. web/tests/docs.test.js fails
// when a screenshot or its entry goes missing, or when a number in it no
// longer matches what the site's own code computes from the repository's file.
//
// No dependencies: Node's http server serves the site, and the PC's Edge (or
// Chrome) runs headless, driven through the DevTools protocol over Node's
// WebSocket. "Live" is served from the commit the live site was built from
// (LIVE_SITE, below), read with git show; "branch" is web/ as it is now.
//
//     node scripts/docs_screenshots.mjs      # from the repository root
//
// Pictures for the page, never a check of it: the owner checks every page by
// hand (docs/web/docs.md, "Screenshots").

import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { extname, join, resolve } from 'node:path';

const REPO = resolve(import.meta.dirname, '..');
const OUT = join(REPO, 'web', 'img', 'docs');
// The live site was deployed from decb812 on 2026-11-07 (commit c42b856, research/todo.md).
export const LIVE_SITE = 'decb812';
const EXAMPLE = join(REPO, 'web', 'data', 'examples', 'pbmc240_proteins_raw.tsv');
const WIDTH = 1280;
const HEIGHT = 1000;
const SCALE = 2;

const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp',
  '.tsv': 'text/tab-separated-values', '.csv': 'text/csv', '.txt': 'text/plain',
};

// The site's files: from the working tree, or as they were at a commit.
function serve(read) {
  const server = createServer((req, res) => {
    const path = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
    let body = null;
    try { body = read(path); } catch { body = null; }
    if (body === null) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': TYPES[extname(path)] ?? 'application/octet-stream' });
    res.end(body);
  });
  return new Promise((ok) => server.listen(0, '127.0.0.1', () => ok(server)));
}
const fromTree = (path) => (path.includes('..') ? null : readFileSync(join(REPO, 'web', path)));
const fromCommit = (rev) => (path) => (path.includes('..') ? null
  : execFileSync('git', ['show', `${rev}:web/${path}`], { cwd: REPO, maxBuffer: 1 << 28, stdio: ['ignore', 'pipe', 'ignore'] }));

function browserPath() {
  const found = [process.env.DOCS_BROWSER,
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'].find((p) => p && existsSync(p));
  if (!found) throw new Error('no Edge or Chrome found: set DOCS_BROWSER to one');
  return found;
}

const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));

// One page over the DevTools protocol.
class Page {
  constructor(ws) { this.ws = ws; this.id = 0; this.waiting = new Map(); this.events = []; }
  static async open(port) {
    const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((ok, fail) => { ws.onopen = ok; ws.onerror = fail; });
    const page = new Page(ws);
    ws.onmessage = (m) => {
      const msg = JSON.parse(m.data);
      if (msg.id && page.waiting.has(msg.id)) {
        const { ok, fail } = page.waiting.get(msg.id);
        page.waiting.delete(msg.id);
        if (msg.error) fail(new Error(msg.error.message)); else ok(msg.result);
      } else if (msg.method) page.events.push(msg);
    };
    return page;
  }
  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((ok, fail) => this.waiting.set(id, { ok, fail }));
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
    return r.result.value;
  }
  async until(expression, what, ms = 20000) {
    for (const end = Date.now() + ms; Date.now() < end; await sleep(150)) {
      if (await this.eval(expression)) return;
    }
    throw new Error(`timed out waiting for ${what}`);
  }
  async goto(url) {
    await this.send('Page.navigate', { url });
    await this.until('document.readyState === "complete"', url);
    await this.eval('document.fonts ? document.fonts.ready.then(() => true) : true');
  }
  // The box around the elements the selectors name, first to last, with a
  // margin, as a WebP at the device scale. The first is scrolled into view
  // and left to settle before it is measured; the picture is of what the
  // window shows, so a dialog stays where it is.
  async shoot(selectors, file, margin = 12) {
    const list = JSON.stringify([selectors].flat());
    await this.eval(`document.querySelector(${list}[0]).scrollIntoView({ block: 'center', behavior: 'instant' }); true`);
    await sleep(700);
    const box = await this.eval(`(() => {
      const rs = ${list}.map((s) => document.querySelector(s).getBoundingClientRect());
      const left = Math.min(...rs.map((r) => r.left)), top = Math.min(...rs.map((r) => r.top));
      const right = Math.max(...rs.map((r) => r.right)), bottom = Math.max(...rs.map((r) => r.bottom));
      return { x: left + scrollX, y: top + scrollY, width: right - left, height: bottom - top }; })()`);
    const clip = { x: Math.max(0, box.x - margin), y: Math.max(0, box.y - margin),
      width: box.width + 2 * margin, height: box.height + 2 * margin, scale: 1 };
    const shot = await this.send('Page.captureScreenshot', { format: 'webp', quality: 88, clip, captureBeyondViewport: false });
    writeFileSync(join(OUT, file), Buffer.from(shot.data, 'base64'));
    return { width: Math.round(clip.width), height: Math.round(clip.height) };
  }
}

// The shots. Each returns its index entry; `numbers` lists every number the
// picture holds and where it came from.
// The Your data tab, clicked until it opens: a click before the page's
// script has wired the tab does nothing.
const openDataTab = (page) => page.until(
  `(document.getElementById('tab-data')?.click(), !document.getElementById('panel-data')?.hidden)`, 'the Your data tab');

const SHOTS = [
  {
    file: 'upload-menus-live.webp',
    site: 'live',
    shows: 'The Atlas page, Your data tab, as it is live: the Values and Zeros menus of the Send a matrix panel, opened out to show every choice.',
    async take(page, base) {
      await page.goto(`${base}/atlas.html`);
      await openDataTab(page);
      // A closed menu shows one choice. The page's own two menus, copied
      // into a panel beside the real one (so the page's styles reach them),
      // wide enough for the longest choice and listed out, show them all. A
      // plain sheet of the field's colour behind it keeps the page out of the
      // margin round the panel.
      await page.eval(`(() => {
        const backdrop = document.createElement('div');
        Object.assign(backdrop.style, { position: 'fixed', inset: '0', background: 'var(--field)', zIndex: 9998 });
        document.body.append(backdrop);
        const box = document.createElement('section');
        box.className = 'control-section sheet';
        box.id = 'docs-shot-target';
        Object.assign(box.style, { position: 'fixed', left: '24px', top: '24px', width: '600px', zIndex: 9999 });
        for (const id of ['value-scale', 'zeros']) {
          box.append(document.querySelector('label[for="' + id + '"]').cloneNode(true));
          const menu = document.getElementById(id).cloneNode(true);
          menu.id = id + '-shot'; menu.size = menu.options.length; menu.style.width = '100%';
          menu.disabled = document.getElementById(id).disabled;
          box.append(menu);
        }
        document.getElementById('value-scale').closest('section').after(box);
        return true; })()`);
      return { numbers: [], size: await page.shoot('#docs-shot-target', this.file) };
    },
  },
  {
    file: 'popup-branch.webp',
    site: 'branch',
    shows: 'The Atlas page on the branch, not live: the pop-up that opens as a protein file is chosen, here the repository\'s example file.',
    async take(page, base) {
      await page.goto(`${base}/atlas.html`);
      await openDataTab(page);
      const { root } = await page.send('DOM.getDocument', { depth: 1 });
      const { nodeId } = await page.send('DOM.querySelector', { nodeId: root.nodeId, selector: '#matrix' });
      await page.send('DOM.setFileInputFiles', { nodeId, files: [EXAMPLE] });
      await page.until(`document.getElementById('scale-question').open`, 'the pop-up');
      await sleep(600);
      const file = await page.eval(`document.getElementById('scale-question-file').textContent`);
      const facts = await page.eval(`document.getElementById('scale-question-facts').textContent`);
      return {
        text: { file, facts },
        numbers: [{ where: 'the file line and the facts below it',
          from: 'web/js/atlas/file-check.js (checkFile, valueFactsText) and web/js/atlas/scale-question.js (questionFile), on web/data/examples/pbmc240_proteins_raw.tsv' }],
        size: await page.shoot('#scale-question', this.file),
      };
    },
  },
];

async function main() {
  mkdirSync(OUT, { recursive: true });
  const branch = await serve(fromTree);
  const live = await serve(fromCommit(LIVE_SITE));
  const profile = mkdtempSync(join(tmpdir(), 'docs-shots-'));
  const port = 9300 + Math.floor(Math.random() * 500);
  const browser = spawn(browserPath(), ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', `--window-size=${WIDTH},${HEIGHT}`, 'about:blank'],
  { stdio: 'ignore' });
  const entries = [];
  try {
    for (let i = 0; ; i += 1) {
      try { await fetch(`http://127.0.0.1:${port}/json/version`); break; } catch { if (i > 60) throw new Error('the browser did not start'); await sleep(250); }
    }
    for (const shot of SHOTS) {
      const page = await Page.open(port);
      await page.send('Page.enable');
      await page.send('Runtime.enable');
      await page.send('DOM.enable');
      await page.send('Emulation.setDeviceMetricsOverride', { width: WIDTH, height: HEIGHT, deviceScaleFactor: SCALE, mobile: false });
      await page.send('Emulation.setEmulatedMedia', { features: [
        { name: 'prefers-reduced-motion', value: 'reduce' }, { name: 'prefers-color-scheme', value: 'light' }] });
      const server = shot.site === 'live' ? live : branch;
      const base = `http://127.0.0.1:${server.address().port}`;
      const got = await shot.take(page, base);
      entries.push({ file: shot.file, site: shot.site, commit: shot.site === 'live' ? LIVE_SITE : 'the working tree',
        shows: shot.shows, width: got.size.width, height: got.size.height, scale: SCALE,
        ...(got.text ? { text: got.text } : {}), numbers: got.numbers });
      page.ws.close();
      console.log(`wrote web/img/docs/${shot.file} (${shot.site})`);
    }
  } finally {
    browser.kill();
    branch.close();
    live.close();
    await sleep(500);
    try { rmSync(profile, { recursive: true, force: true }); } catch { /* the browser may still hold it */ }
  }
  const index = { about: 'The Docs section\'s screenshots, written by scripts/docs_screenshots.mjs. Pictures for the page, never a check of it.',
    live_site: LIVE_SITE, shots: entries };
  writeFileSync(join(OUT, 'index.json'), `${JSON.stringify(index, null, 1)}\n`);
  console.log('wrote web/img/docs/index.json');
}

if (import.meta.url === `file:///${process.argv[1].replace(/\\/g, '/')}` || process.argv[1]?.endsWith('docs_screenshots.mjs')) {
  await main();
}
