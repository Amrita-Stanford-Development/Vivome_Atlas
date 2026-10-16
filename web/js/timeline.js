// The Workflow page's film (web/workflow.html, web/js/film.js): its chapters,
// how long each plays, and the clock maths. Pure: no DOM, so node --test
// covers it. A chapter's progress p runs 0..1 and is split evenly into its
// beats, one caption sentence each (the chapter's <p data-beat> elements).

export const CHAPTERS = [
  { id: 'open', title: 'One cell', seconds: 20, beats: 2 },
  { id: 'data', title: 'Two kinds of data', seconds: 30, beats: 3 },
  { id: 'files', title: 'What the files look like', seconds: 30, beats: 3 },
  { id: 'genes', title: 'One vocabulary of genes', seconds: 35, beats: 3 },
  { id: 'training', title: 'Trained on RNA only', seconds: 40, beats: 4 },
  { id: 'upload', title: 'An upload arrives', seconds: 30, beats: 3 },
  { id: 'matching', title: 'Matching and the mask', seconds: 30, beats: 3 },
  { id: 'smoothing', title: 'Smoothing on the upload’s own neighbours', seconds: 30, beats: 3 },
  { id: 'encoder', title: 'The encoder pass', seconds: 35, beats: 3 },
  { id: 'probabilities', title: 'From a point to probabilities', seconds: 30, beats: 3 },
  { id: 'guess', title: 'The best guess', seconds: 40, beats: 4 },
  { id: 'answer', title: 'The answer, or the reason', seconds: 40, beats: 4 },
  { id: 'landing', title: 'Where the cell lands', seconds: 35, beats: 3 },
  { id: 'results', title: 'How the results were calculated', seconds: 45, beats: 4 },
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
