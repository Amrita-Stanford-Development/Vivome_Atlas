// Where each scene is in the film's water, the camera's journey to it, and
// what it asks of the water (lib/dive.js and lib/camera.js read it).
//
// go      the journey to this scene from the one before, [dx, dy] in water
//         units (y down); the first scene has its place, `at`, and the
//         descent through the surface to it, `opening` (where the camera
//         starts, from that place). The directions vary from journey to
//         journey; the last rises through the surface.
// field   the share of the site's particles shown while the scene's card
//         is on; `links` is the strength of their network; `rise`, how fast
//         the water rises past the camera (1 = background.js's own pace).
//         Each holds while the card is on and eases to the next scene's
//         value on the journey there.
// rain    drops on the surface between two times in the card (seconds
//         into it), `rate` drops a second: rings in the gel, drawn, never
//         heard
// wake    a scripted path: drops along [u, v] points (0..1 from the
//         bottom left) between two times in the card
// splash  single drops: [seconds into the card, u, v, strength, radius]
//
// One ripple field (web/js/water.js's wake) runs the whole film; drops
// fall only while a card is on, so the rings never ride a moving camera.

// The water's surface: a level of the world (`y`) over a stretch of it
// (`x`). One lies over the first scenes, which the camera descends from;
// one over the last, which it rises to. The camera passes from one stretch
// to the other far below both, where neither is in sight.
export const SURFACES = [
  { y: -3.9, x: [-Infinity, 17] },
  { y: 21.8, x: [17, Infinity] },
];

export const PLAN = {
  surface: {
    at: [0, 0], opening: [0, -5.5],
    field: 0.33, rise: 0.6, rain: { from: 0, to: 8, rate: 0.75 },
  },
  unnamed: { go: [0, 6], field: 0.48, rise: 1.2 },
  gaps: { go: [8, 0], field: 0.52, rise: 0.8, links: 0.5 },
  rna: { go: [6, 5], field: 0.65, rise: 1.2 },
  vivome: {
    go: [0, 6], field: 0.72, rise: 1, links: 1.3,
    wake: { from: 0.4, to: 3.4, path: [[0.22, 0.6], [0.4, 0.68], [0.6, 0.68], [0.78, 0.6]] },
  },
  'built-for-gaps': { go: [-6, 5], field: 0.78, rise: 1.1 },
  answers: { go: [-8, 0], field: 0.52, rise: 0.5 },
  'second-opinion': {
    go: [6, 5], field: 0.82, rise: 1.2,
    wake: { from: 0.3, to: 2.8, path: [[0.09, 0.35], [0.3, 0.35], [0.53, 0.3], [0.74, 0.26]] },
  },
  'real-data': { go: [0, 6], field: 0.97, rise: 0.7 },
  methods: { go: [8, 0], field: 0.95, rise: 1 },
  atlas: {
    go: [6, -5], field: 0.68, rise: 1.6,
    wake: { from: 3.86, to: 5.4, path: [[0.42, 0.78], [0.52, 0.64], [0.62, 0.52], [0.7, 0.44]] },
  },
  light: {
    go: [0, -9.5], field: 0.38, rise: 2.2, rain: { from: 1.4, to: 7.5, rate: 0.9 },
    splash: [[0.3, 0.5, 0.1, 2.0, 0.09]],
  },
};

// Where each card's closing picture ends and the next card's opening
// picture begins, in the frame's pixels: the two scenes draw the same thing
// in the same spot on either side of the journey, so the eye carries it
// across (lib/scenes.js draws them; `spread` is a band's half-width).
export const RHYMES = [
  { from: 'surface', to: 'unnamed', close: [1500, 330], open: [1500, 330], what: 'the protein cell' },
  { from: 'unnamed', to: 'gaps', close: [1500, 560], open: [1500, 560], what: 'the cell\'s column of proteins' },
  { from: 'gaps', to: 'rna', close: [1700, 700], open: [1700, 700], what: 'the measured values, gathered as dots' },
  { from: 'rna', to: 'vivome', close: [1240, 170], open: [1240, 170], spread: 280, what: 'a band of the atlas\'s cells' },
  { from: 'vivome', to: 'built-for-gaps', close: [1330, 1014], open: [1330, 1014], what: 'a row of tiles, under the card' },
  { from: 'built-for-gaps', to: 'answers', close: [1000, 640], open: [1000, 640], what: 'the encoders\' merged points' },
  { from: 'answers', to: 'second-opinion', close: [170, 810], open: [170, 810], spread: 110, what: 'two strokes, the currents\' starts' },
  { from: 'second-opinion', to: 'real-data', close: [751, 561], open: [751, 561], what: 'a block of a hundred particles' },
  { from: 'real-data', to: 'methods', close: [560, 870], open: [560, 870], spread: 300, what: 'a row of dots, under the results' },
  { from: 'methods', to: 'atlas', close: [915, 268], open: [915, 268], what: 'a file' },
  { from: 'atlas', to: 'light', close: [1230, 165], open: [1230, 165], spread: 120, what: 'a few landed cells, rising' },
];
