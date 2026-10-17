// The Atlas page's landing (web/js/atlas/landing.js) run end to end in Node,
// on stand-ins for the page, three.js and the stage: the recorded example
// from idle to the settled view, Skip, Clear, and a file sent to a fake
// service, including a busy service and an unreachable one.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createLanding } from '../js/atlas/landing.js';
import { outcomeCounts } from '../js/atlas/answers.js';
import { ServiceError } from '../js/atlas/service-client.js';

const workflowText = readFileSync(new URL('../data/workflow.json', import.meta.url), 'utf8');
const workflow = JSON.parse(workflowText);
const order = workflow.class_order;

// ---- stand-ins ----

class El {
  constructor(id) {
    this.id = id;
    this.innerHTML = '';
    this.textContent = '';
    this.hidden = false;
    this.listeners = {};
    this.attrs = {};
    this.style = {};
    this.dataset = {};
    const classes = new Set();
    this.classList = {
      add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c),
      toggle: (c, on) => ((on ?? !classes.has(c)) ? classes.add(c) : classes.delete(c)),
    };
  }
  addEventListener(type, f) { (this.listeners[type] ??= []).push(f); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k] ?? null; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 800, height: 600 }; }
}

function installDocument() {
  const els = new Map();
  globalThis.document = {
    getElementById: (id) => {
      if (!els.has(id)) els.set(id, new El(id));
      return els.get(id);
    },
    addEventListener() {},
    createElement: () => new El('a'),
    hidden: false,
  };
  globalThis.fetch = async (url) => {
    const path = String(url);
    if (path.endsWith('workflow.json')) return { ok: true, json: async () => JSON.parse(workflowText) };
    if (path.endsWith('pbmc240_proteins_raw.tsv')) {
      const bytes = readFileSync(new URL('../data/examples/pbmc240_proteins_raw.tsv', import.meta.url));
      return { ok: true, blob: async () => new Blob([bytes]) };
    }
    throw new Error(`unexpected fetch ${path}`);
  };
  return els;
}

const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

function fakeThree() {
  class Vec { constructor(...v) { this.v = v; } set(...v) { this.v = v; return this; } get x() { return this.v[0]; } }
  return {
    BufferGeometry: class { constructor() { this.attributes = {}; } setAttribute(k, a) { this.attributes[k] = a; return this; } dispose() {} },
    BufferAttribute: class { constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; } setUsage() { return this; } },
    ShaderMaterial: class { constructor(p) { Object.assign(this, p); } dispose() {} },
    Points: class { constructor(geometry, material) { this.geometry = geometry; this.material = material; } },
    Color: class { constructor(hex) { this.hex = hex; } },
    Vector3: Vec, Vector2: Vec,
    PerspectiveCamera: class {
      constructor() {
        this.position = new Vec(0, 0, 0);
        this.up = new Vec(0, 1, 0);
        this.matrixWorld = { elements: identity };
      }
      lookAt() {}
      updateMatrixWorld() {}
    },
    AdditiveBlending: 2, CustomBlending: 5, AddEquation: 100, ZeroFactor: 200, SrcColorFactor: 202, DynamicDrawUsage: 35048,
  };
}

function fakeStage() {
  const stage = {
    tickers: [], frames: [], width: 800, height: 600,
    scene: { background: { isColor: true, r: 1, g: 1, b: 1 }, add() {}, remove() {} },
    camera: { matrixWorld: { elements: identity } },
    renderer: {
      getContext: () => ({ ALIASED_POINT_SIZE_RANGE: 1, getParameter: () => [1, 1024] }),
      getPixelRatio: () => 1,
      domElement: { getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600 }) },
    },
    rig: {
      pose: { target: [0, 0, 0], yaw: -2.45, pitch: 0.64, radius: 65 },
      poses: [],
      animateTo(p) { stage.rig.poses.push(p); return Promise.resolve(); },
      setPose(p) { stage.rig.poses.push(p); },
      reset() { stage.rig.poses.push('reset'); },
      setGuided() {},
    },
    addTicker(f) { stage.tickers.push(f); return () => {}; },
    onFrame(f) { stage.frames.push(f); },
    invalidate() {},
    pixelScale: () => 500,
    viewProjection: () => identity,
  };
  return stage;
}

// A small reference: ten RNA cells per class, spread out.
function fakeReference() {
  const per = 10;
  const n = order.length * per;
  const positions = new Float32Array(n * 3);
  const codes = new Uint8Array(n);
  for (let i = 0; i < n; i += 1) {
    codes[i] = Math.floor(i / per);
    positions.set([(codes[i] - 11) * 3, (i % per) - 5, 0], i * 3);
  }
  return { order, frame: { centre: [0, 0, 0], scale: 50 }, n, nRna: n, positions, codes };
}

function setup({ client = null } = {}) {
  const els = installDocument();
  const stage = fakeStage();
  const dims = [];
  const opened = [];
  const landing = createLanding({
    THREE: fakeThree(), stage, ref: fakeReference(),
    reference: { setDim: (v) => dims.push(v) },
    drawer: { open: (title, html) => opened.push({ title, html }), close() {}, body() {} },
    client: client ?? { project: async () => { throw new Error('no service'); } },
    serviceUrl: () => 'https://service.example',
    options: () => ({ modality: 'prot', restrict: false }),
    limits: () => ({ max_cells: 2000, max_upload_mb: 200, min_cells: 20 }),
  });
  const tick = (seconds) => {
    for (let t = 0; t < seconds; t += 1 / 30) stage.tickers.forEach((f) => f(1 / 30, t));
  };
  return { els, stage, landing, tick, dims, opened };
}

const settleMicrotasks = () => new Promise((done) => setTimeout(done, 0));

// The traced cells as the service's own response, for the fake service.
function responseFromTrace() {
  return {
    atlas_version: workflow.built_for.atlas_version, pipeline_version: 'v4.1', model_version: 'v4.1',
    n_cells: workflow.trace.cells.length, n_features_matched: 2996, n_features_unmatched: 91,
    best_guess_rule: { correlation_term: 'flat', agreement: 0.37, agreement_threshold: 0.4 },
    cells: workflow.trace.cells.map((c) => {
      const answered = ['class', 'group', 'lineage'].includes(c.outcome);
      return {
        cell_id: c.id, coordinates: c.xyz, observed_genes: c.observed, reference_similarity: c.similarity,
        label: answered ? c.label : null, label_level: answered ? c.level : null,
        label_set: (c.set ?? []).map((k) => order[k]), confidence: c.confidence, abstained: !answered,
        abstain_reason: answered ? undefined : c.outcome,
        best_guess: c.guess === null ? undefined : { label: order[c.guess], probability: c.guess_probability },
      };
    }),
  };
}

// ---- the flows ----

test('the recorded example plays from idle to the settled view', async () => {
  const { els, landing, tick, dims, opened, stage } = setup();
  const seen = [];
  landing.onChange((st) => { if (seen.at(-1) !== st.name) seen.push(st.name); });
  await landing.watchExample();
  await settleMicrotasks();
  assert.equal(landing.state.name, 'working');
  assert.match(els.get('status-card').innerHTML, /Illustration/);
  assert.match(els.get('status-card').innerHTML, /not its progress/);
  tick(30);
  assert.equal(landing.state.name, 'interactive', seen.join(' > '));
  for (const s of ['working', 'finishing', 'receipt', 'flying', 'settling', 'interactive']) assert.ok(seen.includes(s), s);
  const run = landing.run;
  assert.equal(run.source, 'recorded');
  assert.equal(run.cells.length, workflow.trace.cells.length);
  assert.deepEqual(outcomeCounts(run.cells), workflow.trace.outcomes);
  assert.ok(run.schedule.flies.reduce((a, b) => a + b, 0) > 0, 'cells fly');
  assert.ok(Math.max(...dims) > 0.5, 'the reference dims');
  assert.ok(opened.length >= 1, 'the results open');
  assert.match(els.get('status-card').innerHTML, /dl|Cells|cells/);
  assert.equal(els.get('legend-card').hidden, false);
  assert.equal(els.get('skip').hidden, true);
  assert.equal(els.get('replay-view').hidden, false);
  assert.ok(stage.rig.poses.length >= 2, 'the camera was guided');
  assert.match(landing.chips(), /data-outcome/);
  landing.select(0);
  assert.match(opened.at(-1).html, /Back to all answers/);
  landing.clear();
  assert.equal(landing.state.name, 'idle');
  assert.equal(landing.run, null);
});

test('skip jumps to the settled view from the middle of the landing', async () => {
  const { landing, tick } = setup();
  await landing.watchExample();
  await settleMicrotasks();
  tick(7);
  assert.ok(['finishing', 'receipt', 'flying'].includes(landing.state.name), landing.state.name);
  landing.skip();
  assert.equal(landing.state.name, 'interactive');
  landing.replay();
  assert.equal(landing.state.name, 'receipt');
  tick(12);
  assert.equal(landing.state.name, 'interactive');
});

test('a file is checked, sent, waited on and landed', async () => {
  const response = responseFromTrace();
  let sent = null;
  const client = {
    async project(url, form, { onUpload }) {
      sent = { url, modality: form.get('modality'), restrict: form.get('restrict_to_supported_classes') };
      onUpload(0.5);
      onUpload(1);
      await settleMicrotasks();
      return response;
    },
  };
  const { els, landing, tick } = setup({ client });
  const bytes = readFileSync(new URL('../data/examples/pbmc240_proteins_raw.tsv', import.meta.url));
  const check = await landing.chooseFile(new File([bytes], 'pbmc240_proteins_raw.tsv'));
  assert.equal(landing.state.name, 'chosen');
  assert.equal(check.ok, true);
  assert.equal(check.cells, 238);
  landing.send();
  // The fake service reports its whole upload at once, so the page is
  // already waiting.
  assert.ok(['sending', 'working'].includes(landing.state.name), landing.state.name);
  await settleMicrotasks();
  await settleMicrotasks();
  assert.ok(['working', 'finishing'].includes(landing.state.name), landing.state.name);
  assert.deepEqual(sent, { url: 'https://service.example', modality: 'prot', restrict: 'false' });
  tick(15);
  assert.equal(landing.state.name, 'interactive');
  assert.equal(landing.run.source, 'service');
  assert.equal(landing.run.placeable, true);
  assert.match(els.get('status-card').innerHTML, /2,996|2996/);
});

test('a service on another map lists cells without placing them', async () => {
  const response = { ...responseFromTrace(), pipeline_version: 'v5.2' };
  const client = { async project(url, form, { onUpload }) { onUpload(1); return response; } };
  const { els, landing, tick } = setup({ client });
  const bytes = readFileSync(new URL('../data/examples/pbmc240_proteins_raw.tsv', import.meta.url));
  await landing.chooseFile(new File([bytes], 'x.tsv'));
  landing.send();
  await settleMicrotasks();
  tick(15);
  assert.equal(landing.state.name, 'interactive');
  assert.equal(landing.run.placeable, false);
  assert.equal(landing.run.schedule.flies.reduce((a, b) => a + b, 0), 0, 'nothing flies');
  assert.match(els.get('legend-card').innerHTML, /listed, not placed/);
});

test('a busy service counts down, and an unreachable one says so', async () => {
  const busy = { async project() { throw new ServiceError('busy', 'Another file is being labelled.', { status: 503, retryAfter: 30 }); } };
  const a = setup({ client: busy });
  const bytes = readFileSync(new URL('../data/examples/pbmc240_proteins_raw.tsv', import.meta.url));
  await a.landing.chooseFile(new File([bytes], 'x.tsv'));
  a.landing.send();
  await settleMicrotasks();
  assert.equal(a.landing.state.name, 'busy');
  assert.match(a.els.get('status-card').innerHTML, /Trying again in/);
  a.landing.cancel();
  assert.equal(a.landing.state.name, 'chosen');

  const down = { async project() { throw new ServiceError('network', 'No answer.'); } };
  const b = setup({ client: down });
  await b.landing.chooseFile(new File([bytes], 'x.tsv'));
  b.landing.send();
  await settleMicrotasks();
  assert.equal(b.landing.state.name, 'failed');
  assert.match(b.els.get('status-card').innerHTML, /service\.example/);
  assert.match(b.els.get('status-card').innerHTML, /Try again/);
});

test('a file the service would refuse is stopped in the browser', async () => {
  const { landing } = setup();
  const check = await landing.chooseFile(new File(['gene,a,b\nCD3E,1,2\n'], 'tiny.csv'));
  assert.equal(check.ok, false, 'two cells is under the minimum');
  assert.ok(check.problems.length >= 1);
  landing.send();
  assert.equal(landing.state.name, 'chosen', 'not sent');
});
