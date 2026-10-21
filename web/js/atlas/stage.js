// The Atlas page's 3D stage: the renderer, the camera and its orbit rig, and
// one render loop that draws only when something changed and sleeps while
// the tab is hidden. The rig's pose lives on the object, so the landing can
// glide the camera and hand it back.
//
// three.js r128 is the page's classic <script> tag (the same build the
// living water loads; web/tests/chrome.test.js pins the URL), read here as
// window.THREE.

import { DEFAULT_POSE, PITCH_LIMIT, RADIUS_RANGE, orbitPosition } from './spatial.js';

const smooth = (t) => t * t * (3 - 2 * t);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// The orbit rig: drag to turn, right-drag (or shift-drag) to move across,
// wheel to zoom. A click is a press that moved less than 8 px. Auto-rotation
// turns the view slowly until the visitor touches it, and resumes after two
// idle minutes; never under reduced motion.
export function createOrbitRig(camera, canvas, { reduced = false } = {}) {
  const pose = { target: [...DEFAULT_POSE.target], yaw: DEFAULT_POSE.yaw, pitch: DEFAULT_POSE.pitch, radius: DEFAULT_POSE.radius };
  const listeners = { change: [], click: [], hover: [], leave: [], takeover: [] };
  const emit = (name, ...args) => listeners[name].forEach((f) => f(...args));
  let anim = null;
  let autoRotate = !reduced;
  let idleTimer = null;
  let guided = false;
  let press = null;

  function apply() {
    const p = orbitPosition(pose);
    camera.position.set(p[0], p[1], p[2]);
    camera.up.set(0, -1, 0);
    camera.lookAt(pose.target[0], pose.target[1], pose.target[2]);
    camera.updateMatrixWorld();
    emit('change');
  }

  function touched() {
    autoRotate = false;
    clearTimeout(idleTimer);
    if (!reduced) idleTimer = setTimeout(() => { autoRotate = true; emit('change'); }, 120000);
    if (guided) {
      guided = false;
      anim = null;
      emit('takeover');
    }
  }

  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  canvas.addEventListener('pointerdown', (e) => {
    press = { x: e.clientX, y: e.clientY, lastX: e.clientX, lastY: e.clientY, pan: e.button === 2 || e.shiftKey, moved: false };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!press) {
      emit('hover', e);
      return;
    }
    const dx = e.clientX - press.lastX;
    const dy = e.clientY - press.lastY;
    press.lastX = e.clientX;
    press.lastY = e.clientY;
    if (Math.abs(e.clientX - press.x) > 8 || Math.abs(e.clientY - press.y) > 8) press.moved = true;
    if (!press.moved) return;
    touched();
    anim = null;
    if (press.pan) {
      // Move the target across the view: right and up are the camera's own.
      const speed = pose.radius * 0.0015;
      const right = [camera.matrixWorld.elements[0], camera.matrixWorld.elements[1], camera.matrixWorld.elements[2]];
      const up = [camera.matrixWorld.elements[4], camera.matrixWorld.elements[5], camera.matrixWorld.elements[6]];
      for (let k = 0; k < 3; k += 1) pose.target[k] += -right[k] * dx * speed + up[k] * dy * speed;
    } else {
      pose.yaw += dx * 0.01;
      pose.pitch = clamp(pose.pitch + dy * 0.01, -PITCH_LIMIT, PITCH_LIMIT);
    }
    apply();
  });
  canvas.addEventListener('pointerup', (e) => {
    if (press && !press.moved && e.button === 0) emit('click', e);
    press = null;
  });
  canvas.addEventListener('pointercancel', () => { press = null; });
  canvas.addEventListener('pointerleave', () => { if (!press) emit('leave'); });
  // The keyboard, with the map focused (atlas.html gives the canvas a tab
  // stop): the arrows turn it, Shift and the arrows move it, + and - zoom,
  // Enter opens the cell nearest the centre (a click there).
  canvas.addEventListener('keydown', (e) => {
    const turn = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    const zoom = { '+': 0.9, '=': 0.9, '-': 1 / 0.9, '_': 1 / 0.9 }[e.key];
    if (e.key === 'Enter') {
      const r = canvas.getBoundingClientRect();
      emit('click', { clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0 });
      return;
    }
    if (!turn && !zoom) return;
    e.preventDefault();
    touched();
    anim = null;
    if (zoom) {
      pose.radius = clamp(pose.radius * zoom, RADIUS_RANGE[0], RADIUS_RANGE[1]);
    } else if (e.shiftKey) {
      const step = pose.radius * 0.05;
      const right = [camera.matrixWorld.elements[0], camera.matrixWorld.elements[1], camera.matrixWorld.elements[2]];
      const up = [camera.matrixWorld.elements[4], camera.matrixWorld.elements[5], camera.matrixWorld.elements[6]];
      for (let k = 0; k < 3; k += 1) pose.target[k] += -right[k] * turn[0] * step + up[k] * turn[1] * step;
    } else {
      pose.yaw += turn[0] * 0.15;
      pose.pitch = clamp(pose.pitch + turn[1] * 0.15, -PITCH_LIMIT, PITCH_LIMIT);
    }
    apply();
  });
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    touched();
    anim = null;
    pose.radius = clamp(pose.radius * (1 + clamp(e.deltaY, -200, 200) * 0.001), RADIUS_RANGE[0], RADIUS_RANGE[1]);
    apply();
  }, { passive: false });

  // One frame: an animation in flight, or the slow turn. True while moving.
  function tick(dt) {
    if (anim) {
      anim.t = Math.min(1, anim.t + dt / anim.seconds);
      const e = smooth(anim.t);
      const { from, to } = anim;
      for (let k = 0; k < 3; k += 1) pose.target[k] = from.target[k] + (to.target[k] - from.target[k]) * e;
      pose.yaw = from.yaw + (to.yaw - from.yaw) * e;
      pose.pitch = from.pitch + (to.pitch - from.pitch) * e;
      // The radius moves evenly in proportion, so a long zoom feels steady.
      pose.radius = from.radius * Math.pow(to.radius / from.radius, e);
      apply();
      if (anim.t >= 1) {
        const done = anim.done;
        anim = null;
        done?.();
      }
      return true;
    }
    if (autoRotate && !reduced) {
      pose.yaw += 0.12 * dt;
      apply();
      return true;
    }
    return false;
  }

  // Glide to a pose (or jump, under reduced motion or for zero seconds). The
  // yaw takes the short way round.
  function animateTo(to, seconds) {
    const target = { target: [...(to.target ?? pose.target)], yaw: to.yaw ?? pose.yaw, pitch: to.pitch ?? pose.pitch, radius: to.radius ?? pose.radius };
    const turn = ((target.yaw - pose.yaw) % (2 * Math.PI) + 3 * Math.PI) % (2 * Math.PI) - Math.PI;
    target.yaw = pose.yaw + turn;
    autoRotate = false;
    if (reduced || seconds <= 0) {
      Object.assign(pose, target);
      anim = null;
      apply();
      return Promise.resolve();
    }
    return new Promise((done) => {
      anim = { from: { target: [...pose.target], yaw: pose.yaw, pitch: pose.pitch, radius: pose.radius }, to: target, t: 0, seconds, done };
      emit('change');
    });
  }

  apply();
  return {
    pose,
    tick,
    animateTo,
    setPose: (p) => animateTo(p, 0),
    reset: (seconds = 0.9) => animateTo({ ...DEFAULT_POSE, target: [...DEFAULT_POSE.target] }, seconds),
    on: (name, f) => listeners[name].push(f),
    setGuided: (on) => { guided = on; },
    get guided() { return guided; },
    stopAutoRotate: () => { autoRotate = false; },
    // The header's switch (motion-pref.js), pressed midway: still stops the
    // slow turn and ends a glide where it was going; moving again lets the
    // turn come back after the idle minutes, as after any touch.
    setStill(on) {
      reduced = Boolean(on);
      clearTimeout(idleTimer);
      if (!reduced) {
        idleTimer = setTimeout(() => { autoRotate = true; emit('change'); }, 120000);
        return;
      }
      autoRotate = false;
      if (anim) {
        Object.assign(pose, anim.to);
        const done = anim.done;
        anim = null;
        apply();
        done?.();
      }
    },
  };
}

// The stage: renderer, scene, camera, rig, and the loop. `tickers` run every
// frame while any of them says it is still moving; otherwise the loop draws
// once per invalidate() and sleeps.
export function createStage(THREE, canvas, container, { reduced = false } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  // Colours are drawn as given, so a dot's lit centre matches its swatch.
  renderer.outputEncoding = THREE.LinearEncoding;
  renderer.toneMapping = THREE.NoToneMapping;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xffffff);
  const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);

  const grid = new THREE.GridHelper(100, 20, 0x008ecc, 0xcccccc);
  grid.material.opacity = 0.2;
  grid.material.transparent = true;
  scene.add(grid);

  const rig = createOrbitRig(camera, canvas, { reduced });
  const tickers = new Set();
  let frame = 0;
  let last = 0;
  let width = 1;
  let height = 1;
  let dotScale = 1;
  const listeners = [];

  function size() {
    width = Math.max(1, container.clientWidth);
    height = Math.max(1, container.clientHeight);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    invalidate();
  }

  function draw(now) {
    frame = 0;
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 1 / 60;
    last = now;
    let moving = rig.tick(dt);
    for (const t of tickers) if (t(dt, now / 1000)) moving = true;
    listeners.forEach((f) => f());
    renderer.render(scene, camera);
    // A tick may already have asked for the next frame (the rig's change
    // calls invalidate); never schedule a second one.
    if (moving && !document.hidden) {
      if (!frame) frame = requestAnimationFrame(draw);
    } else if (!frame) {
      last = 0;
    }
  }

  function invalidate() {
    if (!frame && !document.hidden) frame = requestAnimationFrame(draw);
  }

  rig.on('change', invalidate);
  new ResizeObserver(size).observe(container);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) invalidate(); });
  size();

  return {
    THREE, renderer, scene, camera, rig, invalidate,
    addTicker: (f) => { tickers.add(f); invalidate(); return () => tickers.delete(f); },
    onFrame: (f) => listeners.push(f),
    get width() { return width; },
    get height() { return height; },
    // The column-major view-projection matrix, for picking.
    viewProjection: () => new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).elements,
    // Device pixels per scene unit at distance 1, for point sizes, times the
    // visitor's dot size (every layer sizes its dots, and picks them, by it).
    pixelScale: () => (height * renderer.getPixelRatio() * camera.projectionMatrix.elements[5] * dotScale) / 2,
    setDotScale(s) {
      dotScale = Math.min(3, Math.max(0.25, Number(s) || 1));
      invalidate();
    },
    get dotScale() { return dotScale; },
  };
}
