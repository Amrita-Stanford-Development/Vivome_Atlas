// The reference cells (web/js/atlas/reference-layer.js) on a stand-in for
// three.js and the stage: highlighting a set of types is a uniform write,
// setFocus still works for one type, and the shaders keep WebGL1's rules
// (uniform arrays indexed in the vertex shader only, every attribute read
// declared and on the geometry).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RADIUS, createReferenceLayer } from '../js/atlas/reference-layer.js';
import { CLASS_COLOURS } from '../js/workflow-data.js';

// ---- stand-ins ----

function fakeThree() {
  class Vec { constructor(...v) { this.v = v; } set(...v) { this.v = v; return this; } get x() { return this.v[0]; } get y() { return this.v[1]; } }
  return {
    BufferGeometry: class { constructor() { this.attributes = {}; } setAttribute(k, a) { this.attributes[k] = a; return this; } dispose() {} },
    BufferAttribute: class { constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; } },
    ShaderMaterial: class { constructor(p) { Object.assign(this, p); } dispose() {} },
    Points: class { constructor(geometry, material) { this.geometry = geometry; this.material = material; } },
    Color: class { constructor(hex) { this.hex = hex; } },
    Vector3: Vec, Vector2: Vec,
  };
}

function fakeStage() {
  const stage = {
    invalidations: 0, frames: [], children: [],
    scene: { add(o) { stage.children.push(o); } },
    renderer: { getContext: () => ({ ALIASED_POINT_SIZE_RANGE: 1, getParameter: () => [1, 1024] }), getPixelRatio: () => 1 },
    onFrame(f) { stage.frames.push(f); },
    invalidate() { stage.invalidations += 1; },
    pixelScale: () => 500,
  };
  return stage;
}

// Two cells per class, the second of each a protein cell.
function fakeReference() {
  const classes = CLASS_COLOURS.length;
  const n = classes * 2;
  const positions = new Float32Array(n * 3);
  const codes = new Uint8Array(n);
  const modality = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    positions[i * 3] = i;
    codes[i] = Math.floor(i / 2);
    modality[i] = i % 2;
  }
  return { positions, codes, modality, n };
}

const build = () => {
  const stage = fakeStage();
  const layer = createReferenceLayer(fakeThree(), stage, fakeReference());
  return { stage, layer, uniforms: layer.points.material.uniforms };
};

const focused = (uniforms) => uniforms.uFocusOn.value.flatMap((v, c) => (v === 1 ? [c] : []));

// ---- highlighting types ----

test('no type is highlighted at first', () => {
  const { layer, uniforms } = build();
  assert.equal(uniforms.uFocusOn.value.length, CLASS_COLOURS.length);
  assert.ok(uniforms.uFocusOn.value.every((v) => v === 0));
  assert.equal(uniforms.uFocusAny.value, 0);
  assert.deepEqual(layer.focusSet, []);
  assert.equal(uniforms.uFocus, undefined, 'the single-type uniform is gone');
});

test('setFocusSet writes the set and the flag, and clears with null or an empty set', () => {
  const { stage, layer, uniforms } = build();
  const before = stage.invalidations;
  layer.setFocusSet([3, 7]);
  assert.deepEqual(focused(uniforms), [3, 7]);
  assert.equal(uniforms.uFocusAny.value, 1);
  assert.deepEqual(layer.focusSet, [3, 7]);
  assert.ok(stage.invalidations > before, 'redraws');
  // A new set replaces the old one; any iterable will do.
  layer.setFocusSet(new Set([5]));
  assert.deepEqual(focused(uniforms), [5]);
  assert.equal(uniforms.uFocusAny.value, 1);
  layer.setFocusSet(null);
  assert.deepEqual(focused(uniforms), []);
  assert.equal(uniforms.uFocusAny.value, 0);
  layer.setFocusSet([0, 21]);
  assert.deepEqual(focused(uniforms), [0, 21]);
  layer.setFocusSet([]);
  assert.deepEqual(focused(uniforms), []);
  assert.equal(uniforms.uFocusAny.value, 0);
  assert.deepEqual(layer.focusSet, []);
  // Indices outside the palette are ignored; a set of only those is no set.
  layer.setFocusSet([-1, 22, 2.5, 'x']);
  assert.deepEqual(focused(uniforms), []);
  assert.equal(uniforms.uFocusAny.value, 0);
  layer.setFocusSet(['4', 99]);
  assert.deepEqual(focused(uniforms), [4]);
  assert.equal(uniforms.uFocusAny.value, 1);
});

test('setFocus still highlights one type, and clears with null or -1', () => {
  const { stage, layer, uniforms } = build();
  layer.setFocusSet([1, 2]);
  const before = stage.invalidations;
  layer.setFocus(4);
  assert.deepEqual(focused(uniforms), [4]);
  assert.equal(uniforms.uFocusAny.value, 1);
  assert.ok(stage.invalidations > before, 'redraws');
  layer.setFocus(null);
  assert.deepEqual(focused(uniforms), []);
  assert.equal(uniforms.uFocusAny.value, 0);
  layer.setFocus(0);
  assert.deepEqual(focused(uniforms), [0], 'class 0 is a type, not "none"');
  layer.setFocus(-1);
  assert.equal(uniforms.uFocusAny.value, 0);
  layer.setFocus(9);
  layer.setFocus(undefined);
  assert.equal(uniforms.uFocusAny.value, 0);
});

test('highlighting leaves the filters, the dimming and picking as they were', () => {
  const { layer, uniforms } = build();
  layer.setDim(0.6);
  layer.setFocusSet([2]);
  assert.equal(layer.dim, 0.6);
  assert.equal(uniforms.uDim.value, 0.6);
  assert.ok([...Array(layer.n).keys()].every(layer.visible), 'highlighting hides nothing');
  layer.setClassOn(3, false);
  assert.equal(layer.visible(6), false);
  assert.equal(layer.visible(4), true);
  assert.equal(layer.pickRadius(1, false), Math.max(4, RADIUS.rna * 500));
});

// ---- the shaders ----

// The shader sources the layer actually draws with.
const shaders = () => {
  const { material } = build().layer.points;
  return { vertex: material.vertexShader, fragment: material.fragmentShader };
};

test('the dimming rule: as before with no set; with one, its types light and the rest faded', () => {
  const { vertex } = shaders();
  // No set: every type at uDim * 0.35, as before the set existed.
  assert.match(vertex, /uFocusAny < 0\.5 \? uDim \* 0\.35/);
  // A set: its types at most lightly dimmed, the rest at least 0.85.
  assert.match(vertex, /uFocusOn\[c\] > 0\.5 \? uDim \* 0\.25/);
  assert.match(vertex, /: max\(uDim, 0\.85\);/);
  assert.ok(!/\buFocus\b/.test(vertex), 'no single-type uniform left');
});

test('uniform arrays are declared and indexed in the vertex shader only', () => {
  const { vertex, fragment } = shaders();
  const arrays = [...vertex.matchAll(/uniform\s+\w+\s+(\w+)\s*\[(\d+)\]/g)].map((m) => [m[1], Number(m[2])]);
  assert.deepEqual(arrays.map(([name]) => name).sort(), ['uClassOn', 'uFocusOn', 'uPalette']);
  for (const [name, size] of arrays) {
    assert.equal(size, CLASS_COLOURS.length, `${name}: one entry per class`);
    assert.ok(!new RegExp(`\\b${name}\\b`).test(fragment), `${name} in the fragment shader`);
  }
  assert.ok(!/uniform\s+\w+\s+\w+\s*\[/.test(fragment), 'a uniform array in the fragment shader');
  assert.match(vertex, /uFocusOn\[c\]/, 'the set is read in the vertex shader');
});

test('every uniform the shaders declare is set, and every one set is declared', () => {
  const { uniforms } = build();
  const { vertex, fragment } = shaders();
  const declared = new Set([...`${vertex}\n${fragment}`.matchAll(/uniform\s+\w+\s+(\w+)/g)].map((m) => m[1]));
  assert.deepEqual([...declared].sort(), Object.keys(uniforms).sort());
  for (const name of ['uFocusOn', 'uClassOn']) assert.equal(uniforms[name].value.length, CLASS_COLOURS.length, name);
});

const SIZES = { float: 1, vec2: 2, vec3: 3, vec4: 4 };

test('the vertex shader declares every attribute it reads, and the geometry carries them', () => {
  const { layer } = build();
  const { vertex, fragment } = shaders();
  const declared = new Map([...vertex.matchAll(/^\s*attribute\s+(\w+)\s+(\w+)\s*;/gm)].map((m) => [m[2], m[1]]));
  const read = new Set([...vertex.replace(/^\s*attribute\s.*$/gm, '').matchAll(/\ba[A-Z]\w*/g)].map((m) => m[0]));
  assert.ok(read.size > 0);
  for (const name of read) assert.ok(declared.has(name), `${name} is read but not declared`);
  for (const [name, type] of declared) {
    const attribute = layer.points.geometry.attributes[name];
    assert.ok(attribute, `${name} is not on the geometry`);
    assert.equal(attribute.itemSize, SIZES[type], name);
    assert.equal(attribute.array.length, layer.n * SIZES[type], name);
  }
  assert.ok(!/\battribute\b/.test(fragment), 'no attribute in the fragment shader');
});
