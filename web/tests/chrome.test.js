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

// The landing story loads three.js itself; it must be the build the atlas
// viewer uses, so the site never ships two versions and the cache is shared.
test('the story and the atlas load the same three.js', () => {
  const fromAtlas = read('atlas.html').match(/<script src="(https:[^"]*three[^"]*)"/);
  const fromStory = readFileSync(new URL('../js/story.js', import.meta.url), 'utf8').match(/THREE_URL = '([^']+)'/);
  assert.ok(fromAtlas && fromStory, 'three.js URL not found in atlas.html or js/story.js');
  assert.equal(fromStory[1], fromAtlas[1]);
});
