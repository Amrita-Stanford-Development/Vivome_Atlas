// The atlas's reference cells, read from the real metadata files
// (web/js/atlas/reference-data.js).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  SCENE_SPAN, atlasFrame, classAnchors, classCodes, classOrderFrom, fromScene, parseCsvLine, parseMetadataCsv,
  sceneArray, toScene,
} from '../js/atlas/reference-data.js';
import { CLASS_COLOURS } from '../js/workflow-data.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const rnaText = read('data/metadata_RNA_lat128.csv');
const protText = read('data/metadata_PROT_lat128.csv');
const rna = parseMetadataCsv(rnaText, 'rna');
const prot = parseMetadataCsv(protText, 'prot');
const order = classOrderFrom(rna, prot);

test('the real metadata files read in full', () => {
  assert.equal(rna.n, 85233);
  assert.equal(prot.n, 1490);
  assert.equal(rna.raw.length, rna.n * 3);
  assert.equal(order.length, 22);
  assert.equal(order.length, CLASS_COLOURS.length, 'one colour per class');
  for (const name of new Set(prot.names)) assert.ok(new Set(rna.names).has(name), `${name} is a reference class`);
});

test('quoted class names keep their commas', () => {
  assert.deepEqual(parseCsvLine('128,rna,7,2,"cd4-positive, alpha-beta t cell",lymphoid,0.1,0.2,0.3'),
    ['128', 'rna', '7', '2', 'cd4-positive, alpha-beta t cell', 'lymphoid', '0.1', '0.2', '0.3']);
  assert.ok(rna.names.includes('cd4-positive, alpha-beta t cell'));
  assert.deepEqual(parseCsvLine('a,"say ""hi""",b'), ['a', 'say "hi"', 'b']);
});

test('each file\'s class index is the class\'s place in sorted order, so every type keeps its colour', () => {
  for (const data of [rna, prot]) {
    const codes = classCodes(data, order);
    for (let i = 0; i < data.n; i += 1) assert.equal(data.classIdx[i], codes[i], `${data.modality} row ${i}`);
  }
  assert.deepEqual([...order].sort(), order);
});

test('the frame is the one the viewer has always used, and maps both ways', () => {
  // The old viewer: the box round every RNA and protein cell, its midpoint,
  // and 80 units across the widest axis, computed from the parsed numbers.
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  for (const text of [rnaText, protText]) {
    const lines = text.trim().split('\n');
    const header = parseCsvLine(lines[0]);
    const cols = ['PC1', 'PC2', 'PC3'].map((c) => header.indexOf(c));
    for (const line of lines.slice(1)) {
      const v = parseCsvLine(line);
      cols.forEach((c, k) => {
        lo[k] = Math.min(lo[k], Number(v[c]));
        hi[k] = Math.max(hi[k], Number(v[c]));
      });
    }
  }
  const frame = atlasFrame(rna.raw, prot.raw);
  const scale = SCENE_SPAN / Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  assert.ok(Math.abs(frame.scale - scale) / scale < 1e-6, `${frame.scale} against ${scale}`);
  frame.centre.forEach((c, k) => assert.ok(Math.abs(c - (lo[k] + hi[k]) / 2) < 1e-6));
  const p = [0.1, -0.2, 0.3];
  fromScene(frame, toScene(frame, p)).forEach((v, k) => assert.ok(Math.abs(v - p[k]) < 1e-12));
  const pos = sceneArray(frame, rna.raw);
  const first = toScene(frame, [rna.raw[0], rna.raw[1], rna.raw[2]]);
  first.forEach((v, k) => assert.ok(Math.abs(pos[k] - v) < 1e-4));
  // Every reference cell sits inside the 80-unit box.
  for (let i = 0; i < pos.length; i += 1) assert.ok(Math.abs(pos[i]) <= SCENE_SPAN / 2 + 1e-3);
});

test('each class name sits on one of its own cells', () => {
  const frame = atlasFrame(rna.raw, prot.raw);
  const pos = sceneArray(frame, rna.raw);
  const codes = classCodes(rna, order);
  const anchors = classAnchors(pos, codes, rna.n, order.length);
  assert.equal(anchors.length, 22);
  anchors.forEach((a, c) => {
    assert.ok(a, order[c]);
    let found = false;
    for (let i = 0; i < rna.n && !found; i += 1) {
      found = codes[i] === c && pos[i * 3] === a[0] && pos[i * 3 + 1] === a[1] && pos[i * 3 + 2] === a[2];
    }
    assert.ok(found, `${order[c]}'s name is on one of its cells`);
  });
});
