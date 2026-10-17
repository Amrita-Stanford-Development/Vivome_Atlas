import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildBenchmarkTable, factText } from '../js/panels.js';
import {
  CAVEATS, checkSync, formatManuscript, msBasis, msFact, validateManuscript,
} from '../js/manuscript-data.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const html = read('manuscript.html');
const manuscript = JSON.parse(read('data/manuscript.json'));
const manifest = JSON.parse(read('data/atlas_manifest.json'));
const main = html.match(/<main[\s\S]*<\/main>/)[0];
const visible = main.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
// The records the page shows as Pending on purpose: work not done yet
// (scripts/test_build_manuscript.py pins the same set).
const PENDING_ON_PURPOSE = new Set(['open_sorted_test', 'open_khoury_committed', 'open_probe_v41', 'open_doi']);
const PAYLOAD = '<script>alert(1)</script>';

test('the committed manuscript data is valid and built for the committed manifest', () => {
  validateManuscript(manuscript);
  assert.deepEqual(checkSync(manifest, manuscript), { ok: true, problems: [] });
  const stale = checkSync({ ...manifest, atlas_version: '0.0.1' }, manuscript);
  assert.equal(stale.ok, false);
  assert.match(stale.problems[0], /0\.0\.1/);
  assert.throws(() => validateManuscript({ ...manuscript, schema_version: '9' }), /schema_version/);
});

test('every number slot on the page has a measured record, apart from the work not done yet', () => {
  const slots = [...html.matchAll(/data-ms="([^"]+)"/g)].map((m) => m[1]);
  const facts = [...html.matchAll(/data-fact="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(slots.length > 300 && facts.length >= 2);
  for (const key of slots) {
    assert.ok(key in manuscript.records, `data-ms="${key}" has no record`);
    const text = msFact(manuscript, key);
    if (PENDING_ON_PURPOSE.has(key)) assert.match(text, /Pending/, key);
    else assert.ok(!/Pending/.test(text), `data-ms="${key}" reads Pending`);
  }
  for (const key of facts) assert.ok(!/Pending/.test(factText(manifest, key)), `data-fact="${key}" reads Pending`);
  for (const key of PENDING_ON_PURPOSE) assert.ok(slots.includes(key), `${key} is not on the page`);
});

test('the page types no metric: every share and decimal is a slot', () => {
  // Protocol constants (a 95% interval, k = 30) are marked .constant; model
  // names such as v4.1 are names, not numbers.
  const text = main.replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<span class="constant">[^<]*<\/span>/g, ' ')
    .replace(/<code>[^<]*<\/code>/g, ' ')
    .replace(/<[^>]+>/g, ' ');
  assert.deepEqual(text.match(/\d+(?:\.\d+)?\s?%/g) ?? [], [], 'a typed percentage');
  assert.deepEqual(text.match(/(?<![\w.])\d+\.\d+/g) ?? [], [], 'a typed decimal');
});

test('the page keeps the copy rules', () => {
  assert.ok(!main.includes('—'), 'no em dash');
  for (const word of [/calibrated/i, /beats/i, /state of the art/i, /99%/, /every ome/i, /\bdeployed\b/i, /\bhosted\b/i]) {
    assert.ok(!word.test(visible), `banned: ${word}`);
  }
  assert.equal((html.match(/<h1[\s>]/g) ?? []).length, 1, 'exactly one h1');
});

test('every caveat tag is one of the vocabulary, named as it is', () => {
  const tags = [...html.matchAll(/<span class="bead[^"]*caveat" data-caveat="([^"]+)">([^<]+)<\/span>/g)];
  assert.ok(tags.length > 40);
  for (const [, key, text] of tags) {
    assert.ok(key in CAVEATS, `unknown caveat ${key}`);
    assert.equal(text, key);
  }
  // The legend explains each one.
  for (const key of Object.keys(CAVEATS)) assert.ok(html.includes(`data-caveat="${key}">${key}</span> `), `${key} has no legend line`);
});

test('the contents link to sections that exist', () => {
  const ids = new Set([...html.matchAll(/ id="([^"]+)"/g)].map((m) => m[1]));
  const links = [...html.matchAll(/class="ms-contents"[\s\S]*?<\/nav>/g)][0][0].matchAll(/href="#([^"]+)"/g);
  for (const [, id] of links) assert.ok(ids.has(id), `#${id} is missing`);
  assert.ok(ids.has('benchmark'), 'the benchmark anchor other pages link to');
});

test('records format by their kind, escape what they show, and pending ones read Pending', () => {
  assert.equal(formatManuscript({ value: 0.6905, status: 'measured', format: 'pct2' }), '69.05%');
  assert.equal(formatManuscript({ value: 0.8698, status: 'measured', format: 'pct1' }), '87.0%');
  assert.equal(formatManuscript({ value: -0.0975, status: 'measured', format: 'pp' }), '9.75');
  assert.equal(formatManuscript({ value: -0.003298, status: 'measured', format: 'points' }), '−0.33');
  assert.equal(formatManuscript({ value: 85233, status: 'measured', format: 'count' }), '85,233');
  assert.equal(formatManuscript({ value: null, status: 'pending' }), 'Pending');
  assert.match(msFact(manuscript, 'no_such_key'), /class="pending"/);
  const bad = { records: { x: { value: 1, status: 'measured', format: PAYLOAD } } };
  assert.ok(!msFact(bad, 'x').includes('<script>'));
  assert.match(msBasis(manuscript, 'fulcher_ba'), /development\.json/);
  assert.match(msBasis(manuscript, 'open_doi'), /DOI/);
});

test('the benchmark tables on this page show the current model only, without the role notes', () => {
  const current = manifest.benchmark.current;
  const page = buildBenchmarkTable(manifest, { currentOnly: true, roles: false, note: false });
  const ours = manifest.benchmark.datasets.flatMap((d) => d.rows.filter((r) => r.ours).map((r) => r.method));
  for (const method of new Set(ours)) {
    if (method.startsWith(current)) assert.ok(page.includes(method), method);
    else assert.ok(!page.includes(method), `${method} is shown`);
  }
  for (const d of manifest.benchmark.datasets) assert.ok(!page.includes(d.role), `${d.key}'s role note is shown`);
  // The default keeps every row and note, as before.
  const full = buildBenchmarkTable(manifest);
  for (const method of new Set(ours)) assert.ok(full.includes(method), method);
});
