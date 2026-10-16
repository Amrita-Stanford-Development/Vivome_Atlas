// Loading, checking and reading web/data/workflow.json, the Workflow page's
// companion to the manifest (scripts/build_workflow.py; docs/web/workflow.md).
// Pure: no DOM, so node --test covers it. Every number a sentence cites is a
// record, shown through manifest.js's isMeasured guard, as the manifest's are.

import { PENDING_LABEL, formatCount, isMeasured } from './manifest.js';
import { escapeHtml } from './panels.js';

export const WORKFLOW_SCHEMA = '1';
const REQUIRED_KEYS = ['schema_version', 'built_for', 'facts', 'reference', 'class_order', 'gene_space', 'raw',
  'training', 'trace', 'evaluation', 'service'];

export function validateWorkflow(workflow) {
  if (!workflow || typeof workflow !== 'object') throw new Error('Workflow data is not an object');
  for (const key of REQUIRED_KEYS) {
    if (!(key in workflow)) throw new Error(`Workflow data missing required key: ${key}`);
  }
  if (workflow.schema_version !== WORKFLOW_SCHEMA) {
    throw new Error(`Workflow schema_version ${workflow.schema_version} is not supported (expected ${WORKFLOW_SCHEMA})`);
  }
  return workflow;
}

export async function loadWorkflow(url = './data/workflow.json') {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Workflow data fetch failed: ${response.status} ${response.statusText}`);
  return validateWorkflow(await response.json());
}

// The two files are built together (scripts/build_manifest.py); a page that
// gets one from one release and one from another says so instead of mixing them.
export function checkSync(manifest, workflow) {
  const problems = [];
  const built = workflow?.built_for ?? {};
  if (built.atlas_version !== manifest?.atlas_version) {
    problems.push(`the workflow data is for atlas ${built.atlas_version ?? 'unknown'}, the manifest for ${manifest?.atlas_version ?? 'unknown'}`);
  }
  if (built.model_name !== manifest?.model?.name) {
    problems.push(`the workflow data is for ${built.model_name ?? 'an unknown model'}, the manifest for ${manifest?.model?.name ?? 'an unknown model'}`);
  }
  return { ok: problems.length === 0, problems };
}

// ---- records ----

const DECIMALS = new Intl.NumberFormat('en-US', { maximumFractionDigits: 6 });

export function formatRecord(record) {
  if (!isMeasured(record)) return PENDING_LABEL;
  const v = Number(record.value);
  switch (record.format) {
    case 'percent': return `${(v * 100).toFixed(1).replace(/\.0$/, '')}%`;
    case 'fixed2': return v.toFixed(2);
    case 'fixed3': return v.toFixed(3);
    case 'fixed4': return v.toFixed(4);
    case 'points': return `${v >= 0 ? '+' : '−'}${Math.abs(v * 100).toFixed(2)}`;
    case 'plain': return DECIMALS.format(v);
    default: return formatCount(v);
  }
}

// A record by key: a name in `facts`, or a dotted path from the root
// ("training.recipe.epochs", "evaluation.heldout.0.value").
export function recordAt(workflow, key) {
  if (!workflow || typeof key !== 'string') return undefined;
  if (!key.includes('.')) return workflow.facts?.[key];
  return key.split('.').reduce((node, part) => (node == null ? undefined : node[part]), workflow);
}

// The text a data-wf slot shows, escaped.
export function wfFact(workflow, key) {
  const record = recordAt(workflow, key);
  return isMeasured(record) ? escapeHtml(formatRecord(record)) : `<span class="pending">${PENDING_LABEL}</span>`;
}

// ---- the traced cells ----

export const OUTCOME_LABELS = {
  class: 'one class',
  group: 'a group',
  lineage: 'a lineage',
  ambiguous_between_classes: 'ambiguous',
  no_confident_label: 'no confident label',
  outside_supported_region: 'outside the reference',
  coverage_too_low: 'too few genes',
};
export const OUTCOME_ORDER = Object.keys(OUTCOME_LABELS);
export const ANSWERED = new Set(['class', 'group', 'lineage']);

export const outcomeOf = (cell) => cell?.outcome;
export const isAnswered = (cell) => ANSWERED.has(cell?.outcome);

// A cell's answer in words: the label it names, or why it has none.
export function answerText(cell) {
  if (!cell) return PENDING_LABEL;
  if (isAnswered(cell)) return `${cell.label} (${OUTCOME_LABELS[cell.outcome]})`;
  return `no answer: ${OUTCOME_LABELS[cell.outcome] ?? cell.outcome}`;
}

export function storyCells(workflow) {
  const cells = workflow?.trace?.cells ?? [];
  return (workflow?.trace?.story?.cells ?? []).map((index) => ({ index, cell: cells[index], detail: detailFor(workflow, index) }));
}

export function detailFor(workflow, index) {
  return (workflow?.trace?.detail ?? []).find((d) => d.cell === index) ?? null;
}

// The story cell to show for a followed cell: its own detail when it has
// one, else the story cell with the same outcome, else the first.
export function storyFor(workflow, index) {
  const own = detailFor(workflow, index);
  if (own) return own;
  const cells = workflow?.trace?.cells ?? [];
  const kind = cells[index]?.outcome;
  const same = (workflow?.trace?.detail ?? []).find((d) => cells[d.cell]?.outcome === kind);
  return same ?? workflow?.trace?.detail?.[0] ?? null;
}

export function searchCells(workflow, query, limit = 8) {
  const q = String(query ?? '').trim().toLowerCase();
  if (!q) return [];
  const out = [];
  (workflow?.trace?.cells ?? []).forEach((c, i) => {
    if (out.length < limit && (c.id.toLowerCase().includes(q) || String(i) === q)) out.push(i);
  });
  return out;
}

// The raw rows to show for the story runs: the first n of their recorded
// rows seen in at least two of the runs, then the others, in file order.
export function snippetRows(details, n = 10) {
  const rows = details?.[0]?.raw_row ?? [];
  const seen = (g) => details.filter((d) => d.raw_row[g]?.[1] !== null && d.raw_row[g]?.[1] !== undefined).length;
  const busy = [...rows.keys()].filter((g) => seen(g) >= 2);
  const rest = [...rows.keys()].filter((g) => seen(g) < 2);
  return [...busy, ...rest].slice(0, n).sort((a, b) => a - b);
}

export function outcomeCounts(cells) {
  const counts = Object.fromEntries(OUTCOME_ORDER.map((k) => [k, 0]));
  for (const c of cells ?? []) if (c.outcome in counts) counts[c.outcome] += 1;
  return counts;
}

// Indices of the k largest values, largest first; ties keep their order.
export function topK(values, k) {
  return [...(values ?? []).keys()]
    .sort((a, b) => (values[b] - values[a]) || (a - b))
    .slice(0, Math.max(0, k));
}

// ---- genes ----

// The packed gene lookup (gene_space.genes, sorted; gene_space.gene_flags,
// one bit per source, first source in the top bit).
export function geneLookup(workflow, symbol) {
  const genes = workflow?.gene_space?.genes ?? [];
  const target = String(symbol ?? '').trim().toUpperCase();
  let lo = 0;
  let hi = genes.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (genes[mid] === target) {
      const order = workflow.gene_space.source_order ?? [];
      const flags = workflow.gene_space.gene_flags[mid];
      const sources = (workflow.gene_space.sources ?? [])
        .filter((s) => (flags >> (order.length - 1 - order.indexOf(s.key))) & 1)
        .map((s) => s.name);
      return { gene: target, index: mid, sources };
    }
    if (genes[mid] < target) lo = mid + 1;
    else hi = mid - 1;
  }
  return null;
}

// A packed boolean vector (scripts/trace_workflow.py, bits()): base64 of
// bytes, first flag in the top bit. Returns n values, each 0 or 1.
export function decodeBits(base64, n) {
  const bytes = typeof atob === 'function'
    ? Uint8Array.from(atob(base64 ?? ''), (ch) => ch.charCodeAt(0))
    : new Uint8Array(0);
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i += 1) out[i] = (bytes[i >> 3] >> (7 - (i & 7))) & 1;
  return out;
}

// ---- colour: the atlas viewer's cell-type palette, by class position ----
// (web/atlas.html, colorPalette, over the sorted class names; the reference's
// class order is that sorted order, so position i takes slot i.)
export const CLASS_COLOURS = [
  '#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948',
  '#1f5ea8', '#b85020', '#13875e', '#9c6b00', '#b8406f', '#3d7a1f', '#7a5cc4', '#a8322f',
  '#5b9be6', '#c77a3e', '#4cc496', '#c49a1c', '#d05f95', '#6f9e2e',
];

export const classColour = (i) => CLASS_COLOURS[((i % CLASS_COLOURS.length) + CLASS_COLOURS.length) % CLASS_COLOURS.length];
