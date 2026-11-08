// The Atlas page's Your data tab: the service line (and an own copy's
// address), the recorded example, sending a file, the results card and the
// supported label space. The landing (landing.js) does the drawing; this tab
// holds the controls and asks the service whether it is ready, only when the
// tab is first opened, so a visit to the map never wakes the service.

import { PENDING_LABEL, formatCount, isMeasured, loadManifest } from '../manifest.js';
import { buildSupportedLabelSpace, errorPanel, escapeHtml } from '../panels.js';
import { loadWorkflow, wfFact } from '../workflow-data.js';
import { coordinatesCompatible } from './answers.js';
import { scaleNote } from './atlas-panels.js';
import { valueFactsText } from './file-check.js';
import { asksScale, asksZeros, menuChoice, questionFile } from './scale-question.js';
import { explainFailure, rememberServiceUrl, serviceUrlFrom } from './service-client.js';

const $ = (id) => document.getElementById(id);
const storage = () => {
  try { return window.localStorage; } catch { return null; }
};

// The service's address and its limits, shared with the landing.
export function createServiceState() {
  const input = $('service-url');
  input.value = serviceUrlFrom(storage());
  const state = { ready: false, status: null, limits: null };
  return {
    state,
    url: () => input.value.trim().replace(/\/+$/, ''),
    limits: () => state.limits ?? {},
  };
}

// acceptsFiles is false on an organ's map, which labels no file: a file
// dropped there is refused instead of opening this tab.
export function mountDataTab({ landing, client, service, acceptsFiles = true }) {
  const line = (text, kind = null) => {
    const el = $('service-status');
    el.textContent = text;
    el.classList.toggle('is-ready', kind === 'ready');
    el.classList.toggle('is-down', kind === 'down');
  };
  let opened = false;
  let workflow = null;
  let checks = 0;
  let setupWanted = false;

  // Only the latest check speaks: one still waiting on a cold service, or
  // on an address since changed, is ignored when it answers.
  async function checkService() {
    rememberServiceUrl(storage(), $('service-url').value.trim());
    const seq = ++checks;
    service.state.ready = false;
    service.state.status = null;
    line('Checking…');
    update();
    const slow = setTimeout(() => {
      if (seq === checks) line('Waking the service: after a quiet spell this takes up to a minute.');
    }, 3000);
    try {
      const status = await client.status(service.url());
      clearTimeout(slow);
      if (seq !== checks) return;
      if (status?.status !== 'ready') {
        line(`The service is running but cannot label yet: ${status?.reason ?? 'no reason given'}.`, 'down');
      } else {
        service.state.ready = true;
        service.state.status = status;
        if (status.limits) {
          service.state.limits = { ...service.state.limits, max_cells: status.limits.max_cells, max_upload_mb: status.limits.max_upload_mb };
          landing.recheckLimits();
        }
        const map = coordinatesCompatible(status.pipeline_version) ? ''
          : ' Its model draws a different map, so your cells will be listed, not placed.';
        line(`Service ready: ${status.pipeline_version ?? status.model_version ?? 'model unknown'}.${map}`, 'ready');
        $('service-status').title = status.model_version ?? '';
      }
    } catch (err) {
      clearTimeout(slow);
      if (seq !== checks) return;
      line(explainFailure(err, service.url(), { retrying: false }), 'down');
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
      landing.recheckLimits();
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
    // What the values look like, so the visitor can choose how they are read (Values, Zeros).
    const facts = valueFactsText(c.values);
    return `<dl>
        <dt>File</dt><dd>${escapeHtml(c.name)} (${escapeHtml((c.size / 1024).toFixed(1))} KB)</dd>
        <dt>Cells</dt><dd>${formatCount(c.cells)}</dd>
        <dt>Feature rows</dt><dd>${formatCount(c.features)}</dd>${facts ? `
        <dt>Values</dt><dd>${escapeHtml(facts)}</dd>` : ''}
      </dl>${problems}`;
  }

  // Assigns markup only when it changed: the landing redraws every frame
  // while it waits, and #file-result is a live region.
  const written = new Map();
  const setHtml = (el, html) => {
    if (written.get(el) === html) return;
    el.innerHTML = html;
    written.set(el, html);
  };

  // Buttons and cards follow the landing's state.
  function update(st = landing.state) {
    const name = st.name;
    const resting = ['idle', 'chosen', 'interactive', 'failed'].includes(name);
    $('project').disabled = !(name === 'chosen' && st.check?.ok && service.state.ready);
    $('cancel').hidden = !['sending', 'working', 'busy'].includes(name) || st.example;
    $('watch-example').disabled = !resting;
    $('send-example').disabled = !(resting && service.state.ready);
    $('matrix').disabled = !resting;
    // An RNA file is read by the service, and what a 0 means is asked only of a
    // file read as already log: a menu that does not apply shows I don't know.
    const protein = $('modality').value === 'prot';
    if (!protein) $('value-scale').value = 'auto';
    $('value-scale').disabled = !protein;
    if ($('value-scale').value !== 'log') $('zeros').value = 'auto';
    $('zeros').disabled = $('value-scale').value !== 'log';
    setHtml($('file-result'), fileResult(st));
    const run = landing.run;
    const shown = Boolean(run) && ['interactive', 'settling', 'flying', 'receipt', 'finishing'].includes(name);
    // With an answer on the map the tab is just the file's card; "Send
    // another file" brings the setup back below it.
    if (!shown) setupWanted = false;
    $('results-card').hidden = !shown;
    $('data-setup').hidden = shown && !setupWanted;
    $('send-another').hidden = !shown || setupWanted;
    // When the service read the values on its own and its check was unsure,
    // or found the table unusual: said on the card, not only in the receipt.
    const note = run ? scaleNote(run.receipt) : null;
    $('results-scale-note').hidden = !shown || !note;
    if (shown) {
      $('results-note').textContent = run.source === 'recorded'
        ? 'The recorded example: answers from the served model, no file sent.'
        : `${formatCount(run.cells.length)} cells from ${st.file?.name ?? 'your file'}.`;
      $('results-scale-note').textContent = note ?? '';
      setHtml($('outcome-chips'), landing.chips());
      $('download').hidden = run.source !== 'service';
      // Replay and Clear wait for the landing to end.
      $('replay').disabled = name !== 'interactive';
      $('clear').disabled = name !== 'interactive';
    }
  }
  landing.onChange((st) => update(st));

  $('check-service').addEventListener('click', checkService);
  $('service-url').addEventListener('change', checkService);
  $('modality').addEventListener('change', () => {
    landing.optionsChanged();
    update();
  });
  $('value-scale').addEventListener('change', () => {
    landing.optionsChanged();
    update();
  });
  $('zeros').addEventListener('change', () => landing.optionsChanged());

  // The question about a protein file's values, asked once as the file is
  // chosen (research/value-scale-b5-design.md, "The pop-up"). Its answers
  // only set the Values and Zeros menus, which stay the one place the
  // choice lives; answering does not send the file.
  const question = $('scale-question');
  let asking = null; // while it is open: the file's check, and the reading once chosen
  function showStep(step) {
    const zeros = step === 'zeros';
    $('scale-question-title').hidden = zeros;
    $('scale-question-readings').hidden = zeros;
    $('scale-question-zeros-title').hidden = !zeros;
    $('scale-question-zeros').hidden = !zeros;
    const title = zeros ? 'scale-question-zeros-title' : 'scale-question-title';
    question.setAttribute('aria-labelledby', title);
    if (!question.open) question.showModal();
    // Focus on the question, so no answer is chosen in advance.
    $(title).focus();
  }
  function ask(check) {
    asking = { check, reading: null };
    $('scale-question-file').textContent = questionFile(check);
    const facts = valueFactsText(check.values);
    $('scale-question-facts').textContent = facts ?? '';
    $('scale-question-facts').hidden = !facts;
    showStep('reading');
  }
  function answer(reading, zeros = 'auto') {
    if (!asking) return;
    asking = null;
    const { valueScale, zeros: zerosChoice } = menuChoice(reading, zeros);
    $('value-scale').value = valueScale;
    $('zeros').value = zerosChoice;
    if (question.open) question.close();
    landing.optionsChanged();
    update();
    $('project').focus();
  }
  question.addEventListener('click', (e) => {
    if (!asking) return;
    // The close button counts as I don't know for the open question.
    if (e.target.closest('#scale-question-close')) {
      answer(asking.reading ?? 'auto');
      return;
    }
    const reading = e.target.closest('[data-reading]')?.dataset.reading;
    if (reading === 'log' && asksZeros(asking.check)) {
      asking.reading = 'log';
      showStep('zeros');
    } else if (reading) {
      answer(reading);
    } else {
      const zeros = e.target.closest('[data-zeros]')?.dataset.zeros;
      if (zeros) answer(asking.reading, zeros);
    }
  });
  // Escape: I don't know for the open question; a reading already chosen is kept.
  question.addEventListener('cancel', (e) => {
    e.preventDefault();
    answer(asking?.reading ?? 'auto');
  });
  // Any other way it closes counts the same.
  question.addEventListener('close', () => answer(asking?.reading ?? 'auto'));

  // A file picked or dropped is checked, then asked about. A check overtaken
  // by another file comes back null, so the question opens once, for the
  // latest file. Never for the example (landing.js, sendExample). Modality
  // is read when the check finishes.
  const modalityMenu = $('modality');
  const choose = (file) => Promise.resolve(landing.chooseFile(file)).then((check) => {
    if (asksScale({ modality: modalityMenu.value, check })) ask(check);
  });

  // Emptied as the picker opens, so choosing the same file again still
  // counts as a choice.
  $('matrix').addEventListener('click', () => { $('matrix').value = ''; });
  $('matrix').addEventListener('change', () => {
    const file = $('matrix').files[0];
    if (file) choose(file);
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
  $('send-another').addEventListener('click', () => {
    setupWanted = true;
    update();
    $('matrix').focus();
  });
  $('outcome-chips').addEventListener('click', (e) => {
    const chip = e.target.closest('[data-outcome]');
    if (chip) landing.setOutcomeOn(chip.dataset.outcome, chip.getAttribute('aria-pressed') !== 'true');
  });

  // A file dropped on the map is checked the same way.
  const box = $('three-container');
  const hint = $('drop-hint');
  box.addEventListener('dragover', (e) => {
    if (![...(e.dataTransfer?.types ?? [])].includes('Files')) return;
    e.preventDefault();
    if (!acceptsFiles) {
      e.dataTransfer.dropEffect = 'none';
      return;
    }
    hint.hidden = false;
  });
  box.addEventListener('dragleave', (e) => { if (!box.contains(e.relatedTarget)) hint.hidden = true; });
  box.addEventListener('drop', (e) => {
    e.preventDefault();
    hint.hidden = true;
    if (!acceptsFiles) return;
    const file = e.dataTransfer?.files?.[0];
    if (!file || !['idle', 'chosen', 'interactive', 'failed'].includes(landing.state.name)) return;
    showDataTab();
    choose(file);
  });

  let showDataTab = () => {};
  return {
    open,
    update,
    set onShow(f) { showDataTab = f; },
  };
}
