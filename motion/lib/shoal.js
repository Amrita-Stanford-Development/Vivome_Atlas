// The film's water: the site's cells and threads (web/js/biocells.js), each
// at a fixed depth and a constant size, seen from a camera that travels
// sideways and up and down through them but never forward. As it travels,
// each object moves across the frame by the camera's move over its depth,
// so the near ones pass faster than the far (parallax); none grows, none
// shrinks, none is recycled in view. An object that leaves one side of the
// frame comes back on the other only once it is wholly out of sight.
//
// The objects themselves are the site's: the same meshes, materials and
// shaders, through biocells.js's specimen(). What is forked from it, with
// the line numbers it was taken from, is the WATER table (how many of each
// kind, and their sizes; web/tests/reel.test.js keeps the two copies the
// same) and the placement, rewritten in closed form from biocells.js's
// createBioLayer update loop (lines 1084 to 1135): there it steps each
// object forward per frame and recycles it; here every position is a
// function of the camera's place and the time, so any frame renders the
// same on its own.
//
// seedShoal() and placeAt() are pure, for node --test. createShoal() needs
// three.js and the vendored biocells.js, which lib/dive.js passes in.

import { ASPECT, TAN } from './camera.js';

// ---- from web/js/biocells.js, unchanged ----

const UM = 0.14;   // scene units per micrometre
const NM = 0.24;   // scene units per nanometre: DNA is magnified thousands of times

// How many of each kind drift in the water, how large they are drawn
// (`scale` per micrometre or nanometre, or `size`: the object's width in
// scene units), how fast they turn (radians a second) and how far into the
// water they reach (1 = the whole depth). Real blood has about 600 red cells
// to 40 platelets to one white cell; the water keeps that order, not the
// ratio, and draws platelets 1.5 times larger so they stay visible. The
// molecules are drawn hundreds to thousands of times larger than they would
// be beside the cells, and, thin as they are, stay in the nearer water.
const WATER = {
  rbc: { calm: 30, rich: 60, scale: UM, spin: [0.04, 0.12] },
  platelet: { calm: 24, rich: 46, scale: UM * 1.5, spin: [0.05, 0.16] },
  lymphocyte: { calm: 3, rich: 6, scale: UM, spin: [0.03, 0.08] },
  neutrophil: { calm: 3, rich: 5, scale: UM, spin: [0.03, 0.08] },
  monocyte: { calm: 2, rich: 4, scale: UM, spin: [0.02, 0.06] },
  dna: { calm: 5, rich: 9, scale: NM, spin: [0.05, 0.12], reach: 0.55 },
  coil: { calm: 4, rich: 7, size: 2.4, spin: [0.04, 0.1], reach: 0.8 },
  thread: { calm: 4, rich: 7, size: 4.5, spin: [0.02, 0.06], reach: 0.9 },
  longCell: { calm: 3, rich: 5, size: 2.8, spin: [0.02, 0.06] },
  chromatin: { calm: 2, rich: 4, size: 3.6, spin: [0.03, 0.07], reach: 0.7 },
};

// ---- placement, in closed form ----

export const NEAR = 6;    // the nearest an object is placed (scene units)
export const FAR = 46;    // the farthest

export const kinds = () => Object.entries(WATER);

// Wrap x into [-h, h).
export const wrapC = (x, h) => ((((x + h) % (2 * h)) + 2 * h) % (2 * h)) - h;

// One kind's objects: each a fixed depth (even in volume, so the near water
// is sparse and the far water full), a place in screen terms (u, v from -1
// to 1 across the view), a size, a slow rise (scene units a second), a
// spin and a sway. `radius` is the kind's mesh radius at scale 1.
export function seedShoal(rand, spec, radius, { near = NEAR, far = FAR, density = 'rich' } = {}) {
  const count = Math.max(1, Math.round(spec[density]));
  const deep = near + (spec.reach ?? 1) * (far - near);
  const scale = spec.size ? spec.size / (2 * radius) : spec.scale;
  return Array.from({ length: count }, () => {
    const d = Math.cbrt(near ** 3 + rand() * (deep ** 3 - near ** 3));
    const size = scale * (0.88 + rand() * 0.24);
    // Half the period of the wrap, across and up: the object is wholly out
    // of the frame before it comes back on the other side.
    const hu = 1.05 + (radius * size) / (d * TAN * ASPECT);
    const hv = 1.05 + (radius * size) / (d * TAN);
    return {
      d, size, hu, hv,
      u0: (rand() * 2 - 1) * hu,
      v0: (rand() * 2 - 1) * hv,
      rise: 0.02 + rand() * 0.03,
      spin: spec.spin[0] + rand() * (spec.spin[1] - spec.spin[0]),
      phase: rand() * Math.PI * 2,
      axis: [rand() - 0.5, rand() - 0.5, rand() - 0.5],
      start: [rand() - 0.5, rand() - 0.5, rand() - 0.5, rand() * Math.PI * 2],
      shade: 0.92 + rand() * 0.12,
    };
  });
}

// Where an object is when the camera is at `pose` ({ x, y }, water units,
// y down) at film time t: [x, y, z] in the camera's space, its turn
// (radians about its axis) and its scale, which never changes.
export function placeAt(o, pose, t) {
  const sway = 0.035 * Math.sin(t * 0.11 + o.phase);
  const u = wrapC(o.u0 - pose.x / (o.d * TAN * ASPECT) + sway, o.hu);
  const v = wrapC(o.v0 + (pose.y + o.rise * t) / (o.d * TAN), o.hv);
  return { x: u * o.d * TAN * ASPECT, y: v * o.d * TAN, z: -o.d, u, v, turn: o.spin * t + o.phase, scale: o.size };
}

// ---- the meshes ----

// The shoal in three.js: one instanced mesh per part of each kind, sharing
// the site's materials. lib: { PALETTES, sharedUniforms, specimen, rng },
// from vendor/site/biocells.js and random.js.
export function createShoal(THREE, lib, { fog = '#E3ECF5', seed = 41 } = {}) {
  const shared = lib.sharedUniforms(THREE, { fog, depthFade: [NEAR, NEAR + 4, FAR - 16, FAR], haze: 0.5 });
  const group = new THREE.Group();
  const rand = lib.rng(seed);
  const flocks = [];
  for (const [kind, spec] of kinds()) {
    const model = lib.specimen(THREE, kind, lib.PALETTES.vivid, shared);
    let radius = 0;
    for (const child of model.children) {
      child.geometry.computeBoundingSphere();
      radius = Math.max(radius, child.geometry.boundingSphere.radius);
    }
    const objects = seedShoal(rand, spec, radius);
    let matrix = null;
    const tint = new THREE.InstancedBufferAttribute(new Float32Array(objects.length * 3), 3);
    objects.forEach((o, i) => tint.setXYZ(i, o.shade, o.shade, o.shade));
    for (const child of model.children) {
      const mesh = new THREE.InstancedMesh(child.geometry, child.material, objects.length);
      if (matrix) mesh.instanceMatrix = matrix;
      else { matrix = mesh.instanceMatrix; matrix.setUsage(THREE.DynamicDrawUsage); }
      mesh.instanceColor = tint;
      mesh.renderOrder = child.renderOrder;
      mesh.frustumCulled = false;
      group.add(mesh);
    }
    const turns = objects.map((o) => ({
      axis: new THREE.Vector3(...o.axis).normalize(),
      start: new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(...o.start.slice(0, 3)).normalize(), o.start[3]),
    }));
    flocks.push({ objects, matrix, turns });
  }
  const pos = new THREE.Vector3();
  const quat = new THREE.Quaternion();
  const scl = new THREE.Vector3();
  const mat = new THREE.Matrix4();

  // Every object for the camera at `pose` at film time t.
  function update(t, pose) {
    shared.uTime.value = t;
    for (const { objects, matrix, turns } of flocks) {
      objects.forEach((o, i) => {
        const at = placeAt(o, pose, t);
        pos.set(at.x, at.y, at.z);
        quat.setFromAxisAngle(turns[i].axis, at.turn).multiply(turns[i].start);
        scl.setScalar(at.scale);
        mat.compose(pos, quat, scl).toArray(matrix.array, i * 16);
      });
      matrix.needsUpdate = true;
    }
  }

  return { group, shared, update, setFade: (f) => { shared.uFade.value = f; } };
}
