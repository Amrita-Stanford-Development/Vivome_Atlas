import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  escapeHtml, errorPanel, buildSupportSummary, buildSupportTable,
  buildDiagnosticsTable, buildBenchmarkTable, buildModelCard, buildNextReferenceCard, buildPriorBaselineCard,
  buildAvailabilityTable, buildSupportedLabelSpace,
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
