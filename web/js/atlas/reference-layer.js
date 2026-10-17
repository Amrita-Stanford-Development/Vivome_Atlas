// The reference cells: every RNA and protein cell of the atlas as one
// THREE.Points, drawn as small lit spheres by the shader (a sphere impostor:
// each dot is shaded as if round). Filters, dimming and focusing a type are
// uniform writes, so nothing is rebuilt when they change.
//
// Colours are web/js/workflow-data.js's CLASS_COLOURS, in the reference's
// sorted class order, as the atlas has always assigned them. Every uniform
// array is read in the vertex shader only (GLSL ES 1.0 guarantees dynamic
// indexing of uniforms there, not in fragment shaders).

import { CLASS_COLOURS } from '../workflow-data.js';

export const RADIUS = { rna: 0.5, prot: 0.9 };   // scene units, as the spheres were

const VERTEX = `
attribute float aClass;
attribute float aModality;
uniform vec3 uPalette[22];
uniform float uClassOn[22];
uniform vec2 uModalityOn;
uniform float uRadius;
uniform float uProtScale;
uniform float uPixelScale;
uniform float uMaxSize;
uniform float uDim;
uniform float uFocus;
varying vec3 vColour;
varying float vDim;
void main() {
  int c = int(aClass + 0.5);
  float on = uClassOn[c] * (aModality < 0.5 ? uModalityOn.x : uModalityOn.y);
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  if (on < 0.5) {
    gl_PointSize = 0.0;
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    vColour = vec3(1.0);
    vDim = 1.0;
    return;
  }
  gl_Position = projectionMatrix * mv;
  float r = uRadius * (aModality < 0.5 ? 1.0 : uProtScale);
  gl_PointSize = clamp(2.0 * r * uPixelScale / max(-mv.z, 0.001), 1.0, uMaxSize);
  vColour = uPalette[c];
  bool focused = uFocus < -0.5 || abs(aClass - uFocus) < 0.5;
  vDim = focused ? uDim * 0.35 : uDim;
}`;

// Lit from the upper left, front. At the centre the shading is about 1, so
// the dot shows its swatch's colour; it darkens a little towards the rim and
// has a small highlight. Dimming mixes towards white.
const FRAGMENT = `
varying vec3 vColour;
varying float vDim;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float r2 = dot(p, p);
  if (r2 > 1.0) discard;
  vec3 n = vec3(p.x, -p.y, sqrt(1.0 - r2));
  vec3 light = normalize(vec3(-0.45, 0.55, 0.7));
  float diffuse = max(dot(n, light), 0.0);
  float spec = pow(max(dot(reflect(-light, n), vec3(0.0, 0.0, 1.0)), 0.0), 24.0) * 0.22;
  vec3 colour = vColour * (0.72 + 0.4 * diffuse) * (0.86 + 0.14 * n.z) + spec;
  gl_FragColor = vec4(mix(colour, vec3(1.0), vDim * 0.82), 1.0);
}`;

export function createReferenceLayer(THREE, stage, { positions, codes, modality, n }) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aClass', new THREE.BufferAttribute(Float32Array.from(codes), 1));
  geometry.setAttribute('aModality', new THREE.BufferAttribute(modality, 1));
  const gl = stage.renderer.getContext();
  const range = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE);
  const uniforms = {
    uPalette: { value: CLASS_COLOURS.map((hex) => new THREE.Color(hex)) },
    uClassOn: { value: new Array(22).fill(1) },
    uModalityOn: { value: new THREE.Vector2(1, 1) },
    uRadius: { value: RADIUS.rna },
    uProtScale: { value: RADIUS.prot / RADIUS.rna },
    uPixelScale: { value: 1 },
    uMaxSize: { value: Math.min(64, range ? range[1] : 64) },
    uDim: { value: 0 },
    uFocus: { value: -1 },
  };
  const material = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: FRAGMENT, uniforms });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  stage.scene.add(points);
  stage.onFrame(() => { uniforms.uPixelScale.value = stage.pixelScale(); });

  // The same visibility the shader applies, for picking.
  const visible = (i) => uniforms.uClassOn.value[codes[i]] > 0.5
    && (modality[i] < 0.5 ? uniforms.uModalityOn.value.x : uniforms.uModalityOn.value.y) > 0.5;

  return {
    points, n, positions, codes, modality, visible,
    setClassOn(c, on) { uniforms.uClassOn.value[c] = on ? 1 : 0; stage.invalidate(); },
    setAllClasses(on) { uniforms.uClassOn.value.fill(on ? 1 : 0); stage.invalidate(); },
    classOn: (c) => uniforms.uClassOn.value[c] > 0.5,
    setModality(which, on) { uniforms.uModalityOn.value[which === 'rna' ? 'x' : 'y'] = on ? 1 : 0; stage.invalidate(); },
    setDim(v) { uniforms.uDim.value = v; stage.invalidate(); },
    get dim() { return uniforms.uDim.value; },
    setFocus(c) { uniforms.uFocus.value = c ?? -1; stage.invalidate(); },
    // The drawn radius in CSS pixels of a reference dot at clip depth w.
    pickRadius: (w, isProt) => {
      const scale = stage.pixelScale() / stage.renderer.getPixelRatio();
      return Math.max(4, (RADIUS.rna * (isProt ? uniforms.uProtScale.value : 1) * scale) / w);
    },
  };
}
