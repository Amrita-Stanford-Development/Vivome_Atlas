// The Atlas page's Explore tab: the counts, the RNA and protein switches,
// and one list of the reference's cell types (which is also the colour key;
// a click shows or hides a type). The view controls and the visitor's cells
// are view-controls.js. `onChange` hears every filter change. An organ's map
// brings its colours, names and families (web/js/atlas/organs.js): the list
// is then one block per family, and a family's name shows or hides it whole.

import { formatCount } from '../manifest.js';
import { escapeHtml } from '../panels.js';
import { CLASS_COLOURS, plainName } from '../workflow-data.js';

const $ = (id) => document.getElementById(id);

export function mountExploreTab({
  layer, order, counts, colours = CLASS_COLOURS, nameOf = plainName, families = null, onChange = () => {},
}) {
  $('rna-count').textContent = formatCount(counts.rna);
  $('class-count').textContent = formatCount(order.length);

  for (const which of ['rna']) {
    const toggle = $(`${which}-toggle`);
    toggle.addEventListener('click', () => {
      const on = toggle.getAttribute('aria-checked') !== 'true';
      toggle.setAttribute('aria-checked', String(on));
      toggle.classList.toggle('active', on);
      layer.setModality(which, on);
      onChange();
    });
  }

  // One row per type, with its colour and its cells in each modality.
  const list = $('cell-type-filters');
  const row = (c) => `
    <button type="button" class="filter-item" data-class="${c}" aria-pressed="true">
      <span class="color-indicator" style="background:${escapeHtml(colours[c])}"></span>
      <span class="filter-name">${escapeHtml(nameOf(order[c]))}</span>
      <span class="filter-count">${formatCount(counts.byClass[c])}${counts.protByClass[c] ? ` · ${formatCount(counts.protByClass[c])} protein` : ''}</span>
    </button>`;
  list.innerHTML = families
    ? families.map((f, k) => `
    <div class="filter-family">
      <button type="button" class="filter-family-head" data-family="${k}" aria-pressed="true">
        <span class="filter-name">${escapeHtml(f.label)}</span>
        <span class="filter-count">${formatCount(f.classes.reduce((s, c) => s + counts.byClass[c], 0))}</span>
      </button>${f.classes.map(row).join('')}
    </div>`).join('')
    : order.map((name, c) => row(c)).join('');
  const sync = () => {
    for (const item of list.querySelectorAll('.filter-item')) {
      const on = layer.classOn(Number(item.dataset.class));
      item.setAttribute('aria-pressed', String(on));
      item.classList.toggle('deselected', !on);
    }
    for (const head of list.querySelectorAll('.filter-family-head')) {
      const on = families[Number(head.dataset.family)].classes.some((c) => layer.classOn(c));
      head.setAttribute('aria-pressed', String(on));
      head.classList.toggle('deselected', !on);
    }
    onChange();
  };
  list.addEventListener('click', (e) => {
    const head = e.target.closest('.filter-family-head');
    if (head) {
      const family = families[Number(head.dataset.family)];
      const on = !family.classes.some((c) => layer.classOn(c));
      for (const c of family.classes) layer.setClassOn(c, on);
      sync();
      return;
    }
    const item = e.target.closest('.filter-item');
    if (!item) return;
    const c = Number(item.dataset.class);
    layer.setClassOn(c, !layer.classOn(c));
    sync();
  });
  $('types-all').addEventListener('click', () => { layer.setAllClasses(true); sync(); });
  $('types-none').addEventListener('click', () => { layer.setAllClasses(false); sync(); });
}
