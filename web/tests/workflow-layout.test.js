import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  RESERVED, colourDistance, depthOrder, distanceForOverlap, diverging, histogramBars, lensArea, linear, pickNearest, project,
  radialAngles, rocSnap, rotate, sankey, sequential, ticks,
} from '../js/workflow-layout.js';
import { heatmapSvg, HATCH_ID, rocSvg, upsetSvg } from '../js/workflow-svg.js';

test('turning the view keeps every distance', () => {
  const a = [0.3, -0.2, 0.9];
  const b = [-0.5, 0.4, 0.1];
  const dist = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
  for (const [yaw, pitch] of [[0, 0], [1.1, -0.4], [3, 2]]) {
    assert.ok(Math.abs(dist(rotate(a, yaw, pitch), rotate(b, yaw, pitch)) - dist(a, b)) < 1e-12);
  }
});

test('nearer points draw last, and picking finds the closest one in range', () => {
  const cam = { width: 200, height: 100, scale: 50 };
  const pts = [[0, 0, -1], [0, 0, 1], [0, 0, 0]].map((q) => project(q, cam));
  assert.deepEqual(depthOrder(pts), [0, 2, 1]);
  assert.equal(pickNearest([{ x: 10, y: 10 }, { x: 50, y: 50 }], 48, 52, 5), 1);
  assert.equal(pickNearest([{ x: 10, y: 10 }], 100, 100, 5), -1);
});

test('a Sankey conserves every flow', () => {
  const flows = [
    { source: 'a', target: 'x', value: 5 }, { source: 'a', target: 'y', value: 3 },
    { source: 'b', target: 'x', value: 2 }, { source: 'b', target: 'z', value: 0 },
  ];
  const out = sankey(flows, ['a', 'b'], ['x', 'y', 'z'], { height: 200, gap: 10 });
  const by = (side, key) => out[side].find((n) => n.key === key);
  for (const n of out.left) {
    const h = out.links.filter((l) => l.source === n.key).reduce((s, l) => s + l.h, 0);
    assert.ok(Math.abs(h - n.h) < 1e-9, n.key);
  }
  for (const n of out.right) {
    const v = out.links.filter((l) => l.target === n.key).reduce((s, l) => s + l.value, 0);
    assert.equal(v, n.value, n.key);
  }
  assert.equal(by('right', 'z'), undefined, 'an empty node is left out');
  assert.equal(by('left', 'a').value + by('left', 'b').value, 10);
});

test('the colour ramps never use a reserved colour', () => {
  for (let z = -4; z <= 4; z += 0.05) {
    const c = diverging(z);
    for (const r of RESERVED) assert.ok(colourDistance(c, r) > 40, `${c} is close to ${r} at z ${z}`);
  }
  for (let t = 0; t <= 1; t += 0.05) for (const r of RESERVED) assert.ok(colourDistance(sequential(t), r) > 40);
  assert.equal(diverging(null), null);
  assert.equal(diverging(Number.NaN), null);
});

test('histogram bars, ticks and scales', () => {
  const bars = histogramBars([1, 4, 2], 30, 100);
  assert.equal(bars[1].h, 100);
  assert.equal(bars[0].h, 25);
  assert.deepEqual(ticks(0, 10, 5), [0, 2, 4, 6, 8, 10]);
  assert.equal(linear([0, 10], [0, 100])(2.5), 25);
});

test('the compass gives every class its own angle', () => {
  const names = ['a', 'b', 'c', 'd'];
  const h = { a: { lineage: 'L1' }, b: { lineage: 'L2' }, c: { lineage: 'L1' }, d: { lineage: 'L2' } };
  const angles = radialAngles(names, h);
  assert.equal(new Set(angles).size, 4);
  for (const a of angles) assert.ok(a >= 0 && a < 2 * Math.PI);
  assert.ok(Math.abs(angles[2] - angles[0]) < Math.abs(angles[1] - angles[0]), 'a lineage stays together');
});

test('ROC snapping picks the recorded point nearest a rate', () => {
  const curve = [[0, 0], [0.1, 0.4], [0.5, 0.8], [1, 1]];
  assert.deepEqual(rocSnap(curve, 0.12), [0.1, 0.4]);
  assert.deepEqual(rocSnap(curve, 0.9), [1, 1]);
});

test('the static figures hatch missing values and escape their labels', () => {
  const svg = heatmapSvg({ values: [[1, null], [null, -1]], rowLabels: ['<b>x</b>', 'y'], colLabels: ['c1', 'c2'] });
  assert.equal((svg.match(new RegExp(`url\\(#${HATCH_ID}\\)`, 'g')) ?? []).length, 2);
  assert.equal((svg.match(/<rect x=/g) ?? []).length, 4);
  assert.ok(!svg.includes('<b>x</b>') && svg.includes('&lt;b&gt;x&lt;/b&gt;'));
  assert.match(rocSvg([[0, 0], [1, 1]], { auroc: '0.67' }), /AUROC 0\.67/);
  const upset = upsetSvg([{ sources: '101', genes: 5 }], ['<i>a</i>', 'b', 'c']);
  assert.ok(upset.includes('&lt;i&gt;a&lt;/i&gt;'));
});

test('two circles are placed so they share the area asked for', () => {
  assert.ok(Math.abs(lensArea(1, 1, 0) - Math.PI) < 1e-12);
  assert.equal(lensArea(1, 1, 2), 0);
  for (const [r1, r2, share] of [[3, 1, 0.97], [2, 2, 0.5], [5, 1.5, 0.1]]) {
    const area = share * Math.PI * Math.min(r1, r2) ** 2;
    const d = distanceForOverlap(r1, r2, area);
    assert.ok(Math.abs(lensArea(r1, r2, d) - area) < 1e-6, `${r1}, ${r2}, ${share}`);
  }
});
