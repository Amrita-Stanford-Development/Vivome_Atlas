import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  between, stagger, smooth, pinnedProgress, revealProgress,
  CHAPTERS, flightAt, formationState, INTRO_MS, introWeight,
} from '../js/motion.js';

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8');

test('between remaps and clamps', () => {
  assert.equal(between(0.5, 0.25, 0.75), 0.5);
  assert.equal(between(0, 0.25, 0.75), 0);
  assert.equal(between(1, 0.25, 0.75), 1);
  assert.equal(between(0.3, 0.5, 0.5), 0, 'an empty window is a step');
  assert.equal(between(0.5, 0.5, 0.5), 1);
});

test('smooth eases and keeps its ends', () => {
  assert.equal(smooth(0), 0);
  assert.equal(smooth(1), 1);
  assert.equal(smooth(0.5), 0.5);
  assert.ok(smooth(0.25) < 0.25);
});

test('stagger gives each sibling its own window, in order', () => {
  const n = 4;
  for (let i = 0; i < n; i++) {
    assert.equal(stagger(0, i, n), 0);
    assert.equal(stagger(1, i, n), 1);
  }
  const mid = [0, 1, 2, 3].map((i) => stagger(0.5, i, n));
  for (let i = 1; i < n; i++) assert.ok(mid[i - 1] >= mid[i], JSON.stringify(mid));
  assert.equal(stagger(0.4, 0, 1), 0.4, 'a single sibling follows p');
});

test('pinned progress runs across the pinned stretch and never divides by zero', () => {
  assert.equal(pinnedProgress(0, 3000, 1000), 0);
  assert.equal(pinnedProgress(-1000, 3000, 1000), 0.5);
  assert.equal(pinnedProgress(-2000, 3000, 1000), 1);
  assert.equal(pinnedProgress(400, 3000, 1000), 0);
  assert.equal(pinnedProgress(-10, 1000, 1000), 1);
});

test('reveal progress starts at 85% of the viewport and ends 70% through the section', () => {
  assert.equal(revealProgress(900, 1000, 1000), 0);
  assert.equal(revealProgress(850, 1000, 1000), 0);
  assert.equal(revealProgress(150, 1000, 1000), 1);
  assert.equal(revealProgress(500, 1000, 1000), 0.5);
});

test('flight counts chapters as the viewport middle passes through them', () => {
  const heights = [1000, 1000, 2000];
  const at = (scroll) => flightAt([0, 1000, 2000].map((t) => t - scroll), heights, 1000);
  assert.equal(at(0), 0.5, 'the landing is half passed when the page opens');
  assert.equal(at(500), 1);
  assert.equal(at(1000), 1.5);
  assert.equal(at(2500), 2.5);
  assert.equal(at(99999), 3, 'clamped at the end of the last chapter');
});

test('chapters with the same formation hold it; different ones return to water between', () => {
  const chapters = [
    { id: 'a', formation: null, x: 0 },
    { id: 'b', formation: 'cell', x: 1 },
    { id: 'c', formation: 'cell', x: -1 },
    { id: 'd', formation: 'plate', x: 1 },
  ];
  assert.equal(formationState(0.5, chapters).weight, 0, 'open water');
  assert.equal(formationState(1.0, chapters).weight, 0, 'the cell starts to gather');
  assert.equal(formationState(1.5, chapters).weight, 1);
  assert.equal(formationState(2.0, chapters).weight, 1, 'held across its two chapters');
  assert.equal(formationState(2.0, chapters).name, 'cell');
  assert.equal(formationState(2.99, chapters).weight < 0.01, true, 'dispersed before the plate');
  assert.equal(formationState(1.25, chapters).phase, 0.125);
  assert.equal(formationState(1.2, chapters).x, 1);
  assert.equal(formationState(1.99, chapters).x < -0.9, true, 'drifts to the next side within a span');
  assert.equal(formationState(3.4, chapters).name, 'plate');
  assert.equal(formationState(3.95, chapters).weight, 1, 'the last structure stays at the end of the story');
});

test('the landing page has one section per chapter, in order', () => {
  const html = read('../index.html');
  const ids = [...html.matchAll(/data-chapter="([^"]+)"/g)].map((m) => m[1]);
  assert.deepEqual(ids, CHAPTERS.map((c) => c.id));
});

test('the intro question forms, holds and is gone well before the intro ends', () => {
  assert.equal(introWeight(0), 0);
  assert.equal(introWeight(INTRO_MS * 0.35), 1);
  assert.equal(introWeight(INTRO_MS * 0.7), 0);
});

// The intro overlay is timed in CSS; the field times the particle question in JS.
test('the intro length is the same in motion.js and css/story.css', () => {
  const match = read('../css/story.css').match(/--intro-length:\s*(\d+)ms/);
  assert.ok(match, '--intro-length not found in web/css/story.css');
  assert.equal(Number(match[1]), INTRO_MS);
});
