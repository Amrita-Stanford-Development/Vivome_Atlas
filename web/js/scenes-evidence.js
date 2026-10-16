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

// ---- 4: trained on RNA only ----

export function training(el, ctx) {
  const w = ctx.workflow;
  const t = w.training;
  const classes = w.reference.classes;
  const counts = classes.map((c) => c.cells.value);
  return scene(el, ({ g, width, height }, p) => {
    const one = 1 - phase(p, 0.23, 0.28);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const appear = phase(p, 0, 0.18);
      box(g, 12, height * 0.3, width * 0.26, 56, 'RNA reference, labelled', { colour: RNA });
      box(g, 12, height * 0.62, width * 0.26, 56, 'protein labels: not used', { colour: '#9AA6AF', fill: BENCH });
      const members = t.members;
      members.forEach((m, k) => {
        const y = 30 + k * ((height - 60) / members.length);
        const x = width * 0.62;
        const a = clamp(appear * members.length - k, 0, 1);
        line(g, 12 + width * 0.26, height * 0.3 + 28, lerp(12 + width * 0.26, x, a), y + 20, { colour: RNA, opacity: 0.5 });
        box(g, x, y, width * 0.34, 40, `encoder, seed ${k}`, { colour: ACCENT, opacity: a });
      });
      g.restore();
    }
    const two = phase(p, 0.23, 0.28) * (1 - phase(p, 0.48, 0.53));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      const kSel = Number(ctx.options('training').classes ?? 0);
      const r = rng(7 + kSel);
      const total = counts.reduce((s, v) => s + v, 0);
      const bw = width - 24;
      text(g, 'The reference’s natural mix', 12, 18, { size: 11, colour: INK, weight: 600 });
      let x = 12;
      counts.forEach((v, i) => { bar(g, x, 26, (v / total) * bw, 18, ctx.classColour(i), 0); x += (v / total) * bw; });
      const label = kSel === 0 ? 'A batch kept natural' : `A batch of ${kSel} type${kSel === 1 ? '' : 's'}, random proportions`;
      text(g, `${label} (illustration)`, 12, 70, { size: 11, colour: INK, weight: 600 });
      let parts;
      if (kSel === 0) parts = counts.map((v, i) => [i, v / total]);
      else {
        const order = [...classes.keys()];
        for (let k = order.length - 1; k > 0; k -= 1) { const j = Math.floor(r() * (k + 1)); [order[k], order[j]] = [order[j], order[k]]; }
        const picked = order.slice(0, kSel);
        const weights = picked.map(() => -Math.log(1 - r() * 0.999));
        const sum = weights.reduce((s, v) => s + v, 0);
        parts = picked.map((i, k) => [i, weights[k] / sum]);
      }
      x = 12;
      parts.forEach(([i, share]) => { bar(g, x, 78, share * bw * phase(p, 0.28, 0.36), 18, ctx.classColour(i), 0); x += share * bw * phase(p, 0.28, 0.36); });
      // Two masked views of one cell's genes.
      const genes = 96;
      const lo = t.recipe.coverage_low.value;
      const hi = t.recipe.coverage_high.value;
      const views = [lo + (hi - lo) * r(), lo + (hi - lo) * r()];
      const gw = bw / genes;
      text(g, `Two masked views: each keeps a random ${formatRecord(t.recipe.coverage_low)} to ${formatRecord(t.recipe.coverage_high)} of genes (illustration)`, 12, 128, { size: 11, colour: INK, weight: 600, max: bw });
      const mask = phase(p, 0.36, 0.46);
      views.forEach((keep, v) => {
        const y = 148 + v * 64;
        text(g, `view ${v + 1}: about ${Math.round(keep * 100)}% kept`, 12, y - 4, { size: 10, colour: FAINT });
        for (let k = 0; k < genes; k += 1) {
          const kept = r() < keep || mask === 0;
          bar(g, 12 + k * gw, y + 2, gw - 1, 36, kept ? alpha(ACCENT, 0.45 + 0.45 * ((k * 13) % 7) / 7) : '#E3E7EB', 1);
        }
      });
      g.restore();
    }
    const three = phase(p, 0.48, 0.53) * (1 - phase(p, 0.73, 0.78));
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      const s = phase(p, 0.52, 0.72);
      const cx = width / 2;
      const cy = height / 2 + 6;
      const R = Math.min(width, height) * 0.32;
      const r = rng(11);
      const groups = [[0, ctx.classColour(2)], [2.1, ctx.classColour(15)], [4.2, ctx.classColour(12)]];
      groups.forEach(([angle, colour]) => {
        const tx = cx + Math.cos(angle) * R * 0.7;
        const ty = cy + Math.sin(angle) * R * 0.7;
        for (let k = 0; k < 14; k += 1) {
          const sx = cx + (r() - 0.5) * R * 1.8;
          const sy = cy + (r() - 0.5) * R * 1.8;
          const jx = (r() - 0.5) * 22;
          const jy = (r() - 0.5) * 22;
          dot(g, lerp(sx, tx + jx, s), lerp(sy, ty + jy, s), 4, colour, 0.85);
        }
      });
      text(g, 'Four forces (illustration, no data)', 12, 18, { size: 11.5, colour: INK, weight: 600 });
      ['each cell toward its type', 'cells of a type together', 'no point everyone’s neighbour', 'a cell’s two views together']
        .forEach((f, k) => chip(g, f, 12, 44 + k * 28, { size: 10.5, opacity: clamp(s * 4 - k, 0, 1) }));
      g.restore();
    }
    const four = phase(p, 0.76, 0.82);
    if (four > 0) {
      g.save();
      g.globalAlpha = four;
      const cands = t.encoder_choice.candidates;
      const bw = width - 230;
      const vals = cands.map((c) => c.balanced_accuracy.value);
      const lo = Math.min(...vals.map((v, k) => v - cands[k].seed_sd.value)) - 0.02;
      const hi = Math.max(...vals.map((v, k) => v + cands[k].seed_sd.value)) + 0.02;
      const x = (v) => 220 + ((v - lo) / (hi - lo)) * bw;
      text(g, `The encoder choice: balanced accuracy over ${formatRecord(t.encoder_choice.seeds)} seeds, ± 1 SD`, 12, 18, { size: 11.5, colour: INK, weight: 600, max: width - 24 });
      cands.forEach((c, k) => {
        const y = 50 + k * 40;
        text(g, c.name, 210, y + 4, { size: 11, align: 'right', colour: INK, max: 200 });
        line(g, x(c.balanced_accuracy.value - c.seed_sd.value), y, x(c.balanced_accuracy.value + c.seed_sd.value), y, { colour: INK, width: 1.5 });
        dot(g, x(c.balanced_accuracy.value), y, 6, k === 0 ? ACCENT : '#9AA6AF');
        text(g, formatRecord(c.balanced_accuracy), x(c.balanced_accuracy.value), y - 10, { size: 10, colour: FAINT, align: 'center' });
      });
      const y = 50 + cands.length * 40 + 20;
      text(g, `Reproduced: seed ${t.reproduction.seed} retrained here, validation loss ${formatRecord(t.reproduction.retrained_loss)} against the served ${formatRecord(t.reproduction.recorded_loss)}`, 12, y, { size: 11, colour: INK, max: width - 24 });
      text(g, `Training curves: ${isMeasured(t.history) ? '' : 'Pending, not in this repository'}`, 12, y + 20, { size: 10.5, colour: FAINT });
      text(g, 'The five members and their softmax temperatures (answers / best guess)', 12, y + 56, { size: 11, colour: INK, weight: 600 });
      t.members.forEach((m, k) => chip(g, `seed ${k}: ${formatRecord(m.answer_temperature)} / ${formatRecord(m.guess_temperature)}`, 12 + (k % 3) * ((width - 24) / 3), y + 84 + Math.floor(k / 3) * 30, { size: 10.5 }));
      g.restore();
    }
  }, {
    describe: () => `Five encoders trained on RNA only, ${formatRecord(t.recipe.epochs)} epochs at most, batches of ${formatRecord(t.recipe.batch)}.`,
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
