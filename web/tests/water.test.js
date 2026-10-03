// The water effects' list (web/js/water.js), which the previews build their
// choosers and cards from. The shaders are checked by eye on
// web/preview-water.html.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EFFECTS } from '../js/water.js';

test('every effect has a unique name, a label and a description', () => {
  const names = EFFECTS.map((e) => e.name);
  assert.deepEqual(names, ['still', 'flow', 'rain', 'touch', 'wake', 'ink']);
  for (const e of EFFECTS) {
    assert.ok(e.label && e.about, e.name);
    assert.ok([null, 'click', 'move'].includes(e.pointer), `${e.name}: pointer ${e.pointer}`);
  }
});

test('the descriptions follow the site copy rules: sentence case, no em dashes', () => {
  for (const e of EFFECTS) {
    assert.ok(!/\u2014/.test(e.about + e.label), `${e.name} uses an em dash`);
    assert.equal(e.label[0], e.label[0].toUpperCase(), e.name);
    assert.ok(e.label.slice(1) === e.label.slice(1).toLowerCase(), `${e.name}: "${e.label}" is not sentence case`);
  }
});
