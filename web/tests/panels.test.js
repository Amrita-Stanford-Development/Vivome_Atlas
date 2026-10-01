import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  escapeHtml, errorPanel, buildSupportSummary, buildSupportTable,
  buildDiagnosticsTable, buildBenchmarkTable, buildModelCard, buildNextReferenceCard, buildPriorBaselineCard,
  buildAvailabilityTable, buildSupportedLabelSpace, buildReleaseStatus, buildWhatsNew, buildProofPoints, factText,
  buildProjectionSummary, buildProjectionLabels, buildProjectionCells, buildModelCardTable,
} from '../js/panels.js';
import { measured, pending, manifestFixture, nextReferenceFixture } from './fixtures.js';

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

test('benchmark table renders a pending notice and lists planned methods', () => {
  const html = buildBenchmarkTable(manifestFixture());
  assert.match(html, /Not run yet\./);
  assert.match(html, /GLUE/);
  assert.match(html, /Pending/);
});

test('benchmark table renders measured rows when present', () => {
  const m = manifestFixture();
  m.benchmark.status = 'measured';
  m.benchmark.rows = [{ method: 'GLUE', dataset: 'SCoPE2',
    transfer_accuracy: measured(0.883, 'mean of 10 seeds'),
    modality_probe_accuracy: measured(0.51, 'linear probe') }];
  const html = buildBenchmarkTable(m);
  assert.match(html, /88\.3%/);
  assert.match(html, /51\.0%/);
  assert.ok(!/<span class="pending">88\.3%/.test(html));
});

test('benchmark table uses one header list for both branches', () => {
  const pendingHead = buildBenchmarkTable(manifestFixture()).match(/<thead>.*?<\/thead>/s)[0];
  const m = manifestFixture();
  m.benchmark.status = 'measured';
  m.benchmark.rows = [{ method: 'GLUE', dataset: 'SCoPE2',
    transfer_accuracy: measured(0.883, 'x'), modality_probe_accuracy: measured(0.51, 'y') }];
  const measuredHead = buildBenchmarkTable(m).match(/<thead>.*?<\/thead>/s)[0];
  assert.equal(pendingHead, measuredHead);
});

test('model card shows version, dims, and a measured seed count', () => {
  const html = buildModelCard(manifestFixture());
  assert.match(html, /0\.2\.0/);
  assert.match(html, /128/);
  assert.match(html, /<dd>5<\/dd>/);
  assert.ok(!/<span class="pending">5/.test(html),
    'a measured seed count must not carry the pending style');
});

test('model card marks a pending seed count with the pending style', () => {
  const m = manifestFixture();
  m.model.seeds = pending('Phase 1');
  const html = buildModelCard(m);
  assert.match(html, /<span class="pending">Pending<\/span>/);
});

test('model card renders the folded-in architecture facts', () => {
  const html = buildModelCard(manifestFixture());
  assert.match(html, /9,002/);
  assert.match(html, /module pooling/);
  assert.match(html, /uniform/);
});

test('model card omits the architecture fields on an older manifest that predates them', () => {
  const m = manifestFixture();
  delete m.model.feature_space_size;
  delete m.model.previous_feature_space_size;
  delete m.model.encoder_family;
  delete m.model.mask_sampling;
  delete m.model.detected_by_source;
  const html = buildModelCard(m);
  assert.ok(!html.includes('undefined'), html);
  assert.ok(!html.includes('NaN'), html);
});

test('model card renders Pending, not NaN, for absent modality counts', () => {
  const m = manifestFixture();
  m.modalities = {};
  const html = buildModelCard(m);
  assert.ok(!html.includes('NaN'), html);
  assert.ok(!html.includes('undefined'), html);
});

test('next reference card shows the settled architecture facts', () => {
  // The real manifest's next_reference is null today — the architecture
  // change it described is complete (folded into `model` instead). This
  // rendering path stays real code, worth testing against a hypothetical
  // future one via its own fixture.
  const m = manifestFixture();
  m.next_reference = nextReferenceFixture();
  const html = buildNextReferenceCard(m);
  assert.match(html, /module pooling/);
  assert.match(html, /uniform/);
  assert.match(html, /9,002/);
  assert.match(html, /Not yet/);
});

test('next reference card never reads as an update to the deployed model card', () => {
  const m = manifestFixture();
  m.next_reference = nextReferenceFixture();
  const html = buildNextReferenceCard(m);
  assert.ok(!html.includes('VivOME v3 reference'), 'must not merge with the current release\'s own model card');
});

test('next reference card renders nothing when the manifest has no next_reference', () => {
  const m = manifestFixture();
  delete m.next_reference;
  assert.equal(buildNextReferenceCard(m), '');
});

test('prior baseline card shows the real kept numbers, not erased', () => {
  const html = buildPriorBaselineCard(manifestFixture());
  assert.match(html, /CrossModalNet/);
  assert.match(html, /2,903/);
  assert.match(html, /0\.6417/);
  assert.match(html, /ribosome/);
});

test('prior baseline card renders nothing when the manifest has no previous_release', () => {
  const m = manifestFixture();
  delete m.previous_release;
  assert.equal(buildPriorBaselineCard(m), '');
});

test('availability table maps status enums to readable labels', () => {
  const html = buildAvailabilityTable(manifestFixture());
  assert.match(html, /Not fetched \(Git LFS\)/);
  assert.match(html, /Available/);
  assert.ok(!html.includes('lfs_not_fetched'), 'raw enum token must not reach the page');
});

test('availability table shows the remedy command', () => {
  assert.match(buildAvailabilityTable(manifestFixture()), /git lfs install &amp;&amp; git lfs pull/);
});

test('supported label space lists cross-modal types and the RNA-only count', () => {
  const html = buildSupportedLabelSpace(manifestFixture());
  assert.match(html, /Cross-modal support \(2\)/);
  assert.match(html, /monocyte/);
  assert.match(html, /macrophage/);
  assert.match(html, /RNA-only \(1\)/);
});

test('release status shows the manifest release facts', () => {
  const html = buildReleaseStatus(manifestFixture());
  assert.match(html, /Atlas version<\/dt><dd>0\.2\.0/);
  assert.match(html, /VivOME v3 reference/);
  assert.match(html, /RNA cells<\/dt><dd>85,233/);
  assert.match(html, /Protein cells<\/dt><dd>1,490/);
});

test('release status renders Pending, never undefined, for missing fields', () => {
  const m = manifestFixture();
  delete m.atlas_version;
  delete m.model.name;
  m.modalities = {};
  const html = buildReleaseStatus(m);
  assert.ok(!html.includes('undefined'), html);
  assert.ok(!html.includes('NaN'), html);
  assert.match(html, /Pending/);
});

test('release status escapes model names', () => {
  const m = manifestFixture();
  m.model.name = '<script>alert(1)</script>';
  assert.ok(!buildReleaseStatus(m).includes('<script>'));
});

test("what's new formats dates and escapes every field", () => {
  const html = buildWhatsNew([{
    date: '2026-09-30', title: '<b>t</b>', text: '<img src=x>', link: 'atlas.html', link_text: '<i>go</i>',
  }]);
  assert.match(html, /30 September 2026/);
  assert.match(html, /datetime="2026-09-30"/);
  assert.ok(!html.includes('<b>') && !html.includes('<img') && !html.includes('<i>'), html);
  assert.match(html, /href="atlas\.html"/);
});

test("what's new drops links that are not pages of this site", () => {
  for (const link of ['javascript:alert(1)', 'https://example.com', '../secret.html', '//x.html']) {
    const html = buildWhatsNew([{ date: '2026-09-30', title: 't', text: 'x', link }]);
    assert.ok(!html.includes('href='), `${link} should not render: ${html}`);
  }
  const anchored = buildWhatsNew([{ date: '2026-09-30', title: 't', text: 'x', link: 'project.html#labels' }]);
  assert.match(anchored, /href="project\.html#labels"/);
});

test("what's new says so when there is nothing to announce", () => {
  assert.match(buildWhatsNew([]), /No announcements yet/);
  assert.match(buildWhatsNew(null), /No announcements yet/);
});

test("the shipped what's new entries render with no metrics in them", async () => {
  const { readFileSync } = await import('node:fs');
  const entries = JSON.parse(readFileSync(new URL('../data/whats_new.json', import.meta.url), 'utf8'));
  assert.ok(entries.length > 0);
  for (const e of entries) {
    assert.match(e.date, /^\d{4}-\d{2}-\d{2}$/, e.title);
    // Numbers belong in the manifest; an announcement links to them instead.
    // Version names (v3.1) are names, not measurements.
    assert.ok(!/\d%|(?<![v\d.])\d+\.\d/.test(`${e.title} ${e.text}`), `metric-like text in: ${e.title}`);
  }
});

test('proof points come from the manifest', () => {
  const html = buildProofPoints(manifestFixture());
  assert.match(html, /RNA cells in the reference<\/dt><dd>85,233/);
  assert.match(html, /protein cells, projected zero-shot<\/dt><dd>1,490/);
  assert.match(html, /cell types<\/dt><dd>3</);
  assert.match(html, /atlas version<\/dt><dd>0\.2\.0/);
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
  assert.equal(factText(m, 'atlas_version'), '0.2.0');
  assert.equal(factText(m, 'model_name'), 'VivOME v3 reference');
  assert.equal(factText(m, 'previous_model'), 'CrossModalNet');
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
});

test('projection labels count each label and each abstain reason, most first', () => {
  const html = buildProjectionLabels(projection());
  assert.ok(html.indexOf('monocyte') < html.indexOf('Abstained'), html);
  assert.match(html, /monocyte<\/td><td class="support-num">2<\/td><td class="support-num">66\.7%/);
  assert.match(html, /Abstained: Too few observed genes/);
});

test('projection cells escape ids from the upload and show abstentions plainly', () => {
  const html = buildProjectionCells(projection());
  assert.ok(!html.includes('<img'), 'a cell id from the upload must not become markup');
  assert.match(html, /&lt;img/);
  assert.match(html, /0\.912/);
  assert.match(html, /Too few observed genes/);
});

test('projection cells show the first rows and say how many there are', () => {
  const html = buildProjectionCells(projection(), 2);
  assert.equal((html.match(/<tr>/g) ?? []).length, 3, 'header row plus two cells');
  assert.match(html, /first 2 of 3 cells/);
});

test('projection builders survive a malformed response', () => {
  for (const build of [buildProjectionSummary, buildProjectionLabels, buildProjectionCells]) {
    const html = build({});
    assert.ok(!html.includes('undefined') && !html.includes('NaN'), `${build.name}: ${html}`);
  }
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

test("the model card table names each row's rule and shows mean, spread and range", () => {
  const html = buildModelCardTable(withModelCard());
  assert.match(html, /nearest centroid \(the service&#39;s rule\)/);
  assert.match(html, /79\.8%/);
  assert.match(html, /63\.3% &plusmn; 10\.8/);
  assert.match(html, /range 50\.8 to 79\.8%/);
  assert.ok(!html.includes('<b>x</b>'), 'measure names are escaped');
});

test('the model card table reads Pending when the manifest has none', () => {
  assert.match(buildModelCardTable(manifestFixture()), /Pending/);
});

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
