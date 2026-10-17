// Names on the map (web/js/atlas/type-labels.js): the pure layout through a
// real perspective camera, and the labels kept in their container, run on
// stand-ins for the page, the stage and the reference layer.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { LABEL_HEIGHT, LABEL_PAD, createTypeLabels, estimateBox, labelLayout } from '../js/atlas/type-labels.js';
import { CLASS_COLOURS, plainName } from '../js/workflow-data.js';

const W = 800;
const H = 600;

// ---- a camera ----

// Column-major a * b.
function multiply(a, b) {
  const out = new Array(16).fill(0);
  for (let col = 0; col < 4; col += 1) {
    for (let row = 0; row < 4; row += 1) {
      for (let k = 0; k < 4; k += 1) out[col * 4 + row] += a[k * 4 + row] * b[col * 4 + k];
    }
  }
  return out;
}

// The stage's camera (75 degrees, near 0.1, far 1000) on the z axis at eyeZ,
// looking towards -z: a point at z = 0 sits eyeZ in front of it.
function viewProjection(eyeZ = 50, width = W, height = H) {
  const near = 0.1;
  const far = 1000;
  const f = 1 / Math.tan((75 / 2) * (Math.PI / 180));
  const projection = [
    f / (width / height), 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) / (near - far), -1,
    0, 0, (2 * far * near) / (near - far), 0,
  ];
  const view = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, -eyeZ, 1];
  return multiply(projection, view);
}

const overlaps = (a, b, pad = LABEL_PAD) => Math.abs(a.x - b.x) * 2 < a.w + b.w + pad * 2
  && Math.abs(a.y - b.y) * 2 < a.h + b.h + pad * 2;

const onScreen = (b) => b.x - b.w / 2 >= 0 && b.x + b.w / 2 <= W && b.y - b.h / 2 >= 0 && b.y + b.h / 2 <= H;

// A small deterministic generator, so the crowded test is the same every run.
function lcg(seed) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

// ---- labelLayout ----

test('labelLayout leaves out hidden types and types with no cells', () => {
  const anchors = [[-20, -10, 0], [0, 0, 0], null, [20, 10, 0]];
  const sizes = [5, 5, 5, 0];
  const placed = labelLayout(anchors, viewProjection(), W, H, { shown: (c) => c !== 1, sizeOf: (c) => sizes[c] });
  assert.deepEqual(placed.map((b) => b.c), [0], 'type 1 hidden, type 2 has no anchor, type 3 has no cells');
  const all = labelLayout(anchors, viewProjection(), W, H, { sizeOf: () => 5 });
  assert.deepEqual(all.map((b) => b.c).sort(), [0, 1, 3]);
});

test('labelLayout leaves out a centre behind the camera, nearer than the near plane, or off screen', () => {
  const anchors = [
    [0, 0, 0],        // in front, on screen
    [0, 0, 70],       // behind the eye (z = 50)
    [0, 0, 49.95],    // in front of the eye but nearer than the near plane
    [500, 0, 0],      // far to the right
    [0, -400, 0],     // far above
  ];
  // Every left-out type is larger, so none is dropped as a collision instead.
  const placed = labelLayout(anchors, viewProjection(), W, H, { sizeOf: (c) => (c === 0 ? 1 : 10) });
  assert.deepEqual(placed.map((b) => b.c), [0]);
  // The centre of the view lands at the centre of the screen.
  assert.ok(Math.abs(placed[0].x - W / 2) < 1e-3 && Math.abs(placed[0].y - H / 2) < 1e-3);
});

test('labelLayout keeps every label inside the screen', () => {
  // Centres just inside each edge and corner: their boxes would spill over.
  const m = viewProjection();
  const halfW = 50 * Math.tan((75 / 2) * (Math.PI / 180)) * (W / H);
  const halfH = 50 * Math.tan((75 / 2) * (Math.PI / 180));
  const anchors = [
    [-halfW * 0.99, 0, 0], [halfW * 0.99, 0, 0], [0, -halfH * 0.99, 0], [0, halfH * 0.99, 0],
    [-halfW * 0.99, -halfH * 0.99, 0], [halfW * 0.99, halfH * 0.99, 0],
  ];
  const placed = labelLayout(anchors, m, W, H, { sizeOf: () => 1, boxOf: () => ({ w: 160, h: LABEL_HEIGHT }) });
  assert.ok(placed.length >= 4, `${placed.length} placed`);
  for (const b of placed) assert.ok(onScreen(b), JSON.stringify(b));
  // A box wider than the screen is not drawn at all.
  assert.deepEqual(labelLayout([[0, 0, 0]], m, W, H, { boxOf: () => ({ w: W + 1, h: 20 }) }), []);
});

test('labelLayout never returns two overlapping boxes', () => {
  const random = lcg(7);
  const anchors = Array.from({ length: 60 }, () => [(random() - 0.5) * 40, (random() - 0.5) * 30, (random() - 0.5) * 20]);
  const sizes = anchors.map(() => Math.floor(random() * 1000) + 1);
  const placed = labelLayout(anchors, viewProjection(), W, H, {
    sizeOf: (c) => sizes[c],
    boxOf: (c) => estimateBox(`type number ${c}`),
  });
  assert.ok(placed.length > 3 && placed.length < 60, `${placed.length} placed`);
  for (let i = 0; i < placed.length; i += 1) {
    assert.ok(onScreen(placed[i]));
    for (let j = i + 1; j < placed.length; j += 1) assert.ok(!overlaps(placed[i], placed[j]), `${placed[i].c} and ${placed[j].c}`);
  }
  // Larger types come first.
  for (let i = 1; i < placed.length; i += 1) assert.ok(sizes[placed[i - 1].c] >= sizes[placed[i].c]);
});

test('labelLayout gives a collision to the larger type', () => {
  const anchors = [[0, 0, 0], [0.5, 0.2, 0], [30, 0, 0]];
  const sizes = [10, 900, 4];
  const placed = labelLayout(anchors, viewProjection(), W, H, { sizeOf: (c) => sizes[c] });
  assert.deepEqual(placed.map((b) => b.c), [1, 2]);
  // Equal sizes: the earlier type in the class order.
  const tie = labelLayout(anchors.slice(0, 2), viewProjection(), W, H, { sizeOf: () => 3 });
  assert.deepEqual(tie.map((b) => b.c), [0]);
});

// ---- createTypeLabels on stand-ins ----

class El {
  constructor(tag) {
    this.tagName = tag;
    this.className = '';
    this.textContent = '';
    this.style = {};
    this.dataset = {};
    this.children = [];
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
}

function installDocument() {
  globalThis.document = { createElement: (tag) => new El(tag) };
}

// Four types, eight cells each, spread across the view: two RNA cells at the
// type's spot and six protein cells 6 units to its right. Type 3 has protein
// cells only.
const ORDER = ['b cell', 'neutrophil', 'platelet', '<b>type</b> & co'];

function fakeReference() {
  const per = 8;
  const n = ORDER.length * per;
  const positions = new Float32Array(n * 3);
  const codes = new Uint8Array(n);
  const prot = new Uint8Array(n);
  const spots = [[-20, -12], [18, -10], [-16, 12], [20, 14]];
  for (let i = 0; i < n; i += 1) {
    const c = Math.floor(i / per);
    const k = i % per;
    codes[i] = c;
    prot[i] = c === 3 || k >= 2 ? 1 : 0;
    const [x, y] = spots[c];
    positions.set([x + (prot[i] && c !== 3 ? 6 : 0) + (k % 2) * 0.2, y, 0], i * 3);
  }
  return { order: ORDER, n, nRna: n, positions, codes, prot };
}

function fakeLayer(ref) {
  const classOn = ORDER.map(() => true);
  const modalityOn = { rna: true, prot: true };
  return {
    classOn: (c) => classOn[c],
    setClassOn: (c, on) => { classOn[c] = on; },
    setModality: (which, on) => { modalityOn[which] = on; },
    visible: (i) => classOn[ref.codes[i]] && (ref.prot[i] ? modalityOn.prot : modalityOn.rna),
  };
}

function fakeStage() {
  const listeners = { change: [] };
  const frames = [];
  const stage = {
    width: W,
    height: H,
    projections: 0,
    eyeZ: 50,
    rig: { on: (name, f) => (listeners[name] ??= []).push(f) },
    onFrame: (f) => frames.push(f),
    invalidate() {},
    viewProjection() { stage.projections += 1; return viewProjection(stage.eyeZ, stage.width, stage.height); },
    change: () => listeners.change.forEach((f) => f()),
    frame: () => frames.forEach((f) => f()),
  };
  return stage;
}

function setup() {
  installDocument();
  const ref = fakeReference();
  const layer = fakeLayer(ref);
  const stage = fakeStage();
  const container = new El('div');
  const labels = createTypeLabels({ stage, ref, layer, container });
  const shownTypes = () => container.children.map((el) => Number(el.dataset.class)).sort();
  return { ref, layer, stage, container, labels, shownTypes };
}

test('the labels start off and fill the container when switched on', () => {
  const { stage, container, labels, shownTypes } = setup();
  assert.equal(labels.on, false);
  assert.equal(container.children.length, 0);
  stage.change();
  stage.frame();
  assert.equal(stage.projections, 0, 'nothing is laid out while off');
  assert.equal(container.children.length, 0);

  labels.setOn(true);
  assert.equal(labels.on, true);
  assert.deepEqual(shownTypes(), [0, 1, 2, 3]);
  for (const el of container.children) {
    const c = Number(el.dataset.class);
    assert.equal(el.className, 'type-label');
    const [dot, name] = el.children;
    assert.equal(dot.className, 'type-label-dot');
    assert.equal(dot.style.background, CLASS_COLOURS[c]);
    assert.equal(name.className, 'type-label-name');
    assert.equal(name.textContent, plainName(ORDER[c]), 'the plain name, as text');
    assert.match(el.style.transform, /^translate\(-?\d+px, -?\d+px\)$/);
  }
  assert.equal(container.children[0].children[1].textContent, 'B cell');
});

test('switched off, the container empties', () => {
  const { container, labels } = setup();
  labels.setOn(true);
  assert.ok(container.children.length > 0);
  labels.setOn(false);
  assert.equal(labels.on, false);
  assert.equal(container.children.length, 0);
});

test('the labels follow the camera at most once a frame, and on a resize', () => {
  const { stage, container, labels } = setup();
  labels.setOn(true);
  const before = stage.projections;
  const transform = container.children[0].style.transform;
  stage.frame();
  assert.equal(stage.projections, before, 'no camera change, no new layout');

  stage.eyeZ = 80;
  stage.change();
  stage.change();
  stage.change();
  stage.frame();
  assert.equal(stage.projections, before + 1, 'three changes, one layout');
  assert.notEqual(container.children[0].style.transform, transform, 'the label moved with the camera');
  stage.frame();
  assert.equal(stage.projections, before + 1);

  stage.width = 1000;
  stage.frame();
  assert.equal(stage.projections, before + 2, 'a resize lays out again');
});

test('refresh drops a type the visitor hid, and one whose cells are all hidden', () => {
  const { layer, labels, shownTypes } = setup();
  labels.setOn(true);
  layer.setClassOn(1, false);
  labels.refresh();
  assert.deepEqual(shownTypes(), [0, 2, 3]);

  // Type 3 has protein cells only: hiding the protein cells hides its name.
  layer.setModality('prot', false);
  labels.refresh();
  assert.deepEqual(shownTypes(), [0, 2]);

  layer.setClassOn(1, true);
  layer.setModality('prot', true);
  labels.refresh();
  assert.deepEqual(shownTypes(), [0, 1, 2, 3]);
});

test('a filter changed while the labels were off is read when they come back', () => {
  const { layer, labels, shownTypes } = setup();
  layer.setClassOn(2, false);
  labels.refresh();
  labels.setOn(true);
  assert.deepEqual(shownTypes(), [0, 1, 3]);
});

test('a name sits over the cells on show', () => {
  const { stage, container, layer, labels } = setup();
  labels.setOn(true);
  const x = () => {
    const el = container.children.find((e) => e.dataset.class === '0');
    return Number(el.style.transform.match(/translate\((-?\d+)px/)[1]);
  };
  // Type 0's RNA cells sit at x = -20, its protein cells at x = -14, so its
  // name starts on a protein cell. With the protein cells hidden, the name
  // moves onto the RNA cells.
  const both = x();
  layer.setModality('prot', false);
  labels.refresh();
  const rnaOnly = x();
  assert.ok(rnaOnly < both, `${rnaOnly} < ${both}`);
  assert.ok(stage.projections >= 2);
});

test('the module sets names as text, never as markup', () => {
  const src = readFileSync(new URL('../js/atlas/type-labels.js', import.meta.url), 'utf8');
  assert.ok(!/innerHTML|insertAdjacentHTML|outerHTML/.test(src));
  assert.ok(!src.includes(String.fromCharCode(0x2014)), 'no em dash');
  assert.ok(!src.includes('\r'), 'LF line endings');
});
