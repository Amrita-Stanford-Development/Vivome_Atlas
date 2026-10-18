// Renders the storyboard's stills for the site's Motion page:
//
// 1. HyperFrames seeks the film to each scene's still time
//    (web/js/reel-frames.js, stillTime) and captures it at 1920 by 1080;
// 2. FFmpeg gives each a light grade (a touch of contrast and colour, a soft
//    vignette) and writes it as WebP, web/motion/frames/NN-<scene>.webp;
// 3. web/motion/frames/index.json, the sidecar, lists each still's time and
//    every number baked into it, with the record and the file and field it
//    came from. web/tests/reel.test.js fails when a number no longer matches
//    its record, so a stale still is caught.
//
// Run scripts/prepare.mjs and scripts/manim.mjs first; `npm run stills`
// runs all three.
//
//     node scripts/stills.mjs                    every scene
//     node scripts/stills.mjs --only methods     just these scenes (by id, comma-separated);
//                                                the other stills and their entries stay

import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { ROOT, hyperframes, toolEnv } from './hf.mjs';

const REPO = join(ROOT, '..');
const OUT = join(REPO, 'web', 'motion', 'frames');
const SHOTS = join(ROOT, '.hyperframes', 'stills');
const { FRAMES, TOTAL, frameSlots, sceneNumber, stillTime } = await import(pathToFileURL(join(REPO, 'web/js/reel-frames.js')).href);

// What the render baked in: build/facts.js, as scripts/prepare.mjs wrote it.
const factsJs = readFileSync(join(ROOT, 'build', 'facts.js'), 'utf8');
const VIVOME = JSON.parse(factsJs.slice(factsJs.indexOf('{'), factsJs.lastIndexOf('}') + 1));

const flag = process.argv.indexOf('--only');
const only = flag > 0 ? new Set(String(process.argv[flag + 1] ?? '').split(',').filter(Boolean)) : null;
for (const id of only ?? []) if (!FRAMES.some((f) => f.id === id)) throw new Error(`no scene ${id}`);
const chosen = FRAMES.map((f, i) => i).filter((i) => !only || only.has(FRAMES[i].id));
const previous = only ? JSON.parse(readFileSync(join(OUT, 'index.json'), 'utf8')).frames : [];

const times = FRAMES.map((_, i) => stillTime(i));
const code = await hyperframes(['snapshot', '.', '--at', chosen.map((i) => times[i].toFixed(3)).join(','), '--no-end', '--output', SHOTS]);
if (code !== 0) throw new Error(`hyperframes snapshot failed (${code})`);
const shots = readdirSync(SHOTS).filter((f) => /^frame-\d+-at-.*\.png$/.test(f)).sort();
if (shots.length !== chosen.length) throw new Error(`expected ${chosen.length} snapshots, found ${shots.length}`);

const env = toolEnv();
const tool = (cmd, args) => {
  const r = spawnSync(cmd, args, { env, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`${cmd} failed: ${r.stderr}`);
  return r.stdout;
};

mkdirSync(OUT, { recursive: true });
const GRADE = 'eq=contrast=1.03:saturation=1.06,vignette=angle=PI/7';
const frames = FRAMES.map((frame, i) => {
  if (!chosen.includes(i)) {
    const kept = previous.find((f) => f.id === frame.id);
    if (!kept) throw new Error(`scene ${frame.id} has no still yet: render it too`);
    return kept;
  }
  const file = `${sceneNumber(i)}-${frame.id}.webp`;
  tool('ffmpeg', ['-v', 'error', '-y', '-i', join(SHOTS, shots[chosen.indexOf(i)]), '-vf', GRADE,
    '-c:v', 'libwebp', '-quality', '84', '-compression_level', '6', join(OUT, file)]);
  const numbers = frameSlots(frame).map((slot) => {
    const fact = VIVOME.facts[slot.id];
    return { slot: slot.id, text: fact.text, record: fact.record, file: fact.file, field: fact.field };
  });
  return { scene: i + 1, id: frame.id, file, at: times[i], bytes: statSync(join(OUT, file)).size, numbers };
});

const version = (dir) => JSON.parse(readFileSync(join(ROOT, 'node_modules', dir, 'package.json'), 'utf8')).version;
const sidecar = {
  note: 'Written by motion/scripts/stills.mjs; do not edit. Each still, when in the film it was taken, and every number baked into it with its source.',
  built_for: VIVOME.built_for,
  film_seconds: TOTAL,
  rendered_with: {
    hyperframes: version('hyperframes'),
    gsap: version('gsap'),
    three: version('three'),
    ffmpeg: tool('ffmpeg', ['-version']).split('\n')[0].split(' ')[2],
  },
  frames,
};
writeFileSync(join(OUT, 'index.json'), `${JSON.stringify(sidecar, null, 2)}\n`);
const total = frames.reduce((s, f) => s + f.bytes, 0);
console.log(`stills: ${chosen.length} of ${frames.length} rendered into web/motion/frames/ (all ${(total / 1e6).toFixed(1)} MB), sidecar index.json`);
