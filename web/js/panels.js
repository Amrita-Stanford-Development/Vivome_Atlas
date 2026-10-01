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
      <td class="support-num">${c.prot_cells > 0 ? formatCount(c.prot_cells) : 'none'}</td>
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
      It is not a latent-space alignment measurement; the latent cosine column is. The modality probe column is one global score (how well a linear classifier tells
      RNA from protein in the shared latent space), repeated on every cross-modal row rather
      than measured per class.
    </p>`;
}

const BENCHMARK_HEADERS = ['Method', 'Dataset', 'Transfer accuracy', 'Modality probe'];

export function buildBenchmarkTable(manifest) {
  const b = manifest.benchmark;
  if (b.status !== 'measured' || b.rows.length === 0) {
    const planned = b.methods.map((m) => `
      <tr>
        <td>${escapeHtml(m)}</td><td class="pending">Not run</td>
        <td class="support-num pending">${PENDING_LABEL}</td>
        <td class="support-num pending">${PENDING_LABEL}</td>
      </tr>`).join('');
    return `
      <div class="pending-banner">
        <strong>${escapeHtml(b.phase)}: pending sign-off.</strong> ${escapeHtml(b.note)}
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

const cardField = (label, value) =>
  `<div class="card-field"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;

// Shared by buildModelCard's optional architecture block and
// buildNextReferenceCard — both describe an encoder's settled design facts
// (feature space, encoder family, mask sampling, gene sources), just for
// the currently-deployed architecture vs. a possible future one. Kept as
// one implementation so the two cards can't drift in how they format the
// same underlying fields.
function architectureFieldsHtml(source) {
  const sources = Object.entries(source.detected_by_source ?? {})
    .map(([name, count]) => `${escapeHtml(name)} (${formatCount(count)})`)
    .join(', ');
  return [
    cardField('Feature space', `${formatCount(source.feature_space_size)} genes (was ${formatCount(source.previous_feature_space_size)})`),
    cardField('Encoder family', textOrPending(source.encoder_family)),
    cardField('Mask sampling', textOrPending(source.mask_sampling)),
    cardField('Detected by source', sources),
  ].join('');
}

export function buildModelCard(manifest) {
  const m = manifest.model;
  // Architecture facts (feature_space_size, encoder_family, ...) are
  // optional — present for the current v3 reference, absent on an older
  // manifest that predates this schema addition.
  const architectureFields = m.feature_space_size == null ? '' : architectureFieldsHtml(m);
  return `
    <dl class="model-card">
      ${cardField('Atlas version', escapeHtml(manifest.atlas_version))}
      ${cardField('Generated', escapeHtml(manifest.generated))}
      ${cardField('Model', escapeHtml(m.name))}
      ${cardField('Latent dimension', formatCount(m.latent_dim))}
      ${cardField('Training regime', escapeHtml(m.training_regime))}
      ${cardField('Seeds', metricText(m.seeds, (x) => formatMetric(x, 0)))}
      ${cardField('RNA cells', formatCount(manifest.modalities.rna?.cells))}
      ${cardField('Protein cells', formatCount(manifest.modalities.prot?.cells))}
      ${architectureFields}
    </dl>
    <p class="panel-note">${escapeHtml(m.notes)}</p>`;
}

// The next reference's architecture is decided; the reference itself is not
// trained (service/model/README.md). This is deliberately a separate panel
// from buildModelCard, not a merge into it: `manifest.model` describes the
// currently deployed release, and this section must never be read as
// updating that release's own numbers. Renders nothing when next_reference
// is absent — older manifests without this field still render the page.
export function buildNextReferenceCard(manifest) {
  const n = manifest.next_reference;
  if (!n) return '';
  return `
    <dl class="model-card">
      ${architectureFieldsHtml(n)}
      ${cardField('Reference trained', n.trained ? 'Yes' : 'Not yet')}
    </dl>
    <p class="panel-note">${escapeHtml(n.note)}</p>`;
}

// The previous release (v3), with its own seeds and architecture, kept as it
// was measured. Like buildPriorBaselineCard and buildNextReferenceCard, an
// additive section: it never edits buildModelCard's rendering of manifest.model.
export function buildPreviousReleaseCard(manifest) {
  const p = manifest.previous_release;
  if (!p) return '';
  const architectureFields = p.feature_space_size == null ? '' : architectureFieldsHtml(p);
  return `
    <dl class="model-card">
      ${cardField('Model', textOrPending(p.model_name))}
      ${cardField('Atlas version', textOrPending(p.atlas_version))}
      ${cardField('Seeds', metricText(p.seeds, (x) => formatMetric(x, 0)))}
      ${architectureFields}
    </dl>
    <p class="panel-note">${textOrPending(p.note)}</p>`;
}

// The first model's own numbers, kept as the documented baseline rather than
// erased when the architecture moved on.
export function buildPriorBaselineCard(manifest) {
  const p = manifest.first_release;
  if (!p) return '';
  return `
    <dl class="model-card">
      ${cardField('Model', escapeHtml(p.model_name))}
      ${cardField('Shared genes', formatCount(p.n_shared_genes))}
      ${cardField('Zero-shot AUC (raw)', metricText(p.zero_shot_auc_raw, (x) => formatMetric(x, 4)))}
      ${cardField('Zero-shot AUC (smoothed)', metricText(p.zero_shot_auc_smoothed, (x) => formatMetric(x, 4)))}
      ${cardField('Shipped properties', (p.shipped_properties ?? []).map(escapeHtml).join(', '))}
    </dl>
    <p class="panel-note">${escapeHtml(p.note)}</p>`;
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
    <p><strong>RNA-only (${formatCount(manifest.summary?.rna_only)}):</strong> these types have no
    proteomics evidence yet. By default the service can still assign them to protein queries;
    a request can set <code>restrict_to_supported_classes</code> to limit labels to the
    cross-modal types.</p>`;
}

// A missing string field renders as Pending, never as the literal "undefined"
// that escapeHtml(undefined) would produce.
const textOrPending = (value) => (value === null || value === undefined || value === ''
  ? `<span class="pending">${PENDING_LABEL}</span>`
  : escapeHtml(value));

// The dashboard's compact view of the release in manifest.model. The full
// card, with architecture and seeds, stays on versions.html (buildModelCard).
export function buildReleaseStatus(manifest) {
  return `
    <dl class="model-card">
      ${cardField('Atlas version', textOrPending(manifest.atlas_version))}
      ${cardField('Model', textOrPending(manifest.model?.name))}
      ${cardField('Generated', textOrPending(manifest.generated))}
      ${cardField('RNA cells', formatCount(manifest.modalities?.rna?.cells))}
      ${cardField('Protein cells', formatCount(manifest.modalities?.prot?.cells))}
      ${cardField('Cell types', formatCount(manifest.summary?.total))}
    </dl>`;
}

const NEWS_DATE = new Intl.DateTimeFormat('en-GB', { dateStyle: 'long', timeZone: 'UTC' });

// Links in web/data/whats_new.json may only point at pages of this site, so
// a bad entry can't smuggle in a javascript: or off-site URL.
const SITE_PAGE = /^[a-z0-9_-]+\.html(#[a-z0-9_-]+)?$/i;

function newsDate(iso) {
  const date = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? escapeHtml(iso) : NEWS_DATE.format(date);
}

// Entries are text only (web/data/whats_new.json). Numbers belong in the
// manifest, so an announcement links to the page that shows them.
export function buildWhatsNew(entries) {
  if (!Array.isArray(entries) || entries.length === 0) {
    return '<p class="panel-note">No announcements yet.</p>';
  }
  const items = entries.map((e) => {
    const link = SITE_PAGE.test(e.link ?? '')
      ? `<a href="${escapeHtml(e.link)}">${escapeHtml(e.link_text ?? 'Read more')}</a>`
      : '';
    return `
      <li>
        <time datetime="${escapeHtml(e.date)}">${newsDate(e.date)}</time>
        <h3>${escapeHtml(e.title)}</h3>
        <p>${escapeHtml(e.text)}</p>
        ${link}
      </li>`;
  }).join('');
  return `<ol class="news">${items}</ol>`;
}

// The landing finale's proof points: plain facts from the manifest, each
// through the same guards as every other panel, so a missing count reads
// Pending instead of a number nobody measured.
export function buildProofPoints(manifest) {
  const point = (value, label) =>
    `<div class="proof-point"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;
  return `
    <dl class="proof-points">
      ${point(formatCount(manifest.modalities?.rna?.cells), 'RNA cells in the reference')}
      ${point(formatCount(manifest.modalities?.prot?.cells), 'protein cells, projected zero-shot')}
      ${point(formatCount(manifest.summary?.total), 'cell types')}
      ${point(textOrPending(manifest.atlas_version), 'atlas version')}
    </dl>`;
}

// Numbers and names inside the landing's prose (<span data-fact="...">),
// looked up in the manifest and guarded like every panel: an unknown key or
// a missing value reads Pending, never a number nobody measured.
const FACTS = {
  rna_cells: (m) => formatCount(m.modalities?.rna?.cells),
  prot_cells: (m) => formatCount(m.modalities?.prot?.cells),
  cell_types: (m) => formatCount(m.summary?.total),
  cross_modal_types: (m) => formatCount(m.summary?.cross_modal),
  feature_space: (m) => formatCount(m.model?.feature_space_size),
  latent_dim: (m) => formatCount(m.model?.latent_dim),
  atlas_version: (m) => textOrPending(m.atlas_version),
  model_name: (m) => textOrPending(m.model?.name),
  previous_model: (m) => textOrPending(m.first_release?.model_name),
  v3_model_name: (m) => textOrPending(m.previous_release?.model_name),
  v3_atlas_version: (m) => textOrPending(m.previous_release?.atlas_version),
};

export function factText(manifest, key) {
  const fact = FACTS[key];
  return fact ? fact(manifest ?? {}) : `<span class="pending">${PENDING_LABEL}</span>`;
}

// ---- Projection results (project.html) ----
// A response from the projection service (docs/service/projection-api.md).
// Its numbers are computed by the service from the visitor's own upload, not
// read from the manifest; cell ids come from the visitor's file, so every
// value is escaped like any other data.

const ABSTAIN_TEXT = {
  coverage_too_low: 'Too few observed genes',
  outside_supported_region: 'Outside the region the atlas has evidence for',
  no_confident_label: 'No class met the confidence bar',
  ambiguous_between_classes: 'Ambiguous between classes',
};

const abstainText = (reason) => ABSTAIN_TEXT[reason] ?? reason ?? 'Abstained';
const cellsOf = (result) => (Array.isArray(result?.cells) ? result.cells : []);
const share = (count, total) => (total > 0 ? `${((count / total) * 100).toFixed(1)}%` : '');

export function buildProjectionSummary(result) {
  const cells = cellsOf(result);
  const abstained = cells.filter((c) => c.abstained).length;
  const space = result?.label_space;
  const candidates = space?.candidate_classes ?? [];
  const spaceText = space?.restricted_to_supported_classes
    ? `Restricted to ${candidates.map(escapeHtml).join(', ')}`
    : `All ${formatCount(candidates.length)} reference classes`;
  const scale = result?.value_scale;
  const scaleText = scale?.transformed ? 'Linear intensities, log2-transformed' : 'Already on a log scale';
  return `
    <dl class="model-card">
      ${cardField('Cells', formatCount(result?.n_cells))}
      ${cardField('Features matched', `${formatCount(result?.n_features_matched)} of ${formatCount(
        (result?.n_features_matched ?? 0) + (result?.n_features_unmatched ?? 0))}`)}
      ${cardField('Labelled', `${formatCount(cells.length - abstained)} (${share(cells.length - abstained, cells.length)})`)}
      ${cardField('Abstained', `${formatCount(abstained)} (${share(abstained, cells.length)})`)}
      ${cardField('Label space', spaceText)}
      ${cardField('Values', scaleText)}
      ${cardField('Model', textOrPending(result?.model_version))}
      ${cardField('Atlas version', textOrPending(result?.atlas_version))}
    </dl>`;
}

// How many cells got each label, and how many abstained for each reason.
export function buildProjectionLabels(result) {
  const cells = cellsOf(result);
  const counts = new Map();
  for (const c of cells) {
    const key = c.abstained ? `\u0000${c.abstain_reason}` : c.label;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const rows = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => {
      const name = key.startsWith('\u0000')
        ? `<span class="pending">Abstained: ${escapeHtml(abstainText(key.slice(1)))}</span>`
        : escapeHtml(key);
      return `<tr><td class="support-name">${name}</td><td class="support-num">${formatCount(count)}</td>`
        + `<td class="support-num">${share(count, cells.length)}</td></tr>`;
    }).join('');
  return table(['Label', 'Cells', 'Share'], rows);
}

// One row per cell, the first `limit` of them.
export function buildProjectionCells(result, limit = 200) {
  const cells = cellsOf(result);
  const rows = cells.slice(0, limit).map((c) => {
    const labelSet = (c.label_set ?? []).map(escapeHtml).join(', ');
    const confidence = Number.isFinite(c.confidence) ? c.confidence.toFixed(3) : '';
    const label = c.abstained
      ? `<span class="pending">${escapeHtml(abstainText(c.abstain_reason))}</span>`
      : escapeHtml(c.label);
    return `<tr><td><code>${escapeHtml(c.cell_id)}</code></td><td>${label}</td><td>${labelSet}</td>`
      + `<td class="support-num">${confidence}</td><td class="support-num">${formatCount(c.observed_genes)}</td></tr>`;
  }).join('');
  const note = cells.length > limit
    ? `<p class="panel-note">Showing the first ${formatCount(limit)} of ${formatCount(cells.length)} cells. Download the response for all of them.</p>`
    : '';
  return table(['Cell', 'Label', 'Label set', 'Confidence', 'Observed genes'], rows) + note;
}

// ---- The model card's accuracy table (versions.html) ----
// manifest.model_card: each row names its decision rule, because a
// shipped-checkpoint number and a 5-seed mean compare only under one rule.

const pct1 = (x) => `${(x * 100).toFixed(1)}`;

function cardValue(metric) {
  if (!isMeasured(metric)) return `<span class="pending">${PENDING_LABEL}</span>`;
  const sd = Number.isFinite(metric.sd) ? ` &plusmn; ${pct1(metric.sd)}` : '';
  const range = Number.isFinite(metric.min) && Number.isFinite(metric.max)
    ? `<span class="metric-basis">range ${pct1(metric.min)} to ${pct1(metric.max)}%</span>` : '';
  return `${escapeHtml(formatPercent(metric))}${sd}${range}`;
}

export function buildModelCardTable(manifest) {
  const rows = manifest.model_card?.rows ?? [];
  if (rows.length === 0) return `<p class="pending">${PENDING_LABEL}</p>`;
  const body = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.measure)}<span class="metric-basis"><code>${escapeHtml(metricBasis(r.accuracy))}</code></span></td>
      <td>${escapeHtml(r.rule)}</td>
      <td class="support-num">${cardValue(r.accuracy)}</td>
      <td class="support-num">${cardValue(r.balanced_accuracy)}</td>
    </tr>`).join('');
  return table(['Measure', 'Decision rule', 'Accuracy', 'Balanced accuracy'], body);
}

// manifest.model.evaluation: the current release's numbers, each with what
// it describes. NB2's evaluation-suite figures are NB2's rule, before the two
// service flags; the development datasets are measured as served.
export function buildEvaluationTable(manifest) {
  const ev = manifest.model?.evaluation;
  const nb2 = ev?.nb2 ?? [];
  const served = ev?.served ?? [];
  if (nb2.length === 0 && served.length === 0) return `<p class="pending">${PENDING_LABEL}</p>`;
  const valueRow = (measure, metric) => `
    <tr>
      <td>${escapeHtml(measure)}<span class="metric-basis"><code>${escapeHtml(metricBasis(metric))}</code></span></td>
      <td class="support-num">${cardValue(metric)}</td>
    </tr>`;
  const nb2Rows = nb2.map((r) => valueRow(r.measure, r.value)).join('');
  const servedRows = served.map((r) => [
    valueRow(`${r.dataset}: committed`, r.committed),
    valueRow(`${r.dataset}: ${r.correct_label}`, r.correct),
  ].join('')).join('');
  return `<h3>NB2's evaluation suite</h3>${table(['Measure', 'Value'], nb2Rows)}`
    + `<h3>Development datasets, as served</h3>${table(['Measure', 'Value'], servedRows)}`;
}

const cardRow = (m, key) => (m.model_card?.rows ?? []).find((r) => r.key === key);
const balanced = (m, key) => cardRow(m, key)?.balanced_accuracy;
const withSd = (metric) => (isMeasured(metric) && Number.isFinite(metric.sd)
  ? `${escapeHtml(formatPercent(metric))} &plusmn; ${pct1(metric.sd)}` : textOrPending(null));
const rangeOf = (metric) => (isMeasured(metric) && Number.isFinite(metric.min) && Number.isFinite(metric.max)
  ? `${pct1(metric.min)} to ${pct1(metric.max)}%` : textOrPending(null));
const spreadOf = (metric) => (isMeasured(metric) && Number.isFinite(metric.min) && Number.isFinite(metric.max)
  ? `${pct1(metric.max - metric.min)} points` : textOrPending(null));
const pairings = (m, regime) => {
  const v = m.model_card?.vs_scanvi?.[regime];
  return Number.isFinite(v?.v3_ahead) && Number.isFinite(v?.pairings)
    ? `${formatCount(v.v3_ahead)} of ${formatCount(v.pairings)}` : textOrPending(null);
};
const latentCosine = (m, name) => {
  const c = (m.cell_types ?? []).find((t) => t.name === name);
  return escapeHtml(formatMetric(c?.latent_centroid_cosine, 2));
};

Object.assign(FACTS, {
  restricted_centroid_seed0: (m) => escapeHtml(formatPercent(balanced(m, 'restricted_native_centroid:seed0'))),
  restricted_centroid_mean: (m) => withSd(balanced(m, 'restricted_native_centroid:mean')),
  restricted_centroid_range: (m) => rangeOf(balanced(m, 'restricted_native_centroid:mean')),
  restricted_knn_mean: (m) => withSd(balanced(m, 'restricted_shared_knn:mean')),
  restricted_knn_range: (m) => rangeOf(balanced(m, 'restricted_shared_knn:mean')),
  restricted_knn_spread: (m) => spreadOf(balanced(m, 'restricted_shared_knn:mean')),
  scanvi_restricted_pairings: (m) => pairings(m, 'restricted_shared_knn'),
  scanvi_unrestricted_pairings: (m) => pairings(m, 'unrestricted'),
  scanvi_unrestricted_margin: (m) => {
    const d = m.model_card?.vs_scanvi?.unrestricted?.mean_difference;
    return isMeasured(d) ? `${pct1(Number(d.value))} points` : textOrPending(null);
  },
  latent_cosine_macrophage: (m) => latentCosine(m, 'macrophage'),
  latent_cosine_monocyte: (m) => latentCosine(m, 'monocyte'),
  v3_latent_cosine_macrophage: (m) => escapeHtml(formatMetric(m.previous_release?.latent_centroid_cosine?.macrophage, 2)),
  v3_latent_cosine_monocyte: (m) => escapeHtml(formatMetric(m.previous_release?.latent_centroid_cosine?.monocyte, 2)),
});

const pair = (row) => (row && isMeasured(row.accuracy) && isMeasured(row.balanced_accuracy)
  ? `${escapeHtml(formatPercent(row.accuracy))} / ${escapeHtml(formatPercent(row.balanced_accuracy))}`
  : textOrPending(null));

Object.assign(FACTS, {
  rna_to_rna_test: (m) => pair(cardRow(m, 'rna_to_rna_test')),
  rna_to_rna_superseded: (m) => pair(m.model_card?.rna_to_rna_superseded),
  seeds: (m) => escapeHtml(formatMetric(m.model?.seeds, 0)),
  v3_seeds: (m) => escapeHtml(formatMetric(m.previous_release?.seeds, 0)),
});
