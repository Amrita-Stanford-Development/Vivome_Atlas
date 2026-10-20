// Writes the film's captions for the Motion page: web/motion/film/vivome.en.vtt,
// each phrase of the voice-over at the time it is said (web/js/reel-frames.js,
// captionsVtt), with the numbers the film says (web/motion/film/index.json).
// Run after scripts/film.mjs; web/tests/motion.test.js fails when they differ.
//
//     node scripts/captions.mjs

import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { ROOT } from './hf.mjs';

const REPO = join(ROOT, '..');
const FILM = join(REPO, 'web', 'motion', 'film');
const { captionsVtt } = await import(pathToFileURL(join(REPO, 'web/js/reel-frames.js')).href);
const film = JSON.parse(readFileSync(join(FILM, 'index.json'), 'utf8'));
writeFileSync(join(FILM, 'vivome.en.vtt'), captionsVtt(film.numbers));
console.log(`captions: ${join(FILM, 'vivome.en.vtt')}`);
