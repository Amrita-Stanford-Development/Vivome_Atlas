import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The site header and footer are static markup copied into every page (no JS
// injection, so no layout shift and they work without JS). This pins the
// copies together: after removing the one aria-current marker, every page's
// header and footer must be byte-identical to home.html's.
const PAGES = ['home.html', 'atlas.html', 'benchmark.html', 'project.html', 'versions.html'];
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
    assert.deepEqual(current, [page], `${page} marks ${JSON.stringify(current)} as current`);
  }
});
