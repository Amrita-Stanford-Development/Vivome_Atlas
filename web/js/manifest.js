// Loading and formatting for web/data/atlas_manifest.json.
// Pure functions only — no DOM access — so this runs under `node --test`.

export const PENDING_LABEL = 'Pending';
export const SCHEMA_VERSION = '1.0';

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
  if (manifest.schema_version !== SCHEMA_VERSION) {
    throw new Error(
      `Manifest schema_version ${manifest.schema_version} is not supported (expected ${SCHEMA_VERSION})`
    );
  }
  return manifest;
}

export async function loadManifest(url = './data/atlas_manifest.json') {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Manifest fetch failed: ${response.status} ${response.statusText}`);
  }
  return validateManifest(await response.json());
}

// A metric is displayable only when it is explicitly measured with a non-null
// value. Everything else — pending, absent, malformed — renders as Pending.
// This is the single guard that keeps unmeasured quantities off the page.
export function isMeasured(metric) {
  return metric?.status === 'measured'
    && metric.value !== null
    && Number.isFinite(Number(metric.value));
}

export function formatMetric(metric, digits = 3) {
  return isMeasured(metric) ? Number(metric.value).toFixed(digits) : PENDING_LABEL;
}

export function formatPercent(metric) {
  return isMeasured(metric) ? `${(Number(metric.value) * 100).toFixed(1)}%` : PENDING_LABEL;
}

// measured() records carry `basis`, pending() records carry `phase`; the two
// shapes are disjoint, so a single coalesce covers both.
export function metricBasis(metric) {
  return metric?.basis ?? metric?.phase ?? '';
}

// Counts are bare scalars in the schema rather than metric records, so they
// need their own guard — without one a truncated manifest renders "NaN" or
// "undefined" as an authoritative cell count.
const COUNT_FORMAT = new Intl.NumberFormat('en-US');

export function formatCount(value) {
  if (value === null || value === undefined) return PENDING_LABEL;
  const n = Number(value);
  return Number.isFinite(n) ? COUNT_FORMAT.format(n) : PENDING_LABEL;
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
