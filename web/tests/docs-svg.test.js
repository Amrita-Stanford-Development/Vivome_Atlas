// The Docs section's data figures (web/js/docs-svg.js), drawn from the real
// web/data/docs.json: labelled for screen readers, Pending rather than NaN,
// the promise marked broken exactly where the data says so, and no number in
// their words that is not a record.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { FIGURES, docsText } from '../js/docs-data.js';
import { drawFigure, guaranteeSvg, corpusFunnelSvg, missingBandsSvg, oldRuleSvg } from '../js/docs-svg.js';

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

test('the figures type no number: every number in their words is a record', () => {
  for (const [name, keys] of Object.entries(FIGURES)) {
    const shown = keys.map((k) => docsText(docs, k)).sort((a, b) => b.length - a.length);
    for (const w of words(drawFigure(name, docs))) {
      let left = unescape(w);
      for (const s of shown) left = left.split(s).join(' ');
      left = left.replace(/\bS2\+S3\b|\bS[123]\b/g, ' ');
      assert.doesNotMatch(left, /\d/, `${name}: "${w}" holds a number that is not a record`);
    }
  }
});

test('the promise is marked broken exactly where the lower bound is above it', () => {
  const real = guaranteeSvg(docs);
  assert.equal((real.match(/promise broken/g) ?? []).length, 1);
  assert.equal((real.match(/promise holds/g) ?? []).length, 3);
  assert.match(real, /data-group="s1_log" data-broken="true"/);
  const changed = structuredClone(docs);
  changed.records.rl_b7_s23_log_lower.value = 0.06;
  assert.equal((guaranteeSvg(changed).match(/promise broken/g) ?? []).length, 2);
  changed.records.rl_b7_s1_log_lower.value = 0.05;   // equal to the promise is not above it
  assert.equal((guaranteeSvg(changed).match(/promise broken/g) ?? []).length, 1);
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
