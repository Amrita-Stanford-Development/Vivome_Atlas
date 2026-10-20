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
  // A class that sets display must not unhide what the page hides (the
  // drop hint once stayed on the map).
  assert.match(read('css/atlas.css'), /\.atlas-page \[hidden\] \{ display: none !important; \}/);
  for (const id of ['tab-explore', 'tab-data', 'panel-explore', 'panel-data', 'your-data', 'labels', 'status-card', 'legend-card', 'skip', 'atlas-drawer']) {
    assert.match(html, new RegExp(`id="${id}"`), id);
  }
  // The service sends no progress: the waiting animation says it is an illustration.
  const landing = read('js/atlas/landing.js');
  assert.match(landing, />Illustration</);
  assert.match(landing, /It shows the steps the service runs, not its progress\./);
});

test('Explore holds the view controls; the research panels live on the Manuscript page', () => {
  const explore = html.slice(html.indexOf('id="panel-explore"'), html.indexOf('id="panel-data"'));
  for (const id of ['your-cells', 'cells-toggle', 'explore-chips', 'types-given', 'given-all', 'given-none', 'highlight-toggle',
    'rna-toggle', 'prot-toggle', 'names-toggle', 'dim-slider', 'size-slider', 'cell-type-filters']) {
    assert.match(explore, new RegExp(`id="${id}"`), id);
  }
  assert.match(explore, /<section class="control-section sheet" id="your-cells" hidden>/, 'shown only with an answer');
  for (const gone of ['support-tiles', 'support-table-mount', 'diagnostics-mount']) assert.ok(!html.includes(gone), gone);
  assert.ok(!/buildSupport|buildDiagnostics/.test(read('js/atlas/explore-tab.js')));
});

test('the map has a step bar for going through the cells one by one', () => {
  assert.match(html, /<div class="step-bar glass" id="step-bar" role="group" aria-label="Your cells, one by one" hidden>/);
  for (const id of ['step-prev', 'step-text', 'step-next', 'step-play']) assert.match(html, new RegExp(`id="${id}"`), id);
  assert.match(html, /id="step-prev" aria-label="Previous cell"/);
  assert.match(html, /id="step-next" aria-label="Next cell"/);
});

test('with an answer on the map, Your data is the file’s card above the setup', () => {
  const data = html.slice(html.indexOf('id="panel-data"'));
  const card = data.indexOf('id="results-card"');
  const setup = data.indexOf('id="data-setup"');
  assert.ok(card > 0 && setup > card, 'the card comes first');
  for (const id of ['send-another', 'open-results', 'replay', 'download', 'clear', 'labels-fold']) assert.match(data, new RegExp(`id="${id}"`), id);
  // The rarely used parts fold away.
  assert.match(data, /<details class="fold" id="labels-fold">/);
  assert.match(data, /<details class="fold own-copy">/);
  const tab = read('js/atlas/data-tab.js');
  assert.match(tab, /\$\('data-setup'\)\.hidden = shown && !setupWanted/);
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

test('hidden panels on the Atlas page are inert, and hovering the map is not announced', () => {
  const html = readFileSync(new URL('../atlas.html', import.meta.url), 'utf8');
  assert.match(html, /<aside class="atlas-drawer sheet" id="atlas-drawer" inert /, 'the closed drawer takes no focus');
  assert.doesNotMatch(html, /id="tooltip" role="status"/, 'a hover name is not read out on every move');
  const main = readFileSync(new URL('../js/atlas/main.js', import.meta.url), 'utf8');
  assert.match(main, /drawer\.inert = true/);
  assert.match(main, /drawer\.inert = false/);
  assert.match(main, /panel\.inert = !open/, 'a folded sidebar takes no focus');
});

test('the status card is not read out on every tick; a status line says each step once', () => {
  const html = readFileSync(new URL('../atlas.html', import.meta.url), 'utf8');
  assert.match(html, /<div class="status-card glass" id="status-card" hidden><\/div>/);
  assert.match(html, /<p class="visually-hidden" id="status-line" role="status"><\/p>/);
});

test('the step bar\'s Play button says what it will do, not also whether it is pressed', () => {
  const html = readFileSync(new URL('../atlas.html', import.meta.url), 'utf8');
  assert.match(html, /<button type="button" id="step-play">Play<\/button>/);
  const landing = readFileSync(new URL('../js/atlas/landing.js', import.meta.url), 'utf8');
  assert.doesNotMatch(landing, /\$\('step-play'\)\.setAttribute\('aria-pressed'/);
});

test('the panel\'s tabs take Home and End as well as the arrows', () => {
  const main = readFileSync(new URL('../js/atlas/main.js', import.meta.url), 'utf8');
  const handler = main.slice(main.indexOf("querySelector('[role=\"tablist\"]').addEventListener('keydown'"));
  assert.match(handler.slice(0, 900), /Home: 'explore', End: 'data'/);
  assert.match(handler.slice(0, 900), /e\.preventDefault\(\)/, 'Home and End do not also scroll the page');
});

