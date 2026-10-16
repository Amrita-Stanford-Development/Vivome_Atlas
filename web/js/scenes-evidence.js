// The Workflow page's scenes for the evidence: how the encoders were trained,
// and how the results were calculated, with the live service at the end.
// Same interface and rules as web/js/scenes-input.js. The mechanism pictures
// (a training batch, the four forces, a bootstrap draw) are illustrations
// with no numbers and say so; every number drawn is a recorded one.

import { isMeasured } from './manifest.js';
import { formatRecord } from './workflow-data.js';
import { buildScenarioTable } from './workflow-panels.js';
import { clamp, lerp, phase } from './workflow-layout.js';
import { rng } from './random.js';
import {
  ACCENT, BENCH, FAINT, INK, LINE, PROT, RNA, SOFT, alpha, bar, chip, dot, line, mountCanvas, roundRect, text,
} from './scene-kit.js';

function scene(el, draw, { describe = () => '', table = () => '' } = {}) {
  const view = mountCanvas(el);
  let last = null;
  const api = {
    render(p, state) { last = [p, state]; view.clear(); draw(view, clamp(p, 0, 1), state); },
    resize() { view.resize(); if (last) api.render(...last); },
    dispose() { view.dispose(); },
    describe,
    table,
  };
  return api;
}

const box = (g, x, y, w, h, label, { colour = INK, fill = '#FFFFFF', opacity = 1, size = 11.5 } = {}) => {
  g.save();
  g.globalAlpha *= opacity;
  g.fillStyle = fill;
  roundRect(g, x, y, w, h, 10);
  g.fill();
  g.strokeStyle = colour;
  g.lineWidth = 1.5;
  g.stroke();
  g.restore();
  text(g, label, x + w / 2, y + h / 2 + 4, { size, colour, align: 'center', opacity, max: w - 10 });
};

// ---- 4: how VivOME learns ----
// Beat 1: the example cells, scattered at first, pull together by type over
// the training rounds; the end is the real map (the start and the path are
// drawn, and say so). Beat 2: practising with gaps, and mixes like real
// files. Beat 3: five learners, averaged. Beat 4: the three designs compared,
// and the training repeated here.

const DESIGNS = { // the designs' names, in plain words
  'H module, uniform': 'Groups of genes, random gaps',
  'F2 module, profile': 'Groups of genes, gaps like real files',
  'C mask channel, uniform': 'Genes one by one, random gaps',
};

export function training(el, ctx) {
  const w = ctx.workflow;
  const t = w.training;
  const classes = w.reference.classes;
  const counts = classes.map((c) => c.cells.value);
  const epochs = t.recipe.epochs.value;
  const pts = w.reference.sample.slice(0, 900);
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const r0 = rng(31);
  const start = pts.map(() => [r0(), r0()]);
  const fit = (bw, bh, ox, oy) => {
    const s = Math.min(bw / (x1 - x0), bh / (y1 - y0));
    return (q) => [ox + (bw - (x1 - x0) * s) / 2 + (q[0] - x0) * s, oy + (bh - (y1 - y0) * s) / 2 + (y1 - q[1]) * s];
  };
  return scene(el, ({ g, width, height }, p) => {
    // Beat 1: learning by example.
    const one = 1 - phase(p, 0.23, 0.28);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const learn = phase(p, 0.03, 0.21);
      const round = Math.max(1, Math.round(epochs * learn));
      text(g, 'Learning by example', 12, 22, { size: 12, weight: 600, colour: INK });
      chip(g, `round ${round} of up to ${epochs}`, width - 12, 20, { size: 11, align: 'right', border: ACCENT, colour: ACCENT });
      const map = fit(width - 24, height - 92, 12, 40);
      pts.forEach((q, i) => {
        const [mx, my] = map(q);
        const sx = 12 + start[i][0] * (width - 24);
        const sy = 40 + start[i][1] * (height - 92);
        const e = learn * learn * (3 - 2 * learn);
        dot(g, lerp(sx, mx, e), lerp(sy, my, e), 2.2, ctx.classColour(q[3]), 0.8);
      });
      text(g, 'Each dot is an example cell, coloured by its type. The end is the real map from step 1;', 12, height - 44, { size: 10, colour: FAINT, max: width - 24 });
      text(g, 'the scattered start and the path in between are drawn to show the idea.', 12, height - 30, { size: 10, colour: FAINT, max: width - 24 });
      text(g, 'No protein labels: only the named RNA examples.', 12, height - 14, { size: 10, colour: RNA, max: width - 24 });
      g.restore();
    }

    // Beat 2: practising with gaps, in mixes like real files.
    const two = phase(p, 0.23, 0.28) * (1 - phase(p, 0.48, 0.53));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      const r = rng(7);
      const genes = 64;
      const bw = width - 24;
      const gw = bw / genes;
      const lo = t.recipe.coverage_low.value;
      const hi = t.recipe.coverage_high.value;
      text(g, 'Practising with gaps', 12, 22, { size: 12, weight: 600, colour: INK });
      text(g, 'One example cell\u2019s genes, as the learner sees them in practice:', 12, 46, { size: 10.5, colour: SOFT, max: bw });
      const hide = phase(p, 0.28, 0.38);
      [lo, (lo + hi) / 2, hi].forEach((keep, v) => {
        const y = 58 + v * 46;
        for (let k = 0; k < genes; k += 1) {
          const shown = hide === 0 || r() < keep;
          bar(g, 12 + k * gw, y, gw - 1, 26, shown ? alpha(ACCENT, 0.5 + 0.4 * ((k * 13) % 7) / 7) : '#E3E7EB', 1);
        }
        text(g, `${Math.round(keep * 100)}% shown`, 12 + bw, y + 40, { size: 10, colour: FAINT, align: 'right', opacity: hide });
      });
      const mixY = 58 + 3 * 46 + 22;
      const kSel = Number(ctx.options('training').classes ?? 0);
      const rm = rng(7 + kSel);
      const total = counts.reduce((s, v) => s + v, 0);
      text(g, 'Cells come in mixes like real files:', 12, mixY, { size: 10.5, colour: SOFT });
      text(g, 'the natural mix', 12, mixY + 22, { size: 10, colour: INK });
      let x = 110;
      counts.forEach((v, i) => { bar(g, x, mixY + 10, (v / total) * (bw - 98), 16, ctx.classColour(i), 0); x += (v / total) * (bw - 98); });
      text(g, kSel === 0 ? 'or one mix of 1 to 8 kinds' : `or ${kSel} kind${kSel === 1 ? '' : 's'} only`, 12, mixY + 52, { size: 10, colour: INK });
      const mix = phase(p, 0.36, 0.46);
      if (kSel > 0) {
        const order = [...classes.keys()];
        for (let k = order.length - 1; k > 0; k -= 1) { const j = Math.floor(rm() * (k + 1)); [order[k], order[j]] = [order[j], order[k]]; }
        const picked = order.slice(0, kSel);
        const weights = picked.map(() => -Math.log(1 - rm() * 0.999));
        const sum = weights.reduce((s, v) => s + v, 0);
        x = 110;
        picked.forEach((i, k) => { const wd = (weights[k] / sum) * (bw - 98) * mix; bar(g, x, mixY + 40, wd, 16, ctx.classColour(i), 0); x += wd; });
      } else {
        text(g, '(pick a mix with the buttons below)', 12, mixY + 68, { size: 10, colour: FAINT, opacity: mix });
      }
      text(g, 'Gaps and mixes are drawn at random, as in training.', 12, height - 12, { size: 10, colour: FAINT, max: bw });
      g.restore();
    }

    // Beat 3: five learners, averaged.
    const three = phase(p, 0.48, 0.53) * (1 - phase(p, 0.73, 0.78));
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, `${t.members.length} learners instead of one`, 12, 22, { size: 12, weight: 600, colour: INK });
      const n = t.members.length;
      const gap = 10;
      const cw = (width - 24 - gap * (n - 1)) / n;
      const ch = Math.min(cw * 1.7, height * 0.52);
      t.members.forEach((m, k) => {
        const x = 12 + k * (cw + gap);
        const y = 42;
        const appear = clamp(phase(p, 0.52, 0.62) * n - k, 0, 1);
        g.globalAlpha = three * appear;
        g.fillStyle = '#FFFFFF';
        roundRect(g, x, y, cw, ch, 10);
        g.fill();
        g.strokeStyle = LINE;
        g.stroke();
        // Each learner's map differs a little: drawn here as a small turn of the same map.
        const turn = (k - (n - 1) / 2) * 0.12;
        const map = fit(cw - 16, ch - 34, x + 8, y + 8);
        const [mx, my] = [x + cw / 2, y + (ch - 26) / 2 + 8];
        pts.slice(0, 300).forEach((q) => {
          const [px, py] = map(q);
          const [dx, dy] = [px - mx, py - my];
          dot(g, mx + dx * Math.cos(turn) - dy * Math.sin(turn), my + dx * Math.sin(turn) + dy * Math.cos(turn), 1.3, ctx.classColour(q[3]), 0.75);
        });
        text(g, `learner ${k + 1}`, x + cw / 2, y + ch - 10, { size: 10.5, colour: INK, align: 'center' });
        g.globalAlpha = three;
      });
      const avg = phase(p, 0.62, 0.7);
      const ay = 42 + ch + 50;
      t.members.forEach((m, k) => {
        const x = 12 + k * (cw + gap) + cw / 2;
        line(g, x, 42 + ch + 4, lerp(x, width / 2, avg), lerp(42 + ch + 4, ay - 8, avg), { colour: ACCENT, width: 1.4, opacity: avg });
      });
      if (avg > 0) {
        chip(g, 'their views are averaged into one (step 9)', width / 2, ay + 6, { size: 12, align: 'center', border: ACCENT, colour: ACCENT, opacity: avg });
        text(g, 'Same training, different random starts; the small differences between the maps are drawn to show the idea.', width / 2, ay + 44,
          { size: 10, colour: FAINT, align: 'center', opacity: avg, max: width - 24 });
      }
      g.restore();
    }

    // Beat 4: the designs compared, and the training repeated.
    const four = phase(p, 0.76, 0.82);
    if (four > 0) {
      g.save();
      g.globalAlpha = four;
      const cands = t.encoder_choice.candidates;
      text(g, `Three designs, each trained ${formatRecord(t.encoder_choice.seeds)} times: test cells named correctly`, 12, 22, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, 'with most genes hidden; every type counted equally; the line shows the spread over the repeats', 12, 40, { size: 10, colour: FAINT, max: width - 24 });
      const labelW = Math.min(250, width * 0.42);
      const bw = width - labelW - 70;
      const grow = phase(p, 0.8, 0.9);
      cands.forEach((c, k) => {
        const y = 66 + k * 46;
        const v = c.balanced_accuracy.value;
        const sd = c.seed_sd.value;
        const chosen = k === 0;
        text(g, DESIGNS[c.name] ?? c.name, labelW, y + 14, { size: 11, align: 'right', colour: chosen ? ACCENT : INK, weight: chosen ? 600 : 400, max: labelW - 8 });
        bar(g, labelW + 10, y, bw * v * grow, 22, chosen ? ACCENT : '#AEB9C2', 3);
        line(g, labelW + 10 + bw * (v - sd) * grow, y + 11, labelW + 10 + bw * (v + sd) * grow, y + 11, { colour: INK, width: 1.4, opacity: grow });
        text(g, formatRecord(c.balanced_accuracy), labelW + 16 + bw * (v + sd) * grow, y + 15, { size: 11, colour: INK, opacity: grow });
      });
      if (cands[0]) text(g, 'chosen', labelW + 12, 66 + 34, { size: 9.5, colour: ACCENT });
      const yR = 66 + cands.length * 46 + 34;
      const again = phase(p, 0.88, 0.96);
      text(g, `The training repeated on this PC (learner ${t.reproduction.seed + 1} of ${t.members.length}):`, 12, yR, { size: 11.5, weight: 600, colour: INK, opacity: again });
      const rec = t.reproduction.recorded_loss.value;
      const ret = t.reproduction.retrained_loss.value;
      const maxE = Math.max(rec, ret) * 1.15;
      [['original', rec, '#AEB9C2'], ['trained again here', ret, ACCENT]].forEach(([label, v, colour], k) => {
        const y = yR + 14 + k * 30;
        text(g, label, labelW, y + 14, { size: 11, align: 'right', colour: INK, opacity: again });
        bar(g, labelW + 10, y, bw * (v / maxE) * again, 20, colour, 3);
        text(g, `error ${v.toFixed(3)}`, labelW + 16 + bw * (v / maxE) * again, y + 14, { size: 10.5, colour: INK, opacity: again });
      });
      text(g, t.reproduction.passed ? 'Within the limit set before the run: the training can be repeated.' : 'Outside the limit set before the run.',
        12, yR + 88, { size: 10.5, colour: SOFT, opacity: again, max: width - 24 });
      g.restore();
    }
  }, {
    describe: () => `${t.members.length} learners, each trained on the named RNA examples alone, up to ${epochs} rounds, with most genes hidden in practice.`,
  });
}

// ---- 13: how the results were calculated, and new data today ----

export function results(el, ctx) {
  const w = ctx.workflow;
  const m = ctx.manifest;
  const scenarios = w.evaluation.scenarios;
  const heldout = w.evaluation.heldout;
  const fulcher = (m?.benchmark?.datasets ?? []).find((d) => d.key === 'fulcher2026');
  const svc = w.service;
  return scene(el, ({ g, width, height }, p) => {
    const one = 1 - phase(p, 0.23, 0.28);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      text(g, 'Simulated uploads of held-out RNA cells, by kind', 12, 18, { size: 11.5, colour: INK, weight: 600 });
      const rowH = (height - 60) / scenarios.length;
      const bw = width - 150;
      const grow = phase(p, 0, 0.18);
      scenarios.forEach((s, k) => {
        const y = 34 + k * rowH;
        text(g, s.group, 120, y + rowH * 0.45, { size: 11, align: 'right', colour: INK });
        bar(g, 128, y + 4, bw * s.committed.value * grow, rowH * 0.3, '#B9C9D6', 2);
        bar(g, 128, y + 6 + rowH * 0.3, bw * s.correct_when_committed.value * grow, rowH * 0.3, ACCENT, 2);
        text(g, `${formatRecord(s.committed)} answered, ${formatRecord(s.correct_when_committed)} right`, 132 + bw * s.committed.value * grow, y + 4 + rowH * 0.25, { size: 9.5, colour: FAINT, opacity: grow });
      });
      g.restore();
    }
    const two = phase(p, 0.23, 0.28) * (1 - phase(p, 0.48, 0.53));
    if (two > 0 && fulcher) {
      g.save();
      g.globalAlpha = two;
      const rows = fulcher.rows.filter((r) => isMeasured(r.score)).slice(0, 12);
      const lo = 0;
      const hi = 1;
      const left = Math.min(260, width * 0.44);
      const x = (v) => left + ((v - lo) / (hi - lo)) * (width - left - 16);
      const rowH = Math.min(24, (height - 70) / rows.length);
      text(g, `Fulcher 2026, balanced accuracy over its types (in-sample for VivOME)`, 12, 18, { size: 11.5, colour: INK, weight: 600, max: width - 24 });
      const show = phase(p, 0.28, 0.42);
      rows.forEach((r, k) => {
        if (k / rows.length > show) return;
        const y = 40 + k * rowH;
        text(g, `${r.method}, ${r.rule}`, left - 8, y + 4, { size: 10, align: 'right', colour: r.ours ? INK : SOFT, weight: r.ours ? 600 : 400, max: left - 12 });
        if (Number.isFinite(r.score.sd)) line(g, x(r.score.value - r.score.sd), y, x(r.score.value + r.score.sd), y, { colour: INK });
        dot(g, x(r.score.value), y, r.ours ? 6 : 4, r.ours ? ACCENT : '#9AA6AF');
      });
      [0, 0.25, 0.5, 0.75, 1].forEach((v) => text(g, `${v * 100}%`, x(v), 48 + rows.length * rowH, { size: 9.5, colour: FAINT, align: 'center' }));
      if (isMeasured(fulcher.chance)) {
        line(g, x(fulcher.chance.value), 30, x(fulcher.chance.value), 40 + rows.length * rowH, { colour: FAINT, dash: [3, 3] });
        text(g, 'chance', x(fulcher.chance.value) + 4, 34, { size: 9.5, colour: FAINT });
      }
      // A paired bootstrap, in miniature: resample cells, rescore both.
      const boot = phase(p, 0.42, 0.5);
      if (boot > 0) {
        const r = rng(Math.floor(p * 40));
        const y = height - 26;
        text(g, 'Paired bootstrap: draw cells with replacement, score both methods on the same draw (illustration)', 12, y - 14, { size: 10, colour: FAINT, max: width - 24 });
        for (let k = 0; k < 40; k += 1) dot(g, 16 + k * ((width - 32) / 40), y, 3.5, r() < 0.5 ? ACCENT : '#9AA6AF', boot);
      }
      g.restore();
    }
    const three = phase(p, 0.48, 0.53) * (1 - phase(p, 0.73, 0.78));
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, 'The internal held-out test: six sets, scored once', 12, 18, { size: 11.5, colour: INK, weight: 600 });
      const cols = width > 640 ? 3 : 2;
      const cw = (width - 24) / cols;
      const ch = (height - 40) / Math.ceil(heldout.length / cols);
      heldout.forEach((c, k) => {
        const x = 12 + (k % cols) * cw;
        const y = 30 + Math.floor(k / cols) * ch;
        const a = clamp(phase(p, 0.5, 0.7) * heldout.length - k, 0, 1);
        g.globalAlpha = three * a;
        g.fillStyle = '#FFFFFF';
        roundRect(g, x + 4, y + 4, cw - 8, ch - 8, 12);
        g.fill();
        g.globalAlpha = three;
        chip(g, c.result, x + 12, y + 20, { size: 10.5, opacity: a, border: c.result === 'pass' ? ACCENT : c.result === 'fail' ? INK : LINE });
        text(g, c.key.toUpperCase().replace('HAO2021', 'Hao 2021').replace('TIAN', 'Tian'), x + 70, y + 24, { size: 11, colour: INK, weight: 600, opacity: a });
        text(g, c.question, x + 12, y + 44, { size: 9.5, colour: SOFT, opacity: a, max: cw - 24 });
        if (c.curve) {
          const s = Math.min(ch - 70, cw - 30);
          const ox = x + 12;
          const oy = y + 56;
          line(g, ox, oy + s, ox + s, oy, { colour: LINE, dash: [3, 3], opacity: a });
          g.strokeStyle = ACCENT;
          g.lineWidth = 2;
          g.globalAlpha = three * a;
          g.beginPath();
          c.curve.forEach(([fx, ty], i) => { const px = ox + fx * s; const py = oy + s - ty * s; if (i === 0) g.moveTo(px, py); else g.lineTo(px, py); });
          g.stroke();
          g.globalAlpha = three;
          text(g, `AUROC ${formatRecord(c.value)}`, ox + s + 8, oy + s - 4, { size: 10.5, colour: INK, opacity: a });
        } else if (c.value) {
          text(g, `${formatRecord(c.value)} points over correlation`, x + 12, y + 72, { size: 11, colour: INK, opacity: a });
          text(g, `lower bound ${formatRecord(c.lower)}`, x + 12, y + 90, { size: 10, colour: FAINT, opacity: a });
        } else {
          text(g, c.reason, x + 12, y + 72, { size: 10, colour: FAINT, opacity: a, max: cw - 24 });
        }
      });
      g.restore();
    }
    const four = phase(p, 0.76, 0.82);
    if (four > 0) {
      g.save();
      g.globalAlpha = four;
      const y = height * 0.42;
      const bw = Math.min(170, width * 0.26);
      box(g, 12, y, bw, 64, 'your browser', { colour: INK });
      box(g, width - bw - 12, y, bw, 64, `${svc.platform}`, { colour: ACCENT });
      text(g, `${formatRecord(svc.cpu)} vCPU, ${svc.memory}, ${formatRecord(svc.min_instances)} to ${formatRecord(svc.max_instances)} instance`, width - bw / 2 - 12, y + 84, { size: 10, colour: FAINT, align: 'center', max: bw + 20 });
      const x0 = 12 + bw;
      const x1 = width - bw - 12;
      line(g, x0, y + 20, x1, y + 20, { colour: INK, width: 1.5 });
      line(g, x1, y + 44, x0, y + 44, { colour: ACCENT, width: 1.5 });
      text(g, 'POST /api/project: the file', (x0 + x1) / 2, y + 12, { size: 10.5, colour: INK, align: 'center' });
      text(g, 'JSON: one answer per cell', (x0 + x1) / 2, y + 62, { size: 10.5, colour: ACCENT, align: 'center' });
      const t = phase(p, 0.8, 1);
      if (t < 0.5) dot(g, lerp(x0, x1, t * 2), y + 20, 6, PROT);
      else dot(g, lerp(x1, x0, (t - 0.5) * 2), y + 44, 6, ACCENT);
      const steps = ['read', 'scale', 'merge', 'match', 'smooth', 'encode', 'probabilities', 'best guess', 'set', 'ladder', 'atlas'];
      let sx = 12;
      let sy = y + 112;
      text(g, 'Inside the service, every step on this page:', 12, sy - 18, { size: 10.5, colour: FAINT });
      steps.forEach((s, k) => {
        const on = t > 0.15 + (k / steps.length) * 0.35;
        const wChip = s.length * 6.4 + 18;
        if (sx + wChip > width - 12) { sx = 12; sy += 28; }
        chip(g, s, sx, sy, { size: 10.5, opacity: on ? 1 : 0.35, colour: on ? INK : FAINT, border: on ? ACCENT : null });
        sx += wChip + 6;
      });
      text(g, `Up to ${formatRecord(svc.max_cells)} cells per upload; it sleeps when idle and wakes for the next file`, 12, height - 10, { size: 10.5, colour: SOFT, max: width - 24 });
      g.restore();
    }
  }, {
    describe: () => `Six kinds of simulated upload, the Fulcher 2026 benchmark, the six held-out sets, and the live service on ${svc.platform}.`,
    table: () => buildScenarioTable(w),
  });
}
