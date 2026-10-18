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
//    smaller copy for sending, renders/<name>-share.mp4 (about 17 MB).
//
// Run scripts/prepare.mjs and scripts/manim.mjs first (npm run film does).
// Everything it writes is gitignored; nothing goes on the site.
//
//     node scripts/film.mjs [--name vivome-draft] [--skip-render]

import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, rmSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { ROOT, hyperframes, toolEnv } from './hf.mjs';

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

const t0 = Date.now();
if (!skipRender || !existsSync(master)) {
  const code = await hyperframes(['render', '--output', master, '--fps', '30', '--quality', 'draft', '--quiet']);
  if (code !== 0) throw new Error(`hyperframes render failed (${code})`);
}
const renderTime = clock(t0);

// The voice and the score.
const t1 = Date.now();
run(process.execPath, [join(ROOT, 'scripts', 'voice.mjs')], 'voice');
const python = process.env.VIVOME_VOICE_PYTHON || join(homedir(), 'miniforge3', 'envs', 'vivome-voice', process.platform === 'win32' ? 'python.exe' : 'bin/python');
run(python, [join(ROOT, 'audio', 'score.py')], 'score');
const voice = JSON.parse(readFileSync(join(audio, 'voice.json'), 'utf8'));
const long = voice.lines.filter((l) => !l.fits);
if (long.length) console.warn(`film: voice lines that run long: ${long.map((l) => l.id).join(', ')}`);

// The mix: voice lines at their times, the music ducked under them.
const inputs = ['-i', join(audio, 'music.wav')];
const lines = voice.lines.map((l, k) => {
  inputs.push('-i', join(ROOT, l.file));
  const ms = Math.round(l.at * 1000);
  return `[${k + 1}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,adelay=${ms}:all=1[v${k}]`;
});
const filter = [
  ...lines,
  `${voice.lines.map((_, k) => `[v${k}]`).join('')}amix=inputs=${voice.lines.length}:normalize=0:duration=longest,apad=whole_dur=120[voice]`,
  '[voice]asplit=2[vo][key]',
  '[0:a][key]sidechaincompress=threshold=0.01:ratio=12:attack=20:release=500:makeup=1[ducked]',
  '[ducked]volume=0.42[m]',
  '[vo]volume=1.0[v]',
  '[m][v]amix=inputs=2:normalize=0:duration=first,atrim=0:120,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]',
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
const shareVideo = ['-vf', scale, '-c:v', 'libx264', '-preset', 'slow', '-b:v', '1000k', '-maxrate', '1500k', '-bufsize', '3000k', '-pix_fmt', 'yuv420p', '-passlogfile', log];
run('ffmpeg', ['-v', 'error', '-y', '-i', master, ...shareVideo, '-pass', '1', '-an', '-f', 'mp4', process.platform === 'win32' ? 'NUL' : '/dev/null'], 'share, pass 1');
run('ffmpeg', ['-v', 'error', '-y', '-i', master, '-i', mix, '-map', '0:v', '-map', '1:a', ...shareVideo, '-pass', '2',
  '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-shortest', share], 'share, pass 2');
for (const f of [`${log}-0.log`, `${log}-0.log.mbtree`]) rmSync(f, { force: true });
const encodeTime = clock(t2);

const mb = (f) => `${(statSync(f).size / 1e6).toFixed(1)} MB`;
console.log(`film: ${draft} (${mb(draft)}), ${share} (${mb(share)}); render ${renderTime}, voice, score and mix ${mixTime}, encode ${encodeTime}`);
