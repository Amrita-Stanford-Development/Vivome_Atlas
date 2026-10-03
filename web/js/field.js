// The landing's field: the camera flies through the water as the story is
// read, and the particles in it gather into a structure for each chapter
// (web/js/formations.js, timed by CHAPTERS in web/js/motion.js), then drift
// back into the water.
//
// Two kinds of particle, both soft glowing points drawn by the shader below:
// - the pool travels with the camera and is what forms the structures. It has
//   one particle per cell in web/data/story_cells.json, so the atlas chapters
//   show the real cells at their real coordinates;
// - the ambient water is fixed along the flight path, so the camera visibly
//   moves through it.
//
// Needs the global THREE (three.js r128, loaded by web/js/story.js from the
// same cdnjs URL as the atlas viewer). It sits above background.js's
// breathing field and the living water of web/js/biofield.js.

import { smooth, between, stagger, formationState, introWeight, CHAPTERS } from './motion.js';
import {
  ROLE, rng, cell, readouts, plate, growthRings, helix, atlas, centroid, fromMask,
} from './formations.js';

const SPACING = 14;   // world units between chapters along the flight
const DIST = 16;      // how far ahead of the camera a structure assembles
const FOV = 45;

const VERTEX = `
attribute vec3 aColor;
attribute float aSize;
attribute float aRing;
attribute float aAlpha;
attribute float aPhase;
attribute float aDrift;
uniform float uScale;
uniform float uTime;
varying vec3 vColor;
varying float vRing;
varying float vAlpha;
void main() {
  vec3 p = position + aDrift * vec3(sin(uTime * 0.35 + aPhase) * 0.35, cos(uTime * 0.3 + aPhase * 1.3) * 0.3, 0.0);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float depth = -mv.z;
  gl_PointSize = aSize * uScale / depth;
  gl_Position = projectionMatrix * mv;
  vColor = aColor;
  vRing = aRing;
  // Fade out right at the camera and in the far distance.
  vAlpha = aAlpha * smoothstep(0.8, 4.0, depth) * smoothstep(80.0, 36.0, depth);
}`;

const FRAGMENT = `
varying vec3 vColor;
varying float vRing;
varying float vAlpha;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  float glow = smoothstep(1.0, 0.25, d);
  float core = smoothstep(0.5, 0.0, d);
  float ring = smoothstep(0.24, 0.0, abs(d - 0.68));
  float a = mix(glow * 0.5 + core * 0.5, ring, vRing) * vAlpha;
  if (a < 0.01) discard;
  gl_FragColor = vec4(mix(vColor, vec3(1.0), core * 0.3 * (1.0 - vRing)), a);
}`;

function cssColor(name, fallback) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

// Text as points: draw it on a canvas and keep the lit pixels.
function textPoints(text, n, seed) {
  const size = 120;
  const font = `600 ${size}px Poppins, sans-serif`;
  const c = document.createElement('canvas');
  const g = c.getContext('2d');
  g.font = font;
  const w = Math.ceil(g.measureText(text).width) + 24;
  const h = Math.ceil(size * 1.4);
  c.width = w;
  c.height = h;
  g.font = font;
  g.textBaseline = 'middle';
  g.fillText(text, 12, h / 2);
  const pixels = g.getImageData(0, 0, w, h).data;
  const step = 3;
  const mw = Math.floor(w / step);
  const mh = Math.floor(h / step);
  const mask = new Uint8Array(mw * mh);
  for (let y = 0; y < mh; y++) {
    for (let x = 0; x < mw; x++) mask[y * mw + x] = pixels[((y * step) * w + x * step) * 4 + 3] > 128 ? 1 : 0;
  }
  return fromMask(mask, mw, mh, n, seed);
}

export function createField(THREE, canvas, cells, { compact = false } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 200);

  // Phones get every second cell and a thinner water.
  const step = compact ? 2 : 1;
  const rnaRows = cells.rna.filter((_, i) => i % step === 0);
  const protRows = cells.prot.filter((_, i) => i % step === 0);
  const R = rnaRows.length;
  const P = R + protRows.length;
  const A = compact ? 1400 : 3600;
  const N = P + A;

  const colour = {
    [ROLE.cell]: new THREE.Color(cssColor('--accent-bright', '#0073AD')),
    [ROLE.rna]: new THREE.Color(cssColor('--rna', '#C8641E')),
    [ROLE.prot]: new THREE.Color(cssColor('--prot', '#2F8F6A')),
    [ROLE.ring]: new THREE.Color(cssColor('--prot', '#2F8F6A')),
    [ROLE.dot]: new THREE.Color(cssColor('--dot', '#E4577A')),
    [ROLE.pale]: new THREE.Color('#7FBDE6'),
  };
  const roleSize = { [ROLE.cell]: 0.085, [ROLE.rna]: 0.1, [ROLE.prot]: 0.1, [ROLE.ring]: 0.16, [ROLE.dot]: 0.6, [ROLE.pale]: 0.075 };
  const waterBlues = ['#0073AD', '#2F9BD8', '#7FC4EC', '#5AAEE6'].map((h) => new THREE.Color(h));

  // ---- the structures, in formation units ----
  const centre = centroid([...rnaRows, ...protRows]);
  const atlasRna = atlas(rnaRows, ROLE.rna, centre);
  const atlasProt = atlas(protRows, ROLE.prot, centre);
  const abstained = new Uint8Array(P);
  protRows.forEach((r, i) => { abstained[R + i] = r[3] ? 1 : 0; });
  const shapes = {
    cell: cell(P),
    readouts: readouts(P),
    plate: plate(P),
    rings: growthRings(P),
    helix: helix(P),
  };
  let question = null;
  let wordmark = null;
  // Text needs the webfont; until it has loaded, those structures wait.
  document.fonts.ready.then(() => {
    question = textPoints('Where does your cell belong?', P, 21);
    wordmark = textPoints('VivOME', P, 22);
  });

  // ---- particles ----
  const geometry = new THREE.BufferGeometry();
  const position = new Float32Array(N * 3);
  const aColor = new Float32Array(N * 3);
  const aSize = new Float32Array(N);
  const aRing = new Float32Array(N);
  const aAlpha = new Float32Array(N);
  const aPhase = new Float32Array(N);
  const aDrift = new Float32Array(N);
  const rand = rng(31);

  // Where each pool particle rests in the water, relative to the camera, and
  // how long it lags behind the others when a structure gathers.
  const water = new Float32Array(P * 3);
  const lag = new Float32Array(P);
  const waterColour = [];
  const waterSize = new Float32Array(N);
  const waterAlpha = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const blue = waterBlues[Math.floor(rand() * waterBlues.length)];
    waterColour.push(blue);
    waterSize[i] = 0.05 + rand() * 0.11;
    waterAlpha[i] = 0.35 + rand() * 0.45;
    aPhase[i] = rand() * Math.PI * 2;
    aDrift[i] = 1;
    blue.toArray(aColor, i * 3);
    aSize[i] = waterSize[i];
    aAlpha[i] = waterAlpha[i];
    if (i < P) {
      water[i * 3] = (rand() - 0.5) * 2;       // scaled to the view each frame
      water[i * 3 + 1] = (rand() - 0.5) * 2;
      water[i * 3 + 2] = 6 + rand() * 34;       // depth ahead of the camera
      lag[i] = rand();
    } else {
      position[i * 3] = (rand() - 0.5) * 52;
      position[i * 3 + 1] = (rand() - 0.5) * 32;
      position[i * 3 + 2] = 12 - rand() * (CHAPTERS.length * SPACING + 60);
    }
  }
  for (const [name, array, size] of [
    ['position', position, 3], ['aColor', aColor, 3], ['aSize', aSize, 1], ['aRing', aRing, 1],
    ['aAlpha', aAlpha, 1], ['aPhase', aPhase, 1], ['aDrift', aDrift, 1],
  ]) {
    geometry.setAttribute(name, new THREE.BufferAttribute(array, size));
  }
  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX,
    fragmentShader: FRAGMENT,
    uniforms: { uScale: { value: 1 }, uTime: { value: 0 } },
    transparent: true,
    depthWrite: false,
  });
  scene.add(new THREE.Points(geometry, material));

  let halfH = 1;
  let halfW = 1;
  function resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    halfH = Math.tan((FOV / 2) * Math.PI / 180) * DIST;
    halfW = halfH * camera.aspect;
    material.uniforms.uScale.value = (h / 2 / Math.tan((FOV / 2) * Math.PI / 180)) * renderer.getPixelRatio();
  }
  resize();

  const target = [0, 0, 0];
  const mixColour = new THREE.Color();
  const scratch = new THREE.Color();

  // One structure's target for pool particle i, in formation units, with its
  // role blend (roleA -> roleB by m), whether it is a ring, and a gate that
  // holds it in the water until its moment in the structure's phase.
  function aim(name, phase, i, time) {
    let ax; let ay; let az; let roleA; let roleB = null; let m = 0; let ring = 0; let gate = 1;
    const at = (shape) => { ax = shape.pos[i * 3]; ay = shape.pos[i * 3 + 1]; az = shape.pos[i * 3 + 2]; roleA = shape.role[i]; };
    if (name === 'question') {
      if (!question) return null;
      at(question);
    } else if (name === 'finale' && !wordmark) {
      at(shapes.helix);
    } else if (name === 'cell') {
      // The cell unwinds into its two readouts in the second chapter.
      m = smooth(between(phase, 0.5, 0.85));
      const a = shapes.cell;
      const b = shapes.readouts;
      ax = a.pos[i * 3] + (b.pos[i * 3] - a.pos[i * 3]) * m;
      ay = a.pos[i * 3 + 1] + (b.pos[i * 3 + 1] - a.pos[i * 3 + 1]) * m;
      az = a.pos[i * 3 + 2] + (b.pos[i * 3 + 2] - a.pos[i * 3 + 2]) * m;
      roleA = a.role[i];
      roleB = b.role[i];
    } else if (name === 'atlas') {
      // The RNA reference first; then the protein sample streams into its
      // real places; then the cells the model abstained on lift out as rings.
      if (i < R) at(atlasRna);
      else {
        const j = i - R;
        ax = atlasProt.pos[j * 3]; ay = atlasProt.pos[j * 3 + 1]; az = atlasProt.pos[j * 3 + 2]; roleA = ROLE.prot;
        gate = smooth(stagger(between(phase, 0.3, 0.62), j % 80, 80, 0.85));
        if (abstained[i]) {
          const lift = smooth(between(phase, 0.7, 0.92));
          const k = 1 + 0.55 * lift;
          ax *= k; ay *= k; az *= k;
          ring = lift;
        }
      }
    } else if (name === 'finale') {
      m = smooth(between(phase, 0.35, 0.75));
      const a = shapes.helix;
      ax = a.pos[i * 3] + (wordmark.pos[i * 3] * 1.1 - a.pos[i * 3]) * m;
      ay = a.pos[i * 3 + 1] + (wordmark.pos[i * 3 + 1] * 1.1 - a.pos[i * 3 + 1]) * m;
      az = a.pos[i * 3 + 2] * (1 - m);
      roleA = a.role[i];
      roleB = ROLE.cell;
      if (i === P - 1) { ax = 1.22; ay = 0.12; az = 0; roleA = ROLE.dot; roleB = ROLE.dot; }
    } else {
      at(shapes[name]);
    }
    // Structures turn slowly in the water; text and the plate face the reader.
    if (name === 'cell' || name === 'atlas' || name === 'rings') {
      // Once the cell has unwound, its two readouts face the reader.
      const a = (time * 0.08 + phase * 1.2) * (name === 'cell' ? 1 - m : 1);
      const c = Math.cos(a);
      const s = Math.sin(a);
      const x = ax * c - az * s;
      az = ax * s + az * c;
      ax = x;
    }
    target[0] = ax; target[1] = ay; target[2] = az;
    return { roleA, roleB: roleB ?? roleA, m, ring, gate };
  }

  const scaleFor = (name) => {
    const base = Math.min(halfW, halfH * 1.25);
    if (name === 'question') return halfW * 0.8;
    if (name === 'finale') return base * 0.42;
    if (name === 'plate') return Math.min(halfW * 0.3, halfH * 0.8);
    if (name === 'atlas') return halfH * (compact ? 0.6 : 0.78);
    return halfH * (compact ? 0.5 : 0.62);
  };

  // state: flight (chapters travelled), time (s), introMs (ms since the intro
  // began, or null once it has been seen).
  function render({ flight, time, introMs }) {
    camera.position.set(Math.sin(flight * 0.9) * 1.4, Math.cos(flight * 0.7) * 0.9, -flight * SPACING);
    camera.rotation.z = Math.sin(flight * 0.5) * 0.03;
    material.uniforms.uTime.value = time;

    let { name, weight, phase, x } = formationState(flight);
    const intro = introMs === null ? 0 : introWeight(introMs);
    if (weight === 0 && intro > 0) { name = 'question'; weight = intro; phase = 0; x = 0; }

    const scale = scaleFor(name);
    const cx = camera.position.x + (compact ? 0 : x * halfW * 0.44);
    // The finale's structure rises above its card.
    const cy = camera.position.y + (name === 'finale' ? halfH * 0.64 : 0);
    const cz = camera.position.z - DIST;
    const spreadX = halfW * 1.9;
    const spreadY = halfH * 1.9;

    for (let i = 0; i < P; i++) {
      const j = i * 3;
      const depth = water[j + 2];
      const wx = camera.position.x + water[j] * spreadX * (depth / DIST);
      const wy = camera.position.y + water[j + 1] * spreadY * (depth / DIST);
      const wz = camera.position.z - depth;
      const aimed = weight > 0 ? aim(name, phase, i, time) : null;
      const w = aimed ? smooth(between(weight * aimed.gate, lag[i] * 0.35, lag[i] * 0.35 + 0.65)) : 0;
      if (w === 0) {
        position[j] = wx; position[j + 1] = wy; position[j + 2] = wz;
        waterColour[i].toArray(aColor, j);
        aSize[i] = waterSize[i]; aAlpha[i] = waterAlpha[i]; aRing[i] = 0; aDrift[i] = 1;
        continue;
      }
      const tx = cx + target[0] * scale;
      const ty = cy + target[1] * scale;
      const tz = cz + target[2] * scale;
      position[j] = wx + (tx - wx) * w;
      position[j + 1] = wy + (ty - wy) * w;
      position[j + 2] = wz + (tz - wz) * w;
      mixColour.copy(colour[aimed.roleA]).lerp(colour[aimed.roleB], aimed.m);
      mixColour.lerp(colour[ROLE.ring], aimed.ring);
      scratch.copy(waterColour[i]).lerp(mixColour, w).toArray(aColor, j);
      // Text needs slightly larger points to read.
      const size = (roleSize[aimed.m > 0.5 ? aimed.roleB : aimed.roleA] + aimed.ring * 0.06)
        * (name === 'question' || (name === 'finale' && aimed.m > 0.5) ? 1.3 : 1);
      aSize[i] = waterSize[i] + (size - waterSize[i]) * w;
      aAlpha[i] = waterAlpha[i] + (0.95 - waterAlpha[i]) * w;
      aRing[i] = aimed.ring * w;
      aDrift[i] = 1 - w;
    }
    for (const attr of ['position', 'aColor', 'aSize', 'aRing', 'aAlpha', 'aDrift']) {
      geometry.attributes[attr].needsUpdate = true;
    }
    renderer.render(scene, camera);
  }

  return { render, resize };
}
