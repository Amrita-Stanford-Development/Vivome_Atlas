// Where each scene sits in the film's world, how the camera moves while it
// plays, and what it asks of the water (lib/dive.js and lib/camera.js read
// it). The film is one continuous shot: nothing here is applied as a step
// at a scene's start.
//
// at      the scene's plane: [x, y, z] in the world (the scenes' own pixels;
//         z is depth). The camera travels from plane to plane, so the
//         outgoing cards leave and the incoming arrive with it.
// move    the camera while the scene plays, as offsets from `at`:
//         from and to are [dx, dy, dz, yaw, pitch, roll] (pixels and
//         degrees; +dz is a push-in), eased; `until`, seconds into the
//         scene, ends the move early so the shot can hold.
// field   the share of the site's particles shown, and how fast the water
//         rises past the camera (`rise`, 1 = background.js's own pace);
//         `links` is the strength of their network. Pairs are [start, end],
//         joined across scenes into one smooth curve.
// rain    drops on the surface between two times in the scene (seconds),
//         `rate` drops a second: rings in the gel, drawn, never heard
// wake    a scripted path: drops along [u, v] points (0..1 from the
//         bottom left) between two times in the scene
// splash  single drops: [seconds into the scene, u, v, strength, radius]
//
// One ripple field (web/js/water.js's wake) runs the whole film; a scene
// with no drops leaves it still, which is the site's still gel.

// The water's surface: a level of the world (`y`, in the scenes' pixels)
// over a stretch of it (`x`). One lies over the first scenes, which the
// camera sinks from; one over the last, which it rises to. Where the camera
// is deep, the surface is far above the frame and is not drawn.
export const SURFACES = [
  { y: -346, x: [-Infinity, 14500] },
  { y: 4078, x: [14500, Infinity] },
];

export const PLAN = {
  surface: {
    at: [0, 0, 0], move: { from: [0, 40, -60], to: [40, 0, 60] },
    field: [0.3, 0.35], rise: 0.6, rain: { from: 0, to: 8, rate: 0.75 },
  },
  unnamed: {
    at: [200, 1500, 400], move: { from: [-70, -30, -50, -2], to: [70, 30, 40, 2] },
    field: [0.4, 0.55], rise: 1.8, rain: { from: 0, to: 1.0, rate: 0.4 },
  },
  gaps: {
    at: [2600, 1650, 700], move: { from: [-60, 0, -40, 1.2], to: [60, 0, 40, -1.2] },
    field: [0.5, 0.55], rise: 0.8, links: [0.6, 0.4],
  },
  rna: {
    at: [5000, 1800, 1000], move: { from: [-30, 20, -60, -2], to: [30, -10, 30, 2] },
    field: [0.6, 0.7], rise: 1.4,
  },
  vivome: {
    at: [5300, 3400, 1300], move: { from: [-70, -60, -40, -3], to: [70, 40, 70, 3] },
    field: [0.7, 0.75], rise: 1, links: [1.3, 1.3],
    wake: { from: 0.4, to: 3.4, path: [[0.22, 0.6], [0.4, 0.68], [0.6, 0.68], [0.78, 0.6]] },
  },
  'built-for-gaps': {
    at: [7700, 3600, 1600], move: { from: [-50, 0, -50, 1.2], to: [50, 0, 30, -1.2] },
    field: [0.75, 0.8], rise: 1.1,
  },
  answers: {
    at: [8000, 5200, 2000], move: { from: [0, 0, -70, -1.5], to: [0, 0, 10, 1.5] },
    field: [0.55, 0.5], rise: 0.5,
  },
  'second-opinion': {
    at: [10400, 5400, 2300], move: { from: [-40, 0, -60, 1], to: [40, 0, 10, -1] },
    field: [0.8, 0.85], rise: 1.3,
    wake: { from: 2.0, to: 4.8, path: [[0.09, 0.35], [0.3, 0.35], [0.53, 0.3], [0.74, 0.26]] },
  },
  'real-data': {
    at: [10700, 7000, 2800], move: { from: [0, -60, -60, -1], to: [0, 0, 80, 1] },
    field: [0.95, 1], rise: 0.7,
  },
  methods: {
    at: [13100, 7100, 3000], move: { from: [-60, 0, -50, -1.5], to: [60, 0, 20, 1.5] },
    field: [1, 0.9], rise: 1,
  },
  atlas: {
    at: [15900, 6100, 2400], move: { from: [0, 80, -40, 2], to: [0, -40, 60, -2] },
    field: [0.75, 0.6], rise: 1.9,
    wake: { from: 0.8, to: 4.2, path: [[0.95, 0.9], [0.84, 0.74], [0.74, 0.62], [0.64, 0.55]] },
  },
  light: {
    at: [16200, 3700, 2000], move: { from: [0, 968, -40], to: [0, 0, 0], until: 3.6 },
    field: [0.5, 0.25], rise: 2.6, rain: { from: 2.7, to: 6, rate: 0.9 },
    splash: [[2.7, 0.5, 0.42, 2.4, 0.09]],
  },
};
