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

import { buildProjectionSummary, errorPanel, escapeHtml } from '../panels.js';
import { SERVICE_STEPS, SERVICE_STEP_CHAPTERS, SERVICE_STEP_NOTES, answerShort } from '../workflow-data.js';
import {
  answerStyle, coordinatesCompatible, outcomeCode, outcomeCounts, receiptFromResponse, receiptFromWorkflow,
  responseToCells, traceToCells,
} from './answers.js';
import { buildAnswerKey, buildAtlasCellCard, buildExampleSummary, buildOutcomeChips, buildReceipt } from './atlas-panels.js';
import { answerGroups, browseOrder, buildBrowseList, buildCellBrowser } from './cell-browser.js';
import { TIMING, finishWaiting, flightSchedule, framePose, landingTimeline, reducedTiming, waitingFrame } from './choreography.js';
import { GUIDED, MAX_ATTEMPTS, initialState, statusLine, transition } from './director.js';
import { checkFile, checkLimits } from './file-check.js';
import { createIllustration } from './illustration.js';
import { toScene } from './reference-data.js';
import {
  boundingSphere, buildGrid, cloudSize, fileCloudLayout, nearestOfClasses, orbitPosition, pickScreen, projectAll,
} from './spatial.js';
import { explainFailure } from './service-client.js';
import { FLIGHT, createUploadLayer } from './upload-layer.js';

const $ = (id) => document.getElementById(id);
const clockText = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

// Where the file's sheet sits: beside the atlas, facing the camera.
const BENCH = { pitch: 0.25, radius: 105, shift: 24, sheetAt: 62, sheetWidth: 30, sheetAspect: 1.6 };
const NEIGHBOURS = { k: 6, maxR: 12, cell: 3 };
// The file's cloud: its shape is seeded by this plus the file's cell count.
const CLOUD_SEED = 0x5eed;
// Play in the step bar: one cell this often (seconds), the camera flying to each.
export const PLAY_SECONDS = 2.5;

export function createLanding({
  THREE, stage, ref, reference, drawer, client, serviceUrl, options, limits, reduced = false, autoPlay = true,
}) {
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
  let lastKey = '';
  let clock = 0;           // the flight clock the upload layer shows
  // The visitor cancelled while the service had their file: cancelling stops
  // the wait, not the service's work, so the next busy answer is likely theirs.
  let cancelledWork = false;
  let userCam = false;      // the visitor took the camera during this landing
  let current = -1;         // the selected cell
  let playing = false;
  let playTimer = null;
  let highlight = true;     // the selected cell's types stay bright on the reference
  const browse = { sort: 'confidence', query: '', open: new Set() };

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

  // Every load sizes the resting cells for the file's cloud; they grow to
  // full size in flight.
  function loadUpload(model) {
    upload.load(model);
    upload.setSheetRadius(Math.min(FLIGHT.radius, cloudSize(model.n).dot));
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

  // The file's cells at rest: an irregular cloud beside the atlas (its shape
  // set by the file's size), facing the camera, a little deep.
  function sheetPositions(n, anchor) {
    const unit = fileCloudLayout(n, CLOUD_SEED + n);
    const { radius } = cloudSize(n);
    const { centre, right, up } = anchor;
    const depth = [right[1] * up[2] - right[2] * up[1], right[2] * up[0] - right[0] * up[2], right[0] * up[1] - right[1] * up[0]];
    const out = new Float32Array(n * 3);
    for (let i = 0; i < n; i += 1) {
      const [x, y, z] = [unit[i * 3], unit[i * 3 + 1], unit[i * 3 + 2]];
      for (let k = 0; k < 3; k += 1) {
        out[i * 3 + k] = centre[k] + (right[k] * x + up[k] * y + depth[k] * z) * radius;
      }
    }
    return out;
  }

  // A cloud of waiting dots, breathing: the file, before its answers.
  function showSheet(n) {
    upload.setShown(true); // a new file is always shown, whatever the switch said before
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
    if (!reduced) upload.setBreathing(true, sheet.anchor.centre);
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
    // The answers the cells were given, as groups (one per type, family,
    // branch or reason for no answer), each shown or hidden by the visitor.
    const groups = answerGroups(cells, ref.order, { placeable });
    const groupOf = new Int32Array(n);
    groups.forEach((g, k) => g.cells.forEach((i) => { groupOf[i] = k; }));
    return {
      source, data, cells, styles, placeable, schedule, model, poses: { fly, settle },
      timeline: landingTimeline(schedule, { T }),
      receipt: recorded ? receiptFromWorkflow(data) : receiptFromResponse(data),
      glow: neighboursOf(cells, styles, model, schedule),
      on: Object.fromEntries(Object.keys(outcomeCounts(cells)).map((k) => [k, true])),
      groups, groupOf, groupOn: groups.map(() => true),
      fills: styles.map((s) => s.fill),
    };
  }

  // ---- the cells, one by one ----

  // Shown by both filters: the answer level (the chips) and the type given.
  const cellShown = (i) => run.on[run.cells[i].outcome] !== false && run.groupOn[run.groupOf[i]];
  // The browser's order (grouped, sorted, searched), and the cells the step
  // bar walks: the shown ones, in that order.
  const browseList = () => browseOrder(run.cells, run.groups, browse);
  const steps = () => browseList().filter(cellShown);

  function browserOptions() {
    return {
      ...browse, order: browseList(), fills: run.fills, shown: cellShown, selected: current,
    };
  }

  // The type filter on the GPU: a cell of a hidden group is not drawn.
  function applyGroups() {
    const all = run.groupOn.every(Boolean);
    upload.setCellMask(all ? null : Uint8Array.from(run.groupOf, (k) => (run.groupOn[k] ? 1 : 0)));
    if (current >= 0 && !cellShown(current)) deselect();
    refreshBrowser();
    render();
  }

  // The selected cell's possible types stay bright on the reference; the
  // rest fade (the visitor's switch, on by default).
  function focusTypes() {
    const set = run && current >= 0 ? run.cells[current].set : [];
    reference.setFocusSet(highlight && set.length ? set : null);
  }

  function deselect() {
    current = -1;
    upload.setSelected(-1);
    reference.setFocusSet(null);
    play(false);
  }

  // The drawer's results as folding sections, under the results' own
  // actions (the sidebar folds away while an answer is shown).
  const section = (title, body, open = false) => `<details class="fold drawer-section"${open ? ' open' : ''}>`
    + `<summary>${escapeHtml(title)}</summary>${body}</details>`;

  function resultsHtml() {
    if (!run) return '';
    const cellsTitle = `Your cells (${run.cells.length.toLocaleString('en-US')})`;
    const download = run.source === 'service' ? '<button type="button" class="text-button" data-action="download">Download the response</button>' : '';
    const actions = `<div class="drawer-actions">${download}<button type="button" class="text-button" data-action="clear">Clear</button></div>`;
    const browser = section(cellsTitle, buildCellBrowser(run.cells, run.groups, browserOptions()), true);
    if (run.source === 'recorded') return `${actions}${buildExampleSummary(run.data)}${browser}`;
    return actions + section('About this answer', buildProjectionSummary(run.data)) + browser;
  }

  function openResults() {
    if (run) drawer.open(run.source === 'recorded' ? 'The example: answers' : 'Your file: answers', resultsHtml());
  }

  // Redraws the browser's list in place (the search box keeps its focus).
  function refreshBrowser() {
    const list = $('browse-list');
    if (run && list && $('atlas-drawer').classList.contains('open') && !$('drawer-body').querySelector('.atlas-cell-card')) {
      list.innerHTML = buildBrowseList(run.cells, run.groups, browserOptions());
    }
  }

  // One cell's card, with its place among the cells shown and the way on.
  function cardHtml(i) {
    const list = steps();
    const k = list.indexOf(i);
    const where = k >= 0 ? `${(k + 1).toLocaleString('en-US')} of ${list.length.toLocaleString('en-US')}` : 'Hidden by a filter';
    return '<div class="card-nav">'
      + '<button type="button" class="drawer-back" data-back>Back to all cells</button>'
      + `<span class="card-nav-where">${escapeHtml(where)}</span>`
      + '<button type="button" class="text-button" data-step="-1" aria-label="Previous cell">&lsaquo; Previous</button>'
      + '<button type="button" class="text-button" data-step="1" aria-label="Next cell">Next &rsaquo;</button>'
      + `</div><p class="card-group">${escapeHtml(run.groups[run.groupOf[i]].name)}</p>`
      + buildAtlasCellCard(run.cells[i], ref.order, { source: run.source });
  }

  function select(i, { fly = true } = {}) {
    if (!run || i < 0 || i >= run.cells.length) return;
    current = i;
    upload.setSelected(i);
    upload.setGlowMode('selected');
    focusTypes();
    if (fly) {
      const p = run.schedule.flies[i] ? run.model.end : run.model.start;
      stage.rig.animateTo({ target: [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]], radius: 18 }, T.flyToCell);
    }
    drawer.open('One cell', cardHtml(i));
    render();
  }

  // The next or previous shown cell, in the browser's order (from the first
  // or the last when none is selected); false at either end when `wrap` is off.
  function step(direction, { wrap = true } = {}) {
    if (!run) return false;
    const list = steps();
    if (!list.length) return false;
    const k = list.indexOf(current);
    let next = k < 0 ? (direction > 0 ? 0 : list.length - 1) : k + direction;
    if (next < 0 || next >= list.length) {
      if (!wrap) return false;
      next = (next + list.length) % list.length;
    }
    select(list[next]);
    return true;
  }

  // Play: a cell every PLAY_SECONDS, to the end of the shown cells.
  function play(on) {
    clearTimeout(playTimer);
    playTimer = null;
    playing = Boolean(on) && Boolean(run);
    if (playing) {
      const next = () => {
        if (!step(1, { wrap: false })) return play(false);
        playTimer = setTimeout(next, PLAY_SECONDS * 1000);
        return undefined;
      };
      if (current < 0 || steps().indexOf(current) < 0) {
        step(1);
        playTimer = setTimeout(next, PLAY_SECONDS * 1000);
      } else {
        next();
      }
    }
    render();
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
    else if (name === 'busy') {
      const who = cancelledWork ? 'The service is still finishing the file you cancelled.' : 'Another file is being labelled.';
      status(`<p>${who} Trying again in ${Math.max(0, Math.ceil((st.retryAfter ?? 30) - phase))} s.</p>`);
    }
    let failure = '';
    if (name === 'failed') {
      // A file the service turned down would be turned down again as it is.
      const again = st.example || (st.file && st.check?.ok && st.error?.kind !== 'refused');
      const retry = again ? '<button type="button" class="text-button" data-retry>Try again</button>' : '';
      failure = st.stage === 'busy'
        ? `The service was still busy after ${MAX_ATTEMPTS} tries. Try again in a few minutes.`
        : explainFailure(st.error, serviceUrl());
      status(`${errorPanel(new Error(failure))}${retry}`);
    } else if (run && !['idle', 'checking', 'chosen', 'sending', 'working', 'finishing', 'busy'].includes(name)) {
      status(buildReceipt(run.receipt, { open: name !== 'interactive' }));
    }
    const line = statusLine(st, { cells: run?.cells?.length ?? null, failure });
    if ($('status-line').textContent !== line) $('status-line').textContent = line;
    $('skip').hidden = !GUIDED.has(name);
    $('replay-view').hidden = name !== 'interactive';
    // The step bar: which shown cell is selected, and the way on.
    const stepping = Boolean(run) && name === 'interactive' && upload.shown;
    $('step-bar').hidden = !stepping;
    if (stepping) {
      const list = steps();
      const k = list.indexOf(current);
      const count = list.length.toLocaleString('en-US');
      $('step-text').textContent = k >= 0
        ? `${(k + 1).toLocaleString('en-US')} of ${count} · ${run.groups[run.groupOf[current]].name}`
        : `${count} cells shown: step through them`;
      // Its label says what a press does (one or the other: a label that
      // changes and a pressed state would read "Pause, pressed").
      $('step-play').textContent = playing ? 'Pause' : 'Play';
      for (const id of ['step-prev', 'step-next', 'step-play']) $(id).disabled = list.length === 0;
    }
    const legend = $('legend-card');
    if (run && (GUIDED.has(name) || name === 'interactive')) {
      // Written only when it changes, so an opened key stays open.
      const key = buildAnswerKey() + (run.placeable ? ''
        : `<p class="panel-note">This service runs ${escapeHtml(run.data?.pipeline_version ?? 'another model')}; its map is not this atlas's, so cells are listed, not placed.</p>`);
      if (key !== lastKey) legend.innerHTML = key;
      lastKey = key;
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
    deselect();
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
      upload.setBreathing(false);
      if (!userCam) stage.rig.animateTo(run.poses.settle, T.settle);
      openResults();
    }
    if (name === 'receipt') {
      illustration.hide();
      if (run) loadUpload({ ...run.model, flies: new Uint8Array(run.model.n) });
      upload.setOpacity(1);
      setClock(0);
      if (!reduced && sheet) upload.setBreathing(true, sheet.anchor.centre);
    }
    if (name === 'interactive') finish();
    if (name === 'idle') {
      deselect();
      illustration.hide();
      upload.clear();
      reference.setDim(0);
      drawer.close();
      sheet = null;
      run = null;
      stage.rig.reset();
    }
  }

  // The settled view, reached at the end of the landing or by Skip. Then
  // the camera goes to the first cell and Play walks on from it, unless the
  // visitor took the camera during the landing or asked for less motion.
  function finish() {
    if (!run) return;
    illustration.hide();
    loadUpload(run.model);
    upload.setOpacity(1);
    upload.setBreathing(false);
    if (!reduced) upload.setPulse(true);
    upload.setNeighbours(run.glow);
    setClock(run.schedule.end + 10);
    upload.setGlowMode('selected');
    reference.setDim(0.6);
    stage.rig.setGuided(false);
    if (!userCam) stage.rig.setPose(run.poses.settle);
    if (!$('atlas-drawer').classList.contains('open')) openResults();
    if (autoPlay && !reduced && !userCam && upload.shown) play(true);
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
    deselect();
    run = buildRun(data, source);
    // A new answer starts with every outcome and type shown, no cell
    // selected, and its largest group open in the browser.
    upload.setAllOutcomes(true);
    upload.setCellMask(null);
    browse.query = '';
    browse.open = new Set(run.groups.length ? [run.groups[0].key] : []);
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
      cancelledWork = false;
      if (st.name === 'working') arrive(response, 'service');
    } catch (error) {
      if (error?.kind === 'cancelled' || !['sending', 'working'].includes(st.name)) return;
      illustration.hide();
      upload.setOpacity(1);
      // The service turned the file down in its own words: it read the file,
      // which it does only in a projection slot, so the cancelled work is done.
      // (Its refusals before the slot are ones this page's checks keep from
      // it: the size check leaves room for the form, binary files are refused
      // here as there, and the form is this page's own.)
      if (error?.kind === 'refused' && error.said) cancelledWork = false;
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
    const action = e.target.closest('[data-action]')?.dataset.action;
    if (action === 'download') return download();
    if (action === 'clear') return dispatch({ type: 'CLEAR' });
    const stepper = e.target.closest('[data-step]');
    if (stepper) {
      play(false);
      return step(Number(stepper.dataset.step));
    }
    const row = e.target.closest('[data-cell]');
    if (row) select(Number(row.dataset.cell));
    return undefined;
  });
  // The browser's search and sort redraw its list; its groups remember
  // whether they are open ('toggle' does not bubble, so it is caught on the way down).
  $('drawer-body').addEventListener('input', (e) => {
    if (e.target.dataset?.browse !== 'query') return;
    browse.query = e.target.value;
    refreshBrowser();
    render();
  });
  $('drawer-body').addEventListener('change', (e) => {
    if (e.target.dataset?.browse !== 'sort') return;
    browse.sort = e.target.value;
    refreshBrowser();
    render();
  });
  $('drawer-body').addEventListener('toggle', (e) => {
    const key = e.target.dataset?.group;
    if (key === undefined) return;
    if (e.target.open) browse.open.add(key);
    else browse.open.delete(key);
  }, true);
  $('skip').addEventListener('click', () => dispatch({ type: 'SKIP' }));
  $('replay-view').addEventListener('click', () => replay());
  $('step-prev').addEventListener('click', () => { play(false); step(-1); });
  $('step-next').addEventListener('click', () => { play(false); step(1); });
  $('step-play').addEventListener('click', () => play(!playing));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && GUIDED.has(st.name)) {
      e.stopImmediatePropagation();
      dispatch({ type: 'SKIP' });
    }
    // The arrow keys step through the cells, unless the visitor is typing or
    // on the panel's tabs (main.js: there the arrows change the tab).
    const typing = e.target?.closest?.('input, select, textarea, [contenteditable="true"], [role="tablist"]');
    if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && run && st.name === 'interactive' && upload.shown && !typing) {
      e.preventDefault();
      play(false);
      step(e.key === 'ArrowRight' ? 1 : -1);
    }
  }, true);

  // The response as received, saved as a file.
  function download() {
    if (!run || run.source !== 'service') return;
    const blob = new Blob([JSON.stringify(run.data, null, 2)], { type: 'application/json' });
    const stem = (st.file?.name ?? 'upload').replace(/\.[^.]+$/, '');
    const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `vivome-projection-${stem}.json` });
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function replay() {
    if (!run || st.name !== 'interactive') return;
    drawer.close();
    deselect();
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
      if (st.name === 'working') cancelledWork = true;
      abort?.abort();
      clearTimeout(busyTimer);
      illustration.hide();
      upload.setOpacity(1);
      dispatch({ type: 'CANCEL' });
    },
    watchExample,
    // The example is sent only if the visitor chose nothing while it loaded:
    // a file they chose meanwhile stays theirs. The service's limits arriving
    // in the meantime change nothing. A load that fails says so.
    async sendExample() {
      const before = st;
      const changed = () => st.name !== before.name || st.file !== before.file;
      const name = 'pbmc240_proteins_raw.tsv';
      let blob;
      try {
        const response = await fetch(new URL(`../../data/examples/${name}`, import.meta.url));
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        blob = await response.blob();
      } catch (error) {
        if (changed()) return;
        const file = new File([], name);
        if (dispatch({ type: 'FILE_CHOSEN', file })) {
          dispatch({ type: 'CHECK_FAILED', file, error: new Error(`The example file could not be loaded (${error.message}). Try again.`) });
        }
        return;
      }
      if (changed()) return;
      const check = await chooseFile(new File([blob], name, { type: 'text/tab-separated-values' }));
      if (check?.ok) send();
    },
    // The service's limits arrived or changed after a file was checked
    // (data-tab.js): the file is judged again against them.
    recheckLimits() {
      if (st.name !== 'chosen' || !st.check) return;
      const verdict = checkLimits(st.check, limits());
      dispatch({ type: 'LIMITS', check: { ...st.check, ok: verdict.ok, problems: verdict.problems } });
    },
    skip: () => dispatch({ type: 'SKIP' }),
    replay,
    clear: () => dispatch({ type: 'CLEAR' }),
    openResults,
    select,
    // The answer filters and the switch for the visitor's cells; every
    // control showing them (the Your data card, Explore) hears the change.
    setOutcomeOn(outcome, on) {
      if (!run) return;
      run.on[outcome] = on;
      upload.setOutcomeOn(outcomeCode(outcome), on);
      if (current >= 0 && !cellShown(current)) deselect();
      refreshBrowser();
      render();
    },
    setCellsShown(on) {
      upload.setShown(on);
      if (!on) play(false);
      render();
    },
    get cellsShown() { return upload.shown; },
    // The types given: each group with its count and whether it is shown.
    groups: () => (run ? run.groups.map((g, k) => ({ ...g, count: g.cells.length, on: run.groupOn[k] })) : []),
    setGroupOn(key, on) {
      const k = run ? run.groups.findIndex((g) => g.key === key) : -1;
      if (k < 0) return;
      run.groupOn[k] = Boolean(on);
      applyGroups();
    },
    showOnlyGroup(key) {
      if (!run || !run.groups.some((g) => g.key === key)) return;
      run.groupOn = run.groups.map((g) => g.key === key);
      applyGroups();
    },
    setAllGroups(on) {
      if (!run) return;
      run.groupOn = run.groups.map(() => Boolean(on));
      applyGroups();
    },
    setHighlight(on) {
      highlight = Boolean(on);
      focusTypes();
      render();
    },
    get highlight() { return highlight; },
    get current() { return current; },
    get playing() { return playing; },
    step,
    play,
    deselect() {
      deselect();
      render();
    },
    chips: () => (run ? buildOutcomeChips(outcomeCounts(run.cells), run.on) : ''),
    download,
    // The uploaded cell under the pointer, or -1.
    pick(clientX, clientY) {
      if (!run || !upload.shown || upload.n === 0 || upload.n !== run.cells.length) return -1;
      const rect = stage.renderer.domElement.getBoundingClientRect();
      const now = upload.positionsAt(clock);
      const screen = projectAll(now, upload.n, stage.viewProjection(), rect.width, rect.height);
      return pickScreen(screen, upload.n, clientX - rect.left, clientY - rect.top, 10, (i) => upload.visible(i));
    },
    describe: (i) => (run ? `Your cell ${run.cells[i].id}: ${answerShort(run.cells[i])}` : ''),
  };
}
