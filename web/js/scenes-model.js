// The Workflow page's scenes for the model: the encoder pass, probabilities,
// the best guess, the answer and where the cell lands. Same interface and
// rules as web/js/scenes-input.js: every value drawn is recorded in
// web/data/workflow.json, and a frame depends only on p and the cell.

import { formatCount } from './manifest.js';
import { OUTCOME_CHIPS, OUTCOME_ORDER, plainName, topK } from './workflow-data.js';
import {
  buildGuessTable, buildOutcomeTable, buildProbabilityTable,
} from './workflow-panels.js';
import {
  bandPath, clamp, depthOrder, diverging, fitSphere, lerp, phase, pickNearest, project, radialAngles, rotate, sankey,
  sequential,
} from './workflow-layout.js';
import {
  ACCENT, BENCH, FAINT, FONT, INK, LINE, PROT, RNA, SOFT, alpha, bar, chip, dot, line, mountCanvas, onDrag, short, text,
} from './scene-kit.js';

const fc = (x) => formatCount(x);
const pct = (x) => `${(x * 100).toFixed(1)}%`;

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
      const diagramH = lerp(height - 40, height * (narrow ? 0.56 : 0.62), barcode);
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
      text(g, 'the cell\u2019s address', last, 40 + H + 34, { size: 10.5, colour: PROT, align: 'center', weight: 600, opacity: squeeze });
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
        const y = diagramH + 6;
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
        if (k === anchor && t > 0.95 && !narrow) chip(g, 'also draws the map (step 11)', ex + 12, y, { size: 10, border: ACCENT, colour: ACCENT });
      });
      text(g, narrow ? 'Step 8 compares them with each type\u2019s home.' : 'Step 8 compares each of these positions with the types\u2019 homes on the map.', 12, height - 12,
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

// ---- 9: the best guess ----
// Beat 1: the top types, the first marked as the best guess. Beat 2: the
// second opinion: our cell's proteins against a type's typical levels.
// Beat 3: whether the second opinion is trusted in this file.

export function guess(el, ctx) {
  const w = ctx.workflow;
  const names = w.class_order;
  const fusion = w.trace.stages.fusion;
  const cells = w.trace.cells;
  return scene(el, ({ g, width, height }, p, state) => {
    const { detail, own } = ctx.detail(state);
    if (!detail) return;
    const narrow = width < 560;
    const gd = detail.guess;
    const one = 1 - phase(p, 0.3, 0.36);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const top = topK(gd.fused, 5);
      text(g, `Our cell\u2019s best guess: ${plainName(names[top[0]])}`, 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, 'its five likeliest types, with their chances', 12, 38, { size: 10.5, colour: SOFT });
      const labelW = narrow ? 120 : 200;
      // Room after the top bar for its value and the "best guess" tag.
      const bw = width - labelW - (narrow ? 80 : 170);
      const rowH = Math.min(46, (height - 110) / top.length);
      const grow = phase(p, 0.02, 0.14);
      top.forEach((c, r) => {
        const y = 60 + r * rowH;
        text(g, plainName(names[c]), labelW - 10, y + rowH * 0.55, { size: 11.5, colour: INK, align: 'right', weight: r === 0 ? 600 : 400, max: labelW - 14 });
        bar(g, labelW, y + rowH * 0.2, bw * gd.fused[c] / gd.fused[top[0]] * grow, rowH * 0.5, r === 0 ? ACCENT : '#AEB9C2', 3);
        text(g, pct(gd.fused[c]), labelW + bw * gd.fused[c] / gd.fused[top[0]] * grow + 6, y + rowH * 0.55, { size: 10.5, colour: INK, opacity: grow });
      });
      if (!narrow) chip(g, 'best guess', labelW + bw * grow + 52, 60 + rowH * 0.45, { size: 10.5, colour: ACCENT, border: ACCENT, opacity: phase(p, 0.12, 0.2) });
      if (!own) text(g, `(shown for cell ${detail.cell + 1}, a cell like ours)`, 12, height - 10, { size: 9.5, colour: FAINT });
      g.restore();
    }
    const two = phase(p, 0.3, 0.36) * (1 - phase(p, 0.63, 0.69));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      const sc = gd.scatter;
      const typeName = plainName(names[sc.class]);
      text(g, narrow ? `Second opinion: our cell vs a typical ${typeName}` : `Second opinion: our cell\u2019s proteins against a typical ${typeName}`, 12, 20,
        { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, narrow ? 'one dot per protein' : `one dot per protein (${fc(sc.points.length)} of the ${fc(sc.observed_proteins)} it measured)`, 12, 38, { size: 10.5, colour: SOFT, max: width - 24 });
      const box = { x: 56, y: 56, w: Math.min(width - 80, (height - 130) * 1.4), h: height - 140 };
      const xs = sc.points.map((q) => q[0]);
      const ys = sc.points.map((q) => q[1]);
      const [ax0, ax1, ay0, ay1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      g.strokeStyle = LINE;
      g.strokeRect(box.x, box.y, box.w, box.h);
      const appear = phase(p, 0.36, 0.5);
      sc.points.forEach((q, k) => {
        if (k / sc.points.length > appear) return;
        dot(g, box.x + ((q[0] - ax0) / (ax1 - ax0 || 1)) * box.w, box.y + box.h - ((q[1] - ay0) / (ay1 - ay0 || 1)) * box.h, 2.4, PROT, 0.6);
      });
      text(g, 'our cell: less \u2192 more', box.x + box.w, box.y + box.h + 16, { size: 10.5, colour: INK, align: 'right' });
      g.save();
      g.translate(box.x - 12, box.y + box.h);
      g.rotate(-Math.PI / 2);
      text(g, `typical ${typeName}: less \u2192 more`, 0, 0, { size: 10.5, colour: INK, max: box.h });
      g.restore();
      const verdict = phase(p, 0.5, 0.58);
      text(g, narrow ? `Match score ${sc.r.toFixed(2)} (1: perfect, 0: none)` : `Match score ${sc.r.toFixed(2)}: 1 would mean they rise and fall together perfectly, 0 not at all.`, 12, box.y + box.h + 40,
        { size: 10.5, colour: SOFT, opacity: verdict, max: width - 24 });
      const corrTop = topK(gd.correlation_probability, 3).map((c) => plainName(names[c]));
      text(g, narrow ? `Its top type: ${corrTop[0]}` : `The second opinion\u2019s top types: ${corrTop.join(', ')}`, 12, box.y + box.h + 58, { size: 10.5, colour: INK, opacity: verdict, max: width - 24 });
      g.restore();
    }
    const three = phase(p, 0.63, 0.69);
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      const counted = cells.filter((c) => c.counted);
      text(g, 'Can the second opinion be trusted in this file?', 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, narrow ? 'one dot per cell; blue: it agrees with the learners' : 'one dot per cell; blue: the second opinion picks the same type as the learners', 12, 38,
        { size: 10.5, colour: SOFT, max: width - 24 });
      const fill = phase(p, 0.68, 0.84);
      const bw = width - 24;
      const per = Math.ceil(counted.length / 8);
      const dw = bw / per;
      const gap = narrow ? 10 : 15;
      counted.forEach((c, k) => {
        if (k / counted.length > fill) return;
        dot(g, 12 + (k % per) * dw + dw / 2, 58 + Math.floor(k / per) * gap, Math.min(4.5, dw * 0.38), c.agrees ? ACCENT : '#C9D1D7');
      });
      const by = 58 + 8 * gap + (narrow ? 14 : 26);
      bar(g, 12, by, bw, 16, BENCH, 8);
      bar(g, 12, by, bw * fusion.agreement * fill, 16, ACCENT, 8, 0.85);
      line(g, 12 + bw * fusion.threshold, by - 10, 12 + bw * fusion.threshold, by + 26, { colour: INK, width: 2 });
      text(g, `needed: ${pct(fusion.threshold)}`, 12 + bw * fusion.threshold + 6, by - 4, { size: 11, colour: INK, weight: 600 });
      text(g, `agrees: ${pct(fusion.agreement)} (${fc(fusion.agreeing)} of ${fc(fusion.counted)} cells)`, 12, by + (narrow ? 34 : 44), { size: 11, colour: ACCENT, weight: 600, opacity: fill });
      const used = fusion.correlation_term === 'used';
      text(g, used ? (narrow ? 'Above the line: it is used.' : 'Above the line: in this file the second opinion is trusted and mixed in.')
        : (narrow ? 'Below the line: set aside in this file.' : 'Below the line: in this file the second opinion is set aside, and the best guess is the learners\u2019.'),
      12, by + (narrow ? 52 : 66), { size: 11, colour: SOFT, opacity: phase(p, 0.84, 0.92), max: width - 24 });
      g.restore();
    }
  }, {
    describe: (state) => {
      const { detail } = ctx.detail(state);
      const c = topK(detail.guess.fused, 1)[0];
      return `Best guess ${plainName(names[c])} (${pct(detail.guess.fused[c])}); the second opinion agrees with the learners on ${pct(fusion.agreement)} of cells against ${pct(fusion.threshold)} needed, so it is ${fusion.correlation_term === 'used' ? 'used' : 'set aside'} here.`;
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
      const shown = order.slice(0, Math.max(4, Math.min(narrow ? 8 : 14, Math.floor((height - 110) / rowH))));
      const set = new Set(cell.candidate_set);
      const labelW = narrow ? 110 : 190;
      const bw = width - labelW - 30;
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
          text(g, 'joins as the likeliest type', labelW + bw * value(i) * grow + 8, y + rowH * 0.7, { size: 10, colour: ACCENT, opacity: phase(p, 0.14, 0.2) });
        }
      });
      const yS = 58 + shown.length * rowH + 20;
      const list = cell.candidate_set.map((i) => plainName(names[i]));
      if (narrow && list.length) {
        text(g, `Shortlist: ${list.length} type${list.length === 1 ? '' : 's'}`, 12, yS, { size: 11.5, colour: INK, weight: 600, opacity: ticks });
        text(g, list.join(', '), 12, yS + 16, { size: 10, colour: SOFT, opacity: ticks, max: width - 24 });
      } else {
        text(g, list.length ? `Shortlist: ${list.join(', ')}` : 'Shortlist: empty, no type clears its bar', 12, yS, { size: 11.5, colour: INK, weight: 600, opacity: ticks, max: width - 24 });
      }
      if (!own) text(g, `(chances shown for cell ${cell.id ? state.cell + 1 : ''}\u2019s top types only)`, 12, yS + 18, { size: 9.5, colour: FAINT });
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
      const mid = height * 0.5;
      const spread = Math.min(80, height * 0.2);
      g.fillStyle = alpha(INK, 0.06);
      g.fillRect(24, mid - spread - 30, x(ood) - 24, spread * 2 + 50);
      text(g, 'too unlike: no answer', 30, mid - spread - 14, { size: 10.5, colour: INK, weight: 600 });
      withSim.forEach(([c, i]) => {
        const jitter = ((((i * 41) % 37) / 36) - 0.5) * 2 * spread;
        dot(g, x(c.similarity), mid + jitter, i === state.cell ? 6.5 : 3, c.outcome === 'outside_supported_region' ? INK : alpha(ACCENT, 0.55), 1, i === state.cell ? INK : null);
      });
      line(g, x(ood), mid - spread - 30, x(ood), mid + spread + 20, { colour: INK, dash: [4, 3], width: 1.5 });
      const axisY = mid + spread + 34;
      text(g, 'less alike', 24, axisY, { size: 10.5, colour: SOFT });
      text(g, 'more alike \u2192', width - 24, axisY, { size: 10.5, colour: SOFT, align: 'right' });
      if (cell.similarity !== null && cell.similarity !== undefined) {
        chip(g, 'our cell', Math.min(x(cell.similarity) + 10, width - 90), mid - spread - 14, { size: 10.5, colour: ACCENT, border: ACCENT });
      }
      text(g, narrow ? `The other check (${fc(floor)} genes) is in step 5.` : `The other check, enough genes measured (at least ${fc(floor)}), was shown in step 5.`, 12, height - 12, { size: 10.5, colour: SOFT, max: width - 24 });
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
      const size = narrow ? 5 : 10;
      const step = narrow ? 6.5 : size + 2;
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
        y += Math.max(rows * step, 10) + (narrow ? 8 : 12);
      });
      text(g, narrow ? 'Blue: an answer. Grey: none. Outlined: our cell.' : 'Blues: an answer. Grey: no answer, with its reason. The outlined square is our cell.', 12, height - 12,
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
