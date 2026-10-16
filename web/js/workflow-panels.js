// HTML builders for the Workflow page: tables, cards and readouts. Pure: they
// return strings and escape every value from the data (cell ids, gene names
// and class names are data), so node --test covers them, as panels.js's are.

import { PENDING_LABEL, formatCount, isMeasured } from './manifest.js';
import { escapeHtml } from './panels.js';
import {
  OUTCOME_LABELS, OUTCOME_ORDER, answerSentence, answerText, formatRecord, guessText, isAnswered, outcomeCounts, plainName,
  snippetRows, topK,
} from './workflow-data.js';
import { rocSvg } from './workflow-svg.js';

const e = escapeHtml;
const rec = (record) => (isMeasured(record) ? e(formatRecord(record)) : `<span class="pending">${PENDING_LABEL}</span>`);
const pct = (x) => (Number.isFinite(x) ? `${(x * 100).toFixed(1)}%` : PENDING_LABEL);
const num = (x, d = 3) => (Number.isFinite(x) ? x.toFixed(d) : PENDING_LABEL);
const table = (headers, rows, cls = 'support-table') =>
  `<table class="${cls}"><thead><tr>${headers.map((h) => `<th>${e(h)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`;
const missing = '<span class="wf-missing" title="missing in the file">blank</span>';

export function buildSyncBanner(problems) {
  if (!problems?.length) return '';
  return `<div class="pending-banner" role="status"><strong>These two data files are from different releases.</strong> `
    + `${e(problems.join('; '))}. Numbers below may not match the rest of the site until both are rebuilt.</div>`;
}

// ---- the files ----

// A corner of a file: its header and first rows, missing values marked.
export function buildRawSnippet(snippet, { caption = '' } = {}) {
  if (!snippet) return `<p class="pending">${PENDING_LABEL}</p>`;
  const rows = snippet.rows.map((row) => `<tr>${row.map((v, i) => (i === 0 ? `<td class="wf-key">${e(v)}</td>`
    : `<td class="support-num">${v === null ? missing : e(typeof v === 'number' ? v.toLocaleString('en-US') : v)}</td>`)).join('')}</tr>`).join('');
  const head = snippet.header.map((h, i) => (i === 0 && !h ? '(index)' : h));
  return `<div class="table-scroll">${table(head, rows, 'support-table wf-snippet')}</div>`
    + `<p class="panel-note">${e(caption || `${snippet.orientation}; ${snippet.values ?? ''}`)} <code>${e(snippet.path)}</code></p>`;
}

// PBMC240 as the DIA-NN report holds it: the first protein groups (rows)
// over the story cells' runs (columns), on the file's linear scale.
export function buildPbmcTable(workflow, rows = 10) {
  const details = workflow?.trace?.detail ?? [];
  if (!details.length) return `<p class="pending">${PENDING_LABEL}</p>`;
  const ids = details.map((d) => `Cell ${d.cell + 1}`);
  const body = snippetRows(details, rows).map((g) => `<tr><td class="wf-key">${e(details[0].raw_row[g][0])}</td>${details
    .map((d) => {
      const v = d.raw_row[g]?.[1];
      return `<td class="support-num">${v === null || v === undefined ? missing : e(v.toLocaleString('en-US'))}</td>`;
    }).join('')}</tr>`).join('');
  return `<div class="table-scroll">${table(['Protein', ...ids], body, 'support-table wf-snippet')}</div>`;
}

export function buildHeaderMorph(workflow) {
  const examples = workflow?.raw?.pbmc240?.parse?.header_examples ?? [];
  return `<ul class="wf-morph">${examples.map(([raw, clean]) => `<li><code class="wf-from">${e(raw)}</code>`
    + `<span class="wf-arrow" aria-hidden="true">→</span><code class="wf-to">${e(clean)}</code></li>`).join('')}</ul>`;
}

export function buildFormatCards(workflow) {
  const s = workflow?.raw?.snippets ?? {};
  const parse = workflow?.raw?.pbmc240?.parse ?? {};
  const cards = [
    ['PBMC240', `${parse.format ?? ''}: one row per protein group, one column per run, annotation columns first (${(parse.annotation_columns ?? []).join(', ')}).`,
      'The example traced on this page.'],
    ['SCoPE2', s.scope2 ? `${s.scope2.orientation}; ${s.scope2.values}.` : PENDING_LABEL, 'Development data.'],
    ['Fulcher 2026', s.fulcher2026 ? `${s.fulcher2026.orientation}; ${s.fulcher2026.values}; ${formatCount(s.fulcher2026.channels)} channels.` : PENDING_LABEL,
      'Development data.'],
    ['The RNA reference', s.reference ? `${s.reference.note}.` : PENDING_LABEL, 'Training data.'],
  ];
  return `<ul class="wf-cards">${cards.map(([title, text, role]) => `<li class="liquid wf-card"><h3>${e(title)}</h3>`
    + `<p>${e(text)}</p><p class="caption">${e(role)}</p></li>`).join('')}</ul>`;
}

// ---- genes ----

export function buildGeneLookup(result, query) {
  if (!String(query ?? '').trim()) return '';
  if (!result) {
    return `<p class="wf-lookup-result"><strong>${e(String(query).trim().toUpperCase())}</strong> is not on the shared list. `
      + 'Check the spelling; otherwise none of the protein lists named it, or the RNA examples do not cover it.</p>';
  }
  return `<p class="wf-lookup-result"><strong>${e(result.gene)}</strong> is on the shared list, seat `
    + `${e(formatCount(result.index + 1))}. Named by ${result.sources.length ? e(result.sources.join(', ')) : 'no listed source'}.</p>`;
}

// ---- training ----

export function buildRecipe(workflow) {
  const r = workflow?.training?.recipe;
  if (!r) return `<p class="pending">${PENDING_LABEL}</p>`;
  const rows = [
    ['Optimiser', `AdamW, learning rate ${rec(r.learning_rate)}, weight decay ${rec(r.weight_decay)}, cosine schedule`],
    ['Epochs', `up to ${rec(r.epochs)}, stopping after ${rec(r.patience)} without a better validation loss`],
    ['Batch', `${rec(r.batch)} cells, drawn as an upload would be: ${rec(r.natural_share)} natural composition, otherwise ${e(r.mini_upload_classes.join(', '))} classes`],
    ['Masking', `two views per batch, each keeping a random ${rec(r.coverage_low)} to ${rec(r.coverage_high)} of genes`],
    ['Losses', `cross-entropy × ${rec(r.loss_weights.cross_entropy)}, supervised contrastive × ${rec(r.loss_weights.supervised_contrastive)} (temperature ${rec(r.contrastive_temperature)}, margin ${rec(r.margin)}), hubness × ${rec(r.loss_weights.hubness)}, view consistency × ${rec(r.loss_weights.consistency)}`],
    ['Network', `${r.hidden.map(rec).join(' then ')} wide, dropout ${rec(r.dropout)}, ${rec(r.latent)}-dimensional output`],
  ];
  return table(['Setting', 'Value'], rows.map(([k, v]) => `<tr><td class="wf-key">${e(k)}</td><td>${v}</td></tr>`).join(''));
}

export function buildMembers(workflow) {
  const members = workflow?.training?.members ?? [];
  return table(['Member', 'Answer temperature', 'Best-guess temperature'],
    members.map((m) => `<tr><td><code>${e(m.name)}</code></td><td class="support-num">${rec(m.answer_temperature)}</td>`
      + `<td class="support-num">${rec(m.guess_temperature)}</td></tr>`).join(''));
}

export function buildEncoderChoice(workflow) {
  const c = workflow?.training?.encoder_choice;
  if (!c) return `<p class="pending">${PENDING_LABEL}</p>`;
  return table(['Encoder', 'Balanced accuracy, realistic coverage', 'Seed SD'],
    c.candidates.map((x) => `<tr><td>${e(x.name)}</td><td class="support-num">${rec(x.balanced_accuracy)}</td>`
      + `<td class="support-num">${rec(x.seed_sd)}</td></tr>`).join(''));
}

// ---- one cell ----

// The followed cell, for a reader new to all of it: which cell, how much
// was measured, a rough hint, what VivOME says, and its single best guess.
export function buildCellCard(cell, classOrder, { index = 0, total = null, featureSpace = null } = {}) {
  if (!cell) return `<p class="pending">${PENDING_LABEL}</p>`;
  const guess = cell.guess === null || cell.guess === undefined ? null : classOrder[cell.guess];
  const icon = '<svg class="wf-cell-icon" viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="20" fill="#EAF3FA" stroke="#0066A3" stroke-width="2"/>'
    + '<circle cx="27" cy="21" r="7" fill="#C9DDEE"/><circle cx="16" cy="31" r="2.5" fill="#0066A3" opacity="0.5"/><circle cx="31" cy="33" r="2" fill="#0066A3" opacity="0.5"/></svg>';
  return `<div class="wf-cell-head">${icon}<div><p class="wf-cell-name">Cell ${e(formatCount(index + 1))}`
    + `${total ? ` <span>of ${e(formatCount(total))}</span>` : ''}</p>`
    + `<p class="caption">File name: <code>${e(cell.id)}</code></p></div></div>`
    + `<dl class="wf-cellcard">`
    + `<div><dt>Proteins measured</dt><dd>${e(formatCount(cell.observed))}`
    + `${featureSpace ? `<span class="wf-sub">of the ${e(formatCount(featureSpace))} genes VivOME reads</span>` : ''}</dd></div>`
    + `<div><dt>A rough first look</dt><dd>${e(cell.weak_label && cell.weak_label !== 'unassigned' ? cell.weak_label : 'no hint')}`
    + `<span class="wf-sub">from a few telltale proteins: a hint, not proof</span></dd></div>`
    + `<div class="wf-cellcard-wide"><dt>What VivOME says</dt><dd class="${isAnswered(cell) ? '' : 'wf-abstain'}">${e(answerSentence(cell))}</dd></div>`
    + `<div><dt>If it had to pick one</dt><dd>${guess ? e(plainName(guess)) : 'none'}`
    + `<span class="wf-sub">${guess ? `the model gives it ${e(pct(cell.guess_probability))}` : 'too little was measured'}</span></dd></div>`
    + `</dl>`;
}

// The classes with the most probability: each member's, and their mean.
export function buildProbabilityTable(detail, classOrder, k = 5) {
  if (!detail) return `<p class="pending">${PENDING_LABEL}</p>`;
  const top = topK(detail.ensemble, k);
  const head = ['Class', ...detail.members.map((_, j) => `Member ${j + 1}`), 'Mean'];
  const rows = top.map((c) => `<tr><td>${e(classOrder[c])}</td>${detail.members
    .map((m) => `<td class="support-num">${pct(m.probability[c])}</td>`).join('')}<td class="support-num"><strong>${pct(detail.ensemble[c])}</strong></td></tr>`).join('');
  return `<div class="table-scroll">${table(head, rows)}</div>`;
}

export function buildGuessTable(detail, classOrder, k = 5) {
  if (!detail) return `<p class="pending">${PENDING_LABEL}</p>`;
  const g = detail.guess;
  const rows = topK(g.fused, k).map((c) => `<tr><td>${e(classOrder[c])}</td>`
    + `<td class="support-num">${pct(g.encoder[c])}</td>`
    + `<td class="support-num">${num(g.r_rna[c], 3)}</td>`
    + `<td class="support-num">${g.r_protein[c] === null ? '<span class="pending">not covered</span>' : num(g.r_protein[c], 3)}</td>`
    + `<td class="support-num">${pct(g.correlation_probability[c])}</td>`
    + `<td class="support-num"><strong>${pct(g.fused[c])}</strong></td></tr>`).join('');
  return `<div class="table-scroll">${table(['Class', 'Encoders', 'r, RNA means', 'r, protein means', 'Correlation', 'Fused'], rows)}</div>`;
}

// The abstention ladder, rung by rung, for one cell.
export function buildLadderTrace(cell, workflow) {
  if (!cell) return `<p class="pending">${PENDING_LABEL}</p>`;
  const f = workflow?.facts ?? {};
  const floor = f.floor?.value;
  const threshold = f.ood_threshold?.value;
  const rungs = [
    ['Enough genes?', `${formatCount(cell.observed)} observed, floor ${formatCount(floor)}`, cell.observed >= floor, 'coverage_too_low'],
    ['Like the reference?', `similarity ${num(cell.similarity, 3)}, threshold ${num(threshold, 3)}`, cell.similarity >= threshold, 'outside_supported_region'],
    ['Any class confident?', `${cell.candidate_set.length} class${cell.candidate_set.length === 1 ? '' : 'es'} in the set`, cell.candidate_set.length > 0, 'no_confident_label'],
    ['One level they share?', isAnswered(cell) ? `${cell.label} (${OUTCOME_LABELS[cell.outcome]})` : 'no shared group or lineage', isAnswered(cell), 'ambiguous_between_classes'],
  ];
  let stopped = false;
  const items = rungs.map(([q, detailText, pass, reason]) => {
    const state = stopped ? 'skipped' : pass ? 'pass' : (cell.outcome === reason ? 'stop' : 'pass');
    if (state === 'stop') stopped = true;
    return `<li class="wf-rung wf-${state}"><span class="level">${e(q)}</span><span class="example">${e(detailText)}`
      + `${state === 'stop' ? ` <strong>Stops here: ${e(OUTCOME_LABELS[reason])}.</strong>` : ''}${state === 'skipped' ? ' (not reached)' : ''}</span></li>`;
  });
  return `<ol class="ladder wf-ladder">${items.join('')}</ol>`;
}

export function buildResponseJson(detail) {
  if (!detail) return `<p class="pending">${PENDING_LABEL}</p>`;
  return `<pre class="well wf-json"><code>${e(JSON.stringify(detail.response, null, 2))}</code></pre>`;
}

export function buildOutcomeTable(workflow) {
  const cells = workflow?.trace?.cells ?? [];
  const counts = outcomeCounts(cells);
  const rows = OUTCOME_ORDER.map((k) => `<tr><td>${e(OUTCOME_LABELS[k])}</td><td class="support-num">${formatCount(counts[k])}</td>`
    + `<td class="support-num">${pct(cells.length ? counts[k] / cells.length : NaN)}</td></tr>`).join('');
  return table(['Outcome', 'Cells', 'Share'], rows);
}

// ---- results ----

export function buildScenarioTable(workflow) {
  const rows = (workflow?.evaluation?.scenarios ?? []).map((s) => `<tr><td>${e(s.group)}</td><td class="support-num">${rec(s.cells)}</td>`
    + `<td class="support-num">${rec(s.committed)}</td><td class="support-num">${rec(s.correct_when_committed)}</td>`
    + `<td class="support-num">${rec(s.best_guess_per_upload_balanced)}</td><td class="support-num">${rec(s.coverage)}</td></tr>`).join('');
  return `<div class="table-scroll">${table(['Uploads of', 'Cells', 'Answered', 'Correct when answered', 'Best guess, balanced', 'Set coverage'], rows)}</div>`;
}

const RESULT_BEAD = { pass: 'wf-pass', fail: 'wf-fail', void: 'wf-void' };

export function buildHeldoutCards(workflow) {
  const cards = workflow?.evaluation?.heldout ?? [];
  return `<ul class="wf-heldout">${cards.map((c) => {
    let figure = '';
    let stat = '';
    if (c.curve) {
      figure = rocSvg(c.curve, { size: 180, label: `ROC curve for ${c.key}`, auroc: formatRecord(c.value) });
      stat = `AUROC ${rec(c.value)}, p ${rec(c.p)}; ${Object.entries(c.groups).map(([g, n]) => `${e(g)} ${formatCount(n)}`).join(', ')}`;
    } else if (c.key === 'hao2021') {
      stat = `${rec(c.value)} points over the correlation baseline (lower bound ${rec(c.lower)}); donors ${e(c.donors.join(', '))}`;
    } else {
      stat = e(c.reason ?? '');
    }
    return `<li class="liquid wf-card"><span class="bead ${RESULT_BEAD[c.result] ?? ''}">${e(c.result)}</span>`
      + `<h3>${e(c.question)}</h3><p class="caption">${e(c.statistic ?? '')}</p><p>${stat}</p>${figure}</li>`;
  }).join('')}</ul>`;
}

export function buildServiceCard(workflow, status = null) {
  const s = workflow?.service;
  if (!s) return `<p class="pending">${PENDING_LABEL}</p>`;
  const live = status
    ? `<p class="wf-live"><span class="bead wf-pass">${e(status.status ?? 'answered')}</span> atlas ${e(status.atlas_version ?? '')}, `
      + `${e(status.pipeline_version ?? '')}: ${e(status.model_version ?? '')}</p>`
    : '';
  return `<dl class="model-card">`
    + `<div class="card-field"><dt>Platform</dt><dd>${e(s.platform)}, ${e(s.region)}</dd></div>`
    + `<div class="card-field"><dt>Machine</dt><dd>${rec(s.cpu)} vCPU, ${e(s.memory)}</dd></div>`
    + `<div class="card-field"><dt>Instances</dt><dd>${rec(s.min_instances)} to ${rec(s.max_instances)}</dd></div>`
    + `<div class="card-field"><dt>Per upload</dt><dd>up to ${rec(s.max_cells)} cells, ${rec(s.max_mb)} MB</dd></div>`
    + `<div class="card-field"><dt>At once</dt><dd>${rec(s.concurrent_projections)} projection</dd></div>`
    + `<div class="card-field"><dt>Address</dt><dd><code>${e(s.url)}</code></dd></div>`
    + `</dl>${live}`;
}
