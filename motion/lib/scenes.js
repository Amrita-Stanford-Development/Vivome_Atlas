// The scenes' pictures, drawn on each seek by lib/dive.js while a scene's
// card is on screen: a pure function of the time into the card, keyed to
// the moments its voice line says each phrase (cueOf; web/js/reel-frames.js,
// `said`), so the pictures act out what is being said. Every value drawn
// comes from the repository's data (window.VIVOME, written by
// scripts/prepare.mjs from web/data/workflow.json and manuscript.json);
// nothing here computes a model output.
//
// Each card closes with a picture at its edge, in its last moments before
// it fades, and the next card opens on the same picture in the same spot
// (lib/plan.js, RHYMES): the eye carries it across the camera's journey.
// Nothing crosses the journey itself.
//
// DRAW[sceneId](seconds into the card, frame) draws into the scene's
// canvases, or swaps its Manim frame, and may return a promise the frame
// must wait for.

import { diverging } from '../vendor/site/workflow-layout.js';
import { short } from '../vendor/site/scene-kit.js';
import { createMap3D, projectPoint, unprojectPoint } from './map3d.js';
import { RHYMES } from './plan.js';

const V = window.VIVOME;
const TAU = Math.PI * 2;
export const ACCENT = '#0066A3';
export const RNA = '#C8641E';   // reserved: RNA, and nothing else
export const PROT = '#2F8F6A';  // reserved: protein, and nothing else
export const STREAMS = { encoder: '#0073AD', correlation: '#9A6A12' };
const INK = '#1D2B36';

export const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
export const smooth = (x) => { const t = clamp(x); return t * t * (3 - 2 * t); };
const phase = (t, a, b) => smooth((t - a) / (b - a));
export const lerp = (a, b, t) => a + (b - a) * t;
const mix2 = (p, q, t) => [lerp(p[0], q[0], t), lerp(p[1], q[1], t)];
export const mixHex = (a, b, t) => {
  const p = (h) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16));
  const [x, y] = [p(a), p(b)];
  return `#${x.map((v, i) => Math.round(v + (y[i] - v) * clamp(t)).toString(16).padStart(2, '0')).join('')}`;
};
export const rgba = (hex, a) => `rgba(${[1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16)).join(',')},${a})`;
// A seeded hash, so every render scatters the same way.
export const jitter = (i, k = 0) => { const x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return x - Math.floor(x); };

// ---- the cards' timing ----

const frameOf = (id) => V.frames.find((f) => f.id === id);
// When phrase k of the scene's line is said, in seconds into its card.
export const cueOf = (id, k) => frameOf(id).cues[k];
// When the scene's closing picture starts.
const exitOf = (id) => frameOf(id).exit;
// Where the closing picture of `from` ends and the opening of the next begins.
const rhyme = (from) => RHYMES.find((r) => r.from === from);
const opening = (to) => RHYMES.find((r) => r.to === to);

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
// A canvas whose origin is `at` in the frame: draw in frame pixels.
function framed(id, at) {
  const s = surface(id);
  if (s) s.g.setTransform(1, 0, 0, 1, -at[0], -at[1]);
  return s;
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
// element `anchorId`), inside the same card, then only their place and
// opacity change.
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
const dot = (g, x, y, r) => { g.beginPath(); g.arc(x, y, Math.max(0.1, r), 0, TAU); g.fill(); };

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

// A protein cell, as the film draws it: a translucent green body with a
// bright rim and a soft glow.
function proteinCell(g, x, y, r, alpha = 1) {
  if (alpha <= 0 || r <= 0) return;
  g.save();
  g.globalAlpha = alpha;
  const glow = g.createRadialGradient(x, y, r * 0.7, x, y, r * 1.8);
  glow.addColorStop(0, rgba(PROT, 0.3));
  glow.addColorStop(1, rgba(PROT, 0));
  g.fillStyle = glow;
  g.fillRect(x - r * 2, y - r * 2, r * 4, r * 4);
  const body = g.createRadialGradient(x - r * 0.32, y - r * 0.36, 0, x - r * 0.32, y - r * 0.36, r * 1.9);
  body.addColorStop(0, 'rgba(255,255,255,0.95)');
  body.addColorStop(0.46, rgba(PROT, 0.32));
  body.addColorStop(1, rgba(PROT, 0.78));
  g.fillStyle = body;
  dot(g, x, y, r);
  g.lineWidth = Math.max(1.5, r * 0.06);
  g.strokeStyle = rgba(PROT, 0.9);
  g.stroke();
  g.restore();
}

// ---- the matrix: PBMC240's own cells and proteins ----
// One column per cell of the file, one row per protein.

export const COLS = 44;
export const ROW_H = 23;
export const LABEL_W = 96;
export const level = (v, extra = 0) => rgba(ACCENT, clamp(0.16 + 0.7 * clamp(((v ?? 8) - 8) / 14) + extra));
// Where each matrix sits in its scene's layout (the card's place plus its
// 1px rim and its padding, compositions/s03 and s06).
export const MATRIX = {
  gaps: { left: 785, top: 429, width: 960 },
  'built-for-gaps': { left: 905, top: 359, width: 860 },
};
export const tileWidth = (id) => (MATRIX[id].width - LABEL_W - 8) / COLS;
const HM = V.heatmap;
const ROWS = HM.genes.length;
// A tile: bright where the protein was measured, striped where it was not.
function tile(g, x, y, w, h, v, alpha = 1, r = 3) {
  if (alpha <= 0) return;
  g.globalAlpha = alpha;
  g.fillStyle = v === null ? hatch(g) : level(v);
  roundRect(g, x, y, w, h, r);
  g.fill();
  g.globalAlpha = 1;
}

// ---- scene 1: one cell, its proteins as bars ----

const READOUT = { at: [1201, 211], cell: [120, 330], r: 60 };
function surfaceScene(c) {
  const s = surface('readout-canvas');
  if (!s) return;
  const { g } = s;
  const ex = exitOf('surface');
  const fold = phase(c, ex, ex + 0.6);
  const [cx, cy] = READOUT.cell;
  // Two more cells wait behind it, as the voice says "one cell at a time".
  const queue = phase(c, cueOf('surface', 1), cueOf('surface', 1) + 0.6) * (1 - phase(c, ex, ex + 0.4));
  proteinCell(g, cx - 52, cy - 110, 40, 0.35 * queue);
  proteinCell(g, cx - 56, cy + 118, 38, 0.35 * queue);
  // Its proteins, read out as bars: long where much was measured, a
  // striped stub where nothing was.
  g.font = "500 13px 'Poppins', sans-serif";
  g.textBaseline = 'middle';
  g.textAlign = 'right';
  for (let r = 0; r < ROWS; r++) {
    const y = 70 + r * 22;
    const grow = phase(c, 1.9 + r * 0.05, 2.3 + r * 0.05) * (1 - fold);
    if (grow <= 0) continue;
    const v = HM.log2[0][r];
    g.globalAlpha = grow * 0.18;
    g.strokeStyle = PROT;
    g.lineWidth = 1;
    g.beginPath();
    g.moveTo(cx + READOUT.r, cy);
    g.lineTo(304, y + 7);
    g.stroke();
    g.globalAlpha = grow;
    g.fillStyle = 'rgba(29,43,54,0.72)';
    g.fillText(HM.genes[r], 296, y + 8);
    const length = v === null ? 56 : 260 * (0.15 + 0.85 * clamp((v - 8) / 14));
    tile(g, 304, y, length * grow, 14, v, grow);
  }
  g.globalAlpha = 1;
  // At the close, the bars fold back into the cell, which settles where
  // scene 2 opens.
  const move = phase(c, ex + 0.4, ex + 1.2);
  const to = [rhyme('surface').close[0] - READOUT.at[0], rhyme('surface').close[1] - READOUT.at[1]];
  const [x, y] = mix2([cx, cy], to, move);
  proteinCell(g, x, y, lerp(READOUT.r, POOL.cells[0][2], move));
}

// ---- scene 2: cells without names, each with its own set ----

const POOL = {
  at: [1241, 91],
  // [x, y, radius] in the pool card; the first is where scene 1 left its cell.
  cells: [[259, 239, 46], [110, 110, 38], [440, 130, 34], [120, 470, 42], [420, 520, 36]],
};
function miniColumn(g, k, x, y, w, h, pitch, reveal, alpha = 1) {
  for (let r = 0; r < ROWS; r++) {
    const on = clamp((reveal - r / ROWS) * 4);
    if (on <= 0) continue;
    const v = HM.log2[k][r];
    if (v === null) {
      g.globalAlpha = alpha * on * 0.7;
      g.strokeStyle = 'rgba(70, 90, 110, 0.45)';
      g.lineWidth = 1;
      roundRect(g, x + 0.5, y + r * pitch + 0.5, w - 1, h - 1, 2);
      g.stroke();
      g.globalAlpha = 1;
    } else {
      tile(g, x, y + r * pitch, w, h, v, alpha * on, 2);
    }
  }
}
function unnamedScene(c) {
  const s = surface('pool-canvas');
  if (!s) return;
  const { g } = s;
  const ex = exitOf('unnamed');
  const leave = 1 - phase(c, ex, ex + 0.5);
  const grow = phase(c, ex, ex + 1.0);
  const cue2 = cueOf('unnamed', 2);
  POOL.cells.forEach(([x, y, r], k) => {
    const here = k === 0 ? 1 : phase(c, 0.5 + k * 0.2, 0.9 + k * 0.2);
    // "and every lab detects a different set of proteins": each cell's own
    // column of what was measured in it.
    const reveal = clamp((c - cue2 - k * 0.15) / 0.6);
    if (k === 0) {
      proteinCell(g, x, y, r, here * (1 - grow));
      // At the close the first cell's column grows to full height, where
      // scene 3's matrix begins.
      const w = lerp(8, tileWidth('gaps') - 2, grow);
      const h = lerp(6, ROW_H - 2, grow);
      const pitch = lerp(7, ROW_H, grow);
      const [px, py] = [rhyme('unnamed').close[0] - POOL.at[0], rhyme('unnamed').close[1] - POOL.at[1]];
      const left = lerp(x + r + 12, px - w / 2, grow);
      const top = lerp(y - (ROWS * 7) / 2, py - (ROWS * pitch) / 2, grow);
      miniColumn(g, 0, left, top, w, h, pitch, reveal);
    } else {
      proteinCell(g, x, y, r, here * leave);
      miniColumn(g, k, x + r + 12, y - (ROWS * 7) / 2, 8, 6, 7, reveal, leave);
    }
  });
}

// ---- scene 3: mostly missing ----

const gapsLift = (c, r) => 0.4 * jitter(c, r + 40);
function gapsScene(c) {
  const s = surface('gaps-canvas');
  const o = surface('gaps-over');
  if (!s || !o) return;
  const { g } = s;
  const m = MATRIX.gaps;
  const tw = tileWidth('gaps');
  const ex = exitOf('gaps');
  const cue1 = cueOf('gaps', 1);
  // It opens on scene 2's column, which takes its place as the first.
  const settle = phase(c, 0.3, 1.0);
  if (c < 1.0) {
    const [px, py] = opening('gaps').open;
    const x = lerp(px - (tw - 2) / 2, m.left + LABEL_W + 1, settle);
    const y = lerp(py - (ROWS * ROW_H) / 2, m.top, settle);
    for (let r = 0; r < ROWS; r++) tile(o.g, x, y + r * ROW_H + 1, tw - 2, ROW_H - 2, HM.log2[0][r]);
  }
  g.font = "500 13px 'Poppins', sans-serif";
  g.textBaseline = 'middle';
  g.textAlign = 'right';
  g.fillStyle = `rgba(29,43,54,${0.75 * (1 - phase(c, ex, ex + 0.5))})`;
  for (let r = 0; r < ROWS; r++) g.fillText(HM.genes[r], LABEL_W - 10, r * ROW_H + ROW_H / 2 + 2);
  // The matrix fills column by column; each tile lights as it is read.
  for (let col = 0; col < COLS; col++) {
    const when = col === 0 ? 1.0 : 1.0 + (col / COLS) * 1.3;
    if (c < when) continue;
    for (let r = 0; r < ROWS; r++) {
      const x = LABEL_W + col * tw;
      const y = r * ROW_H;
      const v = HM.log2[col][r];
      const lit = col === 0 ? 0 : clamp(1 - (c - when - r * 0.01) / 0.45);
      if (v === null) {
        // "Much of a protein matrix is empty": the missing ones dim and
        // fall away.
        const fall = phase(c, cue1 + jitter(col, r) * 0.9, cue1 + 0.5 + jitter(col, r) * 0.9);
        g.globalAlpha = (1 - fall * 0.8) * (1 - phase(c, ex, ex + 0.5));
        g.fillStyle = lit > 0 ? `rgba(150,160,170,${0.25 + 0.5 * lit})` : hatch(g);
        roundRect(g, x + 1, y + 1 + fall * 18, tw - 2, ROW_H - 2, 3);
        g.fill();
        if (fall > 0) {
          g.globalAlpha = fall * 0.7 * (1 - phase(c, ex, ex + 0.5));
          g.strokeStyle = 'rgba(70, 90, 110, 0.45)';
          g.setLineDash([3, 3]);
          roundRect(g, x + 1.5, y + 1.5, tw - 3, ROW_H - 3, 3);
          g.stroke();
          g.setLineDash([]);
        }
        g.globalAlpha = 1;
        continue;
      }
      // At the close each measured tile lifts off as a dot.
      const gone = clamp((c - ex - gapsLift(col, r)) / 0.12);
      if (lit > 0) {
        g.globalAlpha = 1 - gone;
        g.fillStyle = rgba('#3FA9E0', 0.35 * lit);
        roundRect(g, x - 2, y - 2, tw + 4, ROW_H + 4, 5);
        g.fill();
      }
      tile(g, x + 1, y + 1, tw - 2, ROW_H - 2, v, 1 - gone);
      if (gone <= 0) continue;
      // The dots gather at the matrix's right edge, turning from the
      // protein measurement's blue to RNA's orange: scene 4's atlas
      // gathers from them there.
      const q = clamp((c - ex - gapsLift(col, r)) / 0.8);
      const e = smooth(q);
      const from = [m.left + x + tw / 2, m.top + y + ROW_H / 2];
      const [px, py] = rhyme('gaps').close;
      const k = col * ROWS + r;
      const to = [px + (jitter(k, 3) - 0.5) * 120, py + (jitter(k, 4) - 0.5) * 120];
      const [dx, dy] = mix2(from, to, e);
      o.g.globalAlpha = 0.95;
      o.g.fillStyle = mixHex(ACCENT, RNA, e);
      dot(o.g, dx, dy - Math.sin(Math.PI * e) * 40, lerp(6, 4, e));
    }
  }
  g.globalAlpha = 1;
  o.g.globalAlpha = 1;
}

// ---- scene 4: RNA has names, in 3D ----

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
export const RNA_SIZE = 0.045;
const MAP_DISTANCE = 2.4;
const MAP_FOV = 38;
// A slow turn, at a fixed distance and field of view, at rest once the
// types are named, so their names never move.
const RNA_REST = () => cueOf('rna', 2) + 0.8;
const rnaView = (c) => ({ angle: -0.75 + 0.6 * smooth(c / RNA_REST()), height: 0.5, distance: MAP_DISTANCE, fov: MAP_FOV });
// Where the atlas gathers from: the dots of scene 3, a small cloud at the
// spot it closed on, a little in front of the map.
const GATHER = (() => {
  const [px, py] = opening('rna').open;
  return unprojectPoint(rnaView(0), px - RNA_CANVAS.left, py - RNA_CANVAS.top, 1.6, RNA_CANVAS.width, RNA_CANVAS.height);
})();
const N3 = V.atlas3.points.length;
// One of the reference's cells, c seconds into scene 4's card.
function rnaPoint(i, c) {
  const [x, y, z, k] = V.atlas3.points[i];
  const delay = (i / N3) * 0.6;
  const arrive = phase(c, 0.3 + delay, 2.4 + delay);
  const a = jitter(i, 1) * TAU;
  const b = Math.acos(2 * jitter(i, 2) - 1);
  const r = 0.16 * Math.cbrt(jitter(i, 7));
  const from = [GATHER[0] + r * Math.sin(b) * Math.cos(a), GATHER[1] + r * Math.cos(b), GATHER[2] + r * Math.sin(b) * Math.sin(a)];
  // "Its atlases are large": the rest of the cells come in.
  const shown = i < N3 * 0.35 ? 1 : phase(c, cueOf('rna', 1) + (i / N3) * 0.4, cueOf('rna', 1) + 0.4 + (i / N3) * 0.4);
  // "and every cell in them has a name": each takes its type's colour.
  const named = phase(c, cueOf('rna', 2) + jitter(i, 4) * 0.4, cueOf('rna', 2) + 0.4 + jitter(i, 4) * 0.4);
  return {
    xyz: [lerp(from[0], x, arrive), lerp(from[1], y, arrive), lerp(from[2], z, arrive)],
    colour: mixHex(RNA, V.classes[k].colour, named),
    alpha: 0.95 * shown,
  };
}
const CARRIED = Array.from({ length: 320 }, (_, j) => Math.floor((j * N3) / 320));
const CARRIED_SET = new Set(CARRIED);
const bandAt = (r, j, n) => [r.close[0] - r.spread + (2 * r.spread * j) / (n - 1), r.close[1] + (jitter(j, 21) - 0.5) * 18];
function rnaScene(c) {
  const map = map3d('rna-canvas', N3);
  const o = surface('rna-over');
  if (!map || !o) return;
  const view = rnaView(c);
  const ex = exitOf('rna');
  const out = phase(c, ex, ex + 0.3);
  map.draw(view, V.atlas3.points.map((_, i) => {
    const pt = rnaPoint(i, c);
    return { xyz: pt.xyz, colour: pt.colour, size: RNA_SIZE, alpha: pt.alpha * (CARRIED_SET.has(i) ? 1 - out : 1) };
  }));
  // The big types are named at the rest pose, and stay put.
  const rest = rnaView(RNA_REST());
  const tags = labels('rna-canvas', 'rna', () => BIG.map((k) => ({ text: short(V.classes[k].name), colour: V.classes[k].colour })));
  tags.forEach((el, j) => {
    const k = BIG[j];
    const [x, y, depth] = map.project(rest, V.atlas3.centres[k]);
    el.style.left = `${Math.round(Math.min(x + 12, RNA_CANVAS.width - el.offsetWidth - 16))}px`;
    el.style.top = `${Math.round(y - 18)}px`;
    el.style.opacity = String(depth > 0.3 ? phase(c, RNA_REST() + j * 0.1, RNA_REST() + 0.3 + j * 0.1) : 0);
  });
  // At the close, a band of the atlas's cells gathers along the map's top
  // edge: scene 5's wordmark forms from them.
  if (c < ex) return;
  const r = rhyme('rna');
  CARRIED.forEach((i, j) => {
    const q = clamp((c - ex - jitter(j, 22) * 0.3) / 0.8);
    const [x, y] = map.project(view, rnaPoint(i, c).xyz);
    const from = [RNA_CANVAS.left + x, RNA_CANVAS.top + y];
    const [bx, by] = mix2(from, bandAt(r, j, CARRIED.length), smooth(q));
    o.g.fillStyle = V.classes[V.atlas3.points[i][3]].colour;
    o.g.globalAlpha = 0.95;
    dot(o.g, bx, by, 3.6);
  });
  o.g.globalAlpha = 1;
}

// ---- scene 5: VivOME ----

// The wordmark's "OME", in scene 5's layout (compositions/s05-vivome.html).
const WORDMARK = { x: [960, 1290], y: [112, 238] };
// An element's place in its scene, in the scene's pixels.
function offsetIn(el) {
  let x = 0;
  let y = 0;
  for (let n = el; n && !n.classList?.contains('scene'); n = n.offsetParent) { x += n.offsetLeft; y += n.offsetTop; }
  return [x, y];
}
export const LINK = { from: 20, to: 536, y: 24.5 };
function vivomeScene(c) {
  const o = surface('vivome-over');
  const s = surface('link-canvas');
  if (!o || !s) return;
  // It opens on scene 4's band, which flows into the wordmark as it forms.
  const r = opening('vivome');
  if (c < 1.2) {
    CARRIED.forEach((i, j) => {
      const q = smooth(clamp((c - jitter(j, 23) * 0.25) / 0.7));
      const to = [lerp(WORDMARK.x[0], WORDMARK.x[1], jitter(j, 24)), lerp(WORDMARK.y[0], WORDMARK.y[1], jitter(j, 25))];
      const [x, y] = mix2(bandAt(r, j, CARRIED.length), to, q);
      o.g.globalAlpha = 0.95 * (1 - phase(c, 0.6 + jitter(j, 26) * 0.3, 1.1 + jitter(j, 26) * 0.1));
      o.g.fillStyle = mixHex(V.classes[V.atlas3.points[i][3]].colour, INK, q);
      dot(o.g, x, y, 3.6);
    });
  }
  // The link: once drawn, dots run along it from the RNA side to the
  // protein side.
  const { g } = s;
  const reach = phase(c, 5.0, 6.0);
  const ex = exitOf('vivome');
  for (let j = 0; j < 16 && reach > 0; j++) {
    const u = (jitter(j, 5) + (c - 5.0) * 0.42) % 1;
    if (u > reach) continue;
    const x = lerp(LINK.from, LINK.to, u);
    g.globalAlpha = 0.9 * smooth(u / 0.06) * smooth((1 - u) / 0.06) * (1 - phase(c, ex, ex + 0.3));
    g.fillStyle = '#FFFFFF';
    dot(g, x, LINK.y, 8);
    g.fillStyle = u < 0.5 ? mixHex(RNA, ACCENT, u * 2) : mixHex(ACCENT, PROT, u * 2 - 1);
    dot(g, x, LINK.y, 5.5);
  }
  g.globalAlpha = 1;
  // At the close, dots leave the link and pile into a row of tiles at the
  // card's foot, where scene 6's matrix fills from.
  if (c < ex) return;
  const link = document.getElementById('link-canvas');
  const [lx, ly] = offsetIn(link);
  const row = rhyme('vivome').close;
  const tw = tileWidth('built-for-gaps');
  for (let col = 0; col < COLS; col++) {
    const q = smooth(clamp((c - ex - jitter(col, 27) * 0.35) / 0.8));
    const from = [lx + lerp(LINK.from, LINK.to, col / (COLS - 1)), ly + LINK.y];
    const to = [row[0] + (col - (COLS - 1) / 2) * tw, row[1]];
    const [x, y] = mix2(from, to, q);
    const w = lerp(10, tw - 2, q);
    const h = lerp(10, ROW_H - 2, q);
    tile(o.g, x - w / 2, y - h / 2, w, h, HM.log2[col][0], 0.95, lerp(5, 3, q));
  }
}

// ---- scene 6: built for gaps ----

export const SWEEP = { scale: [0, 1.15], smooth: [1.35, 1.95] };
const ENCODERS = (() => {
  const m = V.facts['ms:wf_members'];
  return m?.measured ? Math.max(1, Number(m.value) || 1) : 1;
})();
function maskScene(c) {
  const s = surface('mask-canvas');
  const o = surface('built-for-gaps-over');
  if (!s || !o) return;
  const { g, w } = s;
  const id = 'built-for-gaps';
  const m = MATRIX[id];
  const tw = tileWidth(id);
  const height = ROWS * ROW_H;
  const cue1 = cueOf(id, 1);
  const cue2 = cueOf(id, 2);
  const cue3 = cueOf(id, 3);
  const ex = exitOf(id);
  // It opens on scene 5's row of tiles, which rises to the top; then the
  // rows fill down.
  const rise = phase(c, 0.3, 0.8);
  if (c < 0.85) {
    const row = opening(id).open;
    for (let col = 0; col < COLS; col++) {
      const from = [row[0] + (col - (COLS - 1) / 2) * tw, row[1]];
      const to = [m.left + LABEL_W + col * tw + tw / 2, m.top + ROW_H / 2];
      const [x, y] = mix2(from, to, rise);
      tile(o.g, x - (tw - 2) / 2, y - (ROW_H - 2) / 2, tw - 2, ROW_H - 2, HM.log2[col][0]);
    }
  }
  // The steps, each with its point: the mask marks each gap ("it knows
  // which proteins were never measured"), a band sweeps down as each
  // protein is scaled ("scales each one within your file"), a band sweeps
  // across as each cell borrows from similar cells.
  const scaleAt = lerp(-0.1, 1.1, phase(c, cue2 + SWEEP.scale[0], cue2 + SWEEP.scale[1])) * height;
  const smoothAt = lerp(-0.1, 1.1, phase(c, cue2 + SWEEP.smooth[0], cue2 + SWEEP.smooth[1])) * (w - LABEL_W) + LABEL_W;
  // "and asks the encoders to answer together": the matrix steps back.
  const back = 1 - 0.75 * phase(c, cue3, cue3 + 0.4);
  g.font = "500 13px 'Poppins', sans-serif";
  g.textBaseline = 'middle';
  g.textAlign = 'right';
  for (let r = 0; r < ROWS; r++) {
    const y = r * ROW_H;
    const here = r === 0 ? (c >= 0.85 ? 1 : 0) : phase(c, 0.8 + r * 0.045, 1.0 + r * 0.045);
    if (here <= 0) continue;
    const swept = clamp((scaleAt - y) / (ROW_H * 2));
    g.globalAlpha = here * back;
    g.fillStyle = `rgba(29,43,54,${0.55 + 0.3 * swept})`;
    g.fillText(HM.genes[r], LABEL_W - 10, y + ROW_H / 2 + 2);
    for (let col = 0; col < COLS; col++) {
      const x = LABEL_W + col * tw;
      const v = HM.log2[col][r];
      if (v === null) {
        const masked = phase(c, cue1 + (col / COLS) * 0.4, cue1 + 0.25 + (col / COLS) * 0.4);
        g.globalAlpha = here * back;
        g.fillStyle = 'rgba(255,255,255,0.4)';
        roundRect(g, x + 1, y + 1, tw - 2, ROW_H - 2, 3);
        g.fill();
        g.globalAlpha = masked * here * back;
        g.strokeStyle = 'rgba(29,43,54,0.45)';
        g.lineWidth = 1.2;
        roundRect(g, x + 2, y + 2, tw - 4, ROW_H - 4, 3);
        g.stroke();
        g.fillStyle = 'rgba(29,43,54,0.6)';
        dot(g, x + tw / 2, y + ROW_H / 2, 1.8);
        continue;
      }
      const scaled = clamp((scaleAt - y) / ROW_H);
      const smoothed = clamp((smoothAt - x) / (tw * 3));
      const z = lerp(HM.z[col][r], HM.smoothed[col][r], smoothed);
      tile(g, x + 1, y + 1, tw - 2, ROW_H - 2, v, here * back);
      if (scaled > 0) {
        g.globalAlpha = scaled * here * back;
        g.fillStyle = diverging(z) ?? level(v);
        roundRect(g, x + 1, y + 1, tw - 2, ROW_H - 2, 3);
        g.fill();
      }
    }
  }
  g.globalAlpha = 1;
  const band = (x0, y0, x1, y1, a) => {
    const grad = g.createLinearGradient(x0, y0, x1, y1);
    grad.addColorStop(0, 'rgba(63,169,224,0)');
    grad.addColorStop(0.5, `rgba(63,169,224,${a})`);
    grad.addColorStop(1, 'rgba(63,169,224,0)');
    g.fillStyle = grad;
  };
  const scaling = phase(c, cue2, cue2 + 0.1) * (1 - phase(c, cue2 + SWEEP.scale[1] - 0.1, cue2 + SWEEP.scale[1]));
  if (scaling > 0) {
    band(0, scaleAt - 26, 0, scaleAt + 26, 0.55 * scaling);
    g.fillRect(LABEL_W, scaleAt - 26, w - LABEL_W, 52);
  }
  const smoothing = phase(c, cue2 + SWEEP.smooth[0], cue2 + SWEEP.smooth[0] + 0.1) * (1 - phase(c, cue2 + SWEEP.smooth[1] - 0.1, cue2 + SWEEP.smooth[1]));
  if (smoothing > 0) {
    band(smoothAt - 30, 0, smoothAt + 30, 0, 0.5 * smoothing);
    g.fillRect(smoothAt - 30, 0, 60, height);
  }
  // The encoders, one for each of the served model's members, inside the
  // card: the rows stream into them, and their answers merge into one.
  if (c < cue3) return;
  const merge = [w - 90, height / 2];
  const ring = (k) => [180 + (k - (ENCODERS - 1) / 2) * (ENCODERS > 1 ? Math.min(110, 420 / (ENCODERS - 1)) : 0) + 200, height / 2];
  const shown = phase(c, cue3, cue3 + 0.4);
  for (let r = 0; r < ROWS; r++) {
    const q = clamp((c - cue3 - 0.3 - r * 0.04) / 0.7);
    if (q <= 0 || q >= 1) continue;
    const e = smooth(q);
    const [rx, ry] = ring(r % ENCODERS);
    const from = [LABEL_W + (COLS * tw) / 2, r * ROW_H + ROW_H / 2];
    const [x, y] = mix2(from, [rx, ry], e);
    const bw = lerp(COLS * tw, 10, e);
    const bh = lerp(ROW_H - 2, 10, e);
    g.globalAlpha = 0.85 * (1 - smooth((q - 0.8) / 0.2));
    g.fillStyle = rgba(ACCENT, 0.7);
    roundRect(g, x - bw / 2, y - bh / 2, bw, bh, bh / 2);
    g.fill();
  }
  for (let k = 0; k < ENCODERS; k++) {
    const [x, y] = ring(k);
    const busy = phase(c, cue3 + 0.6, cue3 + 1.4);
    g.globalAlpha = shown;
    const halo = g.createRadialGradient(x, y, 0, x, y, 64);
    halo.addColorStop(0, rgba('#3FA9E0', 0.45 * busy));
    halo.addColorStop(1, 'rgba(63,169,224,0)');
    g.fillStyle = halo;
    g.fillRect(x - 64, y - 64, 128, 128);
    g.fillStyle = '#FFFFFF';
    dot(g, x, y, 28);
    g.lineWidth = 5;
    g.strokeStyle = ACCENT;
    g.stroke();
    g.fillStyle = rgba(ACCENT, 0.3 + 0.6 * busy);
    dot(g, x, y, 11);
    // Each encoder's answers flow on to one point, where they merge.
    for (let j = 0; j < 6; j++) {
      const u = ((c - cue3 - 1.2) * 0.6 + jitter(j, k + 30)) % 1;
      if (c < cue3 + 1.2 || u < 0) continue;
      const [px, py] = mix2([x + 30, y], merge, u);
      g.fillStyle = ACCENT;
      g.globalAlpha = shown * 0.9 * (1 - phase(c, ex, ex + 0.2));
      dot(g, px, py + Math.sin(u * Math.PI) * (k - (ENCODERS - 1) / 2) * 18, 4);
    }
  }
  g.globalAlpha = shown * (1 - phase(c, ex, ex + 0.2));
  g.fillStyle = ACCENT;
  dot(g, merge[0], merge[1], 9 * phase(c, cue3 + 1.4, cue3 + 2.0));
  g.globalAlpha = 1;
  // At the close the merged points gather at the matrix's left edge, where
  // scene 7's map grows from.
  if (c < ex) return;
  const to = rhyme(id).close;
  for (let j = 0; j < 60; j++) {
    const q = smooth(clamp((c - ex - jitter(j, 31) * 0.3) / 0.85));
    const from = [m.left + merge[0], m.top + merge[1]];
    const end = [to[0] + (jitter(j, 32) - 0.5) * 40, to[1] + (jitter(j, 33) - 0.5) * 40];
    const [x, y] = mix2(from, end, q);
    o.g.globalAlpha = 0.9;
    o.g.fillStyle = mixHex(ACCENT, V.classes[j % V.classes.length].colour, q);
    dot(o.g, x, y + Math.sin(q * Math.PI) * (jitter(j, 34) - 0.5) * 160, 4);
  }
  o.g.globalAlpha = 1;
}

// ---- scene 7: honest answers (Manim's frames) ----

// Where each answer sits beside its cell, so the four never overlap.
const CHIP_AT = [[-330, 18], [22, -64], [30, 4], [26, 24]];
function answersScene(c) {
  const img = document.getElementById('answers-img');
  const o = surface('answers-over');
  if (!img || !o) return null;
  const shot = V.answersShot;
  const place = placer(shot.box, shot.bounds);
  const chips = labels('answers-img', 'answers', () => V.answers.map((a, k) => {
    const [x, y] = place(a.xy);
    const [dx, dy] = CHIP_AT[k] ?? [24, 18];
    return { text: a.answer, x: x + dx, y: y + dy, cls: `answer-${a.level}` };
  }));
  // Each answer shows as its rung is said, when its cell's set has settled.
  chips.forEach((el, k) => { el.style.opacity = String(clamp((c - shot.settle[k]) / 0.3)); });
  // At the close the last cell's best guess splits into two strokes that
  // run to the map's edge, where scene 8's two currents start.
  const ex = exitOf('answers');
  if (c >= ex) {
    const from = place(V.answers[3].xy);
    const r = rhyme('answers');
    ['encoder', 'correlation'].forEach((name, k) => {
      const end = [r.close[0], r.close[1] + (k ? r.spread : -r.spread)];
      const at = (s) => {
        const e = smooth(clamp((s - ex) / 1.0));
        return [lerp(from[0], end[0], e), lerp(from[1], end[1], e) + Math.sin(Math.PI * e) * (k ? 60 : -60)];
      };
      o.g.strokeStyle = STREAMS[name];
      o.g.lineCap = 'round';
      for (let j = 1; j < 12; j++) {
        const [a, b] = [at(c - (j - 1) * 0.03), at(c - j * 0.03)];
        o.g.globalAlpha = 1 - j / 12;
        o.g.lineWidth = 12 * (1 - (j / 12) * 0.6);
        o.g.beginPath();
        o.g.moveTo(a[0], a[1]);
        o.g.lineTo(b[0], b[1]);
        o.g.stroke();
      }
      o.g.globalAlpha = 1;
      o.g.fillStyle = STREAMS[name];
      dot(o.g, ...at(c), 6);
    });
  }
  const n = clamp(Math.round(c * shot.fps), 0, Math.round(shot.seconds * shot.fps) - 1);
  const src = `build/manim/answers/${String(n).padStart(4, '0')}.png`;
  if (img.getAttribute('src') === src) return null;
  img.setAttribute('src', src);
  return img.decode().catch(() => {});
}

// ---- scene 8: a second opinion ----

const CURVES = {
  encoder: [[170, 700], [520, 700], [760, 700], [1010, 760], [1260, 820], [1260, 800], [1420, 800]],
  correlation: [[170, 920], [520, 920], [760, 900], [1010, 840], [1260, 780], [1260, 800], [1420, 800]],
};
const GATE_X = 1203;
export function bezier(pts, u) {
  const seg = u < 0.5 ? 0 : 1;
  const t = u < 0.5 ? u * 2 : (u - 0.5) * 2;
  const [a, b, c, d] = seg === 0 ? pts.slice(0, 4) : pts.slice(3, 7);
  const m = 1 - t;
  return [0, 1].map((k) => m * m * m * a[k] + 3 * m * m * t * b[k] + 3 * m * t * t * c[k] + t * t * t * d[k]);
}
const gateU = (name) => {
  let lo = 0.5;
  let hi = 1;
  for (let k = 0; k < 40; k++) { const mid = (lo + hi) / 2; if (bezier(CURVES[name], mid)[0] < GATE_X) lo = mid; else hi = mid; }
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
// Where particle j of the block of a hundred sits (scene 8's close, scene 9's open).
const BLOCK = 24;
const blockAt = (j, centre) => [centre[0] + ((j % 10) - 4.5) * BLOCK, centre[1] + (Math.floor(j / 10) - 4.5) * BLOCK];
function secondOpinion(c) {
  const s = framed('so-canvas', [DIAGRAM.left, DIAGRAM.top]);
  const o = surface('second-opinion-over');
  if (!s || !o) return;
  const { g } = s;
  const SO = V.secondOpinion;
  const ex = exitOf('second-opinion');
  const leave = 1 - phase(c, ex, ex + 0.4);
  const open = phase(c, SO.open[0], SO.open[1]);
  const beyond = inOut((c - SO.open[0]) / 0.9);
  for (const name of ['encoder', 'correlation']) {
    const [start, length] = SO[name];
    const drawn = Math.max(0.012, inOut((c - start) / length));
    const gu = GATE_U[name];
    const reach = Math.min(drawn, gu);
    g.globalAlpha = 0.92 * leave;
    stroke(g, CURVES[name], 0, reach, STREAMS[name], 12);
    // Particles flow along what is drawn, gather at the gate while it is
    // shut, and run on through it once it opens.
    const head = reach + (1 - gu) * beyond;
    for (let j = 0; j < 18; j++) {
      const u = ((jitter(j, name.length) + (c - start) * 0.22) % 1) * head;
      if (u <= 0.002 || c < start) continue;
      const [x, y] = bezier(CURVES[name], u);
      g.globalAlpha = 0.95 * smooth((head - u) / 0.03 + 0.2) * leave;
      g.fillStyle = '#FFFFFF';
      dot(g, x, y, 3.6);
    }
  }
  g.globalAlpha = 0.95 * leave;
  const gu = GATE_U.encoder;
  stroke(g, CURVES.encoder, gu, gu + (1 - gu) * beyond, ACCENT, 14);
  // The gate, as the voice says the second opinion is used only when the
  // file agrees: two halves, a meter that fills to its mark, then the gate
  // opens.
  g.globalAlpha = phase(c, SO.gate, SO.gate + 0.4) * leave;
  g.fillStyle = INK;
  const gap = 78 * open;
  roundRect(g, GATE_X - 7, 700 - gap, 14, 96, 7);
  g.fill();
  roundRect(g, GATE_X - 7, 794 + gap, 14, 96, 7);
  g.fill();
  const fill = phase(c, SO.meter[0], SO.meter[1]);
  g.fillStyle = 'rgba(29,43,54,0.14)';
  roundRect(g, GATE_X + 28, 700, 10, 190, 5);
  g.fill();
  g.fillStyle = ACCENT;
  const h = 190 * 0.66 * fill;
  roundRect(g, GATE_X + 28, 890 - h, 10, h, 5);
  g.fill();
  g.fillStyle = INK;
  g.fillRect(GATE_X + 22, 890 - 190 * 0.6, 22, 2);
  g.globalAlpha = 1;
  // At the close, particles leave the currents and pack into a block of a
  // hundred, where scene 9's first result fills from.
  if (c < ex) return;
  const centre = rhyme('second-opinion').close;
  for (let j = 0; j < 100; j++) {
    const q = smooth(clamp((c - ex - jitter(j, 41) * 0.3) / 0.85));
    const name = j % 2 ? 'correlation' : 'encoder';
    const from = bezier(CURVES[name], 0.1 + 0.8 * jitter(j, 42));
    const [x, y] = mix2(from, blockAt(j, centre), q);
    o.g.globalAlpha = 0.95;
    o.g.fillStyle = mixHex(STREAMS[name], ACCENT, q);
    roundRect(o.g, x - lerp(4, 10, q), y - lerp(4, 10, q), lerp(8, 20, q), lerp(8, 20, q), lerp(4, 4, q));
    o.g.fill();
  }
  o.g.globalAlpha = 1;
}

// ---- scene 9: real data, drawn from the records ----

const value = (key) => {
  const f = V.facts[`ms:${key}`];
  return f?.measured && Number.isFinite(f.value) ? f.value : null;
};
const WAFFLE = { at: [611, 421], centre: [140, 140] };
// A record that is not measured is drawn as a hatched shape, saying Pending.
function pendingShape(g, x, y, w, h) {
  g.fillStyle = hatch(g);
  roundRect(g, x, y, w, h, 8);
  g.fill();
  g.fillStyle = 'rgba(29,43,54,0.6)';
  g.font = "italic 500 18px 'Poppins', sans-serif";
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText('Pending', x + w / 2, y + h / 2);
}
function realData(c) {
  const s = framed('waffle-canvas', WAFFLE.at);
  const b = surface('lineage-canvas');
  const o = surface('real-data-over');
  if (!s || !b || !o) return;
  const id = 'real-data';
  const ex = exitOf(id);
  const centre = opening(id).open;
  const answered = value('committed_fulcher');
  const right = value('correct_fulcher');
  // It opens on scene 8's block; the particles become a grid of a hundred
  // squares. "here is how often it answers": the grid fills to that share;
  // "and how often those answers are right": the right ones turn solid.
  const shape = phase(c, 0.3, 1.0);
  const n1 = answered === null ? 0 : Math.round(answered * 100);
  const n2 = right === null ? 0 : Math.round(right * n1);
  const away = c >= ex;
  for (let j = 0; j < 100; j++) {
    const [x, y] = blockAt(j, centre);
    const filled = j < n1 ? phase(c, cueOf(id, 1) + (j / 100) * 1.2, cueOf(id, 1) + 0.2 + (j / 100) * 1.2) : 0;
    const solid = j < n2 ? phase(c, cueOf(id, 2) + (j / 100) * 0.8, cueOf(id, 2) + 0.2 + (j / 100) * 0.8) : 0;
    const colour = mixHex(mixHex(STREAMS.encoder, '#FFFFFF', shape * 0.8), ACCENT, filled);
    const draw = (g, px, py, size, alpha) => {
      g.globalAlpha = alpha;
      g.fillStyle = solid > 0 ? mixHex(mixHex(ACCENT, '#FFFFFF', 0.55), ACCENT, solid) : filled > 0 ? mixHex('#FFFFFF', mixHex(ACCENT, '#FFFFFF', 0.55), filled) : colour;
      roundRect(g, px - size / 2, py - size / 2, size, size, 4);
      g.fill();
      if (filled < 1) {
        g.strokeStyle = rgba(ACCENT, 0.4 * shape);
        g.lineWidth = 1.5;
        g.stroke();
      }
    };
    if (!away) draw(s.g, x, y, 20, 1);
    else {
      // At the close the squares slide into one row, where scene 10's
      // methods line up.
      const r = rhyme(id);
      const q = smooth(clamp((c - ex - jitter(j, 51) * 0.3) / 0.85));
      const to = [r.close[0] - r.spread + (2 * r.spread * j) / 99, r.close[1]];
      const [px, py] = mix2([x, y], to, q);
      draw(o.g, px, py, lerp(20, 6, q), 1);
    }
  }
  if (answered === null) pendingShape(s.g, centre[0] - 120, centre[1] - 120, 240, 240);
  s.g.globalAlpha = 1;
  o.g.globalAlpha = 1;
  // Khoury 2026's two lineages, as bars beside their numbers.
  const bars = [['khoury_lymphoid', 70, 6.6], ['khoury_myeloid', 252, 7.5]];
  for (const [key, y, at] of bars) {
    const v = value(key);
    b.g.fillStyle = 'rgba(29,43,54,0.1)';
    roundRect(b.g, 10, y, 250, 22, 11);
    b.g.fill();
    if (v === null) { pendingShape(b.g, 10, y - 10, 250, 42); continue; }
    b.g.fillStyle = ACCENT;
    roundRect(b.g, 10, y, 250 * v * phase(c, at, at + 1.0), 22, 11);
    b.g.fill();
  }
}

// ---- scene 10: against established methods ----

const SQUARES = {
  runs: { canvas: 'runs-canvas', at: [621, 609], favour: 'bm_khoury_baseline_favour', of: 'bm_khoury_baseline_runs', per: 7, size: 26, pitch: 32 },
  pairs: { canvas: 'pairs-canvas', at: [1441, 609], favour: 'bm_fulcher_favour', of: 'bm_fulcher_pairings', per: 8, size: 22, pitch: 28 },
};
const squareAt = (q, j) => [q.at[0] + 4 + (j % q.per) * q.pitch + q.size / 2, q.at[1] + 4 + Math.floor(j / q.per) * q.pitch + q.size / 2];
function methodsScene(c) {
  const o = surface('methods-over');
  const weak = surface('weak-canvas');
  if (!o || !weak) return;
  const id = 'methods';
  const ex = exitOf(id);
  // It opens on scene 9's row of dots, which rises to the methods' row and
  // gives way to their names as each comes in.
  const r = opening(id);
  const first = document.querySelector('[data-composition-id="s-methods"] .method');
  const rowY = first ? offsetIn(first)[1] + first.offsetHeight / 2 : r.open[1];
  const up = phase(c, 0, 0.5);
  for (let j = 0; j < 100; j++) {
    const x = r.open[0] - r.spread + (2 * r.spread * j) / 99;
    o.g.globalAlpha = 1 - phase(c, 0.3 + (j / 100) * 1.2, 0.6 + (j / 100) * 1.2);
    o.g.fillStyle = ACCENT;
    roundRect(o.g, x - 3, lerp(r.open[1], rowY, up) - 3, 6, 6, 2);
    o.g.fill();
  }
  o.g.globalAlpha = 1;
  // "it is level with the best and ahead of the rest": one square per run,
  // filled where it favours VivOME.
  const starts = { runs: cueOf(id, 2) + 0.3, pairs: 4.9 };
  const all = [];
  for (const [name, q] of Object.entries(SQUARES)) {
    const s = surface(q.canvas);
    if (!s) continue;
    const favour = value(q.favour);
    const of = value(q.of);
    if (favour === null || of === null) { pendingShape(s.g, 4, 4, 220, 100); continue; }
    for (let j = 0; j < of; j++) {
      const [fx, fy] = squareAt(q, j);
      all.push([fx, fy, j < favour]);
      if (c >= ex) continue;
      const x = fx - q.at[0];
      const y = fy - q.at[1];
      const on = j < favour ? phase(c, starts[name] + j * 0.04, starts[name] + 0.2 + j * 0.04) : 0;
      s.g.fillStyle = mixHex('#FFFFFF', ACCENT, on);
      roundRect(s.g, x - q.size / 2, y - q.size / 2, q.size, q.size, 5);
      s.g.fill();
      s.g.strokeStyle = rgba(ACCENT, 0.45);
      s.g.lineWidth = 1.5;
      s.g.stroke();
    }
  }
  // "Where it is still weak": the weak types, as dashed rings in their colours.
  const types = ['cd8-positive, alpha-beta t cell', 'myeloid dendritic cell'].map((n) => V.classes.find((k) => k.name === n)).filter(Boolean);
  types.forEach((k, j) => {
    weak.g.globalAlpha = phase(c, cueOf(id, 3) + 0.3 + j * 0.2, cueOf(id, 3) + 0.7 + j * 0.2);
    weak.g.strokeStyle = k.colour;
    weak.g.lineWidth = 4;
    weak.g.setLineDash([6, 6]);
    weak.g.beginPath();
    weak.g.arc(40 + j * 90, 40, 26, 0, TAU);
    weak.g.stroke();
    weak.g.setLineDash([]);
  });
  weak.g.globalAlpha = 1;
  // At the close the squares gather into a file, where scene 11 opens on
  // its file.
  if (c < ex) return;
  const to = rhyme(id).close;
  all.forEach(([x, y, fav], j) => {
    const q = smooth(clamp((c - ex - jitter(j, 61) * 0.3) / 0.85));
    const end = [to[0] + ((j % 13) - 6) * 22, to[1] + (Math.floor(j / 13) - 2) * 8];
    const [px, py] = mix2([x, y], end, q);
    o.g.fillStyle = fav ? ACCENT : '#FFFFFF';
    o.g.strokeStyle = rgba(ACCENT, 0.45);
    roundRect(o.g, px - lerp(12, 5, q), py - lerp(12, 3, q), lerp(24, 10, q), lerp(24, 6, q), 3);
    o.g.fill();
    o.g.stroke();
  });
  const chip = phase(c, ex + 0.6, ex + 1.1);
  o.g.globalAlpha = chip;
  o.g.strokeStyle = 'rgba(29,43,54,0.35)';
  o.g.lineWidth = 2;
  roundRect(o.g, to[0] - 182, to[1] - 25, 364, 50, 25);
  o.g.stroke();
  o.g.globalAlpha = 1;
}

// ---- scene 11: label your own data ----

const ATLAS_CANVAS = { left: 701, top: 221, width: 1060, height: 720 };
const atlasView = (c) => ({ angle: -0.6 + 0.5 * smooth(c / 11.5), height: 0.6, distance: MAP_DISTANCE, fov: 40 });
function atlasScene(c) {
  const ref = V.atlas3.points;
  const cells = V.cells;
  const map = map3d('atlas-canvas', ref.length + cells.length * 5);
  const o = surface('atlas-over');
  if (!map || !o) return;
  const id = 'atlas';
  const view = atlasView(c);
  const fly = cueOf(id, 2);
  const looks = cueOf(id, 3);
  const ex = exitOf(id);
  const list = ref.map(([x, y, z, k]) => ({ xyz: [x, y, z], colour: V.classes[k].colour, size: 0.036, alpha: 0.5 * phase(c, 0, 1.0) }));
  // The file: under its chip, a little in front of the map. As the voice
  // says to send it, it is ringed.
  const [fx, fy] = opening(id).open;
  const file = unprojectPoint(view, fx - ATLAS_CANVAS.left, fy - ATLAS_CANVAS.top + 40, 1.4, ATLAS_CANVAS.width, ATLAS_CANVAS.height);
  const ring = phase(c, cueOf(id, 1), cueOf(id, 1) + 0.4) * (1 - phase(c, fly, fly + 0.4));
  if (ring > 0) {
    o.g.globalAlpha = ring;
    o.g.strokeStyle = PROT;
    o.g.lineWidth = 3;
    roundRect(o.g, fx - 192, fy - 32, 384, 64, 32);
    o.g.stroke();
    o.g.globalAlpha = 1;
  }
  const rising = [];
  cells.forEach((cell, i) => {
    // "and your cells land on the map": out of the file, each on its arc.
    const start = fly + (i / cells.length) * 0.9;
    const arrive = phase(c, start, start + 0.05);
    if (arrive <= 0) return;
    const q = phase(c, start, start + 0.6);
    const k = cell.level === 'class' ? V.classes.findIndex((x) => x.name === cell.label) : cell.guess;
    const colour = V.classes[k]?.colour ?? '#8A99A8';
    const placed = V.atlas3.cells[i] && cell.outcome !== 'outside_supported_region' && cell.outcome !== 'coverage_too_low';
    const cloud = file.map((v, d) => v + (jitter(i, d + 3) - 0.5) * 0.18);
    if (!placed) {
      list.push({ xyz: cloud, colour: '#8A99A8', size: 0.075, alpha: arrive * 0.9, look: 5 });
      return;
    }
    const to = V.atlas3.cells[i];
    const at = (f) => cloud.map((v, d) => lerp(v, to[d], f) + (d === 1 ? Math.sin(f * Math.PI) * 0.35 : 0));
    if (q < 1) {
      for (let tr = 3; tr >= 1; tr--) list.push({ xyz: at(Math.max(0, q - tr * 0.06)), colour: PROT, size: 0.03, alpha: 0.25 * (4 - tr) / 3 });
      list.push({ xyz: at(q), colour: PROT, size: 0.05, alpha: 0.95 });
      return;
    }
    // "each with its answer": the Atlas page's look for the answer, with a
    // ring as it shows.
    const when = looks + (i / cells.length) * 0.5;
    const shown = phase(c, when, when + 0.2);
    const look = cell.level === 'class' ? 1 : cell.level === 'group' ? 2 : cell.level === 'lineage' ? 3 : 4;
    list.push({ xyz: to, colour: shown > 0.5 ? colour : PROT, size: lerp(0.05, 0.078, shown), alpha: 0.95, look: shown > 0.5 ? look : 0 });
    const r = clamp((c - when) / 0.5);
    if (r > 0 && r < 1) list.push({ xyz: to, colour, size: 0.08 + r * 0.16, alpha: (1 - r) * 0.8, look: 4 });
    if (rising.length < 12 && i % 17 === 0) rising.push({ xyz: to, colour, i });
  });
  map.draw(view, list);
  // At the close a few landed cells rise to the window's top edge, where
  // scene 12's bubbles start.
  if (c < ex) return;
  const r = rhyme(id);
  rising.forEach(({ xyz, colour, i }, j) => {
    const [x, y] = projectPoint(view, xyz, ATLAS_CANVAS.width, ATLAS_CANVAS.height);
    const q = smooth(clamp((c - ex - jitter(i, 71) * 0.3) / 0.85));
    const end = [r.close[0] - r.spread + (2 * r.spread * j) / Math.max(1, rising.length - 1), r.close[1]];
    const [px, py] = mix2([ATLAS_CANVAS.left + x, ATLAS_CANVAS.top + y], end, q);
    o.g.fillStyle = colour;
    o.g.globalAlpha = 0.95;
    dot(o.g, px, py, lerp(6, 8, q));
  });
  o.g.globalAlpha = 1;
}

// ---- scene 12: into the light ----

const WORDMARK_12 = [960, 262];
function lightScene(c) {
  const o = surface('light-over');
  if (!o) return;
  // Scene 11's cells rise as bubbles and burst at the wordmark as it forms.
  const r = opening('light');
  for (let j = 0; j < 12; j++) {
    const start = [r.open[0] - r.spread + (2 * r.spread * j) / 11, r.open[1]];
    const end = [WORDMARK_12[0] + (jitter(j, 81) - 0.5) * 420, WORDMARK_12[1] + (jitter(j, 82) - 0.5) * 80];
    const q = smooth(clamp((c - jitter(j, 83) * 0.3) / 1.1));
    const burst = clamp((c - jitter(j, 83) * 0.3 - 1.1) / 0.35);
    const [x, y] = mix2(start, end, q);
    if (burst <= 0) {
      o.g.globalAlpha = 0.9;
      o.g.strokeStyle = 'rgba(255,255,255,0.95)';
      o.g.fillStyle = rgba(PROT, 0.25);
      o.g.lineWidth = 2;
      o.g.beginPath();
      o.g.arc(x, y + Math.sin(q * Math.PI) * -30, 9, 0, TAU);
      o.g.fill();
      o.g.stroke();
    } else if (burst < 1) {
      o.g.globalAlpha = 1 - burst;
      o.g.strokeStyle = rgba(PROT, 0.8);
      o.g.lineWidth = 2;
      o.g.beginPath();
      o.g.arc(x, y, 9 + burst * 26, 0, TAU);
      o.g.stroke();
    }
  }
  o.g.globalAlpha = 1;
}

export const DRAW = {
  surface: surfaceScene,
  unnamed: unnamedScene,
  gaps: gapsScene,
  rna: rnaScene,
  vivome: vivomeScene,
  'built-for-gaps': maskScene,
  answers: answersScene,
  'second-opinion': secondOpinion,
  'real-data': realData,
  methods: methodsScene,
  atlas: atlasScene,
  light: lightScene,
};
