// The atlas's reference cells (web/data/metadata_RNA_lat128.csv and
// metadata_PROT_lat128.csv) as typed arrays, and the frame that maps their
// PCA coordinates onto the scene. Pure: no DOM, no THREE, so node --test
// covers it.
//
// The frame is the one the viewer has always used: the midpoint of the box
// around every RNA and protein cell, scaled so the widest axis spans
// SCENE_SPAN units. It is computed once from the reference and kept, so a
// projected cell, whose coordinates the service returns in the same PCA
// (docs/service/projection-api.md), lands through the same transform and
// never moves the atlas.

export const SCENE_SPAN = 80;

// One CSV line. Commas inside double quotes belong to the field: class names
// such as "cd4-positive, alpha-beta t cell" are quoted.
export function parseCsvLine(line) {
  if (!line.includes('"')) return line.split(',').map((v) => v.trim());
  const out = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        field += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (ch === ',' && !quoted) {
      out.push(field.trim());
      field = '';
    } else {
      field += ch;
    }
  }
  out.push(field.trim());
  return out;
}

// A metadata CSV as typed arrays: raw PC coordinates (x, y, z per cell), the
// file's class index, the row's original index, and the class name per cell.
// Rows without three finite coordinates are skipped, as the viewer always did.
export function parseMetadataCsv(text, modality) {
  const lines = String(text).split('\n');
  const header = parseCsvLine(lines[0].replace(/\r$/, ''));
  const column = (name) => {
    const i = header.indexOf(name);
    if (i < 0) throw new Error(`The ${modality} metadata has no ${name} column`);
    return i;
  };
  const [pc1, pc2, pc3, cls, idx, orig] = ['PC1', 'PC2', 'PC3', 'class_name', 'class_idx', 'orig_index'].map(column);
  const size = Math.max(0, lines.length - 1);
  const raw = new Float32Array(size * 3);
  const classIdx = new Uint8Array(size);
  const origIndex = new Uint32Array(size);
  const names = [];
  let n = 0;
  for (let r = 1; r < lines.length; r += 1) {
    const line = lines[r].replace(/\r$/, '');
    if (!line.trim()) continue;
    const v = parseCsvLine(line);
    const x = Number(v[pc1]);
    const y = Number(v[pc2]);
    const z = Number(v[pc3]);
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    raw[n * 3] = x;
    raw[n * 3 + 1] = y;
    raw[n * 3 + 2] = z;
    classIdx[n] = Number(v[idx]) || 0;
    const o = Number(v[orig]);
    origIndex[n] = Number.isFinite(o) ? o : r - 1;
    names.push(v[cls] || 'Unknown');
    n += 1;
  }
  return {
    modality, n, names,
    raw: raw.subarray(0, n * 3), classIdx: classIdx.subarray(0, n), origIndex: origIndex.subarray(0, n),
  };
}

// The class order every colour follows: the sorted union of the class names
// (web/js/workflow-data.js CLASS_COLOURS is indexed by this order).
export function classOrderFrom(...datasets) {
  return [...new Set(datasets.flatMap((d) => d.names))].sort();
}

// Each cell's position in that order.
export function classCodes(data, order) {
  const position = new Map(order.map((name, i) => [name, i]));
  const codes = new Uint8Array(data.n);
  for (let i = 0; i < data.n; i += 1) codes[i] = position.get(data.names[i]) ?? 0;
  return codes;
}

// The frame: centre and scale over every coordinate given.
export function atlasFrame(...raws) {
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  for (const raw of raws) {
    for (let i = 0; i < raw.length; i += 3) {
      for (let k = 0; k < 3; k += 1) {
        if (raw[i + k] < lo[k]) lo[k] = raw[i + k];
        if (raw[i + k] > hi[k]) hi[k] = raw[i + k];
      }
    }
  }
  const span = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  return { centre: [0, 1, 2].map((k) => (lo[k] + hi[k]) / 2), scale: SCENE_SPAN / span };
}

export const toScene = (frame, p) => [0, 1, 2].map((k) => (p[k] - frame.centre[k]) * frame.scale);
export const fromScene = (frame, p) => [0, 1, 2].map((k) => p[k] / frame.scale + frame.centre[k]);

// A whole raw array in scene units.
export function sceneArray(frame, raw) {
  const out = new Float32Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = (raw[i] - frame.centre[i % 3]) * frame.scale;
  return out;
}

// Where each class's name goes: the member nearest the class's mean, so a
// name never floats in empty space between two lobes of a class. null for a
// class with no members.
export function classAnchors(pos, codes, n, nClasses) {
  const sum = new Float64Array(nClasses * 3);
  const count = new Uint32Array(nClasses);
  for (let i = 0; i < n; i += 1) {
    const c = codes[i];
    count[c] += 1;
    for (let k = 0; k < 3; k += 1) sum[c * 3 + k] += pos[i * 3 + k];
  }
  const best = new Float64Array(nClasses).fill(Infinity);
  const anchor = new Int32Array(nClasses).fill(-1);
  for (let i = 0; i < n; i += 1) {
    const c = codes[i];
    let d = 0;
    for (let k = 0; k < 3; k += 1) d += (pos[i * 3 + k] - sum[c * 3 + k] / count[c]) ** 2;
    if (d < best[c]) {
      best[c] = d;
      anchor[c] = i;
    }
  }
  return [...anchor].map((i) => (i < 0 ? null : [pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]]));
}
