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

// Words a sentence quotes from the data files (not numbers): a file's
// column names, an example of a raw column header.
const TEXTS = {
  annotation_columns: (w) => (w?.raw?.pbmc240?.parse?.annotation_columns ?? []).join(', '),
  header_example: (w) => w?.raw?.pbmc240?.parse?.header_examples?.[0]?.[0] ?? '',
};
export function wfText(workflow, key) {
  const text = TEXTS[key]?.(workflow);
  return text ? text : PENDING_LABEL;
}

// ---- the traced cells ----

// Outcomes in plain words, for readers new to the field: short labels for
// buttons and charts, and the full reason a cell gets no answer.
export const OUTCOME_LABELS = {
  class: 'named one cell type',
  group: 'narrowed to a family',
  lineage: 'narrowed to a branch',
  ambiguous_between_classes: 'no answer: looks like several kinds',
  no_confident_label: 'no answer: no type stands out',
  outside_supported_region: 'no answer: unlike any known cell',
  coverage_too_low: 'no answer: too little measured',
};
export const OUTCOME_ORDER = Object.keys(OUTCOME_LABELS);
export const ANSWERED = new Set(['class', 'group', 'lineage']);

export const NO_ANSWER_REASONS = {
  ambiguous_between_classes: 'the cell looks like several different kinds of cell, so the model does not pick one',
  no_confident_label: 'no cell type stands out clearly enough',
  outside_supported_region: 'the cell looks unlike any blood cell the model has learned',
  coverage_too_low: 'too little was measured in this cell to judge',
};

// What a family or a branch holds, in plain words.
export const LINEAGE_PLAIN = {
  lymphoid: 'the branch of T, B and NK cells',
  myeloid: 'the branch of monocytes, neutrophils and their relatives',
  erythroid: 'the branch of red blood cells',
  progenitor: 'the branch of stem and precursor cells',
  other: 'the branch of platelets',
};
export const GROUP_PLAIN = {
  'T cell': 'one of the T cell types',
  'B cell': 'a B cell or a plasma cell',
  'NK cell': 'a natural killer cell',
  'monocyte/macrophage': 'one of the monocyte or macrophage types',
  granulocyte: 'a neutrophil or a basophil',
  'dendritic cell': 'one of the dendritic cell types',
  progenitor: 'a stem or precursor cell',
  erythroid: 'a red blood cell',
  'platelet/megakaryocyte': 'a platelet',
};

// The reference's type names, as a reader would say them.
export const PLAIN_NAMES = {
  'b cell': 'B cell',
  basophil: 'basophil',
  'cd4-positive, alpha-beta t cell': 'CD4 T cell (helper)',
  'cd8-positive, alpha-beta t cell': 'CD8 T cell (killer)',
  'classical monocyte': 'classical monocyte',
  'common myeloid progenitor': 'myeloid progenitor',
  erythrocyte: 'red blood cell',
  'hematopoietic precursor cell': 'blood precursor cell',
  'hematopoietic stem cell': 'blood stem cell',
  'intermediate monocyte': 'intermediate monocyte',
  macrophage: 'macrophage',
  'mature nk t cell': 'NK T cell',
  monocyte: 'monocyte',
  'myeloid dendritic cell': 'myeloid dendritic cell',
  'naive thymus-derived cd4-positive, alpha-beta t cell': 'naive CD4 T cell',
  'natural killer cell': 'natural killer (NK) cell',
  neutrophil: 'neutrophil',
  'non-classical monocyte': 'non-classical monocyte',
  'plasma cell': 'plasma cell',
  'plasmacytoid dendritic cell': 'plasmacytoid dendritic cell',
  platelet: 'platelet',
  'regulatory t cell': 'regulatory T cell',
};
export const plainName = (name) => PLAIN_NAMES[name] ?? name;

export const outcomeOf = (cell) => cell?.outcome;
export const isAnswered = (cell) => ANSWERED.has(cell?.outcome);

// A cell's answer in a sentence: what it names, and how far; or why it has none.
export function answerText(cell) {
  if (!cell) return PENDING_LABEL;
  if (cell.outcome === 'class') return `${plainName(cell.label)}, one cell type`;
  if (cell.outcome === 'group') return `${cell.label}: ${GROUP_PLAIN[cell.label] ?? 'a family of types'}, not narrowed to one type`;
  if (cell.outcome === 'lineage') return `${cell.label}: ${LINEAGE_PLAIN[cell.label] ?? 'a broad branch'}, not narrowed further`;
  return `no answer, because ${NO_ANSWER_REASONS[cell.outcome] ?? cell.outcome}`;
}

// The buttons that pick a cell by its result.
export const OUTCOME_CHIPS = {
  class: 'Named as one type',
  group: 'Narrowed to a family',
  lineage: 'Narrowed to a branch',
  ambiguous_between_classes: 'Looks like several kinds',
  no_confident_label: 'No type stands out',
  outside_supported_region: 'Unlike any known cell',
  coverage_too_low: 'Too little measured',
};

// The three ways of practising that were compared (step 4), in plain words.
export const DESIGN_NAMES = {
  'H module, uniform': 'Groups of genes, random gaps',
  'F2 module, profile': 'Groups of genes, gaps like real files',
  'C mask channel, uniform': 'Genes one by one, random gaps',
};

// The kinds of practice file in the simulated tests (step 12), in plain words.
export const PRACTICE_KINDS = {
  single: 'one type only', narrow: '2 or 3 types', mixed: '5 or 8 types', lineage: 'one branch',
  pbmc: 'like a blood sample', scope2: 'like the SCoPE2 study',
};

// What each result means, in a sentence under its button. VivOME answers as
// precisely as it can be sure of, like reading the address on a letter.
export const OUTCOME_NOTES = {
  class: 'It could tell the exact type, like reading the full street address. For example: B cell.',
  group: 'It knew the family but not the exact member, like knowing the street but not the house. For example: a T cell, without saying which kind of T cell.',
  lineage: 'It only knew the broad branch, like knowing the city. For example: lymphoid, the branch that holds T cells, B cells and NK cells.',
  ambiguous_between_classes: 'Two or more types fit about equally well, so it did not guess.',
  no_confident_label: 'No single type fit well enough to name.',
  outside_supported_region: 'The cell did not resemble anything VivOME learned from.',
  coverage_too_low: 'Too few proteins were measured in the cell to judge.',
};

// What VivOME says about a cell, as whole sentences for a reader new to it.
export function answerSentence(cell) {
  if (!cell) return PENDING_LABEL;
  if (cell.outcome === 'class') return `It names one type: ${plainName(cell.label)}.`;
  if (cell.outcome === 'group') {
    return `It narrows the cell to a family, ${cell.label}: ${GROUP_PLAIN[cell.label] ?? 'one of a few related types'}. It cannot tell which one.`;
  }
  if (cell.outcome === 'lineage') {
    return `It narrows the cell to a broad branch, ${cell.label}: ${LINEAGE_PLAIN[cell.label] ?? 'a branch of related types'}. It cannot narrow it further.`;
  }
  const reason = NO_ANSWER_REASONS[cell.outcome] ?? cell.outcome;
  return `No answer. ${reason.charAt(0).toUpperCase()}${reason.slice(1)}.`;
}

// The same, short enough for a label in a figure.
export function answerShort(cell) {
  if (!cell) return PENDING_LABEL;
  if (cell.outcome === 'class') return plainName(cell.label);
  if (isAnswered(cell)) return `${cell.label} (${cell.outcome === 'group' ? 'a family' : 'a branch'})`;
  const text = OUTCOME_LABELS[cell.outcome] ?? cell.outcome;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// The best guess in words, with its probability.
export function guessText(cell, classOrder) {
  if (!cell || cell.guess === null || cell.guess === undefined) return 'none, too little was measured';
  return `${plainName(classOrder[cell.guess])} (probability ${(cell.guess_probability * 100).toFixed(1)}%)`;
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
    // Cells are numbered from 1 for readers; the file's run name also matches.
    if (out.length < limit && (String(i + 1) === q || (q.length > 2 && c.id.toLowerCase().includes(q)))) out.push(i);
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
