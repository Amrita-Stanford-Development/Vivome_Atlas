import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { factText } from '../js/panels.js';
import { CHAPTERS } from '../js/timeline.js';
import {
  CLASS_COLOURS, OUTCOME_CHIPS, OUTCOME_LABELS, OUTCOME_NOTES, checkSync, decodeBits, formatRecord, geneLookup, recordAt, storyFor, validateWorkflow, wfFact,
} from '../js/workflow-data.js';
import {
  buildCellCard, buildGeneLookup, buildHeldoutCards, buildLadderTrace, buildPbmcTable, buildRawSnippet,
  buildResponseJson, buildServiceCard,
} from '../js/workflow-panels.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const html = read('workflow.html');
const workflow = JSON.parse(read('data/workflow.json'));
const manifest = JSON.parse(read('data/atlas_manifest.json'));
const main = html.match(/<main[\s\S]*<\/main>/)[0];
const visible = main.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
const PAYLOAD = '<script>alert(1)</script>';
// The one record the page shows as Pending on purpose: the training curves
// are not in this repository.
const PENDING_ON_PURPOSE = new Set(['training.history']);

test('the committed workflow data is valid and built for the committed manifest', () => {
  validateWorkflow(workflow);
  assert.deepEqual(checkSync(manifest, workflow), { ok: true, problems: [] });
  const stale = checkSync({ ...manifest, atlas_version: '0.0.1' }, workflow);
  assert.equal(stale.ok, false);
  assert.match(stale.problems[0], /0\.0\.1/);
  assert.throws(() => validateWorkflow({ ...workflow, schema_version: '9' }), /schema_version/);
});

test('every number slot on the page has a measured value in the real files', () => {
  const facts = [...html.matchAll(/data-fact="([^"]+)"/g)].map((m) => m[1]);
  const wfs = [...html.matchAll(/data-wf="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(facts.length >= 3 && wfs.length > 60);
  for (const key of facts) assert.ok(!/Pending/.test(factText(manifest, key)), `data-fact="${key}" reads Pending`);
  for (const key of wfs) {
    const text = wfFact(workflow, key);
    if (PENDING_ON_PURPOSE.has(key)) assert.match(text, /Pending/, key);
    else assert.ok(!/Pending/.test(text), `data-wf="${key}" reads Pending`);
  }
});

test('every result has a button label and a note in plain words', () => {
  for (const kind of Object.keys(OUTCOME_LABELS)) {
    assert.ok(OUTCOME_CHIPS[kind], kind);
    assert.ok(OUTCOME_NOTES[kind] && !OUTCOME_NOTES[kind].includes('\u2014'), kind);
  }
});

test('the page keeps the copy rules', () => {
  assert.ok(!main.includes('—'), 'no em dash');
  for (const word of [/calibrated/i, /beats scanvi/i, /state of the art/i, /99%/, /every ome/i, /\bdeployed\b/i, /\bhosted\b/i]) {
    assert.ok(!word.test(visible), `banned: ${word}`);
  }
  assert.equal((html.match(/<h1[\s>]/g) ?? []).length, 1, 'exactly one h1');
});

test('the chapters are the film’s, in order, each with its beats', () => {
  const sections = [...html.matchAll(/<section class="wf-chapter" id="([^"]+)" data-chapter="([^"]+)"[\s\S]*?<\/section>/g)];
  assert.deepEqual(sections.map((m) => m[2]), CHAPTERS.map((c) => c.id));
  sections.forEach((m, i) => {
    assert.equal(m[1], m[2], 'id and data-chapter agree');
    const beats = (m[0].match(/data-beat/g) ?? []).length;
    assert.equal(beats, CHAPTERS[i].beats, `${m[2]} has ${beats} beats`);
    assert.match(m[0], new RegExp(`data-scene="${m[2]}"`), `${m[2]} has its figure`);
    // The pinned stage holds the heading, every beat and the figure; the rest follows it.
    const pin = m[0].match(/<div class="wf-runway">\s*<div class="wf-pin">([\s\S]*?)<\/figure>/);
    assert.ok(pin, `${m[2]} has a runway and a pinned stage`);
    assert.equal((pin[1].match(/data-beat/g) ?? []).length, CHAPTERS[i].beats, `${m[2]}'s beats are pinned`);
    assert.match(pin[1], /<h2 /, `${m[2]}'s heading is pinned`);
    assert.ok(!/class="wf-more"|class="wf-lookup"|class="wf-service"/.test(pin[1]), `${m[2]} pins only its story`);
  });
});

test('records format by their kind, and pending ones read Pending', () => {
  assert.equal(formatRecord({ value: 0.27431, status: 'measured', format: 'percent' }), '27.4%');
  assert.equal(formatRecord({ value: 20055296, status: 'measured', format: 'count' }), '20,055,296');
  assert.equal(formatRecord({ value: 0.047277, status: 'measured', format: 'points' }), '+4.73');
  assert.equal(formatRecord({ value: 0.001, status: 'measured', format: 'plain' }), '0.001');
  assert.equal(formatRecord({ value: null, status: 'pending' }), 'Pending');
  assert.match(wfFact(workflow, 'no.such.key'), /class="pending"/);
  assert.equal(recordAt(workflow, 'training.recipe.epochs').value, 60);
});

test('every builder escapes data it is given', () => {
  const cell = { ...workflow.trace.cells[0], id: PAYLOAD, weak_label: PAYLOAD, label: PAYLOAD };
  const order = workflow.class_order.map(() => PAYLOAD);
  const detail = { ...workflow.trace.detail[0], id: PAYLOAD, response: { cell_id: PAYLOAD },
    raw_row: workflow.trace.detail[0].raw_row.map((r) => [PAYLOAD, r[1], r[2]]) };
  const outputs = [
    buildCellCard(cell, order),
    buildLadderTrace({ ...workflow.trace.cells.find((c) => c.outcome === 'lineage'), label: PAYLOAD }, workflow),
    buildRawSnippet({ path: PAYLOAD, orientation: PAYLOAD, values: '', header: [PAYLOAD], rows: [[PAYLOAD, 1]] }),
    buildGeneLookup(null, PAYLOAD),
    buildPbmcTable({ trace: { detail: [detail] } }),
    buildResponseJson(detail),
    buildServiceCard({ service: { ...workflow.service, url: PAYLOAD, platform: PAYLOAD } }, { status: PAYLOAD, model_version: PAYLOAD }),
    buildHeldoutCards({ evaluation: { heldout: [{ key: 'x', result: PAYLOAD, question: PAYLOAD, statistic: PAYLOAD, reason: PAYLOAD }] } }),
  ];
  for (const out of outputs) {
    assert.ok(!out.toLowerCase().includes('<script>'), out.slice(0, 120));
    assert.match(out, /&lt;script&gt;/i, out.slice(0, 120));
  }
});

test('the class colours are the atlas viewer’s palette, in the reference’s order', () => {
  const atlas = read('atlas.html').match(/this\.colorPalette = \[([\s\S]*?)\]/)[1];
  const palette = [...atlas.matchAll(/'(#[0-9a-f]{6})'/gi)].map((m) => m[1]);
  assert.deepEqual(CLASS_COLOURS, palette);
  assert.deepEqual([...workflow.class_order].sort(), workflow.class_order, 'sorted order, as the atlas assigns colours');
});

test('the live service’s address is the project page’s', () => {
  const url = read('project.html').match(/DEFAULT_SERVICE_URL = '([^']+)'/)[1];
  assert.equal(workflow.service.url, url);
});

test('the page computes no model output', () => {
  const modules = readdirSync(new URL('../js/', import.meta.url))
    .filter((f) => /^(workflow|scenes-|scene-kit|film|timeline)/.test(f));
  assert.ok(modules.length >= 9, modules.join(', '));
  for (const f of modules) {
    const src = read(`js/${f}`);
    assert.ok(!/Math\.exp\b/.test(src), `${f} calls Math.exp`);
    assert.ok(!/softmax\(/.test(src), `${f} computes a softmax`);
  }
});

test('genes and observed flags decode from their packed form', () => {
  const first = workflow.gene_space.genes[0];
  const hit = geneLookup(workflow, first.toLowerCase());
  assert.equal(hit.gene, first);
  assert.ok(hit.sources.length >= 1);
  assert.equal(geneLookup(workflow, 'NOT-A-GENE'), null);
  assert.deepEqual([...decodeBits(Buffer.from([0b10100000]).toString('base64'), 4)], [1, 0, 1, 0]);
  const align = workflow.raw.pbmc240.align;
  const matched = decodeBits(align.matched_bits, align.feature_space);
  assert.equal(matched.reduce((s, v) => s + v, 0), align.matched);
  const d = workflow.trace.detail[0];
  const observed = decodeBits(d.observed_bits, align.feature_space);
  assert.equal(observed.reduce((s, v) => s + v, 0), workflow.trace.cells[d.cell].observed);
});

test('a cell without its own detail borrows the story cell with its outcome', () => {
  const cells = workflow.trace.cells;
  const story = new Set(workflow.trace.story.cells);
  const other = cells.findIndex((c, i) => !story.has(i) && c.outcome === 'lineage');
  const d = storyFor(workflow, other);
  assert.equal(cells[d.cell].outcome, 'lineage');
  assert.equal(storyFor(workflow, workflow.trace.story.cells[0]).cell, workflow.trace.story.cells[0]);
});
