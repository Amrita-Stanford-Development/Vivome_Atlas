// Moving water over the landing's objects (web/js/biocells.js). The objects
// are drawn to a texture once a frame; an effect then shows that texture
// through the water in one full-screen pass, running its own small
// simulation first where it has one. Sizes are in CSS pixels or 0..1 across
// the area drawn, so the look holds at any screen density.
//
// The ripples are a height field on the GPU, as in Evan Wallace's WebGL
// Water and jquery.ripples: each step, every point moves towards the mean
// of its neighbours, so a drop spreads as rings; the rings bend what is
// behind them and catch the light. The ink is dye carried by a slowly
// turning flow (the curl of a noise field, so it swirls without bunching
// up) and fading as it goes.
//
// Needs THREE (three.js r128) and a WebGL2 context that can render to
// half-float textures, which the ripples and the ink need; `supported`
// says whether they can run.

import { rng } from './formations.js';

// The effects, in the order a chooser lists them. `pointer` says what the
// pointer does: nothing, a drop on click, or a wake as it moves.
export const EFFECTS = [
  { name: 'still', label: 'Still', pointer: null, about: 'The soft gel on its own. Only the objects move.' },
  { name: 'flow', label: 'Flowing gel', pointer: null, about: 'The gel drifts, gently bending what is in it, with caustic light moving through it.' },
  { name: 'rain', label: 'Rain', pointer: null, about: 'Now and then a drop lands and its rings spread across the water, bending the objects as they pass.' },
  { name: 'touch', label: 'Touch', pointer: 'click', about: 'Rain, and a drop wherever you click.' },
  { name: 'wake', label: 'Wake', pointer: 'move', about: 'A soft wake follows the pointer across the water.' },
  { name: 'ink', label: 'Ink', pointer: null, about: 'Faint coloured ink curls slowly through the gel, behind the objects.' },
];

const QUAD_VERTEX = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';

const NOISE = `
float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = p * 2.03 + 17.1;
    a *= 0.5;
  }
  return v;
}`;

// One full-screen pass: a shader drawn over the whole of the current target.
function pass(THREE, fragmentShader, uniforms) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
    vertexShader: QUAD_VERTEX,
    fragmentShader,
    uniforms,
    depthTest: false,
    depthWrite: false,
    blending: THREE.NoBlending,
  }));
  mesh.frustumCulled = false;
  const scene = new THREE.Scene();
  scene.add(mesh);
  return {
    uniforms,
    run(renderer, camera, target) {
      if (target !== undefined) renderer.setRenderTarget(target);
      renderer.render(scene, camera);
    },
    dispose() {
      mesh.geometry.dispose();
      mesh.material.dispose();
    },
  };
}

// Two half-float targets that take turns: read one, write the other.
function pingPong(THREE, filter) {
  const make = () => new THREE.WebGLRenderTarget(1, 1, {
    type: THREE.HalfFloatType, format: THREE.RGBAFormat, minFilter: filter, magFilter: filter,
    depthBuffer: false, stencilBuffer: false,
  });
  let read = make();
  let write = make();
  return {
    get read() { return read; },
    get write() { return write; },
    swap() { [read, write] = [write, read]; },
    setSize(w, h) { read.setSize(w, h); write.setSize(w, h); },
    dispose() { read.dispose(); write.dispose(); },
  };
}

// The simulations' grid: 256 cells tall, as wide as the area's aspect.
const GRID = 256;

// A fixed 60 steps a second, whatever the frame rate, at most 3 a frame.
function stepper() {
  let owed = 0;
  return (dt) => {
    owed = Math.min(owed + dt * 60, 3);
    const n = Math.floor(owed);
    owed -= n;
    return n;
  };
}

// Can this renderer run the simulations?
export function supported(renderer) {
  return renderer.capabilities.isWebGL2 && renderer.extensions.has('EXT_color_buffer_float');
}

// The objects, drawn to a texture each frame for an effect to show.
export function createSceneTarget(THREE) {
  const Target = THREE.WebGLMultisampleRenderTarget || THREE.WebGLRenderTarget;
  const target = new Target(1, 1);
  return {
    texture: target.texture,
    setSize(width, height, pixelRatio) {
      target.setSize(Math.max(1, Math.round(width * pixelRatio)), Math.max(1, Math.round(height * pixelRatio)));
    },
    capture(renderer, scene, camera) {
      renderer.setRenderTarget(target);
      renderer.setClearColor(0x000000, 0);
      renderer.clear();
      renderer.render(scene, camera);
      renderer.setRenderTarget(null);
    },
    dispose() { target.dispose(); },
  };
}

// ---- still ----

function still(THREE) {
  const camera = new THREE.Camera();
  const show = pass(THREE, 'uniform sampler2D uScene; varying vec2 vUv; void main() { gl_FragColor = texture2D(uScene, vUv); }',
    { uScene: { value: null } });
  return {
    setSize() {},
    step() {},
    draw(renderer, scene) {
      show.uniforms.uScene.value = scene;
      show.run(renderer, camera);
    },
    drop() {},
    dispose() { show.dispose(); },
  };
}

// ---- flowing gel ----

// The gel drifts and bends what is in it; caustic light (the bright net of
// a pool floor: the edges of a slowly churning cellular pattern, in two
// warped layers) moves through it; and it thickens and thins in broad, slow
// patches. On the light field the caustics are a soft blue, since white
// light would barely show.
const FLOW = `
uniform sampler2D uScene;
uniform vec2 uSize;
uniform float uTime;
uniform float uWarp;
uniform float uLight;
uniform vec3 uLineColour;
varying vec2 vUv;
${NOISE}
vec2 hash2(vec2 p) {
  p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
  return fract(sin(p) * 43758.5453);
}
float cellEdge(vec2 p, float t) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  float d1 = 8.0;
  float d2 = 8.0;
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      vec2 g = vec2(float(x), float(y));
      vec2 o = 0.5 + 0.42 * sin(t + 6.2831 * hash2(i + g));
      float d = length(g + o - f);
      if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) { d2 = d; }
    }
  }
  return d2 - d1;
}
void main() {
  vec2 px = vUv * uSize;
  float t = uTime;
  vec2 p = px / 320.0;
  vec2 flow = vec2(fbm(p + vec2(0.0, t * 0.06)), fbm(p + vec2(4.3, 1.7) - vec2(t * 0.05, 0.0))) - 0.5;
  vec4 scene = texture2D(uScene, vUv + flow * uWarp / uSize);
  vec2 q = px / 150.0;
  q += (vec2(fbm(q * 0.5 + t * 0.04), fbm(q * 0.5 + 7.3 - t * 0.03)) - 0.5) * 0.9;
  float near = 1.0 - smoothstep(0.0, 0.11, cellEdge(q, t * 0.35));
  float far = 1.0 - smoothstep(0.0, 0.08, cellEdge(q * 1.45 + 11.0, t * 0.27 + 2.0));
  float lines = clamp(near * 0.75 + far * 0.45, 0.0, 1.0);
  float body = smoothstep(0.4, 0.8, fbm(p * 0.45 + vec2(t * 0.02, -t * 0.015)));
  float bodyA = clamp(body * 0.1 * uLight, 0.0, 1.0);
  float lineA = clamp(lines * 0.32 * uLight, 0.0, 1.0);
  vec4 c = vec4(vec3(bodyA) + scene.rgb * (1.0 - bodyA), bodyA + scene.a * (1.0 - bodyA));
  gl_FragColor = vec4(uLineColour * lineA + c.rgb * (1.0 - lineA), lineA + c.a * (1.0 - lineA));
}`;

function flow(THREE, { warp = 9, light = 1, colour = '#7DBCE8' } = {}) {
  const camera = new THREE.Camera();
  const show = pass(THREE, FLOW, {
    uScene: { value: null },
    uSize: { value: new THREE.Vector2(1, 1) },
    uTime: { value: 0 },
    uWarp: { value: warp },
    uLight: { value: light },
    uLineColour: { value: new THREE.Color(colour) },
  });
  return {
    setSize(width, height) { show.uniforms.uSize.value.set(width, height); },
    step(renderer, time) { show.uniforms.uTime.value = time; },
    draw(renderer, scene) {
      show.uniforms.uScene.value = scene;
      show.run(renderer, camera);
    },
    drop() {},
    dispose() { show.dispose(); },
  };
}

// ---- ripples ----

const RIPPLE_STEP = `
uniform sampler2D uState;
uniform vec2 uTexel;
uniform float uDamping;
varying vec2 vUv;
void main() {
  vec4 s = texture2D(uState, vUv);
  float mean = 0.25 * (
    texture2D(uState, vUv + vec2(uTexel.x, 0.0)).r + texture2D(uState, vUv - vec2(uTexel.x, 0.0)).r +
    texture2D(uState, vUv + vec2(0.0, uTexel.y)).r + texture2D(uState, vUv - vec2(0.0, uTexel.y)).r);
  s.g = (s.g + (mean - s.r) * 2.0) * uDamping;
  s.r = (s.r + s.g) * 0.999;
  gl_FragColor = s;
}`;

const RIPPLE_DROP = `
uniform sampler2D uState;
uniform vec2 uCentre;
uniform float uRadius;
uniform float uStrength;
uniform float uAspect;
varying vec2 vUv;
void main() {
  vec4 s = texture2D(uState, vUv);
  float r = length((vUv - uCentre) * vec2(uAspect, 1.0)) / uRadius;
  s.r += (0.5 - 0.5 * cos(max(0.0, 1.0 - r) * 3.14159)) * uStrength;
  gl_FragColor = s;
}`;

// The water's surface: its slope bends the objects behind it, brightens
// where it tilts towards the light and shades where it tilts away. On the
// light field the shading is what shows the rings.
const RIPPLE_SHOW = `
uniform sampler2D uScene;
uniform sampler2D uState;
uniform vec2 uTexel;
uniform float uRefract;
uniform vec3 uShade;
varying vec2 vUv;
void main() {
  vec2 slope = vec2(
    texture2D(uState, vUv + vec2(uTexel.x, 0.0)).r - texture2D(uState, vUv - vec2(uTexel.x, 0.0)).r,
    texture2D(uState, vUv + vec2(0.0, uTexel.y)).r - texture2D(uState, vUv - vec2(0.0, uTexel.y)).r);
  vec4 scene = texture2D(uScene, vUv + slope * uRefract);
  vec3 n = normalize(vec3(-slope * 3.0, 1.0));
  vec3 light = normalize(vec3(-0.5, 0.6, 0.62));
  float lit = dot(n, light) - light.z;
  float glint = pow(max(dot(reflect(-light, n), vec3(0.0, 0.0, 1.0)), 0.0), 40.0) * 0.6;
  float hiA = clamp(lit * 2.2 + glint, 0.0, 0.55);
  float shA = clamp(-lit * 2.6, 0.0, 0.4);
  vec4 c = vec4(uShade * shA + scene.rgb * (1.0 - shA), shA + scene.a * (1.0 - shA));
  gl_FragColor = vec4(vec3(hiA) + c.rgb * (1.0 - hiA), hiA + c.a * (1.0 - hiA));
}`;

// `rain`: drops now and then by themselves. drop() adds one where asked.
function ripples(THREE, { rain = true, seed = 7 } = {}) {
  const camera = new THREE.Camera();
  const rand = rng(seed);
  const state = pingPong(THREE, THREE.LinearFilter);
  const texel = new THREE.Vector2(1 / GRID, 1 / GRID);
  const step = pass(THREE, RIPPLE_STEP, { uState: { value: null }, uTexel: { value: texel }, uDamping: { value: 0.994 } });
  const dropPass = pass(THREE, RIPPLE_DROP, {
    uState: { value: null }, uCentre: { value: new THREE.Vector2() }, uRadius: { value: 0.04 }, uStrength: { value: 1 }, uAspect: { value: 1 },
  });
  const show = pass(THREE, RIPPLE_SHOW, {
    uScene: { value: null }, uState: { value: null }, uTexel: { value: texel },
    uRefract: { value: 0.035 }, uShade: { value: new THREE.Color('#4F84B3') },
  });
  const queue = [];
  const steps = stepper();
  let nextRain = 0;   // the first drop falls at once
  return {
    setSize(width, height) {
      const w = Math.max(2, Math.round(GRID * (width / height)));
      state.setSize(w, GRID);
      texel.set(1 / w, 1 / GRID);
      dropPass.uniforms.uAspect.value = width / height;
    },
    drop(u, v, strength = 1, radius = 0.035) { queue.push([u, v, strength, radius]); },
    step(renderer, time, dt) {
      if (rain && time >= nextRain) {
        queue.push([0.05 + rand() * 0.9, 0.05 + rand() * 0.9, 0.5 + rand() * 0.5, 0.025 + rand() * 0.03]);
        nextRain = time + 0.9 + rand() * 1.8;
      }
      for (const [u, v, strength, radius] of queue.splice(0)) {
        dropPass.uniforms.uCentre.value.set(u, v);
        dropPass.uniforms.uStrength.value = strength;
        dropPass.uniforms.uRadius.value = radius;
        dropPass.uniforms.uState.value = state.read.texture;
        dropPass.run(renderer, camera, state.write);
        state.swap();
      }
      for (let i = steps(dt); i > 0; i--) {
        step.uniforms.uState.value = state.read.texture;
        step.run(renderer, camera, state.write);
        state.swap();
      }
      renderer.setRenderTarget(null);
    },
    draw(renderer, scene) {
      show.uniforms.uScene.value = scene;
      show.uniforms.uState.value = state.read.texture;
      show.run(renderer, camera);
    },
    dispose() { state.dispose(); step.dispose(); dropPass.dispose(); show.dispose(); },
  };
}

// ---- ink ----

const INK_MOVE = `
uniform sampler2D uDye;
uniform float uTime;
uniform float uAspect;
uniform float uSpeed;
uniform float uKeep;
varying vec2 vUv;
${NOISE}
float potential(vec2 p) { return fbm(p * 1.4 + vec2(uTime * 0.03, -uTime * 0.02)); }
void main() {
  vec2 p = vUv * vec2(uAspect, 1.0) * 2.0;
  float e = 0.02;
  float dx = potential(p + vec2(e, 0.0)) - potential(p - vec2(e, 0.0));
  float dy = potential(p + vec2(0.0, e)) - potential(p - vec2(0.0, e));
  vec2 velocity = vec2(dy, -dx) / (2.0 * e) * uSpeed;
  gl_FragColor = texture2D(uDye, vUv - velocity * vec2(1.0 / uAspect, 1.0)) * uKeep;
}`;

const INK_SPLAT = `
uniform sampler2D uDye;
uniform vec2 uCentre;
uniform float uRadius;
uniform vec4 uColour;
uniform float uAspect;
varying vec2 vUv;
void main() {
  vec2 d = (vUv - uCentre) * vec2(uAspect, 1.0);
  float a = exp(-dot(d, d) / (uRadius * uRadius));
  vec4 dye = texture2D(uDye, vUv);
  gl_FragColor = uColour * a + dye * (1.0 - uColour.a * a);
}`;

// The ink sits behind the objects, so they stay clear.
const INK_SHOW = `
uniform sampler2D uScene;
uniform sampler2D uDye;
varying vec2 vUv;
void main() {
  vec4 scene = texture2D(uScene, vUv);
  vec4 ink = clamp(texture2D(uDye, vUv), 0.0, 1.0);
  gl_FragColor = scene + ink * (1.0 - scene.a);
}`;

function ink(THREE, { seed = 11, colours = ['#7CC4F0', '#B39DEB', '#F6B48F', '#5CC9C0', '#F29AC2'] } = {}) {
  const camera = new THREE.Camera();
  const rand = rng(seed);
  const dye = pingPong(THREE, THREE.LinearFilter);
  const move = pass(THREE, INK_MOVE, {
    uDye: { value: null }, uTime: { value: 0 }, uAspect: { value: 1 }, uSpeed: { value: 0.0003 }, uKeep: { value: 0.9975 },
  });
  const splat = pass(THREE, INK_SPLAT, {
    uDye: { value: null }, uCentre: { value: new THREE.Vector2() }, uRadius: { value: 0.1 },
    uColour: { value: new THREE.Vector4() }, uAspect: { value: 1 },
  });
  const show = pass(THREE, INK_SHOW, { uScene: { value: null }, uDye: { value: null } });
  const steps = stepper();
  const tint = new THREE.Color();
  let next = 0;
  let seeded = 0;
  const addSplat = (renderer) => {
    tint.set(colours[Math.floor(rand() * colours.length)]);
    const a = 0.16 + rand() * 0.12;
    splat.uniforms.uColour.value.set(tint.r * a, tint.g * a, tint.b * a, a);
    splat.uniforms.uCentre.value.set(0.08 + rand() * 0.84, 0.08 + rand() * 0.84);
    splat.uniforms.uRadius.value = 0.06 + rand() * 0.07;
    splat.uniforms.uDye.value = dye.read.texture;
    splat.run(renderer, camera, dye.write);
    dye.swap();
  };
  return {
    setSize(width, height) {
      dye.setSize(Math.max(2, Math.round(GRID * (width / height))), GRID);
      move.uniforms.uAspect.value = width / height;
      splat.uniforms.uAspect.value = width / height;
      seeded = 0;
    },
    drop() {},
    step(renderer, time, dt) {
      // Start with some ink already in the water, then add a little at a time.
      while (seeded < 6) { addSplat(renderer); seeded++; }
      if (time >= next) { addSplat(renderer); next = time + 1.6 + rand() * 1.6; }
      move.uniforms.uTime.value = time;
      for (let i = steps(dt); i > 0; i--) {
        move.uniforms.uDye.value = dye.read.texture;
        move.run(renderer, camera, dye.write);
        dye.swap();
      }
      renderer.setRenderTarget(null);
    },
    draw(renderer, scene) {
      show.uniforms.uScene.value = scene;
      show.uniforms.uDye.value = dye.read.texture;
      show.run(renderer, camera);
    },
    dispose() { dye.dispose(); move.dispose(); splat.dispose(); show.dispose(); },
  };
}

// An effect by name. Each one has setSize(width, height) in CSS pixels;
// step(renderer, time, dt) to run its simulation (it leaves the renderer on
// the screen); draw(renderer, sceneTexture) to draw the area, into the
// viewport the caller has set; drop(u, v, strength, radius) for a drop at
// (u, v), 0..1 from the bottom left; and dispose().
export function createEffect(THREE, name) {
  if (name === 'flow') return flow(THREE);
  if (name === 'rain' || name === 'touch') return ripples(THREE, { seed: name === 'rain' ? 7 : 8 });
  if (name === 'wake') return ripples(THREE, { rain: false });
  if (name === 'ink') return ink(THREE);
  return still(THREE);
}
