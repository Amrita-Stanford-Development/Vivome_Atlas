// The site's "Pause motion" switch (web/js/motion-pref.js) and what reads it.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

function installBrowser({ system = false, stored = null } = {}) {
  const classes = new Set();
  const buttons = [];
  const store = new Map(stored ? [['vivome-motion', stored]] : []);
  const media = { matches: system, listeners: [], addEventListener(type, f) { this.listeners.push(f); } };
  const button = {
    attrs: {}, handlers: [],
    setAttribute(k, v) { this.attrs[k] = v; },
    addEventListener(type, f) { this.handlers.push(f); },
    click() { this.handlers.forEach((f) => f()); },
  };
  buttons.push(button);
  globalThis.window = { matchMedia: () => media };
  globalThis.document = {
    documentElement: { classList: { toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)) } },
    querySelectorAll: (sel) => (sel === '.motion-toggle' ? buttons : []),
  };
  globalThis.localStorage = {
    getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k),
  };
  return { classes, button, store, media };
}

let n = 0;
const fresh = () => import(`../js/motion-pref.js?case=${n += 1}`);

test('the switch pauses and resumes motion, is remembered, and tells every listener', async () => {
  const b = installBrowser();
  const m = await fresh();
  assert.equal(m.motionStill(), false);
  assert.equal(b.button.attrs['aria-pressed'], 'false');
  let heard = 0;
  m.onMotionChange(() => { heard += 1; });
  b.button.click();
  assert.equal(m.motionStill(), true);
  assert.ok(b.classes.has('motion-off'));
  assert.equal(b.button.attrs['aria-pressed'], 'true');
  assert.equal(b.store.get('vivome-motion'), 'off');
  assert.equal(heard, 1);
  b.button.click();
  assert.equal(m.motionStill(), false);
  assert.ok(!b.classes.has('motion-off'));
  assert.equal(b.store.has('vivome-motion'), false);
});

test('a remembered pause, or the system setting, starts still', async () => {
  installBrowser({ stored: 'off' });
  assert.equal((await fresh()).motionStill(), true);
  installBrowser({ system: true });
  const m = await fresh();
  assert.equal(m.motionStill(), true);
  assert.equal(m.motionPaused(), false, 'the system, not the switch');
});

test('every page has the switch, and every moving part reads it', () => {
  for (const page of ['index.html', 'atlas.html', 'manuscript.html', 'workflow.html', 'motion.html']) {
    assert.match(read(page), /<button type="button" class="motion-toggle" aria-pressed="false">Pause motion<\/button>/, page);
  }
  for (const file of ['js/background.js', 'js/biofield.js']) {
    const code = read(file);
    assert.match(code, /from '\.\/motion-pref\.js'/, file);
    assert.doesNotMatch(code, /prefers-reduced-motion: reduce/, `${file} reads the shared preference`);
  }
  const main = read('js/atlas/main.js');
  assert.match(main, /onMotionChange/);
  assert.match(main, /stage\.rig\.setStill\(/);
  assert.match(main, /landing\.setStill\(/);
  assert.match(read('js/atlas/landing.js'), /setStill\(on\) \{/);
  assert.match(read('css/page.css'), /html\.motion-off \*/);
  // Each stylesheet's reduced-motion rules have their switch copy.
  for (const sheet of ['css/page.css', 'css/story.css', 'css/workflow.css', 'css/atlas.css']) {
    const css = read(sheet);
    const blocks = css.match(/@media \(prefers-reduced-motion: reduce\)/g)?.length ?? 0;
    const copies = css.match(/^\s*(html)?\.(js)?\.?motion-off /gm)?.length ?? 0;
    assert.ok(copies >= blocks, `${sheet}: ${blocks} reduced-motion blocks, ${copies} switch rules`);
  }
});

test('paused midway, the map stops its slow turn and ends a glide where it was going', async () => {
  const { createOrbitRig } = await import('../js/atlas/stage.js');
  const canvas = new EventTarget();
  canvas.setPointerCapture = () => {};
  const camera = {
    position: { set() {} }, up: { set() {} }, lookAt() {}, updateMatrixWorld() {},
    matrixWorld: { elements: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] },
  };
  const rig = createOrbitRig(camera, canvas, { reduced: false });
  assert.equal(rig.tick(0.1), true, 'the slow turn');
  const glide = rig.animateTo({ yaw: 1, radius: 40 }, 5);
  rig.tick(0.1);
  rig.setStill(true);
  await glide;
  assert.equal(rig.pose.radius, 40);
  assert.equal(rig.tick(0.1), false, 'nothing moves');
  rig.setStill(false);
  assert.equal(rig.tick(0.1), false, 'the turn waits for the idle minutes');
  rig.setStill(true);   // clears that timer, so the test run can end
});
