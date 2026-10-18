// How each scene looks under water (lib/dive.js reads it). Every pair is
// [at the scene's start, at its end], eased between.
//
// effect     the water effect from web/js/water.js: still, flow, rain, wake, ink
// waterline  where the surface crosses the frame, 0 (bottom) to 1 (top);
//            absent when the surface is out of sight. `surfaceBy`: the share
//            of the scene by which the waterline has finished moving.
// fov, pitch, yaw, roll   the camera, in degrees of view and radians of turn
// field      the share of the site's particles shown, and how fast the water
//            rises past the camera (`rise`, 1 = background.js's own pace)
// frost      extra frost over the water (+ thicker, - clearer)
// caustics   the moving net of light on the water; `pool`: light pooled on the floor
// cut        how the scene is entered: 'flow' (a continuous move) or 'dip'
//            (the water clouds for a moment over the cut)
// wake       a scripted pointer path: drops along [u, v] points (0..1 from
//            the bottom left) between two times in the scene
// splash     single drops: [seconds into the scene, u, v, strength, radius]

export const PLAN = {
  surface: {
    effect: 'rain', waterline: [0.8, 0.83], fov: [49, 43], pitch: [0.14, 0.11],
    field: [0.3, 0.35], rise: 0.6, frost: 0, caustics: 0.7, cut: 'flow',
  },
  unnamed: {
    effect: 'flow', waterline: [0.83, 1.45], surfaceBy: 0.55, fov: [43, 45], pitch: [0.11, -0.05],
    field: [0.4, 0.6], rise: 1.8, frost: 0.02, caustics: 0.5, cut: 'flow',
  },
  gaps: {
    effect: 'flow', fov: [45, 45], yaw: [0.07, -0.07],
    field: [0.6, 0.55], rise: 0.7, frost: 0.22, caustics: 0.15, links: 0.3, cut: 'dip',
  },
  rna: {
    effect: 'flow', fov: [42, 50], pitch: [-0.05, 0.02],
    field: [0.8, 0.95], rise: 1.4, frost: 0, caustics: 1.1, cut: 'dip',
  },
  vivome: {
    effect: 'ink', fov: [46, 44], pitch: [0.03, -0.02],
    field: [0.8, 0.8], rise: 1, frost: 0.03, caustics: 0.5, links: 1.6, cut: 'dip',
  },
  'built-for-gaps': {
    effect: 'flow', fov: [45, 45], yaw: [-0.06, 0.06],
    field: [0.7, 0.7], rise: 0.9, frost: -0.04, caustics: 0.6, cut: 'dip',
  },
  answers: {
    effect: 'still', fov: [45, 45],
    field: [0.3, 0.3], rise: 0.4, frost: 0.08, caustics: 0.2, cut: 'dip',
  },
  'second-opinion': {
    effect: 'ink', fov: [45, 43], roll: [0.02, -0.02],
    field: [0.6, 0.7], rise: 1.2, frost: 0, caustics: 0.5, cut: 'dip',
  },
  'real-data': {
    effect: 'flow', fov: [44, 41], pitch: [0.04, -0.02],
    field: [1, 1], rise: 0.6, frost: -0.02, caustics: 1.3, pool: 1, cut: 'dip',
  },
  methods: {
    effect: 'flow', fov: [41, 44], yaw: [0.08, -0.04],
    field: [0.9, 0.85], rise: 1, frost: 0, caustics: 1, pool: 0.5, cut: 'flow',
  },
  atlas: {
    effect: 'wake', fov: [46, 48], pitch: [-0.06, 0.07],
    field: [0.7, 0.6], rise: 1.9, frost: 0, caustics: 0.8, cut: 'dip',
    wake: { from: 0.8, to: 4.2, path: [[0.95, 0.9], [0.84, 0.74], [0.74, 0.62], [0.64, 0.55]] },
  },
  light: {
    effect: 'rain', waterline: [1.4, 0.15], surfaceBy: 0.55, fov: [52, 44], pitch: [0.22, 0.2],
    field: [0.5, 0.2], rise: 2.6, frost: 0, caustics: 1, cut: 'flow',
    splash: [[2.9, 0.5, 0.42, 2.4, 0.09]],
  },
};
