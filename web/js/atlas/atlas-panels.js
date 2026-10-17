// HTML for the Atlas page's "Your data" side: one uploaded cell's card, the
// receipt for a file, the key to how answers are drawn, the buttons that
// show or hide cells by their answer, and the recorded example's summary.
// Pure: they return strings and escape every value (cell ids come from the
// visitor's file, class and model names from the data), so node --test
// covers them. Numbers are the service's or the recorded example's; nothing
// here computes one beyond counting.

import { PENDING_LABEL, formatCount } from '../manifest.js';
import { escapeHtml } from '../panels.js';
import {
  ANSWERED, OUTCOME_CHIPS, OUTCOME_NOTES, OUTCOME_ORDER, answerSentence, formatRecord, guessText, plainName,
} from '../workflow-data.js';
import { FLIGHT, LOOK } from './upload-layer.js';

const e = escapeHtml;
const pending = `<span class="pending">${PENDING_LABEL}</span>`;
const known = (v) => v !== null && v !== undefined && v !== '';
const finite = (v) => known(v) && Number.isFinite(Number(v));
const text = (v) => (known(v) ? e(v) : pending);
const count = (v) => (finite(v) ? e(formatCount(v)) : pending);
const percent = (x) => `${(Number(x) * 100).toFixed(1).replace(/\.0$/, '')}%`;
const field = (label, value, cls = '') => `<div${cls ? ` class="${cls}"` : ''}><dt>${e(label)}</dt><dd>${value}</dd></div>`;

// ---- the answer looks, as small pictures ----

// A neutral stand-in for a type's colour: the key explains the shapes, and
// the colour on the map is the type's own.
const KEY_FILL = '#6B7A86';

const lighten = (hex, k) => {
  const v = parseInt(hex.slice(1), 16);
  const channel = (shift) => Math.round(((v >> shift) & 255) + (255 - ((v >> shift) & 255)) * k);
  return `#${[16, 8, 0].map((s) => channel(s).toString(16).padStart(2, '0')).join('')}`;
};
const round = (x) => Number(x.toFixed(3));
const ringAt = ([a, b]) => ({ r: round((a + b) / 2), w: round(b - a) });

// One picture per look, drawn from the shader's own numbers (LOOK, FLIGHT),
// in units of the cell's radius.
const GLYPH_BODY = {
  class: () => `<circle r="${LOOK.outline}" fill="${LOOK.colours.outline}"/><circle r="1" fill="${KEY_FILL}"/>`,
  group: () => {
    const ring = ringAt(LOOK.inkRing);
    return `<circle r="1" fill="${lighten(KEY_FILL, FLIGHT.lightenGroup)}"/>`
      + `<circle r="${ring.r}" fill="none" stroke="${LOOK.colours.ink}" stroke-width="${ring.w}"/>`;
  },
  lineage: () => {
    const fill = lighten(KEY_FILL, FLIGHT.lightenLineage);
    const [a, b] = LOOK.halo;
    const halo = [1, 0.62, 0.3].map((f, k) => `<circle r="${round(a + (b - a) * f)}" fill="${fill}" opacity="${[0.12, 0.2, 0.3][k]}"/>`);
    return `${halo.join('')}<circle r="1" fill="${fill}"/>`;
  },
  none: () => {
    const ring = ringAt(LOOK.hollow);
    return `<circle r="${ring.r}" fill="none" stroke="${LOOK.colours.none}" stroke-width="${ring.w}"/>`;
  },
  unplaced: () => {
    const ring = ringAt(LOOK.hollow);
    const dash = round((Math.PI * 2 * ring.r) / (LOOK.dashes * 2));
    return `<circle r="${ring.r}" fill="none" stroke="${LOOK.colours.none}" stroke-width="${ring.w}" stroke-dasharray="${dash} ${dash}"/>`;
  },
};

// Sized here so it never shows at an SVG's default 300 by 150; CSS may resize it.
const glyph = (look, cls = 'atlas-glyph', size = 22) => `<svg class="${cls}" width="${size}" height="${size}" viewBox="-2 -2 4 4" `
  + `aria-hidden="true" focusable="false">${GLYPH_BODY[look]()}</svg>`;

// The look an outcome is drawn in (answers.js, answerStyle).
const lookOf = (outcome) => (ANSWERED.has(outcome) ? outcome : outcome === 'coverage_too_low' ? 'unplaced' : 'none');

// ---- one cell ----

function guessLine(cell, classOrder) {
  const name = Number.isInteger(cell.guess) ? classOrder?.[cell.guess] : undefined;
  if (name === undefined) return e(cell.outcome === 'coverage_too_low' ? guessText(cell, classOrder) : 'none given');
  if (!finite(cell.guess_probability)) return e(plainName(name));
  return e(guessText(cell, classOrder));
}

function notPlacedReason(cell) {
  if (cell.outcome === 'coverage_too_low') return 'too little was measured in it to place it';
  if (!Array.isArray(cell.xyz)) return 'the answer gave it no place';
  return 'its place is on a different map from this one';
}

// One uploaded cell: what VivOME says, its best guess, the types it could
// be, how like the reference it is, how much was measured, and its name in
// the file. `placed` (default: it has a place and enough was measured) says
// whether it flew to the map or stayed on the sheet.
export function buildAtlasCellCard(cell, classOrder, { source = 'service', placed = null } = {}) {
  if (!cell) return `<p class="pending">${PENDING_LABEL}</p>`;
  const onMap = placed ?? (cell.outcome !== 'coverage_too_low' && Array.isArray(cell.xyz));
  const sheet = source === 'recorded' ? 'the file’s sheet' : 'your file’s sheet';
  const names = (Array.isArray(cell.set) ? cell.set : [])
    .map((k) => classOrder?.[k])
    .filter((name) => name !== undefined)
    .map((name) => e(plainName(name)));
  const heading = Number.isInteger(cell.index) ? `Cell ${e(formatCount(cell.index + 1))}` : 'Cell';
  return `<div class="atlas-cell-card">`
    + `<div class="atlas-cell-head">${glyph(onMap ? lookOf(cell.outcome) : 'unplaced')}<div>`
    + `<p class="atlas-cell-name">${heading}</p>`
    + `<p class="caption">Name in the file: <code>${text(cell.id)}</code></p></div></div>`
    + `<p class="atlas-cell-answer${ANSWERED.has(cell.outcome) ? '' : ' is-none'}">${e(answerSentence(cell))}</p>`
    + `<dl class="atlas-cell-facts">`
    + field('Best guess', guessLine(cell, classOrder))
    + field('Types it could be', names.length ? names.join(', ') : 'none')
    + field('Likeness to the reference', finite(cell.similarity) ? e(Number(cell.similarity).toFixed(3)) : pending)
    + field('Genes measured', count(cell.observed))
    + `</dl>`
    + (onMap ? '' : `<p class="atlas-cell-note">Not placed on the map: ${e(notPlacedReason(cell))}, so it stays on ${sheet}.</p>`)
    + `<p class="caption">${source === 'recorded'
      ? 'Recorded from the served model for the example file. No file was sent.'
      : 'From the service’s answer for your file.'}</p>`
    + `</div>`;
}

// ---- the file ----

function secondOpinionLine(receipt, whose) {
  const numbers = finite(receipt.agreement) && finite(receipt.threshold)
    ? ` (${percent(receipt.agreement)}, at least ${percent(receipt.threshold)} needed)` : '';
  if (receipt.secondOpinion === 'used') return e(`Used: enough of ${whose} agreed with the learners${numbers}`);
  if (receipt.secondOpinion === 'flat') return e(`Not used: too little of ${whose} agreed with the learners${numbers}`);
  return pending;
}

// What came back for a file (answers.js, receiptFromResponse or
// receiptFromWorkflow): how many cells, how many genes matched the shared
// list, whether the second opinion was used, and which model answered.
export function buildReceipt(receipt) {
  const r = receipt ?? {};
  const recorded = r.source === 'recorded';
  const whose = recorded ? 'the file' : 'your file';
  const genes = finite(r.matched) && finite(r.unmatched)
    ? `${count(r.matched)} of ${count(Number(r.matched) + Number(r.unmatched))}`
    : count(r.matched);
  return `<dl class="atlas-receipt">`
    + field('Cells', count(r.cells))
    + field('Genes matched', genes)
    + field('Second opinion', secondOpinionLine(r, whose))
    + field('Model', text(r.model))
    + `</dl>`
    + (recorded ? '<p class="caption">Recorded from the served model: no file was sent.</p>' : '');
}

// ---- the key ----

const KEY = [
  ['class', 'One type', 'filled, in its type’s colour'],
  ['group', 'A family', 'paler, in a dark ring'],
  ['lineage', 'A branch', 'paler still, in a soft halo'],
  ['none', 'No answer', 'a grey ring'],
  ['unplaced', 'Not placed', 'a broken ring, left on the file’s sheet'],
];

// How an answer is drawn: one picture per look, as the map draws it.
export function buildAnswerKey() {
  const items = KEY.map(([look, name, how]) => `<li class="atlas-key-item">${glyph(look)}`
    + `<span><strong>${e(name)}:</strong> ${e(how)}</span></li>`).join('');
  return `<ul class="atlas-key">${items}</ul>`
    + '<p class="caption">A blue ring marks the cell you picked.</p>'
    + '<p class="caption">Glow: nearby reference cells of the type it was given, on this map.</p>';
}

// One button per outcome, with how many cells had it; `on` says which are
// shown (all, unless set to false).
export function buildOutcomeChips(counts, on = {}) {
  return OUTCOME_ORDER.map((k) => `<button type="button" class="atlas-chip" data-outcome="${e(k)}" `
    + `aria-pressed="${on?.[k] === false ? 'false' : 'true'}" title="${e(OUTCOME_NOTES[k])}">`
    + `${glyph(lookOf(k), 'atlas-chip-glyph', 16)}<span class="atlas-chip-label">${e(OUTCOME_CHIPS[k])}</span>`
    + `<span class="atlas-chip-count">${count(counts?.[k])}</span></button>`).join('');
}

// ---- the recorded example ----

export function buildExampleSummary(workflow) {
  const runs = formatRecord(workflow?.facts?.runs);
  const cells = runs === PENDING_LABEL ? pending : e(runs);
  const model = text(workflow?.built_for?.model_name);
  return `<p class="atlas-example">The example is PBMC240, a real file of ${cells} cells from a blood sample, `
    + `answered by ${model}. The answers were recorded from the served model, so no file is sent. `
    + 'Each cell flies from the file’s sheet to the place the model gave it.</p>';
}
