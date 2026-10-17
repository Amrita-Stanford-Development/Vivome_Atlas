// The Workflow page's scenes for the evidence: how the encoders were trained,
// and how the results were calculated, with the live service at the end.
// Same interface and rules as web/js/scenes-input.js. The mechanism pictures
// (a training batch, the four forces, a bootstrap draw) are illustrations
// with no numbers and say so; every number drawn is a recorded one.

import { isMeasured } from './manifest.js';
import { PRACTICE_KINDS, SERVICE_STEPS as STEPS, formatRecord, plainName } from './workflow-data.js';
import { buildScenarioTable, buildServiceCard } from './workflow-panels.js';
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
// share a real file has. Beat 3: several learners, averaged. (Their test is
// the first beat of the results.)

export function training(el, ctx) {
  const w = ctx.workflow;
  const t = w.training;
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
  return scene(el, ({ g, width, height }, p, state) => {
    const narrow = width < 560;
    const short = height < 340;
    // Beat 1: learning by example.
    const one = 1 - phase(p, 0.31, 0.36);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const learn = phase(p, 0.04, 0.28);
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
    const two = phase(p, 0.31, 0.36) * (1 - phase(p, 0.645, 0.695));
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
      const hide = phase(p, 0.36, 0.49);
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
      const real = phase(p, 0.49, 0.6);
      const cell = ctx.cell(state);
      if (real > 0 && cell) {
        const share = cell.observed / fs;
        strip(top + 3 * gap + 6, share, PROT, narrow
          ? `real file: our cell has ${Math.round(share * 100)}% of its genes`
          : `a real protein file: our cell (cell ${state.cell + 1}) has ${cell.observed.toLocaleString('en-US')} of ${fs.toLocaleString('en-US')} genes, ${Math.round(share * 100)}%`, real);
      }
      text(g, narrow ? 'Each bar is one gene; grey means hidden.' : 'Each bar is one gene; grey means hidden. Which genes are hidden is drawn at random, as in training.',
        12, height - 10, { size: 10, colour: FAINT, max: bw });
      g.restore();
    }

    // Beat 3: five learners, averaged.
    const three = phase(p, 0.645, 0.695);
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, `${t.members.length} learners instead of one`, 12, 22, { size: 12, weight: 600, colour: INK });
      const n = t.members.length;
      const gap = 10;
      const cw = (width - 24 - gap * (n - 1)) / n;
      const ch = Math.min(cw * 1.7, height * 0.52, height - 150);
      t.members.forEach((m, k) => {
        const x = 12 + k * (cw + gap);
        const y = 42;
        const appear = clamp(phase(p, 0.69, 0.82) * n - k, 0, 1);
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
      const avg = phase(p, 0.82, 0.93);
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

  }, {
    describe: () => `${t.members.length} learners, each trained on the named RNA examples alone, up to ${epochs} rounds, with most genes hidden in practice.`,
  });
}

// ---- 13: testing VivOME ----
// Beat 1: the learners' own test, against guessing. Beat 2: the practice
// files: when VivOME answers, how often it is right, by kind. Beat 3: the
// Fulcher 2026 contest, VivOME against the other methods.

export function results(el, ctx) {
  const w = ctx.workflow;
  const m = ctx.manifest;
  const scenarios = w.evaluation.scenarios;
  const fulcher = (m?.benchmark?.datasets ?? []).find((d) => d.key === 'fulcher2026');
  const t = w.training;
  const classes = w.reference.classes;
  const chance = 1 / classes.length;
  return scene(el, ({ g, width, height }, p) => {
    const narrow = width < 560;
    const short = height < 340;
    // Beat 1: did it learn? The learners' own test, straight after training.
    // Ten cells stand for the score; then the score against guessing at random.
    const zero = 1 - phase(p, 0.31, 0.355);
    const chosen = t.encoder_choice.candidates[0];
    if (zero > 0 && chosen && isMeasured(chosen.balanced_accuracy)) {
      g.save();
      g.globalAlpha = zero;
      const v = chosen.balanced_accuracy.value;
      text(g, 'First, did it learn? A test on cells it never practised on', 12, 22, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, 'with most of their genes hidden, as in a protein file', 12, 40, { size: 10.5, colour: SOFT, max: width - 24 });
      const n = 10;
      const right = Math.round(v * n);
      // The ticks shrink on a short figure so the note fits under the bars.
      const size = Math.min(26, (width - 24) / (n * 2.6), short ? (height - 188) / 2 : 26);
      const step = size * 2.6;
      const x0 = (width - step * (n - 1)) / 2;
      const yI = 64 + size;
      const fill = phase(p, 0.02, 0.12);
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
      const vs = phase(p, 0.12, 0.22);
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
      } else {
        // A short figure: both notes on one line, under the bars.
        text(g, narrow ? `Guessing: right once in ${classes.length}. Score: average of ${formatRecord(t.encoder_choice.seeds)} runs.`
          : `Guessing is right about once in ${classes.length} tries. The score is the chosen design\u2019s average over its ${formatRecord(t.encoder_choice.seeds)} training runs.`,
        12, height - 6, { size: 10, colour: FAINT, opacity: vs, max: width - 24 });
      }
      g.restore();
    }
    // Beat 2: the practice files: when VivOME answers, how often it is right.
    const one = phase(p, 0.31, 0.355) * (1 - phase(p, 0.645, 0.69));
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      text(g, narrow ? 'When VivOME answers, it is right' : 'Practice files: when VivOME gives an answer, how often it is right', 12, 20,
        { size: 12, colour: INK, weight: 600, max: width - 24 });
      text(g, narrow ? 'by kind of file' : 'by kind of file, from RNA cells it never trained on, with most genes hidden', 12, 38,
        { size: 10.5, colour: SOFT, max: width - 24 });
      const rows = scenarios.filter((s) => isMeasured(s.correct_when_committed))
        .sort((a, b) => b.correct_when_committed.value - a.correct_when_committed.value);
      const labelW = narrow ? 112 : 200;
      const top = 58;
      const rowH = clamp((height - top - 24) / rows.length, 18, 46);
      const bw = width - labelW - 70;
      const grow = phase(p, 0.36, 0.55);
      rows.forEach((s, k) => {
        const y = top + k * rowH;
        const v = s.correct_when_committed.value;
        text(g, PRACTICE_KINDS[s.group] ?? s.group, labelW - 10, y + rowH * 0.62, { size: narrow ? 10 : 11.5, align: 'right', colour: INK, max: labelW - 14 });
        bar(g, labelW, y + rowH * 0.18, bw * v * grow, rowH * 0.6, ACCENT, 3);
        text(g, formatRecord(s.correct_when_committed), labelW + bw * v * grow + 6, y + rowH * 0.62, { size: narrow ? 10 : 11.5, weight: 600, colour: INK, opacity: grow });
      });
      g.restore();
    }
    // Beat 3: the Fulcher 2026 contest.
    const two = phase(p, 0.645, 0.69);
    if (two > 0 && fulcher) {
      g.save();
      g.globalAlpha = two;
      // The served model and the other methods (an earlier VivOME is not this contest's entry).
      const served = (r) => r.ours && String(r.method).startsWith(m?.model?.name ?? '\u0000');
      const fits = Math.max(4, Math.floor((height - 130) / 15));
      const rows = fulcher.rows.filter((r) => isMeasured(r.score) && (!r.ours || served(r))).slice(0, Math.min(narrow ? 6 : 12, fits));
      const best = rows.length && served(rows[0]);
      const left = narrow ? 130 : Math.min(300, width * 0.46);
      const x = (v) => left + v * (width - left - 24);
      const rowH = Math.min(24, (height - 130) / rows.length);
      text(g, narrow ? 'Fulcher 2026: types named correctly' : 'Fulcher 2026: share of cells named correctly, every type counted equally', 12, 20,
        { size: 12, colour: INK, weight: 600, max: width - 24 });
      text(g, narrow ? 'one dot per method; blue: VivOME' : 'one dot per method; blue: VivOME; grey: other published methods', 12, 38, { size: 10.5, colour: SOFT, max: width - 24 });
      const show = phase(p, 0.7, 0.86);
      rows.forEach((r, k) => {
        if (k / rows.length > show) return;
        const y = 60 + k * rowH;
        const vivome = r.ours ? 'VivOME' : null;
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
      const verdict = phase(p, 0.86, 0.92);
      if (best) {
        text(g, narrow ? 'VivOME named the most cells correctly.' : 'VivOME named more cells correctly than any other method tested.', 12, height - 28,
          { size: 11.5, weight: 600, colour: ACCENT, max: width - 24, opacity: verdict });
      }
      text(g, narrow ? 'This file also helped build VivOME.' : 'This file was also used while building VivOME, so it is not a fully independent test.', 12, height - 10,
        { size: 10, colour: SOFT, max: width - 24, opacity: verdict });
      g.restore();
    }
  }, {
    describe: () => `The learners' own test (${formatRecord(t.encoder_choice.candidates[0].balanced_accuracy)} named correctly, against guessing), how often VivOME's answers on practice files are right, and the Fulcher 2026 contest.`,
    table: () => buildScenarioTable(w),
  });
}

// ---- 14: sending a file to VivOME ----
// One picture, the browser on one side and the cloud service on the other.
// Beat 1: the file chosen and checked in the browser. Beat 2: it travels;
// the service wakes. Beat 3: the service's checks. Beat 4: every step of
// this page, lit in turn. Beat 5: the answers travel back, one log line is
// kept, and the service sleeps again. Numbers are the service's settings.

// A small file: a sheet with a folded corner and a grid.
function fileIcon(g, x, y, s, colour, opacity = 1) {
  g.save();
  g.globalAlpha *= opacity;
  g.fillStyle = '#FFFFFF';
  g.strokeStyle = colour;
  g.lineWidth = 1.5;
  g.beginPath();
  g.moveTo(x, y);
  g.lineTo(x + s * 0.72, y);
  g.lineTo(x + s, y + s * 0.28);
  g.lineTo(x + s, y + s * 1.25);
  g.lineTo(x, y + s * 1.25);
  g.closePath();
  g.fill();
  g.stroke();
  for (let k = 1; k < 5; k += 1) line(g, x + s * 0.14, y + s * 0.22 * k + s * 0.12, x + s * 0.86, y + s * 0.22 * k + s * 0.12, { colour: alpha(colour, 0.45) });
  line(g, x + s * 0.4, y + s * 0.3, x + s * 0.4, y + s * 1.12, { colour: alpha(colour, 0.45) });
  g.restore();
}

// A tick or a cross in a circle, then its label.
function mark(g, ok, x, y, label, { opacity = 1, size = 11, colour = INK, max } = {}) {
  dot(g, x + 7, y - 4, 7, ok ? ACCENT : '#C9D1D7', opacity);
  if (ok) {
    line(g, x + 3.6, y - 4, x + 6.2, y - 1.4, { colour: '#FFFFFF', width: 2, opacity });
    line(g, x + 6.2, y - 1.4, x + 10.6, y - 7.4, { colour: '#FFFFFF', width: 2, opacity });
  } else {
    line(g, x + 4.5, y - 6.5, x + 9.5, y - 1.5, { colour: '#FFFFFF', width: 2, opacity });
    line(g, x + 9.5, y - 6.5, x + 4.5, y - 1.5, { colour: '#FFFFFF', width: 2, opacity });
  }
  text(g, label, x + 20, y, { size, colour, opacity, max });
}

export function online(el, ctx) {
  const w = ctx.workflow;
  const svc = w.service;
  const rec = (r) => (isMeasured(r) ? formatRecord(r) : '\u2026');
  return scene(el, ({ g, width, height }, p) => {
    const narrow = width < 560;
    // The two places: the browser, and the cloud service.
    const boxH = Math.min(270, height - 66);
    const top = narrow ? 50 : 50 + (height - 66 - boxH) / 2;
    const B = narrow ? { x: 12, y: top, w: width - 24, h: (height - top - 16) * 0.36 }
      : { x: 12, y: top, w: Math.min(300, width * 0.32), h: boxH };
    const C = narrow ? { x: 12, y: B.y + B.h + 34, w: width - 24, h: height - (B.y + B.h + 34) - 8 }
      : { x: width - 12 - Math.min(400, width * 0.42), y: top, w: Math.min(400, width * 0.42), h: boxH };
    const titles = ['Your file, checked in your browser', 'To the cloud, which wakes up', 'The service checks the file', 'Every step of this page, in order', 'The answers come back'];
    const beat = Math.min(4, Math.floor(p * 5));
    text(g, titles[beat], 12, 22, { size: 12, weight: 600, colour: INK, max: width - 24 });

    // The browser.
    const wakeUp = phase(p, 0.24, 0.36);
    const back = phase(p, 0.82, 0.92);
    const sleep = phase(p, 0.93, 0.965);
    g.save();
    bar(g, B.x, B.y, B.w, B.h, '#FFFFFF', 12);
    g.strokeStyle = LINE;
    g.lineWidth = 1.5;
    roundRect(g, B.x + 0.75, B.y + 0.75, B.w - 1.5, B.h - 1.5, 12);
    g.stroke();
    bar(g, B.x, B.y, B.w, 22, BENCH, 12);
    [0, 1, 2].forEach((k) => dot(g, B.x + 14 + k * 11, B.y + 11, 3.2, '#C9D1D7'));
    text(g, 'your browser: the project page', B.x + 50, B.y + 15, { size: 10, colour: SOFT, max: B.w - 58 });
    g.restore();
    const fs = Math.min(34, B.h * 0.26);
    const away = phase(p, 0.2, 0.3);
    if (away < 1) fileIcon(g, B.x + 16, B.y + 34, fs, ACCENT, 1 - away);
    text(g, 'your file', B.x + 16 + fs + 10, B.y + 34 + fs * 0.6, { size: 11, weight: 600, colour: INK, opacity: 1 - away, max: B.w - fs - 40 });
    const chk = phase(p, 0.04, 0.14) * (1 - phase(p, 0.2, 0.26));
    const yC = B.y + 34 + fs * 1.25 + 22;
    if (!narrow || B.h > 120) {
      mark(g, true, B.x + 14, yC, 'rows and columns counted', { opacity: chk, size: 10.5, max: B.w - 40 });
      mark(g, true, B.x + 14, yC + 22, 'nothing sent yet', { opacity: chk, size: 10.5, max: B.w - 40 });
    }
    // While the file is away, the page waits.
    const waiting = phase(p, 0.28, 0.34) * (1 - back);
    if (waiting > 0) {
      text(g, 'waiting for the answers\u2026', B.x + 16, B.y + B.h / 2, { size: 11, colour: SOFT, opacity: waiting, max: B.w - 32 });
      [0, 1, 2].forEach((k) => dot(g, B.x + 22 + k * 14, B.y + B.h / 2 + 18, 3.5, ACCENT, waiting * (0.35 + 0.65 * ((Math.floor(p * 60) + k) % 3 === 0 ? 1 : 0.3))));
    }
    // The answers, back in the browser.
    if (back > 0) {
      const ry = B.y + 34;
      const rw = B.w - 28;
      text(g, 'every cell\u2019s answer', B.x + 14, ry + 10, { size: 11, weight: 600, colour: ACCENT, opacity: back });
      [0.82, 0.55, 0.32, 0.18].forEach((v, k) => bar(g, B.x + 14, ry + 20 + k * 12, rw * v * back, 8, k === 0 ? ACCENT : '#8bb6da', 3, back));
      if (!narrow) {
        fileIcon(g, B.x + 14, ry + 82, 16, INK, back);
        text(g, 'download: one file of answers', B.x + 38, ry + 96, { size: 10.5, colour: INK, opacity: back, max: B.w - 50 });
      }
    }

    // The cloud service.
    const awake = wakeUp * (1 - sleep);
    g.save();
    bar(g, C.x, C.y, C.w, C.h, awake > 0.5 ? '#FFFFFF' : '#EEF1F4', 12);
    g.strokeStyle = awake > 0.5 ? ACCENT : LINE;
    g.lineWidth = 1.5;
    roundRect(g, C.x + 0.75, C.y + 0.75, C.w - 1.5, C.h - 1.5, 12);
    g.stroke();
    g.restore();
    text(g, svc.platform, C.x + 14, C.y + 20, { size: 12, weight: 600, colour: awake > 0.5 ? ACCENT : SOFT, max: C.w - 28 });
    const machine = `${rec(svc.cpu)} processors, ${parseInt(svc.memory, 10) || ''} GB of memory, switched on only when needed`;
    text(g, machine, C.x + 14, C.y + 36, { size: 10, colour: SOFT, max: C.w - 28 });
    const state = sleep > 0.5 ? 'asleep again' : awake > 0.99 ? 'awake' : awake > 0 ? 'waking: up to a minute' : 'asleep';
    chip(g, state, C.x + C.w - 14, C.y + 18, { size: 10, align: 'right', colour: awake > 0.99 && sleep < 0.5 ? ACCENT : SOFT, border: awake > 0.99 && sleep < 0.5 ? ACCENT : LINE });
    if (awake > 0 && awake < 1) {
      // The waking ring.
      g.save();
      g.strokeStyle = ACCENT;
      g.lineWidth = 3;
      g.beginPath();
      g.arc(C.x + C.w / 2, C.y + C.h / 2 + 10, 18, -Math.PI / 2, -Math.PI / 2 + awake * Math.PI * 2);
      g.stroke();
      g.restore();
    }
    // The file's journey there, and the answers' journey back.
    const [ax, ay, bx, by] = narrow ? [B.x + B.w / 2, B.y + B.h, C.x + C.w / 2, C.y] : [B.x + B.w, B.y + B.h * 0.35, C.x, C.y + C.h * 0.35];
    line(g, ax, ay, bx, by, { colour: LINE, width: 2, dash: [5, 5] });
    const go = phase(p, 0.2, 0.3);
    if (go > 0 && go < 1) fileIcon(g, lerp(ax, bx, go) - 9, lerp(ay, by, go) - 11, 18, ACCENT);
    if (back > 0 && back < 1) dot(g, lerp(bx, ax, back), lerp(by, ay, back), 6, ACCENT);
    if (!narrow) {
      text(g, 'your file \u2192', (ax + bx) / 2, ay - 10, { size: 10.5, colour: INK, align: 'center', opacity: phase(p, 0.2, 0.26) * (1 - back) });
      text(g, '\u2190 the answers', (ax + bx) / 2, ay + 22, { size: 10.5, colour: ACCENT, align: 'center', opacity: back });
    }

    // Inside the service: the file arrived, its checks, then the steps.
    const inside = { x: C.x + 14, y: C.y + 62, w: C.w - 28 };
    const arrived = phase(p, 0.3, 0.34) * (1 - phase(p, 0.4, 0.44));
    if (arrived > 0) {
      fileIcon(g, inside.x, inside.y, 22, ACCENT, arrived);
      text(g, 'your file has arrived', inside.x + 32, inside.y + 14, { size: 11, weight: 600, colour: INK, opacity: arrived, max: inside.w - 36 });
      text(g, 'the service woke for it, and stays awake while it works', inside.x + 32, inside.y + 30, { size: 10, colour: SOFT, opacity: arrived, max: inside.w - 36 });
    }
    const checks = phase(p, 0.42, 0.56) * (1 - phase(p, 0.6, 0.64));
    if (checks > 0) {
      const rows = [`at least ${rec(svc.min_cells)} cells`, `at most ${rec(svc.max_cells)} cells`, `no more than ${rec(svc.max_mb)} MB`,
        `${rec(svc.concurrent_projections)} file at a time; others: try again shortly`];
      rows.forEach((s, k) => mark(g, true, inside.x, inside.y + 12 + k * (narrow ? 20 : 26), s,
        { opacity: clamp(checks * rows.length - k, 0, 1), size: narrow ? 10 : 11, max: inside.w - 24 }));
    }
    const steps = phase(p, 0.62, 0.78) * (1 - phase(p, 0.8, 0.84));
    if (steps > 0) {
      const rowH = Math.min(26, (C.y + C.h - inside.y - 20) / STEPS.length);
      STEPS.forEach((s, k) => {
        const lit = steps * STEPS.length > k;
        chip(g, `${k + 1}. ${s}`, inside.x, inside.y + 10 + k * rowH, { size: narrow ? 9.5 : 10.5, colour: lit ? INK : FAINT, border: lit ? ACCENT : null, opacity: Math.min(1, steps * 3) });
      });
    }
    const after = phase(p, 0.84, 0.92);
    if (after > 0) {
      text(g, 'kept: one log line per file', inside.x, inside.y + 14, { size: 11, weight: 600, colour: INK, opacity: after, max: inside.w });
      text(g, 'the counts and a fingerprint of the file,', inside.x, inside.y + 32, { size: 10.5, colour: SOFT, opacity: after, max: inside.w });
      text(g, 'not your values; no copy of the file is saved', inside.x, inside.y + 48, { size: 10.5, colour: SOFT, opacity: after, max: inside.w });
    }
  }, {
    describe: () => `Your file is checked in the browser, sent to ${svc.platform}, which wakes if it was asleep, checked against the service's limits, run through every step of this page, and answered; the service keeps one log line and goes back to sleep.`,
    table: () => buildServiceCard(w),
  });
}

// ---- 15: running VivOME yourself ----
// Beat 1: a computer of your own, the two commands and the address it
// answers at. Beat 2: what it needs. Beat 3: what is ready and what is not.

export function local(el, ctx) {
  const w = ctx.workflow;
  const svc = w.service;
  const rec = (r) => (isMeasured(r) ? formatRecord(r) : '\u2026');
  const mono = (g, str, x, y, { size = 11, colour = INK, opacity = 1, max } = {}) => {
    g.save();
    g.globalAlpha *= opacity;
    let sz = size;
    g.font = `400 ${sz}px ui-monospace, Consolas, Menlo, monospace`;
    while (max && sz > 8 && g.measureText(str).width > max) { sz -= 0.5; g.font = `400 ${sz}px ui-monospace, Consolas, Menlo, monospace`; }
    g.fillStyle = colour;
    g.fillText(str, x, y);
    g.restore();
  };
  return scene(el, ({ g, width, height }, p) => {
    const narrow = width < 560;
    // Beat 1: the computer and its terminal.
    const one = 1 - phase(p, 0.31, 0.355);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      text(g, narrow ? 'On your own computer' : 'On your own computer: your file never leaves it', 12, 22, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const T = { x: 12, y: 44, w: narrow ? width - 24 : Math.min(620, width * 0.62), h: Math.min(200, height - 90) };
      bar(g, T.x, T.y, T.w, T.h, '#1D2B36', 10);
      [0, 1, 2].forEach((k) => dot(g, T.x + 14 + k * 11, T.y + 12, 3.2, '#4B5B67'));
      const typed = phase(p, 0.03, 0.2);
      const lines = [
        ['$ pip install -r service/requirements.txt', '#E8EEF2', 0.0],
        ['  installing what it needs\u2026', '#8FA3B1', 0.35],
        ['$ python -m service.app', '#E8EEF2', 0.55],
        [`  listening on 127.0.0.1:${isMeasured(svc.local_port) ? svc.local_port.value : '\u2026'}`, '#7CC4F0', 0.8],
      ];
      lines.forEach(([s, c, at], k) => mono(g, s, T.x + 16, T.y + 40 + k * Math.min(30, (T.h - 50) / 4), { size: narrow ? 9.5 : 12, colour: c, opacity: typed > at ? 1 : 0, max: T.w - 28 }));
      if (!narrow) {
        const sx = T.x + T.w + 30;
        const ready = phase(p, 0.2, 0.28);
        fileIcon(g, sx, T.y + 30, 28, ACCENT, ready);
        text(g, 'the project page sends', sx + 40, T.y + 44, { size: 11, colour: INK, opacity: ready, max: width - sx - 52 });
        text(g, 'your file here instead', sx + 40, T.y + 60, { size: 11, colour: INK, opacity: ready, max: width - sx - 52 });
        text(g, 'of to the cloud', sx + 40, T.y + 76, { size: 11, colour: INK, opacity: ready, max: width - sx - 52 });
      }
      text(g, 'Two commands, from a copy of VivOME\u2019s code.', 12, T.y + T.h + 24, { size: 10.5, colour: SOFT, opacity: typed, max: width - 24 });
      g.restore();
    }
    // Beat 2: what it needs.
    const two = phase(p, 0.31, 0.355) * (1 - phase(p, 0.645, 0.69));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      text(g, 'What it needs', 12, 22, { size: 12, weight: 600, colour: INK });
      const needs = [
        [`Python ${rec(svc.python)}`, 'the language it is written in'],
        ['an ordinary processor', 'no graphics card'],
        ['a few gigabytes of memory', 'more for bigger files'],
        [`up to ${rec(svc.max_cells)} cells and ${rec(svc.max_mb)} MB a file`, 'the cloud copy\u2019s limits, which you can raise'],
      ];
      const rowH = clamp((height - 60) / needs.length, 34, 62);
      const show = phase(p, 0.36, 0.5);
      needs.forEach(([a, b], k) => {
        const y = 52 + k * rowH;
        const o = clamp(show * needs.length - k, 0, 1);
        mark(g, true, 12, y + 12, a, { opacity: o, size: narrow ? 11 : 12.5, max: width - 48 });
        text(g, b, 32, y + 30, { size: 10.5, colour: SOFT, opacity: o, max: width - 48 });
      });
      g.restore();
    }
    // Beat 3: what is ready, and what is not yet.
    const three = phase(p, 0.645, 0.69);
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, 'Ready, and not yet', 12, 22, { size: 12, weight: 600, colour: INK });
      const items = [
        [true, 'the code, public for anyone to copy'],
        [true, 'two commands to install and start it'],
        [true, 'the project page can send files to it'],
        [false, 'the learners\u2019 files in the public copy: not yet'],
        [false, 'a one-click download: not yet'],
      ];
      const rowH = clamp((height - 80) / items.length, 24, 46);
      const show = phase(p, 0.7, 0.86);
      items.forEach(([ok, s], k) => mark(g, ok, 12, 56 + k * rowH, s,
        { opacity: clamp(show * items.length - k, 0, 1), size: narrow ? 11 : 12.5, colour: ok ? INK : SOFT, max: width - 48 }));
      text(g, narrow ? 'For now, ask the VivOME team for the learners\u2019 files.' : 'Until the learners\u2019 files are public, running VivOME yourself needs them from the VivOME team.', 12, height - 10,
        { size: 10.5, colour: SOFT, opacity: phase(p, 0.86, 0.92), max: width - 24 });
      g.restore();
    }
  }, {
    describe: () => `The same service on your own computer: two commands from a copy of the code; it needs Python ${rec(svc.python)} and an ordinary processor. Not finished: the learners' files are not yet public, and there is no one-click download.`,
  });
}
