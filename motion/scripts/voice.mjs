// Speaks the film's voice-over: each scene's `voice` line from the
// storyboard (web/js/reel-frames.js), its number slots filled from the data
// files as the page fills them, read by Kokoro-82M on this machine through
// HyperFrames' `tts` (kokoro-onnx; nothing is sent anywhere).
//
// The name is said as one word, "Vivome" (VIV-ohm, as in genome and
// proteome); written VivOME, the phonemizer spells out O, M, E. Only the
// text the voice reads changes, never the wordmark on screen. Before
// speaking, each line's phonemes are worked out as Kokoro will (through
// audio/phonemes.py) and recorded; a line where the name is not /vˈɪvoʊm/
// stops the run.
//
// Every line is spoken whole, at normal speed (SPEED), and starts VOICE_AT
// seconds after its card appears (voiceStart). Then it is timed phrase by
// phrase (phrasesOf), so the pictures can act out each phrase as it is
// said: each phrase's share of the line's phonemes, with a pause after it
// (PAUSES, by its last mark), predicts where it starts; FFmpeg's
// silencedetect finds the pauses in the speech; a pause that ends within
// NEAR seconds of a prediction is where that phrase starts.
//
// The timings the film uses are the storyboard's committed `said`, so the
// stills and the compositions never depend on a generated file. This stops
// the run when a line does not fit its card (VOICE_AT + the line + AFTER +
// FADE), or when a measured length or phrase start is more than DRIFT
// seconds from `said`, and prints the `said` lines to paste.
//
//     node scripts/voice.mjs            (after scripts/prepare.mjs)

import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { ROOT, hyperframes, toolEnv } from './hf.mjs';

export const VOICE = 'af_heart';   // Kokoro-82M's American English "Heart" voice
export const SPEED = 1;            // every line at its natural pace
const PAUSES = { '.': 0.48, '?': 0.48, '!': 0.48, ':': 0.4, ';': 0.4, ',': 0.22 };
const NEAR = 0.4;                  // how far a pause may be from its prediction
const DRIFT = 0.15;                // how far a measurement may be from `said`
const SILENCE = 'silencedetect=noise=-38dB:d=0.10';

const REPO = join(ROOT, '..');
const OUT = join(ROOT, 'build', 'audio', 'voice');
const {
  FRAMES, AFTER, FADE, VOICE_AT, cardLength, phrasesOf, slotsIn, slotText, voiceStart,
} = await import(pathToFileURL(join(REPO, 'web/js/reel-frames.js')).href);
const json = (p) => JSON.parse(readFileSync(join(REPO, p), 'utf8'));
const sources = { manifest: json('web/data/atlas_manifest.json'), manuscript: json('web/data/manuscript.json') };

export const SAY_NAME = 'Vivome';
export const NAME_PHONEMES = 'vˈɪvoʊm';
const spoken = (text) => slotsIn(text).reduce((s, slot) => s.replace(slot.token, slotText(slot, sources)), text)
  .replace(/VivOME/g, SAY_NAME);
const env = toolEnv();
const seconds = (file) => {
  const r = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', file], { env, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`ffprobe failed on ${file}`);
  return Number(r.stdout.trim());
};
// The pauses in a line: [start, end] in seconds.
const silences = (file) => {
  const r = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-af', SILENCE, '-f', 'null', '-'], { env, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`silencedetect failed on ${file}`);
  const out = [];
  let open = null;
  for (const line of r.stderr.split(/\r?\n/)) {
    const a = line.match(/silence_start: (-?[0-9.]+)/);
    if (a) open = Math.max(0, Number(a[1]));
    const b = line.match(/silence_end: ([0-9.]+)/);
    if (b && open !== null) { out.push([open, Number(b[1])]); open = null; }
  }
  if (open !== null) out.push([open, Infinity]);
  return out;
};
const r2 = (v) => Math.round(v * 100) / 100;

mkdirSync(OUT, { recursive: true });

// What Kokoro will say: each line's phonemes, and each phrase's, worked out
// before speaking.
const texts = FRAMES.map((frame) => spoken(frame.voice));
const phrases = FRAMES.map((frame) => phrasesOf(frame.voice).map(spoken));
const voicePython = process.env.HYPERFRAMES_PYTHON || env.HYPERFRAMES_PYTHON;
const listFile = join(ROOT, 'build', 'audio', 'lines.json');
writeFileSync(listFile, JSON.stringify([...texts, ...phrases.flat()]));
const run = spawnSync(voicePython, [join(ROOT, 'audio', 'phonemes.py'), listFile], { env: { ...env, PYTHONIOENCODING: 'utf-8' }, encoding: 'utf8' });
if (run.status !== 0) throw new Error(`phonemes failed: ${run.stderr}`);
const all = JSON.parse(run.stdout);
const phonemes = all.slice(0, texts.length);
let next = texts.length;
const phrasePhonemes = phrases.map((list) => list.map(() => all[next++]));
texts.forEach((text, i) => {
  if (text.includes(SAY_NAME) && !phonemes[i].includes(NAME_PHONEMES)) {
    throw new Error(`scene ${i + 1} would not say ${SAY_NAME} as one word: ${phonemes[i]}`);
  }
});
const reportFile = join(ROOT, 'build', 'audio', 'voice.json');
const before = existsSync(reportFile) ? JSON.parse(readFileSync(reportFile, 'utf8')) : { lines: [] };

async function say(text, file) {
  const code = await hyperframes(['tts', text, '--voice', VOICE, '--speed', String(SPEED), '--output', file], { stdio: 'ignore' });
  if (code !== 0 || !existsSync(file)) throw new Error(`tts failed (${code}) for: ${text}`);
  return seconds(file);
}

// Where each phrase starts, in seconds into the line's file.
function phraseStarts(i, file, length) {
  const list = phrases[i];
  if (list.length === 1) return { at: [0], how: ['start'] };
  const quiet = silences(file);
  const speechFrom = quiet.find(([a]) => a <= 0.02)?.[1] ?? 0;
  const speechTo = quiet.find(([, b]) => b === Infinity || b >= length - 0.02)?.[0] ?? length;
  const pauses = list.map((p, k) => (k === list.length - 1 ? 0 : PAUSES[p.trim().slice(-1)] ?? 0.2));
  const weight = phrasePhonemes[i].map((p) => p.replace(/[\sˈˌ.,:;?!]/g, '').length);
  const talk = Math.max(0.1, speechTo - speechFrom - pauses.reduce((s, v) => s + v, 0));
  const total = weight.reduce((s, v) => s + v, 0);
  const at = [0];
  const how = ['start'];
  let clock = speechFrom;
  for (let k = 1; k < list.length; k++) {
    clock += (talk * weight[k - 1]) / total + pauses[k - 1];
    const guess = clock;
    const hit = quiet.filter(([a, b]) => a > speechFrom && b !== Infinity && b < speechTo && Math.abs(b - guess) <= NEAR)
      .sort((x, y) => Math.abs(x[1] - guess) - Math.abs(y[1] - guess))[0];
    const start = hit ? hit[1] : guess;
    at.push(start);
    how.push(hit ? 'pause' : 'share');
    clock = start;
  }
  // A phrase with no pause before it was run on from the one before: share
  // the speech between the pauses found on either side by phonemes alone.
  for (let k = 1; k < list.length; k++) {
    if (how[k] !== 'share') continue;
    let a = k - 1;
    while (how[a] === 'share') a--;
    let b = k + 1;
    while (b < list.length && how[b] === 'share') b++;
    const to = b < list.length ? quiet.find(([, e]) => Math.abs(e - at[b]) < 1e-6)[0] : speechTo;
    const from = a === 0 ? speechFrom : at[a];
    const span = weight.slice(a, b).reduce((s, v) => s + v, 0);
    at[k] = from + ((to - from) * weight.slice(a, k).reduce((s, v) => s + v, 0)) / span;
  }
  return { at: at.map((v, k) => (k === 0 ? 0 : r2(v))), how };
}

const lines = [];
const problems = [];
for (const [i, frame] of FRAMES.entries()) {
  const text = texts[i];
  const file = join(OUT, `${String(i + 1).padStart(2, '0')}-${frame.id}.wav`);
  const kept = before.lines.find((l) => l.id === frame.id && l.text === text && l.voice === VOICE && l.speed === SPEED && existsSync(file));
  const length = kept ? seconds(file) : await say(text, file);
  const room = cardLength(i) - VOICE_AT - AFTER - FADE;
  const fits = length <= room;
  const { at, how } = phraseStarts(i, file, length);
  const said = { seconds: r2(length), at };
  const drift = Math.max(Math.abs(said.seconds - frame.said.seconds),
    ...at.map((v, k) => Math.abs(v - (frame.said.at[k] ?? Infinity))));
  if (!fits) problems.push(`scene ${i + 1} (${frame.id}): the line runs ${length.toFixed(2)} s, its card has room for ${room.toFixed(2)} s`);
  if (at.length !== frame.said.at.length || drift > DRIFT) problems.push(`scene ${i + 1} (${frame.id}): said is off by ${drift.toFixed(2)} s`);
  lines.push({
    scene: i + 1, id: frame.id, text, phonemes: phonemes[i], voice: VOICE, speed: SPEED, seconds: +length.toFixed(3),
    room: +room.toFixed(3), at: +voiceStart(i).toFixed(3), phrases: phrases[i], said, found: how,
    file: `build/audio/voice/${file.split(/[\\/]/).pop()}`, fits,
  });
  console.log(`voice ${String(i + 1).padStart(2, '0')} ${frame.id}: ${length.toFixed(2)} s of ${room.toFixed(2)}; phrases at ${at.join(', ')} (${how.join(', ')})${fits ? '' : '  RUNS LONG'}`);
}
writeFileSync(reportFile, `${JSON.stringify({ voice: VOICE, model: 'Kokoro-82M v1.0 (kokoro-onnx)', speed: SPEED, voice_at: VOICE_AT, lines }, null, 2)}\n`);
if (problems.length) {
  console.log('\nThe storyboard\'s said, as measured (web/js/reel-frames.js):');
  for (const l of lines) console.log(`  ${l.id}: said: { seconds: ${l.said.seconds}, at: [${l.said.at.join(', ')}] },`);
  throw new Error(`voice: ${problems.join('; ')}`);
}
console.log('voice: every line fits its card, and its phrases are where the storyboard says');
