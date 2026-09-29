import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  PENDING_LABEL, validateManifest, formatMetric, formatPercent, formatCount,
  metricBasis, isMeasured, supportRows, isLfsPointer,
} from '../js/manifest.js';
import { measured, pending, manifestFixture } from './fixtures.js';

test('validateManifest returns the manifest when complete', () => {
  const m = manifestFixture();
  assert.equal(validateManifest(m), m);
});

test('validateManifest throws naming the missing key', () => {
  const m = manifestFixture();
  delete m.cell_types;
  assert.throws(() => validateManifest(m), /cell_types/);
});

test('validateManifest rejects an unsupported schema version', () => {
  const m = manifestFixture();
  m.schema_version = '2.0';
  assert.throws(() => validateManifest(m), /schema_version 2\.0 is not supported/);
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

test('isMeasured is true only for a measured record with a finite value', () => {
  assert.equal(isMeasured(measured(0.5, 'x')), true);
  assert.equal(isMeasured(measured(0, 'x')), true);
  assert.equal(isMeasured(pending('Phase 1')), false);
  assert.equal(isMeasured({ value: 'abc', status: 'measured' }), false);
  assert.equal(isMeasured(undefined), false);
});

test('formatCount groups thousands', () => {
  assert.equal(formatCount(85233), '85,233');
  assert.equal(formatCount(0), '0');
});

test('formatCount never renders NaN or undefined for a missing count', () => {
  assert.equal(formatCount(undefined), PENDING_LABEL);
  assert.equal(formatCount(null), PENDING_LABEL);
  assert.equal(formatCount('not a number'), PENDING_LABEL);
  assert.equal(formatCount(NaN), PENDING_LABEL);
});

test('metricBasis gives basis when measured and phase when pending', () => {
  assert.equal(metricBasis(measured(1, '3-PC projection')), '3-PC projection');
  assert.equal(metricBasis(pending('Phase 4')), 'Phase 4');
  assert.equal(metricBasis(undefined), '');
});

test('supportRows puts cross-modal first, then descending RNA count', () => {
  const rows = supportRows(manifestFixture());
  assert.deepEqual(rows.map((r) => r.name), ['monocyte', 'macrophage', '<script>alert(1)</script>']);
});

test('supportRows does not mutate the manifest order', () => {
  const m = manifestFixture();
  supportRows(m);
  assert.equal(m.cell_types[0].class_idx, 16);
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
