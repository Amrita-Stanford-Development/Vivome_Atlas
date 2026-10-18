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
const REPO = join(ROOT, '..');
const site = (p) => join(REPO, p);
const load = (p) => import(pathToFileURL(site(p)).href);

const { FRAMES, STARTS, TOTAL, CHAPTERS, frameSlots, slotText, slotMeasured, slotSource } = await load('web/js/reel-frames.js');
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

const facts = {};
for (const frame of FRAMES) {
  for (const slot of frameSlots(frame)) {
    facts[slot.id] = { text: slotText(slot, sources), measured: slotMeasured(slot, sources), ...slotSource(slot, sources) };
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

// Where the answers shot draws its map, and when each cell's answer
// starts: Manim draws the map and the sets, the composition the words.
const answersFrame = FRAMES.find((f) => f.id === 'answers');
// The shot looks closely at the types the four cells' sets name.
const involved = new Set(answers.flatMap((a) => a.types));
const near = sample.filter((p) => involved.has(p[2]));
const nx = near.map((p) => p[0]).sort((a, b) => a - b);
const ny = near.map((p) => p[1]).sort((a, b) => a - b);
const pad = (lo, hi) => [lo - (hi - lo) * 0.08, hi + (hi - lo) * 0.08];
const answersShot = {
  box: [90, 230, 1130, 1040],
  bounds: [...pad(q(nx, 0.02), q(nx, 0.98)), ...pad(q(ny, 0.02), q(ny, 0.98))],
  seconds: answersFrame.seconds,
  fps: 30,
  starts: answers.map((_, k) => +(1.6 + k * 2.5).toFixed(2)),
};

const hm = w.trace.heatmap;
const VIVOME = {
  built_for: manuscript.built_for,
  total: TOTAL,
  chapters: CHAPTERS,
  frames: FRAMES.map((f, i) => ({ id: f.id, title: f.title, chapter: f.chapter, start: STARTS[i], seconds: f.seconds, depth: f.depth })),
  facts,
  classes,
  map: { sample, bounds, centres },
  cells,
  answers,
  answersShot,
  heatmap: { genes: hm.genes, log2: hm.log2, z: hm.z, mask: hm.mask, smoothed: hm.smoothed },
};
write('build/facts.js', `// Written by scripts/prepare.mjs from web/data/; do not edit.\nwindow.VIVOME = ${JSON.stringify(VIVOME)};\n`);

// ---- 3. the Manim shot ----

write('build/answers.json', `${JSON.stringify({ classes, map: { sample, bounds, centres }, answers, shot: answersShot }, null, 1)}\n`);

const pending = Object.entries(facts).filter(([, f]) => !f.measured).map(([k]) => k);
console.log(`prepare: ${Object.keys(facts).length} numbers for ${FRAMES.length} scenes (${TOTAL} s)`
  + `${pending.length ? `; Pending: ${pending.join(', ')}` : ''}; built for ${manuscript.built_for.model_name}, atlas ${manuscript.built_for.atlas_version}`);
