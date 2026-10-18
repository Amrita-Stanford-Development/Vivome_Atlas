// How each scene looks under water (lib/dive.js reads it). Every pair is
// [at the scene's start, at its end], eased between. The background is the
// site's white field and gel in every scene; depth (web/js/reel-frames.js)
// moves the objects, not the colour.
//
// effect     the water effect from web/js/water.js that leaves the gel's
//            colour as it is: still (the gel alone), rain or wake (rings)
// waterline  where the surface crosses the frame, 0 (bottom) to 1 (top);
//            absent when the surface is out of sight. `surfaceBy`: the share
//            of the scene by which the waterline has finished moving.
// fov, pitch, yaw, roll   the camera before depth narrows it, in degrees of
//            view and radians of turn
// field      the share of the site's particles shown, and how fast the water
//            rises past the camera (`rise`, 1 = background.js's own pace)
// frost      extra gel over the water (+ thicker, - clearer)
// cut        how the scene is entered: 'flow' (a continuous move) or 'dip'
//            (the gel clouds for a moment over the cut)
// wake       a scripted path: drops along [u, v] points (0..1 from the
//            bottom left) between two times in the scene
// splash     single drops: [seconds into the scene, u, v, strength, radius]

export const PLAN = {
  surface: {
    effect: 'rain', waterline: [0.8, 0.83], fov: [49, 45], pitch: [0.14, 0.11],
    field: [0.3, 0.35], rise: 0.6, frost: 0, cut: 'flow',
  },
  unnamed: {
    effect: 'still', waterline: [0.83, 1.45], surfaceBy: 0.55, fov: [45, 46], pitch: [0.11, -0.05],
    field: [0.4, 0.55], rise: 1.8, frost: 0, cut: 'flow',
  },
  gaps: {
    effect: 'still', fov: [46, 46], yaw: [0.07, -0.07],
    field: [0.5, 0.55], rise: 0.8, frost: 0.14, links: 0.3, cut: 'dip',
  },
  rna: {
    effect: 'still', fov: [44, 48], pitch: [-0.05, 0.02],
    field: [0.6, 0.7], rise: 1.4, frost: 0, cut: 'dip',
  },
  vivome: {
    effect: 'wake', fov: [47, 45], pitch: [0.03, -0.02],
    field: [0.7, 0.75], rise: 1, frost: 0, links: 1.6, cut: 'dip',
    wake: { from: 0.4, to: 3.4, path: [[0.22, 0.6], [0.4, 0.68], [0.6, 0.68], [0.78, 0.6]] },
  },
  'built-for-gaps': {
    effect: 'still', fov: [46, 46], yaw: [-0.06, 0.06],
    field: [0.75, 0.8], rise: 1.1, frost: -0.06, cut: 'dip',
  },
  answers: {
    effect: 'still', fov: [46, 46],
    field: [0.4, 0.4], rise: 0.5, frost: 0.06, cut: 'dip',
  },
  'second-opinion': {
    effect: 'wake', fov: [46, 44], roll: [0.02, -0.02],
    field: [0.8, 0.85], rise: 1.3, frost: 0, cut: 'dip',
    wake: { from: 2.0, to: 4.8, path: [[0.09, 0.35], [0.3, 0.35], [0.53, 0.3], [0.74, 0.26]] },
  },
  'real-data': {
    effect: 'still', fov: [46, 44], pitch: [0.04, -0.02],
    field: [0.95, 1], rise: 0.7, frost: 0.04, cut: 'dip',
  },
  methods: {
    effect: 'still', fov: [44, 46], yaw: [0.08, -0.04],
    field: [1, 0.9], rise: 1, frost: 0.02, cut: 'flow',
  },
  atlas: {
    effect: 'wake', fov: [46, 48], pitch: [-0.06, 0.07],
    field: [0.75, 0.6], rise: 1.9, frost: 0, cut: 'dip',
    wake: { from: 0.8, to: 4.2, path: [[0.95, 0.9], [0.84, 0.74], [0.74, 0.62], [0.64, 0.55]] },
  },
  light: {
    effect: 'rain', waterline: [1.4, 0.15], surfaceBy: 0.55, fov: [52, 46], pitch: [0.22, 0.2],
    field: [0.5, 0.25], rise: 2.6, frost: 0, cut: 'flow',
    splash: [[2.9, 0.5, 0.42, 2.4, 0.09]],
  },
};
