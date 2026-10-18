// What each scene asks of the water (lib/dive.js reads it). The film is one
// continuous shot: nothing here is applied as a step at a scene's start.
// Values given as [at the scene's start, at its end] are joined across the
// scenes into one smooth curve (each boundary takes the mean of the two
// scenes' values there), so the camera and the particles never jump.
//
// fov, pitch, yaw, roll   the camera before depth narrows it, in degrees of
//            view and radians of turn
// field      the share of the site's particles shown, and how fast the water
//            rises past the camera (`rise`, 1 = background.js's own pace)
// links      the strength of the particles' molecular network
// waterline  where the surface crosses the frame, 0 (bottom) to 1 (top);
//            absent when the surface is out of sight. `surfaceBy`: the share
//            of the scene by which the waterline has finished moving.
// rain       drops on the surface between two times in the scene (seconds),
//            `rate` drops a second: rings in the gel, drawn, never heard
// wake       a scripted path: drops along [u, v] points (0..1 from the
//            bottom left) between two times in the scene
// splash     single drops: [seconds into the scene, u, v, strength, radius]
//
// One ripple field (web/js/water.js's wake) runs the whole film; a scene
// with no drops leaves it still, which is the site's still gel.

export const PLAN = {
  surface: {
    waterline: [0.8, 0.83], fov: [49, 45], pitch: [0.14, 0.11],
    field: [0.3, 0.35], rise: 0.6, rain: { from: 0, to: 8, rate: 0.75 },
  },
  unnamed: {
    waterline: [0.83, 1.45], surfaceBy: 0.55, fov: [45, 46], pitch: [0.11, -0.05],
    field: [0.4, 0.55], rise: 1.8, rain: { from: 0, to: 1.6, rate: 0.4 },
  },
  gaps: {
    fov: [46, 46], yaw: [0.07, -0.07],
    field: [0.5, 0.55], rise: 0.8, links: [0.6, 0.4],
  },
  rna: {
    fov: [44, 48], pitch: [-0.05, 0.02],
    field: [0.6, 0.7], rise: 1.4,
  },
  vivome: {
    fov: [47, 45], pitch: [0.03, -0.02],
    field: [0.7, 0.75], rise: 1, links: [1.3, 1.3],
    wake: { from: 0.4, to: 3.4, path: [[0.22, 0.6], [0.4, 0.68], [0.6, 0.68], [0.78, 0.6]] },
  },
  'built-for-gaps': {
    fov: [46, 46], yaw: [-0.06, 0.06],
    field: [0.75, 0.8], rise: 1.1,
  },
  answers: {
    fov: [46, 46],
    field: [0.55, 0.5], rise: 0.5,
  },
  'second-opinion': {
    fov: [46, 44], roll: [0.02, -0.02],
    field: [0.8, 0.85], rise: 1.3,
    wake: { from: 2.0, to: 4.8, path: [[0.09, 0.35], [0.3, 0.35], [0.53, 0.3], [0.74, 0.26]] },
  },
  'real-data': {
    fov: [46, 44], pitch: [0.04, -0.02],
    field: [0.95, 1], rise: 0.7,
  },
  methods: {
    fov: [44, 46], yaw: [0.08, -0.04],
    field: [1, 0.9], rise: 1,
  },
  atlas: {
    fov: [46, 48], pitch: [-0.06, 0.07],
    field: [0.75, 0.6], rise: 1.9,
    wake: { from: 0.8, to: 4.2, path: [[0.95, 0.9], [0.84, 0.74], [0.74, 0.62], [0.64, 0.55]] },
  },
  light: {
    waterline: [1.4, 0.15], surfaceBy: 0.55, fov: [52, 46], pitch: [0.22, 0.2],
    field: [0.5, 0.25], rise: 2.6, rain: { from: 2.9, to: 6, rate: 0.9 },
    splash: [[2.9, 0.5, 0.42, 2.4, 0.09]],
  },
};
