import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rng } from '../js/random.js';

test('rng is deterministic and in [0, 1)', () => {
  const a = rng(7);
  const b = rng(7);
  for (let i = 0; i < 100; i++) {
    const x = a();
    assert.equal(x, b());
    assert.ok(x >= 0 && x < 1);
  }
});

// Pinned, so the site's procedural shapes stay the same from visit to visit
// (and across the move of rng from the old formations module).
test('rng(7) starts with the same three draws as ever', () => {
  const r = rng(7);
  assert.deepEqual([r(), r(), r()], [0.011704753153026104, 0.06195825757458806, 0.97690763277933]);
});
