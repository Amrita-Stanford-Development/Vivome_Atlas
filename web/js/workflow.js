// The Workflow page (web/workflow.html; docs/web/workflow.md). It loads the
// manifest and web/data/workflow.json together, fills every [data-fact] and
// [data-wf] slot through the isMeasured guard, keeps the followed cell, and
// drives each chapter's scene by scroll. A chapter's stage (its heading,
// beats and figure) pins in the middle of the window, and the scrolled share
// of the chapter's runway is the animation's progress, 0 to 1, split evenly
// into its beats (web/js/timeline.js); when it reaches 1 the stage lets go
// and the page moves on. Scenes load when their chapter comes near
// (web/js/scenes-*.js). The film
// (web/js/film.js) loads on "Play the whole story" or a #film link.
// Under reduced motion nothing animates: each figure shows the finished
// frame of the beat being read.

import { loadManifest, PENDING_LABEL } from './manifest.js';
import { errorPanel, escapeHtml, factText } from './panels.js';
import { CHAPTERS, beatAt, parseHash, stepTarget } from './timeline.js';
import {
  OUTCOME_LABELS, OUTCOME_ORDER, answerText, checkSync, classColour, detailFor, geneLookup, loadWorkflow, outcomeCounts,
  searchCells, storyFor, wfFact,
} from './workflow-data.js';
import {
  buildCellCard, buildEncoderChoice, buildFormatCards, buildGeneLookup, buildGuessTable, buildHeldoutCards,
  buildLadderTrace, buildMembers, buildOutcomeTable, buildRawSnippet, buildRecipe, buildResponseJson,
  buildScenarioTable, buildServiceCard, buildSyncBanner,
} from './workflow-panels.js';
import { treeSvg } from './workflow-svg.js';

const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// Which module draws which chapter.
const MODULES = {
  input: () => import('./scenes-input.js'),
  model: () => import('./scenes-model.js'),
  evidence: () => import('./scenes-evidence.js'),
};
const MODULE_OF = {
  open: 'input', data: 'input', files: 'input', genes: 'input', upload: 'input', matching: 'input', smoothing: 'input',
  encoder: 'model', probabilities: 'model', guess: 'model', answer: 'model', landing: 'model',
  training: 'evidence', results: 'evidence',
};

const state = { cell: 0, options: {} };
// Scroll per beat while a stage is pinned, as a share of the window's height.
const RUNWAY_PER_BEAT = 0.8;
const pins = new Map(); // chapter id -> {runway, pin, top, height}
const scenes = new Map(); // chapter id -> {scene, section, progress}
let ctx = null;
let film = null;

function setSlots(manifest, workflow) {
  for (const el of $$('[data-fact]')) el.innerHTML = manifest ? factText(manifest, el.dataset.fact) : PENDING_LABEL;
  for (const el of $$('[data-wf]')) el.innerHTML = workflow ? wfFact(workflow, el.dataset.wf) : PENDING_LABEL;
}

function buildContext(manifest, workflow) {
  const classes = workflow.reference.classes;
  const hierarchy = Object.fromEntries(classes.map((c) => [c.name, { group: c.group, lineage: c.lineage }]));
  const cells = workflow.trace.cells;
  return {
    workflow,
    manifest,
    hierarchy,
    classColour,
    cell: (s) => cells[s.cell],
    detail: (s) => {
      const own = detailFor(workflow, s.cell);
      return { detail: own ?? storyFor(workflow, s.cell), own: !!own };
    },
    options: (id) => state.options[id] ?? {},
    answerText: (cell) => answerText(cell).replace(/ \((one class|a group|a lineage)\)$/, (_, l) => ` (${l.replace(/^(one|a) /, '')})`),
    guessText: (cell) => (cell.guess === null ? 'none (too few genes)' : `${workflow.class_order[cell.guess]} (${(cell.guess_probability * 100).toFixed(1)}%)`),
    pick: (i) => setCell(i),
  };
}

// ---- the followed cell ----

function setCell(i) {
  const cells = ctx.workflow.trace.cells;
  if (!Number.isInteger(i) || i < 0 || i >= cells.length) return;
  state.cell = i;
  const cell = cells[i];
  for (const el of $$('[data-cell]')) {
    const kind = el.dataset.cell;
    el.textContent = kind === 'id' ? cell.id
      : kind === 'answer' ? ctx.answerText(cell)
        : kind === 'guess' ? ctx.guessText(cell)
          : kind === 'observed' ? cell.observed.toLocaleString('en-US') : '';
  }
  $('#cell-card').innerHTML = buildCellCard(cell, ctx.workflow.class_order);
  $('#ladder').innerHTML = buildLadderTrace(cell, ctx.workflow);
  const { detail, own } = ctx.detail(state);
  $('#guess-table').innerHTML = (own ? '' : `<p class="caption">The full arrays are recorded for the story runs; this is ${escapeHtml(detail.id)}, a run with the same outcome.</p>`)
    + buildGuessTable(detail, ctx.workflow.class_order);
  $('#response-json').innerHTML = (own ? '' : `<p class="caption">Recorded for the story runs; this is ${escapeHtml(detail.id)}'s.</p>`)
    + buildResponseJson(detail);
  for (const chip of $$('.wf-chip')) chip.setAttribute('aria-pressed', String(Number(chip.dataset.pick) === i));
  if (pins.size) layoutPins();
  renderAll();
  film?.onCell?.(i);
}

function buildPicker() {
  const w = ctx.workflow;
  const cells = w.trace.cells;
  const counts = outcomeCounts(cells);
  const chips = [['the first run', 0], ...OUTCOME_ORDER.filter((k) => counts[k] > 0).map((k) => [OUTCOME_LABELS[k], cells.findIndex((c) => c.outcome === k)])];
  $('#outcome-chips').innerHTML = chips.map(([label, i]) => {
    const kind = cells[i].outcome;
    const n = label === 'the first run' ? '' : `<span class="wf-count">${counts[kind]}</span>`;
    return `<button type="button" class="wf-chip" data-pick="${i}" aria-pressed="false">${escapeHtml(label)}${n}</button>`;
  }).join('');
  $('#outcome-chips').addEventListener('click', (e) => {
    const b = e.target.closest('.wf-chip');
    if (b) setCell(Number(b.dataset.pick));
  });
  const input = $('#cell-search');
  const results = $('#cell-results');
  input.addEventListener('input', () => {
    results.innerHTML = searchCells(w, input.value).map((i) => `<li><button type="button" role="option" data-pick="${i}">${escapeHtml(cells[i].id.replace('Astral_TopMedPBMC1_', ''))}</button></li>`).join('');
  });
  results.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-pick]');
    if (b) setCell(Number(b.dataset.pick));
  });
}

// ---- static panels ----

function buildPanels() {
  const w = ctx.workflow;
  const s = w.raw.snippets;
  $('#format-cards').innerHTML = buildFormatCards(w);
  $('#snippet-scope2').innerHTML = buildRawSnippet(s.scope2);
  $('#snippet-fulcher').innerHTML = buildRawSnippet(s.fulcher2026);
  $('#snippet-reference').innerHTML = buildRawSnippet(s.reference, { caption: s.reference?.note ?? '' });
  $('#recipe').innerHTML = buildRecipe(w);
  $('#members').innerHTML = buildMembers(w);
  $('#encoder-choice').innerHTML = buildEncoderChoice(w);
  $('#outcome-table').innerHTML = buildOutcomeTable(w);
  $('#tree').innerHTML = treeSvg(w.class_order, ctx.hierarchy);
  $('#scenario-table').innerHTML = buildScenarioTable(w);
  $('#service-card').innerHTML = buildServiceCard(w);
  $('#heldout-cards').innerHTML = buildHeldoutCards(w);
  const gene = $('#gene-search');
  gene.addEventListener('input', () => {
    $('#gene-result').innerHTML = buildGeneLookup(geneLookup(w, gene.value), gene.value);
    state.options.genes = { ...(state.options.genes ?? {}), gene: gene.value };
    renderChapter('genes');
  });
  $('#ask-service').addEventListener('click', askService);
}

async function askService() {
  const out = $('#service-status');
  const button = $('#ask-service');
  button.disabled = true;
  out.textContent = 'Asking. If the service is asleep, waking it takes up to a minute.';
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 120000);
    const response = await fetch(`${ctx.workflow.service.url}/api/status`, { signal: controller.signal });
    clearTimeout(timer);
    const status = await response.json();
    $('#service-card').innerHTML = buildServiceCard(ctx.workflow, status);
    out.textContent = response.ok ? 'The live service answered.' : `The service answered with status ${response.status}.`;
  } catch (err) {
    out.textContent = `No answer: ${err.name === 'AbortError' ? 'it took too long' : err.message}.`;
  } finally {
    button.disabled = false;
  }
}

// ---- the table of contents and the figures' controls ----

function buildToc() {
  $('#toc').innerHTML = CHAPTERS.map((c) => `<li><a href="#${c.id}">${escapeHtml(c.title)}</a></li>`).join('');
}

function wireFigures() {
  for (const figure of $$('.wf-stage')) {
    const id = figure.dataset.scene;
    figure.addEventListener('click', (e) => {
      const toggle = e.target.closest('.wf-toggle');
      if (toggle) {
        const option = toggle.dataset.option;
        const group = $$(`.wf-toggle[data-option="${option}"]`, figure);
        const exclusive = toggle.dataset.value !== undefined;
        const opts = { ...(state.options[id] ?? {}) };
        if (exclusive) {
          group.forEach((b) => b.setAttribute('aria-pressed', String(b === toggle)));
          opts[option] = toggle.dataset.value;
        } else {
          const on = toggle.getAttribute('aria-pressed') !== 'true';
          toggle.setAttribute('aria-pressed', String(on));
          opts[option] = on;
        }
        state.options[id] = opts;
        renderChapter(id);
        return;
      }
      const tableToggle = e.target.closest('.wf-table-toggle');
      if (tableToggle) {
        const box = $('.wf-table', figure);
        const open = box.hidden;
        box.hidden = !open;
        figure.classList.toggle('show-table', open);
        tableToggle.setAttribute('aria-expanded', String(open));
        tableToggle.textContent = open ? 'Show the figure' : 'Show as table';
        if (open) box.innerHTML = scenes.get(id)?.scene.table?.(state) || '<p class="caption">This figure has no table.</p>';
        else { scenes.get(id)?.scene?.resize(); renderChapter(id); }
      }
    });
  }
}

// ---- scenes ----

function chapterIndex(id) {
  return CHAPTERS.findIndex((c) => c.id === id);
}

async function mountScene(id) {
  if (scenes.has(id)) return scenes.get(id);
  const section = document.getElementById(id);
  const holder = $('.wf-canvas', section);
  const entry = { scene: null, section, progress: progressOf(id), loading: true };
  scenes.set(id, entry);
  try {
    const module = await MODULES[MODULE_OF[id]]();
    entry.scene = module[id](holder, ctx);
    entry.loading = false;
    renderChapter(id);
  } catch (err) {
    holder.innerHTML = errorPanel(err);
  }
  return entry;
}

function renderChapter(id) {
  const entry = scenes.get(id);
  if (!entry?.scene) return;
  const chapter = CHAPTERS[chapterIndex(id)];
  const p = reduced ? stepTarget(chapter, entry.progress) : entry.progress;
  entry.scene.render(p, state);
  const caption = $('[data-describe]', entry.section);
  if (caption) caption.textContent = entry.scene.describe(state);
}

function renderAll() {
  for (const id of scenes.keys()) renderChapter(id);
}

// Pinning: each stage is centred in the window below the header and held
// there for its chapter's runway. Where every beat does not fit beside the
// figure (and on narrow screens), the beats share one place and cross-fade.
function headerHeight() {
  const header = $('.site-header');
  return header && getComputedStyle(header).position === 'sticky' ? header.offsetHeight : 0;
}

function layoutPins() {
  const vh = window.innerHeight;
  const head = headerHeight();
  const room = vh - head - 16;
  const narrow = window.matchMedia('(max-width: 1023px)').matches;
  for (const c of CHAPTERS) {
    const section = document.getElementById(c.id);
    const runway = $('.wf-runway', section);
    const pin = $('.wf-pin', section);
    const text = $('.wf-text', section);
    if (!runway || !pin) continue;
    if (!$('.wf-beat-dots', text)) {
      const dots = document.createElement('ol');
      dots.className = 'wf-beat-dots';
      dots.setAttribute('aria-hidden', 'true');
      dots.innerHTML = '<li></li>'.repeat(c.beats);
      text.appendChild(dots);
    }
    text.classList.toggle('wf-compact', narrow);
    if (!narrow && pin.offsetHeight > room) text.classList.add('wf-compact');
    const height = pin.offsetHeight;
    const top = head + Math.max(8, (room - height) / 2);
    runway.style.setProperty('--runway', `${Math.round(height + c.beats * RUNWAY_PER_BEAT * vh)}px`);
    runway.style.setProperty('--pin-top', `${Math.round(top)}px`);
    runway.classList.add('is-measured');
    pins.set(c.id, { runway, pin, text, top, height });
  }
}

function progressOf(id) {
  const p = pins.get(id);
  if (!p) return 0;
  const box = p.runway.getBoundingClientRect();
  return Math.min(1, Math.max(0, (p.top - box.top) / Math.max(1, box.height - p.height)));
}

function onScroll() {
  const vh = window.innerHeight;
  for (const c of CHAPTERS) {
    const pin = pins.get(c.id);
    if (!pin) continue;
    const box = pin.runway.getBoundingClientRect();
    if (box.bottom < -vh || box.top > vh * 2) continue;
    const p = progressOf(c.id);
    const beat = beatAt(c, p);
    $$('[data-beat]', pin.text).forEach((el, k) => el.classList.toggle('is-active', k === beat));
    $$('.wf-beat-dots li', pin.text).forEach((el, k) => el.classList.toggle('is-on', k <= beat));
    const entry = scenes.get(c.id);
    if (entry && (Math.abs(p - entry.progress) > 0.002 || p === 1 || p === 0)) {
      entry.progress = p;
      renderChapter(c.id);
    }
  }
  const current = CHAPTERS.find((c) => {
    const box = document.getElementById(c.id).getBoundingClientRect();
    return box.top < vh * 0.5 && box.bottom > vh * 0.5;
  });
  $$('.wf-toc a').forEach((a) => a.classList.toggle('is-current', current && a.getAttribute('href') === `#${current.id}`));
}

function watchChapters() {
  const near = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) mountScene(e.target.id).then(onScroll);
  }, { rootMargin: '600px 0px' });
  for (const c of CHAPTERS) near.observe(document.getElementById(c.id));
  layoutPins();
  document.fonts?.ready.then(() => { layoutPins(); onScroll(); });
  let queued = false;
  const tick = () => { queued = false; onScroll(); };
  window.addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(tick); } }, { passive: true });
  let resizeTimer = null;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { layoutPins(); for (const { scene } of scenes.values()) scene?.resize(); onScroll(); }, 120);
  });
}

// ---- the film ----

async function openFilm(fromHash = null) {
  if (!film) {
    const { createFilm } = await import('./film.js');
    film = createFilm({
      ctx,
      state,
      reduced,
      loadScene: async (id, holder) => (await MODULES[MODULE_OF[id]]())[id](holder, ctx),
      setCell,
    });
  }
  film.open(fromHash ?? { t: 0 });
}

function wireFilm() {
  for (const b of $$('[data-film="play"]')) b.addEventListener('click', () => openFilm());
  const fromHash = parseHash(location.hash);
  if (fromHash.film) {
    if (Number.isInteger(fromHash.cell)) setCell(fromHash.cell);
    openFilm(fromHash);
  }
}

// ---- start ----

Promise.all([loadManifest(), loadWorkflow()]).then(([manifest, workflow]) => {
  const sync = checkSync(manifest, workflow);
  $('#sync-banner').innerHTML = buildSyncBanner(sync.problems);
  ctx = buildContext(manifest, workflow);
  setSlots(manifest, workflow);
  buildToc();
  buildPanels();
  buildPicker();
  wireFigures();
  setCell(0);
  watchChapters();
  wireFilm();
}).catch((err) => {
  setSlots(null, null);
  $('#sync-banner').innerHTML = errorPanel(err);
  for (const holder of $$('.wf-canvas')) holder.innerHTML = '';
});
