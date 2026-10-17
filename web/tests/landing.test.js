// The landing (web/index.html): checks no other test makes, so a typo can't
// quietly show Pending.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { factText } from '../js/panels.js';
import { manifestFixture } from './fixtures.js';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const main = html.slice(html.indexOf('<main'), html.indexOf('</main>'));

test('every fact the landing asks for exists', () => {
  const keys = [...new Set([...main.matchAll(/data-fact="([^"]+)"/g)].map((m) => m[1]))];
  assert.ok(keys.length > 10);
  // An unknown key renders Pending even with a full manifest.
  const real = JSON.parse(readFileSync(new URL('../data/atlas_manifest.json', import.meta.url), 'utf8'));
  for (const key of keys) assert.doesNotMatch(factText(real, key), /Pending/, `data-fact="${key}"`);
});

test('the copy follows the site rules: no em dashes, none of the words that wait for evidence', () => {
  const text = main.replace(/<[^>]+>/g, ' ');
  assert.ok(!text.includes('—'), 'em dash');
  for (const word of [/calibrated/i, /beats scanvi/i, /state of the art/i, /\bdeployed\b/i, /\bhosted\b/i, /every ome/i]) {
    assert.doesNotMatch(text, word);
  }
});

test('the finale has its proof points slot, and the page one h1', () => {
  assert.match(main, /id="proof-points"/);
  assert.equal((html.match(/<h1\b/g) ?? []).length, 1);
});

test('nothing is drawn in front of the title: no hero canvas, no hero script', () => {
  assert.ok(!html.includes('hero-canvas'));
  assert.ok(!html.includes('hero.js'));
});

test('the fixture manifest still renders the landing facts it has', () => {
  assert.equal(factText(manifestFixture(), 'rna_cells'), '85,233');
});
