// The Atlas page: loads the reference cells, draws them, and wires the
// sidebar, the viewer and the drawer (docs/web/atlas.md). three.js r128 is
// the page's classic <script> tag, read here as window.THREE. With
// ?organ=<id> it draws that organ's map instead (web/data/organs/), without
// labelling: Your data is blood's only.

import { escapeHtml } from '../panels.js';
import { plainName } from '../workflow-data.js';
import { createServiceState, mountDataTab } from './data-tab.js';
import { sidebarFor } from './director.js';
import { mountExploreTab } from './explore-tab.js';
import { createLanding } from './landing.js';
import { createServiceClient } from './service-client.js';
import {
  loadProfile, profileErrorHtml, profileLoadingHtml, profileProgressHtml, profileTableHtml,
} from './gene-profile.js';
import { createTooltip, hideLoading, showFailure } from './overlay.js';
import { createTypeLabels } from './type-labels.js';
import { mountViewControls } from './view-controls.js';
import { BLOOD, familiesOf, organCellLines, organFrom, organHref, organPalette, organPlainName } from './organs.js';
import { atlasFrame, classCodes, classOrderFrom, parseMetadataCsv, parseOrganCsv, sceneArray } from './reference-data.js';
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

// The organ maps on offer; none when the index cannot be read, so blood
// still loads.
async function loadOrganIndex() {
  try {
    const response = await fetch(new URL('../../data/organs/index.json', import.meta.url));
    return response.ok ? (await response.json()).organs ?? [] : [];
  } catch {
    return [];
  }
}

// An organ's map in the same shape as loadReference's: RNA cells only, its
// own class order, colours by family and plain names.
async function loadOrganReference(organ) {
  const rna = parseOrganCsv(await fetchText(new URL(`../../data/${organ.file}`, import.meta.url)), organ.class_order);
  const order = organ.class_order;
  const frame = atlasFrame(rna.raw);
  const byClass = new Array(order.length).fill(0);
  for (let i = 0; i < rna.n; i += 1) byClass[rna.classIdx[i]] += 1;
  return {
    order, frame, n: rna.n, nRna: rna.n,
    positions: sceneArray(frame, rna.raw), raw: rna.raw, codes: rna.classIdx,
    modality: new Float32Array(rna.n), origIndex: rna.origIndex,
    counts: { rna: rna.n, prot: 0, byClass, protByClass: new Array(order.length).fill(0) },
    colours: organPalette(order, organ.hierarchy), nameOf: organPlainName,
    families: familiesOf(order, organ.hierarchy), organ,
  };
}

// The organ chooser at the top of Explore. Choosing another organ loads its
// page; an organ's map hides what only blood has (protein cells, Your data).
function mountOrganChooser(organs, organ) {
  const select = $('organ-select');
  select.innerHTML = [{ id: BLOOD, name: 'Blood' }, ...organs].map((o) => `<option value="${escapeHtml(o.id)}">${
    escapeHtml(o.id === BLOOD ? 'Blood' : `${o.name} (map only)`)}</option>`).join('');
  select.value = organ ? organ.id : BLOOD;
  select.addEventListener('change', () => location.assign(organHref(location.href, select.value)));
  if (!organ) return;
  $('organ-note').innerHTML = `Map only: files cannot be labelled against the ${escapeHtml(organ.name.toLowerCase())} yet, `
    + 'because its reference missed its checks (<a href="manuscript.html#organs">why</a>). Colours keep each family of types together.';
  document.title = `Atlas · ${organ.name} · VivOME`;
  document.body.classList.add('organ-map');
  for (const id of ['tab-data', 'prot-toggle-row', 'prot-well']) $(id).hidden = true;
}

// The drawer over the viewer's right side. While it is open the viewer is
// marked, so the controls in its right corners move out from under it.
function createDrawer() {
  const drawer = $('atlas-drawer');
  const close = () => {
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    $('three-container').classList.remove('drawer-open');
  };
  $('drawer-close').addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
  return {
    open(title, html) {
      $('drawer-title').textContent = title;
      $('drawer-body').innerHTML = html;
      drawer.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
      $('three-container').classList.add('drawer-open');
    },
    body: (html) => { $('drawer-body').innerHTML = html; },
    close,
  };
}

async function start() {
  const THREE = window.THREE;
  if (!THREE || THREE.REVISION !== '128') throw new Error('three.js r128 did not load, so the atlas cannot be drawn.');
  const organs = await loadOrganIndex();
  const organ = organFrom(location.search, organs);
  const ref = organ ? await loadOrganReference(organ) : await loadReference();
  mountOrganChooser(organs, organ);
  const stage = createStage(THREE, $('three-canvas'), $('three-container'), { reduced });
  const layer = createReferenceLayer(THREE, stage, ref);
  const labels = createTypeLabels({ stage, ref, layer, container: $('type-labels') });
  mountExploreTab({
    layer, order: ref.order, counts: ref.counts, colours: ref.colours, nameOf: ref.nameOf, families: ref.families,
    onChange: () => labels.refresh(),
  });
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

  // The Your data tab and the landing.
  const client = createServiceClient();
  const service = createServiceState();
  const landing = createLanding({
    THREE, stage, ref, reference: layer, drawer, client, reduced,
    serviceUrl: service.url,
    limits: service.limits,
    options: () => ({ modality: $('modality').value, restrict: $('restrict').checked }),
  });
  const dataTab = mountDataTab({ landing, client, service, acceptsFiles: !organ });
  mountViewControls({ stage, layer, landing, labels });
  const tabs = { explore: [$('tab-explore'), $('panel-explore')], data: [$('tab-data'), $('panel-data')] };
  function showTab(which) {
    if (organ && which === 'data') return; // an organ's map labels no file
    for (const [key, [tab, panel]] of Object.entries(tabs)) {
      const on = key === which;
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;
      panel.hidden = !on;
    }
    if (which === 'data') dataTab.open();
  }
  dataTab.onShow = () => showTab('data');
  $('tab-explore').addEventListener('click', () => showTab('explore'));
  $('tab-data').addEventListener('click', () => showTab('data'));
  $('controls-panel').querySelector('[role="tablist"]').addEventListener('keydown', (e) => {
    if (organ || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return;
    const next = $('tab-explore').getAttribute('aria-selected') === 'true' ? 'data' : 'explore';
    showTab(next);
    tabs[next][0].focus();
  });
  // atlas.html#your-data and #labels open the tab (the other pages link
  // here this way); #labels scrolls to the supported label space.
  function fromHash() {
    if (organ) return;
    if (location.hash === '#your-data' || location.hash === '#labels') {
      showTab('data');
      if (location.hash === '#labels') {
        $('labels-fold').open = true;
        $('labels').scrollIntoView({ block: 'start' });
      }
    }
  }
  window.addEventListener('hashchange', fromHash);
  fromHash();

  let hoverEvent = null;
  stage.rig.on('hover', (e) => {
    if (!hoverEvent) requestAnimationFrame(() => {
      const ev = hoverEvent;
      hoverEvent = null;
      const mine = landing.pick(ev.clientX, ev.clientY);
      if (mine >= 0) return tooltip.show([landing.describe(mine), 'Click for its answer'], ev.clientX, ev.clientY);
      const i = pickAt(ev.clientX, ev.clientY);
      if (i < 0) return tooltip.hide();
      if (organ) return tooltip.show(organCellLines(organ, ref.order[ref.codes[i]]), ev.clientX, ev.clientY);
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
    const mine = landing.pick(e.clientX, e.clientY);
    if (mine >= 0) return landing.select(mine);
    const i = pickAt(e.clientX, e.clientY);
    if (i < 0) {
      // A click on empty space lets go of the selected cell.
      if (landing.current >= 0) {
        landing.deselect();
        landing.openResults();
      }
      return;
    }
    if (organ) {
      const [title, family] = organCellLines(organ, ref.order[ref.codes[i]]);
      drawer.open(title, `<p class="panel-note">${escapeHtml(family)}.</p>`
        + '<p class="panel-note">This map shows where each reference cell sits; gene profiles are kept for blood only.</p>');
      return;
    }
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
  function setSidebar(open) {
    $('controls-panel').classList.toggle('collapsed', !open);
    $('sidebar-toggle').setAttribute('aria-expanded', String(open));
    $('sidebar-toggle').textContent = open ? 'Hide controls' : 'Show controls';
  }
  const sidebarOpen = () => !$('controls-panel').classList.contains('collapsed');
  // Folded away while an answer plays (director.js, sidebarFor); the button
  // opens or closes it any time.
  let folded = false;
  $('sidebar-toggle').addEventListener('click', () => {
    folded = false;
    setSidebar(!sidebarOpen());
  });
  landing.onChange((st) => {
    const next = sidebarFor(st, { open: sidebarOpen(), folded });
    folded = next.folded;
    if (next.open !== sidebarOpen()) setSidebar(next.open);
  });

  hideLoading();
  // A handle for checking the page from the browser's console.
  window.vivomeAtlas = { stage, layer, reference: ref, landing, organ };
}

start().catch(showFailure);
