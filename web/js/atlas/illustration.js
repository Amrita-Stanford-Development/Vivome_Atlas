// The waiting illustration. While the service works on a file it sends no
// progress, so the Atlas page plays the six steps it runs (SERVICE_STEPS in
// web/js/workflow-data.js) as a loop of dots on the file's sheet: an
// illustration of what each step does, not a measure of how far it has got
// (the page's label says so). Grey and the accent only, never a class colour
// or a reserved one, and the bins of step 4 are equal so no share is implied.
//
// illustrationLayout is the pure part (node --test covers it); the rest
// draws it as one THREE.Points of round soft dots on a plane facing the
// camera, where the file's sheet is.

export const ILLUSTRATION = {
  steps: 6,
  aspect: 1.6,          // the grid's columns over its rows, as the file's sheet
  margin: [0.06, 0.1],  // the grid's inset from the plane's sides (u) and top and bottom (v)
  edge: 0.05,           // how far past the plane's sides a streaming dot goes before it wraps
  centres: 6,           // step 1: the local centres the dots borrow from
  bins: 4,              // step 4: equal bins (a type, a family, a branch, a reason)
  dot: 0.28,            // a dot's radius over the grid's spacing
  colours: { grey: '#9AA6AF', accent: '#0066A3' },
};

const SEED = 7;
const [MU, MV] = ILLUSTRATION.margin;
const EDGE = ILLUSTRATION.edge;
const LAP = 1 + 2 * EDGE;

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const smooth = (x) => {
  const t = clamp01(x);
  return t * t * (3 - 2 * t);
};
// 0 before a, 1 after b, eased between.
const span = (t, a, b) => smooth((t - a) / (b - a));
// 0 at a and at b, 1 halfway.
const bump = (t, a, b) => Math.sin(Math.PI * clamp01((t - a) / (b - a)));
const mix = (a, b, k) => a + (b - a) * k;
// A u that ran off one side comes back in at the other.
const wrap = (u) => -EDGE + ((((u + EDGE) % LAP) + LAP) % LAP);

// A stable number in [0, 1) for (seed, dot, purpose).
function hash01(seed, i, k) {
  let h = Math.imul(seed ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(i + 1, 0xc2b2ae35) ^ Math.imul(k + 1, 0x27d4eb2f);
  h ^= h >>> 15;
  h = Math.imul(h, 0x2c1b3c6d);
  h ^= h >>> 12;
  h = Math.imul(h, 0x297a2d39);
  h ^= h >>> 15;
  return (h >>> 0) / 4294967296;
}

// The grid every step starts and ends on: one slot per dot, row by row.
export function illustrationGrid(n) {
  const cols = Math.max(1, Math.ceil(Math.sqrt(n * ILLUSTRATION.aspect)));
  const rows = Math.max(1, Math.ceil(n / cols));
  return {
    cols,
    rows,
    du: cols === 1 ? 1 - 2 * MU : (1 - 2 * MU) / (cols - 1),
    dv: rows === 1 ? 1 - 2 * MV : (1 - 2 * MV) / (rows - 1),
  };
}

export function illustrationSlot(i, n) {
  const { cols, rows } = illustrationGrid(n);
  const col = i % cols;
  const row = Math.floor(i / cols);
  return [
    cols === 1 ? 0.5 : MU + ((1 - 2 * MU) * col) / (cols - 1),
    rows === 1 ? 0.5 : MV + ((1 - 2 * MV) * row) / (rows - 1),
    col,
    row,
  ];
}

// The local centres of step 1, spread over the sheet.
function centre(seed, k) {
  const across = Math.ceil(ILLUSTRATION.centres / 2);
  return [
    mix(0.2, 0.8, across === 1 ? 0.5 : (k % across) / (across - 1)) + (hash01(seed, k, 11) - 0.5) * 0.12,
    (k < across ? 0.32 : 0.68) + (hash01(seed, k, 12) - 0.5) * 0.12,
  ];
}

// Where dot i of n is at time t (0..1) of a step, as [u, v, tone]: u, v in
// 0..1 across and down the plane (a streaming dot may run EDGE past a side),
// tone 0 grey to 1 accent. Every step starts and ends with each dot on its
// grid slot in grey, so the steps join and the loop is seamless.
export function illustrationLayout(step, t, i, n, seed = SEED, lanes = 5) {
  const k = ((Math.round(step) % ILLUSTRATION.steps) + ILLUSTRATION.steps) % ILLUSTRATION.steps;
  const tt = clamp01(t);
  const [su, sv, col] = illustrationSlot(i, n);
  const { cols, du, dv } = illustrationGrid(n);

  if (k === 0) {
    // Fit to the shared list: the dots scatter, then snap into the column
    // grid one column at a time, left to right.
    const xu = mix(MU, 1 - MU, hash01(seed, i, 1));
    const xv = mix(MV, 1 - MV, hash01(seed, i, 2));
    const at = 0.3 + 0.5 * (cols === 1 ? 0 : col / (cols - 1));
    const loose = span(tt, 0, 0.3) * (1 - span(tt, at, at + 0.2));
    return [mix(su, xu, loose), mix(sv, xv, loose), bump(tt, at, at + 0.2)];
  }

  if (k === 1) {
    // Borrow from similar cells: each dot drifts toward its nearest centre,
    // eases back a little, then home.
    let best = 0;
    let bestD = Infinity;
    for (let c = 0; c < ILLUSTRATION.centres; c += 1) {
      const [cu, cv] = centre(seed, c);
      const d = (cu - su) ** 2 + (cv - sv) ** 2;
      if (d < bestD) { best = c; bestD = d; }
    }
    const [cu, cv] = centre(seed, best);
    const p = tt < 0.45 ? span(tt, 0, 0.45) : tt < 0.6 ? 1 - 0.25 * span(tt, 0.45, 0.6) : 0.75 * (1 - span(tt, 0.6, 1));
    const pull = 0.5 * (0.75 + 0.25 * hash01(seed, i, 3)) * p;
    return [mix(su, cu, pull), mix(sv, cv, pull), p];
  }

  if (k === 2) {
    // The learners: the dots stream through parallel lanes, one lap each.
    const count = Math.max(1, Math.floor(lanes));
    const lane = i % count;
    const lv = count === 1 ? 0.5 : MV + ((1 - 2 * MV) * lane) / (count - 1);
    const width = (count === 1 ? 1 - 2 * MV : (1 - 2 * MV) / (count - 1)) * 0.35;
    const inLane = span(tt, 0, 0.2) * (1 - span(tt, 0.8, 1));
    const lead = 0.08 * hash01(seed, i, 5);
    const run = span(tt, 0.2 + lead, 0.72 + lead);
    const u = wrap(su + run * LAP + inLane * (hash01(seed, i, 6) - 0.5) * du * 0.8);
    return [u, mix(sv, lv + (hash01(seed, i, 4) - 0.5) * width, inLane), inLane];
  }

  if (k === 3) {
    // The second opinion: every other dot is a partner that comes to sit
    // beside its neighbour, goes once round it, and goes home.
    const partner = col % 2 === 1;
    if (partner) {
      const [hu, hv] = illustrationSlot(i - 1, n);
      const near = span(tt, 0, 0.25) * (1 - span(tt, 0.75, 1));
      const angle = hash01(seed, i, 7) * 2 * Math.PI + 2 * Math.PI * span(tt, 0.25, 0.75);
      const r = 0.6 * Math.min(du, dv);
      return [mix(su, hu + Math.cos(angle) * r, near), mix(sv, hv + Math.sin(angle) * r, near), near];
    }
    const checked = col + 1 < cols && i + 1 < n;
    return [su, sv, checked ? bump(tt, 0.3, 0.8) : 0];
  }

  if (k === 4) {
    // The answer or reason: the dots sort into equal bins, a type, a family,
    // a branch and a reason, stacked from the bottom; the reason's bin stays grey.
    const bins = ILLUSTRATION.bins;
    const b = i % bins;
    const j = Math.floor(i / bins);
    const per = Math.ceil(n / bins);
    const binW = (1 - 2 * MU) / bins;
    const left = MU + b * binW + binW * 0.1;
    const innerW = binW * 0.8;
    const innerH = 1 - 2 * MV;
    const bc = Math.max(1, Math.ceil(Math.sqrt((per * innerW * ILLUSTRATION.aspect) / innerH)));
    const br = Math.max(1, Math.ceil(per / bc));
    const bu = left + (bc === 1 ? innerW / 2 : (innerW * (j % bc)) / (bc - 1));
    const bv = 1 - MV - (br === 1 ? 0 : (innerH * Math.floor(j / bc)) / (br - 1));
    const lag = 0.05 * hash01(seed, i, 8);
    const sorted = span(tt, lag, 0.3 + lag) * (1 - span(tt, 0.7 + lag, 0.95 + lag));
    return [mix(su, bu, sorted), mix(sv, bv, sorted), b < bins - 1 ? sorted : 0];
  }

  // Place on the map: the dots stream out through the left side, toward
  // the atlas, gathering toward the middle as they go, and the sheet refills.
  const lead = 0.15 * hash01(seed, i, 9);
  const run = span(tt, 0.05 + lead, 0.8 + lead);
  const u = wrap(su - run * LAP);
  const moving = span(tt, 0, 0.1) * (1 - span(tt, 0.9, 1));
  const toward = moving * (1 - smooth(u / 0.5));
  return [u, mix(sv, 0.5, 0.6 * toward), moving * (1 - smooth(u / 0.35))];
}

// ---- drawing ----

const glslFloat = (x) => (Number.isInteger(x) ? `${x}.0` : String(x));
const glslColour = (hex) => {
  const v = parseInt(hex.slice(1), 16);
  return `vec3(${[16, 8, 0].map((shift) => glslFloat(((v >> shift) & 255) / 255)).join(', ')})`;
};

const VERTEX = `
#define EDGE ${glslFloat(EDGE)}
attribute vec3 aUvt;
uniform vec3 uCentre;
uniform vec3 uRight;
uniform vec3 uUp;
uniform vec2 uPlane;
uniform float uRadius;
uniform float uPixelScale;
uniform float uMaxSize;
varying float vTone;
varying float vFade;
varying float vSoft;
void main() {
  vec3 p = uCentre + uRight * ((aUvt.x - 0.5) * uPlane.x) - uUp * ((aUvt.y - 0.5) * uPlane.y);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float px = clamp(2.0 * uRadius * uPixelScale / max(-mv.z, 0.001), 1.0, uMaxSize);
  gl_PointSize = px;
  vTone = clamp(aUvt.z, 0.0, 1.0);
  vFade = smoothstep(-EDGE, 0.0, aUvt.x) * smoothstep(-EDGE, 0.0, 1.0 - aUvt.x);
  vSoft = max(0.3, 2.0 / px);
}`;

const FRAGMENT = `
#define GREY ${glslColour(ILLUSTRATION.colours.grey)}
#define ACCENT ${glslColour(ILLUSTRATION.colours.accent)}
uniform float uOpacity;
varying float vTone;
varying float vFade;
varying float vSoft;
void main() {
  float rho = length(gl_PointCoord * 2.0 - 1.0);
  float a = (1.0 - smoothstep(1.0 - vSoft, 1.0, rho)) * vFade * uOpacity;
  if (a < 0.01) discard;
  gl_FragColor = vec4(mix(GREY, ACCENT, vTone), a);
}`;

export const ILLUSTRATION_SHADERS = { vertex: VERTEX, fragment: FRAGMENT };

const unit = (v) => {
  const l = Math.hypot(v[0], v[1], v[2]);
  return l > 0 ? [v[0] / l, v[1] / l, v[2] / l] : [0, 0, 0];
};

export function createIllustration(THREE, stage, { count = 400 } = {}) {
  const n = Math.max(1, Math.floor(count));
  const uvt = new Float32Array(n * 3);
  const geometry = new THREE.BufferGeometry();
  // The dots' places come from aUvt and the plane; position only sets the count.
  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  const attribute = new THREE.BufferAttribute(uvt, 3);
  attribute.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute('aUvt', attribute);
  const gl = stage.renderer.getContext();
  const range = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE);
  const uniforms = {
    uCentre: { value: new THREE.Vector3() },
    uRight: { value: new THREE.Vector3(1, 0, 0) },
    uUp: { value: new THREE.Vector3(0, -1, 0) },
    uPlane: { value: new THREE.Vector2(1, 1) },
    uRadius: { value: 0.1 },
    uPixelScale: { value: 1 },
    uMaxSize: { value: Math.min(256, range ? range[1] : 64) },
    uOpacity: { value: 1 },
  };
  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX, fragmentShader: FRAGMENT, uniforms, transparent: true, depthWrite: false,
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.renderOrder = 4;
  points.visible = false;
  stage.scene.add(points);
  let disposed = false;
  let waking = false;
  stage.onFrame(() => { if (!disposed) uniforms.uPixelScale.value = stage.pixelScale(); });

  // Redraw after the current frame's own work, never inside it (see
  // upload-layer.js): setFrame is called from the page's own ticker.
  function wake() {
    if (waking || disposed) return;
    waking = true;
    queueMicrotask(() => {
      waking = false;
      if (!disposed) stage.invalidate();
    });
  }

  function setFrame({ step = 0, stepT = 0 } = {}) {
    for (let i = 0; i < n; i += 1) {
      const [u, v, tone] = illustrationLayout(step, stepT, i, n, SEED);
      uvt[i * 3] = u;
      uvt[i * 3 + 1] = v;
      uvt[i * 3 + 2] = tone;
    }
    attribute.needsUpdate = true;
    wake();
  }
  setFrame({ step: 0, stepT: 0 });

  return {
    points,
    get count() { return n; },
    // anchor: { centre, right, up, width, height } in scene units, the plane
    // facing the camera where the file's sheet is. Call again to move it.
    show(anchor) {
      const { centre: c = [0, 0, 0], right = [1, 0, 0], up = [0, -1, 0], width = 1, height = 1 } = anchor ?? {};
      const r = unit(right);
      const u = unit(up);
      uniforms.uCentre.value.set(c[0], c[1], c[2]);
      uniforms.uRight.value.set(r[0], r[1], r[2]);
      uniforms.uUp.value.set(u[0], u[1], u[2]);
      uniforms.uPlane.value.set(width, height);
      const { du, dv } = illustrationGrid(n);
      uniforms.uRadius.value = ILLUSTRATION.dot * Math.min(du * width, dv * height);
      points.visible = true;
      wake();
    },
    hide() {
      if (!points.visible) return;
      points.visible = false;
      wake();
    },
    setFrame,
    setOpacity(a) {
      uniforms.uOpacity.value = Math.min(1, Math.max(0, Number(a) || 0));
      wake();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      stage.scene.remove(points);
      geometry.dispose();
      material.dispose();
    },
  };
}
