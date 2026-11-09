// The Docs section (web/docs.html and one page per topic) against the real
// files: its data, how a record reads, and the tabs' addresses.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  DOCS_SCHEMA, FIGURES, TABS, docsBasis, docsFact, docsRecord, docsText, nextTab, tabForHash, validateDocs,
} from '../js/docs-data.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const docs = JSON.parse(read('data/docs.json'));
const PAYLOAD = '<script>alert(1)</script>';

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
