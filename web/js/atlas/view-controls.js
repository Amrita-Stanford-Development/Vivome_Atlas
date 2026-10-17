// The Atlas page's view controls, in the Explore tab: the visitor's cells
// while an answer is on the map (a switch, and the answer filters the Your
// data card also has), names on the map, dimming the reference and the dot
// size. The landing (landing.js) does the drawing; this only asks it.

import { formatCount } from '../manifest.js';

const $ = (id) => document.getElementById(id);

// The states in which the visitor's cells are on the map.
export const CELLS_ON_MAP = new Set(['finishing', 'receipt', 'flying', 'settling', 'interactive']);

// The dimming slider's value (percent, in its steps of 5) for a dim of 0 to 1.
export const dimPercent = (dim) => String(Math.min(90, Math.max(0, Math.round((Number(dim) || 0) * 20) * 5)));

export function mountViewControls({ stage, layer, landing, labels }) {
  const setSwitch = (el, on) => {
    el.setAttribute('aria-checked', String(on));
    el.classList.toggle('active', on);
  };
  // Markup is written only when it changed, so a chip keeps its focus.
  const written = new Map();
  const setHtml = (el, html) => {
    if (written.get(el) === html) return;
    el.innerHTML = html;
    written.set(el, html);
  };

  $('cells-toggle').addEventListener('click', () => landing.setCellsShown(!landing.cellsShown));
  $('explore-chips').addEventListener('click', (e) => {
    const chip = e.target.closest('[data-outcome]');
    if (chip) landing.setOutcomeOn(chip.dataset.outcome, chip.getAttribute('aria-pressed') !== 'true');
  });

  $('names-toggle').addEventListener('click', () => {
    labels.setOn(!labels.on);
    setSwitch($('names-toggle'), labels.on);
  });

  // The dimming slider sets the dimming, and follows it when the landing
  // dims the reference for an answer (and lifts it again on Clear).
  const dim = $('dim-slider');
  const showDim = () => { $('dim-value').textContent = `${dim.value}%`; };
  dim.addEventListener('input', () => {
    layer.setDim(Number(dim.value) / 100);
    showDim();
  });

  const size = $('size-slider');
  size.addEventListener('input', () => {
    stage.setDotScale(Number(size.value) / 100);
    $('size-value').textContent = `${size.value}%`;
  });

  function update(st = landing.state, run = landing.run) {
    const shown = Boolean(run) && CELLS_ON_MAP.has(st.name);
    $('your-cells').hidden = !shown;
    if (shown) {
      setSwitch($('cells-toggle'), landing.cellsShown);
      $('your-cells-note').textContent = run.source === 'recorded'
        ? `The recorded example: ${formatCount(run.cells.length)} cells.`
        : `${formatCount(run.cells.length)} cells from ${st.file?.name ?? 'your file'}.`;
      setHtml($('explore-chips'), landing.chips());
    }
    const value = dimPercent(layer.dim);
    if (dim.value !== value && document.activeElement !== dim) {
      dim.value = value;
      showDim();
    }
  }
  landing.onChange((st, run) => update(st, run));
  update();
  return { update };
}
