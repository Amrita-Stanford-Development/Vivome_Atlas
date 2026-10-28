// What the browser tells about an upload before sending it
// (web/js/atlas/file-check.js), on Node Blobs: separators, line endings,
// empty and header-only files, the real PBMC240 example, and the limits.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  DIANN_ANNOTATIONS, HEADER_BYTES, HEADER_LIMIT_BYTES, checkFile, checkLimits, countNonEmptyLines, parseHeader,
  readHeaderLine, splitFields, valueFactsText,
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
  const summaries = ['Protein', 'Gene', 'Combined Total Peptides', 'A Intensity', 'A Unique Intensity', 'A Total Intensity',
    'A Razor Intensity', 'A MaxLFQ Unique Intensity'].join('\t');
  assert.equal(parseHeader(summaries).cellEstimate, 1, 'unique, total and razor intensities are not cells');
});

test('a Spectronaut pivot report counts one cell per run', () => {
  const header = ['PG.ProteinGroups', 'PG.Genes', 'PG.ProteinNames', '[1] a.raw.PG.Quantity', '[2] b.raw.PG.Quantity',
    '[3] c.d.PG.Quantity'].join('\t');
  assert.deepEqual(parseHeader(header), { separator: '\t', columns: 6, annotation: 3, cellEstimate: 3, format: 'spectronaut' });
});

test('MaxQuant SILAC and TMT searches are refused in words, as the service refuses them', async () => {
  const silac = ['Majority protein IDs', 'Gene names', 'Ratio H/L', 'Intensity', 'Intensity L', 'Intensity H'].join('\t');
  assert.match(parseHeader(silac).refusal, /SILAC/);
  const tmt = ['Majority protein IDs', 'Gene names', 'Reporter intensity corrected 1 X1', 'Intensity X1'].join('\t');
  assert.match(parseHeader(tmt).refusal, /TMT/);
  await assert.rejects(checkFile(blob(`${tmt}\nP1\tGENE1\t10\t300\n`)), /TMT/);
});

test('the DIA-NN annotation columns are the service\'s own list', () => {
  const source = readFileSync(new URL('../../service/pipeline/alignment.py', import.meta.url), 'utf8');
  const block = /_DIA_NN_ANNOTATION_COLUMNS = frozenset\(\{([\s\S]*?)\}\)/.exec(source)[1];
  const python = [...block.matchAll(/"([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual([...DIANN_ANNOTATIONS].sort(), python);
  const diann18 = ['Protein.Group', 'Protein.Ids', 'Protein.Names', 'Genes', 'First.Protein.Description', 'a.raw', 'b.raw'].join('\t');
  assert.equal(parseHeader(diann18).cellEstimate, 2);
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

test('the check reads the values in the cell columns: range, zeros, empties and negatives', async () => {
  const matrix = 'gene,a,b\nG1,0,5\nG2,-1.5,NA\nG3,,200\n';
  assert.deepEqual((await checkFile(blob(matrix))).values,
    { entries: 6, empty: 2, zeros: 1, negatives: 1, min: -1.5, max: 200 });
  const diann = 'Protein.Group\tProtein.Names\tGenes\tFirst.Protein.Description\tc1\tc2\n'
    + 'P1\tN1\tCD3E\t-99 kDa protein\t1000\t0\nP2\tN2\tCD19\tsomething\t\t30000\n';
  assert.deepEqual((await checkFile(blob(diann))).values,
    { entries: 4, empty: 1, zeros: 1, negatives: 0, min: 0, max: 30000 }, 'annotation columns are not values');
  const maxquant = 'Majority protein IDs\tGene names\tIntensity\tIntensity s1\tLFQ intensity s1\tLFQ intensity s2\n'
    + 'P1\tCD3E\t9e9\t5e9\t100\t0\n';
  assert.deepEqual((await checkFile(blob(maxquant))).values,
    { entries: 2, empty: 0, zeros: 1, negatives: 0, min: 0, max: 100 }, 'only the LFQ intensities, as the service reads them');
  const rTable = 'a\tb\nG1\t1\t2\nG2\t3\t4\n';
  assert.deepEqual((await checkFile(blob(rTable))).values,
    { entries: 4, empty: 0, zeros: 0, negatives: 0, min: 1, max: 4 }, 'R\'s layout: every header field is a cell');
  const quoted = 'gene,a,b\n"G1, isoform 2",7,8\n';
  assert.deepEqual((await checkFile(blob(quoted))).values,
    { entries: 2, empty: 0, zeros: 0, negatives: 0, min: 7, max: 8 }, 'a quoted comma does not shift the columns');
});

test('the value facts in words', () => {
  assert.equal(valueFactsText({ entries: 200, empty: 20, zeros: 90, negatives: 0, min: 0, max: 211481 }),
    'From 0 to 211,481; 45.0% are 0 and 10.0% are empty; none is negative.');
  assert.equal(valueFactsText({ entries: 4, empty: 0, zeros: 0, negatives: 1, min: -1.523, max: 12.75 }),
    'From -1.523 to 12.75; 0.0% are 0 and 0.0% are empty; 1 is negative.');
  assert.equal(valueFactsText({ entries: 10, empty: 0, zeros: 0, negatives: 3, min: -2, max: 1234.56 }),
    'From -2 to 1,234.6; 0.0% are 0 and 0.0% are empty; 3 are negative.');
  assert.equal(valueFactsText({ entries: 3, empty: 3, zeros: 0, negatives: 0, min: null, max: null }), 'Every value is empty.');
  for (const bad of [null, undefined, {}, { entries: 0 }]) assert.equal(valueFactsText(bad), null);
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
  assert.deepEqual(tsv, {
    name: 'cells.tsv', size: 33, separator: '\t', columns: 4, annotation: 1, format: 'matrix', features: 2, cells: 3,
    values: { entries: 6, empty: 0, zeros: 0, negatives: 0, min: 1, max: 6 },
  });
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
  assert.equal(s.max_mb.value, 31, 'what Cloud Run takes in one HTTP/1 request, with room for the form');
  assert.match(large.problems[0], /^The file is 250\.4 MB; the service takes at most 31 MB per upload\./);

  const both = checkLimits({ cells: 3000, size: 300 * 1024 * 1024 }, limits);
  assert.equal(both.problems.length, 2);
  for (const p of [...many.problems, ...few.problems, ...large.problems]) assert.ok(!p.includes('—'), p);

  // A limit not known is not checked.
  assert.deepEqual(checkLimits({ cells: 99999, size: 1e12 }, {}), { ok: true, problems: [] });
  assert.deepEqual(checkLimits({ cells: 99999, size: 1e12 }, null), { ok: true, problems: [] });
  const pending = { max_cells: { value: null, status: 'pending' }, min_cells: { value: 20, status: 'measured' } };
  assert.deepEqual(checkLimits({ cells: 99999, size: 1 }, pending), { ok: true, problems: [] });
});

test('a table written by R without the corner field counts every header field as a cell, as the service reads it', async () => {
  const header = Array.from({ length: 20 }, (_, i) => `c${i + 1}`).join('\t');
  const row = ['CD3E', ...Array.from({ length: 20 }, (_, i) => String(i + 1))].join('\t');
  const check = await checkFile(blob(`${header}\n${row}\n${row.replace('CD3E', 'CD4')}\n`));
  assert.equal(check.cells, 20);
  assert.equal(checkLimits(check, { min_cells: 20 }).ok, true);
  // a trailing separator on the rows only is not a missing corner
  assert.equal((await checkFile(blob('gene,c1,c2\nG1,1,2,\nG2,3,4,\n'))).cells, 2);
  // nor is a named or blank corner, or one row's extra field filled (service/tests/test_alignment.py)
  assert.equal((await checkFile(blob('gene,c1,c2\nG0,1,2,\nG1,3,4,5\n'))).cells, 2);
  assert.equal((await checkFile(blob('Gene,c1,c2\nG0,1,2,9\nG1,3,4,9\n'))).cells, 2);
  assert.equal((await checkFile(blob(',c1,c2\nG0,1,2,9\nG1,3,4,9\n'))).cells, 2);
});

test('R\'s layout with blank missing values, and the rows judged, as the service reads them', async () => {
  // R's write.table(m, sep="\t", na=""): a row whose last value is missing (service/tests/test_alignment.py)
  const header = Array.from({ length: 20 }, (_, i) => `s${i + 1}`).join('\t');
  const rows = Array.from({ length: 30 }, (_, g) => {
    const values = Array.from({ length: 20 }, (_, i) => String(g + i));
    if (g % 3 === 0) values[19] = '';
    return [`G${g}`, ...values].join('\t');
  });
  assert.equal((await checkFile(blob(`${header}\n${rows.join('\n')}\n`))).cells, 20);
  // a row of blank fields is not judged
  const plain = Array.from({ length: 30 }, (_, g) => `G${g},${g},${g + 1}`).join('\n');
  assert.equal((await checkFile(blob(`s1,s2\n,,\n${plain}\n`))).cells, 2);
  // 12 Perseus rows ahead: the 50 rows judged reach row 50, which is one field too long
  const perseus = Array.from({ length: 12 }, () => '#!{Type}E,E').join('\n');
  const good = Array.from({ length: 49 }, (_, g) => `G${g},${g},${g + 1}`).join('\n');
  assert.equal((await checkFile(blob(`s1,s2\n${perseus}\n${good}\nG49,1,2,3\n`))).cells, 1);
});

test('R\'s layout of a DIA-NN table: its first annotation column is not a cell, as the service reads it', async () => {
  const rows = Array.from({ length: 30 }, (_, g) => `G${g}\tP${g}\t${g}\t${g + 1}`).join('\n');
  assert.equal((await checkFile(blob(`Protein.Group\ts1\ts2\n${rows}\n`))).cells, 2);
});

test('a row of separators alone is not a feature row', async () => {
  assert.equal((await checkFile(blob('gene,c1,c2\nG0,1,2\n,,\nG1,3,4\n'))).features, 2);
  // only the file's own separator: a line of commas in a tab-separated file is a row the service reads
  assert.equal((await checkFile(blob('gene\tc1\tc2\nG0\t1\t2\n\t\t\nG1\t3\t4\n,,\n'))).features, 3);
});

test('UTF-16 cut off mid-character is refused, as the service refuses it', async () => {
  const text = 'gene,c1,c2\nG0,1,2\nG1,3,4\n';
  const bytes = new Uint8Array(2 + text.length * 2 + 1);
  bytes.set([0xff, 0xfe]);
  for (let i = 0; i < text.length; i += 1) bytes[2 + 2 * i] = text.charCodeAt(i);
  await assert.rejects(checkFile(blob(bytes)), /cut off/);
});

test('the size check leaves room for the form around the file', () => {
  const limits = { max_upload_mb: 31 };
  const exact = checkLimits({ cells: 100, size: 31 * 1024 * 1024 }, limits);
  assert.equal(exact.ok, false, 'a file of exactly the limit is over it once sent');
  assert.match(exact.problems[0], /the form around the file needs a little room/);
  assert.equal(checkLimits({ cells: 100, size: 30 * 1024 * 1024 }, limits).ok, true);
});

test('Perseus rows are skipped quoted or not, before the first 50 rows are judged, as the service does', async () => {
  const header = Array.from({ length: 20 }, (_, i) => `c${i + 1}`).join(',');
  const row = (g) => [g, ...Array.from({ length: 20 }, (_, i) => String(i + 1))].join(',');
  const perseus = ['"#!{Type}"', ...Array.from({ length: 20 }, () => 'E')].join(',');
  const rows = Array.from({ length: 50 }, (_, i) => row(`G${i}`));
  const check = await checkFile(blob([header, perseus, perseus, ...rows].join('\n') + '\n'));
  assert.equal(check.cells, 20, 'R layout: every header field a cell');
  assert.equal(check.features, 50, 'the quoted Perseus rows are not features');
});

test('a workbook, a binary file or UTF-16 text is read the way the service reads it', async () => {
  await assert.rejects(checkFile(blob(new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0, 0, 0, 0]))), /Excel workbook/);
  await assert.rejects(checkFile(blob(new Uint8Array([0x50, 0x41, 0x52, 0x31, 0, 1, 2, 3]))), /not text/);
  // text that merely starts with "PAR1" (a cell's name) is text, as the service reads it
  assert.equal((await checkFile(blob('PAR1_a,PAR1_b\nG0,1,2\n'))).cells, 2);
  const cells = Array.from({ length: 25 }, (_, i) => `E:\\raw\\SP_${i + 1}.raw`);
  const text = [['Protein.Group', 'Protein.Names', 'Genes', ...cells].join('\t'),
    ['P1', 'N1', 'CD3E', ...cells.map(() => '1.5')].join('\t'),
    ['P2', 'N2', 'CD4', ...cells.map(() => '2.5')].join('\t')].join('\r\n') + '\r\n';
  const utf16 = new Uint8Array(2 + text.length * 2);
  utf16.set([0xff, 0xfe]);
  for (let i = 0; i < text.length; i += 1) utf16[2 + 2 * i] = text.charCodeAt(i);
  const check = await checkFile(blob(utf16));
  assert.equal(check.format, 'diann');
  assert.equal(check.cells, 25);
  assert.equal(check.features, 2);
});

test('Perseus annotation rows are not feature rows', async () => {
  const header = ['Majority protein IDs', 'Gene names', 'LFQ intensity S1', 'LFQ intensity S2'].join('\t');
  const check = await checkFile(blob(`${header}\n#!{Type}E\tT\tE\tE\n#!{C:Group}\t\tA\tB\nP1\tGENE1\t100\t200\n`));
  assert.equal(check.features, 1);
});
