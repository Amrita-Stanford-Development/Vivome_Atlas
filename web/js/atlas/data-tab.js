// The Atlas page's Your data tab: the service line (and an own copy's
// address), the recorded example, sending a file, the results card and the
// supported label space. The landing (landing.js) does the drawing; this tab
// holds the controls and asks the service whether it is ready, only when the
// tab is first opened, so a visit to the map never wakes the service.

import { PENDING_LABEL, formatCount, isMeasured, loadManifest } from '../manifest.js';
import { buildSupportedLabelSpace, errorPanel, escapeHtml } from '../panels.js';
import { loadWorkflow, wfFact } from '../workflow-data.js';
import { coordinatesCompatible } from './answers.js';
import { DEFAULT_SERVICE_URL, explainFailure, rememberServiceUrl, serviceUrlFrom } from './service-client.js';

const $ = (id) => document.getElementById(id);
const storage = () => {
  try { return window.localStorage; } catch { return null; }
};

// The service's address and its limits, shared with the landing.
export function createServiceState() {
  const input = $('service-url');
  input.value = serviceUrlFrom(storage()) || DEFAULT_SERVICE_URL;
  const state = { ready: false, status: null, limits: null };
  return {
    state,
    url: () => input.value.trim().replace(/\/+$/, ''),
    limits: () => state.limits ?? {},
  };
}

export function mountDataTab({ landing, client, service }) {
  const line = (text, kind = null) => {
    const el = $('service-status');
    el.textContent = text;
    el.classList.toggle('is-ready', kind === 'ready');
    el.classList.toggle('is-down', kind === 'down');
  };
  let opened = false;
  let workflow = null;

  async function checkService() {
    rememberServiceUrl(storage(), $('service-url').value.trim());
    service.state.ready = false;
    line('Checking…');
    update();
    const slow = setTimeout(() => line('Waking the service: after a quiet spell this takes up to a minute.'), 3000);
    try {
      const status = await client.status(service.url());
      clearTimeout(slow);
      if (status?.status !== 'ready') {
        line(`The service is running but cannot label yet: ${status?.reason ?? 'no reason given'}.`, 'down');
      } else {
        service.state.ready = true;
        service.state.status = status;
        if (status.limits) {
          service.state.limits = { ...service.state.limits, max_cells: status.limits.max_cells, max_upload_mb: status.limits.max_upload_mb };
        }
        const map = coordinatesCompatible(status.pipeline_version) ? ''
          : ' Its model draws a different map, so your cells will be listed, not placed.';
        line(`Ready: ${status.model_version ?? 'the service'} (pipeline ${status.pipeline_version ?? 'unknown'}).${map}`, 'ready');
      }
    } catch (err) {
      clearTimeout(slow);
      line(explainFailure(err, service.url()), 'down');
    }
    update();
  }

  // The first time the tab opens: the service's status, the workflow data
  // (limits, the example's numbers) and the supported label space.
  async function open() {
    if (opened) return;
    opened = true;
    checkService();
    try {
      workflow = await loadWorkflow();
      const value = (key) => (isMeasured(workflow.service?.[key]) ? workflow.service[key].value : undefined);
      service.state.limits = {
        max_cells: value('max_cells'), max_upload_mb: value('max_mb'), min_cells: value('min_cells'),
        ...(service.state.limits ?? {}),
      };
      for (const el of document.querySelectorAll('#panel-data [data-wf]')) el.innerHTML = wfFact(workflow, el.dataset.wf);
    } catch (err) {
      for (const el of document.querySelectorAll('#panel-data [data-wf]')) el.textContent = PENDING_LABEL;
    }
    loadManifest().then((manifest) => {
      $('supported').innerHTML = buildSupportedLabelSpace(manifest);
    }).catch((err) => {
      $('supported').innerHTML = errorPanel(err);
    });
  }

  function fileResult(st) {
    if (st.name === 'checking') return '<p class="panel-note">Checking the file…</p>';
    if (st.name === 'failed' && st.stage === 'check') return errorPanel(st.error);
    const c = st.check;
    if (!c) return '';
    const problems = (c.problems ?? []).map((p) => `<p class="panel-error">${escapeHtml(p)}</p>`).join('');
    return `<dl>
        <dt>File</dt><dd>${escapeHtml(c.name)} (${escapeHtml((c.size / 1024).toFixed(1))} KB)</dd>
        <dt>Cells</dt><dd>${formatCount(c.cells)}</dd>
        <dt>Feature rows</dt><dd>${formatCount(c.features)}</dd>
      </dl>${problems}`;
  }

  // Buttons and cards follow the landing's state.
  function update(st = landing.state) {
    const name = st.name;
    const resting = ['idle', 'chosen', 'interactive', 'failed'].includes(name);
    $('project').disabled = !(name === 'chosen' && st.check?.ok && service.state.ready);
    $('cancel').hidden = !['sending', 'working', 'busy'].includes(name) || st.example;
    $('watch-example').disabled = !resting;
    $('send-example').disabled = !(resting && service.state.ready);
    $('matrix').disabled = !resting;
    $('file-result').innerHTML = fileResult(st);
    const run = landing.run;
    const shown = run && ['interactive', 'settling', 'flying', 'receipt', 'finishing'].includes(name);
    $('results-card').hidden = !shown;
    if (shown) {
      $('results-note').textContent = run.source === 'recorded'
        ? 'The recorded example: answers from the served model, no file sent.'
        : `${formatCount(run.cells.length)} cells from ${st.file?.name ?? 'your file'}.`;
      $('outcome-chips').innerHTML = landing.chips();
      $('download').hidden = run.source !== 'service';
    }
  }
  landing.onChange((st) => update(st));

  $('check-service').addEventListener('click', checkService);
  $('service-url').addEventListener('change', checkService);
  $('matrix').addEventListener('change', () => {
    const file = $('matrix').files[0];
    if (file) landing.chooseFile(file);
  });
  $('project').addEventListener('click', () => landing.send());
  $('cancel').addEventListener('click', () => landing.cancel());
  $('watch-example').addEventListener('click', () => landing.watchExample());
  $('send-example').addEventListener('click', () => landing.sendExample());
  $('open-results').addEventListener('click', () => landing.openResults());
  $('replay').addEventListener('click', () => landing.replay());
  $('download').addEventListener('click', () => landing.download());
  $('clear').addEventListener('click', () => {
    $('matrix').value = '';
    landing.clear();
  });
  $('outcome-chips').addEventListener('click', (e) => {
    const chip = e.target.closest('[data-outcome]');
    if (!chip) return;
    const on = chip.getAttribute('aria-pressed') !== 'true';
    landing.setOutcomeOn(chip.dataset.outcome, on);
    update();
  });

  // A file dropped on the map is checked the same way.
  const box = $('three-container');
  const hint = $('drop-hint');
  box.addEventListener('dragover', (e) => {
    if (![...(e.dataTransfer?.types ?? [])].includes('Files')) return;
    e.preventDefault();
    hint.hidden = false;
  });
  box.addEventListener('dragleave', (e) => { if (!box.contains(e.relatedTarget)) hint.hidden = true; });
  box.addEventListener('drop', (e) => {
    e.preventDefault();
    hint.hidden = true;
    const file = e.dataTransfer?.files?.[0];
    if (!file || !['idle', 'chosen', 'interactive', 'failed'].includes(landing.state.name)) return;
    showDataTab();
    landing.chooseFile(file);
  });

  let showDataTab = () => {};
  return {
    open,
    update,
    set onShow(f) { showDataTab = f; },
  };
}
