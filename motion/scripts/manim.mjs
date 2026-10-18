// Renders the Manim shot (manim/answers.py) for scene 7 and cuts it into
// one transparent PNG per film frame, build/manim/answers/0000.png onwards,
// which the composition shows on each seek (lib/scenes.js).
//
// Manim runs from the vivome-manim conda env (docs/setup-windows.md, "Motion
// tools"), or the Python named by VIVOME_MANIM_PYTHON. It writes a QuickTime
// file with an alpha channel (its PNG sequence skips held frames, so its
// frame numbers would not be times); FFmpeg, from the vivome-motion env,
// cuts it at the film's 30 frames a second.
//
//     node scripts/manim.mjs        (after scripts/prepare.mjs)

import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { homedir } from 'node:os';
import { delimiter, join } from 'node:path';
import { ROOT, toolEnv } from './hf.mjs';

const conda = join(homedir(), 'miniforge3', 'envs', 'vivome-manim');
const python = process.env.VIVOME_MANIM_PYTHON || join(conda, process.platform === 'win32' ? 'python.exe' : 'bin/python');
if (!existsSync(python)) throw new Error(`Manim's Python was not found at ${python}; see docs/setup-windows.md`);
if (!existsSync(join(ROOT, 'build', 'answers.json'))) throw new Error('Run scripts/prepare.mjs first');

// A conda env's DLLs (cairo, pango) are found only with its folders on PATH.
const env = toolEnv();
const pathKey = Object.keys(env).find((k) => k.toUpperCase() === 'PATH') ?? 'PATH';
if (!process.env.VIVOME_MANIM_PYTHON && process.platform === 'win32') {
  env[pathKey] = [conda, join(conda, 'Library', 'bin'), join(conda, 'Scripts'), env[pathKey]].join(delimiter);
}

const run = (cmd, args) => {
  const r = spawnSync(cmd, args, { cwd: ROOT, env, stdio: 'inherit' });
  if (r.status !== 0) throw new Error(`${cmd} ${args.slice(0, 3).join(' ')} failed (${r.status})`);
};

const media = join(ROOT, 'build', 'manim', 'media');
const frames = join(ROOT, 'build', 'manim', 'answers');
rmSync(media, { recursive: true, force: true });
rmSync(frames, { recursive: true, force: true });
mkdirSync(frames, { recursive: true });

run(python, ['-m', 'manim', 'render', '-t', '--format', 'mov', '--fps', '30', '-r', '1920,1080',
  '--media_dir', media, '--disable_caching', '--progress_bar', 'none', 'manim/answers.py', 'Answers']);
const mov = join(media, 'videos', 'answers', '1080p30', 'Answers.mov');
run('ffmpeg', ['-v', 'error', '-y', '-i', mov, '-vf', 'fps=30', '-start_number', '0', join(frames, '%04d.png')]);
console.log(`manim: ${readdirSync(frames).length} frames in build/manim/answers/`);
