// The landing's opening: large 3D bio objects (web/js/biocells.js) fill the
// screen in front of the title panel, drifting and turning slowly. They ease
// in from beyond the edges when the page opens, and fly back out along the
// same lines as the hero scrolls away (web/js/motion.js). One WebGL canvas
// above the panel; it takes no pointer events.
//
// Needs the global THREE (three.js r128, loaded by web/js/story.js).

import { PALETTES, specimen, sharedUniforms } from './biocells.js';
import { heroEntrance, heroExit, between, smooth } from './motion.js';

const FOV = 35;
const DEPTH = 10;   // scene units from the camera to the cast's plane

// The cast. x and y place each object on screen, from -1 to 1 across it;
// size is its radius as a share of half the screen's height. They frame the
// edges, several partly off screen, and leave the panel's middle clear.
// `tilt` sets how it first faces the viewer; `own` turns DNA about its axis.
// Phones get the ones marked `phone`, smaller, and behind the panel
// (css/story.css).
export const CAST = [
  { kind: 'neutrophil', x: -0.86, y: -0.5, size: 0.62, z: -0.6, tilt: [0.35, 0.2], spin: 0.07, phone: true },
  { kind: 'monocyte', x: 1.02, y: -0.62, size: 0.52, z: 0.4, tilt: [0.3, 0.1], spin: 0.05 },
  { kind: 'lymphocyte', x: 0.8, y: 0.6, size: 0.32, z: -0.2, tilt: [0.2, 0], spin: 0.09, phone: true },
  { kind: 'rbc', x: -0.84, y: 0.78, size: 0.3, z: -1, tilt: [0.9, 0.3], spin: 0.11, phone: true },
  { kind: 'rbc', x: 0.42, y: -0.86, size: 0.24, z: 0.6, tilt: [0.6, -0.2], spin: 0.1 },
  { kind: 'rbc', x: 0.97, y: 0.08, size: 0.19, z: 1, tilt: [1.1, 0.4], spin: 0.13 },
  { kind: 'dna', x: 0.5, y: 0.94, size: 0.46, z: 0.2, tilt: [0.15, 1.1], spin: 0.25, own: true, phone: true },
  { kind: 'chromatin', x: -0.22, y: 0.92, size: 0.3, z: 0.8, tilt: [0.4, 0.2], spin: 0.06 },
  { kind: 'coil', x: -1, y: 0.16, size: 0.3, z: 0.5, tilt: [0.3, 0.7], spin: 0.08 },
  { kind: 'longCell', x: -0.06, y: -0.96, size: 0.38, z: 0.3, tilt: [0.3, 0.12], spin: 0.05, phone: true },
  { kind: 'platelet', x: 0.3, y: 0.66, size: 0.09, z: 1.4, tilt: [0.9, 0.2], spin: 0.18 },
  { kind: 'platelet', x: -0.42, y: -0.78, size: 0.08, z: 1.6, tilt: [0.8, -0.3], spin: 0.2 },
];

export function createHero(THREE, canvas, { compact = false, reduced = false } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, compact ? 1.5 : 1.75));
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 100);
  const tanH = Math.tan((FOV / 2) * (Math.PI / 180));
  const palette = PALETTES.vivid;

  const cast = (compact ? CAST.filter((c) => c.phone) : CAST).map((c, i) => {
    const shared = sharedUniforms(THREE);
    const object = specimen(THREE, c.kind, palette, shared);
    // Centre it, and remember its radius to size it on screen.
    const box = new THREE.Box3().setFromObject(object);
    object.position.sub(box.getCenter(new THREE.Vector3()));
    const radius = box.getBoundingSphere(new THREE.Sphere()).radius;
    const spinner = new THREE.Group();
    spinner.add(object);
    const tilt = new THREE.Group();
    tilt.rotation.set(c.tilt[0], 0, c.tilt[1]);
    tilt.add(spinner);
    const holder = new THREE.Group();
    holder.add(tilt);
    scene.add(holder);
    return { ...c, size: c.size * (compact ? 0.75 : 1), i, shared, spinner, holder, radius, phase: i * 1.7 };
  });

  function resize() {
    const w = canvas.clientWidth || window.innerWidth;
    const h = canvas.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  // time: seconds since the page opened; progress: how far the hero has
  // scrolled away, 0 to 1.
  function render(time, progress) {
    const t = reduced ? 1e3 : time;
    for (const c of cast) {
      const depth = DEPTH - c.z;
      const halfH = depth * tanH;
      const halfW = halfH * camera.aspect;
      // Coming in and going out follow one line: whichever is further out wins.
      const away = Math.max(1 - heroEntrance(t, c.i), progress);
      const exit = heroExit({ x: c.x, y: c.y }, c.size, away);
      const float = reduced ? 0 : 0.012 * Math.sin(t * 0.35 + c.phase);
      c.holder.position.set((c.x + exit.x) * halfW, (c.y + exit.y + float) * halfH, -depth);
      c.holder.scale.setScalar((c.size * halfH * exit.scale) / c.radius);
      const turn = (reduced ? 0 : t * c.spin) + exit.spin + c.phase;
      if (c.own) c.spinner.rotation.y = turn;
      else c.holder.rotation.set(0.25 * Math.sin(turn * 0.7), turn, 0);
      c.shared.uTime.value = t;
      // Fade in as it arrives; fade out over the last stretch of the exit.
      c.shared.uFade.value = smooth(heroEntrance(t, c.i)) * (1 - smooth(between(progress, 0.85, 1)));
    }
    renderer.render(scene, camera);
  }

  function dispose() {
    scene.traverse((o) => {
      if (o.isMesh) {
        o.geometry.dispose();
        o.material.dispose();
      }
    });
    renderer.dispose();
  }

  resize();
  return { render, resize, dispose };
}
