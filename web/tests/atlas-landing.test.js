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
  querySelector() { return null; }
}

function installDocument() {
  const els = new Map();
  globalThis.document = {
    getElementById: (id) => {
      if (!els.has(id)) els.set(id, new El(id));
      return els.get(id);
    },
    listeners: {},
    addEventListener(type, f) { (globalThis.document.listeners[type] ??= []).push(f); },
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
    tickers: [], frames: [], added: [], width: 800, height: 600,
    scene: { background: { isColor: true, r: 1, g: 1, b: 1 }, add(o) { stage.added.push(o); }, remove() {} },
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
      listeners: {},
      on(name, f) { (stage.rig.listeners[name] ??= []).push(f); },
      // What the real rig does when the visitor drags during a guided move.
      takeover() { (stage.rig.listeners.takeover ?? []).forEach((f) => f()); },
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

// Play does not start on its own here, unless a test asks (autoPlay).
function setup({ client = null, autoPlay = false, limits = () => ({ max_cells: 2000, max_upload_mb: 200, min_cells: 20 }) } = {}) {
  const els = installDocument();
  const stage = fakeStage();
  const dims = [];
  const focus = [];
  const opened = [];
  const landing = createLanding({
    THREE: fakeThree(), stage, ref: fakeReference(),
    reference: { setDim: (v) => dims.push(v), setFocusSet: (set) => focus.push(set ? [...set] : null) },
    drawer: { open: (title, html) => opened.push({ title, html }), close() {}, body() {} },
    client: client ?? { project: async () => { throw new Error('no service'); } },
    serviceUrl: () => 'https://service.example',
    options: () => ({ modality: 'prot', restrict: false }),
    limits,
    autoPlay,
  });
  const tick = (seconds) => {
    for (let t = 0; t < seconds; t += 1 / 30) stage.tickers.forEach((f) => f(1 / 30, t));
  };
  return { els, stage, landing, tick, dims, focus, opened };
}

const settleMicrotasks = () => new Promise((done) => setTimeout(done, 0));

// The uploaded cells' uniforms, as the GPU would see them.
const uploadUniforms = (stage) => stage.added.find((o) => o.material?.uniforms?.uTime).material.uniforms;

// A file of n cells that passes the browser's check.
function fileOf(n, name = `cells${n}.csv`) {
  const ids = Array.from({ length: n }, (_, i) => `c${i}`);
  const row = (gene) => `${gene},${ids.map(() => '1').join(',')}`;
  return new File([`gene,${ids.join(',')}\n${['CD3E', 'CD19', 'CD14'].map(row).join('\n')}\n`], name);
}

// Ticks in small steps until the landing reaches the named state.
function tickUntil(landing, tick, name, seconds = 30) {
  for (let t = 0; t < seconds && landing.state.name !== name; t += 0.1) tick(0.1);
  assert.equal(landing.state.name, name);
}

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
  assert.match(opened.at(-1).html, /Back to all cells/);
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

test('a new file chosen over an answer replaces it, and the next answer starts fresh', async () => {
  const { landing, tick, stage } = setup();
  await landing.watchExample();
  tick(30);
  assert.equal(landing.state.name, 'interactive');
  landing.setOutcomeOn('lineage', false);
  landing.select(3);
  const benches = stage.rig.poses.length;
  // More cells than the example: the old answer must not be read for them.
  const check = await landing.chooseFile(fileOf(300));
  assert.equal(check.ok, true);
  assert.equal(landing.state.name, 'chosen');
  assert.equal(landing.run, null, 'the old answer is gone');
  assert.equal(landing.pick(400, 300), -1);
  assert.equal(landing.describe(250), '');
  assert.ok(stage.rig.poses.length > benches, 'the camera takes the bench again');
  await landing.watchExample();
  tick(30);
  assert.equal(landing.state.name, 'interactive');
  const u = uploadUniforms(stage);
  assert.ok(u.uOutcomeOn.value.every((v) => v === 1), 'every outcome shown again');
  assert.equal(u.uSelected.value, -1, 'no cell selected');
});

test('replay waits for the landing to end, and starts its sheet unanswered', async () => {
  const { landing, tick, stage } = setup();
  await landing.watchExample();
  tickUntil(landing, tick, 'flying');
  const poses = stage.rig.poses.length;
  landing.replay();
  assert.equal(landing.state.name, 'flying', 'not replayed mid-landing');
  assert.equal(stage.rig.poses.length, poses, 'the camera was left alone');
  tick(30);
  landing.replay();
  assert.equal(landing.state.name, 'receipt');
  assert.equal(uploadUniforms(stage).uTime.value, 0, 'the clock starts again, so the sheet shows no answers yet');
});

test('a drag during the landing keeps the camera where the visitor put it', async () => {
  const { landing, tick, stage } = setup();
  await landing.watchExample();
  tickUntil(landing, tick, 'flying');
  stage.rig.takeover();
  const poses = stage.rig.poses.length;
  tick(30);
  assert.equal(landing.state.name, 'interactive');
  assert.equal(stage.rig.poses.length, poses, 'no glide and no jump to the settled pose');
  // A replay is guided again.
  landing.replay();
  tick(30);
  assert.ok(stage.rig.poses.length > poses + 1);
});

test('the receipt is open while the landing plays and folds after; the drawer holds the answer', async () => {
  const response = responseFromTrace();
  const client = { async project(url, form, { onUpload }) { onUpload(1); return response; } };
  const { els, landing, tick, opened } = setup({ client });
  await landing.chooseFile(fileOf(40));
  landing.send();
  await settleMicrotasks();
  tickUntil(landing, tick, 'receipt');
  assert.match(els.get('status-card').innerHTML, /<details class="fold atlas-receipt-card" open><summary>Your file · 238 cells · v4\.1</);
  assert.match(els.get('legend-card').innerHTML, /<details class="fold atlas-key-card"><summary>/, 'the key starts folded');
  tick(30);
  assert.equal(landing.state.name, 'interactive');
  assert.match(els.get('status-card').innerHTML, /<details class="fold atlas-receipt-card"><summary>/, 'folded once the map is yours');
  const results = opened.at(-1).html;
  for (const title of ['About this answer', 'Your cells (238)']) assert.ok(results.includes(`<summary>${title}</summary>`), title);
  assert.match(results, /<details class="fold drawer-section" open><summary>Your cells/, 'the cells are open');
  assert.match(results, /data-action="download"/);
  // Clear, from the drawer.
  const clear = { target: { closest: (sel) => (sel === '[data-action]' ? { dataset: { action: 'clear' } } : null) } };
  els.get('drawer-body').listeners.click.forEach((f) => f(clear));
  assert.equal(landing.state.name, 'idle');
  assert.equal(landing.run, null);
});

test('the visitor can hide their cells; a new file shows them again', async () => {
  const { landing, tick, stage } = setup();
  const seen = [];
  landing.onChange((st) => seen.push(st.name));
  await landing.watchExample();
  tick(30);
  assert.equal(landing.state.name, 'interactive');
  // The cells themselves (the glow, under them, is drawn first; the ripples over them).
  const cells = () => stage.added.find((o) => o.material?.uniforms?.uTime && o.renderOrder === 2);
  assert.equal(cells().visible, true);
  const before = seen.length;
  landing.setCellsShown(false);
  assert.equal(landing.cellsShown, false);
  assert.equal(cells().visible, false);
  assert.equal(landing.pick(400, 300), -1, 'hidden cells cannot be picked');
  assert.ok(seen.length > before, 'the controls hear it');
  await landing.chooseFile(fileOf(40));
  assert.equal(landing.cellsShown, true, 'a new file is shown');
  assert.equal(cells().visible, true);
});

// ---- the cells, one by one ----

async function settledExample() {
  const ctx = setup();
  await ctx.landing.watchExample();
  ctx.tick(30);
  assert.equal(ctx.landing.state.name, 'interactive');
  return ctx;
}
const stepText = (els) => els.get('step-text').textContent;

test('the drawer lists every cell, grouped by the answer it was given', async () => {
  const { landing, opened } = await settledExample();
  const html = opened.at(-1).html;
  assert.match(html, /class="cell-browser"/);
  assert.equal((html.match(/class="browse-row/g) ?? []).length, workflow.trace.cells.length, 'every cell, none capped');
  const groups = landing.groups();
  assert.equal(groups.reduce((sum, g) => sum + g.count, 0), workflow.trace.cells.length);
  for (const g of groups) assert.ok(html.includes(`data-group="${g.key}"`), g.key);
  assert.ok(!html.includes('<th>Label set</th>'), 'the capped table is gone');
});

test('the step bar walks the shown cells in the browser’s order, and wraps', async () => {
  const { els, landing, opened } = await settledExample();
  const n = workflow.trace.cells.length;
  assert.equal(els.get('step-bar').hidden, false);
  assert.equal(stepText(els), `${n} cells shown: step through them`);
  els.get('step-next').listeners.click.forEach((f) => f());
  const first = landing.current;
  assert.ok(first >= 0);
  assert.match(stepText(els), new RegExp(`^1 of ${n} · `));
  assert.match(opened.at(-1).html, new RegExp(`1 of ${n}`), 'the card says where it is');
  assert.match(opened.at(-1).html, /data-step="1"/);
  landing.step(-1);
  assert.match(stepText(els), new RegExp(`^${n} of ${n} · `), 'back from the first wraps to the last');
  landing.step(1);
  assert.equal(landing.current, first);
  // The card's own Previous and Next.
  const next = { target: { closest: (sel) => (sel === '[data-step]' ? { dataset: { step: '1' } } : null) } };
  els.get('drawer-body').listeners.click.forEach((f) => f(next));
  assert.match(stepText(els), new RegExp(`^2 of ${n} · `));
});

test('Play steps on its own until the last shown cell, and Pause stops it', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { els, landing } = await settledExample();
  const only = landing.groups().find((g) => g.count >= 3);
  landing.showOnlyGroup(only.key);
  landing.play(true);
  assert.equal(landing.playing, true);
  assert.match(stepText(els), new RegExp(`^1 of ${only.count} · `));
  assert.equal(els.get('step-play').textContent, 'Pause');
  t.mock.timers.tick(2500);
  assert.match(stepText(els), new RegExp(`^2 of ${only.count} · `));
  // One step at a time: each step sets the next one's timer.
  for (let k = 0; k < only.count + 2; k += 1) t.mock.timers.tick(2500);
  assert.equal(landing.playing, false, 'it stops at the end');
  assert.match(stepText(els), new RegExp(`^${only.count} of ${only.count} · `));
  landing.play(true);
  landing.play(false);
  assert.equal(els.get('step-play').textContent, 'Play');
});

test('the types given filter the map, the browser and the steps', async () => {
  const { els, landing, stage } = await settledExample();
  const n = workflow.trace.cells.length;
  const [first, second] = landing.groups();
  landing.setGroupOn(first.key, false);
  assert.equal(landing.groups()[0].on, false);
  assert.equal(stepText(els), `${n - first.count} cells shown: step through them`);
  const cells = stage.added.find((o) => o.material?.uniforms?.uTime && o.renderOrder === 2);
  const shown = Object.values(cells.geometry.attributes).find((a) => a.itemSize === 1 && a.array.length === n && a.array.some((v) => v === 0));
  assert.ok(shown, 'a per-cell mask reaches the GPU');
  landing.showOnlyGroup(second.key);
  assert.equal(stepText(els), `${second.count} cells shown: step through them`);
  landing.step(1);
  assert.ok(second.cells.includes(landing.current), 'only that type is stepped through');
  // Hiding the selected cell's type lets go of it.
  landing.setGroupOn(second.key, false);
  assert.equal(landing.current, -1);
  landing.setAllGroups(true);
  assert.equal(stepText(els), `${n} cells shown: step through them`);
});

test('a selected cell’s possible types are highlighted on the reference', async () => {
  const { landing, focus } = await settledExample();
  const i = landing.run.cells.findIndex((c) => c.set.length >= 2);
  landing.select(i);
  assert.deepEqual(focus.at(-1), landing.run.cells[i].set);
  landing.setHighlight(false);
  assert.equal(focus.at(-1), null, 'switched off');
  landing.setHighlight(true);
  assert.deepEqual(focus.at(-1), landing.run.cells[i].set);
  landing.deselect();
  assert.equal(focus.at(-1), null, 'let go');
  assert.equal(landing.current, -1);
});

test('the arrow keys step, except while typing', async () => {
  const { landing } = await settledExample();
  const keys = globalThis.document.listeners.keydown;
  const press = (key, typing = false) => keys.forEach((f) => f({
    key, target: { closest: () => (typing ? {} : null) }, preventDefault() {}, stopImmediatePropagation() {},
  }));
  press('ArrowRight');
  const first = landing.current;
  assert.ok(first >= 0);
  press('ArrowRight', true);
  assert.equal(landing.current, first, 'not while typing in the search box');
  press('ArrowLeft');
  assert.notEqual(landing.current, first);
  // on the panel's tabs the arrows change the tab only
  const at = landing.current;
  keys.forEach((f) => f({ key: 'ArrowRight', target: { closest: (sel) => (sel.includes('[role="tablist"]') ? {} : null) },
    preventDefault() {}, stopImmediatePropagation() {} }));
  assert.equal(landing.current, at, 'not while on the tabs');
});

test('the file waits as a breathing cloud and settles as its cells land', async () => {
  const { landing, tick, stage } = setup();
  await landing.watchExample();
  const u = uploadUniforms(stage);
  tick(1);
  assert.equal(u.uBreath.value, 1, 'breathing while it waits');
  assert.equal(u.uPulse.value, 0);
  tick(30);
  assert.equal(landing.state.name, 'interactive');
  assert.equal(u.uBreath.value, 0, 'still once landed');
  assert.equal(u.uPulse.value, 1, 'the beads pulse');
  landing.clear();
  assert.equal(u.uPulse.value, 0);
});

test('once the cells land, the camera goes to the first cell and Play starts', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { landing, tick, stage, els } = setup({ autoPlay: true });
  await landing.watchExample();
  tick(30);
  assert.equal(landing.state.name, 'interactive');
  assert.equal(landing.playing, true);
  assert.ok(landing.current >= 0);
  assert.match(els.get('step-text').textContent, /^1 of /);
  assert.equal(stage.rig.poses.at(-1).radius, 18, 'zoomed in on the cell');
  t.mock.timers.tick(2500);
  assert.match(els.get('step-text').textContent, /^2 of /);
  landing.play(false);
});

test('Play does not start on its own after the visitor took the camera', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { landing, tick, stage } = setup({ autoPlay: true });
  await landing.watchExample();
  tickUntil(landing, tick, 'flying');
  stage.rig.takeover();
  tick(30);
  assert.equal(landing.state.name, 'interactive');
  assert.equal(landing.playing, false);
  assert.equal(landing.current, -1);
});

test('a failed load of the example can be tried again', async () => {
  const { els, landing, tick } = setup();
  const real = globalThis.fetch;
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await landing.watchExample();
  assert.equal(landing.state.name, 'failed');
  assert.match(els.get('status-card').innerHTML, /Try again/);
  globalThis.fetch = real;
  const retry = { target: { closest: (sel) => (sel === '[data-retry]' ? {} : null) } };
  els.get('status-card').listeners.click.forEach((f) => f(retry));
  await settleMicrotasks();
  assert.equal(landing.state.name, 'working');
  tick(30);
  assert.equal(landing.state.name, 'interactive');
});

test('a service still busy after the last try says so', async () => {
  let tries = 0;
  const busy = { async project() { tries += 1; throw new ServiceError('busy', 'Busy.', { status: 503, retryAfter: 0 }); } };
  const { els, landing } = setup({ client: busy });
  await landing.chooseFile(fileOf(40));
  landing.send();
  for (let k = 0; k < 10 && landing.state.name !== 'failed'; k += 1) await settleMicrotasks();
  assert.equal(landing.state.name, 'failed');
  assert.equal(tries, 3);
  assert.match(els.get('status-card').innerHTML, /still busy after 3 tries/);
  assert.doesNotMatch(els.get('status-card').innerHTML, /Something went wrong/);
});

test('a check of a file no longer chosen is ignored', async () => {
  const { landing } = setup();
  const first = landing.chooseFile(fileOf(40, 'mine.csv'));
  const second = landing.chooseFile(fileOf(60, 'other.csv'));
  assert.equal(await second, null);
  const check = await first;
  assert.equal(landing.state.name, 'chosen');
  assert.equal(landing.state.file.name, 'mine.csv');
  assert.equal(check.cells, 40);
  assert.equal(landing.state.check.cells, 40);
});

test('a file the service would refuse is stopped in the browser', async () => {
  const { landing } = setup();
  const check = await landing.chooseFile(new File(['gene,a,b\nCD3E,1,2\n'], 'tiny.csv'));
  assert.equal(check.ok, false, 'two cells is under the minimum');
  assert.ok(check.problems.length >= 1);
  landing.send();
  assert.equal(landing.state.name, 'chosen', 'not sent');
});

test('a file checked before the limits arrived is judged again when they do', async () => {
  let current = {};
  const { landing } = setup({ limits: () => current });
  await landing.chooseFile(fileOf(5));
  assert.equal(landing.state.check.ok, true, 'no limits known yet');
  current = { max_cells: 2000, max_upload_mb: 200, min_cells: 20 };
  landing.recheckLimits();
  assert.equal(landing.state.name, 'chosen');
  assert.equal(landing.state.check.ok, false);
  assert.match(landing.state.check.problems.join(' '), /at least 20/);
});

test('the example file does not replace a file the visitor chose while it loaded', async () => {
  const sent = [];
  const { landing } = setup({ client: { project: async (url, form) => { sent.push(form.get('matrix').name); throw new Error('stop'); } } });
  const real = globalThis.fetch;
  let release;
  globalThis.fetch = (url) => (String(url).endsWith('pbmc240_proteins_raw.tsv')
    ? new Promise((done) => { release = () => real(url).then(done); })
    : real(url));
  const example = landing.sendExample();
  await settleMicrotasks();
  await landing.chooseFile(fileOf(40, 'mine.csv'));
  release();
  await example;
  globalThis.fetch = real;
  assert.equal(landing.state.file.name, 'mine.csv');
  assert.deepEqual(sent, []);
});

test('the example is still sent when only the service limits arrive while it loads', async () => {
  const sent = [];
  const { landing } = setup({ client: { project: async (url, form) => { sent.push(form.get('matrix').name); throw new Error('stop'); } },
    limits: () => ({}) });
  await landing.chooseFile(fileOf(40, 'mine.csv'));
  assert.equal(landing.state.name, 'chosen');
  const real = globalThis.fetch;
  let release;
  globalThis.fetch = (url) => (String(url).endsWith('pbmc240_proteins_raw.tsv')
    ? new Promise((done) => { release = () => real(url).then(done); })
    : real(url));
  const example = landing.sendExample();
  await settleMicrotasks();
  landing.recheckLimits(); // the status check answered: same limits, same verdict
  release();
  await example;
  globalThis.fetch = real;
  assert.deepEqual(sent, ['pbmc240_proteins_raw.tsv']);
});

test('an example file that cannot load says so', async () => {
  const { landing } = setup();
  const real = globalThis.fetch;
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await landing.sendExample();
  globalThis.fetch = real;
  assert.equal(landing.state.name, 'failed');
  assert.match(String(landing.state.error?.message), /example file could not be loaded/);
});

test('a file the service turned down is not offered again as it is', async () => {
  const refusal = Object.assign(new Error('upload has 4 cells; at least 20 are required'), { kind: 'refused', status: 400 });
  const { els, landing } = setup({ client: { project: async () => { throw refusal; } }, limits: () => ({}) });
  await landing.chooseFile(fileOf(25));
  landing.send();
  for (let i = 0; i < 20 && landing.state.name !== 'failed'; i += 1) await settleMicrotasks();
  assert.equal(landing.state.name, 'failed');
  assert.match(els.get('status-card').innerHTML, /turned the file down/);
  assert.doesNotMatch(els.get('status-card').innerHTML, /Try again/);
  assert.match(els.get('status-line').textContent, /turned the file down/, 'the failure is announced once');
});

test('after cancelling a file the service was working on, a busy answer names that file', async () => {
  let calls = 0;
  const client = {
    project: async (url, form, { signal, onUpload }) => {
      calls += 1;
      if (calls === 1) {
        onUpload(1);
        return new Promise((_, reject) => signal.addEventListener('abort', () => reject(Object.assign(new Error('cancelled'), { kind: 'cancelled' }))));
      }
      throw Object.assign(new Error('busy'), { kind: 'busy', retryAfter: 30 });
    },
  };
  const { els, landing } = setup({ client, limits: () => ({}) });
  await landing.chooseFile(fileOf(25));
  landing.send();
  for (let i = 0; i < 50 && landing.state.name !== 'working'; i += 1) await settleMicrotasks();
  assert.equal(landing.state.name, 'working');
  landing.cancel();
  for (let i = 0; i < 50 && landing.state.name !== 'chosen'; i += 1) await settleMicrotasks();
  landing.send();
  for (let i = 0; i < 50 && landing.state.name !== 'busy'; i += 1) await settleMicrotasks();
  assert.equal(landing.state.name, 'busy');
  assert.match(els.get('status-card').innerHTML, /still finishing the file you cancelled/);
  landing.cancel();
});

test('once the service has answered again, a busy answer no longer blames the cancelled file', async () => {
  let calls = 0;
  const client = {
    project: async (url, form, { signal, onUpload }) => {
      calls += 1;
      if (calls === 1) {
        onUpload(1);
        return new Promise((_, reject) => signal.addEventListener('abort', () => reject(Object.assign(new Error('cancelled'), { kind: 'cancelled' }))));
      }
      if (calls === 2) throw Object.assign(new Error('the file has text where a number belongs'), { kind: 'refused', status: 400 });
      throw Object.assign(new Error('busy'), { kind: 'busy', status: 503, retryAfter: 30 });
    },
  };
  const { els, landing } = setup({ client, limits: () => ({}) });
  await landing.chooseFile(fileOf(25));
  landing.send();
  for (let i = 0; i < 50 && landing.state.name !== 'working'; i += 1) await settleMicrotasks();
  landing.cancel();
  for (let i = 0; i < 50 && landing.state.name !== 'chosen'; i += 1) await settleMicrotasks();
  landing.send();
  for (let i = 0; i < 50 && landing.state.name !== 'failed'; i += 1) await settleMicrotasks();
  assert.equal(landing.state.name, 'failed', 'the service turned the second file down: its slot was free');
  await landing.chooseFile(fileOf(30, 'third.csv'));
  landing.send();
  for (let i = 0; i < 50 && landing.state.name !== 'busy'; i += 1) await settleMicrotasks();
  assert.equal(landing.state.name, 'busy');
  assert.doesNotMatch(els.get('status-card').innerHTML, /file you cancelled/);
  assert.match(els.get('status-card').innerHTML, /Another file is being labelled/);
  landing.cancel();
});
