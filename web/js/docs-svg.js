// The Docs section's data figures, drawn from web/data/docs.json. Pure:
// each builder takes the docs data and returns an SVG string, and every word
// goes through escapeHtml, so node --test covers them. Every number a figure
// writes is a record's text (docs-data.js docsText); a pending record writes
// Pending and draws nothing. Colours are the accent, the ink and greys only:
// what a mark means is said in words or by its shape, never by colour alone.

import { escapeHtml } from './panels.js';
import { isMeasured } from './manifest.js';
import { docsRecord, docsSeries, docsText } from './docs-data.js';
import { linear } from './workflow-layout.js';

const INK = '#1D2B36';
const FAINT = '#666666';
const LINE = '#E4E3DE';
const ACCENT = '#0066A3';
const PALE = '#A9CBE2';
const WIDTH = 640;
const n2 = (x) => Math.round(x * 100) / 100;

const value = (docs, key) => {
  const record = docsRecord(docs, key);
  return isMeasured(record) ? Number(record.value) : null;
};
const say = (docs, key) => docsText(docs, key);

const svg = (h, label, body) =>
  `<svg class="docs-svg" viewBox="0 0 ${WIDTH} ${h}" role="img" aria-label="${escapeHtml(label)}" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
const text = (x, y, words, { size = 12, fill = INK, anchor = 'start', weight = 400 } = {}) =>
  `<text x="${n2(x)}" y="${n2(y)}" font-size="${size}" fill="${fill}" text-anchor="${anchor}"${weight !== 400 ? ` font-weight="${weight}"` : ''}>${escapeHtml(words)}</text>`;

// A figure whose data is not there says so, and draws nothing.
const pendingSvg = (what) => svg(60, `${what}: Pending`, text(0, 30, 'Pending', { fill: FAINT }));

// ---- what the old rule read wrongly in the bank (Step 1) ----

// A dot for each bank table at its median measured value, on a scale where
// each labelled step is a hundred times the last, raw tables above, log tables
// below, and the old rule's line at its median. A table the rule read wrongly
// is a filled dot, one it read right a ring. A log table with negative values
// has no place on the scale (the rule reads it as log whatever its median), so
// it sits in a box of its own at the left.
export function oldRuleSvg(docs) {
  const series = docsSeries(docs, 'bank_medians');
  if (!series || !isMeasured(docsRecord(docs, 'rl_median_rule'))) return pendingSvg('The bank\'s tables and the old rule');
  const left = 150;
  const right = WIDTH - 10;
  const x = (v) => left + ((Math.log10(v) - series.lo_exp) / (series.hi_exp - series.lo_exp)) * (right - left);
  const lanes = [
    { label: 'raw', title: 'Raw tables', n: 'rl_step1_linear', wrong: 'rl_step1_linear_misread', reads: 'read as log', y: 64 },
    { label: 'log', title: 'Log tables', n: 'rl_step1_log', wrong: 'rl_step1_log_misread', reads: 'read as raw', y: 140 },
  ];
  let body = text(0, 14, 'Each bank table\'s median measured value', { weight: 600 });
  const rx = n2(x(value(docs, 'rl_median_rule')));
  body += `<line class="docs-rule" x1="${rx}" y1="24" x2="${rx}" y2="198" stroke="${INK}" stroke-dasharray="5 4"/>`
    + text(rx + 6, 34, `the old rule's line: ${say(docs, 'rl_median_rule')}`, { size: 11.5 })
    + text(rx - 6, 194, 'below it: read as log', { size: 11, fill: FAINT, anchor: 'end' })
    + text(rx + 6, 194, 'above it: read as raw', { size: 11, fill: FAINT });
  for (const lane of lanes) {
    body += text(left - 12, lane.y + 4, lane.title, { anchor: 'end' })
      + `<line x1="${left}" y1="${lane.y}" x2="${right}" y2="${lane.y}" stroke="${LINE}"/>`;
    const rows = series.rows.filter((r) => r.label === lane.label && !r.negatives).sort((a, b) => a.median - b.median);
    // Dots closer than a dot's width stack upwards, so each one shows.
    const placed = [];
    for (const r of rows) {
      const cx = x(r.median);
      let level = 0;
      while (placed.some((p) => p.level === level && Math.abs(p.cx - cx) < 9)) level += 1;
      placed.push({ cx, level });
      body += `<circle data-table="${escapeHtml(r.id)}" data-misread="${r.misread}" cx="${n2(cx)}" cy="${lane.y - level * 9}" r="4.2" `
        + `fill="${r.misread ? INK : '#FFFFFF'}" stroke="${r.misread ? INK : ACCENT}" stroke-width="1.5"/>`;
    }
    const note = isMeasured(docsRecord(docs, lane.n)) && isMeasured(docsRecord(docs, lane.wrong))
      ? `${say(docs, lane.wrong)} of ${say(docs, lane.n)} ${lane.reads}` : 'Pending';
    body += text(left - 12, lane.y + 18, note, { anchor: 'end', size: 11, fill: FAINT });
  }
  // The log tables with negative values, in their own box under their lane.
  const neg = series.rows.filter((r) => r.negatives);
  if (neg.length) {
    const by = lanes[1].y + 16;
    body += `<rect x="${left}" y="${by}" width="${neg.length * 11 + 132}" height="20" rx="4" fill="none" stroke="${LINE}"/>`;
    neg.forEach((r, i) => {
      body += `<circle data-table="${escapeHtml(r.id)}" data-misread="${r.misread}" cx="${left + 10 + i * 11}" cy="${by + 10}" r="4.2" `
        + `fill="${r.misread ? INK : '#FFFFFF'}" stroke="${r.misread ? INK : ACCENT}" stroke-width="1.5"/>`;
    });
    body += text(left + 8 + neg.length * 11, by + 14, 'with negative values', { size: 11, fill: FAINT });
  }
  // The scale, with its labels from the series.
  body += `<line x1="${left}" y1="208" x2="${right}" y2="208" stroke="${FAINT}"/>`;
  for (const t of series.ticks) {
    const tx = n2(x(t.value));
    body += `<line x1="${tx}" y1="208" x2="${tx}" y2="213" stroke="${FAINT}"/>` + text(tx, 226, t.label, { size: 11, fill: FAINT, anchor: 'middle' });
  }
  body += `<circle cx="${left + 4}" cy="246" r="4.2" fill="${INK}" stroke="${INK}" stroke-width="1.5"/>`
    + text(left + 14, 250, 'read wrongly by the old rule', { size: 11, fill: FAINT })
    + `<circle cx="${left + 214}" cy="246" r="4.2" fill="#FFFFFF" stroke="${ACCENT}" stroke-width="1.5"/>`
    + text(left + 224, 250, 'read right', { size: 11, fill: FAINT });
  return svg(258, 'Each bank table\'s median measured value, raw tables and log tables, against the old rule\'s line: the raw tables written on a small scale fall below it and are read as log', body);
}

// ---- one real table, raw and as log (the Atlas page's example) ----

function histogram(h, top, left, width, height, fill) {
  const max = Math.max(1, ...h.counts);
  const lo = h.edges[0];
  const hi = h.edges[h.edges.length - 1];
  const x = (v) => left + ((v - lo) / (hi - lo)) * width;
  let out = '';
  h.counts.forEach((c, i) => {
    const bh = (c / max) * height;
    const w = Math.max(0.5, x(h.edges[i + 1]) - x(h.edges[i]) - 1);
    out += `<rect x="${n2(x(h.edges[i]) + 0.5)}" y="${n2(top + height - bh)}" width="${n2(w)}" height="${n2(bh)}" fill="${fill}"/>`;
  });
  out += `<line x1="${left}" y1="${top + height}" x2="${left + width}" y2="${top + height}" stroke="${FAINT}"/>`;
  for (const t of h.ticks) {
    const tx = n2(x(t.value));
    out += `<line x1="${tx}" y1="${top + height}" x2="${tx}" y2="${top + height + 5}" stroke="${FAINT}"/>`
      + text(tx, top + height + 18, t.label, { size: 11, fill: FAINT, anchor: 'middle' });
  }
  return out;
}

export function exampleValuesSvg(docs) {
  const series = docsSeries(docs, 'example_values');
  if (!series) return pendingSvg('The example table\'s values');
  const left = 40;
  const width = WIDTH - 80;
  let body = text(0, 14, 'Written raw: how many values fall at each size', { weight: 600 })
    + histogram(series.raw, 26, left, width, 110, ACCENT);
  const beyond = isMeasured(docsRecord(docs, 'rl_ex_beyond')) && isMeasured(docsRecord(docs, 'rl_ex_max'))
    ? `and ${say(docs, 'rl_ex_beyond')} larger values, up to ${say(docs, 'rl_ex_max')}, beyond the right edge` : 'Pending';
  body += text(WIDTH - 40, 62, 'almost every value crowds into the first few bars', { size: 11.5, fill: FAINT, anchor: 'end' })
    + text(WIDTH - 40, 80, beyond, { size: 11.5, fill: FAINT, anchor: 'end' });
  body += text(0, 196, 'The same values as log2: each step of one is a doubling', { weight: 600 })
    + histogram(series.log2, 208, left, width, 110, INK);
  body += text(WIDTH - 40, 244, 'one hump, close to even on both sides', { size: 11.5, fill: FAINT, anchor: 'end' });
  return svg(346, 'One real protein table\'s values: written raw, they crowd at the left with a long thin tail; as log2, they form one even hump', body);
}

// ---- spread against level in the same table ----

export function exampleSpreadSvg(docs) {
  const series = docsSeries(docs, 'example_spread');
  if (!series || !isMeasured(docsRecord(docs, 'rl_ex_spread_raw')) || !isMeasured(docsRecord(docs, 'rl_ex_spread_log'))) {
    return pendingSvg('Spread against level');
  }
  const left = 70;
  const right = WIDTH - 170;
  const top = 34;
  const height = 170;
  const hi = Math.log10(series.ticks[series.ticks.length - 1].value);
  const y = (v) => top + height - (Math.log10(v) / hi) * height;
  const n = series.raw.length;
  const x = (i) => left + (i / (n - 1)) * (right - left);
  let body = text(0, 14, 'How spread out each group\'s values are, as a multiple of the quietest group\'s', { weight: 600 });
  for (const t of series.ticks) {
    const ty = n2(y(t.value));
    body += `<line x1="${left}" y1="${ty}" x2="${right}" y2="${ty}" stroke="${LINE}"/>`
      + text(left - 8, ty + 4, t.label, { size: 11, fill: FAINT, anchor: 'end' });
  }
  const line = (vals, colour, dashed, square) => {
    let out = `<polyline fill="none" stroke="${colour}" stroke-width="2"${dashed ? ' stroke-dasharray="6 4"' : ''} `
      + `points="${vals.map((v, i) => `${n2(x(i))},${n2(y(v))}`).join(' ')}"/>`;
    vals.forEach((v, i) => {
      out += square
        ? `<rect x="${n2(x(i) - 3.5)}" y="${n2(y(v) - 3.5)}" width="7" height="7" fill="${colour}"/>`
        : `<circle cx="${n2(x(i))}" cy="${n2(y(v))}" r="3.5" fill="${colour}"/>`;
    });
    return out;
  };
  body += line(series.raw, ACCENT, false, false) + line(series.log, INK, true, true);
  body += text(right + 12, y(series.raw[n - 1]) + 4, `raw: ${say(docs, 'rl_ex_spread_raw')} times`, { size: 12 })
    + text(right + 12, y(series.log[n - 1]) + 4, `log2: ${say(docs, 'rl_ex_spread_log')} times`, { size: 12 });
  body += text(left, top + height + 20, 'quietest proteins', { size: 11, fill: FAINT })
    + text(right, top + height + 20, 'busiest proteins', { size: 11, fill: FAINT, anchor: 'end' })
    + text((left + right) / 2, top + height + 20, 'groups of proteins, by level', { size: 11, fill: FAINT, anchor: 'middle' });
  const ly = top + height + 44;
  body += `<circle cx="${left + 4}" cy="${ly - 4}" r="3.5" fill="${ACCENT}"/>` + text(left + 14, ly, 'raw values, solid line', { size: 11, fill: FAINT })
    + `<rect x="${left + 180}" y="${ly - 7.5}" width="7" height="7" fill="${INK}"/>` + text(left + 194, ly, 'log2 values, dashed line', { size: 11, fill: FAINT });
  return svg(ly + 10, 'In the same table, the busiest proteins\' raw values are spread far wider than the quietest\'s; after a log2 the spread is about the same in every group', body);
}

// ---- the lowest scores of S1's log tables, against the threshold ----

const SCORES_KEYS = ['rl_s1_log_cut', 'rl_s1_k', 'rl_ph_cal_below'];
const SCORES_TEST_KEYS = ['rl_s1_log_cut', 'rl_ph_cal_below', 'rl_sc_test_below'];

function scoresSvg(docs, withTest) {
  const series = docsSeries(docs, 's1_log_scores');
  const keys = withTest ? SCORES_TEST_KEYS : SCORES_KEYS;
  if (!series || !keys.every((k) => isMeasured(docsRecord(docs, k)))) return pendingSvg('The lowest scores of the small log tables');
  const cut = value(docs, 'rl_s1_log_cut');
  const left = 74;
  const right = WIDTH - 20;
  const top = 46;
  const height = 190;
  const all = withTest ? [...series.calibration, ...series.test] : series.calibration;
  const lo = Math.floor(Math.min(...all) * 50) / 50;
  const hi = Math.ceil(Math.max(...all) * 50) / 50;
  const y = (v) => top + height - ((v - lo) / (hi - lo)) * height;
  const n = Math.max(series.calibration.length, withTest ? series.test.length : 0);
  const x = (i) => left + 10 + (i / (n - 1)) * (right - left - 20);
  const cy = n2(y(cut));
  let body = text(0, 14, withTest ? 'The lowest scores of the small log tables: calibration and the sealed test'
    : 'The lowest scores of the small log tables in calibration', { weight: 600 })
    + text(0, 31, 'Each mark is one table: the model\'s probability that it is log, lowest first', { size: 11.5, fill: FAINT });
  body += `<line class="docs-threshold" x1="${left}" y1="${cy}" x2="${right}" y2="${cy}" stroke="${INK}" stroke-dasharray="5 4"/>`
    + text(right, cy - 7, `the threshold: ${say(docs, 'rl_s1_log_cut')}`, { size: 11.5, anchor: 'end' })
    + text(left, top + height + 18, 'lowest score', { size: 11, fill: FAINT })
    + text(right, top + height + 18, 'higher scores', { size: 11, fill: FAINT, anchor: 'end' })
    + text(left - 10, top + 8, 'surer', { size: 11, fill: FAINT, anchor: 'end' })
    + text(left - 10, top + height, 'less sure', { size: 11, fill: FAINT, anchor: 'end' });
  const mark = (split, v, i) => {
    const under = v < cut;
    return split === 'calibration'
      ? `<circle data-split="calibration" data-under="${under}" cx="${n2(x(i))}" cy="${n2(y(v))}" r="4.5" fill="${under ? INK : '#FFFFFF'}" stroke="${INK}" stroke-width="1.4"/>`
      : `<rect data-split="test" data-under="${under}" x="${n2(x(i) - 4.5)}" y="${n2(y(v) - 4.5)}" width="9" height="9" fill="${under ? ACCENT : '#FFFFFF'}" stroke="${ACCENT}" stroke-width="1.4"/>`;
  };
  series.calibration.forEach((v, i) => { body += mark('calibration', v, i); });
  if (withTest) series.test.forEach((v, i) => { body += mark('test', v, i); });
  const ly = top + height + 42;
  if (withTest) {
    body += `<circle cx="${left + 4}" cy="${ly - 4}" r="4.5" fill="${INK}" stroke="${INK}"/>`
      + text(left + 14, ly, `calibration (circles): ${say(docs, 'rl_ph_cal_below')} under the threshold`, { size: 11.5 })
      + `<rect x="${left + 294}" y="${ly - 8.5}" width="9" height="9" fill="${ACCENT}" stroke="${ACCENT}"/>`
      + text(left + 310, ly, `sealed test (squares): ${say(docs, 'rl_sc_test_below')} under it`, { size: 11.5 })
      + text(left, ly + 19, 'filled: under the threshold, so the log reading is left out of the answer', { size: 11, fill: FAINT });
    return svg(ly + 28, 'The lowest scores of the small log tables: in calibration a few fall under the threshold; in the sealed test many more do, most of them only a little under', body);
  }
  body += `<circle cx="${left + 4}" cy="${ly - 4}" r="4.5" fill="${INK}" stroke="${INK}"/>`
    + text(left + 14, ly, `filled: ${say(docs, 'rl_ph_cal_below')} under the threshold`, { size: 11.5 })
    + text(left + 200, ly, `the threshold is score number ${say(docs, 'rl_s1_k')}, counting from the lowest`, { size: 11.5, fill: FAINT });
  return svg(ly + 12, 'The lowest scores of the small log tables in calibration, lowest first, with the threshold at the k-th of them', body);
}

export const s1ScoresSvg = (docs) => scoresSvg(docs, false);
export const s1ScoresTestSvg = (docs) => scoresSvg(docs, true);

// ---- where the tables came from (B3) ----

export function corpusFunnelSvg(docs) {
  const plot = WIDTH - 20;
  let body = '';
  let y = 0;
  // The reserve is pale (kept aside), the sealed test is ink; each bar is named in words beside it.
  const FILLS = { reserve: PALE, test: INK };
  const bar = (id, x0, width, yy) => `<rect data-bar="${id}" x="${n2(x0)}" y="${n2(yy)}" width="${n2(width)}" height="16" rx="2" fill="${FILLS[id] ?? ACCENT}"/>`;
  const count = (key) => (isMeasured(docsRecord(docs, key)) ? say(docs, key) : 'Pending');

  // The deposits: the frame, then the part listed and the reserve.
  const frame = value(docs, 'rl_b3_frame') ?? 0;
  const dx = linear([0, Math.max(1, frame)], [0, plot]);
  body += text(0, y + 14, 'Deposits', { weight: 600 });
  y += 24;
  body += text(0, y + 12, `The frame: ${count('rl_b3_frame')} deposits, in a fixed order`);
  body += bar('frame', 0, dx(frame), y + 18);
  y += 44;
  const listed = value(docs, 'rl_b3_listed') ?? 0;
  const reserve = value(docs, 'rl_b3_reserve') ?? 0;
  body += text(0, y + 12, `Listed, in order: ${count('rl_b3_listed')}`);
  body += text(plot, y + 12, `Not listed, the reserve: ${count('rl_b3_reserve')}`, { anchor: 'end' });
  body += bar('listed', 0, dx(listed), y + 18) + bar('reserve', dx(listed), dx(reserve), y + 18);
  y += 56;

  // The tables kept from the listed deposits, then the two splits.
  const kept = value(docs, 'rl_b3_kept') ?? 0;
  const tx = linear([0, Math.max(1, kept)], [0, plot]);
  body += `<line x1="0" y1="${y - 6}" x2="${plot}" y2="${y - 6}" stroke="${LINE}"/>`;
  body += text(0, y + 14, 'Tables, from the listed deposits (a new scale)', { weight: 600 });
  y += 24;
  body += text(0, y + 12, `Kept: ${count('rl_b3_kept')}`);
  body += bar('kept', 0, tx(kept), y + 18);
  y += 44;
  const audited = value(docs, 'rl_b3_after_audit') ?? 0;
  body += text(0, y + 12, `Kept after the hand audit: ${count('rl_b3_after_audit')}`);
  body += bar('after_audit', 0, tx(audited), y + 18);
  y += 44;
  const cal = value(docs, 'rl_b3_calibration') ?? 0;
  const test = value(docs, 'rl_b3_test') ?? 0;
  body += text(0, y + 12, `Calibration: ${count('rl_b3_calibration')}`);
  body += text(plot, y + 12, `Sealed test: ${count('rl_b3_test')}`, { anchor: 'end' });
  body += bar('calibration', 0, tx(cal), y + 18) + bar('test', tx(cal), tx(test), y + 18);
  y += 40;
  return svg(y, 'From the frame of deposits to the tables for calibration and the sealed test', body);
}

// ---- the sealed test against the promise (B7) ----

const GROUPS = [
  ['s1_linear', 'S1, raw tables'],
  ['s1_log', 'S1, log tables'],
  ['s23_linear', 'S2+S3, raw tables'],
  ['s23_log', 'S2+S3, log tables'],
];

export function guaranteeSvg(docs) {
  const left = 124;
  const plot = 230;
  const alpha = value(docs, 'rl_alpha');
  const rates = GROUPS.map(([g]) => value(docs, `rl_b7_${g}_rate`) ?? 0);
  const top = Math.max(alpha ?? 0, ...rates) * 1.2 || 1;
  const perUnit = plot / top;
  const x = (v) => left + v * perUnit;
  const rowTop = 34;
  const row = 42;
  let body = '';
  if (alpha !== null) {
    const ax = n2(x(alpha));
    body += `<line class="docs-promise" x1="${ax}" y1="${rowTop - 8}" x2="${ax}" y2="${rowTop + GROUPS.length * row}" stroke="${INK}" stroke-dasharray="5 4"/>`
      + text(ax, 16, `the promise: at most ${say(docs, 'rl_alpha')} missed`, { anchor: 'middle', size: 11.5 });
  } else {
    body += text(left, 16, 'the promise: Pending', { size: 11.5 });
  }
  GROUPS.forEach(([g, label], i) => {
    const y = rowTop + i * row;
    const rate = value(docs, `rl_b7_${g}_rate`);
    const lower = value(docs, `rl_b7_${g}_lower`);
    const known = rate !== null && lower !== null && alpha !== null
      && isMeasured(docsRecord(docs, `rl_b7_${g}_miss`)) && isMeasured(docsRecord(docs, `rl_b7_${g}_n`));
    const broken = known && lower > alpha;
    body += `<g data-group="${g}" data-broken="${broken}" data-x0="${left}" data-per-unit="${n2(perUnit)}">`
      + text(left - 8, y + 14, label, { anchor: 'end' })
      + `<rect x="${left}" y="${y + 3}" width="${n2((rate ?? 0) * perUnit)}" height="16" rx="2" fill="${PALE}"/>`;
    if (known) {
      body += `<circle cx="${n2(x(lower))}" cy="${y + 11}" r="5.5" fill="${broken ? INK : '#FFFFFF'}" stroke="${INK}" stroke-width="1.6"/>`;
    }
    // Two short lines beside the bar: the count, then the verdict in words.
    const noteX = left + plot + 14;
    if (known) {
      body += text(noteX, y + 10, `${say(docs, `rl_b7_${g}_miss`)} of ${say(docs, `rl_b7_${g}_n`)} missed, lower bound ${say(docs, `rl_b7_${g}_lower`)}`, { size: 11.5, fill: FAINT })
        + text(noteX, y + 25, broken ? 'contradicted' : 'not contradicted', { size: 11.5, fill: INK, weight: broken ? 600 : 400 });
    } else {
      body += text(noteX, y + 14, 'Pending', { size: 11.5, fill: FAINT });
    }
    body += '</g>';
  });
  const legendY = rowTop + GROUPS.length * row + 16;
  body += `<rect x="${left}" y="${legendY - 9}" width="14" height="10" fill="${PALE}"/>`
    + text(left + 20, legendY, 'the share missed', { size: 11, fill: FAINT })
    + `<circle cx="${left + 140}" cy="${legendY - 4}" r="4.5" fill="#FFFFFF" stroke="${INK}" stroke-width="1.5"/>`
    + text(left + 150, legendY, 'its lower bound; filled when above the promise', { size: 11, fill: FAINT });
  return svg(legendY + 8, 'The sealed test: the share of tables missed in each group, against the promise', body);
}

// ---- log tables under the threshold, by share of missing values (post hoc) ----

export function missingBandsSvg(docs) {
  const left = 150;
  const plot = 250;
  const count = value(docs, 'rl_ph_bands');
  const bands = [];
  for (let i = 0; docsRecord(docs, `rl_ph_band${i}_lo`) && (count === null || i < count); i += 1) bands.push(i);
  const share = (i, split) => {
    const below = value(docs, `rl_ph_band${i}_${split}_below`);
    const tables = value(docs, `rl_ph_band${i}_${split}_tables`);
    return below !== null && tables ? below / tables : null;
  };
  const top = Math.max(0.1, ...bands.flatMap((i) => [share(i, 'cal') ?? 0, share(i, 'test') ?? 0])) * 1.1;
  const x = linear([0, top], [0, plot]);
  let body = text(0, 14, 'Missing values in the table', { weight: 600 })
    + text(WIDTH, 14, 'post hoc: looked at after the test', { anchor: 'end', size: 11, fill: FAINT });
  bands.forEach((i, k) => {
    const y = 28 + k * 46;
    const lo = docsRecord(docs, `rl_ph_band${i}_lo`);
    const hi = docsRecord(docs, `rl_ph_band${i}_hi`);
    const label = isMeasured(lo) && isMeasured(hi)
      ? `${say(docs, `rl_ph_band${i}_lo`)} to ${say(docs, `rl_ph_band${i}_hi`)}` : 'Pending';
    body += text(left - 8, y + 24, label, { anchor: 'end' });
    [['cal', 'calibration', PALE, 0], ['test', 'test', ACCENT, 20]].forEach(([split, name, fill, dy]) => {
      const s = share(i, split);
      body += `<rect data-band="${i}" data-split="${split}" data-share="${s === null ? 0 : s.toFixed(4)}" x="${left}" y="${y + dy}" width="${n2(x(s ?? 0))}" height="16" rx="2" fill="${fill}"/>`;
      const known = s !== null && isMeasured(docsRecord(docs, `rl_ph_band${i}_${split}_below`));
      const note = known
        ? `${name}: ${say(docs, `rl_ph_band${i}_${split}_below`)} of ${say(docs, `rl_ph_band${i}_${split}_tables`)} under the threshold`
        : `${name}: Pending`;
      body += text(left + x(s ?? 0) + 8, y + dy + 12, note, { size: 11, fill: FAINT });
    });
  });
  const h = 28 + bands.length * 46 + 4;
  return svg(h, 'Log tables under the threshold, by the share of their values missing: calibration against the sealed test (post hoc)', body);
}

const BUILDERS = {
  old_rule: oldRuleSvg,
  example_values: exampleValuesSvg,
  example_spread: exampleSpreadSvg,
  s1_scores: s1ScoresSvg,
  s1_scores_test: s1ScoresTestSvg,
  corpus_funnel: corpusFunnelSvg,
  guarantee: guaranteeSvg,
  missing_bands: missingBandsSvg,
};

// A figure by the name a page's data-docs-figure attribute gives.
export function drawFigure(name, docs) {
  const build = Object.hasOwn(BUILDERS, name) ? BUILDERS[name] : null;
  if (!build) throw new Error(`no figure named ${name}`);
  return build(docs);
}
