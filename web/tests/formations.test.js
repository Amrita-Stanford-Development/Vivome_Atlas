import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  ROLE, rng, cell, readouts, plate, growthRings, RINGS, helix, atlas, centroid, fromMask,
} from '../js/formations.js';

const finite = (f) => f.pos.every(Number.isFinite);
const maxRadius = (f) => {
  let m = 0;
  for (let i = 0; i < f.pos.length; i += 3) m = Math.max(m, Math.hypot(f.pos[i], f.pos[i + 1], f.pos[i + 2]));
  return m;
};

test('rng is deterministic and in [0, 1)', () => {
  const a = rng(7);
  const b = rng(7);
  for (let i = 0; i < 100; i++) {
    const x = a();
    assert.equal(x, b());
    assert.ok(x >= 0 && x < 1);
  }
});

for (const [name, make] of [['cell', cell], ['readouts', readouts], ['plate', plate], ['growthRings', growthRings], ['helix', helix]]) {
  test(`${name} makes exactly n finite points, the same every time, within formation units`, () => {
    for (const n of [1, 97, 1000]) {
      const f = make(n);
      assert.equal(f.pos.length, n * 3);
      assert.equal(f.role.length, n);
      assert.ok(finite(f), name);
      assert.ok(maxRadius(f) < 1.8, `${name} radius ${maxRadius(f)}`);
    }
    assert.deepEqual(make(300).pos, make(300).pos);
  });
}

test('readouts splits the cell into an RNA strand and a protein chain', () => {
  const f = readouts(400);
  const roles = [...f.role];
  assert.equal(roles.filter((r) => r === ROLE.rna).length, 200);
  assert.equal(roles.filter((r) => r === ROLE.prot).length, 200);
});

test('plate lays out 96 wells', () => {
  const f = plate(96 * 10);
  const centres = new Set();
  for (let i = 0; i < 96 * 10; i += 10) {
    // The first point of each well sits at angle 0, well centre + radius on x.
    centres.add(`${f.pos[i * 3].toFixed(2)},${f.pos[i * 3 + 1].toFixed(2)}`);
  }
  assert.equal(centres.size, 96);
});

test('growth rings end with the release still forming, drawn pale and partial', () => {
  const f = growthRings(900);
  assert.equal(RINGS[RINGS.length - 1].arc < 1, true);
  assert.ok([...f.role].includes(ROLE.pale));
  assert.equal([...f.role].filter((r) => r === ROLE.pale).length > 0, true);
});

test('helix alternates the RNA and protein strands', () => {
  const f = helix(10);
  assert.deepEqual([...f.role], [1, 2, 1, 2, 1, 2, 1, 2, 1, 2].map((k) => (k === 1 ? ROLE.rna : ROLE.prot)));
});

test('atlas keeps the data placement, only recentred and scaled', () => {
  const rows = [[1, 2, 3], [3, 2, 1]];
  const c = centroid(rows);
  assert.deepEqual(c, [2, 2, 2]);
  const f = atlas(rows, ROLE.rna, c, 2);
  assert.deepEqual([...f.pos], [-2, 0, 2, 2, 0, -2]);
  assert.deepEqual([...f.role], [ROLE.rna, ROLE.rna]);
});

test('fromMask puts points only on lit pixels, and copes with an empty mask', () => {
  const w = 10;
  const h = 4;
  const mask = new Uint8Array(w * h);
  mask[1 * w + 2] = 1;   // one lit pixel at (2, 1)
  const f = fromMask(mask, w, h, 50);
  const span = w / 2;
  for (let i = 0; i < 50; i++) {
    assert.ok(Math.abs(f.pos[i * 3] - (2 - w / 2) / span) < 1 / span);
    assert.ok(Math.abs(f.pos[i * 3 + 1] - (h / 2 - 1) / span) < 1 / span);
  }
  const empty = fromMask(new Uint8Array(w * h), w, h, 5);
  assert.ok(finite(empty));
});
