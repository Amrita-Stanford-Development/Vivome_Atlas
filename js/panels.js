// HTML-string builders for the manifest-driven panels.
// Pure functions only — they return strings and never touch the DOM — so the
// same code is unit-tested under Node and assigned to innerHTML in the browser.

import {
  formatMetric, formatPercent, formatCount, metricBasis, isMeasured,
  supportRows, PENDING_LABEL,
} from './manifest.js';

const HTML_ESCAPES = {
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
};

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

const SUPPORT_LABEL = {
  cross_modal: 'Cross-modal',
  rna_only: 'RNA only',
  prot_only: 'Protein only',
};

const AVAILABILITY_LABEL = {
  available: 'Available',
  lfs_not_fetched: 'Not fetched (Git LFS)',
  not_distributed: 'Not distributed',
};

const table = (headers, rows) =>
  `<table class="support-table"><thead><tr>${
    headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('')
  }</tr></thead><tbody>${rows}</tbody></table>`;

// Renders a metric's text and marks it pending from the single isMeasured
// decision, so a value that later becomes measured stops looking pending
// without any edit here.
function metricText(metric, formatter) {
  const text = formatter(metric);
  return isMeasured(metric) ? text : `<span class="pending">${escapeHtml(text)}</span>`;
}

const metricCell = (metric, formatter) =>
  `<td class="support-num">${metricText(metric, formatter)}` +
  `<span class="metric-basis">${escapeHtml(metricBasis(metric))}</span></td>`;

const cosine4 = (m) => formatMetric(m, 4);

export function errorPanel(err) {
  return `<p class="panel-error">${escapeHtml(err?.message ?? String(err))}</p>`;
}

export function buildSupportSummary(manifest) {
  const s = manifest.summary ?? {};
  const tile = (value, label) =>
    `<div class="support-tile"><div class="support-tile-value">${formatCount(value)}</div>` +
    `<div class="support-tile-label">${escapeHtml(label)}</div></div>`;
  return [
    tile(s.cross_modal, 'Cross-modal'),
    tile(s.rna_only, 'RNA-only'),
    tile(s.total, 'Cell types'),
  ].join('');
}

export function buildSupportTable(manifest) {
  const rows = supportRows(manifest).map((c) => `
    <tr>
      <td class="support-name">${escapeHtml(c.name)}</td>
      <td class="support-num">${formatCount(c.rna_cells)}</td>
      <td class="support-num">${c.prot_cells > 0 ? formatCount(c.prot_cells) : '&mdash;'}</td>
      <td><span class="support-badge badge-${escapeHtml(c.support)}">${
        escapeHtml(SUPPORT_LABEL[c.support] ?? c.support)
      }</span></td>
    </tr>`).join('');
  return table(['Cell type', 'RNA', 'Protein', 'Support'], rows);
}

export function buildDiagnosticsTable(manifest) {
  const rows = supportRows({ cell_types: manifest.cell_types.filter((c) => c.support === 'cross_modal') })
    .map((c) => `
      <tr>
        <td class="support-name">${escapeHtml(c.name)}</td>
        ${metricCell(c.pca_centroid_cosine, cosine4)}
        ${metricCell(c.latent_centroid_cosine, cosine4)}
        ${metricCell(c.modality_probe_accuracy, formatPercent)}
      </tr>`).join('');
  return table(['Cell type', 'Centroid cosine', 'Latent cosine', 'Modality probe'], rows) + `
    <p class="panel-note">
      Centroid cosine is computed on the 3-component PCA projection that this build ships.
      It is not a latent-space alignment measurement. High centroid similarity alongside a
      high modality probe score is the directional-alignment signature; the probe column
      fills in once Phase 4 runs.
    </p>`;
}

const BENCHMARK_HEADERS = ['Method', 'Dataset', 'Transfer accuracy', 'Modality probe'];

export function buildBenchmarkTable(manifest) {
  const b = manifest.benchmark;
  if (b.status !== 'measured' || b.rows.length === 0) {
    const planned = b.methods.map((m) => `
      <tr>
        <td>${escapeHtml(m)}</td><td>&mdash;</td>
        <td class="support-num pending">${PENDING_LABEL}</td>
        <td class="support-num pending">${PENDING_LABEL}</td>
      </tr>`).join('');
    return `
      <div class="pending-banner">
        <strong>${escapeHtml(b.phase)} &mdash; not yet run.</strong> ${escapeHtml(b.note)}
      </div>` + table(BENCHMARK_HEADERS, planned);
  }
  const rows = b.rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.method)}</td>
      <td>${escapeHtml(r.dataset)}</td>
      <td class="support-num">${metricText(r.transfer_accuracy, formatPercent)}</td>
      <td class="support-num">${metricText(r.modality_probe_accuracy, formatPercent)}</td>
    </tr>`).join('');
  return table(BENCHMARK_HEADERS, rows);
}

export function buildModelCard(manifest) {
  const m = manifest.model;
  const field = (label, value) =>
    `<div class="card-field"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;
  return `
    <dl class="model-card">
      ${field('Atlas version', escapeHtml(manifest.atlas_version))}
      ${field('Generated', escapeHtml(manifest.generated))}
      ${field('Model', escapeHtml(m.name))}
      ${field('Latent dimension', formatCount(m.latent_dim))}
      ${field('Training regime', escapeHtml(m.training_regime))}
      ${field('Seeds', metricText(m.seeds, (x) => formatMetric(x, 0)))}
      ${field('RNA cells', formatCount(manifest.modalities.rna?.cells))}
      ${field('Protein cells', formatCount(manifest.modalities.prot?.cells))}
    </dl>
    <p class="panel-note">${escapeHtml(m.notes)}</p>`;
}

export function buildAvailabilityTable(manifest) {
  const rows = Object.entries(manifest.data_availability).map(([key, info]) => `
    <tr>
      <td><code>${escapeHtml(key)}</code></td>
      <td>${escapeHtml(AVAILABILITY_LABEL[info.status] ?? info.status)}</td>
      <td>${escapeHtml(info.note)}${info.remedy ? ` <code>${escapeHtml(info.remedy)}</code>` : ''}</td>
    </tr>`).join('');
  return table(['Asset', 'Status', 'Notes'], rows);
}

export function buildSupportedLabelSpace(manifest) {
  const supported = manifest.cell_types
    .filter((c) => c.support === 'cross_modal')
    .map((c) => escapeHtml(c.name));
  return `
    <p><strong>Cross-modal support (${formatCount(supported.length)}):</strong> ${supported.join(', ')}</p>
    <p><strong>RNA-only (${formatCount(manifest.summary?.rna_only)}):</strong> projection onto these
    types has no proteomics evidence and the service abstains for protein queries.</p>`;
}
