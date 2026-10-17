// What sits over the Atlas page's viewer: the loading screen, the error
// panel and the hover tooltip. Every value shown is escaped or set as text.

import { escapeHtml } from '../panels.js';

const $ = (id) => document.getElementById(id);

export function hideLoading() {
  const overlay = $('loading-overlay');
  overlay.classList.add('is-done');
  setTimeout(() => { overlay.hidden = true; }, 300);
}

export function showFailure(err) {
  const overlay = $('loading-overlay');
  overlay.hidden = false;
  overlay.classList.remove('is-done');
  overlay.innerHTML = `
    <div class="error-message">
      <h2>The atlas could not load</h2>
      <p>${escapeHtml(err?.message ?? String(err))}</p>
    </div>`;
}

// The tooltip: a few lines of text beside the pointer, inside the viewer.
export function createTooltip() {
  const el = $('tooltip');
  const box = el.parentElement;
  return {
    show(lines, clientX, clientY) {
      el.textContent = lines.join('\n');
      const rect = box.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;
      el.style.opacity = '1';
      // Flip to the left of the pointer near the right edge.
      const flip = x > rect.width - 220;
      el.style.left = `${flip ? x - 14 : x + 14}px`;
      el.style.top = `${y + 12}px`;
      el.style.transform = flip ? 'translateX(-100%)' : 'none';
    },
    hide() { el.style.opacity = '0'; },
  };
}
