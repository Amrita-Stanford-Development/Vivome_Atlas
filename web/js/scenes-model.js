// The Workflow page's scenes for the model: the encoder pass, probabilities,
// the best guess, the answer and where the cell lands. Same interface and
// rules as web/js/scenes-input.js: every value drawn is recorded in
// web/data/workflow.json, and a frame depends only on p and the cell.

import { formatCount, isMeasured } from './manifest.js';
import { OUTCOME_CHIPS, OUTCOME_ORDER, PRACTICE_KINDS, formatRecord, plainName, topK } from './workflow-data.js';
import {
  buildGuessTable, buildOutcomeTable, buildProbabilityTable, buildSecondOpinionTable,
} from './workflow-panels.js';
import {
  bandPath, clamp, depthOrder, diverging, fitSphere, lerp, phase, pickNearest, project, radialAngles, rotate, sankey,
  sequential,
} from './workflow-layout.js';
import {
  ACCENT, BENCH, FAINT, FONT, INK, LINE, PROT, PROT_INK, RNA, SOFT, alpha, bar, chip, dot, hatch, line, mountCanvas, onDrag, short, text,
} from './scene-kit.js';

const fc = (x) => formatCount(x);
const pct = (x) => `${(x * 100).toFixed(1)}%`;

// A sentence broken into lines of at most maxW pixels.
function wrapLines(g, str, maxW, size, weight = 400) {
  g.save();
  g.font = `${weight} ${size}px ${FONT}`;
  const lines = [];
  let cur = '';
  for (const word of String(str).split(' ')) {
    const next = cur ? `${cur} ${word}` : word;
    if (cur && g.measureText(next).width > maxW) { lines.push(cur); cur = word; } else cur = next;
  }
  if (cur) lines.push(cur);
  g.restore();
  return lines;
}

// Paragraphs from y down, each drawn whole or not at all (none past bottom).
// Returns where the next one would start.
function paragraphs(g, items, x, y, maxW, bottom, { size = 10.5, colour = SOFT, opacity = 1, lead = 1.5, gap = 8 } = {}) {
  let yy = y;
  for (const item of items) {
    const { str, weight = 400, tint = colour, sz: size0 = size } = typeof item === 'string' ? { str: item } : item;
    // Smaller and tighter before giving up: the full size, then 90% and 82%.
    let fit = null;
    for (const [sz, ld] of [[size0, lead], [size0 * 0.9, lead * 0.95], [Math.max(8, size0 * 0.82), lead * 0.92]]) {
      const lines = wrapLines(g, str, maxW, sz, weight);
      const h = lines.length * sz * ld;
      if (yy + h - sz * (ld - 1) <= bottom) { fit = { sz, ld, lines, h }; break; }
    }
    if (!fit) {
      // Counted on the canvas, so a script can check that no figure drops its explanation.
      g.canvas.dropped = (g.canvas.dropped ?? 0) + 1;
      break;
    }
    fit.lines.forEach((ln, k) => text(g, ln, x, yy + fit.sz + k * fit.sz * fit.ld, { size: fit.sz, colour: tint, weight, opacity }));
    yy += fit.h + gap;
  }
  return yy;
}

// A colour key: a swatch (or a hatched one) and its label; returns the next x.
function key(g, x, y, fill, label, opacity = 1) {
  if (fill) bar(g, x, y - 9, 11, 11, fill, 2, opacity);
  else hatch(g, x, y - 9, 11, 11, opacity);
  text(g, label, x + 16, y, { size: 10.5, colour: SOFT, opacity });
  g.save();
  g.font = `400 10.5px ${FONT}`;
  const wd = g.measureText(label).width;
  g.restore();
  return x + 16 + wd + 14;
}

function scene(el, draw, { describe = () => '', table = () => '', dispose = () => {}, setup = null } = {}) {
  const view = mountCanvas(el);
  let last = null;
  const api = {
    render(p, state) {
      last = [p, state];
      view.clear();
      draw(view, clamp(p, 0, 1), state);
    },
    redraw() { if (last) api.render(...last); },
    resize() { view.resize(); api.redraw(); },
    dispose() { dispose(); view.dispose(); },
    describe,
    table,
  };
  if (setup) setup(view, api);
  return api;
}

// ---- 7: turning the cell into a point on the map ----
// Beat 1: what a learner reads. Beat 2: the narrowing, ending in the cell's
// 128 numbers. Beat 3: every learner side by side.

const PARTS = {
  values: 'its values', mask: 'its mask', module_values: 'gene-group averages', module_mask_fraction: 'share of each group measured',
};
const PARTS_SHORT = { values: 'values', mask: 'mask', module_values: 'group averages', module_mask_fraction: 'group shares' };

export function encoder(el, ctx) {
  const w = ctx.workflow;
  const enc = w.trace.stages.encoder;
  const layers = enc.layers;
  const anchor = enc.members.indexOf(enc.coordinate_member);
  return scene(el, ({ g, width, height }, p, state) => {
    const narrow = width < 560;
    const { detail, own } = ctx.detail(state);
    const lanes = phase(p, 0.66, 0.72);
    const diagram = 1 - lanes;
    if (diagram > 0) {
      g.save();
      g.globalAlpha = diagram;
      const squeeze = phase(p, 0.36, 0.58);
      text(g, squeeze < 0.05 ? (narrow ? `Each learner reads ${fc(layers[0].width)} numbers` : `What each learner reads: ${fc(layers[0].width)} numbers about our cell`) : `Squeezed step by step, down to ${fc(layers[layers.length - 1].width)} numbers`,
        12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const barcode = phase(p, 0.56, 0.64);
      // Room under the diagram for the cell's numbers and their note, on a short figure too.
      const diagramH = lerp(height - 40, Math.min(height * (narrow ? 0.56 : 0.62), height - 76), barcode);
      const left = narrow ? 100 : 290;
      const colX = layers.map((_, i) => left + (i / (layers.length - 1)) * (width - left - 70));
      const H = diagramH - 70;
      const tall = (wd) => Math.max(10, (Math.log10(wd) / Math.log10(layers[0].width)) * H);
      // The input: its four parts, stacked.
      const parts = Object.entries(layers[0].parts);
      const minH = 16;
      const big = H - minH * parts.filter(([, v]) => v / layers[0].width < 0.05).length;
      let yy = 40;
      const reveal = phase(p, 0.02, 0.2);
      parts.forEach(([name, n], k) => {
        const share = n / layers[0].width;
        const ph = share < 0.05 ? minH : (n / parts.filter(([, v]) => v / layers[0].width >= 0.05).reduce((s, [, v]) => s + v, 0)) * big;
        const op = clamp(reveal * parts.length - k, 0, 1);
        bar(g, colX[0] - 14, yy, 28, ph - 2, [ACCENT, INK, '#5b8fc0', '#8a97a3'][k], 2, op);
        text(g, `${(narrow ? PARTS_SHORT : PARTS)[name] ?? name}: ${fc(n)}`, colX[0] - 22, yy + ph / 2 + 4, { size: narrow ? 9.5 : 11, colour: INK, align: 'right', opacity: op, max: colX[0] - 30 });
        yy += ph;
      });
      text(g, narrow ? fc(layers[0].width) : `${fc(layers[0].width)} in`, colX[0], 40 + H + 18, { size: 12, colour: INK, align: 'center', weight: 600, opacity: reveal });
      // The narrowing.
      layers.forEach((layer, i) => {
        if (i === 0) return;
        const on = clamp(squeeze * (layers.length - 1) - (i - 1), 0, 1);
        const h = tall(layer.width);
        const y = 40 + (H - h) / 2;
        bar(g, colX[i] - 12, y, 24, h, i === layers.length - 1 ? PROT : ACCENT, 4, 0.9 * on);
        text(g, fc(layer.width), colX[i], 40 + H + 18, { size: 12, colour: INK, align: 'center', weight: 600, opacity: on });
      });
      const last = colX[layers.length - 1];
      text(g, 'the cell\u2019s address', last, 40 + H + 34, { size: 10.5, colour: PROT_INK, align: 'center', weight: 600, opacity: squeeze });
      for (let k = 0; k < 40; k += 1) {
        const t = squeeze * 1.4 - (k / 40) * 0.4;
        if (t <= 0 || t >= 1) continue;
        const seg = Math.min(layers.length - 2, Math.floor(t * (layers.length - 1)));
        const local = t * (layers.length - 1) - seg;
        const spread = ((k * 53) % 17) / 17 - 0.5;
        const h = lerp(seg === 0 ? H : tall(layers[seg].width), tall(layers[seg + 1].width), local);
        dot(g, lerp(colX[seg] + 14, colX[seg + 1] - 12, local), 40 + H / 2 + spread * h * 0.8, 2.2, ACCENT, 0.55);
      }
      // The cell's numbers.
      if (barcode > 0 && detail) {
        const y = Math.min(diagramH + 6, height - 70);
        const bw = width - 24;
        text(g, `Our cell\u2019s ${detail.embedding.length} numbers, from learner ${anchor + 1}${own ? '' : ` (shown for cell ${detail.cell + 1}, a cell like ours)`}`, 12, y + 10,
          { size: 11, colour: INK, weight: 600, opacity: barcode, max: bw });
        const cw = bw / detail.embedding.length;
        detail.embedding.forEach((v, k) => {
          if (k / detail.embedding.length > barcode) return;
          g.fillStyle = diverging(v * 8) ?? BENCH;
          g.fillRect(12 + k * cw, y + 20, Math.max(0.5, cw - 0.4), 26);
        });
        text(g, narrow ? 'Each stripe is one number.' : 'Each stripe is one number: blue below zero, brown above. Together they place the cell on the map.', 12, y + 64,
          { size: 10.5, colour: SOFT, opacity: barcode, max: bw });
      }
      g.restore();
    }
    if (lanes > 0) {
      g.save();
      g.globalAlpha = lanes;
      const n = enc.members.length;
      text(g, `${n} learners, side by side: ${n} positions for our cell`, 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const rowH = Math.min(70, (height - 80) / n);
      const fx = narrow ? 96 : 150;
      const ex = width - (narrow ? 70 : 230);
      enc.members.forEach((name, k) => {
        const y = 48 + k * rowH + rowH / 2;
        const t = clamp(phase(p, 0.72, 0.9) * n - k, 0, 1);
        text(g, `learner ${k + 1}`, fx - 14, y + 4, { size: 11.5, colour: INK, align: 'right', weight: k === anchor ? 600 : 400 });
        // A funnel: wide in, narrow out.
        g.save();
        g.globalAlpha *= 0.85;
        g.fillStyle = alpha(ACCENT, 0.25);
        g.beginPath();
        g.moveTo(fx, y - rowH * 0.32);
        g.lineTo(fx + (ex - fx) * 0.55, y - rowH * 0.08);
        g.lineTo(fx + (ex - fx) * 0.55, y + rowH * 0.08);
        g.lineTo(fx, y + rowH * 0.32);
        g.closePath();
        g.fill();
        g.restore();
        line(g, fx + (ex - fx) * 0.55, y, lerp(fx + (ex - fx) * 0.55, ex, t), y, { colour: ACCENT, width: 1.5 });
        if (t > 0.95) dot(g, ex, y, 6, PROT, 1, INK);
        if (k === anchor && t > 0.95 && !narrow) chip(g, 'also draws the map (step 6 of this part)', ex + 12, y, { size: 10, border: ACCENT, colour: ACCENT });
      });
      text(g, narrow ? 'The next step compares them with each type\u2019s home.' : 'The next step compares each of these positions with the types\u2019 homes on the map.', 12, height - 12,
        { size: 10.5, colour: SOFT, opacity: phase(p, 0.9, 0.97), max: width - 24 });
      g.restore();
    }
  }, {
    describe: () => `Each learner reads ${fc(layers[0].width)} numbers about the cell and squeezes them to ${fc(layers[layers.length - 1].width)}, the cell's position on the map; ${enc.members.length} learners do it side by side.`,
  });
}

// ---- 8: which types is our cell close to? ----
// Beat 1: closeness to each type's home (one learner). Beat 2: the same as
// chances. Beat 3: every learner's chances and their average.

export function probabilities(el, ctx) {
  const w = ctx.workflow;
  const names = w.class_order;
  return scene(el, ({ g, width, height }, p, state) => {
    const { detail, own } = ctx.detail(state);
    if (!detail) return;
    const narrow = width < 560;
    const order = topK(detail.ensemble, names.length);
    const rowH = narrow ? 18 : 22;
    const fit = Math.max(4, Math.floor((height - 92) / rowH));
    const shown = order.slice(0, Math.min(fit, narrow ? 8 : names.length));
    const m0 = detail.members[0];
    const toProb = phase(p, 0.36, 0.5);
    const toAll = phase(p, 0.68, 0.8);
    const cosMin = Math.min(...m0.cosine);
    const cosMax = Math.max(...m0.cosine);
    const pMax = Math.max(...detail.members.flatMap((m) => m.probability), ...detail.ensemble);
    const labelW = narrow ? 110 : 190;
    const bw = width - labelW - 72;
    text(g, toAll > 0.5 ? `All ${detail.members.length} learners\u2019 chances, and their average`
      : toProb > 0.5 ? 'Learner 1: chances for each type, adding up to 100%' : 'Learner 1: how close our cell is to each type\u2019s home',
    12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
    text(g, toAll > 0.5 ? 'thin bars: each learner; thick bar: their average' : toProb > 0.5 ? 'the nearest homes get most of the chance' : 'a longer bar means closer; types are listed by their final chance',
      12, 38, { size: 10.5, colour: SOFT, max: width - 24 });
    shown.forEach((c, r) => {
      const y = 54 + r * rowH;
      text(g, plainName(names[c]), labelW - 8, y + rowH * 0.66, { size: narrow ? 10 : 11, colour: INK, align: 'right', max: labelW - 12, weight: r === 0 && toAll > 0.5 ? 600 : 400 });
      const close = (m0.cosine[c] - cosMin) / (cosMax - cosMin || 1);
      const prob = m0.probability[c] / pMax;
      const one = lerp(close, prob, toProb);
      if (toAll < 1) bar(g, labelW, y + rowH * 0.18, bw * one, rowH * 0.64, toProb > 0.5 ? '#7FA7C9' : '#AEB9C2', 3, 1 - toAll);
      if (toAll > 0) {
        detail.members.forEach((m, j) => bar(g, labelW, y + 2 + j * 2.2, bw * (m.probability[c] / pMax), 1.6, '#8EA9C1', 0, toAll * 0.9));
        bar(g, labelW, y + rowH * 0.45, bw * (detail.ensemble[c] / pMax) * toAll, rowH * 0.42, ACCENT, 3);
      }
      const value = toAll > 0.5 ? detail.ensemble[c] : m0.probability[c];
      if (toProb > 0.5) text(g, pct(value), labelW + bw * (toAll > 0.5 ? detail.ensemble[c] / pMax : prob) + 6, y + rowH * 0.7, { size: 10, colour: INK });
    });
    const hidden = names.length - shown.length;
    if (hidden > 0) {
      const rest = Math.max(...order.slice(shown.length).map((c) => detail.ensemble[c]));
      text(g, `and ${hidden} more types${toProb > 0.5 ? `, each under ${pct(rest)}` : ''}`, labelW, 54 + shown.length * rowH + 14, { size: 10, colour: FAINT });
    }
    if (!own) text(g, `(shown for cell ${detail.cell + 1}, a cell like ours)`, width - 12, height - 8, { size: 9.5, colour: FAINT, align: 'right' });
  }, {
    describe: (state) => {
      const { detail } = ctx.detail(state);
      const c = topK(detail.ensemble, 1)[0];
      return `Averaged over the learners, the highest chance is ${plainName(names[c])}, ${pct(detail.ensemble[c])}.`;
    },
    table: (state) => buildProbabilityTable(ctx.detail(state).detail, names),
  });
}

// ---- 9: a second opinion ----
// Beat 1: the types' fingerprints on a few marker genes. Beat 2: our cell's
// own pattern above them. Beat 3: our cell against its best and its worst
// match, gene by gene. Beat 4: every type's match score, then the chances
// they become. Beat 5: the best guess with it and without it, in testing.
// Beat 6: whether it is trusted in this file. Beat 7: how that bar was set.

// The fingerprint picture: well-known marker genes and a spread of types (by
// name, those the trace has), the cell's best match always among the types.
const PRINT_GENES = ['CD3E', 'CD4', 'CD8A', 'PRF1', 'GZMB', 'LYZ', 'S100A8', 'CD14', 'HLA-DRA', 'PPBP', 'PF4', 'HBB'];
const PRINT_GENES_NARROW = ['CD3E', 'CD8A', 'GZMB', 'LYZ', 'CD14', 'PPBP', 'HBB'];
// The practice files' kinds in a phone's few words.
const KINDS_SHORT = { single: 'one type', lineage: 'one branch', scope2: 'SCoPE2-like', narrow: '2 or 3 types', pbmc: 'blood-like', mixed: '5 or 8 types' };
const PRINT_TYPES = ['cd4-positive, alpha-beta t cell', 'cd8-positive, alpha-beta t cell', 'natural killer cell', 'b cell',
  'classical monocyte', 'platelet', 'erythrocyte'];

// One scatter: our cell's values (x) against a type's (y), each axis in its
// own spread around its own middle (the picture's scale, not the score's);
// the dashed diagonal is a perfect match, the solid line the recorded score.
function scatterPanel(g, points, r, x, y, s, { dots = 1, lines = 1, colour = ACCENT }) {
  const mean = (v) => v.reduce((a, b) => a + b, 0) / v.length;
  const sd = (v, m) => Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / v.length) || 1;
  const xs = points.map((q) => q[0]);
  const ys = points.map((q) => q[1]);
  const [mx, my] = [mean(xs), mean(ys)];
  const [sx, sy] = [sd(xs, mx), sd(ys, my)];
  const lim = 2.5;
  const px = (v) => x + ((clamp(v, -lim, lim) + lim) / (2 * lim)) * s;
  const py = (v) => y + s - ((clamp(v, -lim, lim) + lim) / (2 * lim)) * s;
  bar(g, x, y, s, s, '#FFFFFF', 4);
  g.strokeStyle = LINE;
  g.strokeRect(x + 0.5, y + 0.5, s - 1, s - 1);
  points.forEach((q, k) => {
    if (k / points.length > dots) return;
    dot(g, px((q[0] - mx) / sx), py((q[1] - my) / sy), 2.2, PROT, 0.55);
  });
  line(g, px(-lim), py(-lim), px(lim), py(lim), { colour: FAINT, dash: [4, 4], opacity: lines });
  text(g, 'perfect match', x + s - 6, y + 14, { size: 9, colour: FAINT, align: 'right', opacity: lines });
  line(g, px(-lim), py(-lim * r), px(lim), py(lim * r), { colour, width: 2.5, opacity: lines });
}

export function second(el, ctx) {
  const w = ctx.workflow;
  const names = w.class_order;
  const hm = w.trace.heatmap;
  const fusion = w.trace.stages.fusion;
  const cells = w.trace.cells;
  const so = w.second_opinion;
  const genesOf = (list) => list.map((name) => hm.genes.indexOf(name)).filter((k) => k >= 0);
  return scene(el, ({ g, width, height }, p, state) => {
    const { detail } = ctx.detail(state);
    if (!detail) return;
    const narrow = width < 560;
    const gd = detail.guess;
    const sc = gd.scatter;
    const worst = gd.scatter_worst;

    // Beats 1 and 2: the fingerprints, then our cell's own row above them.
    const grid = 1 - phase(p, 0.268, 0.305);
    if (grid > 0) {
      g.save();
      g.globalAlpha = grid;
      const mine = phase(p, 0.155, 0.22);
      const genes = genesOf(narrow ? PRINT_GENES_NARROW : PRINT_GENES);
      let types = PRINT_TYPES.map((name) => names.indexOf(name)).filter((k) => k >= 0);
      if (!types.includes(sc.class)) types = [sc.class, ...types];
      if (narrow) types = [sc.class, ...types.filter((k) => k !== sc.class)].slice(0, 5);
      else types = types.slice(0, 7);
      const labelW = narrow ? 100 : 220;
      const cw = Math.min(58, (width - 24 - labelW) / genes.length);
      const top = 74;
      // Room under the rows for the key (two rows of it on a phone).
      const rh = clamp((height - top - (narrow ? 68 : 52)) / (types.length + 1), 11, 30);
      const yTypes = top + rh + 8;
      text(g, narrow ? 'Each type\u2019s fingerprint' : 'Each type\u2019s fingerprint: its average cell, gene by gene', 12, 20, { size: 12, weight: 600, colour: INK, opacity: 1 - mine, max: width - 24 });
      text(g, narrow ? 'Our cell\u2019s own pattern' : 'Our cell\u2019s own pattern, above the fingerprints', 12, 20, { size: 12, weight: 600, colour: INK, opacity: mine, max: width - 24 });
      text(g, narrow ? `${types.length} of ${names.length} types; ${genes.length} marker genes`
        : `each against all example cells; ${types.length} of the ${names.length} types and ${genes.length} well-known marker genes shown`, 12, 38,
      { size: 10.5, colour: SOFT, max: width - 24 });
      genes.forEach((k, j) => text(g, hm.genes[k], labelW + j * cw + cw / 2, top - 8, { size: narrow ? 8.5 : 9.5, colour: INK, align: 'center', max: cw - 2 }));
      const reveal = phase(p, 0.01, 0.085);
      types.forEach((c, r) => {
        const y = yTypes + r * rh;
        const a = clamp(reveal * types.length - r, 0, 1);
        text(g, plainName(names[c]), labelW - 8, y + rh * 0.68, { size: narrow ? 9.5 : 11, colour: INK, align: 'right', opacity: a, max: labelW - 12 });
        genes.forEach((k, j) => bar(g, labelW + j * cw + 1, y + 1, cw - 2, rh - 2, diverging(hm.fingerprints[c][k]) ?? BENCH, 2, a));
      });
      // Our cell's row: its own values in the file, empty where it measured nothing.
      const hmOwn = hm.cells.indexOf(state.cell) >= 0;
      const hc = hmOwn ? hm.cells.indexOf(state.cell) : hm.cells.indexOf(detail.cell);
      if (mine > 0 && hc >= 0) {
        text(g, hmOwn ? 'our cell' : `cell ${hm.cells[hc] + 1}`, labelW - 8, top + rh * 0.68, { size: narrow ? 10 : 11.5, colour: ACCENT, weight: 700, align: 'right', opacity: mine });
        genes.forEach((k, j) => {
          const x = labelW + j * cw + 1;
          if (hm.mask[hc][k]) bar(g, x, top + 1, cw - 2, rh - 2, diverging(hm.z[hc][k]) ?? BENCH, 2, mine);
          else hatch(g, x, top + 1, cw - 2, rh - 2, mine);
        });
        g.save();
        g.globalAlpha *= mine;
        g.strokeStyle = ACCENT;
        g.lineWidth = 1.5;
        g.strokeRect(labelW - 0.5, top - 0.5, genes.length * cw + 1, rh + 1);
        g.restore();
      }
      const yL = yTypes + types.length * rh + 20;
      let lx = 12;
      lx = key(g, lx, yL, diverging(-2), narrow ? 'less' : 'less than average', reveal);
      lx = key(g, lx, yL, diverging(0), narrow ? 'average' : 'about average', reveal);
      lx = key(g, lx, yL, diverging(2), narrow ? 'more' : 'more than average', reveal);
      if (narrow) key(g, 12, yL + 17, null, 'not measured, left out', mine);
      else key(g, lx, yL, null, 'not measured, left out', mine);
      if (!hmOwn && mine > 0) {
        text(g, `(shown for cell ${hm.cells[hc] + 1}, a cell like ours)`, narrow ? 12 : width - 12, narrow ? 54 : 38,
          { size: 9.5, colour: FAINT, align: narrow ? 'left' : 'right', opacity: mine });
      }
      g.restore();
    }

    // Beat 3: our cell against its best match and its worst, gene by gene.
    const three = phase(p, 0.268, 0.305) * (1 - phase(p, 0.41, 0.447));
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, narrow ? 'Our cell against a fingerprint' : 'Our cell against a type\u2019s fingerprint, gene by gene', 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, narrow ? `one dot per gene (${fc(sc.points.length)} shown)` : `one dot per gene our cell measured (${fc(sc.points.length)} of its ${fc(sc.observed_proteins)} shown)`, 12, 38,
        { size: 10.5, colour: SOFT, max: width - 24 });
      const panels = narrow || !worst ? [[sc, 'best match', ACCENT]] : [[sc, 'best match', ACCENT], [worst, 'worst match', INK]];
      const pw = (width - 24 - (panels.length - 1) * 12) / panels.length;
      // Room under the boxes for the score, its verdict and the lines' key.
      const boxS = Math.max(60, Math.min(pw - 56, height - 70 - (narrow ? 104 : 86)));
      const dotsIn = phase(p, 0.30, 0.35);
      const lines = phase(p, 0.35, 0.385);
      panels.forEach(([s, kind, colour], k) => {
        const px = 12 + k * (pw + 12);
        const bx = px + (pw - boxS) / 2;
        const by = 70;
        text(g, `${kind}: ${plainName(names[s.class])}`, bx + boxS / 2, by - 8, { size: 11, weight: 600, colour, align: 'center', max: pw });
        scatterPanel(g, s.points, s.r, bx, by, boxS, { dots: dotsIn, lines, colour });
        text(g, 'our cell: less \u2192 more', bx + boxS, by + boxS + 13, { size: 9.5, colour: SOFT, align: 'right' });
        g.save();
        g.translate(bx - 8, by + boxS);
        g.rotate(-Math.PI / 2);
        text(g, boxS < 120 ? 'type: less \u2192 more' : 'the type: less \u2192 more', 0, 0, { size: 9.5, colour: SOFT, max: boxS });
        g.restore();
        const score = `match score ${s.r.toFixed(2)}`;
        const verdict = `the dots ${s.r >= 0 ? 'climb' : 'fall'} ${Math.abs(s.r) < 0.3 ? 'only slightly' : 'clearly'}; ${kind === 'best match' ? 'still the best' : 'the poorest'} of all ${names.length}`;
        text(g, score, bx + boxS / 2, by + boxS + 32, { size: 13, weight: 700, colour, align: 'center', opacity: lines });
        text(g, narrow ? `${s.r >= 0 ? 'climbs' : 'falls'} ${Math.abs(s.r) < 0.3 ? 'slightly' : 'clearly'}; ${kind === 'best match' ? 'still the best' : 'the poorest'} of ${names.length}` : verdict,
          bx + boxS / 2, by + boxS + 49, { size: 10, colour: SOFT, align: 'center', opacity: lines, max: pw });
      });
      if (narrow) {
        if (worst) text(g, `Worst match: ${plainName(names[worst.class])}, score ${worst.r.toFixed(2)}`, 12, height - 22, { size: 10, colour: INK, opacity: lines, max: width - 24 });
        text(g, 'Solid line: the dots\u2019 trend. Dashed: a perfect match.', 12, height - 7, { size: 9.5, colour: FAINT, opacity: lines, max: width - 24 });
      } else {
        text(g, 'Solid line: the trend of the dots. Dashed: where a perfect match would sit. The score uses every gene our cell measured.', 12, height - 8,
          { size: 10, colour: FAINT, opacity: lines, max: width - 24 });
      }
      g.restore();
    }

    // Beat 4: every type's score, then the chances they become.
    const four = phase(p, 0.41, 0.447) * (1 - phase(p, 0.553, 0.59));
    if (four > 0) {
      g.save();
      g.globalAlpha = four;
      const order = topK(gd.r, names.length);
      const last = order[order.length - 1];
      const rowH = narrow ? 17 : clamp((height - 136) / 8, 19, 30);
      const n = Math.max(3, Math.min(8, Math.floor((height - 128) / rowH)));
      const shown = order.slice(0, n);
      const grow = phase(p, 0.445, 0.49);
      const morph = phase(p, 0.495, 0.533);
      const cp = gd.correlation_probability;
      text(g, narrow ? 'Every type scored, then chances' : 'Every type\u2019s match score, then the chances they become', 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, `the ${n} best of ${names.length}; the rest score lower, down to ${plainName(names[last])} at ${gd.r[last].toFixed(2)}`, 12, 38,
        { size: 10.5, colour: SOFT, max: width - 24 });
      const labelW = narrow ? 104 : 210;
      const top = 70;
      const maxR = Math.max(0.01, gd.r[order[0]]);
      const maxP = Math.max(0.01, cp[order[0]]);
      const colour = (r) => (r === 0 ? ACCENT : '#AEB9C2');
      if (!narrow) {
        const colW = (width - labelW - 24 - 80) / 2;
        const x1 = labelW;
        const x2 = labelW + colW + 80;
        text(g, 'match score', x1, top - 10, { size: 10.5, weight: 600, colour: INK, opacity: grow });
        text(g, 'chance, the second opinion', x2, top - 10, { size: 10.5, weight: 600, colour: ACCENT, opacity: morph });
        text(g, '\u2192', x1 + colW + 40, top + (n * rowH) / 2, { size: 22, colour: ACCENT, align: 'center', opacity: morph });
        shown.forEach((c, r) => {
          const y = top + r * rowH;
          text(g, plainName(names[c]), labelW - 10, y + rowH * 0.68, { size: 11, colour: INK, align: 'right', weight: r === 0 ? 600 : 400, max: labelW - 14 });
          const l1 = (colW - 50) * Math.max(0, gd.r[c]) / maxR * grow;
          bar(g, x1, y + rowH * 0.2, l1, rowH * 0.6, colour(r), 3);
          text(g, gd.r[c].toFixed(2), x1 + l1 + 6, y + rowH * 0.68, { size: 10.5, colour: INK, opacity: grow });
          const l2 = (colW - 56) * cp[c] / maxP * morph;
          bar(g, x2, y + rowH * 0.2, l2, rowH * 0.6, colour(r), 3);
          text(g, pct(cp[c]), x2 + l2 + 6, y + rowH * 0.68, { size: 10.5, colour: INK, opacity: morph });
        });
      } else {
        const bw = width - labelW - 60;
        text(g, morph > 0.5 ? 'chance, the second opinion' : 'match score', labelW, top - 10, { size: 10.5, weight: 600, colour: morph > 0.5 ? ACCENT : INK });
        shown.forEach((c, r) => {
          const y = top + r * rowH;
          text(g, plainName(names[c]), labelW - 8, y + rowH * 0.7, { size: 9.5, colour: INK, align: 'right', weight: r === 0 ? 600 : 400, max: labelW - 10 });
          const l = bw * lerp(Math.max(0, gd.r[c]) / maxR, cp[c] / maxP, morph) * grow;
          bar(g, labelW, y + rowH * 0.2, l, rowH * 0.6, colour(r), 3);
          text(g, morph > 0.5 ? pct(cp[c]) : gd.r[c].toFixed(2), labelW + l + 5, y + rowH * 0.7, { size: 9.5, colour: INK, opacity: grow });
        });
      }
      paragraphs(g, [narrow ? 'The chances add up to 100%; the best matches take most.'
        : 'The chances add up to 100%. A type that matches a little better than the rest takes a much bigger share, so even weak scores pick out the best matches.'],
      12, top + n * rowH + 10, width - 24, height - 4, { opacity: morph });
      g.restore();
    }

    // Beat 5: the best guess with the second opinion and without it, in testing.
    const five = phase(p, 0.553, 0.59) * (1 - phase(p, 0.695, 0.733));
    if (five > 0 && so) {
      g.save();
      g.globalAlpha = five;
      text(g, narrow ? 'Does it help? Best guesses right' : 'Does it help? The share of best guesses that are right, every type counted equally', 12, 20,
        { size: 12, weight: 600, colour: INK, max: width - 24 });
      let lx = key(g, 12, 42, '#AEB9C2', 'the learners alone');
      key(g, lx, 42, ACCENT, 'with the second opinion');
      const label = (r) => (r.files === 'all' ? `all ${formatRecord(r.count)} practice files`
        : narrow ? `practice, ${PRACTICE_KINDS[r.files]}` : `${formatRecord(r.count)} practice files with ${PRACTICE_KINDS[r.files]}`);
      const rows = [[narrow ? 'Fulcher 2026' : 'Fulcher 2026, a real protein file', so.fulcher_without, so.fulcher_with],
        ...so.practice.map((r) => [label(r), r.without, r.with])].filter(([, a, b]) => isMeasured(a) && isMeasured(b));
      const labelW = narrow ? 120 : 280;
      const bw = width - labelW - 64;
      const top = 58;
      const rowH = clamp((height - top - 30) / rows.length, 26, 56);
      const grow = phase(p, 0.59, 0.67);
      rows.forEach(([name, without, withIt], k) => {
        const y = top + k * rowH;
        const bh = Math.min(14, rowH * 0.3);
        text(g, name, labelW - 10, y + bh + 4, { size: narrow ? 9.5 : 11, colour: INK, align: 'right', max: labelW - 14 });
        [[without, '#AEB9C2'], [withIt, ACCENT]].forEach(([rec, colour], j) => {
          const yy = y + 2 + j * (bh + 3);
          bar(g, labelW, yy, bw * rec.value * grow, bh, colour, 3);
          text(g, formatRecord(rec), labelW + bw * rec.value * grow + 5, yy + bh - 2, { size: 10, colour: INK, opacity: grow });
        });
      });
      text(g, narrow ? 'Development figures.' : 'Development figures: Fulcher 2026 also chose how much weight the second opinion gets.', 12, height - 10,
        { size: 10, colour: FAINT, opacity: grow, max: width - 24 });
      g.restore();
    }

    // Beat 6: can it be trusted in this file?
    const six = phase(p, 0.695, 0.733) * (1 - phase(p, 0.838, 0.876));
    if (six > 0) {
      g.save();
      g.globalAlpha = six;
      const counted = cells.filter((c) => c.counted);
      text(g, 'Can the second opinion be trusted in this file?', 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, narrow ? 'one dot per cell; blue: it agrees with the learners' : 'one dot per cell; blue: the second opinion\u2019s top type is the learners\u2019 top type', 12, 38,
        { size: 10.5, colour: SOFT, max: width - 24 });
      const fill = phase(p, 0.735, 0.79);
      const bw = width - 24;
      const per = Math.ceil(counted.length / 8);
      const dw = bw / per;
      const gap = clamp((height - 58 - 150) / 8, 6, narrow ? 10 : 22);
      counted.forEach((c, k) => {
        if (k / counted.length > fill) return;
        dot(g, 12 + (k % per) * dw + dw / 2, 58 + Math.floor(k / per) * gap, Math.min(4.5, dw * 0.38, gap * 0.42), c.agrees ? ACCENT : '#C9D1D7');
      });
      const by = 58 + 8 * gap + 14;
      bar(g, 12, by, bw, 16, BENCH, 8);
      bar(g, 12, by, bw * fusion.agreement * fill, 16, ACCENT, 8, 0.85);
      line(g, 12 + bw * fusion.threshold, by - 8, 12 + bw * fusion.threshold, by + 24, { colour: INK, width: 2 });
      text(g, `needed: ${pct(fusion.threshold)}`, 12 + bw * fusion.threshold + 6, by - 2, { size: 11, colour: INK, weight: 600 });
      text(g, `agrees: ${pct(fusion.agreement)} (${fc(fusion.agreeing)} of ${fc(fusion.counted)} cells)`, 12, by + 40, { size: 11, colour: ACCENT, weight: 600, opacity: fill });
      const used = fusion.correlation_term === 'used';
      const verdict = phase(p, 0.79, 0.815);
      paragraphs(g, [
        { str: used ? 'Above the line: in this file the second opinion is trusted and mixed in.'
          : 'Below the line: in this file the second opinion is set aside, and the learners decide alone.', tint: INK },
        narrow ? 'Why: in a file of one kind of cell, \u201cmore than average\u201d says little.'
          : 'Why a check: each gene is compared within the file, so in a file of one kind of cell \u201cmore than average\u201d says little, and the second opinion would mislead.',
      ], 12, by + 50, width - 24, height - 4, { opacity: verdict, gap: 4, size: narrow ? 10 : 11.5, lead: narrow ? 1.4 : 1.5 });
      g.restore();
    }

    // Beat 7: how the bar was set: the practice files it was chosen on, by kind.
    const seven = phase(p, 0.838, 0.876);
    const gate = so?.gate;
    if (seven > 0 && gate) {
      g.save();
      g.globalAlpha = seven;
      const barText = formatRecord(w.facts.agreement_threshold);
      text(g, narrow ? 'How the bar was set' : `How the ${barText} bar was set: the practice files it was chosen on, by kind`, 12, 20,
        { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, narrow ? 'one dot per file: how often its second opinion agreed'
        : 'one dot per practice file, placed at how often its second opinion agreed with the learners; blue: at or above the bar', 12, 38,
      { size: 10.5, colour: SOFT, max: width - 24 });
      const order = ['single', 'lineage', 'scope2', 'narrow', 'pbmc', 'mixed'].filter((k) => gate.rows.some(([grp]) => grp === k));
      const labelW = narrow ? 104 : 200;
      const right = narrow ? 44 : 96;
      const ax = (v) => labelW + v * (width - labelW - right);
      const top = 60;
      const rowH = clamp((height - top - (narrow ? 76 : 70)) / (order.length + 1), 15, 34);
      const appear = phase(p, 0.875, 0.93);
      const notes = phase(p, 0.93, 0.96);
      const yEnd = top + (order.length + 1) * rowH;
      line(g, ax(fusion.threshold), top - 6, ax(fusion.threshold), yEnd + 2, { colour: INK, width: 2 });
      text(g, `the bar: ${barText}`, ax(fusion.threshold) + 5, top - 2, { size: 10, colour: INK, weight: 600 });
      order.forEach((grp, r) => {
        const y = top + 6 + r * rowH + rowH / 2;
        const files = gate.rows.filter(([k]) => k === grp);
        const kind = narrow ? (KINDS_SHORT[grp] ?? grp) : (PRACTICE_KINDS[grp] ?? grp);
        text(g, `${kind} (${fc(files.length)})`, labelW - 10, y + 4, { size: narrow ? 9.5 : 11, colour: INK, align: 'right', max: labelW - 14 });
        files.forEach(([, a], k) => {
          if (k / files.length > appear) return;
          const jitter = ((((k * 37) % 11) / 10) - 0.5) * Math.min(10, rowH * 0.5);
          dot(g, ax(a), y + jitter, narrow ? 2.4 : 3, a >= fusion.threshold ? ACCENT : '#AEB9C2', 0.85);
        });
        const med = gate.median?.[grp];
        if (isMeasured(med)) {
          line(g, ax(med.value), y - rowH * 0.42, ax(med.value), y + rowH * 0.42, { colour: INK, width: 1.5, opacity: appear });
          text(g, narrow ? formatRecord(med) : `typical ${formatRecord(med)}`, width - 12, y + 4, { size: 10, colour: SOFT, align: 'right', opacity: appear });
        }
      });
      // This file, for comparison.
      const yF = top + 6 + order.length * rowH + rowH / 2;
      text(g, narrow ? 'this file' : 'this file, PBMC240', labelW - 10, yF + 4, { size: narrow ? 9.5 : 11, colour: ACCENT, weight: 700, align: 'right', max: labelW - 14 });
      dot(g, ax(fusion.agreement), yF, 5, fusion.agreement >= fusion.threshold ? ACCENT : '#AEB9C2', 1, ACCENT);
      text(g, pct(fusion.agreement), width - 12, yF + 4, { size: 10, colour: ACCENT, weight: 600, align: 'right' });
      [0, 0.5, 1].forEach((v) => text(g, `${v * 100}%`, ax(v), yEnd + 16, { size: 9.5, colour: FAINT, align: 'center', opacity: appear }));
      const tried = (gate.tried ?? []).filter(isMeasured).map(formatRecord);
      paragraphs(g, [
        narrow ? 'Short line: each kind\u2019s typical file. Files of one kind sit below the bar; mixed ones above.'
          : 'The short line in each row is that kind\u2019s typical file. Files of one kind of cell sit below the bar, where the second opinion made guesses worse; files with many kinds sit above it, where it made them better.',
        tried.length > 1 ? `${tried.join(' and ')} were both tried and gave nearly the same results; ${barText} was kept. Development figures.` : 'Development figures.',
      ], 12, yEnd + 22, width - 24, height - 2, { size: narrow ? 9.5 : 10.5, opacity: notes, gap: 2, lead: 1.4 });
      g.restore();
    }
  }, {
    describe: (state) => {
      const { detail } = ctx.detail(state);
      const gd = detail.guess;
      const top = topK(gd.correlation_probability, 1)[0];
      return `Best match ${plainName(names[gd.scatter.class])} (${gd.scatter.r.toFixed(2)})${gd.scatter_worst ? `, worst ${plainName(names[gd.scatter_worst.class])} (${gd.scatter_worst.r.toFixed(2)})` : ''}; the second opinion's top chance: ${plainName(names[top])}, ${pct(gd.correlation_probability[top])}. ${fusion.correlation_term === 'used' ? 'Used' : 'Set aside'} in this file: it agrees on ${pct(fusion.agreement)} of cells, ${pct(fusion.threshold)} needed.`;
    },
    table: (state) => buildSecondOpinionTable(ctx.detail(state).detail, names),
  });
}

// ---- 10: the best guess ----
// Beat 1: the learners' chances and the second opinion's (or, where it is
// set aside, an even split), mixed into the best guess. Beat 2: the best
// guess and the likeliest types after it.

export function guess(el, ctx) {
  const w = ctx.workflow;
  const names = w.class_order;
  const fusion = w.trace.stages.fusion;
  return scene(el, ({ g, width, height }, p, state) => {
    const { detail, own } = ctx.detail(state);
    if (!detail) return;
    const narrow = width < 560;
    const gd = detail.guess;
    const used = fusion.correlation_term === 'used';
    const wEnc = used ? fusion.encoder_weight_used : fusion.encoder_weight_flat;
    const one = 1 - phase(p, 0.48, 0.52);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const order = topK(gd.fused, 5);
      const flat = names.map(() => 1 / names.length);
      const cols = [
        ['the learners (step 2)', gd.encoder, phase(p, 0.02, 0.12), `\u00d7 ${wEnc}`],
        [used ? 'the second opinion (step 3)' : 'an even split', used ? gd.correlation_probability : flat, phase(p, 0.12, 0.22), `\u00d7 ${(1 - wEnc).toFixed(1)}`],
        [narrow ? 'the best guess' : 'the best guess\u2019s chances', gd.fused, phase(p, 0.3, 0.42), ''],
      ].filter((c, k) => !narrow || k !== 1);
      text(g, 'Two sets of chances, mixed into one', 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, used ? `the second opinion is trusted in this file: the learners weigh ${wEnc}, the second opinion ${(1 - wEnc).toFixed(1)}`
        : narrow ? `second opinion set aside here; learners \u00d7 ${wEnc}, even split \u00d7 ${(1 - wEnc).toFixed(1)}`
          : `the second opinion is set aside in this file (step 3), so an even split takes its place: the learners weigh ${wEnc}, the split ${(1 - wEnc).toFixed(1)}`,
      12, 38, { size: 10.5, colour: SOFT, max: width - 24 });
      const labelW = narrow ? 100 : 190;
      const opGap = narrow ? 22 : 44;
      const colW = (width - labelW - 12 - opGap * (cols.length - 1)) / cols.length;
      const top = 82;
      const rowH = clamp((height - top - 40) / order.length, 18, 40);
      const most = Math.max(...cols.map(([, v]) => Math.max(...order.map((c) => v[c]))));
      order.forEach((c, r) => text(g, plainName(names[c]), labelW - 8, top + r * rowH + rowH * 0.62, { size: narrow ? 9.5 : 11, colour: INK, align: 'right', weight: r === 0 ? 600 : 400, max: labelW - 12 }));
      cols.forEach(([head, values, grow, weight], k) => {
        const x = labelW + k * (colW + opGap);
        const last = k === cols.length - 1;
        text(g, head, x, top - 22, { size: narrow ? 9.5 : 10.5, weight: 600, colour: last ? ACCENT : INK, opacity: grow, max: Math.min(colW + opGap - 6, width - x - 6) });
        if (weight) text(g, weight, x, top - 8, { size: 10, colour: SOFT, opacity: grow });
        order.forEach((c, r) => {
          const y = top + r * rowH;
          const l = (colW - (narrow ? 34 : 44)) * values[c] / most * grow;
          bar(g, x, y + rowH * 0.2, l, rowH * 0.6, last && r === 0 ? ACCENT : last ? '#8bb6da' : '#AEB9C2', 3);
          text(g, pct(values[c]), x + l + 4, y + rowH * 0.62, { size: narrow ? 8.5 : 10, colour: INK, opacity: grow });
        });
        if (!last) text(g, narrow ? '→' : k === cols.length - 2 ? '=' : '+', x + colW + opGap / 2, top + (order.length * rowH) / 2 + 6, { size: 18, colour: ACCENT, align: 'center', opacity: cols[k + 1][2] });
      });
      if (!used) {
        text(g, narrow ? 'An even split adds the same to every type: the order stays.' : 'An even split adds the same to every type, so the learners\u2019 order stays: their top type is the best guess.', 12, height - 10,
          { size: 10, colour: FAINT, opacity: phase(p, 0.3, 0.42), max: width - 24 });
      }
      if (!own) text(g, `(shown for cell ${detail.cell + 1}, a cell like ours)`, width - 12, 20, { size: 9.5, colour: FAINT, align: 'right' });
      g.restore();
    }
    const two = phase(p, 0.48, 0.52);
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      const top = topK(gd.fused, 5);
      text(g, `Our cell\u2019s best guess: ${plainName(names[top[0]])}`, 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, 'its five likeliest types, with their chances', 12, 38, { size: 10.5, colour: SOFT });
      const labelW = narrow ? 120 : 200;
      // Room after the top bar for its value and the "best guess" tag.
      const bw = width - labelW - (narrow ? 80 : 170);
      const rowH = Math.min(46, (height - 110) / top.length);
      const grow = phase(p, 0.52, 0.64);
      top.forEach((c, r) => {
        const y = 60 + r * rowH;
        text(g, plainName(names[c]), labelW - 10, y + rowH * 0.55, { size: 11.5, colour: INK, align: 'right', weight: r === 0 ? 600 : 400, max: labelW - 14 });
        bar(g, labelW, y + rowH * 0.2, bw * gd.fused[c] / gd.fused[top[0]] * grow, rowH * 0.5, r === 0 ? ACCENT : '#AEB9C2', 3);
        text(g, pct(gd.fused[c]), labelW + bw * gd.fused[c] / gd.fused[top[0]] * grow + 6, y + rowH * 0.55, { size: 10.5, colour: INK, opacity: grow });
      });
      if (!narrow) chip(g, 'best guess', labelW + bw * grow + 52, 60 + rowH * 0.45, { size: 10.5, colour: ACCENT, border: ACCENT, opacity: phase(p, 0.62, 0.7) });
      if (!own) text(g, `(shown for cell ${detail.cell + 1}, a cell like ours)`, 12, height - 10, { size: 9.5, colour: FAINT });
      g.restore();
    }
  }, {
    describe: (state) => {
      const { detail } = ctx.detail(state);
      const c = topK(detail.guess.fused, 1)[0];
      return `Best guess ${plainName(names[c])} (${pct(detail.guess.fused[c])}), from the learners' chances ${fusion.correlation_term === 'used' ? 'mixed with the second opinion' : 'with an even split, the second opinion set aside in this file'}.`;
    },
    table: (state) => buildGuessTable(ctx.detail(state).detail, names),
  });
}

// ---- 10: the answer, or the reason for none ----
// Beat 1: the chances against each type's bar: the shortlist. Beat 2: the
// two checks, with every cell's likeness to the examples. Beat 3: how the
// shortlist decides. Beat 4: every cell of the file, by result.

const RULES_SHORT = [
  ['one type', 'name it'], ['one family', 'the family'], ['one branch', 'the branch'], ['mixed branches', 'no answer'], ['none clears', 'no answer'],
];
const OUTCOME_SHORT = {
  class: 'one type', group: 'a family', lineage: 'a branch', ambiguous_between_classes: 'several kinds',
  no_confident_label: 'none stands out', outside_supported_region: 'unlike any', coverage_too_low: 'too little',
};

const RULES = [
  ['class', 'one type on the shortlist', 'name that type'],
  ['group', 'several types, one family', 'name the family'],
  ['lineage', 'several families, one branch', 'name the branch'],
  ['ambiguous_between_classes', 'types from different branches', 'no answer: looks like several kinds'],
  ['no_confident_label', 'nothing clears its bar', 'no answer: no type stands out'],
];

export function answer(el, ctx) {
  const w = ctx.workflow;
  const names = w.class_order;
  const cells = w.trace.cells;
  const qhat = w.trace.stages.calibration.qhat;
  const ood = w.trace.stages.ood.threshold;
  const floor = w.raw.pbmc240.align.floor;
  const outcomeColour = (k) => ({ class: ACCENT, group: '#3f86c0', lineage: '#8bb6da' }[k] ?? '#9AA6AF');
  return scene(el, ({ g, width, height }, p, state) => {
    const narrow = width < 560;
    const cell = ctx.cell(state);
    const { detail, own } = ctx.detail(state);
    // Beat 1: the shortlist.
    const one = 1 - phase(p, 0.22, 0.27);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const probs = own ? detail.ensemble : null;
      const value = (i) => (probs ? probs[i] : (cell.top.find(([c]) => c === i)?.[1] ?? 0));
      const order = [...names.keys()].sort((a, b) => value(b) - value(a));
      const rowH = narrow ? 18 : 20;
      // Without room beside the bars (a phone, a narrow window), how a bar is
      // set goes under the shortlist, and fewer rows are shown.
      const explain = !narrow && width >= 760;
      const below = explain ? 0 : narrow ? 64 : 40;
      const shown = order.slice(0, Math.max(4, Math.min(narrow ? 8 : 14, Math.floor((height - 110 - below) / rowH))));
      const set = new Set(cell.candidate_set);
      const labelW = narrow ? 110 : 190;
      // On a wide figure the right side explains how each type's bar is set.
      const bw = explain ? (width - labelW) * 0.46 : width - labelW - 30;
      const grow = phase(p, 0, 0.1);
      const ticks = phase(p, 0.08, 0.16);
      text(g, 'Our cell\u2019s chances, and each type\u2019s bar to clear', 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      line(g, 12, 34, 12, 46, { colour: INK, width: 2, opacity: ticks });
      text(g, 'the type\u2019s bar', 20, 44, { size: 10.5, colour: SOFT, opacity: ticks });
      bar(g, 120, 35, 11, 11, ACCENT, 2, ticks);
      text(g, 'clears it: on the shortlist', 136, 44, { size: 10.5, colour: SOFT, opacity: ticks });
      shown.forEach((i, r) => {
        const y = 58 + r * rowH;
        const inSet = set.has(i);
        text(g, plainName(names[i]), labelW - 8, y + rowH * 0.7, { size: narrow ? 10 : 11, colour: inSet ? INK : SOFT, weight: inSet ? 600 : 400, align: 'right', max: labelW - 12 });
        bar(g, labelW, y + rowH * 0.18, bw * value(i) * grow, rowH * 0.64, inSet && ticks > 0.9 ? ACCENT : '#B9C9D6', 2);
        line(g, labelW + bw * (1 - qhat[i]), y + 1, labelW + bw * (1 - qhat[i]), y + rowH - 1, { colour: INK, width: 2, opacity: ticks });
        // The likeliest type joins a shortlist that is not empty, bar or no bar.
        if (inSet && value(i) < 1 - qhat[i] && !narrow) {
          text(g, 'joins as the likeliest type', labelW + bw * value(i) * grow + 8, y + rowH * 0.7, { size: 10, colour: ACCENT, opacity: phase(p, 0.14, 0.2), max: labelW + bw + 40 - (labelW + bw * value(i) * grow + 8) });
        }
      });
      if (explain) {
        const target = w.facts.target_coverage;
        const ex = labelW + bw + 56;
        const show = phase(p, 0.1, 0.18);
        text(g, 'How each type\u2019s bar is set', ex, 64, { size: 12, weight: 600, colour: INK, opacity: show, max: width - ex - 12 });
        paragraphs(g, [
          '1. Take example RNA cells of that type that VivOME never trained on, with most genes hidden as in a protein file.',
          '2. Note the chance VivOME gives each of them for its own type.',
          `3. Put the bar where ${isMeasured(target) ? `${Math.round(target.value * 10)} in 10` : 'most'} of them reach it (${formatRecord(target)}).`,
          { str: 'Why one bar per type: some types are harder to tell apart, so one bar for all would be too strict for some and too loose for others. Per type, the promise holds for each: on RNA test cells, the true type makes the shortlist that often. On protein files it is approximate.', tint: SOFT, sz: 10.5 },
        ], ex, 72, width - ex - 12, height - 4, { opacity: show, gap: 6, size: 11.5 });
      }
      const yS = 58 + shown.length * rowH + 20;
      const list = cell.candidate_set.map((i) => plainName(names[i]));
      if (narrow && list.length) {
        text(g, `Shortlist: ${list.length} type${list.length === 1 ? '' : 's'}`, 12, yS, { size: 11.5, colour: INK, weight: 600, opacity: ticks });
        text(g, list.join(', '), 12, yS + 16, { size: 10, colour: SOFT, opacity: ticks, max: width - 24 });
      } else {
        text(g, list.length ? `Shortlist: ${list.join(', ')}` : 'Shortlist: empty, no type clears its bar', 12, yS, { size: 11.5, colour: INK, weight: 600, opacity: ticks, max: width - 24 });
      }
      if (!own) text(g, `(chances shown for cell ${cell.id ? state.cell + 1 : ''}\u2019s top types only)`, 12, yS + 18, { size: 9.5, colour: FAINT });
      if (!explain) {
        const target = w.facts.target_coverage;
        const share = isMeasured(target) ? `${Math.round(target.value * 10)} in 10` : 'most';
        paragraphs(g, [narrow
          ? `How a bar is set: unseen RNA cells of that type, most genes hidden; the bar is where ${share} of them reach it.`
          : `How a type\u2019s bar is set: example RNA cells of that type that VivOME never trained on, most genes hidden, each get a chance for their own type; the bar sits where ${share} of them reach it.`],
        12, yS + (narrow && list.length ? 22 : 6) + (own ? 0 : 14), width - 24, height - 2, { size: narrow ? 9.5 : 10.5, opacity: phase(p, 0.1, 0.18), lead: 1.4 });
      }
      g.restore();
    }
    // Beat 2: the two checks.
    const two = phase(p, 0.22, 0.27) * (1 - phase(p, 0.47, 0.52));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      text(g, narrow ? 'Does each cell resemble an example?' : 'How closely each cell resembles its nearest example cell: one dot per cell', 12, 20,
        { size: 12, weight: 600, colour: INK, max: width - 24 });
      const withSim = cells.map((c, i) => [c, i]).filter(([c]) => c.similarity !== null && c.similarity !== undefined);
      const sims = withSim.map(([c]) => c.similarity);
      const lo = Math.min(...sims, ood) - 0.01;
      const x = (v) => 24 + ((v - lo) / (1 - lo)) * (width - 48);
      // Under the dots, at any height: why the check, and how likeness is
      // measured (shorter on a phone). The dots give up room for it.
      const f = w.facts;
      const away = cells.filter((c) => c.outcome === 'outside_supported_region').length;
      const textH = narrow ? 70 : clamp(height * 0.32, 72, 130);
      const top = 34;
      const axisY = height - textH - 26;
      const rectBottom = axisY - 14;
      const spread = Math.min(80, (rectBottom - 8 - (top + 26)) / 2);
      const mid = (top + 26 + rectBottom - 8) / 2;
      g.fillStyle = alpha(INK, 0.06);
      g.fillRect(24, top, x(ood) - 24, rectBottom - top);
      text(g, narrow ? 'too unlike: no answer' : `too unlike: no answer (the ${fc(away)} dark dots)`, 30, top + 16, { size: 10.5, colour: INK, weight: 600, max: x(ood) - 36 });
      withSim.forEach(([c, i]) => {
        const jitter = ((((i * 41) % 37) / 36) - 0.5) * 2 * spread;
        dot(g, x(c.similarity), mid + jitter, i === state.cell ? 6.5 : 3, c.outcome === 'outside_supported_region' ? INK : alpha(ACCENT, 0.55), 1, i === state.cell ? INK : null);
      });
      line(g, x(ood), top, x(ood), rectBottom + 6, { colour: INK, dash: [4, 3], width: 1.5 });
      text(g, 'less alike', 24, axisY, { size: 10.5, colour: SOFT });
      text(g, 'more alike \u2192', width - 24, axisY, { size: 10.5, colour: SOFT, align: 'right' });
      if (cell.similarity !== null && cell.similarity !== undefined) {
        // A cell turned away sits in the grey band: its tag goes low, clear of the band's label.
        chip(g, 'our cell', Math.min(x(cell.similarity) + 10, width - 90), cell.similarity < ood ? rectBottom - 12 : top + 12, { size: 10.5, colour: ACCENT, border: ACCENT });
      }
      const show = phase(p, 0.3, 0.38);
      if (narrow && textH > 0) {
        paragraphs(g, [
          'Why: chances always add up to 100%, even for a cell unlike any example. This check stops a forced answer.',
          `How: likeness to the nearest example cell on the map; the line keeps ${formatRecord(f.ood_share_above)} of ordinary cells.`,
        ], 12, axisY + 8, width - 24, height - 20, { size: 10, opacity: show, gap: 3, lead: 1.4 });
      } else if (textH > 0) {
        const colW = (width - 48) / 2;
        paragraphs(g, [{ str: 'Why this check', weight: 600, tint: INK },
          'The learners\u2019 chances always add up to 100%, even for a cell unlike anything they learned from. This check stops such a cell getting a confident-looking answer.'],
        24, axisY + 8, colW, height - 20, { opacity: show, gap: 2 });
        paragraphs(g, [{ str: 'How it is measured', weight: 600, tint: INK },
          `Likeness is how near our cell\u2019s point sits to the nearest example cell\u2019s point on the map (1 means the same place), averaged over the ${formatRecord(f.members)} learners. The line, at ${formatRecord(f.ood_threshold)}, is where ${formatRecord(f.ood_share_above)} of ordinary example cells score above it.`],
        24 + colW + 24, axisY + 8, colW, height - 20, { opacity: show, gap: 2 });
      }
      text(g, narrow ? `The other check (${fc(floor)} genes) is in Part 2, step 1.` : `The other check, enough genes measured (at least ${fc(floor)}), was shown in Part 2, step 1.`, 12, height - 8, { size: 10.5, colour: SOFT, max: width - 24 });
      g.restore();
    }
    // Beat 3: how the shortlist decides.
    const three = phase(p, 0.47, 0.52) * (1 - phase(p, 0.72, 0.77));
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, 'How the shortlist decides', 12, 20, { size: 12, weight: 600, colour: INK });
      const list = cell.candidate_set.map((i) => plainName(names[i]));
      text(g, list.length ? `Our cell\u2019s shortlist: ${list.join(', ')}` : 'Our cell\u2019s shortlist is empty', 12, 40, { size: 11, colour: SOFT, max: width - 24 });
      const top = narrow ? 52 : 62;
      const rowH = Math.min(52, (height - top - (narrow ? 44 : 78)) / RULES.length);
      const hit = phase(p, 0.55, 0.62);
      RULES.forEach(([kind, when, then], k) => {
        const y = top + k * rowH;
        const mine = cell.outcome === kind;
        g.save();
        g.globalAlpha *= mine ? 1 : lerp(1, 0.45, hit);
        bar(g, 12, y, width - 24, rowH - 8, mine && hit > 0.5 ? alpha(ACCENT, 0.12) : BENCH, 8);
        if (mine && hit > 0.5) {
          g.strokeStyle = ACCENT;
          g.lineWidth = 2;
          roundRectStroke(g, 12, y, width - 24, rowH - 8, 8);
        }
        text(g, narrow ? RULES_SHORT[k][0] : when, narrow ? 20 : 28, y + (rowH - 8) * 0.66, { size: narrow ? 10 : 12, colour: INK, max: (width - 24) * 0.48 });
        text(g, `\u2192 ${narrow ? RULES_SHORT[k][1] : then}`, width * 0.5, y + (rowH - 8) * 0.66,
          { size: narrow ? 10 : 12, colour: kind === 'class' || kind === 'group' || kind === 'lineage' ? ACCENT : INK, weight: 600, max: width * 0.5 - 16 });
        g.restore();
      });
      const yR = top + RULES.length * rowH + 16;
      const otherReason = !RULES.some(([kind]) => kind === cell.outcome);
      const result = cell.level ? ctx.answerShort(cell) : `no answer (${OUTCOME_CHIPS[cell.outcome].toLowerCase()})`;
      text(g, otherReason ? `Our cell stopped at an earlier check: ${result}` : `Our cell: ${result}`, 12, yR,
        { size: 12, colour: INK, weight: 600, opacity: hit, max: width - 24 });
      g.restore();
    }
    // Beat 4: every cell of the file, by result.
    const four = phase(p, 0.72, 0.77);
    if (four > 0) {
      g.save();
      g.globalAlpha = four;
      text(g, `Every cell in the file, by result (${fc(cells.length)} squares)`, 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const groups = OUTCOME_ORDER.map((k) => [k, cells.map((c, i) => [c, i]).filter(([c]) => c.outcome === k)]).filter(([, list]) => list.length);
      const labelW = narrow ? 104 : 230;
      // The largest squares whose rows fit above the note at the bottom.
      const fits = (sz, gap) => {
        const st = sz + (narrow ? 1.5 : 2);
        const per = Math.max(10, Math.floor((width - labelW - 24) / st));
        return 44 + groups.reduce((s, [, list]) => s + Math.max(Math.ceil(list.length / per) * st, 10) + gap, 0) <= height - 26;
      };
      const [size, gapY] = [[10, 12], [8, 10], [7, 7], [6, 6], [5, 5], [4, 4]].filter(([sz]) => !narrow || sz <= 5)
        .find(([sz, gap]) => fits(sz, gap)) ?? [4, 4];
      const step = size + (narrow ? 1.5 : 2);
      const perRow = Math.max(10, Math.floor((width - labelW - 24) / step));
      let y = 44;
      const fill = phase(p, 0.78, 0.94);
      groups.forEach(([kind, list]) => {
        const rows = Math.ceil(list.length / perRow);
        text(g, `${narrow ? OUTCOME_SHORT[kind] : OUTCOME_CHIPS[kind]}: ${fc(list.length)}`, labelW - 10, y + Math.max(size, 8), { size: narrow ? 10 : 11, colour: INK, align: 'right', max: labelW - 14 });
        list.forEach(([c, i], k) => {
          if (k / list.length > fill) return;
          const x = labelW + (k % perRow) * step;
          const yy = y + Math.floor(k / perRow) * step;
          bar(g, x, yy, size, size, outcomeColour(kind), 2);
          if (i === state.cell) {
            g.strokeStyle = INK;
            g.lineWidth = 2;
            g.strokeRect(x - 2, yy - 2, size + 4, size + 4);
          }
        });
        y += Math.max(rows * step, 10) + gapY;
      });
      text(g, narrow ? 'Blue: an answer. Grey: none. Outlined: our cell.' : 'Blues: an answer. Grey: no answer, with its reason. The outlined square is our cell.', 12, height - 8,
        { size: 10.5, colour: SOFT, opacity: fill, max: width - 24 });
      g.restore();
    }
  }, {
    describe: (state) => {
      const cell = ctx.cell(state);
      return `Cell ${state.cell + 1}: ${cell.candidate_set.length} type${cell.candidate_set.length === 1 ? '' : 's'} on its shortlist; ${ctx.answerText(cell)}.`;
    },
    table: () => buildOutcomeTable(w),
  });
}

function roundRectStroke(g, x, y, w, h, r) {
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
  g.stroke();
}

// ---- 11: where the cell lands on the map ----

// The neighbours' clues, in plain words (the response's properties).
const PROPERTY_NAMES = {
  cell_cycle_S: 'copying its DNA, ready to divide',
  oxphos: 'making energy with oxygen',
  glycolysis: 'making energy from sugar',
  antigen_presentation: 'showing signals to immune cells',
  inflammatory: 'inflammation',
  ribosome: 'making new proteins',
};

export function landing(el, ctx) {
  const w = ctx.workflow;
  const sample = w.reference.sample.map((q) => [q[0] / 1000, q[1] / 1000, q[2] / 1000, q[3]]);
  const centres = w.reference.centres;
  const cells = w.trace.cells;
  const { centre } = fitSphere(sample.map((q) => q.slice(0, 3)));
  const spread = sample.map((q) => Math.hypot(q[0] - centre[0], q[1] - centre[1], q[2] - centre[2])).sort((a, b) => a - b);
  const radius = spread[Math.floor(spread.length * 0.95)] || 1;
  const norm = (q) => [(q[0] - centre[0]) / radius, (q[1] - centre[1]) / radius, (q[2] - centre[2]) / radius];
  const ref = sample.map((q) => [...norm(q), q[3]]);
  const up = cells.map((c) => norm(c.xyz));
  const compact = window.matchMedia?.('(max-width: 820px)').matches;
  const limit = compact ? 2500 : ref.length;
  let yawDrag = 0;
  let pitchDrag = 0;
  let projectedUp = [];
  let removeDrag = () => {};
  return scene(el, ({ g, width, height }, p, state) => {
    const colourMode = ctx.options('landing').colour ?? 'class';
    const yaw = 0.6 + p * 1.2 + yawDrag;
    const pitch = 0.35 + pitchDrag;
    const cam = { width, height: height + 44, scale: Math.min(width, height - 44) * 0.55, distance: 4 };
    const showRef = phase(p, 0, 0.25);
    const drop = phase(p, 0.33, 0.6);
    const fly = phase(p, 0.66, 0.9);
    const pr = ref.slice(0, limit).map((q) => project(rotate(q, yaw, pitch), cam));
    depthOrder(pr).forEach((i) => {
      const colour = colourMode === 'class' ? ctx.classColour(ref[i][3]) : RNA;
      dot(g, pr[i].x, pr[i].y, 1.3 * pr[i].f, colour, 0.35 * showRef);
    });
    const placed = [];
    centres.forEach((c, i) => {
      if (!c || showRef < 0.9) return;
      const q = project(rotate(norm(c.map((v) => v / 1000)), yaw, pitch), cam);
      const label = short(w.class_order[i]);
      const half = label.length * 2.9 + 4;
      if (placed.some((b) => Math.abs(b.x - q.x) < b.half + half && Math.abs(b.y - q.y) < 13)) return;
      placed.push({ x: q.x, y: q.y, half });
      text(g, label, q.x, q.y, { size: 9.5, colour: INK, align: 'center', opacity: 0.8 });
    });
    projectedUp = up.map((q) => project(rotate(q, yaw, pitch), cam));
    projectedUp.forEach((q, i) => {
      if (drop <= 0 || i === state.cell) return;
      const colour = colourMode === 'class' ? (cells[i].guess === null ? '#9AA6AF' : ctx.classColour(cells[i].guess)) : PROT;
      dot(g, q.x, q.y - (1 - drop) * 60, 3, colour, 0.9 * drop, colourMode === 'class' ? '#FFFFFF' : null);
    });
    const { detail, own } = ctx.detail(state);
    const me = projectedUp[state.cell];
    if (fly > 0 && me) {
      if (own && detail.neighbours) {
        detail.neighbours.forEach((nb) => {
          const q = project(rotate(norm(nb.xyz), yaw, pitch), cam);
          line(g, me.x, me.y, lerp(me.x, q.x, fly), lerp(me.y, q.y, fly), { colour: INK, width: 0.8, opacity: 0.45 });
          dot(g, q.x, q.y, 3, ctx.classColour(nb.class), fly);
        });
      }
      dot(g, me.x, me.y - (1 - fly) * 120, 7, PROT, 1, INK);
      const label = width < 560 ? 'our cell' : `our cell: ${ctx.answerShort(ctx.cell(state))}`;
      g.save();
      g.font = `500 11px ${FONT}`;
      const cw = g.measureText(label).width + 16;
      g.restore();
      chip(g, label, clamp(me.x + 12, 8, width - cw - 8), me.y - (1 - fly) * 120 - 16, { size: 11, opacity: fly, border: ACCENT });
      const clues = phase(p, 0.8, 0.92);
      // The clues are in the results file below as well; a phone has no room for both.
      if (detail?.response && clues > 0 && width >= 560) {
        const props = Object.entries(detail.response.properties ?? {});
        const bw = Math.min(260, width * 0.42);
        const y0 = height - 16 - props.length * 18;
        g.save();
        g.globalAlpha = clues;
        bar(g, 8, y0 - 26, bw + 16, props.length * 18 + 34, 'rgba(255,255,255,0.9)', 8);
        text(g, own ? 'Clues from its neighbours (score \u00b1 spread)' : `Clues, shown for cell ${detail.cell + 1}, a cell like ours`, 16, y0 - 8, { size: 10.5, colour: INK, weight: 600, max: bw });
        props.forEach(([name, v], k) => text(g, `${PROPERTY_NAMES[name] ?? name.replace(/_/g, ' ')}: ${v.value.toFixed(2)} \u00b1 ${v.uncertainty.toFixed(2)}`,
          16, y0 + 10 + k * 18, { size: 10.5, colour: SOFT, max: bw }));
        g.restore();
      }
    }
    text(g, colourMode === 'class' ? 'Small dots: example cells, by type. Larger dots: the file\u2019s cells, by best guess.' : 'Orange: example cells (RNA). Green: the file\u2019s cells (protein).',
      12, 20, { size: 11, colour: INK, weight: 600, max: width - 24 });
    text(g, 'Drag to turn the map.', 12, 36, { size: 10.5, colour: SOFT });
  }, {
    setup: (view, api) => {
      removeDrag = onDrag(view.canvas, (dx, dy) => {
        yawDrag += dx * 0.008;
        pitchDrag = clamp(pitchDrag + dy * 0.006, -1.2, 1.2);
        api.redraw();
      });
      view.canvas.addEventListener('click', (e) => {
        const box = view.canvas.getBoundingClientRect();
        const hit = pickNearest(projectedUp, e.clientX - box.left, e.clientY - box.top, 7);
        if (hit >= 0) ctx.pick(hit);
      });
    },
    dispose: () => removeDrag(),
    describe: (state) => {
      const cell = ctx.cell(state);
      return `Cell ${state.cell + 1} lands among ${fc(w.reference.total.value)} example cells (${fc(limit)} of them drawn here).`;
    },
  });
}
