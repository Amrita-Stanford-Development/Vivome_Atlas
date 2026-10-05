import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  clamp01, between, smooth, HERO_IN, heroEntrance, heroExit, countText,
} from '../js/motion.js';

test('clamp01, between and smooth stay in 0..1', () => {
  assert.equal(clamp01(-1), 0);
  assert.equal(clamp01(2), 1);
  assert.equal(between(0.5, 0, 1), 0.5);
  assert.equal(between(-1, 0, 1), 0);
  assert.equal(between(2, 0, 1), 1);
  assert.equal(between(1, 1, 1), 1);
  assert.equal(smooth(0), 0);
  assert.equal(smooth(1), 1);
  assert.equal(smooth(0.5), 0.5);
});

test('the opening eases each object in, one after another, in about three seconds', () => {
  let last = -1;
  for (let t = 0; t <= 4; t += 0.05) {
    const v = heroEntrance(t, 0);
    assert.ok(v >= last, 'never goes back');
    last = v;
  }
  assert.equal(heroEntrance(0, 0), 0);
  assert.equal(heroEntrance(HERO_IN.each, 0), 1);
  // A later object is behind an earlier one at the same moment.
  assert.ok(heroEntrance(1, 5) < heroEntrance(1, 0));
  // Even the twelfth has settled by 3.5 seconds.
  assert.equal(heroEntrance(3.5, 11), 1);
});

test('an object stays put at p = 0 and has left the screen by p = 1', () => {
  for (const [rest, size] of [[{ x: -0.7, y: 0.2 }, 0.3], [{ x: 0.85, y: -0.6 }, 0.2], [{ x: 0.1, y: 0.9 }, 0.15], [{ x: 0, y: 0 }, 0.2]]) {
    const start = heroExit(rest, size, 0);
    assert.equal(start.x, 0);
    assert.equal(start.y, 0);
    assert.equal(start.scale, 1);
    const end = heroExit(rest, size, 1);
    const x = rest.x + end.x;
    const y = rest.y + end.y;
    assert.ok(Math.abs(x) >= 1 + size - 1e-9 || Math.abs(y) >= 1 + size - 1e-9, `still on screen at ${x}, ${y}`);
    // Outward: it never moves towards the centre.
    assert.ok(x * rest.x >= 0 && y * rest.y >= 0);
  }
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
