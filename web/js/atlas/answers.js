// What the service said about each uploaded cell, in the one shape the Atlas
// page draws and describes: the trace-cell shape web/js/workflow-data.js
// already speaks (outcome, label, set, best guess, likeness, coordinates).
// Pure: no DOM, no THREE. Every value is the service's, from the visitor's
// own upload, or the recorded example's (web/data/workflow.json); nothing
// here is computed by the browser beyond counting.

import { OUTCOME_ORDER } from '../workflow-data.js';

// The pipelines whose coordinates are this atlas's: they share v3.1's
// coordinate member and its sign-fixed PCA (service/pipeline/fusion.py,
// load_answers). Other versions are listed, not placed.
export const COMPATIBLE_PIPELINES = ['v3.1', 'v4', 'v4.1', 'v4.2'];
export const coordinatesCompatible = (version) => COMPATIBLE_PIPELINES.includes(String(version ?? ''));

// How a cell is drawn. FILL is the colour's class index (-1: none).
export const STYLE = { class: 0, group: 1, lineage: 2, none: 3, unplaced: 4 };

const indexIn = (order, name) => {
  const i = order.indexOf(name);
  return i < 0 ? null : i;
};

// A service response's cells.
export function responseToCells(response, classOrder) {
  return (Array.isArray(response?.cells) ? response.cells : []).map((c, i) => {
    const abstained = c?.abstained === true;
    const outcome = abstained ? (c.abstain_reason ?? 'no_confident_label') : (c?.label_level ?? 'class');
    const xyz = Array.isArray(c?.coordinates) && c.coordinates.length === 3 && c.coordinates.every(Number.isFinite)
      ? c.coordinates : null;
    return {
      index: i,
      id: String(c?.cell_id ?? `cell ${i + 1}`),
      outcome,
      label: abstained ? null : (c?.label ?? null),
      level: abstained ? null : (c?.label_level ?? null),
      set: (Array.isArray(c?.label_set) ? c.label_set : []).map((name) => indexIn(classOrder, name)).filter((v) => v !== null),
      guess: c?.best_guess ? indexIn(classOrder, c.best_guess.label) : null,
      guess_probability: c?.best_guess?.probability ?? null,
      confidence: c?.confidence ?? null,
      similarity: c?.reference_similarity ?? null,
      observed: c?.observed_genes ?? null,
      xyz,
    };
  });
}

// The recorded example: the PBMC240 file traced through the served model.
export function traceToCells(workflow) {
  return (workflow?.trace?.cells ?? []).map((c, i) => ({
    index: i,
    id: c.id,
    outcome: c.outcome,
    label: c.label ?? null,
    level: c.level ?? null,
    set: Array.isArray(c.set) ? c.set : [],
    guess: c.guess ?? null,
    guess_probability: c.guess_probability ?? null,
    confidence: c.confidence ?? null,
    similarity: c.similarity ?? null,
    observed: c.observed ?? null,
    xyz: Array.isArray(c.xyz) ? c.xyz : null,
  }));
}

// How a cell is drawn: an answer of one type is filled in that type's
// colour; a family or branch answer takes the best guess's colour (under
// v4.1 the best guess is always in the set); no answer is a hollow ring; a
// cell with too little measured, or from a service on another map, stays
// on the file's sheet.
export function answerStyle(cell, classOrder, placeable = true) {
  if (!placeable || !cell.xyz || cell.outcome === 'coverage_too_low') {
    return { style: STYLE.unplaced, fill: cell.guess ?? -1 };
  }
  if (cell.outcome === 'class') return { style: STYLE.class, fill: indexIn(classOrder, cell.label) ?? cell.guess ?? -1 };
  if (cell.outcome === 'group') return { style: STYLE.group, fill: cell.guess ?? cell.set[0] ?? -1 };
  if (cell.outcome === 'lineage') return { style: STYLE.lineage, fill: cell.guess ?? cell.set[0] ?? -1 };
  return { style: STYLE.none, fill: -1 };
}

export const outcomeCode = (outcome) => Math.max(0, OUTCOME_ORDER.indexOf(outcome));

export function outcomeCounts(cells) {
  const counts = Object.fromEntries(OUTCOME_ORDER.map((k) => [k, 0]));
  for (const c of cells) if (c.outcome in counts) counts[c.outcome] += 1;
  return counts;
}

// What the receipt shows when an answer arrives: the service's own numbers.
// scaleAsked is the reading the visitor chose for the values (atlas.html's
// #value-scale) and zerosAsked what they said a 0 means (#zeros); null for
// Automatic.
export function receiptFromResponse(r, { scaleAsked = null, zerosAsked = null } = {}) {
  return {
    source: 'service',
    cells: r?.n_cells ?? (Array.isArray(r?.cells) ? r.cells.length : null),
    matched: r?.n_features_matched ?? null,
    unmatched: r?.n_features_unmatched ?? null,
    scale: r?.value_scale ?? null,
    scaleAsked: ['linear', 'log'].includes(scaleAsked) ? scaleAsked : null,
    zerosAsked: ['missing', 'measured'].includes(zerosAsked) ? zerosAsked : null,
    secondOpinion: r?.best_guess_rule?.correlation_term ?? null,
    agreement: r?.best_guess_rule?.agreement ?? null,
    threshold: r?.best_guess_rule?.agreement_threshold ?? null,
    model: r?.model_version ?? null,
    pipeline: r?.pipeline_version ?? null,
    atlas: r?.atlas_version ?? null,
  };
}

// The same for the recorded example, from the workflow data's records.
export function receiptFromWorkflow(w) {
  const value = (record) => (record?.status === 'measured' ? record.value : null);
  const fusion = w?.trace?.stages?.fusion ?? {};
  const scale = w?.raw?.pbmc240?.scale;
  return {
    source: 'recorded',
    cells: value(w?.facts?.runs),
    matched: value(w?.facts?.matched),
    unmatched: value(w?.facts?.unmatched_rows),
    scale: scale ? { detected: scale.detected, transformed: scale.transformed } : null,
    scaleAsked: null,
    zerosAsked: null,
    secondOpinion: fusion.correlation_term ?? null,
    agreement: fusion.agreement ?? null,
    threshold: fusion.threshold ?? null,
    model: w?.built_for?.model_name ?? null,
    pipeline: w?.built_for?.pipeline_version ?? null,
    atlas: w?.built_for?.atlas_version ?? null,
  };
}
