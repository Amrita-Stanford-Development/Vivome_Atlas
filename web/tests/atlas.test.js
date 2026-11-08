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
    'rna-toggle', 'names-toggle', 'dim-slider', 'size-slider', 'cell-type-filters']) {
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

test('the file’s card has a note for how the values were read, under its first line', () => {
  const card = html.slice(html.indexOf('id="results-card"'), html.indexOf('id="data-setup"'));
  assert.match(card, /<p class="panel-note" id="results-note"><\/p>\s*<p class="panel-note atlas-scale-note" id="results-scale-note" hidden><\/p>/);
  const tab = read('js/atlas/data-tab.js');
  assert.match(tab, /const note = run \? scaleNote\(run\.receipt\) : null;/);
  assert.match(tab, /\$\('results-scale-note'\)\.hidden = !shown \|\| !note;/);
});

test('the page asks how the values are written', () => {
  const dialog = html.match(/<dialog id="scale-question"[^>]*>[\s\S]*?<\/dialog>/)?.[0];
  assert.ok(dialog, 'a native dialog');
  assert.ok(html.indexOf(dialog) > html.indexOf('</main>') && html.indexOf(dialog) < html.indexOf('</body>'), 'after main, before </body>');
  assert.match(dialog, /^<dialog id="scale-question" class="[^"]+" aria-labelledby="scale-question-title">/);
  assert.match(dialog, /<h2 id="scale-question-title" tabindex="-1">Are these values raw intensities, or already log\?<\/h2>/);
  assert.match(dialog, /<h2 id="scale-question-zeros-title" tabindex="-1" hidden>What does a 0 mean in this file\?<\/h2>/);
  assert.match(dialog, /<button type="button" class="drawer-close" id="scale-question-close" aria-label="Close">&times;<\/button>/);
  for (const id of ['scale-question-file', 'scale-question-facts', 'scale-question-readings', 'scale-question-zeros']) {
    assert.match(dialog, new RegExp(`id="${id}"`), id);
  }
  const buttons = (attr) => [...dialog.matchAll(new RegExp(`<button type="button" class="btn btn-quiet" data-${attr}="([a-z]+)">([^<]+)</button>`, 'g'))]
    .map((m) => [m[1], m[2]]);
  assert.deepEqual(buttons('reading'), [
    ['linear', 'Raw intensities: the service takes log2'],
    ['log', 'Already log: used as they are'],
    ['auto', "I don't know: the service checks the numbers"],
  ]);
  assert.deepEqual(buttons('zeros'), [
    ['missing', 'Not measured: the protein was not seen'],
    ['measured', 'Measured: a 0 is a real value'],
    ['auto', "I don't know: the service decides"],
  ]);
  assert.doesNotMatch(dialog, /autofocus/, 'no answer chosen in advance');
  const words = dialog.replace(/<[^>]+>/g, ' ');
  assert.ok(!words.includes('—'), 'no em dash');
  for (const word of [/calibrated/i, /state of the art/i, /\bdeployed\b/i]) assert.ok(!word.test(words), `banned: ${word}`);
  assert.doesNotMatch(words, /\d{2,}/, 'no rule constant: the facts are the file’s own');

  // The menus stay the one place the choice lives.
  const options = (id) => [...html.match(new RegExp(`<select id="${id}"[\\s\\S]*?</select>`))[0]
    .matchAll(/<option value="([a-z]+)">([^<]+)<\/option>/g)].map((m) => [m[1], m[2]]);
  assert.deepEqual(options('value-scale'), [
    ['auto', "I don't know: the service checks the numbers"],
    ['linear', 'Raw intensities: the service takes log2'],
    ['log', 'Already log: used as they are'],
  ]);
  assert.deepEqual(options('zeros'), [
    ['auto', "I don't know: a 0 is not measured, unless the values are centred"],
    ['missing', 'Not measured: a 0 means the protein was not seen'],
    ['measured', 'Measured: a 0 is a real value'],
  ]);
  assert.ok(!main.includes('Automatic'), 'Automatic is renamed');

  // Asked when the visitor chooses a file: never for the example.
  const tab = read('js/atlas/data-tab.js');
  assert.match(tab, /const modalityMenu = \$\('modality'\);/);
  assert.match(tab, /if \(asksScale\(\{ modality: modalityMenu\.value, check \}\)\) ask\(check\);/);
  assert.equal((tab.match(/\bchoose\(file\)/g) ?? []).length, 2, 'the picker and the drop');
  assert.doesNotMatch(read('js/atlas/landing.js'), /scale-question|asksScale/);
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

test('the blood map is the RNA reference alone: SCoPE2\'s protein cells are a Manuscript result, not on the map', () => {
  const html = readFileSync(new URL('../atlas.html', import.meta.url), 'utf8');
  for (const gone of ['prot-toggle', 'prot-well', 'prot-count', 'SCoPE2']) assert.ok(!html.includes(gone), gone);
  const main = readFileSync(new URL('../js/atlas/main.js', import.meta.url), 'utf8');
  assert.doesNotMatch(main, /metadata_PROT_lat128/, 'the map does not load the protein layer');
  assert.doesNotMatch(main, /isProt/);
  const explore = readFileSync(new URL('../js/atlas/explore-tab.js', import.meta.url), 'utf8');
  assert.doesNotMatch(explore, /prot-count|'prot'\]/);
});

test('restricted mode is retired: no option on the page, and the request does not ask for it', () => {
  const html = readFileSync(new URL('../atlas.html', import.meta.url), 'utf8');
  assert.ok(!html.includes('id="restrict"'));
  const landing = readFileSync(new URL('../js/atlas/landing.js', import.meta.url), 'utf8');
  assert.doesNotMatch(landing, /restrict_to_supported_classes/);
});

test('at high zoom the Atlas page scrolls and its controls sit above the viewer', () => {
  const css = readFileSync(new URL('../css/atlas.css', import.meta.url), 'utf8');
  const narrow = css.slice(css.indexOf('@media (max-width: 720px)'));
  const block = narrow.slice(0, narrow.indexOf('\n}\n'));
  assert.ok(block.length > 0, 'a narrow layout exists');
  assert.match(block, /body\.atlas-page \{ height: auto; overflow: visible; \}/);
  assert.match(block, /\.main-content \{ flex-direction: column; \}/);
  assert.match(block, /\.controls-panel \{ width: auto; overflow: visible;/);
});
