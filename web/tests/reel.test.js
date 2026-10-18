// The Motion page (web/motion.html) and the film's storyboard
// (web/js/reel-frames.js): its timing, its numbers, its words, and the
// rendered stills (web/motion/frames/, from motion/scripts/stills.mjs).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { CAVEATS } from '../js/manuscript-data.js';
import {
  CHAPTERS, FRAMES, STARTS, TOTAL, buildScript, buildShot, buildStrip, fillSlots, frameSlots, locate,
  rangeText, slotSource, slotText, slotsIn, staleNumbers, stillTime,
} from '../js/reel-frames.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const readRepo = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8');
const manifest = JSON.parse(read('data/atlas_manifest.json'));
const manuscript = JSON.parse(read('data/manuscript.json'));
const sources = { manifest, manuscript };
const sidecar = JSON.parse(read('motion/frames/index.json'));
// The records the film shows as Pending on purpose: work not done yet.
const PENDING_ON_PURPOSE = new Set(['ms:open_sorted_test']);
const PAYLOAD = '<script>alert(1)</script>';

const visible = (frame) => [
  ...frame.screen.map((s) => s.text), frame.voice, frame.camera, frame.transition, frame.water,
  frame.particles, frame.sound, frame.title, frame.drawn ?? '',
];

test('the scenes add up to two minutes, in order, each still inside its scene', () => {
  assert.equal(TOTAL, 120);
  assert.equal(FRAMES.reduce((s, f) => s + f.seconds, 0), 120);
  assert.ok(FRAMES.length >= 8 && FRAMES.length <= 12, `${FRAMES.length} scenes`);
  FRAMES.forEach((f, i) => {
    assert.equal(STARTS[i], FRAMES.slice(0, i).reduce((s, g) => s + g.seconds, 0));
    assert.ok(f.seconds > 0 && Number.isInteger(f.seconds), f.id);
    assert.ok(f.still > 0 && f.still <= 1, f.id);
    assert.ok(stillTime(i) > STARTS[i] && stillTime(i) < STARTS[i] + f.seconds, `${f.id}'s still is outside it`);
    assert.equal(locate(stillTime(i)).id, f.id);
    assert.ok(CHAPTERS.some((c) => c.id === f.chapter), f.id);
    assert.ok(f.depth.every((d) => d >= 0 && d <= 1), f.id);
  });
  assert.equal(new Set(FRAMES.map((f) => f.id)).size, FRAMES.length, 'scene ids are unique');
  assert.equal(rangeText(0), '0:00 to 0:08');
  assert.equal(locate(119.9).id, FRAMES.at(-1).id);
});

test('every scene has its words, its motion notes and its sound', () => {
  for (const f of FRAMES) {
    assert.ok(f.screen.length > 0 && f.voice && f.camera && f.transition && f.water && f.particles && f.sound, f.id);
    assert.ok(f.tools.length > 0, f.id);
    const headlines = f.screen.filter((s) => s.role === 'headline');
    assert.equal(headlines.length, 1, `${f.id} has one headline`);
    assert.ok(headlines[0].text.endsWith(headlines[0].cut), `${f.id}'s cut word ends its headline`);
  }
  // The arc: the problem first, the results before the end, a call at the end.
  assert.equal(FRAMES[0].chapter, 'problem');
  assert.equal(FRAMES.at(-1).chapter, 'use');
  assert.ok(FRAMES.some((f) => f.chapter === 'results'));
  assert.ok(FRAMES.some((f) => f.tools.includes('Manim')));
});

test('every number slot names a measured record, apart from the work not done yet', () => {
  const slots = FRAMES.flatMap(frameSlots);
  assert.ok(slots.length > 12);
  for (const slot of slots) {
    if (slot.source === 'ms') assert.ok(slot.key in manuscript.records, `${slot.id} has no record`);
    const text = slotText(slot, sources);
    if (PENDING_ON_PURPOSE.has(slot.id)) assert.equal(text, 'Pending', slot.id);
    else assert.notEqual(text, 'Pending', `${slot.id} reads Pending`);
    assert.ok(slotSource(slot, sources).file, `${slot.id} names no source file`);
  }
  for (const id of PENDING_ON_PURPOSE) assert.ok(slots.some((s) => s.id === id), `${id} is not in the film`);
  assert.deepEqual(slotsIn('{ms:a_b} and {fact:model_name}').map((s) => s.id), ['ms:a_b', 'fact:model_name']);
  assert.equal(slotText({ source: 'fact', key: 'no_such_fact' }, sources), 'Pending');
});

test('no number is typed into the storyboard or the page: every share and decimal is a slot', () => {
  for (const f of FRAMES) {
    const text = visible(f).join(' ').replace(/\{(ms|fact):[a-z0-9_]+\}/g, ' ');
    assert.deepEqual(text.match(/\d+(?:\.\d+)?\s?%/g) ?? [], [], `${f.id}: a typed percentage`);
    assert.deepEqual(text.match(/(?<![\w.])\d+\.\d+/g) ?? [], [], `${f.id}: a typed decimal`);
  }
  const html = read('motion.html');
  const main = html.match(/<main[\s\S]*<\/main>/)[0].replace(/<code>[^<]*<\/code>/g, ' ').replace(/<[^>]+>/g, ' ');
  assert.deepEqual(main.match(/\d+(?:\.\d+)?\s?%/g) ?? [], [], 'a typed percentage');
  assert.deepEqual(main.match(/(?<![\w.])\d+\.\d+/g) ?? [], [], 'a typed decimal');
});

test('the words keep the site\'s copy rules', () => {
  const html = read('motion.html');
  const main = html.match(/<main[\s\S]*<\/main>/)[0].replace(/<[^>]+>/g, ' ');
  for (const text of [...FRAMES.flatMap(visible), main]) {
    assert.ok(!text.includes('—'), `an em dash: ${text}`);
    for (const word of [/calibrated/i, /\bbeats?\b/i, /state of the art/i, /\bdeployed\b/i, /\bhosted\b/i, /99%/, /every ome/i]) {
      assert.doesNotMatch(text, word, text);
    }
  }
  assert.equal((html.match(/<h1[\s>]/g) ?? []).length, 1, 'exactly one h1');
  for (const f of FRAMES) for (const key of f.caveats ?? []) assert.ok(key in CAVEATS, `${f.id}: unknown caveat ${key}`);
});

test('the page escapes what it fills in, and a failed load reads Pending', () => {
  assert.ok(!fillSlots(PAYLOAD, sources).includes('<script>'));
  const bad = { manuscript: { records: { x: { value: 1, status: 'measured', format: PAYLOAD, basis: PAYLOAD } } } };
  assert.ok(!fillSlots('{ms:x}', bad).includes('<script>'));
  const html = FRAMES.map((_, i) => buildShot(i, {}, null)).join('');
  assert.match(html, /class="pending">Pending/);
  assert.match(html, /Not rendered yet/);
  assert.ok(!/NaN|undefined/.test(html));
  const live = buildShot(8, sources, sidecar.frames[8]);
  assert.ok(live.includes(slotText({ source: 'ms', key: 'committed_fulcher' }, sources)));
  assert.match(buildScript(sources), /<table/);
  assert.equal((buildStrip(sidecar.frames).match(/<li>/g) ?? []).length, FRAMES.length);
});

// The stills are rendered with the numbers of their day; this fails when a
// record has changed since, so the stills are rendered again
// (cd motion && npm run stills).
test('the rendered stills match the storyboard and the current records', () => {
  assert.deepEqual(sidecar.built_for, manuscript.built_for, 'the stills were rendered for another release');
  assert.equal(sidecar.film_seconds, TOTAL);
  assert.deepEqual(sidecar.frames.map((f) => f.id), FRAMES.map((f) => f.id));
  sidecar.frames.forEach((still, i) => {
    assert.ok(existsSync(new URL(`../motion/frames/${still.file}`, import.meta.url)), `${still.file} is missing`);
    assert.ok(still.bytes < 1.5e6, `${still.file} is over 1.5 MB`);
    assert.equal(still.at, stillTime(i), `${still.id} was taken at another time`);
    assert.deepEqual(still.numbers.map((n) => n.slot), frameSlots(FRAMES[i]).map((s) => s.id), `${still.id}'s numbers`);
    assert.deepEqual(staleNumbers(still, sources), [], `${still.id} shows a number that has changed: render the stills again`);
    for (const n of still.numbers) {
      assert.ok(n.file && n.record, `${still.id}: ${n.slot} has no source`);
      const [source, key] = n.slot.split(':');
      assert.deepEqual({ file: n.file, field: n.field }, (({ file, field }) => ({ file, field }))(slotSource({ source, key }, sources)));
    }
  });
  // A changed record is caught.
  const changed = structuredClone(manuscript);
  changed.records.committed_fulcher.value = 0.5;
  assert.equal(staleNumbers(sidecar.frames[8], { manifest, manuscript: changed }).length, 1);
});

// The owner's rule for the film: one background throughout, the site's white
// field and gel, never tinted with depth; depth shows in the objects, and
// every word is in dark ink.
test('the film keeps one white background: no tinting water effect, no white-on-dark scenes, no note of the water changing colour', async () => {
  const { PLAN } = await import('../../motion/lib/plan.js');
  assert.deepEqual(Object.keys(PLAN).sort(), FRAMES.map((f) => f.id).sort());
  for (const [id, plan] of Object.entries(PLAN)) {
    assert.ok(['still', 'rain', 'wake'].includes(plan.effect), `${id} uses the ${plan.effect} effect, which tints the gel`);
  }
  FRAMES.forEach((f, i) => {
    const n = String(i + 1).padStart(2, '0');
    assert.ok(!readRepo(`motion/compositions/s${n}-${f.id}.html`).includes('on-deep'), `${f.id} sets white type`);
    for (const note of [f.camera, f.transition, f.water, f.particles]) {
      assert.doesNotMatch(note, /\b(blue|bluer|dark|darker|darkens|caustic|ink)\b/i, `${f.id}: "${note}"`);
    }
  });
  assert.ok(!readRepo('motion/lib/film.css').includes('on-deep'));
});

// Every word and diagram sits on one of the site's two cards: white sheets
// in odd scenes, liquid glass in even ones; a scene uses only its own kind.
test('each scene puts its words on its card kind, alternating white sheet and liquid glass', () => {
  FRAMES.forEach((f, i) => {
    assert.equal(f.card, i % 2 === 0 ? 'sheet' : 'liquid', `${f.id}'s card`);
    const n = String(i + 1).padStart(2, '0');
    const classes = [...readRepo(`motion/compositions/s${n}-${f.id}.html`).matchAll(/class="([^"]*)"/g)].map((m) => m[1].split(/\s+/));
    const kinds = new Set(classes.flat().filter((c) => c === 'sheet' || c === 'liquid'));
    assert.deepEqual([...kinds], [f.card], `${f.id} uses ${[...kinds].join(' and ')} cards`);
    assert.ok(classes.some((c) => c.includes('card') && c.includes(f.card)), `${f.id} has no ${f.card} card`);
  });
  const film = readRepo('motion/lib/film.css');
  assert.match(film, /\.scene \.sheet, \.scene \.liquid \{/, 'the film styles both of the site\'s cards');
  assert.ok(!/\.liquid\s*\{[^}]*background/.test(film), 'the film keeps the site\'s own liquid glass');
});

// docs/web/motion.md carries the full script, for producing the film.
test('the docs carry every scene\'s time, words and notes as the storyboard has them', () => {
  const doc = readRepo('docs/web/motion.md');
  FRAMES.forEach((f, i) => {
    assert.ok(doc.includes(`### ${i + 1}. ${f.title} (${rangeText(i)}, ${f.seconds} s)`), `${f.id}'s heading`);
    for (const text of [f.voice, f.camera, f.transition, f.water, f.particles, f.sound, ...f.screen.map((s) => s.text)]) {
      assert.ok(doc.includes(text), `${f.id}: "${text}" is not in docs/web/motion.md`);
    }
  });
});

// The compositions in motion/ render what the storyboard says: each scene's
// on-screen words and slots, at its time in the film.
test('each composition shows its scene\'s words and numbers, at its place in the film', () => {
  const index = readRepo('motion/index.html');
  const squash = (s) => s.replace(/<[^>]+>/g, '').replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, '');
  FRAMES.forEach((frame, i) => {
    const n = String(i + 1).padStart(2, '0');
    const host = index.match(new RegExp(`<div id="host-${frame.id}"[^>]*>`));
    assert.ok(host, `motion/index.html has no host for ${frame.id}`);
    assert.match(host[0], new RegExp(`data-composition-src="compositions/s${n}-${frame.id}\\.html"`));
    assert.match(host[0], new RegExp(`data-start="${STARTS[i]}"`));
    assert.match(host[0], new RegExp(`data-duration="${frame.seconds}"`));
    const html = readRepo(`motion/compositions/s${n}-${frame.id}.html`);
    const words = squash(html.replace(/<style[\s\S]*?<\/style>|<script[\s\S]*?<\/script>|<!--[\s\S]*?-->/g, ''));
    for (const item of frame.screen) {
      for (const part of item.text.split(/\{(?:ms|fact):[a-z0-9_]+\}/)) {
        if (part.trim()) assert.ok(words.includes(squash(part)), `${frame.id}: "${part}" is not on screen`);
      }
      for (const slot of slotsIn(item.text)) assert.ok(html.includes(`data-slot="${slot.id}"`), `${frame.id}: no slot for ${slot.id}`);
    }
    for (const key of frame.caveats ?? []) assert.ok(html.includes(`data-caveat="${key}"`), `${frame.id}: no ${key} bead`);
  });
  assert.match(index, /data-duration="120"/);
});
