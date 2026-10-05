// Motion maths for the landing (web/js/story.js and web/js/hero.js). Pure: no
// DOM, so node --test covers it. Every progress value is 0..1.

export const clamp01 = (x) => Math.min(1, Math.max(0, x));

// Remap p into the window [a, b], clamped.
export const between = (p, a, b) => (b <= a ? (p >= b ? 1 : 0) : clamp01((p - a) / (b - a)));

// Ease in and out (smoothstep).
export const smooth = (t) => t * t * (3 - 2 * t);

// The hero's opening, in seconds: each object eases in over `each`, starting
// `stagger` after the one before, so the whole cast settles in about three
// seconds rather than arriving at once.
export const HERO_IN = { each: 2, stagger: 0.12 };

// How far object i has come in, at t seconds since the opening began.
export function heroEntrance(t, i) {
  const start = i * HERO_IN.stagger;
  return smooth(between(t, start, start + HERO_IN.each));
}

// Where an object goes as the hero scrolls away. `rest` is its place on
// screen, x and y from -1 to 1 across the view, and `size` its half-size in
// the same units. It moves outward along the line from the centre through
// its place, just far enough to leave the screen by p = 1, growing a little
// and turning a little more as it goes, as if the camera passed through.
export function heroExit(rest, size, p) {
  const len = Math.hypot(rest.x, rest.y);
  const dir = len > 1e-6 ? { x: rest.x / len, y: rest.y / len } : { x: 0, y: 1 };
  // The distance to the first edge it crosses, plus its own size.
  const edge = (pos, d) => (Math.abs(d) < 1e-6 ? Infinity : (1 + size - Math.abs(pos)) / Math.abs(d));
  const reach = Math.max(0, Math.min(edge(rest.x, dir.x), edge(rest.y, dir.y)));
  const s = smooth(clamp01(p));
  // (+ 0 turns a -0 into 0.)
  return { x: dir.x * reach * s + 0, y: dir.y * reach * s + 0, scale: 1 + 0.15 * s, spin: 0.6 * s };
}

// A number counting up to its final text, keeping the final's format:
// "85,233" passes through "42,617", "94.9%" through "47.5%". Text that isn't
// a single number, with nothing but symbols such as % around it ("Pending",
// a version such as "0.3.0", a name such as "VivOME v3.1") is left as it is.
export function countText(final, t) {
  const text = String(final);
  if (t >= 1) return text;
  const m = text.match(/^([^\dA-Za-z]*?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?([^\dA-Za-z.]*)$/);
  if (!m) return text;
  const [, before, whole, fraction = '', after] = m;
  const decimals = fraction ? fraction.length - 1 : 0;
  const target = Number(whole.replace(/,/g, '') + fraction);
  const eased = 1 - (1 - clamp01(t)) ** 3;
  let shown = (target * eased).toFixed(decimals);
  if (whole.includes(',')) {
    const [int, dec] = shown.split('.');
    shown = int.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (dec ? `.${dec}` : '');
  }
  return before + shown + after;
}
