// Static SVG figures for the Workflow page: each scene's finished frame, as
// shown under reduced motion, without WebGL, and in print. Pure: they return
// strings, and every label goes through escapeHtml, so node --test covers them.

import { escapeHtml } from './panels.js';
import { bandPath, diverging, histogramBars, linear, sequential, ticks } from './workflow-layout.js';

const INK = '#1D2B36';
const FAINT = '#666666';
const LINE = '#E4E3DE';
const ACCENT = '#0066A3';
const n2 = (x) => Math.round(x * 100) / 100;

const svg = (w, h, label, body, cls = 'wf-svg') =>
  `<svg class="${cls}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${escapeHtml(label)}" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;

// The hatch that marks a value the file left missing.
export const HATCH_ID = 'wf-hatch';
export const hatchDefs = () =>
  `<defs><pattern id="${HATCH_ID}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">`
  + `<rect width="5" height="5" fill="#F5F5F3"/><line x1="0" y1="0" x2="0" y2="5" stroke="#B9C2C9" stroke-width="1.6"/></pattern></defs>`;

// A histogram, with an optional marker line at a value.
export function histogramSvg({ counts, edges, width = 520, height = 160, label = 'Histogram', marker = null, markerLabel = '', xLabel = '' }) {
  const plotH = height - 34;
  const bars = histogramBars(counts, width, plotH);
  const x = linear([edges[0], edges[edges.length - 1]], [0, width]);
  let body = bars.map((b) => `<rect x="${n2(b.x)}" y="${n2(b.y)}" width="${n2(b.w)}" height="${n2(b.h)}" fill="${ACCENT}" opacity="0.78"/>`).join('');
  body += `<line x1="0" y1="${plotH}" x2="${width}" y2="${plotH}" stroke="${LINE}"/>`;
  for (const t of ticks(edges[0], edges[edges.length - 1], 6)) {
    body += `<text x="${n2(x(t))}" y="${plotH + 14}" font-size="10" fill="${FAINT}" text-anchor="middle">${escapeHtml(String(t))}</text>`;
  }
  if (marker !== null && Number.isFinite(marker)) {
    const mx = n2(x(marker));
    body += `<line x1="${mx}" y1="0" x2="${mx}" y2="${plotH}" stroke="${INK}" stroke-dasharray="4 3"/>`
      + `<text x="${mx + 4}" y="11" font-size="11" fill="${INK}">${escapeHtml(markerLabel)}</text>`;
  }
  if (xLabel) body += `<text x="${width / 2}" y="${height - 2}" font-size="11" fill="${FAINT}" text-anchor="middle">${escapeHtml(xLabel)}</text>`;
  return svg(width, height, label, body);
}

// A heatmap: rows x columns of values (null where missing, hatched).
export function heatmapSvg({ values, rowLabels = [], colLabels = [], cell = 12, label = 'Heatmap', colour = diverging }) {
  const left = 70;
  const top = 46;
  const rows = values.length;
  const cols = rows ? values[0].length : 0;
  const w = left + cols * cell + 4;
  const h = top + rows * cell + 4;
  let body = hatchDefs();
  values.forEach((row, r) => {
    row.forEach((v, c) => {
      const fill = v === null || v === undefined ? `url(#${HATCH_ID})` : colour(v);
      body += `<rect x="${left + c * cell}" y="${top + r * cell}" width="${cell - 1}" height="${cell - 1}" fill="${fill}"/>`;
    });
    if (rowLabels[r] !== undefined) {
      body += `<text x="${left - 4}" y="${top + r * cell + cell - 3}" font-size="${Math.min(10, cell - 2)}" fill="${FAINT}" text-anchor="end">${escapeHtml(rowLabels[r])}</text>`;
    }
  });
  colLabels.forEach((name, c) => {
    const x = left + c * cell + cell / 2;
    body += `<text transform="translate(${x},${top - 4}) rotate(-60)" font-size="${Math.min(10, cell - 2)}" fill="${FAINT}">${escapeHtml(name)}</text>`;
  });
  return svg(w, h, label, body);
}

// Horizontal bars: [{label, value (0..1 of max), colour, tick (0..1), note}].
export function barsSvg({ items, width = 520, row = 20, labelWidth = 200, label = 'Bars', max = 1 }) {
  const plot = width - labelWidth - 56;
  const x = linear([0, max || 1], [0, plot]);
  let body = '';
  items.forEach((it, i) => {
    const y = i * row;
    body += `<text x="${labelWidth - 6}" y="${y + row * 0.68}" font-size="11" fill="${INK}" text-anchor="end">${escapeHtml(it.label)}</text>`
      + `<rect x="${labelWidth}" y="${y + 3}" width="${n2(Math.max(0, x(it.value ?? 0)))}" height="${row - 7}" rx="2" fill="${it.colour ?? ACCENT}" opacity="${it.dim ? 0.3 : 0.85}"/>`;
    if (Number.isFinite(it.tick)) {
      const tx = n2(labelWidth + x(it.tick));
      body += `<line x1="${tx}" y1="${y + 1}" x2="${tx}" y2="${y + row - 2}" stroke="${INK}" stroke-width="1.5"/>`;
    }
    if (it.note !== undefined) {
      body += `<text x="${labelWidth + x(it.value ?? 0) + 5}" y="${y + row * 0.68}" font-size="10.5" fill="${FAINT}">${escapeHtml(it.note)}</text>`;
    }
  });
  return svg(width, items.length * row + 4, label, body);
}

// The Sankey of a layout from workflow-layout.js's sankey().
export function sankeySvg(layout, { label = 'Flows', leftLabels = {}, rightLabels = {}, colourOf = () => ACCENT, margin = 150 } = {}) {
  const { left, right, links, node, width, height } = layout;
  const total = width + margin * 2;
  let body = '';
  for (const l of links) {
    const a = left.find((n) => n.key === l.source);
    const b = right.find((n) => n.key === l.target);
    if (!a || !b) continue;
    body += `<path d="${bandPath(margin + node, n2(l.y0), margin + b.x, n2(l.y1), n2(l.h))}" fill="${colourOf(l.target)}" opacity="0.32"/>`;
  }
  for (const n of left) {
    body += `<rect x="${margin}" y="${n2(n.y)}" width="${node}" height="${n2(Math.max(1, n.h))}" fill="${INK}"/>`
      + `<text x="${margin - 6}" y="${n2(n.y + n.h / 2 + 4)}" font-size="11" fill="${INK}" text-anchor="end">${escapeHtml(leftLabels[n.key] ?? n.key)} (${n.value})</text>`;
  }
  for (const n of right) {
    body += `<rect x="${margin + n.x}" y="${n2(n.y)}" width="${node}" height="${n2(Math.max(1, n.h))}" fill="${colourOf(n.key)}"/>`
      + `<text x="${margin + n.x + node + 6}" y="${n2(n.y + n.h / 2 + 4)}" font-size="11" fill="${INK}">${escapeHtml(rightLabels[n.key] ?? n.key)} (${n.value})</text>`;
  }
  return svg(total, height + 4, label, body);
}

// The hierarchy: classes, their groups, their lineages, left to right, with
// one path highlighted ({class, group, lineage} names).
export function treeSvg(classOrder, hierarchy, highlight = {}, { label = 'Class, group and lineage' } = {}) {
  const groups = [...new Set(classOrder.map((c) => hierarchy[c].group))];
  const lineages = [...new Set(classOrder.map((c) => hierarchy[c].lineage))];
  const row = 15;
  const h = classOrder.length * row + 10;
  const ys = (list) => Object.fromEntries(list.map((k, i) => [k, 8 + (i + 0.5) * ((h - 16) / list.length)]));
  const [yc, yg, yl] = [ys(classOrder), ys(groups), ys(lineages)];
  const [xc, xg, xl] = [250, 430, 600];
  const on = (kind, k) => highlight[kind] === k;
  let body = '';
  for (const c of classOrder) {
    const { group, lineage } = hierarchy[c];
    const hot = on('class', c) || (on('group', group) && !highlight.class) || (on('lineage', lineage) && !highlight.class && !highlight.group);
    body += `<path d="M${xc},${n2(yc[c])}C${xc + 60},${n2(yc[c])} ${xg - 60},${n2(yg[group])} ${xg},${n2(yg[group])}" fill="none" stroke="${hot ? ACCENT : LINE}" stroke-width="${hot ? 2 : 1}"/>`;
  }
  for (const g of groups) {
    const l = hierarchy[classOrder.find((c) => hierarchy[c].group === g)].lineage;
    const hot = on('group', g) || on('lineage', l) || (highlight.class && hierarchy[highlight.class]?.group === g);
    body += `<path d="M${xg},${n2(yg[g])}C${xg + 60},${n2(yg[g])} ${xl - 60},${n2(yl[l])} ${xl},${n2(yl[l])}" fill="none" stroke="${hot ? ACCENT : LINE}" stroke-width="${hot ? 2 : 1}"/>`;
  }
  const textAt = (x, y, t, hot, anchor) => `<text x="${x}" y="${n2(y + 4)}" font-size="11" text-anchor="${anchor}" fill="${hot ? ACCENT : INK}" font-weight="${hot ? 600 : 400}">${escapeHtml(t)}</text>`;
  for (const c of classOrder) body += textAt(xc - 6, yc[c], c, on('class', c), 'end');
  for (const g of groups) body += textAt(xg, yg[g] - 8, g, on('group', g), 'middle');
  for (const l of lineages) body += textAt(xl + 6, yl[l], l, on('lineage', l), 'start');
  return svg(720, h, label, body);
}

// The UpSet strip: which combinations of sources found how many genes.
export function upsetSvg(combinations, sourceNames, { label = 'Genes by source combination', limit = 12 } = {}) {
  const shown = combinations.slice(0, limit);
  const colW = 34;
  const left = 190;
  const barH = 110;
  const row = 16;
  const max = Math.max(1, ...shown.map((c) => c.genes));
  let body = '';
  shown.forEach((c, i) => {
    const x = left + i * colW;
    const h = (c.genes / max) * barH;
    body += `<rect x="${x + 6}" y="${barH - h}" width="${colW - 12}" height="${n2(h)}" fill="${ACCENT}" opacity="0.8"/>`
      + `<text x="${x + colW / 2}" y="${barH - h - 3}" font-size="9.5" fill="${FAINT}" text-anchor="middle">${c.genes}</text>`;
    const on = [...c.sources].map((b) => b === '1');
    const ys = on.map((v, k) => (v ? barH + 14 + k * row : null)).filter((y) => y !== null);
    if (ys.length > 1) body += `<line x1="${x + colW / 2}" y1="${Math.min(...ys)}" x2="${x + colW / 2}" y2="${Math.max(...ys)}" stroke="${INK}" stroke-width="2"/>`;
    on.forEach((v, k) => {
      body += `<circle cx="${x + colW / 2}" cy="${barH + 14 + k * row}" r="4.5" fill="${v ? INK : LINE}"/>`;
    });
  });
  sourceNames.forEach((name, k) => {
    body += `<text x="${left - 8}" y="${barH + 18 + k * row}" font-size="11" fill="${INK}" text-anchor="end">${escapeHtml(name)}</text>`;
  });
  return svg(left + shown.length * colW + 8, barH + 14 + sourceNames.length * row + 6, label, body);
}

// A graph: nodes [{x, y, colour}], edges [[a, b, weight]], one node highlighted.
export function networkSvg(nodes, edges, { width = 520, height = 360, focus = -1, label = 'Neighbour graph' } = {}) {
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const sx = linear([Math.min(...xs), Math.max(...xs)], [16, width - 16]);
  const sy = linear([Math.min(...ys), Math.max(...ys)], [height - 16, 16]);
  let body = '';
  for (const [a, b, w] of edges) {
    body += `<line x1="${n2(sx(nodes[a].x))}" y1="${n2(sy(nodes[a].y))}" x2="${n2(sx(nodes[b].x))}" y2="${n2(sy(nodes[b].y))}" stroke="${ACCENT}" stroke-width="${n2(0.6 + 6 * w)}" opacity="0.55"/>`;
  }
  nodes.forEach((n, i) => {
    body += `<circle cx="${n2(sx(n.x))}" cy="${n2(sy(n.y))}" r="${i === focus ? 6 : 3}" fill="${n.colour ?? INK}" stroke="${i === focus ? INK : 'none'}" stroke-width="2"/>`;
  });
  return svg(width, height, label, body);
}

// A recorded ROC curve with its AUROC.
export function rocSvg(curve, { size = 200, label = 'ROC curve', auroc = null } = {}) {
  const s = linear([0, 1], [24, size - 8]);
  const sy = linear([0, 1], [size - 24, 8]);
  const pts = curve.map(([f, t]) => `${n2(s(f))},${n2(sy(t))}`).join(' ');
  let body = `<rect x="24" y="8" width="${size - 32}" height="${size - 32}" fill="none" stroke="${LINE}"/>`
    + `<line x1="${s(0)}" y1="${sy(0)}" x2="${s(1)}" y2="${sy(1)}" stroke="${LINE}" stroke-dasharray="3 3"/>`
    + `<polyline points="${pts}" fill="none" stroke="${ACCENT}" stroke-width="2"/>`
    + `<text x="${size / 2 + 8}" y="${size - 6}" font-size="10" fill="${FAINT}" text-anchor="middle">false positive rate</text>`
    + `<text transform="translate(10,${size / 2 - 8}) rotate(-90)" font-size="10" fill="${FAINT}" text-anchor="middle">true positive rate</text>`;
  if (auroc !== null) body += `<text x="${size - 12}" y="${size - 30}" font-size="12" fill="${INK}" text-anchor="end">AUROC ${escapeHtml(auroc)}</text>`;
  return svg(size, size, label, body);
}

// A strip of values in [0, 1] as small squares (a barcode).
export function stripSvg(values, { width = 520, height = 26, label = 'Strip', colour = sequential } = {}) {
  const w = width / Math.max(1, values.length);
  const body = values.map((v, i) => `<rect x="${n2(i * w)}" y="0" width="${n2(Math.max(0.5, w))}" height="${height}" fill="${colour(v)}"/>`).join('');
  return svg(width, height, label, body);
}
