// Text colours meet WCAG's 4.5:1 on every background the pages put text on
// (web/css/page.css's tokens); the RNA and protein hues have darker twins for
// text (--rna-ink, --prot-ink), and the bright ones stay for dots and strokes.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { PROT, PROT_INK, RNA, RNA_INK } from '../js/scene-kit.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const css = read('css/page.css');
const token = (name) => css.match(new RegExp(`--${name}:\\s*(#[0-9A-Fa-f]{6})`))?.[1];

function luminance(hex) {
  const [r, g, b] = hex.slice(1).match(/../g).map((h) => parseInt(h, 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

test('every text colour reads at 4.5:1 or better on every background', () => {
  const backgrounds = ['paper', 'bench', 'field', 'well'].map(token);
  for (const name of ['ink', 'ink-soft', 'ink-faint', 'accent', 'error', 'rna-ink', 'prot-ink']) {
    for (const bg of backgrounds) {
      assert.ok(contrast(token(name), bg) >= 4.5, `--${name} on ${bg}: ${contrast(token(name), bg).toFixed(2)}`);
    }
  }
});

test('form fields and switches show an edge at 3:1 or better (WCAG 1.4.11)', () => {
  const edge = token('edge');
  for (const bg of ['paper', 'bench', 'field', 'well'].map(token)) {
    assert.ok(contrast(edge, bg) >= 3, `--edge on ${bg}: ${contrast(edge, bg).toFixed(2)}`);
  }
  assert.match(css, /input\.well,\s*select\.well,\s*textarea\.well\s*\{[^}]*inset 0 0 0 1px var\(--edge\)/);
  const atlas = read('css/atlas.css');
  assert.match(atlas, /\.toggle-switch \{[^}]*inset 0 0 0 1px var\(--edge\)/, 'the switch track, off');
  assert.match(atlas, /\.organ-select \{[^}]*inset 0 0 0 1px var\(--edge\)/, 'the organ chooser');
});

test('a control that is off stays readable: its swatch fades, its words do not', () => {
  const atlas = read('css/atlas.css');
  const workflow = read('css/workflow.css');
  for (const [sheet, text, selector] of [
    [atlas, 'atlas.css', '.filter-item.deselected'],
    [atlas, 'atlas.css', '.filter-family-head.deselected'],
    [atlas, 'atlas.css', '.outcome-chips button[aria-pressed="false"]'],
    [workflow, 'workflow.css', '.wf-rung.wf-skipped'],
  ]) {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    for (const m of sheet.matchAll(new RegExp(`${escaped}(?::hover)?\\s*\\{([^}]*)\\}`, 'g'))) {
      assert.doesNotMatch(m[1], /opacity/, `${text}: ${selector} fades its words`);
    }
  }
  assert.match(atlas, /\.filter-item\.deselected \.color-indicator \{[^}]*opacity/);
  assert.match(atlas, /\.filter-item\.deselected \.filter-name \{[^}]*line-through/);
});

test('faint numbers are decoration, hidden from screen readers; organ chips to build are not faded', () => {
  const html = read('workflow.html');
  const numbers = [...html.matchAll(/<span class="wf-scene-num"[^>]*>/g)];
  assert.ok(numbers.length >= 4);
  for (const [tag] of numbers) assert.match(tag, /aria-hidden="true"/, tag);
  assert.doesNotMatch(read('css/story.css'), /\.organ-to-build \{[^}]*opacity/);
});

test('the canvas scenes use the same text colours as the pages', () => {
  assert.equal(RNA_INK, token('rna-ink'));
  assert.equal(PROT_INK, token('prot-ink'));
  assert.equal(RNA, token('rna'));
  assert.equal(PROT, token('prot'));
});

test('no text is drawn in the bright RNA or protein colours', () => {
  for (const page of ['index.html', 'atlas.html', 'manuscript.html', 'workflow.html', 'motion.html']) {
    const html = read(page);
    for (const m of html.matchAll(/<text\b[^>]*>/g)) {
      assert.doesNotMatch(m[0], new RegExp(`fill="(${RNA}|${PROT})"`, 'i'), `${page}: ${m[0].slice(0, 80)}`);
    }
  }
  for (const file of readdirSync(new URL('../js/', import.meta.url)).filter((f) => f.endsWith('.js'))) {
    const code = read(`js/${file}`);
    for (const m of code.matchAll(/\b(text|chip)\(g,(?:(?!\}\);)[\s\S])*?colour: (RNA|PROT)\b(?!_)/g)) {
      assert.fail(`${file}: ${m[0].slice(0, 90)}`);
    }
  }
  for (const sheet of ['workflow.css', 'atlas.css']) {
    assert.doesNotMatch(read(`css/${sheet}`), /\bcolor: var\(--(rna|prot)\)/, sheet);
  }
});
