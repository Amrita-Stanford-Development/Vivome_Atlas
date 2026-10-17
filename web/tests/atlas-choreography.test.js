// When things move after an upload (web/js/atlas/choreography.js): the
// fly-in schedule, the landing timeline, the waiting steps, the camera pose
// and reduced motion.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  LEVELS, TIMING, WAITING_STEPS, finishWaiting, finishingFrame, flightProgress, flightSchedule, framePose,
  landingTimeline, levelOf, reducedTiming, waitingFrame,
} from '../js/atlas/choreography.js';
import { DEFAULT_POSE } from '../js/atlas/spatial.js';

const EPS = 1e-5;
const OUTCOMES = ['class', 'group', 'lineage', 'ambiguous_between_classes', 'no_confident_label', 'outside_supported_region'];

// n cells in the answers.js shape; `outcomeOf(i)` picks each one's outcome.
function makeCells(n, outcomeOf = () => 'class') {
  return Array.from({ length: n }, (_, i) => ({
    index: i,
    outcome: outcomeOf(i),
    confidence: ((i * 37) % 100) / 100,
    similarity: ((i * 53) % 100) / 100,
    xyz: [i % 7, i % 11, i % 13],
  }));
}

// The window from the first take-off to the last landing, checked against
// the schedule's own end and T.flyWindow.
function assertWindow(s, T = TIMING) {
  let first = Infinity;
  let last = 0;
  for (const i of s.order) {
    first = Math.min(first, s.delay[i]);
    last = Math.max(last, s.delay[i] + s.duration[i]);
  }
  assert.equal(first, 0, 'the first take-off opens the window');
  assert.ok(last <= s.end + EPS, `last landing ${last} after the end ${s.end}`);
  assert.ok(s.end >= T.flyWindow[0] - EPS && s.end <= T.flyWindow[1] + EPS, `window ${s.end}`);
}

test('the timing is the agreed one', () => {
  assert.deepEqual({ ...TIMING, flyWindow: [...TIMING.flyWindow] }, {
    flight: 1.6, levelGap: 0.4, flyWindow: [3.4, 4.7], receipt: 2.2, settle: 2.2, finishMax: 1.2, step: 2.2,
    exampleStep: 1.0, bench: 0.9, flyToCell: 1.0,
  });
  assert.ok(Object.isFrozen(TIMING) && Object.isFrozen(TIMING.flyWindow));
});

test('each outcome lands in its wave; unplaced cells do not fly', () => {
  const cell = (outcome, xyz = [0, 0, 0]) => ({ outcome, xyz });
  assert.deepEqual(OUTCOMES.map((o) => levelOf(cell(o))), [0, 1, 2, 3, 3, 3]);
  assert.deepEqual(OUTCOMES.map((o) => LEVELS[o]), [0, 1, 2, 3, 3, 3]);
  assert.equal(levelOf(cell('coverage_too_low')), null);
  assert.equal(levelOf(cell('class', null)), null, 'no coordinates');
  assert.equal(levelOf(cell('class'), false), null, 'a service on another map');
  assert.equal(levelOf(cell('something new')), 3, 'an unknown outcome lands with no answer, as answers.js draws it');
});

test('the fly-in fits its window for any number of cells, in one level or four', () => {
  const mixes = {
    one: () => 'class',
    four: (i) => OUTCOMES[i % OUTCOMES.length],
    skewed: (i) => (i % 50 === 0 ? 'no_confident_label' : i % 17 === 0 ? 'group' : i % 23 === 0 ? 'lineage' : 'class'),
  };
  for (const n of [1, 2, 3, 238, 2000]) {
    for (const [mix, outcomeOf] of Object.entries(mixes)) {
      const cells = makeCells(n, outcomeOf);
      const s = flightSchedule(cells);
      assert.equal(s.order.length, n, `${mix} ${n}: every cell flies`);
      assertWindow(s);
      for (let i = 0; i < n; i += 1) {
        assert.equal(s.flies[i], 1);
        assert.ok(Math.abs(s.duration[i] - TIMING.flight) < EPS, 'each flight lasts T.flight');
      }
      const t = landingTimeline(s);
      assert.ok(t.total >= 7.8 - EPS && t.total <= 9.1 + EPS, `${mix} ${n}: total ${t.total}`);
    }
  }
});

test('levels land in order, strongest first, separated by the level gap', () => {
  const cells = makeCells(240, (i) => OUTCOMES[i % 4 === 3 ? 3 + (i % 3) : i % 4]);
  cells[0].confidence = null;
  cells[4].confidence = Number.NaN;
  cells[8].confidence = cells[12].confidence;
  const s = flightSchedule(cells);
  const levels = [...s.order].map((i) => levelOf(cells[i]));
  assert.deepEqual(levels, [...levels].sort((a, b) => a - b), 'by level, 0 to 3');
  for (let k = 1; k < s.order.length; k += 1) {
    const a = s.order[k - 1];
    const b = s.order[k];
    assert.ok(s.delay[b] >= s.delay[a], 'landing order is take-off order');
    if (levels[k] !== levels[k - 1]) {
      assert.ok(Math.abs(s.delay[b] - s.delay[a] - TIMING.levelGap) < EPS, 'the gap between levels');
      continue;
    }
    const key = levels[k] === 3 ? 'similarity' : 'confidence';
    const va = Number.isFinite(cells[a][key]) ? cells[a][key] : null;
    const vb = Number.isFinite(cells[b][key]) ? cells[b][key] : null;
    if (va === null) assert.equal(vb, null, 'a missing value comes last');
    else if (vb !== null) assert.ok(va > vb || (va === vb && a < b), `${key} order at ${k}`);
  }
  const classLevel = [...s.order].filter((i) => levelOf(cells[i]) === 0);
  assert.deepEqual(classLevel.slice(-2), [0, 4], 'null and NaN confidence last, by index');
  assert.deepEqual(flightSchedule(cells), s, 'deterministic');
});

test('empty levels are skipped and cells that stay on the sheet do not fly', () => {
  const cells = makeCells(30, (i) => (i < 10 ? 'class' : i < 20 ? 'no_confident_label' : 'coverage_too_low'));
  cells[5].xyz = null;
  const s = flightSchedule(cells);
  assert.equal(s.order.length, 19);
  for (let i = 0; i < 30; i += 1) {
    if (i >= 20 || i === 5) assert.deepEqual([s.flies[i], s.delay[i], s.duration[i]], [0, 0, 0], `cell ${i}`);
  }
  const lastClass = Math.max(...[...s.order].filter((i) => i < 10).map((i) => s.delay[i]));
  const firstNone = Math.min(...[...s.order].filter((i) => i >= 10).map((i) => s.delay[i]));
  assert.ok(Math.abs(firstNone - lastClass - TIMING.levelGap) < EPS, 'one gap, not three');
  assertWindow(s);

  const off = flightSchedule(cells, { placeable: false });
  assert.equal(off.order.length, 0);
  assert.equal(off.end, 0);
  assert.ok(off.flies.every((f) => f === 0));
  assert.deepEqual(landingTimeline(off), { receipt: [0, 2.2], fly: [2.2, 2.2], settle: [2.2, 4.4], total: 4.4 });
  assert.deepEqual(flightSchedule([]).order, new Int32Array(0));
});

test('the landing timeline runs receipt, fly-in, settle back to back', () => {
  for (const n of [1, 238, 2000]) {
    const s = flightSchedule(makeCells(n));
    const t = landingTimeline(s);
    assert.equal(t.receipt[0], 0);
    assert.equal(t.receipt[1], TIMING.receipt);
    assert.equal(t.fly[0], t.receipt[1]);
    assert.ok(Math.abs(t.fly[1] - t.fly[0] - s.end) < EPS);
    assert.equal(t.settle[0], t.fly[1]);
    assert.ok(Math.abs(t.settle[1] - t.settle[0] - TIMING.settle) < EPS);
    assert.equal(t.total, t.settle[1]);
    assert.ok(t.total >= 7.8 && t.total <= 9.1, `n ${n}: ${t.total}`);
  }
  const ends = [1, 2, 238, 2000].map((n) => flightSchedule(makeCells(n)).end);
  assert.ok(ends.every((e) => Math.abs(e - ends[0]) < EPS), `one level lasts the same for any n: ${ends}`);
});

test('a cell moves along its flight from 0 to 1', () => {
  const s = flightSchedule(makeCells(3));
  const i = s.order[1];
  assert.equal(flightProgress(s, i, s.delay[i] - 0.1), 0);
  assert.ok(Math.abs(flightProgress(s, i, s.delay[i] + TIMING.flight / 2) - 0.5) < EPS);
  assert.equal(flightProgress(s, i, s.end), 1);
  const unplaced = flightSchedule(makeCells(1, () => 'coverage_too_low'));
  assert.equal(flightProgress(unplaced, 0, 10), 0);
});

test('the waiting steps loop for as long as the service works', () => {
  assert.equal(WAITING_STEPS, 6);
  assert.deepEqual(waitingFrame(0), { step: 0, stepT: 0, loop: 0 });
  assert.deepEqual(waitingFrame(-3), { step: 0, stepT: 0, loop: 0 });
  const f = waitingFrame(TIMING.step * 2.5);
  assert.equal(f.step, 2);
  assert.ok(Math.abs(f.stepT - 0.5) < EPS);
  assert.equal(f.loop, 0);
  const later = waitingFrame(TIMING.step * (6 * 40 + 5.25));
  assert.deepEqual([later.step, later.loop], [5, 40]);
  assert.ok(Math.abs(later.stepT - 0.25) < 1e-6);
  assert.deepEqual(waitingFrame(3, { stepSeconds: 1 }), { step: 3, stepT: 0, loop: 0 });
  for (let t = 0; t < 200; t += 0.37) {
    const w = waitingFrame(t);
    assert.ok(Number.isInteger(w.step) && w.step >= 0 && w.step < 6);
    assert.ok(w.stepT >= 0 && w.stepT < 1);
    assert.ok(Number.isInteger(w.loop));
  }
});

test('the remaining steps finish at 4x speed, in at most T.finishMax', () => {
  assert.equal(finishWaiting({ step: 0, stepT: 0, loop: 0 }), TIMING.finishMax, 'capped');
  assert.ok(Math.abs(finishWaiting({ step: 5, stepT: 0.5, loop: 2 }) - (0.5 * TIMING.step) / 4) < EPS);
  assert.equal(finishWaiting({ step: 5, stepT: 1, loop: 0 }), 0);
  assert.ok(Math.abs(finishWaiting({ step: 4, stepT: 0.5 }, { stepSeconds: 1 }) - 1.5 / 4) < EPS);
  assert.equal(finishWaiting({ step: 0, stepT: 0 }, { T: reducedTiming() }), 0);

  const from = { step: 3, stepT: 0.5, loop: 1 };
  const seconds = finishWaiting(from);
  const start = finishingFrame(from, 0);
  assert.deepEqual([start.step, start.done], [3, false]);
  assert.ok(Math.abs(start.stepT - 0.5) < EPS);
  assert.deepEqual(finishingFrame(from, seconds), { step: 5, stepT: 1, loop: 1, done: true });
  assert.equal(finishingFrame(from, 0, { T: reducedTiming() }).done, true);
});

test('the camera frames the sphere with room to spare', () => {
  const sphere = { centre: [3, -2, 5], radius: 60 };
  for (const aspect of [0.5, 1, 1.6, 2.4]) {
    const pose = framePose(sphere, { aspect, yaw: 0.3, pitch: 0.2 });
    assert.deepEqual(pose.target, [3, -2, 5]);
    assert.notEqual(pose.target, sphere.centre, 'a copy');
    assert.deepEqual([pose.yaw, pose.pitch], [0.3, 0.2]);
    const halfV = (75 * Math.PI) / 360;
    const halfH = Math.atan(Math.tan(halfV) * aspect);
    for (const half of [halfV, halfH]) {
      // The sphere, grown by the margin, is inside this field of view.
      assert.ok(sphere.radius * 1.25 <= pose.radius * Math.sin(half) + EPS, `aspect ${aspect}`);
    }
    assert.ok(Math.abs(sphere.radius * 1.25 - pose.radius * Math.sin(Math.min(halfV, halfH))) < EPS, 'and no farther');
  }
  const narrow = framePose(sphere, { aspect: 0.5 }).radius;
  const wide = framePose(sphere, { aspect: 2 }).radius;
  assert.ok(narrow > wide, 'a narrow view stands back further');
  assert.equal(framePose({ centre: [0, 0, 0], radius: 1 }, { aspect: 1.6 }).radius, 45, 'never below minRadius');
  assert.equal(framePose({ centre: [0, 0, 0], radius: 1 }, { minRadius: 10 }).radius, 10);
  const d = framePose(sphere);
  assert.deepEqual([d.yaw, d.pitch], [DEFAULT_POSE.yaw, DEFAULT_POSE.pitch], 'the atlas view by default');
});

test('reduced motion: the same shape with every duration 0', () => {
  const r = reducedTiming();
  assert.deepEqual(Object.keys(r), Object.keys(TIMING));
  for (const [key, value] of Object.entries(r)) {
    if (key === 'flyWindow') assert.deepEqual(value, [0, 0]);
    else assert.equal(value, 0, key);
  }
  assert.notEqual(reducedTiming(), r, 'a fresh object each time');
  const s = flightSchedule(makeCells(238, (i) => OUTCOMES[i % 6]), { T: r });
  assert.equal(s.order.length, 238);
  assert.equal(s.end, 0);
  assert.ok(s.delay.every((v) => v === 0) && s.duration.every((v) => v === 0));
  assert.equal(landingTimeline(s, { T: r }).total, 0);
});
