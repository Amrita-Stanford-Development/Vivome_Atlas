// What the browser tells about an upload before sending it
// (web/js/atlas/file-check.js), on Node Blobs: separators, line endings,
// empty and header-only files, the real PBMC240 example, and the limits.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  DIANN_ANNOTATIONS, HEADER_BYTES, HEADER_LIMIT_BYTES, checkFile, checkLimits, countNonEmptyLines, parseHeader,
  readHeaderLine, splitFields,
} from '../js/atlas/file-check.js';

const workflow = JSON.parse(readFileSync(new URL('../data/workflow.json', import.meta.url), 'utf8'));
const blob = (text) => new Blob([text]);

test('the DIA-NN annotation columns are the ones the contract lists', () => {
  const doc = readFileSync(new URL('../../docs/service/projection-api.md', import.meta.url), 'utf8');
  for (const name of DIANN_ANNOTATIONS) assert.ok(doc.includes(`\`${name}\``) || doc.includes(`"${name}"`), name);
  assert.equal(HEADER_BYTES, 64 * 1024);
  assert.ok(HEADER_LIMIT_BYTES > HEADER_BYTES);
});

test('a header line, with tabs or commas, and its cells', () => {
  assert.deepEqual(parseHeader('gene\ta\tb\tc'), { separator: '\t', columns: 4, annotation: 1, cellEstimate: 3, format: 'matrix' });
  assert.deepEqual(parseHeader('gene,a,b'), { separator: ',', columns: 3, annotation: 1, cellEstimate: 2, format: 'matrix' });
  // More tabs than commas is a tab file, as the service decides.
  assert.equal(parseHeader('gene\tcell, one\tcell, two').cellEstimate, 2);
  assert.equal(parseHeader('gene,"cell, one","cell ""two"""').cellEstimate, 2, 'quoted commas');
  assert.deepEqual(splitFields('gene,"cell, one","cell ""two""",', ','), ['gene', 'cell, one', 'cell "two"', '']);
  assert.equal(parseHeader('gene,a,b,').cellEstimate, 2, 'a trailing separator names no cell');
  const diann = ['Protein.Group', 'Protein.Names', 'Genes', 'First.Protein.Description', 'N.Sequences',
    'N.Proteotypic.Sequences', 'E:\\raw\\SP_1.raw', 'E:\\raw\\SP_2.raw'].join('\t');
  assert.deepEqual(parseHeader(diann), { separator: '\t', columns: 8, annotation: 6, cellEstimate: 2, format: 'diann' });
  // "Genes" is the identifiers wherever it sits; the first column is then a cell.
  assert.equal(parseHeader('x1\tGenes\tx2').cellEstimate, 2);
  const fragpipe = ['Index', 'NumberPSM', 'Gene', 'ReferenceIntensity', 'RefInt_a', 'sample_1', 'sample_2'].join('\t');
  assert.deepEqual(parseHeader(fragpipe), { separator: '\t', columns: 7, annotation: 5, cellEstimate: 2, format: 'fragpipe' });
  assert.equal(parseHeader('gene').cellEstimate, 0);
});

test('MaxQuant and FragPipe LFQ tables count one cell per sample, as the service reads them', () => {
  const maxquant = ['Protein IDs', 'Majority protein IDs', 'Gene names', 'Peptides S1', 'Peptides S2', 'Intensity',
    'Intensity S1', 'Intensity S2', 'iBAQ S1', 'iBAQ S2', 'LFQ intensity S1', 'LFQ intensity S2', 'Reverse',
    'Potential contaminant', 'id'].join('\t');
  assert.deepEqual(parseHeader(maxquant), { separator: '\t', columns: 15, annotation: 13, cellEstimate: 2, format: 'maxquant' });
  const noLfq = ['Majority protein IDs', 'Gene names', 'Intensity', 'Intensity S1', 'Intensity S2', 'Intensity S3'].join('\t');
  assert.equal(parseHeader(noLfq).cellEstimate, 3);
  const fragpipe = ['Protein', 'Protein ID', 'Gene', 'Combined Total Peptides', 'Combined Spectral Count',
    'A_1 Spectral Count', 'A_1 Intensity', 'A_1 MaxLFQ Intensity', 'B_2 Spectral Count', 'B_2 Intensity',
    'B_2 MaxLFQ Intensity', 'Indistinguishable Proteins'].join('\t');
  assert.deepEqual(parseHeader(fragpipe), { separator: '\t', columns: 12, annotation: 10, cellEstimate: 2, format: 'fragpipe-lfq' });
  const noMaxLfq = ['Gene', 'Combined Total Peptides', 'A_1 Intensity', 'B_2 Intensity', 'C_3 Intensity'].join('\t');
  assert.equal(parseHeader(noMaxLfq).cellEstimate, 3);
});

test('reading the header line from a slice, and on when asked', async () => {
  assert.equal(await readHeaderLine(blob('gene,a,b\r\nX,1,2\r\n')), 'gene,a,b');
  assert.equal(await readHeaderLine(blob('gene\ta\tb')), 'gene\ta\tb', 'no line end at all');
  assert.equal(await readHeaderLine(blob('')), '');
  assert.equal(await readHeaderLine(blob('\ufeffgene,a\n')), 'gene,a', 'a byte order mark is not a column name');
  // A header longer than one slice: the default reads one slice only; a
  // larger limit reads to the line end, even through a character split
  // across two slices.
  const cells = Array.from({ length: 3000 }, (_, i) => `E:\\Proteomics_Astral\\raw\\TopMedPBMC1\\Astral_SP_é_${i}.raw`);
  const long = `Genes\t${cells.join('\t')}\r\nCD3E${'\t1'.repeat(3000)}\r\n`;
  assert.ok(long.length > 2 * HEADER_BYTES);
  const short = await readHeaderLine(blob(long));
  assert.ok(new TextEncoder().encode(short).length <= HEADER_BYTES);
  const full = await readHeaderLine(blob(long), { maxBytes: HEADER_LIMIT_BYTES });
  assert.equal(full, `Genes\t${cells.join('\t')}`);
  assert.equal((await checkFile(blob(long))).cells, 3000);
  // A two-byte character whose bytes sit either side of the slice boundary.
  const split = `Genes\t${'a'.repeat(HEADER_BYTES - 7)}é\tb\nX\t1\t2\n`;
  assert.equal(new TextEncoder().encode(split.slice(0, split.indexOf('é'))).length, HEADER_BYTES - 1);
  assert.equal(await readHeaderLine(blob(split), { maxBytes: HEADER_LIMIT_BYTES }), split.split('\n')[0]);
});

test('counting lines by streaming, whatever the line endings', async () => {
  assert.equal(await countNonEmptyLines(blob('')), 0);
  assert.equal(await countNonEmptyLines(blob('a\nb\n\n  \nc')), 3);
  assert.equal(await countNonEmptyLines(blob('a\r\nb\r\n\r\n')), 2);
  const big = 'x,1,2\n'.repeat(50000);
  assert.equal(await countNonEmptyLines(blob(big)), 50000, 'across many chunks');
});

test('a file checked: tabs and commas, CRLF', async () => {
  const tsv = await checkFile(blob('gene\ta\tb\tc\nCD3E\t1\t2\t3\nCD19\t4\t5\t6\n'), 'cells.tsv');
  assert.deepEqual(tsv, { name: 'cells.tsv', size: 33, separator: '\t', columns: 4, annotation: 1, format: 'matrix', features: 2, cells: 3 });
  const csv = await checkFile(blob('gene,a,b\r\nCD3E,1,2\r\n\r\nCD19,4,5\r\nCD14,7,8\r\n'));
  assert.deepEqual([csv.name, csv.separator, csv.columns, csv.features, csv.cells], ['', ',', 3, 3, 2]);
  const file = new File(['gene,a\nX,1\n'], 'named.csv');
  assert.equal((await checkFile(file)).name, 'named.csv', 'a File brings its name');
});

test('a file that cannot be sent says why in plain words', async () => {
  await assert.rejects(checkFile(blob(''), 'empty.csv'), { message: 'The file has no header row.' });
  await assert.rejects(checkFile(blob('\n\nX,1\n')), { message: 'The file has no header row.' });
  await assert.rejects(checkFile(blob('gene\nCD3E\n')), { message: 'The header row lists no cells.' });
  await assert.rejects(checkFile(blob('gene,a,b\n')), { message: 'The file has a header row but no feature rows.' });
  await assert.rejects(checkFile(blob('gene,a,b\r\n\r\n  \r\n')), { message: 'The file has a header row but no feature rows.' });
});

test('the real PBMC240 example: a DIA-NN report of 238 cells', async () => {
  const bytes = readFileSync(new URL('../../service/examples/pbmc240_proteins_raw.tsv', import.meta.url));
  const check = await checkFile(new Blob([bytes]), 'pbmc240_proteins_raw.tsv');
  const text = bytes.toString('utf8');
  const lines = text.split('\n').filter((l) => l.trim() !== '');
  assert.equal(check.cells, 238);
  assert.equal(check.cells, workflow.facts.runs.value, 'the runs the workflow data counts');
  assert.equal(check.separator, '\t');
  assert.equal(check.format, 'diann');
  assert.equal(check.annotation, 6);
  assert.equal(check.columns, 244);
  assert.equal(check.features, lines.length - 1);
  assert.equal(check.size, bytes.length);
  assert.deepEqual(checkLimits(check, { max_cells: 2000, max_upload_mb: 200, min_cells: 20 }), { ok: true, problems: [] });
});

test('the limits, as numbers or as the workflow data records them', () => {
  const s = workflow.service;
  const limits = { max_cells: s.max_cells, max_upload_mb: s.max_mb, min_cells: s.min_cells };
  const fits = { cells: 238, size: 2_758_124 };
  assert.deepEqual(checkLimits(fits, limits), { ok: true, problems: [] });
  assert.deepEqual(checkLimits(fits, { max_cells: 2000, max_upload_mb: 200.0, min_cells: 20 }), { ok: true, problems: [] });

  const many = checkLimits({ cells: 2500, size: 1000 }, limits);
  assert.equal(many.ok, false);
  assert.equal(many.problems.length, 1);
  assert.match(many.problems[0], /^The file has 2,500 cells; the service labels at most 2,000 per upload\. Split the cells at random/);

  const few = checkLimits({ cells: 12, size: 1000 }, limits);
  assert.deepEqual(few, { ok: false, problems: ['The file has 12 cells; the service needs at least 20 in one upload.'] });
  assert.equal(checkLimits({ cells: 1, size: 10 }, limits).problems[0], 'The file has 1 cell; the service needs at least 20 in one upload.');

  const large = checkLimits({ cells: 500, size: 250.4 * 1024 * 1024 }, limits);
  assert.equal(s.max_mb.value, 100, 'what the site’s host takes in one request');
  assert.match(large.problems[0], /^The file is 250\.4 MB; the service takes at most 100 MB per upload\./);

  const both = checkLimits({ cells: 3000, size: 300 * 1024 * 1024 }, limits);
  assert.equal(both.problems.length, 2);
  for (const p of [...many.problems, ...few.problems, ...large.problems]) assert.ok(!p.includes('—'), p);

  // A limit not known is not checked.
  assert.deepEqual(checkLimits({ cells: 99999, size: 1e12 }, {}), { ok: true, problems: [] });
  assert.deepEqual(checkLimits({ cells: 99999, size: 1e12 }, null), { ok: true, problems: [] });
  const pending = { max_cells: { value: null, status: 'pending' }, min_cells: { value: 20, status: 'measured' } };
  assert.deepEqual(checkLimits({ cells: 99999, size: 1 }, pending), { ok: true, problems: [] });
});
