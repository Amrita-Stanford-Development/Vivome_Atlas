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
// A landed bead's soft halo in its own colour, as three faint discs.
const halo = (fill) => {
  const [a, b] = LOOK.halo;
  return [1, 0.62, 0.3].map((f, k) => `<circle r="${round(a + (b - a) * f)}" fill="${fill}" opacity="${round([0.1, 0.16, 0.24][k] * LOOK.haloAlpha * 2)}"/>`).join('');
};

const GLYPH_BODY = {
  class: () => `${halo(KEY_FILL)}<circle r="${LOOK.outline}" fill="${LOOK.colours.outline}"/><circle r="1" fill="${KEY_FILL}"/>`,
  group: () => {
    const ring = ringAt(LOOK.inkRing);
    const fill = lighten(KEY_FILL, FLIGHT.lightenGroup);
    return `${halo(fill)}<circle r="1" fill="${fill}"/>`
      + `<circle r="${ring.r}" fill="none" stroke="${LOOK.colours.ink}" stroke-width="${ring.w}"/>`;
  },
  lineage: () => {
    const fill = lighten(KEY_FILL, FLIGHT.lightenLineage);
    return `${halo(fill)}<circle r="1" fill="${fill}"/>`;
  },
  none: () => {
    const ring = ringAt(LOOK.hollow);
    return `${halo(LOOK.colours.none)}<circle r="${ring.r}" fill="none" stroke="${LOOK.colours.none}" stroke-width="${ring.w}"/>`;
  },
  unplaced: () => {
    const ring = ringAt(LOOK.hollow);
    const dash = round((Math.PI * 2 * ring.r) / (LOOK.dashes * 2));
    return `<circle r="${ring.r}" fill="none" stroke="${LOOK.colours.none}" stroke-width="${ring.w}" stroke-dasharray="${dash} ${dash}"/>`;
  },
};

// Sized here so it never shows at an SVG's default 300 by 150; CSS may resize it.
const glyph = (look, cls = 'atlas-glyph', size = 22) => `<svg class="${cls}" width="${size}" height="${size}" viewBox="-2.4 -2.4 4.8 4.8" `
  + `aria-hidden="true" focusable="false">${GLYPH_BODY[look]()}</svg>`;

// The look an outcome is drawn in (answers.js, answerStyle).
const lookOf = (outcome) => (ANSWERED.has(outcome) ? outcome : outcome === 'coverage_too_low' ? 'unplaced' : 'none');

// The same pictures for other panels (cell-browser.js): a look's glyph at a size.
export const lookGlyph = (look, size = 22, cls = 'atlas-glyph') => glyph(look, cls, size);
export { lookOf };

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
// whether it flew to the map or stayed in the file's cloud.
export function buildAtlasCellCard(cell, classOrder, { source = 'service', placed = null } = {}) {
  if (!cell) return `<p class="pending">${PENDING_LABEL}</p>`;
  const onMap = placed ?? (cell.outcome !== 'coverage_too_low' && Array.isArray(cell.xyz));
  const sheet = source === 'recorded' ? 'the file’s cloud' : 'your file’s cloud';
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
    + (onMap ? '' : `<p class="atlas-cell-note">Not placed on the map: ${e(notPlacedReason(cell))}, so it stays in ${sheet}.</p>`)
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
// A folding card: the line says whose file, how many cells and which model;
// opened, the numbers. `open` while the landing plays, folded after.
export function buildReceipt(receipt, { open = true } = {}) {
  const r = receipt ?? {};
  const recorded = r.source === 'recorded';
  const whose = recorded ? 'the file' : 'your file';
  const genes = finite(r.matched) && finite(r.unmatched)
    ? `${count(r.matched)} of ${count(Number(r.matched) + Number(r.unmatched))}`
    : count(r.matched);
  const line = [recorded ? 'The example' : 'Your file', finite(r.cells) ? `${count(r.cells)} cells` : '',
    known(r.pipeline) ? e(r.pipeline) : ''].filter(Boolean).join(' · ');
  return `<details class="fold atlas-receipt-card"${open ? ' open' : ''}><summary>${line}</summary>`
    + `<dl class="atlas-receipt">`
    + field('Cells', count(r.cells))
    + field('Genes matched', genes)
    + field('Second opinion', secondOpinionLine(r, whose))
    + field('Model', text(r.model))
    + `</dl>`
    + (recorded ? '<p class="caption">Recorded from the served model: no file was sent.</p>' : '')
    + `</details>`;
}

// ---- the key ----

const KEY = [
  ['class', 'One type', 'Type', 'filled in its type’s colour, with a white rim'],
  ['group', 'A family', 'Family', 'paler, in a dark ring'],
  ['lineage', 'A branch', 'Branch', 'paler still, with no ring'],
  ['none', 'No answer', 'No answer', 'a grey ring'],
  ['unplaced', 'Not placed', 'Not placed', 'a broken ring, left in the file’s cloud'],
];

// How an answer is drawn: one picture per look, as the map draws it. A
// folding card: the line shows the five looks; opened, what each one means.
export function buildAnswerKey({ open = false } = {}) {
  const row = KEY.map(([look, , short]) => `<span class="atlas-key-mini">${glyph(look, 'atlas-glyph', 14)}${e(short)}</span>`).join('');
  const items = KEY.map(([look, name, , how]) => `<li class="atlas-key-item">${glyph(look)}`
    + `<span><strong>${e(name)}:</strong> ${e(how)}</span></li>`).join('');
  return `<details class="fold atlas-key-card"${open ? ' open' : ''}><summary><span class="atlas-key-row">${row}</span></summary>`
    + `<ul class="atlas-key">${items}</ul>`
    + '<p class="caption">Every landed cell is a bead in a soft halo of its colour. A blue ring marks the cell you picked.</p>'
    + '<p class="caption">Glow: nearby reference cells of the type it was given, on this map.</p>'
    + '</details>';
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
    + 'Each cell flies from the file’s cloud to the place the model gave it.</p>';
}
