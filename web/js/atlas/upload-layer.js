// The visitor's cells on the atlas: each uploaded cell flies from the file's
// sheet beside the atlas to the place the service gave it, and lands in its
// answer's look (answers.js, STYLE). One THREE.Points draws the cells; a
// second, on the same geometry, the ripple each makes as it lands; a third
// the glow of the reference cells near it.
//
// The flight runs on a clock the page feeds every frame (setClock), the same
// clock the cells' delays are on. The vertex shader moves every cell from
// that clock; positionsAt replays the same path on the CPU, for picking. Both
// read the constants in FLIGHT, and the shader's pathPoint and easeFlight are
// the JS functions line for line. Every uniform array is read in the vertex
// shader only (GLSL ES 1.0 guarantees dynamic indexing of uniforms there, not
// in fragment shaders). Colours are web/js/workflow-data.js's CLASS_COLOURS,
// in the reference's sorted class order, as reference-layer.js draws them.

import { CLASS_COLOURS, OUTCOME_ORDER } from '../workflow-data.js';
import { fileGridLayout } from './spatial.js';

// The flight, the landing and the glow. Lengths are scene units, times
// seconds on the page's clock.
export const FLIGHT = {
  arc: 0.3,             // the path's rise toward arcUp, as a share of the flight's length
  side: 0.15,           // its lean to one side, the same way, so the flights fan out
  minLength: 1e-6,      // a flight shorter than this is a straight line
  parallel: 1e-8,       // |flight x arcUp|^2 below this: arcUp is along the flight, lean off an axis
  minDuration: 0.001,   // a shorter flight is a jump
  reveal: 0.92,         // the eased progress past which a cell shows its answer
  radius: 0.9,          // a cell's radius, as a protein reference cell's
  sprite: 1.6,          // the sprite's half-size over the radius: room for rings
  ringed: 2.0,          // the same, hovered or selected: room for the accent ring
  pop: 1.8,             // the landing pop's peak size
  popSeconds: 0.35,
  popPeak: 0.25,        // the pop peaks this far through
  rippleSeconds: 0.7,
  rippleSprite: 4,      // the ripple's sprite half-size over the radius
  rippleFrom: 0.3,      // the ripple ring's radius over the sprite's, as it starts
  rippleTo: 1.0,        // and as it ends
  rippleWidth: 0.06,
  rippleAlpha: 0.6,
  glowSeconds: 1.2,
  glowPeak: 0.15,       // the glow's burst peaks this far through
  glowRadius: 2.2,      // the glow's sprite half-size
  glowAlpha: 0.55,
  glowSteady: 0.7,      // its strength round the selected cell
  lightenGroup: 0.25,   // a family's fill, mixed this far toward white
  lightenLineage: 0.45, // a branch's
  breathSwell: 0.06,    // while the file waits, its cloud swells by this share and back
  breathRate: 1.1,      // radians a second: one breath in about 5.7 s
  breathDrift: 0.35,    // and each waiting cell drifts on its own small loop, in scene units
  breathFade: 0.8,      // seconds for the breathing to start or to settle
  landedScale: 1.8,     // a landed cell is a bead this many times a flying cell's radius
  beadSprite: 2.4,      // its sprite's half-size over its radius: room for the halo
  pulseRate: 1.6,       // radians a second: the halo's slow pulse
  pulseLow: 0.55,       // the halo's strength at the low of a pulse, as a share of its peak
  pulseFade: 0.8,       // seconds for the pulse to start or to stop
};

// The answer looks, in units of the cell's radius (the sprite's edge is at
// FLIGHT.sprite). atlas-panels.js draws the answer key from the same numbers.
export const LOOK = {
  outline: 1.15,          // one type: a white rim out to here
  inkRing: [1.2, 1.52],   // a family: the ink ring (0.75 to 0.95 of the sprite)
  halo: [1.0, 2.3],       // every landed cell: a soft halo in its own colour, from its edge to here
  haloAlpha: 0.5,
  hollow: [0.55, 1.0],    // no answer, and not placed: the hollow ring
  dashes: 8,              // not placed: its ring is broken into this many dashes
  accent: [1.65, 1.95],   // hovered or selected
  colours: { flight: '#9AA6AF', ink: '#1D2B36', none: '#8A96A0', accent: '#0066A3', outline: '#FFFFFF' },
};

export const GLOW_MODES = { off: 0, landing: 1, selected: 2 };

// ---- the path (pure; the shaders run the same lines) ----

// A stable number in [0, 1) for each cell index: which way its flight leans.
export function cellSeed(i) {
  let h = Math.imul((i + 1) ^ 0x9e3779b9, 0x85ebca6b);
  h ^= h >>> 13;
  h = Math.imul(h, 0xc2b2ae35);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

// How far along its flight a cell is at clock t: 0 before take-off, 1 once
// landed, eased in and out (smoothstep) between.
export function easeFlight(t, delay, duration) {
  const u = Math.min(1, Math.max(0, (t - delay) / Math.max(duration, FLIGHT.minDuration)));
  return u * u * (3 - 2 * u);
}

export const landingTime = (delay, duration) => delay + Math.max(duration, FLIGHT.minDuration);

// A cell's drawn radius at eased progress u: its radius at rest in the
// file's cloud, growing evenly to a bead's by landing. A cell that does not
// fly keeps its resting radius. The vertex shader's
// mix(uSheetRadius, RADIUS * LANDED, u).
export function cellRadius(u, flies, sheetRadius = FLIGHT.radius) {
  return flies ? sheetRadius * (1 - u) + FLIGHT.radius * FLIGHT.landedScale * u : sheetRadius;
}

// A radius that fits n cells on a sheet `width` units wide laid out by
// spatial.js's fileGridLayout: 0.42 of the spacing between columns, within
// [0.2, FLIGHT.radius].
export const SHEET_FIT = { share: 0.42, min: 0.2 };
export function sheetRadiusFor(n, width = 30, aspect = 1.6) {
  const { cols } = fileGridLayout(Math.max(1, Math.floor(n) || 1), aspect);
  if (cols < 2) return FLIGHT.radius;
  return Math.min(FLIGHT.radius, Math.max(SHEET_FIT.min, (SHEET_FIT.share * width) / (cols - 1)));
}

const unit = (v) => {
  const l = Math.hypot(v[0], v[1], v[2]);
  return l > 0 ? [v[0] / l, v[1] / l, v[2] / l] : [0, 0, 0];
};

// A quadratic Bezier from s to e through m: the chord's midpoint, raised
// toward `up` by FLIGHT.arc of the flight's length and leaned sideways by
// FLIGHT.side of it. The lean's direction is perpendicular to the flight, at
// an angle the cell's seed sets, so many flights fan out round the arc.
function pathInto(s, so, e, eo, seed, up, u, out, oo) {
  const sx = s[so];
  const sy = s[so + 1];
  const sz = s[so + 2];
  const ex = e[eo];
  const ey = e[eo + 1];
  const ez = e[eo + 2];
  const dx = ex - sx;
  const dy = ey - sy;
  const dz = ez - sz;
  const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
  if (d < FLIGHT.minLength) {
    out[oo] = sx + dx * u;
    out[oo + 1] = sy + dy * u;
    out[oo + 2] = sz + dz * u;
    return out;
  }
  const fx = dx / d;
  const fy = dy / d;
  const fz = dz / d;
  // r = f x up, or f x (1, 0, 0), or f x (0, 0, 1) when up lies along f.
  let rx = fy * up[2] - fz * up[1];
  let ry = fz * up[0] - fx * up[2];
  let rz = fx * up[1] - fy * up[0];
  if (rx * rx + ry * ry + rz * rz < FLIGHT.parallel) { rx = 0; ry = fz; rz = -fy; }
  if (rx * rx + ry * ry + rz * rz < FLIGHT.parallel) { rx = fy; ry = -fx; rz = 0; }
  const rl = Math.sqrt(rx * rx + ry * ry + rz * rz);
  rx /= rl;
  ry /= rl;
  rz /= rl;
  // q = r x f: perpendicular to the flight and to r.
  const qx = ry * fz - rz * fy;
  const qy = rz * fx - rx * fz;
  const qz = rx * fy - ry * fx;
  const a = seed * 6.283185307179586;
  const c = Math.cos(a);
  const sn = Math.sin(a);
  const lift = FLIGHT.arc * d;
  const lean = FLIGHT.side * d;
  const mx = sx + dx * 0.5 + up[0] * lift + (c * rx + sn * qx) * lean;
  const my = sy + dy * 0.5 + up[1] * lift + (c * ry + sn * qy) * lean;
  const mz = sz + dz * 0.5 + up[2] * lift + (c * rz + sn * qz) * lean;
  const w = 1 - u;
  out[oo] = w * w * sx + 2 * w * u * mx + u * u * ex;
  out[oo + 1] = w * w * sy + 2 * w * u * my + u * u * ey;
  out[oo + 2] = w * w * sz + 2 * w * u * mz + u * u * ez;
  return out;
}

// The point on a cell's path at progress u (0: start, 1: end). arcUp is
// normalised here, as setArcUp normalises it for the shader.
export function pathPoint(start, end, seed, arcUp, u, out = [0, 0, 0]) {
  return pathInto(start, 0, end, 0, seed, unit(arcUp), u, out, 0);
}

// ---- the shaders ----

const glslFloat = (x) => (Number.isInteger(x) ? `${x}.0` : String(x));
const glslColour = (hex) => {
  const v = parseInt(hex.slice(1), 16);
  return `vec3(${[16, 8, 0].map((shift) => glslFloat(((v >> shift) & 255) / 255)).join(', ')})`;
};

export const SHADER_DEFINES = {
  ARC: FLIGHT.arc, SIDE: FLIGHT.side, MIN_LENGTH: FLIGHT.minLength, PARALLEL: FLIGHT.parallel,
  MIN_DURATION: FLIGHT.minDuration, REVEAL: FLIGHT.reveal,
  RADIUS: FLIGHT.radius, SPRITE: FLIGHT.sprite, RINGED: FLIGHT.ringed,
  POP: FLIGHT.pop, POP_SECONDS: FLIGHT.popSeconds, POP_PEAK: FLIGHT.popPeak,
  RIPPLE_SECONDS: FLIGHT.rippleSeconds, RIPPLE_SPRITE: FLIGHT.rippleSprite, RIPPLE_FROM: FLIGHT.rippleFrom,
  RIPPLE_TO: FLIGHT.rippleTo, RIPPLE_WIDTH: FLIGHT.rippleWidth, RIPPLE_ALPHA: FLIGHT.rippleAlpha,
  GLOW_SECONDS: FLIGHT.glowSeconds, GLOW_PEAK: FLIGHT.glowPeak, GLOW_RADIUS: FLIGHT.glowRadius,
  GLOW_ALPHA: FLIGHT.glowAlpha, GLOW_STEADY: FLIGHT.glowSteady,
  LIGHTEN_GROUP: FLIGHT.lightenGroup, LIGHTEN_LINEAGE: FLIGHT.lightenLineage,
  BREATH_SWELL: FLIGHT.breathSwell, BREATH_RATE: FLIGHT.breathRate, BREATH_DRIFT: FLIGHT.breathDrift,
  LANDED: FLIGHT.landedScale, BEAD_SPRITE: FLIGHT.beadSprite, PULSE_RATE: FLIGHT.pulseRate, PULSE_LOW: FLIGHT.pulseLow,
  OUTLINE: LOOK.outline, INK_IN: LOOK.inkRing[0], INK_OUT: LOOK.inkRing[1],
  HALO_IN: LOOK.halo[0], HALO_OUT: LOOK.halo[1], HALO_ALPHA: LOOK.haloAlpha,
  HOLLOW_IN: LOOK.hollow[0], HOLLOW_OUT: LOOK.hollow[1], DASHES: LOOK.dashes,
  ACCENT_IN: LOOK.accent[0], ACCENT_OUT: LOOK.accent[1],
};

const CLASSES = CLASS_COLOURS.length;
const OUTCOMES = OUTCOME_ORDER.length;

const DEFINES = [
  ...Object.entries(SHADER_DEFINES).map(([k, v]) => `#define ${k} ${glslFloat(v)}`),
  ...Object.entries(LOOK.colours).map(([k, hex]) => `#define ${k.toUpperCase()}_COLOUR ${glslColour(hex)}`),
].join('\n');

// What the vertex shaders share: the per-cell attributes, the palette and
// the switches, and the path. aShow is the caller's per-cell mask
// (setCellMask): 1 drawn, 0 hidden.
const CELL_HEAD = `
${DEFINES}
attribute vec3 aEnd;
attribute vec2 aTiming;
attribute vec4 aLook;
attribute vec2 aMeta;
attribute float aShow;
uniform vec3 uPalette[${CLASSES}];
uniform float uOutcomeOn[${OUTCOMES}];
uniform float uTime;
uniform vec3 uArcUp;
uniform float uPixelScale;
uniform float uMaxSize;
uniform float uBreath;
uniform float uBreathTime;
uniform vec3 uCloudCentre;
// Where a waiting cell rests: its place in the file's cloud, which breathes
// (swells and settles about its centre) while each cell drifts on its own
// small loop. uBreath fades it all in and out; at 0 the place is exact.
vec3 breathe(vec3 p, float seed) {
  if (uBreath <= 0.0) return p;
  float phase = seed * 6.283185307179586;
  float swell = 1.0 + BREATH_SWELL * sin(uBreathTime * BREATH_RATE);
  vec3 drift = vec3(sin(uBreathTime * 0.9 + phase), cos(uBreathTime * 0.7 + phase * 1.3), sin(uBreathTime * 0.8 + phase * 0.7));
  return uCloudCentre + (p - uCloudCentre) * mix(1.0, swell, uBreath) + drift * (BREATH_DRIFT * uBreath);
}
float easeFlight(float delay, float duration) {
  float u = clamp((uTime - delay) / max(duration, MIN_DURATION), 0.0, 1.0);
  return u * u * (3.0 - 2.0 * u);
}
float landingTime(float delay, float duration) {
  return delay + max(duration, MIN_DURATION);
}
vec3 pathPoint(vec3 s, vec3 e, float seed, float u) {
  vec3 span = e - s;
  float d = length(span);
  if (d < MIN_LENGTH) return s + span * u;
  vec3 f = span / d;
  vec3 r = cross(f, uArcUp);
  if (dot(r, r) < PARALLEL) r = cross(f, vec3(1.0, 0.0, 0.0));
  if (dot(r, r) < PARALLEL) r = cross(f, vec3(0.0, 0.0, 1.0));
  r = normalize(r);
  vec3 q = cross(r, f);
  float a = seed * 6.283185307179586;
  vec3 m = s + span * 0.5 + uArcUp * (ARC * d) + (cos(a) * r + sin(a) * q) * (SIDE * d);
  float w = 1.0 - u;
  return w * w * s + 2.0 * w * u * m + u * u * e;
}
float outcomeOn() {
  return uOutcomeOn[int(clamp(aLook.z, 0.0, ${glslFloat(OUTCOMES - 1)}) + 0.5)];
}
float drawn() {
  return outcomeOn() * aShow;
}
vec3 fillColour() {
  return aLook.y < -0.5 ? NONE_COLOUR : uPalette[int(clamp(aLook.y, 0.0, ${glslFloat(CLASSES - 1)}) + 0.5)];
}`;

const CELL_VERTEX = `${CELL_HEAD}
uniform float uHover;
uniform float uSelected;
uniform float uSheetRadius;
uniform float uPulse;
uniform float uPulseTime;
varying vec3 vColour;
varying float vStyle;
varying float vRing;
varying float vExtent;
varying float vSoft;
varying float vHalo;
void main() {
  if (drawn() < 0.5) {
    gl_PointSize = 0.0;
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    vColour = vec3(1.0);
    vStyle = -1.0;
    vRing = 0.0;
    vExtent = 1.0;
    vSoft = 1.0;
    vHalo = 0.0;
    return;
  }
  bool flies = aLook.w > 0.5;
  float u = easeFlight(aTiming.x, aTiming.y);
  // A flight leaves from the cell's breathing place, so the cloud pours into the map.
  vec3 home = breathe(position, aMeta.x);
  vec3 p = flies ? pathPoint(home, aEnd, aMeta.x, u) : home;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  vec3 fill = fillColour();
  float style = aLook.x;
  vec3 look = style < 0.5 ? fill
    : style < 1.5 ? mix(fill, vec3(1.0), LIGHTEN_GROUP)
    : style < 2.5 ? mix(fill, vec3(1.0), LIGHTEN_LINEAGE)
    : NONE_COLOUR;
  bool shown = u > REVEAL;
  vColour = shown ? look : FLIGHT_COLOUR;
  vStyle = shown ? style : -1.0;
  vRing = (abs(aMeta.y - uSelected) < 0.5 || abs(aMeta.y - uHover) < 0.5) ? 1.0 : 0.0;
  // Landed, a cell is a bead: larger than any reference dot, in a soft halo
  // of its own colour that pulses slowly (uPulse fades the pulse in and out).
  bool bead = flies && shown;
  float beat = 0.5 + 0.5 * sin(uPulseTime * PULSE_RATE + aMeta.x * 6.283185307179586);
  vHalo = bead ? mix(1.0, PULSE_LOW + (1.0 - PULSE_LOW) * beat, uPulse) : 0.0;
  vExtent = bead ? BEAD_SPRITE : vRing > 0.5 ? RINGED : SPRITE;
  // The pop as it lands: up fast, back slower.
  float s = (uTime - landingTime(aTiming.x, aTiming.y)) / POP_SECONDS;
  float bump = (flies && s >= 0.0 && s <= 1.0)
    ? (s < POP_PEAK ? smoothstep(0.0, POP_PEAK, s) : 1.0 - smoothstep(POP_PEAK, 1.0, s))
    : 0.0;
  // The cloud's radius at rest, a bead's by landing.
  float r = flies ? mix(uSheetRadius, RADIUS * LANDED, u) : uSheetRadius;
  float px = clamp(2.0 * r * vExtent * (1.0 + (POP - 1.0) * bump) * uPixelScale / max(-mv.z, 0.001), 1.0, uMaxSize);
  gl_PointSize = px;
  vSoft = 2.0 * vExtent / px;
}`;

// Each look, in units of the cell's radius: one type a lit sphere in its
// colour with a thin white outline; a family a paler sphere in an ink ring;
// a branch a paler one still in a soft halo; no answer a hollow grey ring;
// not placed the same ring, broken. In flight, a plain grey sphere.
const CELL_FRAGMENT = `
${DEFINES}
uniform float uOpacity;
varying vec3 vColour;
varying float vStyle;
varying float vRing;
varying float vExtent;
varying float vSoft;
varying float vHalo;
vec3 shade(vec3 c, vec2 q) {
  vec3 n = vec3(q.x, -q.y, sqrt(1.0 - min(dot(q, q), 1.0)));
  vec3 light = normalize(vec3(-0.45, 0.55, 0.7));
  float diffuse = max(dot(n, light), 0.0);
  float spec = pow(max(dot(reflect(-light, n), vec3(0.0, 0.0, 1.0)), 0.0), 24.0) * 0.22;
  return c * (0.72 + 0.4 * diffuse) * (0.86 + 0.14 * n.z) + spec;
}
float band(float x, float a, float b) {
  return smoothstep(a - vSoft, a, x) * (1.0 - smoothstep(b, b + vSoft, x));
}
void main() {
  vec2 q = (gl_PointCoord * 2.0 - 1.0) * vExtent;
  float rho = length(q);
  float body = 1.0 - smoothstep(1.0 - vSoft, 1.0, rho);
  vec3 colour = vColour;
  float alpha = 0.0;
  if (vStyle < -0.5) {
    colour = shade(vColour, q);
    alpha = body;
  } else if (vStyle < 0.5) {
    colour = mix(OUTLINE_COLOUR, shade(vColour, q), body);
    alpha = 1.0 - smoothstep(OUTLINE - vSoft, OUTLINE, rho);
  } else if (vStyle < 1.5) {
    colour = mix(INK_COLOUR, shade(vColour, q), body);
    alpha = max(body, band(rho, INK_IN, INK_OUT));
  } else if (vStyle < 2.5) {
    colour = shade(vColour, q);
    alpha = body;
  } else {
    alpha = band(rho, HOLLOW_IN, HOLLOW_OUT);
    if (vStyle > 3.5) alpha *= smoothstep(-0.2, 0.2, sin(atan(q.y, q.x) * DASHES));
  }
  // The bead's halo, under its look.
  if (vHalo > 0.0) {
    float halo = (1.0 - smoothstep(HALO_IN, HALO_OUT, rho)) * HALO_ALPHA * vHalo;
    colour = mix(vColour, colour, alpha);
    alpha = max(alpha, halo);
  }
  if (vRing > 0.5) {
    float ring = band(rho, ACCENT_IN, ACCENT_OUT);
    colour = mix(colour, ACCENT_COLOUR, ring);
    alpha = max(alpha, ring);
  }
  alpha *= uOpacity;
  if (alpha < 0.01) discard;
  gl_FragColor = vec4(colour, alpha);
}`;

// The ripple: a ring that grows from where the cell lands and fades.
const RIPPLE_VERTEX = `${CELL_HEAD}
varying vec3 vColour;
varying float vV;
varying float vSoft;
void main() {
  float v = (uTime - landingTime(aTiming.x, aTiming.y)) / RIPPLE_SECONDS;
  if (drawn() < 0.5 || aLook.w < 0.5 || v < 0.0 || v > 1.0) {
    gl_PointSize = 0.0;
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    vColour = vec3(1.0);
    vV = 1.0;
    vSoft = 1.0;
    return;
  }
  vec4 mv = modelViewMatrix * vec4(aEnd, 1.0);
  gl_Position = projectionMatrix * mv;
  float px = clamp(2.0 * RADIUS * RIPPLE_SPRITE * uPixelScale / max(-mv.z, 0.001), 1.0, uMaxSize);
  gl_PointSize = px;
  vColour = aLook.x > 2.5 ? NONE_COLOUR : mix(fillColour(), vec3(1.0), LIGHTEN_GROUP);
  vV = v;
  vSoft = 2.0 / px;
}`;

// Tints: added to a dark scene, multiplied into a light one (adding colour
// to white leaves white). uMultiply picks the output for the blending set.
const TINT_OUT = `gl_FragColor = uMultiply > 0.5 ? vec4(mix(vec3(1.0), vColour, a), 1.0) : vec4(vColour, a);`;

const RIPPLE_FRAGMENT = `
${DEFINES}
uniform float uOpacity;
uniform float uMultiply;
varying vec3 vColour;
varying float vV;
varying float vSoft;
void main() {
  float rho = length(gl_PointCoord * 2.0 - 1.0);
  float r = mix(RIPPLE_FROM, RIPPLE_TO, vV);
  float ring = 1.0 - smoothstep(RIPPLE_WIDTH * 0.5, RIPPLE_WIDTH * 0.5 + vSoft, abs(rho - r));
  float a = ring * (1.0 - vV) * (1.0 - vV) * RIPPLE_ALPHA * uOpacity;
  if (a < 0.004) discard;
  ${TINT_OUT}
}`;

// The glow round reference cells near an uploaded one: a burst as it lands,
// or a steady glow round the selected cell.
const GLOW_VERTEX = `
${DEFINES}
attribute vec4 aGlow;
uniform vec3 uPalette[${CLASSES}];
uniform float uOutcomeOn[${OUTCOMES}];
uniform float uTime;
uniform float uPixelScale;
uniform float uMaxSize;
uniform float uGlowMode;
uniform float uSelected;
varying vec3 vColour;
varying float vStrength;
void main() {
  float k = 0.0;
  if (uGlowMode > 1.5) {
    k = abs(aGlow.y - uSelected) < 0.5 ? GLOW_STEADY : 0.0;
  } else if (uGlowMode > 0.5) {
    float s = (uTime - aGlow.z) / GLOW_SECONDS;
    if (s >= 0.0 && s <= 1.0) k = s < GLOW_PEAK ? smoothstep(0.0, GLOW_PEAK, s) : 1.0 - smoothstep(GLOW_PEAK, 1.0, s);
  }
  float on = uOutcomeOn[int(clamp(aGlow.w, 0.0, ${glslFloat(OUTCOMES - 1)}) + 0.5)];
  if (on < 0.5 || k <= 0.0) {
    gl_PointSize = 0.0;
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    vColour = vec3(1.0);
    vStrength = 0.0;
    return;
  }
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = clamp(2.0 * GLOW_RADIUS * uPixelScale / max(-mv.z, 0.001), 1.0, uMaxSize);
  vColour = uPalette[int(clamp(aGlow.x, 0.0, ${glslFloat(CLASSES - 1)}) + 0.5)];
  vStrength = k;
}`;

const GLOW_FRAGMENT = `
${DEFINES}
uniform float uOpacity;
uniform float uMultiply;
varying vec3 vColour;
varying float vStrength;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float r2 = dot(p, p);
  if (r2 >= 1.0) discard;
  float a = (1.0 - r2) * (1.0 - r2) * vStrength * GLOW_ALPHA * uOpacity;
  if (a < 0.004) discard;
  ${TINT_OUT}
}`;

export const SHADERS = {
  cell: { vertex: CELL_VERTEX, fragment: CELL_FRAGMENT },
  ripple: { vertex: RIPPLE_VERTEX, fragment: RIPPLE_FRAGMENT },
  glow: { vertex: GLOW_VERTEX, fragment: GLOW_FRAGMENT },
};

// ---- the layer ----

const f32 = (a) => (a instanceof Float32Array ? a : Float32Array.from(a ?? []));

function need(model, fields, n, what) {
  for (const [key, size] of fields) {
    if (!model?.[key] || model[key].length !== n * size) throw new Error(`The upload layer needs ${what}.${key} with ${n * size} values.`);
  }
}

export function createUploadLayer(THREE, stage) {
  const gl = stage.renderer.getContext();
  const range = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE);
  const bg = stage.scene.background;
  const lightScene = !bg?.isColor || 0.2126 * bg.r + 0.7152 * bg.g + 0.0722 * bg.b > 0.5;
  // One set of uniforms, shared by the three materials (each reads its own).
  const uniforms = {
    uPalette: { value: CLASS_COLOURS.map((hex) => new THREE.Color(hex)) },
    uOutcomeOn: { value: new Array(OUTCOMES).fill(1) },
    uTime: { value: 0 },
    uArcUp: { value: new THREE.Vector3(0, -1, 0) },
    uPixelScale: { value: 1 },
    uMaxSize: { value: Math.min(1024, range ? range[1] : 64) },
    uHover: { value: -1 },
    uSelected: { value: -1 },
    uSheetRadius: { value: FLIGHT.radius },
    uOpacity: { value: 1 },
    uGlowMode: { value: GLOW_MODES.landing },
    uMultiply: { value: lightScene ? 1 : 0 },
    uBreath: { value: 0 },
    uBreathTime: { value: 0 },
    uPulse: { value: 0 },
    uPulseTime: { value: 0 },
    uCloudCentre: { value: new THREE.Vector3(0, 0, 0) },
  };
  const tint = lightScene
    ? { blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.ZeroFactor, blendDst: THREE.SrcColorFactor }
    : { blending: THREE.AdditiveBlending };
  const material = (shader, extra = {}) => new THREE.ShaderMaterial({
    vertexShader: shader.vertex, fragmentShader: shader.fragment, uniforms, transparent: true, depthWrite: false, ...extra,
  });
  const cells = new THREE.Points(new THREE.BufferGeometry(), material(SHADERS.cell));
  const ripples = new THREE.Points(cells.geometry, material(SHADERS.ripple, tint));
  const glow = new THREE.Points(new THREE.BufferGeometry(), material(SHADERS.glow, tint));
  // After the reference (renderOrder 0): the glow under the cells, the ripples over them.
  for (const [points, order] of [[glow, 1], [cells, 2], [ripples, 3]]) {
    points.frustumCulled = false;
    points.renderOrder = order;
    points.visible = false;
    stage.scene.add(points);
  }

  let shown = true; // the visitor's switch: their cells on the map or not
  let state = {
    n: 0, start: new Float32Array(0), end: new Float32Array(0), timing: new Float32Array(0), look: new Float32Array(0), meta: new Float32Array(0),
    show: new Float32Array(0), showAttribute: null,
  };
  let neighbours = { m: 0, owner: null, data: null, attribute: null };
  let arcUp = [0, -1, 0];
  let clock = 0;
  let fed = false;
  let flightUntil = -Infinity;
  let glowUntil = -Infinity;
  let disposed = false;
  let waking = false;

  // Redraw after the current frame's own work, not inside it: a change made
  // while the stage draws (setClock from a ticker or onFrame) must not ask
  // for a second loop.
  function wake() {
    if (waking || disposed) return;
    waking = true;
    queueMicrotask(() => {
      waking = false;
      if (!disposed) stage.invalidate();
    });
  }

  // The clock past which nothing moves: every flight landed, its pop and
  // ripple done, and (while landing glows are on) every burst faded.
  const activeUntil = () => Math.max(flightUntil, uniforms.uGlowMode.value === GLOW_MODES.landing ? glowUntil : -Infinity);

  // Frames keep coming while the page feeds the clock and something moves.
  const removeTicker = stage.addTicker(() => {
    if (disposed) return false;
    const feeding = fed;
    fed = false;
    return feeding && clock < activeUntil();
  });
  stage.onFrame(() => { if (!disposed) uniforms.uPixelScale.value = stage.pixelScale(); });

  // The waiting cloud's breath: eased in and out over FLIGHT.breathFade, and
  // only drawing frames while it moves (the page goes still once it settles).
  let breathTarget = 0;
  const removeBreath = stage.addTicker((dt) => {
    if (disposed) return false;
    const a = uniforms.uBreath.value;
    if (a === 0 && breathTarget === 0) return false;
    const step = Math.min(1, (Number(dt) || 0) / FLIGHT.breathFade);
    uniforms.uBreath.value = breathTarget > a ? Math.min(breathTarget, a + step) : Math.max(breathTarget, a - step);
    uniforms.uBreathTime.value += Number(dt) || 0;
    return true;
  });
  function setBreathing(on, centre) {
    breathTarget = on ? 1 : 0;
    if (centre) uniforms.uCloudCentre.value.set(centre[0], centre[1], centre[2]);
    wake();
  }

  // The beads' slow pulse: eased in and out over FLIGHT.pulseFade; while on,
  // the stage keeps drawing.
  let pulseTarget = 0;
  const removePulse = stage.addTicker((dt) => {
    if (disposed) return false;
    const a = uniforms.uPulse.value;
    if (a === 0 && pulseTarget === 0) return false;
    const step = Math.min(1, (Number(dt) || 0) / FLIGHT.pulseFade);
    uniforms.uPulse.value = pulseTarget > a ? Math.min(pulseTarget, a + step) : Math.max(pulseTarget, a - step);
    uniforms.uPulseTime.value += Number(dt) || 0;
    return state.n > 0 && shown;
  });
  function setPulse(on) {
    pulseTarget = on ? 1 : 0;
    wake();
  }

  // Each glowing reference cell takes its owner's outcome, so a hidden
  // outcome's glow hides with it.
  function syncNeighbourOutcomes() {
    const { m, owner, data, attribute } = neighbours;
    if (!attribute) return;
    for (let k = 0; k < m; k += 1) {
      const i = Math.round(owner[k]);
      data[k * 4 + 3] = i >= 0 && i < state.n ? state.look[i * 4 + 2] : 0;
    }
    attribute.needsUpdate = true;
  }

  function load(model) {
    const n = model?.n ?? 0;
    if (n > 0) {
      need(model, [['start', 3], ['end', 3], ['delay', 1], ['duration', 1], ['style', 1], ['fill', 1], ['outcome', 1], ['flies', 1]], n, 'model');
    }
    const start = n ? f32(model.start) : new Float32Array(0);
    const end = n ? f32(model.end) : new Float32Array(0);
    const timing = new Float32Array(n * 2);
    const look = new Float32Array(n * 4);
    const meta = new Float32Array(n * 2);
    const show = new Float32Array(n).fill(1); // a new file starts with every cell drawn
    let until = -Infinity;
    for (let i = 0; i < n; i += 1) {
      timing[i * 2] = model.delay[i];
      timing[i * 2 + 1] = model.duration[i];
      look[i * 4] = model.style[i];
      look[i * 4 + 1] = model.fill[i];
      look[i * 4 + 2] = model.outcome[i];
      look[i * 4 + 3] = model.flies[i] ? 1 : 0;
      meta[i * 2] = cellSeed(i);
      meta[i * 2 + 1] = i;
      const land = landingTime(timing[i * 2], timing[i * 2 + 1]);
      until = Math.max(until, model.flies[i] ? land + Math.max(FLIGHT.popSeconds, FLIGHT.rippleSeconds) : land);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(start, 3));
    geometry.setAttribute('aEnd', new THREE.BufferAttribute(end, 3));
    geometry.setAttribute('aTiming', new THREE.BufferAttribute(timing, 2));
    geometry.setAttribute('aLook', new THREE.BufferAttribute(look, 4));
    geometry.setAttribute('aMeta', new THREE.BufferAttribute(meta, 2));
    const showAttribute = new THREE.BufferAttribute(show, 1);
    geometry.setAttribute('aShow', showAttribute);
    const old = cells.geometry;
    cells.geometry = geometry;
    ripples.geometry = geometry;
    old.dispose();
    cells.visible = n > 0 && shown;
    ripples.visible = n > 0 && shown;
    state = { n, start, end, timing, look, meta, show, showAttribute };
    flightUntil = until;
    syncNeighbourOutcomes();
    fed = true;
    wake();
  }

  function setNeighbours(g) {
    const m = g?.m ?? 0;
    if (m > 0) need(g, [['position', 3], ['cls', 1], ['owner', 1], ['at', 1]], m, 'glow');
    const data = new Float32Array(m * 4);
    let until = -Infinity;
    for (let k = 0; k < m; k += 1) {
      data[k * 4] = g.cls[k];
      data[k * 4 + 1] = g.owner[k];
      data[k * 4 + 2] = g.at[k];
      until = Math.max(until, g.at[k] + FLIGHT.glowSeconds);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(m ? f32(g.position) : new Float32Array(0), 3));
    const attribute = new THREE.BufferAttribute(data, 4);
    geometry.setAttribute('aGlow', attribute);
    const old = glow.geometry;
    glow.geometry = geometry;
    old.dispose();
    glow.visible = m > 0 && shown;
    neighbours = { m, owner: m ? g.owner : null, data, attribute };
    syncNeighbourOutcomes();
    glowUntil = until;
    fed = true;
    wake();
  }

  const index = (i) => (Number.isInteger(i) && i >= 0 ? i : -1);
  const set = (name, value) => {
    if (uniforms[name].value === value) return;
    uniforms[name].value = value;
    wake();
  };

  // Cell i's drawn radius in scene units at clock t (default: the layer's),
  // as the vertex shader draws it.
  function radiusAt(i, t = clock) {
    if (!(i >= 0 && i < state.n)) return uniforms.uSheetRadius.value;
    const { timing, look } = state;
    return cellRadius(easeFlight(t, timing[i * 2], timing[i * 2 + 1]), look[i * 4 + 3] > 0.5, uniforms.uSheetRadius.value);
  }

  // Hides single cells: mask[i] truthy draws cell i, falsy hides it (with its
  // ripple); null draws every cell. Written in place into aShow, so nothing
  // is rebuilt. The neighbour glow ignores it.
  function setCellMask(mask) {
    const { n, show, showAttribute } = state;
    if (mask != null && mask.length !== n) throw new Error(`The cell mask needs ${n} values, not ${mask.length}.`);
    for (let i = 0; i < n; i += 1) show[i] = mask == null || mask[i] ? 1 : 0;
    if (showAttribute) showAttribute.needsUpdate = true;
    wake();
  }

  const cellShown = (i) => i >= 0 && i < state.n && state.show[i] > 0.5;

  function clear() {
    load({ n: 0 });
    setNeighbours(null);
    uniforms.uHover.value = -1;
    uniforms.uSelected.value = -1;
    uniforms.uOutcomeOn.value.fill(1);
    uniforms.uOpacity.value = 1;
    uniforms.uSheetRadius.value = FLIGHT.radius;
    breathTarget = 0;
    uniforms.uBreath.value = 0;
    pulseTarget = 0;
    uniforms.uPulse.value = 0;
    wake();
  }

  return {
    points: cells,
    load,
    setNeighbours,
    clear,
    // The waiting cloud breathes about `centre` (scene units) while on; off,
    // it settles over FLIGHT.breathFade and the cells rest at their places.
    setBreathing,
    get breathing() { return breathTarget > 0; },
    // The landed beads' halo pulses slowly while on.
    setPulse,
    get pulsing() { return pulseTarget > 0; },
    // The flight clock, in seconds, on the clock the delays are on. Feed it
    // every frame while cells fly; the layer keeps the stage drawing until
    // the last ripple and burst are done.
    setClock(t) {
      const before = clock;
      clock = Number(t);
      uniforms.uTime.value = clock;
      fed = true;
      const until = activeUntil();
      if (before < until || clock < until) wake();
    },
    get clock() { return clock; },
    // The clock past which nothing moves: feed the clock at least this far.
    get settledAt() { return activeUntil(); },
    // The camera's up direction at take-off: the arcs rise toward it.
    setArcUp(v) {
      const up = unit(v ?? [0, 0, 0]);
      if (up.every((x, k) => x === arcUp[k])) return;
      arcUp = up;
      uniforms.uArcUp.value.set(up[0], up[1], up[2]);
      wake();
    },
    setGlowMode(mode) {
      if (!(mode in GLOW_MODES)) throw new Error(`Unknown glow mode: ${mode}`);
      fed = true;
      set('uGlowMode', GLOW_MODES[mode]);
    },
    setOutcomeOn(code, on) {
      if (!(code >= 0 && code < OUTCOMES)) return;
      const value = on ? 1 : 0;
      if (uniforms.uOutcomeOn.value[code] === value) return;
      uniforms.uOutcomeOn.value[code] = value;
      wake();
    },
    setAllOutcomes(on) {
      uniforms.uOutcomeOn.value.fill(on ? 1 : 0);
      wake();
    },
    outcomeOn: (code) => uniforms.uOutcomeOn.value[code] > 0.5,
    setHover: (i) => set('uHover', index(i)),
    setSelected: (i) => set('uSelected', index(i)),
    setOpacity: (a) => set('uOpacity', Math.min(1, Math.max(0, Number(a) || 0))),
    get n() { return state.n; },
    // Shows or hides every cell of the upload, with its ripples and glow.
    setShown(on) {
      shown = Boolean(on);
      cells.visible = state.n > 0 && shown;
      ripples.visible = state.n > 0 && shown;
      glow.visible = neighbours.m > 0 && shown;
      wake();
    },
    get shown() { return shown; },
    setCellMask,
    // Whether cell i is drawn by the mask alone (the outcome filter aside).
    cellShown,
    // The mask as set: null while every cell is drawn, else a copy, 1 drawn, 0 hidden.
    get mask() { return state.show.every((v) => v > 0.5) ? null : Uint8Array.from(state.show, (v) => (v > 0.5 ? 1 : 0)); },
    // The same visibility the shader applies, for picking: the switch, the
    // mask, the opacity and the outcome filter.
    visible: (i) => shown && cellShown(i) && uniforms.uOpacity.value > 0
      && uniforms.uOutcomeOn.value[Math.round(Math.min(OUTCOMES - 1, Math.max(0, state.look[i * 4 + 2])))] > 0.5,
    // The radius cells draw at on the sheet, in scene units (at most the
    // full radius); they grow to the full radius as they fly.
    setSheetRadius(r) {
      const value = Number.isFinite(Number(r)) ? Math.min(FLIGHT.radius, Math.max(0.01, Number(r))) : FLIGHT.radius;
      set('uSheetRadius', value);
    },
    get sheetRadius() { return uniforms.uSheetRadius.value; },
    radiusAt,
    // A cell's drawn half-size in CSS pixels at clip depth w, for picking:
    // cell i's at the layer's clock, or without i the largest drawn now.
    pickRadius: (w, i = -1) => {
      let r = radiusAt(i);
      if (!(i >= 0 && i < state.n)) for (let k = 0; k < state.n && r < FLIGHT.radius * FLIGHT.landedScale; k += 1) r = Math.max(r, radiusAt(k));
      const scale = stage.pixelScale() / stage.renderer.getPixelRatio();
      return Math.max(4, (r * FLIGHT.sprite * scale) / w);
    },
    // Every cell's position at clock t: the shader's path, on the CPU (from
    // the cloud's resting places: the breath is a small sway, ignored here).
    positionsAt(t, out = new Float32Array(state.n * 3)) {
      const { n, start, end, timing, look, meta } = state;
      for (let i = 0; i < n; i += 1) {
        const o = i * 3;
        if (look[i * 4 + 3] < 0.5) {
          out[o] = start[o];
          out[o + 1] = start[o + 1];
          out[o + 2] = start[o + 2];
        } else {
          pathInto(start, o, end, o, meta[i * 2], arcUp, easeFlight(t, timing[i * 2], timing[i * 2 + 1]), out, o);
        }
      }
      return out;
    },
    dispose() {
      if (disposed) return;
      clear();
      disposed = true;
      removeTicker();
      removeBreath();
      removePulse();
      for (const points of [glow, cells, ripples]) {
        stage.scene.remove(points);
        points.material.dispose();
      }
      cells.geometry.dispose();
      glow.geometry.dispose();
    },
  };
}
