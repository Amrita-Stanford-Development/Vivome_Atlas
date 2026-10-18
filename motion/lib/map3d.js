// The atlas in 3D, as the Atlas page shows it: the reference's own cells at
// their coordinates in the atlas's projection (web/data/workflow.json), in
// the atlas palette (CLASS_COLOURS), drawn as soft round points by three.js
// into a scene's canvas. Scene 4 flies through it; scene 11 lands the
// example file's cells on it. A pure function of the time, like the water.
//
// createMap3D(canvas, capacity) -> { draw(view, list), project(view, xyz) }
// where the view is the camera (orbit angle, height, distance, target,
// fov), and the list gives per point its position, colour, size, opacity
// and look (0 a filled dot; 1 filled with a white rim; 2 lighter with an ink
// ring; 3 paler, no ring; 4 a hollow ring; 5 a broken ring), so the Atlas
// page's answer looks can be drawn too. projectPoint() is the same camera
// without three.js, for the handovers (lib/bridges.js).

const THREE = window.THREE;

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = (a) => { const n = Math.hypot(...a) || 1; return a.map((v) => v / n); };

// The camera of a view: where it stands, orbiting its target.
export function eyeOf({ angle, height, distance, target = [0, 0, 0] }) {
  return [target[0] + distance * Math.sin(angle), target[1] + height, target[2] + distance * Math.cos(angle)];
}

// Where a point lands on a canvas of width by height pixels, and how far in
// front of the camera it is (negative: behind it).
export function projectPoint(view, xyz, width, height) {
  const target = view.target ?? [0, 0, 0];
  const eye = eyeOf(view);
  const f = unit(sub(target, eye));
  const r = unit(cross(f, [0, 1, 0]));
  const u = cross(r, f);
  const d = sub(xyz, eye);
  const depth = dot(d, f);
  const t = Math.tan(((view.fov ?? 38) / 2) * (Math.PI / 180));
  const x = dot(d, r) / (depth * t * (width / height));
  const y = dot(d, u) / (depth * t);
  return [(x + 1) / 2 * width, (1 - y) / 2 * height, depth];
}

const VERTEX = `
attribute vec3 aColour;
attribute float aSize;
attribute float aAlpha;
attribute float aLook;
varying vec3 vColour;
varying float vAlpha;
varying float vLook;
uniform float uScale;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = aSize * uScale / -mv.z;
  vColour = aColour;
  vAlpha = aAlpha * smoothstep(9.0, 3.0, -mv.z);
  vLook = aLook;
}`;

const FRAGMENT = `
varying vec3 vColour;
varying float vAlpha;
varying float vLook;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float r = length(p);
  if (r > 1.0) discard;
  float edge = 1.0 - smoothstep(0.86, 1.0, r);
  vec3 c = vColour;
  float a = vAlpha * edge;
  if (vLook < 0.5) {
    // a soft sphere-shaded dot
    c *= 0.82 + 0.3 * (1.0 - r * r);
  } else if (vLook < 1.5) {
    c = mix(c, vec3(1.0), smoothstep(0.62, 0.72, r));
  } else if (vLook < 2.5) {
    c = mix(mix(c, vec3(1.0), 0.35), vec3(0.11, 0.17, 0.21), smoothstep(0.6, 0.72, r));
  } else if (vLook < 3.5) {
    c = mix(c, vec3(1.0), 0.6);
  } else {
    float ring = smoothstep(0.58, 0.66, r) * (1.0 - smoothstep(0.86, 0.94, r));
    if (vLook > 4.5) ring *= step(0.0, sin(atan(p.y, p.x) * 6.0));
    c = vec3(0.54, 0.6, 0.66);
    a *= ring;
  }
  gl_FragColor = vec4(c * a, a);
}`;

// The point `depth` in front of the camera that lands on canvas pixel
// (px, py): where a thing seen at that place on the canvas stands.
export function unprojectPoint(view, px, py, depth, width, height) {
  const target = view.target ?? [0, 0, 0];
  const eye = eyeOf(view);
  const f = unit(sub(target, eye));
  const r = unit(cross(f, [0, 1, 0]));
  const u = cross(r, f);
  const t = Math.tan(((view.fov ?? 38) / 2) * (Math.PI / 180));
  const x = (px / width) * 2 - 1;
  const y = 1 - (py / height) * 2;
  return [0, 1, 2].map((k) => eye[k] + depth * (f[k] + r[k] * x * t * (width / height) + u[k] * y * t));
}

export function createMap3D(canvas, capacity) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true, premultipliedAlpha: true });
  renderer.setPixelRatio(1);
  renderer.setSize(canvas.width, canvas.height, false);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, canvas.width / canvas.height, 0.05, 60);
  const geometry = new THREE.BufferGeometry();
  const attr = (name, size) => {
    const a = new THREE.BufferAttribute(new Float32Array(capacity * size), size);
    a.setUsage(THREE.DynamicDrawUsage);
    geometry.setAttribute(name, a);
    return a;
  };
  const position = attr('position', 3);
  const colour = attr('aColour', 3);
  const size = attr('aSize', 1);
  const alpha = attr('aAlpha', 1);
  const look = attr('aLook', 1);
  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX, fragmentShader: FRAGMENT, transparent: true, depthWrite: false,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
    uniforms: { uScale: { value: canvas.height * 0.5 } },
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  scene.add(points);
  const tmp = new THREE.Color();

  function aim(view) {
    const target = view.target ?? [0, 0, 0];
    camera.fov = view.fov ?? 38;
    camera.position.set(...eyeOf(view));
    camera.lookAt(target[0], target[1], target[2]);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
  }

  // points: [{ xyz, colour (hex), size, alpha, look }]
  function draw(view, list) {
    aim(view);
    const n = Math.min(capacity, list.length);
    for (let i = 0; i < n; i++) {
      const p = list[i];
      position.setXYZ(i, p.xyz[0], p.xyz[1], p.xyz[2]);
      tmp.set(p.colour);
      colour.setXYZ(i, tmp.r, tmp.g, tmp.b);
      size.setX(i, p.size);
      alpha.setX(i, p.alpha);
      look.setX(i, p.look ?? 0);
    }
    for (const a of [position, colour, size, alpha, look]) a.needsUpdate = true;
    geometry.setDrawRange(0, n);
    renderer.setClearColor(0x000000, 0);
    renderer.clear();
    renderer.render(scene, camera);
  }

  // Where a point lands on the canvas (pixels), for labels.
  const project = (view, xyz) => projectPoint(view, xyz, canvas.width, canvas.height);

  return { draw, project };
}
