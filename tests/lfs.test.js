import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isLfsPointer } from '../js/manifest.js';

test('the shipped RNA part files are still unfetched LFS pointers', () => {
  const part1 = readFileSync(new URL('../Atlas/atlas_RNA_lat128-001-part1.csv', import.meta.url), 'utf8');
  assert.equal(isLfsPointer(part1), true,
    'If this fails, git lfs pull has been run — the guard should now fall through to real parsing.');
});

test('atlas.html guards RNA profile loading behind an LFS check', () => {
  const html = readFileSync(new URL('../atlas.html', import.meta.url), 'utf8');
  assert.match(html, /isLfsPointer/, 'atlas.html must check for LFS pointers before parsing');
  assert.match(html, /git lfs pull/, 'the error shown to the user must name the remedy');
});
