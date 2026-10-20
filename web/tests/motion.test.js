import { test } from 'node:test';
import assert from 'node:assert/strict';
import { clamp01, countText } from '../js/motion.js';

test('clamp01 stays in 0..1', () => {
  assert.equal(clamp01(-1), 0);
  assert.equal(clamp01(2), 1);
  assert.equal(clamp01(0.5), 0.5);
});

test('counting up keeps the final format and leaves non-numbers alone', () => {
  assert.equal(countText('85,233', 1), '85,233');
  assert.equal(countText('85,233', 0), '0');
  assert.match(countText('85,233', 0.5), /^\d{1,3}(,\d{3})*$/);
  assert.equal(countText('94.9%', 0), '0.0%');
  assert.match(countText('94.9%', 0.5), /^\d+\.\d%$/);
  assert.equal(countText('22', 0.999).length <= 2, true);
  for (const text of ['Pending', '0.3.0', 'VivOME v3.1', '']) assert.equal(countText(text, 0.3), text);
});

test('the film has English captions, each phrase of its voice-over at the time it is said', async () => {
  const { readFileSync: read } = await import('node:fs');
  const { FRAMES, captionsVtt, phrasesOf, voiceStart } = await import('../js/reel-frames.js');
  const html = read(new URL('../motion.html', import.meta.url), 'utf8');
  const video = html.match(/<video id="reel-video"[\s\S]*?<\/video>/)[0];
  assert.match(video, /<track kind="captions" srclang="en" label="English" src="motion\/film\/vivome\.en\.vtt">/);
  assert.doesNotMatch(video, /<track[^>]*\bdefault\b/, 'off until the viewer turns them on');
  const film = JSON.parse(read(new URL('../motion/film/index.json', import.meta.url), 'utf8'));
  const vtt = read(new URL('../motion/film/vivome.en.vtt', import.meta.url), 'utf8');
  assert.equal(vtt, captionsVtt(film.numbers), 'the committed captions are the records\' (node motion/scripts/captions.mjs)');
  assert.ok(vtt.startsWith('WEBVTT\n\n'));
  assert.doesNotMatch(vtt, /\{(ms|fact):/, 'every number filled as the film says it');
  const cues = vtt.trim().split('\n\n').slice(1);
  assert.equal(cues.length, FRAMES.reduce((n, f) => n + f.said.at.length, 0), 'one cue per phrase');
  assert.match(cues[0], /^1\n00:00:02\.300 --> 00:00:06\.360\n/);
  const last = FRAMES.length - 1;
  const end = voiceStart(last) + FRAMES[last].said.seconds;
  assert.ok(cues.at(-1).includes(`--> 00:02:${(end - 120).toFixed(3).padStart(6, '0')}`), 'the last cue ends with the last line');
  assert.equal(phrasesOf('a, b. c').length, 3);
});
