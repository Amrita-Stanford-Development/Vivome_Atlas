// Browsing the projected cells one by one (web/js/atlas/cell-browser.js):
// the groups by answer, the order of the rows, the search, and the list's
// HTML. The recorded example (web/data/workflow.json) and small hand-made
// cells.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { SORTS, answerGroups, browseOrder, buildBrowseList, buildCellBrowser } from '../js/atlas/cell-browser.js';
import { STYLE, answerStyle, outcomeCounts, traceToCells } from '../js/atlas/answers.js';
import { escapeHtml } from '../js/panels.js';
import { ANSWERED, CLASS_COLOURS, OUTCOME_CHIPS, OUTCOME_ORDER, answerShort, plainName } from '../js/workflow-data.js';

const workflow = JSON.parse(readFileSync(new URL('../data/workflow.json', import.meta.url), 'utf8'));
const order = workflow.class_order;
const cells = traceToCells(workflow);
const PAYLOAD = '<script>x</script>';
const XYZ = [0, 0, 0];

const clean = (html) => {
  assert.ok(!html.includes('undefined') && !html.includes('NaN') && !html.includes('null'), html.slice(0, 200));
  assert.ok(!html.includes('—'), 'no em dash');
  for (const word of [/calibrated/i, /state of the art/i, /\bdeployed\b/i, /\bhosted\b/i]) assert.ok(!word.test(html), `${word}`);
  return html;
};
const cleanGroups = (groups) => {
  for (const g of groups) clean(`${g.key} ${g.name} ${g.look}`);
  return groups;
};

// A hand-made cell: position i, an outcome, a label, and the values the sorts read.
const make = (i, outcome, label = null, extra = {}) => ({
  index: i, id: `cell-${i}`, outcome, label, level: ANSWERED.has(outcome) ? outcome : null, set: [], guess: null,
  guess_probability: null, confidence: null, similarity: null, observed: null, xyz: XYZ, ...extra,
});
const fillsOf = (list, placeable = true) => list.map((c) => answerStyle(c, order, placeable).fill);
const buttons = (html) => [...html.matchAll(/<button [^>]*>/g)].map((m) => m[0]);
const buttonFor = (html, i) => buttons(html).find((b) => b.includes(`data-cell="${i}"`));
const groupTags = (html) => [...html.matchAll(/<details [^>]*>/g)].map((m) => m[0]);
const rowCells = (html) => [...html.matchAll(/data-cell="(\d+)"/g)].map((m) => Number(m[1]));

test('the example’s groups hold every cell once, as outcomeCounts counts them', () => {
  const groups = cleanGroups(answerGroups(cells, order));
  const all = groups.flatMap((g) => g.cells);
  assert.equal(all.length, cells.length, 'group sizes sum to the cells');
  assert.deepEqual([...all].sort((a, b) => a - b), cells.map((_, i) => i), 'every cell in exactly one group');
  const counts = outcomeCounts(cells);
  for (const outcome of OUTCOME_ORDER) {
    const inGroups = groups.flatMap((g) => g.cells).filter((i) => cells[i].outcome === outcome).length;
    assert.equal(inGroups, counts[outcome], outcome);
    const kind = ANSWERED.has(outcome) ? outcome : outcome === 'coverage_too_low' ? 'unplaced' : 'none';
    const ofKind = groups.filter((g) => g.kind === kind && (kind !== 'none' || g.outcome === outcome));
    assert.equal(ofKind.reduce((n, g) => n + g.cells.length, 0), counts[outcome], `${outcome}: its groups`);
  }
  for (const g of groups) {
    assert.deepEqual(g.cells, [...g.cells].sort((a, b) => a - b), `${g.key}: file order`);
    assert.ok(g.cells.length > 0, g.key);
    const first = cells[g.cells[0]];
    if (g.kind === 'unplaced') {
      assert.equal(g.key, 'unplaced');
      assert.equal(g.name, 'Not placed on the map');
      continue;
    }
    for (const i of g.cells) {
      assert.equal(cells[i].outcome, first.outcome, `${g.key}: one outcome`);
      assert.equal(cells[i].label, first.label, `${g.key}: one label`);
    }
    assert.equal(g.look, g.kind);
    if (ANSWERED.has(g.kind)) {
      assert.equal(g.key, `${g.kind}:${first.label}`);
      assert.equal(g.name, answerShort(first), `${g.key}: answerShort’s wording`);
    } else {
      assert.equal(g.key, `none:${first.outcome}`);
      assert.equal(g.name, OUTCOME_CHIPS[first.outcome]);
    }
    if (g.kind === 'class') {
      assert.equal(g.name, plainName(first.label));
      assert.equal(g.colour, CLASS_COLOURS[order.indexOf(first.label)]);
    } else {
      assert.equal(g.colour, null, g.key);
    }
  }
});

test('the example’s groups follow the order rule', () => {
  const groups = answerGroups(cells, order);
  const rank = { class: 0, group: 1, lineage: 2, none: 3, unplaced: 4 };
  for (let k = 1; k < groups.length; k += 1) {
    const [a, b] = [groups[k - 1], groups[k]];
    assert.ok(rank[a.kind] <= rank[b.kind], `${a.key} before ${b.key}`);
    if (a.kind !== b.kind) continue;
    if (a.kind === 'none') {
      assert.ok(OUTCOME_ORDER.indexOf(a.outcome) < OUTCOME_ORDER.indexOf(b.outcome), `${a.key} before ${b.key}`);
    } else {
      assert.ok(a.cells.length > b.cells.length || (a.cells.length === b.cells.length && a.name.localeCompare(b.name, 'en') < 0),
        `${a.key} (${a.cells.length}) before ${b.key} (${b.cells.length})`);
    }
  }
  assert.equal(groups.at(-1).key, 'unplaced', 'the example has one cell with too little measured');
});

test('hand-made groups: largest first, ties by name, then families, branches, no answers, unplaced', () => {
  const list = [
    make(0, 'outside_supported_region'),
    make(1, 'class', 'platelet'),
    make(2, 'group', 'T cell'),
    make(3, 'class', 'neutrophil'),
    make(4, 'lineage', 'myeloid'),
    make(5, 'class', 'platelet'),
    make(6, 'ambiguous_between_classes'),
    make(7, 'group', 'B cell'),
    make(8, 'class', 'b cell'),
    make(9, 'lineage', 'lymphoid'),
    make(10, 'coverage_too_low'),
    make(11, 'group', 'T cell'),
    make(12, 'lineage', 'lymphoid'),
    make(13, 'group', 'B cell'),
    make(14, 'no_confident_label'),
    make(15, 'class', 'platelet', { xyz: null }),
  ];
  const groups = cleanGroups(answerGroups(list, order));
  assert.deepEqual(groups.map((g) => g.key), [
    'class:platelet', 'class:b cell', 'class:neutrophil',
    'group:B cell', 'group:T cell',
    'lineage:lymphoid', 'lineage:myeloid',
    'none:ambiguous_between_classes', 'none:no_confident_label', 'none:outside_supported_region',
    'unplaced',
  ]);
  assert.deepEqual(groups.map((g) => g.name), [
    'platelet', 'B cell', 'neutrophil', 'B cell (a family)', 'T cell (a family)', 'lymphoid (a branch)', 'myeloid (a branch)',
    OUTCOME_CHIPS.ambiguous_between_classes, OUTCOME_CHIPS.no_confident_label, OUTCOME_CHIPS.outside_supported_region,
    'Not placed on the map',
  ]);
  assert.deepEqual(groups.map((g) => g.kind), ['class', 'class', 'class', 'group', 'group', 'lineage', 'lineage', 'none', 'none', 'none', 'unplaced']);
  assert.deepEqual(groups.map((g) => g.look), groups.map((g) => g.kind));
  assert.deepEqual(groups[0].cells, [1, 5]);
  assert.deepEqual(groups.at(-1).cells, [10, 15]);
  assert.equal(groups[1].colour, CLASS_COLOURS[order.indexOf('b cell')]);
  assert.equal(groups[0].colour, CLASS_COLOURS[order.indexOf('platelet')]);
  assert.deepEqual(groups.slice(3).map((g) => g.colour), Array(8).fill(null));
  assert.equal(groups[7].outcome, 'ambiguous_between_classes');
  assert.deepEqual(answerGroups([], order), []);
});

test('a cell is unplaced when the map is not this one, it has no place, or too little was measured', () => {
  const list = [make(0, 'class', 'b cell'), make(1, 'class', 'b cell', { xyz: null }), make(2, 'coverage_too_low'), make(3, 'group', 'T cell')];
  const groups = answerGroups(list, order);
  assert.deepEqual(groups.map((g) => [g.key, g.cells]), [['class:b cell', [0]], ['group:T cell', [3]], ['unplaced', [1, 2]]]);
  const off = answerGroups(list, order, { placeable: false });
  assert.equal(off.length, 1);
  assert.deepEqual(off[0], {
    key: 'unplaced', kind: 'unplaced', outcome: null, name: 'Not placed on the map', look: 'unplaced', colour: null, cells: [0, 1, 2, 3],
  });
  // The same rule as the map's (answerStyle), on the example too.
  for (const placeable of [true, false]) {
    for (const source of [list, cells]) {
      const unplaced = new Set(answerGroups(source, order, { placeable }).find((g) => g.kind === 'unplaced')?.cells ?? []);
      source.forEach((c, i) => assert.equal(unplaced.has(i), answerStyle(c, order, placeable).style === STYLE.unplaced, `${c.id}`));
    }
  }
});

test('each sort orders a group high first, missing values last, ties by position', () => {
  const values = [[0.5, 0.7], [null, 0.95], [0.9, null], [0.5, 0.95], [undefined, 0.1], [0.97, undefined]];
  const list = values.map(([confidence, similarity], i) => make(i, 'class', 'b cell', { confidence, similarity }));
  const groups = answerGroups(list, order);
  assert.deepEqual(browseOrder(list, groups, { sort: 'confidence' }), [5, 2, 0, 3, 1, 4]);
  assert.deepEqual(browseOrder(list, groups), [5, 2, 0, 3, 1, 4], 'confidence by default');
  assert.deepEqual(browseOrder(list, groups, { sort: 'likeness' }), [1, 3, 0, 4, 2, 5]);
  assert.deepEqual(browseOrder(list, groups, { sort: 'file' }), [0, 1, 2, 3, 4, 5]);
  assert.deepEqual(browseOrder(list, groups, { sort: 'nonsense' }), [5, 2, 0, 3, 1, 4], 'an unknown sort is confidence');
  assert.deepEqual(Object.keys(SORTS), ['confidence', 'file', 'likeness']);

  // Groups stay in their order; each is sorted inside.
  const mixed = [make(0, 'group', 'T cell', { confidence: 0.2 }), make(1, 'class', 'b cell', { confidence: 0.1 }),
    make(2, 'class', 'b cell', { confidence: 0.3 }), make(3, 'group', 'T cell', { confidence: 0.9 })];
  assert.deepEqual(browseOrder(mixed, answerGroups(mixed, order)), [2, 1, 3, 0]);
  assert.deepEqual(browseOrder(mixed, answerGroups(mixed, order), { sort: 'file' }), [1, 2, 0, 3]);
});

test('the example’s order for each sort', () => {
  const groups = answerGroups(cells, order);
  for (const [sort, field] of [['confidence', 'confidence'], ['likeness', 'similarity'], ['file', null]]) {
    const out = browseOrder(cells, groups, { sort });
    assert.deepEqual(out, groups.flatMap((g) => browseOrder(cells, [g], { sort })), `${sort}: groups in order`);
    assert.deepEqual([...out].sort((a, b) => a - b), cells.map((_, i) => i), `${sort}: every cell once`);
    let at = 0;
    for (const g of groups) {
      const part = out.slice(at, at + g.cells.length);
      at += g.cells.length;
      assert.deepEqual([...part].sort((a, b) => a - b), g.cells, `${sort}, ${g.key}: its own cells`);
      for (let k = 1; k < part.length; k += 1) {
        const [a, b] = [part[k - 1], part[k]];
        if (field === null) { assert.ok(a < b); continue; }
        const [va, vb] = [cells[a][field], cells[b][field]];
        if (va === null) assert.ok(vb === null && a < b, `${sort}, ${g.key}: missing last`);
        else if (vb !== null) assert.ok(va > vb || (va === vb && a < b), `${sort}, ${g.key}: ${va} then ${vb}`);
      }
    }
  }
});

test('the search keeps cells whose name holds the words, in any case, trimmed', () => {
  const list = [make(0, 'class', 'b cell', { id: 'Cell_A1' }), make(1, 'class', 'b cell', { id: 'cell_b2' }),
    make(2, 'group', 'T cell', { id: 'OTHER' }), make(3, 'group', 'T cell', { id: 'my CELL_c3' })];
  const groups = answerGroups(list, order);
  assert.deepEqual(browseOrder(list, groups, { sort: 'file', query: '  CELL_ ' }), [0, 1, 3]);
  assert.deepEqual(browseOrder(list, groups, { sort: 'file', query: 'other' }), [2]);
  assert.deepEqual(browseOrder(list, groups, { sort: 'file', query: '   ' }), [0, 1, 2, 3], 'empty keeps every cell');
  assert.deepEqual(browseOrder(list, groups, { sort: 'file', query: 'zzz' }), []);

  const q = 'sp_1';
  const expected = cells.map((c, i) => i).filter((i) => cells[i].id.toLowerCase().includes(q));
  const groupsEx = answerGroups(cells, order);
  const found = browseOrder(cells, groupsEx, { query: ` ${q.toUpperCase()} ` });
  assert.ok(expected.length > 0);
  assert.deepEqual([...found].sort((a, b) => a - b), expected);

  const none = clean(buildBrowseList(list, groups, { order: [], query: '  zzz ' }));
  assert.equal(none, '<p class="panel-note">No cell is named like “zzz”.</p>');
  const nothing = clean(buildBrowseList(list, groups, { order: [], query: '' }));
  assert.match(nothing, /^<p class="panel-note">/);
});

test('the list: one folding group per answer with rows, each row a button in the given order', () => {
  const list = [make(0, 'class', 'b cell', { confidence: 0.9564 }), make(1, 'class', 'b cell', { confidence: null }),
    make(2, 'group', 'T cell', { confidence: 0.5, guess: order.indexOf('cd8-positive, alpha-beta t cell') }),
    make(3, 'ambiguous_between_classes')];
  const groups = answerGroups(list, order);
  const fills = fillsOf(list);
  const html = clean(buildBrowseList(list, groups, { order: [1, 0, 3], fills }));
  assert.deepEqual(rowCells(html), [1, 0, 3], 'rows follow the order; a group with no rows is left out');
  assert.deepEqual(groupTags(html), [
    '<details class="fold browse-group" data-group="class:b cell">',
    '<details class="fold browse-group" data-group="none:ambiguous_between_classes">',
  ]);
  for (const b of buttons(html)) assert.match(b, /^<button type="button" class="browse-row" data-cell="\d+">$/);
  // The class group's head is a swatch in its colour; the others show their look.
  const [classPart, nonePart] = html.split('</details>');
  assert.match(classPart, new RegExp(`<summary><span class="browse-swatch" style="background:${CLASS_COLOURS[order.indexOf('b cell')]}"`));
  assert.match(classPart, /<span class="browse-name">B cell<\/span><span class="browse-count">2<\/span><\/summary>/);
  assert.match(nonePart, /<summary><svg class="atlas-glyph browse-glyph" width="14" height="14"/);
  assert.match(nonePart, new RegExp(`<span class="browse-name">${OUTCOME_CHIPS.ambiguous_between_classes}</span><span class="browse-count">1</span>`));
  // A row: its colour (or a hollow ring), its name, its answer, its confidence to 2 decimals.
  assert.ok(html.includes(`<span class="browse-swatch" style="background:${CLASS_COLOURS[fills[0]]}" aria-hidden="true"></span>`
    + '<code class="browse-id">cell-0</code><span class="browse-answer">B cell</span><span class="browse-conf">0.96</span></button>'));
  assert.ok(html.includes('<code class="browse-id">cell-1</code><span class="browse-answer">B cell</span><span class="browse-conf"></span>'));
  assert.equal(fills[3], -1);
  assert.match(html, /<span class="browse-swatch is-hollow" style="background:transparent;[^"]*"[^>]*><\/span><code class="browse-id">cell-3<\/code>/);
  assert.ok(html.includes(`<span class="browse-answer">${escapeHtml(answerShort(list[3]))}</span>`));

  const family = clean(buildBrowseList(list, groups, { order: [2], fills }));
  assert.ok(family.includes(`<span class="browse-answer">T cell (a family)</span>`));
  assert.ok(family.includes(`style="background:${CLASS_COLOURS[fills[2]]}"`), 'a family row takes the best guess’s colour');
  assert.match(family, /<summary><svg class="atlas-glyph browse-glyph" width="14" height="14"/);
});

test('rows hidden by a filter, the current cell, and open groups', () => {
  const groups = answerGroups(cells, order);
  const ord = browseOrder(cells, groups);
  const fills = fillsOf(cells);
  const html = clean(buildBrowseList(cells, groups, { order: ord, fills, shown: (i) => i !== 1, selected: 2, open: new Set([groups[1].key]) }));
  assert.deepEqual(rowCells(html), ord);
  const off = buttonFor(html, 1);
  assert.match(off, /class="browse-row is-off"/);
  assert.match(off, /title="Hidden by a filter"/);
  assert.ok(!off.includes('aria-current'));
  const current = buttonFor(html, 2);
  assert.match(current, /class="browse-row is-current"/);
  assert.match(current, /aria-current="true"/);
  assert.ok(!current.includes('title='));
  assert.equal(buttons(html).filter((b) => b.includes('is-off')).length, 1);
  assert.equal(buttons(html).filter((b) => b.includes('is-current') || b.includes('aria-current')).length, 1);
  const both = buttonFor(clean(buildBrowseList(cells, groups, { order: ord, fills, shown: () => false, selected: 4 })), 4);
  assert.match(both, /class="browse-row is-off is-current"/);

  const tags = groupTags(html);
  assert.equal(tags.length, groups.length);
  tags.forEach((t, k) => assert.equal(t.endsWith(' open>'), k === 1, t));
  const closed = groupTags(buildBrowseList(cells, groups, { order: ord }));
  assert.ok(closed.every((t) => !t.includes(' open')), 'folded unless asked');

  // While searching, every group with a match is open.
  const query = 'SP_1';
  const found = browseOrder(cells, groups, { query });
  const searched = clean(buildBrowseList(cells, groups, { order: found, query }));
  const withMatch = groups.filter((g) => g.cells.some((i) => found.includes(i))).map((g) => g.key);
  assert.ok(withMatch.length > 1 && withMatch.length < groups.length, withMatch.join(', '));
  assert.deepEqual(groupTags(searched), withMatch.map((key) => `<details class="fold browse-group" data-group="${escapeHtml(key)}" open>`));
});

test('cell names and labels from the file are escaped everywhere', () => {
  const list = [make(0, 'class', PAYLOAD, { id: PAYLOAD, confidence: 0.4 }), make(1, 'group', PAYLOAD, { id: `"${PAYLOAD}'` }),
    make(2, 'lineage', PAYLOAD), make(3, PAYLOAD, null, { id: '&amp;' })];
  const groups = answerGroups(list, order);
  const outs = [
    buildBrowseList(list, groups, { open: new Set(groups.map((g) => g.key)) }),
    buildBrowseList(list, groups, { query: PAYLOAD }),
    buildBrowseList(list, groups, { order: [], query: PAYLOAD }),
    buildCellBrowser(list, groups, { query: PAYLOAD }),
    buildCellBrowser(list, groups, { query: `"><img src=x onerror=alert(1)>` }),
  ];
  for (const out of outs) {
    clean(out);
    assert.ok(!out.includes('<script>'), out.slice(0, 200));
    assert.ok(!out.includes('<img'), out.slice(0, 200));
    assert.match(out, /&lt;script&gt;|&lt;img/);
  }
  assert.ok(outs[0].includes(`data-group="class:${escapeHtml(PAYLOAD)}"`));
  assert.ok(outs[0].includes(`<code class="browse-id">${escapeHtml(`"${PAYLOAD}'`)}</code>`));
  assert.ok(outs[0].includes('<code class="browse-id">&amp;amp;</code>'), 'escaped once more, not trusted');
  assert.ok(outs[2].includes(`No cell is named like “${escapeHtml(PAYLOAD)}”.`));
  assert.ok(outs[3].includes(`value="${escapeHtml(PAYLOAD)}"`));
  // An outcome the page does not know is still a group of its own, after the known ones.
  assert.deepEqual(groups.map((g) => g.kind), ['class', 'group', 'lineage', 'none']);
});

test('the whole browser: a search box, a sort menu, and the list', () => {
  const groups = answerGroups(cells, order);
  const fills = fillsOf(cells);
  for (const sort of Object.keys(SORTS)) {
    const html = clean(buildCellBrowser(cells, groups, { sort, query: '', fills, selected: 0 }));
    assert.match(html, /^<div class="cell-browser"><div class="browse-tools"><input type="search" class="well" data-browse="query" /);
    assert.match(html, /placeholder="Find a cell by its name" aria-label="Find a cell by its name"/);
    assert.match(html, /value=""><select class="well" data-browse="sort" aria-label="Sort the cells">/);
    const options = [...html.matchAll(/<option value="([^"]+)"( selected)?>([^<]+)<\/option>/g)];
    assert.deepEqual(options.map((m) => [m[1], m[3]]), Object.entries(SORTS));
    assert.deepEqual(options.filter((m) => m[2]).map((m) => m[1]), [sort], `${sort} is selected`);
    const list = buildBrowseList(cells, groups, { order: browseOrder(cells, groups, { sort }), fills, selected: 0 });
    assert.ok(html.endsWith(`</select></div><div class="browse-list" id="browse-list">${list}</div></div>`), sort);
  }
  const searched = clean(buildCellBrowser(cells, groups, { query: ' sp_1 ' }));
  assert.match(searched, /value=" sp_1 "/, 'the box keeps what was typed');
  assert.deepEqual(rowCells(searched), browseOrder(cells, groups, { query: 'sp_1' }));
  const fallback = clean(buildCellBrowser(cells, groups, { sort: 'nonsense' }));
  assert.match(fallback, /<option value="confidence" selected>/);
  const empty = clean(buildCellBrowser(cells, groups, { query: 'zzz' }));
  assert.ok(empty.includes('<p class="panel-note">No cell is named like “zzz”.</p></div></div>'));
});

test('no em dash in anything the browser says', () => {
  const groups = answerGroups(cells, order);
  const off = answerGroups(cells, order, { placeable: false });
  const strings = [
    ...Object.values(SORTS),
    ...[...groups, ...off].flatMap((g) => [g.key, g.name]),
    buildCellBrowser(cells, groups, { fills: fillsOf(cells), open: new Set(groups.map((g) => g.key)) }),
    buildCellBrowser(cells, off, { fills: fillsOf(cells, false), query: 'x' }),
    buildBrowseList(cells, groups, { order: [], query: 'nothing like it' }),
    buildBrowseList([], [], {}),
  ];
  for (const s of strings) clean(String(s));
});
