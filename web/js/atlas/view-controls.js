// The Atlas page's view controls, in the Explore tab: the visitor's cells
// while an answer is on the map (a switch, the answer filters the Your data
// card also has, the types given, and whether a selected cell's types are
// highlighted), names on the map, dimming the reference and the dot size.
// The landing (landing.js) does the drawing; this only asks it.

import { formatCount } from '../manifest.js';
import { escapeHtml } from '../panels.js';
import { lookGlyph } from './atlas-panels.js';

const $ = (id) => document.getElementById(id);

// The types given, one row each: a click shows or hides those cells, Only
// shows them alone. `groups` is landing.groups(): { key, name, look, colour,
// count, on }. Pure, so node --test covers it.
export function buildTypesGiven(groups) {
  if (!groups.length) return '';
  return groups.map((g) => {
    const mark = g.colour
      ? `<span class="browse-swatch" style="background:${escapeHtml(g.colour)}"></span>`
      : lookGlyph(g.look, 14);
    return `<div class="given-row${g.on ? '' : ' is-off'}">`
      + `<button type="button" class="given-toggle" data-given="${escapeHtml(g.key)}" aria-pressed="${g.on}">`
      + `${mark}<span class="given-name">${escapeHtml(g.name)}</span><span class="given-count">${escapeHtml(formatCount(g.count))}</span></button>`
      + `<button type="button" class="text-button given-only" data-only="${escapeHtml(g.key)}" aria-label="Show only ${escapeHtml(g.name)}">Only</button>`
      + '</div>';
  }).join('');
}

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

  $('types-given').addEventListener('click', (e) => {
    const only = e.target.closest('[data-only]');
    if (only) return landing.showOnlyGroup(only.dataset.only);
    const row = e.target.closest('[data-given]');
    if (row) landing.setGroupOn(row.dataset.given, row.getAttribute('aria-pressed') !== 'true');
    return undefined;
  });
  $('given-all').addEventListener('click', () => landing.setAllGroups(true));
  $('given-none').addEventListener('click', () => landing.setAllGroups(false));
  $('highlight-toggle').addEventListener('click', () => landing.setHighlight(!landing.highlight));

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
      setHtml($('types-given'), buildTypesGiven(landing.groups()));
      setSwitch($('highlight-toggle'), landing.highlight);
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
