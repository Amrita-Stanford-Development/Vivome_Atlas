// Loading, checking and reading web/data/manuscript.json, the Manuscript
// page's records (scripts/build_manuscript.py; docs/web/manuscript.md).
// Pure: no DOM, so node --test covers it. Every number the page cites is a
// record, shown through manifest.js's isMeasured guard, as the manifest's are.

import { PENDING_LABEL, isMeasured } from './manifest.js';
import { escapeHtml } from './panels.js';
import { formatRecord } from './workflow-data.js';

export const MANUSCRIPT_SCHEMA = '1';
const REQUIRED_KEYS = ['schema_version', 'built_for', 'sources', 'records'];

// The caveat tags an evidence item may carry, and what each means.
export const CAVEATS = {
  development: 'development data: used while the model was built',
  'in-sample': 'in-sample: the one tuned weight was chosen on these data',
  'post-hoc': 'post-hoc: the labels were read at an earlier scoring',
  'internal held-out': 'internal held-out: locked before development, scored once',
  'simulated RNA': 'simulated RNA uploads, not protein',
  pending: 'not measured yet',
};

export function validateManuscript(manuscript) {
  if (!manuscript || typeof manuscript !== 'object') throw new Error('Manuscript data is not an object');
  for (const key of REQUIRED_KEYS) {
    if (!(key in manuscript)) throw new Error(`Manuscript data missing required key: ${key}`);
  }
  if (manuscript.schema_version !== MANUSCRIPT_SCHEMA) {
    throw new Error(`Manuscript schema_version ${manuscript.schema_version} is not supported (expected ${MANUSCRIPT_SCHEMA})`);
  }
  return manuscript;
}

export async function loadManuscript(url = './data/manuscript.json') {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Manuscript data fetch failed: ${response.status} ${response.statusText}`);
  return validateManuscript(await response.json());
}

// The two files are built together (scripts/build_manifest.py); a page that
// gets them from different releases says so instead of mixing them.
export function checkSync(manifest, manuscript) {
  const problems = [];
  const built = manuscript?.built_for ?? {};
  if (built.atlas_version !== manifest?.atlas_version) {
    problems.push(`the manuscript data is for atlas ${built.atlas_version ?? 'unknown'}, the manifest for ${manifest?.atlas_version ?? 'unknown'}`);
  }
  if (built.model_name !== manifest?.model?.name) {
    problems.push(`the manuscript data is for ${built.model_name ?? 'an unknown model'}, the manifest for ${manifest?.model?.name ?? 'an unknown model'}`);
  }
  return { ok: problems.length === 0, problems };
}

// A record's text. Shares are fractions: pct1 and pct2 show one or two
// decimals; pp is a difference in percentage points without its sign (the
// sentence says which way). The Workflow page's formats pass through.
export function formatManuscript(record) {
  if (!isMeasured(record)) return PENDING_LABEL;
  const v = Number(record.value);
  switch (record.format) {
    case 'pct1': return `${(v * 100).toFixed(1)}%`;
    case 'pct2': return `${(v * 100).toFixed(2)}%`;
    case 'pp': return Math.abs(v * 100).toFixed(2);
    default: return formatRecord(record);
  }
}

export const recordFor = (manuscript, key) => manuscript?.records?.[key];

// The text a data-ms slot shows, escaped, with the record's basis as its title.
export function msFact(manuscript, key) {
  const record = recordFor(manuscript, key);
  if (!isMeasured(record)) return `<span class="pending">${PENDING_LABEL}</span>`;
  return escapeHtml(formatManuscript(record));
}

export function msBasis(manuscript, key) {
  const record = recordFor(manuscript, key);
  if (isMeasured(record)) return record.basis ?? '';
  return record?.note ?? 'no record';
}
