// Browsing a file's cells one by one, grouped by the answer each was given:
// the groups (one type, a family, a branch, each reason for no answer, and
// the cells left off the map), the order the rows are shown in, and the
// list as HTML. Pure: no DOM, strings only, every value escaped (cell ids
// come from the visitor's file, labels from the service), so node --test
// covers it. Nothing here computes a number beyond counting and sorting the
// service's own values.
//
// `cells` is the page's run.cells (answers.js, responseToCells or
// traceToCells); a cell is named by its position in that array, which is
// also its `index`.

import { formatCount } from '../manifest.js';
import { escapeHtml } from '../panels.js';
import { ANSWERED, CLASS_COLOURS, OUTCOME_CHIPS, OUTCOME_ORDER, answerShort, plainName } from '../workflow-data.js';
import { lookGlyph } from './atlas-panels.js';
import { LOOK } from './upload-layer.js';

const e = escapeHtml;

export const SORTS = { confidence: 'Confidence', file: 'Order in the file', likeness: 'Likeness to the reference' };
const DEFAULT_SORT = 'confidence';
const sortName = (sort) => (Object.hasOwn(SORTS, sort) ? sort : DEFAULT_SORT);

const UNPLACED_NAME = 'Not placed on the map';
const KIND_RANK = { class: 0, group: 1, lineage: 2, none: 3, unplaced: 4 };
const SUFFIX = { group: 'a family', lineage: 'a branch' };

const listOf = (v) => (Array.isArray(v) ? v : []);
const known = (v) => v !== null && v !== undefined && v !== '';
const valueOf = (v) => (known(v) && Number.isFinite(Number(v)) ? Number(v) : null);
const normalQuery = (query) => String(query ?? '').trim().toLowerCase();
const matches = (cell, q) => !q || String(cell?.id ?? '').toLowerCase().includes(q);

// As answers.js's answerStyle decides it: the cell stays on the file's sheet.
const unplaced = (cell, placeable) => !placeable || !cell?.xyz || cell?.outcome === 'coverage_too_low';

function describe(cell, classOrder, placeable) {
  if (unplaced(cell, placeable)) {
    return { key: 'unplaced', kind: 'unplaced', outcome: null, name: UNPLACED_NAME, look: 'unplaced', colour: null };
  }
  const outcome = cell?.outcome;
  if (ANSWERED.has(outcome)) {
    const label = known(cell.label) ? String(cell.label) : '';
    let name = OUTCOME_CHIPS[outcome];
    if (label) name = outcome === 'class' ? String(plainName(label)) : `${label} (${SUFFIX[outcome]})`;
    const at = outcome === 'class' ? listOf(classOrder).indexOf(label) : -1;
    return { key: `${outcome}:${label}`, kind: outcome, outcome, name, look: outcome, colour: CLASS_COLOURS[at] ?? null };
  }
  const reason = known(outcome) ? String(outcome) : '';
  return {
    key: `none:${reason}`, kind: 'none', outcome: known(outcome) ? outcome : null,
    name: OUTCOME_CHIPS[reason] ?? (reason || 'No answer'), look: 'none', colour: null,
  };
}

const byName = (a, b) => a.name.localeCompare(b.name, 'en') || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0);
const reasonRank = (g) => {
  const at = OUTCOME_ORDER.indexOf(g.outcome);
  return at < 0 ? OUTCOME_ORDER.length : at;
};

function compareGroups(a, b) {
  const kind = KIND_RANK[a.kind] - KIND_RANK[b.kind];
  if (kind) return kind;
  if (a.kind === 'none') return (reasonRank(a) - reasonRank(b)) || byName(a, b);
  return (b.cells.length - a.cells.length) || byName(a, b);
}

// The cells grouped by their answer: [{ key, kind, outcome, name, look,
// colour, cells }], cells as positions in file order. One type's groups
// first (largest first, ties by name), then families, then branches (the
// same rule), then each reason for no answer in OUTCOME_ORDER, then the
// cells not placed on the map (`placeable` false, no place given, or too
// little measured).
export function answerGroups(cells, classOrder, { placeable = true } = {}) {
  const groups = new Map();
  listOf(cells).forEach((cell, i) => {
    const info = describe(cell, classOrder, placeable);
    if (!groups.has(info.key)) groups.set(info.key, { ...info, cells: [] });
    groups.get(info.key).cells.push(i);
  });
  return [...groups.values()].sort(compareGroups);
}

// High first; a missing value after every known one; ties by position.
const highFirst = (values) => (a, b) => {
  const va = values(a);
  const vb = values(b);
  if (va === null || vb === null) return ((va === null) - (vb === null)) || (a - b);
  return (vb - va) || (a - b);
};

// The cells in the order the list shows them: the groups in order, each
// sorted by `sort` (confidence or likeness: high first, missing last; file:
// the file's order; ties by position), keeping only cells whose name holds
// `query` (any case, trimmed; empty keeps every cell).
export function browseOrder(cells, groups, { sort = DEFAULT_SORT, query = '' } = {}) {
  const list = listOf(cells);
  const q = normalQuery(query);
  const how = sortName(sort);
  const field = how === 'likeness' ? 'similarity' : 'confidence';
  const compare = how === 'file' ? (a, b) => a - b : highFirst((i) => valueOf(list[i]?.[field]));
  return listOf(groups).flatMap((g) => listOf(g?.cells).filter((i) => i in list && matches(list[i], q)).sort(compare));
}

// ---- the list ----

const swatch = (colour) => (colour
  ? `<span class="browse-swatch" style="background:${e(colour)}" aria-hidden="true"></span>`
  : `<span class="browse-swatch is-hollow" style="background:transparent;box-shadow:inset 0 0 0 2px ${e(LOOK.colours.none)}" aria-hidden="true"></span>`);

const fillColour = (fill) => (Number.isInteger(fill) && fill >= 0 ? CLASS_COLOURS[fill] ?? null : null);

function row(cell, i, { fills, shown, selected }) {
  const on = typeof shown === 'function' ? shown(i) !== false : true;
  const current = selected === i;
  const confidence = valueOf(cell?.confidence);
  return `<button type="button" class="browse-row${on ? '' : ' is-off'}${current ? ' is-current' : ''}" data-cell="${e(i)}"`
    + `${current ? ' aria-current="true"' : ''}${on ? '' : ' title="Hidden by a filter"'}>`
    + swatch(fillColour(listOf(fills)[i]))
    + `<code class="browse-id">${e(cell?.id ?? '')}</code>`
    + `<span class="browse-answer">${e(answerShort(cell))}</span>`
    + `<span class="browse-conf">${confidence === null ? '' : e(confidence.toFixed(2))}</span>`
    + '</button>';
}

function groupHead(g, count) {
  const mark = g.kind === 'class' && g.colour ? swatch(g.colour) : lookGlyph(g.look, 14, 'atlas-glyph browse-glyph');
  return `<summary>${mark}<span class="browse-name">${e(g.name)}</span>`
    + `<span class="browse-count">${e(formatCount(count))}</span></summary>`;
}

const isOpen = (open, key) => (open instanceof Set ? open.has(key) : Array.isArray(open) && open.includes(key));

// The list part alone, so the page can redraw it while the search box keeps
// focus: one folding group per answer that has rows in `order`, each row a
// button naming the cell (data-cell, its position). `fills` are the class
// indices the map draws each cell in (answerStyle; -1: none), `open` the
// group keys shown open (every group with a match while searching),
// `shown(i)` false marks a row hidden by a filter, `selected` the cell
// whose card is open.
export function buildBrowseList(cells, groups, {
  order, fills = [], open = new Set(), shown = () => true, selected = null, query = '',
} = {}) {
  const list = listOf(cells);
  const q = normalQuery(query);
  const rowsOrder = Array.isArray(order) ? order : browseOrder(list, groups, { query });
  const groupAt = new Map();
  listOf(groups).forEach((g, k) => listOf(g?.cells).forEach((i) => groupAt.set(i, k)));
  const rows = listOf(groups).map(() => []);
  const seen = new Set();
  for (const i of rowsOrder) {
    if (seen.has(i) || !groupAt.has(i) || !(i in list)) continue;
    seen.add(i);
    rows[groupAt.get(i)].push(i);
  }
  const html = listOf(groups).map((g, k) => {
    if (!rows[k].length) return '';
    const unfolded = isOpen(open, g.key) || (q !== '' && rows[k].some((i) => matches(list[i], q)));
    return `<details class="fold browse-group" data-group="${e(g.key)}"${unfolded ? ' open' : ''}>`
      + groupHead(g, rows[k].length)
      + rows[k].map((i) => row(list[i], i, { fills, shown, selected })).join('')
      + '</details>';
  }).join('');
  if (html) return html;
  return q
    ? `<p class="panel-note">No cell is named like “${e(String(query).trim())}”.</p>`
    : '<p class="panel-note">No cells to show.</p>';
}

// The whole browser: a search box and a sort menu above the list.
export function buildCellBrowser(cells, groups, opts = {}) {
  const query = String(opts?.query ?? '');
  const sort = sortName(opts?.sort);
  const order = Array.isArray(opts?.order) ? opts.order : browseOrder(cells, groups, { sort, query });
  const options = Object.entries(SORTS)
    .map(([key, name]) => `<option value="${e(key)}"${key === sort ? ' selected' : ''}>${e(name)}</option>`).join('');
  return '<div class="cell-browser"><div class="browse-tools">'
    + '<input type="search" class="well" data-browse="query" placeholder="Find a cell by its name" '
    + `aria-label="Find a cell by its name" autocomplete="off" spellcheck="false" value="${e(query)}">`
    + `<select class="well" data-browse="sort" aria-label="Sort the cells">${options}</select>`
    + '</div><div class="browse-list" id="browse-list">'
    + buildBrowseList(cells, groups, { ...opts, order, query })
    + '</div></div>';
}
