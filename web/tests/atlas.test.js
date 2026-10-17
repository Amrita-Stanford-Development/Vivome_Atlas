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

test('the page has its two tabs, the labels section old links arrive at, and a labelled illustration', () => {
  for (const id of ['tab-explore', 'tab-data', 'panel-explore', 'panel-data', 'your-data', 'labels', 'status-card', 'legend-card', 'skip', 'atlas-drawer']) {
    assert.match(html, new RegExp(`id="${id}"`), id);
  }
  // The service sends no progress: the waiting animation says it is an illustration.
  const landing = read('js/atlas/landing.js');
  assert.match(landing, />Illustration</);
  assert.match(landing, /It shows the steps the service runs, not its progress\./);
});

test('every number slot on the Your data tab has a measured record', async () => {
  const { wfFact } = await import('../js/workflow-data.js');
  const workflow = JSON.parse(read('data/workflow.json'));
  const slots = [...html.matchAll(/data-wf="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(slots.length >= 2);
  for (const key of slots) assert.ok(!/Pending/.test(wfFact(workflow, key)), key);
});

test('the browser computes no model output', () => {
  for (const f of modules) {
    const src = read(`js/atlas/${f}`);
    assert.ok(!/Math\.exp\b/.test(src), `${f} calls Math.exp`);
    assert.ok(!/softmax\(/.test(src), `${f} computes a softmax`);
  }
});
