// The landing: a visitor's file, or the recorded PBMC240 example, from a
// sheet beside the atlas to its cells' places on the map (docs/web/atlas.md).
// It runs the page's state machine (director.js) on the stage's clock:
//
//   file chosen  the file is checked in the browser and laid out as a sheet
//                of dots, one per cell, beside the atlas
//   sending      real upload progress
//   working      the service sends no progress, so an animated ILLUSTRATION
//                of its six steps loops, labelled as one, with a clock
//   receipt      the answer's own numbers
//   flying       cells arc from the sheet onto their coordinates, by answer
//                level, while the camera glides to frame them
//   settling     the reference dims, the results open, the camera settles
//   interactive  the visitor's camera; click a cell for its card
//
// Every number shown comes from the service's response or the recorded
// example (web/data/workflow.json); the browser computes no model output.

import { buildProjectionCells, buildProjectionLabels, buildProjectionSummary, errorPanel, escapeHtml } from '../panels.js';
import { SERVICE_STEPS, SERVICE_STEP_CHAPTERS, SERVICE_STEP_NOTES, answerShort } from '../workflow-data.js';
import {
  answerStyle, coordinatesCompatible, outcomeCode, outcomeCounts, receiptFromResponse, receiptFromWorkflow,
  responseToCells, traceToCells,
} from './answers.js';
import { buildAnswerKey, buildAtlasCellCard, buildExampleSummary, buildOutcomeChips, buildReceipt } from './atlas-panels.js';
import { TIMING, finishWaiting, flightSchedule, framePose, landingTimeline, reducedTiming, waitingFrame } from './choreography.js';
import { GUIDED, MAX_ATTEMPTS, initialState, transition } from './director.js';
import { checkFile, checkLimits } from './file-check.js';
import { createIllustration } from './illustration.js';
import { toScene } from './reference-data.js';
import { boundingSphere, buildGrid, fileGridLayout, nearestOfClasses, orbitPosition, pickScreen, projectAll } from './spatial.js';
import { explainFailure } from './service-client.js';
import { createUploadLayer, sheetRadiusFor } from './upload-layer.js';

const $ = (id) => document.getElementById(id);
const clockText = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

// Where the file's sheet sits: beside the atlas, facing the camera.
const BENCH = { pitch: 0.25, radius: 105, shift: 24, sheetAt: 62, sheetWidth: 30, sheetAspect: 1.6 };
const NEIGHBOURS = { k: 6, maxR: 12, cell: 3 };

export function createLanding({ THREE, stage, ref, reference, drawer, client, serviceUrl, options, limits, reduced = false }) {
  const T = reduced ? reducedTiming() : TIMING;
  const upload = createUploadLayer(THREE, stage);
  const illustration = createIllustration(THREE, stage);
  const listeners = [];
  let st = initialState();
  let phase = 0;            // seconds in the current state
  let waited = 0;           // seconds of the waiting illustration
  let stepSeconds = T.step;
  let finishSeconds = 0;
  let abort = null;
  let busyTimer = null;
  let uploaded = 0;
  let sheet = null;         // { bench, anchor, n }
  let run = null;           // the results being shown
  let workflow = null;      // the recorded example, loaded on demand
  let grid = null;          // RNA reference cells, for the neighbour glow
  let lastStatus = '';
  let clock = 0;            // the flight clock the upload layer shows
  let userCam = false;      // the visitor took the camera during this landing

  // A drag or the wheel during the guided landing hands the camera back: the
  // landing goes on, but no longer moves it.
  stage.rig.on('takeover', () => {
    if (GUIDED.has(st.name)) userCam = true;
  });
  function guide() {
    userCam = false;
    stage.rig.setGuided(true);
  }

  function setClock(t) {
    clock = t;
    upload.setClock(t);
  }

  // Every load sizes the cells to fit the file's sheet; they grow to full
  // size in flight.
  function loadUpload(model) {
    upload.load(model);
    upload.setSheetRadius(sheetRadiusFor(model.n, BENCH.sheetWidth, BENCH.sheetAspect));
  }

  // ---- geometry ----

  function axesOf(pose) {
    const cam = new THREE.PerspectiveCamera();
    const p = orbitPosition(pose);
    cam.position.set(p[0], p[1], p[2]);
    cam.up.set(0, -1, 0);
    cam.lookAt(pose.target[0], pose.target[1], pose.target[2]);
    cam.updateMatrixWorld();
    const e = cam.matrixWorld.elements;
    return { right: [e[0], e[1], e[2]], up: [e[4], e[5], e[6]] };
  }

  function benchFor() {
    const base = { target: [0, 0, 0], yaw: stage.rig.pose.yaw, pitch: BENCH.pitch, radius: BENCH.radius };
    const { right, up } = axesOf(base);
    return {
      bench: { ...base, target: right.map((v) => v * BENCH.shift) },
      anchor: {
        centre: right.map((v) => v * BENCH.sheetAt), right, up,
        width: BENCH.sheetWidth, height: BENCH.sheetWidth / BENCH.sheetAspect,
      },
    };
  }

  function sheetPositions(n, anchor) {
    const { slots } = fileGridLayout(n, BENCH.sheetAspect);
    const out = new Float32Array(n * 3);
    for (let i = 0; i < n; i += 1) {
      const u = slots[i * 2] - 0.5;
      const v = 0.5 - slots[i * 2 + 1];
      for (let k = 0; k < 3; k += 1) {
        out[i * 3 + k] = anchor.centre[k] + anchor.right[k] * u * anchor.width + anchor.up[k] * v * anchor.height;
      }
    }
    return out;
  }

  // A sheet of waiting dots: the file, before its answers.
  function showSheet(n) {
    if (!sheet) {
      sheet = benchFor();
      stage.rig.setGuided(true);
      stage.rig.animateTo(sheet.bench, T.bench).then(() => stage.rig.setGuided(false));
    }
    sheet.n = Math.max(1, Math.min(n, 2000));
    const start = sheetPositions(sheet.n, sheet.anchor);
    loadUpload({
      n: sheet.n, start, end: start, delay: new Float32Array(sheet.n), duration: new Float32Array(sheet.n).fill(1),
      style: new Float32Array(sheet.n).fill(4), fill: new Float32Array(sheet.n).fill(-1),
      outcome: new Float32Array(sheet.n), flies: new Uint8Array(sheet.n),
    });
    upload.setOpacity(1);
    setClock(0);
  }

  // The waiting illustration plays on the sheet; the file's dots fade back
  // so the two do not crowd each other.
  function startIllustration() {
    illustration.show(sheet.anchor);
    upload.setOpacity(0.25);
  }

  // ---- results ----

  function neighboursOf(cells, styles, model, schedule) {
    if (!grid) grid = buildGrid(ref.positions.subarray(0, ref.nRna * 3), ref.nRna, NEIGHBOURS.cell);
    const position = [];
    const cls = [];
    const owner = [];
    const at = [];
    cells.forEach((c, i) => {
      if (!schedule.flies[i]) return;
      const types = new Set(c.outcome === 'class' ? [styles[i].fill] : (c.outcome === 'group' || c.outcome === 'lineage') ? c.set : []);
      if (types.size === 0 || types.has(-1)) return;
      const p = [model.end[i * 3], model.end[i * 3 + 1], model.end[i * 3 + 2]];
      for (const j of nearestOfClasses(grid, p, (k) => types.has(ref.codes[k]), NEIGHBOURS.k, NEIGHBOURS.maxR)) {
        position.push(ref.positions[j * 3], ref.positions[j * 3 + 1], ref.positions[j * 3 + 2]);
        cls.push(ref.codes[j]);
        owner.push(i);
        at.push(schedule.delay[i] + schedule.duration[i]);
      }
    });
    return {
      m: owner.length, position: Float32Array.from(position), cls: Float32Array.from(cls),
      owner: Float32Array.from(owner), at: Float32Array.from(at),
    };
  }

  function buildRun(data, source) {
    const recorded = source === 'recorded';
    const cells = recorded ? traceToCells(data) : responseToCells(data, ref.order);
    const placeable = recorded || coordinatesCompatible(data?.pipeline_version);
    const n = cells.length;
    showSheet(n);
    const start = sheetPositions(n, sheet.anchor);
    const end = new Float32Array(start);
    const styles = cells.map((c) => answerStyle(c, ref.order, placeable));
    const schedule = flightSchedule(cells, { placeable, T });
    const placed = [];
    cells.forEach((c, i) => {
      if (!schedule.flies[i]) return;
      const p = toScene(ref.frame, c.xyz);
      end.set(p, i * 3);
      placed.push(...p);
    });
    const model = {
      n, start, end, delay: schedule.delay, duration: schedule.duration,
      style: Float32Array.from(styles, (s) => s.style), fill: Float32Array.from(styles, (s) => s.fill),
      outcome: Float32Array.from(cells, (c) => outcomeCode(c.outcome)), flies: schedule.flies,
    };
    const aspect = stage.width / stage.height;
    const nPlaced = placed.length / 3;
    const core = [30, 0, 0, -30, 0, 0, 0, 30, 0, 0, -30, 0, 0, 0, 30, 0, 0, -30];
    const wide = boundingSphere(Float32Array.from([...placed, ...core]), nPlaced + 6);
    const yaw = sheet.bench.yaw - 0.45;
    const fly = framePose(wide, { aspect, yaw, pitch: 0.45 });
    const settle = nPlaced ? framePose(boundingSphere(Float32Array.from(placed), nPlaced), { aspect, yaw, pitch: 0.45, margin: 1.25, minRadius: 45 }) : fly;
    return {
      source, data, cells, styles, placeable, schedule, model, poses: { fly, settle },
      timeline: landingTimeline(schedule, { T }),
      receipt: recorded ? receiptFromWorkflow(data) : receiptFromResponse(data),
      glow: neighboursOf(cells, styles, model, schedule),
      on: Object.fromEntries(Object.keys(outcomeCounts(cells)).map((k) => [k, true])),
    };
  }

  // The recorded cells as the rows the results tables read.
  function recordedRows(cells) {
    return {
      cells: cells.map((c) => ({
        cell_id: c.id, label: c.label, abstained: !['class', 'group', 'lineage'].includes(c.outcome),
        abstain_reason: ['class', 'group', 'lineage'].includes(c.outcome) ? undefined : c.outcome,
        label_set: c.set.map((k) => ref.order[k]), confidence: c.confidence, observed_genes: c.observed,
      })),
    };
  }

  function resultsHtml() {
    if (!run) return '';
    if (run.source === 'recorded') {
      // Every recorded cell is listed: the example has no response to download.
      return `${buildExampleSummary(run.data)}<h3>Cells</h3><div class="table-scroll">${buildProjectionCells(recordedRows(run.cells), run.cells.length)}</div>`;
    }
    return `${buildProjectionSummary(run.data)}<h3>Answers</h3><div class="table-scroll">${buildProjectionLabels(run.data)}</div>`
      + `<h3>Cells</h3><div class="table-scroll">${buildProjectionCells(run.data)}</div>`;
  }

  function openResults() {
    if (run) drawer.open(run.source === 'recorded' ? 'The example: answers' : 'Your file: answers', resultsHtml());
  }

  function select(i) {
    if (!run || i < 0 || i >= run.cells.length) return;
    upload.setSelected(i);
    upload.setGlowMode('selected');
    const p = run.schedule.flies[i] ? run.model.end : run.model.start;
    stage.rig.animateTo({ target: [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]], radius: 18 }, T.flyToCell);
    drawer.open('One cell', `<button type="button" class="drawer-back" data-back>Back to all answers</button>${buildAtlasCellCard(run.cells[i], ref.order, { source: run.source })}`);
  }

  // ---- the overlays ----

  function status(html) {
    const card = $('status-card');
    if (html === null) {
      card.hidden = true;
      lastStatus = '';
      return;
    }
    if (html !== lastStatus) card.innerHTML = html;
    lastStatus = html;
    card.hidden = false;
  }

  function workingHtml() {
    const frame = waitingFrame(waited, { stepSeconds });
    const example = st.example;
    const steps = reduced
      ? `<ol class="step-list">${SERVICE_STEPS.map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ol>`
      : `<h3>${escapeHtml(SERVICE_STEPS[frame.step])}</h3><p>${escapeHtml(SERVICE_STEP_NOTES[frame.step])}</p>`
        + `<a href="workflow.html#${SERVICE_STEP_CHAPTERS[frame.step]}">How this step works</a>`;
    const wake = !example && waited > 6
      ? '<p class="panel-note">The service may be waking up: after a quiet spell this takes up to a minute.</p>' : '';
    const lead = example
      ? 'Replaying the recorded example: no file is sent.'
      : `Waiting for the answer: <span class="clock">${clockText(waited)}</span>`;
    return `<span class="bead">Illustration</span>
      <p>It shows the steps the service runs, not its progress.</p>${steps}
      <p>${lead}</p>${wake}`;
  }

  function render() {
    const name = st.name;
    if (name === 'idle') status(null);
    else if (name === 'checking') status('<p>Checking the file in your browser…</p>');
    else if (name === 'chosen') status(st.check?.ok ? '<p>Checked in your browser; nothing has been sent yet.</p>' : null);
    else if (name === 'sending') {
      const pct = Math.round(uploaded * 100);
      status(`<p>Sending your file: ${pct}%</p><div class="bar"><span style="width:${pct}%"></span></div>`);
    } else if (name === 'working' || name === 'finishing') status(workingHtml());
    else if (name === 'busy') status(`<p>Another file is being labelled. Trying again in ${Math.max(0, Math.ceil((st.retryAfter ?? 30) - phase))} s.</p>`);
    else if (name === 'failed') {
      const retry = st.example || (st.file && st.check?.ok) ? '<button type="button" class="text-button" data-retry>Try again</button>' : '';
      const message = st.stage === 'busy'
        ? `The service was still busy after ${MAX_ATTEMPTS} tries. Try again in a few minutes.`
        : explainFailure(st.error, serviceUrl());
      status(`${errorPanel(new Error(message))}${retry}`);
    } else if (run) status(buildReceipt(run.receipt));
    $('skip').hidden = !GUIDED.has(name);
    $('replay-view').hidden = name !== 'interactive';
    const legend = $('legend-card');
    if (run && (GUIDED.has(name) || name === 'interactive')) {
      legend.innerHTML = buildAnswerKey() + (run.placeable ? ''
        : `<p class="panel-note">This service runs ${escapeHtml(run.data?.pipeline_version ?? 'another model')}; its map is not this atlas's, so cells are listed, not placed.</p>`);
      legend.hidden = false;
    } else {
      legend.hidden = true;
    }
    listeners.forEach((f) => f(st, run));
  }

  // ---- the state machine ----

  // A new file or the example, chosen while an answer is shown: the old
  // answer leaves the map, and the new sheet takes the bench again.
  function dropRun() {
    if (!run && !sheet) return;
    illustration.hide();
    upload.clear();
    reference.setDim(0);
    drawer.close();
    run = null;
    sheet = null;
  }

  function enter(name) {
    phase = 0;
    if (name === 'checking') dropRun();
    if (name === 'flying') {
      loadUpload(run.model);
      upload.setNeighbours(run.glow);
      upload.setGlowMode('landing');
      setClock(0);
      const e = stage.camera.matrixWorld.elements;
      upload.setArcUp([e[4], e[5], e[6]]);
      if (!userCam) stage.rig.animateTo(run.poses.fly, Math.max(0, (run.timeline.fly[1] - run.timeline.fly[0]) * 0.8));
    }
    if (name === 'settling') {
      if (!userCam) stage.rig.animateTo(run.poses.settle, T.settle);
      openResults();
    }
    if (name === 'receipt') {
      illustration.hide();
      if (run) loadUpload({ ...run.model, flies: new Uint8Array(run.model.n) });
      upload.setOpacity(1);
      setClock(0);
    }
    if (name === 'interactive') finish();
    if (name === 'idle') {
      illustration.hide();
      upload.clear();
      reference.setDim(0);
      drawer.close();
      sheet = null;
      run = null;
      stage.rig.reset();
    }
  }

  // The settled view, reached at the end of the landing or by Skip.
  function finish() {
    if (!run) return;
    illustration.hide();
    loadUpload(run.model);
    upload.setOpacity(1);
    upload.setNeighbours(run.glow);
    setClock(run.schedule.end + 10);
    upload.setGlowMode('selected');
    reference.setDim(0.6);
    stage.rig.setGuided(false);
    if (!userCam) stage.rig.setPose(run.poses.settle);
    if (!$('atlas-drawer').classList.contains('open')) openResults();
  }

  function dispatch(event) {
    const before = st;
    st = transition(st, event);
    if (st !== before && st.name !== before.name) enter(st.name);
    render();
    return st !== before;
  }

  // One tick of the stage's clock while something moves.
  function tick(dt) {
    phase += dt;
    const name = st.name;
    if (name === 'working') {
      waited += dt;
      illustration.setFrame(waitingFrame(waited, { stepSeconds }));
      if (st.example && workflow && waited >= stepSeconds * SERVICE_STEPS.length) arrive(workflow, 'recorded');
      render();
      return !reduced;
    }
    if (name === 'finishing') {
      waited += dt * 4;
      illustration.setFrame(waitingFrame(waited, { stepSeconds }));
      if (phase >= finishSeconds) dispatch({ type: 'FINISHED' });
      return true;
    }
    if (name === 'receipt') {
      if (phase >= run.timeline.receipt[1] - run.timeline.receipt[0]) dispatch({ type: 'RECEIPT_DONE' });
      return true;
    }
    if (name === 'flying') {
      setClock(phase);
      reference.setDim(Math.min(0.6, phase * 0.6));
      if (phase >= run.schedule.end) dispatch({ type: 'FLIGHT_DONE' });
      return true;
    }
    if (name === 'settling') {
      setClock(run.schedule.end + phase);
      if (phase >= T.settle) dispatch({ type: 'SETTLED' });
      return true;
    }
    if (name === 'busy') {
      render();
      return true;
    }
    return false;
  }
  stage.addTicker(tick);

  // ---- what the page calls ----

  function arrive(data, source) {
    run = buildRun(data, source);
    // A new answer starts with every outcome shown and no cell selected.
    upload.setAllOutcomes(true);
    upload.setSelected(-1);
    guide();
    finishSeconds = finishWaiting(waitingFrame(waited, { stepSeconds }), { stepSeconds, T });
    dispatch({ type: 'RESPONSE', response: data });
    stage.invalidate();
  }

  async function chooseFile(file) {
    if (!dispatch({ type: 'FILE_CHOSEN', file })) return null;
    try {
      const check = await checkFile(file, file.name);
      const verdict = checkLimits(check, limits());
      // A check of a file no longer chosen is ignored (director.js).
      if (!dispatch({ type: 'CHECKED', file, check: { ...check, ok: verdict.ok, problems: verdict.problems } })) return null;
      showSheet(check.cells);
      stage.invalidate();
      return st.check;
    } catch (error) {
      dispatch({ type: 'CHECK_FAILED', file, error });
      return null;
    }
  }

  async function request() {
    const { file } = st;
    const { modality, restrict } = options();
    const form = new FormData();
    form.append('modality', modality);
    form.append('restrict_to_supported_classes', restrict ? 'true' : 'false');
    form.append('matrix', file, file.name);
    abort = new AbortController();
    uploaded = 0;
    try {
      const response = await client.project(serviceUrl(), form, {
        signal: abort.signal,
        onUpload: (f) => {
          uploaded = f;
          if (f >= 1 && st.name === 'sending') {
            waited = 0;
            startIllustration();
            dispatch({ type: 'UPLOADED' });
          } else render();
        },
      });
      if (st.name === 'sending') {
        waited = 0;
        startIllustration();
        dispatch({ type: 'UPLOADED' });
      }
      if (st.name === 'working') arrive(response, 'service');
    } catch (error) {
      if (error?.kind === 'cancelled' || !['sending', 'working'].includes(st.name)) return;
      illustration.hide();
      upload.setOpacity(1);
      if (error?.kind === 'busy') {
        dispatch({ type: 'BUSY', retryAfter: error.retryAfter ?? 30 });
        if (st.name === 'busy') {
          clearTimeout(busyTimer);
          busyTimer = setTimeout(() => {
            if (st.name !== 'busy') return;
            dispatch({ type: 'RETRY' });
            if (st.name === 'sending') request();
          }, (st.retryAfter ?? 30) * 1000);
        }
        return;
      }
      dispatch({ type: 'FAILED', error });
    }
  }

  function send() {
    if (!dispatch({ type: 'SEND' })) return;
    request();
  }

  async function watchExample() {
    if (!dispatch({ type: 'EXAMPLE' })) return;
    dropRun();
    await playExample();
  }

  // The recorded example's waiting, from the start; it also runs again
  // from "Try again" after a failed load.
  async function playExample() {
    stepSeconds = T.exampleStep;
    waited = 0;
    try {
      workflow ??= await (await fetch(new URL('../../data/workflow.json', import.meta.url))).json();
      showSheet(workflow.trace.cells.length);
      startIllustration();
      if (reduced) arrive(workflow, 'recorded');
    } catch (error) {
      dispatch({ type: 'FAILED', error });
    }
  }

  // Clicks inside the status card and the drawer.
  $('status-card').addEventListener('click', (e) => {
    if (!e.target.closest('[data-retry]') || !dispatch({ type: 'RETRY' })) return;
    if (st.name === 'sending') request();
    else if (st.example && st.name === 'working') playExample();
  });
  $('drawer-body').addEventListener('click', (e) => {
    if (e.target.closest('[data-back]')) return openResults();
    const row = e.target.closest('[data-cell]');
    if (row) select(Number(row.dataset.cell));
  });
  $('skip').addEventListener('click', () => dispatch({ type: 'SKIP' }));
  $('replay-view').addEventListener('click', () => replay());
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && GUIDED.has(st.name)) {
      e.stopImmediatePropagation();
      dispatch({ type: 'SKIP' });
    }
  }, true);

  function replay() {
    if (!run || st.name !== 'interactive') return;
    drawer.close();
    upload.setSelected(-1);
    reference.setDim(0);
    stage.rig.setPose(sheet.bench);
    guide();
    dispatch({ type: 'REPLAY' });
  }

  return {
    get state() { return st; },
    get run() { return run; },
    onChange: (f) => listeners.push(f),
    chooseFile,
    send,
    cancel() {
      abort?.abort();
      clearTimeout(busyTimer);
      illustration.hide();
      upload.setOpacity(1);
      dispatch({ type: 'CANCEL' });
    },
    watchExample,
    async sendExample() {
      const blob = await (await fetch(new URL('../../data/examples/pbmc240_proteins_raw.tsv', import.meta.url))).blob();
      const check = await chooseFile(new File([blob], 'pbmc240_proteins_raw.tsv', { type: 'text/tab-separated-values' }));
      if (check?.ok) send();
    },
    skip: () => dispatch({ type: 'SKIP' }),
    replay,
    clear: () => dispatch({ type: 'CLEAR' }),
    openResults,
    select,
    setOutcomeOn(outcome, on) {
      if (!run) return;
      run.on[outcome] = on;
      upload.setOutcomeOn(outcomeCode(outcome), on);
    },
    chips: () => (run ? buildOutcomeChips(outcomeCounts(run.cells), run.on) : ''),
    download() {
      if (!run || run.source !== 'service') return;
      const blob = new Blob([JSON.stringify(run.data, null, 2)], { type: 'application/json' });
      const stem = (st.file?.name ?? 'upload').replace(/\.[^.]+$/, '');
      const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `vivome-projection-${stem}.json` });
      link.click();
      URL.revokeObjectURL(link.href);
    },
    // The uploaded cell under the pointer, or -1.
    pick(clientX, clientY) {
      if (!run || upload.n === 0 || upload.n !== run.cells.length) return -1;
      const rect = stage.renderer.domElement.getBoundingClientRect();
      const now = upload.positionsAt(clock);
      const screen = projectAll(now, upload.n, stage.viewProjection(), rect.width, rect.height);
      return pickScreen(screen, upload.n, clientX - rect.left, clientY - rect.top, 10, (i) => run.on[run.cells[i].outcome]);
    },
    describe: (i) => (run ? `Your cell ${run.cells[i].id}: ${answerShort(run.cells[i])}` : ''),
  };
}
