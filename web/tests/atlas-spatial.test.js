// The atlas's geometry (web/js/atlas/spatial.js): the camera pose, nearby
// cells, picking, the file's sheet and class names.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  CLOUD, DEFAULT_POSE, boundingSphere, buildGrid, cloudSize, fileCloudLayout, fileGridLayout, nearestOfClasses,
  orbitPosition, pickScreen, placeLabels, projectAll,
} from '../js/atlas/spatial.js';
import { rng } from '../js/random.js';

const points = (n, seed) => {
  const r = rng(seed);
  return Float32Array.from({ length: n * 3 }, () => (r() - 0.5) * 80);
};

test('the default view is the one the atlas has always opened on', () => {
  const [x, y, z] = orbitPosition(DEFAULT_POSE);
  assert.deepEqual([Math.round(x), Math.round(y), Math.round(z)], [-33, -39, -40]);
  const p = orbitPosition({ target: [1, 2, 3], yaw: 0, pitch: 0, radius: 10 });
  assert.deepEqual(p, [1, 2, 13]);
});

test('the grid finds the same nearest cells as checking every cell', () => {
  const n = 4000;
  const pos = points(n, 7);
  const kind = Uint8Array.from({ length: n }, (_, i) => i % 5);
  const grid = buildGrid(pos, n, 4);
  const r = rng(11);
  for (let t = 0; t < 40; t += 1) {
    const p = [(r() - 0.5) * 70, (r() - 0.5) * 70, (r() - 0.5) * 70];
    const accept = (i) => kind[i] === 2 || kind[i] === 3;
    const got = nearestOfClasses(grid, p, accept, 6, 30);
    const brute = [...Array(n).keys()].filter(accept)
      .map((i) => [(pos[i * 3] - p[0]) ** 2 + (pos[i * 3 + 1] - p[1]) ** 2 + (pos[i * 3 + 2] - p[2]) ** 2, i])
      .filter((d) => d[0] <= 900)
      .sort((a, b) => a[0] - b[0] || a[1] - b[1])
      .slice(0, 6)
      .map((d) => d[1]);
    assert.deepEqual(got, brute);
    for (const i of got) assert.ok(accept(i));
  }
  assert.deepEqual(nearestOfClasses(grid, [0, 0, 0], () => false, 6, 30), []);
});

test('picking takes the nearest visible point within reach, or none', () => {
  // An identity view: clip space is the scene.
  const m = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const pos = Float32Array.from([0, 0, 0, 0.1, 0, 0, -0.5, 0.5, 0]);
  const screen = projectAll(pos, 3, m, 200, 200);
  assert.deepEqual([...screen.slice(0, 3)], [100, 100, 1]);
  assert.equal(pickScreen(screen, 3, 101, 100, 5), 0);
  assert.equal(pickScreen(screen, 3, 109, 100, 5), 1);
  assert.equal(pickScreen(screen, 3, 101, 100, 5, (i) => i !== 0), -1, 'a hidden point is never picked');
  assert.equal(pickScreen(screen, 3, 150, 150, 5), -1);
  // Behind the camera: never picked.
  const behind = projectAll(Float32Array.from([0, 0, 0]), 1, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1], 200, 200);
  assert.equal(behind[2], Infinity);
  assert.equal(pickScreen(behind, 1, 100, 100, 50), -1);
});

test('every cell of a file gets its own slot on the sheet', () => {
  for (const n of [1, 2, 20, 238, 2000]) {
    const { cols, rows, slots } = fileGridLayout(n);
    assert.ok(cols * rows >= n && cols >= rows);
    const seen = new Set();
    for (let i = 0; i < n; i += 1) {
      const u = slots[i * 2];
      const v = slots[i * 2 + 1];
      assert.ok(u >= 0 && u <= 1 && v >= 0 && v <= 1);
      seen.add(`${u},${v}`);
    }
    assert.equal(seen.size, n);
  }
});

test('class names never overlap, and the first in line is always shown', () => {
  const r = rng(3);
  const boxes = Array.from({ length: 40 }, () => ({ x: r() * 300, y: r() * 200, w: 30 + r() * 60, h: 14 }));
  const shown = placeLabels(boxes);
  assert.equal(shown[0], true);
  const kept = boxes.filter((_, i) => shown[i]);
  for (let a = 0; a < kept.length; a += 1) {
    for (let b = a + 1; b < kept.length; b += 1) {
      const overlap = Math.abs(kept[a].x - kept[b].x) * 2 < kept[a].w + kept[b].w
        && Math.abs(kept[a].y - kept[b].y) * 2 < kept[a].h + kept[b].h;
      assert.ok(!overlap);
    }
  }
  assert.equal(placeLabels([null, { x: 0, y: 0, w: 10, h: 10 }])[0], false);
});

test('the sphere round a set of points holds them all', () => {
  const pos = points(500, 5);
  const { centre, radius } = boundingSphere(pos, 500);
  for (let i = 0; i < 500; i += 1) {
    const d = Math.hypot(pos[i * 3] - centre[0], pos[i * 3 + 1] - centre[1], pos[i * 3 + 2] - centre[2]);
    assert.ok(d <= radius + 1e-9);
  }
  assert.deepEqual(boundingSphere(pos, 0), { centre: [0, 0, 0], radius: 0 });
});

test('the file waits as an irregular cloud: inside the unit ball, deep, the same for the same seed', () => {
  for (const n of [1, 20, 238, 2000]) {
    const cloud = fileCloudLayout(n, 7);
    assert.equal(cloud.length, n * 3);
    assert.ok(cloud.every(Number.isFinite), `${n}: finite`);
    for (let i = 0; i < n; i += 1) {
      assert.ok(Math.hypot(cloud[i * 3], cloud[i * 3 + 1], cloud[i * 3 + 2]) <= 1 + 1e-6, `${n}: cell ${i} inside`);
    }
    assert.deepEqual(fileCloudLayout(n, 7), cloud, `${n}: the same seed, the same cloud`);
  }
  const cloud = fileCloudLayout(500, 7);
  assert.notDeepEqual(fileCloudLayout(500, 8), cloud, 'another seed, another shape');
  const column = (k) => Array.from({ length: 500 }, (_, i) => cloud[i * 3 + k]);
  const spread = (xs) => Math.max(...xs) - Math.min(...xs);
  assert.ok(spread(column(2)) > 0.2, 'it has depth');
  assert.ok(spread(column(2)) < spread(column(0)), 'flatter in depth than across');
  // Not a grid, and no two cells in one place.
  assert.equal(new Set(Array.from({ length: 500 }, (_, i) => `${cloud[i * 3]},${cloud[i * 3 + 1]},${cloud[i * 3 + 2]}`)).size, 500);
  assert.equal(new Set(column(0)).size, 500, 'no shared columns');
  // Lumpy, not a ball: for nearly every seed, the cells are far from evenly
  // spread round the centre (one of eight sectors holds over twice another's).
  const lumpy = Array.from({ length: 20 }, (_, k) => {
    const c = fileCloudLayout(500, 0x5eed + k * 97);
    const sectors = new Array(8).fill(0);
    for (let i = 0; i < 500; i += 1) sectors[Math.floor(((Math.atan2(c[i * 3 + 1], c[i * 3]) + Math.PI) / (2 * Math.PI)) * 8) % 8] += 1;
    return Math.max(...sectors) > 2 * Math.min(...sectors);
  });
  assert.ok(lumpy.filter(Boolean).length >= 16, `lumpy for ${lumpy.filter(Boolean).length} of 20 seeds`);
});

test('the cloud and its resting cells are sized by the number of cells', () => {
  let last = 0;
  for (const n of [1, 10, 100, 238, 1000, 2000]) {
    const { radius, dot } = cloudSize(n);
    assert.ok(radius >= CLOUD.radius[0] && radius <= CLOUD.radius[1], `${n}: radius ${radius}`);
    assert.ok(radius >= last, 'more cells, no smaller a cloud');
    last = radius;
    assert.ok(dot >= CLOUD.dot[0] && dot <= CLOUD.dot[1], `${n}: dot ${dot}`);
  }
  assert.ok(cloudSize(2000).dot < cloudSize(20).dot, 'a crowded cloud has smaller dots');
});
