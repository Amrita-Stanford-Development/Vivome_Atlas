// Seeded randomness for the site's procedural visuals (web/js/biocells.js,
// web/js/water.js): the same seed gives the same shapes on every visit.
// Pure, so node --test covers it.

// mulberry32: small, fast, deterministic.
export function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
