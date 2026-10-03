import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The site header and footer are static markup copied into every page (no JS
// injection, so no layout shift and they work without JS). This pins the
// copies together: after removing the one aria-current marker, every page's
// header and footer must be byte-identical to home.html's.
const PAGES = ['index.html', 'home.html', 'atlas.html', 'benchmark.html', 'project.html', 'versions.html'];
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
    const canonical = block(read('home.html'), tag, cls);
    assert.ok(canonical, `home.html has no ${cls}`);
    for (const page of PAGES) {
      if (tag === 'footer' && WITHOUT_FOOTER.has(page)) continue;
      const copy = block(read(page), tag, cls);
      assert.ok(copy, `${page} has no ${cls}`);
      assert.equal(normalise(copy), normalise(canonical), `${page}'s ${cls} differs from home.html's`);
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

// The landing story and the living water behind every page load three.js
// themselves; both must load the build the atlas viewer uses, so the site
// never ships two versions and the cache is shared.
test('the story, the living water and the atlas load the same three.js', () => {
  const fromAtlas = read('atlas.html').match(/<script src="(https:[^"]*three[^"]*)"/);
  assert.ok(fromAtlas, 'three.js URL not found in atlas.html');
  for (const module of ['story.js', 'biofield.js']) {
    const url = readFileSync(new URL(`../js/${module}`, import.meta.url), 'utf8').match(/THREE_URL = '([^']+)'/);
    assert.ok(url, `three.js URL not found in js/${module}`);
    assert.equal(url[1], fromAtlas[1], `js/${module} loads a different three.js`);
  }
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
