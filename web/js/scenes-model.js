// The Workflow page's scenes for the model: the encoder pass, probabilities,
// the best guess, the answer and where the cell lands. Same interface and
// rules as web/js/scenes-input.js: every value drawn is recorded in
// web/data/workflow.json, and a frame depends only on p and the cell.

import { formatCount } from './manifest.js';
import { OUTCOME_LABELS, OUTCOME_ORDER, topK } from './workflow-data.js';
import {
  buildGuessTable, buildOutcomeTable, buildProbabilityTable,
} from './workflow-panels.js';
import {
  bandPath, clamp, depthOrder, diverging, fitSphere, lerp, phase, pickNearest, project, radialAngles, rotate, sankey,
  sequential,
} from './workflow-layout.js';
import {
  ACCENT, BENCH, FAINT, INK, LINE, PROT, RNA, SOFT, alpha, bar, chip, dot, line, mountCanvas, onDrag, short, text,
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

// ---- 8: the encoder pass ----

export function encoder(el, ctx) {
  const w = ctx.workflow;
  const enc = w.trace.stages.encoder;
  return scene(el, ({ g, width, height }, p, state) => {
    const { detail, own } = ctx.detail(state);
    const layers = enc.layers;
    const diagramH = height * lerp(0.92, 0.55, phase(p, 0.33, 0.45));
    const colX = layers.map((_, i) => 180 + (i / (layers.length - 1)) * (width - 250));
    const tall = (wd) => (Math.log10(wd) / Math.log10(layers[0].width)) * (diagramH - 60);
    const flow = phase(p, 0, 0.32);
    layers.forEach((layer, i) => {
      const h = tall(layer.width);
      const y = 30 + (diagramH - 60 - h) / 2;
      const on = flow * (layers.length - 1) >= i - 0.2;
      if (i === 0) {
        const parts = Object.entries(layer.parts);
        let yy = y;
        let labelY = -Infinity;
        parts.forEach(([name, n], k) => {
          const ph = (n / layer.width) * h;
          bar(g, colX[i] - 14, yy, 28, Math.max(3, ph - 1), [ACCENT, INK, '#5b8fc0', '#8a97a3'][k], 2, 0.85);
          labelY = Math.max(labelY + 14, yy + Math.max(8, ph / 2) + 4);
          text(g, `${name.replace(/_/g, ' ')} ${fc(n)}`, colX[i] - 20, labelY, { size: 9.5, colour: SOFT, align: 'right', max: colX[i] - 28 });
          yy += Math.max(3, ph);
        });
      } else {
        bar(g, colX[i] - 12, y, 24, h, on ? ACCENT : LINE, 4, on ? 0.85 : 1);
      }
      text(g, fc(layer.width), colX[i], y + h + 16, { size: 12, colour: INK, align: 'center', weight: 600 });
      if (i > 0) text(g, layer.name, colX[i], y + h + 30, { size: 9, colour: FAINT, align: 'center', max: (width - 250) / 3 - 6 });
    });
    // Particles carry the cell from layer to layer.
    for (let k = 0; k < 40; k += 1) {
      const t = (flow * 1.4 - (k / 40) * 0.4);
      if (t <= 0 || t >= 1) continue;
      const seg = Math.min(layers.length - 2, Math.floor(t * (layers.length - 1)));
      const local = t * (layers.length - 1) - seg;
      const spread = ((k * 53) % 17) / 17 - 0.5;
      dot(g, lerp(colX[seg] + 14, colX[seg + 1] - 12, local), 30 + (diagramH - 60) / 2 + spread * lerp(tall(layers[seg].width), tall(layers[seg + 1].width), local) * 0.8, 2.2, ACCENT, 0.55);
    }
    text(g, `${fc(enc.parameters)} weights in one encoder`, width - 6, 16, { size: 11, colour: FAINT, align: 'right' });
    const two = phase(p, 0.36, 0.5);
    if (two > 0 && detail) {
      const y = diagramH + 6;
      const bw = width - 16;
      text(g, `The cell's ${detail.embedding.length} numbers from seed 4${own ? '' : ` (shown for ${detail.id})`}`, 8, y + 10, { size: 11, colour: INK, opacity: two });
      const cw = bw / detail.embedding.length;
      detail.embedding.forEach((v, k) => {
        if (k / detail.embedding.length > two) return;
        g.fillStyle = diverging(v * 8) ?? BENCH;
        g.fillRect(8 + k * cw, y + 18, Math.max(0.5, cw - 0.4), 22);
      });
    }
    const three = phase(p, 0.68, 0.82);
    if (three > 0 && detail) {
      const y = diagramH + 56;
      text(g, `Share of each module's genes observed (${detail.module_fraction.length} modules)`, 8, y + 10, { size: 11, colour: INK, opacity: three });
      const cw = (width - 16) / detail.module_fraction.length;
      detail.module_fraction.forEach((v, k) => {
        g.globalAlpha = three;
        g.fillStyle = sequential(v);
        g.fillRect(8 + k * cw, y + 18, Math.max(0.5, cw), 16);
      });
      g.globalAlpha = 1;
      const lanes = enc.members.length;
      enc.members.forEach((name, k) => {
        chip(g, name.replace('V2_batchgene_aug_', '').replace('.pt', ''), 8 + k * ((width - 16) / lanes), y + 58, { size: 10.5, opacity: three, border: name === enc.coordinate_member ? ACCENT : null });
      });
    }
  }, {
    describe: () => `${fc(enc.layers[0].width)} inputs, then ${enc.layers.slice(1).map((l) => fc(l.width)).join(', then ')}; ${fc(enc.parameters)} weights.`,
  });
}

// ---- 9: from a point to probabilities ----

export function probabilities(el, ctx) {
  const w = ctx.workflow;
  const names = w.class_order;
  const angles = radialAngles(names, ctx.hierarchy);
  return scene(el, ({ g, width, height }, p, state) => {
    const { detail, own } = ctx.detail(state);
    if (!detail) return;
    const member = Number(ctx.options('probabilities').member ?? -1);
    const cx = width / 2;
    const cy = height / 2 + 8;
    const R = Math.min(width, height) * 0.36;
    const cosPhase = 1 - phase(p, 0.33, 0.5);
    const shown = member >= 0 ? [member] : detail.members.map((_, j) => j);
    const meanPhase = member >= 0 ? 0 : phase(p, 0.66, 0.85);
    // The compass: one spoke per type, grouped by lineage.
    names.forEach((name, i) => {
      const a = angles[i];
      const [dx, dy] = [Math.sin(a), -Math.cos(a)];
      line(g, cx, cy, cx + dx * R, cy + dy * R, { colour: LINE });
      dot(g, cx + dx * R, cy + dy * R, 4, ctx.classColour(i));
      const out = R + (Math.abs(dx) < 0.45 && i % 2 ? 26 : 12);
      const lx = cx + dx * out;
      const ly = cy + dy * out + 4;
      text(g, short(name), lx, ly, { size: 9.5, colour: SOFT, align: dx > 0.15 ? 'left' : dx < -0.15 ? 'right' : 'center', max: 110 });
    });
    // Each member: cosines first, then probabilities; then the mean.
    shown.forEach((j) => {
      const m = detail.members[j];
      const cosMin = Math.min(...m.cosine);
      const cosMax = Math.max(...m.cosine);
      g.beginPath();
      names.forEach((_, i) => {
        const cosR = (m.cosine[i] - cosMin) / (cosMax - cosMin || 1);
        const r = R * lerp(Math.sqrt(m.probability[i]), cosR, cosPhase);
        const x = cx + Math.sin(angles[i]) * r;
        const y = cy - Math.cos(angles[i]) * r;
        if (i === 0) g.moveTo(x, y); else g.lineTo(x, y);
      });
      g.closePath();
      g.strokeStyle = alpha(ACCENT, member >= 0 ? 0.9 : 0.35 * (1 - meanPhase) + 0.1);
      g.lineWidth = member >= 0 ? 2 : 1.2;
      g.stroke();
    });
    if (meanPhase > 0) {
      g.beginPath();
      names.forEach((_, i) => {
        const r = R * Math.sqrt(detail.ensemble[i]) * meanPhase;
        const x = cx + Math.sin(angles[i]) * r;
        const y = cy - Math.cos(angles[i]) * r;
        if (i === 0) g.moveTo(x, y); else g.lineTo(x, y);
      });
      g.closePath();
      g.fillStyle = alpha(ACCENT, 0.18);
      g.fill();
      g.strokeStyle = ACCENT;
      g.lineWidth = 2.2;
      g.stroke();
      topK(detail.ensemble, 3).forEach((c, k) => chip(g, `${short(names[c])} ${pct(detail.ensemble[c])}`, 8, 16 + k * 26, { size: 11, opacity: meanPhase, border: k === 0 ? ACCENT : null }));
    }
    const label = cosPhase > 0.5 ? 'cosine to each type’s centre (scaled per encoder)' : member >= 0 ? `seed ${member}: softmax at temperature ${detail.members[member].temperature}` : 'probability (square-root radius)';
    text(g, label, width - 8, 14, { size: 10.5, colour: FAINT, align: 'right', max: width * 0.6 });
    if (!own) text(g, `recorded for the story runs; showing ${detail.id}`, width - 8, height - 6, { size: 9.5, colour: FAINT, align: 'right' });
  }, {
    describe: (state) => {
      const { detail } = ctx.detail(state);
      const c = topK(detail.ensemble, 1)[0];
      return `Mean probability: ${names[c]} ${pct(detail.ensemble[c])} highest.`;
    },
    table: (state) => buildProbabilityTable(ctx.detail(state).detail, names),
  });
}

// ---- 10: the best guess ----

export function guess(el, ctx) {
  const w = ctx.workflow;
  const names = w.class_order;
  const fusion = w.trace.stages.fusion;
  const cells = w.trace.cells;
  const uploads = w.evaluation.uploads;
  return scene(el, ({ g, width, height }, p, state) => {
    const { detail, own } = ctx.detail(state);
    if (!detail) return;
    const gd = detail.guess;
    const useRna = ctx.options('guess').means === 'rna';
    const one = 1 - phase(p, 0.48, 0.54);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const top = topK(gd.fused, 6);
      const cols = [['encoders', gd.encoder, ACCENT], ['correlation', gd.correlation_probability, SOFT], ['fused', gd.fused, INK]];
      const colW = (width - 140) / 3;
      const rowH = Math.min(30, (height * 0.55) / top.length);
      top.forEach((c, r) => text(g, short(names[c]), 132, 46 + r * rowH, { size: 11, align: 'right', colour: INK, max: 128 }));
      cols.forEach(([label, vals, colour], k) => {
        const x = 140 + k * colW;
        const appear = phase(p, k * 0.08, k * 0.08 + 0.15);
        text(g, label, x, 22, { size: 11, weight: 600, colour });
        top.forEach((c, r) => {
          const flat = k === 1 && fusion.correlation_term === 'flat';
          bar(g, x, 34 + r * rowH, (colW - 50) * vals[c] * appear, rowH * 0.55, colour, 2, flat ? 0.35 : 0.85);
          text(g, pct(vals[c]), x + (colW - 50) * vals[c] * appear + 4, 46 + r * rowH, { size: 9.5, colour: FAINT, opacity: appear });
        });
        if (k === 1 && fusion.correlation_term === 'flat') chip(g, 'computed, not used here', x, 34 + top.length * rowH + 10, { size: 10, colour: SOFT });
      });
      // This cell's profile against a type's protein average.
      const sc = gd.scatter;
      const y0 = height * 0.62;
      const sh = height - y0 - 18;
      const sw = Math.min(sh * 1.3, width * 0.45);
      const appear = phase(p, 0.2, 0.36);
      if (appear > 0 && !useRna) {
        const xs = sc.points.map((q) => q[0]);
        const ys = sc.points.map((q) => q[1]);
        const [ax0, ax1, ay0, ay1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
        g.strokeStyle = LINE;
        g.strokeRect(8, y0, sw, sh);
        sc.points.forEach((q, k) => {
          if (k / sc.points.length > appear) return;
          dot(g, 8 + ((q[0] - ax0) / (ax1 - ax0 || 1)) * sw, y0 + sh - ((q[1] - ay0) / (ay1 - ay0 || 1)) * sh, 2, PROT, 0.6);
        });
        text(g, `this cell (x) against the ${short(names[sc.class])} protein average (y): r ${sc.r.toFixed(2)} over ${fc(sc.observed_proteins)} proteins`, sw + 18, y0 + 14, { size: 10.5, colour: INK, max: width - sw - 26 });
      }
      if (appear > 0 && useRna) {
        const covered = fusion.protein_classes;
        const bw = width - 160;
        text(g, 'r with RNA averages (orange) and protein averages (green), types the protein averages cover', 8, y0 + 4, { size: 10.5, colour: INK, max: width - 16 });
        covered.slice(0, 8).forEach((c, k) => {
          const y = y0 + 16 + k * Math.min(16, (sh - 10) / 8);
          text(g, short(names[c]), 150, y + 9, { size: 9.5, align: 'right', colour: SOFT, max: 140 });
          bar(g, 156, y, bw / 2 * Math.max(0, gd.r_rna[c]) * 2, 5, RNA, 1, appear);
          bar(g, 156, y + 6, bw / 2 * Math.max(0, gd.r_protein[c] ?? 0) * 2, 5, PROT, 1, appear);
        });
      }
      if (!own) text(g, `recorded for the story runs; showing ${detail.id}`, width - 8, height - 4, { size: 9.5, colour: FAINT, align: 'right' });
      g.restore();
    }
    const two = phase(p, 0.5, 0.56);
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      // The agreement gate: one dot per counted cell.
      const counted = cells.filter((c) => c.counted);
      const fill = phase(p, 0.54, 0.72);
      const bw = width - 32;
      const per = Math.ceil(counted.length / 8);
      const dw = bw / per;
      text(g, `Does the correlation agree with the encoders? ${fc(fusion.agreeing)} of ${fc(fusion.counted)} cells`, 16, 20, { size: 11.5, weight: 600, colour: INK, max: width - 24 });
      counted.forEach((c, k) => {
        if (k / counted.length > fill) return;
        const x = 16 + (k % per) * dw + dw / 2;
        const y = 40 + Math.floor(k / per) * 14;
        dot(g, x, y, Math.min(4, dw * 0.38), c.agrees ? ACCENT : LINE);
      });
      const by = 40 + 8 * 14 + 14;
      bar(g, 16, by, bw, 14, BENCH, 7);
      bar(g, 16, by, bw * fusion.agreement * fill, 14, ACCENT, 7, 0.85);
      line(g, 16 + bw * fusion.threshold, by - 6, 16 + bw * fusion.threshold, by + 20, { colour: INK, width: 2 });
      text(g, `gate ${pct(fusion.threshold)}`, 16 + bw * fusion.threshold + 4, by + 30, { size: 10.5, colour: INK });
      text(g, `${pct(fusion.agreement)}: the term is ${fusion.correlation_term} here`, 16, by + 30, { size: 10.5, colour: SOFT });
      // Where it opens: the simulated uploads.
      const four = phase(p, 0.76, 0.9);
      if (four > 0) {
        const y = by + 64;
        const h = height - y - 26;
        text(g, `240 simulated uploads: agreement, and whether the term was used (blue) or flat (grey)`, 16, y, { size: 10.5, colour: INK, opacity: four, max: width - 24 });
        uploads.rows.forEach(([group, a, used], k) => {
          const jitter = (((k * 29) % 31) / 31 - 0.5) * (h - 20);
          dot(g, 16 + bw * a, y + 12 + (h - 20) / 2 + jitter, 2.6, used ? ACCENT : '#AEB6BD', four);
        });
        line(g, 16 + bw * uploads.threshold.value, y + 6, 16 + bw * uploads.threshold.value, y + h, { colour: INK, dash: [4, 3], opacity: four });
        ['0%', '50%', '100%'].forEach((t, k) => text(g, t, 16 + bw * k / 2, y + h + 14, { size: 9.5, colour: FAINT, align: 'center', opacity: four }));
      }
      g.restore();
    }
  }, {
    describe: (state) => {
      const { detail } = ctx.detail(state);
      const c = topK(detail.guess.fused, 1)[0];
      return `Best guess ${names[c]} (${pct(detail.guess.fused[c])}); agreement ${pct(fusion.agreement)} against a ${pct(fusion.threshold)} gate, so the correlation term is ${fusion.correlation_term}.`;
    },
    table: (state) => buildGuessTable(ctx.detail(state).detail, names),
  });
}

// ---- 11: the answer, or the reason ----

const SANKEY_TARGETS = OUTCOME_ORDER;

export function answer(el, ctx) {
  const w = ctx.workflow;
  const names = w.class_order;
  const cells = w.trace.cells;
  const qhat = w.trace.stages.calibration.qhat;
  const ood = w.trace.stages.ood.threshold;
  const weak = [...new Set(cells.map((c) => c.weak_label ?? 'none'))];
  const flows = [];
  for (const s of weak) {
    for (const t of SANKEY_TARGETS) {
      const value = cells.filter((c) => (c.weak_label ?? 'none') === s && c.outcome === t).length;
      if (value) flows.push({ source: s, target: t, value });
    }
  }
  const outcomeColour = (k) => ({ class: ACCENT, group: '#3f86c0', lineage: '#8bb6da' }[k] ?? '#9AA6AF');
  return scene(el, ({ g, width, height }, p, state) => {
    const cell = ctx.cell(state);
    const { detail, own } = ctx.detail(state);
    const one = 1 - phase(p, 0.23, 0.29);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const probs = own ? detail.ensemble : null;
      const set = new Set(cell.candidate_set);
      const rowH = (height - 40) / names.length;
      const bw = width - 200;
      const grow = phase(p, 0, 0.12);
      const ticks = phase(p, 0.08, 0.18);
      text(g, own ? 'Mean probability per type, and each type’s bar' : 'Its top types (full arrays recorded for the story runs)', 8, 14, { size: 11, weight: 600, colour: INK, max: width - 16 });
      names.forEach((name, i) => {
        const y = 24 + i * rowH;
        const v = probs ? probs[i] : (cell.top.find(([c]) => c === i)?.[1] ?? 0);
        const inSet = set.has(i);
        text(g, short(name), 186, y + rowH * 0.75, { size: Math.min(10.5, rowH * 0.8), align: 'right', colour: inSet ? INK : SOFT, weight: inSet ? 600 : 400, max: 180 });
        bar(g, 192, y + rowH * 0.15, bw * v * grow, rowH * 0.7, inSet && ticks > 0.9 ? ACCENT : '#B9C9D6', 2);
        if (ticks > 0) line(g, 192 + bw * (1 - qhat[i]), y + 1, 192 + bw * (1 - qhat[i]), y + rowH - 1, { colour: INK, width: 1.5, opacity: ticks });
        if (cell.guess === i) dot(g, 192 + bw * v * grow + 9, y + rowH / 2, 4.5, '#FFFFFF', ticks, ACCENT);
      });
      g.restore();
    }
    const two = phase(p, 0.23, 0.29) * (1 - phase(p, 0.48, 0.54));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      const sims = cells.map((c) => c.similarity);
      const lo = Math.min(...sims, ood) - 0.01;
      const hi = 1;
      const x = (v) => 16 + ((v - lo) / (hi - lo)) * (width - 32);
      const mid = height / 2;
      text(g, 'Similarity to the nearest reference cell, every run', 8, 16, { size: 11.5, weight: 600, colour: INK });
      cells.forEach((c, i) => {
        const jitter = (((i * 41) % 37) / 37 - 0.5) * 120;
        const out = c.outcome === 'outside_supported_region';
        dot(g, x(c.similarity), mid + jitter, i === state.cell ? 6.5 : 3, out ? INK : alpha(ACCENT, 0.55), 1, i === state.cell ? INK : null);
      });
      line(g, x(ood), mid - 80, x(ood), mid + 80, { colour: INK, dash: [4, 3] });
      text(g, `threshold ${ood.toFixed(3)}`, x(ood) + 4, mid - 84, { size: 10.5, colour: INK });
      text(g, 'outside the reference', x(ood) - 4, mid + 96, { size: 10, colour: FAINT, align: 'right' });
      g.restore();
    }
    const three = phase(p, 0.48, 0.54) * (1 - phase(p, 0.73, 0.79));
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, 'Where the answer stops: type, group or lineage', 8, 16, { size: 11.5, weight: 600, colour: INK });
      const groups = [...new Set(names.map((n) => ctx.hierarchy[n].group))];
      const lineages = [...new Set(names.map((n) => ctx.hierarchy[n].lineage))];
      const cols = [[names, 0.04], [groups, 0.47], [lineages, 0.82]];
      const pos = {};
      cols.forEach(([list, fx]) => list.forEach((k, i) => { pos[k] = [8 + fx * (width - 16), 34 + (i + 0.5) * ((height - 44) / list.length)]; }));
      const hot = (kind, k) => cell.level === kind && cell.label === k;
      names.forEach((n) => {
        const { group, lineage } = ctx.hierarchy[n];
        const lit = hot('class', n) || hot('group', group) || hot('lineage', lineage);
        line(g, pos[n][0] + 100, pos[n][1], pos[group][0] - 4, pos[group][1], { colour: lit ? ACCENT : LINE, width: lit ? 2 : 1 });
      });
      groups.forEach((gr) => {
        const lin = ctx.hierarchy[names.find((n) => ctx.hierarchy[n].group === gr)].lineage;
        const lit = hot('group', gr) || hot('lineage', lin);
        line(g, pos[gr][0] + 110, pos[gr][1], pos[lin][0] - 4, pos[lin][1], { colour: lit ? ACCENT : LINE, width: lit ? 2 : 1 });
      });
      for (const [list, kind] of [[names, 'class'], [groups, 'group'], [lineages, 'lineage']]) {
        list.forEach((k) => text(g, kind === 'class' ? short(k) : k, pos[k][0], pos[k][1] + 4, { size: kind === 'class' ? 9.5 : 11, colour: hot(kind, k) ? ACCENT : INK, weight: hot(kind, k) ? 600 : 400, max: kind === 'class' ? 98 : 110 }));
      }
      if (!cell.level) chip(g, `no answer: ${OUTCOME_LABELS[cell.outcome]}`, width - 8, height - 18, { size: 11.5, align: 'right', border: INK });
      g.restore();
    }
    const four = phase(p, 0.76, 0.82);
    if (four > 0) {
      g.save();
      g.globalAlpha = four;
      const margin = Math.min(150, width * 0.26);
      const layout = sankey(flows, weak, SANKEY_TARGETS, { width: width - margin * 2 - 4, height: height - 40, gap: 6, node: 10 });
      const grow = phase(p, 0.8, 0.96);
      layout.links.forEach((l) => {
        const b = layout.right.find((n) => n.key === l.target);
        g.fillStyle = alpha(outcomeColour(l.target).startsWith('#') ? outcomeColour(l.target) : ACCENT, 0.3 * grow);
        g.fill(new Path2D(bandPath(margin + layout.node, 28 + l.y0, margin + lerp(layout.node, b.x, grow), 28 + lerp(l.y0, l.y1, grow), l.h)));
      });
      layout.left.forEach((nd) => {
        bar(g, margin, 28 + nd.y, layout.node, Math.max(1, nd.h), INK, 1);
        text(g, `${nd.key} (${nd.value})`, margin - 6, 28 + nd.y + nd.h / 2 + 4, { size: 10, align: 'right', colour: INK, max: margin - 8 });
      });
      layout.right.forEach((nd) => {
        bar(g, margin + nd.x, 28 + nd.y, layout.node, Math.max(1, nd.h), outcomeColour(nd.key), 1, grow);
        text(g, `${OUTCOME_LABELS[nd.key]} (${nd.value})`, margin + nd.x + layout.node + 6, 28 + nd.y + nd.h / 2 + 4, { size: 10, colour: INK, opacity: grow, max: margin - 10 });
      });
      text(g, 'Every run: marker-based label (weak, left) to outcome (right)', 8, 16, { size: 11.5, weight: 600, colour: INK });
      g.restore();
    }
  }, {
    describe: (state) => {
      const cell = ctx.cell(state);
      return `${cell.id}: ${cell.candidate_set.length} type${cell.candidate_set.length === 1 ? '' : 's'} clear their bars; ${ctx.answerText(cell)}.`;
    },
    table: () => buildOutcomeTable(w),
  });
}

// ---- 12: where the cell lands ----

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
    const cam = { width, height, scale: Math.min(width, height) * 0.6, distance: 4 };
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
      dot(g, q.x, q.y - (1 - drop) * 60, 2.4, colour, 0.85 * drop);
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
      chip(g, ctx.answerText(ctx.cell(state)), me.x + 12, me.y - (1 - fly) * 120 - 14, { size: 11, opacity: fly, border: ACCENT });
      if (own && fly > 0.9) {
        const props = Object.entries(detail.response.properties ?? {});
        props.forEach(([name, v], k) => text(g, `${name.replace(/_/g, ' ')}: ${v.value.toFixed(2)} ± ${v.uncertainty.toFixed(2)}`, 8, height - 8 - (props.length - 1 - k) * 15, { size: 10.5, colour: SOFT }));
      }
    }
    text(g, colourMode === 'class' ? 'Reference cells by type; uploaded runs by best guess. Drag to turn.' : 'Reference cells (RNA) and uploaded runs (protein). Drag to turn.', 8, 14, { size: 10.5, colour: FAINT, max: width - 16 });
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
      return `Run ${cell.id} lands at (${cell.xyz.map((v) => v.toFixed(2)).join(', ')}) among ${fc(w.reference.total.value)} reference cells (${fc(limit)} drawn).`;
    },
  });
}
