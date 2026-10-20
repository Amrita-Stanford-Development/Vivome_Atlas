// What the browser can tell about an upload before sending it: its
// separator, how many cells and feature rows it has, and whether those fit
// the service's limits. Expression matrices are routinely gigabytes, so the
// file is never read into memory whole: the header line is read slice by
// slice and the rows are counted by streaming, and peak memory stays flat
// whatever the file's size. Pure: works on any Blob (a File in the browser,
// a Blob under node --test).

import { formatCount, isMeasured } from '../manifest.js';

export const HEADER_BYTES = 64 * 1024;
// checkFile reads a header longer than one slice up to this many bytes,
// enough for far more cells than any upload the service takes.
export const HEADER_LIMIT_BYTES = 16 * 1024 * 1024;

// A DIA-NN report's annotation columns (docs/service/projection-api.md):
// "Genes" holds the identifiers; none of them is a cell.
export const DIANN_ANNOTATIONS = Object.freeze([
  'Genes', 'Protein.Group', 'Protein.Names', 'First.Protein.Description', 'N.Sequences', 'N.Proteotypic.Sequences',
]);

// A FragPipe TMT-Integrator protein table's, which the service also reads
// (service/pipeline/alignment.py): "Gene" holds the identifiers, and the
// reference channels are not cells.
export const FRAGPIPE_ANNOTATIONS = Object.freeze([
  'Index', 'NumberPSM', 'Gene', 'MaxPepProb', 'Protein', 'Protein ID', 'Entry Name', 'Protein Description',
  'Organism', 'Indistinguishable Proteins', 'ReferenceIntensity',
]);
const FRAGPIPE_REFERENCE_PREFIXES = ['RefInt_', 'RefDInt_'];

// MaxQuant's proteinGroups.txt and FragPipe's LFQ combined_protein.tsv: the
// service reads one cell per sample from the first of these quantity
// columns it finds (service/pipeline/alignment.py); every other column
// is annotation.
const MAXQUANT_QUANTITIES = [/^LFQ intensity (.+)$/, /^Intensity (.+)$/];
const FRAGPIPE_LFQ_QUANTITIES = [/^(?!Combined )(.+) MaxLFQ Intensity$/, /^(?!Combined )(.+?)(?<! MaxLFQ) Intensity$/];
const sampleColumns = (fields, patterns) => patterns.map((p) => fields.filter((f) => p.test(f)).length).find((n) => n > 0) ?? 0;

// The file's first line, without its line ending. By default from the first
// HEADER_BYTES only; a larger maxBytes reads on, a slice at a time, until
// the line ends.
export async function readHeaderLine(blob, { maxBytes = HEADER_BYTES } = {}) {
  const decoder = new TextDecoder();
  let text = '';
  for (let offset = 0; offset < Math.min(blob.size, maxBytes); offset += HEADER_BYTES) {
    const end = Math.min(blob.size, maxBytes, offset + HEADER_BYTES);
    const searchFrom = text.length;
    text += decoder.decode(new Uint8Array(await blob.slice(offset, end).arrayBuffer()), { stream: end < blob.size });
    const newline = text.indexOf('\n', searchFrom);
    if (newline !== -1) return text.slice(0, newline).replace(/\r$/, '');
  }
  return (text + decoder.decode()).replace(/\r$/, '');
}

// How many lines hold anything but white space, streamed in chunks.
export async function countNonEmptyLines(blob) {
  const reader = blob.stream().getReader();
  const decoder = new TextDecoder();
  let count = 0;
  let tail = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const parts = (tail + decoder.decode(value, { stream: true })).split('\n');
    tail = parts.pop();
    for (const part of parts) if (part.trim() !== '') count += 1;
  }
  tail += decoder.decode();
  if (tail.trim() !== '') count += 1;
  return count;
}

// One header line's fields, as the service's CSV reader splits them: a
// field that starts with a double quote runs to its closing quote, and two
// quotes inside it are one.
export function splitFields(line, separator) {
  const out = [];
  let i = 0;
  while (true) {
    let field = '';
    if (line[i] === '"') {
      i += 1;
      while (i < line.length) {
        if (line[i] === '"' && line[i + 1] === '"') {
          field += '"';
          i += 2;
        } else if (line[i] === '"') {
          i += 1;
          break;
        } else {
          field += line[i];
          i += 1;
        }
      }
    }
    while (i < line.length && line[i] !== separator) {
      field += line[i];
      i += 1;
    }
    out.push(field);
    if (i >= line.length) return out;
    i += 1;
  }
}

// The header's separator (a tab when it has more tabs than commas, as the
// service decides), its fields, and how many of them are not cells: the
// identifier column, the known annotation columns, and blank names.
export function parseHeader(line) {
  const text = String(line ?? '');
  const tabs = text.split('\t').length - 1;
  const commas = text.split(',').length - 1;
  const separator = tabs > commas ? '\t' : ',';
  const fields = splitFields(text, separator);
  const maxquant = fields.includes('Majority protein IDs') && fields.includes('Gene names');
  const fragpipeLfq = !maxquant && fields.includes('Gene') && fields.includes('Combined Total Peptides');
  if (maxquant || fragpipeLfq) {
    const cells = sampleColumns(fields, maxquant ? MAXQUANT_QUANTITIES : FRAGPIPE_LFQ_QUANTITIES);
    return {
      separator, columns: fields.length, annotation: fields.length - cells, cellEstimate: cells,
      format: maxquant ? 'maxquant' : 'fragpipe-lfq',
    };
  }
  const diann = fields.includes('Genes');
  const fragpipe = !diann && fields.includes('Gene');
  const idColumn = diann ? fields.indexOf('Genes') : fragpipe ? fields.indexOf('Gene') : 0;
  const known = (name) => (fragpipe
    ? FRAGPIPE_ANNOTATIONS.includes(name) || FRAGPIPE_REFERENCE_PREFIXES.some((p) => name.startsWith(p))
    : DIANN_ANNOTATIONS.includes(name));
  let annotation = 0;
  fields.forEach((name, i) => {
    if (i === idColumn || known(name) || name.trim() === '') annotation += 1;
  });
  return {
    separator,
    columns: fields.length,
    annotation,
    cellEstimate: fields.length - annotation,
    format: diann ? 'diann' : fragpipe ? 'fragpipe' : 'matrix',
  };
}

// The file's shape, or an Error saying in plain words why it cannot be sent.
export async function checkFile(blob, name = blob?.name ?? '') {
  const header = await readHeaderLine(blob, { maxBytes: HEADER_LIMIT_BYTES });
  if (header.trim() === '') throw new Error('The file has no header row.');
  const parsed = parseHeader(header);
  if (parsed.cellEstimate < 1) throw new Error('The header row lists no cells.');
  const features = (await countNonEmptyLines(blob)) - 1;
  if (features < 1) throw new Error('The file has a header row but no feature rows.');
  return {
    name, size: blob.size, separator: parsed.separator, columns: parsed.columns,
    annotation: parsed.annotation, format: parsed.format, features, cells: parsed.cellEstimate,
  };
}

// A limit given as a number (the service's /api/status) or as a measured
// record (web/data/workflow.json's service records); anything else is not
// checked.
function limitValue(limit) {
  if (limit && typeof limit === 'object') return isMeasured(limit) ? Number(limit.value) : null;
  return limit === null || limit === undefined || !Number.isFinite(Number(limit)) ? null : Number(limit);
}

const MB = 1024 * 1024;
const SPLIT_ADVICE = 'Split the cells at random into smaller files, so each is still a mix of cell types.';

// Whether a checked file fits the service: at most max_cells cells and
// max_upload_mb megabytes, at least min_cells cells (service/config.py,
// service/pipeline/validation.py). Each problem is one plain sentence.
export function checkLimits(check, limits = {}) {
  const problems = [];
  const maxCells = limitValue(limits?.max_cells);
  const maxMb = limitValue(limits?.max_upload_mb);
  const minCells = limitValue(limits?.min_cells);
  const cellWord = (n) => (n === 1 ? 'cell' : 'cells');
  if (maxCells !== null && check.cells > maxCells) {
    problems.push(`The file has ${formatCount(check.cells)} cells; the service labels at most ${formatCount(maxCells)} per upload. ${SPLIT_ADVICE}`);
  }
  if (minCells !== null && check.cells < minCells) {
    problems.push(`The file has ${formatCount(check.cells)} ${cellWord(check.cells)}; the service needs at least ${formatCount(minCells)} in one upload.`);
  }
  if (maxMb !== null && check.size > maxMb * MB) {
    problems.push(`The file is ${(check.size / MB).toFixed(1)} MB; the service takes at most ${formatCount(maxMb)} MB per upload. ${SPLIT_ADVICE}`);
  }
  return { ok: problems.length === 0, problems };
}
