// A reference cell's gene profile, for the Atlas page's drawer, fetched only
// when a cell is clicked.
//
// The public site has the RNA profiles as shards (data/profiles/, written by
// scripts/build_pages_site.py): float32 values, gzipped, a fixed number of
// cells each, so a click fetches one shard of about 120 KB. Without shards
// (a clone of the repository), the profiles come from the large CSVs
// (web/data/atlas_PROT_lat128.csv, 47 MB; the RNA parts, 1.43 GB each, as Git
// LFS objects): the protein file is read once and every profile kept; the RNA
// parts are searched row by row until the cell is found. A clone without
// `git lfs pull` gets the LFS remedy (isLfsPointer, the one copy of the
// check, in web/js/manifest.js).

import { isLfsPointer } from '../manifest.js';
import { escapeHtml } from '../panels.js';
import { parseCsvLine } from './reference-data.js';

// Resolved from this module, so they hold wherever the page lives.
const FILES = {
  prot: [new URL('../../data/atlas_PROT_lat128.csv', import.meta.url).href],
  rna: [new URL('../../data/atlas_RNA_lat128-001-part1.csv', import.meta.url).href,
    new URL('../../data/atlas_RNA_lat128-001-part2.csv', import.meta.url).href],
};
const SHARDS = new URL('../../data/profiles/', import.meta.url).href;

const MISSING = 'Gene profiles are not on this copy of the site: the files are too large for it. '
  + 'A clone of the repository has them (git lfs pull).';
const LFS = 'The profile file is a Git LFS object that has not been fetched. Run: git lfs install && git lfs pull';

const cache = new Map();
let protLoad = null;
let shardIndex = null;

const pause = () => new Promise((resolve) => setTimeout(resolve, 1));

// Read a file line by line. `onRow` gets each data row's values and the gene
// columns; returning true stops the read. Throws when no file could be
// fetched, or when the file is an LFS pointer.
async function scan(files, onRow, onProgress) {
  let fetched = 0;
  for (const file of files) {
    const response = await fetch(file).catch(() => null);
    if (!response?.ok) continue;
    fetched += 1;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let genes = null;
    let rows = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      if (genes === null && isLfsPointer(buffer)) {
        reader.cancel();
        throw new Error(LFS);
      }
      let end;
      while ((end = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, end).trim();
        buffer = buffer.slice(end + 1);
        if (!line) continue;
        const values = parseCsvLine(line);
        if (!genes) {
          genes = values.map((h, i) => [i, h]).filter(([, h]) => h.startsWith('gene_')).map(([i, h]) => [i, h.slice(5)]);
          continue;
        }
        rows += 1;
        if (onRow(values, genes)) {
          reader.cancel();
          return true;
        }
        if (rows % 1000 === 0) {
          onProgress?.(rows, file);
          await pause();
        }
      }
    }
  }
  if (fetched === 0) throw new Error(MISSING);
  return false;
}

const profileOf = (values, genes) => {
  const profile = {};
  for (const [i, name] of genes) {
    const v = Number(values[i]);
    if (Number.isFinite(v)) profile[name] = v;
  }
  return profile;
};

// A float32 as the CSV parts print it: the shortest text that reads back as
// the same float32 ("3.15165", not 3.1516499519…). A shard's value goes
// through it, so the drawer shows the same four decimals from either copy.
export function float32Text(x) {
  for (let digits = 1; digits <= 9; digits += 1) {
    const text = x.toPrecision(digits);
    if (Math.fround(Number(text)) === x) return text;
  }
  return String(x);
}

// One cell's profile from a decoded shard: `row` cells of `genes` float32
// values (little-endian) come before it.
export function shardProfile(buffer, genes, row) {
  const width = genes.length * 4;
  if (buffer.byteLength < (row + 1) * width) throw new Error('The profile shard is shorter than its index says.');
  const view = new DataView(buffer, row * width, width);
  const profile = {};
  genes.forEach((name, i) => {
    const v = view.getFloat32(i * 4, true);
    if (Number.isFinite(v)) profile[name] = Number(float32Text(v));
  });
  return profile;
}

// The shards' index, or null on a copy without shards (fetched once; a
// network failure is tried again on the next click).
function loadShardIndex() {
  shardIndex ??= fetch(new URL('index.json', SHARDS))
    .then((response) => (response.ok ? response.json() : null))
    .catch(() => {
      shardIndex = null;
      return null;
    });
  return shardIndex;
}

// A shard arrives gzipped, unless something on the way already decoded it.
async function gunzip(buffer) {
  const head = new Uint8Array(buffer, 0, Math.min(2, buffer.byteLength));
  if (head[0] !== 0x1f || head[1] !== 0x8b) return buffer;
  return new Response(new Blob([buffer]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}

async function shardLoad(index, modality, origIndex) {
  const entry = index[modality];
  if (!Number.isInteger(origIndex) || origIndex < 0 || origIndex >= entry.cells) return null;
  const shard = Math.floor(origIndex / index.cells_per_shard);
  const file = entry.file.replace('{shard}', String(shard).padStart(index.digits, '0'));
  const response = await fetch(new URL(file, SHARDS)).catch(() => null);
  if (!response?.ok) throw new Error(`The profile file could not be fetched${response ? ` (HTTP ${response.status})` : ''}. Try again later.`);
  return shardProfile(await gunzip(await response.arrayBuffer()), entry.genes, origIndex % index.cells_per_shard);
}

export async function loadProfile(modality, origIndex, onProgress) {
  const key = `${modality}_${origIndex}`;
  if (cache.has(key)) return cache.get(key);
  const index = await loadShardIndex();
  if (index?.[modality]) {
    const profile = await shardLoad(index, modality, origIndex);
    if (profile) cache.set(key, profile);
  } else if (modality === 'prot') {
    if (!protLoad) {
      protLoad = scan(FILES.prot, (values, genes) => {
        cache.set(`prot_${Number(values[2])}`, profileOf(values, genes));
        return false;
      }, onProgress).catch((err) => {
        protLoad = null;
        throw err;
      });
    }
    await protLoad;
  } else {
    await scan(FILES.rna, (values, genes) => {
      if (Number(values[2]) !== origIndex) return false;
      cache.set(key, profileOf(values, genes));
      return true;
    }, onProgress);
  }
  if (!cache.has(key)) throw new Error(`Cell ${origIndex} was not found in the ${modality === 'prot' ? 'protein' : 'RNA'} profiles.`);
  return cache.get(key);
}

// The drawer's view: a title and a two-column table, filled while loading.
export function profileLoadingHtml(cellName, modality) {
  return `<p class="panel-note">Reading the ${modality === 'prot' ? 'protein' : 'RNA'} profile of this ${escapeHtml(cellName)}…</p>`;
}

export function profileProgressHtml(rows) {
  return `<p class="panel-note">Searching: ${rows.toLocaleString('en-US')} rows read…</p>`;
}

export function profileTableHtml(profile) {
  const genes = Object.keys(profile).sort();
  if (genes.length === 0) return '<p class="panel-note">No values were recorded for this cell.</p>';
  const rows = genes.map((g) => `<tr><td class="gene-name">${escapeHtml(g)}</td><td class="gene-value">${profile[g].toFixed(4)}</td></tr>`).join('');
  return `<table class="gene-profile-table"><thead><tr><th>Gene</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>`;
}

export function profileErrorHtml(err) {
  return `<p class="panel-error">${escapeHtml(err?.message ?? String(err))}</p>`;
}
