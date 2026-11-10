// Loading, checking and reading web/data/docs.json, the Docs section's
// records (scripts/build_docs.py). Pure: no DOM, so node --test covers it.
// Every number a Docs page shows is a record, shown through manifest.js's
// isMeasured guard, as the manifest's are; the words around it are typed in
// the page, the numbers never.

import { PENDING_LABEL, isMeasured } from './manifest.js';
import { escapeHtml } from './panels.js';
import { formatManuscript } from './manuscript-data.js';

export const DOCS_SCHEMA = '1';
const REQUIRED_KEYS = ['schema_version', 'built_for', 'sources', 'records', 'steps', 'series'];

export function validateDocs(docs) {
  if (!docs || typeof docs !== 'object') throw new Error('Docs data is not an object');
  for (const key of REQUIRED_KEYS) {
    if (!(key in docs)) throw new Error(`Docs data missing required key: ${key}`);
  }
  if (docs.schema_version !== DOCS_SCHEMA) {
    throw new Error(`Docs schema_version ${docs.schema_version} is not supported (expected ${DOCS_SCHEMA})`);
  }
  return docs;
}

export async function loadDocs(url = './data/docs.json') {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Docs data fetch failed: ${response.status} ${response.statusText}`);
  return validateDocs(await response.json());
}

export const docsRecord = (docs, key) => docs?.records?.[key];

// A record's text, not escaped (the figure builders escape what they draw):
// the manuscript's formats, or Pending.
export function docsText(docs, key) {
  const record = docsRecord(docs, key);
  return isMeasured(record) ? formatManuscript(record) : PENDING_LABEL;
}

// The text a data-docs slot shows, escaped.
export function docsFact(docs, key) {
  const record = docsRecord(docs, key);
  if (!isMeasured(record)) return `<span class="pending">${PENDING_LABEL}</span>`;
  return escapeHtml(formatManuscript(record));
}

// Where a number comes from: its basis, or why it is pending.
export function docsBasis(docs, key) {
  const record = docsRecord(docs, key);
  if (isMeasured(record)) return record.basis ?? '';
  return record?.note ?? 'no record';
}

// A figure's many values (scripts/build_docs.py, "the series"): the series by
// name when every number in it is finite, or null, and the figure says Pending.
export function docsSeries(docs, name) {
  const series = docs?.series?.[name];
  if (!series || typeof series !== 'object') return null;
  const finite = (node) => {
    if (typeof node === 'number') return Number.isFinite(node);
    if (Array.isArray(node)) return node.length > 0 && node.every(finite);
    if (node && typeof node === 'object') return Object.values(node).every(finite);
    return typeof node === 'string' || typeof node === 'boolean';
  };
  return finite(series) ? series : null;
}

// The records each data figure draws (the builders in docs-svg.js), so a test can
// check that every one exists and that every record is shown somewhere; and the
// series it draws, whose axis labels are the only other words it may write.
const GROUPS = ['s1_linear', 's1_log', 's23_linear', 's23_log'];
const BANDS = [0, 1, 2, 3, 4];
export const FIGURE_SERIES = {
  old_rule: 'bank_medians',
  example_values: 'example_values',
  example_spread: 'example_spread',
  s1_scores: 's1_log_scores',
  s1_scores_test: 's1_log_scores',
};
export const FIGURES = {
  old_rule: ['rl_median_rule', 'rl_step1_linear', 'rl_step1_linear_misread', 'rl_step1_log', 'rl_step1_log_misread'],
  example_values: ['rl_ex_values', 'rl_ex_beyond', 'rl_ex_max'],
  example_spread: ['rl_ex_spread_raw', 'rl_ex_spread_log'],
  s1_scores: ['rl_s1_log_cut', 'rl_s1_k', 'rl_ph_cal_below'],
  s1_scores_test: ['rl_s1_log_cut', 'rl_ph_cal_below', 'rl_sc_test_below'],
  corpus_funnel: ['rl_b3_frame', 'rl_b3_listed', 'rl_b3_reserve', 'rl_b3_kept', 'rl_b3_after_audit',
    'rl_b3_calibration', 'rl_b3_test'],
  guarantee: ['rl_alpha', ...GROUPS.flatMap((g) => ['n', 'miss', 'rate', 'lower'].map((f) => `rl_b7_${g}_${f}`))],
  missing_bands: ['rl_ph_bands', ...BANDS.flatMap((i) => ['lo', 'hi', 'cal_tables', 'cal_below', 'test_tables', 'test_below']
    .map((f) => `rl_ph_band${i}_${f}`))],
};

// The three tabs of a topic page, in order. An address names a tab, or an
// element inside one: #did-b7 is the step B7 in "What we did", opened.
export const TABS = ['how', 'did', 'words'];
const ADDRESS = /^#(how|did|words)(?:-([a-z0-9]+(?:-[a-z0-9]+)*))?$/;

export function tabForHash(hash) {
  const m = ADDRESS.exec(hash ?? '');
  if (!m) return { tab: 'how', target: null, open: false };
  const target = m[2] ? `${m[1]}-${m[2]}` : null;
  return { tab: m[1], target, open: m[1] === 'did' && target !== null };
}

// The tab a key moves to from the current one, or null for other keys.
export function nextTab(current, key) {
  const i = Math.max(0, TABS.indexOf(current));
  if (key === 'ArrowRight') return TABS[(TABS.indexOf(current) + 1) % TABS.length];
  if (key === 'ArrowLeft') return TABS[(i + TABS.length - 1) % TABS.length];
  if (key === 'Home') return TABS[0];
  if (key === 'End') return TABS[TABS.length - 1];
  return null;
}
