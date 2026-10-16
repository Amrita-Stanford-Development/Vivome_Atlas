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
import { clamp, distanceForOverlap, diverging, histogramBars, lerp, phase, sequential, ticks } from './workflow-layout.js';
import { rng } from './random.js';
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
      const answer = ctx.answerShort(cell);
      chip(g, cell.level ? `Answer: ${answer}` : answer, x1, railY + 64, { size: 13, align: 'right', opacity: end, border: ACCENT });
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
// Beat 1: a crowd of reference cells settles into the atlas map, one colour
// per type. Beat 2: the types fold into their family tree (type, family,
// branch), with the branch of the followed cell's best guess lit. Beat 3:
// the two sides: the labelled RNA map, and one protein measurement with its
// blanks and no type; the protein lists choose the genes both sides read.

export function data(el, ctx) {
  const w = ctx.workflow;
  const classes = w.reference.classes;
  const names = w.class_order;
  const lineages = [...new Set(classes.map((c) => c.lineage))];
  const groupsOf = (l) => [...new Set(classes.filter((c) => c.lineage === l).map((c) => c.group))];
  const order = [...classes.keys()].sort((a, b) => (lineages.indexOf(classes[a].lineage) - lineages.indexOf(classes[b].lineage))
    || (groupsOf(classes[a].lineage).indexOf(classes[a].group) - groupsOf(classes[b].lineage).indexOf(classes[b].group))
    || (a - b));
  const groupKeys = lineages.flatMap((l) => groupsOf(l).map((gr) => [l, gr]));
  const narrow = window.matchMedia?.('(max-width: 820px)').matches;
  const pts = w.reference.sample.slice(0, narrow ? 700 : 1400);
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const r = rng(21);
  const scatter = pts.map(() => [r(), r()]);
  const total = w.reference.total.value;
  const featureSpace = w.raw.pbmc240.align.feature_space;
  const sources = w.gene_space.sources;
  const fit = (wd, ht, ox, oy) => {
    const s = Math.min(wd / (x1 - x0), ht / (y1 - y0));
    return { s, ox: ox + (wd - (x1 - x0) * s) / 2, oy: oy + (ht - (y1 - y0) * s) / 2 };
  };
  const at = (box, q) => [box.ox + (q[0] - x0) * box.s, box.oy + (y1 - q[1]) * box.s];
  return scene(el, ({ g, width, height }, p, state) => {
    const cell = ctx.cell(state);
    const settle = phase(p, 0, 0.28);
    const toTree = phase(p, 0.34, 0.5);
    const links = phase(p, 0.44, 0.62);
    const toSides = phase(p, 0.67, 0.76);
    const lists = phase(p, 0.8, 0.95);
    const full = fit(width - 24, height - 76, 12, 50);
    const sideH = height * 0.52;
    const mini = fit(width * 0.42 - 24, sideH - 40, 12, 64);
    const rowH = (height - 58) / names.length;
    const treeX = Math.min(200, width * 0.36);
    const rowY = (i) => 50 + order.indexOf(i) * rowH + rowH / 2;
    const gx = treeX + (width - treeX) * 0.42;
    const lx = treeX + (width - treeX) * 0.76;
    const mean = (list) => list.reduce((s, v) => s + v, 0) / list.length;
    const groupY = Object.fromEntries(groupKeys.map(([l, gr]) => [`${l}|${gr}`,
      mean(order.filter((i) => classes[i].lineage === l && classes[i].group === gr).map(rowY))]));
    const lineageY = Object.fromEntries(lineages.map((l) => [l, mean(order.filter((i) => classes[i].lineage === l).map(rowY))]));
    const guess = cell.guess;
    const hot = guess === null || guess === undefined ? null : classes[guess];

    // The cells: scattered, then on the map, then into their type's row, then onto the small map.
    const treeOp = toTree * (1 - toSides);
    pts.forEach((q, i) => {
      const c = q[3];
      const te = clamp(settle * 1.5 - (i / pts.length) * 0.5, 0, 1);
      const e1 = te * te * (3 - 2 * te);
      const [mx, my] = at(full, q);
      let x = lerp(12 + scatter[i][0] * (width - 24), mx, e1);
      let y = lerp(50 + scatter[i][1] * (height - 76), my, e1);
      x = lerp(x, treeX + 10, toTree);
      y = lerp(y, rowY(c), toTree);
      const [sx, sy] = at(mini, q);
      x = lerp(x, sx, toSides);
      y = lerp(y, sy, toSides);
      const colour = mixHex('#B9C2C9', ctx.classColour(c), e1);
      const op = lerp(lerp(0.8, 0.12, toTree), 0.7, toSides);
      dot(g, x, y, lerp(2.3, 1.6, toSides), colour, op);
    });

    // Beat 1: the counter and the largest types' names.
    const labels = phase(settle, 0.75, 1) * (1 - toTree);
    if (settle > 0) {
      text(g, `${fc(total)} example cells with known types (a sample is drawn; one dot is one cell)`, 12, 20,
        { size: 12, weight: 600, colour: RNA, opacity: 1 - toTree, max: width - 24 });
    }
    if (labels > 0) {
      const placed = [];
      [...classes.keys()].filter((i) => classes[i].cells.value >= 2000 && w.reference.centres[i]).forEach((i) => {
        const [cx, cy] = at(full, w.reference.centres[i].map((v) => v / 1000));
        const label = short(names[i]);
        const half = label.length * 3.2 + 8;
        if (placed.some((b) => Math.abs(b[0] - cx) < b[2] + half && Math.abs(b[1] - cy) < 18)) return;
        placed.push([cx, cy, half]);
        chip(g, label, cx, cy, { size: 10.5, align: 'center', opacity: labels });
      });
    }

    // Beat 2: the family tree.
    if (treeOp > 0) {
      g.save();
      g.globalAlpha = treeOp;
      text(g, 'The types as a family tree', 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      text(g, 'type', treeX - 6, 38, { size: 10.5, colour: FAINT, align: 'right' });
      text(g, 'family', gx, 38, { size: 10.5, colour: FAINT, align: 'center' });
      text(g, 'branch', lx, 38, { size: 10.5, colour: FAINT, align: 'center' });
      order.forEach((i) => {
        const y = rowY(i);
        const lit = hot && i === guess;
        text(g, short(names[i]), treeX - 6, y + 4, { size: Math.min(11, rowH * 0.78), align: 'right', colour: lit ? ACCENT : INK, weight: lit ? 600 : 400, max: treeX - 10 });
        dot(g, treeX + 10, y, Math.min(4.5, rowH * 0.3), ctx.classColour(i));
        text(g, compact(classes[i].cells.value), treeX + 20, y + 4, { size: 9.5, colour: FAINT });
        const key = `${classes[i].lineage}|${classes[i].group}`;
        const sx = treeX + 52;
        line(g, sx, y, lerp(sx, gx - 8, links), lerp(y, groupY[key], links), { colour: lit ? ACCENT : LINE, width: lit ? 2.4 : 1 });
      });
      const groupLinks = phase(p, 0.52, 0.64);
      groupKeys.forEach(([l, gr]) => {
        const y = groupY[`${l}|${gr}`];
        const lit = hot && hot.group === gr && hot.lineage === l;
        text(g, gr, gx, y + 4, { size: 11, align: 'center', colour: lit ? ACCENT : INK, weight: lit ? 600 : 500, opacity: links, max: (lx - gx) * 0.9 });
        line(g, gx + 46, y, lerp(gx + 46, lx - 34, groupLinks), lerp(y, lineageY[l], groupLinks), { colour: lit ? ACCENT : LINE, width: lit ? 2.4 : 1 });
      });
      lineages.forEach((l) => {
        const lit = hot && hot.lineage === l;
        text(g, l, lx, lineageY[l] + 4, { size: 12, align: 'center', colour: lit ? ACCENT : INK, weight: 600, opacity: groupLinks });
      });
      if (hot && links > 0.95) chip(g, 'our cell\u2019s best guess', treeX + 52, rowY(guess) - rowH * 0.9, { size: 10, colour: ACCENT, border: ACCENT, opacity: phase(p, 0.6, 0.66) });
      g.restore();
    }

    // Beat 3: the two sides, and the lists that link them.
    if (toSides > 0) {
      g.save();
      g.globalAlpha = toSides;
      text(g, 'Learned from: RNA, every cell named', 12, 40, { size: 12.5, weight: 600, colour: RNA, max: width * 0.44 });
      chip(g, `${names.length} types`, 12, sideH + 34, { size: 10.5, colour: RNA, border: RNA });
      const px = width * 0.5;
      const pw = width - px - 12;
      text(g, 'Used on: proteins of one cell, no name', px, 40, { size: 12.5, weight: 600, colour: PROT, max: pw });
      const { detail, own } = ctx.detail(state);
      // A typical stretch of the cell's column: rows other cells also see, and some they miss.
      const rows = detail ? snippetRows(w.trace.detail, 24).map((k) => detail.raw_row[k]) : [];
      const tileW = (pw - 6) / 2;
      const tileH = Math.min(17, (sideH - 60) / 12);
      rows.forEach((row, k) => {
        const x = px + (k % 2) * (tileW + 6);
        const y = 52 + Math.floor(k / 2) * tileH;
        if (row[1] === null) hatch(g, x, y, tileW, tileH - 2);
        else bar(g, x, y, tileW, tileH - 2, alpha(PROT, 0.18 + 0.5 * clamp(((row[2] ?? 0) - 8) / 14, 0, 1)), 2);
        if (tileH > 11) text(g, row[0].split(';')[0], x + 4, y + tileH - 5, { size: 9, colour: INK, max: tileW - 8 });
      });
      const below = 52 + 12 * tileH + 18;
      chip(g, 'type: ?', px, below, { size: 11, colour: PROT, border: PROT });
      text(g, `our cell: ${fc(cell.observed)} of ${fc(featureSpace)} genes measured`, px + 66, below + 4, { size: 10.5, colour: SOFT, max: pw - 70 });
      hatch(g, px, below + 18, 22, 10);
      text(g, 'striped: not seen in this cell', px + 28, below + 27, { size: 10, colour: FAINT, max: pw - 30 });
      g.restore();
    }
    if (lists > 0) {
      g.save();
      g.globalAlpha = lists;
      const top = sideH + 64;
      const avail = height - top - 8;
      text(g, 'Six lists of proteins from earlier experiments choose the genes used on both sides', 12, top, { size: 11.5, weight: 600, colour: INK, max: width - 24 });
      const maxG = Math.max(...sources.map((s) => s.genes.value));
      const per = narrow ? 1 : 2;
      const colW = (width - 24) / per;
      const rowH2 = Math.min(30, (avail - 14) / Math.ceil(sources.length / per));
      sources.forEach((s, k) => {
        const x = 12 + (k % per) * colW;
        const y = top + 14 + Math.floor(k / per) * rowH2;
        text(g, s.name, x, y + 8, { size: 10, colour: INK, max: colW * 0.46 });
        const bw = (colW * 0.5 - 44) * (s.genes.value / maxG) * lists;
        bar(g, x + colW * 0.47, y, bw, 9, PROT, 2, 0.85);
        text(g, compact(s.genes.value), x + colW * 0.47 + bw + 4, y + 8, { size: 9.5, colour: FAINT });
      });
      g.restore();
    }
  }, {
    describe: (state) => {
      const cell = ctx.cell(state);
      const guessName = cell.guess === null ? null : names[cell.guess];
      return `${fc(total)} labelled RNA cells in ${names.length} types, in ${lineages.length} branches`
        + `${guessName ? `; this cell's best guess, ${short(guessName)}, sits in the ${classes[cell.guess].lineage} branch` : ''}.`
        + ' A protein measurement has blanks and no type.';
    },
    table: () => `<table class="support-table"><thead><tr><th>Type</th><th>Family</th><th>Branch</th><th>Cells</th></tr></thead><tbody>${classes
      .map((c) => `<tr><td>${escapeHtml(c.name)}</td><td>${escapeHtml(c.group)}</td><td>${escapeHtml(c.lineage)}</td><td class="support-num">${fc(c.cells.value)}</td></tr>`).join('')}</tbody></table>`,
  });
}

// ---- 2: what a protein file looks like ----
// Beat 1: the whole PBMC240 file as a picture, one pixel per protein and
// cell (seen or not), rows from most often seen to least, our cell's column
// outlined. Beat 2: a corner of the real table up close; one of our cell's
// values enlarged, a blank explained, our cell's count. Beat 3: three labs'
// layouts, read into one shape.

const LAYOUTS = [
  { key: 'pbmc240', name: 'PBMC240', note: 'cells in columns', cellsIn: 'cols' },
  { key: 'scope2', name: 'SCoPE2', note: 'cells in rows, numbers already adjusted', cellsIn: 'rows' },
  { key: 'fulcher2026', name: 'Fulcher 2026', note: 'cells in columns, another program', cellsIn: 'cols' },
];

function miniTable(g, x, y, w, h, cellsIn, colour, opacity = 1) {
  const rows = 5;
  const cols = 6;
  const cw = w / cols;
  const rh = h / rows;
  g.save();
  g.globalAlpha *= opacity;
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const header = (r === 0 && cellsIn === 'cols') || (c === 0 && cellsIn === 'rows');
      const label = (c === 0 && cellsIn === 'cols') || (r === 0 && cellsIn === 'rows');
      let fill = ((r * 7 + c * 3) % 5) < 2 ? '#E9ECEF' : alpha(colour, 0.35);
      if (label) fill = '#D7DCE0';
      if (header) fill = colour;
      g.fillStyle = fill;
      g.fillRect(x + c * cw + 0.5, y + r * rh + 0.5, cw - 1, rh - 1);
    }
  }
  g.restore();
}

export function files(el, ctx) {
  const w = ctx.workflow;
  const parse = w.raw.pbmc240.parse;
  const pres = parse.presence;
  const cells = w.trace.cells;
  const details = w.trace.detail;
  const rowsShown = snippetRows(details, 8);
  // The whole file, one pixel per protein and cell, drawn once and scaled.
  const image = document.createElement('canvas');
  image.width = pres.cols;
  image.height = pres.rows;
  const ig = image.getContext('2d');
  const pixels = ig.createImageData(pres.cols, pres.rows);
  const seen = decodeBits(pres.bits, pres.rows * pres.cols);
  for (let k = 0; k < seen.length; k += 1) {
    const [r, gg, b] = seen[k] ? [47, 143, 106] : [233, 236, 239];
    pixels.data[k * 4] = r;
    pixels.data[k * 4 + 1] = gg;
    pixels.data[k * 4 + 2] = b;
    pixels.data[k * 4 + 3] = 255;
  }
  ig.putImageData(pixels, 0, 0);
  return scene(el, ({ g, width, height }, p, state) => {
    const i = state.cell;
    const cell = cells[i];
    const shrink = phase(p, 0.34, 0.44);
    const toLayouts = phase(p, 0.67, 0.74);
    // The picture: full size in beat 1, a thumbnail in beat 2, gone in beat 3.
    const full = { x: 64, y: 46, w: width - 84, h: height - 96 };
    const thumb = { x: 12, y: 46, w: Math.min(150, width * 0.24), h: height - 120 };
    const box = {
      x: lerp(full.x, thumb.x, shrink), y: lerp(full.y, thumb.y, shrink),
      w: lerp(full.w, thumb.w, shrink), h: lerp(full.h, thumb.h, shrink),
    };
    const pictureOp = 1 - toLayouts;
    if (pictureOp > 0) {
      g.save();
      g.globalAlpha = pictureOp;
      const reveal = phase(p, 0.02, 0.26);
      g.imageSmoothingEnabled = true;
      if (reveal > 0) g.drawImage(image, 0, 0, pres.cols, Math.max(1, pres.rows * reveal), box.x, box.y, box.w, box.h * reveal);
      g.strokeStyle = LINE;
      g.strokeRect(box.x - 0.5, box.y - 0.5, box.w + 1, box.h + 1);
      // Our cell's column.
      const cx = box.x + (i / pres.cols) * box.w;
      const colW = Math.max(2, box.w / pres.cols);
      g.strokeStyle = ACCENT;
      g.lineWidth = 2;
      g.strokeRect(cx - 1, box.y - 2, colW + 2, box.h * Math.max(reveal, 0.02) + 4);
      const labels = 1 - shrink;
      if (labels > 0) {
        text(g, `\u2190 ${fc(pres.cols)} cells, one column each \u2192`, box.x + box.w / 2, 30, { size: 11.5, colour: INK, align: 'center', weight: 600, opacity: labels });
        g.save();
        g.translate(box.x - 14, box.y + box.h / 2);
        g.rotate(-Math.PI / 2);
        text(g, `${fc(pres.rows)} proteins, most often seen at the top`, 0, 0, { size: 11.5, colour: INK, align: 'center', weight: 600, opacity: labels });
        g.restore();
        chip(g, `our cell (cell ${i + 1})`, Math.min(cx + 6, box.x + box.w - 120), box.y + 14, { size: 10.5, colour: ACCENT, border: ACCENT, opacity: labels * phase(p, 0.1, 0.18) });
        const ly = box.y + box.h + 18;
        bar(g, box.x, ly - 9, 12, 12, PROT, 2, labels);
        text(g, 'seen', box.x + 18, ly + 1, { size: 10.5, colour: SOFT, opacity: labels });
        bar(g, box.x + 64, ly - 9, 12, 12, '#E9ECEF', 2, labels);
        text(g, 'not seen', box.x + 82, ly + 1, { size: 10.5, colour: SOFT, opacity: labels });
      } else {
        text(g, 'the whole file', box.x + box.w / 2, box.y + box.h + 16, { size: 10.5, colour: FAINT, align: 'center' });
      }
      g.restore();
    }

    // Beat 2: a corner of the real table, up close.
    const corner = shrink * (1 - toLayouts);
    if (corner > 0) {
      g.save();
      g.globalAlpha = corner;
      const tx = thumb.x + thumb.w + 28;
      const tw = width - tx - 10;
      const nameW = Math.min(86, tw * 0.2);
      const cw = (tw - nameW) / details.length;
      const rh = Math.min(26, (height * 0.5) / (rowsShown.length + 1));
      const top = 46;
      text(g, 'A corner of the table, up close', tx, 30, { size: 11.5, colour: INK, weight: 600 });
      details.forEach((d, c) => {
        const mine = d.cell === i;
        text(g, `cell ${d.cell + 1}`, tx + nameW + c * cw + cw / 2, top + rh * 0.6, { size: 10.5, colour: mine ? ACCENT : INK, weight: mine ? 600 : 400, align: 'center' });
        if (mine) {
          g.strokeStyle = ACCENT;
          g.lineWidth = 2;
          g.strokeRect(tx + nameW + c * cw + 1, top + 2, cw - 2, rh * (rowsShown.length + 1) - 2);
        }
      });
      rowsShown.forEach((g0, r) => {
        const y = top + rh * (r + 1);
        text(g, details[0].raw_row[g0][0].split(';')[0], tx + nameW - 6, y + rh * 0.66, { size: 10, colour: INK, align: 'right', max: nameW - 8 });
        details.forEach((d, c) => {
          const v = d.raw_row[g0]?.[1];
          const x = tx + nameW + c * cw + 3;
          if (v === null || v === undefined) hatch(g, x, y + 2, cw - 6, rh - 4);
          else {
            bar(g, x, y + 2, cw - 6, rh - 4, BENCH, 3);
            text(g, compact(v), x + (cw - 6) / 2, y + rh * 0.66, { size: 10, align: 'center', colour: INK });
          }
        });
      });
      // One of our cell's numbers, and one blank, explained.
      const { detail, own } = ctx.detail(state);
      const callout = phase(p, 0.46, 0.56);
      const yC = top + rh * (rowsShown.length + 1) + 18;
      if (callout > 0 && detail) {
        const values = rowsShown.map((g0) => detail.raw_row[g0]?.[1]).filter((v) => v !== null && v !== undefined);
        const maxV = Math.max(...rowsShown.flatMap((g0) => details.map((d) => d.raw_row[g0]?.[1] ?? 0)), 1);
        // The largest of our cell's shown values, so its meter reads clearly.
        const pick = rowsShown.filter((g0) => detail.raw_row[g0]?.[1] !== null && detail.raw_row[g0]?.[1] !== undefined)
          .sort((a, b) => detail.raw_row[b][1] - detail.raw_row[a][1])[0];
        if (pick !== undefined) {
          const v = detail.raw_row[pick][1];
          const name = detail.raw_row[pick][0].split(';')[0];
          text(g, `${name} in cell ${detail.cell + 1}:`, tx, yC + 4, { size: 11, colour: SOFT, opacity: callout });
          text(g, Math.round(v).toLocaleString('en-US'), tx, yC + 32, { size: 24, colour: INK, weight: 700, opacity: callout });
          const mw = Math.min(220, tw * 0.45);
          bar(g, tx, yC + 42, mw, 8, BENCH, 4, callout);
          bar(g, tx, yC + 42, mw * (v / maxV) * callout, 8, PROT, 4, callout);
          text(g, 'how strongly it was detected:', tx, yC + 64, { size: 10.5, colour: SOFT, opacity: callout });
          text(g, 'bigger means more of it', tx, yC + 79, { size: 10.5, colour: SOFT, opacity: callout });
        }
        const blank = phase(p, 0.52, 0.6);
        const bx = tx + tw * 0.55;
        if (blank > 0) {
          hatch(g, bx, yC - 4, 34, 22, blank);
          text(g, 'blank: not seen.', bx + 42, yC + 6, { size: 11, colour: INK, weight: 600, opacity: blank });
          text(g, 'Often just too little', bx + 42, yC + 22, { size: 10.5, colour: SOFT, opacity: blank });
          text(g, 'to catch, not none.', bx + 42, yC + 37, { size: 10.5, colour: SOFT, opacity: blank });
        }
        if (!own) text(g, `(the numbers shown are for cell ${detail.cell + 1}, a cell like ours)`, tx, yC + 98, { size: 9.5, colour: FAINT, opacity: callout });
        void values;
      }
      const count = phase(p, 0.58, 0.65);
      if (count > 0) {
        const yN = height - 34;
        const nw = width - tx - 20;
        text(g, `Our cell: ${fc(cell.observed_raw)} of ${fc(pres.rows)} proteins seen`, tx, yN - 8, { size: 12, colour: INK, weight: 600, opacity: count });
        bar(g, tx, yN, nw, 10, '#E9ECEF', 5, count);
        bar(g, tx, yN, nw * (cell.observed_raw / pres.rows) * count, 10, PROT, 5, count);
      }
      g.restore();
    }

    // Beat 3: every lab's layout, read into one shape.
    if (toLayouts > 0) {
      g.save();
      g.globalAlpha = toLayouts;
      text(g, 'Three labs, three layouts', 12, 24, { size: 12, colour: INK, weight: 600 });
      text(g, 'the dark strip marks where the cells are listed', width - 12, 24, { size: 10.5, colour: FAINT, align: 'right', max: width * 0.5 });
      const n = LAYOUTS.length;
      const gap = 18;
      const cardW = (width - 24 - gap * (n - 1)) / n;
      const cardH = Math.min(130, height * 0.3);
      const merge = phase(p, 0.8, 0.95);
      const uw = Math.min(260, width * 0.5);
      const ux = width / 2 - uw / 2;
      const uy = height - cardH - 40;
      LAYOUTS.forEach((L, k) => {
        const x = 12 + k * (cardW + gap);
        const y = 40;
        const appear = clamp(phase(p, 0.68, 0.8) * n - k, 0, 1);
        text(g, L.name, x, y + 12, { size: 11.5, colour: INK, weight: 600, opacity: appear });
        miniTable(g, x, y + 20, cardW, cardH - 44, L.cellsIn, PROT, appear);
        text(g, L.note, x, y + cardH - 8, { size: 10, colour: SOFT, opacity: appear, max: cardW });
        if (merge > 0) {
          line(g, x + cardW / 2, y + cardH + 4, lerp(x + cardW / 2, ux + uw / 2, merge), lerp(y + cardH + 4, uy - 6, merge), { colour: ACCENT, width: 1.5, opacity: merge });
        }
      });
      if (merge > 0) {
        miniTable(g, ux, uy, uw, cardH - 30, 'rows', ACCENT, merge);
        text(g, 'VivOME\u2019s shape: one row per cell, one column per gene', width / 2, uy + cardH - 14, { size: 11.5, colour: INK, weight: 600, align: 'center', opacity: merge, max: width - 24 });
      }
      g.restore();
    }
  }, {
    describe: (state) => `The whole file: ${fc(pres.rows)} proteins by ${fc(pres.cols)} cells, ${formatRecord(w.facts.missing_share)} blank. Our cell has values for ${fc(cells[state.cell].observed_raw)} of the proteins.`,
    table: () => buildPbmcTable(w) + buildHeaderMorph(w),
  });
}

// ---- 3: one shared list of genes ----
// Beat 1: six protein lists pool into one pile; the antibody and T-cell
// receptor gene pieces drop out. Beat 2: that list against the RNA side's,
// as two circles whose areas match the counts; the overlap is the shared
// list. Beat 3: one seat per gene on the shared list, a few familiar ones lit.

const SEAT_EXAMPLES = [['CD3E', 'T cells'], ['MS4A1', 'B cells'], ['CD14', 'monocytes'], ['HBB', 'red blood cells'], ['PPBP', 'platelets']];

export function genes(el, ctx) {
  const w = ctx.workflow;
  const gs = w.gene_space;
  const f = gs.funnel;
  const union = f.union.value;
  const cut = f.ig_tcr_excluded.value;
  const kept = f.union_without_ig_tcr.value;
  const rna = f.rna_genes.value;
  const shared = f.feature_space.value;
  const sources = gs.sources;
  const examples = SEAT_EXAMPLES.map(([gene, what]) => ({ gene, what, i: gs.genes.indexOf(gene) })).filter((x) => x.i >= 0);
  return scene(el, ({ g, width, height }, p) => {
    // Beat 1: the protein lists, pooled.
    const one = 1 - phase(p, 0.31, 0.37);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      text(g, 'Six lists of proteins, pooled into one', 12, 24, { size: 12, weight: 600, colour: INK });
      const listW = width * 0.46;
      const rowH = (height - 90) / sources.length;
      const maxS = Math.max(...sources.map((s) => s.genes.value));
      const pool = phase(p, 0.06, 0.22);
      const pileX = width * 0.54;
      const pileW = Math.min(90, width * 0.14);
      const pileTop = 70;
      const pileMax = height - 130;
      sources.forEach((s, k) => {
        const y = 52 + k * rowH;
        const appear = phase(p, 0.0 + k * 0.01, 0.06 + k * 0.01);
        text(g, s.name, 12, y + 12, { size: 10.5, colour: INK, opacity: appear, max: listW });
        const bw = (listW - 50) * (s.genes.value / maxS);
        bar(g, 12, y + 18, bw, 10, PROT, 2, 0.85 * appear);
        text(g, compact(s.genes.value), 16 + bw, y + 27, { size: 9.5, colour: FAINT, opacity: appear });
        if (pool > 0 && pool < 1) {
          const t2 = clamp(pool * 1.4 - k * 0.07, 0, 1);
          dot(g, lerp(12 + bw, pileX, t2), lerp(y + 23, pileTop + pileMax * 0.5, t2), 3, PROT, 1 - t2 * 0.3);
        }
      });
      // The pile: its height grows as the lists are pooled.
      const count = Math.round(union * phase(p, 0.08, 0.22));
      const ph = pileMax * (count / union);
      const drop = phase(p, 0.22, 0.3);
      const cutH = Math.max(5, pileMax * (cut / union));
      bar(g, pileX, pileTop + pileMax - ph + (drop > 0 ? cutH : 0), pileW, ph - (drop > 0 ? cutH : 0), PROT, 3, 0.85);
      if (count > 0) {
        if (drop === 0) bar(g, pileX, pileTop + pileMax - ph, pileW, Math.min(cutH, ph), '#9AA6AF', 2);
        else {
          const sx = pileX + pileW + 18 * drop + 8;
          const sy = pileTop + pileMax - ph + 40 * drop;
          const room = width - sx - 10;
          bar(g, sx, sy, pileW * 0.6, cutH, '#9AA6AF', 2, 1 - drop * 0.2);
          text(g, `${fc(cut)} genes left out:`, sx, sy + cutH + 16, { size: 10.5, colour: INK, weight: 600, opacity: drop, max: room });
          text(g, 'pieces of antibody and', sx, sy + cutH + 31, { size: 10, colour: SOFT, opacity: drop, max: room });
          text(g, 'T-cell receptor genes', sx, sy + cutH + 45, { size: 10, colour: SOFT, opacity: drop, max: room });
        }
        const label = drop >= 1 ? `${fc(kept)} genes` : `${fc(count)} genes`;
        text(g, label, pileX + pileW / 2, pileTop + pileMax + 22, { size: 15, weight: 700, colour: INK, align: 'center' });
        text(g, drop >= 1 ? 'the protein side\u2019s list' : 'named by the lists together', pileX + pileW / 2, pileTop + pileMax + 40, { size: 10, colour: FAINT, align: 'center' });
      }
      g.restore();
    }

    // Beat 2: the two sides' lists, and their overlap.
    const two = phase(p, 0.31, 0.37) * (1 - phase(p, 0.64, 0.7));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      text(g, 'Which genes both sides know (circle areas match the counts)', 12, 24, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const R = Math.min(width * 0.3, height * 0.36);
      const r = R * Math.sqrt(kept / rna);
      const d = distanceForOverlap(R, r, (shared / rna) * Math.PI * R * R);
      const cx = width * 0.42;
      const cy = height * 0.55;
      const enter = phase(p, 0.36, 0.48);
      const px = lerp(width + r, cx + d, enter);
      g.beginPath();
      g.arc(cx, cy, R, 0, Math.PI * 2);
      g.fillStyle = alpha(RNA, 0.1);
      g.fill();
      g.strokeStyle = RNA;
      g.lineWidth = 2;
      g.stroke();
      g.beginPath();
      g.arc(px, cy, r, 0, Math.PI * 2);
      g.fillStyle = alpha(PROT, 0.16);
      g.fill();
      g.strokeStyle = PROT;
      g.stroke();
      const lens = phase(p, 0.48, 0.58);
      if (lens > 0) {
        g.save();
        g.beginPath();
        g.arc(cx, cy, R, 0, Math.PI * 2);
        g.clip();
        g.beginPath();
        g.arc(px, cy, r, 0, Math.PI * 2);
        g.fillStyle = alpha(ACCENT, 0.4 * lens);
        g.fill();
        g.restore();
      }
      text(g, 'RNA examples', cx - R * 0.55, cy - R * 0.2, { size: 12.5, weight: 600, colour: RNA, align: 'center' });
      text(g, `${fc(rna)} genes`, cx - R * 0.55, cy - R * 0.2 + 18, { size: 11.5, colour: RNA, align: 'center' });
      const lx = cx + R + 18;
      line(g, px + r * 0.7, cy - r * 0.7, lx - 4, cy - r - 18, { colour: PROT, width: 1, opacity: enter });
      text(g, 'protein lists', lx, cy - r - 22, { size: 12, weight: 600, colour: PROT, opacity: enter, max: width - lx - 8 });
      text(g, `${fc(kept)} genes`, lx, cy - r - 6, { size: 11, colour: PROT, opacity: enter, max: width - lx - 8 });
      if (lens > 0) chip(g, `shared list: ${fc(shared)} genes`, px, cy + r + 24, { size: 12, align: 'center', border: ACCENT, colour: ACCENT, opacity: lens });
      g.restore();
    }

    // Beat 3: one seat per gene.
    const three = phase(p, 0.64, 0.7);
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      const lookup = geneLookup(w, ctx.options('genes').gene ?? '');
      text(g, `${fc(shared)} seats, one per gene, in alphabetical order`, 12, 24, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const gridW = width * 0.66;
      const gridH = height - 60;
      const cols = Math.ceil(Math.sqrt(shared * (gridW / gridH)));
      const size = Math.min(gridW / cols, gridH / Math.ceil(shared / cols));
      const fill = phase(p, 0.68, 0.8);
      const seatAt = (i) => [12 + (i % cols) * size, 40 + Math.floor(i / cols) * size];
      g.fillStyle = '#DCE3E9';
      for (let i = 0; i < shared * fill; i += 1) {
        const [x, y] = seatAt(i);
        g.fillRect(x, y, Math.max(0.6, size - 0.6), Math.max(0.6, size - 0.6));
      }
      const lit = phase(p, 0.8, 0.92);
      const labelX = 12 + cols * size + 22;
      const marks = lookup && !examples.some((x) => x.i === lookup.index)
        ? [...examples, { gene: lookup.gene, what: 'your look-up', i: lookup.index, mine: true }] : examples;
      marks.forEach((x, k) => {
        const [sx, sy] = seatAt(x.i);
        const ly = 70 + k * Math.min(54, (gridH - 40) / marks.length);
        const colour = x.mine ? INK : ACCENT;
        g.fillStyle = colour;
        g.globalAlpha = three * lit;
        g.fillRect(sx - 1.5, sy - 1.5, size + 3, size + 3);
        g.globalAlpha = three;
        line(g, sx + size + 2, sy + size / 2, labelX - 6, ly - 4, { colour, width: 1, opacity: lit * 0.7 });
        text(g, x.gene, labelX, ly, { size: 12, weight: 600, colour, opacity: lit });
        text(g, `${x.what}, seat ${fc(x.i + 1)}`, labelX, ly + 15, { size: 10, colour: SOFT, opacity: lit, max: width - labelX - 8 });
      });
      g.restore();
    }
  }, {
    describe: () => `${fc(union)} genes named by the protein lists, ${fc(kept)} after the antibody and T-cell receptor pieces are left out; ${fc(shared)} of them are also among the RNA examples' ${fc(rna)}.`,
    table: () => `<table class="support-table"><tbody>${[
      ...sources.map((s) => [`Named by ${s.name}`, s.genes.value]),
      ['Named by the six lists together', union], ['Antibody and T-cell receptor gene pieces, left out', cut],
      ['The protein side\u2019s list', kept], ['Genes in the RNA examples', rna], ['The shared list', shared],
    ].map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td class="support-num">${fc(v)}</td></tr>`).join('')}</tbody></table>`,
  });
}

// ---- 4 is in web/js/scenes-evidence.js ----

// ---- 5: tidying up a new file ----
// Beat 1: our cell's amounts on an ordinary ruler (crowded near zero), then
// on a ruler that counts doublings (spread out). Beat 2: a gene's two rows
// joined into one. Beat 3: the rows' names sorted into found, several genes,
// and not on the list.

export function upload(el, ctx) {
  const w = ctx.workflow;
  const raw = w.raw.pbmc240;
  const r = rng(5);
  // Found examples: well-known genes, shown only where this file matched
  // them on the shared list and measured them.
  const inFile = decodeBits(raw.align.matched_bits, raw.align.feature_space);
  const found = ['CD3E', 'LYZ', 'HBB', 'CD14', 'MS4A1', 'PKM']
    .filter((n) => { const hit = geneLookup(w, n); return hit && inFile[hit.index]; }).slice(0, 4);
  const starts = Array.from({ length: 12 }, () => [r(), r()]);
  return scene(el, ({ g, width, height }, p, state) => {
    const narrow = width < 500;
    const { detail, own } = ctx.detail(state);
    const values = detail?.observed_values ?? [];
    const cellNo = (own ? state.cell : detail?.cell ?? 0) + 1;

    // Beat 1: one scale.
    const one = 1 - phase(p, 0.31, 0.37);
    if (one > 0 && values.length) {
      g.save();
      g.globalAlpha = one;
      const toLog = phase(p, 0.12, 0.26);
      text(g, narrow ? `Cell ${cellNo}: ${fc(values.length)} amounts, one dot each` : `Cell ${cellNo}: each dot is one protein amount (${fc(values.length)} of them)`,
        12, 22, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const x0 = 24;
      const x1 = width - 24;
      const vmax = values[values.length - 1];
      const lmin = Math.floor(Math.log2(Math.max(1, values[0])));
      const lmax = Math.ceil(Math.log2(vmax));
      const lin = (v) => x0 + (v / vmax) * (x1 - x0);
      const lg = (v) => x0 + ((Math.log2(Math.max(1, v)) - lmin) / (lmax - lmin)) * (x1 - x0);
      const axisY = height - 110;
      line(g, x0, axisY, x1, axisY, { colour: INK, width: 1.5 });
      values.forEach((v, k) => {
        const jitter = (((k * 37) % 41) / 41) * (axisY - 70);
        dot(g, lerp(lin(v), lg(v), toLog), axisY - 10 - jitter, 2.2, PROT, 0.55);
      });
      // The ruler's marks: ordinary round steps, then doublings (every
      // other one labelled, every fourth on a narrow screen).
      ticks(0, vmax, narrow ? 2 : 4).filter((v) => v <= vmax).forEach((v) => {
        line(g, lin(v), axisY, lin(v), axisY + 6, { colour: INK, opacity: 1 - toLog });
        text(g, v.toLocaleString('en-US'), lin(v), axisY + 20, { size: 10, colour: SOFT, align: 'center', opacity: 1 - toLog });
      });
      const every = narrow ? 4 : 2;
      for (let k = lmin; k <= lmax; k += 1) {
        const v = 2 ** k;
        line(g, lg(v), axisY, lg(v), axisY + 6, { colour: INK, opacity: toLog });
        if ((k - lmin) % every === 0) text(g, v.toLocaleString('en-US'), lg(v), axisY + 20, { size: 10, colour: SOFT, align: 'center', opacity: toLog });
      }
      text(g, toLog < 0.5 ? 'an ordinary ruler: most amounts crowd near zero' : 'counting doublings: each mark is twice the one before',
        width / 2, axisY + 44, { size: 11.5, colour: INK, align: 'center', weight: 600 });
      const typical = `typical amount ${raw.scale.median_observed.toLocaleString('en-US')}, all positive`;
      if (narrow) {
        text(g, `${typical}:`, width / 2, axisY + 62, { size: 10.5, colour: SOFT, align: 'center', max: width - 24 });
        text(g, 'raw amounts, so VivOME converts them', width / 2, axisY + 77, { size: 10.5, colour: SOFT, align: 'center', max: width - 24 });
      } else {
        text(g, `${typical}: raw amounts, so VivOME converts them`, width / 2, axisY + 64, { size: 10.5, colour: SOFT, align: 'center', max: width - 24 });
      }
      if (!own) text(g, `(amounts shown for cell ${cellNo}, a cell like ours)`, width / 2, axisY + (narrow ? 94 : 82), { size: 9.5, colour: FAINT, align: 'center' });
      g.restore();
    }

    // Beat 2: one row per gene.
    const two = phase(p, 0.31, 0.37) * (1 - phase(p, 0.64, 0.7));
    if (two > 0) {
      g.save();
      g.globalAlpha = two;
      const ex = raw.collapse.examples.slice(0, clamp(Math.floor((height - 84) / 64), 1, 4));
      text(g, narrow ? 'Genes on two rows, joined into one' : 'Genes that appear on more than one row, joined into one', 12, 22,
        { size: 12, weight: 600, colour: INK, max: width - 24 });
      const join = phase(p, 0.4, 0.55);
      const rowH = Math.min(96, (height - 84) / ex.length);
      const bx = narrow ? 70 : 100;
      const bw = width - bx - 12;
      ex.forEach((e, k) => {
        const y = 48 + k * rowH;
        text(g, e.gene, 12, y + 20, { size: 13, weight: 600, colour: INK });
        text(g, `${e.rows} rows`, 12, y + 36, { size: 10, colour: FAINT, opacity: 1 - join });
        text(g, '1 row', 12, y + 36, { size: 10, colour: ACCENT, opacity: join });
        for (let rr = 0; rr < e.rows; rr += 1) {
          const yy = lerp(y + 4 + rr * 22, y + 15, join);
          bar(g, bx, yy, bw, 16, rr === 0 ? alpha(PROT, 0.6) : alpha(PROT, 0.35), 3, rr === 0 ? 1 : 1 - join * 0.9);
          text(g, `row ${rr + 1}`, bx + 8, yy + 12, { size: 9.5, colour: INK, opacity: clamp(1 - join * 2.5, 0, 1) });
        }
        text(g, 'one row', bx + 8, y + 27, { size: 9.5, colour: INK, opacity: clamp((join - 0.7) / 0.3, 0, 1) });
        text(g, narrow ? `cells with a value: ${e.best_single_row_cells}, then ${e.merged_cells}` : `cells with a value: ${e.best_single_row_cells} on its fuller row, ${e.merged_cells} once joined`, bx, y + 54,
          { size: 10, colour: SOFT, opacity: join, max: bw });
      });
      const count = phase(p, 0.55, 0.63);
      text(g, `${fc(raw.collapse.rows_before)} rows \u2192 ${fc(raw.collapse.rows_after)} rows`, width / 2, height - 14,
        { size: 15, weight: 700, colour: INK, align: 'center', opacity: count });
      g.restore();
    }

    // Beat 3: the names, sorted into three bins.
    const three = phase(p, 0.64, 0.7);
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      const ids = raw.ids;
      text(g, 'Each row\u2019s name, looked up on the shared list', 12, 22, { size: 12, weight: 600, colour: INK, max: width - 24 });
      // A two-gene name explains the middle bin: it could be either gene.
      const pair = ids.ambiguous_examples.find((n) => n.split(';').length === 2);
      if (pair) {
        const [a, b2] = pair.split(';');
        text(g, narrow ? `${pair}: ${a} or ${b2}? No way to tell` : `A name like ${pair} stands for ${a} or ${b2}: VivOME cannot tell which`, 12, 42,
          { size: 10.5, colour: SOFT, max: width - 24 });
      }
      const bins = [
        { label: 'found on the list', n: ids.matched, colour: ACCENT, names: found },
        { label: narrow ? 'set aside' : 'names several genes: set aside', n: ids.ambiguous, colour: INK, names: ids.ambiguous_examples.slice(0, 4) },
        { label: 'not on the list', n: ids.unmapped, colour: '#7C8A95', names: ids.unmapped_examples.slice(0, 4) },
      ];
      const bwid = (width - 48) / 3;
      const binTop = height < 360 ? 56 : 116;
      const binBottom = height - 36;
      const countSize = height < 360 ? 16 : 22;
      const fits = clamp(Math.floor((binBottom - countSize - 30 - (binTop + 22)) / 30) + 1, 0, 4);
      const maxChars = Math.max(5, Math.floor((bwid - 34) / 5.8));
      const drop = phase(p, 0.72, 0.9);
      bins.forEach((b, k) => {
        const x = 12 + k * (bwid + 12);
        g.strokeStyle = b.colour;
        g.lineWidth = 2;
        g.beginPath();
        g.moveTo(x, binTop);
        g.lineTo(x + 8, binBottom);
        g.lineTo(x + bwid - 8, binBottom);
        g.lineTo(x + bwid, binTop);
        g.stroke();
        text(g, fc(b.n), x + bwid / 2, binBottom - 12, { size: countSize, weight: 700, colour: b.colour, align: 'center', opacity: drop });
        text(g, b.label, x + bwid / 2, binBottom + 20, { size: 10.5, colour: INK, align: 'center', max: bwid });
        b.names.slice(0, fits).forEach((name, j) => {
          const [sx, sy] = starts[k * 4 + j];
          const startX = 12 + sx * (width - 140);
          const startY = binTop - 52 + sy * 36;
          const t2 = clamp(drop * 1.6 - j * 0.15 - k * 0.1, 0, 1);
          const tx = x + 14;
          const ty = binTop + 22 + j * 30;
          const label = name.length > maxChars ? `${name.slice(0, maxChars - 1)}\u2026` : name;
          chip(g, label, lerp(startX, tx, t2), lerp(startY, ty, t2), { size: 9.5, colour: b.colour, border: b.colour, opacity: clamp(drop * 4, 0, 1) });
        });
      });
      g.restore();
    }
  }, {
    describe: () => `Raw amounts converted to a scale that counts doublings; ${raw.collapse.genes_merged} genes on more than one row joined; ${fc(raw.ids.matched)} names found, ${fc(raw.ids.ambiguous)} set aside, ${fc(raw.ids.unmapped)} not on the list.`,
    table: () => `<table class="support-table"><tbody>`
      + `<tr><td>Typical amount in the file</td><td>${escapeHtml(raw.scale.median_observed.toLocaleString('en-US'))}: raw amounts, converted</td></tr>`
      + `<tr><td>Rows before and after joining</td><td>${fc(raw.collapse.rows_before)}, ${fc(raw.collapse.rows_after)}</td></tr>`
      + `<tr><td>Names found, set aside, not on the list</td><td>${fc(raw.ids.matched)}, ${fc(raw.ids.ambiguous)}, ${fc(raw.ids.unmapped)}</td></tr>`
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
