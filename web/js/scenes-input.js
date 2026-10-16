// The Workflow page's scenes for the input side: the cold open, the two kinds
// of data, the raw files, the gene space, the upload's first steps, matching
// and smoothing. Each is createScene(el, ctx) -> {render(p, state), resize(),
// dispose(), describe(state), table(state)}; a frame is a pure function of the
// chapter's progress p (0..1) and the followed cell, so scrolling, the film
// and scrubbing draw the same thing. Every value drawn comes from
// web/data/workflow.json (ctx.workflow); nothing here computes a model output.

import { formatCount } from './manifest.js';
import { escapeHtml } from './panels.js';
import { decodeBits, formatRecord, geneLookup, snippetRows } from './workflow-data.js';
import { buildPbmcTable, buildHeaderMorph } from './workflow-panels.js';
import { clamp, diverging, histogramBars, lerp, phase, sequential } from './workflow-layout.js';
import {
  ACCENT, BENCH, FAINT, INK, LINE, PROT, RNA, SOFT, alpha, bar, chip, dot, hatch, line, mountCanvas, short, text,
} from './scene-kit.js';

const fc = (x) => formatCount(x);
const compact = (v) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e4 ? `${Math.round(v / 1e3)}k` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}k` : `${Math.round(v)}`);

// A scene from a draw function: the canvas, the last frame kept for resizes.
function scene(el, draw, { describe = () => '', table = () => '', dispose = () => {} } = {}) {
  const view = mountCanvas(el);
  let last = null;
  const api = {
    render(p, state) {
      last = [p, state];
      view.clear();
      draw(view, clamp(p, 0, 1), state);
    },
    resize() { view.resize(); if (last) api.render(...last); },
    dispose() { dispose(); view.dispose(); },
    describe,
    table,
  };
  return api;
}

// ---- 0: one cell, start to end ----

const STOPS = ['file', 'scale', 'merge', 'match', 'mask', 'smooth', 'encode', 'probabilities', 'best guess', 'set', 'ladder', 'atlas'];

export function open(el, ctx) {
  return scene(el, ({ g, width, height }, p, state) => {
    const cell = ctx.cell(state);
    const { detail, own } = ctx.detail(state);
    const rows = own ? detail.raw_row : [];
    const colW = Math.min(150, width * 0.3);
    const tileH = Math.min(17, (height - 60) / 20);
    const shown = Math.floor(phase(p, 0, 0.3) * rows.length + 0.0001);
    const squeeze = phase(p, 0.3, 0.45);
    const target = [colW + 40, height * 0.62];
    text(g, own ? `Run ${cell.id}: the first protein groups of its column` : `Run ${cell.id}`, 8, 16, { size: 12, colour: FAINT, max: width - 16 });
    rows.forEach((r, i) => {
      if (i >= shown) return;
      const col = i < 20 ? 0 : 1;
      const x0 = 8 + col * (colW / 2 + 4);
      const y0 = 30 + (i % 20) * tileH;
      const x = x0;
      const y = y0;
      const w = colW / 2;
      const h = tileH - 2;
      const fade = 1 - squeeze * 0.55;
      if (squeeze > 0 && squeeze < 1) dot(g, lerp(x0 + w / 2, target[0], squeeze), lerp(y0 + h / 2, target[1], squeeze), 2.5, ACCENT, 1 - squeeze * 0.5);
      if (r[1] === null) hatch(g, x, y, w, h, fade);
      else bar(g, x, y, w, h, alpha(ACCENT, 0.12 + 0.55 * clamp(((r[2] ?? 0) - 8) / 14, 0, 1)), 2, fade);
      if (tileH > 11) text(g, `${r[0].split(';')[0]}`, x + 4, y + h - 4, { size: 9.5, colour: INK, max: w - 6, opacity: fade });
    });
    if (!own) text(g, 'Its raw column is recorded for the story runs only; pick one above to see it.', 8, 40, { size: 12, colour: SOFT, max: width * 0.5 });
    // The rail: the steps the cell passes through.
    const railY = height * 0.62;
    const x0 = colW + 40;
    const x1 = width - 24;
    line(g, x0, railY, x1, railY, { colour: LINE, width: 3 });
    const travel = phase(p, 0.45, 0.88);
    STOPS.forEach((name, i) => {
      const x = lerp(x0, x1, i / (STOPS.length - 1));
      const reached = travel * (STOPS.length - 1) >= i - 0.001;
      dot(g, x, railY, reached ? 6 : 4.5, reached ? ACCENT : '#FFFFFF', 1, reached ? null : LINE);
      text(g, name, x, railY + (i % 2 ? 24 : -14), { size: 10.5, colour: reached ? INK : FAINT, align: 'center' });
    });
    if (squeeze > 0.95) dot(g, lerp(x0, x1, travel), railY, 9, ACCENT, 1, '#FFFFFF');
    const end = phase(p, 0.88, 1);
    if (end > 0) {
      const answer = ctx.answerText(cell);
      chip(g, cell.level ? `Answer: ${answer}` : answer.replace(/^no/, "No"), x1, railY + 64, { size: 13, align: 'right', opacity: end, border: ACCENT });
      chip(g, `Best guess: ${ctx.guessText(cell)}`, x1, railY + 98, { size: 12, align: 'right', opacity: end, colour: SOFT });
    }
  }, {
    describe: (state) => {
      const cell = ctx.cell(state);
      return `Run ${cell.id} passes through ${STOPS.length} steps, from its raw column to ${ctx.answerText(cell)}.`;
    },
  });
}

// ---- 1: two kinds of data ----

export function data(el, ctx) {
  const w = ctx.workflow;
  const classes = w.reference.classes;
  const counts = classes.map((c) => c.cells.value);
  const lineages = [...new Set(classes.map((c) => c.lineage))];
  const byLineage = [...classes.keys()].sort((a, b) => (lineages.indexOf(classes[a].lineage) - lineages.indexOf(classes[b].lineage)) || (a - b));
  const sources = w.gene_space.sources;
  return scene(el, ({ g, width, height }, p) => {
    const opt = ctx.options('data');
    const log = !!opt.scale;
    const leftW = width * 0.6;
    const labelW = Math.min(130, leftW * 0.42);
    const top = 34;
    const row = (height - top - 8) / classes.length;
    const max = Math.max(...counts);
    const scale = (v) => (log ? Math.log10(v + 1) / Math.log10(max + 1) : v / max);
    const grow = phase(p, 0, 0.3);
    const group = opt.lineage ? 1 : phase(p, 0.36, 0.58);
    text(g, 'RNA reference: cells per type', 4, 16, { size: 12.5, weight: 600, colour: RNA });
    classes.forEach((c, i) => {
      const rank = lerp(i, byLineage.indexOf(i), group);
      const y = top + rank * row;
      text(g, short(c.name), labelW - 6, y + row * 0.7, { size: Math.min(11, row * 0.75), align: 'right', colour: INK, max: labelW - 8 });
      const bw = (leftW - labelW - 46) * scale(counts[i]) * grow;
      bar(g, labelW, y + row * 0.15, bw, row * 0.7, RNA, 2, 0.85);
      if (grow > 0.98) text(g, compact(counts[i]), labelW + bw + 4, y + row * 0.7, { size: 10, colour: FAINT });
    });
    if (group > 0.02) {
      lineages.forEach((l) => {
        const idx = byLineage.filter((i) => classes[i].lineage === l).map((i) => byLineage.indexOf(i));
        const y0 = top + Math.min(...idx) * row + 2;
        const y1 = top + (Math.max(...idx) + 1) * row - 2;
        line(g, leftW - 10, y0, leftW - 10, y1, { colour: INK, width: 2, opacity: group });
        text(g, l, leftW - 4, (y0 + y1) / 2 + 4, { size: 10.5, colour: INK, weight: 600, opacity: group });
      });
    }
    const right = phase(p, 0.66, 0.86);
    if (right > 0) {
      const x0 = leftW + 64;
      const rw = width - x0 - 8;
      text(g, 'Protein lists: genes in the space', x0, 16, { size: 12.5, weight: 600, colour: PROT, opacity: right, max: rw });
      const maxG = Math.max(...sources.map((s) => s.genes.value));
      sources.forEach((s, i) => {
        const y = top + 8 + i * Math.min(54, (height - top) / sources.length);
        text(g, s.name, x0, y + 10, { size: 11, colour: INK, opacity: right, max: rw });
        bar(g, x0, y + 16, (rw - 50) * (s.genes.value / maxG) * right, 10, PROT, 2, 0.85);
        text(g, fc(s.genes.value), x0 + (rw - 50) * (s.genes.value / maxG) * right + 4, y + 25, { size: 10, colour: FAINT, opacity: right });
        text(g, s.role, x0, y + 40, { size: 9.5, colour: FAINT, opacity: right, max: rw });
      });
    }
  }, {
    describe: () => `${classes.length} reference types, from ${fc(Math.max(...counts))} to ${fc(Math.min(...counts))} cells each, in ${lineages.length} lineages; six protein lists choose the genes.`,
    table: () => `<table class="support-table"><thead><tr><th>Type</th><th>Group</th><th>Lineage</th><th>Cells</th></tr></thead><tbody>${classes
      .map((c) => `<tr><td>${escapeHtml(c.name)}</td><td>${escapeHtml(c.group)}</td><td>${escapeHtml(c.lineage)}</td><td class="support-num">${fc(c.cells.value)}</td></tr>`).join('')}</tbody></table>`,
  });
}

// ---- 2: what the files look like ----

export function files(el, ctx) {
  const w = ctx.workflow;
  const details = w.trace.detail;
  const parse = w.raw.pbmc240.parse;
  const shownRows = snippetRows(details, 10);
  const names = shownRows.map((g) => details[0].raw_row[g][0]);
  return scene(el, ({ g, width, height }, p) => {
    const gridH = height * 0.56;
    const left = Math.min(120, width * 0.22);
    const cols = details.length;
    const cw = (width - left - 8) / cols;
    const rh = (gridH - 26) / names.length;
    const appear = phase(p, 0, 0.25);
    const pulse = p < 0.34 ? 0.55 + 0.45 * Math.abs(Math.sin(p * 30)) : 1;
    details.forEach((d, c) => {
      text(g, d.id.replace('Astral_TopMedPBMC1_', ''), left + c * cw + cw / 2, 14, { size: 10, align: 'center', colour: INK, max: cw - 4 });
    });
    names.forEach((name, r) => {
      const y = 22 + r * rh;
      if (r / names.length > appear) return;
      text(g, name.split(';')[0], left - 6, y + rh * 0.68, { size: 10.5, align: 'right', colour: INK, max: left - 8 });
      details.forEach((d, c) => {
        const v = d.raw_row[shownRows[r]]?.[1];
        const x = left + c * cw + 2;
        if (v === null || v === undefined) hatch(g, x, y + 2, cw - 4, rh - 4, pulse);
        else {
          bar(g, x, y + 2, cw - 4, rh - 4, BENCH, 3);
          text(g, compact(v), x + (cw - 4) / 2, y + rh * 0.66, { size: 10, align: 'center', colour: INK });
        }
      });
    });
    // The headers: instrument paths become run names.
    const morph = phase(p, 0.36, 0.62);
    const ex = parse.header_examples.slice(0, 3);
    const yH = gridH + 10;
    if (p > 0.33) {
      text(g, 'Column headers', 4, yH + 4, { size: 11.5, weight: 600, colour: INK, opacity: phase(p, 0.33, 0.4) });
      ex.forEach(([raw, clean], i) => {
        const y = yH + 22 + i * 18;
        text(g, raw, 4, y, { size: 10, colour: FAINT, opacity: 1 - morph, max: width - 8 });
        text(g, `→ ${clean}`, 4, y, { size: 10.5, colour: ACCENT, weight: 500, opacity: morph, max: width - 8 });
      });
    }
    // Detection: proteins per run, and runs per protein.
    const hist = phase(p, 0.68, 0.9);
    if (hist > 0) {
      const y0 = gridH + 84;
      const hh = height - y0 - 22;
      const halfW = (width - 24) / 2;
      [[parse.proteins_per_run, 'protein groups seen per run'], [parse.runs_per_protein, 'share of runs that see each protein group']]
        .forEach(([h, label], k) => {
          const x0 = 4 + k * (halfW + 16);
          histogramBars(h.counts, halfW, hh * hist).forEach((b) => bar(g, x0 + b.x, y0 + hh - b.h, b.w, b.h, ACCENT, 1, 0.75));
          line(g, x0, y0 + hh, x0 + halfW, y0 + hh, { colour: LINE });
          text(g, label, x0, y0 + hh + 14, { size: 10, colour: FAINT, max: halfW });
        });
    }
  }, {
    describe: () => `${fc(parse.rows)} protein groups by ${fc(parse.runs)} runs; ${formatRecord(w.facts.missing_share)} of values blank (hatched).`,
    table: () => buildPbmcTable(w) + buildHeaderMorph(w),
  });
}

// ---- 3: one vocabulary of genes ----

export function genes(el, ctx) {
  const w = ctx.workflow;
  const gs = w.gene_space;
  const f = gs.funnel;
  return scene(el, ({ g, width, height }, p) => {
    const one = 1 - phase(p, 0.62, 0.7);
    const sources = gs.sources;
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const laneH = (height - 40) / sources.length;
      const maxS = Math.max(...sources.map((s) => s.genes.value));
      const grow = phase(p, 0, 0.18);
      const bx = Math.min(170, width * 0.32);
      sources.forEach((s, i) => {
        const y = 20 + i * laneH;
        text(g, s.name, 4, y + laneH * 0.42, { size: 10.5, colour: INK, max: bx - 8 });
        bar(g, 4, y + laneH * 0.5, (bx - 50) * (s.genes.value / maxS) * grow, Math.min(10, laneH * 0.25), PROT, 2, 0.85);
        text(g, compact(s.genes.value), 8 + (bx - 50) * (s.genes.value / maxS) * grow, y + laneH * 0.5 + 9, { size: 9.5, colour: FAINT });
      });
      // The genes flow into the union, lose the IG/TCR segments, meet RNA.
      const flow = phase(p, 0.12, 0.36);
      const ux = bx + (width - bx) * 0.32;
      const fx = bx + (width - bx) * 0.8;
      const cy = height / 2;
      for (let k = 0; k < 90; k += 1) {
        const lane = k % sources.length;
        const t = clamp(flow * 1.6 - (k / 90) * 0.6, 0, 1);
        if (t <= 0 || t >= 1) continue;
        const y0 = 20 + lane * laneH + laneH * 0.55;
        dot(g, lerp(bx - 30, ux, t), lerp(y0, cy, t * t), 2.2, PROT, 0.6);
      }
      const box = (x, label, value, colour, show) => {
        if (show <= 0) return;
        chip(g, value, x, cy - 10, { size: 15, align: 'center', opacity: show, border: colour });
        text(g, label, x, cy + 24, { size: 10.5, align: 'center', colour: FAINT, opacity: show, max: 150 });
      };
      box(ux, 'genes named', formatRecord(f.union), PROT, phase(p, 0.2, 0.3));
      const cut = phase(p, 0.28, 0.36);
      if (cut > 0) {
        chip(g, `− ${formatRecord(f.ig_tcr_excluded)}`, ux, cy + 58, { size: 11, align: 'center', opacity: cut, colour: SOFT });
        text(g, 'immunoglobulin and T-cell receptor segments', ux, cy + 82, { size: 9.5, align: 'center', colour: FAINT, opacity: cut, max: 170 });
      }
      const meet = phase(p, 0.36, 0.55);
      if (meet > 0) {
        line(g, ux + 46, cy - 10, fx - 52, cy - 10, { colour: LINE, width: 2, opacity: meet });
        chip(g, `RNA: ${formatRecord(f.rna_genes)} genes`, (ux + fx) / 2, cy - 52, { size: 11, align: 'center', colour: RNA, opacity: meet, border: RNA });
        box(fx, 'the shared vocabulary', formatRecord(f.feature_space), ACCENT, phase(p, 0.45, 0.58));
      }
      g.restore();
    }
    const two = phase(p, 0.66, 0.78);
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      // The UpSet strip: the commonest combinations of sources.
      const combos = gs.combinations.slice(0, 9);
      const left = Math.min(150, width * 0.28);
      const cw = Math.min(40, (width * 0.62 - left) / combos.length);
      const barH = height * 0.42;
      const maxC = Math.max(...combos.map((c) => c.genes));
      text(g, 'Genes by which lists name them', 4, 14, { size: 11.5, weight: 600, colour: INK });
      combos.forEach((c, i) => {
        const x = left + i * cw;
        const h = (c.genes / maxC) * barH;
        bar(g, x + 5, 40 + barH - h, cw - 10, h, ACCENT, 2, 0.8);
        text(g, compact(c.genes), x + cw / 2, 36 + barH - h, { size: 9, colour: FAINT, align: 'center' });
        [...c.sources].forEach((bit, k) => dot(g, x + cw / 2, 56 + barH + k * 15, 4, bit === '1' ? INK : LINE));
      });
      sources.forEach((s, k) => text(g, s.name, left - 6, 60 + barH + k * 15, { size: 9.5, colour: INK, align: 'right', max: left - 8 }));
      // Module sizes.
      const mx = left + combos.length * cw + 24;
      const mw = width - mx - 6;
      if (mw > 80) {
        text(g, `${formatRecord(w.facts.modules)} modules, by size`, mx, 14, { size: 11.5, weight: 600, colour: INK, max: mw });
        const mh = gs.module_sizes;
        histogramBars(mh.counts, mw, barH).forEach((b, i) => {
          bar(g, mx + b.x, 40 + barH - b.h, b.w, b.h, ACCENT, 1, 0.6);
          text(g, String(mh.edges[i]), mx + b.x + b.w / 2, 54 + barH, { size: 8.5, colour: FAINT, align: 'center' });
        });
        text(g, 'genes per module (bin start)', mx, 68 + barH, { size: 9.5, colour: FAINT, max: mw });
      }
      const hit = geneLookup(w, ctx.options('genes').gene ?? '');
      if (hit) {
        const y = height - 26;
        chip(g, `${hit.gene}: ${hit.sources.join(', ') || 'in the space'}`, 4, y, { size: 11.5, border: ACCENT, opacity: two });
      }
      g.restore();
    }
  }, {
    describe: () => `${formatRecord(f.union)} genes named, ${formatRecord(f.union_without_ig_tcr)} after the immune receptor segments, ${formatRecord(f.feature_space)} shared with RNA.`,
    table: () => `<table class="support-table"><thead><tr><th>Lists</th><th>Genes</th></tr></thead><tbody>${gs.combinations.slice(0, 20)
      .map((c) => `<tr><td>${escapeHtml(gs.sources.filter((_, k) => c.sources[k] === '1').map((s) => s.name).join(', '))}</td><td class="support-num">${fc(c.genes)}</td></tr>`).join('')}</tbody></table>`,
  });
}

// ---- 5: an upload arrives ----

export function upload(el, ctx) {
  const w = ctx.workflow;
  const raw = w.raw.pbmc240;
  return scene(el, ({ g, width, height }, p) => {
    const one = 1 - phase(p, 0.31, 0.37);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const h = height * 0.62;
      const toLog = phase(p, 0.14, 0.3);
      const draw = (hist, label, op, marker, threshold) => {
        if (op <= 0) return;
        const edges = hist.edges;
        const bars = histogramBars(hist.counts, width - 16, h);
        bars.forEach((b) => bar(g, 8 + b.x, 30 + h - b.h, b.w, b.h, ACCENT, 1, 0.7 * op));
        line(g, 8, 30 + h, width - 8, 30 + h, { colour: LINE, opacity: op });
        const x = (v) => 8 + ((v - edges[0]) / (edges[edges.length - 1] - edges[0])) * (width - 16);
        for (let k = 0; k < edges.length; k += Math.ceil(edges.length / 8)) text(g, String(edges[k]), x(edges[k]), 44 + h, { size: 9.5, colour: FAINT, align: 'center', opacity: op });
        text(g, label, width / 2, 62 + h, { size: 10.5, colour: FAINT, align: 'center', opacity: op });
        if (marker) {
          line(g, x(marker[0]), 26, x(marker[0]), 30 + h, { colour: INK, dash: [4, 3], opacity: op });
          text(g, marker[1], x(marker[0]) + 4, 24, { size: 10.5, colour: INK, opacity: op });
        }
        if (threshold) {
          line(g, x(threshold[0]), 26, x(threshold[0]), 30 + h, { colour: FAINT, dash: [2, 3], opacity: op });
          text(g, threshold[1], x(threshold[0]) - 4, 24, { size: 10, colour: FAINT, align: 'right', opacity: op });
        }
      };
      draw(raw.scale.linear_log10, 'log10 of the file’s values', 1 - toLog,
        [Math.log10(raw.scale.median_observed), `median ${raw.scale.median_observed.toLocaleString('en-US')}`],
        [Math.log10(raw.scale.threshold), `${raw.scale.threshold}`]);
      draw(raw.scale.log2, 'after log2, what the service reads', toLog, null, null);
      text(g, toLog < 0.5 ? 'Linear intensities, as the file holds them' : 'Log2', 8, 14, { size: 11.5, weight: 600, colour: INK });
      g.restore();
    }
    const two = phase(p, 0.31, 0.37) * (1 - phase(p, 0.64, 0.7));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      const ex = raw.collapse.examples;
      text(g, `Genes on several rows, merged: cells seen by the best row, then by the merge`, 8, 14, { size: 11.5, weight: 600, colour: INK, max: width - 16 });
      const rowH = Math.min(44, (height - 40) / ex.length);
      const maxC = Math.max(...ex.map((e) => e.merged_cells));
      const bw = width - 150;
      ex.forEach((e, i) => {
        const y = 32 + i * rowH;
        text(g, `${e.gene} (${e.rows} rows)`, 8, y + 14, { size: 11, colour: INK });
        bar(g, 130, y + 4, bw * (e.best_single_row_cells / maxC), 9, LINE, 2);
        bar(g, 130, y + 16, bw * (e.merged_cells / maxC) * phase(p, 0.4, 0.55), 9, ACCENT, 2, 0.85);
        text(g, `${e.best_single_row_cells} → ${e.merged_cells}`, 130 + bw * (e.merged_cells / maxC) + 6, y + 24, { size: 9.5, colour: FAINT });
      });
      g.restore();
    }
    const three = phase(p, 0.64, 0.72);
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      const ids = raw.ids;
      const total = ids.matched + ids.unmapped + ids.ambiguous;
      const parts = [['match one gene', ids.matched, ACCENT], ['name several', ids.ambiguous, INK], ['match none', ids.unmapped, '#9AA6AF']];
      text(g, 'Each row’s name, matched to the gene space', 8, 14, { size: 11.5, weight: 600, colour: INK });
      let x = 8;
      const bw = width - 16;
      const fill = phase(p, 0.68, 0.86);
      parts.forEach(([label, n, colour], k) => {
        const segW = (n / total) * bw * fill;
        bar(g, x, 30, segW, 26, colour, 2, 0.9);
        text(g, `${fc(n)} ${label}`, 8, 80 + k * 18, { size: 11, colour });
        x += segW;
      });
      const examples = [['name several', ids.ambiguous_examples.slice(0, 6)], ['match none', ids.unmapped_examples.slice(0, 6)]];
      examples.forEach(([label, list], k) => {
        const y = 150 + k * (height - 150) / 2;
        text(g, `Some that ${label}:`, 8, y, { size: 10.5, colour: FAINT });
        list.forEach((id, j) => text(g, id, 8, y + 16 + j * 14, { size: 10, colour: SOFT, max: width - 16 }));
      });
      g.restore();
    }
  }, {
    describe: () => `Median value ${raw.scale.median_observed.toLocaleString('en-US')}, so the file is read as linear and log2-transformed; ${raw.collapse.genes_merged} genes merged; ${fc(raw.ids.matched)} rows matched.`,
    table: () => `<table class="support-table"><tbody>`
      + `<tr><td>Scale detected</td><td>${escapeHtml(raw.scale.detected)}, ${raw.scale.transformed ? 'log2 taken' : 'left as is'}</td></tr>`
      + `<tr><td>Rows before and after merging</td><td>${fc(raw.collapse.rows_before)}, ${fc(raw.collapse.rows_after)}</td></tr>`
      + `<tr><td>Rows matched, ambiguous, unmapped</td><td>${fc(raw.ids.matched)}, ${fc(raw.ids.ambiguous)}, ${fc(raw.ids.unmapped)}</td></tr>`
      + `</tbody></table>`,
  });
}

// ---- 6: matching and the mask ----

export function matching(el, ctx) {
  const w = ctx.workflow;
  const align = w.raw.pbmc240.align;
  const n = align.feature_space;
  const matched = decodeBits(align.matched_bits, n);
  const cells = w.trace.cells;
  const hm = w.trace.heatmap;
  const observedCache = new Map();
  const observedOf = (detail) => {
    if (!observedCache.has(detail.cell)) observedCache.set(detail.cell, decodeBits(detail.observed_bits, n));
    return observedCache.get(detail.cell);
  };
  const log2Range = (() => {
    const vals = hm.log2.flat().filter((v) => v !== null);
    return [Math.min(...vals), Math.max(...vals)];
  })();
  return scene(el, ({ g, width, height }, p, state) => {
    const cell = ctx.cell(state);
    const { detail, own } = ctx.detail(state);
    const one = 1 - phase(p, 0.31, 0.37);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      const cols = Math.ceil(Math.sqrt(n * (width / (height - 40))));
      const size = Math.min((width - 8) / cols, (height - 44) / Math.ceil(n / cols));
      const fillM = phase(p, 0, 0.16);
      const fillC = phase(p, 0.14, 0.3);
      const obs = own ? observedOf(detail) : null;
      for (let i = 0; i < n; i += 1) {
        const x = 4 + (i % cols) * size;
        const y = 36 + Math.floor(i / cols) * size;
        let colour = '#EEF0F2';
        if (matched[i] && i / n <= fillM) colour = '#BFD5E6';
        if (obs && obs[i] && i / n <= fillC) colour = ACCENT;
        g.fillStyle = colour;
        g.fillRect(x, y, Math.max(0.6, size - 0.6), Math.max(0.6, size - 0.6));
      }
      text(g, `${fc(n)} genes: grey not in the file, pale blue in the file, blue observed in this cell${own ? '' : ' (recorded for the story runs)'}`, 4, 14, { size: 11, colour: INK, max: width - 8 });
      text(g, `this cell: ${fc(cell.observed)} observed`, 4, 28, { size: 10.5, colour: FAINT });
      g.restore();
    }
    const two = phase(p, 0.31, 0.37) * (1 - phase(p, 0.64, 0.7));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      const max = Math.max(...cells.map((c) => c.observed));
      const x = (v) => 24 + (v / max) * (width - 48);
      const mid = height / 2;
      text(g, 'Observed genes per cell, all runs', 8, 18, { size: 11.5, weight: 600, colour: INK });
      line(g, 24, mid + 40, width - 24, mid + 40, { colour: LINE });
      cells.forEach((c, i) => {
        const jitter = ((i * 37) % 23) - 11;
        const below = c.observed < align.floor;
        dot(g, x(c.observed), mid + jitter * 2.4, i === state.cell ? 6 : 3, below ? INK : alpha(ACCENT, 0.6), 1, i === state.cell ? INK : null);
      });
      line(g, x(align.floor), mid - 50, x(align.floor), mid + 46, { colour: INK, dash: [4, 3] });
      text(g, `floor ${align.floor}`, x(align.floor) + 4, mid - 40, { size: 10.5, colour: INK });
      for (const v of [0, 500, 1000, 1500, 2000].filter((t) => t <= max)) text(g, String(v), x(v), mid + 56, { size: 9.5, colour: FAINT, align: 'center' });
      g.restore();
    }
    const three = phase(p, 0.64, 0.72);
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      const z = phase(p, 0.74, 0.94);
      const left = 64;
      const cw = (width - left - 6) / hm.cells.length;
      const rh = (height - 52) / hm.genes.length;
      text(g, z < 0.5 ? 'Log2 values, as merged' : 'Scaled within the upload (mean 0, spread 1)', left, 14, { size: 11.5, weight: 600, colour: INK });
      hm.genes.forEach((gene, r) => text(g, gene, left - 4, 30 + r * rh + rh * 0.75, { size: Math.min(10, rh * 0.85), align: 'right', colour: INK }));
      hm.cells.forEach((ci, c) => {
        hm.genes.forEach((_, r) => {
          const x = left + c * cw;
          const y = 22 + r * rh;
          const raw = hm.log2[c][r];
          if (!hm.mask[c][r] || raw === null) { hatch(g, x, y, cw - 0.8, rh - 0.8); return; }
          const a = sequential((raw - log2Range[0]) / (log2Range[1] - log2Range[0] || 1));
          const b = diverging(hm.z[c][r]);
          g.fillStyle = z < 1 ? (z > 0 ? mixHex(a, b, z) : a) : b;
          g.fillRect(x, y, cw - 0.8, rh - 0.8);
        });
        if (ci === state.cell) {
          g.strokeStyle = INK;
          g.lineWidth = 2;
          g.strokeRect(left + c * cw - 1, 21, cw + 1, hm.genes.length * rh + 1);
        }
      });
      text(g, 'cells (the story runs first); hatched: missing', left, height - 8, { size: 10, colour: FAINT });
      g.restore();
    }
  }, {
    describe: (state) => `This cell observed ${fc(ctx.cell(state).observed)} of ${fc(n)} genes; the upload measures ${fc(align.matched)}; floor ${align.floor}.`,
    table: () => `<table class="support-table"><thead><tr><th>Run</th><th>Observed genes</th></tr></thead><tbody>${cells
      .map((c) => `<tr><td><code>${escapeHtml(c.id)}</code></td><td class="support-num">${fc(c.observed)}</td></tr>`).join('')}</tbody></table>`,
  });
}

function mixHex(a, b, t) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return `rgb(${pa.map((v, i) => Math.round(lerp(v, pb[i], t))).join(',')})`;
}

// ---- 7: smoothing on the upload's own neighbours ----

const WEAK_CLASS = { 'T cell': 2, 'NK cell': 15, Monocyte: 12, Dendritic: 13, Platelet: 20 };

export function smoothing(el, ctx) {
  const w = ctx.workflow;
  const cells = w.trace.cells;
  const sm = w.trace.stages.smoothing;
  const hm = w.trace.heatmap;
  const xs = cells.map((c) => c.layout[0]);
  const ys = cells.map((c) => c.layout[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  return scene(el, ({ g, width, height }, p, state) => {
    const i = state.cell;
    const rowsShown = phase(p, 0.33, 0.45);
    const graphH = height * lerp(0.95, 0.6, rowsShown);
    const sx = (v) => 14 + ((v - x0) / (x1 - x0 || 1)) * (width - 28);
    const sy = (v) => 14 + (1 - (v - y0) / (y1 - y0 || 1)) * (graphH - 28);
    const grow = phase(p, 0.06, 0.3);
    sm.neighbours[i].forEach((j, k) => {
      const t = clamp(grow * 1.5 - k / sm.neighbours[i].length * 0.5, 0, 1);
      if (t <= 0) return;
      const ax = sx(cells[i].layout[0]);
      const ay = sy(cells[i].layout[1]);
      line(g, ax, ay, lerp(ax, sx(cells[j].layout[0]), t), lerp(ay, sy(cells[j].layout[1]), t), { colour: ACCENT, width: 0.6 + 7 * sm.weights[i][k], opacity: 0.55 });
    });
    cells.forEach((c, k) => {
      const cls = WEAK_CLASS[c.weak_label];
      const colour = cls === undefined ? '#AEB6BD' : ctx.classColour(cls);
      const isN = sm.neighbours[i].includes(k);
      dot(g, sx(c.layout[0]), sy(c.layout[1]), k === i ? 7 : isN ? 4 : 2.6, colour, k === i || isN ? 1 : 0.7, k === i ? INK : null);
    });
    text(g, 'Each dot a run, placed by its proteins; colour: marker-based label (weak)', 8, 12, { size: 10.5, colour: FAINT, max: width - 16 });
    if (rowsShown > 0) {
      const at = hm.cells.indexOf(i);
      const c = at >= 0 ? at : 0;
      const y = graphH + 8;
      const left = 124;
      const cw = (width - left - 8) / hm.genes.length;
      const rh = Math.min(22, (height - y - 30) / 3.6);
      g.save();
      g.globalAlpha = rowsShown;
      const blend = phase(p, 0.45, 0.62);
      const rows = [['own value', hm.z[c], 1], ['smoothed', hm.smoothed[c], blend]];
      rows.forEach(([label, vals, op], r) => {
        text(g, label, left - 6, y + r * (rh + 6) + rh * 0.7, { size: 10.5, align: 'right', colour: INK, opacity: op });
        vals.forEach((v, k) => {
          g.globalAlpha = rowsShown * op;
          g.fillStyle = diverging(v) ?? BENCH;
          g.fillRect(left + k * cw, y + r * (rh + 6), cw - 1, rh);
        });
        g.globalAlpha = rowsShown;
      });
      const maskOp = phase(p, 0.7, 0.85);
      if (maskOp > 0) {
        const r = 2;
        text(g, 'mask (unchanged)', left - 6, y + r * (rh + 6) + rh * 0.7, { size: 10.5, align: 'right', colour: INK, opacity: maskOp });
        hm.mask[c].forEach((m, k) => bar(g, left + k * cw, y + r * (rh + 6), cw - 1, rh, m ? INK : BENCH, 1, maskOp));
      }
      hm.genes.forEach((gene, k) => text(g, gene, left + k * cw + cw / 2, y + 3 * (rh + 6) + 10, { size: Math.min(9, cw * 0.32), align: 'center', colour: FAINT, max: cw }));
      if (at < 0) text(g, `(this run is not in the heatmap sample; showing ${cells[hm.cells[0]].id})`, 8, height - 4, { size: 9.5, colour: FAINT, max: width - 16 });
      g.restore();
    }
  }, {
    describe: (state) => `Run ${ctx.cell(state).id} and its ${sm.k} nearest runs; lines are as thick as their weights.`,
    table: (state) => `<table class="support-table"><thead><tr><th>Neighbour</th><th>Weight</th></tr></thead><tbody>${sm.neighbours[state.cell]
      .map((j, k) => `<tr><td><code>${escapeHtml(cells[j].id)}</code></td><td class="support-num">${sm.weights[state.cell][k].toFixed(3)}</td></tr>`).join('')}</tbody></table>`,
  });
}
