// The Atlas page: loads the reference cells, draws them, and wires the
// sidebar, the viewer and the drawer (docs/web/atlas.md). three.js r128 is
// the page's classic <script> tag, read here as window.THREE.

import { escapeHtml } from '../panels.js';
import { plainName } from '../workflow-data.js';
import { mountExploreTab } from './explore-tab.js';
import {
  loadProfile, profileErrorHtml, profileLoadingHtml, profileProgressHtml, profileTableHtml,
} from './gene-profile.js';
import { createTooltip, hideLoading, showFailure } from './overlay.js';
import { atlasFrame, classCodes, classOrderFrom, parseMetadataCsv, sceneArray } from './reference-data.js';
import { createReferenceLayer } from './reference-layer.js';
import { pickScreen, projectAll } from './spatial.js';
import { createStage } from './stage.js';

const $ = (id) => document.getElementById(id);
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url.pathname.split('/').pop()} (${response.status}).`);
  return response.text();
}

// The reference, RNA cells first, then protein, in scene units.
async function loadReference() {
  const [rnaText, protText] = await Promise.all([
    fetchText(new URL('../../data/metadata_RNA_lat128.csv', import.meta.url)),
    fetchText(new URL('../../data/metadata_PROT_lat128.csv', import.meta.url)),
  ]);
  const rna = parseMetadataCsv(rnaText, 'rna');
  const prot = parseMetadataCsv(protText, 'prot');
  const order = classOrderFrom(rna, prot);
  const frame = atlasFrame(rna.raw, prot.raw);
  const n = rna.n + prot.n;
  const positions = new Float32Array(n * 3);
  positions.set(sceneArray(frame, rna.raw));
  positions.set(sceneArray(frame, prot.raw), rna.n * 3);
  const raw = new Float32Array(n * 3);
  raw.set(rna.raw);
  raw.set(prot.raw, rna.n * 3);
  const codes = new Uint8Array(n);
  codes.set(classCodes(rna, order));
  codes.set(classCodes(prot, order), rna.n);
  const modality = new Float32Array(n);
  modality.fill(1, rna.n);
  const origIndex = new Uint32Array(n);
  origIndex.set(rna.origIndex);
  origIndex.set(prot.origIndex, rna.n);
  const byClass = new Array(order.length).fill(0);
  const protByClass = new Array(order.length).fill(0);
  for (let i = 0; i < n; i += 1) (i < rna.n ? byClass : protByClass)[codes[i]] += 1;
  return {
    order, frame, n, nRna: rna.n, positions, raw, codes, modality, origIndex,
    counts: { rna: rna.n, prot: prot.n, byClass, protByClass },
  };
}

// The drawer over the viewer's right side.
function createDrawer() {
  const drawer = $('atlas-drawer');
  const close = () => { drawer.classList.remove('open'); drawer.setAttribute('aria-hidden', 'true'); };
  $('drawer-close').addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
  return {
    open(title, html) {
      $('drawer-title').textContent = title;
      $('drawer-body').innerHTML = html;
      drawer.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
    },
    body: (html) => { $('drawer-body').innerHTML = html; },
    close,
  };
}

async function start() {
  const THREE = window.THREE;
  if (!THREE || THREE.REVISION !== '128') throw new Error('three.js r128 did not load, so the atlas cannot be drawn.');
  const ref = await loadReference();
  const stage = createStage(THREE, $('three-canvas'), $('three-container'), { reduced });
  const layer = createReferenceLayer(THREE, stage, ref);
  mountExploreTab({ layer, order: ref.order, counts: ref.counts });
  const drawer = createDrawer();
  const tooltip = createTooltip();

  // Picking: every point's screen position, recomputed when the view moved.
  let screen = null;
  let stale = true;
  stage.rig.on('change', () => { stale = true; });
  new ResizeObserver(() => { stale = true; }).observe($('three-container'));
  function pickAt(clientX, clientY) {
    const rect = stage.renderer.domElement.getBoundingClientRect();
    if (stale || !screen) {
      screen = projectAll(ref.positions, ref.n, stage.viewProjection(), rect.width, rect.height, screen ?? undefined);
      stale = false;
    }
    return pickScreen(screen, ref.n, clientX - rect.left, clientY - rect.top, 8, layer.visible);
  }

  let hoverEvent = null;
  stage.rig.on('hover', (e) => {
    if (!hoverEvent) requestAnimationFrame(() => {
      const ev = hoverEvent;
      hoverEvent = null;
      const i = pickAt(ev.clientX, ev.clientY);
      if (i < 0) return tooltip.hide();
      const isProt = i >= ref.nRna;
      tooltip.show([
        `${isProt ? 'Protein cell (SCoPE2)' : 'RNA reference cell'}: ${plainName(ref.order[ref.codes[i]])}`,
        `PC1 ${ref.raw[i * 3].toFixed(2)}, PC2 ${ref.raw[i * 3 + 1].toFixed(2)}, PC3 ${ref.raw[i * 3 + 2].toFixed(2)}`,
        'Click for its gene profile',
      ], ev.clientX, ev.clientY);
    });
    hoverEvent = e;
  });
  stage.rig.on('leave', () => tooltip.hide());

  stage.rig.on('click', async (e) => {
    const i = pickAt(e.clientX, e.clientY);
    if (i < 0) return;
    const isProt = i >= ref.nRna;
    const modality = isProt ? 'prot' : 'rna';
    const name = plainName(ref.order[ref.codes[i]]);
    drawer.open(`${isProt ? 'Protein' : 'RNA'} cell: ${name}`, profileLoadingHtml(name, modality));
    try {
      const profile = await loadProfile(modality, ref.origIndex[i], (rows) => drawer.body(profileProgressHtml(rows)));
      drawer.body(`<p class="panel-note">${escapeHtml(Object.keys(profile).length.toLocaleString('en-US'))} genes.</p>${profileTableHtml(profile)}`);
    } catch (err) {
      drawer.body(profileErrorHtml(err));
    }
  });

  $('reset-view').addEventListener('click', () => stage.rig.reset());
  $('sidebar-toggle').addEventListener('click', () => {
    const collapsed = $('controls-panel').classList.toggle('collapsed');
    $('sidebar-toggle').setAttribute('aria-expanded', String(!collapsed));
    $('sidebar-toggle').textContent = collapsed ? 'Show controls' : 'Hide controls';
  });

  hideLoading();
  // A handle for checking the page from the browser's console.
  window.vivomeAtlas = { stage, layer, reference: ref };
}

start().catch(showFailure);
