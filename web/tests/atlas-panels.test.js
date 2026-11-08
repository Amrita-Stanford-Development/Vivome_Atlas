// The Atlas page's "Your data" panels (web/js/atlas/atlas-panels.js): an
// uploaded cell's card, the receipt, the answer key, the outcome buttons and
// the recorded example's summary.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  buildAnswerKey, buildAtlasCellCard, buildExampleSummary, buildOutcomeChips, buildReceipt, scaleNote,
} from '../js/atlas/atlas-panels.js';
import { outcomeCounts, receiptFromResponse, receiptFromWorkflow, responseToCells, traceToCells } from '../js/atlas/answers.js';
import { escapeHtml } from '../js/panels.js';
import { OUTCOME_CHIPS, OUTCOME_ORDER, answerSentence, plainName } from '../js/workflow-data.js';

const workflow = JSON.parse(readFileSync(new URL('../data/workflow.json', import.meta.url), 'utf8'));
const order = workflow.class_order;
const cells = traceToCells(workflow);
const PAYLOAD = '<script>x</script>';
const clean = (html) => {
  assert.ok(!html.includes('undefined') && !html.includes('NaN'), html);
  assert.ok(!html.includes('—'), 'no em dash');
  for (const word of [/calibrated/i, /state of the art/i, /\bdeployed\b/i, /\bhosted\b/i]) assert.ok(!word.test(html), `${word}`);
  return html;
};
const firstOf = (outcome) => cells.find((c) => c.outcome === outcome);

test('a cell card says each kind of answer in plain words', () => {
  // The example has every outcome but "no type stands out"; that one is made from a cell with no answer.
  const kinds = OUTCOME_ORDER.map((k) => firstOf(k) ?? { ...firstOf('ambiguous_between_classes'), outcome: k });
  for (const cell of kinds) {
    const html = clean(buildAtlasCellCard(cell, order));
    assert.ok(html.includes(escapeHtml(answerSentence(cell))), `${cell.outcome}: ${html}`);
    assert.ok(html.includes(escapeHtml(cell.id)), 'the cell’s name in the file');
    assert.match(html, new RegExp(`Cell ${cell.index + 1}<`));
    if (Number.isFinite(cell.similarity)) assert.ok(html.includes(cell.similarity.toFixed(3)), 'likeness to 3 decimals');
    for (const k of cell.set) assert.ok(html.includes(escapeHtml(plainName(order[k]))), `set member ${order[k]}`);
    if (cell.guess !== null) assert.ok(html.includes(escapeHtml(plainName(order[cell.guess]))), 'best guess');
    const notPlaced = cell.outcome === 'coverage_too_low';
    assert.equal(html.includes('Not placed on the map'), notPlaced, `${cell.outcome}: the note`);
    assert.equal((html.match(/<svg/g) ?? []).length, 1, 'its look');
  }
  const low = clean(buildAtlasCellCard(firstOf('coverage_too_low'), order, { source: 'recorded' }));
  assert.match(low, /too little was measured/);
  assert.match(low, /stays in the file’s cloud/);
  assert.match(low, /No file was sent/);
});

test('a cell card for a service answer, placed or not', () => {
  const response = {
    cells: [
      { cell_id: 'a', coordinates: [0.1, 0.2, 0.3], observed_genes: 900, reference_similarity: 0.95123, label: 'T cell',
        label_level: 'group', label_set: ['cd4-positive, alpha-beta t cell', 'cd8-positive, alpha-beta t cell'], abstained: false,
        best_guess: { label: 'cd8-positive, alpha-beta t cell', probability: 0.5 } },
      { cell_id: 'b', observed_genes: 800, label: 'b cell', label_level: 'class', label_set: ['b cell'], abstained: false },
    ],
  };
  const [group, noPlace] = responseToCells(response, order);
  const html = clean(buildAtlasCellCard(group, order));
  assert.match(html, /a family, T cell/);
  assert.match(html, /CD8 T cell \(killer\) \(probability 50\.0%\)/);
  assert.match(html, /CD4 T cell \(helper\), CD8 T cell \(killer\)/);
  assert.match(html, /0\.951/);
  assert.match(html, /900/);
  assert.match(html, /From the service’s answer for your file/);
  assert.ok(!html.includes('Not placed'));
  const unplaced = clean(buildAtlasCellCard(noPlace, order));
  assert.match(unplaced, /Not placed on the map: the answer gave it no place, so it stays in your file’s cloud/);
  assert.match(unplaced, /none given/);
  assert.match(unplaced, /Pending/, 'no likeness given');
  assert.match(clean(buildAtlasCellCard(group, order, { placed: false })), /a different map/);
  assert.match(buildAtlasCellCard(null, order), /Pending/);
});

test('the panels escape ids, class names and model names', () => {
  const evilOrder = [...order];
  evilOrder[0] = PAYLOAD;
  const cell = { index: 0, id: PAYLOAD, outcome: 'class', label: PAYLOAD, set: [0], guess: 0, guess_probability: 0.9, similarity: 0.9, observed: 10, xyz: [0, 0, 0] };
  const outputs = [
    buildAtlasCellCard(cell, evilOrder),
    buildReceipt({ source: 'service', cells: 1, matched: 1, unmatched: 0, secondOpinion: 'used', model: PAYLOAD }),
    buildExampleSummary({ facts: workflow.facts, built_for: { model_name: PAYLOAD } }),
  ];
  for (const out of outputs) {
    assert.ok(!out.includes('<script>'), out);
    assert.match(out, /&lt;script&gt;x&lt;\/script&gt;/);
  }
});

test('the receipt shows the service’s numbers, and Pending for what is missing', () => {
  const recorded = clean(buildReceipt(receiptFromWorkflow(workflow)));
  assert.match(recorded, /Cells<\/dt><dd>238</);
  assert.match(recorded, /2,996 of 3,087/);
  assert.match(recorded, /Not used: too little of the file agreed with the learners \(36\.7%, at least 40% needed\)/);
  assert.match(recorded, /VivOME v4\.1/);
  assert.match(recorded, /Recorded from the served model: no file was sent\./);
  const live = clean(buildReceipt(receiptFromResponse({
    n_cells: 5, n_features_matched: 2996, model_version: 'v4.1',
    best_guess_rule: { correlation_term: 'used', agreement: 0.62, agreement_threshold: 0.4 },
  })));
  assert.match(live, /Used: enough of your file agreed with the learners \(62%, at least 40% needed\)/);
  assert.match(live, /Genes matched<\/dt><dd>2,996</, 'no total without the unmatched count');
  assert.ok(!live.includes('no file was sent'));
  for (const empty of [{}, null, undefined, receiptFromResponse({})]) {
    const html = clean(buildReceipt(empty));
    assert.equal((html.match(/Pending/g) ?? []).length, 5, html);
    assert.match(html, /<summary>Your file<\/summary>/, 'the folded line leaves out what is missing');
  }
});

test('the receipt says how the values were read', () => {
  assert.match(clean(buildReceipt(receiptFromWorkflow(workflow))), /Values<\/dt><dd>Linear intensities, log2-transformed</);
  const stated = { detected: 'log', transformed: true, stated: 'linear' };
  const live = clean(buildReceipt(receiptFromResponse({ n_cells: 5, value_scale: stated }, { scaleAsked: 'linear' })));
  assert.match(live, /Linear intensities, log2-transformed\. You chose this; on its own the service reads them as already on a log scale\./);
  assert.ok(!live.includes('did not take'));
});

test('the receipt warns when the service did not take the visitor’s reading', () => {
  const older = { detected: 'log', transformed: false };  // a service from before value_scale existed
  const html = clean(buildReceipt(receiptFromResponse({ n_cells: 5, value_scale: older }, { scaleAsked: 'linear' })));
  assert.match(html, /Already on a log scale\. This service did not take your choice \(Raw intensities\): it read the values on its own\./);
});

test('the receipt warns when the service did not take what the visitor said a 0 means', () => {
  const noZeros = { detected: 'log', transformed: false, stated: 'log' };
  const html = clean(buildReceipt(receiptFromResponse({ n_cells: 5, value_scale: noZeros }, { scaleAsked: 'log', zerosAsked: 'missing' })));
  assert.match(html, /This service did not take your choice \(Already log; a 0 is not measured\): it read the values on its own\./);
  const taken = { ...noZeros, zeros: 'missing' };
  const ok = clean(buildReceipt(receiptFromResponse({ n_cells: 5, value_scale: taken }, { scaleAsked: 'log', zerosAsked: 'missing' })));
  assert.match(ok, /Already on a log scale, each 0 read as not measured\. You chose this/);
  assert.ok(!ok.includes('did not take'));
});

test('the receipt says what the service’s check found', () => {
  const scale = { detected: 'linear', transformed: true, verdict: 'cant_tell', zeros_read: 'missing',
    evidence: { verdict: 'cant_tell', warning: 'unlike', reason: 'too few columns' } };
  const html = clean(buildReceipt(receiptFromResponse({ n_cells: 5, value_scale: scale })));
  assert.match(html, /Values<\/dt><dd>Linear intensities, log2-transformed\. The service&#39;s check could not tell raw from log, so it read them as raw\. Too few cells to tell\. The table is unlike the tables the check was built on: check the reading\.<\/dd>/);
});

test('scaleNote shows only for the service’s own unsure or unusual reading', () => {
  const UNSURE = 'The service could not tell whether your values are raw or log, and read them as raw. '
    + 'If they are already log, send the file again and choose Already log.';
  const UNUSUAL = "Your table is unlike the tables the service's check was built on, so check how its values were read.";
  const of = (scale) => scaleNote(receiptFromResponse({ n_cells: 5, value_scale: scale }));
  const raw = { detected: 'linear', transformed: true, zeros_read: 'missing' };
  const checked = (verdict, ev = {}, extra = {}) => ({ ...raw, verdict, evidence: { verdict, warning: null, reason: null, ...ev }, ...extra });

  assert.equal(of(checked('cant_tell', { reason: 'too few columns' })), UNSURE);
  assert.equal(of(checked('unlike_either', { reason: 'no spread' })), UNSURE);
  assert.equal(of(checked('cant_tell', { warning: 'unlike' })), UNSURE, 'unsure says more than the warning');
  assert.equal(of(checked('linear', { warning: 'unlike its design tables' })), UNUSUAL);
  assert.equal(of(checked('log', { warning: '<b>x</b>' }, { detected: 'log', transformed: false })), UNUSUAL, 'the warning is never echoed');

  assert.equal(of(checked('linear')), null, 'a sure reading, like its design tables');
  assert.equal(of(checked('log', {}, { detected: 'log', transformed: false })), null);
  assert.equal(of(checked('linear', { warning: '' })), null);
  assert.equal(of({ ...raw, verdict: 'linear' }), null, 'no evidence');
  assert.equal(of({ ...raw, verdict: 'linear', evidence: 'unlike' }), null);
  assert.equal(of({ detected: 'unknown', transformed: false, verdict: 'unknown', evidence: null }), null, 'no values');
  assert.equal(of({ detected: 'linear', transformed: true }), null, 'RNA, or a service older than the check');
  assert.equal(of({ detected: 'log', transformed: false, stated: 'log' }), null);
  assert.equal(of(checked('cant_tell', { warning: 'unlike' }, { stated: 'linear' })), null, 'the visitor chose the reading');
  assert.equal(of(checked('unlike_either', {}, { stated: 'log', transformed: false })), null);
  assert.equal(of(checked('<b>x</b>', { warning: 'unlike' })), null, 'a verdict the page does not know');
  assert.equal(scaleNote(receiptFromWorkflow(workflow)), null, 'the recorded example');
  for (const empty of [null, undefined, {}, receiptFromResponse({})]) assert.equal(scaleNote(empty), null);
});

test('the receipt folds to one line: whose file, how many cells, which model', () => {
  const r = receiptFromResponse({ n_cells: 216, n_features_matched: 2996, pipeline_version: 'v4.1', model_version: 'v4.1 (long name)' });
  const open = clean(buildReceipt(r));
  assert.match(open, /^<details class="fold atlas-receipt-card" open><summary>Your file · 216 cells · v4\.1<\/summary>/);
  const folded = clean(buildReceipt(r, { open: false }));
  assert.match(folded, /^<details class="fold atlas-receipt-card"><summary>/);
  assert.match(folded, /v4\.1 \(long name\)/, 'the full model name is inside');
  assert.match(clean(buildReceipt(receiptFromWorkflow(workflow), { open: false })), /<summary>The example · 238 cells · v4\.1<\/summary>/);
});

test('the outcome buttons cover every outcome, with counts and their state', () => {
  const counts = outcomeCounts(cells);
  const html = clean(buildOutcomeChips(counts, { lineage: false }));
  const buttons = [...html.matchAll(/<button[^>]*data-outcome="([^"]+)"[^>]*aria-pressed="(true|false)"/g)];
  assert.deepEqual(buttons.map((m) => m[1]), OUTCOME_ORDER);
  assert.deepEqual(buttons.filter((m) => m[2] === 'false').map((m) => m[1]), ['lineage']);
  for (const k of OUTCOME_ORDER) assert.ok(html.includes(escapeHtml(OUTCOME_CHIPS[k])), k);
  assert.match(html, /Narrowed to a branch<\/span><span class="atlas-chip-count">115</);
  assert.match(html, /No type stands out<\/span><span class="atlas-chip-count">0</);
  assert.equal((html.match(/<svg/g) ?? []).length, OUTCOME_ORDER.length);
  assert.match(clean(buildOutcomeChips(undefined)), /Pending/);
});

test('the answer key draws the five looks and says what the glow is', () => {
  const html = clean(buildAnswerKey());
  // Each look twice: small in the folded line, and beside what it means.
  assert.equal((html.match(/<svg/g) ?? []).length, 10);
  assert.match(html, /^<details class="fold atlas-key-card"><summary>/, 'folded unless asked');
  assert.match(clean(buildAnswerKey({ open: true })), /^<details class="fold atlas-key-card" open>/);
  for (const name of ['One type', 'A family', 'A branch', 'No answer', 'Not placed']) assert.ok(html.includes(name), name);
  assert.ok(html.includes('Glow: nearby reference cells of the type it was given, on this map.'));
  assert.match(html, /stroke-dasharray/, 'not placed: a broken ring');
  // Neutral colours only: no reserved colour stands in for a type.
  assert.ok(!/#c8641e|#2f8f6a/i.test(html));
});

test('the example summary names the file, its cells and the model, and that nothing is sent', () => {
  const html = clean(buildExampleSummary(workflow));
  assert.match(html, /PBMC240/);
  assert.match(html, /238 cells/);
  assert.match(html, /VivOME v4\.1/);
  assert.match(html, /no file is sent/);
  assert.ok((html.match(/\. /g) ?? []).length <= 2, 'two or three sentences');
  const missing = clean(buildExampleSummary({}));
  assert.equal((missing.match(/Pending/g) ?? []).length, 2);
});
