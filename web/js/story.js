// The landing (index.html): its numbers and its scroll reveals.
//
// - Numbers: every [data-fact] slot is filled from the manifest by factText,
//   the finale's proof points by buildProofPoints and the organs' grid by
//   buildOrganGrid (web/js/panels.js). A failed load shows Pending and an
//   error, never a stale number.
// - Each [data-in] block rises in once as it comes into view, and each
//   [data-count] number counts up to its manifest value.
// Under reduced motion nothing moves: every block is shown at once.

import { loadManifest, PENDING_LABEL } from './manifest.js';
import { buildOrganGrid, buildProofPoints, factText, errorPanel } from './panels.js';
import { countText } from './motion.js';

const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---- numbers ----

const facts = loadManifest().then((manifest) => {
  for (const el of document.querySelectorAll('[data-fact]')) el.innerHTML = factText(manifest, el.dataset.fact);
  document.getElementById('proof-points').innerHTML = buildProofPoints(manifest);
  document.getElementById('organ-grid').innerHTML = buildOrganGrid(manifest);
}).catch((err) => {
  for (const el of document.querySelectorAll('[data-fact]')) el.textContent = PENDING_LABEL;
  document.getElementById('organ-grid').textContent = PENDING_LABEL;
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
