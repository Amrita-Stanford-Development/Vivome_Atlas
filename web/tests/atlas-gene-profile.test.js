// A clicked cell's gene profile (web/js/atlas/gene-profile.js): read from the
// site's shards when it has them, from the CSVs when it has none.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { gzipSync } from 'node:zlib';

// A fresh copy of the module per test: it keeps the shards' index once fetched.
let copies = 0;
const freshModule = () => import(`../js/atlas/gene-profile.js?copy=${(copies += 1)}`);

const GENES = ['CD3E', 'MS4A1', 'NKG7'];
const CELLS = 5;
const PER_SHARD = 2;
// Cell c, gene g: c + g / 8, exact in float32; cell 3's MS4A1 is not a number.
const value = (c, g) => (c === 3 && g === 1 ? NaN : c + g / 8);
const shardBytes = (shard) => {
  const cells = [];
  for (let c = shard * PER_SHARD; c < Math.min(CELLS, (shard + 1) * PER_SHARD); c += 1) cells.push(c);
  return Buffer.from(new Float32Array(cells.flatMap((c) => GENES.map((_, g) => value(c, g)))).buffer);
};
const INDEX = {
  cells_per_shard: PER_SHARD, digits: 5,
  rna: { cells: CELLS, shards: 3, file: 'rna/{shard}.f32.gz', genes: GENES },
};

// fetch answers from `files` (by the URL's end), 404 for anything else; every
// URL asked for is kept in `asked`.
function serve(files) {
  const asked = [];
  globalThis.fetch = async (url) => {
    const href = String(url);
    asked.push(href);
    const name = Object.keys(files).find((end) => href.endsWith(end));
    return name ? new Response(files[name]) : new Response('Not found', { status: 404 });
  };
  return asked;
}

test('a float32 reads back as the shortest text the CSVs print', async () => {
  const { float32Text } = await freshModule();
  // Values as written in web/data/atlas_RNA_lat128-001-part1.csv.
  for (const text of ['-0.3303922', '3.15165', '12.60425', '2.68525', '-0.45338115', '2.4165416', '0.5', '-2']) {
    assert.equal(float32Text(Math.fround(Number(text))), String(Number(text)), text);
  }
  // The drawer's four decimals then match the CSV's, not the float32's own:
  // 3.15165 is stored as 3.1516499519…
  assert.equal(Math.fround(3.15165).toFixed(4), '3.1516');
  assert.equal(Number(float32Text(Math.fround(3.15165))).toFixed(4), '3.1517');
});

test('a shard row decodes to its cell, leaving out values that are not numbers', async () => {
  const { shardProfile } = await freshModule();
  const bytes = shardBytes(1); // cells 2 and 3
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  assert.deepEqual(shardProfile(buffer, GENES, 0), { CD3E: 2, MS4A1: 2.125, NKG7: 2.25 });
  assert.deepEqual(shardProfile(buffer, GENES, 1), { CD3E: 3, NKG7: 3.25 });
  assert.throws(() => shardProfile(buffer, GENES, 2), /shorter than its index/);
});

test('a click fetches the index once and only its cell\'s shard', async () => {
  const { loadProfile } = await freshModule();
  const asked = serve({
    'profiles/index.json': JSON.stringify(INDEX),
    'profiles/rna/00000.f32.gz': gzipSync(shardBytes(0)),
    'profiles/rna/00002.f32.gz': gzipSync(shardBytes(2)),
  });
  assert.deepEqual(await loadProfile('rna', 4), { CD3E: 4, MS4A1: 4.125, NKG7: 4.25 });
  assert.deepEqual(await loadProfile('rna', 1), { CD3E: 1, MS4A1: 1.125, NKG7: 1.25 });
  await loadProfile('rna', 1); // kept from the first time
  assert.deepEqual(asked.map((url) => url.split('/data/')[1]),
    ['profiles/index.json', 'profiles/rna/00002.f32.gz', 'profiles/rna/00000.f32.gz']);
});

test('a shard already decoded on the way reads the same', async () => {
  const { loadProfile } = await freshModule();
  serve({ 'profiles/index.json': JSON.stringify(INDEX), 'profiles/rna/00001.f32.gz': shardBytes(1) });
  assert.deepEqual(await loadProfile('rna', 3), { CD3E: 3, NKG7: 3.25 });
});

test('a cell beyond the index is not found, and a missing shard says so', async () => {
  const { loadProfile } = await freshModule();
  serve({ 'profiles/index.json': JSON.stringify(INDEX) });
  await assert.rejects(loadProfile('rna', CELLS), /Cell 5 was not found in the RNA profiles/);
  await assert.rejects(loadProfile('rna', 0), /could not be fetched \(HTTP 404\)/);
});

test('without shards, the CSVs are read, and their absence says the profiles are not on this copy', async () => {
  const { loadProfile } = await freshModule();
  const asked = serve({});
  await assert.rejects(loadProfile('rna', 0), /Gene profiles are not on this copy of the site/);
  assert.ok(asked.some((url) => url.endsWith('atlas_RNA_lat128-001-part1.csv')), 'the CSV parts were tried');
});
