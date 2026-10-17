// Geometry for the atlas: the orbit camera's pose, a grid for finding nearby
// reference cells, picking a cell on screen, the cloud an uploaded file waits
// in, and placing class names so they never overlap. Pure: no DOM, no THREE,
// so node --test covers it.

import { rng } from '../random.js';

// The view the atlas opens on (the viewer's long-standing default).
export const DEFAULT_POSE = { target: [0, 0, 0], yaw: -2.45, pitch: 0.64, radius: 65 };
export const PITCH_LIMIT = Math.PI / 2 - 0.1;
export const RADIUS_RANGE = [10, 200];

// Where the camera sits for a pose: on a sphere round the target, with the
// scene's y axis pointing down the screen (camera up = (0, -1, 0)), as the
// viewer has always drawn it.
export function orbitPosition({ target = [0, 0, 0], yaw, pitch, radius }) {
  return [
    target[0] + radius * Math.sin(yaw) * Math.cos(pitch),
    target[1] - radius * Math.sin(pitch),
    target[2] + radius * Math.cos(yaw) * Math.cos(pitch),
  ];
}

// ---- nearby reference cells ----

const OFFSET = 512;
const key = (x, y, z) => ((x + OFFSET) * 1024 + (y + OFFSET)) * 1024 + (z + OFFSET);

// Cells bucketed into cubes of side `cell` scene units.
export function buildGrid(pos, n, cell) {
  const map = new Map();
  for (let i = 0; i < n; i += 1) {
    const k = key(Math.floor(pos[i * 3] / cell), Math.floor(pos[i * 3 + 1] / cell), Math.floor(pos[i * 3 + 2] / cell));
    let list = map.get(k);
    if (!list) map.set(k, (list = []));
    list.push(i);
  }
  return { pos, n, cell, map };
}

// The k cells nearest p that `accept` keeps, within maxR scene units,
// nearest first. The search widens one shell of cubes at a time and stops
// once the k-th distance is inside the searched radius.
export function nearestOfClasses(grid, p, accept, k, maxR) {
  const { pos, cell, map } = grid;
  const c = p.map((v) => Math.floor(v / cell));
  const found = [];
  const maxShell = Math.ceil(maxR / cell);
  for (let shell = 0; shell <= maxShell; shell += 1) {
    for (let dx = -shell; dx <= shell; dx += 1) {
      for (let dy = -shell; dy <= shell; dy += 1) {
        for (let dz = -shell; dz <= shell; dz += 1) {
          if (Math.max(Math.abs(dx), Math.abs(dy), Math.abs(dz)) !== shell) continue;
          const list = map.get(key(c[0] + dx, c[1] + dy, c[2] + dz));
          if (!list) continue;
          for (const i of list) {
            if (!accept(i)) continue;
            const d2 = (pos[i * 3] - p[0]) ** 2 + (pos[i * 3 + 1] - p[1]) ** 2 + (pos[i * 3 + 2] - p[2]) ** 2;
            if (d2 <= maxR * maxR) found.push([d2, i]);
          }
        }
      }
    }
    if (found.length >= k) {
      found.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      // Every cell within `shell * cell` of p has been seen, so the k nearest
      // are final once the k-th sits inside that radius.
      if (Math.sqrt(found[k - 1][0]) <= shell * cell) break;
    }
  }
  found.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return found.slice(0, k).map((f) => f[1]);
}

// ---- picking on screen ----

// Every point's screen position (x, y in CSS pixels, from the top left) and
// clip w, through a column-major 4x4 view-projection matrix (THREE.Matrix4's
// elements). A point behind the camera gets w = Infinity.
export function projectAll(pos, n, m, width, height, out = new Float32Array(n * 3)) {
  for (let i = 0; i < n; i += 1) {
    const x = pos[i * 3];
    const y = pos[i * 3 + 1];
    const z = pos[i * 3 + 2];
    const w = m[3] * x + m[7] * y + m[11] * z + m[15];
    if (w <= 1e-6) {
      out[i * 3 + 2] = Infinity;
      continue;
    }
    const cx = (m[0] * x + m[4] * y + m[8] * z + m[12]) / w;
    const cy = (m[1] * x + m[5] * y + m[9] * z + m[13]) / w;
    out[i * 3] = ((cx + 1) / 2) * width;
    out[i * 3 + 1] = ((1 - cy) / 2) * height;
    out[i * 3 + 2] = w;
  }
  return out;
}

// The visible point nearest (x, y) within radius px, or -1; between two at
// the same distance, the one nearer the camera.
export function pickScreen(screen, n, x, y, radius, visible = null) {
  let best = -1;
  let bestD2 = radius * radius;
  let bestW = Infinity;
  for (let i = 0; i < n; i += 1) {
    const w = screen[i * 3 + 2];
    if (w === Infinity) continue;
    const d2 = (screen[i * 3] - x) ** 2 + (screen[i * 3 + 1] - y) ** 2;
    if (d2 > bestD2 || (d2 === bestD2 && w >= bestW)) continue;
    if (visible && !visible(i)) continue;
    best = i;
    bestD2 = d2;
    bestW = w;
  }
  return best;
}

// ---- the file's sheet ----

// One slot per cell on a sheet, row by row, as (u, v) in 0..1 with v
// increasing down the sheet. The sheet is wider than tall, like a page
// turned sideways.
export function fileGridLayout(n, aspect = 1.6) {
  const cols = Math.max(1, Math.ceil(Math.sqrt(n * aspect)));
  const rows = Math.max(1, Math.ceil(n / cols));
  const slots = new Float32Array(n * 2);
  for (let i = 0; i < n; i += 1) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    slots[i * 2] = cols === 1 ? 0.5 : col / (cols - 1);
    slots[i * 2 + 1] = rows === 1 ? 0.5 : row / (rows - 1);
  }
  return { cols, rows, slots };
}

// ---- the file's cloud ----

// Before its cells fly, an uploaded file waits beside the atlas as a cloud:
// an irregular, lumpy shape of a few overlapping lobes, as a cluster of the
// reference looks. The shape is decoration (the cells have no answers yet)
// and the same for the same seed. Sizes in scene units.
export const CLOUD = {
  lobes: 4,          // overlapping lobes, each a stretched, turned Gaussian
  spread: 0.8,       // how far the lobes sit from the first, in the cloud's units
  depth: 0.35,       // the lobes' spread in depth, flatter than across
  edge: 0.98,        // the share of cells inside the unit radius; the rest are pulled to its edge
  perCell: 2.2,      // the cloud's radius grows with the cube root of the cells ...
  radius: [6, 15],   // ... between these
  dotShare: 0.35,    // a resting cell's radius, as a share of the typical spacing
  dot: [0.3, 0.9],   // between these (0.9: a flying cell's full radius)
};

// Each cell's resting place, as x, y, z in a unit ball (z the depth), cell
// i in slot i.
export function fileCloudLayout(n, seed = 1) {
  const random = rng(seed);
  const gauss = () => Math.sqrt(-2 * Math.log(Math.max(1e-12, random()))) * Math.cos(2 * Math.PI * random());
  const lobes = Array.from({ length: CLOUD.lobes }, (_, k) => {
    const angle = random() * 2 * Math.PI;
    const away = k === 0 ? 0 : CLOUD.spread * (0.5 + 0.5 * random());
    return {
      at: [Math.cos(angle) * away, Math.sin(angle) * away * 0.8, (random() - 0.5) * CLOUD.depth],
      sd: [0.16 + 0.16 * random(), 0.1 + 0.12 * random(), 0.08 + 0.08 * random()],
      turn: random() * Math.PI,
      weight: 0.5 + random(),
    };
  });
  const total = lobes.reduce((sum, l) => sum + l.weight, 0);
  const out = new Float32Array(n * 3);
  const reach = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    let pick = random() * total;
    const lobe = lobes.find((l) => (pick -= l.weight) <= 0) ?? lobes[lobes.length - 1];
    const a = gauss() * lobe.sd[0];
    const b = gauss() * lobe.sd[1];
    const cos = Math.cos(lobe.turn);
    const sin = Math.sin(lobe.turn);
    out[i * 3] = lobe.at[0] + a * cos - b * sin;
    out[i * 3 + 1] = lobe.at[1] + a * sin + b * cos;
    out[i * 3 + 2] = lobe.at[2] + gauss() * lobe.sd[2];
  }
  // Centred, and scaled so CLOUD.edge of the cells fall inside the unit ball;
  // the few beyond are pulled to its edge.
  const mean = [0, 1, 2].map((k) => { let s = 0; for (let i = 0; i < n; i += 1) s += out[i * 3 + k]; return n ? s / n : 0; });
  for (let i = 0; i < n; i += 1) {
    for (let k = 0; k < 3; k += 1) out[i * 3 + k] -= mean[k];
    reach[i] = Math.hypot(out[i * 3], out[i * 3 + 1], out[i * 3 + 2]);
  }
  const sorted = Float32Array.from(reach).sort();
  const scale = n ? 1 / Math.max(1e-6, sorted[Math.floor(CLOUD.edge * (n - 1))]) : 1;
  for (let i = 0; i < n; i += 1) {
    const shrink = Math.min(scale, 1 / Math.max(1e-6, reach[i]));
    for (let k = 0; k < 3; k += 1) out[i * 3 + k] *= shrink;
  }
  return out;
}

// The cloud's radius and a resting cell's radius for n cells, in scene units.
export function cloudSize(n) {
  const cells = Math.max(1, n);
  const radius = Math.min(CLOUD.radius[1], Math.max(CLOUD.radius[0], CLOUD.perCell * Math.cbrt(cells)));
  const spacing = (2 * radius) / Math.cbrt(cells);
  const dot = Math.min(CLOUD.dot[1], Math.max(CLOUD.dot[0], CLOUD.dotShare * spacing));
  return { radius, dot };
}

// ---- class names ----

// Which labels to show: each box {x, y, w, h} (centred on x, y) in priority
// order is kept unless it overlaps one already kept.
export function placeLabels(boxes, pad = 4) {
  const kept = [];
  return boxes.map((b) => {
    if (!b) return false;
    const clash = kept.some((k) => Math.abs(k.x - b.x) * 2 < k.w + b.w + pad * 2
      && Math.abs(k.y - b.y) * 2 < k.h + b.h + pad * 2);
    if (clash) return false;
    kept.push(b);
    return true;
  });
}

// The sphere round a set of points: their centroid and the farthest from it.
export function boundingSphere(points, n) {
  if (n === 0) return { centre: [0, 0, 0], radius: 0 };
  const centre = [0, 0, 0];
  for (let i = 0; i < n; i += 1) for (let k = 0; k < 3; k += 1) centre[k] += points[i * 3 + k] / n;
  let r2 = 0;
  for (let i = 0; i < n; i += 1) {
    const d2 = (points[i * 3] - centre[0]) ** 2 + (points[i * 3 + 1] - centre[1]) ** 2 + (points[i * 3 + 2] - centre[2]) ** 2;
    if (d2 > r2) r2 = d2;
  }
  return { centre, radius: Math.sqrt(r2) };
}
