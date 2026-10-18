// Gets the compositions ready to render, from the repository as it is now:
//
// 1. vendor/: the site's own code the film uses, copied unchanged: the
//    living water (web/js/biocells.js, water.js, random.js), the Workflow
//    page's colour ramps and type names (web/js/workflow-layout.js,
//    web/js/scene-kit.js), the site stylesheet (web/css/page.css),
//    three.js r128 (the build the site loads) and GSAP.
//    The landing's count-up maths (web/js/motion.js) is wrapped as a
//    classic script, build/count.js.
// 2. build/facts.js: every number the storyboard puts on screen, read from
//    web/data/atlas_manifest.json and web/data/manuscript.json through the
//    site's own formatters (web/js/reel-frames.js), with its source; and
//    the data the drawn shots use, from web/data/workflow.json.
// 3. build/answers.json: the Manim shot's map and cells (manim/answers.py).
// 4. build/timeline.json: when each scene's journey and card are, and when
//    each phrase of its line is said, in film seconds, for the score
//    (audio/score.py) and the mix (scripts/film.mjs).
//
// Nothing here is typed in: run it before every preview or render (the npm
// scripts do). It refuses to run on a manifest and manuscript data built
// for different releases.
//
//     node scripts/prepare.mjs

import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const { RHYMES } = await import(pathToFileURL(join(ROOT, 'lib', 'plan.js')).href);
const REPO = join(ROOT, '..');
const site = (p) => join(REPO, p);
const load = (p) => import(pathToFileURL(site(p)).href);

const {
  FRAMES, STARTS, TOTAL, CHAPTERS, FADE, EXIT, VOICE_AT, journeyOf, cardRange, cardLength, cueTime,
  frameSlots, slotText, slotMeasured, slotSource,
} = await load('web/js/reel-frames.js');
const { checkSync } = await load('web/js/manuscript-data.js');
const { CLASS_COLOURS } = await load('web/js/workflow-data.js');

const json = (p) => JSON.parse(readFileSync(site(p), 'utf8'));
const write = (p, text) => {
  mkdirSync(dirname(join(ROOT, p)), { recursive: true });
  writeFileSync(join(ROOT, p), text.replace(/\r\n/g, '\n'));
};

// ---- 1. the site's code, copied ----

const COPIES = [
  ['node_modules/three/build/three.min.js', 'vendor/three.min.js'],
  ['node_modules/gsap/dist/gsap.min.js', 'vendor/gsap.min.js'],
];
const SITE_COPIES = ['web/js/biocells.js', 'web/js/water.js', 'web/js/random.js', 'web/js/workflow-layout.js', 'web/js/scene-kit.js', 'web/css/page.css'];
mkdirSync(join(ROOT, 'vendor', 'site'), { recursive: true });
for (const [from, to] of COPIES) copyFileSync(join(ROOT, from), join(ROOT, to));
for (const from of SITE_COPIES) copyFileSync(site(from), join(ROOT, 'vendor', 'site', from.split('/').pop()));

const count = readFileSync(site('web/js/motion.js'), 'utf8').replace(/^export /gm, '');
write('build/count.js', `// web/js/motion.js, unchanged but for its exports: the landing's count-up maths.\n(function () {\n${count}\nwindow.VivomeCount = { countText, clamp01 };\n})();\n`);

// ---- 2. the numbers, and the data the drawn shots use ----

const manifest = json('web/data/atlas_manifest.json');
const manuscript = json('web/data/manuscript.json');
const sync = checkSync(manifest, manuscript);
if (!sync.ok) throw new Error(`The data files are from different releases: ${sync.problems.join('; ')}`);
const sources = { manifest, manuscript };

// Each number as text, through the site's guards, with its source; a
// measured record also gives its value, for the pictures that draw it (a
// grid filled to a share, a row of squares). A pending one has none.
const facts = {};
for (const frame of FRAMES) {
  for (const slot of frameSlots(frame)) {
    const measured = slotMeasured(slot, sources);
    const value = slot.source === 'ms' && measured ? manuscript.records[slot.key].value : null;
    facts[slot.id] = { text: slotText(slot, sources), measured, value, ...slotSource(slot, sources) };
  }
}

const w = json('web/data/workflow.json');
const classes = w.reference.classes.map((c, i) => ({
  name: c.name, group: c.group, lineage: c.lineage, colour: CLASS_COLOURS[i % CLASS_COLOURS.length],
}));

// One view of the atlas's 3D projection for every map in the film, turned
// so the big types sit apart (yaw 108 degrees, pitch 24).
const YAW = (108 * Math.PI) / 180;
const PITCH = (24 * Math.PI) / 180;
const turn = ([x, y, z]) => {
  const x1 = x * Math.cos(YAW) + z * Math.sin(YAW);
  const z1 = -x * Math.sin(YAW) + z * Math.cos(YAW);
  return [x1, y * Math.cos(PITCH) - z1 * Math.sin(PITCH)];
};
// Then turned in the plane so the cloud's long axis lies along the frame's
// width (the principal axis of the sample's spread).
const flat = w.reference.sample.map(([x, y, z]) => turn([x / 1000, y / 1000, z / 1000]));
const mx = flat.reduce((s, p) => s + p[0], 0) / flat.length;
const my = flat.reduce((s, p) => s + p[1], 0) / flat.length;
let sxx = 0; let syy = 0; let sxy = 0;
for (const [x, y] of flat) { sxx += (x - mx) ** 2; syy += (y - my) ** 2; sxy += (x - mx) * (y - my); }
const ANGLE = -0.5 * Math.atan2(2 * sxy, sxx - syy);
const view = (p) => {
  const [x, y] = turn(p);
  return [x * Math.cos(ANGLE) - y * Math.sin(ANGLE), x * Math.sin(ANGLE) + y * Math.cos(ANGLE)];
};
const sample = w.reference.sample.slice(0, 1600).map(([x, y, z, c]) => [...view([x / 1000, y / 1000, z / 1000]).map((v) => +v.toFixed(4)), c]);
const xs = sample.map((p) => p[0]).sort((a, b) => a - b);
const ys = sample.map((p) => p[1]).sort((a, b) => a - b);
const q = (arr, f) => arr[Math.floor(f * (arr.length - 1))];
const bounds = [q(xs, 0.01), q(xs, 0.99), q(ys, 0.01), q(ys, 0.99)];
const centres = w.reference.centres.map((c) => view(c.map((v) => v / 1000)).map((v) => +v.toFixed(4)));

const REASONS = {
  coverage_too_low: 'too few genes measured',
  outside_supported_region: 'too unlike the reference',
  no_confident_label: 'no type stands out',
  ambiguous_between_classes: 'several types fit',
};
const cells = w.trace.cells.map((c) => ({
  xy: c.xyz ? view(c.xyz).map((v) => +v.toFixed(4)) : null,
  outcome: c.outcome,
  level: c.level,
  label: c.label,
  set: c.set,
  candidates: c.candidate_set,
  guess: c.guess,
}));

// The answers shot: the file's first cell answered at each level, then
// its first with no answer because several types fit.
const firstOf = (outcome) => w.trace.cells.findIndex((c) => c.outcome === outcome);
const answers = ['class', 'group', 'lineage', 'ambiguous_between_classes'].map((outcome) => {
  const i = firstOf(outcome);
  const c = w.trace.cells[i];
  return {
    cell: i,
    level: c.level ?? 'none',
    answer: c.level ? c.label : REASONS[c.outcome],
    types: (c.set?.length ? c.set : c.candidate_set),
    xy: cells[i].xy,
  };
});

// Where the answers shot draws its map, and when: the four cells land
// together at the start of scene 7's card, each with its widest set; then
// each cell's set narrows as its rung is said (its phrase, from the
// storyboard's `said`), and the last widens as "or no answer" is said.
// Manim draws the map and the sets, the composition the words.
const answersAt = FRAMES.findIndex((f) => f.id === 'answers');
const frame30 = (v) => Math.round(v * 30) / 30;
// The shot looks closely at the types the four cells' sets name.
const involved = new Set(answers.flatMap((a) => a.types));
const near = sample.filter((p) => involved.has(p[2]));
const nx = near.map((p) => p[0]).sort((a, b) => a - b);
const ny = near.map((p) => p[1]).sort((a, b) => a - b);
const pad = (lo, hi) => [lo - (hi - lo) * 0.08, hi + (hi - lo) * 0.08];
// How each cell's set narrows in the shot, from the wider sets its types
// belong to down to the set itself: a cell-type answer from its group and
// its lineage (the wider first: the two are not always nested), a group
// answer from its lineage, a lineage answer from every type; with no
// answer, the set widens instead, from the best guess to every type that
// fits. A stage that names the same types as the next is left out.
const typesWhere = (keep) => classes.map((_, k) => k).filter((k) => keep(classes[k]));
const sameTypes = (a, b) => a.length === b.length && [...a].sort().every((v, i) => v === [...b].sort()[i]);
const stagesOf = (a) => {
  const first = classes[a.types[0]];
  const wide = {
    class: [typesWhere((c) => c.lineage === first.lineage), typesWhere((c) => c.group === first.group)],
    group: [typesWhere((c) => c.lineage === first.lineage)],
    lineage: [classes.map((_, k) => k)],
    none: [[cells[a.cell].guess]],
  }[a.level];
  if (a.level !== 'none') wide.sort((x, y) => y.length - x.length);
  const all = [...wide, a.types];
  return all.filter((set, i) => i === all.length - 1 || !sameTypes(set, all[i + 1]));
};
const stages = answers.map(stagesOf);
const answersShot = {
  box: [90, 230, 1130, 1040],
  bounds: [...pad(q(nx, 0.02), q(nx, 0.98)), ...pad(q(ny, 0.02), q(ny, 0.98))],
  seconds: cardLength(answersAt),
  fps: 30,
  // The map's points arrive from where scene 6 left its points (seconds
  // into the card).
  map: [0.3, 1.0],
  from: RHYMES.find((r) => r.to === 'answers').open,
  // When each cell appears, its fade and its flight to its place, the
  // drawing of its widest set, and each later stage's step.
  land: answers.map((_, k) => frame30(1.0 + k * 0.2)),
  fade: 0.2,
  flight: 0.3,
  outline: 0.4,
  step: 0.4,
  stages,
  // When each cell's set has settled: as its rung is said.
  settle: answers.map((_, k) => frame30(cueTime(answersAt, k + 1))),
  // When the reason for no answer is said.
  reason: frame30(cueTime(answersAt, 5)),
};

// Scene 8's diagram, in seconds into its card: when each current is drawn
// (from, for), when the gate appears (as the voice says when the second
// opinion is used), the meter fills, the gate opens, and the best guess
// shows.
const secondAt = FRAMES.findIndex((f) => f.id === 'second-opinion');
const secondOpinion = {
  encoder: [0.3, 1.2], correlation: [1.4, 1.2], gate: +cueTime(secondAt, 1).toFixed(3),
  meter: [3.4, 4.4], open: [4.6, 5.0], guess: 5.6,
};

// The atlas in 3D for the flights of scenes 4 and 11: the same reference
// sample and the example file's cells at their coordinates in the atlas's
// projection, centred and scaled so the cloud spans about one unit.
const raw3 = w.reference.sample.slice(0, 2600).map(([x, y, z, c]) => [x / 1000, y / 1000, z / 1000, c]);
const mid3 = [0, 1, 2].map((k) => raw3.reduce((s, p) => s + p[k], 0) / raw3.length);
const radii = raw3.map((p) => Math.hypot(p[0] - mid3[0], p[1] - mid3[1], p[2] - mid3[2])).sort((a, b) => a - b);
const unit = 1 / radii[Math.floor(radii.length * 0.95)];
const to3 = (xyz) => xyz.map((v, k) => +((v - mid3[k]) * unit).toFixed(4));
const atlas3 = {
  points: raw3.map(([x, y, z, c]) => [...to3([x, y, z]), c]),
  centres: w.reference.centres.map((c) => to3(c.map((v) => v / 1000))),
  cells: w.trace.cells.map((c) => (c.xyz ? to3(c.xyz) : null)),
};

const hm = w.trace.heatmap;
const VIVOME = {
  built_for: manuscript.built_for,
  total: TOTAL,
  fade: FADE,
  chapters: CHAPTERS,
  // Each scene: its journey, then its card (arrive to depart, film
  // seconds); when its line starts, each phrase's cue and its closing
  // picture, in seconds into the card.
  frames: FRAMES.map((f, i) => ({
    id: f.id, title: f.title, chapter: f.chapter, start: STARTS[i], seconds: f.seconds,
    journey: journeyOf(i), arrive: cardRange(i)[0], depart: cardRange(i)[1], card: cardLength(i),
    voiceAt: VOICE_AT, cues: f.said.at.map((_, k) => +cueTime(i, k).toFixed(3)), exit: +(cardLength(i) - FADE - EXIT).toFixed(3),
    last: i === FRAMES.length - 1,
  })),
  facts,
  classes,
  map: { sample, bounds, centres },
  atlas3,
  cells,
  answers,
  answersShot,
  secondOpinion,
  heatmap: { genes: hm.genes, log2: hm.log2, z: hm.z, mask: hm.mask, smoothed: hm.smoothed },
};
write('build/facts.js', `// Written by scripts/prepare.mjs from web/data/; do not edit.\nwindow.VIVOME = ${JSON.stringify(VIVOME)};\n`);

// ---- 3. the Manim shot ----

write('build/answers.json', `${JSON.stringify({ classes, map: { sample, bounds, centres }, answers, shot: answersShot }, null, 1)}\n`);

// ---- 4. the scene timeline, for the score (audio/score.py) ----

write('build/timeline.json', `${JSON.stringify({ total: TOTAL, frames: VIVOME.frames.map((f) => ({ ...f, cuesAt: f.cues.map((c) => +(f.arrive + c).toFixed(3)) })) }, null, 1)}\n`);

const pending = Object.entries(facts).filter(([, f]) => !f.measured).map(([k]) => k);
console.log(`prepare: ${Object.keys(facts).length} numbers for ${FRAMES.length} scenes (${TOTAL} s)`
  + `${pending.length ? `; Pending: ${pending.join(', ')}` : ''}; built for ${manuscript.built_for.model_name}, atlas ${manuscript.built_for.atlas_version}`);
