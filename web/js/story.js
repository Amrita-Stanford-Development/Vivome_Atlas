// The landing story (index.html): one scroll listener, one render loop.
//
// The camera's flight through the water (web/js/field.js) and every text
// reveal (web/js/reveal.js) are driven from here, from each chapter's own
// rect: never from total page height. Timings live in web/js/motion.js.
// Under reduced motion there is no flight: the field is drawn once as still
// water and every reveal is shown.

import { revealProgress, pinnedProgress, flightAt, INTRO_MS } from './motion.js';
import { loadManifest, PENDING_LABEL } from './manifest.js';
import { buildProofPoints, factText, errorPanel } from './panels.js';
import { createField } from './field.js';
import { mountReveals } from './reveal.js';

// The same three.js build the atlas viewer loads, so the browser cache
// shares it. web/tests/chrome.test.js pins the two URLs together.
const THREE_URL = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';

const root = document.documentElement;
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const compact = window.matchMedia('(max-width: 820px)').matches;
const introStart = performance.now();
const introRunning = root.dataset.intro !== 'seen' && !reduced;
try { sessionStorage.setItem('vivome-intro', 'seen'); } catch { /* private mode: the intro plays again */ }

const chapters = [...document.querySelectorAll('[data-chapter]')];
const reveals = mountReveals(document, reduced);
const canvas = document.querySelector('.story-field');

let field = null;
let flight = 0;
let dirty = true;

window.addEventListener('scroll', () => { dirty = true; }, { passive: true });
window.addEventListener('resize', () => {
  dirty = true;
  field?.resize();
  if (reduced) drawStill();
});

function measure() {
  const vh = window.innerHeight;
  const rects = chapters.map((el) => el.getBoundingClientRect());
  flight = flightAt(rects.map((r) => r.top), rects.map((r) => r.height), vh);
  for (const { el, update } of reveals) {
    const r = el.getBoundingClientRect();
    update(el.hasAttribute('data-pin') ? pinnedProgress(r.top, r.height, vh) : revealProgress(r.top, r.height, vh));
  }
}

function frame(now) {
  if (dirty) {
    measure();
    dirty = false;
  }
  if (field) {
    const elapsed = now - introStart;
    field.render({ flight, time: now / 1000, introMs: introRunning && elapsed < INTRO_MS ? elapsed : null });
  }
  requestAnimationFrame(frame);
}

function drawStill() {
  measure();
  field?.render({ flight: 0, time: 0, introMs: null });
}

// Without WebGL the page falls back to the site's usual living background.
function fallBack(err) {
  console.warn('Landing field unavailable, using the plain background:', err);
  root.classList.add('no-field');
}

function loadThree() {
  if (window.THREE) return Promise.resolve(window.THREE);
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = THREE_URL;
    script.onload = () => resolve(window.THREE);
    script.onerror = () => reject(new Error('three.js failed to load'));
    document.head.append(script);
  });
}

const cellsLoaded = fetch('./data/story_cells.json').then((response) => {
  if (!response.ok) throw new Error(`story_cells.json: ${response.status} ${response.statusText}`);
  return response.json();
});

Promise.all([loadThree(), cellsLoaded]).then(([THREE, cells]) => {
  field = createField(THREE, canvas, cells, { compact });
  root.classList.add('has-field');
  if (reduced) drawStill();
}).catch(fallBack);

loadManifest().then((manifest) => {
  for (const el of document.querySelectorAll('[data-fact]')) el.innerHTML = factText(manifest, el.dataset.fact);
  document.getElementById('proof-points').innerHTML = buildProofPoints(manifest);
}).catch((err) => {
  for (const el of document.querySelectorAll('[data-fact]')) el.textContent = PENDING_LABEL;
  document.getElementById('proof-points').innerHTML = errorPanel(err);
});

if (!reduced) requestAnimationFrame(frame);
else measure();
