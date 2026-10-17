// A reference cell's gene profile, for the Atlas page's drawer. The profiles
// live in large CSVs (web/data/atlas_PROT_lat128.csv, 47 MB; the RNA parts,
// 1.43 GB each, as Git LFS objects), fetched only when a cell is clicked:
// the protein file is read once and every profile kept; the RNA parts are
// searched row by row until the cell is found.
//
// The public site leaves the large files out (scripts/build_pages_site.py),
// so there a click says the profiles are not on this copy; a local clone
// without `git lfs pull` gets the LFS remedy (isLfsPointer, the one copy of
// the check, in web/js/manifest.js).

import { isLfsPointer } from '../manifest.js';
import { escapeHtml } from '../panels.js';
import { parseCsvLine } from './reference-data.js';

// Resolved from this module, so they hold wherever the page lives.
const FILES = {
  prot: [new URL('../../data/atlas_PROT_lat128.csv', import.meta.url).href],
  rna: [new URL('../../data/atlas_RNA_lat128-001-part1.csv', import.meta.url).href,
    new URL('../../data/atlas_RNA_lat128-001-part2.csv', import.meta.url).href],
};

const MISSING = 'Gene profiles are not on this copy of the site: the files are too large for it. '
  + 'A clone of the repository has them (git lfs pull).';
const LFS = 'The profile file is a Git LFS object that has not been fetched. Run: git lfs install && git lfs pull';

const cache = new Map();
let protLoad = null;

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

export async function loadProfile(modality, origIndex, onProgress) {
  const key = `${modality}_${origIndex}`;
  if (cache.has(key)) return cache.get(key);
  if (modality === 'prot') {
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
