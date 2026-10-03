// The measured shapes behind web/js/biocells.js: the red cell's profile, the
// DNA helix, the nucleosome and the noise the surfaces use. The THREE builders are checked
// by eye on web/preview-biocells.html.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  RBC, rbcHalfThickness, BDNA, dnaPoint, dnaTangent, dnaGrooves, makeNoise, PALETTES, KINDS,
  helixPoint, NUCLEOSOME,
} from '../js/biocells.js';

const close = (a, b, tol, what) => assert.ok(Math.abs(a - b) <= tol, `${what}: ${a} is not within ${tol} of ${b}`);

test('the red cell follows Evans and Fung: 7.8 um across, 0.81 um at the centre, 2.6 um at its thickest', () => {
  close(2 * RBC.radius, 7.82, 0.01, 'diameter');
  close(2 * rbcHalfThickness(0), 0.81, 0.01, 'centre thickness');
  let max = 0;
  let at = 0;
  for (let i = 0; i <= 1000; i++) {
    const t = 2 * rbcHalfThickness(i / 1000);
    if (t > max) { max = t; at = i / 1000; }
  }
  close(max, 2.57, 0.05, 'greatest thickness');
  assert.ok(at > 0.6 && at < 0.8, `thickest at xi = ${at}, expected near 0.7`);
  assert.equal(rbcHalfThickness(1), 0);
  // Biconcave: thinner at the centre than anywhere out to the thickest ring.
  for (let xi = 0.05; xi < at; xi += 0.05) assert.ok(rbcHalfThickness(xi) > rbcHalfThickness(0));
});

test('DNA is B-form: 10.5 base pairs and 3.57 nm a turn, 34.3 degrees a pair', () => {
  const [x0, , z0] = dnaPoint(0, 0);
  const [x1, y1, z1] = dnaPoint(BDNA.pairsPerTurn, 0);
  close(x1, x0, 1e-9, 'x after one turn');
  close(z1, z0, 1e-9, 'z after one turn');
  close(y1, 3.57, 1e-9, 'pitch');
  const [ax, , az] = dnaPoint(1, 0);
  close((Math.acos((ax * x0 + az * z0) / BDNA.backbone ** 2) * 180) / Math.PI, 360 / 10.5, 1e-6, 'twist per pair');
});

test('DNA is right-handed', () => {
  // Climbing +y, each pair turns anticlockwise seen from above (z towards x).
  const [x0, y0, z0] = dnaPoint(0, 0);
  const [x1, y1, z1] = dnaPoint(1, 0);
  assert.ok(y1 > y0);
  assert.ok(z0 * x1 - x0 * z1 > 0);
});

test('the backbones sit 144 degrees apart, so the minor groove is narrower than the major', () => {
  const [ax, , az] = dnaPoint(5, 0);
  const [bx, , bz] = dnaPoint(5, 1);
  close((Math.acos((ax * bx + az * bz) / BDNA.backbone ** 2) * 180) / Math.PI, 144, 1e-6, 'strand separation');
  const { pitch, minor, major } = dnaGrooves();
  close(minor + major, pitch, 1e-12, 'grooves fill a turn');
  assert.ok(minor < major);
  close(minor / pitch, 0.4, 1e-12, 'minor groove share');
});

test('a bent DNA axis keeps the backbone at its radius and stays right-handed', () => {
  const bend = 40;
  for (let k = 0; k < 32; k += 3) {
    const t = dnaTangent(k, bend);
    const s = k * BDNA.rise;
    const centre = [bend * (1 - Math.cos(s / bend)), bend * Math.sin(s / bend), 0];
    const p = dnaPoint(k, 0, { bend });
    const off = p.map((v, i) => v - centre[i]);
    close(Math.hypot(...off), BDNA.backbone, 1e-9, `radius at pair ${k}`);
    close(off[0] * t[0] + off[1] * t[1] + off[2] * t[2], 0, 1e-9, `backbone across the axis at pair ${k}`);
  }
  assert.deepEqual(dnaPoint(0, 0, { bend }), dnaPoint(0, 0));
  assert.ok(dnaPoint(31, 0, { bend })[0] > dnaPoint(31, 0)[0] + 0.5, 'bends towards +x');
});

test('noise is seeded, bounded and smooth', () => {
  const a = makeNoise(4);
  const b = makeNoise(4);
  const c = makeNoise(5);
  let differs = false;
  for (let i = 0; i < 4000; i++) {
    const x = i * 0.137;
    const y = i * 0.071 - 3;
    const z = i * 0.0193 + 1;
    const v = a(x, y, z);
    assert.equal(v, b(x, y, z));
    assert.ok(Math.abs(v) <= 1.1, `noise ${v} out of range`);
    assert.ok(Math.abs(a(x + 1e-4, y, z) - v) < 1e-2, 'noise jumps');
    if (Math.abs(c(x, y, z) - v) > 1e-6) differs = true;
  }
  assert.ok(differs, 'different seeds give different noise');
  assert.equal(a(3, -2, 7), 0, 'zero on the lattice');
});

test('every palette colours every part, with valid hex colours', () => {
  assert.deepEqual(Object.keys(PALETTES), ['vivid', 'site', 'stained']);
  const keys = Object.keys(PALETTES.site).sort();
  for (const [name, palette] of Object.entries(PALETTES)) {
    assert.deepEqual(Object.keys(palette).sort(), keys, name);
    for (const value of Object.values(palette)) assert.match(value, /^#[0-9A-F]{6}$/);
  }
  // Each white cell has its own nucleus colours in the vivid look.
  const v = PALETTES.vivid;
  assert.equal(new Set(['lymph', 'mono', 'neutro', 'long'].map((c) => v[`${c}NucleusDark`])).size, 4);
  assert.deepEqual(KINDS, [
    'dna', 'chromatin', 'coil', 'thread', 'longCell', 'rbc', 'platelet', 'lymphocyte', 'monocyte', 'neutrophil',
  ]);
});

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
// Seen from above (+y), z turning towards x is anticlockwise.
const turnsRight = (a, b) => a[2] * b[0] - a[0] * b[2] > 0;

test('helixPoint matches dnaPoint for straight B-form DNA', () => {
  for (const k of [0, 1, 7.5, 20]) {
    const h = helixPoint(k, { radius: BDNA.backbone, rise: BDNA.rise, perTurn: BDNA.pairsPerTurn });
    dnaPoint(k, 0).forEach((v, i) => close(h[i], v, 1e-12, `pair ${k}`));
  }
});

test('DNA winds round the nucleosome left-handed, about 43 nm of it per core, 10 nm across', () => {
  const { radius, pitch, turns } = NUCLEOSOME;
  const at = (k) => helixPoint(k, { radius, rise: pitch, perTurn: 1, left: true });
  assert.ok(!turnsRight(at(0), at(0.05)) && at(0.05)[1] > at(0)[1], 'left-handed');
  let contour = 0;
  for (let i = 1; i <= 1000; i++) contour += dist(at(((i - 1) / 1000) * turns), at((i / 1000) * turns));
  close(contour, 43.6, 0.5, 'DNA per wrap (nm)');
  close(2 * (radius + BDNA.radius), 10.4, 0.1, 'nucleosome width');
  assert.ok(pitch >= 2 * BDNA.radius, 'successive turns of the wrap do not overlap');
});
