// The Atlas page (web/atlas.html and web/js/atlas/): its markup, its copy
// and the rules its modules keep.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const html = read('atlas.html');
const main = html.match(/<main[\s\S]*<\/main>/)[0];
const visible = main.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
const modules = readdirSync(new URL('../js/atlas/', import.meta.url)).filter((f) => f.endsWith('.js'));

test('the page is markup: its code is the atlas modules', () => {
  assert.match(html, /<script type="module" src="js\/atlas\/main\.js"><\/script>/);
  const inline = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>/g)];
  assert.deepEqual(inline, [], 'no inline script');
  assert.ok(!/papaparse/i.test(html), 'the CSVs are read by reference-data.js');
  assert.ok(!html.includes('biofield.js'), 'the viewer covers the window, so no living water');
  assert.equal((html.match(/<h1[\s>]/g) ?? []).length, 1, 'exactly one h1');
  assert.ok(modules.length >= 9, modules.join(', '));
});

test('the page keeps the copy rules', () => {
  assert.ok(!main.includes('—'), 'no em dash');
  for (const word of [/calibrated/i, /beats scanvi/i, /state of the art/i, /99%/, /every ome/i, /\bdeployed\b/i]) {
    assert.ok(!word.test(visible), `banned: ${word}`);
  }
  for (const f of modules) {
    const strings = [...read(`js/atlas/${f}`).matchAll(/'[^'\n]*'|`[^`]*`/g)].map((m) => m[0]).join(' ');
    assert.ok(!strings.includes('—'), `${f}: an em dash in its text`);
    for (const word of [/calibrated/i, /state of the art/i, /\bdeployed\b/i]) assert.ok(!word.test(strings), `${f}: ${word}`);
  }
});

test('the browser computes no model output', () => {
  for (const f of modules) {
    const src = read(`js/atlas/${f}`);
    assert.ok(!/Math\.exp\b/.test(src), `${f} calls Math.exp`);
    assert.ok(!/softmax\(/.test(src), `${f} computes a softmax`);
  }
});
