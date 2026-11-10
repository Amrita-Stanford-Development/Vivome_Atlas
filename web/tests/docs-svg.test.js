// The Docs section's data figures (web/js/docs-svg.js), drawn from the real
// web/data/docs.json: labelled for screen readers, Pending rather than NaN,
// the promise marked broken exactly where the data says so, and no number in
// their words that is not a record.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { FIGURES, FIGURE_SERIES, docsText } from '../js/docs-data.js';
import {
  drawFigure, guaranteeSvg, corpusFunnelSvg, missingBandsSvg, oldRuleSvg, exampleValuesSvg, exampleSpreadSvg,
  s1ScoresSvg, s1ScoresTestSvg,
} from '../js/docs-svg.js';

const docs = JSON.parse(readFileSync(new URL('../data/docs.json', import.meta.url), 'utf8'));
const pendingDocs = { records: Object.fromEntries(Object.keys(docs.records).map((k) => [k, { value: null, status: 'pending', note: 'n' }])) };
const words = (svg) => [
  ...[...svg.matchAll(/<text\b[^>]*>([^<]*)<\/text>/g)].map((m) => m[1]),
  ...[...svg.matchAll(/aria-label="([^"]*)"/g)].map((m) => m[1]),
];
const unescape = (s) => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");

test('every figure is an image with a label, drawn for each name the data module lists', () => {
  for (const name of Object.keys(FIGURES)) {
    const svg = drawFigure(name, docs);
    assert.match(svg, /^<svg class="docs-svg" viewBox="0 0 \d+ \d+" role="img" aria-label="[^"]+"/, name);
    assert.doesNotMatch(svg, /NaN|undefined|Infinity/, name);
  }
  assert.throws(() => drawFigure('no_such_figure', docs), /no_such_figure/);
});

test('a figure whose records are pending says Pending and draws nothing from them', () => {
  for (const name of Object.keys(FIGURES)) {
    const svg = drawFigure(name, pendingDocs);
    assert.match(svg, /Pending/, name);
    assert.doesNotMatch(svg, /NaN|undefined|Infinity/, name);
  }
});

// A series' axis labels, written by the builder from the data's range.
const tickLabels = (node) => (node && typeof node === 'object'
  ? [...(Array.isArray(node.ticks) ? node.ticks.map((t) => t.label) : []),
    ...Object.values(node).flatMap((v) => (v && typeof v === 'object' && !Array.isArray(v) ? tickLabels(v) : []))]
  : []);

test('the figures type no number: every number in their words is a record, or an axis label of their series', () => {
  for (const [name, keys] of Object.entries(FIGURES)) {
    const labels = FIGURE_SERIES[name] ? tickLabels(docs.series[FIGURE_SERIES[name]]) : [];
    const shown = [...keys.map((k) => docsText(docs, k)), ...labels].sort((a, b) => b.length - a.length);
    for (const w of words(drawFigure(name, docs))) {
      let left = unescape(w);
      for (const s of shown) left = left.split(s).join(' ');
      left = left.replace(/\bS2\+S3\b|\bS[123]\b|\blog(?:2|10)\b/g, ' ');
      assert.doesNotMatch(left, /\d/, `${name}: "${w}" holds a number that is not a record`);
    }
  }
});

// A test can contradict the promise; one that does not, has not proved it.
const contradicted = (svg) => (svg.match(/>contradicted<\/text>/g) ?? []).length;
const notContradicted = (svg) => (svg.match(/>not contradicted<\/text>/g) ?? []).length;

test('the promise is marked contradicted exactly where the lower bound is above it', () => {
  const real = guaranteeSvg(docs);
  assert.equal(contradicted(real), 1);
  assert.equal(notContradicted(real), 3);
  assert.doesNotMatch(words(real).join(' '), /holds|broken/, 'a test that does not contradict the promise has not shown it holds');
  assert.match(real, /data-group="s1_log" data-broken="true"/);
  const changed = structuredClone(docs);
  changed.records.rl_b7_s23_log_lower.value = 0.06;
  assert.equal(contradicted(guaranteeSvg(changed)), 2);
  changed.records.rl_b7_s1_log_lower.value = 0.05;   // equal to the promise is not above it
  assert.equal(contradicted(guaranteeSvg(changed)), 1);
  // The line sits at alpha on the same scale as the rates.
  const line = real.match(/<line class="docs-promise" x1="([\d.]+)"/);
  const rate = real.match(/data-group="s1_log"[^>]*data-x0="([\d.]+)" data-per-unit="([\d.]+)"/);
  assert.ok(line && rate);
  assert.ok(Math.abs(Number(line[1]) - (Number(rate[1]) + docs.records.rl_alpha.value * Number(rate[2]))) < 0.02);
});

test('the funnel never grows going down, and its splits add up to what they split', () => {
  const svg = corpusFunnelSvg(docs);
  const width = (id) => Number(svg.match(new RegExp(`data-bar="${id}" [^>]*width="([\\d.]+)"`))[1]);
  assert.ok(width('frame') >= width('listed'));
  assert.ok(Math.abs(width('listed') + width('reserve') - width('frame')) < 0.05);
  assert.ok(width('kept') >= width('after_audit'));
  assert.ok(Math.abs(width('calibration') + width('test') - width('after_audit')) < 0.05);
});

test('each band shows the share of tables under the threshold, calibration beside test', () => {
  const svg = missingBandsSvg(docs);
  const shares = [...svg.matchAll(/data-band="(\d)" data-split="(cal|test)" data-share="([\d.]+)"/g)];
  assert.equal(shares.length, docs.records.rl_ph_bands.value * 2);
  for (const [, i, split, share] of shares) {
    const below = docs.records[`rl_ph_band${i}_${split}_below`].value;
    const tables = docs.records[`rl_ph_band${i}_${split}_tables`].value;
    assert.ok(Math.abs(Number(share) - below / tables) < 1e-4, `band ${i} ${split}`);
  }
  assert.match(svg, /post hoc/);
});

test('the old rule figure shows each kind of table and how many it misread', () => {
  const svg = oldRuleSvg(docs);
  assert.match(svg, new RegExp(`${docsText(docs, 'rl_step1_linear_misread')} of ${docsText(docs, 'rl_step1_linear')}`));
  assert.match(svg, new RegExp(`${docsText(docs, 'rl_step1_log_misread')} of ${docsText(docs, 'rl_step1_log')}`));
});

test('the old rule figure draws every bank table once, filled exactly where the rule read it wrongly', () => {
  const svg = oldRuleSvg(docs);
  const dots = [...svg.matchAll(/data-table="([^"]+)" data-misread="(true|false)"/g)];
  assert.equal(dots.length, docs.records.rl_step1_tables.value);
  assert.equal(new Set(dots.map((d) => d[1])).size, dots.length, 'each table once');
  const filled = dots.filter((d) => d[2] === 'true').length;
  assert.equal(filled, docs.records.rl_step1_linear_misread.value + docs.records.rl_step1_log_misread.value);
  assert.match(unescape(svg), new RegExp(`the old rule's line: ${docsText(docs, 'rl_median_rule')}`));
});

test('the example table figure draws a bar for each step of each histogram', () => {
  const svg = exampleValuesSvg(docs);
  const bars = (svg.match(/<rect /g) ?? []).length;
  const ex = docs.series.example_values;
  assert.equal(bars, ex.raw.counts.length + ex.log2.counts.length);
  assert.match(svg, new RegExp(`and ${docsText(docs, 'rl_ex_beyond')} larger values`));
});

test('the spread figure climbs for raw values and stays near its start after a log', () => {
  const svg = exampleSpreadSvg(docs);
  const lines = [...svg.matchAll(/<polyline [^>]*points="([^"]+)"/g)].map((m) => m[1].split(' ').map((p) => Number(p.split(',')[1])));
  assert.equal(lines.length, 2);
  const [raw, log] = lines;
  for (let i = 1; i < raw.length; i += 1) assert.ok(raw[i] <= raw[i - 1], 'raw climbs (a smaller y is higher)');
  assert.ok(raw[0] - raw[raw.length - 1] > 60, 'and far');
  assert.ok(Math.max(...log) - Math.min(...log) < 20, 'log stays near level');
});

test('the score figures fill exactly the tables under the threshold, and the threshold is the k-th calibration score', () => {
  const k = docs.records.rl_s1_k.value;
  const cal = s1ScoresSvg(docs);
  const under = (svg, split) => (svg.match(new RegExp(`data-split="${split}" data-under="true"`, 'g')) ?? []).length;
  assert.equal(under(cal, 'calibration'), docs.records.rl_ph_cal_below.value);
  assert.equal(under(cal, 'test'), 0);
  const line = Number(cal.match(/class="docs-threshold" x1="[\d.]+" y1="([\d.]+)"/)[1]);
  const marks = [...cal.matchAll(/data-split="calibration" data-under="(?:true|false)" cx="[\d.]+" cy="([\d.]+)"/g)].map((m) => Number(m[1]));
  assert.ok(Math.abs(marks[k - 1] - line) < 0.02, 'score number k sits on the line');
  const both = s1ScoresTestSvg(docs);
  assert.equal(under(both, 'calibration'), docs.records.rl_ph_cal_below.value);
  assert.equal(under(both, 'test'), docs.records.rl_sc_test_below.value);
});
