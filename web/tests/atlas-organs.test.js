// The maps of other organs (web/js/atlas/organs.js and parseOrganCsv in
// web/js/atlas/reference-data.js), read from the real files in
// web/data/organs/, and the reference layer sized by an organ's palette.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  BLOOD, FAMILY_HUES, ORGAN_PLAIN_NAMES, familiesOf, organCellLines, organFrom, organHref, organPalette, organPlainName,
} from '../js/atlas/organs.js';
import { parseOrganCsv } from '../js/atlas/reference-data.js';
import { createReferenceLayer } from '../js/atlas/reference-layer.js';
import { PLAIN_NAMES } from '../js/workflow-data.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const index = JSON.parse(read('data/organs/index.json'));
const organs = index.organs;

test('the index lists the three organ maps, each map only and each with a failed gate record', () => {
  assert.deepEqual(organs.map((o) => o.id), ['large_intestine', 'lung', 'lymph_node']);
  for (const o of organs) {
    assert.equal(o.labelling, false, o.id);
    assert.equal(o.gates.all_pass, false, o.id);
    const gates = JSON.parse(readFileSync(new URL(`../../${o.gates.record}`, import.meta.url), 'utf8'));
    assert.equal(gates.all_pass, false, `${o.id}: the page says it missed its checks`);
    assert.deepEqual(Object.keys(o.hierarchy).sort(), [...o.class_order].sort(), o.id);
  }
});

test('each map file holds the index’s cells, every class used and in range', () => {
  for (const o of organs) {
    const map = parseOrganCsv(read(`data/${o.file}`), o.class_order);
    assert.equal(map.n, o.cells, o.id);
    const seen = new Set(map.classIdx);
    assert.equal(seen.size, o.class_order.length, `${o.id}: every class has cells`);
    assert.ok(map.raw.every(Number.isFinite), o.id);
    assert.deepEqual([...map.origIndex.subarray(0, 3)], [0, 1, 2], o.id);
  }
});

test('every organ type has a plain name', () => {
  for (const o of organs) {
    for (const name of o.class_order) {
      assert.ok(name in ORGAN_PLAIN_NAMES || name in PLAIN_NAMES, `${o.id}: ${name}`);
    }
  }
  assert.equal(organPlainName('type ii pneumocyte'), 'alveolar type 2 cell');
  assert.equal(organPlainName('b cell'), PLAIN_NAMES['b cell']);
  assert.equal(organPlainName('something new'), 'something new');
});

test('the address chooses the organ; anything else is blood', () => {
  assert.equal(organFrom('?organ=lung', organs).id, 'lung');
  assert.equal(organFrom('?organ=heart', organs), null);
  assert.equal(organFrom('', organs), null);
  assert.equal(organFrom('?organ=lung', null), null);
  assert.equal(organHref('https://x.dev/atlas?a=1#your-data', 'lymph_node'), 'https://x.dev/atlas?a=1&organ=lymph_node');
  assert.equal(organHref('https://x.dev/atlas?organ=lung', BLOOD), 'https://x.dev/atlas');
});

test('families cover every type once, by branch and then name', () => {
  for (const o of organs) {
    const families = familiesOf(o.class_order, o.hierarchy);
    const all = families.flatMap((f) => f.classes).sort((a, b) => a - b);
    assert.deepEqual(all, o.class_order.map((_, c) => c), o.id);
    for (const f of families) {
      for (const c of f.classes) assert.equal(o.hierarchy[o.class_order[c]].group, f.name, o.id);
    }
    const keys = families.map((f) => `${f.lineage}\u0000${f.name}`);
    assert.deepEqual(keys, [...keys].sort((a, b) => a.localeCompare(b)), o.id);
    assert.ok(families.length <= FAMILY_HUES.length, `${o.id}: one hue per family`);
  }
});

test('the palette gives every type its own colour, a family one hue', () => {
  const hue = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const max = Math.max(r, g, b);
    const d = max - Math.min(r, g, b);
    if (d === 0) return 0;
    const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return (h * 60 + 360) % 360;
  };
  for (const o of organs) {
    const colours = organPalette(o.class_order, o.hierarchy);
    assert.equal(colours.length, o.class_order.length, o.id);
    assert.ok(colours.every((c) => /^#[0-9a-f]{6}$/.test(c)), o.id);
    assert.equal(new Set(colours).size, colours.length, `${o.id}: distinct colours`);
    for (const f of familiesOf(o.class_order, o.hierarchy)) {
      const hues = f.classes.map((c) => hue(colours[c]));
      assert.ok(Math.max(...hues) - Math.min(...hues) < 4, `${o.id}: ${f.name}`);
    }
  }
});

test('a cell’s lines name its type, family and branch, and read the organ', () => {
  const ln = organs.find((o) => o.id === 'lymph_node');
  assert.deepEqual(organCellLines(ln, 'plasma cell'), ['Lymph node reference cell: plasma cell', 'Family: B cell; branch: lymphoid']);
});

test('the organ reader skips rows it cannot place', () => {
  const map = parseOrganCsv('orig_index,class_idx,PC1,PC2,PC3\n0,1,0.1,0.2,0.3\n1,9,0,0,0\n2,0,x,0,0\n\n3,0,1,1,1\r\n', ['a', 'b']);
  assert.equal(map.n, 2);
  assert.deepEqual(map.names, ['b', 'a']);
  assert.deepEqual([...map.origIndex], [0, 3]);
  assert.throws(() => parseOrganCsv('orig_index,PC1,PC2,PC3\n', ['a']), /class_idx/);
});

test('the reference layer takes an organ palette’s length for its uniform arrays', () => {
  class Vec { constructor(...v) { this.v = v; } }
  const THREE = {
    BufferGeometry: class { constructor() { this.attributes = {}; } setAttribute(k, a) { this.attributes[k] = a; } },
    BufferAttribute: class { constructor(array) { this.array = array; } },
    ShaderMaterial: class { constructor(p) { Object.assign(this, p); } },
    Points: class { constructor(geometry, material) { this.material = material; } },
    Color: class { constructor(hex) { this.hex = hex; } },
    Vector2: Vec,
  };
  const stage = {
    scene: { add() {} }, onFrame() {}, invalidate() {}, pixelScale: () => 1,
    renderer: { getContext: () => ({ getParameter: () => [1, 64] }), getPixelRatio: () => 1 },
  };
  const lung = organs.find((o) => o.id === 'lung');
  const colours = organPalette(lung.class_order, lung.hierarchy);
  const layer = createReferenceLayer(THREE, stage, {
    positions: new Float32Array(3), codes: new Uint8Array([27]), modality: new Float32Array(1), n: 1, colours,
  });
  const { uniforms, vertexShader } = layer.points.material;
  assert.equal(colours.length, 28);
  assert.equal(uniforms.uPalette.value.length, 28);
  assert.equal(uniforms.uClassOn.value.length, 28);
  assert.equal(uniforms.uFocusOn.value.length, 28);
  assert.match(vertexShader, /uniform vec3 uPalette\[28\];/);
  assert.match(vertexShader, /uniform float uFocusOn\[28\];/);
  layer.setFocusSet([27, 28]);
  assert.deepEqual(layer.focusSet, [27]);
});

// A stand-in page: every element the Your data tab looks up, recording its
// listeners, so a drop can be played without a browser.
function fakePage() {
  const els = new Map();
  const make = () => ({
    handlers: {}, hidden: true, disabled: false, value: '', title: '', innerHTML: '', textContent: '', files: [],
    dataset: {}, classList: { toggle() {}, add() {}, remove() {} },
    addEventListener(type, f) { this.handlers[type] = f; }, contains: () => false, focus() {},
  });
  return {
    els,
    document: {
      getElementById: (id) => (els.has(id) ? els.get(id) : els.set(id, make()).get(id)),
      querySelectorAll: () => [],
    },
  };
}

test('an organ map refuses a dropped file; blood takes it to Your data', async () => {
  const { mountDataTab } = await import('../js/atlas/data-tab.js');
  const saved = globalThis.document;
  try {
    for (const acceptsFiles of [false, true]) {
      const page = fakePage();
      globalThis.document = page.document;
      const chosen = [];
      let shown = 0;
      const landing = { state: { name: 'idle' }, run: null, onChange() {}, chooseFile: (f) => chosen.push(f), chips: () => '' };
      const service = { state: { ready: false, limits: null }, url: () => '', limits: () => ({}) };
      const tab = mountDataTab({ landing, client: {}, service, acceptsFiles });
      tab.onShow = () => { shown += 1; };
      const box = page.els.get('three-container');
      const hint = page.els.get('drop-hint');
      const transfer = { types: ['Files'], files: [{ name: 'cells.csv' }], dropEffect: 'copy' };
      let prevented = 0;
      const event = { dataTransfer: transfer, preventDefault: () => { prevented += 1; } };
      box.handlers.dragover(event);
      assert.equal(hint.hidden, !acceptsFiles, 'the drop hint shows only where files are taken');
      box.handlers.drop(event);
      assert.equal(prevented, 2, 'the browser never opens the file in place of the page');
      assert.deepEqual(chosen.length, acceptsFiles ? 1 : 0);
      assert.equal(shown, acceptsFiles ? 1 : 0);
      if (!acceptsFiles) assert.equal(transfer.dropEffect, 'none');
    }
  } finally {
    globalThis.document = saved;
  }
});

test('the organ page guards Your data on every path: tabs, arrow keys, the address, drops', () => {
  const main = read('js/atlas/main.js');
  assert.match(main, /mountDataTab\(\{ landing, client, service, acceptsFiles: !organ \}\)/);
  assert.match(main, /function showTab\(which\) \{\n\s+if \(organ && which === 'data'\) return;/);
  assert.match(main, /if \(organ \|\| !next\) return;/, 'the tab keys (arrows, Home, End) do nothing on an organ page');
  assert.match(main, /function fromHash\(\) \{\n\s+if \(organ\) return;/);
});
