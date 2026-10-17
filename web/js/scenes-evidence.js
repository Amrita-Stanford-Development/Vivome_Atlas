// The Workflow page's scenes for the evidence: how the encoders were trained,
// and how the results were calculated, with the live service at the end.
// Same interface and rules as web/js/scenes-input.js. The mechanism pictures
// (a training batch, the four forces, a bootstrap draw) are illustrations
// with no numbers and say so; every number drawn is a recorded one.

import { isMeasured } from './manifest.js';
import { PRACTICE_KINDS, formatRecord, plainName } from './workflow-data.js';
import { buildScenarioTable } from './workflow-panels.js';
import { clamp, lerp, phase } from './workflow-layout.js';
import { rng } from './random.js';
import {
  ACCENT, BENCH, FAINT, FONT, INK, LINE, PROT, RNA, SOFT, alpha, bar, chip, dot, line, mountCanvas, roundRect, text,
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
// drawn, and say so). Beat 2: practising with most genes hidden, beside the
// share a real file has. Beat 3: several learners, averaged. Beat 4: the
// test: test cells named correctly, against guessing.

export function training(el, ctx) {
  const w = ctx.workflow;
  const t = w.training;
  const classes = w.reference.classes;
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
  // The example cell in beat 2: the sample's first, by its type's name.
  const exampleType = plainName(w.class_order[pts[0][3]]);
  const fs = w.raw.pbmc240.align.feature_space;
  const chance = 1 / classes.length;
  return scene(el, ({ g, width, height }, p, state) => {
    const narrow = width < 560;
    const short = height < 340;
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

    // Beat 2: practising with most genes hidden, beside a real file's share.
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
      const top = narrow ? 70 : 58;
      const stripH = clamp((height - top - 30) / 4 - 22, 8, 32);
      const gap = stripH + 22;
      text(g, 'Practising with most genes hidden', 12, 22, { size: 12, weight: 600, colour: INK, max: bw });
      if (narrow) {
        text(g, 'One example cell, as the learner sees it.', 12, 40, { size: 10.5, colour: SOFT, max: bw });
        text(g, `The name it must learn to give: ${exampleType}`, 12, 55, { size: 10.5, colour: SOFT, max: bw });
      } else {
        text(g, `One example cell, as the learner sees it in practice. The name it must learn to give: ${exampleType}`, 12, 42,
          { size: 10.5, colour: SOFT, max: bw });
      }
      const hide = phase(p, 0.28, 0.38);
      const strip = (y, keep, colour, label, opacity = 1) => {
        for (let k = 0; k < genes; k += 1) {
          const shown = r() < keep;
          bar(g, 12 + k * gw, y, gw - 1, stripH, shown ? alpha(colour, 0.5 + 0.4 * ((k * 13) % 7) / 7) : '#E3E7EB', 1, opacity);
        }
        text(g, label, 12, y + stripH + 14, { size: 10, colour: INK, opacity, max: bw });
      };
      [lo, (lo + hi) / 2, hi].forEach((keep, v) => {
        strip(top + v * gap, hide === 0 ? 1 : keep, ACCENT, `practice: ${Math.round(keep * 100)}% of its genes shown`, hide > 0 ? 1 : 0.4);
      });
      // A real protein file, for comparison: our cell's share.
      const real = phase(p, 0.38, 0.46);
      const cell = ctx.cell(state);
      if (real > 0 && cell) {
        const share = cell.observed / fs;
        strip(top + 3 * gap + 6, share, PROT, narrow
          ? `real file: our cell has ${Math.round(share * 100)}% of its genes`
          : `a real protein file: our cell (cell ${state.cell + 1}) has ${cell.observed.toLocaleString('en-US')} of ${fs.toLocaleString('en-US')} genes, ${Math.round(share * 100)}%`, real);
      }
      if (!short) {
        text(g, narrow ? 'Each bar is one gene; grey means hidden.' : 'Each bar is one gene; grey means hidden. Which genes are hidden is drawn at random, as in training.',
          12, height - 12, { size: 10, colour: FAINT, max: bw });
      }
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
        chip(g, 'their views are averaged into one (Part 3, step 2)', width / 2, ay + 6, { size: 12, align: 'center', border: ACCENT, colour: ACCENT, opacity: avg });
        text(g, 'Same training, different random starts; the small differences between the maps are drawn to show the idea.', width / 2, ay + 44,
          { size: 10, colour: FAINT, align: 'center', opacity: avg, max: width - 24 });
      }
      g.restore();
    }

    // Beat 4: the test. Ten cells stand for the score; then the score
    // against guessing at random.
    const four = phase(p, 0.76, 0.82);
    const chosen = t.encoder_choice.candidates[0];
    if (four > 0 && chosen && isMeasured(chosen.balanced_accuracy)) {
      g.save();
      g.globalAlpha = four;
      const v = chosen.balanced_accuracy.value;
      text(g, 'Did it learn? A test on cells it never practised on', 12, 22, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, 'with most of their genes hidden, as in a protein file', 12, 40, { size: 10.5, colour: SOFT, max: width - 24 });
      const n = 10;
      const right = Math.round(v * n);
      const size = Math.min(26, (width - 24) / (n * 2.6));
      const step = size * 2.6;
      const x0 = (width - step * (n - 1)) / 2;
      const yI = 64 + size;
      const fill = phase(p, 0.8, 0.88);
      for (let k = 0; k < n; k += 1) {
        const x = x0 + k * step;
        const ok = k < right && fill > k / n;
        dot(g, x, yI, size, ok ? ACCENT : '#E9ECEF', 1, ok ? null : '#C9D1D7');
        if (ok) {
          line(g, x - size * 0.42, yI + size * 0.02, x - size * 0.1, yI + size * 0.34, { colour: '#FFFFFF', width: 3 });
          line(g, x - size * 0.1, yI + size * 0.34, x + size * 0.45, yI - size * 0.3, { colour: '#FFFFFF', width: 3 });
        }
      }
      const yT = yI + size + (short ? 22 : 30);
      text(g, `${formatRecord(chosen.balanced_accuracy)} named correctly: about ${right} in ${n}`, width / 2, yT,
        { size: short ? 14 : 16, weight: 700, colour: INK, align: 'center', opacity: fill, max: width - 24 });
      text(g, `every one of the ${classes.length} types counted equally`, width / 2, yT + (short ? 16 : 20),
        { size: 10.5, colour: SOFT, align: 'center', opacity: fill });
      // Against guessing at random.
      const vs = phase(p, 0.88, 0.95);
      const labelW = Math.min(170, width * 0.32);
      const bw = width - labelW - 70;
      const yB = yT + (short ? 30 : 50);
      [[narrow ? 'guessing' : 'guessing at random', chance, '#AEB9C2'], ['VivOME', v, ACCENT]].forEach(([label, value, colour], k) => {
        const y = yB + k * (short ? 28 : 34);
        text(g, label, labelW, y + 15, { size: 11, align: 'right', colour: INK, opacity: vs, max: labelW - 8 });
        bar(g, labelW + 10, y, bw * value * vs, 22, colour, 3);
        text(g, `${(value * 100).toFixed(1)}%`, labelW + 16 + bw * value * vs, y + 15, { size: 11, colour: INK, opacity: vs });
      });
      if (!short) {
        text(g, `Guessing picks one of the ${classes.length} types, so it is right about once in ${classes.length} tries.`,
          12, height - 28, { size: 10, colour: FAINT, opacity: vs, max: width - 24 });
        text(g, `The score is the chosen design\u2019s average over its ${formatRecord(t.encoder_choice.seeds)} training runs.`,
          12, height - 14, { size: 10, colour: FAINT, opacity: vs, max: width - 24 });
      }
      g.restore();
    }
  }, {
    describe: () => `${t.members.length} learners, each trained on the named RNA examples alone, up to ${epochs} rounds, with most genes hidden in practice; tested on cells they never practised on, ${formatRecord(t.encoder_choice.candidates[0].balanced_accuracy)} named correctly.`,
  });
}

// ---- 12: testing VivOME, and using it today ----
// Beat 1: the practice files, by kind. Beat 2: the Fulcher 2026 contest.
// Beat 3: the six locked-away sets. Beat 4: a file sent to the live service.

const RESULT_WORDS = { pass: 'passed', fail: 'failed', void: 'could not be scored' };

export function results(el, ctx) {
  const w = ctx.workflow;
  const m = ctx.manifest;
  const scenarios = w.evaluation.scenarios;
  const heldout = w.evaluation.heldout;
  const fulcher = (m?.benchmark?.datasets ?? []).find((d) => d.key === 'fulcher2026');
  const svc = w.service;
  return scene(el, ({ g, width, height }, p) => {
    const narrow = width < 560;
    // Beat 1: the practice files.
    const one = 1 - phase(p, 0.23, 0.28);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      text(g, narrow ? 'Practice files, by kind' : 'Practice files, by kind: how many cells got an answer, and how many answers were right', 12, 20,
        { size: 12, colour: INK, weight: 600, max: width - 24 });
      bar(g, 12, 32, 11, 11, '#B9C9D6', 2);
      text(g, 'got an answer', 28, 42, { size: 10.5, colour: SOFT });
      bar(g, 122, 32, 11, 11, ACCENT, 2);
      text(g, 'answer was right', 138, 42, { size: 10.5, colour: SOFT });
      const labelW = narrow ? 104 : 160;
      const rowH = (height - 76) / scenarios.length;
      const bw = width - labelW - 60;
      const grow = phase(p, 0, 0.18);
      scenarios.forEach((s, k) => {
        const y = 56 + k * rowH;
        text(g, PRACTICE_KINDS[s.group] ?? s.group, labelW - 8, y + rowH * 0.45, { size: narrow ? 10 : 11, align: 'right', colour: INK, max: labelW - 10 });
        bar(g, labelW, y + 4, bw * s.committed.value * grow, rowH * 0.3, '#B9C9D6', 2);
        bar(g, labelW, y + 6 + rowH * 0.3, bw * s.correct_when_committed.value * grow, rowH * 0.3, ACCENT, 2);
        text(g, formatRecord(s.committed), labelW + bw * s.committed.value * grow + 4, y + 4 + rowH * 0.25, { size: 9.5, colour: FAINT, opacity: grow });
        text(g, formatRecord(s.correct_when_committed), labelW + bw * s.correct_when_committed.value * grow + 4, y + 6 + rowH * 0.55, { size: 9.5, colour: INK, opacity: grow });
      });
      g.restore();
    }
    // Beat 2: the Fulcher 2026 contest.
    const two = phase(p, 0.23, 0.28) * (1 - phase(p, 0.48, 0.53));
    if (two > 0 && fulcher) {
      g.save();
      g.globalAlpha = two;
      const rows = fulcher.rows.filter((r) => isMeasured(r.score)).slice(0, narrow ? 6 : 12);
      const left = narrow ? 130 : Math.min(300, width * 0.46);
      const x = (v) => left + v * (width - left - 24);
      const rowH = Math.min(24, (height - 92) / rows.length);
      text(g, narrow ? 'Fulcher 2026: types named correctly' : 'Fulcher 2026: share of cells named correctly, every type counted equally', 12, 20,
        { size: 12, colour: INK, weight: 600, max: width - 24 });
      text(g, narrow ? 'one dot per method; blue: VivOME' : 'one dot per method; blue: VivOME; grey: other published methods', 12, 38, { size: 10.5, colour: SOFT, max: width - 24 });
      const show = phase(p, 0.28, 0.42);
      rows.forEach((r, k) => {
        if (k / rows.length > show) return;
        const y = 60 + k * rowH;
        const vivome = r.ours ? (String(r.method).startsWith(m?.model?.name ?? '\u0000') ? 'VivOME, this version' : 'VivOME, the previous version') : null;
        const label = vivome ?? (narrow || r.rule === r.method.toLowerCase() || r.rule.toLowerCase() === r.method.toLowerCase() ? r.method : `${r.method}, ${r.rule}`);
        text(g, label, left - 8, y + 4, { size: 10, align: 'right', colour: r.ours ? INK : SOFT, weight: r.ours ? 600 : 400, max: left - 12 });
        dot(g, x(r.score.value), y, r.ours ? 6 : 4, r.ours ? ACCENT : '#9AA6AF');
      });
      const axisY = 60 + rows.length * rowH + 6;
      [0, 0.25, 0.5, 0.75, 1].forEach((v) => text(g, `${v * 100}%`, x(v), axisY + 8, { size: 9.5, colour: FAINT, align: 'center' }));
      if (isMeasured(fulcher.chance)) {
        line(g, x(fulcher.chance.value), 50, x(fulcher.chance.value), axisY - 4, { colour: FAINT, dash: [3, 3] });
        text(g, 'guessing', x(fulcher.chance.value) + 4, 54, { size: 9.5, colour: FAINT });
      }
      if (!narrow) {
        text(g, 'This file was also used while building VivOME: a fair contest, not a fully independent test.', 12, height - 12,
          { size: 10, colour: SOFT, max: width - 24, opacity: phase(p, 0.4, 0.46) });
      }
      g.restore();
    }
    // Beat 3: the six locked-away sets.
    const three = phase(p, 0.48, 0.53) * (1 - phase(p, 0.73, 0.78));
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, narrow ? 'Six sets kept back, opened once' : 'Six test sets, locked away before building started and opened once', 12, 20,
        { size: 12, colour: INK, weight: 600, max: width - 24 });
      const cols = narrow ? 2 : 3;
      const cw = (width - 24) / cols;
      const ch = narrow ? 44 : Math.min(112, (height - 100) / Math.ceil(heldout.length / cols));
      heldout.forEach((c, k) => {
        const x = 12 + (k % cols) * cw;
        const y = 34 + Math.floor(k / cols) * ch;
        const a = clamp(phase(p, 0.5, 0.7) * heldout.length - k, 0, 1);
        g.save();
        g.globalAlpha *= a;
        g.fillStyle = '#FFFFFF';
        roundRect(g, x + 4, y + 4, cw - 8, ch - 8, 12);
        g.fill();
        g.restore();
        const colour = c.result === 'pass' ? ACCENT : c.result === 'fail' ? INK : FAINT;
        chip(g, RESULT_WORDS[c.result] ?? c.result, x + 14, y + (narrow ? 18 : 24), { size: narrow ? 9.5 : 10.5, colour, border: colour, opacity: a });
        // The question, wrapped onto a few lines.
        const words = String(c.question).split(' ');
        const lines = [];
        let cur = '';
        g.save();
        g.font = `400 ${narrow ? 9.5 : 10.5}px ${FONT}`;
        for (const word of words) {
          const next = cur ? `${cur} ${word}` : word;
          if (g.measureText(next).width > cw - 32 && cur) { lines.push(cur); cur = word; } else cur = next;
        }
        if (cur) lines.push(cur);
        g.restore();
        const maxLines = narrow ? 1 : Math.max(1, Math.floor((ch - 46) / 14));
        lines.slice(0, maxLines).forEach((ln, j) => text(g, j === maxLines - 1 && lines.length > maxLines ? `${ln}\u2026` : ln, x + 14, y + (narrow ? 35 : 50) + j * 14,
          { size: narrow ? 9.5 : 10.5, colour: SOFT, opacity: a }));
      });
      const legend = phase(p, 0.66, 0.72);
      const yL = 34 + Math.ceil(heldout.length / cols) * ch + (narrow ? 12 : 18);
      const notes = narrow
        ? ['passed: it did what the test asked', 'failed: it did not', 'could not be scored: the data could not settle it']
        : ['passed: VivOME did what the test asked of it', 'failed: it did not, and the page says so', 'could not be scored: the data turned out unable to settle the question'];
      notes.forEach((s, k) => text(g, s, 16, yL + k * (narrow ? 14 : 16), { size: narrow ? 9.5 : 10.5, colour: SOFT, opacity: legend, max: width - 32 }));
      g.restore();
    }
    // Beat 4: a file sent to the live service.
    const four = phase(p, 0.76, 0.82);
    if (four > 0) {
      g.save();
      g.globalAlpha = four;
      text(g, narrow ? 'Using VivOME today' : 'Using VivOME today: a file goes to the service and answers come back', 12, 20,
        { size: 12, colour: INK, weight: 600, max: width - 24 });
      const y = narrow ? 44 : Math.min(height * 0.3, 90);
      const bw = Math.min(170, width * 0.3);
      box(g, 12, y, bw, 64, 'your browser', { colour: INK, size: narrow ? 10 : 11.5 });
      box(g, width - bw - 12, y, bw, 64, narrow ? 'Cloud Run' : `${svc.platform}`, { colour: ACCENT, size: narrow ? 10 : 11.5 });
      const x0 = 12 + bw;
      const x1 = width - bw - 12;
      line(g, x0, y + 20, x1, y + 20, { colour: INK, width: 1.5 });
      line(g, x1, y + 44, x0, y + 44, { colour: ACCENT, width: 1.5 });
      text(g, 'your file', (x0 + x1) / 2, y + 12, { size: 10.5, colour: INK, align: 'center' });
      text(g, 'answers', (x0 + x1) / 2, y + 62, { size: 10.5, colour: ACCENT, align: 'center' });
      const t = phase(p, 0.8, 1);
      if (t < 0.5) dot(g, lerp(x0, x1, t * 2), y + 20, 6, PROT);
      else dot(g, lerp(x1, x0, (t - 0.5) * 2), y + 44, 6, ACCENT);
      const steps = ['fit to the list', 'borrow from similar cells', 'turn into a point', 'closeness to types', 'best guess', 'answer or reason', 'place on the map'];
      let sx = 12;
      let sy = y + (narrow ? 88 : 112);
      text(g, 'Inside the service, the steps on this page:', 12, sy - 20, { size: 10.5, colour: SOFT });
      steps.forEach((s, k) => {
        const on = t > 0.15 + (k / steps.length) * 0.35;
        g.save();
        g.font = `500 ${narrow ? 10 : 10.5}px ${FONT}`;
        const wChip = g.measureText(s).width + 16;
        g.restore();
        if (sx + wChip > width - 12) { sx = 12; sy += narrow ? 24 : 28; }
        chip(g, s, sx, sy, { size: narrow ? 10 : 10.5, opacity: on ? 1 : 0.35, colour: on ? INK : FAINT, border: on ? ACCENT : null });
        sx += wChip + 8;
      });
      if (!narrow) {
        text(g, `Up to ${formatRecord(svc.max_cells)} cells per file. The service sleeps when nobody is using it and wakes for the next file.`,
          12, height - 12, { size: 10.5, colour: SOFT, max: width - 24 });
      }
      g.restore();
    }
  }, {
    describe: () => `Practice files by kind, the Fulcher 2026 contest, the six locked-away sets, and the live service on ${svc.platform}.`,
    table: () => buildScenarioTable(w),
  });
}
