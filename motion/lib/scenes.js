// The scenes' data pictures, drawn on each seek by lib/dive.js: a pure
// function of the time into the scene, like the water. Every value drawn
// comes from web/data/workflow.json (window.VIVOME.atlas3, .map, .cells,
// .heatmap, .answers, written by scripts/prepare.mjs); nothing here
// computes a model output.
//
// DRAW[sceneId](seconds into the scene, progress, frame) draws into the
// scene's canvas, or swaps its Manim frame, and may return a promise the
// frame must wait for. Seconds past the scene's end mean the camera is
// carrying it away while the next scene arrives; lib/bridges.js draws the
// morph between the two, from the places this module exports.

import { diverging } from '../vendor/site/workflow-layout.js';
import { short } from '../vendor/site/scene-kit.js';
import { createMap3D, eyeOf, projectPoint, unprojectPoint } from './map3d.js';
import { OUT } from './camera.js';

const V = window.VIVOME;
const TAU = Math.PI * 2;
export const ACCENT = '#0066A3';
export const RNA = '#C8641E';   // reserved: RNA, and nothing else
export const PROT = '#2F8F6A';  // reserved: protein, and nothing else
export const STREAMS = { encoder: '#0073AD', correlation: '#9A6A12' };

export const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
export const smooth = (x) => { const t = clamp(x); return t * t * (3 - 2 * t); };
const phase = (p, a, b) => smooth((p - a) / (b - a));
export const lerp = (a, b, t) => a + (b - a) * t;
export const mixHex = (a, b, t) => {
  const p = (h) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16));
  const [x, y] = [p(a), p(b)];
  return `#${x.map((v, i) => Math.round(v + (y[i] - v) * clamp(t)).toString(16).padStart(2, '0')).join('')}`;
};
export const rgba = (hex, a) => `rgba(${[1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16)).join(',')},${a})`;
// A seeded hash, so every render scatters the same way.
export const jitter = (i, k = 0) => { const x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return x - Math.floor(x); };
// How far a scene is into its handover: 0 until the camera sets off.
const leavingOf = (local, frame, over) => clamp((local - (frame.seconds - OUT)) / over);

// A scene's elements, by its composition id. HyperFrames mounts each scene
// in its host and re-scopes the scene's own root, so the root's id is not
// kept; ids inside it are.
export const sceneRoots = (id) => [...document.querySelectorAll(`[data-composition-id="s-${id}"]`)];

function surface(id) {
  const canvas = document.getElementById(id);
  if (!canvas) return null;
  const g = canvas.getContext('2d');
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.clearRect(0, 0, canvas.width, canvas.height);
  return { canvas, g, w: canvas.width, h: canvas.height };
}

// The atlas's 2D projection placed in a box (the Manim shot's map).
export function placer(box, bounds = V.map.bounds) {
  const [x0, x1, y0, y1] = bounds;
  const s = Math.min((box[2] - box[0]) / (x1 - x0), (box[3] - box[1]) / (y1 - y0));
  const ox = (box[0] + box[2]) / 2 - ((x0 + x1) / 2) * s;
  const oy = (box[1] + box[3]) / 2 + ((y0 + y1) / 2) * s;
  return ([x, y]) => [ox + x * s, oy - y * s];
}

// Words placed on a picture: made once beside the scene's picture (the
// element `anchorId`), then only their place and opacity change.
function labels(anchorId, key, make) {
  const root = document.getElementById(anchorId)?.parentElement;
  if (!root) return [];
  let layer = root.querySelector(`.labels-${key}`);
  if (!layer) {
    layer = document.createElement('div');
    layer.className = `labels labels-${key}`;
    for (const item of make()) {
      const el = document.createElement('span');
      el.className = `f-chip map-label${item.cls ? ` ${item.cls}` : ''}`;
      if (item.colour) {
        const dot = document.createElement('i');
        dot.style.background = item.colour;
        el.append(dot);
      }
      el.append(document.createTextNode(item.text));
      if (item.x !== undefined) { el.style.left = `${Math.round(item.x)}px`; el.style.top = `${Math.round(item.y)}px`; }
      layer.append(el);
    }
    root.append(layer);
  }
  return [...layer.children];
}

export function roundRect(g, x, y, w, h, r) {
  const q = Math.max(0, Math.min(r, w / 2, h / 2));
  g.beginPath();
  g.moveTo(x + q, y);
  g.arcTo(x + w, y, x + w, y + h, q);
  g.arcTo(x + w, y + h, x, y + h, q);
  g.arcTo(x, y + h, x, y, q);
  g.arcTo(x, y, x + w, y, q);
  g.closePath();
}

// ---- the matrix: PBMC240's own cells and proteins (scenes 3 and 6) ----
// One column per cell of the file, one row per protein.

let stripes = null;
export function hatch(g) {
  if (!stripes) {
    const tile = document.createElement('canvas');
    tile.width = 8;
    tile.height = 8;
    const t = tile.getContext('2d');
    t.strokeStyle = 'rgba(120, 140, 160, 0.55)';
    t.lineWidth = 1.4;
    t.beginPath();
    t.moveTo(0, 8); t.lineTo(8, 0);
    t.moveTo(-1, 1); t.lineTo(1, -1);
    t.moveTo(7, 9); t.lineTo(9, 7);
    t.stroke();
    stripes = g.createPattern(tile, 'repeat');
  }
  return stripes;
}

export const COLS = 44;
export const ROW_H = 23;
export const LABEL_W = 96;
export const level = (v, extra = 0) => rgba(ACCENT, clamp(0.16 + 0.7 * clamp(((v ?? 8) - 8) / 14) + extra));
// Where each matrix sits in its scene's layout (the card's place plus its
// 1px rim and its padding, compositions/s03 and s06), for the morphs.
export const MATRIX = {
  gaps: { left: 785, top: 429, width: 960 },
  'built-for-gaps': { left: 905, top: 359, width: 860 },
};
export const tileWidth = (id) => (MATRIX[id].width - LABEL_W - 8) / COLS;
// When scene 3's first column shows: once the protein cell of scene 2 has
// opened into it (lib/bridges.js), as the camera arrives.
export const FIRST_COLUMN = 0.19;

// Scene 3: the matrix fills column by column from the cell that opened into
// it; each tile lights up as it is read, bright where a protein was
// measured, grey where it was not; then the missing ones fall away. As the
// camera leaves, the measured tiles lift off as dots (lib/bridges.js).
function gapsMatrix(local, p, frame) {
  const s = surface('gaps-canvas');
  if (!s) return;
  const { g } = s;
  const hm = V.heatmap;
  const rows = hm.genes.length;
  const tw = tileWidth('gaps');
  const leaving = leavingOf(local, frame, 0.9);
  g.font = "500 13px 'Poppins', sans-serif";
  g.textBaseline = 'middle';
  g.textAlign = 'right';
  g.fillStyle = `rgba(29,43,54,${0.75 * (1 - leaving)})`;
  for (let r = 0; r < rows; r++) g.fillText(hm.genes[r], LABEL_W - 10, r * ROW_H + ROW_H / 2 + 2);
  for (let c = 0; c < COLS; c++) {
    const when = c === 0 ? FIRST_COLUMN : FIRST_COLUMN + 0.02 + (c / COLS) * 0.3;
    const shown = c === 0 ? phase(p, FIRST_COLUMN - 0.02, FIRST_COLUMN) : (p >= when ? 1 : 0);
    if (shown <= 0) continue;
    for (let r = 0; r < rows; r++) {
      const x = LABEL_W + c * tw;
      const y = r * ROW_H;
      const v = hm.log2[c][r];
      const lit = c === 0 ? 0 : clamp(1 - (p - when - r * 0.002) / 0.07);   // the flash as a tile is read
      if (v === null) {
        const fall = phase(p, 0.5 + jitter(c, r) * 0.18, 0.64 + jitter(c, r) * 0.18);
        g.globalAlpha = shown * (1 - fall * 0.75) * (1 - leaving);
        g.fillStyle = lit > 0 ? `rgba(150,160,170,${0.25 + 0.5 * lit})` : hatch(g);
        roundRect(g, x + 1, y + 1 + fall * 18, tw - 2, ROW_H - 2, 3);
        g.fill();
        if (fall > 0) {
          g.globalAlpha = fall * 0.7 * (1 - leaving);
          g.strokeStyle = 'rgba(70, 90, 110, 0.45)';
          g.setLineDash([3, 3]);
          roundRect(g, x + 1.5, y + 1.5, tw - 3, ROW_H - 3, 3);
          g.stroke();
          g.setLineDash([]);
        }
      } else {
        // A measured tile stays until its dot lifts off (lib/bridges.js).
        g.globalAlpha = shown * (1 - clamp((leaving - gapsLift(c, r)) / 0.12));
        if (lit > 0) {
          g.fillStyle = rgba('#3FA9E0', 0.35 * lit);
          roundRect(g, x - 2, y - 2, tw + 4, ROW_H + 4, 5);
          g.fill();
        }
        g.fillStyle = level(v, 0.3 * lit);
        roundRect(g, x + 1, y + 1, tw - 2, ROW_H - 2, 3);
        g.fill();
      }
    }
  }
  g.globalAlpha = 1;
}
// When, in the handover's 0..1, the measured tile (c, r) lifts off.
export const gapsLift = (c, r) => 0.05 + 0.5 * jitter(c, r + 40);

// Scene 6: the same matrix. A mask marks each gap; then a bright band
// sweeps down the rows, and each protein is scaled within the file as it
// passes; then a second band sweeps across, and each cell borrows from
// similar cells. As it hands over, its rows stream out to the encoders
// (lib/bridges.js).
export const SWEEP = { scale: [0.3, 0.56], smooth: [0.6, 0.8] };
export const rowLift = (r, rows) => 0.04 + 0.4 * (r / rows);
function maskMatrix(local, p, frame) {
  const s = surface('mask-canvas');
  if (!s) return;
  const { g, w } = s;
  const hm = V.heatmap;
  const rows = hm.genes.length;
  const tw = tileWidth('built-for-gaps');
  const height = rows * ROW_H;
  const leaving = leavingOf(local, frame, 1.2);
  const scaleAt = lerp(-0.1, 1.1, phase(p, ...SWEEP.scale)) * height;     // the scaling band's height
  const smoothAt = lerp(-0.1, 1.1, phase(p, ...SWEEP.smooth)) * (w - LABEL_W) + LABEL_W;
  g.font = "500 13px 'Poppins', sans-serif";
  g.textBaseline = 'middle';
  g.textAlign = 'right';
  for (let r = 0; r < rows; r++) {
    const y = r * ROW_H;
    const swept = clamp((scaleAt - y) / (ROW_H * 2));
    const gone = clamp((leaving - rowLift(r, rows)) / 0.1);
    g.globalAlpha = 1 - gone;
    g.fillStyle = `rgba(29,43,54,${0.55 + 0.3 * swept})`;
    g.fillText(hm.genes[r], LABEL_W - 10, y + ROW_H / 2 + 2);
    for (let c = 0; c < COLS; c++) {
      const x = LABEL_W + c * tw;
      const v = hm.log2[c][r];
      g.globalAlpha = 1 - gone;
      if (v === null) {
        const masked = phase(p, 0.06 + (c / COLS) * 0.12, 0.14 + (c / COLS) * 0.12);
        g.fillStyle = 'rgba(255,255,255,0.4)';
        roundRect(g, x + 1, y + 1, tw - 2, ROW_H - 2, 3);
        g.fill();
        g.globalAlpha = masked * (1 - gone);
        g.strokeStyle = 'rgba(29,43,54,0.45)';
        g.lineWidth = 1.2;
        roundRect(g, x + 2, y + 2, tw - 4, ROW_H - 4, 3);
        g.stroke();
        g.fillStyle = 'rgba(29,43,54,0.6)';
        g.beginPath();
        g.arc(x + tw / 2, y + ROW_H / 2, 1.8, 0, TAU);
        g.fill();
        continue;
      }
      const scaled = clamp((scaleAt - y) / ROW_H);
      const smoothed = clamp((smoothAt - x) / (tw * 3));
      const z = lerp(hm.z[c][r], hm.smoothed[c][r], smoothed);
      g.fillStyle = level(v);
      roundRect(g, x + 1, y + 1, tw - 2, ROW_H - 2, 3);
      g.fill();
      if (scaled > 0) {
        g.globalAlpha = scaled * (1 - gone);
        g.fillStyle = diverging(z) ?? level(v);
        roundRect(g, x + 1, y + 1, tw - 2, ROW_H - 2, 3);
        g.fill();
      }
    }
  }
  g.globalAlpha = 1;
  // The sweeps themselves: soft bright bands while they pass.
  const band = (x0, y0, x1, y1, a) => {
    const grad = g.createLinearGradient(x0, y0, x1, y1);
    grad.addColorStop(0, 'rgba(63,169,224,0)');
    grad.addColorStop(0.5, `rgba(63,169,224,${a})`);
    grad.addColorStop(1, 'rgba(63,169,224,0)');
    g.fillStyle = grad;
  };
  const scaling = phase(p, SWEEP.scale[0], SWEEP.scale[0] + 0.03) * (1 - phase(p, SWEEP.scale[1] - 0.03, SWEEP.scale[1]));
  if (scaling > 0) {
    band(0, scaleAt - 26, 0, scaleAt + 26, 0.55 * scaling);
    g.fillRect(LABEL_W, scaleAt - 26, w - LABEL_W, 52);
  }
  const smoothing = phase(p, SWEEP.smooth[0], SWEEP.smooth[0] + 0.03) * (1 - phase(p, SWEEP.smooth[1] - 0.03, SWEEP.smooth[1]));
  if (smoothing > 0) {
    band(smoothAt - 30, 0, smoothAt + 30, 0, 0.5 * smoothing);
    g.fillRect(smoothAt - 30, 0, 60, height);
  }
}

// ---- the atlas in 3D (scenes 4 and 11) ----

const maps = new Map();
function map3d(id, capacity) {
  const canvas = document.getElementById(id);
  if (!canvas) return null;
  if (!maps.has(id) || maps.get(id).canvas !== canvas) maps.set(id, { canvas, map: createMap3D(canvas, capacity) });
  return maps.get(id).map;
}
const BIG = V.classes.map((c, k) => k).filter((k) => V.atlas3.points.filter((q) => q[3] === k).length >= 100);

// Scene 4's map: the canvas inside its card (compositions/s04-rna.html,
// inside the card's 1px rim), in the scene's layout.
export const RNA_CANVAS = { left: 821, top: 111, width: 980, height: 920 };

// Scene 4: a shoal of the reference's own cells streams in as RNA (orange),
// settles into the atlas, and takes each type's colour as it is named, while
// the camera flies in through the cloud and draws back to see it whole.
export function rnaView(p) {
  const e = smooth(p);
  return { angle: lerp(-1.6, -0.2, e), height: lerp(0.15, 0.6, e), distance: lerp(1.25, 2.6, smooth((p - 0.1) / 0.9)), fov: lerp(52, 38, e) };
}
// Where the atlas gathers from: a small cloud just ahead of the camera as it
// arrives, where scene 3's dots land (lib/bridges.js).
export const GATHERED = 0.19;
const GATHER = (() => {
  const view = rnaView(GATHERED);
  const eye = eyeOf(view);
  const n = Math.hypot(...eye);
  return eye.map((v) => v - (v / n) * 1.0);
})();
// One of the reference's cells at progress p of scene 4: it appears in the
// gathered cloud, streams out to its place in the atlas, and takes its
// type's colour as the types are named.
export function rnaPoint(i, p) {
  const [x, y, z, k] = V.atlas3.points[i];
  const delay = (i / V.atlas3.points.length) * 0.2;
  const arrive = phase(p, 0.2 + delay, 0.5 + delay);
  const a = jitter(i, 1) * TAU;
  const b = Math.acos(2 * jitter(i, 2) - 1);
  const r = 0.26 * Math.cbrt(jitter(i, 7));
  const from = [GATHER[0] + r * Math.sin(b) * Math.cos(a), GATHER[1] + r * Math.cos(b), GATHER[2] + r * Math.sin(b) * Math.sin(a)];
  const named = phase(p, 0.56 + jitter(i, 4) * 0.08, 0.7 + jitter(i, 4) * 0.08);
  return {
    xyz: [lerp(from[0], x, arrive), lerp(from[1], y, arrive), lerp(from[2], z, arrive)],
    colour: mixHex(RNA, V.classes[k].colour, named),
    alpha: 0.95 * phase(p, GATHERED - 0.025 + delay * 0.05, GATHERED + 0.01 + delay * 0.05),
  };
}
// The size of scene 4's dots on its canvas (map3d.js draws aSize x half the
// canvas height over the depth, across): the radius, in pixels.
export const RNA_SIZE = 0.045;
export const rnaRadius = (depth) => (0.5 * RNA_SIZE * (RNA_CANVAS.height / 2)) / Math.max(0.15, depth);
// Where that cell is on scene 4's canvas: [x, y, depth].
export const rnaOnCanvas = (i, p) => projectPoint(rnaView(Math.min(p, 1)), rnaPoint(i, p).xyz, RNA_CANVAS.width, RNA_CANVAS.height);
// The cells that leave scene 4 for scene 5 (lib/bridges.js): every few,
// across the types.
export const rnaCarried = (count) => Array.from({ length: count }, (_, j) => Math.floor((j * V.atlas3.points.length) / count));
export const rnaLift = (i) => 0.05 + 0.45 * jitter(i, 11);
const CARRIED = new Set(rnaCarried(320));

function rnaMap(local, p, frame) {
  const map = map3d('rna-canvas', V.atlas3.points.length);
  if (!map) return;
  const view = rnaView(Math.min(p, 1));
  const leaving = leavingOf(local, frame, 1.2);
  const list = V.atlas3.points.map((_, i) => {
    const pt = rnaPoint(i, p);
    // A carried cell leaves as its dot lifts off (lib/bridges.js); the rest
    // thin out as the camera draws away.
    const out = CARRIED.has(i) ? clamp((leaving - rnaLift(i)) / 0.08) : leaving * (0.5 + 0.5 * jitter(i, 9));
    return { xyz: pt.xyz, colour: pt.colour, size: RNA_SIZE, alpha: pt.alpha * (1 - out) };
  });
  map.draw(view, list);
  const tags = labels('rna-canvas', 'rna', () => BIG.map((k) => ({ text: short(V.classes[k].name), colour: V.classes[k].colour })));
  tags.forEach((el, j) => {
    const k = BIG[j];
    const [x, y, depth] = map.project(view, V.atlas3.centres[k]);
    el.style.left = `${Math.round(Math.min(x + 12, RNA_CANVAS.width - el.offsetWidth - 16))}px`;
    el.style.top = `${Math.round(y - 18)}px`;
    el.style.opacity = String(depth > 0.3 ? phase(p, 0.66 + j * 0.012, 0.74 + j * 0.012) * (1 - clamp(leaving * 2)) : 0);
  });
}

// Scene 11: the PBMC240 example file's cells fly out of the file and land on
// the reference in 3D, each in the Atlas page's look for its answer, with a
// trail in flight and a ring as it lands; cells that cannot be placed stay
// beside the file as broken rings.
const ATLAS_CANVAS = { width: 1060, height: 720 };
const FILE_ON_CANVAS = [190, 46];   // the file's chip, top left of the window
function atlasMap(local, p) {
  const ref = V.atlas3.points;
  const cells = V.cells;
  const map = map3d('atlas-canvas', ref.length + cells.length * 5);
  if (!map) return;
  const view = { angle: lerp(-0.6, -0.3, smooth(p)), height: 0.6, distance: lerp(2.5, 2.3, smooth(p)), fov: 40 };
  const list = ref.map(([x, y, z, k]) => ({ xyz: [x, y, z], colour: V.classes[k].colour, size: 0.036, alpha: 0.5 * phase(p, 0, 0.12) }));
  // Where the file is: just under its chip, a little in front of the map.
  const file = unprojectPoint(view, FILE_ON_CANVAS[0], FILE_ON_CANVAS[1] + 40, 1.5, ATLAS_CANVAS.width, ATLAS_CANVAS.height);
  cells.forEach((cell, i) => {
    const start = 0.2 + (i / cells.length) * 0.4;
    const arrive = phase(p, start, start + 0.02);
    if (arrive <= 0) return;
    const fly = phase(p, start, start + 0.12);
    const k = cell.level === 'class' ? V.classes.findIndex((c) => c.name === cell.label) : cell.guess;
    const colour = V.classes[k]?.colour ?? '#8A99A8';
    const placed = V.atlas3.cells[i] && cell.outcome !== 'outside_supported_region' && cell.outcome !== 'coverage_too_low';
    const cloud = file.map((v, c) => v + (jitter(i, c + 3) - 0.5) * 0.18);
    if (!placed) {
      list.push({ xyz: cloud, colour: '#8A99A8', size: 0.075, alpha: arrive * 0.9, look: 5 });
      return;
    }
    const to = V.atlas3.cells[i];
    const at = (f) => cloud.map((v, c) => lerp(v, to[c], f) + (c === 1 ? Math.sin(f * Math.PI) * 0.35 : 0));
    if (fly < 1) {
      for (let tr = 3; tr >= 1; tr--) list.push({ xyz: at(Math.max(0, fly - tr * 0.06)), colour: PROT, size: 0.03, alpha: 0.25 * (4 - tr) / 3 });
      list.push({ xyz: at(fly), colour: PROT, size: 0.05, alpha: 0.95 });
      return;
    }
    const look = cell.level === 'class' ? 1 : cell.level === 'group' ? 2 : cell.level === 'lineage' ? 3 : 4;
    list.push({ xyz: to, colour, size: 0.078, alpha: phase(p, start + 0.12, start + 0.15), look });
    const ring = clamp((p - start - 0.12) / 0.06);
    if (ring > 0 && ring < 1) list.push({ xyz: to, colour, size: 0.08 + ring * 0.16, alpha: (1 - ring) * 0.8, look: 4 });
  });
  map.draw(view, list);
}

// ---- the link of scene 5: RNA on one side, protein on the other ----
// Dots run along the link once it is drawn (compositions/s05-vivome.html,
// where the link runs from 440 to 956 px across the bridge, 52 px down, and
// this canvas lies over it from 420 px across and 30 px down), orange on the
// RNA side and green on the protein side.
export const LINK = { from: 20, to: 536, y: 24.5, drawn: [7.6, 8.7] };
function vivomeLink(local) {
  const s = surface('link-canvas');
  if (!s) return;
  const { g } = s;
  const reach = smooth((local - LINK.drawn[0]) / (LINK.drawn[1] - LINK.drawn[0]));
  if (reach <= 0) return;
  for (let j = 0; j < 16; j++) {
    const u = (jitter(j, 5) + (local - LINK.drawn[0]) * 0.42) % 1;
    if (u > reach) continue;
    const x = lerp(LINK.from, LINK.to, u);
    const colour = u < 0.5 ? mixHex(RNA, ACCENT, u * 2) : mixHex(ACCENT, PROT, u * 2 - 1);
    g.globalAlpha = 0.9 * smooth(u / 0.06) * smooth((1 - u) / 0.06);
    g.fillStyle = '#FFFFFF';
    g.beginPath();
    g.arc(x, LINK.y, 8, 0, TAU);
    g.fill();
    g.fillStyle = colour;
    g.beginPath();
    g.arc(x, LINK.y, 5.5, 0, TAU);
    g.fill();
  }
  g.globalAlpha = 1;
}

// ---- the second opinion (scene 8) ----
// Two currents, the encoder's and the correlation's, are drawn on to the
// agreement gate with particles flowing along them. A meter fills to its
// mark; the gate opens; the two run on as one into the best guess.

const CURVES = {
  encoder: [[170, 700], [520, 700], [760, 700], [1010, 760], [1260, 820], [1260, 800], [1420, 800]],
  correlation: [[170, 920], [520, 920], [760, 900], [1010, 840], [1260, 780], [1260, 800], [1420, 800]],
};
// When each current is drawn (seconds into the scene, and for how long),
// when the meter fills and the gate opens: the score's two lines start
// with the currents (audio/score.py).
export const SECOND = { encoder: [2.0, 2.6], correlation: [2.5, 2.6], meter: [4.0, 4.6], open: [4.6, 5.0], guess: 5.0, gateX: 1203 };
export const streamStart = (name) => CURVES[name][0];
export function bezier(pts, u) {
  const seg = u < 0.5 ? 0 : 1;
  const t = u < 0.5 ? u * 2 : (u - 0.5) * 2;
  const [a, b, c, d] = seg === 0 ? pts.slice(0, 4) : pts.slice(3, 7);
  const m = 1 - t;
  return [0, 1].map((k) => m * m * m * a[k] + 3 * m * m * t * b[k] + 3 * m * t * t * c[k] + t * t * t * d[k]);
}
// Where along a current the gate stands.
const gateU = (name) => {
  let lo = 0.5;
  let hi = 1;
  for (let k = 0; k < 40; k++) { const mid = (lo + hi) / 2; if (bezier(CURVES[name], mid)[0] < SECOND.gateX) lo = mid; else hi = mid; }
  return lo;
};
const GATE_U = { encoder: gateU('encoder'), correlation: gateU('correlation') };
const inOut = (x) => { const t = clamp(x); return t < 0.5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2; };

function stroke(g, pts, a, b, colour, width) {
  if (b <= a) return;
  g.strokeStyle = colour;
  g.lineWidth = width;
  g.lineCap = 'round';
  g.beginPath();
  const n = Math.max(2, Math.ceil((b - a) * 90));
  for (let k = 0; k <= n; k++) {
    const [x, y] = bezier(pts, a + ((b - a) * k) / n);
    if (k === 0) g.moveTo(x, y); else g.lineTo(x, y);
  }
  g.stroke();
}

// Scene 8's canvas lies inside its diagram card, past the card's 1px rim:
// the currents are drawn in the scene's own pixels, moved by that much.
const DIAGRAM = { left: 111, top: 471 };
function secondOpinion(local) {
  const s = surface('so-canvas');
  if (!s) return;
  const { g } = s;
  g.setTransform(1, 0, 0, 1, -DIAGRAM.left, -DIAGRAM.top);
  const open = smooth((local - SECOND.open[0]) / (SECOND.open[1] - SECOND.open[0]));
  const beyond = inOut((local - SECOND.open[0]) / 0.9);
  for (const name of ['encoder', 'correlation']) {
    const [start, length] = SECOND[name];
    const drawn = inOut((local - start) / length);
    const gu = GATE_U[name];
    const reach = Math.min(drawn, gu);
    g.globalAlpha = 0.92;
    stroke(g, CURVES[name], 0, reach, STREAMS[name], 12);
    // Particles flow along what is drawn; they gather at the gate while it
    // is shut, and run on through it once it opens.
    const head = reach + (1 - gu) * beyond;
    for (let j = 0; j < 18; j++) {
      const u = ((jitter(j, name.length) + (local - start) * 0.22) % 1) * head;
      if (u <= 0.002 || local < start) continue;
      const [x, y] = bezier(CURVES[name], u);
      g.globalAlpha = 0.95 * smooth((head - u) / 0.03 + 0.2);
      g.fillStyle = '#FFFFFF';
      g.beginPath();
      g.arc(x, y, 3.6, 0, TAU);
      g.fill();
    }
  }
  // The single current beyond the gate, into the best guess.
  g.globalAlpha = 0.95;
  const gu = GATE_U.encoder;
  stroke(g, CURVES.encoder, gu, gu + (1 - gu) * beyond, ACCENT, 14);
  // The gate: two halves that slide apart, and the agreement meter beside it.
  g.globalAlpha = smooth((local - 2.9) / 0.5);
  g.fillStyle = '#1D2B36';
  const gap = 78 * open;
  roundRect(g, SECOND.gateX - 7, 700 - gap, 14, 96, 7);
  g.fill();
  roundRect(g, SECOND.gateX - 7, 794 + gap, 14, 96, 7);
  g.fill();
  const fill = smooth((local - SECOND.meter[0]) / (SECOND.meter[1] - SECOND.meter[0]));
  g.fillStyle = 'rgba(29,43,54,0.14)';
  roundRect(g, SECOND.gateX + 28, 700, 10, 190, 5);
  g.fill();
  g.fillStyle = ACCENT;
  const h = 190 * 0.66 * fill;
  roundRect(g, SECOND.gateX + 28, 890 - h, 10, h, 5);
  g.fill();
  g.fillStyle = '#1D2B36';
  g.fillRect(SECOND.gateX + 22, 890 - 190 * 0.6, 22, 2);
  g.globalAlpha = 1;
}

// ---- Manim's frames (scene 7) ----

// Where each answer sits beside its cell, so the four never overlap.
const CHIP_AT = [[-330, 18], [22, -64], [30, 4], [26, 24]];

function answers(local) {
  const img = document.getElementById('answers-img');
  if (!img) return null;
  const shot = V.answersShot;
  const place = placer(shot.box, shot.bounds);
  const chips = labels('answers-img', 'answers', () => V.answers.map((a, k) => {
    const [x, y] = place(a.xy);
    const [dx, dy] = CHIP_AT[k] ?? [24, 18];
    return { text: a.answer, x: x + dx, y: y + dy, cls: `answer-${a.level}` };
  }));
  const active = shot.starts.reduce((n, s, k) => (local >= s ? k : n), -1);
  chips.forEach((el, k) => {
    // Each answer shows once its set has narrowed (manim/answers.py).
    const on = clamp((local - shot.starts[k] - shot.settle[k]) / 0.4);
    el.style.opacity = String(k < active ? 0.6 : k === active ? on : 0);
  });
  const n = clamp(Math.round(local * shot.fps), 0, Math.round(shot.seconds * shot.fps) - 1);
  const src = `build/manim/answers/${String(n).padStart(4, '0')}.png`;
  if (img.getAttribute('src') === src) return null;
  img.setAttribute('src', src);
  return img.decode().catch(() => {});
}

export const DRAW = {
  gaps: gapsMatrix,
  rna: rnaMap,
  vivome: vivomeLink,
  'built-for-gaps': maskMatrix,
  answers,
  'second-opinion': secondOpinion,
  atlas: atlasMap,
};
