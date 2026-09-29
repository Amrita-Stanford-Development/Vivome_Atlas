import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isLfsPointer } from '../js/manifest.js';

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8');

test('the shipped RNA part files are still unfetched LFS pointers', () => {
  const part1 = read('../data/atlas_RNA_lat128-001-part1.csv');
  assert.equal(isLfsPointer(part1), true,
    'If this fails, git lfs pull has been run — the guard should now fall through to real parsing.');
});

test('atlas.html guards RNA profile loading behind an LFS check', () => {
  const html = read('../atlas.html');
  assert.match(html, /isLfsPointer/, 'atlas.html must check for LFS pointers before parsing');
  assert.match(html, /git lfs pull/, 'the error shown to the user must name the remedy');
});

// atlas.html's main script is a classic script and cannot import web/js/manifest.js,
// so the magic string exists twice. Pin them together: a typo in either copy
// would otherwise disable the guard on one side while the suite stayed green.
test('the LFS magic string is byte-identical in both copies', () => {
  const fromModule = read('../js/manifest.js').match(/const LFS_MAGIC = '([^']+)'/);
  const fromAtlas = read('../atlas.html').match(/text\.startsWith\('([^']+)'\)/);
  assert.ok(fromModule, 'LFS_MAGIC not found in web/js/manifest.js');
  assert.ok(fromAtlas, 'startsWith literal not found in atlas.html');
  assert.equal(fromAtlas[1], fromModule[1],
    'atlas.html and web/js/manifest.js disagree on the Git LFS pointer magic string');
});

test('both copies agree with a real pointer file', () => {
  const magic = read('../js/manifest.js').match(/const LFS_MAGIC = '([^']+)'/)[1];
  assert.ok(read('../data/atlas_RNA_lat128-001-part1.csv').startsWith(magic));
});
