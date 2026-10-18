// The Motion page (web/motion.html): the film's storyboard, one scene at a
// time, beside the still rendered for it (docs/web/motion.md).
//
// The words, timings and notes are web/js/reel-frames.js; the stills and
// their sidecar are web/motion/frames/ (motion/scripts/stills.mjs). Numbers
// in the notes go through the site's guards (msFact, factText): a failed
// load shows Pending and an error, never a stale number. A still whose
// baked-in number no longer matches its record says so.

import { loadManifest } from './manifest.js';
import { checkSync, loadManuscript } from './manuscript-data.js';
import { errorPanel } from './panels.js';
import { FRAMES, TOTAL, buildScript, buildShot, buildStrip } from './reel-frames.js';
import { formatClock } from './timeline.js';

const $ = (id) => document.getElementById(id);

async function loadStills(url = './motion/frames/index.json') {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`The stills' list failed to load: ${response.status} ${response.statusText}`);
  const sidecar = await response.json();
  if (!Array.isArray(sidecar?.frames)) throw new Error('The stills\' list has no frames');
  return sidecar;
}

function show(sources, sidecar) {
  const byId = new Map((sidecar?.frames ?? []).map((f) => [f.id, f]));
  const stills = FRAMES.map((f) => byId.get(f.id) ?? null);
  $('reel-strip').innerHTML = buildStrip(stills);
  $('reel-shots').innerHTML = FRAMES.map((_, i) => buildShot(i, sources, stills[i])).join('');
  $('reel-script').innerHTML = buildScript(sources);
}

$('reel-total').textContent = formatClock(TOTAL);

Promise.all([loadManifest(), loadManuscript()]).then(async ([manifest, manuscript]) => {
  const sync = checkSync(manifest, manuscript);
  if (!sync.ok) throw new Error(`This page's data files are from different releases: ${sync.problems.join('; ')}`);
  let sidecar = null;
  try {
    sidecar = await loadStills();
  } catch (err) {
    $('reel-error').innerHTML = errorPanel(err);
  }
  show({ manifest, manuscript }, sidecar);
}).catch((err) => {
  $('reel-error').innerHTML = errorPanel(err);
  show({}, null);
});
