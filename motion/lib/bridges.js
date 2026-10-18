// The morphs between scenes: the film's match cuts. While the camera
// travels from one scene's plane to the next (lib/camera.js), something of
// the outgoing scene leaves it and becomes something of the incoming one,
// drawn here on one canvas over the scenes (#bridges), in the world: each
// end is a place in a scene's layout, projected through the camera at that
// moment, so it moves with its scene and the camera's path carries it.
//
// - 2 to 3: an unnamed protein cell opens into its column of the matrix
//   (one column for each cell of the PBMC240 file).
// - 3 to 4: the measured tiles lift off as dots and gather in front of the
//   camera, where scene 4's atlas assembles from them.
// - 4 to 5: cells of the atlas stream into the VivOME wordmark.
// - 6 to 7: the matrix's rows stream into the encoders, which send points
//   on to the map of scene 7.
// - 7 to 8: the ladder folds into two currents that start scene 8's two
//   paths.
// Every value drawn comes from window.VIVOME (scripts/prepare.mjs): the
// matrix's own tiles, the reference's own cells, the number of encoders.

import { project, OUT, IN, smootherstep } from './camera.js';
import { PLAN } from './plan.js';
import {
  ACCENT, RNA, PROT, STREAMS, COLS, ROW_H, LABEL_W, MATRIX, RNA_CANVAS, clamp, lerp, mixHex, rgba, jitter,
  level, hatch, roundRect, tileWidth, gapsLift, rowLift, rnaOnCanvas, rnaPoint, rnaCarried, rnaLift, rnaRadius,
  placer, streamStart, SECOND,
} from './scenes.js';

const V = window.VIVOME;
const TAU = Math.PI * 2;
const INK = '#1D2B36';
const startOf = (id) => V.frames.find((f) => f.id === id).start;
const on = (id, pose, lx, ly) => project(pose, PLAN[id].at, lx, ly);
const span = (t, a, b) => clamp((t - a) / (b - a));

// ---- 2 to 3: the protein cell opens into its column ----

// The first cell of scene 2 (compositions/s02-unnamed.html): its body's
// centre and radius in the scene's layout. The scene hides it as the
// camera sets off and this takes its place.
export const HERO = { x: 1092, y: 302, r: 52 };
function cellToColumn(g, t, poseOf) {
  const E = startOf('gaps');
  const u = span(t, E - OUT, E + IN);
  if (u <= 0 || u >= 1) return;
  const pose = poseOf(t);
  const hm = V.heatmap;
  const rows = hm.genes.length;
  const tw = tileWidth('gaps');
  const m = MATRIX.gaps;
  const [sx, sy, ss] = on('unnamed', pose, HERO.x, HERO.y);
  const [dx, dy, ds] = on('gaps', pose, m.left + LABEL_W + tw / 2, m.top + (rows * ROW_H) / 2);
  const e = smootherstep(u);
  const x = lerp(sx, dx, e);
  const y = lerp(sy, dy, e) - Math.sin(Math.PI * e) * 70;
  const open = smootherstep((u - 0.3) / 0.55);
  const w = lerp(2 * HERO.r * ss, (tw - 2) * ds, open);
  const h = lerp(2 * HERO.r * ss, rows * ROW_H * ds, open);
  const fade = 1 - smootherstep((u - 0.91) / 0.09);
  g.save();
  g.globalAlpha = fade;
  // The cell's body, as the scene draws it, while it is still round.
  if (open < 1) {
    const r = Math.min(w, h) / 2;
    g.globalAlpha = fade * (1 - open);
    const glow = g.createRadialGradient(x, y, r * 0.6, x, y, r * 1.9);
    glow.addColorStop(0, rgba(PROT, 0.35));
    glow.addColorStop(1, rgba(PROT, 0));
    g.fillStyle = glow;
    g.fillRect(x - r * 2, y - r * 2, r * 4, r * 4);
    const body = g.createRadialGradient(x - r * 0.32, y - r * 0.36, 0, x - r * 0.32, y - r * 0.36, r * 1.9);
    body.addColorStop(0, 'rgba(255,255,255,0.95)');
    body.addColorStop(0.46, rgba(PROT, 0.32));
    body.addColorStop(1, rgba(PROT, 0.78));
    g.fillStyle = body;
    roundRect(g, x - w / 2, y - h / 2, w, h, lerp(r, 3 * ds, open));
    g.fill();
    g.lineWidth = 3 * ss;
    g.strokeStyle = rgba(PROT, 0.9);
    g.stroke();
  }
  // Its measurements: one tile per protein, bright where measured.
  if (open > 0) {
    g.globalAlpha = fade * open;
    const th = h / rows;
    for (let r = 0; r < rows; r++) {
      const v = hm.log2[0][r];
      g.fillStyle = v === null ? hatch(g) : level(v);
      roundRect(g, x - w / 2, y - h / 2 + r * th + ds, w, th - 2 * ds, 3 * ds);
      g.fill();
    }
  }
  g.restore();
}

// ---- 3 to 4: the measured tiles lift off and gather ----

const MEASURED = [];
for (let c = 0; c < COLS; c++) for (let r = 0; r < V.heatmap.genes.length; r++) if (V.heatmap.log2[c][r] !== null) MEASURED.push([c, r]);
function tilesToShoal(g, t, poseOf) {
  const E = startOf('rna');
  if (t < E - OUT || t > E + IN) return;
  const pose = poseOf(t);
  const tw = tileWidth('gaps');
  const m = MATRIX.gaps;
  const n = V.atlas3.points.length;
  const p4 = Math.max(0, t - E) / V.frames.find((f) => f.id === 'rna').seconds;
  g.save();
  MEASURED.forEach(([c, r], j) => {
    const lift = E - OUT + 0.9 * gapsLift(c, r);
    const land = E + IN - 0.45 + 0.35 * jitter(j, 13);
    const q = span(t, lift, land);
    if (q <= 0 || q >= 1) return;
    const e = smootherstep(q);
    const [sx, sy, ss] = on('gaps', pose, m.left + LABEL_W + c * tw + tw / 2, m.top + r * ROW_H + ROW_H / 2);
    const i = Math.floor((j * n) / MEASURED.length);
    const [cx, cy, depth] = rnaOnCanvas(i, p4);
    const [dx, dy, ds] = on('rna', pose, RNA_CANVAS.left + cx, RNA_CANVAS.top + cy);
    const bend = (jitter(j, 14) - 0.5) * 240;
    const x = lerp(sx, dx, e) + Math.sin(Math.PI * e) * bend;
    const y = lerp(sy, dy, e) - Math.sin(Math.PI * e) * 90;
    // A tile becomes a dot, and the protein's blue the RNA's orange.
    const size = lerp(Math.min(tw, ROW_H) * 0.45 * ss, rnaRadius(depth) * ds, e);
    g.globalAlpha = 0.95 * (1 - smootherstep((q - 0.88) / 0.12));
    g.fillStyle = mixHex(ACCENT, RNA, smootherstep((q - 0.25) / 0.5));
    roundRect(g, x - size, y - size, size * 2, size * 2, lerp(3 * ss, size, Math.min(1, e * 3)));
    g.fill();
  });
  g.restore();
}

// ---- 4 to 5: the atlas streams into the wordmark ----

// The wordmark's letters in scene 5's layout (compositions/s05-vivome.html).
export const WORDMARK = { x: [620, 1300], y: [375, 490] };
const CARRIED = rnaCarried(320);
function shoalToWordmark(g, t, poseOf) {
  const E = startOf('vivome');
  if (t < E - OUT || t > E + IN) return;
  const pose = poseOf(t);
  const p4 = (t - startOf('rna')) / V.frames.find((f) => f.id === 'rna').seconds;
  g.save();
  CARRIED.forEach((i, j) => {
    const lift = E - OUT + 1.2 * rnaLift(i);
    const land = E + 1.25 + 0.35 * jitter(j, 17);
    const q = span(t, lift, land);
    if (q <= 0 || q >= 1) return;
    const e = smootherstep(q);
    const [cx, cy, depth] = rnaOnCanvas(i, Math.min(p4, 1));
    const [sx, sy, ss] = on('rna', pose, RNA_CANVAS.left + cx, RNA_CANVAS.top + cy);
    const tx = lerp(WORDMARK.x[0], WORDMARK.x[1], jitter(j, 18));
    const ty = lerp(WORDMARK.y[0], WORDMARK.y[1], jitter(j, 19));
    const [dx, dy, ds] = on('vivome', pose, tx, ty);
    const x = lerp(sx, dx, e);
    const y = lerp(sy, dy, e) + Math.sin(Math.PI * e) * (jitter(j, 20) - 0.5) * 260;
    g.globalAlpha = 0.95 * (1 - smootherstep((q - 0.8) / 0.2));
    g.fillStyle = mixHex(rnaPoint(i, 1).colour, INK, smootherstep((q - 0.4) / 0.5));
    g.beginPath();
    g.arc(x, y, lerp(rnaRadius(depth) * ss, 5 * ds, e), 0, TAU);
    g.fill();
  });
  g.restore();
}

// ---- 6 to 7: rows into the encoders, points out onto the map ----

const members = V.facts['ms:wf_members'];
// The encoders drawn are the served model's own count; one, unnumbered,
// if that number is pending.
const ENCODERS = members?.measured ? Math.max(1, parseInt(members.text, 10) || 1) : 1;
const between = (a, b) => PLAN[a].at.map((v, k) => (v + PLAN[b].at[k]) / 2);
const MID = between('built-for-gaps', 'answers');
const encoderAt = (k) => [960 + (k - (ENCODERS - 1) / 2) * 200, 520];
const SHOT_POINTS = (() => {
  const shot = V.answersShot;
  const place = placer(shot.box, shot.bounds);
  const inside = V.map.sample.map(([x, y, k]) => [...place([x, y]), k])
    .filter(([x, y]) => x >= shot.box[0] && x <= shot.box[2] && y >= shot.box[1] && y <= shot.box[3]);
  return Array.from({ length: 160 }, (_, j) => inside[Math.floor((j * inside.length) / 160)]);
})();
function rowsToMap(g, t, poseOf) {
  const E = startOf('answers');
  if (t < E - OUT || t > E + IN) return;
  const pose = poseOf(t);
  const hm = V.heatmap;
  const rows = hm.genes.length;
  const tw = tileWidth('built-for-gaps');
  const m = MATRIX['built-for-gaps'];
  const nodes = Array.from({ length: ENCODERS }, (_, k) => project(pose, MID, ...encoderAt(k)));
  g.save();
  // The rows: each leaves the matrix as a bar and narrows to a dot.
  for (let r = 0; r < rows; r++) {
    const lift = E - OUT + 1.2 * rowLift(r, rows);
    const q = span(t, lift, lift + 0.75);
    if (q <= 0 || q >= 1) continue;
    const e = smootherstep(q);
    const [sx, sy, ss] = on('built-for-gaps', pose, m.left + LABEL_W + (COLS * tw) / 2, m.top + r * ROW_H + ROW_H / 2);
    const [nx, ny, ns] = nodes[r % ENCODERS];
    const x = lerp(sx, nx, e);
    const y = lerp(sy, ny, e);
    const w = lerp(COLS * tw * ss, 10 * ns, e);
    const h = lerp((ROW_H - 2) * ss, 10 * ns, e);
    g.globalAlpha = 0.9 * (1 - smootherstep((q - 0.85) / 0.15));
    const grad = g.createLinearGradient(x - w / 2, y, x + w / 2, y);
    grad.addColorStop(0, rgba(ACCENT, 0.25));
    grad.addColorStop(1, rgba(ACCENT, 0.85));
    g.fillStyle = grad;
    roundRect(g, x - w / 2, y - h / 2, w, h, h / 2);
    g.fill();
  }
  // The encoders: they open as the rows set off, glow as rows reach them,
  // and close once they have sent their points on.
  const shown = smootherstep(span(t, E - OUT, E)) * (1 - smootherstep(span(t, E + 1.3, E + 1.8)));
  nodes.forEach(([x, y, s], k) => {
    if (shown <= 0) return;
    const busy = smootherstep(span(t, E - OUT + 0.6 + k * 0.05, E + 0.5)) * (1 - smootherstep(span(t, E + 0.9, E + 1.4)));
    g.globalAlpha = shown;
    const halo = g.createRadialGradient(x, y, 0, x, y, 70 * s);
    halo.addColorStop(0, rgba('#3FA9E0', 0.45 * busy));
    halo.addColorStop(1, 'rgba(63,169,224,0)');
    g.fillStyle = halo;
    g.fillRect(x - 70 * s, y - 70 * s, 140 * s, 140 * s);
    g.fillStyle = '#FFFFFF';
    g.beginPath();
    g.arc(x, y, 30 * s, 0, TAU);
    g.fill();
    g.lineWidth = 5 * s;
    g.strokeStyle = ACCENT;
    g.stroke();
    g.fillStyle = rgba(ACCENT, 0.3 + 0.6 * busy);
    g.beginPath();
    g.arc(x, y, 12 * s, 0, TAU);
    g.fill();
  });
  // The points: from the encoders to their places on scene 7's map.
  SHOT_POINTS.forEach(([px, py, k], j) => {
    const leave = E + 0.45 + 0.45 * jitter(j, 21);
    const q = span(t, leave, leave + 0.65);
    if (q <= 0 || q >= 1) return;
    const e = smootherstep(q);
    const [nx, ny, ns] = nodes[j % ENCODERS];
    const [dx, dy, ds] = on('answers', pose, px, py);
    g.globalAlpha = 0.95 * (1 - smootherstep((q - 0.8) / 0.2));
    g.fillStyle = mixHex(ACCENT, V.classes[k].colour, e);
    g.beginPath();
    g.arc(lerp(nx, dx, e), lerp(ny, dy, e) - Math.sin(Math.PI * e) * 60, lerp(4 * ns, 4.5 * ds, e), 0, TAU);
    g.fill();
  });
  g.restore();
}

// ---- 7 to 8: the ladder folds into the two currents ----

// The ladder's middle in scene 7's layout (compositions/s07-answers.html),
// where it folds to.
export const LADDER = { x: 1480, y: 552 };
const STREAM_ORDER = ['encoder', 'correlation'];
function ladderToStreams(g, t, poseOf) {
  const E = startOf('second-opinion');
  const set = E - OUT + 0.2;
  g.save();
  g.lineCap = 'round';
  STREAM_ORDER.forEach((name, k) => {
    const arrive = E + SECOND[name][0];
    if (t < set || t > arrive) return;
    // Where the current's head is at time s: from the folded ladder to the
    // start of its path in scene 8, along an arc, both ends moving with
    // their scenes.
    const head = (s) => {
      const pose = poseOf(s);
      const e = smootherstep(span(s, set, arrive));
      const [sx, sy, ss] = on('answers', pose, LADDER.x, LADDER.y + (k ? 26 : -26));
      const [dx, dy, ds] = on('second-opinion', pose, ...streamStart(name));
      return [lerp(sx, dx, e), lerp(sy, dy, e) + Math.sin(Math.PI * e) * (k ? 110 : -110), lerp(ss, ds, e)];
    };
    const trail = Array.from({ length: 14 }, (_, j) => head(Math.max(set, t - j * 0.035)));
    const grow = smootherstep(span(t, set, set + 0.3));
    g.strokeStyle = STREAMS[name];
    for (let j = 1; j < trail.length; j++) {
      g.globalAlpha = grow * (1 - j / trail.length);
      g.lineWidth = 12 * trail[j][2] * (1 - (j / trail.length) * 0.6);
      g.beginPath();
      g.moveTo(trail[j - 1][0], trail[j - 1][1]);
      g.lineTo(trail[j][0], trail[j][1]);
      g.stroke();
    }
    g.globalAlpha = grow;
    g.fillStyle = STREAMS[name];
    g.beginPath();
    g.arc(trail[0][0], trail[0][1], 6 * trail[0][2], 0, TAU);
    g.fill();
  });
  g.restore();
}

const BRIDGES = [cellToColumn, tilesToShoal, shoalToWordmark, rowsToMap, ladderToStreams];

// When each morph can draw: from the camera setting off from the outgoing
// scene to the end of the incoming scene's first second or so.
const WINDOWS = ['gaps', 'rna', 'vivome', 'answers', 'second-opinion'].map((id) => {
  const E = startOf(id);
  return [E - OUT, E + Math.max(IN, ...(id === 'second-opinion' ? [SECOND.encoder[0], SECOND.correlation[0]] : [0]))];
});

// Draws every morph that is under way at time t. poseOf(s) is the camera at
// any time s (a trail needs where things were a moment ago). Between morphs
// the canvas is hidden, so it lies over no scene's words.
export function createBridges(canvas) {
  const g = canvas.getContext('2d');
  return function draw(t, poseOf) {
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, canvas.width, canvas.height);
    const on = WINDOWS.some(([a, b]) => t >= a && t <= b);
    canvas.style.visibility = on ? 'visible' : 'hidden';
    if (!on) return;
    for (const bridge of BRIDGES) bridge(g, t, poseOf);
    g.globalAlpha = 1;
  };
}
