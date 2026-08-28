// HTML-string builders for the manifest-driven panels.
// Pure functions only — they return strings and never touch the DOM — so the
// same code is unit-tested under Node and assigned to innerHTML in the browser.

import {
  formatMetric, formatPercent, metricBasis, supportRows, PENDING_LABEL,
} from './manifest.js';

const HTML_ESCAPES = {
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
};

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

const num = (n) => Number(n).toLocaleString('en-US');

const SUPPORT_LABEL = {
  cross_modal: 'Cross-modal',
  rna_only: 'RNA only',
  prot_only: 'Protein only',
};

export function buildSupportSummary(manifest) {
  const s = manifest.summary;
  const tile = (value, label) =>
    `<div class="support-tile"><div class="support-tile-value">${value}</div>` +
    `<div class="support-tile-label">${label}</div></div>`;
  return [
    tile(s.cross_modal, 'Cross-modal'),
    tile(s.rna_only, 'RNA-only'),
    tile(s.total, 'Cell types'),
  ].join('');
}

export function buildSupportTable(manifest) {
  const rows = supportRows(manifest).map((c) => `
    <tr class="support-${escapeHtml(c.support)}">
      <td class="support-name">${escapeHtml(c.name)}</td>
      <td class="support-num">${num(c.rna_cells)}</td>
      <td class="support-num">${c.prot_cells > 0 ? num(c.prot_cells) : '&mdash;'}</td>
      <td><span class="support-badge badge-${escapeHtml(c.support)}">${SUPPORT_LABEL[c.support] || escapeHtml(c.support)}</span></td>
    </tr>`).join('');
  return `
    <table class="support-table">
      <thead><tr><th>Cell type</th><th>RNA</th><th>Protein</th><th>Support</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

export function buildDiagnosticsTable(manifest) {
  const rows = supportRows(manifest)
    .filter((c) => c.support === 'cross_modal')
    .map((c) => `
      <tr>
        <td class="support-name">${escapeHtml(c.name)}</td>
        <td class="support-num">${formatMetric(c.pca_centroid_cosine, 4)}
          <span class="metric-basis">${escapeHtml(metricBasis(c.pca_centroid_cosine))}</span></td>
        <td class="support-num">${formatMetric(c.latent_centroid_cosine, 4)}
          <span class="metric-basis">${escapeHtml(metricBasis(c.latent_centroid_cosine))}</span></td>
        <td class="support-num">${formatPercent(c.modality_probe_accuracy)}
          <span class="metric-basis">${escapeHtml(metricBasis(c.modality_probe_accuracy))}</span></td>
      </tr>`).join('');
  return `
    <table class="support-table">
      <thead><tr>
        <th>Cell type</th><th>Centroid cosine</th><th>Latent cosine</th><th>Modality probe</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="panel-note">
      Centroid cosine is computed on the 3-component PCA projection that this build ships.
      It is not a latent-space alignment measurement. High centroid similarity alongside a
      high modality probe score is the directional-alignment signature; the probe column
      fills in once Phase 4 runs.
    </p>`;
}

export function buildBenchmarkTable(manifest) {
  const b = manifest.benchmark;
  if (b.status !== 'measured' || b.rows.length === 0) {
    const planned = b.methods
      .map((m) => `<tr><td>${escapeHtml(m)}</td><td>&mdash;</td>` +
                  `<td class="pending">${PENDING_LABEL}</td>` +
                  `<td class="pending">${PENDING_LABEL}</td></tr>`).join('');
    return `
      <div class="pending-banner">
        <strong>${escapeHtml(b.phase)} &mdash; not yet run.</strong> ${escapeHtml(b.note)}
      </div>
      <table class="support-table">
        <thead><tr>
          <th>Method</th><th>Dataset</th><th>Transfer accuracy</th><th>Modality probe</th>
        </tr></thead>
        <tbody>${planned}</tbody>
      </table>`;
  }
  const rows = b.rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.method)}</td>
      <td>${escapeHtml(r.dataset)}</td>
      <td class="support-num">${formatPercent(r.transfer_accuracy)}</td>
      <td class="support-num">${formatPercent(r.modality_probe_accuracy)}</td>
    </tr>`).join('');
  return `
    <table class="support-table">
      <thead><tr>
        <th>Method</th><th>Dataset</th><th>Transfer accuracy</th><th>Modality probe</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
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
      ${field('Latent dimension', escapeHtml(String(m.latent_dim)))}
      ${field('Training regime', escapeHtml(m.training_regime))}
      ${field('Seeds', `<span class="pending">${formatMetric(m.seeds, 0)}</span>`)}
      ${field('RNA cells', num(manifest.modalities.rna.cells))}
      ${field('Protein cells', num(manifest.modalities.prot.cells))}
    </dl>
    <p class="panel-note">${escapeHtml(m.notes)}</p>`;
}
