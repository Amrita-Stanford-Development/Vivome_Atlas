// Scroll maths for the landing story. Pure: no DOM access, so node --test
// covers it, and web/js/field.js, web/js/reveal.js and web/js/story.js read
// one set of timings. Every progress value is 0..1.

export const clamp01 = (x) => Math.min(1, Math.max(0, x));

// Remap p into the window [a, b], clamped.
export const between = (p, a, b) => (b <= a ? (p >= b ? 1 : 0) : clamp01((p - a) / (b - a)));

// Ease in and out (smoothstep).
export const smooth = (t) => t * t * (3 - 2 * t);

// Sibling i of n gets its own window of p, overlapping its neighbours by
// `overlap` (0 = one after another, towards 1 = nearly together).
export function stagger(p, i, n, overlap = 0.5) {
  if (n <= 1) return clamp01(p);
  const width = 1 / (n - (n - 1) * overlap);
  const start = i * width * (1 - overlap);
  return between(p, start, start + width);
}

// A pinned section (a tall wrapper with a sticky child): how far through its
// pinned stretch the page has scrolled.
export const pinnedProgress = (top, height, vh) => clamp01(-top / Math.max(height - vh, 1));

// A section's text reveal: starts as its top crosses 85% of the viewport and
// completes once 70% of the section has passed that line. Always relative to
// the section itself, never to total page scroll, so changing another
// section's height moves no timing.
export const revealProgress = (top, height, vh) => clamp01((vh * 0.85 - top) / Math.max(height * 0.7, 1));

// The chapters, in page order. Each names the structure the particles form
// while it is on screen (null: open water) and which side of the screen it
// sits on (-1 left, 1 right), opposite the text. Consecutive chapters with
// the same formation share it: it holds, and moves on through its phases.
export const CHAPTERS = [
  { id: 'landing', formation: null, x: 0 },
  { id: 'twice', formation: 'cell', x: 0.95 },
  { id: 'both', formation: 'cell', x: -0.95 },
  { id: 'read', formation: 'atlas', x: 0 },
  { id: 'matrix', formation: 'atlas', x: 0.95 },
  { id: 'unsure', formation: 'atlas', x: -0.95 },
  { id: 'scored', formation: 'plate', x: 0.95 },
  { id: 'versioned', formation: 'rings', x: -0.95 },
  { id: 'evidence', formation: 'finale', x: 0 },
];

// The camera's place in the story: chapter k plus how far the viewport's
// middle has travelled through it. `tops` and `heights` are the chapter
// sections' rects, in CHAPTERS order.
export function flightAt(tops, heights, vh) {
  const mid = vh / 2;
  let k = 0;
  for (let i = 0; i < tops.length; i++) if (tops[i] <= mid) k = i;
  return k + clamp01((mid - tops[k]) / Math.max(heights[k], 1));
}

// Which formation is on screen at a flight position, how fully it is formed
// (weight), how far through its span of chapters it is (phase), and where it
// sits (x). A formation gathers over the first 30% of its first chapter and
// disperses over the last 30% of its last, so the particles return to the
// water between two different structures. The story's last structure stays.
export function formationState(flight, chapters = CHAPTERS) {
  const last = chapters.length - 1;
  const c = Math.min(Math.max(Math.floor(flight), 0), last);
  const frac = Math.min(Math.max(flight - c, 0), 1);
  const name = chapters[c].formation;
  let a = c;
  let b = c;
  while (a > 0 && chapters[a - 1].formation === name) a--;
  while (b < last && chapters[b + 1].formation === name) b++;
  const weight = name === null ? 0
    : smooth(between(flight - a, 0, 0.3)) * (b === last ? 1 : 1 - smooth(between(flight - b, 0.7, 1)));
  const next = chapters[Math.min(c + 1, last)];
  const x = next.formation === name && c < last
    ? chapters[c].x + (next.x - chapters[c].x) * smooth(between(frac, 0.55, 1))
    : chapters[c].x;
  return { name, weight, phase: clamp01((flight - a) / (b - a + 1)), x };
}

// The intro's length in ms. css/story.css runs the overlay on the same
// number (--intro-length); web/tests/motion.test.js pins the two together.
export const INTRO_MS = 4800;

// How formed the intro's particle question is at elapsed time t (ms).
export const introWeight = (t) =>
  smooth(between(t, INTRO_MS * 0.04, INTRO_MS * 0.24)) * (1 - smooth(between(t, INTRO_MS * 0.5, INTRO_MS * 0.66)));
