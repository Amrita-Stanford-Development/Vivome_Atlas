// The 3D map by keyboard (web/js/atlas/stage.js, createOrbitRig): with the
// map focused, the arrows turn it, Shift and the arrows move it, + and - zoom,
// and Enter opens the cell nearest the centre.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createOrbitRig } from '../js/atlas/stage.js';

function fakes() {
  const target = new EventTarget();
  target.setPointerCapture = () => {};
  target.getBoundingClientRect = () => ({ left: 100, top: 50, width: 800, height: 600 });
  const camera = {
    position: { set() {} }, up: { set() {} }, lookAt() {}, updateMatrixWorld() {},
    matrixWorld: { elements: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] },
  };
  return { canvas: target, camera };
}

const key = (canvas, k, extra = {}) => {
  const e = Object.assign(new Event('keydown', { cancelable: true }), { key: k, shiftKey: false, ...extra });
  canvas.dispatchEvent(e);
  return e;
};

test('the arrows turn the map, Shift and the arrows move it, + and - zoom', () => {
  const { canvas, camera } = fakes();
  const rig = createOrbitRig(camera, canvas, { reduced: true });
  const yaw = rig.pose.yaw;
  assert.ok(key(canvas, 'ArrowRight').defaultPrevented, 'the page does not scroll');
  assert.notEqual(rig.pose.yaw, yaw);
  const pitch = rig.pose.pitch;
  key(canvas, 'ArrowUp');
  assert.notEqual(rig.pose.pitch, pitch);
  const target = [...rig.pose.target];
  key(canvas, 'ArrowLeft', { shiftKey: true });
  assert.notDeepEqual(rig.pose.target, target);
  const radius = rig.pose.radius;
  key(canvas, '+');
  assert.ok(rig.pose.radius < radius, 'closer');
  key(canvas, '-');
  key(canvas, '-');
  assert.ok(rig.pose.radius > radius, 'farther');
});

test('Enter opens the cell nearest the centre, as a click there would', () => {
  const { canvas, camera } = fakes();
  const rig = createOrbitRig(camera, canvas, { reduced: true });
  const clicks = [];
  rig.on('click', (e) => clicks.push([e.clientX, e.clientY]));
  key(canvas, 'Enter');
  assert.deepEqual(clicks, [[500, 350]]);
  key(canvas, 'x');
  assert.equal(clicks.length, 1, 'other keys do nothing');
});

test('the map can take focus and says how to use it; the landing leaves it its arrows', () => {
  const html = readFileSync(new URL('../atlas.html', import.meta.url), 'utf8');
  assert.match(html, /<canvas id="three-canvas" tabindex="0" role="application"[^>]*aria-describedby="scene-info"/);
  assert.match(html, /arrows turn/);
  const landing = readFileSync(new URL('../js/atlas/landing.js', import.meta.url), 'utf8');
  assert.match(landing, /\[role="application"\]/);
});
