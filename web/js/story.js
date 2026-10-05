// The landing (index.html): its numbers, its 3D hero and its scroll reveals.
//
// - Numbers: every [data-fact] slot is filled from the manifest by factText,
//   and the finale's proof points by buildProofPoints (web/js/panels.js).
//   A failed load shows Pending and an error, never a stale number.
// - The hero (web/js/hero.js) eases its objects in when the page opens, and
//   flies them out as the hero section scrolls away; it stops drawing once
//   they have gone or the hero is off screen.
// - Each [data-in] block rises in once as it comes into view, and each
//   [data-count] number counts up to its manifest value.
// Under reduced motion nothing moves: the hero is drawn once and every block
// is shown at once.

import { loadManifest, PENDING_LABEL } from './manifest.js';
import { buildProofPoints, factText, errorPanel } from './panels.js';
import { clamp01, countText } from './motion.js';
import { createHero } from './hero.js';

// The same three.js build the atlas viewer loads, so the browser cache
// shares it. web/tests/chrome.test.js pins the URLs together.
const THREE_URL = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';

const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const compact = window.matchMedia('(max-width: 820px)').matches;
const opened = performance.now();

// ---- numbers ----

const facts = loadManifest().then((manifest) => {
  for (const el of document.querySelectorAll('[data-fact]')) el.innerHTML = factText(manifest, el.dataset.fact);
  document.getElementById('proof-points').innerHTML = buildProofPoints(manifest);
}).catch((err) => {
  for (const el of document.querySelectorAll('[data-fact]')) el.textContent = PENDING_LABEL;
  document.getElementById('proof-points').innerHTML = errorPanel(err);
});

// A number counts up from zero to its final text, once, in about 1.4 s.
function countUp(el) {
  const final = el.textContent;
  if (countText(final, 0) === final) return;   // not a plain number
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / 1400);
    el.textContent = countText(final, t);
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ---- reveals ----

const blocks = [...document.querySelectorAll('[data-in]')];
if (reduced || !('IntersectionObserver' in window)) {
  for (const el of blocks) el.classList.add('is-in');
} else {
  const seen = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      const el = entry.target;
      el.classList.add('is-in');
      seen.unobserve(el);
      facts.then(() => el.querySelectorAll('[data-count]').forEach(countUp));
    }
  }, { threshold: 0.15 });
  for (const el of blocks) seen.observe(el);
}

// ---- the hero ----

// Another script (the living water) may already be loading three.js; wait for
// it rather than load it twice.
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

const heroSection = document.querySelector('.hero');
const heroCanvas = document.querySelector('.hero-canvas');

// How far the hero has scrolled away: 0 at the top, 1 once its sticky stage
// is about to leave.
function heroProgress() {
  const r = heroSection.getBoundingClientRect();
  return clamp01(-r.top / Math.max(r.height - window.innerHeight, 1));
}

loadThree().then((THREE) => {
  const hero = createHero(THREE, heroCanvas, { compact, reduced });
  window.addEventListener('resize', () => {
    hero.resize();
    if (reduced) hero.render(0, 0);
  });
  if (reduced) {
    hero.render(0, 0);
    return;
  }
  let visible = true;
  new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }).observe(heroSection);
  const frame = (now) => {
    const p = heroProgress();
    // Once the objects have flown out, or the hero is off screen, stop drawing.
    if (visible && p < 1) hero.render((now - opened) / 1000, p);
    heroCanvas.style.visibility = p < 1 ? 'visible' : 'hidden';
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}).catch((err) => {
  // Without WebGL the title panel stands alone; the page reads the same.
  console.warn('Landing hero unavailable:', err);
  heroCanvas.remove();
});
