// The Manuscript page's figures (web/js/figures.js, web/figures/ from
// scripts/build_figures.py): each one fills its slot with its legend,
// sources and downloads; its numbers show as a table; every slot on the page
// has a figure and every figure a slot.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { buildFigure, buildFigureList, buildNumbersTable, mountFigures, parseCsv } from '../js/figures.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const PAGE = read('manuscript.html');
const INDEX_PATH = new URL('../figures/index.json', import.meta.url);
const index = existsSync(INDEX_PATH) ? JSON.parse(readFileSync(INDEX_PATH, 'utf8')) : { figures: [] };
const PAYLOAD = '<script>x</script>';

test('CSV fields may hold commas, quotes and line breaks', () => {
  assert.deepEqual(parseCsv('a,b\n1,"x, y"\n2,"he said ""hi"""\n3,"two\nlines"\n'), [
    ['a', 'b'], ['1', 'x, y'], ['2', 'he said "hi"'], ['3', 'two\nlines'],
  ]);
  assert.deepEqual(parseCsv('a,b\r\n1,2'), [['a', 'b'], ['1', '2']]);
  assert.deepEqual(parseCsv(''), []);
});

test('a figure shows its picture, title, legend, sources and downloads, escaped', () => {
  const html = buildFigure({
    name: 'fig9-x', title: 'Figure 9', width: 'double', alt: `Alt ${PAYLOAD}`, caption: `Caption ${PAYLOAD}`,
    sources: ['research/todo.md'], svg: 'figures/fig9-x.svg', csv: 'figures/fig9-x.csv',
  });
  assert.match(html, /^<figure class="ms-figure ms-figure-double" id="figure-fig9-x">/);
  assert.match(html, /<img src="figures\/fig9-x\.svg" alt="Alt &lt;script&gt;/);
  assert.match(html, /<strong>Figure 9\.<\/strong> Caption &lt;script&gt;/);
  assert.match(html, /<code>research\/todo\.md<\/code>/);
  assert.match(html, /href="figures\/fig9-x\.csv" download/);
  assert.match(html, /data-figure-numbers="figures\/fig9-x\.csv"/);
  assert.ok(!html.includes('<script>'));
});

test('the numbers drawn show as a table, escaped', () => {
  const html = buildNumbersTable(`panel,label,value\na,${PAYLOAD},1.5\nb,"x, y",2\n`);
  assert.equal((html.match(/<tr>/g) ?? []).length, 3);
  assert.match(html, /<th>panel<\/th><th>label<\/th><th>value<\/th>/);
  assert.match(html, /<td>x, y<\/td>/);
  assert.ok(!html.includes('<script>'));
  assert.match(buildFigureList([]), /No figures yet/);
});

test('every slot on the Manuscript page has a figure, and every figure a slot, with its files', () => {
  const slots = [...PAGE.matchAll(/<div class="ms-figure-slot" data-figure="([^"]+)"><\/div>/g)].map((m) => m[1]);
  assert.equal(new Set(slots).size, slots.length, 'one slot each');
  const names = index.figures.map((f) => f.name);
  assert.deepEqual([...names].sort(), [...slots].sort(), 'run python scripts/build_figures.py');
  for (const f of index.figures) {
    assert.ok(existsSync(new URL(`../${f.svg}`, import.meta.url)), f.svg);
    assert.ok(existsSync(new URL(`../${f.csv}`, import.meta.url)), f.csv);
    // The slot sits in the section the figure supports: the last heading or
    // section with an id before it is that one.
    const before = PAGE.slice(0, PAGE.indexOf(`data-figure="${f.name}"`));
    const headings = [...before.matchAll(/<(?:h2|h3|section)[^>]*\sid="([^"]+)"/g)];
    assert.equal(headings.at(-1)?.[1], f.section, `${f.name} sits in #${f.section}`);
  }
  assert.match(PAGE, /<div id="figure-list"><\/div>/);
  assert.match(PAGE, /import \{ mountFigures \} from '\.\/js\/figures\.js';/);
});

test('mounting fills each slot and the list, and loads a figure’s numbers when opened', async () => {
  const entry = {
    name: 'fig9-x', title: 'Figure 9', width: 'single', alt: 'Alt', caption: 'Caption', sources: [],
    svg: 'figures/fig9-x.svg', csv: 'figures/fig9-x.csv',
  };
  const slot = { innerHTML: '' };
  const list = { innerHTML: '' };
  const mount = { innerHTML: '', dataset: {} };
  const listeners = {};
  const details = {
    open: false, dataset: { figureNumbers: entry.csv }, querySelector: () => mount,
    addEventListener: (type, f) => { listeners[type] = f; },
  };
  const doc = {
    querySelectorAll: (sel) => (sel === '[data-figure="fig9-x"]' ? [slot] : sel === '[data-figure-numbers]' ? [details] : []),
    getElementById: (id) => (id === 'figure-list' ? list : null),
  };
  const fetched = [];
  const fetchImpl = async (url) => {
    fetched.push(url);
    if (url === 'figures/index.json') return { ok: true, json: async () => ({ figures: [entry] }) };
    return { ok: true, text: async () => 'panel,value\na,1\n' };
  };
  await mountFigures(doc, fetchImpl);
  assert.match(slot.innerHTML, /id="figure-fig9-x"/);
  assert.match(list.innerHTML, /href="#figure-fig9-x"/);
  details.open = true;
  await listeners.toggle();
  assert.match(mount.innerHTML, /<td>a<\/td><td>1<\/td>/);
  await listeners.toggle();
  assert.equal(fetched.filter((u) => u.endsWith('.csv')).length, 1, 'loaded once');
});
