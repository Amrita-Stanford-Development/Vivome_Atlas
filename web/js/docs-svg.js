// The Docs section's data figures, drawn from web/data/docs.json. Pure:
// each builder takes the docs data and returns an SVG string, and every word
// goes through escapeHtml, so node --test covers them. Every number a figure
// writes is a record's text (docs-data.js docsText); a pending record writes
// Pending and draws nothing. Colours are the accent, the ink and greys only:
// what a mark means is said in words or by its shape, never by colour alone.

import { escapeHtml } from './panels.js';
import { isMeasured } from './manifest.js';
import { docsRecord, docsText } from './docs-data.js';
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

// ---- what the old rule read wrongly in the bank (Step 1) ----

export function oldRuleSvg(docs) {
  const rows = [
    { label: 'Raw (linear) tables', n: 'rl_step1_linear', wrong: 'rl_step1_linear_misread', reads: 'read as log' },
    { label: 'Log tables', n: 'rl_step1_log', wrong: 'rl_step1_log_misread', reads: 'read as raw' },
  ];
  const left = 170;
  const plot = 300;
  const max = Math.max(1, ...rows.map((r) => value(docs, r.n) ?? 0));
  const x = linear([0, max], [0, plot]);
  let body = text(0, 14, `The old rule: raw when the middle value is above ${say(docs, 'rl_median_rule')}`, { weight: 600 });
  rows.forEach((r, i) => {
    const y = 34 + i * 34;
    const n = value(docs, r.n) ?? 0;
    const wrong = value(docs, r.wrong) ?? 0;
    body += text(left - 8, y + 13, r.label, { anchor: 'end' })
      + `<rect data-bar="${r.n}" x="${left}" y="${y}" width="${n2(x(n))}" height="18" rx="2" fill="${PALE}"/>`
      + `<rect data-bar="${r.wrong}" x="${left}" y="${y}" width="${n2(x(wrong))}" height="18" rx="2" fill="${INK}"/>`;
    const note = isMeasured(docsRecord(docs, r.n)) && isMeasured(docsRecord(docs, r.wrong))
      ? `${say(docs, r.wrong)} of ${say(docs, r.n)} ${r.reads}` : 'Pending';
    body += text(left + x(n) + 8, y + 13, note, { fill: FAINT });
  });
  body += `<rect x="${left}" y="106" width="12" height="10" fill="${INK}"/>` + text(left + 18, 115, 'read wrongly', { size: 11, fill: FAINT })
    + `<rect x="${left + 110}" y="106" width="12" height="10" fill="${PALE}"/>` + text(left + 128, 115, 'read right', { size: 11, fill: FAINT });
  return svg(124, 'What the old rule read wrongly among the bank\'s tables, raw and log', body);
}

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
        + text(noteX, y + 25, broken ? 'promise broken' : 'promise holds', { size: 11.5, fill: INK, weight: broken ? 600 : 400 });
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
