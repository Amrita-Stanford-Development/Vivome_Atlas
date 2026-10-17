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
  ACCENT, BENCH, FAINT, FONT, INK, LINE, PROT, RNA, SOFT, alpha, bar, chip, dot, hatch, line, mountCanvas, short, text,
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
// Beat 1: the cell's raw column, protein by protein. Beat 2: it travels a
// line with one stop per step on the page, to its answer and best guess.

const STOPS = ['the file', 'fit to the list', 'borrow', 'squeeze', 'closeness', 'best guess', 'shortlist', 'answer', 'map'];

export function open(el, ctx) {
  return scene(el, ({ g, width, height }, p, state) => {
    const narrow = width < 560;
    const cell = ctx.cell(state);
    const { detail, own } = ctx.detail(state);
    const rows = own ? detail.raw_row : [];
    const colW = Math.min(150, width * 0.3);
    const tileH = Math.min(17, (height - 60) / 20);
    const shown = Math.floor(phase(p, 0, 0.3) * rows.length + 0.0001);
    const squeeze = phase(p, 0.3, 0.45);
    const target = [colW + 40, height * 0.62];
    text(g, own ? `Cell ${state.cell + 1}: the first proteins in its column` : `Cell ${state.cell + 1}`, 8, 16, { size: 12, colour: INK, weight: 600, max: width - 16 });
    rows.forEach((r, i) => {
      if (i >= shown) return;
      const col = i < 20 ? 0 : 1;
      const x0 = 8 + col * (colW / 2 + 4);
      const y0 = 30 + (i % 20) * tileH;
      const w = colW / 2;
      const h = tileH - 2;
      const fade = 1 - squeeze * 0.55;
      if (squeeze > 0 && squeeze < 1) dot(g, lerp(x0 + w / 2, target[0], squeeze), lerp(y0 + h / 2, target[1], squeeze), 2.5, ACCENT, 1 - squeeze * 0.5);
      if (r[1] === null) hatch(g, x0, y0, w, h, fade);
      else bar(g, x0, y0, w, h, alpha(ACCENT, 0.12 + 0.55 * clamp(((r[2] ?? 0) - 8) / 14, 0, 1)), 2, fade);
      if (tileH > 11) text(g, `${r[0].split(';')[0]}`, x0 + 4, y0 + h - 4, { size: 9.5, colour: INK, max: w - 6, opacity: fade });
    });
    if (own && shown > 0) {
      text(g, 'darker: more of it; striped: not seen', 8, 30 + 20 * tileH + 14, { size: 10, colour: SOFT, opacity: 1 - squeeze, max: colW + 20 });
    }
    if (!own) text(g, 'This cell\u2019s raw column is kept for a few cells only; its journey is shown here.', 8, 40, { size: 11, colour: SOFT, max: width * 0.5 });
    // The line: one stop per step on the page.
    const railY = height * 0.62;
    const x0 = colW + 40;
    const x1 = width - 24;
    line(g, x0, railY, x1, railY, { colour: LINE, width: 3 });
    const travel = phase(p, 0.45, 0.88);
    STOPS.forEach((name, i) => {
      const x = lerp(x0, x1, i / (STOPS.length - 1));
      const reached = travel * (STOPS.length - 1) >= i - 0.001;
      dot(g, x, railY, reached ? 6 : 4.5, reached ? ACCENT : '#FFFFFF', 1, reached ? null : LINE);
      // A phone has room for the first and last stop's names only.
      const label = !narrow || i === 0 || i === STOPS.length - 1;
      if (label) text(g, name, x, railY + (i % 2 ? 24 : -14), { size: narrow ? 9.5 : 10.5, colour: reached ? INK : FAINT, align: i === 0 && narrow ? 'left' : i === STOPS.length - 1 && narrow ? 'right' : 'center' });
    });
    if (squeeze > 0.95) dot(g, lerp(x0, x1, travel), railY, 9, ACCENT, 1, '#FFFFFF');
    const end = phase(p, 0.88, 1);
    if (end > 0) {
      const answer = ctx.answerShort(cell);
      chip(g, cell.level ? `Answer: ${answer}` : answer, x1, railY + (narrow ? 34 : 64), { size: narrow ? 10.5 : 13, align: 'right', opacity: end, border: ACCENT });
      chip(g, `Best guess: ${ctx.guessText(cell)}`, x1, railY + (narrow ? 60 : 98), { size: narrow ? 10 : 12, align: 'right', opacity: end, colour: SOFT });
    }
  }, {
    describe: (state) => `Cell ${state.cell + 1} passes through every step on this page, from its raw column to ${ctx.answerText(ctx.cell(state))}.`,
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
      text(g, 'The types as a family tree', 12, 20, { size: 12, weight: 600, colour: INK, max: hot ? width * 0.4 : width - 24 });
      if (hot) {
        // The blue path is our cell's best guess; say so in the header row,
        // where it covers no label.
        const key = width < 520 ? 'blue: our cell\u2019s best guess' : 'blue: our cell\u2019s best guess, its family and its branch';
        const keyOp = phase(p, 0.6, 0.66);
        g.save();
        g.font = `400 10.5px ${FONT}`;
        const kw = g.measureText(key).width;
        g.restore();
        line(g, width - 12 - kw - 26, 16, width - 12 - kw - 6, 16, { colour: ACCENT, width: 2.4, opacity: keyOp });
        text(g, key, width - 12, 20, { size: 10.5, colour: ACCENT, align: 'right', opacity: keyOp });
      }
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
    const narrow = width < 560;
    const shrink = phase(p, 0.34, 0.44);
    const toLayouts = phase(p, 0.67, 0.74);
    // The picture: full size in beat 1, a thumbnail in beat 2, gone in beat 3.
    const full = { x: 40, y: 66, w: width - 52, h: height - 102 };
    const thumb = { x: 12, y: 46, w: Math.min(150, width * 0.24), h: height - 120 };
    const box = {
      x: lerp(full.x, thumb.x, shrink), y: lerp(full.y, thumb.y, shrink),
      w: lerp(full.w, thumb.w, shrink), h: lerp(full.h, thumb.h, shrink),
    };
    const pictureOp = (1 - toLayouts) * (narrow ? 1 - shrink : 1);
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
        // What the picture is: a title, then what one square means, with its two colours.
        text(g, narrow ? 'One square = one protein in one cell' : 'The whole file as one picture', 12, 20,
          { size: 12, colour: INK, weight: 600, opacity: labels, max: width - 24 });
        const words = narrow ? ['', 'found', 'not found']
          : ['Each tiny square is one protein in one cell:', 'the machine found it', 'it did not'];
        g.save();
        g.font = `400 11px ${FONT}`;
        const [w0, w1] = [words[0] ? g.measureText(words[0]).width + 8 : 0, g.measureText(words[1]).width];
        g.restore();
        if (words[0]) text(g, words[0], 12, 40, { size: 11, colour: SOFT, opacity: labels });
        bar(g, 12 + w0, 30, 12, 12, PROT, 2, labels);
        text(g, words[1], 29 + w0, 40, { size: 11, colour: SOFT, opacity: labels });
        bar(g, 41 + w0 + w1, 30, 12, 12, '#E9ECEF', 2, labels);
        text(g, words[2], 58 + w0 + w1, 40, { size: 11, colour: SOFT, opacity: labels });
        // The two directions.
        text(g, narrow ? `${fc(pres.cols)} cells, one per column \u2192` : `${fc(pres.cols)} cells, one column per cell, in the file\u2019s order \u2192`,
          box.x, box.y + box.h + 18, { size: 11, colour: INK, weight: 600, opacity: labels, max: box.w });
        g.save();
        g.translate(box.x - 12, box.y + box.h);
        g.rotate(-Math.PI / 2);
        text(g, narrow ? `${fc(pres.rows)} proteins` : `${fc(pres.rows)} proteins, one row per protein`, 0, 0,
          { size: 11, colour: INK, weight: 600, opacity: labels, max: box.h });
        g.restore();
        chip(g, `our cell (cell ${i + 1})`, Math.min(cx + 6, box.x + box.w - 120), box.y + 14, { size: 10.5, colour: ACCENT, border: ACCENT, opacity: labels * phase(p, 0.1, 0.18) });
        // How to read the rows.
        const hints = labels * phase(p, 0.14, 0.2);
        chip(g, narrow ? 'top: found in most cells' : 'top rows: proteins found in almost every cell', box.x + box.w - 8, box.y + box.h * 0.14,
          { size: 10, colour: INK, align: 'right', border: LINE, opacity: hints });
        chip(g, narrow ? 'bottom: found in few cells' : 'bottom rows: proteins found in only a few cells', box.x + 8, box.y + box.h * 0.9,
          { size: 10, colour: INK, border: LINE, opacity: hints });
        // A cell where nothing was found shows as an empty column.
        const empty = cells.findIndex((c) => c.observed_raw === 0);
        if (empty >= 0 && empty !== i) {
          const ex = box.x + ((empty + 0.5) / pres.cols) * box.w;
          const right = ex < box.x + box.w * 0.6;
          chip(g, `cell ${empty + 1}: nothing found`, right ? ex + 8 : ex - 8, box.y + box.h * 0.42,
            { size: 10, colour: INK, align: right ? 'left' : 'right', border: LINE, opacity: labels * phase(p, 0.24, 0.3) });
        }
        // A corner zoomed in, so a square can be seen.
        const zoom = labels * phase(p, 0.2, 0.27);
        if (zoom > 0 && !narrow) {
          const n = 10;
          const c0 = clamp(i - 2, 0, pres.cols - n);
          const r0 = Math.round(pres.rows * 0.2);
          const s = Math.min(150, box.h * 0.42);
          const zx = box.x + box.w - s - 10;
          const zy = box.y + box.h - s - 30;
          const sq = s / n;
          const src = { x: box.x + (c0 / pres.cols) * box.w, y: box.y + (r0 / pres.rows) * box.h, w: (n / pres.cols) * box.w, h: (n / pres.rows) * box.h };
          g.save();
          g.globalAlpha *= zoom;
          g.strokeStyle = INK;
          g.lineWidth = 1;
          g.strokeRect(src.x - 1, src.y - 1, Math.max(3, src.w) + 2, Math.max(3, src.h) + 2);
          line(g, src.x + src.w + 1, src.y, zx, zy, { colour: INK, opacity: 0.5 });
          line(g, src.x + src.w + 1, src.y + src.h + 1, zx, zy + s, { colour: INK, opacity: 0.5 });
          bar(g, zx - 4, zy - 4, s + 8, s + 8, '#FFFFFF', 4);
          for (let rr = 0; rr < n; rr += 1) {
            for (let cc = 0; cc < n; cc += 1) {
              const on = seen[(r0 + rr) * pres.cols + c0 + cc];
              bar(g, zx + cc * sq + 1, zy + rr * sq + 1, sq - 2, sq - 2, on ? PROT : '#E9ECEF', 1.5);
            }
          }
          if (i >= c0 && i < c0 + n) {
            g.strokeStyle = ACCENT;
            g.lineWidth = 2;
            g.strokeRect(zx + (i - c0) * sq, zy, sq, s);
          }
          g.restore();
          text(g, 'zoomed in: one square is one protein in one cell', zx + s, zy + s + 20, { size: 10, colour: INK, align: 'right', opacity: zoom });
        }
      } else if (!narrow) {
        text(g, 'the whole file', box.x + box.w / 2, box.y + box.h + 16, { size: 10.5, colour: FAINT, align: 'center' });
      }
      g.restore();
    }

    // Beat 2: a corner of the real table, up close.
    const corner = shrink * (1 - toLayouts);
    if (corner > 0) {
      g.save();
      g.globalAlpha = corner;
      const short = height < 340;
      const tx = narrow ? 12 : thumb.x + thumb.w + 28;
      const tw = width - tx - 10;
      const nameW = Math.min(86, tw * 0.2);
      const cw = (tw - nameW) / details.length;
      // Room below the table: the callout (about 84px, 16 more when it
      // borrows a story cell) and our cell's count (about 46px); on a short
      // figure, the callout's first lines only.
      const top = 46;
      const below = short ? 18 + 56 : 18 + 84 + 24 + 46;
      const { detail, own } = ctx.detail(state);
      const has = (g0) => detail && detail.raw_row[g0]?.[1] !== null && detail.raw_row[g0]?.[1] !== undefined;
      let rowsHere = rowsShown.slice(0, clamp(Math.floor((height - top - below) / 16) - 1, 3, rowsShown.length));
      // Keep at least one row where our cell has a value, for the callout.
      if (detail && !rowsHere.some(has)) {
        const extra = rowsShown.find(has);
        if (extra !== undefined) rowsHere = [...rowsHere.slice(0, -1), extra];
      }
      const rh = clamp((height - top - below) / (rowsHere.length + 1), 14, 26);
      text(g, 'A corner of the table, up close', tx, 30, { size: 11.5, colour: INK, weight: 600 });
      if (narrow) text(g, 'cell', tx + nameW - 6, top + rh * 0.6, { size: 9.5, colour: FAINT, align: 'right' });
      details.forEach((d, c) => {
        const mine = d.cell === i;
        text(g, narrow ? String(d.cell + 1) : `cell ${d.cell + 1}`, tx + nameW + c * cw + cw / 2, top + rh * 0.6,
          { size: narrow ? 9.5 : 10.5, colour: mine ? ACCENT : INK, weight: mine ? 600 : 400, align: 'center' });
        if (mine) {
          g.strokeStyle = ACCENT;
          g.lineWidth = 2;
          g.strokeRect(tx + nameW + c * cw + 1, top + 2, cw - 2, rh * (rowsHere.length + 1) - 2);
        }
      });
      rowsHere.forEach((g0, r) => {
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
      const callout = phase(p, 0.46, 0.56);
      const yC = top + rh * (rowsHere.length + 1) + 18;
      if (callout > 0 && detail) {
        const values = rowsHere.map((g0) => detail.raw_row[g0]?.[1]).filter((v) => v !== null && v !== undefined);
        const maxV = Math.max(...rowsHere.flatMap((g0) => details.map((d) => d.raw_row[g0]?.[1] ?? 0)), 1);
        // The largest of our cell's shown values, so its meter reads clearly.
        const pick = rowsHere.filter((g0) => detail.raw_row[g0]?.[1] !== null && detail.raw_row[g0]?.[1] !== undefined)
          .sort((a, b) => detail.raw_row[b][1] - detail.raw_row[a][1])[0];
        if (pick !== undefined) {
          const v = detail.raw_row[pick][1];
          const name = detail.raw_row[pick][0].split(';')[0];
          text(g, short && !own ? `${name} in cell ${detail.cell + 1} (like ours):` : `${name} in cell ${detail.cell + 1}:`, tx, yC + 4,
            { size: 11, colour: SOFT, opacity: callout, max: tw * 0.5 });
          text(g, Math.round(v).toLocaleString('en-US'), tx, yC + 32, { size: 24, colour: INK, weight: 700, opacity: callout });
          const mw = Math.min(220, tw * 0.45);
          bar(g, tx, yC + 42, mw, 8, BENCH, 4, callout);
          bar(g, tx, yC + 42, mw * (v / maxV) * callout, 8, PROT, 4, callout);
          if (!short) {
            text(g, 'how strongly it was detected:', tx, yC + 64, { size: 10.5, colour: SOFT, opacity: callout });
            text(g, 'bigger means more of it', tx, yC + 79, { size: 10.5, colour: SOFT, opacity: callout });
          }
        }
        const blank = phase(p, 0.52, 0.6);
        const bx = tx + tw * 0.55;
        if (blank > 0) {
          hatch(g, bx, yC - 4, 34, 22, blank);
          text(g, 'blank: not seen.', bx + 42, yC + 6, { size: 11, colour: INK, weight: 600, opacity: blank });
          text(g, 'Often just too little', bx + 42, yC + 22, { size: 10.5, colour: SOFT, opacity: blank });
          text(g, 'to catch, not none.', bx + 42, yC + 37, { size: 10.5, colour: SOFT, opacity: blank });
        }
        if (!own && !short) text(g, `(the numbers shown are for cell ${detail.cell + 1}, a cell like ours)`, tx, yC + 98, { size: 9.5, colour: FAINT, opacity: callout });
        void values;
      }
      const count = phase(p, 0.58, 0.65);
      if (count > 0 && !short) {
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

// ---- 5: fitting the file to the shared list ----
// Beat 1: the seats, one square per gene: the file's, then our cell's.
// Beat 2: an empty seat is not a zero: our cell's amounts beside its mask.
// Beat 3: the minimum, with every cell of the file. Beat 4: each gene
// compared within the file, from amounts to above or below the average.

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
  const fewGenes = cells.map((c, i) => [c, i]).filter(([c]) => c.observed < align.floor);
  return scene(el, ({ g, width, height }, p, state) => {
    const narrow = width < 560;
    const cell = ctx.cell(state);
    const { detail, own } = ctx.detail(state);
    // Our cell's column in the heatmap sample, or the story cell standing in for it.
    const hmAt = hm.cells.indexOf(state.cell) >= 0 ? hm.cells.indexOf(state.cell) : hm.cells.indexOf(detail?.cell ?? -1);
    const hmOwn = hm.cells.indexOf(state.cell) >= 0;
    const swatch = (x, y, colour, label, opacity = 1) => {
      bar(g, x, y - 9, 11, 11, colour, 2, opacity);
      g.save();
      g.globalAlpha *= opacity;
      g.strokeStyle = LINE;
      g.strokeRect(x + 0.5, y - 8.5, 10, 10);
      g.restore();
      text(g, label, x + 16, y, { size: 10.5, colour: SOFT, opacity });
      g.save();
      g.font = `400 10.5px ${FONT}`;
      const wd = g.measureText(label).width;
      g.restore();
      return x + 16 + wd + 14;
    };

    // Beat 1: the seats.
    const one = 1 - phase(p, 0.22, 0.27);
    if (one > 0) {
      g.save();
      g.globalAlpha = one;
      text(g, `VivOME\u2019s ${fc(n)} seats, one square per gene`, 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const fillM = phase(p, 0.02, 0.1);
      const fillC = phase(p, 0.1, 0.19);
      let lx = 12;
      lx = swatch(lx, 40, '#E6E9EC', narrow ? 'none' : 'no cell measured it');
      lx = swatch(lx, 40, '#BFD5E6', narrow ? 'others only' : 'other cells measured it, ours didn\u2019t', fillM);
      swatch(lx, 40, ACCENT, narrow ? 'our cell' : 'our cell measured it', fillC);
      const top = 54;
      const bottom = height - 30;
      const cols = Math.ceil(Math.sqrt(n * ((width - 24) / (bottom - top))));
      const size = Math.min((width - 24) / cols, (bottom - top) / Math.ceil(n / cols));
      const obs = detail ? observedOf(detail) : null;
      for (let i = 0; i < n; i += 1) {
        const x = 12 + (i % cols) * size;
        const y = top + Math.floor(i / cols) * size;
        let colour = '#E6E9EC';
        if (matched[i] && i / n <= fillM) colour = '#BFD5E6';
        if (obs && obs[i] && i / n <= fillC) colour = ACCENT;
        g.fillStyle = colour;
        g.fillRect(x, y, Math.max(0.6, size - 0.6), Math.max(0.6, size - 0.6));
      }
      const counts = narrow
        ? `file: ${fc(align.matched)} seats; our cell: ${fc(cell.observed)}`
        : `This file fills ${fc(align.matched)} of the ${fc(n)} seats; our cell (cell ${state.cell + 1}) has a value in ${fc(cell.observed)}.`;
      text(g, counts, 12, height - 10, { size: 11, colour: INK, opacity: fillC, max: width - 24 });
      if (!own && detail) text(g, `(seat by seat, shown for cell ${detail.cell + 1}, a cell like ours)`, width - 12, 20, { size: 9.5, colour: FAINT, align: 'right', opacity: fillC });
      g.restore();
    }

    // Beat 2: an empty seat is not a zero.
    const two = phase(p, 0.22, 0.27) * (1 - phase(p, 0.47, 0.52));
    if (two > 0 && hmAt >= 0) {
      g.save();
      g.globalAlpha = two;
      text(g, narrow ? 'Our cell: amounts and mask' : 'Our cell, gene by gene: its amounts, and its mask', 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      // A mix of measured and empty genes from the marker list.
      const count = narrow ? 6 : 10;
      const genesIdx = hm.genes.map((_, r) => r);
      const filled = genesIdx.filter((r) => hm.mask[hmAt][r]);
      const empty = genesIdx.filter((r) => !hm.mask[hmAt][r]);
      const pick = [];
      while (pick.length < count && (filled.length || empty.length)) {
        if (filled.length) pick.push(filled.shift());
        if (pick.length < count && empty.length && pick.length % 3 === 1) pick.push(empty.shift());
      }
      pick.sort((a, b) => a - b);
      const nameW = narrow ? 58 : 86;
      const cw = Math.min(64, (width - 24 - nameW) / pick.length);
      const x0 = 12 + nameW;
      // Room below the rows for what the mask is for.
      const rh = clamp((height - (narrow ? 200 : 210)) / 2, 24, 120);
      const yG = 58;
      const yA = yG + 14;
      const yM = yA + rh + 18;
      const showMask = phase(p, 0.31, 0.38);
      text(g, 'gene', x0 - 8, yG + 4, { size: 10, colour: FAINT, align: 'right' });
      text(g, 'amount', x0 - 8, yA + rh * 0.6, { size: 11, colour: INK, align: 'right', weight: 600 });
      text(g, 'mask', x0 - 8, yM + rh * 0.6, { size: 11, colour: INK, align: 'right', weight: 600, opacity: showMask });
      pick.forEach((r, k) => {
        const x = x0 + k * cw;
        const on = hm.mask[hmAt][r] && hm.log2[hmAt][r] !== null;
        text(g, hm.genes[r], x + cw / 2, yG + 4, { size: 10, colour: INK, align: 'center', max: cw - 2 });
        if (on) {
          const t = (hm.log2[hmAt][r] - log2Range[0]) / (log2Range[1] - log2Range[0] || 1);
          bar(g, x + 2, yA, cw - 4, rh, sequential(0.2 + 0.8 * t), 4);
        } else {
          bar(g, x + 2, yA, cw - 4, rh, '#FFFFFF', 4);
          g.strokeStyle = LINE;
          g.strokeRect(x + 2.5, yA + 0.5, cw - 5, rh - 1);
          text(g, 'empty', x + cw / 2, yA + rh * 0.6, { size: 9.5, colour: FAINT, align: 'center' });
        }
        bar(g, x + 2, yM, cw - 4, rh, on ? alpha(ACCENT, 0.15) : BENCH, 4, showMask);
        text(g, on ? '1' : '0', x + cw / 2, yM + rh * 0.66, { size: 16, weight: 700, colour: on ? ACCENT : INK, align: 'center', opacity: showMask });
      });
      // Why the mask: with it, and without it.
      const notes = phase(p, 0.38, 0.45);
      const yN = yM + rh + 18;
      if (narrow) {
        text(g, 'With the mask: 0 means "skip, not measured".', 12, yN + 12, { size: 10.5, colour: ACCENT, weight: 600, opacity: notes, max: width - 24 });
        text(g, 'Without it: empty seats would read as "average".', 12, yN + 30, { size: 10.5, colour: INK, opacity: notes, max: width - 24 });
      } else {
        const bw = (width - 36) / 2;
        const bh = Math.min(96, height - yN - 14);
        const panel = (x, colour, title, lines, mark) => {
          g.save();
          g.globalAlpha *= notes;
          bar(g, x, yN, bw, bh, '#FFFFFF', 10);
          g.strokeStyle = colour;
          g.lineWidth = 1.5;
          g.beginPath();
          g.roundRect?.(x + 0.75, yN + 0.75, bw - 1.5, bh - 1.5, 10);
          g.stroke();
          g.restore();
          text(g, `${mark}  ${title}`, x + 14, yN + 22, { size: 12, weight: 600, colour, opacity: notes, max: bw - 24 });
          lines.forEach((s, k) => text(g, s, x + 14, yN + 42 + k * 17, { size: 10.5, colour: SOFT, opacity: notes, max: bw - 24 }));
        };
        panel(12, ACCENT, 'With the mask', ['1: read this amount', '0: set it aside, it was not measured'], '\u2713');
        panel(24 + bw, INK, 'Without it', ['every empty seat would hold a number, say 0,', 'which reads as "exactly average": guesses', 'would pass for measurements'], '\u2717');
      }
      if (!hmOwn) text(g, `(shown for cell ${hm.cells[hmAt] + 1}, a cell like ours)`, width - 12, 20, { size: 9.5, colour: FAINT, align: 'right', opacity: notes });
      g.restore();
    }

    // Beat 3: the minimum, every cell of the file.
    const three = phase(p, 0.47, 0.52) * (1 - phase(p, 0.72, 0.77));
    if (three > 0) {
      g.save();
      g.globalAlpha = three;
      text(g, narrow ? 'Genes with a value, one dot per cell' : `How many genes each cell has values for: one dot per cell, all ${fc(cells.length)}`, 12, 20, { size: 12, weight: 600, colour: INK, max: width - 24 });
      const max = Math.max(...cells.map((c) => c.observed));
      const x = (v) => 24 + (v / max) * (width - 48);
      const mid = height * 0.5;
      const spread = Math.min(70, height * 0.18);
      const axisY = mid + spread + 16;
      line(g, 24, axisY, width - 24, axisY, { colour: INK });
      ticks(0, max, narrow ? 3 : 5).filter((v) => v <= max).forEach((v) => {
        line(g, x(v), axisY, x(v), axisY + 5, { colour: INK });
        text(g, fc(v), x(v), axisY + 18, { size: 10, colour: SOFT, align: 'center' });
      });
      text(g, 'genes with a value \u2192', width - 24, axisY + 34, { size: 10.5, colour: INK, align: 'right' });
      const appear = phase(p, 0.5, 0.6);
      cells.forEach((c, i) => {
        if (i / cells.length > appear) return;
        const jitter = ((((i * 37) % 23) / 22) - 0.5) * 2 * spread;
        const below = c.observed < align.floor;
        dot(g, x(c.observed), mid + jitter, i === state.cell ? 6 : 3, below ? INK : alpha(ACCENT, 0.55), 1, i === state.cell ? INK : null);
      });
      const floorOp = phase(p, 0.58, 0.64);
      line(g, x(align.floor), mid - spread - 18, x(align.floor), axisY, { colour: INK, dash: [4, 3], width: 1.5, opacity: floorOp });
      text(g, `minimum: ${fc(align.floor)}`, x(align.floor) + 6, mid - spread - 8, { size: 11, colour: INK, weight: 600, opacity: floorOp });
      const me = cells[state.cell];
      chip(g, `our cell: ${fc(me.observed)}`, Math.min(x(me.observed) + 10, width - 130), mid - spread - 30, { size: 10.5, colour: ACCENT, border: ACCENT, opacity: floorOp });
      fewGenes.slice(0, 2).forEach(([c, i], k) => {
        if (i === state.cell) return;
        chip(g, `cell ${i + 1}: ${fc(c.observed)}, no answer`, x(c.observed) + 8, mid + spread - 6 + k * 24, { size: 10, border: INK, opacity: floorOp });
      });
      g.restore();
    }

    // Beat 4: each gene compared within the file.
    const four = phase(p, 0.72, 0.77);
    if (four > 0) {
      g.save();
      g.globalAlpha = four;
      const z = phase(p, 0.8, 0.92);
      const left = narrow ? 46 : 62;
      const rows = narrow ? hm.genes.length / 2 : hm.genes.length;
      const top = 52;
      const cw = (width - left - 12) / hm.cells.length;
      const rh = (height - top - 46) / rows;
      text(g, z < 0.5 ? 'Amounts: rows are genes, columns are cells' : 'Each gene compared with the file\u2019s average cell', 12, 20,
        { size: 12, weight: 600, colour: INK, max: width - 24 });
      let lx = 12;
      if (z < 0.5) {
        lx = swatch(lx, 40, sequential(0.25), 'less');
        lx = swatch(lx, 40, sequential(0.95), 'more');
      } else {
        lx = swatch(lx, 40, diverging(-2), narrow ? 'below' : 'below average');
        lx = swatch(lx, 40, diverging(0), 'average');
        lx = swatch(lx, 40, diverging(2), narrow ? 'above' : 'above average');
      }
      g.save();
      g.globalAlpha *= 1;
      hatch(g, lx, 31, 11, 11);
      g.restore();
      text(g, 'not measured', lx + 16, 40, { size: 10.5, colour: SOFT });
      hm.genes.slice(0, rows).forEach((gene, r) => text(g, gene, left - 4, top + r * rh + rh * 0.72, { size: Math.min(10, rh * 0.8), align: 'right', colour: INK }));
      hm.cells.forEach((ci, c) => {
        for (let r = 0; r < rows; r += 1) {
          const x = left + c * cw;
          const y = top + r * rh;
          const raw = hm.log2[c][r];
          if (!hm.mask[c][r] || raw === null) { hatch(g, x, y, cw - 0.8, rh - 0.8); continue; }
          const a = sequential(0.2 + 0.8 * (raw - log2Range[0]) / (log2Range[1] - log2Range[0] || 1));
          const b = diverging(hm.z[c][r]);
          g.fillStyle = z < 1 ? (z > 0 ? mixHex(a, b, z) : a) : b;
          g.fillRect(x, y, cw - 0.8, rh - 0.8);
        }
      });
      if (hmAt >= 0) {
        g.strokeStyle = INK;
        g.lineWidth = 2;
        g.strokeRect(left + hmAt * cw - 1, top - 1, cw + 1, rows * rh + 1);
        text(g, hmOwn ? 'our cell' : `cell ${hm.cells[hmAt] + 1}`, left + hmAt * cw + cw / 2, top + rows * rh + 14, { size: 10, colour: INK, weight: 600, align: hmAt < 3 ? 'left' : 'center' });
      }
      text(g, `${hm.cells.length} of the file\u2019s ${fc(cells.length)} cells, and ${rows} marker genes`, width - 12, height - 10,
        { size: 10, colour: FAINT, align: 'right', max: width - 24 });
      g.restore();
    }
  }, {
    describe: (state) => `The file fills ${fc(align.matched)} of ${fc(n)} seats; this cell has values in ${fc(ctx.cell(state).observed)}; cells need at least ${align.floor}; each gene is then compared within the file.`,
    table: () => `<table class="support-table"><thead><tr><th>Cell</th><th>Genes with a value</th></tr></thead><tbody>${cells
      .map((c, i) => `<tr><td>Cell ${i + 1}</td><td class="support-num">${fc(c.observed)}</td></tr>`).join('')}</tbody></table>`,
  });
}

function mixHex(a, b, t) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return `rgb(${pa.map((v, i) => Math.round(lerp(v, pb[i], t))).join(',')})`;
}

// ---- 6: borrowing from similar cells ----
// Beat 1: the file's cells placed by likeness; our cell linked to its
// closest matches. Beat 2: before and after the blend, gene by gene.
// Beat 3: the mask under them, unchanged: an empty seat filled from the
// matches is still marked not measured.

export function smoothing(el, ctx) {
  const w = ctx.workflow;
  const cells = w.trace.cells;
  const sm = w.trace.stages.smoothing;
  const hm = w.trace.heatmap;
  const xs = cells.map((c) => c.layout[0]);
  const ys = cells.map((c) => c.layout[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  return scene(el, ({ g, width, height }, p, state) => {
    const narrow = width < 560;
    const i = state.cell;
    const rows = phase(p, 0.33, 0.43);
    const graphTop = 44;
    const graphH = lerp(height - graphTop - 30, (height - graphTop) * (narrow ? 0.26 : 0.42), rows);
    const sx = (v) => 20 + ((v - x0) / (x1 - x0 || 1)) * (width - 40);
    const sy = (v) => graphTop + 8 + (1 - (v - y0) / (y1 - y0 || 1)) * (graphH - 16);
    text(g, narrow ? 'The file\u2019s cells; similar cells sit close' : `The file\u2019s ${fc(cells.length)} cells, placed so that similar cells sit close together`, 12, 20,
      { size: 12, weight: 600, colour: INK, max: width - 24 });
    // A key: our cell and its matches.
    dot(g, 18, 36, 5, PROT, 1, INK);
    text(g, 'our cell', 28, 40, { size: 10.5, colour: SOFT });
    dot(g, 96, 36, 4, ACCENT);
    text(g, `its ${sm.k} closest matches`, 106, 40, { size: 10.5, colour: SOFT });
    const grow = phase(p, 0.06, 0.26);
    sm.neighbours[i].forEach((j, k) => {
      const t = clamp(grow * 1.5 - (k / sm.neighbours[i].length) * 0.5, 0, 1);
      if (t <= 0) return;
      const ax = sx(cells[i].layout[0]);
      const ay = sy(cells[i].layout[1]);
      line(g, ax, ay, lerp(ax, sx(cells[j].layout[0]), t), lerp(ay, sy(cells[j].layout[1]), t), { colour: ACCENT, width: 0.6 + 7 * sm.weights[i][k], opacity: 0.55 });
    });
    cells.forEach((c, k) => {
      if (k === i) return;
      const isN = sm.neighbours[i].includes(k) && grow > 0.5;
      dot(g, sx(c.layout[0]), sy(c.layout[1]), isN ? 4 : 2.6, isN ? ACCENT : '#B7C0C7', isN ? 1 : 0.8);
    });
    dot(g, sx(cells[i].layout[0]), sy(cells[i].layout[1]), 7, PROT, 1, INK);
    if (rows === 0) text(g, 'Thicker lines: closer matches, which count more.', 12, height - 10, { size: 10.5, colour: SOFT, opacity: grow, max: width - 24 });

    // Beats 2 and 3: before and after the blend, then the mask.
    if (rows > 0) {
      const own = hm.cells.indexOf(i) >= 0;
      const c = own ? hm.cells.indexOf(i) : 0;
      const r = [...hm.genes.keys()];
      // A mix: genes our cell measured, and empty ones its matches fill in.
      const empty = r.filter((k) => !hm.mask[c][k]).sort((a, b) => Math.abs(hm.smoothed[c][b]) - Math.abs(hm.smoothed[c][a]));
      const count = narrow ? 6 : 12;
      const pick = [...empty.slice(0, Math.max(2, Math.floor(count / 4))), ...r.filter((k) => hm.mask[c][k])].slice(0, count).sort((a, b) => a - b);
      const nameW = narrow ? 64 : 96;
      const cw = Math.min(54, (width - 24 - nameW) / pick.length);
      const bx = 12 + nameW;
      const y = graphTop + graphH + 22;
      const rh = clamp((height - y - 92) / 3, 14, 34);
      const after = phase(p, 0.45, 0.58);
      const maskOp = phase(p, 0.7, 0.8);
      g.save();
      g.globalAlpha = rows;
      text(g, narrow ? 'our cell, gene by gene' : 'Our cell, gene by gene (colour: above or below the file\u2019s average)', 12, y - 6,
        { size: 10.5, colour: INK, weight: 600, max: width - 24 });
      const rowY = [y + 14, y + 14 + rh + 8, y + 14 + 2 * (rh + 8)];
      text(g, 'before', bx - 8, rowY[0] + rh * 0.66, { size: 10.5, colour: INK, align: 'right' });
      text(g, 'after', bx - 8, rowY[1] + rh * 0.66, { size: 10.5, colour: INK, align: 'right', opacity: after });
      text(g, 'mask', bx - 8, rowY[2] + rh * 0.66, { size: 10.5, colour: INK, align: 'right', opacity: maskOp });
      pick.forEach((k, n) => {
        const x = bx + n * cw;
        const on = !!hm.mask[c][k];
        text(g, hm.genes[k], x + cw / 2, rowY[0] - 4, { size: 9, colour: FAINT, align: 'center', max: cw - 2 });
        if (on) bar(g, x + 1, rowY[0], cw - 2, rh, diverging(hm.z[c][k]) ?? BENCH, 3);
        else hatch(g, x + 1, rowY[0], cw - 2, rh);
        bar(g, x + 1, rowY[1], cw - 2, rh, diverging(hm.smoothed[c][k]) ?? BENCH, 3, after);
        bar(g, x + 1, rowY[2], cw - 2, rh, on ? alpha(ACCENT, 0.15) : BENCH, 3, maskOp);
        text(g, on ? '1' : '0', x + cw / 2, rowY[2] + rh * 0.68, { size: 13, weight: 700, colour: on ? ACCENT : INK, align: 'center', opacity: maskOp });
        if (!on && maskOp > 0) {
          g.save();
          g.globalAlpha *= maskOp;
          g.strokeStyle = PROT;
          g.lineWidth = 2;
          g.strokeRect(x, rowY[0] - 1, cw, rowY[2] + rh - rowY[0] + 2);
          g.restore();
        }
      });
      const yN = rowY[2] + rh + 20;
      if (maskOp > 0) {
        text(g, narrow ? 'Green: empty before, now filled; mask still 0.'
          : 'Green outline: a gene our cell did not measure. It gets a value from its matches, but its mask stays 0.', 12, yN,
        { size: 10.5, colour: SOFT, opacity: maskOp, max: width - 24 });
      } else {
        text(g, 'Hatched: empty before. After: a blend of its own value and its matches\u2019.', 12, yN, { size: 10.5, colour: SOFT, opacity: after, max: width - 24 });
      }
      if (!own) text(g, `(gene by gene, shown for cell ${hm.cells[0] + 1}, a cell like ours)`, 12, yN + 16, { size: 9.5, colour: FAINT });
      g.restore();
    }
  }, {
    describe: (state) => `Cell ${state.cell + 1} and its ${sm.k} closest matches in the file; each value becomes ${Math.round((1 - sm.alpha) * 100)}% its own and ${Math.round(sm.alpha * 100)}% its matches'; the mask is unchanged.`,
    table: (state) => `<table class="support-table"><thead><tr><th>Match</th><th>Weight</th></tr></thead><tbody>${sm.neighbours[state.cell]
      .map((j, k) => `<tr><td>Cell ${j + 1}</td><td class="support-num">${sm.weights[state.cell][k].toFixed(3)}</td></tr>`).join('')}</tbody></table>`,
  });
}
