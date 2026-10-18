// The dive: one continuous shot of the site's living water under all twelve
// scenes. It is web/js/biofield.js's water (the cells and threads of
// web/js/biocells.js through an effect of web/js/water.js, over the
// particles of web/js/background.js, here lib/field.js), with three
// things the site does not need:
//
// - a clock HyperFrames owns: every frame is drawn on its `hf-seek` event,
//   for that exact time, never from requestAnimationFrame. The water's
//   state (the cells and the one ripple field) is stepped on a fixed 60 a
//   second grid from the start of the film, so a frame rendered on its own
//   looks the same as one reached by playing;
// - one continuous shot: nothing resets at a scene's start. The camera,
//   depth, the particles' density and the water's rise follow smooth curves
//   through the scenes' values (lib/plan.js), and each scene's pictures stay
//   drawn while its cards hand over to the next scene's;
// - depth, shown by the objects and never by colour: the background is the
//   site's own white field and gel throughout (background.js's breathing
//   base, biofield's frost). Going down, the cells come forward: the view
//   narrows so they are larger, the camera drifts on through them, it sways
//   so the near ones move more than the far (parallax), the far ones are
//   drawn apart and softly blurred, and the particles grow; going up, all of
//   that eases back. A waterline shows at the surface, in the gel's colours;
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

// ---- smooth curves through the scenes ----
// One key at each scene boundary (the mean of the two scenes' values there,
// which agree when the storyboard is continuous), joined by a cubic Hermite
// curve with Catmull-Rom tangents: no value, and no speed, changes at once.

const KEY_T = [...FRAMES.map((f) => f.start), V.total];
function keysOf(get) {
  return KEY_T.map((_, k) => {
    const before = k > 0 ? get(PLAN[FRAMES[k - 1].id], FRAMES[k - 1], 1) : undefined;
    const after = k < FRAMES.length ? get(PLAN[FRAMES[k].id], FRAMES[k], 0) : undefined;
    if (before === undefined) return after;
    if (after === undefined) return before;
    return (before + after) / 2;
  });
}
function curve(keys) {
  const n = keys.length;
  const slope = (k) => {
    const a = Math.max(0, k - 1);
    const b = Math.min(n - 1, k + 1);
    return (keys[b] - keys[a]) / (KEY_T[b] - KEY_T[a]);
  };
  return (t) => {
    const x = clamp(t, 0, V.total);
    let k = 0;
    while (k < n - 2 && x >= KEY_T[k + 1]) k++;
    const h = KEY_T[k + 1] - KEY_T[k];
    const u = (x - KEY_T[k]) / h;
    const u2 = u * u;
    const u3 = u2 * u;
    return (2 * u3 - 3 * u2 + 1) * keys[k] + (u3 - 2 * u2 + u) * h * slope(k)
      + (-2 * u3 + 3 * u2) * keys[k + 1] + (u3 - u2) * h * slope(k + 1);
  };
}
const pair = (name, fallback) => (plan, frame, end) => (plan[name] ? plan[name][end] : fallback);
const FOV = curve(keysOf(pair('fov', 45)));
const PITCH = curve(keysOf(pair('pitch', 0)));
const YAW = curve(keysOf(pair('yaw', 0)));
const ROLL = curve(keysOf(pair('roll', 0)));
const DENSITY = curve(keysOf(pair('field', 0.6)));
const LINKS = curve(keysOf(pair('links', 1)));
const RISE = curve(keysOf((plan) => plan.rise ?? 1));
const DEPTH = curve(keysOf((plan, frame, end) => frame.depth[end]));

// Depth, 0 at the surface to 1 at the deepest point: it changes what the
// objects do, never the colour.
export const depthAt = (t) => clamp(DEPTH(t));

// How far the water has risen past the camera, in background.js's frames:
// the rise speed added up on the 60 a second grid, once.
const CLIMB = new Float64Array(Math.round(V.total / STEP) + 2);
for (let k = 1; k < CLIMB.length; k++) CLIMB[k] = CLIMB[k - 1] + RISE((k - 1) * STEP) * STEP * 60;
function climbAt(t) {
  const x = clamp(t, 0, V.total) / STEP;
  const k = Math.floor(x);
  return CLIMB[k] + (CLIMB[Math.min(CLIMB.length - 1, k + 1)] - CLIMB[k]) * (x - k);
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
// The cells are drawn in two slices by distance: the far slice is blurred
// (a soft depth of field), then the near slice laid over it.
const nearTarget = createSceneTarget(THREE);
const farTarget = createSceneTarget(THREE);
nearTarget.setSize(W, H, 1);
farTarget.setSize(W, H, 1);
const plainTarget = (w, h) => new THREE.WebGLRenderTarget(w, h, {
  minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false, stencilBuffer: false,
});
const blurA = plainTarget(W / 2, H / 2);
const blurB = plainTarget(W / 2, H / 2);
const cells = plainTarget(W, H);
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

// Behind the cells: the site's field (lib/field.js: background.js's
// breathing white base and its particles). It fills only what the cells
// leave uncovered (it is drawn after them, under their alpha).
const BACK = `
uniform sampler2D uField;
varying vec2 vUv;
void main() { gl_FragColor = vec4(texture2D(uField, vUv).rgb, 1.0); }`;

// A blur along one direction (9 taps), for the far slice of cells. The
// textures hold colour premultiplied by alpha, so blurring them is exact.
const BLUR = `
uniform sampler2D uTex; uniform vec2 uStep;
varying vec2 vUv;
void main() {
  vec4 c = texture2D(uTex, vUv) * 0.2270270;
  c += (texture2D(uTex, vUv + uStep * 1.3846154) + texture2D(uTex, vUv - uStep * 1.3846154)) * 0.3162162;
  c += (texture2D(uTex, vUv + uStep * 3.2307692) + texture2D(uTex, vUv - uStep * 3.2307692)) * 0.0702703;
  gl_FragColor = c;
}`;

// The near slice over the blurred far one.
const COMBINE = `
uniform sampler2D uNear; uniform sampler2D uFar;
varying vec2 vUv;
void main() {
  vec4 n = texture2D(uNear, vUv);
  gl_FragColor = n + texture2D(uFar, vUv) * (1.0 - n.a);
}`;

// Over everything: the surface, when it is in sight. Above the waterline
// the gel is clear and a shade brighter (Snell's window, seen from below);
// along it a fine white meniscus with a soft grey edge under it. White and
// grey only, so the frame keeps the site's colour.
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
  float edge = exp(-pow((uv.y - wl + 0.006) * 200.0, 2.0)) * (1.0 - above);
  vec2 q = vec2(x, uv.y) * 7.0;
  q += (vec2(fbm(q * 0.4 + uTime * 0.06), fbm(q * 0.4 + 5.1 - uTime * 0.05)) - 0.5) * 1.1;
  float shimmer = 1.0 - smoothstep(0.0, 0.12, cellEdge(q, uTime * 0.5));
  vec3 sky = mix(vec3(0.955, 0.965, 0.975), vec3(0.985, 0.99, 0.995), clamp((uv.y - wl) * 2.5, 0.0, 1.0));
  sky += vec3(0.02) * shimmer;
  float a = clamp(max(above, max(line * 0.9, max(glow * 0.35, edge * 0.5))), 0.0, 1.0);
  vec3 c = mix(vec3(1.0), sky, above);
  c = mix(c, vec3(0.72, 0.74, 0.76), edge * (1.0 - line));
  gl_FragColor = vec4(c * a, a);
}`;

function pass(fragmentShader, uniforms, blending = { blending: THREE.NoBlending }) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
    vertexShader: QUAD, fragmentShader, uniforms, depthTest: false, depthWrite: false, transparent: true, ...blending,
  }));
  mesh.frustumCulled = false;
  const s = new THREE.Scene();
  s.add(mesh);
  return {
    uniforms,
    draw: () => renderer.render(s, flat),
    into: (target) => { renderer.setRenderTarget(target); renderer.render(s, flat); renderer.setRenderTarget(null); },
  };
}

const blur = pass(BLUR, { uTex: { value: null }, uStep: { value: new THREE.Vector2() } });
const combine = pass(COMBINE, { uNear: { value: nearTarget.texture }, uFar: { value: blurB.texture } });
const back = pass(BACK, { uField: { value: fieldTexture } }, {
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

// The layer's shared uniforms (its depth fade and haze) are reached through
// any of its materials: every material holds the same objects.
let layer = null;
let layerStep = 0;
let shared = null;
const NEAR = 3;
const FAR = 46;
function freshLayer() {
  if (layer) { scene.remove(layer.group); layer.dispose(); }
  layer = createBioLayer(THREE, { palette: PALETTES.vivid, density: 'rich', near: NEAR, far: FAR });
  scene.add(layer.group);
  shared = layer.group.children[0].material.uniforms;
  layerStep = 0;
  layer.update(0, { aspect: W / H });
}
// Deeper, the camera drifts on through the cells faster (scene units a
// second), so they come forward and pass.
const drift = (d) => 0.4 + 2.2 * d;
function cellsTo(step) {
  if (!layer || step < layerStep) freshLayer();
  while (layerStep < step) {
    layerStep++;
    layer.update(layerStep * STEP, { aspect: W / H, advance: STEP * drift(depthAt(layerStep * STEP)) });
  }
}

// The cells in two slices: the far one blurred, the near one sharp. Deeper,
// the split comes closer and the blur grows.
function captureCells(d) {
  const split = 17 - 6 * d;
  const fade = shared.uDepthFade.value;
  const haze = shared.uHaze.value;
  fade.set(split, split + 3, FAR - 16, FAR);
  shared.uHaze.value = 0.55 + 0.35 * d;
  farTarget.capture(renderer, scene, camera);
  const r = 0.8 + 3.2 * d;
  blur.uniforms.uTex.value = farTarget.texture;
  blur.uniforms.uStep.value.set(r / (W / 2), 0);
  blur.into(blurA);
  blur.uniforms.uTex.value = blurA.texture;
  blur.uniforms.uStep.value.set(0, r / (H / 2));
  blur.into(blurB);
  // The very nearest cells fade before they fill the frame, so the words stay clear.
  fade.set(NEAR + 1.5, NEAR + 6.5, split, split + 3);
  shared.uHaze.value = haze;
  nearTarget.capture(renderer, scene, camera);
  combine.into(cells);
  fade.set(NEAR, NEAR + 4, FAR - 16, FAR);
}

// ---- the water's surface: one ripple field for the whole film ----
// web/js/water.js's ripples, without their own rain; the drops are the
// scenes' (rain, a wake, a splash), chosen by a hash of the step, so the
// field at any moment is the same however the render reached it. With no
// drops it lies flat: the site's still gel.

const hash = (k, salt) => { const x = Math.sin(k * 12.9898 + salt * 78.233) * 43758.5453; return x - Math.floor(x); };
function dropsAt(k) {
  const { plan, local } = locate(k * STEP);
  const out = [];
  const r = plan.rain;
  if (r && local >= r.from && local <= r.to && hash(k, 1) < r.rate * STEP) {
    out.push([0.05 + hash(k, 2) * 0.9, 0.05 + hash(k, 3) * 0.9, 0.5 + hash(k, 4) * 0.5, 0.025 + hash(k, 5) * 0.03]);
  }
  const w = plan.wake;
  if (w && local >= w.from && local <= w.to && k % 4 === 0) {
    const u = (local - w.from) / (w.to - w.from) * (w.path.length - 1);
    const j = Math.min(w.path.length - 2, Math.floor(u));
    const f = u - j;
    out.push([w.path[j][0] + (w.path[j + 1][0] - w.path[j][0]) * f, w.path[j][1] + (w.path[j + 1][1] - w.path[j][1]) * f, 0.3, 0.026]);
  }
  for (const [at, u, v, strength, radius] of plan.splash ?? []) {
    if (Math.abs(local - at) < STEP / 2) out.push([u, v, strength, radius]);
  }
  return out;
}
let fx = null;
let fxStep = -1;
function waterTo(step) {
  if (!fx || step < fxStep) {
    fx?.dispose();
    fx = createEffect(THREE, canSimulate ? 'wake' : 'still');
    fx.setSize(W, H);
    fxStep = -1;
  }
  while (fxStep < step) {
    fxStep++;
    for (const d of dropsAt(fxStep)) fx.drop(...d);
    fx.step(renderer, fxStep * STEP, fxStep === 0 ? 0 : STEP);
  }
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

// The frost is the site's gel, the same all the way through.
document.getElementById('frost').style.opacity = '0.72';
const clock = document.getElementById('hud-time');
const chapter = document.getElementById('hud-chapter');
const mark = document.getElementById('gauge-mark');
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s) % 60).padStart(2, '0')}`;

// ---- one frame ----

export function draw(t) {
  const { index, frame, plan, local, p } = locate(t);
  const d = depthAt(t);
  const step = Math.round(t / STEP);
  cellsTo(step);
  waterTo(step);

  // Deeper: a narrower view (the cells larger) and a wider sway, which
  // moves the near cells more than the far.
  camera.fov = FOV(t) * (1 - 0.24 * d);
  camera.position.set(0.9 * d * Math.sin(t * 0.31), 0.55 * d * Math.sin(t * 0.23 + 1), 0);
  camera.rotation.set(PITCH(t) + 0.02 * d * Math.sin(t * 0.19), YAW(t) - 0.03 * d * Math.sin(t * 0.31), ROLL(t));
  camera.updateProjectionMatrix();
  layer.setFade(clamp(t / 1.6));

  field.draw(t, { climb: climbAt(t), density: DENSITY(t), links: LINKS(t), scale: 1 + 0.6 * d });
  fieldTexture.needsUpdate = true;

  renderer.setRenderTarget(null);
  renderer.setScissorTest(false);
  captureCells(d);
  renderer.setViewport(0, 0, W, H);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  fx.draw(renderer, cells.texture);
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

  clock.textContent = fmt(t);
  chapter.textContent = V.chapters.find((c) => c.id === frame.chapter)?.label ?? '';
  mark.style.top = `${d * 100}%`;

  for (const el of sceneRoots(frame.id)) window.VivomeSlots?.tick(el, local);
  const pending = [DRAW[frame.id]?.(local, p, frame)];
  // While the last scene's cards hand over to these, its pictures stay as
  // they ended, so a frame rendered on its own shows them too.
  const before = FRAMES[index - 1];
  if (before && local < V.handover) {
    for (const el of sceneRoots(before.id)) window.VivomeSlots?.tick(el, before.seconds + local);
    pending.push(DRAW[before.id]?.(before.seconds, 1, before));
  }
  return pending.filter(Boolean);
}

window.addEventListener('hf-seek', (event) => {
  const pending = draw(Math.max(0, Number(event.detail?.time) || 0));
  if (typeof event.detail?.waitUntil === 'function') for (const wait of pending) event.detail.waitUntil(wait);
});
draw(0);
