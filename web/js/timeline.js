// The Workflow page's film (web/workflow.html, web/js/film.js): its chapters,
// how long each plays, and the clock maths. Pure: no DOM, so node --test
// covers it. A chapter's progress p runs 0..1 and is split evenly into its
// beats, one caption sentence each (the chapter's <p data-beat> elements).

export const CHAPTERS = [
  { id: 'open', title: 'One cell', seconds: 20, beats: 2 },
  { id: 'data', title: 'Two kinds of data', seconds: 30, beats: 3 },
  { id: 'files', title: 'What a protein file looks like', seconds: 30, beats: 3 },
  { id: 'genes', title: 'One shared list of genes', seconds: 35, beats: 3 },
  { id: 'training', title: 'How VivOME learns', seconds: 40, beats: 4 },
  { id: 'matching', title: 'Fitting the file to the shared list', seconds: 40, beats: 4 },
  { id: 'smoothing', title: 'Borrowing from similar cells', seconds: 30, beats: 3 },
  { id: 'encoder', title: 'Turning the cell into a point on the map', seconds: 35, beats: 3 },
  { id: 'probabilities', title: 'Which types is our cell close to?', seconds: 30, beats: 3 },
  { id: 'guess', title: 'The best guess', seconds: 35, beats: 3 },
  { id: 'answer', title: 'The answer, or the reason for none', seconds: 40, beats: 4 },
  { id: 'landing', title: 'Where the cell lands on the map', seconds: 35, beats: 3 },
  { id: 'results', title: 'Testing VivOME, and using it today', seconds: 45, beats: 4 },
];

export const STARTS = CHAPTERS.reduce((acc, c, i) => {
  acc.push(i === 0 ? 0 : acc[i - 1] + CHAPTERS[i - 1].seconds);
  return acc;
}, []);

export const TOTAL = STARTS[STARTS.length - 1] + CHAPTERS[CHAPTERS.length - 1].seconds;

export const SPEEDS = [0.5, 1, 1.5, 2];

const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));

// Where the clock is: the chapter, seconds into it, and its progress.
export function locate(t) {
  const time = clamp(Number.isFinite(t) ? t : 0, 0, TOTAL);
  let index = CHAPTERS.length - 1;
  for (let i = 0; i < CHAPTERS.length; i += 1) {
    if (time < STARTS[i] + CHAPTERS[i].seconds) { index = i; break; }
  }
  const local = time - STARTS[index];
  return { index, id: CHAPTERS[index].id, local, p: clamp(local / CHAPTERS[index].seconds, 0, 1) };
}

// The clock time of a chapter's progress p.
export function timeOf(index, p = 0) {
  const i = clamp(index, 0, CHAPTERS.length - 1);
  return STARTS[i] + clamp(p, 0, 1) * CHAPTERS[i].seconds;
}

// Beat b's share of its chapter's progress, [start, end).
export function beatWindow(chapter, b) {
  const n = Math.max(1, chapter.beats);
  const i = clamp(b, 0, n - 1);
  return [i / n, (i + 1) / n];
}

export function beatAt(chapter, p) {
  const n = Math.max(1, chapter.beats);
  return clamp(Math.floor(clamp(p, 0, 1) * n), 0, n - 1);
}

// On the page each beat first plays its animation, then fades the frame to
// its sentence (PLAY_SHARE of the beat's scroll animates). The scene's frame
// is held a little before the beat's end (HOLD), where the scenes finish a
// beat before cross-fading to the next. While the next beat starts, the last
// sentence fades out (FADE_OUT). Returns the beat, the scene's progress, the
// sentence to show and how strongly (0 to 1).
export const PLAY_SHARE = 0.6;
const HOLD = 0.035;
const FADE_IN = 0.1;
const FADE_OUT = 0.08;
const smooth = (x) => { const t = clamp(x, 0, 1); return t * t * (3 - 2 * t); };
export function playThenRead(chapter, p) {
  const n = Math.max(1, chapter.beats);
  const x = clamp(Number.isFinite(p) ? p : 0, 0, 1) * n;
  const beat = Math.min(n - 1, Math.floor(x));
  const u = x - beat;
  const start = beat / n;
  const hold = Math.max(start, (beat + 1) / n - HOLD);
  const scene = start + (hold - start) * Math.min(1, u / PLAY_SHARE);
  if (u >= PLAY_SHARE) return { beat, scene, hold, sentence: beat, read: smooth((u - PLAY_SHARE) / FADE_IN) };
  if (beat > 0 && u < FADE_OUT) return { beat, scene, hold, sentence: beat - 1, read: 1 - smooth(u / FADE_OUT) };
  return { beat, scene, hold, sentence: beat, read: 0 };
}

// Under reduced motion the film steps instead of animating: each beat holds
// its finished frame, the end of its window.
export function stepTarget(chapter, p) {
  return beatWindow(chapter, beatAt(chapter, p))[1];
}

export function formatClock(seconds) {
  const s = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

// The film's place in the address, so a link opens it there:
// #film&t=95.5&cell=3, with &present for the presentation view.
export function parseHash(hash) {
  const parts = String(hash ?? '').replace(/^#/, '').split('&').filter(Boolean);
  if (parts[0] !== 'film') return { film: false };
  const state = { film: true, t: 0, cell: null, present: false };
  for (const part of parts.slice(1)) {
    const [key, value] = part.split('=');
    if (key === 'present') state.present = true;
    else if (key === 't' && Number.isFinite(Number(value))) state.t = clamp(Number(value), 0, TOTAL);
    else if (key === 'cell' && /^\d+$/.test(value ?? '')) state.cell = Number(value);
  }
  return state;
}

export function formatHash({ t = 0, cell = null, present = false } = {}) {
  let hash = `#film&t=${Math.round(clamp(t, 0, TOTAL) * 10) / 10}`;
  if (Number.isInteger(cell)) hash += `&cell=${cell}`;
  if (present) hash += '&present';
  return hash;
}
