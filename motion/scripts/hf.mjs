// Runs the HyperFrames CLI pinned in motion/package.json with this PC's
// tools in reach (docs/setup-windows.md, "Motion tools"):
//
// - FFmpeg and FFprobe from the vivome-motion conda env, put first on PATH
//   (or from VIVOME_FFMPEG_DIR, a folder holding ffmpeg and ffprobe);
// - the system Chrome, unless HYPERFRAMES_BROWSER_PATH is already set;
// - the vivome-voice conda env's Python for the local voice (`tts`), unless
//   HYPERFRAMES_PYTHON is already set;
// - telemetry, update checks and skill installs off, so a render sends
//   nothing anywhere and changes nothing outside this folder.
//
//     node scripts/hf.mjs <command> [args...]      e.g. preview, lint, snapshot

import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { delimiter, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

export function toolEnv(base = process.env) {
  const env = { ...base };
  const ffmpeg = env.VIVOME_FFMPEG_DIR
    || join(homedir(), 'miniforge3', 'envs', 'vivome-motion', process.platform === 'win32' ? 'Library/bin' : 'bin');
  if (existsSync(ffmpeg)) {
    const key = Object.keys(env).find((k) => k.toUpperCase() === 'PATH') ?? 'PATH';
    env[key] = `${ffmpeg}${delimiter}${env[key] ?? ''}`;
  }
  // The local voice (Kokoro, through kokoro-onnx) runs in the vivome-voice env.
  const voice = join(homedir(), 'miniforge3', 'envs', 'vivome-voice', process.platform === 'win32' ? 'python.exe' : 'bin/python');
  if (!env.HYPERFRAMES_PYTHON && existsSync(voice)) env.HYPERFRAMES_PYTHON = voice;
  const chrome = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  if (!env.HYPERFRAMES_BROWSER_PATH && process.platform === 'win32' && existsSync(chrome)) env.HYPERFRAMES_BROWSER_PATH = chrome;
  env.HYPERFRAMES_NO_TELEMETRY = '1';
  env.HYPERFRAMES_NO_UPDATE_CHECK = '1';
  env.HYPERFRAMES_SKIP_SKILLS = '1';
  return env;
}

// The CLI, as a child process; resolves with its exit code.
export function hyperframes(args, { stdio = 'inherit' } = {}) {
  const cli = join(ROOT, 'node_modules', 'hyperframes', 'bin', 'hyperframes.mjs');
  if (!existsSync(cli)) throw new Error('HyperFrames is not installed: run npm install in motion/');
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [cli, ...args], { cwd: ROOT, env: toolEnv(), stdio });
    child.on('error', reject);
    child.on('exit', (code) => resolve(code ?? 1));
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  hyperframes(process.argv.slice(2)).then((code) => process.exit(code));
}
