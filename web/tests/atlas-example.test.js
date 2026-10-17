import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';

// The Atlas page's Your data tab offers the PBMC240 example to try. The site
// serves it from web/data/examples/; the service's tests and
// deploy/huggingface/check_space.py use service/examples/. The two must stay
// one file, byte for byte (it is CRLF as delivered, kept by .gitattributes).
const DEPLOYED = new URL('../data/examples/pbmc240_proteins_raw.tsv', import.meta.url);
const SOURCE = new URL('../../service/examples/pbmc240_proteins_raw.tsv', import.meta.url);
const PAGES_MAX_BYTES = 25 * 1024 * 1024; // Cloudflare Pages' per-file limit (scripts/build_pages_site.py)

test('the deployed example is byte-identical to service/examples\' copy', () => {
  assert.ok(readFileSync(DEPLOYED).equals(readFileSync(SOURCE)),
    'web/data/examples/pbmc240_proteins_raw.tsv differs from service/examples/; copy it again byte for byte');
});

test('the deployed example fits under Cloudflare Pages\' file limit', () => {
  const bytes = statSync(DEPLOYED).size;
  assert.ok(bytes > 0, 'the example is empty');
  assert.ok(bytes <= PAGES_MAX_BYTES, `the example is ${bytes} bytes, over Pages' 25 MiB limit`);
});

test('the deployed example is a DIA-NN report with a Genes column', () => {
  const text = readFileSync(DEPLOYED, 'utf8');
  const header = text.slice(0, text.search(/\r?\n/)).split('\t');
  assert.ok(header.includes('Genes'), 'the header has no Genes column');
  assert.ok(header.includes('Protein.Group'), 'the header has no Protein.Group column');
  assert.ok(header.length > 6, 'the header names no cell columns');
});
