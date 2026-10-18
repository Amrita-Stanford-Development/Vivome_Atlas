// The Motion page (web/motion.html) and the film's storyboard
// (web/js/reel-frames.js): its timing, its numbers, its words, and the
// rendered stills (web/motion/frames/, from motion/scripts/stills.mjs).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { CAVEATS } from '../js/manuscript-data.js';
import { formatClock } from '../js/timeline.js';
import {
  AFTER, CHAPTERS, EXIT, FADE, FRAMES, JOURNEY, OPENING, STARTS, TOTAL, VOICE_AT, buildFilm, buildScript, buildShot, buildStrip,
  cardLength, cardOpacity, cardRange, cueTime, fillSlots, frameSlots, journeyOf, locate, phrasesOf, rangeText,
  slotSource, slotText, slotsIn, staleNumbers, stillTime, voiceStart,
} from '../js/reel-frames.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const readRepo = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8');
const manifest = JSON.parse(read('data/atlas_manifest.json'));
const manuscript = JSON.parse(read('data/manuscript.json'));
const sources = { manifest, manuscript };
const sidecar = JSON.parse(read('motion/frames/index.json'));
const film = JSON.parse(read('motion/film/index.json'));
// The records the film shows as Pending on purpose: work not done yet.
const PENDING_ON_PURPOSE = new Set(['ms:open_sorted_test']);
const PAYLOAD = '<script>alert(1)</script>';

const visible = (frame) => [
  ...frame.screen.map((s) => s.text), frame.voice, frame.camera, frame.transition, frame.water,
  frame.particles, frame.sound, frame.title, frame.drawn ?? '',
];

test('the scenes add up to the film, in order: a journey, then a card that holds its line and its still', () => {
  assert.equal(TOTAL, FRAMES.reduce((s, f) => s + f.seconds, 0));
  assert.ok(TOTAL <= 180, `${TOTAL} s is over three minutes`);
  assert.ok(FRAMES.length >= 8 && FRAMES.length <= 12, `${FRAMES.length} scenes`);
  FRAMES.forEach((f, i) => {
    assert.equal(STARTS[i], FRAMES.slice(0, i).reduce((s, g) => s + g.seconds, 0));
    assert.ok(f.seconds > 0 && Number.isInteger(f.seconds), f.id);
    assert.equal(journeyOf(i), i === 0 ? OPENING : JOURNEY);
    assert.deepEqual(cardRange(i), [STARTS[i] + journeyOf(i), STARTS[i] + f.seconds]);
    assert.ok(f.still > 0 && f.still <= 1, f.id);
    // The still is taken once the line has been said, and before the card's
    // closing picture.
    const still = stillTime(i) - cardRange(i)[0];
    assert.ok(still >= VOICE_AT + f.said.seconds, `${f.id}'s still is taken before its line ends`);
    assert.ok(still <= (i === FRAMES.length - 1 ? cardLength(i) : cardLength(i) - FADE - EXIT), `${f.id}'s still is taken in its close`);
    assert.equal(locate(stillTime(i)).id, f.id);
    assert.equal(locate(stillTime(i)).phase, 'card');
    assert.equal(locate(STARTS[i] + 0.5).phase, 'journey');
    assert.ok(CHAPTERS.some((c) => c.id === f.chapter), f.id);
    assert.ok(!('depth' in f), `${f.id} still sets a depth`);
    // Long enough to hear the line and to read the card.
    const words = f.screen.map((x) => x.text).join(' ').split(/\s+/).length;
    assert.ok(cardLength(i) >= VOICE_AT + f.said.seconds + AFTER + FADE, `${f.id}'s card is shorter than its line`);
    assert.ok(cardLength(i) >= FADE + words / 4 + 0.8, `${f.id}'s card is too short to read`);
  });
  assert.equal(new Set(FRAMES.map((f) => f.id)).size, FRAMES.length, 'scene ids are unique');
  assert.equal(rangeText(0), '0:00 to 0:10');
  assert.equal(locate(TOTAL - 0.1).id, FRAMES.at(-1).id);
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

// The film on the page bakes its numbers in as the stills do: this fails
// when a record has changed since it was made, or the storyboard's length
// has, so the film is made again (cd motion && npm run film).
test('the film on the page is the current film, its numbers the current records, its file the one described', () => {
  assert.deepEqual(film.built_for, manuscript.built_for, 'the film was made for another release');
  assert.ok(Math.abs(film.seconds - TOTAL) < 0.05, `the film runs ${film.seconds} s, the storyboard ${TOTAL} s`);
  const file = readFileSync(new URL(`../motion/film/${film.file}`, import.meta.url));
  assert.equal(file.length, film.bytes, 'the film is not the one its sidecar describes');
  assert.ok(film.bytes < 24e6, `the film is ${film.bytes} bytes; Cloudflare Pages takes no file over 25 MiB`);
  assert.equal(createHash('sha256').update(file).digest('hex'), film.sha256, 'the film is not the one its sidecar describes');
  assert.ok(existsSync(new URL(`../motion/film/${film.poster}`, import.meta.url)), 'the film has no poster');
  assert.deepEqual([film.width, film.height], [1280, 720]);
  // Every number on screen or spoken, once, with its source.
  const slots = [...new Set(FRAMES.flatMap(frameSlots).map((x) => x.id))];
  assert.deepEqual(film.numbers.map((n) => n.slot), slots);
  assert.deepEqual(staleNumbers(film, sources), [], 'the film shows a number that has changed: make it again');
  for (const n of film.numbers) {
    const [source, key] = n.slot.split(':');
    assert.deepEqual({ file: n.file, field: n.field }, (({ file: f, field }) => ({ file: f, field }))(slotSource({ source, key }, sources)));
  }
  // The page says so when it goes stale, as it does for a still.
  const changed = structuredClone(manuscript);
  changed.records.committed_fulcher.value = 0.5;
  assert.match(buildFilm(film, { manifest, manuscript: changed }), /class="reel-stale">This film was rendered with an older value of ms:committed_fulcher/);
  assert.doesNotMatch(buildFilm(film, sources), /reel-stale/);
  assert.match(buildFilm({ ...film, built_for: { ...film.built_for, model_name: 'another' } }, sources), /for another release/);
  assert.ok(buildFilm(film, sources).includes(`<strong>${formatClock(TOTAL)}</strong>`), 'the page gives another running time');
  assert.ok(!/NaN|undefined/.test(buildFilm(null)));
  // A large native player, with its poster, that plays only when asked.
  const html = read('motion.html');
  const video = html.match(/<video[^>]*>/)?.[0];
  assert.ok(video, 'the page has no player');
  for (const attr of ['controls', 'preload="metadata"', 'playsinline', 'poster="motion/film/poster.webp"']) assert.ok(video.includes(attr), `the player has no ${attr}`);
  assert.ok(!/autoplay/.test(video), 'the film plays by itself');
  assert.match(html, /<source src="motion\/film\/vivome\.mp4" type="video\/mp4">/);
  assert.ok(html.indexOf('id="film"') < html.indexOf('id="reel-strip"'), 'the film is not above the storyboard');
});

// The owner's rule for the film: one background throughout, the site's white
// field and gel, never tinted with depth; depth shows in the objects, and
// every word is in dark ink.
test('the film keeps one white background: no tinting water effect, no white-on-dark scenes, no note of the water changing colour', async () => {
  const { PLAN } = await import('../../motion/lib/plan.js');
  assert.deepEqual(Object.keys(PLAN).sort(), FRAMES.map((f) => f.id).sort());
  // One ripple field and one gel for the whole film: no scene picks its own
  // effect, frost or cut.
  for (const [id, plan] of Object.entries(PLAN)) {
    for (const key of ['effect', 'frost', 'cut', 'move']) assert.ok(!(key in plan), `${id} sets its own ${key}`);
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

// The owner's rule: the cards never move. The camera travels between them
// (a journey), and a card is on screen only while the camera stands still:
// it fades in where it stands, holds and fades out. The sound is the music
// and the voice only.
test('card, journey, card: no card is on screen while the camera travels, and none overlaps another', () => {
  FRAMES.forEach((f, i) => {
    assert.doesNotMatch(f.sound, /\b(rain|bubbles?|ticks?|whoosh|pings?|sonar|splash|noise|clicks?)\b/i, `${f.id}'s sound: "${f.sound}"`);
    const [arrive, depart] = cardRange(i);
    assert.equal(arrive, STARTS[i] + journeyOf(i));
    if (i > 0) assert.ok(arrive - cardRange(i - 1)[1] >= JOURNEY - 1e-9, `${f.id}'s card overlaps the journey before it`);
    assert.equal(cardOpacity(i, 0), 0, `${f.id}'s card is on as the camera arrives`);
    assert.equal(cardOpacity(i, FADE), 1);
    if (i < FRAMES.length - 1) assert.equal(cardOpacity(i, depart - arrive), 0, `${f.id}'s card is on as the camera leaves`);
    else assert.equal(cardOpacity(i, depart - arrive), 1, 'the end card stays');
  });
  const dive = readRepo('motion/lib/dive.js');
  assert.match(dive, /function waterTo\(step\)/, 'one ripple field, stepped from the film\'s start');
  assert.doesNotMatch(dive, /function dip\(|plan\.frost|plan\.effect/, 'a per-scene reset is back');
  assert.doesNotMatch(dive, /style\.transform/, 'the cards are moved');
  assert.match(dive, /if \(phase !== 'card'\) return out;/, 'drops fall while the camera travels');
});

// The owner's rule for the camera: it travels from place to place through
// the particles, between the cards, each journey eased at both ends, and is
// exactly still while a card is on.
test('the camera stands still for each card and travels between them, each journey eased and in its own direction', async () => {
  const { PLAN, SURFACES } = await import('../../motion/lib/plan.js');
  const { cameraPath, directionOf, gaugeAt, poseAt, waterlineAt } = await import('../../motion/lib/camera.js');
  const spans = FRAMES.map((f, i) => ({ id: f.id, start: STARTS[i], seconds: f.seconds, journey: journeyOf(i) }));
  const path = cameraPath(spans, PLAN);
  const near = (a, b) => Math.hypot(a.x - b.x, a.y - b.y) < 1e-9;
  FRAMES.forEach((f, i) => {
    // Still during the card.
    const [arrive, depart] = cardRange(i);
    const at = poseAt(path, arrive);
    for (let t = arrive; t <= depart; t += 0.25) assert.ok(near(poseAt(path, t), at), `the camera moves during ${f.id}'s card`);
    // The journey takes its time, and starts and ends at rest.
    const t0 = STARTS[i];
    const t1 = t0 + journeyOf(i);
    const step = (t) => { const a = poseAt(path, t); const b = poseAt(path, t + 1 / 30); return Math.hypot(b.x - a.x, b.y - a.y); };
    assert.ok(step(t0) < 0.002 && step(t1 - 1 / 30) < 0.002, `${f.id}'s journey does not ease in and out`);
    assert.ok(step((t0 + t1) / 2) > 0.01, `the camera does not travel before ${f.id}`);
  });
  // No jump and no lurch.
  let before = 0;
  let prev = poseAt(path, 0);
  for (let k = 1; k <= TOTAL * 30; k += 1) {
    const pose = poseAt(path, k / 30);
    const step = Math.hypot(pose.x - prev.x, pose.y - prev.y);
    assert.ok(step < 0.3, `the camera jumps at ${(k / 30).toFixed(2)} s`);
    assert.ok(Math.abs(step - before) < 0.03, `the camera lurches at ${(k / 30).toFixed(2)} s`);
    before = step;
    prev = pose;
  }
  // The journeys go different ways: down, sideways and diagonally, never
  // twice the same way running, and the last rises.
  const ways = FRAMES.slice(1).map((f) => directionOf(PLAN[f.id].go));
  for (const way of ['down', 'right', 'left', 'down-right', 'down-left', 'up-right', 'up']) assert.ok(ways.includes(way), `no journey ${way}`);
  ways.slice(1).forEach((w, k) => assert.notEqual(w, ways[k], `two journeys ${w} in a row`));
  assert.equal(ways.at(-1), 'up');
  // The depth gauge goes down only on journeys down, up only on journeys up.
  FRAMES.slice(1).forEach((f, k) => {
    const i = k + 1;
    const [from, to] = [gaugeAt(path, STARTS[i], SURFACES), gaugeAt(path, cardRange(i)[0], SURFACES)];
    const [, dy] = PLAN[f.id].go;
    if (dy > 0) assert.ok(to >= from, `the gauge rises on the journey down to ${f.id}`);
    if (dy < 0) assert.ok(to <= from, `the gauge falls on the journey up to ${f.id}`);
    if (dy === 0) assert.ok(Math.abs(to - from) < 1e-9, `the gauge moves on the level journey to ${f.id}`);
  });
  // The waterline: in sight on the first card and the last, out of it on
  // the others; the camera passes between the two surfaces out of sight of both.
  FRAMES.forEach((f, i) => {
    const wl = waterlineAt(poseAt(path, cardRange(i)[0]), SURFACES);
    if (i === 0) assert.ok(wl > 0.5 && wl < 1, `the waterline on ${f.id}: ${wl}`);
    else if (i === FRAMES.length - 1) assert.ok(wl < 0.5, `the waterline on ${f.id}: ${wl}`);
    else assert.ok(wl > 1.05, `the waterline shows on ${f.id}: ${wl}`);
  });
  for (let t = 0; t < TOTAL; t += 1 / 30) {
    const a = poseAt(path, t);
    const b = poseAt(path, t + 1 / 30);
    const [sa, sb] = [SURFACES.find((w) => a.x >= w.x[0] && a.x < w.x[1]), SURFACES.find((w) => b.x >= w.x[0] && b.x < w.x[1])];
    if (sa === sb) continue;
    for (const pose of [a, b]) for (const w of SURFACES) {
      const wl = 0.5 + (pose.y - w.y) / (2 * 12 * Math.tan((23 * Math.PI) / 180));
      assert.ok(wl > 1.05 || wl < -0.05, `the surfaces change in sight at ${t.toFixed(2)} s`);
    }
  }
});

// The owner's rule for the water: every object keeps its size. Each is at a
// fixed depth; the camera's travel moves it across the frame by the travel
// over its depth, and it wraps round only out of sight.
test('the water\'s objects keep their size and depth, pass by in parallax, and wrap only out of sight', async () => {
  const { placeAt, seedShoal, kinds } = await import('../../motion/lib/shoal.js');
  const { ASPECT, TAN } = await import('../../motion/lib/camera.js');
  let seed = 7;
  const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  for (const [kind, spec] of kinds()) {
    for (const o of seedShoal(rand, spec, 1.5)) {
      const a = placeAt(o, { x: 0, y: 0 }, 10);
      const b = placeAt(o, { x: 0.05, y: 0 }, 10);
      const c = placeAt(o, { x: 0, y: 0.05 }, 10);
      assert.equal(a.z, -o.d, kind);
      assert.equal(b.z, a.z);
      assert.equal(a.scale, b.scale);
      assert.equal(a.scale, c.scale);
      if (Math.abs(b.u) < o.hu - 0.1) assert.ok(Math.abs(b.u - a.u + 0.05 / (o.d * TAN * ASPECT)) < 1e-9, `${kind} does not pass by at its depth`);
      if (Math.abs(c.v) < o.hv - 0.1) assert.ok(Math.abs(c.v - a.v - 0.05 / (o.d * TAN)) < 1e-9, `${kind} does not rise past at its depth`);
      // A wrap happens only past the frame's edge, with the object out of sight.
      assert.ok(o.hu > 1.05 && o.hv > 1.05);
    }
  }
  const dive = readRepo('motion/lib/dive.js');
  assert.doesNotMatch(dive, /camera\.fov\s*=/, 'the view narrows');
  assert.doesNotMatch(dive, /advance|createBioLayer/, 'the camera moves forward through the objects');
  const field = readRepo('motion/lib/field.js');
  assert.doesNotMatch(field, /pulse|scale\(/, 'the particles change size');
  const block = (text) => text.match(/const UM[\s\S]*?\n};\n/)[0];
  assert.equal(block(readRepo('motion/lib/shoal.js')), block(read('js/biocells.js')), 'the water\'s table differs from the site\'s');
});

// Cards never move: what changes on a card is its opacity, or a word
// revealed in place; and a card fades by itself, never through its scene.
test('the cards stand still: no composition moves, scales or turns anything, and each fades its cards itself', () => {
  FRAMES.forEach((f, i) => {
    const n = String(i + 1).padStart(2, '0');
    const html = readRepo(`motion/compositions/s${n}-${f.id}.html`);
    const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
    assert.doesNotMatch(script, /\b(x|y|xPercent|yPercent|scale|scaleX|scaleY|rotation|rotationX|rotationY|rotate|transform)\s*:/, `${f.id} moves something`);
    assert.equal((script.match(/VivomeCue\.card\(|C\.card\(/g) ?? []).length, 1, `${f.id} does not fade its cards`);
    assert.ok(!script.includes(`'#s-${f.id}'`), `${f.id} fades through its scene`);
  });
});

// The pictures act out the voice: each phrase has its cue, inside the card,
// in order, as motion/scripts/voice.mjs measured it at the voice's own pace.
test('each line is spoken at its own pace and timed phrase by phrase inside its card', () => {
  FRAMES.forEach((f, i) => {
    const phrases = phrasesOf(f.voice);
    assert.equal(phrases.join(' '), f.voice, f.id);
    assert.equal(phrases.length, f.said.at.length, `${f.id} has ${phrases.length} phrases`);
    assert.equal(f.said.at[0], 0);
    f.said.at.forEach((at, k) => {
      if (k > 0) assert.ok(at > f.said.at[k - 1], `${f.id}'s cues go back`);
      const cue = cueTime(i, k);
      assert.ok(cue >= VOICE_AT && cue <= cardLength(i) - FADE - (i === FRAMES.length - 1 ? 0 : EXIT), `${f.id}'s cue ${k} is outside its card`);
    });
    assert.ok(f.said.at.at(-1) < f.said.seconds);
    assert.equal(voiceStart(i), cardRange(i)[0] + VOICE_AT);
  });
  const voice = readRepo('motion/scripts/voice.mjs');
  assert.match(voice, /export const SPEED = 1;/);
  assert.doesNotMatch(voice, /MAX_SPEED|TIGHT_/, 'a line may be hurried');
});

// What closes one card opens the next, in the same spot: the eye carries it
// across the journey (motion/lib/plan.js, RHYMES), and the places the
// pictures are drawn are the compositions' own.
test('each card opens where the last one closed, on the scenes\' own pictures', async () => {
  const { RHYMES } = await import('../../motion/lib/plan.js');
  assert.deepEqual(RHYMES.map((r) => [r.from, r.to]), FRAMES.slice(1).map((f, i) => [FRAMES[i].id, f.id]));
  for (const r of RHYMES) {
    assert.ok(Math.hypot(r.open[0] - r.close[0], r.open[1] - r.close[1]) <= 40, `${r.to} opens away from where ${r.from} closed`);
    for (const [x, y] of [r.open, r.close]) assert.ok(x >= 0 && x <= 1920 && y >= 0 && y <= 1080, `${r.from} closes off the frame`);
  }
  const scenes = readRepo('motion/lib/scenes.js');
  const px = (html, rule) => {
    const m = html.match(new RegExp(`${rule} \\{([^}]*)\\}`));
    assert.ok(m, `no rule ${rule}`);
    const get = (k) => Number(m[1].match(new RegExp(`(?:^|[\\s;])${k}: (-?\\d+)px`))?.[1] ?? NaN);
    const pad = m[1].match(/padding: (\d+)px(?: (\d+)px)?/);
    return { left: get('left'), top: get('top'), padTop: pad ? Number(pad[1]) : 0, padLeft: pad ? Number(pad[2] ?? pad[1]) : 0 };
  };
  // A canvas inside a card sits past the card's 1px rim and its padding.
  const inside = (html, rule) => { const r = px(html, rule); return [r.left + 1 + r.padLeft, r.top + 1 + r.padTop]; };
  const [gx, gy] = inside(readRepo('motion/compositions/s03-gaps.html'), '#s-gaps \\.matrix');
  assert.match(scenes, new RegExp(`gaps: \\{ left: ${gx}, top: ${gy}, width: 960 \\}`));
  const [mx, my] = inside(readRepo('motion/compositions/s06-built-for-gaps.html'), '#s-built-for-gaps \\.matrix');
  assert.match(scenes, new RegExp(`'built-for-gaps': \\{ left: ${mx}, top: ${my}, width: 860 \\}`));
  const [rx, ry] = inside(readRepo('motion/compositions/s04-rna.html'), '#s-rna \\.map');
  assert.match(scenes, new RegExp(`RNA_CANVAS = \\{ left: ${rx}, top: ${ry}, width: 980, height: 920 \\}`));
  const [dx, dy] = inside(readRepo('motion/compositions/s08-second-opinion.html'), '#s-second-opinion \\.diagram');
  assert.match(scenes, new RegExp(`DIAGRAM = \\{ left: ${dx}, top: ${dy} \\}`));
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
    // Each scene's host is on while its card is, and only then.
    assert.match(host[0], new RegExp(`data-start="${cardRange(i)[0]}"`));
    assert.match(host[0], new RegExp(`data-duration="${cardLength(i)}"`));
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
  assert.match(index, new RegExp(`data-composition-id="main" data-start="0" data-duration="${TOTAL}"`));
});
