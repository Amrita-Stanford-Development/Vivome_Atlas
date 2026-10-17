// The uploaded cells' flight (web/js/atlas/upload-layer.js) and the waiting
// illustration (web/js/atlas/illustration.js): the path maths the shader and
// the CPU share, the layer's bookkeeping on a stand-in for three.js, and the
// illustration's layout.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  FLIGHT, GLOW_MODES, SHADERS, SHADER_DEFINES, SHEET_FIT, cellRadius, cellSeed, createUploadLayer, easeFlight, landingTime,
  pathPoint, sheetRadiusFor,
} from '../js/atlas/upload-layer.js';
import { fileGridLayout } from '../js/atlas/spatial.js';
import {
  ILLUSTRATION, ILLUSTRATION_SHADERS, createIllustration, illustrationGrid, illustrationLayout, illustrationSlot,
} from '../js/atlas/illustration.js';
import { CLASS_COLOURS } from '../js/workflow-data.js';
import { rng } from '../js/random.js';

const close = (a, b, eps, msg) => assert.ok(Math.abs(a - b) <= eps, `${msg ?? ''} ${a} vs ${b}`);
const near3 = (a, b, eps, msg) => [0, 1, 2].forEach((k) => close(a[k], b[k], eps, msg));
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const len = (a) => Math.sqrt(dot(a, a));
const randomPoint = (r) => [(r() - 0.5) * 80, (r() - 0.5) * 80, (r() - 0.5) * 80];

// ---- the path ----

test('a flight eases from 0 before take-off to 1 once landed', () => {
  assert.equal(easeFlight(0, 1, 2), 0);
  assert.equal(easeFlight(1, 1, 2), 0);
  assert.equal(easeFlight(2, 1, 2), 0.5);
  assert.equal(easeFlight(3, 1, 2), 1);
  assert.equal(easeFlight(99, 1, 2), 1);
  let last = -1;
  for (let t = 0; t <= 4; t += 0.05) {
    const u = easeFlight(t, 1, 2);
    assert.ok(u >= last, 'never goes back');
    last = u;
  }
  // A zero-length flight is a jump at its delay.
  assert.equal(easeFlight(0.99, 1, 0), 0);
  assert.equal(easeFlight(1.01, 1, 0), 1);
  assert.equal(landingTime(1, 2), 3);
  assert.equal(landingTime(1, 0), 1 + FLIGHT.minDuration);
});

test('every path starts at its start and ends at its end', () => {
  const r = rng(3);
  const ups = [[0, -1, 0], [0, 0, 1], [0.3, -0.8, 0.2], [0, 0, 0]];
  for (let k = 0; k < 400; k += 1) {
    const s = randomPoint(r);
    const e = randomPoint(r);
    const up = ups[k % ups.length];
    near3(pathPoint(s, e, r(), up, 0), s, 1e-9, 'u = 0');
    near3(pathPoint(s, e, r(), up, 1), e, 1e-9, 'u = 1');
  }
  // Straight up and down the arc's own direction, and nowhere at all.
  near3(pathPoint([0, 0, 0], [0, -10, 0], 0.4, [0, -1, 0], 1), [0, -10, 0], 1e-9);
  assert.ok(pathPoint([0, 0, 0], [0, -10, 0], 0.4, [0, -1, 0], 0.5).every(Number.isFinite));
  near3(pathPoint([1, 2, 3], [1, 2, 3], 0.4, [0, -1, 0], 0.5), [1, 2, 3], 1e-12);
});

test('the arc rises toward arcUp and leans to one side by the shared constants', () => {
  const r = rng(5);
  for (let k = 0; k < 200; k += 1) {
    const s = randomPoint(r);
    const e = randomPoint(r);
    const up = [0, -1, 0];
    const span = sub(e, s);
    const d = len(span);
    const f = span.map((x) => x / d);
    const mid = [(s[0] + e[0]) / 2, (s[1] + e[1]) / 2, (s[2] + e[2]) / 2];
    // B(1/2) = s/4 + m/2 + e/4, so its offset from the chord's midpoint is
    // half the control point's: arcUp * arc * d / 2 plus a unit lean * side * d / 2.
    const offset = sub(pathPoint(s, e, r(), up, 0.5), mid);
    const lean = sub(offset, up.map((x) => (x * FLIGHT.arc * d) / 2));
    close(len(lean), (FLIGHT.side * d) / 2, 1e-9, 'lean length');
    close(dot(lean, f), 0, 1e-9, 'the lean is across the flight');
  }
});

test('flights from one place to another fan out instead of one tube', () => {
  const s = [0, 0, 0];
  const e = [40, 0, 0];
  const leans = [];
  for (let i = 0; i < 2000; i += 1) {
    const seed = cellSeed(i);
    assert.ok(seed >= 0 && seed < 1);
    assert.equal(seed, cellSeed(i), 'stable');
    const p = pathPoint(s, e, seed, [0, -1, 0], 0.5);
    leans.push([p[1] - -FLIGHT.arc * 20, p[2]]);
  }
  const mean = leans.reduce((m, [y, z]) => [m[0] + y / leans.length, m[1] + z / leans.length], [0, 0]);
  assert.ok(Math.hypot(mean[0], mean[1]) < 0.3, `leans balance out: ${mean}`);
  // Every quarter of the circle round the arc gets flights.
  const quarters = new Set(leans.map(([y, z]) => Math.floor(((Math.atan2(z, y) + Math.PI) / (2 * Math.PI)) * 4) % 4));
  assert.equal(quarters.size, 4);
});

test('the shaders run the path on the constants the CPU uses', () => {
  const defines = Object.fromEntries([...SHADERS.cell.vertex.matchAll(/#define (\w+) ([-\d.e]+)\s*$/gm)].map((m) => [m[1], Number(m[2])]));
  assert.equal(defines.ARC, FLIGHT.arc);
  assert.equal(defines.SIDE, FLIGHT.side);
  assert.equal(defines.MIN_LENGTH, FLIGHT.minLength);
  assert.equal(defines.PARALLEL, FLIGHT.parallel);
  assert.equal(defines.MIN_DURATION, FLIGHT.minDuration);
  assert.equal(defines.REVEAL, FLIGHT.reveal);
  assert.equal(defines.RADIUS, FLIGHT.radius);
  for (const [k, v] of Object.entries(SHADER_DEFINES)) assert.equal(defines[k], v, k);
  // The same steps in the same order as pathInto.
  const glsl = SHADERS.cell.vertex;
  const steps = ['vec3 r = cross(f, uArcUp);', 'cross(f, vec3(1.0, 0.0, 0.0))', 'cross(f, vec3(0.0, 0.0, 1.0))',
    'vec3 q = cross(r, f);', 'seed * 6.283185307179586', 'uArcUp * (ARC * d) + (cos(a) * r + sin(a) * q) * (SIDE * d)',
    'w * w * s + 2.0 * w * u * m + u * u * e'];
  let at = 0;
  for (const s of steps) {
    const i = glsl.indexOf(s, at);
    assert.ok(i >= 0, `missing or out of order: ${s}`);
    at = i;
  }
  assert.match(glsl, /u \* u \* \(3\.0 - 2\.0 \* u\)/, 'smoothstep easing');
  assert.match(glsl, new RegExp(`uniform vec3 uPalette\\[${CLASS_COLOURS.length}\\]`));
});

test('a cell draws at the sheet radius on the sheet and grows to the full radius by landing', () => {
  for (const sheet of [0.2, 0.45, FLIGHT.radius]) {
    assert.equal(cellRadius(0, true, sheet), sheet, 'at the start');
    assert.equal(cellRadius(1, true, sheet), FLIGHT.radius, 'landed');
    let last = 0;
    for (let t = -0.5; t <= 3; t += 0.01) {
      const r = cellRadius(easeFlight(t, 0, 2), true, sheet);
      assert.ok(r <= FLIGHT.radius + 1e-12, `never past the full radius: ${r}`);
      assert.ok(r >= last - 1e-12, 'only grows');
      last = r;
      assert.equal(cellRadius(easeFlight(t, 0, 2), false, sheet), sheet, 'a cell that stays keeps the sheet radius');
    }
  }
  assert.equal(cellRadius(0.3, true), FLIGHT.radius, 'by default nothing changes');
  // The shader grows it the same way.
  assert.match(SHADERS.cell.vertex, /uniform float uSheetRadius;/);
  assert.match(SHADERS.cell.vertex, /float r = flies \? mix\(uSheetRadius, RADIUS, u\) : uSheetRadius;/);
  assert.match(SHADERS.cell.vertex, /2\.0 \* r \* vExtent/);
});

test('the sheet radius fits a crowded sheet without overlap', () => {
  const width = 30;
  const aspect = 1.6;
  for (const n of [238, 2000]) {
    const r = sheetRadiusFor(n);
    const { cols, rows } = fileGridLayout(n, aspect);
    close(r, Math.min(FLIGHT.radius, Math.max(SHEET_FIT.min, (0.42 * width) / (cols - 1))), 1e-12, `n ${n}`);
    const gap = Math.min(width / (cols - 1), width / aspect / (rows - 1));
    assert.ok(2 * r < gap, `n ${n}: diameter ${2 * r} within spacing ${gap}`);
    assert.ok(r >= SHEET_FIT.min && r <= FLIGHT.radius);
  }
  assert.ok(sheetRadiusFor(2000) < sheetRadiusFor(238));
  assert.equal(sheetRadiusFor(1), FLIGHT.radius, 'a lone cell takes the full radius');
  assert.equal(sheetRadiusFor(4), FLIGHT.radius, 'a sparse sheet is capped at the full radius');
  assert.equal(sheetRadiusFor(500, 60), Math.min(FLIGHT.radius, (0.42 * 60) / (fileGridLayout(500, 1.6).cols - 1)));
});

test('uniform arrays are read in vertex shaders only', () => {
  const all = { ...SHADERS, illustration: ILLUSTRATION_SHADERS };
  for (const [name, { vertex, fragment }] of Object.entries(all)) {
    assert.ok(!/uniform\s+\w+\s+\w+\s*\[/.test(fragment), `${name}: a uniform array in the fragment shader`);
    assert.ok(/gl_PointSize/.test(vertex), name);
  }
});

// ---- the layer, on a stand-in for three.js ----

function fakeThree() {
  class Vec { constructor(...v) { this.v = v; } set(...v) { this.v = v; return this; } get x() { return this.v[0]; } }
  return {
    BufferGeometry: class { constructor() { this.attributes = {}; this.disposed = false; } setAttribute(k, a) { this.attributes[k] = a; return this; } dispose() { this.disposed = true; } },
    BufferAttribute: class { constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; } setUsage() { return this; } },
    ShaderMaterial: class { constructor(p) { Object.assign(this, p); } dispose() { this.disposed = true; } },
    Points: class { constructor(geometry, material) { this.geometry = geometry; this.material = material; } },
    Color: class { constructor(hex) { this.hex = hex; } },
    Vector3: Vec, Vector2: Vec,
    AdditiveBlending: 2, CustomBlending: 5, AddEquation: 100, ZeroFactor: 200, SrcColorFactor: 202, DynamicDrawUsage: 35048,
  };
}

function fakeStage() {
  const stage = {
    invalidations: 0, tickers: [], frames: [], children: new Set(),
    scene: { background: { isColor: true, r: 1, g: 1, b: 1 }, add(o) { stage.children.add(o); }, remove(o) { stage.children.delete(o); } },
    renderer: { getContext: () => ({ ALIASED_POINT_SIZE_RANGE: 1, getParameter: () => [1, 1024] }), getPixelRatio: () => 1 },
    addTicker(f) { stage.tickers.push(f); return () => { stage.tickers = stage.tickers.filter((g) => g !== f); }; },
    onFrame(f) { stage.frames.push(f); },
    invalidate() { stage.invalidations += 1; },
    pixelScale: () => 500,
    tick: () => stage.tickers.some((f) => f(1 / 60, 0)),
  };
  return stage;
}

const settle = () => new Promise((done) => setTimeout(done, 0));

// Three cells: two fly (one with no answer), one stays on the sheet.
const model = () => ({
  n: 3,
  start: Float32Array.from([0, 0, 0, 1, 0, 0, 2, 0, 0]),
  end: Float32Array.from([10, 5, 3, -8, 4, 2, 2, 0, 0]),
  delay: Float32Array.from([0, 0.5, 0]),
  duration: Float32Array.from([1, 1, 1]),
  style: Float32Array.from([0, 3, 4]),
  fill: Float32Array.from([2, -1, 5]),
  outcome: Float32Array.from([0, 3, 6]),
  flies: Uint8Array.from([1, 1, 0]),
});

test('the layer replays the shader path on the CPU for picking', () => {
  const stage = fakeStage();
  const layer = createUploadLayer(fakeThree(), stage);
  layer.load(model());
  assert.equal(layer.n, 3);
  const m = model();
  near3(layer.positionsAt(-1).subarray(0, 3), [0, 0, 0], 1e-6, 'before take-off');
  near3(layer.positionsAt(10).subarray(0, 3), [10, 5, 3], 1e-6, 'landed');
  near3(layer.positionsAt(10).subarray(3, 6), [-8, 4, 2], 1e-6, 'landed');
  near3(layer.positionsAt(10).subarray(6, 9), [2, 0, 0], 0, 'a cell that does not fly stays on the sheet');
  layer.setArcUp([0, -2, 0]);
  const mid = layer.positionsAt(1.0);
  for (let i = 0; i < 2; i += 1) {
    const s = [...m.start.subarray(i * 3, i * 3 + 3)];
    const e = [...m.end.subarray(i * 3, i * 3 + 3)];
    const want = pathPoint(s, e, Math.fround(cellSeed(i)), [0, -1, 0], easeFlight(1.0, m.delay[i], m.duration[i]));
    near3(mid.subarray(i * 3, i * 3 + 3), want, 1e-5, `cell ${i}`);
  }
  assert.throws(() => layer.load({ ...model(), end: new Float32Array(3) }), /model\.end with 9 values/);
});

test('the layer keeps the stage drawing only while the fed clock has something moving', async () => {
  const stage = fakeStage();
  const layer = createUploadLayer(fakeThree(), stage);
  layer.load(model());
  layer.setClock(0.2);
  assert.equal(stage.tick(), true, 'mid-flight');
  assert.equal(stage.tick(), false, 'the clock was not fed since');
  // The last cell lands at 1.5; its ripple runs FLIGHT.rippleSeconds more.
  close(layer.settledAt, 1.5 + FLIGHT.rippleSeconds, 1e-6);
  layer.setClock(1.5 + FLIGHT.rippleSeconds - 0.01);
  assert.equal(stage.tick(), true, 'a ripple is still running');
  layer.setClock(1.5 + FLIGHT.rippleSeconds + 0.01);
  assert.equal(stage.tick(), false, 'all landed');
  // Landing glows extend it; the steady glow round a selected cell does not.
  layer.setNeighbours({ m: 2, position: new Float32Array(6), cls: Float32Array.from([1, 2]), owner: Float32Array.from([0, 1]), at: Float32Array.from([1, 3]) });
  layer.setClock(3.5);
  assert.equal(stage.tick(), true, 'a glow is bursting');
  layer.setGlowMode('selected');
  layer.setClock(3.6);
  assert.equal(stage.tick(), false);
  assert.throws(() => layer.setGlowMode('sideways'), /glow mode/);
  // Changes redraw after the frame, not inside it.
  const before = stage.invalidations;
  layer.setSelected(1);
  layer.setHover(0);
  assert.equal(stage.invalidations, before, 'not inside the call');
  await settle();
  assert.equal(stage.invalidations, before + 1, 'once, after');
  // Past the end, feeding the clock asks for no more frames.
  await settle();
  const quiet = stage.invalidations;
  layer.setClock(50);
  layer.setClock(51);
  await settle();
  assert.equal(stage.invalidations, quiet);
  assert.equal(GLOW_MODES.selected, 2);
});

test('the layer draws and picks cells at the sheet radius until they fly', () => {
  const stage = fakeStage();
  const layer = createUploadLayer(fakeThree(), stage);
  layer.load(model());
  assert.equal(layer.sheetRadius, FLIGHT.radius, 'by default, today’s size');
  assert.equal(layer.radiusAt(0, -1), FLIGHT.radius);
  layer.setSheetRadius(0.3);
  assert.equal(layer.points.material.uniforms.uSheetRadius.value, 0.3);
  close(layer.radiusAt(0, -1), 0.3, 1e-12, 'on the sheet');
  close(layer.radiusAt(0, 10), FLIGHT.radius, 1e-12, 'landed');
  close(layer.radiusAt(2, 10), 0.3, 1e-12, 'a cell that stays');
  for (let t = 0; t <= 2; t += 0.05) assert.ok(layer.radiusAt(1, t) <= FLIGHT.radius + 1e-12);
  // Picking follows the drawn size: pixelScale 500, pixel ratio 1.
  layer.setClock(-1);
  close(layer.pickRadius(1, 0), 0.3 * FLIGHT.sprite * 500, 1e-9);
  close(layer.pickRadius(1), 0.3 * FLIGHT.sprite * 500, 1e-9, 'the largest drawn now');
  layer.setClock(10);
  close(layer.pickRadius(1, 0), FLIGHT.radius * FLIGHT.sprite * 500, 1e-9);
  close(layer.pickRadius(1, 2), 0.3 * FLIGHT.sprite * 500, 1e-9);
  close(layer.pickRadius(1), FLIGHT.radius * FLIGHT.sprite * 500, 1e-9);
  const { pickRadius } = layer;
  close(pickRadius(1, 2), 0.3 * FLIGHT.sprite * 500, 1e-9, 'works detached');
  layer.setSheetRadius(5);
  assert.equal(layer.sheetRadius, FLIGHT.radius, 'never larger than the full radius');
  layer.setSheetRadius(0.4);
  layer.clear();
  assert.equal(layer.sheetRadius, FLIGHT.radius, 'clear restores it');
});

test('outcome switches, clearing and disposing', () => {
  const stage = fakeStage();
  const three = fakeThree();
  const layer = createUploadLayer(three, stage);
  assert.equal(stage.children.size, 3, 'the cells, their ripples and the glow');
  layer.load(model());
  assert.deepEqual([0, 1, 2].map(layer.visible), [true, true, true]);
  layer.setOutcomeOn(3, false);
  assert.deepEqual([0, 1, 2].map(layer.visible), [true, false, true]);
  layer.setAllOutcomes(false);
  assert.deepEqual([0, 1, 2].map(layer.visible), [false, false, false]);
  layer.setAllOutcomes(true);
  layer.setOpacity(0);
  assert.equal(layer.visible(0), false, 'faded out for Clear');
  const geometry = layer.points.geometry;
  layer.clear();
  assert.equal(layer.n, 0);
  assert.ok(geometry.disposed, 'the old geometry is let go');
  assert.equal(layer.visible(0), false);
  layer.load(model());
  assert.equal(layer.visible(0), true, 'clear restores opacity and switches');
  layer.dispose();
  assert.equal(stage.children.size, 0);
  assert.equal(stage.tickers.length, 0);
});

// ---- the waiting illustration ----

const N = 400;
const layouts = (step, t, n = N, seed = 7, lanes = 5) => Array.from({ length: n }, (_, i) => illustrationLayout(step, t, i, n, seed, lanes));

test('every illustration step starts and ends on the grid, in grey, so the loop is seamless', () => {
  for (const n of [N, 37, 1]) {
    for (let step = 0; step < ILLUSTRATION.steps; step += 1) {
      for (const t of [0, 1]) {
        layouts(step, t, n).forEach(([u, v, tone], i) => {
          const [su, sv] = illustrationSlot(i, n);
          close(u, su, 1e-9, `step ${step} t ${t} dot ${i} u`);
          close(v, sv, 1e-9, `step ${step} t ${t} dot ${i} v`);
          close(tone, 0, 1e-9, `step ${step} t ${t} tone`);
        });
      }
    }
  }
});

test('the illustration stays on its plane and in its two tones', () => {
  for (let step = 0; step < ILLUSTRATION.steps; step += 1) {
    for (let t = 0; t <= 1; t += 0.05) {
      for (const [u, v, tone] of layouts(step, t)) {
        assert.ok(u >= -ILLUSTRATION.edge - 1e-9 && u <= 1 + ILLUSTRATION.edge + 1e-9, `step ${step}: u ${u}`);
        assert.ok(v >= 0 && v <= 1, `step ${step}: v ${v}`);
        assert.ok(tone >= 0 && tone <= 1, `step ${step}: tone ${tone}`);
      }
    }
  }
  // Grey and the accent only: no class colour, no reserved colour.
  const used = Object.values(ILLUSTRATION.colours).map((c) => c.toLowerCase());
  assert.deepEqual(used, ['#9aa6af', '#0066a3']);
  for (const c of used) assert.ok(!CLASS_COLOURS.includes(c) && c !== '#c8641e' && c !== '#2f8f6a');
});

test('step 0 scatters the dots and snaps them back column by column', () => {
  const moved = (t) => layouts(0, t).reduce((s, [u, v], i) => {
    const [su, sv] = illustrationSlot(i, N);
    return s + Math.hypot(u - su, v - sv) / N;
  }, 0);
  assert.ok(moved(0.3) > 0.15, `scattered: ${moved(0.3)}`);
  assert.ok(moved(0.65) < moved(0.3), 'the left columns are back');
});

test('step 1 draws the dots toward a few centres', () => {
  const spread = (t) => {
    const pts = layouts(1, t);
    const mu = pts.reduce((s, [u]) => s + u / N, 0);
    return pts.reduce((s, [u]) => s + (u - mu) ** 2 / N, 0);
  };
  const local = (t) => {
    // Mean distance to the nearest other dot shrinks as they gather.
    const pts = layouts(1, t);
    return pts.reduce((s, [u, v], i) => s + Math.min(...pts.map(([a, b], j) => (i === j ? Infinity : Math.hypot(u - a, v - b)))) / N, 0);
  };
  assert.ok(local(0.45) < local(0), 'closer together at the peak');
  assert.ok(spread(0.45) < spread(0));
});

test('step 2 streams the dots through the given number of lanes', () => {
  for (const lanes of [5, 3]) {
    const pts = layouts(2, 0.5, N, 7, lanes);
    const dv = (1 - 2 * ILLUSTRATION.margin[1]) / (lanes - 1);
    pts.forEach(([, v], i) => {
      const lv = ILLUSTRATION.margin[1] + dv * (i % lanes);
      assert.ok(Math.abs(v - lv) <= dv * 0.2, `dot ${i} in lane ${i % lanes}: ${v} vs ${lv}`);
    });
    assert.ok(pts.every(([, , tone]) => tone > 0.99), 'in the accent while in the lanes');
  }
});

test('step 3 brings a partner beside every other dot', () => {
  const { du, dv } = illustrationGrid(N);
  const pts = layouts(3, 0.5);
  let partners = 0;
  pts.forEach(([u, v], i) => {
    const [su, sv, col] = illustrationSlot(i, N);
    if (col % 2 === 1) {
      partners += 1;
      const [hu, hv] = illustrationSlot(i - 1, N);
      close(Math.hypot(u - hu, v - hv), 0.6 * Math.min(du, dv), 1e-9, `partner ${i}`);
    } else {
      assert.deepEqual([u, v], [su, sv], 'the checked dot stays put');
    }
  });
  // 400 dots on 26 columns: every odd column of every row is a partner.
  assert.equal(illustrationGrid(N).cols, 26);
  assert.equal(partners, N / 2);
});

test('step 4 sorts the dots into equal bins, so no share is implied', () => {
  for (const n of [N, 37]) {
    const pts = layouts(4, 0.5, n);
    const binW = (1 - 2 * ILLUSTRATION.margin[0]) / ILLUSTRATION.bins;
    const counts = new Array(ILLUSTRATION.bins).fill(0);
    for (const [u] of pts) counts[Math.floor((u - ILLUSTRATION.margin[0]) / binW)] += 1;
    assert.ok(Math.max(...counts) - Math.min(...counts) <= 1, `${counts}`);
    assert.equal(counts.reduce((a, b) => a + b, 0), n);
  }
});

test('step 5 streams the dots out through the left side, toward the atlas', () => {
  const pts = layouts(5, 0.35);
  const out = pts.filter(([u]) => u < 0.15);
  assert.ok(out.length > N * 0.1, `${out.length} dots near the left side`);
  assert.ok(out.some(([, , tone]) => tone > 0.5), 'lit as they go');
  // Before any dot wraps, every one has moved left of its slot.
  layouts(5, 0.08).forEach(([u], i) => assert.ok(u <= illustrationSlot(i, N)[0] + 1e-12));
});

test('the illustration is the same for the same seed', () => {
  assert.deepEqual(layouts(1, 0.4, 50, 7), layouts(1, 0.4, 50, 7));
  assert.notDeepEqual(layouts(0, 0.3, 50, 7), layouts(0, 0.3, 50, 8));
});

test('the illustration draws its layout on the given plane', async () => {
  const stage = fakeStage();
  const ill = createIllustration(fakeThree(), stage, { count: 20 });
  assert.equal(ill.count, 20);
  ill.show({ centre: [1, 2, 3], right: [2, 0, 0], up: [0, -1, 0], width: 16, height: 10 });
  assert.equal(ill.points.visible, true);
  assert.deepEqual(ill.points.material.uniforms.uRight.value.v, [1, 0, 0], 'directions are normalised');
  ill.setFrame({ step: 2, stepT: 0.5 });
  const uvt = ill.points.geometry.attributes.aUvt.array;
  for (let i = 0; i < 20; i += 1) assert.deepEqual([...uvt.subarray(i * 3, i * 3 + 3)], illustrationLayout(2, 0.5, i, 20, 7).map(Math.fround));
  ill.hide();
  assert.equal(ill.points.visible, false);
  await settle();
  assert.ok(stage.invalidations >= 1);
  ill.dispose();
  assert.equal(stage.children.size, 0);
});
