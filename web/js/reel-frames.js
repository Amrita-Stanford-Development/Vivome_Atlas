// The Motion page's storyboard (web/motion.html): the two-minute film's
// twelve scenes, their timings, what each shows and says, and how it moves.
// One copy, read by the page (web/js/reel.js) and by the render pipeline
// (motion/scripts/prepare.mjs and motion/scripts/stills.mjs), so the notes
// beside a still always describe the frame that was rendered.
//
// Pure: no DOM, so node --test covers it (web/tests/reel.test.js).
//
// Numbers are slots, never typed: {ms:key} names a record in
// web/data/manuscript.json, shown through msFact's guard; {fact:key} names a
// manifest fact, shown through factText. A pending record reads Pending.

import { escapeHtml, factText } from './panels.js';
import { PENDING_LABEL, isMeasured } from './manifest.js';
import { CAVEATS, formatManuscript, msFact, recordFor } from './manuscript-data.js';
import { formatClock } from './timeline.js';

// The dive's chapters, top to bottom: the depth gauge in every frame.
export const CHAPTERS = [
  { id: 'problem', label: 'The problem' },
  { id: 'solution', label: 'The solution' },
  { id: 'new', label: 'What is new' },
  { id: 'results', label: 'The results' },
  { id: 'use', label: 'Use it' },
];

// Each scene: its length in seconds, its chapter, how deep the camera is
// (0 at the surface, 1 on the floor) at its start and end, and when its
// still is taken (a share of the scene). `screen` is the on-screen text,
// line by line; a headline's `cut` is its one word in the accent block.
export const FRAMES = [
  {
    id: 'surface',
    title: 'The surface',
    chapter: 'problem',
    seconds: 8,
    depth: [0, 0.06],
    still: 0.74,
    screen: [
      { role: 'eyebrow', text: 'Single-cell proteomics' },
      { role: 'headline', text: 'Proteins, measured one cell at a time.', cut: 'time.' },
    ],
    voice: 'Mass spectrometry can now measure the proteins inside single cells, one cell at a time.',
    camera: 'Just under the surface, looking up and ahead; a slow push in.',
    transition: 'Opens from white light. Flows on into scene 2 as the camera tips down.',
    water: 'Rain on the surface: each drop sends rings across the white gel, and a fine white waterline runs along the top.',
    particles: 'Sparse. Cells and molecules drift up towards the light.',
    sound: 'Rain on water, close. A low pad fades in; one soft piano note as the title lands.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (rain)'],
  },
  {
    id: 'unnamed',
    title: 'Without names',
    chapter: 'problem',
    seconds: 10,
    depth: [0.06, 0.18],
    still: 0.8,
    screen: [
      { role: 'headline', text: 'But they arrive without names.', cut: 'names.' },
      { role: 'sub', text: 'Few protein datasets come labelled, and every lab detects a different set of proteins.' },
      { role: 'tag', text: 'Unnamed' },
    ],
    voice: 'But those cells arrive without names. Labelled protein references are few, and every lab detects a different set of proteins.',
    camera: 'Tips down and sinks; the waterline slides up and out of the frame.',
    transition: 'One continuous move from scene 1. Leaves through a cloud of silt.',
    water: 'The same white gel, still now; the waterline slides up out of sight.',
    particles: 'Protein cells in green drift past, each with an empty name tag.',
    sound: 'The rain muffles as we go under. A slow low swell; a hollow tick as each empty tag appears.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)'],
  },
  {
    id: 'gaps',
    title: 'Mostly missing',
    chapter: 'problem',
    seconds: 10,
    depth: [0.18, 0.28],
    still: 0.84,
    screen: [
      { role: 'headline', text: 'And each one is only partly seen.', cut: 'seen.' },
      { role: 'stat', text: '{ms:wf_missing_share}' },
      { role: 'label', text: 'of the values in one public file are missing' },
      { role: 'caption', text: 'PBMC240, the example file on the Workflow page' },
      { role: 'stat', text: '{ms:ds_fulcher2026_proteins_per_cell}' },
      { role: 'label', text: 'proteins measured per cell in Fulcher 2026, the median' },
      { role: 'caption', text: 'VivOME reads {ms:gs_size} genes.' },
    ],
    voice: 'And each cell is only partly seen. Much of a protein matrix is empty.',
    camera: 'A slow sideways track along a matrix of cells and proteins.',
    transition: 'The missing tiles fall away as specks that become the RNA cells of scene 4.',
    water: 'The white gel thickens a little: the frost rises and the far cells soften.',
    particles: 'The molecular network loses links as values drop out.',
    sound: 'Dry ticks as tiles drop out. The pad thins to one held note.',
    drawn: 'The matrix: the PBMC240 example file\'s own values, as the Workflow page shows them (web/data/workflow.json); striped tiles were not measured.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'rna',
    title: 'RNA has names',
    chapter: 'solution',
    seconds: 10,
    depth: [0.28, 0.4],
    still: 0.86,
    screen: [
      { role: 'headline', text: 'RNA atlases already name their cells.', cut: 'cells.' },
      { role: 'stat', text: '{ms:ref_cells}' },
      { role: 'label', text: 'RNA cells, each one labelled' },
      { role: 'caption', text: 'in {ms:ref_classes} blood and immune cell types, from Tabula Sapiens' },
    ],
    voice: 'Single-cell RNA is different. Its atlases are large, and every cell in them has a name.',
    camera: 'Descends through a shoal of cells, then pulls back to see the whole map.',
    transition: 'The map holds and slides aside to become one side of scene 5.',
    water: 'The same white gel. The camera drifts on through the cells, which come closer and larger as it goes down.',
    particles: 'RNA strands in red and gold thread through the shoal.',
    sound: 'A warm chord: the first hint of the theme.',
    drawn: 'The map: a sample of the reference\'s own cells in the atlas\'s projection, coloured by type, as the Atlas page draws them (web/data/workflow.json).',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'vivome',
    title: 'VivOME',
    chapter: 'solution',
    seconds: 12,
    depth: [0.4, 0.5],
    still: 0.82,
    screen: [
      { role: 'wordmark', text: 'VivOME' },
      { role: 'headline', text: 'Trained on RNA. Read on protein.', cut: 'protein.' },
      { role: 'sub', text: 'No protein labels, no paired cells, no retraining on your data.' },
      { role: 'label', text: 'Labelled RNA' },
      { role: 'label', text: 'Your protein cells' },
      { role: 'label', text: '{ms:gs_size} genes link the two' },
      { role: 'caption', text: 'It carries the names across. It never mixes the two kinds of data.' },
    ],
    voice: 'VivOME learns blood cell types from labelled RNA alone, then reads each protein cell against that reference. No protein labels, no paired cells, and no retraining on your data.',
    camera: 'Holds on the wordmark, then a slow crane down to the bridge between the two sides.',
    transition: 'The wordmark rises out of the particles. Leaves on a push into the protein side.',
    water: 'A slow wake ripples through the white gel as the wordmark rises.',
    particles: 'The network links up across the frame as the bridge forms.',
    sound: 'The theme enters in full: a rising arpeggio, and a soft whoosh as the wordmark locks.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (wake)'],
  },
  {
    id: 'built-for-gaps',
    title: 'Built for gaps',
    chapter: 'new',
    seconds: 10,
    depth: [0.5, 0.62],
    still: 0.86,
    screen: [
      { role: 'headline', text: 'Built for missing values.', cut: 'values.' },
      { role: 'point', text: 'It knows which proteins were never measured.' },
      { role: 'point', text: 'It scales each protein within your file.' },
      { role: 'point', text: 'It borrows from similar cells in the same file.' },
      { role: 'point', text: '{ms:wf_members} encoders answer together.' },
    ],
    voice: 'It is built for gaps: it knows which proteins were never measured, scales each one within your file, and asks {ms:wf_members} encoders to answer together.',
    camera: 'Tracks along the matrix from scene 3, now lit: a mask marks each gap.',
    transition: 'Match cut from scene 3\'s matrix. Leaves as the beams meet in one point that drops into scene 7.',
    water: 'The white gel, clearer than in scene 3; nearer cells drift larger past the camera, the far ones softly out of focus.',
    particles: 'Streams of particles converge on one point.',
    sound: 'Soft tones, one per encoder, resolving into one chord.',
    drawn: 'The matrix: the same cells and proteins as scene 3, scaled within the file and then smoothed over similar cells, as the Workflow page shows them (web/data/workflow.json).',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'answers',
    title: 'Honest answers',
    chapter: 'new',
    seconds: 12,
    depth: [0.62, 0.74],
    still: 0.92,
    screen: [
      { role: 'headline', text: 'When unsure, it says so.', cut: 'so.' },
      { role: 'label', text: 'Cell type' },
      { role: 'label', text: 'Group' },
      { role: 'label', text: 'Lineage' },
      { role: 'label', text: 'No answer, and the reason' },
      { role: 'caption', text: 'Cells of the PBMC240 example file, and the answers VivOME gave them.' },
    ],
    voice: 'Every cell gets the most precise answer the evidence allows: a cell type, its group, its lineage, or no answer, and the reason why.',
    camera: 'Locked off on the reference map, seen flat from one side.',
    transition: 'Each answer steps down the ladder in turn. Leaves as the last cell\'s outline dissolves into the gel.',
    water: 'Still gel, so the diagram reads cleanly.',
    particles: 'Few and slow, kept to the edges.',
    sound: 'Descending notes, one per rung, and a soft stop on no answer.',
    drawn: 'Manim draws the reference map and each cell\'s set of plausible types: four real cells of the example file, with the sets and answers the served model gave them (web/data/workflow.json).',
    tools: ['Manim', 'HyperFrames', 'GSAP', 'three.js water (still)'],
  },
  {
    id: 'second-opinion',
    title: 'A second opinion',
    chapter: 'new',
    seconds: 8,
    depth: [0.74, 0.82],
    still: 0.86,
    screen: [
      { role: 'headline', text: 'One best guess, with a second opinion.', cut: 'opinion.' },
      { role: 'label', text: 'The encoder' },
      { role: 'label', text: 'Correlation to each RNA type\'s average' },
      { role: 'label', text: 'Used only when your file agrees with the encoder' },
      { role: 'label', text: 'Best guess' },
      { role: 'chip', text: 'New in {fact:model_name}' },
    ],
    voice: 'Its best guess adds a second opinion, used only when your file agrees with the encoder.',
    camera: 'Follows two currents as they braid into one.',
    transition: 'Comes in as scene 7\'s outline dissolves. Leaves as the braided current dives on down.',
    water: 'A wake follows the two currents through the white gel.',
    particles: 'Two streams of particles that merge after a gate.',
    sound: 'Two lines of melody braid into one.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (wake)'],
  },
  {
    id: 'real-data',
    title: 'On real protein data',
    chapter: 'results',
    seconds: 12,
    depth: [0.84, 1],
    still: 0.9,
    screen: [
      { role: 'headline', text: 'Checked against real data.', cut: 'data.' },
      { role: 'label', text: 'Fulcher 2026' },
      { role: 'stat', text: '{ms:committed_fulcher}' },
      { role: 'label', text: 'of cells given an answer' },
      { role: 'stat', text: '{ms:correct_fulcher}' },
      { role: 'label', text: 'of those answers right, at the level stated' },
      { role: 'label', text: 'Khoury 2026' },
      { role: 'stat', text: '{ms:khoury_lymphoid}' },
      { role: 'label', text: 'of lymphoid cells put in the lymphoid lineage' },
      { role: 'stat', text: '{ms:khoury_myeloid}' },
      { role: 'label', text: 'of myeloid cells put in the myeloid lineage' },
      { role: 'caption', text: 'Development: these data were used while VivOME was built. Post-hoc: their labels had been read before.' },
    ],
    caveats: ['development', 'post-hoc'],
    voice: 'On real blood protein data, here is how often it answers, and how often those answers are right.',
    camera: 'Settles at the deepest point of the dive; the cards rise among the nearest cells.',
    transition: 'Leaves on a slow pan along the floor into scene 10.',
    water: 'The same white gel; at the deepest point the cells are closest and largest, and the far ones most softly blurred.',
    particles: 'Dense and close: cells and strands drift large around the cards.',
    sound: 'The music drops to a deep pulse; each number lands with a soft sonar ping.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)'],
  },
  {
    id: 'methods',
    title: 'Against established methods',
    chapter: 'results',
    seconds: 12,
    depth: [1, 0.9],
    still: 0.9,
    screen: [
      { role: 'headline', text: 'Measured against established methods.', cut: 'methods.' },
      { role: 'sub', text: 'On real protein data, VivOME is level with the best of them and ahead of the rest.' },
      { role: 'stat', text: '{ms:bm_khoury_baseline_favour} of {ms:bm_khoury_baseline_runs}' },
      { role: 'label', text: 'baseline runs favour VivOME on Khoury 2026' },
      { role: 'stat', text: '{ms:bm_fulcher_favour} of {ms:bm_fulcher_pairings}' },
      { role: 'label', text: 'paired comparisons favour VivOME on Fulcher 2026' },
      { role: 'caption', text: 'Still weak: CD8 T cells and dendritic cells, for every method tested.' },
      { role: 'caption', text: 'A sealed test on sorted cells: {ms:open_sorted_test}' },
    ],
    caveats: ['post-hoc', 'in-sample', 'pending'],
    voice: 'Against established methods, on real protein data, it is level with the best and ahead of the rest. Where it is still weak, it says so.',
    camera: 'A slow pan along the floor past the methods, each a bubble with its name.',
    transition: 'Leaves as the camera turns up towards the light.',
    water: 'The same white gel; the cells begin to recede as the camera turns to rise.',
    particles: 'The methods rise past the camera as bubbles, each with its name: scANVI, MaxFuse, scGLUE, Harmony, Seurat, PCA and correlation.',
    sound: 'The pulse continues under a lighter counter-melody: the rise begins.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)'],
  },
  {
    id: 'atlas',
    title: 'In your browser',
    chapter: 'use',
    seconds: 10,
    depth: [0.6, 0.25],
    still: 0.88,
    screen: [
      { role: 'headline', text: 'Label your own data.', cut: 'data.' },
      { role: 'sub', text: 'Send a DIA-NN, FragPipe or CSV file from the Atlas page. Your cells land on the reference, each with its answer or the reason for none.' },
      { role: 'chip', text: 'The PBMC240 example file' },
      { role: 'caption', text: 'Answered by {fact:model_name}, atlas {fact:atlas_version}' },
    ],
    voice: 'It runs online. Send your file from the Atlas page, and your cells land on the map, each with its answer.',
    camera: 'Rises through the water towards a browser window floating near the surface.',
    transition: 'Leaves as the camera keeps rising and breaks the surface.',
    water: 'A wake: the file leaves a trail of ripples as it drops into the atlas.',
    particles: 'The file\'s cells fly in as beads and land in their places.',
    sound: 'Bright plucks as each cell lands; the theme returns in full.',
    drawn: 'The map is the reference sample, and the beads are the PBMC240 example file\'s cells with the answers the served model gave them, in the Atlas page\'s legend (web/data/workflow.json).',
    tools: ['HyperFrames', 'GSAP', 'three.js water (wake)', 'canvas'],
  },
  {
    id: 'light',
    title: 'Into the light',
    chapter: 'use',
    seconds: 6,
    depth: [0.2, 0],
    still: 0.8,
    screen: [
      { role: 'wordmark', text: 'VivOME' },
      { role: 'headline', text: 'No cell placed without evidence.', cut: 'evidence.' },
      { role: 'chip', text: 'Explore the atlas' },
      { role: 'chip', text: 'Label your data' },
      { role: 'caption', text: 'vivome-atlas.pages.dev' },
    ],
    voice: 'Bring your protein cells up into the light. VivOME: no cell placed without evidence.',
    camera: 'Rushes up and breaks the surface, then settles.',
    transition: 'The splash clears to white and the end card holds.',
    water: 'The waterline sweeps down the frame as we surface and settles low; rain rings the water under the end card.',
    particles: 'Bubbles rise and burst at the surface, then the frame clears.',
    sound: 'A swell, a splash as we break the surface, and a bright final chord. Silence on the end card.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (rain)'],
  },
];

export const STARTS = FRAMES.reduce((acc, f, i) => {
  acc.push(i === 0 ? 0 : acc[i - 1] + FRAMES[i - 1].seconds);
  return acc;
}, []);

export const TOTAL = STARTS[STARTS.length - 1] + FRAMES[FRAMES.length - 1].seconds;

// A scene's number (1-based, two digits for file names) and its range.
export const sceneNumber = (i) => String(i + 1).padStart(2, '0');
export const frameRange = (i) => [STARTS[i], STARTS[i] + FRAMES[i].seconds];
export const rangeText = (i) => frameRange(i).map(formatClock).join(' to ');

// When scene i's still is taken, in film seconds, on the 30 fps frame grid.
export const stillTime = (i) => Math.round((STARTS[i] + FRAMES[i].still * FRAMES[i].seconds) * 30) / 30;

// Where the film is at t seconds: the scene and its progress.
export function locate(t) {
  const time = Math.min(TOTAL, Math.max(0, Number.isFinite(t) ? t : 0));
  let index = FRAMES.length - 1;
  for (let i = 0; i < FRAMES.length; i += 1) {
    if (time < STARTS[i] + FRAMES[i].seconds) { index = i; break; }
  }
  const local = time - STARTS[index];
  return { index, id: FRAMES[index].id, local, p: Math.min(1, local / FRAMES[index].seconds) };
}

// ---- number slots ----

const SLOT = /\{(ms|fact):([a-z0-9_]+)\}/g;

export function slotsIn(text) {
  return [...String(text ?? '').matchAll(SLOT)].map(([token, source, key]) => ({ token, source, key, id: `${source}:${key}` }));
}

// Every slot a scene shows or says, once each, in order.
export function frameSlots(frame) {
  const seen = new Map();
  for (const text of [...frame.screen.map((s) => s.text), frame.voice]) {
    for (const slot of slotsIn(text)) if (!seen.has(slot.id)) seen.set(slot.id, slot);
  }
  return [...seen.values()];
}

// Where a manifest fact's value lives (the ones the film shows).
export const FACT_FIELDS = {
  model_name: 'model.name',
  atlas_version: 'atlas_version',
};

const MANIFEST_FILE = 'web/data/atlas_manifest.json';
const MANUSCRIPT_FILE = 'web/data/manuscript.json';

const unescape = (html) => String(html).replace(/<[^>]+>/g, '')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');

// A slot's text, plain: what a render bakes in and what the page shows.
export function slotText(slot, { manifest, manuscript } = {}) {
  if (slot.source === 'ms') return formatManuscript(recordFor(manuscript, slot.key));
  if (!(slot.key in FACT_FIELDS)) return PENDING_LABEL;
  return unescape(factText(manifest, slot.key));
}

export function slotMeasured(slot, sources = {}) {
  if (slot.source === 'ms') return isMeasured(recordFor(sources.manuscript, slot.key));
  return slotText(slot, sources) !== PENDING_LABEL;
}

// Where a slot's value came from: the record it was read through, and the
// file and field that record names.
export function slotSource(slot, { manuscript } = {}) {
  if (slot.source === 'fact') {
    return { record: MANIFEST_FILE, file: MANIFEST_FILE, field: FACT_FIELDS[slot.key] ?? 'no such fact' };
  }
  const record = recordFor(manuscript, slot.key);
  const basis = isMeasured(record) ? String(record.basis ?? '') : String(record?.note ?? 'no record');
  const cut = basis.indexOf(': ');
  return {
    record: `${MANUSCRIPT_FILE}#${slot.key}`,
    file: cut > 0 ? basis.slice(0, cut) : basis,
    field: cut > 0 ? basis.slice(cut + 2) : '',
  };
}

// Text with its slots filled, as escaped HTML for the page. Each number
// goes through its own guard and names its source on hover.
export function fillSlots(text, sources = {}) {
  let out = '';
  let last = 0;
  for (const slot of slotsIn(text)) {
    const at = String(text).indexOf(slot.token, last);
    out += escapeHtml(String(text).slice(last, at));
    const shown = slot.source === 'ms'
      ? msFact(sources.manuscript, slot.key)
      : (slot.key in FACT_FIELDS ? factText(sources.manifest, slot.key) : `<span class="pending">${PENDING_LABEL}</span>`);
    const src = slotSource(slot, sources);
    out += `<span class="reel-num" title="${escapeHtml(`${src.file}${src.field ? `: ${src.field}` : ''}`)}">${shown}</span>`;
    last = at + slot.token.length;
  }
  return out + escapeHtml(String(text ?? '').slice(last));
}

// A headline with its accent word in the cut block.
export function headlineHtml(item, sources) {
  const html = fillSlots(item.text, sources);
  if (!item.cut) return html;
  const word = escapeHtml(item.cut);
  const at = html.lastIndexOf(word);
  return at < 0 ? html : `${html.slice(0, at)}<span class="cut">${word}</span>${html.slice(at + word.length)}`;
}

// ---- the page's markup (web/motion.html) ----

const chapterLabel = (id) => CHAPTERS.find((c) => c.id === id)?.label ?? id;

const ROLE_LABEL = {
  eyebrow: 'Eyebrow', headline: 'Headline', sub: 'Line', stat: 'Number', label: 'Label', caption: 'Caption',
  point: 'Point', tag: 'Tag', chip: 'Chip', wordmark: 'Wordmark',
};

function screenList(frame, sources) {
  return frame.screen.map((item) => {
    const text = item.role === 'headline' ? headlineHtml(item, sources) : fillSlots(item.text, sources);
    return `<li><span class="reel-role">${escapeHtml(ROLE_LABEL[item.role] ?? item.role)}</span><span class="reel-said">${text}</span></li>`;
  }).join('');
}

const caveatBead = (key) => (key in CAVEATS
  ? `<span class="bead caveat${key === 'pending' ? ' bead-open' : ''}" data-caveat="${escapeHtml(key)}" title="${escapeHtml(CAVEATS[key])}">${escapeHtml(key)}</span>`
  : '');

// Does a still's baked-in number still match the record? The render's
// sidecar (web/motion/frames/index.json) lists each one.
export function staleNumbers(still, sources) {
  return (still?.numbers ?? []).filter((n) => {
    const [source, key] = String(n.slot).split(':');
    return slotText({ source, key }, sources) !== n.text;
  });
}

// One scene: its still and everything the film's makers need beside it.
export function buildShot(i, sources = {}, still = null) {
  const frame = FRAMES[i];
  const n = sceneNumber(i);
  const notes = [
    ['Camera', frame.camera], ['Transition', frame.transition], ['Water', frame.water], ['Particles', frame.particles],
  ].map(([k, v]) => `<div><dt>${k}</dt><dd>${escapeHtml(v)}</dd></div>`).join('');
  const stale = still ? staleNumbers(still, sources) : [];
  const image = still?.file
    ? `<img src="motion/frames/${escapeHtml(still.file)}" width="1920" height="1080" alt="${escapeHtml(`Scene ${i + 1}, ${frame.title}: the rendered frame at ${formatClock(still.at)}.`)}" loading="${i < 2 ? 'eager' : 'lazy'}" decoding="async">`
    : '<div class="reel-missing"><span class="pending">Not rendered yet</span></div>';
  return `
    <article class="reel-shot" id="scene-${n}" aria-labelledby="scene-${n}-title">
      <figure class="reel-still">
        ${image}
        <figcaption>
          <span class="reel-time">${escapeHtml(rangeText(i))}</span>
          ${still ? `<span>Still at ${escapeHtml(formatClock(still.at))}</span>` : ''}
          ${frame.tools.map((t) => `<span class="bead">${escapeHtml(t)}</span>`).join('')}
        </figcaption>
      </figure>
      <div class="reel-notes sheet">
        <span class="eyebrow">Scene ${i + 1} · ${escapeHtml(chapterLabel(frame.chapter))}</span>
        <h2 id="scene-${n}-title">${escapeHtml(frame.title)}</h2>
        ${stale.length ? `<p class="reel-stale">This still was rendered with an older value of ${stale.map((s) => escapeHtml(s.slot)).join(', ')}; render the stills again.</p>` : ''}
        <h3>On screen</h3>
        <ul class="reel-screen">${screenList(frame, sources)}</ul>
        ${frame.caveats?.length ? `<p class="reel-caveats">${frame.caveats.map(caveatBead).join('')}</p>` : ''}
        <h3>Voice-over</h3>
        <blockquote class="reel-voice">${fillSlots(frame.voice, sources)}</blockquote>
        <h3>Motion</h3>
        <dl class="reel-motion">${notes}</dl>
        <h3>Sound</h3>
        <p>${escapeHtml(frame.sound)}</p>
        ${frame.drawn ? `<p class="caption">${escapeHtml(frame.drawn)}</p>` : ''}
      </div>
    </article>`;
}

// The strip of every still, in order, each linking to its scene.
export function buildStrip(stills = []) {
  return FRAMES.map((frame, i) => {
    const still = stills[i];
    const thumb = still?.file
      ? `<img src="motion/frames/${escapeHtml(still.file)}" width="1920" height="1080" alt="" loading="lazy" decoding="async">`
      : '<span class="reel-thumb-missing"></span>';
    return `<li><a href="#scene-${sceneNumber(i)}">${thumb}<span class="reel-strip-time">${escapeHtml(formatClock(STARTS[i]))}</span><span class="reel-strip-title">${escapeHtml(frame.title)}</span></a></li>`;
  }).join('');
}

// The full voice-over, scene by scene.
export function buildScript(sources = {}) {
  const rows = FRAMES.map((frame, i) => `
    <tr>
      <td class="reel-script-time">${escapeHtml(rangeText(i))}</td>
      <td>${escapeHtml(frame.title)}</td>
      <td>${fillSlots(frame.voice, sources)}</td>
    </tr>`).join('');
  return `<table class="support-table reel-script"><thead><tr><th>Time</th><th>Scene</th><th>Voice-over</th></tr></thead><tbody>${rows}</tbody></table>`;
}
