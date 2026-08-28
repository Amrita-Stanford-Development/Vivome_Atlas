// Loading and formatting for Atlas/atlas_manifest.json.
// Pure functions only — no DOM access — so this runs under `node --test`.

export const PENDING_LABEL = 'Pending';

const REQUIRED_KEYS = [
  'schema_version', 'atlas_version', 'generated', 'model',
  'modalities', 'cell_types', 'summary', 'benchmark', 'data_availability',
];

export function validateManifest(manifest) {
  if (!manifest || typeof manifest !== 'object') {
    throw new Error('Manifest is not an object');
  }
  for (const key of REQUIRED_KEYS) {
    if (!(key in manifest)) throw new Error(`Manifest missing required key: ${key}`);
  }
  return manifest;
}

export async function loadManifest(url = './Atlas/atlas_manifest.json') {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Manifest fetch failed: ${response.status} ${response.statusText}`);
  }
  return validateManifest(await response.json());
}

// A metric is displayable only when it is explicitly measured with a non-null
// value. Everything else — pending, absent, malformed — renders as Pending.
// This is the single guard that keeps unmeasured quantities off the page.
function isMeasured(metric) {
  return Boolean(metric)
    && metric.status === 'measured'
    && metric.value !== null
    && metric.value !== undefined
    && Number.isFinite(Number(metric.value));
}

export function formatMetric(metric, digits = 3) {
  return isMeasured(metric) ? Number(metric.value).toFixed(digits) : PENDING_LABEL;
}

export function formatPercent(metric) {
  return isMeasured(metric) ? `${(Number(metric.value) * 100).toFixed(1)}%` : PENDING_LABEL;
}

export function metricBasis(metric) {
  if (!metric) return '';
  return metric.status === 'measured' ? (metric.basis || '') : (metric.phase || '');
}

const SUPPORT_ORDER = { cross_modal: 0, prot_only: 1, rna_only: 2 };

export function supportRows(manifest) {
  return [...manifest.cell_types].sort((a, b) => {
    const bySupport = (SUPPORT_ORDER[a.support] ?? 9) - (SUPPORT_ORDER[b.support] ?? 9);
    return bySupport !== 0 ? bySupport : b.rna_cells - a.rna_cells;
  });
}

const LFS_MAGIC = 'version https://git-lfs.github.com/spec/v1';

export function isLfsPointer(text) {
  return typeof text === 'string' && text.startsWith(LFS_MAGIC);
}
