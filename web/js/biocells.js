// Blood, built in code: the 3D objects that drift through the landing's
// water. B-form DNA and chromatin, the red blood cell, the platelet and
// three white cells (lymphocyte, monocyte, neutrophil), each built from its
// measured geometry, cited where it is defined; and three simple drawn
// shapes: a coiled thread, a long thread and a long, spindle-shaped cell.
// No model files are loaded.
//
// The shape maths at the top is pure (no THREE, no DOM), so
// web/tests/biocells.test.js checks it under node --test. Everything after
// it takes THREE (three.js r128, the global web/js/story.js loads) as its
// first argument. Cells are built in micrometres and DNA in nanometres;
// createBioLayer scales both into the scene.

import { rng } from './formations.js';

// ---- the measured shapes (pure) ----

// The resting red cell (Evans and Fung, 1972). With xi = r / R running from
// the centre (0) to the rim (1), the half-thickness is
//   R * 0.5 * sqrt(1 - xi^2) * (c0 + c1 xi^2 + c2 xi^4)
// with R = 3.91 um: 7.8 um across, 0.81 um thick at the centre and 2.6 um
// at its thickest, near xi = 0.7.
export const RBC = { radius: 3.91, c0: 0.207161, c1: 2.002558, c2: -1.122762 };

export function rbcHalfThickness(xi) {
  const u = xi * xi;
  if (u >= 1) return 0;
  return RBC.radius * 0.5 * Math.sqrt(1 - u) * (RBC.c0 + RBC.c1 * u + RBC.c2 * u * u);
}

// B-form DNA: right-handed, 10.5 base pairs a turn, 0.34 nm between pairs,
// 2 nm across, with the backbones' phosphates at about 0.86 nm from the
// axis. The two backbones sit 144 degrees apart around the axis, not 180,
// which opens the wide major groove on one side and the narrow minor groove
// on the other.
export const BDNA = { radius: 1, backbone: 0.86, rise: 0.34, pairsPerTurn: 10.5, strandOffset: 144 };

// The point on one backbone (strand 0 or 1) at base pair k. The axis rises
// along +y, or bends into an arc of radius `bend` (nm) towards +x.
export function dnaPoint(k, strand, { bend = Infinity, radius = BDNA.backbone } = {}) {
  const theta = (2 * Math.PI * k) / BDNA.pairsPerTurn + (strand ? (BDNA.strandOffset * Math.PI) / 180 : 0);
  const s = k * BDNA.rise;
  let cx = 0;
  let cy = s;
  // The frame across the axis: n1 x n2 = the axis tangent, so the helix is
  // right-handed for any bend.
  let n2x = 1;
  let n2y = 0;
  if (Number.isFinite(bend)) {
    const phi = s / bend;
    cx = bend * (1 - Math.cos(phi));
    cy = bend * Math.sin(phi);
    n2x = Math.cos(phi);
    n2y = -Math.sin(phi);
  }
  const a = radius * Math.cos(theta);
  const b = radius * Math.sin(theta);
  return [cx + b * n2x, cy + b * n2y, a];
}

// The axis direction at base pair k.
export function dnaTangent(k, bend = Infinity) {
  if (!Number.isFinite(bend)) return [0, 1, 0];
  const phi = (k * BDNA.rise) / bend;
  return [Math.sin(phi), Math.cos(phi), 0];
}

// One turn's length, and how it splits between the grooves (measured along
// the axis, backbone centre to backbone centre).
export function dnaGrooves() {
  const pitch = BDNA.pairsPerTurn * BDNA.rise;
  const minor = (pitch * BDNA.strandOffset) / 360;
  return { pitch, minor, major: pitch - minor };
}

// A helix about +y: step k of `perTurn` a turn, `rise` apart along the
// axis. Right-handed unless `left`, by the same convention as dnaPoint.
export function helixPoint(k, { radius, rise, perTurn, phase = 0, left = false }) {
  const theta = (2 * Math.PI * k) / perTurn + phase;
  return [(left ? -1 : 1) * radius * Math.sin(theta), k * rise, radius * Math.cos(theta)];
}

// Chromatin: DNA winds about 1.65 turns, left-handed, around each core of
// eight histone proteins, on a superhelix of radius 4.2 nm and pitch 2.4 nm.
// With the DNA's own 1 nm radius, the nucleosome is about 10 nm across:
// beads on a string, the "10 nm fibre".
export const NUCLEOSOME = { radius: 4.2, pitch: 2.4, turns: 1.65, core: [3.2, 2.7] };

// Perlin's improved gradient noise, seeded, in about -1..1. The cells'
// lumps, ruffles and chromatin all come from it.
export function makeNoise(seed = 1) {
  const rand = rng(seed);
  const base = Array.from({ length: 256 }, (_, i) => i);
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [base[i], base[j]] = [base[j], base[i]];
  }
  const p = new Uint8Array(512);
  for (let i = 0; i < 512; i++) p[i] = base[i & 255];
  const fade = (t) => t * t * t * (t * (t * 6 - 15) + 10);
  const lerp = (a, b, t) => a + t * (b - a);
  const grad = (h, x, y, z) => {
    const k = h & 15;
    const u = k < 8 ? x : y;
    const v = k < 4 ? y : (k === 12 || k === 14 ? x : z);
    return ((k & 1) ? -u : u) + ((k & 2) ? -v : v);
  };
  return (x, y, z) => {
    const fx = Math.floor(x);
    const fy = Math.floor(y);
    const fz = Math.floor(z);
    const X = fx & 255;
    const Y = fy & 255;
    const Z = fz & 255;
    x -= fx; y -= fy; z -= fz;
    const u = fade(x);
    const v = fade(y);
    const w = fade(z);
    const A = p[X] + Y;
    const AA = p[A] + Z;
    const AB = p[A + 1] + Z;
    const B = p[X + 1] + Y;
    const BA = p[B] + Z;
    const BB = p[B + 1] + Z;
    return lerp(
      lerp(lerp(grad(p[AA], x, y, z), grad(p[BA], x - 1, y, z), u),
        lerp(grad(p[AB], x, y - 1, z), grad(p[BB], x - 1, y - 1, z), u), v),
      lerp(lerp(grad(p[AA + 1], x, y, z - 1), grad(p[BA + 1], x - 1, y, z - 1), u),
        lerp(grad(p[AB + 1], x, y - 1, z - 1), grad(p[BB + 1], x - 1, y - 1, z - 1), u), v),
      w);
  };
}

// Sharp crests where the noise crosses zero: membrane ruffles.
const ridge = (v) => {
  const r = 1 - Math.abs(v);
  return r * r * r;
};
const smoothstep = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// Three looks. 'vivid' gives each kind of object its own colour family, so
// the water is not one blue. 'site' keeps every object in the field's cool
// blues and blue-greens, so the reserved RNA, protein and dot colours keep
// their meaning (docs/web/design.md). 'stained' uses the colours of a
// Wright-Giemsa blood smear.

// Each white cell and the long cell can have its own membrane rim and
// nucleus colours; a palette that sets none uses its shared ones.
function complete(palette) {
  const out = { ...palette };
  for (const cell of ['lymph', 'mono', 'neutro', 'long']) {
    out[`${cell}Rim`] ??= palette.cytoRim;
    out[`${cell}NucleusDark`] ??= palette.chromatinDark;
    out[`${cell}NucleusLight`] ??= palette.chromatinLight;
  }
  out.coilRim ??= palette.threadRim;
  return out;
}

export const PALETTES = {
  vivid: complete({
    dnaStrand1: '#2563C9', dnaStrand2: '#3FA9E0', dnaRim: '#1B4A9A',
    baseA: '#F06A6A', baseT: '#F7C548', baseG: '#4CC38A', baseC: '#8A7CF2',
    rbc: '#E8615A', rbcRim: '#B23A35',
    platelet: '#D2BEF5', plateletRim: '#8E6BD6', plateletGranule: '#6A3FC4',
    lymphCyto: '#BFE3FA', monoCyto: '#DCD7F4', neutroCyto: '#FCE0EC', cytoRim: '#5A8FD0',
    chromatinDark: '#3B2C8F', chromatinLight: '#7B6BD6',
    neutroGranule: '#E58CC4', monoGranule: '#B993E6', vacuole: '#FFFFFF',
    histone: '#F4A85E', histoneRim: '#C9772E',
    thread: '#E0609B', threadRim: '#A83A70', coil: '#14A3A0', coilRim: '#0B7471', longCyto: '#FFE0CC',
    lymphRim: '#3A93D6', lymphNucleusDark: '#2E2A8F', lymphNucleusLight: '#6F72DA',
    monoRim: '#7C6CC8', monoNucleusDark: '#5B2386', monoNucleusLight: '#A774D4',
    neutroRim: '#D0679E', neutroNucleusDark: '#7A1F6E', neutroNucleusLight: '#C35CAF',
    longRim: '#E08A5A', longNucleusDark: '#1D6680', longNucleusLight: '#4DB0CF',
  }),
  site: complete({
    dnaStrand1: '#0B6FAE', dnaStrand2: '#3D97D3', dnaRim: '#0A5D93',
    baseA: '#9BCBEC', baseT: '#C9E4F5', baseG: '#5E9ED2', baseC: '#A9D1EF',
    rbc: '#86BCE4', rbcRim: '#1F7DBE',
    platelet: '#D4E8F6', plateletRim: '#4A9BD3', plateletGranule: '#2A6C9C',
    lymphCyto: '#E3F0FA', monoCyto: '#E8F1F8', neutroCyto: '#EDF4FA', cytoRim: '#2A8ACB',
    chromatinDark: '#0A4675', chromatinLight: '#3D82B6',
    neutroGranule: '#86B8DE', monoGranule: '#9CC4E3', vacuole: '#FFFFFF',
    histone: '#A8D3BE', histoneRim: '#4E9C7A',
    thread: '#4FA0D8', coil: '#2D84C2', threadRim: '#0A5D93', longCyto: '#E4F0FA',
  }),
  stained: complete({
    dnaStrand1: '#3B6FB6', dnaStrand2: '#6A8FD0', dnaRim: '#2B4F86',
    baseA: '#E46A5E', baseT: '#F0C04F', baseG: '#4FAE7B', baseC: '#5A8FD6',
    rbc: '#DE7468', rbcRim: '#A9423A',
    platelet: '#C9B5E2', plateletRim: '#8A6BB8', plateletGranule: '#5B2E8C',
    lymphCyto: '#B9D3EE', monoCyto: '#C8CCDD', neutroCyto: '#F0DCE6', cytoRim: '#7E6BAE',
    chromatinDark: '#3D1F6B', chromatinLight: '#7A5AA8',
    neutroGranule: '#B07CC0', monoGranule: '#B98FC6', vacuole: '#FFFFFF',
    histone: '#BFA8DC', histoneRim: '#7A5AA8',
    thread: '#D9A3B8', coil: '#B07CC0', threadRim: '#9A5B78', longCyto: '#EBD5E0',
  }),
};

// ---- geometry (THREE from here on) ----

// A closed surface as a map of the unit sphere: map(x, y, z) takes a unit
// direction to a point. Normals come from the map itself by finite
// differences, so a lumpy surface is lit correctly and there is no seam.
// `colour` is a THREE.Color or a function (x, y, z, point) => THREE.Color.
function surface(THREE, map, { w = 64, h = 48, colour }) {
  const g = new THREE.SphereGeometry(1, w, h);
  g.deleteAttribute('uv');
  const pos = g.attributes.position;
  const nor = g.attributes.normal;
  const col = new Float32Array(pos.count * 3);
  const d = new THREE.Vector3();
  const t1 = new THREE.Vector3();
  const t2 = new THREE.Vector3();
  const q = new THREE.Vector3();
  const up = new THREE.Vector3(0, 1, 0);
  const side = new THREE.Vector3(1, 0, 0);
  const E = 1e-3;
  const at = (base, t, e) => {
    q.copy(base).addScaledVector(t, e).normalize();
    return map(q.x, q.y, q.z);
  };
  for (let i = 0; i < pos.count; i++) {
    d.fromBufferAttribute(pos, i).normalize();
    t1.crossVectors(d, Math.abs(d.y) < 0.9 ? up : side).normalize();
    t2.crossVectors(d, t1);
    const p = map(d.x, d.y, d.z);
    const a = at(d, t1, E);
    const b = at(d, t1, -E);
    const c = at(d, t2, E);
    const e = at(d, t2, -E);
    const ux = a[0] - b[0]; const uy = a[1] - b[1]; const uz = a[2] - b[2];
    const vx = c[0] - e[0]; const vy = c[1] - e[1]; const vz = c[2] - e[2];
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz) || 1;
    pos.setXYZ(i, p[0], p[1], p[2]);
    nor.setXYZ(i, nx / len, ny / len, nz / len);
    const c3 = typeof colour === 'function' ? colour(d.x, d.y, d.z, p) : colour;
    col[i * 3] = c3.r;
    col[i * 3 + 1] = c3.g;
    col[i * 3 + 2] = c3.b;
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return g;
}

// One colour on every vertex of a geometry.
function paint(THREE, g, colour) {
  const c = colour instanceof THREE.Color ? colour : new THREE.Color(colour);
  const n = g.attributes.position.count;
  const a = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    a[i * 3] = c.r;
    a[i * 3 + 1] = c.g;
    a[i * 3 + 2] = c.b;
  }
  g.setAttribute('color', new THREE.BufferAttribute(a, 3));
  return g;
}

// Many geometries as one, so each part of an object is one draw call.
function merge(THREE, parts) {
  let vertices = 0;
  let indices = 0;
  for (const g of parts) {
    vertices += g.attributes.position.count;
    indices += g.index ? g.index.count : g.attributes.position.count;
  }
  const position = new Float32Array(vertices * 3);
  const normal = new Float32Array(vertices * 3);
  const color = new Float32Array(vertices * 3);
  const index = vertices > 65535 ? new Uint32Array(indices) : new Uint16Array(indices);
  let v = 0;
  let k = 0;
  for (const g of parts) {
    const n = g.attributes.position.count;
    position.set(g.attributes.position.array, v * 3);
    normal.set(g.attributes.normal.array, v * 3);
    color.set(g.attributes.color.array, v * 3);
    if (g.index) for (let i = 0; i < g.index.count; i++) index[k++] = g.index.array[i] + v;
    else for (let i = 0; i < n; i++) index[k++] = v + i;
    v += n;
    g.dispose();
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(position, 3));
  out.setAttribute('normal', new THREE.BufferAttribute(normal, 3));
  out.setAttribute('color', new THREE.BufferAttribute(color, 3));
  out.setIndex(new THREE.BufferAttribute(index, 1));
  out.computeBoundingSphere();
  return out;
}

// Random points in a box of half-sizes `half` that pass `accept`.
function scatter(rand, n, half, accept) {
  const out = [];
  for (let t = 0; t < n * 80 && out.length < n; t++) {
    const x = (rand() * 2 - 1) * half[0];
    const y = (rand() * 2 - 1) * half[1];
    const z = (rand() * 2 - 1) * half[2];
    if (accept(x, y, z)) out.push([x, y, z]);
  }
  return out;
}

// Small spheres (granules, vacuoles) at the given points.
function beads(THREE, points, rand, [r0, r1], colour, segments = [8, 6]) {
  return merge(THREE, points.map(([x, y, z]) => paint(THREE,
    new THREE.SphereGeometry(r0 + rand() * (r1 - r0), segments[0], segments[1]).translate(x, y, z),
    typeof colour === 'function' ? colour() : colour)));
}

// Chromatin: a nucleus's dark and light patches, from noise, in `cell`'s
// nucleus colours. `contrast` 1 gives the clumped chromatin of a
// lymphocyte, lower the lacier monocyte.
function chromatin(THREE, palette, noise, freq, contrast, cell) {
  const dark = new THREE.Color(palette[`${cell}NucleusDark`]);
  const light = new THREE.Color(palette[`${cell}NucleusLight`]);
  const out = new THREE.Color();
  return (x, y, z) => {
    const v = 0.7 * noise(freq * x + 11, freq * y + 3, freq * z)
      + 0.3 * noise(freq * 2.3 * x, freq * 2.3 * y + 7, freq * 2.3 * z);
    return out.copy(dark).lerp(light, Math.min(1, Math.max(0, 0.5 + v * 1.6 * contrast)));
  };
}

// A flat base between two backbone points: thin along the helix axis, so
// the pairs stack like steps.
function slab(THREE, from, to, axis, colour) {
  const g = new THREE.CylinderGeometry(0.5, 0.5, 1, 12, 1);
  g.deleteAttribute('uv');
  g.scale(0.36, from.distanceTo(to), 0.13);
  const y = to.clone().sub(from).normalize();
  const z = axis.clone().addScaledVector(y, -axis.dot(y)).normalize();
  const x = new THREE.Vector3().crossVectors(y, z);
  g.applyMatrix4(new THREE.Matrix4().makeBasis(x, y, z));
  const m = from.clone().add(to).multiplyScalar(0.5);
  g.translate(m.x, m.y, m.z);
  return paint(THREE, g, colour);
}

// Frames along a dense path that twist as little as possible: the tangent
// T and two directions across it, N and B (N x B = T). Where face[i] gives a
// direction and a weight, N turns towards it there: a ribbon's width
// follows it.
function frames(THREE, points, face = null) {
  const n = points.length;
  const T = [];
  const N = [];
  const B = [];
  const f = new THREE.Vector3();
  let prev = null;
  for (let i = 0; i < n; i++) {
    const t = points[Math.min(i + 1, n - 1)].clone().sub(points[Math.max(i - 1, 0)]).normalize();
    const seed = Math.abs(t.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
    const nn = (prev || seed).clone().addScaledVector(t, -(prev || seed).dot(t));
    if (nn.lengthSq() < 1e-10) nn.copy(seed).addScaledVector(t, -seed.dot(t));
    nn.normalize();
    const want = face && face[i];
    if (want && want.weight > 0) {
      f.copy(want.dir).addScaledVector(t, -want.dir.dot(t));
      if (f.lengthSq() > 1e-8) {
        f.normalize();
        if (f.dot(nn) < 0) f.negate();
        nn.lerp(f, want.weight).normalize();
      }
    }
    T.push(t);
    N.push(nn);
    B.push(new THREE.Vector3().crossVectors(t, nn));
    prev = nn;
  }
  return { T, N, B };
}

// A tube or a ribbon along a dense path, capped at both ends. half(i) gives
// point i's cross-section as half-sizes [along N, along B]: equal for a
// tube, wide and thin for a ribbon. colour(i) gives its colour.
function sweep(THREE, points, { half, face = null, colour, radial = 8 }) {
  const { T, N, B } = frames(THREE, points, face);
  const n = points.length;
  const ring = radial + 1;
  const total = n * ring + 2 * (ring + 1);
  const position = new Float32Array(total * 3);
  const normal = new Float32Array(total * 3);
  const color = new Float32Array(total * 3);
  const index = [];
  const c = new THREE.Color();
  let v = 0;
  const put = (x, y, z, nx, ny, nz) => {
    const len = Math.hypot(nx, ny, nz) || 1;
    position.set([x, y, z], v * 3);
    normal.set([nx / len, ny / len, nz / len], v * 3);
    color.set([c.r, c.g, c.b], v * 3);
    return v++;
  };
  const rim = (i, j, cap) => {
    const [a, b] = half(i);
    const phi = (j / radial) * Math.PI * 2;
    const cs = Math.cos(phi);
    const sn = Math.sin(phi);
    const p = points[i];
    const x = p.x + N[i].x * a * cs + B[i].x * b * sn;
    const y = p.y + N[i].y * a * cs + B[i].y * b * sn;
    const z = p.z + N[i].z * a * cs + B[i].z * b * sn;
    if (cap) return put(x, y, z, T[i].x * cap, T[i].y * cap, T[i].z * cap);
    // The ellipse's outward normal.
    return put(x, y, z,
      N[i].x * b * cs + B[i].x * a * sn, N[i].y * b * cs + B[i].y * a * sn, N[i].z * b * cs + B[i].z * a * sn);
  };
  for (let i = 0; i < n; i++) {
    c.set(colour(i));
    for (let j = 0; j <= radial; j++) rim(i, j, 0);
  }
  for (let i = 0; i < n - 1; i++) {
    for (let j = 0; j < radial; j++) {
      const a = i * ring + j;
      const b = a + ring;
      index.push(a, a + 1, b, b, a + 1, b + 1);
    }
  }
  for (const [i, sign] of [[0, -1], [n - 1, 1]]) {
    c.set(colour(i));
    const centre = put(points[i].x, points[i].y, points[i].z, T[i].x * sign, T[i].y * sign, T[i].z * sign);
    const first = v;
    for (let j = 0; j <= radial; j++) rim(i, j, sign);
    for (let j = 0; j < radial; j++) {
      if (sign < 0) index.push(centre, first + j + 1, first + j);
      else index.push(centre, first + j, first + j + 1);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(position, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(normal, 3));
  g.setAttribute('color', new THREE.BufferAttribute(color, 3));
  g.setIndex(new THREE.BufferAttribute(total > 65535 ? new Uint32Array(index) : new Uint16Array(index), 1));
  return g;
}

// A smooth path through `points`, `per` samples between each pair.
function smoothPath(THREE, points, per) {
  return new THREE.CatmullRomCurve3(points, false, 'centripetal').getPoints((points.length - 1) * per);
}

function centred(THREE, g) {
  g.computeBoundingBox();
  const c = g.boundingBox.getCenter(new THREE.Vector3());
  g.translate(-c.x, -c.y, -c.z);
  g.computeBoundingSphere();
  return g;
}

// ---- the objects ----
// Each builder returns its parts: a geometry, how it is drawn (`look`, see
// LOOKS), its rim colour and how much its membrane breathes.

function dna(THREE, palette, { pairs = 32, bend = 40, seed = 7 } = {}) {
  const rand = rng(seed);
  const parts = [];
  const opts = { bend };
  for (const strand of [0, 1]) {
    const colour = palette[strand ? 'dnaStrand2' : 'dnaStrand1'];
    const curve = new THREE.Curve();
    curve.getPoint = (t, target = new THREE.Vector3()) => target.fromArray(dnaPoint(t * (pairs - 1), strand, opts));
    const tube = new THREE.TubeGeometry(curve, pairs * 8, 0.17, 8, false);
    tube.deleteAttribute('uv');
    parts.push(paint(THREE, tube, colour));
    // A phosphate bead per nucleotide.
    for (let k = 0; k < pairs; k++) {
      parts.push(paint(THREE, new THREE.SphereGeometry(0.25, 10, 8).translate(...dnaPoint(k, strand, opts)), colour));
    }
  }
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const mid = new THREE.Vector3();
  const axis = new THREE.Vector3();
  for (let k = 0; k < pairs; k++) {
    let pair = rand() < 0.5 ? ['G', 'C'] : ['A', 'T'];
    if (rand() < 0.5) pair = [pair[1], pair[0]];
    a.fromArray(dnaPoint(k, 0, opts));
    b.fromArray(dnaPoint(k, 1, opts));
    // Purines (A, G) have two rings and reach further than T and C.
    mid.copy(a).lerp(b, pair[0] === 'A' || pair[0] === 'G' ? 0.56 : 0.44);
    axis.fromArray(dnaTangent(k, bend));
    parts.push(slab(THREE, a, mid, axis, palette[`base${pair[0]}`]));
    parts.push(slab(THREE, mid, b, axis, palette[`base${pair[1]}`]));
  }
  return [{ geometry: centred(THREE, merge(THREE, parts)), look: 'solid', rim: 'dnaRim' }];
}

function redCell(THREE, palette) {
  const R = RBC.radius;
  const base = new THREE.Color(palette.rbc);
  const hollow = base.clone().multiplyScalar(0.62);
  const out = new THREE.Color();
  // On the unit sphere xi^2 = 1 - y^2 and sqrt(1 - xi^2) = |y|, so the
  // Evans and Fung profile is smooth across the rim.
  const geometry = surface(THREE, (x, y, z) => {
    const u = 1 - y * y;
    return [R * x, 0.5 * R * y * (RBC.c0 + RBC.c1 * u + RBC.c2 * u * u), R * z];
  }, {
    w: 72,
    h: 56,
    // Light reaches less of the dimple than of the rim: baked shadow, so the
    // dimple reads at any angle and in any light.
    colour: (x, y, z) => out.copy(hollow).lerp(base, smoothstep(0.1, 0.75, Math.hypot(x, z))),
  });
  return [{ geometry, look: 'body', rim: 'rbcRim' }];
}

// Resting: a lumpy disc about 2.5 um across and 0.7 um thick, its granules
// showing through.
function platelet(THREE, palette, { seed = 3 } = {}) {
  const noise = makeNoise(seed);
  const rand = rng(seed);
  const a = 1.25;
  const b = 0.36;
  const shell = surface(THREE, (x, y, z) => {
    const s = 1 + 0.08 * noise(1.6 * x, 1.6 * y, 1.6 * z) + 0.025 * noise(5 * x + 9, 5 * y, 5 * z);
    return [a * x * s, b * y * (1 + 0.25 * noise(2 * x + 4, 2 * y, 2 * z + 1)), a * z * s];
  }, { w: 48, h: 32, colour: new THREE.Color(palette.platelet) });
  const points = scatter(rand, 16, [0.85, 0.12, 0.85], (x, y, z) => x * x + z * z < 0.72);
  return [
    { geometry: shell, look: 'thick', rim: 'plateletRim' },
    { geometry: beads(THREE, points, rand, [0.07, 0.12], palette.plateletGranule), look: 'solid', rim: 'plateletGranule' },
  ];
}

// About 8 um. A large round nucleus of clumped chromatin fills most of the
// cell, inside a thin rim of cytoplasm. The surface is covered in short
// microvilli.
function lymphocyte(THREE, palette, { seed = 11 } = {}) {
  const noise = makeNoise(seed);
  const rand = rng(seed);
  const R = 4;
  const colour = new THREE.Color(palette.lymphCyto);
  const radius = (x, y, z) => R * (1 + 0.025 * noise(1.3 * x, 1.3 * y, 1.3 * z));
  const shell = [surface(THREE, (x, y, z) => {
    const r = radius(x, y, z);
    return [x * r, y * r, z * r];
  }, { w: 64, h: 48, colour })];
  const up = new THREE.Vector3(0, 1, 0);
  const q = new THREE.Quaternion();
  const turn = new THREE.Matrix4();
  const d = new THREE.Vector3();
  const count = 240;
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (2 * (i + 0.5)) / count;
    const ring = Math.sqrt(1 - y * y);
    const angle = i * golden + (rand() - 0.5) * 0.3;
    d.set(Math.cos(angle) * ring, y, Math.sin(angle) * ring).normalize();
    const length = 0.28 + rand() * 0.32;
    const g = new THREE.CylinderGeometry(0.055, 0.075, length, 6, 1);
    g.deleteAttribute('uv');
    g.translate(0, length / 2, 0);
    g.applyMatrix4(turn.makeRotationFromQuaternion(q.setFromUnitVectors(up, d)));
    const r = radius(d.x, d.y, d.z) - 0.04;
    shell.push(paint(THREE, g.translate(d.x * r, d.y * r, d.z * r), colour));
  }
  const nucleus = surface(THREE, (x, y, z) => {
    const r = 3.15 * (1 + 0.04 * noise(1.8 * x + 5, 1.8 * y, 1.8 * z) + 0.015 * noise(7 * x, 7 * y, 7 * z + 3));
    return [x * r + 0.3, y * r * 0.97 + 0.1, z * r];
  }, { w: 56, h: 40, colour: chromatin(THREE, palette, makeNoise(seed + 1), 3.2, 1, 'lymph') });
  return [
    { geometry: merge(THREE, shell), look: 'membrane', rim: 'lymphRim', breath: 0.05 },
    { geometry: nucleus, look: 'solid', rim: 'lymphNucleusDark' },
  ];
}

// The largest white cell, about 17 um: a kidney-shaped nucleus, a ruffled
// membrane, a wide cytoplasm with a few clear vacuoles and fine granules.
function monocyte(THREE, palette, { seed = 13 } = {}) {
  const noise = makeNoise(seed);
  const rand = rng(seed);
  const R = 8.5;
  const membrane = surface(THREE, (x, y, z) => {
    const r = R * (1 + 0.05 * noise(1.1 * x, 1.1 * y, 1.1 * z)
      + 0.04 * ridge(noise(3.2 * x + 7, 3.2 * y, 3.2 * z))
      + 0.01 * noise(8 * x, 8 * y + 2, 8 * z));
    return [x * r * 1.04, y * r * 0.94, z * r];
  }, { w: 96, h: 72, colour: new THREE.Color(palette.monoCyto) });
  // The kidney: an ellipsoid bent around an arc, notched on its inner side.
  const n = makeNoise(seed + 1);
  const a = 5;
  const b = 2.8;
  const c = 2.6;
  const bendR = (2 * a) / 2.3;
  const nucleus = surface(THREE, (x, y, z) => {
    const s = 1 + 0.05 * n(1.5 * x, 1.5 * y, 1.5 * z) + 0.015 * n(6 * x + 2, 6 * y, 6 * z);
    const qx = a * x * s;
    const qy = b * y * s - 0.35 * b * Math.exp(-((x / 0.4) ** 2)) * Math.max(0, y);
    const qz = c * z * s;
    const angle = qx / bendR;
    return [(bendR - qy) * Math.sin(angle), bendR - (bendR - qy) * Math.cos(angle), qz];
  }, { w: 64, h: 48, colour: chromatin(THREE, palette, makeNoise(seed + 2), 3.6, 0.55, 'mono') });
  nucleus.rotateX(0.3);
  nucleus.translate(0, -0.25 * R, 0);
  const outsideNucleus = (x, y, z) => (x / 6.2) ** 2 + ((y + 1.6) / 4.3) ** 2 + (z / 3.5) ** 2 > 1;
  const inCell = (x, y, z) => x * x + y * y + z * z < (0.8 * R) ** 2;
  const vacuoles = scatter(rand, 9, [0.8 * R, 0.8 * R, 0.8 * R], (x, y, z) => inCell(x, y, z) && outsideNucleus(x, y, z));
  const granules = scatter(rand, 45, [0.85 * R, 0.85 * R, 0.85 * R], (x, y, z) => inCell(x, y, z) && outsideNucleus(x, y, z));
  return [
    { geometry: membrane, look: 'membrane', rim: 'monoRim', breath: 0.1 },
    {
      geometry: merge(THREE, [
        nucleus,
        beads(THREE, vacuoles, rand, [0.35, 0.65], palette.vacuole, [12, 8]),
        beads(THREE, granules, rand, [0.13, 0.18], palette.monoGranule),
      ]),
      look: 'solid',
      rim: 'monoNucleusDark',
    },
  ];
}

// About 13 um. A nucleus of 3 to 5 lobes joined by thin strands, in a
// cytoplasm full of fine granules.
function neutrophil(THREE, palette, { seed = 17, lobes = 4 } = {}) {
  const noise = makeNoise(seed);
  const rand = rng(seed);
  const R = 6.5;
  const membrane = surface(THREE, (x, y, z) => {
    const r = R * (1 + 0.03 * noise(1.2 * x, 1.2 * y, 1.2 * z)
      + 0.022 * ridge(noise(4 * x + 2, 4 * y, 4 * z))
      + 0.008 * noise(9 * x, 9 * y + 5, 9 * z));
    return [x * r, y * r, z * r];
  }, { w: 96, h: 72, colour: new THREE.Color(palette.neutroCyto) });
  // The lobes sit along a C and face along it.
  const arc = 0.48 * R;
  const span = 3.5;
  const size = Math.min(1.3, 0.33 * ((arc * span) / (lobes - 1)));
  const centres = [];
  const parts = [];
  const along = new THREE.Vector3(1, 0, 0);
  const q = new THREE.Quaternion();
  const turn = new THREE.Matrix4();
  for (let i = 0; i < lobes; i++) {
    const t = -Math.PI / 2 - span / 2 + (span * i) / (lobes - 1);
    const centre = new THREE.Vector3(arc * Math.cos(t), 0.9 * arc * Math.sin(t) + 0.5, (rand() - 0.5) * 1.2);
    const tangent = new THREE.Vector3(-Math.sin(t), Math.cos(t), 0).normalize();
    const n = makeNoise(seed + 10 + i);
    const lobe = surface(THREE, (x, y, z) => {
      const s = 1 + 0.06 * n(1.7 * x, 1.7 * y, 1.7 * z) + 0.02 * n(6 * x, 6 * y, 6 * z);
      return [1.25 * size * x * s, size * y * s, 0.9 * size * z * s];
    }, { w: 40, h: 30, colour: chromatin(THREE, palette, makeNoise(seed + 20 + i), 3.4, 0.85, 'neutro') });
    lobe.applyMatrix4(turn.makeRotationFromQuaternion(q.setFromUnitVectors(along, tangent)));
    lobe.translate(centre.x, centre.y, centre.z);
    parts.push(lobe);
    centres.push(centre);
  }
  for (let i = 0; i + 1 < lobes; i++) {
    const mid = centres[i].clone().add(centres[i + 1]).multiplyScalar(0.5)
      .add(new THREE.Vector3((rand() - 0.5) * 0.6, (rand() - 0.5) * 0.6, (rand() - 0.5) * 0.8));
    const strand = new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(centres[i], mid, centres[i + 1]), 16, 0.2, 6, false);
    strand.deleteAttribute('uv');
    parts.push(paint(THREE, strand, palette.neutroNucleusDark));
  }
  const granuleColour = new THREE.Color(palette.neutroGranule);
  const white = new THREE.Color('#FFFFFF');
  const points = scatter(rand, 170, [0.88 * R, 0.88 * R, 0.88 * R], (x, y, z) => x * x + y * y + z * z < (0.86 * R) ** 2
    && centres.every((c) => Math.hypot(x - c.x, y - c.y, z - c.z) > size * 1.5));
  parts.push(beads(THREE, points, rand, [0.11, 0.16], () => granuleColour.clone().lerp(white, rand() * 0.35)));
  return [
    { geometry: membrane, look: 'membrane', rim: 'neutroRim', breath: 0.08 },
    { geometry: merge(THREE, parts), look: 'solid', rim: 'neutroNucleusDark' },
  ];
}

// ---- the threads ----

// Chromatin: DNA rolled up as in a nucleus. It winds round each histone core
// and runs on as linker DNA to the next: beads on a string. The DNA keeps
// its double helix all the way round.
function chromatinFibre(THREE, palette, { seed = 31, beads = 4 } = {}) {
  const rand = rng(seed);
  const noise = makeNoise(seed);
  const wraps = [];
  const cores = [];
  for (let i = 0; i < beads; i++) {
    const centre = new THREE.Vector3(i * 15 - (beads - 1) * 7.5, (i % 2 ? 4.5 : -4.5) + (rand() - 0.5) * 2, (rand() - 0.5) * 5);
    const turn = new THREE.Quaternion().setFromEuler(new THREE.Euler(
      (i % 2 ? 1 : -1) * (1.1 + rand() * 0.4), i * 0.7 + rand() * 0.6, (rand() - 0.5) * 0.6));
    const { radius, pitch, turns } = NUCLEOSOME;
    const steps = Math.ceil((turns * 2 * Math.PI * radius) / 0.15);
    const wrap = [];
    for (let s = 0; s <= steps; s++) {
      const [x, y, z] = helixPoint((s / steps) * turns, { radius, rise: pitch, perTurn: 1, left: true });
      wrap.push(new THREE.Vector3(x, y - (pitch * turns) / 2, z).applyQuaternion(turn).add(centre));
    }
    wraps.push(wrap);
    const [r, h] = NUCLEOSOME.core;
    const core = surface(THREE, (x, y, z) => {
      const s = 1 + 0.07 * noise(1.8 * x + i * 5, 1.8 * y, 1.8 * z) + 0.03 * noise(5 * x, 5 * y + i, 5 * z);
      return [r * x * s, h * y * s, r * z * s];
    }, { w: 36, h: 28, colour: new THREE.Color(palette.histone) });
    core.applyMatrix4(new THREE.Matrix4().makeRotationFromQuaternion(turn));
    core.translate(centre.x, centre.y, centre.z);
    cores.push(core);
  }

  // The DNA's axis: a tail, each wrap, a linker to the next, a tail.
  const axis = [];
  const end = (w, last) => {
    const a = last ? w[w.length - 1] : w[0];
    const b = last ? w[w.length - 2] : w[1];
    return [a, a.clone().sub(b).normalize()];   // the point, heading out
  };
  const bridge = (p0, t0, p3, t3) => {
    const h = 0.4 * p0.distanceTo(p3);
    const curve = new THREE.CubicBezierCurve3(p0, p0.clone().addScaledVector(t0, h), p3.clone().addScaledVector(t3, h), p3);
    const n = Math.ceil(curve.getLength() / 0.15);
    for (let i = 1; i < n; i++) axis.push(curve.getPoint(i / n));
  };
  const [s0, out0] = end(wraps[0], false);
  const tail0 = s0.clone().addScaledVector(out0, 9).add(new THREE.Vector3(0, 2, 0));
  axis.push(tail0);
  bridge(tail0, out0.clone().negate(), s0, out0);
  wraps.forEach((w, i) => {
    axis.push(...w);
    const [e, outE] = end(w, true);
    if (i + 1 < wraps.length) {
      const [s, outS] = end(wraps[i + 1], false);
      bridge(e, outE, s, outS);
    } else {
      const tail = e.clone().addScaledVector(outE, 9).add(new THREE.Vector3(0, -2, 0));
      bridge(e, outE, tail, outE.clone().negate());
      axis.push(tail);
    }
  });

  // The two backbones twist round that axis as B-form DNA.
  const { N, B } = frames(THREE, axis);
  const length = [0];
  for (let i = 1; i < axis.length; i++) length.push(length[i - 1] + axis[i].distanceTo(axis[i - 1]));
  const strands = [[], []];
  const a = new THREE.Vector3();
  const nn = new THREE.Vector3();
  const bb = new THREE.Vector3();
  const pitch = BDNA.pairsPerTurn * BDNA.rise;
  let seg = 0;
  for (let s = 0; s <= length[length.length - 1]; s += BDNA.rise / 4) {
    while (seg < axis.length - 2 && length[seg + 1] < s) seg++;
    const u = Math.min(1, (s - length[seg]) / Math.max(length[seg + 1] - length[seg], 1e-9));
    a.copy(axis[seg]).lerp(axis[seg + 1], u);
    nn.copy(N[seg]).lerp(N[seg + 1], u).normalize();
    bb.copy(B[seg]).lerp(B[seg + 1], u).normalize();
    for (const strand of [0, 1]) {
      const theta = (2 * Math.PI * s) / pitch + (strand ? (BDNA.strandOffset * Math.PI) / 180 : 0);
      strands[strand].push(a.clone()
        .addScaledVector(nn, BDNA.backbone * Math.cos(theta))
        .addScaledVector(bb, BDNA.backbone * Math.sin(theta)));
    }
  }
  const dnaParts = strands.map((points, strand) => sweep(THREE, points, {
    half: () => [0.3, 0.3],
    colour: () => palette[strand ? 'dnaStrand2' : 'dnaStrand1'],
    radial: 6,
  }));
  const geometry = merge(THREE, [...dnaParts, ...cores]);
  return [{ geometry: centred(THREE, geometry), look: 'solid', rim: 'dnaRim' }];
}

// The simple shapes: threads and a long cell, drawn rather than measured.

// A thread's radius along its length (u from 0 to 1), thinning at the tips.
const tapered = (radius, u) => radius * (0.45 + 0.55 * smoothstep(0, 0.06, u) * (1 - smoothstep(0.94, 1, u)));

// A thread wound into a loose coil along a gently bending line, unwinding
// to a free end at each side.
function coil(THREE, palette, { seed = 37, turns = 9, length = 6, radius = 0.5 } = {}) {
  const noise = makeNoise(seed);
  const n = 900;
  const axis = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n;
    axis.push(new THREE.Vector3((u - 0.5) * length, 0.6 * Math.sin(u * Math.PI * 1.4 + 0.3), 0.4 * Math.sin(u * Math.PI * 0.9 + 1.1)));
  }
  const { N, B } = frames(THREE, axis);
  const points = axis.map((a, i) => {
    const u = i / n;
    const wound = smoothstep(0.02, 0.16, u) * (1 - smoothstep(0.84, 0.98, u));
    const r = radius * wound * (1 + 0.18 * noise(u * 6, 0.5, 0.5));
    const theta = 2 * Math.PI * turns * u;
    return a.clone().addScaledVector(N[i], r * Math.cos(theta)).addScaledVector(B[i], r * Math.sin(theta));
  });
  const geometry = sweep(THREE, points, {
    half: (i) => { const r = tapered(0.075, i / n); return [r, r]; },
    colour: () => palette.coil,
  });
  return [{ geometry: centred(THREE, geometry), look: 'solid', rim: 'coilRim' }];
}

// A long, thin thread in gentle curves.
function thread(THREE, palette, { seed = 41, bends = 9 } = {}) {
  const rand = rng(seed);
  const control = [];
  for (let i = 0; i < bends; i++) {
    control.push(new THREE.Vector3((i - (bends - 1) / 2) * 1.6, (rand() - 0.5) * 1.6, (rand() - 0.5) * 1.6));
  }
  const points = smoothPath(THREE, control, 40);
  const n = points.length - 1;
  const geometry = sweep(THREE, points, {
    half: (i) => { const r = tapered(0.085, i / n); return [r, r]; },
    colour: () => palette.thread,
  });
  return [{ geometry: centred(THREE, geometry), look: 'solid', rim: 'threadRim' }];
}

// A long cell: spindle-shaped, tapering to each end and gently bent, with a
// long nucleus, as fibroblasts and smooth muscle cells are.
function longCell(THREE, palette, { seed = 43, half = 3.4, width = 0.75, bend = 0.5 } = {}) {
  const noise = makeNoise(seed);
  const rand = rng(seed);
  // x runs along the cell from -1 to 1; the middle lifts by `bend`.
  const lift = (x) => bend * (1 - x * x);
  const membrane = surface(THREE, (x, y, z) => {
    const s = 1 + 0.03 * noise(1.5 * x, 1.5 * y, 1.5 * z) + 0.01 * noise(6 * x + 3, 6 * y, 6 * z);
    // On the unit sphere |(y, z)| = sqrt(1 - x^2); this makes the radius
    // width * (1 - x^2)^0.8: a spindle, not an ellipsoid.
    const k = width * s * Math.pow(Math.max(1 - x * x, 0), 0.3);
    return [half * x, y * k + lift(x), z * k];
  }, { w: 96, h: 48, colour: new THREE.Color(palette.longCyto) });
  const n = makeNoise(seed + 1);
  const nucleus = surface(THREE, (x, y, z) => {
    const s = 1 + 0.04 * n(2 * x, 2 * y, 2 * z);
    const X = 1.15 * x * s;
    return [X, 0.36 * y * s + lift(X / half), 0.36 * z * s];
  }, { w: 48, h: 32, colour: chromatin(THREE, palette, makeNoise(seed + 2), 3, 0.6, 'long') });
  const points = scatter(rand, 22, [0.8 * half, width, width], (x, y, z) => {
    const r = 0.6 * width * Math.pow(Math.max(1 - (x / half) ** 2, 0), 0.8);
    return Math.hypot(y, z) < r && (Math.abs(x) > 1.4 || Math.hypot(y, z) > 0.45);
  }).map(([x, y, z]) => [x, y + lift(x / half), z]);
  return [
    { geometry: membrane, look: 'membrane', rim: 'longRim', breath: 0.02 },
    {
      geometry: merge(THREE, [nucleus, beads(THREE, points, rand, [0.05, 0.08], palette.monoGranule)]),
      look: 'solid',
      rim: 'longNucleusDark',
    },
  ];
}

const BUILD = {
  dna, chromatin: chromatinFibre, coil, thread, longCell,
  rbc: redCell, platelet, lymphocyte, monocyte, neutrophil,
};
export const KINDS = Object.keys(BUILD);

export function buildParts(THREE, kind, palette) {
  const parts = BUILD[kind](THREE, palette);
  for (const part of parts) part.geometry.computeBoundingSphere();
  return parts;
}

// ---- drawing ----

// Lit in view space, so the light stays put as an object turns: soft wrap
// lighting (light passes into a cell), a rim at grazing angles, and opacity
// that rises towards the rim, so a membrane reads as a thin translucent
// shell with its nucleus showing through. Depth fades a far object into the
// water and a near one out before it reaches the camera.
const VERTEX = `
uniform float uTime;
uniform float uBreath;
varying vec3 vNormal;
varying vec3 vView;
varying vec3 vTint;
varying float vDepth;
float swell(vec3 p, float t) {
  return sin(p.x * 1.7 + t) * sin(p.y * 1.3 + t * 0.77) * sin(p.z * 1.5 + t * 1.13);
}
void main() {
  vec3 p = position;
  vec3 n = normal;
  float seed = 0.0;
#ifdef USE_INSTANCING
  seed = instanceMatrix[3].x * 0.31 + instanceMatrix[3].z * 0.17;
#endif
  if (uBreath > 0.0) {
    vec3 dir = normalize(p + vec3(1e-5));
    p += dir * uBreath * swell(dir * 2.0, uTime * 0.5 + seed);
  }
#ifdef USE_INSTANCING
  p = (instanceMatrix * vec4(p, 1.0)).xyz;
  n = mat3(instanceMatrix) * n;
#endif
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  vNormal = normalize(normalMatrix * n);
  vView = -mv.xyz;
  vTint = color;
#ifdef USE_INSTANCING_COLOR
  vTint *= instanceColor;
#endif
  vDepth = -mv.z;
  gl_Position = projectionMatrix * mv;
}`;

const FRAGMENT = `
uniform vec3 uRim;
uniform float uRimPower;
uniform float uRimStrength;
uniform float uOpacity;
uniform float uEdgeOpacity;
uniform vec3 uShading;
uniform vec3 uLight;
uniform vec3 uFogColour;
uniform vec4 uDepthFade;
uniform float uHaze;
uniform float uFade;
varying vec3 vNormal;
varying vec3 vView;
varying vec3 vTint;
varying float vDepth;
void main() {
  vec3 n = normalize(vNormal);
  if (!gl_FrontFacing) n = -n;
  vec3 v = normalize(vView);
  float fres = pow(1.0 - clamp(dot(n, v), 0.0, 1.0), uRimPower);
  // uShading: (wrap, ambient, diffuse). More wrap is softer, as light
  // passing into a cell; less shows a surface's relief.
  float wrap = clamp((dot(n, uLight) + uShading.x) / (1.0 + uShading.x), 0.0, 1.0);
  float spec = pow(clamp(dot(n, normalize(uLight + v)), 0.0, 1.0), 48.0);
  vec3 col = vTint * (uShading.y + uShading.z * wrap);
  col = mix(col, uRim, clamp(fres * uRimStrength, 0.0, 1.0));
  col += spec * 0.28;
  float a = mix(uOpacity, uEdgeOpacity, fres);
  col = mix(col, uFogColour, smoothstep(uDepthFade.y, uDepthFade.w, vDepth) * uHaze);
  a *= smoothstep(uDepthFade.x, uDepthFade.y, vDepth) * (1.0 - smoothstep(uDepthFade.z, uDepthFade.w, vDepth)) * uFade;
  if (a < 0.003) discard;
  gl_FragColor = vec4(col, a);
}`;

// How each part is drawn. A shell is drawn twice, its far side first, and
// writes no depth, so what is inside it shows through.
const SOFT = [0.5, 0.62, 0.48];
const LOOKS = {
  solid: { opacity: 1, edge: 1, rimPower: 2.2, rimStrength: 0.25, shading: SOFT },
  // The red cell is lit harder, so its dimple reads.
  body: { opacity: 0.97, edge: 1, rimPower: 2.2, rimStrength: 0.4, shading: [0.08, 0.4, 0.8] },
  thick: { opacity: 0.42, edge: 0.94, rimPower: 2, rimStrength: 0.7, shading: SOFT, shell: true },
  membrane: { opacity: 0.12, edge: 0.8, rimPower: 2.4, rimStrength: 0.9, shading: SOFT, shell: true },
};

// The uniforms every material in one scene shares: time, the light, the
// depth fade and the layer's overall fade. depthFade is [fade in from, fully
// in at, fade out from, gone at], in scene units from the camera.
export function sharedUniforms(THREE, { fog = '#E3ECF5', depthFade = [0, 1e-3, 1e4, 1e5], haze = 0 } = {}) {
  return {
    uTime: { value: 0 },
    uFade: { value: 1 },
    uLight: { value: new THREE.Vector3(-0.5, 0.7, 0.5).normalize() },
    uFogColour: { value: new THREE.Color(fog) },
    uDepthFade: { value: new THREE.Vector4(...depthFade) },
    uHaze: { value: haze },
  };
}

function material(THREE, shared, look, rim, breath, side, order) {
  const m = new THREE.ShaderMaterial({
    vertexShader: VERTEX,
    fragmentShader: FRAGMENT,
    uniforms: {
      ...shared,
      uRim: { value: new THREE.Color(rim) },
      uRimPower: { value: look.rimPower },
      uRimStrength: { value: look.rimStrength },
      uOpacity: { value: look.opacity },
      uEdgeOpacity: { value: look.edge },
      uShading: { value: new THREE.Vector3(...look.shading) },
      uBreath: { value: breath },
    },
    vertexColors: true,
    transparent: true,
    depthWrite: !look.shell,
    side,
  });
  m.userData.order = order;
  return m;
}

function partMaterials(THREE, part, palette, shared) {
  const look = LOOKS[part.look];
  const rim = palette[part.rim];
  const breath = part.breath || 0;
  if (!look.shell) return [material(THREE, shared, look, rim, breath, THREE.FrontSide, 1)];
  const back = { ...look, opacity: look.opacity * 0.4, edge: look.edge * 0.4 };
  return [
    material(THREE, shared, back, rim, breath, THREE.BackSide, 2),
    material(THREE, shared, look, rim, breath, THREE.FrontSide, 3),
  ];
}

// One object as a group of meshes, for a close look.
export function specimen(THREE, kind, palette, shared) {
  const group = new THREE.Group();
  for (const part of buildParts(THREE, kind, palette)) {
    for (const m of partMaterials(THREE, part, palette, shared)) {
      const mesh = new THREE.Mesh(part.geometry, m);
      mesh.renderOrder = m.userData.order;
      group.add(mesh);
    }
  }
  return group;
}

// ---- the water ----

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

// The objects drifting in a volume ahead of a camera that looks down -z
// from the group's origin. Each object keeps a place in screen terms (u, v
// from -1 to 1 across the view) and a depth, so the view stays evenly
// filled at any aspect. update() lets them rise slowly and tumble; its
// `advance` (scene units) carries the camera forward through them, for
// scroll parallax. Objects that pass the camera return far ahead.
export function createBioLayer(THREE, {
  palette = PALETTES.site, density = 'calm', compact = false, fov = 45, near = 3, far = 46, fog = '#E3ECF5',
} = {}) {
  const shared = sharedUniforms(THREE, { fog, depthFade: [near, near + 4, far - 16, far], haze: 0.5 });
  const group = new THREE.Group();
  const rand = rng(41);
  const tanH = Math.tan((fov / 2) * (Math.PI / 180));
  // Even in volume, so the near water is sparse and the far water full.
  const depth = (deep) => Math.cbrt(near ** 3 + rand() * (deep ** 3 - near ** 3));
  const kinds = [];

  for (const [kind, spec] of Object.entries(WATER)) {
    const count = Math.max(1, Math.round(spec[density] * (compact ? 0.5 : 1)));
    let matrix = null;
    let tint = null;
    let radius = 0;
    for (const part of buildParts(THREE, kind, palette)) {
      radius = Math.max(radius, part.geometry.boundingSphere.radius);
      for (const m of partMaterials(THREE, part, palette, shared)) {
        const mesh = new THREE.InstancedMesh(part.geometry, m, count);
        if (matrix) {
          mesh.instanceMatrix = matrix;
        } else {
          matrix = mesh.instanceMatrix;
          matrix.setUsage(THREE.DynamicDrawUsage);
          tint = new THREE.InstancedBufferAttribute(new Float32Array(count * 3), 3);
        }
        mesh.instanceColor = tint;
        mesh.renderOrder = m.userData.order;
        mesh.frustumCulled = false;
        group.add(mesh);
      }
    }
    const st = {
      count, matrix, radius, deep: near + (spec.reach ?? 1) * (far - near),
      u: new Float32Array(count), v: new Float32Array(count), d: new Float32Array(count),
      rise: new Float32Array(count), spin: new Float32Array(count), phase: new Float32Array(count),
      size: new Float32Array(count), axis: [], start: [],
    };
    const scale = spec.size ? spec.size / (2 * radius) : spec.scale;
    for (let i = 0; i < count; i++) {
      st.u[i] = (rand() * 2 - 1) * 1.15;
      st.v[i] = (rand() * 2 - 1) * 1.15;
      st.d[i] = depth(st.deep);
      st.rise[i] = 0.006 + rand() * 0.01;
      st.spin[i] = spec.spin[0] + rand() * (spec.spin[1] - spec.spin[0]);
      st.phase[i] = rand() * Math.PI * 2;
      st.size[i] = scale * (0.88 + rand() * 0.24);
      st.axis.push(new THREE.Vector3(rand() - 0.5, rand() - 0.5, rand() - 0.5).normalize());
      st.start.push(new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(rand() - 0.5, rand() - 0.5, rand() - 0.5).normalize(), rand() * Math.PI * 2));
      const shade = 0.92 + rand() * 0.12;
      tint.setXYZ(i, shade, shade, shade);
    }
    kinds.push(st);
  }

  const pos = new THREE.Vector3();
  const quat = new THREE.Quaternion();
  const scl = new THREE.Vector3();
  const mat = new THREE.Matrix4();
  let last = null;

  function update(time, { advance = 0, aspect = 1 } = {}) {
    const dt = last === null ? 0 : Math.min(0.1, Math.max(0, time - last));
    last = time;
    shared.uTime.value = time;
    for (const st of kinds) {
      for (let i = 0; i < st.count; i++) {
        const span = st.deep - near;
        let d = st.d[i] - advance;
        if (d < near) {
          d += span;
          st.u[i] = (rand() * 2 - 1) * 1.15;
          st.v[i] = (rand() * 2 - 1) * 1.15;
        } else if (d > st.deep) {
          d -= span;
        }
        st.d[i] = d;
        // Leave the top fully out of sight and come back in below.
        const margin = 1.05 + (st.radius * st.size[i]) / (d * tanH);
        let v = st.v[i] + st.rise[i] * dt;
        if (v > margin) v = -margin;
        st.v[i] = v;
        const sway = 0.035 * Math.sin(time * 0.11 + st.phase[i]);
        pos.set((st.u[i] + sway) * d * tanH * aspect, v * d * tanH, -d);
        quat.setFromAxisAngle(st.axis[i], st.spin[i] * time + st.phase[i]).multiply(st.start[i]);
        scl.setScalar(st.size[i]);
        mat.compose(pos, quat, scl).toArray(st.matrix.array, i * 16);
      }
      st.matrix.needsUpdate = true;
    }
  }

  function dispose() {
    group.traverse((o) => {
      if (o.isMesh) {
        o.geometry.dispose();
        o.material.dispose();
      }
    });
  }

  return { group, update, dispose, setFade: (f) => { shared.uFade.value = f; } };
}
