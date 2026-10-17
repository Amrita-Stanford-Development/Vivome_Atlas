// The Atlas page's Explore tab: the counts, the RNA and protein switches,
// and one list of the reference's cell types (which is also the colour key;
// a click shows or hides a type). The view controls and the visitor's cells
// are view-controls.js. `onChange` hears every filter change.

import { formatCount } from '../manifest.js';
import { escapeHtml } from '../panels.js';
import { CLASS_COLOURS, plainName } from '../workflow-data.js';

const $ = (id) => document.getElementById(id);

export function mountExploreTab({ layer, order, counts, onChange = () => {} }) {
  $('rna-count').textContent = formatCount(counts.rna);
  $('prot-count').textContent = formatCount(counts.prot);
  $('class-count').textContent = formatCount(order.length);

  for (const which of ['rna', 'prot']) {
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
  list.innerHTML = order.map((name, c) => `
    <button type="button" class="filter-item" data-class="${c}" aria-pressed="true">
      <span class="color-indicator" style="background:${CLASS_COLOURS[c]}"></span>
      <span class="filter-name">${escapeHtml(plainName(name))}</span>
      <span class="filter-count">${formatCount(counts.byClass[c])}${counts.protByClass[c] ? ` · ${formatCount(counts.protByClass[c])} protein` : ''}</span>
    </button>`).join('');
  const sync = () => {
    for (const item of list.querySelectorAll('.filter-item')) {
      const on = layer.classOn(Number(item.dataset.class));
      item.setAttribute('aria-pressed', String(on));
      item.classList.toggle('deselected', !on);
    }
    onChange();
  };
  list.addEventListener('click', (e) => {
    const item = e.target.closest('.filter-item');
    if (!item) return;
    const c = Number(item.dataset.class);
    layer.setClassOn(c, !layer.classOn(c));
    sync();
  });
  $('types-all').addEventListener('click', () => { layer.setAllClasses(true); sync(); });
  $('types-none').addEventListener('click', () => { layer.setAllClasses(false); sync(); });
}
