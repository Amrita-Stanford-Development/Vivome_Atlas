import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  escapeHtml, errorPanel, buildSupportSummary, buildSupportTable,
  buildDiagnosticsTable, buildBenchmarkTable, buildModelCard,
  buildAvailabilityTable, buildSupportedLabelSpace,
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

test('diagnostics table renders measured cosine and Pending elsewhere', () => {
  const html = buildDiagnosticsTable(manifestFixture());
  assert.match(html, /0\.9986/);
  assert.match(html, /Pending/);
});

test('diagnostics table labels the basis of the measured value', () => {
  assert.match(buildDiagnosticsTable(manifestFixture()), /3-PC projection/);
});

test('diagnostics table marks pending cells with the pending class', () => {
  const html = buildDiagnosticsTable(manifestFixture());
  assert.match(html, /<span class="pending">Pending<\/span>/);
});

test('diagnostics table does not mark a measured cell as pending', () => {
  const html = buildDiagnosticsTable(manifestFixture());
  assert.ok(!/<span class="pending">0\.9986/.test(html));
});

test('diagnostics table includes only cross-modal rows', () => {
  const html = buildDiagnosticsTable(manifestFixture());
  assert.ok(!html.includes('&lt;script&gt;'), 'RNA-only row must not appear');
  assert.equal((html.match(/<tr>/g) || []).length, 3);
});

test('diagnostics table never prints a bare zero for a pending metric', () => {
  assert.ok(!/>0\.000</.test(buildDiagnosticsTable(manifestFixture())));
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

test('model card shows version, dims, and a pending seed count', () => {
  const html = buildModelCard(manifestFixture());
  assert.match(html, /0\.1\.0/);
  assert.match(html, /128/);
  assert.match(html, /<span class="pending">Pending<\/span>/);
});

test('model card stops marking seeds pending once they are measured', () => {
  const m = manifestFixture();
  m.model.seeds = measured(10, 'completed runs');
  const html = buildModelCard(m);
  assert.match(html, /<dd>10<\/dd>/);
  assert.ok(!/<span class="pending">10/.test(html),
    'a measured seed count must not carry the pending style');
});

test('model card renders Pending, not NaN, for absent modality counts', () => {
  const m = manifestFixture();
  m.modalities = {};
  const html = buildModelCard(m);
  assert.ok(!html.includes('NaN'), html);
  assert.ok(!html.includes('undefined'), html);
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
