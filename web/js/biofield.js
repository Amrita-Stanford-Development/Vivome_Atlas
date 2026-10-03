// The living water behind every page: the objects of web/js/biocells.js
// (cells, DNA, chromatin and threads) drifting in a soft gel over the
// breathing field and particles of web/js/background.js, with a wake that
// follows the pointer (web/js/water.js). One fixed canvas and a frost layer,
// both behind the page, so the content and the white cards sit on top.
//
// Loaded after background.js as <script type="module" src="js/biofield.js">;
// it mounts itself. Under prefers-reduced-motion it draws one still frame
// and the pointer leaves no wake. Without WebGL, or if three.js fails to
// load, it removes itself and the page keeps background.js alone.

import { PALETTES, createBioLayer } from './biocells.js';
import { createEffect, createSceneTarget, supported } from './water.js';

// The same three.js build as the landing story and the atlas viewer.
// web/tests/chrome.test.js pins the URLs together.
const THREE_URL = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';

const canvas = document.createElement('canvas');
canvas.className = 'bio-field';
canvas.setAttribute('aria-hidden', 'true');
const frost = document.createElement('div');
frost.className = 'bio-frost';
frost.setAttribute('aria-hidden', 'true');
// Their look is in css/page.css; where they sit is also set here, so a
// stale stylesheet can never let them push the page down.
for (const el of [canvas, frost]) {
  el.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;z-index:-1;pointer-events:none';
}
// Just above background.js's canvas, and like it, behind the page.
const field = document.querySelector('.site-bg');
if (field) field.after(canvas, frost); else document.body.prepend(canvas, frost);

const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
const compact = window.matchMedia('(max-width: 820px)').matches;

function giveUp(err) {
  console.warn('Living water unavailable, keeping the plain field:', err);
  canvas.remove();
  frost.remove();
}

// Another script on the page (the landing story) may already be loading
// three.js; wait for it rather than load it twice.
function loadThree() {
  if (window.THREE) return Promise.resolve(window.THREE);
  return new Promise((resolve, reject) => {
    let script = document.querySelector(`script[src="${THREE_URL}"]`);
    if (!script) {
      script = document.createElement('script');
      script.src = THREE_URL;
      document.head.append(script);
    }
    script.addEventListener('load', () => resolve(window.THREE));
    script.addEventListener('error', () => reject(new Error('three.js failed to load')));
  });
}

function start(THREE) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, compact ? 1.5 : 1.75));
  renderer.autoClear = false;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
  const layer = createBioLayer(THREE, { palette: PALETTES.vivid, density: 'calm', compact });
  scene.add(layer.group);
  const target = createSceneTarget(THREE);
  const effect = createEffect(THREE, supported(renderer) ? 'wake' : 'still');

  const born = performance.now();
  let last = born;
  let time = 0;
  let running = false;

  function draw(now, dt) {
    const t = reduced.matches ? 1 : Math.min(1, (now - born) / 2600);
    layer.setFade(t * t * (3 - 2 * t));
    layer.update(time, { aspect: camera.aspect });
    renderer.setScissorTest(false);
    target.capture(renderer, scene, camera);
    effect.step(renderer, time, dt);
    renderer.setViewport(0, 0, window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    renderer.clear();
    effect.draw(renderer, target.texture);
  }

  function loop(now) {
    if (!running) return;
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    time += dt;
    draw(now, dt);
    requestAnimationFrame(loop);
  }

  function play() {
    if (reduced.matches) {
      running = false;
      draw(performance.now(), 0);
    } else if (!running) {
      running = true;
      last = performance.now();
      requestAnimationFrame(loop);
    }
  }

  function resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    target.setSize(w, h, renderer.getPixelRatio());
    effect.setSize(w, h);
    if (!running) draw(performance.now(), 0);
  }

  // The wake: a small drop wherever the pointer has moved a few pixels on.
  let lastWake = null;
  window.addEventListener('pointermove', (e) => {
    if (reduced.matches) return;
    if (lastWake && Math.hypot(e.clientX - lastWake[0], e.clientY - lastWake[1]) < 6) return;
    lastWake = [e.clientX, e.clientY];
    effect.drop(e.clientX / window.innerWidth, 1 - e.clientY / window.innerHeight, 0.22, 0.02);
  }, { passive: true });

  window.addEventListener('resize', resize);
  reduced.addEventListener('change', play);
  resize();
  play();
}

loadThree().then((THREE) => {
  try {
    start(THREE);
  } catch (err) {
    giveUp(err);
  }
}).catch(giveUp);
