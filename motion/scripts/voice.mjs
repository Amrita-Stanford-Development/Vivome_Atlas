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
// Each line must fit its scene, starting LEAD seconds in and ending TAIL
// seconds before the next. A line that runs long is spoken a little faster
// (up to MAX_SPEED), then given shorter pauses around it (TIGHT_LEAD and
// TIGHT_TAIL), never reworded; one that still does not fit is reported, and
// the report in build/audio/voice.json marks it.
//
//     node scripts/voice.mjs            (after scripts/prepare.mjs)

import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { ROOT, hyperframes, toolEnv } from './hf.mjs';

export const VOICE = 'af_heart';   // Kokoro-82M's American English "Heart" voice
const LEAD = 0.45;                 // seconds into the scene before the line starts
const TAIL = 0.3;                  // seconds of quiet before the next scene
const MAX_SPEED = 1.2;             // faster than this starts to sound hurried
const TIGHT_LEAD = 0.2;            // the shortest pauses a long line may get
const TIGHT_TAIL = 0.1;

const REPO = join(ROOT, '..');
const OUT = join(ROOT, 'build', 'audio', 'voice');
const { FRAMES, STARTS, slotsIn, slotText } = await import(pathToFileURL(join(REPO, 'web/js/reel-frames.js')).href);
const json = (p) => JSON.parse(readFileSync(join(REPO, p), 'utf8'));
const sources = { manifest: json('web/data/atlas_manifest.json'), manuscript: json('web/data/manuscript.json') };

export const SAY_NAME = 'Vivome';
export const NAME_PHONEMES = 'vˈɪvoʊm';
const spoken = (text) => slotsIn(text).reduce((s, slot) => s.replace(slot.token, slotText(slot, sources)), text)
  .replace(/VivOME/g, SAY_NAME);
const seconds = (file) => {
  const r = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', file], { env: toolEnv(), encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`ffprobe failed on ${file}`);
  return Number(r.stdout.trim());
};

mkdirSync(OUT, { recursive: true });

// What Kokoro will say: each line's phonemes, worked out before speaking.
const texts = FRAMES.map((frame) => spoken(frame.voice));
const voicePython = process.env.HYPERFRAMES_PYTHON || toolEnv().HYPERFRAMES_PYTHON;
const listFile = join(ROOT, 'build', 'audio', 'lines.json');
writeFileSync(listFile, JSON.stringify(texts));
const said = spawnSync(voicePython, [join(ROOT, 'audio', 'phonemes.py'), listFile], { env: { ...toolEnv(), PYTHONIOENCODING: 'utf-8' }, encoding: 'utf8' });
if (said.status !== 0) throw new Error(`phonemes failed: ${said.stderr}`);
const phonemes = JSON.parse(said.stdout);
texts.forEach((text, i) => {
  if (text.includes(SAY_NAME) && !phonemes[i].includes(NAME_PHONEMES)) {
    throw new Error(`scene ${i + 1} would not say ${SAY_NAME} as one word: ${phonemes[i]}`);
  }
});
const reportFile = join(ROOT, 'build', 'audio', 'voice.json');
const before = existsSync(reportFile) ? JSON.parse(readFileSync(reportFile, 'utf8')) : { lines: [] };

async function say(text, speed, file) {
  const code = await hyperframes(['tts', text, '--voice', VOICE, '--speed', String(speed), '--output', file], { stdio: 'ignore' });
  if (code !== 0 || !existsSync(file)) throw new Error(`tts failed (${code}) for: ${text}`);
  return seconds(file);
}

const lines = [];
for (const [i, frame] of FRAMES.entries()) {
  const text = texts[i];
  const file = join(OUT, `${String(i + 1).padStart(2, '0')}-${frame.id}.wav`);
  const budget = frame.seconds - LEAD - TAIL;
  const kept = before.lines.find((l) => l.id === frame.id && l.text === text && l.voice === VOICE && existsSync(file));
  let speed = kept?.speed ?? 1;
  let length = kept ? seconds(file) : await say(text, speed, file);
  // Faster first (twice at most), then shorter pauses.
  for (let tries = 0; !kept && length > budget && speed < MAX_SPEED && tries < 2; tries++) {
    speed = Math.min(MAX_SPEED, Math.ceil((length / budget) * speed * 100 * 1.02) / 100);
    length = await say(text, speed, file);
  }
  const tight = length > budget;
  const lead = tight ? TIGHT_LEAD : LEAD;
  const room = tight ? frame.seconds - TIGHT_LEAD - TIGHT_TAIL : budget;
  const fits = length <= room;
  lines.push({
    scene: i + 1, id: frame.id, text, phonemes: phonemes[i], voice: VOICE, speed, seconds: +length.toFixed(3), room: +room.toFixed(3),
    pauses: tight ? 'short' : 'normal', at: +(STARTS[i] + lead).toFixed(3), file: `build/audio/voice/${file.split(/[\\/]/).pop()}`, fits,
  });
  console.log(`voice ${String(i + 1).padStart(2, '0')} ${frame.id}: ${length.toFixed(2)} s of ${room.toFixed(2)} at speed ${speed}${tight ? ', short pauses' : ''}${fits ? '' : '  RUNS LONG'}`);
}
writeFileSync(reportFile, `${JSON.stringify({ voice: VOICE, model: 'Kokoro-82M v1.0 (kokoro-onnx)', lead: LEAD, tail: TAIL, lines }, null, 2)}\n`);
const long = lines.filter((l) => !l.fits);
console.log(long.length ? `voice: ${long.length} line(s) run long: ${long.map((l) => l.id).join(', ')}` : 'voice: every line fits its scene');
