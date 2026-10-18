// The scenes' data pictures, drawn on each seek by lib/dive.js: a pure
// function of the time into the scene, like the water. Every value drawn
// comes from web/data/workflow.json (window.VIVOME.map, .cells, .heatmap,
// .answers, written by scripts/prepare.mjs); nothing here computes a
// model output.
//
// DRAW[sceneId](seconds into the scene, progress 0..1) draws into the
// scene's canvas, or swaps its Manim frame, and may return a promise the
// frame must wait for.

import { diverging } from '../vendor/site/workflow-layout.js';
import { short } from '../vendor/site/scene-kit.js';

const V = window.VIVOME;
const TAU = Math.PI * 2;
const ACCENT = '#0066A3';
const RNA = '#C8641E';   // reserved: RNA, and nothing else
const PROT = '#2F8F6A';  // reserved: protein, and nothing else
const INK = '#1D2B36';
const FONT = "'Poppins', -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif";

const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
const smooth = (x) => { const t = clamp(x); return t * t * (3 - 2 * t); };
const phase = (p, a, b) => smooth((p - a) / (b - a));
const lerp = (a, b, t) => a + (b - a) * t;
const mixHex = (a, b, t) => {
  const p = (h) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16));
  const [x, y] = [p(a), p(b)];
  return `rgb(${x.map((v, i) => Math.round(v + (y[i] - v) * clamp(t))).join(',')})`;
};
const rgba = (hex, a) => `rgba(${[1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16)).join(',')},${a})`;

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
  return { g, w: canvas.width, h: canvas.height };
}

// The atlas's projection placed in a box, keeping its shape.
export function placer(box, bounds = V.map.bounds) {
  const [x0, x1, y0, y1] = bounds;
  const s = Math.min((box[2] - box[0]) / (x1 - x0), (box[3] - box[1]) / (y1 - y0));
  const ox = (box[0] + box[2]) / 2 - ((x0 + x1) / 2) * s;
  const oy = (box[1] + box[3]) / 2 + ((y0 + y1) / 2) * s;
  return ([x, y]) => [ox + x * s, oy - y * s];
}

// A seeded hash, so jitter is the same on every render.
const jitter = (i, k = 0) => {
  const x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453;
  return x - Math.floor(x);
};

// Words placed on a map: made once beside the scene's picture (the element
// `anchorId`), then only their opacity changes with the time.
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
      el.style.left = `${Math.round(item.x)}px`;
      el.style.top = `${Math.round(item.y)}px`;
      layer.append(el);
    }
    root.append(layer);
  }
  return [...layer.children];
}

// ---- the matrix: PBMC240's own cells and proteins (scenes 3 and 6) ----

let stripes = null;
function hatch(g) {
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

function roundRect(g, x, y, w, h, r) {
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
}

const COLS = 44;
const level = (v) => rgba(ACCENT, 0.16 + 0.7 * clamp(((v ?? 8) - 8) / 14));

function matrix(id, local, p, mode) {
  const s = surface(id);
  if (!s) return;
  const { g, w } = s;
  const hm = V.heatmap;
  const rows = hm.genes.length;
  const left = 96;
  const tw = (w - left - 8) / COLS;
  const th = 23;
  g.font = `500 13px ${FONT}`;
  g.textBaseline = 'middle';
  g.textAlign = 'right';
  for (let r = 0; r < rows; r++) {
    g.fillStyle = 'rgba(29,43,54,0.75)';
    g.fillText(hm.genes[r], left - 10, r * th + th / 2 + 2);
  }
  for (let c = 0; c < COLS; c++) {
    const appear = mode === 'gaps' ? phase(p, 0.03 + (c / COLS) * 0.32, 0.1 + (c / COLS) * 0.32) : 1;
    for (let r = 0; r < rows; r++) {
      const x = left + c * tw;
      const y = r * th;
      const v = hm.log2[c][r];
      const missing = v === null;
      if (mode === 'gaps') {
        if (missing) {
          // The gaps fall away: striped first, then open holes.
          const fall = phase(p, 0.48 + jitter(c, r) * 0.18, 0.62 + jitter(c, r) * 0.18);
          g.globalAlpha = appear * (1 - fall * 0.75);
          g.fillStyle = hatch(g);
          roundRect(g, x + 1, y + 1 + fall * 18, tw - 2, th - 2, 3);
          g.fill();
          g.globalAlpha = appear * fall * 0.7;
          g.strokeStyle = 'rgba(70, 90, 110, 0.45)';
          g.setLineDash([3, 3]);
          roundRect(g, x + 1.5, y + 1.5, tw - 3, th - 3, 3);
          g.stroke();
          g.setLineDash([]);
        } else {
          g.globalAlpha = appear;
          g.fillStyle = level(v);
          roundRect(g, x + 1, y + 1, tw - 2, th - 2, 3);
          g.fill();
        }
        continue;
      }
      // Scene 6: the mask marks each gap, then each protein is scaled
      // within the file, then smoothed over similar cells.
      const masked = phase(p, 0.08 + (c / COLS) * 0.12, 0.16 + (c / COLS) * 0.12);
      const scaled = phase(p, 0.34 + (r / rows) * 0.1, 0.44 + (r / rows) * 0.1);
      const smoothed = phase(p, 0.6, 0.78);
      g.globalAlpha = 1;
      if (missing) {
        g.fillStyle = 'rgba(255,255,255,0.35)';
        roundRect(g, x + 1, y + 1, tw - 2, th - 2, 3);
        g.fill();
        g.globalAlpha = masked;
        g.strokeStyle = 'rgba(29,43,54,0.45)';
        g.lineWidth = 1.2;
        roundRect(g, x + 2, y + 2, tw - 4, th - 4, 3);
        g.stroke();
        g.fillStyle = 'rgba(29,43,54,0.6)';
        g.beginPath();
        g.arc(x + tw / 2, y + th / 2, 1.8, 0, TAU);
        g.fill();
        continue;
      }
      const z = lerp(hm.z[c][r], hm.smoothed[c][r], smoothed);
      const raw = level(v);
      g.fillStyle = raw;
      roundRect(g, x + 1, y + 1, tw - 2, th - 2, 3);
      g.fill();
      if (scaled > 0) {
        g.globalAlpha = scaled;
        g.fillStyle = diverging(z) ?? raw;
        roundRect(g, x + 1, y + 1, tw - 2, th - 2, 3);
        g.fill();
      }
    }
  }
  g.globalAlpha = 1;
}

// ---- the reference map (scene 4) ----

function rnaMap(local, p) {
  const s = surface('rna-canvas');
  if (!s) return;
  const { g } = s;
  const place = placer([840, 150, 1760, 1000]);
  const pts = V.map.sample;
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const [x, y, k] = pts[i];
    const [tx, ty] = place([x, y]);
    const delay = (i / n) * 0.22;
    const travel = phase(p, 0.06 + delay, 0.42 + delay);
    // The shoal streams in from the top right along a curve, then settles.
    const sx = 2050 + jitter(i) * 200;
    const sy = -160 + jitter(i, 1) * 500;
    const cx = 1500 + jitter(i, 2) * 300;
    const cy = 560 + jitter(i, 3) * 300;
    const u = travel;
    const px = (1 - u) * (1 - u) * sx + 2 * (1 - u) * u * cx + u * u * tx;
    const py = (1 - u) * (1 - u) * sy + 2 * (1 - u) * u * cy + u * u * ty;
    const named = phase(p, 0.56 + jitter(i, 4) * 0.08, 0.7 + jitter(i, 4) * 0.08);
    g.globalAlpha = 0.3 + 0.62 * phase(p, 0.04 + delay, 0.14 + delay);
    g.fillStyle = mixHex(RNA, V.classes[k].colour, named);
    g.beginPath();
    g.arc(px, py, 4, 0, TAU);
    g.fill();
  }
  g.globalAlpha = 1;
  // The big types get their names as they settle.
  const big = V.classes.map((c, k) => k).filter((k) => V.map.sample.filter((q) => q[2] === k).length >= 60);
  const tags = labels('rna-canvas', 'rna', () => big.map((k) => {
    const [x, y] = place(V.map.centres[k]);
    return { text: short(V.classes[k].name), x: Math.min(x + 14, 1600), y: y - 18, colour: V.classes[k].colour };
  }));
  tags.forEach((el, j) => { el.style.opacity = String(phase(p, 0.66 + j * 0.008, 0.74 + j * 0.008)); });
}

// ---- the example file landing on the map (scene 11) ----

const ATLAS_BOX = [60, 110, 1000, 610];
const FILE_AT = [190, 50];

function glyph(g, x, y, cell, alpha) {
  const k = cell.level === 'class' ? V.classes.findIndex((c) => c.name === cell.label) : cell.guess;
  const colour = V.classes[k]?.colour ?? '#8A99A8';
  g.save();
  g.globalAlpha = alpha * 0.3;
  g.fillStyle = colour;
  g.beginPath();
  g.arc(x, y, 13, 0, TAU);
  g.fill();
  g.globalAlpha = alpha;
  g.lineWidth = 2;
  g.beginPath();
  g.arc(x, y, 7, 0, TAU);
  if (cell.level === 'class') { g.fillStyle = colour; g.fill(); g.strokeStyle = '#FFFFFF'; g.stroke(); }
  else if (cell.level === 'group') { g.fillStyle = mixHex(colour, '#FFFFFF', 0.35); g.fill(); g.strokeStyle = INK; g.stroke(); }
  else if (cell.level === 'lineage') { g.fillStyle = mixHex(colour, '#FFFFFF', 0.6); g.fill(); }
  else { g.strokeStyle = '#8A99A8'; g.stroke(); }
  g.restore();
}

function atlasMap(local, p) {
  const s = surface('atlas-canvas');
  if (!s) return;
  const { g } = s;
  const place = placer(ATLAS_BOX);
  g.globalAlpha = 0.5 * phase(p, 0, 0.12);
  for (const [x, y, k] of V.map.sample) {
    const [px, py] = place([x, y]);
    g.fillStyle = V.classes[k].colour;
    g.beginPath();
    g.arc(px, py, 2.4, 0, TAU);
    g.fill();
  }
  const cells = V.cells;
  cells.forEach((cell, i) => {
    const start = 0.2 + (i / cells.length) * 0.4;
    const fly = phase(p, start, start + 0.12);
    const arrive = phase(p, start, start + 0.02);
    if (arrive <= 0) return;
    const cloud = [FILE_AT[0] + (jitter(i) - 0.5) * 90, FILE_AT[1] + (jitter(i, 1) - 0.5) * 50];
    const placed = cell.xy && cell.outcome !== 'outside_supported_region' && cell.outcome !== 'coverage_too_low';
    if (!placed) {
      // A cell that cannot be placed stays in the file's cloud, a broken ring.
      g.save();
      g.globalAlpha = arrive * 0.85;
      g.strokeStyle = '#8A99A8';
      g.lineWidth = 2;
      g.setLineDash([3, 3]);
      g.beginPath();
      g.arc(cloud[0], cloud[1], 7, 0, TAU);
      g.stroke();
      g.restore();
      return;
    }
    const [tx, ty] = place(cell.xy);
    const x = lerp(cloud[0], tx, fly);
    const y = lerp(cloud[1], ty, fly) - Math.sin(fly * Math.PI) * 70;
    if (fly < 1) {
      g.save();
      g.globalAlpha = 0.85;
      g.fillStyle = PROT;
      g.beginPath();
      g.arc(x, y, 5, 0, TAU);
      g.fill();
      g.restore();
    } else {
      glyph(g, x, y, cell, phase(p, start + 0.12, start + 0.16));
    }
  });
}

// ---- Manim's frames (scene 7) ----

// Where each answer sits beside its cell, so the four never overlap.
const CHIP_AT = [[-330, 18], [22, -64], [30, 4], [26, 24]];

function answers(local) {
  const img = document.getElementById('answers-img');
  if (!img) return null;
  const shot = V.answersShot;
  // Each cell's answer beside it on the map, from when Manim lands it.
  const place = placer(shot.box, shot.bounds);
  const chips = labels('answers-img', 'answers', () => V.answers.map((a, k) => {
    const [x, y] = place(a.xy);
    const [dx, dy] = CHIP_AT[k] ?? [24, 18];
    return { text: a.answer, x: x + dx, y: y + dy, cls: `answer-${a.level}` };
  }));
  const active = shot.starts.reduce((n, s, k) => (local >= s ? k : n), -1);
  chips.forEach((el, k) => {
    const on = clamp((local - shot.starts[k] - 0.9) / 0.4);
    el.style.opacity = String(k < active ? 0.6 : k === active ? on : 0);
  });
  const n = clamp(Math.round(local * shot.fps), 0, Math.round(shot.seconds * shot.fps) - 1);
  const src = `build/manim/answers/${String(n).padStart(4, '0')}.png`;
  if (img.getAttribute('src') === src) return null;
  img.setAttribute('src', src);
  return img.decode().catch(() => {});
}

export const DRAW = {
  gaps: (local, p) => matrix('gaps-canvas', local, p, 'gaps'),
  rna: rnaMap,
  'built-for-gaps': (local, p) => matrix('mask-canvas', local, p, 'mask'),
  answers,
  atlas: atlasMap,
};
