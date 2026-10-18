// The Motion page's storyboard (web/motion.html): the film's twelve
// scenes, their timings, what each shows and says, and how it moves.
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

// Each scene: its length in seconds (the camera's journey to it, then its
// card), its chapter, the card its words and diagrams sit on (`card`: the
// site's white `sheet` or its `liquid` glass, odd scenes white, even scenes
// glass), and when its still is taken (a share of the card). `screen` is
// the on-screen text, line by line; a headline's `cut` is its one word in
// the accent block. `said` is the voice line as the voice speaks it: its
// length and when each of its phrases starts (`phrasesOf`), in seconds
// after the line starts, measured by motion/scripts/voice.mjs; the
// pictures inside the card act out each phrase as it is said.
export const FRAMES = [
  {
    id: 'surface',
    title: 'The surface',
    chapter: 'problem',
    card: 'sheet',
    seconds: 10,
    still: 0.75,
    screen: [
      { role: 'eyebrow', text: 'Single-cell proteomics' },
      { role: 'headline', text: 'Proteins, measured one cell at a time.', cut: 'time.' },
      { role: 'caption', text: 'One cell of the PBMC240 example file' },
    ],
    voice: 'Mass spectrometry can now measure the proteins inside single cells, one cell at a time.',
    said: { seconds: 5.33, at: [0, 4.06] },
    camera: 'Descends through the surface in the rain, then stands still while the card is on.',
    transition: 'Opens from white light as the camera comes down through the surface. At the close the bars fold back into the cell, which settles at the top of the card, where scene 2 opens on it.',
    water: 'Rain on the surface: each drop sends rings across the white gel, and a fine white waterline runs along the top.',
    particles: 'Sparse. Cells and molecules drift up towards the light, each keeping its size.',
    sound: 'A low pad fades in from silence; one soft piano note as the title lands.',
    drawn: 'One cell of the PBMC240 example file: its proteins as bars, long where much was measured, a striped stub where nothing was (web/data/workflow.json). Two more cells queue behind it as the voice says one cell at a time.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (rain)', 'canvas'],
  },
  {
    id: 'unnamed',
    title: 'Without names',
    chapter: 'problem',
    card: 'liquid',
    seconds: 13,
    still: 0.8,
    screen: [
      { role: 'headline', text: 'But they arrive without names.', cut: 'names.' },
      { role: 'sub', text: 'Few protein datasets come labelled, and every lab detects a different set of proteins.' },
      { role: 'tag', text: 'Unnamed' },
    ],
    voice: 'But those cells arrive without names. Labelled protein references are few, and every lab detects a different set of proteins.',
    said: { seconds: 7.51, at: [0, 2.57, 4.96] },
    camera: 'Travels down through the particles, then stands still.',
    transition: 'Opens on the cell where scene 1 left it. At the close the first cell\'s column of proteins grows to full height, where scene 3\'s matrix begins.',
    water: 'The same white gel, still; the waterline is far above now.',
    particles: 'Protein cells in green, each given an empty name tag as the voice says they have no names, then each its own short column of the proteins measured in it.',
    sound: 'The pad carries on, a little lower, as the camera goes under.',
    drawn: 'Each cell\'s column marks the proteins measured in one cell of the PBMC240 example file (web/data/workflow.json): the sets differ from cell to cell.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'gaps',
    title: 'Mostly missing',
    chapter: 'problem',
    card: 'sheet',
    seconds: 14,
    still: 0.8,
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
    said: { seconds: 4.27, at: [0, 2.42] },
    camera: 'Travels to the right through the particles, then stands still.',
    transition: 'Opens on the column scene 2 left, which takes its place as the matrix\'s first. At the close the measured tiles lift off as dots and gather at the matrix\'s right edge, where scene 4\'s atlas begins.',
    water: 'The white gel; the far cells are soft behind the cards.',
    particles: 'The molecular network loses links as values drop out.',
    sound: 'The pad thins to one held note as the missing values fall away.',
    drawn: 'The matrix: the PBMC240 example file\'s own values, one column per cell and one row per protein, as the Workflow page shows them (web/data/workflow.json). Each tile lights as it is read; as the voice says much of it is empty, the missing ones fall away.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'rna',
    title: 'RNA has names',
    chapter: 'solution',
    card: 'liquid',
    seconds: 12,
    still: 0.76,
    screen: [
      { role: 'headline', text: 'RNA atlases already name their cells.', cut: 'cells.' },
      { role: 'stat', text: '{ms:ref_cells}' },
      { role: 'label', text: 'RNA cells, each one labelled' },
      { role: 'caption', text: 'in {ms:ref_classes} blood and immune cell types, from Tabula Sapiens' },
    ],
    voice: 'Single-cell RNA is different. Its atlases are large, and every cell in them has a name.',
    said: { seconds: 5.89, at: [0, 2.58, 4.3] },
    camera: 'Travels down and to the right, then stands still.',
    transition: 'Opens on scene 3\'s dots, gathered as an orange cloud. At the close a band of the atlas\'s cells gathers along the map\'s top edge, where scene 5\'s wordmark forms from them.',
    water: 'The same white gel. The cells pass at their own depths as the camera travels, the near ones faster.',
    particles: 'RNA strands in red and gold thread through the shoal.',
    sound: 'A warm chord: the first hint of the theme.',
    drawn: 'The atlas in 3D, turning slowly: a sample of the reference\'s own cells at their coordinates in the atlas\'s projection (web/data/workflow.json). They stream out of the cloud as RNA, in orange; as the voice says every cell has a name, each takes its type\'s colour in the atlas palette and the big types are named.',
    tools: ['HyperFrames', 'GSAP', 'three.js atlas', 'three.js water (still)'],
  },
  {
    id: 'vivome',
    title: 'VivOME',
    chapter: 'solution',
    card: 'sheet',
    seconds: 18,
    still: 0.85,
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
    said: { seconds: 11.5, at: [0, 3.9, 7.25, 8.64, 9.9] },
    camera: 'Travels down, then stands still on the wordmark and the idea.',
    transition: 'Opens on scene 4\'s band of cells, which flows into the wordmark as it forms. At the close dots leave the link and line up as a row of tiles under the card, where scene 6\'s matrix fills from.',
    water: 'A slow wake ripples through the white gel as the wordmark forms.',
    particles: 'The network links up across the frame as the link forms; dots run along it from the RNA side to the protein side.',
    sound: 'The theme enters in full: a rising arpeggio as the wordmark appears.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (wake)', 'canvas'],
  },
  {
    id: 'built-for-gaps',
    title: 'Built for gaps',
    chapter: 'new',
    card: 'liquid',
    seconds: 14,
    still: 0.8,
    screen: [
      { role: 'headline', text: 'Built for missing values.', cut: 'values.' },
      { role: 'point', text: 'It knows which proteins were never measured.' },
      { role: 'point', text: 'It scales each protein within your file.' },
      { role: 'point', text: 'It borrows from similar cells in the same file.' },
      { role: 'point', text: '{ms:wf_members} encoders answer together.' },
    ],
    voice: 'It is built for gaps: it knows which proteins were never measured, scales each one within your file, and asks {ms:wf_members} encoders to answer together.',
    said: { seconds: 8.19, at: [0, 1.65, 3.95, 5.93] },
    camera: 'Travels down and to the left, then stands still.',
    transition: 'Opens on the row of tiles from scene 5, which rises and fills down into the matrix. At the close the encoders\' merged answers gather at the matrix\'s left edge, where scene 7\'s map grows from.',
    water: 'The white gel, clearer than in scene 3; the far cells are soft behind the cards.',
    particles: 'The rows stream into the encoders inside the card, one for each of the served model\'s members, and their answers merge into one.',
    sound: 'Soft tones, one per encoder, resolving into one chord.',
    drawn: 'The matrix: the same cells and proteins as scene 3. As each point is said, its step: a mask marks each gap; a bright band sweeps down as each protein is scaled within the file, then across as each cell borrows from similar cells (web/data/workflow.json).',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'answers',
    title: 'Honest answers',
    chapter: 'new',
    card: 'sheet',
    seconds: 14,
    still: 0.81,
    screen: [
      { role: 'headline', text: 'When unsure, it says so.', cut: 'so.' },
      { role: 'label', text: 'Cell type' },
      { role: 'label', text: 'Group' },
      { role: 'label', text: 'Lineage' },
      { role: 'label', text: 'No answer, and the reason' },
      { role: 'caption', text: 'Cells of the PBMC240 example file, and the answers VivOME gave them.' },
    ],
    voice: 'Every cell gets the most precise answer the evidence allows: a cell type, its group, its lineage, or no answer, and the reason why.',
    said: { seconds: 8.23, at: [0, 3.93, 4.88, 5.55, 6.29, 7.28] },
    camera: 'Travels to the left, then stands still on the reference map.',
    transition: 'Opens on scene 6\'s merged answers, out of which the map grows. At the close the last cell\'s best guess splits into two strokes that run to the map\'s edge, where scene 8\'s two currents start.',
    water: 'Still gel, so the diagram reads cleanly.',
    particles: 'Few and slow, kept to the edges.',
    sound: 'Descending notes, one per rung, and a soft stop on no answer.',
    drawn: 'Manim draws the reference map and four real cells of the example file. As the voice names each rung, that cell\'s outline narrows from the widest set its types belong to down to its set of plausible types, or widens when several types fit, and its answer shows (web/data/workflow.json).',
    tools: ['Manim', 'HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'second-opinion',
    title: 'A second opinion',
    chapter: 'new',
    card: 'liquid',
    seconds: 12,
    still: 0.7,
    screen: [
      { role: 'headline', text: 'One best guess, with a second opinion.', cut: 'opinion.' },
      { role: 'label', text: 'The encoder' },
      { role: 'label', text: 'Correlation to each RNA type\'s average' },
      { role: 'label', text: 'Used only when your file agrees with the encoder' },
      { role: 'label', text: 'Best guess' },
      { role: 'chip', text: 'New in {fact:model_name}' },
    ],
    voice: 'Its best guess adds a second opinion, used only when your file agrees with the encoder.',
    said: { seconds: 5.16, at: [0, 2.5] },
    camera: 'Travels down and to the right, then stands still on the two currents.',
    transition: 'Opens on scene 7\'s two strokes, which start the two currents. At the close the particles pack into a block of a hundred, where scene 9\'s first result fills from.',
    water: 'A wake follows the two currents through the white gel.',
    particles: 'Particles flow along both currents and gather at the gate; as the voice says when the second opinion is used, the gate appears, a meter fills to its mark, the gate opens, and they run on as one.',
    sound: 'Two lines of melody braid into one.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (wake)', 'canvas'],
  },
  {
    id: 'real-data',
    title: 'On real protein data',
    chapter: 'results',
    card: 'sheet',
    seconds: 19,
    still: 0.77,
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
    said: { seconds: 5.82, at: [0, 1.93, 3.86] },
    camera: 'Travels down to the deepest point of the dive and stands still there.',
    transition: 'Opens on scene 8\'s block, which becomes the first result\'s grid. At the close the grid\'s squares slide into a row under the results, where scene 10\'s methods line up.',
    water: 'The same white gel; at the deepest point the far cells are most softly blurred.',
    particles: 'Dense: cells and strands drift around the cards at their own depths.',
    sound: 'The music settles on a low, slow bass pulse under the numbers.',
    drawn: 'Each result from its own record (web/data/manuscript.json): as the voice says how often VivOME answers, a grid of a hundred squares fills to that share; as it says how often those answers are right, the right ones turn solid. Khoury 2026\'s two lineages fill as bars.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'methods',
    title: 'Against established methods',
    chapter: 'results',
    card: 'liquid',
    seconds: 19,
    still: 0.79,
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
    said: { seconds: 7.89, at: [0, 1.65, 3.29, 6.07, 7.19] },
    camera: 'Travels to the right along the floor, then stands still.',
    transition: 'Opens on scene 9\'s row, which rises to become the row of methods. At the close the squares gather into a file, where scene 11 opens on its file.',
    water: 'The same white gel, on the floor of the dive.',
    particles: 'The methods come in one after another, each with its name: scANVI, MaxFuse, scGLUE, Harmony, Seurat, PCA and correlation.',
    sound: 'The pulse continues under a lighter counter-melody: the rise begins.',
    drawn: 'One square for each baseline run and each paired comparison, filled where it favours VivOME, from the Manuscript page\'s records (web/data/manuscript.json); the types where every method is still weak as dashed rings in their atlas colours.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (still)', 'canvas'],
  },
  {
    id: 'atlas',
    title: 'In your browser',
    chapter: 'use',
    card: 'sheet',
    seconds: 14,
    still: 0.75,
    screen: [
      { role: 'headline', text: 'Label your own data.', cut: 'data.' },
      { role: 'sub', text: 'Send a DIA-NN, FragPipe or CSV file from the Atlas page. Your cells land on the reference, each with its answer or the reason for none.' },
      { role: 'chip', text: 'The PBMC240 example file' },
      { role: 'caption', text: 'Answered by {fact:model_name}, atlas {fact:atlas_version}' },
    ],
    voice: 'It runs online. Send your file from the Atlas page, and your cells land on the map, each with its answer.',
    said: { seconds: 6.14, at: [0, 1.47, 3.56, 5.16] },
    camera: 'Travels up and to the right towards the surface, then stands still on a browser window.',
    transition: 'Opens on scene 10\'s file, now the example file in the window. At the close a few landed cells rise to the window\'s top edge, where scene 12\'s bubbles start.',
    water: 'A wake: the file\'s cells leave a trail of ripples as they fly into the atlas.',
    particles: 'The file\'s cells fly out of it in 3D, with trails, and land in their places.',
    sound: 'Bright plucks as each cell lands; the theme returns in full.',
    drawn: 'The map is the reference sample in 3D, turning slowly, and the cells are the PBMC240 example file\'s, landing with the answers the served model gave them, in the Atlas page\'s looks (web/data/workflow.json).',
    tools: ['HyperFrames', 'GSAP', 'three.js atlas', 'three.js water (wake)'],
  },
  {
    id: 'light',
    title: 'Into the light',
    chapter: 'use',
    card: 'liquid',
    seconds: 10,
    still: 0.9,
    screen: [
      { role: 'wordmark', text: 'VivOME' },
      { role: 'headline', text: 'No cell placed without evidence.', cut: 'evidence.' },
      { role: 'chip', text: 'Explore the atlas' },
      { role: 'chip', text: 'Label your data' },
      { role: 'caption', text: 'vivome-atlas.pages.dev' },
    ],
    voice: 'Bring your protein cells up into the light. VivOME: no cell placed without evidence.',
    said: { seconds: 4.93, at: [0, 2.34, 3.1] },
    camera: 'Rises through the surface, then stands still under the end card.',
    transition: 'Opens on scene 11\'s cells, which rise as bubbles and burst at the wordmark as it forms. The end card stays to the end.',
    water: 'The waterline lies low in the frame now the camera has surfaced; rain rings the water under the end card.',
    particles: 'Bubbles rise and burst at the wordmark, then the frame clears.',
    sound: 'The music swells as the camera surfaces and resolves on a bright final chord, then fades to silence on the end card.',
    tools: ['HyperFrames', 'GSAP', 'three.js water (rain)', 'canvas'],
  },
];

export const STARTS = FRAMES.reduce((acc, f, i) => {
  acc.push(i === 0 ? 0 : acc[i - 1] + FRAMES[i - 1].seconds);
  return acc;
}, []);

export const TOTAL = STARTS[STARTS.length - 1] + FRAMES[FRAMES.length - 1].seconds;

// The film's rhythm. Before each scene the camera travels through the
// water to the scene's place (a journey; the first is the descent through
// the surface); then it stands still while the scene's card fades in where
// it is, holds and fades out. Nothing on a card moves while the camera
// does, and no card is on screen during a journey.
export const JOURNEY = 2.5;   // seconds of travel before scenes 2 to 12
export const OPENING = 2.0;   // the descent through the surface, before scene 1
export const FADE = 0.5;      // a card's fade in, and its fade out
export const VOICE_AT = 0.3;  // the voice starts this long after its card does
export const AFTER = 1.5;     // the least a card holds after its line ends
export const EXIT = 1.2;      // the card's closing picture, before its fade out

// A scene's number (1-based, two digits for file names) and its range.
export const sceneNumber = (i) => String(i + 1).padStart(2, '0');
export const frameRange = (i) => [STARTS[i], STARTS[i] + FRAMES[i].seconds];
export const rangeText = (i) => frameRange(i).map(formatClock).join(' to ');

// The journey before scene i, and its card: when it is on screen (film
// seconds, [arrive, depart]) and for how long.
export const journeyOf = (i) => (i === 0 ? OPENING : JOURNEY);
export const cardRange = (i) => [STARTS[i] + journeyOf(i), STARTS[i] + FRAMES[i].seconds];
export const cardLength = (i) => FRAMES[i].seconds - journeyOf(i);
// When scene i's voice line starts, in film seconds.
export const voiceStart = (i) => cardRange(i)[0] + VOICE_AT;

// A line's phrases: it splits after each comma, full stop, colon, semicolon,
// question or exclamation mark, so the phrases joined with spaces are the line.
export const phrasesOf = (text) => String(text).split(/(?<=[,.:;?!])\s+/);
// When phrase k of scene i's line is said, in seconds into its card.
export const cueTime = (i, k) => VOICE_AT + FRAMES[i].said.at[k];

// How visible scene i's card is, `local` seconds into it: it fades in, holds
// and fades out (the last card stays to the end).
export function cardOpacity(i, local) {
  const length = cardLength(i);
  if (local < 0 || local > length) return 0;
  const out = i === FRAMES.length - 1 ? 1 : (length - local) / FADE;
  return Math.max(0, Math.min(1, local / FADE, out));
}

// When scene i's still is taken, in film seconds, on the 30 fps frame grid.
export const stillTime = (i) => Math.round((cardRange(i)[0] + FRAMES[i].still * cardLength(i)) * 30) / 30;

// Where the film is at t seconds: the scene, its progress, and whether the
// camera is on its journey there or its card is on screen (`card`: seconds
// into the card).
export function locate(t) {
  const time = Math.min(TOTAL, Math.max(0, Number.isFinite(t) ? t : 0));
  let index = FRAMES.length - 1;
  for (let i = 0; i < FRAMES.length; i += 1) {
    if (time < STARTS[i] + FRAMES[i].seconds) { index = i; break; }
  }
  const local = time - STARTS[index];
  const card = local - journeyOf(index);
  return {
    index, id: FRAMES[index].id, local, p: Math.min(1, local / FRAMES[index].seconds),
    phase: card < 0 ? 'journey' : 'card', card,
  };
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

// The site's two cards (web/css/page.css), as the notes name them.
export const CARDS = {
  sheet: 'White cards: the site\'s sheet, with its soft blue halo',
  liquid: 'Liquid glass: the site\'s frosted glass over the gel',
};

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

// The film itself, under its player: its running time, from its sidecar
// (web/motion/film/index.json, written by motion/scripts/film.mjs), and a
// warning when a number baked into it, or the release it was made for, no
// longer matches the records, as each still has.
export function buildFilm(film, sources = {}) {
  if (!film || !Number.isFinite(film.seconds)) {
    return '<p class="reel-film-note"><span class="pending">The film\'s details did not load.</span></p>';
  }
  const stale = staleNumbers(film, sources);
  const made = sources.manuscript?.built_for;
  const elsewhere = made && film.built_for && JSON.stringify(film.built_for) !== JSON.stringify(made);
  const warning = stale.length
    ? `<p class="reel-stale">This film was rendered with an older value of ${stale.map((s) => escapeHtml(s.slot)).join(', ')}; render the film again.</p>`
    : elsewhere ? '<p class="reel-stale">This film was rendered for another release of the atlas; render the film again.</p>' : '';
  return `${warning}<p class="reel-film-note">The whole film, <strong>${escapeHtml(formatClock(Math.round(film.seconds)))}</strong>, with its voice-over and music. Its numbers are read from the same records as the stills below.</p>`;
}

// One scene: its still and everything the film's makers need beside it.
export function buildShot(i, sources = {}, still = null) {
  const frame = FRAMES[i];
  const n = sceneNumber(i);
  const notes = [
    ['Cards', CARDS[frame.card] ?? frame.card], ['Camera', frame.camera], ['Transition', frame.transition],
    ['Water', frame.water], ['Particles', frame.particles],
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
