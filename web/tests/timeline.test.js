import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  CHAPTERS, PLAY_SHARE, STARTS, TOTAL, beatAt, beatWindow, formatClock, formatHash, locate, parseHash, playThenRead,
  stepTarget, timeOf,
} from '../js/timeline.js';

test('the chapters add up to the film and start where the last ends', () => {
  assert.equal(TOTAL, CHAPTERS.reduce((s, c) => s + c.seconds, 0));
  assert.equal(STARTS[0], 0);
  for (let i = 1; i < CHAPTERS.length; i += 1) assert.equal(STARTS[i], STARTS[i - 1] + CHAPTERS[i - 1].seconds);
  assert.equal(new Set(CHAPTERS.map((c) => c.id)).size, CHAPTERS.length, 'chapter ids are unique');
  assert.ok(TOTAL > 6 * 60 && TOTAL < 9 * 60, 'about seven to eight minutes');
});

test('locate is clamped, monotonic and inverts timeOf', () => {
  assert.deepEqual(locate(-5), { index: 0, id: CHAPTERS[0].id, local: 0, p: 0 });
  const end = locate(TOTAL + 10);
  assert.equal(end.index, CHAPTERS.length - 1);
  assert.equal(end.p, 1);
  let last = -1;
  for (let t = 0; t <= TOTAL; t += 1.7) {
    const where = locate(t);
    const position = where.index + where.p;
    assert.ok(position >= last - 1e-9, `not monotonic at ${t}`);
    last = position;
    assert.ok(Math.abs(timeOf(where.index, where.p) - t) < 1e-9);
  }
  CHAPTERS.forEach((_, i) => assert.equal(locate(STARTS[i]).index, i));
  assert.equal(locate(Number.NaN).index, 0);
});

test('beats tile each chapter, and reduced motion holds each beat’s end', () => {
  for (const chapter of CHAPTERS) {
    let edge = 0;
    for (let b = 0; b < chapter.beats; b += 1) {
      const [a, z] = beatWindow(chapter, b);
      assert.equal(a, edge);
      edge = z;
    }
    assert.equal(edge, 1);
    assert.equal(beatAt(chapter, 0), 0);
    assert.equal(beatAt(chapter, 1), chapter.beats - 1);
    for (let p = 0; p <= 1; p += 0.05) {
      const target = stepTarget(chapter, p);
      assert.ok(target >= p - 1e-9 && target <= 1);
      assert.equal(target, beatWindow(chapter, beatAt(chapter, p))[1]);
    }
  }
});

test('each beat plays its animation, then shows its sentence over the held frame', () => {
  for (const chapter of CHAPTERS) {
    let last = -1;
    for (let p = 0; p <= 1; p += 0.002) {
      const at = playThenRead(chapter, p);
      const [a, z] = beatWindow(chapter, at.beat);
      assert.ok(at.scene >= a - 1e-9 && at.scene <= z, 'the scene stays in its beat');
      assert.ok(at.scene >= last - 1e-9, 'the scene never runs backwards');
      last = at.scene;
      assert.ok(at.read >= 0 && at.read <= 1);
      assert.ok(at.sentence === at.beat || at.sentence === at.beat - 1);
    }
    for (let b = 0; b < chapter.beats; b += 1) {
      const [a, z] = beatWindow(chapter, b);
      const playing = playThenRead(chapter, a + (z - a) * PLAY_SHARE * 0.5);
      assert.equal(playing.read, 0, 'no sentence while the animation plays');
      const reading = playThenRead(chapter, a + (z - a) * 0.95);
      assert.equal(reading.read, 1);
      assert.equal(reading.sentence, b);
      assert.equal(reading.scene, reading.hold, 'the frame holds while the sentence shows');
    }
    assert.equal(playThenRead(chapter, 1).read, 1, 'the last sentence stays');
  }
});

test('the clock reads minutes and seconds', () => {
  assert.equal(formatClock(0), '0:00');
  assert.equal(formatClock(65.9), '1:05');
  assert.equal(formatClock(-3), '0:00');
  assert.equal(formatClock(TOTAL), `${Math.floor(TOTAL / 60)}:${String(TOTAL % 60).padStart(2, '0')}`);
});

test('the address keeps the film’s place, and nothing else opens it', () => {
  assert.deepEqual(parseHash('#film&t=95.5&cell=3&present'), { film: true, t: 95.5, cell: 3, present: true });
  assert.deepEqual(parseHash('#film'), { film: true, t: 0, cell: null, present: false });
  assert.deepEqual(parseHash('#genes'), { film: false });
  assert.deepEqual(parseHash(''), { film: false });
  assert.equal(parseHash('#film&t=99999').t, TOTAL);
  assert.equal(parseHash('#film&cell=<script>').cell, null);
  const state = { t: 123.44, cell: 7, present: true };
  const back = parseHash(formatHash(state));
  assert.deepEqual(back, { film: true, t: 123.4, cell: 7, present: true });
  assert.equal(formatHash({ t: 1 }), '#film&t=1');
});
