// The maps of other organs' references (web/data/organs/index.json, written
// by scripts/export_atlas_coordinates.py --organ): which organ the address
// asks for, plain names for their types, the families each type belongs to,
// and colours that keep a family together. Pure: no DOM, so node --test
// covers it.
//
// Blood is the page's own reference (web/data/metadata_*_lat128.csv) and
// keeps CLASS_COLOURS; an organ map is shown without labelling, because each
// organ's reference missed its development gates (research/organ-references.md).

import { plainName } from '../workflow-data.js';

export const BLOOD = 'blood';

// The organ the address names (?organ=lung), or null for blood: an unknown
// name is blood too, so an old link never breaks the page.
export function organFrom(search, organs) {
  const id = new URLSearchParams(String(search ?? '')).get('organ');
  return (organs ?? []).find((o) => o.id === id) ?? null;
}

// The address of the page showing `id`, keeping the rest of `href`.
export function organHref(href, id) {
  const url = new URL(href);
  if (id === BLOOD) url.searchParams.delete('organ');
  else url.searchParams.set('organ', id);
  url.hash = '';
  return url.toString();
}

// Plain names for the organ types blood's list does not hold.
export const ORGAN_PLAIN_NAMES = {
  'adventitial cell': 'adventitial fibroblast',
  'alveolar type 2 fibroblast cell': 'alveolar fibroblast',
  'basal cell': 'basal cell (airway)',
  'best4+ intestinal epithelial cell, human': 'BEST4+ epithelial cell',
  'bronchial smooth muscle cell': 'airway smooth muscle cell',
  'capillary endothelial cell': 'capillary endothelial cell',
  'club cell': 'club cell (airway)',
  'colon endothelial cell': 'endothelial cell',
  'colon macrophage': 'macrophage',
  'endothelial cell': 'endothelial cell',
  'endothelial cell of artery': 'artery endothelial cell',
  'endothelial cell of lymphatic vessel': 'lymphatic endothelial cell',
  'enterocyte of epithelium of large intestine': 'enterocyte (absorbing cell)',
  'enteroendocrine cell': 'enteroendocrine (hormone) cell',
  'enteroglial cell': 'enteric glial cell',
  fibroblast: 'fibroblast',
  'gamma-delta t cell': 'gamma-delta T cell',
  'innate lymphoid cell': 'innate lymphoid cell',
  'intestinal crypt stem cell of colon': 'crypt stem cell',
  'large intestine goblet cell': 'goblet cell (mucus)',
  'lung ciliated cell': 'ciliated cell (airway)',
  'mast cell': 'mast cell',
  'myeloid leukocyte': 'other myeloid cell',
  'myofibroblast cell': 'myofibroblast',
  pericyte: 'pericyte',
  'respiratory goblet cell': 'goblet cell (airway)',
  'stromal cell': 'stromal cell',
  't cell': 'T cell (other)',
  'transit amplifying cell of colon': 'transit-amplifying cell',
  'tuft cell of colon': 'tuft cell',
  'type i pneumocyte': 'alveolar type 1 cell',
  'type ii pneumocyte': 'alveolar type 2 cell',
  'vascular associated smooth muscle cell': 'vascular smooth muscle cell',
  'vein endothelial cell': 'vein endothelial cell',
};

export const organPlainName = (name) => ORGAN_PLAIN_NAMES[name] ?? plainName(name);

const capital = (s) => String(s).charAt(0).toUpperCase() + String(s).slice(1);

// The families (the hierarchy's groups) in a stable order: by branch
// (lineage), then by name. Each holds its types' indices in class order.
export function familiesOf(order, hierarchy) {
  const byName = new Map();
  order.forEach((name, c) => {
    const h = hierarchy?.[name] ?? {};
    const key = h.group ?? name;
    if (!byName.has(key)) byName.set(key, { name: key, label: capital(key), lineage: h.lineage ?? '', classes: [] });
    byName.get(key).classes.push(c);
  });
  return [...byName.values()].sort((a, b) => a.lineage.localeCompare(b.lineage) || a.name.localeCompare(b.name));
}

// One hue per family, well apart on the wheel; a family's types are shades of
// its hue, so the families read as blocks of colour on the map.
export const FAMILY_HUES = [212, 28, 145, 340, 268, 48, 185, 310, 95, 5, 238, 165];

function hslHex(h, s, l) {
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return `#${[f(0), f(8), f(4)].map((x) => Math.round(x * 255).toString(16).padStart(2, '0')).join('')}`;
}

// A colour per type, in class order.
export function organPalette(order, hierarchy) {
  const colours = new Array(order.length);
  familiesOf(order, hierarchy).forEach((family, f) => {
    const hue = FAMILY_HUES[f % FAMILY_HUES.length];
    const k = family.classes.length;
    family.classes.forEach((c, j) => {
      const t = k === 1 ? 0.5 : j / (k - 1);
      colours[c] = hslHex(hue, 0.62 + 0.12 * (1 - t), 0.36 + 0.3 * t);
    });
  });
  return colours;
}

// The type, its family and its branch, in plain words.
export function organCellLines(organ, name) {
  const h = organ.hierarchy?.[name] ?? {};
  return [
    `${organ.name} reference cell: ${organPlainName(name)}`,
    `Family: ${h.group ?? 'none'}; branch: ${h.lineage ?? 'none'}`,
  ];
}
