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

import { formatCount, loadManifest, PENDING_LABEL } from './manifest.js';
import { errorPanel, escapeHtml, factText } from './panels.js';
import { CHAPTERS, parseHash, playThenRead } from './timeline.js';
import {
  ANSWERED, OUTCOME_CHIPS, OUTCOME_NOTES, OUTCOME_ORDER, answerShort, answerText, checkSync, classColour, detailFor, geneLookup, guessText,
  loadWorkflow, outcomeCounts, wfText,
  searchCells, searchStatus, storyFor, wfFact,
} from './workflow-data.js';
import {
  buildCellCard, buildEncoderChoice, buildFormatCards, buildGeneLookup, buildGuessTable,
  buildLadderTrace, buildMembers, buildOutcomeTable, buildRawSnippet, buildRecipe, buildResponseJson,
  buildScenarioTable, buildServiceCard, buildSyncBanner,
} from './workflow-panels.js';
import { treeSvg } from './workflow-svg.js';
import { siteServiceUrl } from './atlas/service-client.js';

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
  open: 'input', data: 'input', files: 'input', genes: 'input', matching: 'input', smoothing: 'input',
  encoder: 'model', probabilities: 'model', second: 'model', guess: 'model', answer: 'model', landing: 'model',
  online: 'evidence', local: 'evidence',
  training: 'evidence', results: 'evidence',
};

const state = { cell: 0, options: {} };
// Scroll per beat while a stage is pinned, as a share of the window's height.
const RUNWAY_PER_BEAT = 1.2;
const pins = new Map(); // chapter id -> {runway, pin, top, height}
const scenes = new Map(); // chapter id -> {scene, section, progress}
let ctx = null;
let film = null;

function setSlots(manifest, workflow) {
  for (const el of $$('[data-fact]')) el.innerHTML = manifest ? factText(manifest, el.dataset.fact) : PENDING_LABEL;
  for (const el of $$('[data-wf]')) el.innerHTML = workflow ? wfFact(workflow, el.dataset.wf) : PENDING_LABEL;
  for (const el of $$('[data-wftext]')) el.textContent = workflow ? wfText(workflow, el.dataset.wftext) : PENDING_LABEL;
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
    answerText,
    answerShort,
    guessText: (cell) => guessText(cell, workflow.class_order),
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
      : kind === 'number' ? (i + 1).toLocaleString('en-US')
        : kind === 'unmeasured' ? (ctx.workflow.raw.pbmc240.align.feature_space - cell.observed).toLocaleString('en-US')
      : kind === 'answer' ? ctx.answerShort(cell).replace(/^No answer: (.*)$/, 'no answer ($1)')
        : kind === 'guess' ? ctx.guessText(cell)
          : kind === 'observed' ? cell.observed.toLocaleString('en-US')
            : kind === 'observed_raw' ? cell.observed_raw.toLocaleString('en-US') : '';
  }
  $('#cell-card').innerHTML = buildCellCard(cell, ctx.workflow.class_order,
    { index: i, total: cells.length, featureSpace: ctx.workflow.raw.pbmc240.align.feature_space });
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
  const plural = (n) => `${formatCount(n)} cell${n === 1 ? '' : 's'}`;
  // Each button's meaning is read out with it (a hidden note) and shown in
  // an overlay while the button is pointed at or focused.
  const chip = (label, i, note, kind) => {
    const n = kind ? `<span class="wf-count">${plural(counts[kind])}</span>` : '';
    const id = `outcome-note-${kind ?? 'first'}`;
    return `<button type="button" class="wf-chip" data-pick="${i}" data-label="${escapeHtml(label)}" data-note="${escapeHtml(note)}"`
      + ` aria-pressed="false" aria-describedby="${id}">${escapeHtml(label)}${n}</button>`
      + `<span class="visually-hidden" id="${id}">${escapeHtml(note)}</span>`;
  };
  const group = (title, kinds) => {
    const shown = kinds.filter((k) => counts[k] > 0);
    const total = shown.reduce((s, k) => s + counts[k], 0);
    return `<p class="wf-outcome-group">${escapeHtml(title)} <span class="wf-count">${plural(total)}</span></p>`
      + `<div class="wf-chips">${shown.map((k) => chip(OUTCOME_CHIPS[k], cells.findIndex((c) => c.outcome === k), OUTCOME_NOTES[k], k)).join('')}</div>`;
  };
  $('#outcome-chips').innerHTML = `<div class="wf-chips">${chip('The cell we start with', w.trace.story.default ?? 0, 'The first cell in the file that VivOME names and whose telltale proteins agree, so the page opens on a full answer. Cells with no answer are one click away.', null)}</div>`
    + group('Got an answer', OUTCOME_ORDER.filter((k) => ANSWERED.has(k)))
    + group('No answer', OUTCOME_ORDER.filter((k) => !ANSWERED.has(k)));
  const pick = $('.wf-pick');
  const tip = $('#outcome-tip');
  const showTip = (b) => {
    tip.innerHTML = `<strong>${escapeHtml(b.dataset.label)}</strong>${escapeHtml(b.dataset.note)}`;
    tip.hidden = false;
    const p = pick.getBoundingClientRect();
    const r = b.getBoundingClientRect();
    const left = Math.max(0, Math.min(r.left - p.left, pick.clientWidth - tip.offsetWidth));
    let top = r.top - p.top - tip.offsetHeight - 8;
    if (top < 0) top = r.bottom - p.top + 8;
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
    tip.classList.add('is-on');
  };
  const hideTip = () => tip.classList.remove('is-on');
  // Escape closes it, wherever the pointer or focus is (WCAG 1.4.13).
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideTip(); });
  const chips = $('#outcome-chips');
  chips.addEventListener('pointerover', (e) => { const b = e.target.closest('.wf-chip'); if (b) showTip(b); });
  // A tap leaves the overlay open until the next tap elsewhere.
  chips.addEventListener('pointerout', (e) => {
    const b = e.target.closest('.wf-chip');
    if (b && e.pointerType !== 'touch' && !b.contains(e.relatedTarget)) hideTip();
  });
  document.addEventListener('pointerdown', (e) => { if (!e.target.closest?.('.wf-chip')) hideTip(); });
  chips.addEventListener('focusin', (e) => { const b = e.target.closest('.wf-chip'); if (b) showTip(b); });
  chips.addEventListener('focusout', hideTip);
  $('#outcome-chips').addEventListener('click', (e) => {
    const b = e.target.closest('.wf-chip');
    if (b) setCell(Number(b.dataset.pick));
  });
  const input = $('#cell-search');
  const results = $('#cell-results');
  input.placeholder = `A number from 1 to ${cells.length}`;
  input.addEventListener('input', () => {
    const found = searchCells(w, input.value, 9);
    results.innerHTML = found.slice(0, 8).map((i) => `<li><button type="button" data-pick="${i}">Cell ${i + 1}</button></li>`).join('');
    $('#cell-results-count').textContent = searchStatus(input.value, found);
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
    // Through the site's own /api door: the service answers only through it.
    const response = await fetch(`${siteServiceUrl()}/api/status`, { signal: controller.signal });
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
  const entry = { scene: null, section, progress: sceneProgress(id), loading: true };
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
  entry.scene.render(entry.progress, state);
  const caption = $('[data-describe]', entry.section);
  if (caption) caption.textContent = entry.scene.describe(state);
}

function renderAll() {
  for (const id of scenes.keys()) renderChapter(id);
}

// Pinning: each stage (its heading above its figure card) is centred in the
// window and held there for its chapter's runway. Inside the card each beat
// plays its animation, then the frame fades to the beat's sentence
// (timeline.js, playThenRead), with dots for where the chapter is.
function headerHeight() {
  const header = $('.site-header');
  return header && getComputedStyle(header).position === 'sticky' ? header.offsetHeight : 0;
}

function layoutPins() {
  const vh = window.innerHeight;
  const head = headerHeight();
  const room = vh - head - 16;
  for (const c of CHAPTERS) {
    const section = document.getElementById(c.id);
    const runway = $('.wf-runway', section);
    const pin = $('.wf-pin', section);
    const screen = $('.wf-screen', section);
    if (!runway || !pin || !screen) continue;
    if (!$('.wf-beat-dots', section)) {
      const dots = document.createElement('ol');
      dots.className = 'wf-beat-dots';
      dots.setAttribute('aria-hidden', 'true');
      dots.innerHTML = '<li></li>'.repeat(c.beats);
      screen.after(dots);
    }
    $$('[data-beat]', screen).forEach(typeset);
    runway.classList.add('is-measured');
    const height = pin.offsetHeight;
    const top = head + Math.max(8, (room - height) / 2);
    runway.style.setProperty('--runway', `${Math.round(height + c.beats * RUNWAY_PER_BEAT * vh)}px`);
    runway.style.setProperty('--pin-top', `${Math.round(top)}px`);
    pins.set(c.id, { runway, pin, screen, top, height, beats: $$('[data-beat]', screen), dots: $$('.wf-beat-dots li', section) });
  }
}

// Each sentence types itself out when it shows: its letters become spans
// with their order (--i), shown in turn by the CSS, TYPE_MS apart. A filled
// value (data-wf, data-fact, data-cell) types as one piece, so refilling it
// for another followed cell still works. A caret blinks once it is typed.
const TYPE_MS = 11;
function typeset(beat) {
  if (beat.dataset.typeset) return;
  beat.dataset.typeset = 'yes';
  let i = 0;
  const walk = (node) => {
    for (const child of [...node.childNodes]) {
      if (child.nodeType === Node.TEXT_NODE) {
        const frag = document.createDocumentFragment();
        for (const part of child.textContent.split(/([ \t\n\r]+)/)) {
          if (!part) continue;
          if (/^[ \t\n\r]+$/.test(part)) { frag.append(' '); continue; }
          for (const letter of part) {
            const span = document.createElement('span');
            span.className = 'wf-ch';
            span.style.setProperty('--i', i++);
            span.textContent = letter;
            frag.append(span);
          }
        }
        child.replaceWith(frag);
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        if (child.matches('[data-wf], [data-fact], [data-cell]')) {
          child.classList.add('wf-ch');
          child.style.setProperty('--i', i);
          i += 3;
        } else walk(child);
      }
    }
  };
  walk(beat);
  const caret = document.createElement('span');
  caret.className = 'wf-caret';
  caret.setAttribute('aria-hidden', 'true');
  beat.append(caret);
  beat.style.setProperty('--typed', `${i * TYPE_MS}ms`);
}

// The scene's progress for a chapter's scroll: its beat's animation, held
// at the beat's last frame while the sentence shows; under reduced motion,
// that last frame throughout.
function sceneProgress(id) {
  const chapter = CHAPTERS[chapterIndex(id)];
  const at = playThenRead(chapter, progressOf(id));
  return reduced ? at.hold : at.scene;
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
    const at = playThenRead(c, progressOf(c.id));
    const read = reduced ? (at.read > 0.5 ? 1 : 0) : at.read;
    pin.beats.forEach((el, k) => {
      const on = k === at.sentence;
      el.classList.toggle('is-active', on);
      // Typed once its sentence shows; reset when another takes its place.
      el.classList.toggle('is-typed', on && (read > 0.3 || el.classList.contains('is-typed')));
    });
    pin.dots.forEach((el, k) => el.classList.toggle('is-on', k <= at.beat));
    pin.screen.style.setProperty('--read', read.toFixed(3));
    pin.screen.classList.toggle('is-reading', read > 0.5);
    const p = reduced ? at.hold : at.scene;
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
  // Only when the chapter on screen changes: restyling the links on every
  // scroll frame made them shimmer.
  const id = current?.id ?? null;
  if (id !== lastCurrent) {
    lastCurrent = id;
    $$('.wf-station-steps a').forEach((a) => a.classList.toggle('is-current', a.getAttribute('href') === `#${id}`));
  }
}
let lastCurrent;

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

// The opening's scenes rise in once as they come into view ([data-in],
// css/story.css). Wired before the data loads, so they show even if it fails.
(() => {
  const items = $$('[data-in]');
  if (!('IntersectionObserver' in window)) { items.forEach((el) => el.classList.add('is-in')); return; }
  const seen = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add('is-in'); seen.unobserve(e.target); }
  }, { rootMargin: '0px 0px -10% 0px' });
  items.forEach((el) => seen.observe(el));
})();

Promise.all([loadManifest(), loadWorkflow()]).then(([manifest, workflow]) => {
  const sync = checkSync(manifest, workflow);
  $('#sync-banner').innerHTML = buildSyncBanner(sync.problems);
  ctx = buildContext(manifest, workflow);
  setSlots(manifest, workflow);
  buildPanels();
  buildPicker();
  wireFigures();
  setCell(workflow.trace.story.default ?? 0);
  watchChapters();
  wireFilm();
}).catch((err) => {
  setSlots(null, null);
  $('#sync-banner').innerHTML = errorPanel(err);
  for (const holder of $$('.wf-canvas')) holder.innerHTML = '';
});
