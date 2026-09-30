// The structures the landing's particles gather into (web/js/field.js).
// Pure and seeded: no DOM, the same points on every visit, tested under
// node --test. Each generator returns n points in formation units (about
// -1..1 on each axis) and a role per point, which the field turns into a
// colour and a mark.

export const ROLE = { cell: 0, rna: 1, prot: 2, ring: 3, dot: 4, pale: 5 };

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

const make = (n) => ({ pos: new Float32Array(n * 3), role: new Uint8Array(n) });

function set(f, i, x, y, z, role) {
  f.pos[i * 3] = x;
  f.pos[i * 3 + 1] = y;
  f.pos[i * 3 + 2] = z;
  f.role[i] = role;
}

// A uniform point on the unit sphere.
function onSphere(rand) {
  const u = rand() * 2 - 1;
  const a = rand() * Math.PI * 2;
  const r = Math.sqrt(1 - u * u);
  return [r * Math.cos(a), u, r * Math.sin(a)];
}

// A cell: a membrane shell with a denser nucleus, slightly off centre.
export function cell(n, seed = 11) {
  const rand = rng(seed);
  const f = make(n);
  for (let i = 0; i < n; i++) {
    const [x, y, z] = onSphere(rand);
    if (i < n * 0.68) {
      const r = 0.95 + (rand() - 0.5) * 0.06;
      set(f, i, x * r, y * r * 0.92, z * r, ROLE.cell);
    } else {
      const r = Math.cbrt(rand()) * 0.34;
      set(f, i, 0.12 + x * r, 0.08 + y * r, z * r, ROLE.cell);
    }
  }
  return f;
}

// The cell unwound into its two readouts: an RNA strand (a single helix) to
// one side and a folded protein chain to the other.
export function readouts(n, seed = 12) {
  const rand = rng(seed);
  const f = make(n);
  const half = Math.floor(n / 2);
  for (let i = 0; i < half; i++) {
    const t = i / half;
    const a = t * Math.PI * 7;
    set(f, i, -0.55 + Math.cos(a) * 0.22, -1 + t * 2, Math.sin(a) * 0.22, ROLE.rna);
  }
  // A folded chain: a trefoil knot, the simplest closed fold, beaded with
  // a little jitter so it reads as a chain of residues.
  for (let i = half; i < n; i++) {
    const t = ((i - half) / (n - half)) * Math.PI * 2;
    const j = () => (rand() - 0.5) * 0.025;
    set(f, i,
      0.52 + (Math.sin(t) + 2 * Math.sin(2 * t)) * 0.13 + j(),
      (Math.cos(t) - 2 * Math.cos(2 * t)) * 0.13 + j(),
      -Math.sin(3 * t) * 0.13 + j(),
      ROLE.prot);
  }
  return f;
}

// A 96-well plate, 12 x 8, each well a small ring of points.
export function plate(n) {
  const f = make(n);
  const cols = 12;
  const rows = 8;
  const perWell = Math.max(1, Math.floor(n / (cols * rows)));
  for (let i = 0; i < n; i++) {
    const well = Math.min(Math.floor(i / perWell), cols * rows - 1);
    const k = i % perWell;
    const cx = -1 + (well % cols) * (2 / (cols - 1));
    const cy = 0.62 - Math.floor(well / cols) * (1.24 / (rows - 1));
    const a = (k / perWell) * Math.PI * 2;
    set(f, i, cx + Math.cos(a) * 0.058, cy + Math.sin(a) * 0.058, 0, ROLE.cell);
  }
  return f;
}

// Growth rings, one per release. The outermost, the release in testing, is
// still forming: only part of its circle is drawn.
export const RINGS = [
  { r: 0.34, arc: 1 },
  { r: 0.64, arc: 1 },
  { r: 0.94, arc: 0.62 },
];

export function growthRings(n, seed = 13) {
  const rand = rng(seed);
  const f = make(n);
  const total = RINGS.reduce((sum, ring) => sum + ring.r * ring.arc, 0);
  let i = 0;
  RINGS.forEach((ring, k) => {
    const count = k === RINGS.length - 1 ? n - i : Math.round((n * ring.r * ring.arc) / total);
    for (let j = 0; j < count; j++, i++) {
      const a = Math.PI / 2 - (j / count) * ring.arc * Math.PI * 2;
      const wobble = (rand() - 0.5) * 0.018;
      set(f, i, Math.cos(a) * (ring.r + wobble), Math.sin(a) * (ring.r + wobble), (rand() - 0.5) * 0.03,
        k === RINGS.length - 1 ? ROLE.pale : ROLE.cell);
    }
  });
  return f;
}

// The two strands braided into a double helix: RNA and protein.
export function helix(n) {
  const f = make(n);
  for (let i = 0; i < n; i++) {
    const strand = i % 2;
    const t = Math.floor(i / 2) / Math.ceil(n / 2);
    const a = t * Math.PI * 6 + strand * Math.PI;
    set(f, i, Math.cos(a) * 0.3, -1 + t * 2, Math.sin(a) * 0.3, strand ? ROLE.prot : ROLE.rna);
  }
  return f;
}

// Real atlas cells (web/data/story_cells.json rows: [PC1, PC2, PC3, ...]),
// centred on their own centroid and scaled into formation units. The
// placement is the data's; only the frame is chosen.
export function atlas(rows, role, centre, scale = 1.25) {
  const f = make(rows.length);
  rows.forEach((r, i) => {
    set(f, i, (r[0] - centre[0]) * scale, (r[1] - centre[1]) * scale, (r[2] - centre[2]) * scale, role);
  });
  return f;
}

export function centroid(rows) {
  const c = [0, 0, 0];
  for (const r of rows) for (let k = 0; k < 3; k++) c[k] += r[k] / rows.length;
  return c;
}

// Points sampled from a text bitmap (from a canvas, in web/js/field.js):
// `mask` is a width x height array of 0/1. Returns n points spread over the
// lit pixels, in formation units, with the text's aspect ratio kept.
export function fromMask(mask, width, height, n, seed = 14) {
  const lit = [];
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) if (mask[y * width + x]) lit.push(x, y);
  const f = make(n);
  const count = lit.length / 2;
  if (count === 0) return f;
  const rand = rng(seed);
  const span = Math.max(width, height) / 2;
  for (let i = 0; i < n; i++) {
    const k = Math.floor(rand() * count) * 2;
    const jitter = () => (rand() - 0.5) / span;
    set(f, i, (lit[k] - width / 2) / span + jitter(), (height / 2 - lit[k + 1]) / span + jitter(),
      (rand() - 0.5) * 0.02, ROLE.cell);
  }
  return f;
}
