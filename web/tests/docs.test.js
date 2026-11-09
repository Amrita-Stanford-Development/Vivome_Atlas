// The Docs section (web/docs.html and one page per topic) against the real
// files: its data, how a record reads, and the tabs' addresses.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import {
  DOCS_SCHEMA, FIGURES, TABS, docsBasis, docsFact, docsRecord, docsText, nextTab, tabForHash, validateDocs,
} from '../js/docs-data.js';
import { DOCS_PAGES } from './site-pages.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const docs = JSON.parse(read('data/docs.json'));
const PAYLOAD = '<script>alert(1)</script>';
const HOME = 'docs.html';
const TOPIC_PAGES = DOCS_PAGES.filter((page) => page !== HOME);
// Records left pending on purpose (scripts/test_build_docs.py pins the same set).
const PENDING = new Set(['rl_v2_test']);

// ---- the words a reader meets ----

const ENTITIES = {
  '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&nbsp;': ' ',
  '&middot;': '·', '&rarr;': '→', '&larr;': '←', '&ndash;': '–', '&mdash;': '—', '&copy;': '©', '&hellip;': '…',
};
const decode = (s) => s.replace(/&(?:[a-z]+|#\d+|#x[0-9a-f]+);/gi, (e) => {
  if (e in ENTITIES) return ENTITIES[e];
  if (/^&#x/i.test(e)) return String.fromCodePoint(parseInt(e.slice(3, -1), 16));
  if (e.startsWith('&#')) return String.fromCodePoint(Number(e.slice(2, -1)));
  return e;
});

// A <code> that is a path, a commit hash or an identifier: no spaces, at least one letter.
const CODE_NAME = /^(?=\S*[A-Za-z_])[\w./#*-]+$/;

// The page's title and description, then inside <main> its text, with the
// labels of its parts (aria-label, title, alt), as a reader or a screen
// reader meets them. With names: false, a <code> that is a path, hash or
// identifier is left out (the number guard allows those).
function readerWords(html, { names = true } = {}) {
  const head = [html.match(/<title>([^<]*)<\/title>/)?.[1] ?? '', html.match(/<meta name="description" content="([^"]*)"/)?.[1] ?? ''];
  const main = (html.match(/<main\b[\s\S]*<\/main>/) ?? [html])[0]
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<(script|style)\b[\s\S]*?<\/\1>/g, ' ');
  const labels = [...main.matchAll(/\s(?:aria-label|title|alt)="([^"]*)"/g)].map((m) => m[1]);
  const text = main
    .replace(/<code>([^<]*)<\/code>/g, (whole, inner) => (!names && CODE_NAME.test(decode(inner)) ? ' ' : ` ${inner} `))
    .replace(/<[^>]*>/g, ' ');
  return [...head, ...labels, text].map(decode);
}

// Names that hold a digit but are not a number: dates, step and group
// labels, accessions, versions, the service's revisions, and a few names.
const ALLOWED = [
  /(?<!\d)20\d\d-\d\d-\d\d(?!\d)/g,   // a date
  /\b(?:PXD|MSV)\d+\b/g,              // an accession
  /\bS2\+S3\b/g, /\bS[1-3]\b/g,       // the size groups
  /\bB[0-7]\b/g, /\bR[1-7]\b/g,       // the steps of protein v1 and protein v2
  /\bStep 1\b/g, /\bA2\b/g,           // the bank, and Phase A2
  /\bv\d+(?:\.\d+)*\b/g,              // a version: v4.1, protein-v2
  /\b\d{5}-[a-z]{3}\b/g,              // a service revision, such as 00009-hcz
  /\blog(?:2|10)\b/g, /\bmedian-50\b/g, /\bPBMC240\b/g, /\bSCoPE2\b/g,
];
const NUMBER = new RegExp(String.raw`\d|\b(?:three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|`
  + String.raw`fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|`
  + String.raw`hundreds?|thousands?|millions?|dozens?|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)\b`, 'gi');

// Every number a reader could take for a measurement, typed into the page.
function typedNumbers(html) {
  const found = [];
  for (const words of readerWords(html, { names: false })) {
    let left = words;
    for (const pattern of ALLOWED) left = left.replace(pattern, ' ');
    for (const m of left.matchAll(NUMBER)) {
      found.push(left.slice(Math.max(0, m.index - 30), m.index + 30).replace(/\s+/g, ' ').trim());
    }
  }
  return found;
}
const BANNED = [/—/, /calibrated/i, /\bdeployed\b/i, /\bhosted\b/i, /\bbeats\b/i, /state of the art/i, /99%/, /every ome/i];

test('the committed docs data is valid, and a file of another schema or missing a part is refused', () => {
  assert.equal(validateDocs(docs), docs);
  assert.equal(docs.schema_version, DOCS_SCHEMA);
  assert.throws(() => validateDocs({ ...docs, schema_version: '0' }), /schema_version/);
  for (const key of ['built_for', 'sources', 'records', 'steps']) {
    const { [key]: _, ...without } = docs;
    assert.throws(() => validateDocs(without), new RegExp(key));
  }
  assert.throws(() => validateDocs(null), /not an object/);
});

test('records read in their format, and a pending or missing one reads Pending', () => {
  const at = (value, format) => ({ records: { k: { value, status: 'measured', basis: 'b', format } } });
  assert.equal(docsText(at(0.05, 'percent'), 'k'), '5%');
  assert.equal(docsText(at(0.124, 'pct1'), 'k'), '12.4%');
  assert.equal(docsText(at(18813, 'count'), 'k'), '18,813');
  assert.equal(docsText(at(0.063681, 'fixed3'), 'k'), '0.064');
  assert.equal(docsText(at(6.9903, 'integer'), 'k'), '7');
  assert.equal(docsText(docs, 'rl_b3_reserve'), '8,813');
  assert.equal(docsText(docs, 'rl_alpha'), '5%');
  assert.equal(docsText(docs, 'rl_v2_test'), 'Pending');
  assert.equal(docsText(docs, 'no_such_record'), 'Pending');
  assert.match(docsFact(docs, 'rl_v2_test'), /<span class="pending">Pending<\/span>/);
  assert.equal(docsRecord(docs, 'rl_b7_s1_log_miss').value, 22);
  assert.match(docsBasis(docs, 'rl_b7_s1_log_miss'), /results\.json/);
  assert.match(docsBasis(docs, 'rl_v2_test'), /R1 to R6/);
  assert.equal(docsBasis(docs, 'no_such_record'), 'no record');
});

test('a record shows escaped, even when the file is not to be trusted', () => {
  const hostile = { records: { k: { value: 1, status: 'measured', basis: PAYLOAD, format: PAYLOAD } } };
  assert.doesNotMatch(docsFact(hostile, 'k'), /<script/);
  const text = { records: { k: { value: PAYLOAD, status: 'measured', basis: 'b', format: 'count' } } };
  assert.doesNotMatch(docsFact(text, 'k'), /<script/);
});

test('every figure draws records that exist and are measured', () => {
  assert.ok(Object.keys(FIGURES).length >= 4);
  for (const [name, keys] of Object.entries(FIGURES)) {
    assert.ok(keys.length > 0, name);
    for (const key of keys) {
      const record = docsRecord(docs, key);
      assert.ok(record, `${name}: ${key} is not in docs.json`);
      assert.equal(record.status, 'measured', `${name}: ${key}`);
    }
  }
});

test('an address opens the right tab, and a step or term in it', () => {
  assert.deepEqual(TABS, ['how', 'did', 'words']);
  assert.deepEqual(tabForHash(''), { tab: 'how', target: null, open: false });
  assert.deepEqual(tabForHash('#'), { tab: 'how', target: null, open: false });
  assert.deepEqual(tabForHash('#how'), { tab: 'how', target: null, open: false });
  assert.deepEqual(tabForHash('#did'), { tab: 'did', target: null, open: false });
  assert.deepEqual(tabForHash('#words'), { tab: 'words', target: null, open: false });
  assert.deepEqual(tabForHash('#did-b7'), { tab: 'did', target: 'did-b7', open: true });
  assert.deepEqual(tabForHash('#how-promise'), { tab: 'how', target: 'how-promise', open: false });
  assert.deepEqual(tabForHash('#words-log'), { tab: 'words', target: 'words-log', open: false });
  for (const odd of ['#elsewhere', '#did-', '#did-<b>', '#DID-B7', '#how-a b', 'did-b7']) {
    assert.deepEqual(tabForHash(odd), { tab: 'how', target: null, open: false }, odd);
  }
});

test('the arrow keys move between tabs and wrap; Home and End go to the ends', () => {
  assert.equal(nextTab('how', 'ArrowRight'), 'did');
  assert.equal(nextTab('did', 'ArrowRight'), 'words');
  assert.equal(nextTab('words', 'ArrowRight'), 'how');
  assert.equal(nextTab('how', 'ArrowLeft'), 'words');
  assert.equal(nextTab('did', 'Home'), 'how');
  assert.equal(nextTab('how', 'End'), 'words');
  assert.equal(nextTab('how', 'Enter'), null);
  assert.equal(nextTab('nowhere', 'ArrowRight'), 'how');
});

// ---- the pages ----

test('the Docs pages are on the site page list, the home first, and none is left off', () => {
  assert.equal(DOCS_PAGES[0], HOME);
  assert.ok(TOPIC_PAGES.length >= 1);
  const files = readdirSync(new URL('../', import.meta.url)).filter((n) => /^docs(-[a-z-]+)?\.html$/.test(n)).sort();
  assert.deepEqual(files, [...DOCS_PAGES].sort(), 'a Docs page on disk is not in DOCS_PAGES, or one listed is missing');
  const css = read('css/page.css');
  assert.match(css, /\.site-nav a\[aria-current\] \{/, 'a topic page marks the Docs link with aria-current="true"');
  for (const part of ['.tabs', '.curious', '.glossary']) {
    assert.ok(css.includes(`${part} `), `page.css has no ${part} component`);
  }
});

test('each Docs page loads the shared styles and its own, and has exactly one h1', () => {
  for (const page of DOCS_PAGES) {
    const html = read(page);
    assert.match(html, /<link rel="stylesheet" href="css\/page\.css">\s*<link rel="stylesheet" href="css\/docs\.css">/, page);
    assert.equal((html.match(/<h1\b/g) ?? []).length, 1, page);
    assert.match(html, /<script>document\.documentElement\.classList\.add\('js'\);<\/script>/, page);
  }
  for (const page of TOPIC_PAGES) {
    assert.match(read(page), /<nav class="docs-crumb" aria-label="Breadcrumb"><a href="docs\.html">Docs<\/a><\/nav>/, `${page} links back to the Docs home`);
  }
});

test('the words follow the site copy rules, in code too', () => {
  for (const page of DOCS_PAGES) {
    for (const words of readerWords(read(page))) {
      for (const banned of BANNED) assert.doesNotMatch(words, banned, page);
    }
  }
});

test('the number guard catches a typed number in any form, and lets names through', () => {
  const caught = [
    '<p>22 of 237 tables</p>', '<p>six of the eleven tables</p>', '<p>at most 5% missed</p>',
    '<div aria-label="12 tables"></div>', '<svg role="img"><text x="1" y="2">n = 59</text></svg>',
    '<p><code>0.05</code></p>', '<p>the third group</p>', '<img alt="a figure of 4 groups" src="x.png">',
    '<p>&#53;0 tables</p>', '<p title="about 7">a table</p>', '<p>Three of them</p>',
  ];
  for (const html of caught) assert.ok(typedNumbers(`<main>${html}</main>`).length > 0, html);
  const names = [
    '<p>On 2026-11-09, B7 tested S1 and S2+S3; R1 to R7 follow Step 1 and Phase A2.</p>',
    '<p>PXD064083, v4.1, protein-v2, revision 00009-hcz, log2 and log10, median-50, PBMC240, SCoPE2.</p>',
    '<p><code>valuescale/calibration/protein-v1.json</code> at <code>214fc58</code>, <code>rl_b7_s1_log_miss</code>.</p>',
    '<p>Two gates, one answer, both kinds, often.</p><span data-docs="rl_alpha"></span>',
  ];
  for (const html of names) assert.deepEqual(typedNumbers(`<main>${html}</main>`), [], html);
  assert.ok(typedNumbers('<title>Step 9</title><main></main>').length > 0, 'the title is read too');
});

test('no Docs page types a number: every number on it is a record', () => {
  for (const page of DOCS_PAGES) {
    assert.deepEqual(typedNumbers(read(page)), [], `${page} types a number`);
  }
});

test('a topic page has the three tabs, wired to their panels, and shows every panel without JavaScript', () => {
  for (const page of TOPIC_PAGES) {
    const html = read(page);
    const list = html.match(/<div class="tabs" role="tablist" aria-label="[^"]+" hidden>([\s\S]*?)<\/div>/);
    assert.ok(list, `${page}: no tab list, hidden until the script wires it`);
    const tabs = [...list[1].matchAll(/<button type="button" role="tab" id="tab-(\w+)" aria-controls="(\w+)" aria-selected="(true|false)"( tabindex="-1")?>([^<]+)<\/button>/g)];
    assert.deepEqual(tabs.map((t) => t[1]), TABS, page);
    assert.deepEqual(tabs.map((t) => t[2]), TABS, page);
    assert.deepEqual(tabs.map((t) => t[5]), ['How it works', 'What we did', 'Words'], page);
    assert.deepEqual(tabs.map((t) => [t[3], Boolean(t[4])]), [['true', false], ['false', true], ['false', true]], page);
    const panels = [...html.matchAll(/<section id="(\w+)" role="tabpanel" aria-labelledby="tab-(\w+)"([^>]*)>/g)];
    assert.deepEqual(panels.map((p) => p[1]), TABS, page);
    assert.deepEqual(panels.map((p) => p[2]), TABS, page);
    for (const p of panels) assert.doesNotMatch(p[3], /\bhidden\b/, `${page}: the ${p[1]} panel is hidden in the markup`);
  }
});

test('every slot names a record and is empty in the markup; every figure is one the module draws', () => {
  for (const page of DOCS_PAGES) {
    const html = read(page);
    const all = [...html.matchAll(/data-docs="([^"]*)"/g)].map((m) => m[1]);
    const empty = [...html.matchAll(/<(span|strong)\b[^>]*\bdata-docs="([^"]*)"[^>]*><\/\1>/g)].map((m) => m[2]);
    assert.deepEqual(empty, all, `${page}: a slot holds text, or is not a span or strong`);
    for (const key of all) {
      const record = docsRecord(docs, key);
      assert.ok(record, `${page}: ${key} is not in docs.json`);
      assert.ok(record.status === 'measured' || PENDING.has(key), `${page}: ${key} is pending`);
    }
    const figures = [...html.matchAll(/data-docs-figure="([^"]*)"/g)].map((m) => m[1]);
    const mounts = [...html.matchAll(/<div class="docs-figure" data-docs-figure="(\w+)"><\/div>/g)].map((m) => m[1]);
    assert.deepEqual(mounts, figures, `${page}: a figure mount holds markup`);
    for (const name of figures) assert.ok(Object.hasOwn(FIGURES, name), `${page}: no figure named ${name}`);
  }
});
