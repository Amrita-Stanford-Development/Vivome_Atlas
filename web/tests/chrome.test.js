import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The site header and footer are static markup copied into every page (no JS
// injection, so no layout shift and they work without JS). This pins the
// copies together: after removing the one aria-current marker, every page's
// header and footer must be byte-identical to the landing page's.
const CANONICAL = 'index.html';
const PAGES = ['index.html', 'atlas.html', 'manuscript.html', 'workflow.html', 'motion.html'];
// The atlas is a full-window app view, so it carries the header but no footer.
const WITHOUT_FOOTER = new Set(['atlas.html']);

const read = (page) => readFileSync(new URL(`../${page}`, import.meta.url), 'utf8');
const block = (html, tag, cls) => {
  const match = html.match(new RegExp(`<${tag} class="${cls}[^"]*">[\\s\\S]*?</${tag}>`));
  return match && match[0];
};
const normalise = (html) => html.replace(/ aria-current="page"/g, '');

for (const [tag, cls] of [['header', 'site-header'], ['footer', 'site-footer']]) {
  test(`every page carries the same ${cls}`, () => {
    const canonical = block(read(CANONICAL), tag, cls);
    assert.ok(canonical, `${CANONICAL} has no ${cls}`);
    for (const page of PAGES) {
      if (tag === 'footer' && WITHOUT_FOOTER.has(page)) continue;
      const copy = block(read(page), tag, cls);
      assert.ok(copy, `${page} has no ${cls}`);
      assert.equal(normalise(copy), normalise(canonical), `${page}'s ${cls} differs from ${CANONICAL}'s`);
    }
  });
}

test('each page marks exactly its own nav link as current', () => {
  for (const page of PAGES) {
    const header = block(read(page), 'header', 'site-header');
    const current = [...header.matchAll(/href="([^"]+)"[^>]*aria-current="page"/g)].map((m) => m[1]);
    // The landing is reached from the wordmark, not a nav link.
    const expected = page === 'index.html' ? [] : [page];
    assert.deepEqual(current, expected, `${page} marks ${JSON.stringify(current)} as current`);
  }
});

// The living water behind every page loads three.js itself; it must load the
// build the atlas viewer uses (and the landing preloads), so the site never
// ships two versions and the cache is shared.
test('the living water, the landing and the atlas use the same three.js', () => {
  const fromAtlas = read('atlas.html').match(/<script src="(https:[^"]*three[^"]*)"/);
  assert.ok(fromAtlas, 'three.js URL not found in atlas.html');
  for (const module of ['biofield.js']) {
    const url = readFileSync(new URL(`../js/${module}`, import.meta.url), 'utf8').match(/THREE_URL = '([^']+)'/);
    assert.ok(url, `three.js URL not found in js/${module}`);
    assert.equal(url[1], fromAtlas[1], `js/${module} loads a different three.js`);
  }
  const preload = read('index.html').match(/<link rel="preload" as="script" href="([^"]+)"/);
  assert.ok(preload, 'the landing preloads no script');
  assert.equal(preload[1], fromAtlas[1], 'the landing preloads a different three.js');
});

// Every page but the atlas (whose viewer covers the window) carries the
// living water, after the field it lies on.
test('the living water is behind every page but the atlas', () => {
  for (const page of PAGES) {
    const html = read(page);
    const field = html.indexOf('src="js/background.js"');
    const water = html.indexOf('src="js/biofield.js"');
    assert.ok(field > 0, `${page} has no background.js`);
    if (page === 'atlas.html') assert.equal(water, -1, 'atlas.html should not load the living water');
    else assert.ok(water > field, `${page} should load js/biofield.js after js/background.js`);
  }
});

test('no page hides a control from screen readers while it can still take focus', () => {
  const focusable = /<(button|input|select|textarea|summary)\b|<a\s[^>]*href=/;
  for (const page of ['index.html', 'atlas.html', 'manuscript.html', 'workflow.html', 'motion.html']) {
    const html = read(page);
    for (const m of html.matchAll(/<([a-z0-9]+)\b[^>]*\baria-hidden="true"[^>]*>/g)) {
      let depth = 1;
      let i = m.index + m[0].length;
      while (depth > 0) {
        const open = html.indexOf(`<${m[1]}`, i);
        const close = html.indexOf(`</${m[1]}>`, i);
        if (close < 0) break;
        if (open >= 0 && open < close) { depth += 1; i = open + 1; } else { depth -= 1; i = close + 1; }
      }
      assert.doesNotMatch(html.slice(m.index, i), focusable, `${page}: ${m[0].slice(0, 60)}`);
    }
  }
});

test('a page-level error, written when a load fails, is announced', () => {
  for (const [page, id] of [['manuscript.html', 'ms-error'], ['motion.html', 'reel-error'], ['workflow.html', 'sync-banner']]) {
    assert.match(read(page), new RegExp(`<div id="${id}" role="alert"></div>`), page);
  }
});
