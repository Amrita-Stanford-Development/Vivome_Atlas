// Renders the whole film as a draft, with its sound:
//
// 1. HyperFrames renders the picture at the composition's 1920 by 1080,
//    silent (renders/<name>-1080.mp4), unless --skip-render reuses it;
// 2. scripts/voice.mjs speaks the voice-over (Kokoro, on this machine);
//    audio/score.py writes the music. There are no sound effects;
// 3. FFmpeg mixes them (build/audio/mix.wav): each voice line placed at its
//    time and the music ducked under the voice (a sidechain compressor),
//    the whole brought to -16 LUFS;
// 4. FFmpeg writes renders/<name>.mp4 (1280 by 720, H.264 and AAC) and a
//    smaller copy for sending, renders/<name>-share.mp4 (about 20 MB);
// 5. and the site's copy for the Motion page, web/motion/film/vivome.mp4:
//    1280 by 720, H.264 and AAC, streamable (+faststart), at the best rate
//    that keeps it under SITE_LIMIT; a poster from scene 1's card,
//    web/motion/film/poster.webp; and its sidecar, web/motion/film/index.json:
//    the file's sha256, size and length, the release it was built for, and
//    every number baked into it with its source, as the stills' sidecar
//    lists them (web/tests/reel.test.js fails when one goes stale).
//
// The numbers a render bakes in are kept beside it
// (renders/<name>-1080.facts.json), so a --skip-render run describes the
// picture it reuses, not the data as it is now.
//
// Run scripts/prepare.mjs and scripts/manim.mjs first (npm run film does).
// renders/ and build/ are gitignored; web/motion/film/ is the site's.
//
//     node scripts/film.mjs [--name vivome-draft] [--skip-render]

import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { ROOT, hyperframes, toolEnv } from './hf.mjs';

const REPO = join(ROOT, '..');
const SITE = join(REPO, 'web', 'motion', 'film');
// Cloudflare Pages takes files up to 25 MiB; the site's copy stays under this.
const SITE_LIMIT = 24e6;

const arg = (flag, fallback) => { const i = process.argv.indexOf(flag); return i > 0 ? process.argv[i + 1] : fallback; };
const name = arg('--name', 'vivome-draft');
const skipRender = process.argv.includes('--skip-render');
const renders = join(ROOT, 'renders');
const master = join(renders, `${name}-1080.mp4`);
const audio = join(ROOT, 'build', 'audio');
const env = toolEnv();
const run = (cmd, args, label = cmd) => {
  const r = spawnSync(cmd, args, { cwd: ROOT, env, stdio: ['ignore', 'inherit', 'inherit'] });
  if (r.status !== 0) throw new Error(`${label} failed (${r.status})`);
};
const clock = (start) => `${((Date.now() - start) / 1000).toFixed(0)} s`;
// The film's length, from the storyboard (scripts/prepare.mjs writes it).
const TOTAL = JSON.parse(readFileSync(join(ROOT, 'build', 'timeline.json'), 'utf8')).total;

// The numbers the render bakes in: build/facts.js as prepare.mjs wrote it.
const factsJs = readFileSync(join(ROOT, 'build', 'facts.js'), 'utf8');
const VIVOME = JSON.parse(factsJs.slice(factsJs.indexOf('{'), factsJs.lastIndexOf('}') + 1));
const baked = join(renders, `${name}-1080.facts.json`);

const t0 = Date.now();
if (!skipRender || !existsSync(master)) {
  const code = await hyperframes(['render', '--output', master, '--fps', '30', '--quality', 'draft', '--quiet']);
  if (code !== 0) throw new Error(`hyperframes render failed (${code})`);
  writeFileSync(baked, `${JSON.stringify({ built_for: VIVOME.built_for, facts: VIVOME.facts }, null, 2)}\n`);
}
if (!existsSync(baked)) throw new Error(`${baked} is missing: render the film again (without --skip-render)`);
const renderTime = clock(t0);

// The voice and the score.
const t1 = Date.now();
run(process.execPath, [join(ROOT, 'scripts', 'voice.mjs')], 'voice');
const python = process.env.VIVOME_VOICE_PYTHON || join(homedir(), 'miniforge3', 'envs', 'vivome-voice', process.platform === 'win32' ? 'python.exe' : 'bin/python');
run(python, [join(ROOT, 'audio', 'score.py')], 'score');
const voice = JSON.parse(readFileSync(join(audio, 'voice.json'), 'utf8'));
const long = voice.lines.filter((l) => !l.fits);
if (long.length) console.warn(`film: voice lines that run long: ${long.map((l) => l.id).join(', ')}`);

// The mix: each voice line where its card's line starts, the music ducked
// under them.
const inputs = ['-i', join(audio, 'music.wav')];
const lines = voice.lines.map((l, k) => {
  inputs.push('-i', join(ROOT, l.file));
  const ms = Math.round(l.at * 1000);
  return `[${k + 1}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,adelay=${ms}:all=1[v${k}]`;
});
const filter = [
  ...lines,
  `${voice.lines.map((_, k) => `[v${k}]`).join('')}amix=inputs=${voice.lines.length}:normalize=0:duration=longest,apad=whole_dur=${TOTAL}[voice]`,
  '[voice]asplit=2[vo][key]',
  '[0:a][key]sidechaincompress=threshold=0.01:ratio=12:attack=20:release=500:makeup=1[ducked]',
  '[ducked]volume=0.42[m]',
  '[vo]volume=1.0[v]',
  `[m][v]amix=inputs=2:normalize=0:duration=first,atrim=0:${TOTAL},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]`,
].join(';');
const mix = join(audio, 'mix.wav');
run('ffmpeg', ['-v', 'error', '-y', ...inputs, '-filter_complex', filter, '-map', '[out]', '-ac', '2', '-c:a', 'pcm_s16le', mix], 'mix');
const mixTime = clock(t1);

// The draft at 720p, and a copy for sending.
const t2 = Date.now();
const scale = 'scale=1280:720:flags=lanczos';
const draft = join(renders, `${name}.mp4`);
const share = join(renders, `${name}-share.mp4`);
run('ffmpeg', ['-v', 'error', '-y', '-i', master, '-i', mix, '-map', '0:v', '-map', '1:a', '-vf', scale,
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
  '-movflags', '+faststart', '-shortest', draft], 'draft');
const log = join(audio, 'share2pass');
// The copy for sending: a picture rate that keeps it near 20 MB whatever
// the film's length (at most 1000 kbit/s), beside 128 kbit/s of sound.
const kbps = Math.min(1000, Math.floor((19.5e6 * 8) / TOTAL / 1000 - 128));
const shareVideo = ['-vf', scale, '-c:v', 'libx264', '-preset', 'slow', '-b:v', `${kbps}k`, '-maxrate', `${Math.round(kbps * 1.5)}k`, '-bufsize', `${kbps * 3}k`, '-pix_fmt', 'yuv420p', '-passlogfile', log];
run('ffmpeg', ['-v', 'error', '-y', '-i', master, ...shareVideo, '-pass', '1', '-an', '-f', 'mp4', process.platform === 'win32' ? 'NUL' : '/dev/null'], 'share, pass 1');
run('ffmpeg', ['-v', 'error', '-y', '-i', master, '-i', mix, '-map', '0:v', '-map', '1:a', ...shareVideo, '-pass', '2',
  '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-shortest', share], 'share, pass 2');
for (const f of [`${log}-0.log`, `${log}-0.log.mbtree`]) rmSync(f, { force: true });

// The site's copy: the best picture rate that keeps it under SITE_LIMIT,
// beside 128 kbit/s of sound, in two passes, streamable.
mkdirSync(SITE, { recursive: true });
const site = join(SITE, 'vivome.mp4');
const siteKbps = Math.min(2500, Math.floor(((SITE_LIMIT * 0.96) * 8) / TOTAL / 1000 - 128));
const siteVideo = ['-vf', scale, '-c:v', 'libx264', '-preset', 'slow', '-b:v', `${siteKbps}k`, '-maxrate', `${Math.round(siteKbps * 1.5)}k`, '-bufsize', `${siteKbps * 3}k`, '-pix_fmt', 'yuv420p', '-passlogfile', log];
run('ffmpeg', ['-v', 'error', '-y', '-i', master, ...siteVideo, '-pass', '1', '-an', '-f', 'mp4', process.platform === 'win32' ? 'NUL' : '/dev/null'], 'site, pass 1');
run('ffmpeg', ['-v', 'error', '-y', '-i', master, '-i', mix, '-map', '0:v', '-map', '1:a', ...siteVideo, '-pass', '2',
  '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-shortest', site], 'site, pass 2');
for (const f of [`${log}-0.log`, `${log}-0.log.mbtree`]) rmSync(f, { force: true });
const siteBytes = statSync(site).size;
if (siteBytes >= SITE_LIMIT) throw new Error(`the site's copy is ${siteBytes} bytes, over ${SITE_LIMIT}`);
// Its poster: scene 1's card, at its still's time, as the film shows it.
const { FRAMES, frameSlots, stillTime } = await import(pathToFileURL(join(REPO, 'web/js/reel-frames.js')).href);
run('ffmpeg', ['-v', 'error', '-y', '-ss', stillTime(0).toFixed(3), '-i', master, '-frames:v', '1', '-vf', scale,
  '-c:v', 'libwebp', '-quality', '82', '-compression_level', '6', join(SITE, 'poster.webp')], 'poster');
// Its sidecar.
const probe = (args) => {
  const r = spawnSync('ffprobe', ['-v', 'error', ...args, site], { env, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`ffprobe failed on ${site}`);
  return r.stdout.trim();
};
const [width, height] = probe(['-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0']).split(',').map(Number);
const seconds = Number(probe(['-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1']));
const { built_for: builtFor, facts } = JSON.parse(readFileSync(baked, 'utf8'));
const slots = [...new Map(FRAMES.flatMap(frameSlots).map((slot) => [slot.id, slot])).values()];
const filmSidecar = {
  note: 'Written by motion/scripts/film.mjs; do not edit. The film on the Motion page, and every number baked into it (on screen or spoken) with its source.',
  built_for: builtFor,
  file: 'vivome.mp4',
  poster: 'poster.webp',
  bytes: siteBytes,
  sha256: createHash('sha256').update(readFileSync(site)).digest('hex'),
  seconds: +seconds.toFixed(3),
  width,
  height,
  video: { codec: 'H.264', kbps: siteKbps },
  audio: { codec: 'AAC', kbps: 128 },
  numbers: slots.map((slot) => {
    const fact = facts[slot.id];
    if (!fact) throw new Error(`the render has no number for ${slot.id}: render the film again`);
    return { slot: slot.id, text: fact.text, record: fact.record, file: fact.file, field: fact.field };
  }),
};
writeFileSync(join(SITE, 'index.json'), `${JSON.stringify(filmSidecar, null, 2)}\n`);
const encodeTime = clock(t2);

const mb = (f) => `${(statSync(f).size / 1e6).toFixed(1)} MB`;
console.log(`film: ${draft} (${mb(draft)}), ${share} (${mb(share)}), the site's ${site} (${mb(site)} at ${siteKbps} kbit/s); render ${renderTime}, voice, score and mix ${mixTime}, encode ${encodeTime}`);
