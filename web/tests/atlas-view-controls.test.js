// The Atlas page's view controls (web/js/atlas/view-controls.js), on
// stand-ins for the page, the landing, the reference layer, the stage and
// the names: the Your cells section appears only with an answer on the map,
// and every control asks the right part of the page.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CELLS_ON_MAP, dimPercent, mountViewControls } from '../js/atlas/view-controls.js';

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
