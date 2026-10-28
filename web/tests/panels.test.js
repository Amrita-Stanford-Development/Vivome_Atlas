import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  escapeHtml, errorPanel, buildSupportSummary, buildSupportTable,
  buildDiagnosticsTable, buildBenchmarkTable, buildSupportedLabelSpace, buildProofPoints, factText,
  buildProjectionSummary, valueScaleText,
} from '../js/panels.js';
import { measured, pending, manifestFixture } from './fixtures.js';

test('escapeHtml neutralises angle brackets and quotes', () => {
  assert.equal(escapeHtml('<b>"x"&\'y\'</b>'),
    '&lt;b&gt;&quot;x&quot;&amp;&#39;y&#39;&lt;/b&gt;');
});

test('errorPanel escapes the message', () => {
  const html = errorPanel(new Error('<img onerror=alert(1)>'));
  assert.ok(!html.includes('<img'));
  assert.match(html, /&lt;img/);
});

test('errorPanel accepts a non-Error value', () => {
  assert.match(errorPanel('plain string'), /plain string/);
});

test('support summary reports the real coverage counts', () => {
  const html = buildSupportSummary(manifestFixture());
  assert.match(html, /support-tile-value">2<\/div><div class="support-tile-label">Cross-modal/);
  assert.match(html, /support-tile-value">1<\/div><div class="support-tile-label">RNA-only/);
  assert.match(html, /support-tile-value">3<\/div><div class="support-tile-label">Cell types/);
});

test('support summary renders Pending, not NaN, when summary counts are absent', () => {
  const m = manifestFixture();
  m.summary = {};
  const html = buildSupportSummary(m);
  assert.ok(!html.includes('NaN'), html);
  assert.ok(!html.includes('undefined'), html);
  assert.match(html, /Pending/);
});

test('support table badges cross-modal and RNA-only rows distinctly', () => {
  const html = buildSupportTable(manifestFixture());
  assert.match(html, /badge-cross_modal">Cross-modal/);
  assert.match(html, /badge-rna_only">RNA only/);
});

test('support table escapes cell type names', () => {
  const html = buildSupportTable(manifestFixture());
  assert.ok(!html.includes('<script>alert(1)</script>'));
  assert.match(html, /&lt;script&gt;/);
});

test('support table shows counts with thousands separators', () => {
  assert.match(buildSupportTable(manifestFixture()), /32,198/);
});

test('support table renders Pending, not NaN, for a missing cell count', () => {
  const m = manifestFixture();
  delete m.cell_types[0].rna_cells;
  const html = buildSupportTable(m);
  assert.ok(!html.includes('NaN'), html);
  assert.match(html, /Pending/);
});

test('diagnostics table renders every measured column for a cross-modal class', () => {
  const html = buildDiagnosticsTable(manifestFixture());
  assert.match(html, /0\.8206/); // monocyte pca_centroid_cosine
  assert.match(html, /0\.8303/); // monocyte latent_centroid_cosine
});

test('diagnostics table labels the basis of the measured value', () => {
  assert.match(buildDiagnosticsTable(manifestFixture()), /3-PC projection/);
});

test('diagnostics table marks a pending cell with the pending class', () => {
  // Both cross-modal rows are fully measured in the current real manifest
  // (both diagnostic classes have cross-modal coverage) — override one
  // field back to pending to exercise that render branch.
  const m = manifestFixture();
  m.cell_types.find((c) => c.name === 'macrophage').latent_centroid_cosine = pending('N/A');
  const html = buildDiagnosticsTable(m);
  assert.match(html, /<span class="pending">Pending<\/span>/);
});

test('diagnostics table does not mark a measured cell as pending', () => {
  const html = buildDiagnosticsTable(manifestFixture());
  assert.ok(!/<span class="pending">0\.8206/.test(html));
});

test('diagnostics table includes only cross-modal rows', () => {
  const html = buildDiagnosticsTable(manifestFixture());
  assert.ok(!html.includes('&lt;script&gt;'), 'RNA-only row must not appear');
  assert.equal((html.match(/<tr>/g) || []).length, 3);
});

test('diagnostics table never prints a bare zero for a pending metric', () => {
  const m = manifestFixture();
  m.cell_types.find((c) => c.name === 'macrophage').latent_centroid_cosine = pending('N/A');
  assert.ok(!/>0\.000</.test(buildDiagnosticsTable(m)));
});

test('benchmark renders one table per dataset, ours first and bold, with chance and role', () => {
  const html = buildBenchmarkTable(manifestFixture());
  assert.equal((html.match(/<table/g) ?? []).length, 2);
  assert.match(html, /<h3>Khoury 2026<\/h3>/);
  assert.match(html, /Balanced accuracy over 5 types; chance 20\.0%\./);
  assert.match(html, /<strong>VivOME v4\.2 \(ours\)<\/strong>/);
  assert.match(html, /<strong>VivOME v4\.1 \(ours\)<\/strong>/);
  assert.ok(html.indexOf('VivOME v4.2 (ours)') < html.indexOf('VivOME v4.1 (ours)'));
  assert.ok(html.indexOf('VivOME v4.1 (ours)') < html.indexOf('PCA, no correction'));
  assert.match(html, /<th>VivOME v4\.2 minus it<\/th>/);
  assert.match(html, /62\.5%/);
});

test('benchmark escapes every name and role from the manifest', () => {
  const html = buildBenchmarkTable(manifestFixture());
  assert.ok(!html.includes('<script>x'), 'a method name reached the page unescaped');
  assert.ok(!html.includes('<b>from'), 'a role reached the page unescaped');
  assert.match(html, /&lt;script&gt;x/);
});

test('benchmark shows the spread over seeds and the paired difference in points', () => {
  const html = buildBenchmarkTable(manifestFixture());
  assert.match(html, /56\.9% &plusmn; 1\.7<span class="metric-basis">range 55\.4 to 58\.7%<\/span>/);
  // One pairing: the difference with its interval and verdict.
  assert.match(html, /−0\.3 \(−2\.1 to \+1\.4\)<span class="metric-basis">neither<\/span>/);
  // Several: the range over runs and how many favour each side.
  assert.match(html, /\+3\.8 to \+7\.2<span class="metric-basis">3 of 3 favour VivOME v4\.2<\/span>/);
});

test('benchmark renders a pending score as Pending, never a number', () => {
  const html = buildBenchmarkTable(manifestFixture());
  const row = html.slice(html.indexOf('Not yet run'), html.indexOf('</tr>', html.indexOf('Not yet run')));
  assert.match(row, /<span class="pending">Pending<\/span>/);
  assert.ok(!/NaN|undefined/.test(html));
});

test('benchmark that is not signed off shows a pending banner and no table', () => {
  const m = manifestFixture();
  m.benchmark = { status: 'pending', phase: 'Phase 4', note: 'Not <i>signed</i> off.', datasets: [] };
  const html = buildBenchmarkTable(m);
  assert.match(html, /Phase 4: pending sign-off\./);
  assert.match(html, /Not &lt;i&gt;signed&lt;\/i&gt; off\./);
  assert.ok(!html.includes('<table'));
  assert.match(buildBenchmarkTable({ benchmark: {} }), /Pending: pending sign-off/);
});

test('release facts name each release from its own block', () => {
  const m = manifestFixture();
  assert.equal(factText(m, 'model_name'), 'VivOME v4.2');
  assert.equal(factText(m, 'previous_release_name'), 'VivOME v4.1');
  assert.equal(factText(m, 'previous_release_version'), '0.4.0');
  assert.equal(factText(m, 'v3_model_name'), 'VivOME v3 reference');
  assert.equal(factText(m, 'v3_atlas_version'), '0.2.0');
  assert.equal(factText(m, 'previous_model'), 'CrossModalNet');
  assert.equal(factText(m, 'v3_latent_cosine_macrophage'), '0.19');
  assert.equal(factText(m, 'latent_cosine_macrophage'), '0.08');
});

test('the known limits read their numbers from the manifest, and only measured ones', () => {
  const m = manifestFixture();
  assert.equal(factText(m, 'recall_khoury_cd8t'), 'Pending', 'a pending recall reads Pending');
  assert.match(factText(m, 'khoury_vs_previous'), /Pending/, 'no comparison recorded, none shown');
  assert.equal(factText(m, 'previous_recall_khoury_cd8t'), '2.7%');
  assert.equal(factText(m, 'recall_fulcher_cd8t'), '23.8%');
  assert.equal(factText(m, 'recall_fulcher_dc'), 'Pending');
  assert.equal(factText(m, 'previous_recall_fulcher_dc'), '22.2%');
  assert.equal(factText(m, 'scope2_current'), '38.0%');
  assert.equal(factText(m, 'scope2_chance'), '50.0%');
  // A table whose first row is not ours has no current score to read.
  m.benchmark.datasets[1].rows[0].ours = false;
  assert.equal(factText(m, 'scope2_current'), 'Pending');
  assert.equal(factText({}, 'recall_khoury_cd8t'), 'Pending');
  assert.equal(factText({}, 'previous_recall_khoury_cd8t'), 'Pending');
});

test('every fact the manuscript page asks for exists in the real manifest', async () => {
  const { readFileSync } = await import('node:fs');
  const real = JSON.parse(readFileSync(new URL('../data/atlas_manifest.json', import.meta.url), 'utf8'));
  for (const page of ['manuscript.html']) {
    const html = readFileSync(new URL(`../${page}`, import.meta.url), 'utf8');
    const keys = [...new Set([...html.matchAll(/data-fact="([^"]+)"/g)].map((x) => x[1]))];
    assert.ok(keys.length > 0, page);
    for (const key of keys) assert.doesNotMatch(factText(real, key), /Pending/, `${page}: data-fact="${key}"`);
    const text = html.slice(html.indexOf('<main'), html.indexOf('</main>')).replace(/<[^>]+>/g, ' ');
    assert.ok(!text.includes('—'), `${page}: em dash`);
  }
});

test('supported label space lists cross-modal types and the RNA-only count', () => {
  const html = buildSupportedLabelSpace(manifestFixture());
  assert.match(html, /Cross-modal support \(2\)/);
  assert.match(html, /monocyte/);
  assert.match(html, /macrophage/);
  assert.match(html, /RNA-only \(1\)/);
  assert.match(html, /among all the reference's classes/);
  assert.doesNotMatch(html, /restrict_to_supported_classes/, 'restricted mode is retired (2026-10-21)');
});

test('proof points come from the manifest', () => {
  const html = buildProofPoints(manifestFixture());
  assert.match(html, /RNA cells in the reference<\/dt><dd>85,233/);
  assert.match(html, /protein cells, projected zero-shot<\/dt><dd>1,490/);
  assert.match(html, /cell types<\/dt><dd>3</);
  assert.match(html, /atlas version<\/dt><dd>0\.5\.0/);
});

test('proof points read Pending, never NaN or undefined, when the manifest is short', () => {
  const html = buildProofPoints({ modalities: {}, summary: {} });
  assert.ok(!html.includes('NaN') && !html.includes('undefined'), html);
  assert.equal(html.match(/Pending/g).length, 4);
});

test('facts read the manifest for the landing prose', () => {
  const m = manifestFixture();
  assert.equal(factText(m, 'rna_cells'), '85,233');
  assert.equal(factText(m, 'feature_space'), '9,002');
  assert.equal(factText(m, 'atlas_version'), '0.5.0');
  assert.equal(factText(m, 'model_name'), 'VivOME v4.2');
  assert.equal(factText(m, 'previous_model'), 'CrossModalNet');
});

test('the landing reads the release results from the manifest, and only measured ones', () => {
  const m = manifestFixture();
  assert.equal(factText(m, 'eval_rna_correct'), '96.3%');
  assert.equal(factText(m, 'eval_fulcher_answered'), '87.3%');
  assert.equal(factText(m, 'eval_fulcher_correct'), '98.3%');
  // Absent from the manifest: no abstention record in the fixture.
  assert.equal(factText(m, 'eval_rna_abstained'), 'Pending');
  // Present but pending.
  m.model.evaluation.served[0].correct = { value: null, status: 'pending', phase: 'later' };
  assert.equal(factText(m, 'eval_fulcher_correct'), 'Pending');
  // No evaluation block at all.
  assert.equal(factText({ model: {} }, 'eval_rna_correct'), 'Pending');
});

test('an unknown or missing fact reads Pending, and names are escaped', () => {
  assert.match(factText(manifestFixture(), 'no_such_fact'), /Pending/);
  assert.match(factText({}, 'rna_cells'), /Pending/);
  assert.match(factText(null, 'model_name'), /Pending/);
  const m = manifestFixture();
  m.model.name = '<b>x</b>';
  assert.ok(!factText(m, 'model_name').includes('<b>'));
});

const projection = () => ({
  atlas_version: '0.2.0',
  model_version: 'production',
  n_cells: 3,
  n_features_matched: 900,
  n_features_unmatched: 100,
  value_scale: { detected: 'linear', transformed: true },
  label_space: { restricted_to_supported_classes: false, candidate_classes: ['a', 'b', 'c'] },
  cells: [
    { cell_id: '<img src=x onerror=alert(1)>', label: 'monocyte', label_set: ['monocyte'], confidence: 0.91234, abstained: false, observed_genes: 1200 },
    { cell_id: 'c2', label: 'monocyte', label_set: ['monocyte', 'macrophage'], confidence: 0.5, abstained: false, observed_genes: 800 },
    { cell_id: 'c3', label: null, label_set: [], confidence: null, abstained: true, abstain_reason: 'coverage_too_low', observed_genes: 12 },
  ],
});

test('projection summary reports the upload, the label space and the abstention share', () => {
  const html = buildProjectionSummary(projection());
  assert.match(html, /Cells<\/dt><dd>3/);
  assert.match(html, /900 of 1,000/);
  assert.match(html, /Labelled<\/dt><dd>2 \(66\.7%\)/);
  assert.match(html, /Abstained<\/dt><dd>1 \(33\.3%\)/);
  assert.match(html, /All 3 reference classes/);
  assert.match(html, /log2-transformed/);
  const restricted = projection();
  restricted.label_space = { restricted_to_supported_classes: true, candidate_classes: ['macrophage', 'monocyte'] };
  assert.match(buildProjectionSummary(restricted), /Restricted to macrophage, monocyte/);
  const log = projection();
  log.value_scale = { detected: 'log', transformed: false };
  assert.match(buildProjectionSummary(log), /Already on a log scale/);
  const empty = projection();
  empty.value_scale = { detected: 'unknown', transformed: false };
  assert.match(buildProjectionSummary(empty), /No values to read/, 'not a log scale: there was nothing to judge');
});

test('valueScaleText says how the values were read, and whose choice it was', () => {
  assert.equal(valueScaleText({ detected: 'linear', transformed: true }), 'Linear intensities, log2-transformed');
  assert.equal(valueScaleText({ detected: 'log', transformed: false }), 'Already on a log scale');
  assert.equal(valueScaleText({ detected: 'unknown', transformed: false }), 'No values to read');
  assert.equal(valueScaleText({ detected: 'log', transformed: true, stated: 'linear' }),
    'Linear intensities, log2-transformed. You chose this; on its own the service reads them as already on a log scale.');
  assert.equal(valueScaleText({ detected: 'linear', transformed: false, stated: 'log' }),
    'Already on a log scale. You chose this; on its own the service reads them as linear intensities.');
  assert.equal(valueScaleText({ detected: 'linear', transformed: true, stated: 'linear' }),
    'Linear intensities, log2-transformed. You chose this; the service reads them so too.');
  assert.equal(valueScaleText({ detected: 'log', transformed: false, stated: '<b>x</b>' }), 'Already on a log scale',
    'a stated reading the page does not know is left out');
  for (const bad of [null, undefined, 'linear', {}, { detected: '<img src=x>' }]) assert.equal(valueScaleText(bad), null);
});

test('the projection summary says a stated reading', () => {
  const stated = projection();
  stated.value_scale = { detected: 'log', transformed: true, stated: 'linear' };
  assert.match(buildProjectionSummary(stated), /Values<\/dt><dd>Linear intensities, log2-transformed\. You chose this/);
});

test('the projection summary survives a malformed response', () => {
  const html = buildProjectionSummary({});
  assert.ok(!html.includes('undefined') && !html.includes('NaN'), html);
});

const withModelCard = () => {
  const m = manifestFixture();
  const rec = (value, extra = {}) => ({ ...measured(value, 'research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv'), ...extra });
  m.model_card = {
    rows: [
      { key: 'restricted_native_centroid:seed0', measure: 'Protein, restricted, shipped', rule: "nearest centroid (the service's rule)",
        accuracy: rec(0.861745), balanced_accuracy: rec(0.797915) },
      { key: 'restricted_native_centroid:mean', measure: 'Protein, restricted, 5-seed mean', rule: "nearest centroid (the service's rule)",
        accuracy: rec(0.793826, { sd: 0.047084 }), balanced_accuracy: rec(0.633237, { sd: 0.108427, min: 0.507871, max: 0.797915 }) },
      { key: 'restricted_shared_knn:mean', measure: '<b>x</b>', rule: "shared kNN (the benchmark's rule)",
        accuracy: rec(0.753154, { sd: 0.117906 }), balanced_accuracy: rec(0.714998, { sd: 0.106004, min: 0.590433, max: 0.883992 }) },
    ],
    vs_scanvi: {
      restricted_shared_knn: { pairings: 15, v3_ahead: 3, mean_difference: measured(-0.05654, 'x') },
      unrestricted: { pairings: 15, v3_ahead: 12, mean_difference: measured(0.181375, 'x') },
    },
  };
  return m;
};

test('model card facts compare like with like and come from the manifest', () => {
  const m = withModelCard();
  assert.equal(factText(m, 'restricted_centroid_seed0'), '79.8%');
  assert.equal(factText(m, 'restricted_centroid_mean'), '63.3% &plusmn; 10.8');
  assert.equal(factText(m, 'restricted_centroid_range'), '50.8 to 79.8%');
  assert.equal(factText(m, 'restricted_knn_spread'), '29.4 points');
  assert.equal(factText(m, 'scanvi_restricted_pairings'), '3 of 15');
  assert.equal(factText(m, 'scanvi_unrestricted_pairings'), '12 of 15');
  assert.equal(factText(m, 'scanvi_unrestricted_margin'), '18.1 points');
  for (const key of ['restricted_centroid_mean', 'scanvi_unrestricted_margin', 'restricted_knn_range']) {
    assert.match(factText(manifestFixture(), key), /Pending/, `${key} without a model card`);
  }
});

test('a protein count of 0 reads none; a missing one reads Pending, not none', () => {
  const m = manifestFixture();
  m.cell_types = m.cell_types.map((c, i) => (i === 1 ? { ...c, prot_cells: null } : c));
  const html = buildSupportTable(m);
  const rowOf = (name) => html.slice(html.indexOf(`>${name}<`), html.indexOf('</tr>', html.indexOf(`>${name}<`)));
  const missing = m.cell_types[1].name;
  assert.match(rowOf(missing), /Pending/);
  assert.match(html, /none/, 'a class with 0 protein cells still reads none');
});
