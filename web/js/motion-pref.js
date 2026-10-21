// The visitor's motion preference, one for the whole site: still when the
// system asks for reduced motion, or when the visitor pressed the header's
// "Pause motion" switch (remembered in this browser only). Everything that
// moves reads it: the water and its particles (background.js), the bio-cells
// (biofield.js), the Atlas map's slow turn, and the CSS loops (page.css,
// html.motion-off). Loaded by background.js, which every page runs; it wires
// the header's switch (.motion-toggle) itself.

const KEY = 'vivome-motion';
const system = window.matchMedia('(prefers-reduced-motion: reduce)');
const listeners = new Set();

function stored() {
  try {
    return globalThis.localStorage?.getItem(KEY) === 'off';
  } catch {
    return false;
  }
}

let paused = stored();

// Still now: the system's setting or the visitor's switch.
export const motionStill = () => system.matches || paused;
export const motionPaused = () => paused;

// Run f whenever either changes.
export function onMotionChange(f) {
  listeners.add(f);
}

function show() {
  document.documentElement.classList.toggle('motion-off', paused);
  for (const button of document.querySelectorAll('.motion-toggle')) button.setAttribute('aria-pressed', String(paused));
}

export function setMotionPaused(on) {
  paused = Boolean(on);
  try {
    if (paused) globalThis.localStorage?.setItem(KEY, 'off');
    else globalThis.localStorage?.removeItem(KEY);
  } catch {
    // a browser that keeps nothing still pauses for this visit
  }
  show();
  for (const f of listeners) f();
}

system.addEventListener('change', () => { for (const f of listeners) f(); });
show();
for (const button of document.querySelectorAll('.motion-toggle')) {
  button.addEventListener('click', () => setMotionPaused(!paused));
}
