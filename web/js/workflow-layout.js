// Layout maths for the Workflow page's figures: scales, histogram bars, the
// Sankey of outcomes, the radial class compass, colour ramps and the 3D view.
// Pure: no DOM, so node --test covers it. None of it computes a model output;
// every value it lays out comes from web/data/workflow.json.

export const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const ease = (t) => { const x = clamp(t, 0, 1); return x * x * (3 - 2 * x); };
// Remap p into the window [a, b], clamped and eased.
export const phase = (p, a, b) => (b <= a ? (p >= b ? 1 : 0) : ease((p - a) / (b - a)));

// A linear scale from a domain onto a range.
export function linear([d0, d1], [r0, r1]) {
  const span = d1 - d0 || 1;
  return (x) => r0 + ((x - d0) / span) * (r1 - r0);
}

// Round tick values across [lo, hi], about n of them.
export function ticks(lo, hi, n = 5) {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / Math.max(1, n);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Math.round(v / step) * step);
  return out;
}

// Bars for histogram counts across a width, each {x, y, w, h, count}.
export function histogramBars(counts, width, height, gap = 1) {
  const max = Math.max(1, ...counts);
  const w = width / Math.max(1, counts.length);
  return counts.map((count, i) => {
    const h = (count / max) * height;
    return { x: i * w + gap / 2, y: height - h, w: Math.max(0, w - gap), h, count };
  });
}

// ---- the Sankey: flows from a left column of nodes to a right one ----
// flows: [{source, target, value}]; the orders fix each column's top-down
// order. Every node is as tall as its flow, so what leaves equals what arrives.
export function sankey(flows, sourceOrder, targetOrder, { width = 600, height = 300, gap = 8, node = 12 } = {}) {
  const total = flows.reduce((s, f) => s + f.value, 0) || 1;
  const column = (order, key) => {
    const sums = order.map((k) => flows.filter((f) => f[key] === k).reduce((s, f) => s + f.value, 0));
    const shown = order.filter((_, i) => sums[i] > 0);
    const scale = (height - gap * Math.max(0, shown.length - 1)) / total;
    let y = 0;
    const nodes = {};
    order.forEach((k, i) => {
      if (sums[i] <= 0) return;
      nodes[k] = { key: k, y, h: sums[i] * scale, value: sums[i], used: 0 };
      y += sums[i] * scale + gap;
    });
    return { nodes, scale };
  };
  const left = column(sourceOrder, 'source');
  const right = column(targetOrder, 'target');
  const links = [];
  for (const s of sourceOrder) {
    for (const t of targetOrder) {
      const f = flows.find((x) => x.source === s && x.target === t);
      if (!f || f.value <= 0) continue;
      const a = left.nodes[s];
      const b = right.nodes[t];
      const h = f.value * left.scale;
      links.push({ source: s, target: t, value: f.value, y0: a.y + a.used, y1: b.y + b.used, h });
      a.used += h;
      b.used += f.value * right.scale;
    }
  }
  const strip = (nodes, x) => Object.values(nodes).map(({ used, ...n }) => ({ ...n, x }));
  return { left: strip(left.nodes, 0), right: strip(right.nodes, width - node), links, node, width, height };
}

// An S-curve between two vertical strips, as an SVG path for a band.
export function bandPath(x0, y0, x1, y1, h) {
  const mid = (x0 + x1) / 2;
  return `M${x0},${y0}C${mid},${y0} ${mid},${y1} ${x1},${y1}L${x1},${y1 + h}C${mid},${y1 + h} ${mid},${y0 + h} ${x0},${y0 + h}Z`;
}

// ---- the compass: classes around a circle, grouped by lineage ----
// Returns each class position's angle (radians, clockwise from the top),
// with a wider gap between lineages.
export function radialAngles(classOrder, hierarchy, lineageGap = 0.35) {
  const lineages = [];
  for (const name of classOrder) {
    const l = hierarchy?.[name]?.lineage ?? 'other';
    if (!lineages.includes(l)) lineages.push(l);
  }
  const ordered = lineages.flatMap((l) => classOrder.map((n, i) => [n, i]).filter(([n]) => (hierarchy?.[n]?.lineage ?? 'other') === l));
  const slots = ordered.length + lineageGap * lineages.length;
  const angles = new Array(classOrder.length).fill(0);
  let pos = 0;
  let last = null;
  for (const [name, i] of ordered) {
    const l = hierarchy?.[name]?.lineage ?? 'other';
    if (l !== last) { pos += lineageGap; last = l; }
    angles[i] = (pos / slots) * 2 * Math.PI;
    pos += 1;
  }
  return angles;
}

// ---- colour ----

const hex = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const toHex = (rgb) => `#${rgb.map((v) => clamp(Math.round(v), 0, 255).toString(16).padStart(2, '0')).join('')}`;
export const mix = (a, b, t) => toHex(hex(a).map((v, i) => lerp(v, hex(b)[i], clamp(t, 0, 1))));

// The reserved colours (docs/web/design.md): never data.
export const RESERVED = ['#C8641E', '#2F8F6A', '#E4577A', '#B42318'];

// Diverging, for z-scores: deep blue below zero, near white at zero, ochre
// above, saturating at |z| = limit.
const RAMP_LOW = '#24508f';
const RAMP_MID = '#f4f3ef';
const RAMP_HIGH = '#9a6a12';
export function diverging(z, limit = 2.5) {
  if (z === null || z === undefined || !Number.isFinite(z)) return null;
  const t = clamp(z / limit, -1, 1);
  return t < 0 ? mix(RAMP_MID, RAMP_LOW, -t) : mix(RAMP_MID, RAMP_HIGH, t);
}

// Sequential, for shares and probabilities 0..1.
export const sequential = (t) => mix('#eef3f8', '#0b4f86', clamp(t, 0, 1));

export function colourDistance(a, b) {
  const [x, y] = [hex(a), hex(b)];
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

// ---- the 3D view ----

export function rotate([x, y, z], yaw, pitch) {
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const x1 = x * cy + z * sy;
  const z1 = -x * sy + z * cy;
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  return [x1, y * cp - z1 * sp, y * sp + z1 * cp];
}

// Perspective onto a w x h screen; the camera looks down -z from `distance`.
export function project([x, y, z], { width, height, scale, distance = 4 }) {
  const f = distance / (distance - z);
  return { x: width / 2 + x * scale * f, y: height / 2 - y * scale * f, depth: z, f };
}

// Indices back to front, so nearer points draw last.
export function depthOrder(projected) {
  return [...projected.keys()].sort((a, b) => projected[a].depth - projected[b].depth);
}

// The nearest projected point within r pixels, or -1.
export function pickNearest(projected, x, y, r = 8) {
  let best = -1;
  let bestD = r * r;
  projected.forEach((p, i) => {
    const d = (p.x - x) ** 2 + (p.y - y) ** 2;
    if (d <= bestD) { best = i; bestD = d; }
  });
  return best;
}

// The recorded ROC point nearest a false-positive rate.
export function rocSnap(curve, fpr) {
  let best = curve[0];
  for (const point of curve) if (Math.abs(point[0] - fpr) < Math.abs(best[0] - fpr)) best = point;
  return best;
}

// A centred, uniformly scaled view of 3D points: the factor that fits them
// in a unit sphere, and their centre.
export function fitSphere(points) {
  if (!points.length) return { centre: [0, 0, 0], radius: 1 };
  const centre = [0, 1, 2].map((k) => points.reduce((s, p) => s + p[k], 0) / points.length);
  const radius = Math.max(1e-9, ...points.map((p) => Math.hypot(p[0] - centre[0], p[1] - centre[1], p[2] - centre[2])));
  return { centre, radius };
}

// The area two circles share: radii r1 and r2, centres d apart.
export function lensArea(r1, r2, d) {
  if (d >= r1 + r2) return 0;
  if (d <= Math.abs(r1 - r2)) return Math.PI * Math.min(r1, r2) ** 2;
  const a = r1 * r1 * Math.acos((d * d + r1 * r1 - r2 * r2) / (2 * d * r1));
  const b = r2 * r2 * Math.acos((d * d + r2 * r2 - r1 * r1) / (2 * d * r2));
  const c = 0.5 * Math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2));
  return a + b - c;
}

// The centre distance at which two circles share `area` (bisection; the
// shared area shrinks as the circles move apart).
export function distanceForOverlap(r1, r2, area) {
  let lo = Math.abs(r1 - r2);
  let hi = r1 + r2;
  if (area >= lensArea(r1, r2, lo)) return lo;
  if (area <= 0) return hi;
  for (let k = 0; k < 60; k += 1) {
    const mid = (lo + hi) / 2;
    if (lensArea(r1, r2, mid) > area) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
}
