// What the Atlas page draws for each uploaded cell (web/js/atlas/answers.js),
// from a service response and from the recorded example.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  COMPATIBLE_PIPELINES, STYLE, answerStyle, coordinatesCompatible, outcomeCode, outcomeCounts, receiptFromResponse,
  receiptFromWorkflow, responseToCells, traceToCells,
} from '../js/atlas/answers.js';
import { OUTCOME_ORDER } from '../js/workflow-data.js';

const workflow = JSON.parse(readFileSync(new URL('../data/workflow.json', import.meta.url), 'utf8'));
const order = workflow.class_order;

// A v4.1 response in the shape docs/service/projection-api.md gives.
const response = {
  atlas_version: '0.6.0', model_version: 'v4.1 (...)', pipeline_version: 'v4.1',
  n_cells: 5, n_features_matched: 2996, n_features_unmatched: 91,
  value_scale: { detected: 'linear', transformed: true },
  best_guess_rule: { rule: 'fusion', agreement: 0.37, agreement_threshold: 0.4, correlation_term: 'flat' },
  cells: [
    { cell_id: 'a', coordinates: [0.1, 0.2, 0.3], observed_genes: 900, reference_similarity: 0.95, label: 'b cell',
      label_level: 'class', label_set: ['b cell'], confidence: 0.97, abstained: false,
      best_guess: { label: 'b cell', probability: 0.9 } },
    { cell_id: 'b', coordinates: [0, 0, 0], observed_genes: 800, reference_similarity: 0.9, label: 'T cell',
      label_level: 'group', label_set: ['cd4-positive, alpha-beta t cell', 'cd8-positive, alpha-beta t cell'],
      confidence: 0.92, abstained: false, best_guess: { label: 'cd8-positive, alpha-beta t cell', probability: 0.5 } },
    { cell_id: 'c', coordinates: [0, 0, 0], observed_genes: 700, reference_similarity: 0.8, label: null,
      label_level: null, label_set: [], confidence: null, abstained: true, abstain_reason: 'ambiguous_between_classes',
      best_guess: { label: 'monocyte', probability: 0.4 } },
    { cell_id: 'd', coordinates: [0, 0, 0], observed_genes: 12, reference_similarity: 0.5, label: null,
      label_level: null, label_set: [], confidence: null, abstained: true, abstain_reason: 'coverage_too_low' },
    { cell_id: '<script>x</script>', coordinates: [0, 0, 0], observed_genes: 900, reference_similarity: 0.9,
      label: 'lymphoid', label_level: 'lineage', label_set: ['b cell', 'not a class'], confidence: 0.9,
      abstained: false, best_guess: { label: 'not a class', probability: 0.3 } },
  ],
};

test('a service response maps to one cell shape', () => {
  const cells = responseToCells(response, order);
  assert.equal(cells.length, 5);
  assert.deepEqual(cells.map((c) => c.outcome), ['class', 'group', 'ambiguous_between_classes', 'coverage_too_low', 'lineage']);
  assert.equal(cells[0].guess, order.indexOf('b cell'));
  assert.deepEqual(cells[1].set, [order.indexOf('cd4-positive, alpha-beta t cell'), order.indexOf('cd8-positive, alpha-beta t cell')]);
  assert.equal(cells[3].guess, null, 'no best guess when too little was measured');
  assert.equal(cells[4].guess, null, 'a name that is not a class is no guess');
  assert.deepEqual(cells[4].set, [order.indexOf('b cell')]);
  assert.equal(cells[4].id, '<script>x</script>', 'kept as data; builders escape it');
  assert.deepEqual(cells[0].xyz, [0.1, 0.2, 0.3]);
  assert.deepEqual(responseToCells({}, order), []);
  assert.equal(responseToCells({ cells: [{ coordinates: [1, 2] }] }, order)[0].xyz, null);
});

test('the recorded example keeps every outcome the trace counted', () => {
  const cells = traceToCells(workflow);
  assert.equal(cells.length, workflow.trace.cells.length);
  assert.deepEqual(outcomeCounts(cells), workflow.trace.outcomes);
  assert.ok(cells.every((c) => Array.isArray(c.xyz) && c.xyz.length === 3));
});

test('each answer has its look, and some cells stay on the sheet', () => {
  const cells = responseToCells(response, order);
  const styles = cells.map((c) => answerStyle(c, order));
  assert.deepEqual(styles.map((s) => s.style), [STYLE.class, STYLE.group, STYLE.none, STYLE.unplaced, STYLE.lineage]);
  assert.equal(styles[0].fill, order.indexOf('b cell'));
  assert.equal(styles[1].fill, order.indexOf('cd8-positive, alpha-beta t cell'), 'a family takes the best guess\'s colour');
  assert.equal(styles[2].fill, -1);
  assert.equal(styles[4].fill, order.indexOf('b cell'), 'without a best guess, the first type of its set');
  for (const s of cells.map((c) => answerStyle(c, order, false))) assert.equal(s.style, STYLE.unplaced);
  const counts = {};
  for (const c of traceToCells(workflow)) {
    const s = answerStyle(c, order).style;
    counts[s] = (counts[s] ?? 0) + 1;
  }
  assert.equal(counts[STYLE.class], workflow.trace.outcomes.class);
  assert.equal(counts[STYLE.unplaced], workflow.trace.outcomes.coverage_too_low);
});

test('only services that share this map place their cells', () => {
  assert.deepEqual(COMPATIBLE_PIPELINES, ['v3.1', 'v4', 'v4.1', 'v4.2']);
  for (const v of COMPATIBLE_PIPELINES) assert.ok(coordinatesCompatible(v));
  for (const v of ['v3', 'v5', 'v5.1', 'v5.2', undefined, null, '']) assert.ok(!coordinatesCompatible(v), String(v));
  assert.equal(coordinatesCompatible(workflow.built_for.pipeline_version), true, 'the recorded example is placeable');
});

test('outcomes are coded in the order the page lists them', () => {
  OUTCOME_ORDER.forEach((o, i) => assert.equal(outcomeCode(o), i));
});

test('the receipt holds the service\'s numbers, or the recorded example\'s', () => {
  const r = receiptFromResponse(response);
  assert.equal(r.cells, 5);
  assert.equal(r.matched, 2996);
  assert.equal(r.secondOpinion, 'flat');
  assert.equal(r.pipeline, 'v4.1');
  const w = receiptFromWorkflow(workflow);
  assert.equal(w.source, 'recorded');
  assert.equal(w.cells, workflow.facts.runs.value);
  assert.equal(w.matched, workflow.facts.matched.value);
  assert.equal(w.secondOpinion, workflow.trace.stages.fusion.correlation_term);
  assert.equal(w.model, workflow.built_for.model_name);
});
