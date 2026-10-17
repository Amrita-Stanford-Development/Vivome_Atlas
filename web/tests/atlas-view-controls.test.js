// The Atlas page's view controls (web/js/atlas/view-controls.js), on
// stand-ins for the page, the landing, the reference layer, the stage and
// the names: the Your cells section appears only with an answer on the map,
// and every control asks the right part of the page.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CELLS_ON_MAP, buildTypesGiven, dimPercent, mountViewControls } from '../js/atlas/view-controls.js';

class El {
  constructor(id) {
    this.id = id;
    this.innerHTML = '';
    this.textContent = '';
    this.hidden = false;
    this.value = '';
    this.listeners = {};
    this.attrs = {};
    const classes = new Set();
    this.classList = {
      contains: (c) => classes.has(c),
      toggle: (c, on) => ((on ?? !classes.has(c)) ? classes.add(c) : classes.delete(c)),
    };
  }
  addEventListener(type, f) { (this.listeners[type] ??= []).push(f); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k] ?? null; }
  fire(type, event = {}) { (this.listeners[type] ?? []).forEach((f) => f(event)); }
}

function setup() {
  const els = new Map();
  globalThis.document = {
    getElementById: (id) => {
      if (!els.has(id)) els.set(id, new El(id));
      return els.get(id);
    },
    activeElement: null,
  };
  els.set('dim-slider', Object.assign(new El('dim-slider'), { value: '0' }));
  els.set('size-slider', Object.assign(new El('size-slider'), { value: '100' }));
  const calls = [];
  const listeners = [];
  const landing = {
    state: { name: 'idle' },
    run: null,
    cellsShown: true,
    onChange: (f) => listeners.push(f),
    setCellsShown(on) { calls.push(['cells', on]); landing.cellsShown = on; listeners.forEach((f) => f(landing.state, landing.run)); },
    setOutcomeOn(outcome, on) { calls.push(['outcome', outcome, on]); },
    chips: () => '<button data-outcome="class" aria-pressed="true"></button>',
    groups: () => [
      { key: 'group:T cell', name: 'T cell (a family)', look: 'group', colour: null, count: 42, on: true },
      { key: 'class:natural killer cell', name: 'NK cell', look: 'class', colour: '#123456', count: 3, on: false },
    ],
    highlight: true,
    setHighlight(on) { calls.push(['highlight', on]); landing.highlight = on; },
    setGroupOn(key, on) { calls.push(['group', key, on]); },
    showOnlyGroup(key) { calls.push(['only', key]); },
    setAllGroups(on) { calls.push(['all', on]); },
  };
  const layer = { dim: 0, setDim(v) { layer.dim = v; calls.push(['dim', v]); } };
  const stage = { setDotScale: (s) => calls.push(['size', s]) };
  const labels = { on: false, setOn(on) { labels.on = on; calls.push(['names', on]); } };
  mountViewControls({ stage, layer, landing, labels });
  const change = () => listeners.forEach((f) => f(landing.state, landing.run));
  return { els, landing, layer, calls, change };
}

test('the dimming slider shows the dimming in its own steps', () => {
  assert.equal(dimPercent(0), '0');
  assert.equal(dimPercent(0.6), '60');
  assert.equal(dimPercent(0.62), '60');
  assert.equal(dimPercent(2), '90');
  assert.equal(dimPercent(undefined), '0');
});

test('your cells appear in Explore only while an answer is on the map', () => {
  const { els, landing, change } = setup();
  assert.equal(els.get('your-cells').hidden, true, 'nothing sent yet');
  landing.state = { name: 'working' };
  change();
  assert.equal(els.get('your-cells').hidden, true, 'still waiting');
  landing.run = { source: 'service', cells: new Array(216) };
  landing.state = { name: 'interactive', file: { name: 'simulated.tsv' } };
  change();
  assert.equal(els.get('your-cells').hidden, false);
  assert.equal(els.get('your-cells-note').textContent, '216 cells from simulated.tsv.');
  assert.match(els.get('explore-chips').innerHTML, /data-outcome/);
  assert.equal(els.get('cells-toggle').getAttribute('aria-checked'), 'true');
  landing.run = { source: 'recorded', cells: new Array(238) };
  change();
  assert.equal(els.get('your-cells-note').textContent, 'The recorded example: 238 cells.');
  for (const name of CELLS_ON_MAP) {
    landing.state = { name };
    change();
    assert.equal(els.get('your-cells').hidden, false, name);
  }
});

test('each control asks the right part of the page', () => {
  const { els, landing, calls, change } = setup();
  landing.run = { source: 'service', cells: [] };
  landing.state = { name: 'interactive' };
  change();
  els.get('cells-toggle').fire('click');
  assert.deepEqual(calls.at(-1), ['cells', false]);
  assert.equal(els.get('cells-toggle').getAttribute('aria-checked'), 'false', 'the switch follows');
  const chip = { dataset: { outcome: 'lineage' }, getAttribute: () => 'true' };
  els.get('explore-chips').fire('click', { target: { closest: () => chip } });
  assert.deepEqual(calls.at(-1), ['outcome', 'lineage', false]);
  els.get('names-toggle').fire('click');
  assert.deepEqual(calls.at(-1), ['names', true]);
  assert.equal(els.get('names-toggle').getAttribute('aria-checked'), 'true');
  els.get('dim-slider').value = '40';
  els.get('dim-slider').fire('input');
  assert.deepEqual(calls.at(-1), ['dim', 0.4]);
  assert.equal(els.get('dim-value').textContent, '40%');
  els.get('size-slider').value = '150';
  els.get('size-slider').fire('input');
  assert.deepEqual(calls.at(-1), ['size', 1.5]);
  assert.equal(els.get('size-value').textContent, '150%');
});

test('the dimming slider follows the dimming the landing sets', () => {
  const { els, layer, change } = setup();
  layer.dim = 0.6;
  change();
  assert.equal(els.get('dim-slider').value, '60');
  assert.equal(els.get('dim-value').textContent, '60%');
  // Not while the visitor is dragging it.
  globalThis.document.activeElement = els.get('dim-slider');
  layer.dim = 0;
  change();
  assert.equal(els.get('dim-slider').value, '60');
});

test('the types given: one row each, with a colour or the answer’s look, its count and Only', () => {
  const html = buildTypesGiven([
    { key: 'group:T cell', name: 'T cell (a family)', look: 'group', colour: null, count: 42, on: true },
    { key: 'class:<script>x</script>', name: '<script>x</script>', look: 'class', colour: '#123456', count: 1234, on: false },
  ]);
  assert.equal((html.match(/class="given-row/g) ?? []).length, 2);
  assert.match(html, /data-given="group:T cell" aria-pressed="true"/);
  assert.match(html, /<svg/, 'a family wears its look');
  assert.match(html, /background:#123456/, 'a type wears its colour');
  assert.match(html, /class="given-row is-off"/);
  assert.match(html, /1,234/);
  assert.ok(!html.includes('<script>'), 'names are escaped');
  assert.equal(buildTypesGiven([]), '');
});

test('the types given and the highlight switch ask the landing', () => {
  const { els, landing, calls, change } = setup();
  landing.run = { source: 'service', cells: [] };
  landing.state = { name: 'interactive' };
  change();
  assert.match(els.get('types-given').innerHTML, /T cell \(a family\)/);
  assert.equal(els.get('highlight-toggle').getAttribute('aria-checked'), 'true');
  const row = { dataset: { given: 'group:T cell' }, getAttribute: () => 'true' };
  els.get('types-given').fire('click', { target: { closest: (sel) => (sel === '[data-given]' ? row : null) } });
  assert.deepEqual(calls.at(-1), ['group', 'group:T cell', false]);
  const only = { dataset: { only: 'class:natural killer cell' } };
  els.get('types-given').fire('click', { target: { closest: (sel) => (sel === '[data-only]' ? only : null) } });
  assert.deepEqual(calls.at(-1), ['only', 'class:natural killer cell']);
  els.get('given-all').fire('click');
  assert.deepEqual(calls.at(-1), ['all', true]);
  els.get('given-none').fire('click');
  assert.deepEqual(calls.at(-1), ['all', false]);
  els.get('highlight-toggle').fire('click');
  assert.deepEqual(calls.at(-1), ['highlight', false]);
});
