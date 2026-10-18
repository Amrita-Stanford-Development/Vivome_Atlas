// The dive: one continuous shot of the site's living water under all twelve
// scenes. It is web/js/biofield.js's water (the cells and threads of
// web/js/biocells.js through an effect of web/js/water.js, over the
// particles of web/js/background.js, here lib/field.js), with three
// things the site does not need:
//
// - a clock HyperFrames owns: every frame is drawn on its `hf-seek` event,
//   for that exact time, never from requestAnimationFrame. The water's
//   state is stepped on a fixed 60 a second grid from the start of the film
//   (the cells) or of the scene (the ripples and the ink), so a frame
//   rendered on its own looks the same as one reached by playing;
// - depth: the water darkens from the surface to the floor and lightens
//   again on the way up, with light shafts, caustics and a waterline;
// - the film's motif: a time code and a depth gauge.
//
// It also draws the scenes' data pictures (lib/scenes.js) on the same seek.

import { PALETTES, createBioLayer } from '../vendor/site/biocells.js';
import { createEffect, createSceneTarget, supported } from '../vendor/site/water.js';
import { createField } from './field.js';
import { PLAN } from './plan.js';
import { DRAW, sceneRoots } from './scenes.js';

const W = 1920;
const H = 1080;
const STEP = 1 / 60;
const V = window.VIVOME;
const FRAMES = V.frames;
const THREE = window.THREE;

const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
const smooth = (x) => { const t = clamp(x); return t * t * (3 - 2 * t); };
const lerp = (pair, t, fallback = 0) => (pair ? pair[0] + (pair[1] - pair[0]) * t : fallback);

export function locate(t) {
  let index = FRAMES.length - 1;
  for (let i = 0; i < FRAMES.length; i++) if (t < FRAMES[i].start + FRAMES[i].seconds) { index = i; break; }
  const f = FRAMES[index];
  const local = clamp(t - f.start, 0, f.seconds);
  return { index, frame: f, plan: PLAN[f.id], local, p: local / f.seconds };
}

// ---- depth: the colour of the water, from the surface (0) to the floor (1) ----

const STOPS = [
  [0, '#E4F0F9', '#B4D3EB'],
  [0.35, '#CBE1F2', '#7DB0D7'],
  [0.7, '#6EA2CB', '#1E5B8A'],
  [1, '#3A76A4', '#0A3152'],
];
const hex = (h) => new THREE.Color(h);
function waterColours(d) {
  let i = 0;
  while (i < STOPS.length - 2 && d > STOPS[i + 1][0]) i++;
  const [d0, t0, b0] = STOPS[i];
  const [d1, t1, b1] = STOPS[i + 1];
  const u = clamp((d - d0) / (d1 - d0));
  return [hex(t0).lerp(hex(t1), u), hex(b0).lerp(hex(b1), u)];
}

export function depthAt(t) {
  const { frame, p } = locate(t);
  return lerp(frame.depth, smooth(p));
}

// ---- the renderer and its passes ----

const canvas = document.getElementById('dive');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.autoClear = false;
const canSimulate = supported(renderer);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 200);
const target = createSceneTarget(THREE);
target.setSize(W, H, 1);
const flat = new THREE.Camera();

const field = createField(W, H);
const fieldTexture = new THREE.CanvasTexture(field.canvas);

const QUAD = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';
const NOISE = `
float hash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) { float v = 0.0; float a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p = p * 2.03 + 17.1; a *= 0.5; } return v; }
vec2 hash2(vec2 p) { p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3))); return fract(sin(p) * 43758.5453); }
float cellEdge(vec2 p, float t) {
  vec2 i = floor(p); vec2 f = fract(p); float d1 = 8.0; float d2 = 8.0;
  for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
    vec2 g = vec2(float(x), float(y)); vec2 o = 0.5 + 0.42 * sin(t + 6.2831 * hash2(i + g));
    float d = length(g + o - f); if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) { d2 = d; }
  }
  return d2 - d1;
}`;

// Behind the cells: the water's body, light shafts, caustics, the floor's
// pool of light and the particles. It fills only what the cells leave
// uncovered (it is drawn after them, under their alpha).
const BACK = `
uniform vec3 uTop; uniform vec3 uBottom; uniform float uTime; uniform float uShafts;
uniform float uCaustic; uniform float uPool; uniform float uAspect; uniform sampler2D uField;
varying vec2 vUv;
${NOISE}
void main() {
  vec2 uv = vUv;
  vec3 col = mix(uBottom, uTop, smoothstep(0.0, 1.0, uv.y));
  float sx = (uv.x - 0.5) * uAspect + (1.0 - uv.y) * 0.34;
  float rays = smoothstep(0.44, 0.84, fbm(vec2(sx * 3.1, uTime * 0.05))) * pow(uv.y, 1.3);
  col = mix(col, vec3(0.93, 0.97, 1.0), clamp(rays * uShafts * 0.42, 0.0, 1.0));
  vec2 q = uv * vec2(uAspect, 1.0) * 5.2;
  q += (vec2(fbm(q * 0.5 + uTime * 0.04), fbm(q * 0.5 + 7.3 - uTime * 0.03)) - 0.5) * 0.9;
  float net = 1.0 - smoothstep(0.0, 0.1, cellEdge(q, uTime * 0.35));
  col += vec3(0.72, 0.88, 1.0) * net * uCaustic * 0.11 * (0.35 + 0.65 * uv.y);
  float pool = exp(-pow(length((uv - vec2(0.5, 0.4)) * vec2(uAspect, 1.0)) * 1.5, 2.0));
  col += vec3(0.32, 0.58, 0.84) * pool * uPool * 0.32;
  vec4 f = texture2D(uField, uv);
  col = mix(col, f.rgb, f.a);
  float v = length((uv - 0.5) * vec2(uAspect, 1.0));
  col *= 1.0 - 0.16 * smoothstep(0.55, 1.15, v);
  gl_FragColor = vec4(col, 1.0);
}`;

// Over everything: the surface, when it is in sight. Above the waterline
// is the light (Snell's window, seen from below); along it a bright
// meniscus; under it a glow.
const SURFACE = `
uniform float uWaterline; uniform float uTime; uniform float uAspect;
varying vec2 vUv;
${NOISE}
void main() {
  vec2 uv = vUv;
  float x = uv.x * uAspect;
  float wl = uWaterline + 0.011 * sin(x * 7.0 + uTime * 1.1) + 0.006 * sin(x * 19.0 - uTime * 1.9);
  float above = smoothstep(wl - 0.0025, wl + 0.0025, uv.y);
  float line = exp(-pow((uv.y - wl) * 260.0, 2.0));
  float glow = exp(-pow((uv.y - wl) * 14.0, 2.0)) * (1.0 - above);
  vec2 q = vec2(x, uv.y) * 7.0;
  q += (vec2(fbm(q * 0.4 + uTime * 0.06), fbm(q * 0.4 + 5.1 - uTime * 0.05)) - 0.5) * 1.1;
  float shimmer = 1.0 - smoothstep(0.0, 0.12, cellEdge(q, uTime * 0.5));
  vec3 sky = mix(vec3(0.95, 0.975, 1.0), vec3(1.0), clamp((uv.y - wl) * 2.5, 0.0, 1.0));
  sky = mix(sky, vec3(0.80, 0.90, 0.98), shimmer * 0.22);
  float a = clamp(max(above, max(line * 0.95, glow * 0.4)), 0.0, 1.0);
  vec3 c = mix(vec3(1.0), sky, above);
  c = mix(c, vec3(0.42, 0.66, 0.86), line * (1.0 - above) * 0.85);
  gl_FragColor = vec4(c * a, a);
}`;

function pass(fragmentShader, uniforms, blending) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
    vertexShader: QUAD, fragmentShader, uniforms, depthTest: false, depthWrite: false, transparent: true, ...blending,
  }));
  mesh.frustumCulled = false;
  const s = new THREE.Scene();
  s.add(mesh);
  return { uniforms, draw: () => renderer.render(s, flat) };
}

const back = pass(BACK, {
  uTop: { value: new THREE.Color() }, uBottom: { value: new THREE.Color() }, uTime: { value: 0 },
  uShafts: { value: 1 }, uCaustic: { value: 1 }, uPool: { value: 0 }, uAspect: { value: W / H }, uField: { value: fieldTexture },
}, {
  blending: THREE.CustomBlending, blendEquation: THREE.AddEquation,
  blendSrc: THREE.OneMinusDstAlphaFactor, blendDst: THREE.OneFactor,
  blendSrcAlpha: THREE.OneMinusDstAlphaFactor, blendDstAlpha: THREE.OneFactor,
});
const surface = pass(SURFACE, { uWaterline: { value: 2 }, uTime: { value: 0 }, uAspect: { value: W / H } }, {
  blending: THREE.CustomBlending, blendEquation: THREE.AddEquation,
  blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
  blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
});

// ---- the cells: stepped from the film's start ----

let layer = null;
let layerStep = 0;
function freshLayer() {
  if (layer) { scene.remove(layer.group); layer.dispose(); }
  layer = createBioLayer(THREE, { palette: PALETTES.vivid, density: 'rich' });
  scene.add(layer.group);
  layerStep = 0;
  layer.update(0, { aspect: W / H });
}
function cellsTo(step) {
  if (!layer || step < layerStep) freshLayer();
  while (layerStep < step) { layerStep++; layer.update(layerStep * STEP, { aspect: W / H }); }
}

// ---- the effect: stepped from its scene's start ----

let fx = null;
let fxScene = -1;
let fxStep = 0;
function effectName(plan) {
  return canSimulate || plan.effect === 'still' || plan.effect === 'flow' ? plan.effect : 'flow';
}
function scripted(plan, s) {
  const out = [];
  const w = plan.wake;
  if (w && s >= w.from && s <= w.to && Math.round(s / STEP) % 4 === 0) {
    const u = (s - w.from) / (w.to - w.from) * (w.path.length - 1);
    const k = Math.min(w.path.length - 2, Math.floor(u));
    const f = u - k;
    out.push([w.path[k][0] + (w.path[k + 1][0] - w.path[k][0]) * f, w.path[k][1] + (w.path[k + 1][1] - w.path[k][1]) * f, 0.3, 0.026]);
  }
  for (const [at, u, v, strength, radius] of plan.splash ?? []) {
    if (Math.abs(s - at) < STEP / 2) out.push([u, v, strength, radius]);
  }
  return out;
}
function effectTo(index, plan, step) {
  if (!fx || fxScene !== index || step < fxStep) {
    fx?.dispose();
    fx = createEffect(THREE, effectName(plan));
    fx.setSize(W, H);
    fxScene = index;
    fxStep = 0;
    fx.step(renderer, 0, 0);
  }
  while (fxStep < step) {
    fxStep++;
    for (const d of scripted(plan, fxStep * STEP)) fx.drop(...d);
    fx.step(renderer, fxStep * STEP, STEP);
  }
}

// How far the water has risen past the camera by time t, in background.js's
// frames: each scene's pace, added up.
function climbAt(t) {
  let climb = 0;
  for (const f of FRAMES) {
    const span = clamp(t - f.start, 0, f.seconds);
    climb += span * 60 * (PLAN[f.id].rise ?? 1);
    if (t < f.start + f.seconds) break;
  }
  return climb;
}

// ---- the gel's grain: white specks with page.css's alpha curve
// (0.55 x noise - 0.2), from seeded noise so every render matches ----

(function grain() {
  const tile = document.createElement('canvas');
  tile.width = 180;
  tile.height = 180;
  const g = tile.getContext('2d');
  const img = g.createImageData(180, 180);
  let s = 0x9E3779B9;
  const next = () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 10000) / 10000; };
  for (let i = 0; i < 180 * 180; i++) {
    img.data[i * 4] = 255;
    img.data[i * 4 + 1] = 255;
    img.data[i * 4 + 2] = 255;
    img.data[i * 4 + 3] = Math.round(clamp(0.55 * next() - 0.2) * 255);
  }
  g.putImageData(img, 0, 0);
  document.getElementById('grain').style.backgroundImage = `url(${tile.toDataURL('image/png')})`;
})();

// ---- the film's motif: the time code and the depth gauge ----

const root = document.getElementById('root');
const frost = document.getElementById('frost');
const clock = document.getElementById('hud-time');
const chapter = document.getElementById('hud-chapter');
const mark = document.getElementById('gauge-mark');
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s) % 60).padStart(2, '0')}`;

// The water clouds for a moment over a cut between unlike scenes.
function dip(t) {
  let d = 0;
  for (let i = 1; i < FRAMES.length; i++) {
    if (PLAN[FRAMES[i].id].cut !== 'dip') continue;
    d = Math.max(d, Math.exp(-(((t - FRAMES[i].start) / 0.32) ** 2)));
  }
  return d;
}

// ---- one frame ----

export function draw(t) {
  const { index, frame, plan, local, p } = locate(t);
  const e = smooth(p);
  const d = lerp(frame.depth, e);
  cellsTo(Math.round(t / STEP));
  effectTo(index, plan, Math.round(local / STEP));

  camera.fov = lerp(plan.fov, e, 45);
  camera.rotation.set(lerp(plan.pitch, e), lerp(plan.yaw, e), lerp(plan.roll, e));
  camera.updateProjectionMatrix();
  layer.setFade(clamp(t / 1.6));

  field.draw(t, { climb: climbAt(t), density: lerp(plan.field, e, 0.6), glow: 0.9 + d * 0.7, links: plan.links ?? 1 });
  fieldTexture.needsUpdate = true;

  const [top, bottom] = waterColours(d);
  back.uniforms.uTop.value.copy(top);
  back.uniforms.uBottom.value.copy(bottom);
  back.uniforms.uTime.value = t;
  back.uniforms.uShafts.value = 1 - d * 0.55;
  back.uniforms.uCaustic.value = plan.caustics ?? 0.6;
  back.uniforms.uPool.value = plan.pool ?? 0;

  renderer.setRenderTarget(null);
  renderer.setScissorTest(false);
  target.capture(renderer, scene, camera);
  renderer.setViewport(0, 0, W, H);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  fx.draw(renderer, target.texture);
  back.draw();
  if (plan.waterline) {
    const wl = lerp(plan.waterline, smooth(p / (plan.surfaceBy ?? 1)));
    if (wl > -0.05 && wl < 1.05) {
      surface.uniforms.uWaterline.value = wl;
      surface.uniforms.uTime.value = t;
      surface.draw();
    } else if (wl <= -0.05) {
      surface.uniforms.uWaterline.value = -1;
      surface.uniforms.uTime.value = t;
      surface.draw();
    }
  }

  // The frost is the site's gel: thick near the surface, thin in the deep.
  frost.style.opacity = String(clamp(0.8 - d * 0.66 + (plan.frost ?? 0) + dip(t) * 0.55, 0.06, 1));
  root.classList.toggle('is-deep', d >= 0.45);
  clock.textContent = fmt(t);
  chapter.textContent = V.chapters.find((c) => c.id === frame.chapter)?.label ?? '';
  mark.style.top = `${d * 100}%`;

  for (const el of sceneRoots(frame.id)) window.VivomeSlots?.tick(el, local);
  return DRAW[frame.id]?.(local, p, frame) ?? null;
}

window.addEventListener('hf-seek', (event) => {
  const pending = draw(Math.max(0, Number(event.detail?.time) || 0));
  if (pending && typeof event.detail?.waitUntil === 'function') event.detail.waitUntil(pending);
});
draw(0);
