// The Docs section (web/docs.html and one page per topic) against the real
// files: its data, how a record reads, and the tabs' addresses.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
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

// A <code> that is a path, a commit hash or an identifier: no spaces, at least
// one letter; or a short commit hash, whose seven hex digits can all be digits.
const CODE_NAME = /^(?:(?=\S*[A-Za-z_])[\w./#*-]+|[0-9a-f]{7})$/;

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
  /\bStage 0\b/g,                     // the service's first stage, by name
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
      for (const banned of BANNED) {
        const m = banned.exec(words);
        assert.equal(m, null, m && `${page}: "${words.slice(Math.max(0, m.index - 30), m.index + 30).replace(/\s+/g, ' ')}"`);
      }
    }
  }
});

test('the number guard catches a typed number in any form, and lets names through', () => {
  const caught = [
    '<p>22 of 237 tables</p>', '<p>six of the eleven tables</p>', '<p>at most 5% missed</p>',
    '<div aria-label="12 tables"></div>', '<svg role="img"><text x="1" y="2">n = 59</text></svg>',
    '<p><code>0.05</code></p>', '<p>the third group</p>', '<img alt="a figure of 4 groups" src="x.png">',
    '<p>&#53;0 tables</p>', '<p title="about 7">a table</p>', '<p>Three of them</p>',
    '<p><code>801602</code></p>', '<p><code>80160255</code></p>',
  ];
  for (const html of caught) assert.ok(typedNumbers(`<main>${html}</main>`).length > 0, html);
  const names = [
    '<p>On 2026-11-09, B7 tested S1 and S2+S3; R1 to R7 follow Step 1 and Phase A2.</p>',
    '<p>PXD064083, v4.1, protein-v2, revision 00009-hcz, log2 and log10, median-50, PBMC240, SCoPE2.</p>',
    '<p><code>valuescale/calibration/protein-v1.json</code> at <code>214fc58</code>, <code>rl_b7_s1_log_miss</code>.</p>',
    '<p>commits <code>8016025</code> and <code>B3_frame</code></p>',
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

// ---- the page script (web/js/docs.js) ----

test('each Docs page runs the Docs script last, after the water', () => {
  for (const page of DOCS_PAGES) {
    const scripts = [...read(page).matchAll(/<script type="module" src="([^"]+)"><\/script>/g)].map((m) => m[1]);
    assert.deepEqual(scripts, ['js/background.js', 'js/biofield.js', 'js/docs.js'], page);
  }
});

test('the script writes numbers and figures only through the guarded helpers, and a failed load shows the error and Pending', () => {
  const js = read('js/docs.js');
  assert.match(js, /import \{ PENDING_LABEL \} from '\.\/manifest\.js';/);
  assert.match(js, /import \{ errorPanel \} from '\.\/panels\.js';/);
  assert.match(js, /from '\.\/docs-data\.js';/);
  assert.match(js, /import \{ drawFigure \} from '\.\/docs-svg\.js';/);
  // Every markup the script writes is a record's escaped text, a figure, or the error panel.
  const writes = [...js.matchAll(/\.innerHTML = ([^;]+);/g)].map((m) => m[1].trim());
  assert.ok(writes.length >= 3);
  for (const w of writes) assert.match(w, /^(docsFact|drawFigure|errorPanel)\(/, `innerHTML = ${w}`);
  assert.match(js, /\.title = docsBasis\(docs, el\.dataset\.docs\)/);
  assert.match(js, /\.catch\(\(err\) => \{[\s\S]*?\$\('docs-error'\)\.innerHTML = errorPanel\(err\);[\s\S]*?textContent = PENDING_LABEL/);
});

test('the tabs follow the address without adding to the history, and show only once they work', () => {
  const js = read('js/docs.js');
  assert.match(js, /history\.replaceState\(null, '', `#\$\{/);
  assert.doesNotMatch(js, /location\.hash =/, 'setting the hash would add a history entry and jump');
  assert.match(js, /addEventListener\('hashchange'/);
  assert.match(js, /nextTab\(/);
  assert.match(js, /tabForHash\(/);
  // The list is shown, and the panel headings hidden, only after the wiring.
  const wired = js.indexOf("addEventListener('keydown'");
  assert.ok(wired > 0);
  assert.ok(js.indexOf('list.hidden = false') > wired);
  assert.ok(js.indexOf("classList.add('docs-tabbed')") > wired);
});

// ---- inside a topic page ----

// A panel's markup. Panels hold articles and folds, never a nested section,
// so a panel ends at the first </section>.
function panel(html, id) {
  const start = html.indexOf(`<section id="${id}" role="tabpanel"`);
  assert.ok(start >= 0, `no ${id} panel`);
  const body = html.slice(start, html.indexOf('</section>', start));
  assert.equal(body.indexOf('<section', 1), -1, `the ${id} panel holds a nested section`);
  return body;
}
const plainText = (markup) => decode(markup.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();

test('Words: each term once, in alphabetical order, each with its own address', () => {
  for (const page of TOPIC_PAGES) {
    const words = panel(read(page), 'words');
    assert.match(words, /<div class="glossary sheet">\s*<dl>/, page);
    const terms = [...words.matchAll(/<dt id="(words-[a-z0-9]+(?:-[a-z0-9]+)*)">([\s\S]*?)<\/dt>\s*<dd>/g)];
    assert.equal(terms.length, (words.match(/<dt\b/g) ?? []).length, `${page}: a term without an address or a definition`);
    assert.equal(terms.length, (words.match(/<dd>/g) ?? []).length, `${page}: a term with two definitions`);
    assert.ok(terms.length >= 30, `${page}: only ${terms.length} terms`);
    const key = (t) => plainText(t).toLowerCase().replace(/["“”]/g, '').replace(/^the /, '');
    assert.equal(new Set(terms.map(([, id]) => id)).size, terms.length, `${page}: an address used twice`);
    const keys = terms.map(([, , t]) => key(t));
    assert.equal(new Set(keys).size, keys.length, `${page}: a term defined twice`);
    assert.deepEqual(keys, [...keys].sort((a, b) => a.localeCompare(b, 'en')), `${page}: terms out of order`);
  }
});

test('every link inside a Docs page lands on something on that page', () => {
  for (const page of DOCS_PAGES) {
    const html = read(page);
    const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
    for (const [, target] of html.matchAll(/href="#([^"]*)"/g)) {
      assert.ok(ids.has(target), `${page}: #${target} leads nowhere`);
    }
  }
});

test('How it works: the side list links every chapter, in order, by its title', () => {
  const expected = {
    'docs-raw-or-log.html': ['how-problem', 'how-asking', 'how-reading', 'how-promise', 'how-tables', 'how-testing', 'how-found', 'how-next'],
  };
  for (const page of TOPIC_PAGES) {
    const how = panel(read(page), 'how');
    const toc = how.match(/<nav class="docs-toc glass" aria-label="Chapters">([\s\S]*?)<\/nav>/);
    assert.ok(toc, `${page}: no chapter list`);
    const links = [...toc[1].matchAll(/<a href="#([^"]+)">([\s\S]*?)<\/a>/g)].map((m) => [m[1], plainText(m[2])]);
    const chapters = [...how.matchAll(/<article id="([^"]+)" class="docs-chapter">\s*<h3>([\s\S]*?)<\/h3>/g)].map((m) => [m[1], plainText(m[2])]);
    assert.deepEqual(chapters.map(([id]) => id), expected[page], page);
    assert.deepEqual(links, chapters, `${page}: the side list and the chapters differ`);
    assert.equal((how.match(/<article\b/g) ?? []).length, chapters.length, `${page}: an article that is not a chapter`);
    for (const [id] of chapters) assert.deepEqual(tabForHash(`#${id}`), { tab: 'how', target: id, open: false });
  }
});

test('every figure is drawn from the data or marked an illustration; a data figure lists its numbers', () => {
  const used = new Set();
  for (const page of DOCS_PAGES) {
    for (const [fig] of read(page).matchAll(/<figure class="docs-fig">[\s\S]*?<\/figure>/g)) {
      const data = /data-docs-figure="/.test(fig);
      const drawn = /<span class="bead bead-open docs-illustration">Illustration<\/span>/.test(fig);
      assert.ok(data !== drawn, `${page}: a figure must be one or the other: ${fig.slice(0, 90)}`);
      assert.match(fig, /<figcaption>/, page);
      if (data) {
        assert.match(fig, /<details class="curious docs-numbers"><summary>The numbers<\/summary>/, page);
        for (const [, name] of fig.matchAll(/data-docs-figure="(\w+)"/g)) used.add(name);
      } else {
        assert.match(fig, /<svg class="docs-svg" viewBox="0 0 \d+ \d+" role="img" aria-label="[^"]+">/, page);
        assert.doesNotMatch(fig, /data-docs="/, `${page}: an illustration holds no data`);
      }
    }
    assert.equal((read(page).match(/<figure\b/g) ?? []).length, (read(page).match(/<figure class="docs-fig">/g) ?? []).length, page);
  }
  assert.deepEqual([...used].sort(), Object.keys(FIGURES).sort(), 'every data figure is shown somewhere');
});

const PARTS = ['What we did', 'Why', 'What we expected', 'What we found', 'What you decided', "Where it's kept"];

test('What we did: one entry per step, in order, each with its parts, its own dates and its files', () => {
  const did = panel(read('docs-raw-or-log.html'), 'did');
  const steps = [...did.matchAll(/<details id="did-([a-z0-9]+(?:-[a-z0-9]+)*)" class="docs-step">([\s\S]*?)<\/details>/g)];
  assert.deepEqual(steps.map(([, id]) => id.replace(/-/g, '_')), Object.keys(docs.steps));
  assert.equal((did.match(/<details\b/g) ?? []).length, steps.length + (did.match(/<details class="curious/g) ?? []).length);
  for (const [, id, body] of steps) {
    const step = docs.steps[id.replace(/-/g, '_')];
    const summary = body.match(/^\s*<summary>([\s\S]*?)<\/summary>/);
    assert.ok(summary && /<time /.test(summary[1]), `${id}: no date in its summary`);
    for (const [, when, shown] of body.matchAll(/<time datetime="([^"]+)">([^<]+)<\/time>/g)) {
      assert.equal(when, shown, id);
      assert.ok(step.dates.includes(when), `${id}: ${when} is not one of its dates`);
    }
    const parts = [...body.matchAll(/<dt>([^<]+)<\/dt>\s*<dd( class="[^"]*")?>([\s\S]*?)<\/dd>/g)];
    assert.deepEqual(parts.map(([, name]) => decode(name)), PARTS, id);
    assert.equal(parts[4][2], ' class="docs-decided"', `${id}: what you decided is marked`);
    assert.equal(parts[5][2], ' class="docs-kept"', id);
    const kept = parts[5][3];
    const codes = [...kept.matchAll(/<code>([^<]+)<\/code>/g)].map((m) => m[1]);
    const rest = plainText(kept.replace(/<code>[^<]*<\/code>/g, ' '));
    assert.match(rest, /^(?:(?:commits?|and|to|,|;)\s*)*$/i, `${id}: only paths and commits where it is kept, not "${rest}"`);
    for (const path of [step.report, step.expectations, step.notes].filter(Boolean)) {
      assert.ok(codes.includes(path), `${id}: ${path} is not named where it is kept`);
    }
    for (const c of codes) {
      assert.ok(/^[0-9a-f]{7}$/.test(c) || existsSync(new URL(`../../${c}`, import.meta.url)), `${id}: ${c} is neither a file nor a commit`);
    }
  }
});

test('every record in the data is shown somewhere in the section', () => {
  const shown = new Set(Object.values(FIGURES).flat());
  for (const page of DOCS_PAGES) {
    for (const [, key] of read(page).matchAll(/data-docs="([^"]+)"/g)) shown.add(key);
  }
  const unused = Object.keys(docs.records).filter((key) => !shown.has(key));
  assert.deepEqual(unused, [], 'records no page shows');
});

// ---- the home ----

// The section's topics, in the order the home shows them. A written topic is
// web/docs-<id>.html; the others are cards that say they come next.
const TOPICS = [
  ['raw-or-log', 'Raw or log'],
  ['model', 'The cell model and its versions'],
  ['data', 'The data'],
  ['testing', 'Testing the model'],
  ['organs', 'Other organs'],
  ['service', 'The upload service'],
  ['website', 'The website'],
  ['how-we-work', 'How we work'],
];
const TIME = /<time datetime="([^"]+)">([^<]+)<\/time>/g;

function homeCards() {
  return [...read(HOME).matchAll(/<li class="docs-card[^"]*" id="topic-([a-z-]+)">([\s\S]*?)<\/li>/g)].map(([, id, body]) => ({
    id, body, title: plainText(body.match(/<h3>([\s\S]*?)<\/h3>/)?.[1] ?? ''),
  }));
}

function milestones() {
  const list = read(HOME).match(/<ol class="docs-timeline">([\s\S]*?)<\/ol>/);
  assert.ok(list, 'the home has no timeline');
  return [...list[1].matchAll(/<li class="docs-milestone" data-(step|source)="([^"]+)">([\s\S]*?)<\/li>/g)].map(([, kind, ref, body]) => ({
    kind, ref, body,
    dates: [...body.matchAll(TIME)],
    topic: plainText(body.match(/<span class="docs-milestone-topic">([\s\S]*?)<\/span>/)?.[1] ?? ''),
  }));
}

test('the home says how to read a topic: its tabs, in order', () => {
  const howto = read(HOME).match(/<dl class="docs-howto">([\s\S]*?)<\/dl>/);
  assert.ok(howto, 'the home does not say how to read a topic');
  const named = [...howto[1].matchAll(/<dt>([^<]+)<\/dt>/g)].map((m) => decode(m[1]));
  for (const page of TOPIC_PAGES) {
    const tabs = [...read(page).matchAll(/<button type="button" role="tab"[^>]*>([^<]+)<\/button>/g)].map((m) => decode(m[1]));
    assert.deepEqual(named, tabs, page);
  }
});

test('the home: one card per topic, in order; a written topic links to its page, the rest come next', () => {
  const cards = homeCards();
  assert.deepEqual(cards.map(({ id, title }) => [id, title]), TOPICS);
  for (const { id, body } of cards) {
    const page = `docs-${id}.html`;
    const links = [...body.matchAll(/<a href="([^"]+)"/g)].map((m) => m[1]);
    if (DOCS_PAGES.includes(page)) {
      assert.deepEqual(links, [page], `${id}: a written topic's card links to its page, once`);
      assert.doesNotMatch(body, /Coming next/, id);
    } else {
      assert.deepEqual(links, [], `${id}: a topic not yet written links nowhere`);
      assert.match(body, /<span class="bead bead-open">Coming next<\/span>/, `${id} does not say it comes next`);
      assert.ok(!existsSync(new URL(`../${page}`, import.meta.url)), `${page} exists, but its card says it comes next`);
    }
  }
  for (const page of TOPIC_PAGES) assert.ok(cards.some(({ id }) => `docs-${id}.html` === page), `${page} has no card on the home`);
});

test('the home: the timeline runs forward, and every milestone is in the records', () => {
  const todo = readFileSync(new URL('../../research/todo.md', import.meta.url), 'utf8');
  const titles = new Set(TOPICS.map(([, title]) => title));
  const all = milestones();
  assert.ok(all.length > 0);
  let last = '';
  for (const { kind, ref, body, dates, topic } of all) {
    assert.equal(dates.length, 1, `${ref}: a milestone has one date`);
    const [, when, shown] = dates[0];
    assert.equal(when, shown);
    assert.match(when, /^\d{4}-\d{2}-\d{2}$/);
    assert.ok(when >= last, `${when} comes before ${last}`);
    last = when;
    assert.ok(titles.has(topic), `${when}: "${topic}" is not a topic`);
    if (kind === 'step') {
      // docs.json's steps are Raw or log's; the milestone opens its entry.
      const step = docs.steps[ref];
      assert.ok(step, `${when}: no step ${ref}`);
      assert.ok(step.dates.includes(when), `${when} is not one of ${ref}'s dates`);
      assert.equal(topic, 'Raw or log', ref);
      assert.ok(body.includes(`href="docs-raw-or-log.html#did-${ref.replace(/_/g, '-')}"`), `${ref}: the milestone does not open its step`);
    } else if (ref === 'research/todo.md') {
      assert.match(todo, new RegExp(`^\\| ${when}(?: to [0-9-]+)? \\|`, 'm'), `${when}: no changelog row of that date`);
    } else {
      const source = new URL(`../../${ref}`, import.meta.url);
      assert.ok(existsSync(source), `${ref} does not exist`);
      assert.ok(readFileSync(source, 'utf8').includes(when), `${ref} does not hold ${when}`);
    }
  }
});

test('the home: each card is dated by the first and last of its milestones', () => {
  const all = milestones();
  for (const { title, body } of homeCards()) {
    const dates = all.filter((m) => m.topic === title).map((m) => m.dates[0][1]).sort();
    assert.ok(dates.length > 0, `${title}: no milestone on the timeline`);
    const span = dates[0] === dates.at(-1) ? [dates[0]] : [dates[0], dates.at(-1)];
    assert.deepEqual([...body.matchAll(TIME)].map((m) => m[1]), span, title);
  }
});

test('a link from one Docs page to another lands on that page, and on the part it names', () => {
  for (const page of DOCS_PAGES) {
    for (const [, target, part] of read(page).matchAll(/href="(docs[a-z-]*\.html)(?:#([^"]*))?"/g)) {
      assert.ok(DOCS_PAGES.includes(target), `${page}: ${target} is not a Docs page`);
      if (part) assert.ok(read(target).includes(` id="${part}"`), `${page}: ${target}#${part} leads nowhere`);
    }
  }
});
