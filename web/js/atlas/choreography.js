// When things move on the Atlas page after an upload: the six waiting steps
// while the service works, the receipt, the cells flying from the file's
// sheet onto the atlas level by level, the settle, and the camera pose that
// frames them. Pure: no DOM, no THREE, no clock; every function takes the
// time it is asked about, so node --test covers it. Times are in seconds.

import { DEFAULT_POSE } from './spatial.js';

export const TIMING = Object.freeze({
  flight: 1.6, // one cell's flight from the sheet to its place
  levelGap: 0.4, // between one level's last take-off and the next level's first (short, so each wave keeps time to spread)
  flyWindow: Object.freeze([3.4, 4.7]), // the fly-in lasts this long, however many cells
  receipt: 2.2, // the receipt alone, before anything flies
  settle: 2.2, // after the last landing, before the page hands over
  finishMax: 1.2, // the waiting steps catch up at most this fast when the answer comes
  step: 2.2, // one waiting step
  exampleStep: 1.0, // one waiting step for the recorded example
  bench: 0.9, // the file sliding onto the bench
  flyToCell: 1.0, // the camera flying to a clicked cell
});

// Which wave a cell lands in: an answer of one type first, then a family,
// then a branch, then no answer. A cell with too little measured, without
// coordinates, or from a service on another map is not flown: it stays on
// the file's sheet (answers.js, answerStyle).
export const LEVELS = Object.freeze({
  class: 0,
  group: 1,
  lineage: 2,
  ambiguous_between_classes: 3,
  no_confident_label: 3,
  outside_supported_region: 3,
  coverage_too_low: null,
});
export const LEVEL_COUNT = 4;

export function levelOf(cell, placeable = true) {
  if (!placeable || !Array.isArray(cell?.xyz) || cell.xyz.length !== 3) return null;
  const level = LEVELS[cell.outcome];
  // An outcome this page does not know is drawn as no answer, so it lands
  // with them.
  return level === undefined ? 3 : level;
}

const finiteOrNull = (v) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? null : Number(v));

// Within a level: the strongest first (confidence; for no answer, likeness
// to the reference), a missing value last, ties by position in the file.
function byStrength(cells, key) {
  return (a, b) => {
    const va = finiteOrNull(cells[a][key]);
    const vb = finiteOrNull(cells[b][key]);
    if (va === null || vb === null) return (va === null) - (vb === null) || a - b;
    return vb - va || a - b;
  };
}

// The fly-in window grows with the number of levels flown, from 30% to 90%
// of the way through T.flyWindow, so one level and four both fit.
function windowTarget(levels, T) {
  const [lo, hi] = T.flyWindow;
  return lo + (hi - lo) * (0.3 + (0.6 * (levels - 1)) / (LEVEL_COUNT - 1));
}

// Every cell's take-off (delay from the start of the fly-in window) and
// flight time, which cells fly, the order they land in, and the window's
// length. Each level's take-offs are spread over its share of the window
// (a share growing with the square root of its size), so 1 cell and 2,000
// take the same time.
export function flightSchedule(cells, { placeable = true, T = TIMING } = {}) {
  const n = cells.length;
  const delay = new Float32Array(n);
  const duration = new Float32Array(n);
  const flies = new Uint8Array(n);
  const groups = Array.from({ length: LEVEL_COUNT }, () => []);
  for (let i = 0; i < n; i += 1) {
    const level = levelOf(cells[i], placeable);
    if (level !== null) groups[level].push(i);
  }
  groups.forEach((g, level) => g.sort(byStrength(cells, level === 3 ? 'similarity' : 'confidence')));
  const flown = groups.filter((g) => g.length > 0);
  const order = new Int32Array(flown.reduce((sum, g) => sum + g.length, 0));
  if (flown.length === 0) return { delay, duration, flies, order, end: 0 };

  const fixed = T.flight + (flown.length - 1) * T.levelGap;
  const target = windowTarget(flown.length, T);
  const spread = Math.max(0, target - fixed);
  const weights = flown.map((g) => Math.sqrt(g.length - 1));
  const total = weights.reduce((a, b) => a + b, 0);
  let start = 0;
  let k = 0;
  flown.forEach((g, j) => {
    const span = total > 0 ? (spread * weights[j]) / total : 0;
    g.forEach((i, r) => {
      delay[i] = g.length > 1 ? start + (span * r) / (g.length - 1) : start;
      duration[i] = T.flight;
      flies[i] = 1;
      order[k] = i;
      k += 1;
    });
    start += span + T.levelGap;
  });
  // From the stored (float32) times, so no landing is ever past the end.
  let lastLanding = 0;
  for (const i of order) lastLanding = Math.max(lastLanding, delay[i] + duration[i]);
  // A few cells land early; the window still keeps its length, so the phase
  // reads the same however few cells fly.
  return { delay, duration, flies, order, end: Math.max(lastLanding, target) };
}

// How far cell i is along its flight at t seconds into the fly-in, 0 to 1.
export function flightProgress(schedule, i, t) {
  if (!schedule.flies[i]) return 0;
  const d = schedule.duration[i];
  if (d <= 0) return t >= schedule.delay[i] ? 1 : 0;
  return Math.min(1, Math.max(0, (t - schedule.delay[i]) / d));
}

// The guided landing, from the moment the answer is shown: the receipt, the
// fly-in, the settle.
export function landingTimeline(schedule, { T = TIMING } = {}) {
  const a = T.receipt;
  const b = a + schedule.end;
  const c = b + T.settle;
  return { receipt: [0, a], fly: [a, b], settle: [b, c], total: c };
}

// ---- while the service works ----

export const WAITING_STEPS = 6;

// Which of the six waiting steps is showing after `elapsed` seconds, how far
// through it, and how many times the steps have looped. They loop until the
// answer comes.
export function waitingFrame(elapsed, { stepSeconds = TIMING.step } = {}) {
  if (!(stepSeconds > 0) || !Number.isFinite(elapsed) || elapsed <= 0) return { step: 0, stepT: 0, loop: 0 };
  const steps = elapsed / stepSeconds;
  const whole = Math.floor(steps);
  return { step: whole % WAITING_STEPS, stepT: steps - whole, loop: Math.floor(whole / WAITING_STEPS) };
}

// When the answer comes: the seconds the remaining steps take at 4x speed,
// at most T.finishMax.
export function finishWaiting(frame, { T = TIMING, stepSeconds = T.step } = {}) {
  const remaining = Math.max(0, WAITING_STEPS - frame.step - frame.stepT);
  return Math.min(T.finishMax, (remaining * stepSeconds) / 4);
}

// The waiting frame t seconds into that finish; at its end, the last step
// complete.
export function finishingFrame(frame, t, { T = TIMING, stepSeconds = T.step } = {}) {
  const seconds = finishWaiting(frame, { T, stepSeconds });
  const from = frame.step + frame.stepT;
  const u = seconds > 0 ? Math.min(1, Math.max(0, t / seconds)) : 1;
  const at = from + (WAITING_STEPS - from) * u;
  const step = Math.min(WAITING_STEPS - 1, Math.floor(at));
  return { step, stepT: Math.min(1, at - step), loop: frame.loop, done: u >= 1 };
}

// ---- the camera ----

const RAD = Math.PI / 180;

// The orbit pose that shows the whole sphere, with room to spare: far
// enough that the sphere, grown by `margin`, fits the narrower of the two
// fields of view. Never nearer than minRadius.
export function framePose(sphere, {
  fovDeg = 75, aspect = 1, yaw = DEFAULT_POSE.yaw, pitch = DEFAULT_POSE.pitch, margin = 1.25, minRadius = 45,
} = {}) {
  const halfV = (fovDeg * RAD) / 2;
  const halfH = Math.atan(Math.tan(halfV) * (aspect > 0 ? aspect : 1));
  const half = Math.min(halfV, halfH);
  const fit = ((sphere?.radius ?? 0) * margin) / Math.sin(half);
  return { target: [...(sphere?.centre ?? [0, 0, 0])], yaw, pitch, radius: Math.max(minRadius, fit) };
}

// ---- reduced motion ----

// The same shape with nothing moving: every duration 0.
export function reducedTiming() {
  const out = {};
  for (const [key, value] of Object.entries(TIMING)) out[key] = Array.isArray(value) ? value.map(() => 0) : 0;
  return out;
}
