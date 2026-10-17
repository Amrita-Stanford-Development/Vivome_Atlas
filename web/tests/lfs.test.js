import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { isLfsPointer } from '../js/manifest.js';

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8');

test('the shipped RNA part files are still unfetched LFS pointers', () => {
  const part1 = read('../data/atlas_RNA_lat128-001-part1.csv');
  assert.equal(isLfsPointer(part1), true,
    'If this fails, git lfs pull has been run — the guard should now fall through to real parsing.');
});

test('the Atlas page guards gene-profile loading behind the LFS check', () => {
  const src = read('../js/atlas/gene-profile.js');
  assert.match(src, /import \{[^}]*\bisLfsPointer\b[^}]*\} from '\.\.\/manifest\.js'/,
    'gene-profile.js must use the one LFS check, in web/js/manifest.js');
  assert.match(src, /isLfsPointer\(/, 'it must check for LFS pointers before parsing');
  assert.match(src, /git lfs pull/, 'the error shown to the user must name the remedy');
});

// The magic string lives in one place, so a typo cannot disable the guard on
// one page while the suite stays green.
test('the LFS magic string exists once, in web/js/manifest.js', () => {
  const magic = read('../js/manifest.js').match(/const LFS_MAGIC = '([^']+)'/)[1];
  const web = new URL('../', import.meta.url);
  const files = [];
  const walk = (rel) => {
    for (const name of readdirSync(new URL(rel, web))) {
      const path = `${rel}${name}`;
      if (statSync(new URL(path, web)).isDirectory()) {
        if (name !== 'tests' && name !== 'data') walk(`${path}/`);
      } else if (/\.(html|js)$/.test(name)) {
        files.push(path);
      }
    }
  };
  walk('');
  const holders = files.filter((f) => readFileSync(new URL(f, web), 'utf8').includes(magic));
  assert.deepEqual(holders, ['js/manifest.js']);
});

test('both copies agree with a real pointer file', () => {
  const magic = read('../js/manifest.js').match(/const LFS_MAGIC = '([^']+)'/)[1];
  assert.ok(read('../data/atlas_RNA_lat128-001-part1.csv').startsWith(magic));
});
