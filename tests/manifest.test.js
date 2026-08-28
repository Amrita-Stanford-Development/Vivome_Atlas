import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  PENDING_LABEL, validateManifest, formatMetric, formatPercent,
  metricBasis, supportRows, isLfsPointer,
} from '../js/manifest.js';

const measured = (v, basis) => ({ value: v, status: 'measured', basis });
const pending = (phase) => ({ value: null, status: 'pending', phase, note: 'n/a' });

function fixture() {
  return {
    schema_version: '1.0',
    atlas_version: '0.1.0',
    generated: '2026-08-29',
    model: { name: 'CrossModalNet', latent_dim: 128 },
    modalities: { rna: { cells: 85233 }, prot: { cells: 1490 } },
    cell_types: [
      { class_idx: 16, name: 'neutrophil', rna_cells: 32198, prot_cells: 0,
        support: 'rna_only', pca_centroid_cosine: pending('Phase 2') },
      { class_idx: 12, name: 'monocyte', rna_cells: 9602, prot_cells: 1096,
        support: 'cross_modal', pca_centroid_cosine: measured(0.998634, '3-PC projection') },
      { class_idx: 10, name: 'macrophage', rna_cells: 1228, prot_cells: 394,
        support: 'cross_modal', pca_centroid_cosine: measured(0.997242, '3-PC projection') },
    ],
    summary: { total: 3, cross_modal: 2, rna_only: 1, prot_only: 0 },
    benchmark: { status: 'pending', rows: [] },
    data_availability: {},
  };
}

test('validateManifest returns the manifest when complete', () => {
  const m = fixture();
  assert.equal(validateManifest(m), m);
});

test('validateManifest throws naming the missing key', () => {
  const m = fixture();
  delete m.cell_types;
  assert.throws(() => validateManifest(m), /cell_types/);
});

test('measured metric formats to fixed digits', () => {
  assert.equal(formatMetric(measured(0.998634, '3-PC projection')), '0.999');
  assert.equal(formatMetric(measured(0.998634, '3-PC projection'), 6), '0.998634');
});

test('pending metric never renders a number', () => {
  assert.equal(formatMetric(pending('Phase 1')), PENDING_LABEL);
});

test('missing or malformed metric renders as pending, not as zero', () => {
  assert.equal(formatMetric(undefined), PENDING_LABEL);
  assert.equal(formatMetric(null), PENDING_LABEL);
  assert.equal(formatMetric({ value: 0, status: 'pending' }), PENDING_LABEL);
  assert.equal(formatMetric({ value: null, status: 'measured' }), PENDING_LABEL);
});

test('a genuine zero measurement still renders', () => {
  assert.equal(formatMetric(measured(0, 'probe')), '0.000');
});

test('formatPercent renders one decimal with a percent sign', () => {
  assert.equal(formatPercent(measured(0.4228, 'accuracy')), '42.3%');
  assert.equal(formatPercent(pending('Phase 1')), PENDING_LABEL);
});

test('metricBasis gives basis when measured and phase when pending', () => {
  assert.equal(metricBasis(measured(1, '3-PC projection')), '3-PC projection');
  assert.equal(metricBasis(pending('Phase 4')), 'Phase 4');
  assert.equal(metricBasis(undefined), '');
});

test('supportRows puts cross-modal first, then descending RNA count', () => {
  const rows = supportRows(fixture());
  assert.deepEqual(rows.map(r => r.name), ['monocyte', 'macrophage', 'neutrophil']);
});

test('supportRows does not mutate the manifest order', () => {
  const m = fixture();
  supportRows(m);
  assert.equal(m.cell_types[0].name, 'neutrophil');
});

test('isLfsPointer detects a pointer file', () => {
  const ptr = 'version https://git-lfs.github.com/spec/v1\noid sha256:765299ae\nsize 1432231477\n';
  assert.equal(isLfsPointer(ptr), true);
});

test('isLfsPointer is false for real CSV content and non-strings', () => {
  assert.equal(isLfsPointer('latent_dim,modality,orig_index\n128,RNA,0\n'), false);
  assert.equal(isLfsPointer(''), false);
  assert.equal(isLfsPointer(null), false);
});
