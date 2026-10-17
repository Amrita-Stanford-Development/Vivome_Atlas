import { test } from 'node:test';
import assert from 'node:assert/strict';
import { clamp01, countText } from '../js/motion.js';

test('clamp01 stays in 0..1', () => {
  assert.equal(clamp01(-1), 0);
  assert.equal(clamp01(2), 1);
  assert.equal(clamp01(0.5), 0.5);
});

test('counting up keeps the final format and leaves non-numbers alone', () => {
  assert.equal(countText('85,233', 1), '85,233');
  assert.equal(countText('85,233', 0), '0');
  assert.match(countText('85,233', 0.5), /^\d{1,3}(,\d{3})*$/);
  assert.equal(countText('94.9%', 0), '0.0%');
  assert.match(countText('94.9%', 0.5), /^\d+\.\d%$/);
  assert.equal(countText('22', 0.999).length <= 2, true);
  for (const text of ['Pending', '0.3.0', 'VivOME v3.1', '']) assert.equal(countText(text, 0.3), text);
});
