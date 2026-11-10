// The question the Atlas page asks about a protein file's values
// (web/js/atlas/scale-question.js), and its pop-up wired by the Your data
// tab (web/js/atlas/data-tab.js) on a stand-in page: when it opens, its two
// steps, Escape and the close button, and the menus it sets.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { asksScale, asksZeros, menuChoice, questionFile } from '../js/atlas/scale-question.js';

const ok = (values = { entries: 12, empty: 2, zeros: 3, negatives: 0, min: 0, max: 30000 }) => ({
  ok: true, problems: [], name: 'cells.tsv', size: 2048, features: 3100, cells: 238, values,
});

test('asksScale: only a protein file whose check passed', () => {
  assert.equal(asksScale({ modality: 'prot', check: ok() }), true);
  assert.equal(asksScale({ modality: 'rna', check: ok() }), false, 'RNA is read by the service, never asked');
  assert.equal(asksScale({ modality: 'prot', check: null }), false, 'a check overtaken by another file');
  assert.equal(asksScale({ modality: 'prot', check: undefined }), false);
  assert.equal(asksScale({ modality: 'prot', check: { ...ok(), ok: false } }), false, 'a file that cannot be sent');
  assert.equal(asksScale({ modality: 'prot', check: { ...ok(), ok: 'true' } }), false);
  assert.equal(asksScale({ modality: 'prot', check: 1 }), false);
  assert.equal(asksScale({}), false);
});

test('asksZeros: only a file with a 0', () => {
  assert.equal(asksZeros(ok()), true);
  assert.equal(asksZeros(ok({ entries: 12, empty: 0, zeros: 0, negatives: 0, min: 1, max: 9 })), false);
  assert.equal(asksZeros({ ...ok(), values: null }), false);
  assert.equal(asksZeros({ name: 'x' }), false);
  assert.equal(asksZeros(null), false);
});

test('menuChoice: what the menus are set to, a 0 kept only with Already log', () => {
  assert.deepEqual(menuChoice('log', 'missing'), { valueScale: 'log', zeros: 'missing' });
  assert.deepEqual(menuChoice('log', 'measured'), { valueScale: 'log', zeros: 'measured' });
  assert.deepEqual(menuChoice('log'), { valueScale: 'log', zeros: 'auto' });
  assert.deepEqual(menuChoice('log', '<b>x</b>'), { valueScale: 'log', zeros: 'auto' });
  assert.deepEqual(menuChoice('linear', 'missing'), { valueScale: 'linear', zeros: 'auto' });
  assert.deepEqual(menuChoice('auto', 'measured'), { valueScale: 'auto', zeros: 'auto' });
  assert.deepEqual(menuChoice('x'), { valueScale: 'auto', zeros: 'auto' });
  assert.deepEqual(menuChoice(undefined), { valueScale: 'auto', zeros: 'auto' });
});

test('questionFile: the file as its check found it', () => {
  assert.equal(questionFile(ok()), 'cells.tsv: 3,100 feature rows, 238 cells');
  assert.equal(questionFile({ ...ok(), features: 1, cells: 1 }), 'cells.tsv: 1 feature row, 1 cell');
});

test('the question is pure: no page, no numbers of its own', () => {
  const src = readFileSync(new URL('../js/atlas/scale-question.js', import.meta.url), 'utf8');
  assert.doesNotMatch(src, /\b(document|window|localStorage)\b/);
  assert.doesNotMatch(src.replace(/\/\/.*$/gm, ''), /\b(?:[2-9]|\d{2,})\b/, 'no rule constant such as 20 columns');
});

// ---- the pop-up on a stand-in page ----

function fakePage() {
  const els = new Map();
  const focused = [];
  const make = (id) => ({
    id, handlers: {}, hidden: false, disabled: false, value: '', title: '', innerHTML: '', textContent: '', files: [],
    dataset: {}, attrs: {}, classList: { toggle() {}, add() {}, remove() {} },
    addEventListener(type, f) { (this.handlers[type] ??= []).push(f); },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return this.attrs[k] ?? null; },
    contains: () => false,
    focus() { focused.push(id); },
  });
  const get = (id) => {
    if (!els.has(id)) els.set(id, make(id));
    return els.get(id);
  };
  const dialog = get('scale-question');
  Object.assign(dialog, {
    open: false, opened: 0,
    showModal() { this.open = true; this.opened += 1; },
    close() { this.open = false; (this.handlers.close ?? []).forEach((f) => f({})); },
  });
  return { els, get, focused, document: { getElementById: get, querySelectorAll: () => [] } };
}

const fire = (el, type, event = {}) => (el.handlers[type] ?? []).forEach((f) => f(event));
// A click on a button inside the pop-up: what it matches, as closest() finds it.
const clickOn = (attrs) => ({
  target: {
    closest: (sel) => {
      if (sel === '#scale-question-close') return attrs.close ? {} : null;
      if (sel === '[data-reading]') return attrs.reading ? { dataset: { reading: attrs.reading } } : null;
      if (sel === '[data-zeros]') return attrs.zeros ? { dataset: { zeros: attrs.zeros } } : null;
      return null;
    },
  },
});

async function mounted({ check = ok(), modality = 'prot' } = {}) {
  const { mountDataTab } = await import('../js/atlas/data-tab.js');
  const page = fakePage();
  const saved = globalThis.document;
  globalThis.document = page.document;
  const calls = { optionsChanged: 0, chosen: [] };
  const landing = {
    state: { name: 'chosen', check, file: { name: 'cells.tsv' } }, run: null, onChange() {}, chips: () => '',
    chooseFile: async (file) => { calls.chosen.push(file); return check; },
    optionsChanged: () => { calls.optionsChanged += 1; },
  };
  const service = { state: { ready: true, limits: null }, url: () => '', limits: () => ({}) };
  mountDataTab({ landing, client: {}, service });
  page.get('modality').value = modality;
  page.get('value-scale').value = 'auto';
  page.get('zeros').value = 'auto';
  const restore = () => { globalThis.document = saved; };
  // The picker: a file chosen, then its check.
  const pick = async () => {
    page.get('matrix').files = [{ name: 'cells.tsv' }];
    fire(page.get('matrix'), 'change');
    await new Promise((done) => setTimeout(done, 0));
  };
  return { page, calls, landing, restore, pick, dialog: page.get('scale-question') };
}

test('a protein file that passed its check is asked about once, with its own facts', async () => {
  const t = await mounted();
  try {
    await t.pick();
    assert.equal(t.dialog.opened, 1);
    assert.equal(t.page.get('scale-question-file').textContent, 'cells.tsv: 3,100 feature rows, 238 cells');
    assert.equal(t.page.get('scale-question-facts').textContent, 'From 0 to 30,000; 25.0% are 0 and 16.7% are empty; none is negative.');
    assert.equal(t.page.get('scale-question-readings').hidden, false);
    assert.equal(t.page.get('scale-question-zeros').hidden, true);
    assert.equal(t.dialog.getAttribute('aria-labelledby'), 'scale-question-title');
    assert.equal(t.page.focused.at(-1), 'scale-question-title', 'focus on the question, no answer chosen in advance');
    assert.equal(t.calls.optionsChanged, 0, 'nothing set until it is answered');
  } finally { t.restore(); }
});

test('Raw intensities sets the menus and closes; focus goes to Send', async () => {
  const t = await mounted();
  try {
    await t.pick();
    fire(t.dialog, 'click', clickOn({ reading: 'linear' }));
    assert.equal(t.dialog.open, false);
    assert.equal(t.page.get('value-scale').value, 'linear');
    assert.equal(t.page.get('zeros').value, 'auto');
    assert.equal(t.calls.optionsChanged, 1);
    assert.equal(t.page.focused.at(-1), 'project');
  } finally { t.restore(); }
});

test('Already log asks what a 0 means when the file has one, and both answers are set', async () => {
  const t = await mounted();
  try {
    await t.pick();
    fire(t.dialog, 'click', clickOn({ reading: 'log' }));
    assert.equal(t.dialog.open, true, 'the same pop-up asks again');
    assert.equal(t.page.get('scale-question-readings').hidden, true);
    assert.equal(t.page.get('scale-question-zeros').hidden, false);
    assert.equal(t.page.get('scale-question-zeros-title').hidden, false);
    assert.equal(t.dialog.getAttribute('aria-labelledby'), 'scale-question-zeros-title');
    assert.equal(t.page.focused.at(-1), 'scale-question-zeros-title');
    assert.equal(t.calls.optionsChanged, 0);
    fire(t.dialog, 'click', clickOn({ zeros: 'missing' }));
    assert.equal(t.dialog.open, false);
    assert.equal(t.page.get('value-scale').value, 'log');
    assert.equal(t.page.get('zeros').value, 'missing');
    assert.equal(t.calls.optionsChanged, 1);
  } finally { t.restore(); }
});

test('Already log on a file with no 0 closes at once', async () => {
  const t = await mounted({ check: ok({ entries: 12, empty: 0, zeros: 0, negatives: 0, min: 1, max: 9 }) });
  try {
    await t.pick();
    fire(t.dialog, 'click', clickOn({ reading: 'log' }));
    assert.equal(t.dialog.open, false);
    assert.equal(t.page.get('value-scale').value, 'log');
    assert.equal(t.page.get('zeros').value, 'auto');
  } finally { t.restore(); }
});

test('Escape or the close button is I don’t know for the open question; a reading already chosen is kept', async () => {
  let t = await mounted();
  try {
    await t.pick();
    t.page.get('value-scale').value = 'linear'; // the last file's answer
    let prevented = 0;
    fire(t.dialog, 'cancel', { preventDefault: () => { prevented += 1; } });
    assert.equal(t.dialog.open, false);
    assert.equal(t.page.get('value-scale').value, 'auto', 'not the last file’s answer');
    assert.equal(t.calls.optionsChanged, 1);
    assert.equal(prevented, 1);
  } finally { t.restore(); }
  t = await mounted();
  try {
    await t.pick();
    fire(t.dialog, 'click', clickOn({ reading: 'log' }));
    fire(t.dialog, 'click', clickOn({ close: true }));
    assert.equal(t.dialog.open, false);
    assert.equal(t.page.get('value-scale').value, 'log');
    assert.equal(t.page.get('zeros').value, 'auto');
    assert.equal(t.calls.optionsChanged, 1, 'set once');
  } finally { t.restore(); }
});

test('the pop-up opens for a picked or dropped protein file only', async () => {
  for (const [opts, why] of [[{ modality: 'rna' }, 'RNA'], [{ check: null }, 'a check overtaken by another file'],
    [{ check: { ...ok(), ok: false, problems: ['too few cells'] } }, 'a file that cannot be sent']]) {
    const t = await mounted(opts);
    try {
      await t.pick();
      assert.equal(t.dialog.opened, 0, why);
    } finally { t.restore(); }
  }
  const t = await mounted();
  try {
    const drop = { dataTransfer: { types: ['Files'], files: [{ name: 'cells.tsv' }] }, preventDefault() {} };
    fire(t.page.get('three-container'), 'drop', drop);
    await new Promise((done) => setTimeout(done, 0));
    assert.equal(t.calls.chosen.length, 1);
    assert.equal(t.dialog.opened, 1, 'a file dropped on the map is asked about too');
  } finally { t.restore(); }
});

test('the pop-up sits in the middle of the window: its own margin undoes the page reset', () => {
  // page.css resets every margin to 0 (@layer base), and an author rule beats
  // the browser's own `dialog:modal { margin: auto }`, which is what centres a
  // modal dialog. Without a margin of its own the pop-up opens in the corner.
  const reset = readFileSync(new URL('../css/page.css', import.meta.url), 'utf8');
  assert.match(reset, /\*\s*\{\s*margin:\s*0;/, 'the reset this test is about');
  const css = readFileSync(new URL('../css/atlas.css', import.meta.url), 'utf8');
  const rule = css.match(/^\.scale-question\s*\{([^}]*)\}/m);
  assert.ok(rule, 'atlas.css styles .scale-question');
  assert.match(rule[1], /(?:^|;|\s)margin:\s*auto;/, 'the dialog sets margin: auto');
});
