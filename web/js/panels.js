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
      <td class="support-num">${c.prot_cells === 0 ? 'none' : formatCount(c.prot_cells)}</td>
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

// ---- The benchmark (manuscript.html, section 3.4) ----
// manifest.benchmark.datasets: one table per dataset, every method's score
// with its spread over seeds, and the current model minus each method by
// paired bootstrap. Every number goes through isMeasured.

const points = (x) => `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(1)}`;

function versusText(v, current) {
  const d = v?.difference;
  if (!v || !isMeasured(d)) return '';
  const spread = Number.isFinite(d.ci_low) && Number.isFinite(d.ci_high)
    ? `${points(d.value)} (${points(d.ci_low)} to ${points(d.ci_high)})`
    : Number.isFinite(d.min) && Number.isFinite(d.max)
      ? `${points(d.min)} to ${points(d.max)}` : points(d.value);
  const verdicts = [
    [v.favour_current, `favour${v.pairings === 1 ? 's' : ''} ${current}`],
    [v.neither, 'neither'],
    [v.favour_other, `favour${v.pairings === 1 ? 's' : ''} this method`],
  ].filter(([n]) => n > 0)
    .map(([n, text]) => (v.pairings === 1 ? text : `${formatCount(n)} of ${formatCount(v.pairings)} ${text}`));
  return `${escapeHtml(spread)}<span class="metric-basis">${escapeHtml(verdicts.join(', '))}</span>`;
}

function benchmarkDataset(d, current, { currentOnly = false, roles = true } = {}) {
  const chance = isMeasured(d.chance) ? `; chance ${escapeHtml(formatPercent(d.chance))}` : '';
  // currentOnly keeps the current model's own row and drops the other releases'.
  const shown = (d.rows ?? []).filter((r) => !currentOnly || !r.ours || r.method.startsWith(current));
  const role = roles ? ` ${escapeHtml(d.role)}` : '';
  const rows = shown.map((r) => `
    <tr>
      <td>${r.ours ? `<strong>${escapeHtml(r.method)}</strong>` : escapeHtml(r.method)}</td>
      <td>${escapeHtml(r.rule)}</td>
      <td class="support-num">${cardValue(r.score)}</td>
      <td class="support-num">${formatCount(r.runs)}</td>
      <td class="support-num">${versusText(r.vs_current, current)}</td>
    </tr>`).join('');
  return `
    <h3>${escapeHtml(d.name)}</h3>
    <p class="panel-note"><strong>${escapeHtml(d.measure)}${chance}.</strong>${role}</p>
    <div class="table-scroll">${table(['Method', 'Rule', 'Score', 'Runs', `${current} minus it`], rows)}</div>`;
}

// options { currentOnly, roles, note }: the Manuscript page shows the
// current model's rows only, and says each dataset's role in its own words.
export function buildBenchmarkTable(manifest, options = {}) {
  const b = manifest.benchmark ?? {};
  const datasets = Array.isArray(b.datasets) ? b.datasets : [];
  if (b.status !== 'measured' || datasets.length === 0) {
    return `
      <div class="pending-banner">
        <strong>${escapeHtml(b.phase ?? PENDING_LABEL)}: pending sign-off.</strong> ${escapeHtml(b.note ?? '')}
      </div>`;
  }
  const current = b.current ?? manifest.model?.name ?? 'the current model';
  const note = options.note ?? true;
  return datasets.map((d) => benchmarkDataset(d, current, options)).join('')
    + (note ? `<p class="panel-note">${escapeHtml(b.note ?? '')}</p>` : '');
}

const cardField = (label, value) =>
  `<div class="card-field"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;

export function buildSupportedLabelSpace(manifest) {
  const supported = manifest.cell_types
    .filter((c) => c.support === 'cross_modal')
    .map((c) => escapeHtml(c.name));
  return `
    <p><strong>Cross-modal support (${formatCount(supported.length)}):</strong> ${supported.join(', ')}</p>
    <p><strong>RNA-only (${formatCount(manifest.summary?.rna_only)}):</strong> these types have no
    protein cells in the atlas. Real protein data has since tested several of them (see
    <a href="manuscript.html#benchmark">the benchmark</a>). The service assigns them to protein
    queries too: every label is chosen among all the reference's classes.</p>`;
}

// A missing string field renders as Pending, never as the literal "undefined"
// that escapeHtml(undefined) would produce.
const textOrPending = (value) => (value === null || value === undefined || value === ''
  ? `<span class="pending">${PENDING_LABEL}</span>`
  : escapeHtml(value));

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
  previous_release_name: (m) => textOrPending(m.previous_release?.model_name),
  previous_release_version: (m) => textOrPending(m.previous_release?.atlas_version),
  v3_model_name: (m) => textOrPending(m.earlier_release?.model_name),
  v3_atlas_version: (m) => textOrPending(m.earlier_release?.atlas_version),
  organ_atlas: (m) => textOrPending(m.organs?.atlas),
  organs_total: (m) => formatCount(m.organs?.total),
  organs_labelling: (m) => formatCount(m.organs?.labelling),
  organs_maps: (m) => formatCount(m.organs?.maps),
  organs_to_build: (m) => formatCount(m.organs?.to_build),
};

// The atlas's organs (manifest.organs, scripts/build_manifest.py): one chip
// per organ of the RNA atlas, marked by what VivOME has of it. Blood and the
// organ maps link to their view on the Atlas page. Names are data, so they
// are escaped; an absent list reads Pending.
export const ORGAN_STATUS = { labelling: 'labels files', map: 'map open', to_build: 'to build' };

export function buildOrganGrid(manifest) {
  const list = manifest?.organs?.list;
  if (!Array.isArray(list) || !list.length) return `<p class="pending">${PENDING_LABEL}</p>`;
  const chip = (o) => {
    const status = Object.hasOwn(ORGAN_STATUS, o?.status) ? o.status : 'to_build';
    const href = status === 'labelling' ? 'atlas.html'
      : status === 'map' && typeof o.id === 'string' ? `atlas.html?organ=${encodeURIComponent(o.id)}` : null;
    const inner = `<span class="organ-name">${escapeHtml(o?.name ?? '')}</span><span class="organ-status">${ORGAN_STATUS[status]}</span>`;
    const cls = `organ-chip organ-${status.replace('_', '-')}`;
    return href ? `<li class="${cls}"><a href="${escapeHtml(href)}">${inner}</a></li>` : `<li class="${cls}">${inner}</li>`;
  };
  return `<ul class="organ-grid">${list.map(chip).join('')}</ul>`;
}

export function factText(manifest, key) {
  const fact = FACTS[key];
  return fact ? fact(manifest ?? {}) : `<span class="pending">${PENDING_LABEL}</span>`;
}

// ---- Projection results (atlas.html, Your data) ----
// A response from the projection service (docs/service/projection-api.md).
// Its numbers are computed by the service from the visitor's own upload, not
// read from the manifest; cell ids come from the visitor's file, so every
// value is escaped like any other data.

const cellsOf = (result) => (Array.isArray(result?.cells) ? result.cells : []);
const share = (count, total) => (total > 0 ? `${((count / total) * 100).toFixed(1)}%` : '');

// How the service read the file's values (the response's value_scale): the
// reading it applied, what a 0 was read as when the visitor said it (zeros),
// and, when the visitor chose the reading (stated), whether the service on
// its own reads them the same way. null for a value_scale this page does not
// know.
const SCALE_READ = { linear: 'Linear intensities, log2-transformed', log: 'Already on a log scale' };
const SCALE_ALONE = { linear: 'linear intensities', log: 'already on a log scale' };
const ZEROS_READ = { missing: ', each 0 read as not measured', measured: ', each 0 read as a measured value' };

export function valueScaleText(scale) {
  if (!scale || typeof scale !== 'object') return null;
  if (scale.detected === 'unknown') return 'No values to read';
  if (!Object.hasOwn(SCALE_ALONE, scale.detected ?? '')) return null;
  const zeros = Object.hasOwn(ZEROS_READ, scale.zeros ?? '') ? ZEROS_READ[scale.zeros] : '';
  const read = SCALE_READ[scale.transformed ? 'linear' : 'log'] + zeros;
  if (!Object.hasOwn(SCALE_ALONE, scale.stated ?? '')) return read;
  return scale.stated === scale.detected
    ? `${read}. You chose this; the service reads them so too.`
    : `${read}. You chose this; on its own the service reads them as ${SCALE_ALONE[scale.detected]}.`;
}

export function buildProjectionSummary(result) {
  const cells = cellsOf(result);
  const abstained = cells.filter((c) => c.abstained).length;
  const space = result?.label_space;
  const candidates = space?.candidate_classes ?? [];
  const spaceText = space?.restricted_to_supported_classes
    ? `Restricted to ${candidates.map(escapeHtml).join(', ')}`
    : `All ${formatCount(candidates.length)} reference classes`;
  const scaleText = valueScaleText(result?.value_scale) ?? textOrPending(null);
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

// ---- A measured value with its spread, and the facts the prose cites ----
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
  v3_latent_cosine_macrophage: (m) => escapeHtml(formatMetric(m.earlier_release?.latent_centroid_cosine?.macrophage, 2)),
  v3_latent_cosine_monocyte: (m) => escapeHtml(formatMetric(m.earlier_release?.latent_centroid_cosine?.monocyte, 2)),
});

const pair = (row) => (row && isMeasured(row.accuracy) && isMeasured(row.balanced_accuracy)
  ? `${escapeHtml(formatPercent(row.accuracy))} / ${escapeHtml(formatPercent(row.balanced_accuracy))}`
  : textOrPending(null));

Object.assign(FACTS, {
  rna_to_rna_test: (m) => pair(cardRow(m, 'rna_to_rna_test')),
  rna_to_rna_superseded: (m) => pair(m.model_card?.rna_to_rna_superseded),
  seeds: (m) => escapeHtml(formatMetric(m.model?.seeds, 0)),
  v3_seeds: (m) => escapeHtml(formatMetric(m.earlier_release?.seeds, 0)),
});

// The current release's results, for the prose of index.html and
// workflow.html. Each number only makes sense with what it measured, so the
// page says that in the same sentence: simulated RNA uploads, a dataset as
// served (Fulcher 2026 is development data, Khoury 2026 post-hoc), or a
// benchmark table.
const suiteValue = (m, key) => (m.model?.evaluation?.suite?.rows ?? []).find((r) => r.key === key)?.value;
const served = (m, dataset) => (m.model?.evaluation?.served ?? []).find((r) => r.dataset === dataset);
const recallIn = (ev, dataset, type) => (ev?.recall ?? []).find((r) => r.dataset === dataset && r.type === type)?.value;
const recall = (m, dataset, type) => recallIn(m.model?.evaluation, dataset, type);
// The previous release's, to show what changed.
const previousRecall = (m, dataset, type) => recallIn(m.previous_release?.evaluation, dataset, type);
const benchmarkSet = (m, key) => (m.benchmark?.datasets ?? []).find((d) => d.key === key);
// The current model minus the previous release on a benchmark table, with
// its interval: "+6.7 points (95% CI 4.4 to 9.2)".
const versusPrevious = (m, key) => {
  const name = m.previous_release?.model_name;
  const row = (benchmarkSet(m, key)?.rows ?? []).find((r) => r.ours && name && r.method.startsWith(name));
  const d = row?.vs_current?.difference;
  if (!isMeasured(d)) return textOrPending(null);
  const ci = Number.isFinite(d.ci_low) && Number.isFinite(d.ci_high) ? ` (95% CI ${points(d.ci_low)} to ${points(d.ci_high)})` : '';
  return escapeHtml(`${points(d.value)} points${ci}`);
};
// The current model's own row: the first of a table, marked as ours.
const currentScore = (m, key) => {
  const row = benchmarkSet(m, key)?.rows?.[0];
  return row?.ours ? row.score : undefined;
};

Object.assign(FACTS, {
  eval_rna_correct: (m) => escapeHtml(formatPercent(suiteValue(m, 'correct_when_committed'))),
  eval_rna_abstained: (m) => escapeHtml(formatPercent(suiteValue(m, 'abstention'))),
  eval_fulcher_answered: (m) => escapeHtml(formatPercent(served(m, 'Fulcher 2026')?.committed)),
  eval_fulcher_correct: (m) => escapeHtml(formatPercent(served(m, 'Fulcher 2026')?.correct)),
  recall_khoury_cd8t: (m) => escapeHtml(formatPercent(recall(m, 'Khoury 2026', 'CD8T'))),
  recall_fulcher_cd8t: (m) => escapeHtml(formatPercent(recall(m, 'Fulcher 2026', 'CD8T'))),
  recall_fulcher_dc: (m) => escapeHtml(formatPercent(recall(m, 'Fulcher 2026', 'DC'))),
  previous_recall_khoury_cd8t: (m) => escapeHtml(formatPercent(previousRecall(m, 'Khoury 2026', 'CD8T'))),
  previous_recall_fulcher_dc: (m) => escapeHtml(formatPercent(previousRecall(m, 'Fulcher 2026', 'DC'))),
  scope2_current: (m) => escapeHtml(formatPercent(currentScore(m, 'scope2'))),
  fulcher_current: (m) => escapeHtml(formatPercent(currentScore(m, 'fulcher2026'))),
  fulcher_vs_previous: (m) => versusPrevious(m, 'fulcher2026'),
  khoury_current: (m) => escapeHtml(formatPercent(currentScore(m, 'khoury2026'))),
  khoury_vs_previous: (m) => versusPrevious(m, 'khoury2026'),
  scope2_chance: (m) => escapeHtml(formatPercent(benchmarkSet(m, 'scope2')?.chance)),
});
