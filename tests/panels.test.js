import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  escapeHtml, buildSupportSummary, buildSupportTable,
  buildDiagnosticsTable, buildBenchmarkTable, buildModelCard,
} from '../js/panels.js';

const measured = (v, basis) => ({ value: v, status: 'measured', basis });
const pending = (phase) => ({ value: null, status: 'pending', phase, note: 'n/a' });

function fixture() {
  return {
    schema_version: '1.0',
    atlas_version: '0.1.0',
    generated: '2026-08-29',
    model: {
      name: 'CrossModalNet', latent_dim: 128, training_regime: 'supervised',
      seeds: pending('Phase 1'), notes: 'PCA projection of the latent space.',
    },
    modalities: {
      rna: { label: 'RNA', cells: 85233, classes: 22, source: 'scRNA-seq' },
      prot: { label: 'Protein', cells: 1490, classes: 2, source: 'SCoPE2 mass spectrometry' },
    },
    cell_types: [
      { class_idx: 12, name: 'monocyte', rna_cells: 9602, prot_cells: 1096, support: 'cross_modal',
        pca_centroid_cosine: measured(0.998634, '3-PC projection'),
        latent_centroid_cosine: pending('Phase 1'),
        modality_probe_accuracy: pending('Phase 4'),
        transfer_accuracy: pending('Phase 1') },
      { class_idx: 16, name: '<script>alert(1)</script>', rna_cells: 32198, prot_cells: 0,
        support: 'rna_only',
        pca_centroid_cosine: pending('Phase 2'),
        latent_centroid_cosine: pending('Phase 1'),
        modality_probe_accuracy: pending('Phase 4'),
        transfer_accuracy: pending('Phase 1') },
    ],
    summary: { total: 2, cross_modal: 1, rna_only: 1, prot_only: 0 },
    benchmark: { status: 'pending', phase: 'Phase 4', note: 'Not run yet.',
                 methods: ['CrossModalNet (ours)', 'GLUE'], rows: [] },
    data_availability: {},
  };
}

test('escapeHtml neutralises angle brackets and quotes', () => {
  assert.equal(escapeHtml('<b>"x"&\'y\'</b>'),
    '&lt;b&gt;&quot;x&quot;&amp;&#39;y&#39;&lt;/b&gt;');
});

test('support summary reports the real coverage counts', () => {
  const html = buildSupportSummary(fixture());
  assert.match(html, /support-tile-value">1<\/div><div class="support-tile-label">Cross-modal/);
  assert.match(html, /support-tile-value">1<\/div><div class="support-tile-label">RNA-only/);
  assert.match(html, /support-tile-value">2<\/div><div class="support-tile-label">Cell types/);
});

test('support table marks cross-modal and RNA-only rows distinctly', () => {
  const html = buildSupportTable(fixture());
  assert.match(html, /support-cross_modal/);
  assert.match(html, /support-rna_only/);
  assert.match(html, /Cross-modal/);
  assert.match(html, /RNA only/);
});

test('support table escapes cell type names', () => {
  const html = buildSupportTable(fixture());
  assert.ok(!html.includes('<script>alert(1)</script>'));
  assert.match(html, /&lt;script&gt;/);
});

test('support table shows counts with thousands separators', () => {
  assert.match(buildSupportTable(fixture()), /32,198/);
});

test('diagnostics table renders measured cosine and Pending elsewhere', () => {
  const html = buildDiagnosticsTable(fixture());
  assert.match(html, /0\.9986/);
  assert.match(html, /Pending/);
});

test('diagnostics table labels the basis of the measured value', () => {
  assert.match(buildDiagnosticsTable(fixture()), /3-PC projection/);
});

test('diagnostics table never prints a bare zero for a pending metric', () => {
  const html = buildDiagnosticsTable(fixture());
  assert.ok(!/>0\.000</.test(html));
});

test('benchmark table renders a pending notice and lists planned methods', () => {
  const html = buildBenchmarkTable(fixture());
  assert.match(html, /Not run yet\./);
  assert.match(html, /GLUE/);
  assert.match(html, /Pending/);
});

test('benchmark table renders measured rows when present', () => {
  const m = fixture();
  m.benchmark.status = 'measured';
  m.benchmark.rows = [{ method: 'GLUE', dataset: 'SCoPE2',
    transfer_accuracy: measured(0.883, 'mean of 10 seeds'),
    modality_probe_accuracy: measured(0.51, 'linear probe') }];
  const html = buildBenchmarkTable(m);
  assert.match(html, /88\.3%/);
  assert.match(html, /51\.0%/);
});

test('model card shows version, dims, and a pending seed count', () => {
  const html = buildModelCard(fixture());
  assert.match(html, /0\.1\.0/);
  assert.match(html, /128/);
  assert.match(html, /Pending/);
});
