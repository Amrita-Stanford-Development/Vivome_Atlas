// The Workflow page's film mode: the whole story played in a theatre over the
// page, one chapter's scene at a time, with the chapter's own sentences as
// captions (its <p data-beat> elements). Play, pause, scrub, skip, change
// speed; the address keeps the place (#film&t=95.5&cell=3), and &present
// opens a 16:9 frame for screen recording. A hidden tab pauses it. Under
// reduced motion each beat holds its finished frame instead of animating.
// The clock maths is web/js/timeline.js.

import {
  CHAPTERS, SPEEDS, STARTS, TOTAL, beatAt, formatClock, formatHash, locate, stepTarget, timeOf,
} from './timeline.js';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// What a key does while the film is open. A focused field keeps its own keys
// (the scrubber its arrows); a focused button or link keeps Space, which
// presses it. control: 'field', 'button' or null.
export function filmKeyAction(key, shift, control) {
  if (control === 'field') return null;
  if (key === ' ') return control === 'button' ? null : 'toggle';
  if (key === 'ArrowRight') return shift ? 'forward' : 'next';
  if (key === 'ArrowLeft') return shift ? 'back' : 'prev';
  if (key === 'Escape') return 'close';
  if (key === 'c' || key === 'C') return 'captions';
  return null;
}

// The page behind the film: inert while it plays, so focus stays with the
// film and its bar (they sit beside the page, not in it).
const setPageInert = (on) => {
  for (const el of $$('body > .skip-link, body > header, body > main, body > footer')) el.inert = on;
};

export function createFilm({ ctx, state, reduced, loadScene, setCell }) {
  const bar = $('#filmbar');
  const theatre = $('#theatre');
  const stage = $('#theatre-stage');
  const clock = $('#film-clock');
  const scrub = $('#film-scrub');
  const rail = $('#film-rail');
  const speedSelect = $('#film-speed');
  const caption = $('#theatre-caption');
  const toggleButton = $('[data-film="toggle"]', bar);
  let t = 0;
  let playing = false;
  let speed = 1;
  let captions = true;
  let present = false;
  let shown = -1;
  let scene = null;
  let token = 0;
  let frame = null;
  let last = 0;
  let lastHash = 0;
  let wakeTimer = null;
  let opener = null;

  scrub.max = String(TOTAL);
  speedSelect.innerHTML = SPEEDS.map((s) => `<option value="${s}"${s === 1 ? ' selected' : ''}>${s}×</option>`).join('');
  rail.innerHTML = CHAPTERS.map((c, i) => `<li><button type="button" data-chapter="${i}" aria-label="${c.title}" title="${c.title}"></button></li>`).join('');

  const beatsOf = (id) => $$('[data-beat]', document.getElementById(id)).map((el) => el.textContent.replace(/\s+/g, ' ').trim());

  async function show(index) {
    shown = index;
    const my = ++token;
    scene?.dispose();
    scene = null;
    stage.innerHTML = '<div class="wf-canvas"></div>';
    const chapter = CHAPTERS[index];
    $('#theatre-title').textContent = chapter.title;
    $('#theatre-step').textContent = index === 0 ? 'The journey' : `Step ${index} of ${CHAPTERS.length - 1}`;
    const made = await loadScene(chapter.id, $('.wf-canvas', stage));
    if (my !== token) { made.dispose(); return; }
    scene = made;
    draw();
  }

  function draw() {
    const where = locate(t);
    if (where.index !== shown) { show(where.index); return; }
    const chapter = CHAPTERS[where.index];
    if (scene) scene.render(reduced ? stepTarget(chapter, where.p) : where.p, state);
    const beats = beatsOf(chapter.id);
    caption.textContent = beats[beatAt(chapter, where.p)] ?? '';
    clock.textContent = `${formatClock(t)} / ${formatClock(TOTAL)}`;
    scrub.value = String(t);
    $$('button', rail).forEach((b, i) => {
      b.classList.toggle('is-current', i === where.index);
      b.classList.toggle('is-done', i < where.index);
    });
    const now = performance.now();
    if (now - lastHash > 1000 || !playing) {
      lastHash = now;
      history.replaceState(null, '', formatHash({ t, cell: state.cell, present }));
    }
  }

  function loop(now) {
    if (!playing) return;
    const dt = Math.min(0.25, (now - last) / 1000);
    last = now;
    t = Math.min(TOTAL, t + dt * speed);
    draw();
    if (t >= TOTAL) { setPlaying(false); return; }
    frame = requestAnimationFrame(loop);
  }

  function setPlaying(on) {
    playing = on && t < TOTAL;
    toggleButton.innerHTML = playing ? '&#10074;&#10074;' : '&#9654;';
    toggleButton.setAttribute('aria-label', playing ? 'Pause' : 'Play');
    cancelAnimationFrame(frame);
    if (playing) { last = performance.now(); frame = requestAnimationFrame(loop); }
    draw();
  }

  function seek(seconds) {
    t = Math.min(TOTAL, Math.max(0, seconds));
    draw();
  }

  const skip = (step) => {
    const where = locate(t);
    if (step < 0 && where.local > 2) seek(STARTS[where.index]);
    else seek(timeOf(Math.min(CHAPTERS.length - 1, Math.max(0, where.index + step)), 0));
  };

  function setPresent(on) {
    present = on;
    document.body.classList.toggle('wf-present', on);
    $('[data-film="present"]', bar).setAttribute('aria-pressed', String(on));
    scene?.resize();
    draw();
  }

  function close() {
    setPlaying(false);
    token += 1;
    scene?.dispose();
    scene = null;
    shown = -1;
    bar.hidden = true;
    theatre.hidden = true;
    document.body.classList.remove('wf-film-open', 'wf-present', 'wf-awake');
    setPageInert(false);
    history.replaceState(null, '', location.pathname + location.search);
    opener?.focus?.();
  }

  function open({ t: start = 0, present: inPresent = false } = {}) {
    opener = document.activeElement;
    bar.hidden = false;
    theatre.hidden = false;
    document.body.classList.add('wf-film-open');
    setPageInert(true);
    setPresent(!!inPresent);
    t = Math.min(TOTAL, Math.max(0, start));
    shown = -1;
    setPlaying(true);
    toggleButton.focus();
  }

  bar.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.chapter !== undefined) { seek(timeOf(Number(b.dataset.chapter), 0)); return; }
    const action = b.dataset.film;
    if (action === 'toggle') setPlaying(!playing);
    else if (action === 'prev') skip(-1);
    else if (action === 'next') skip(1);
    else if (action === 'close') close();
    else if (action === 'present') setPresent(!present);
    else if (action === 'captions') {
      captions = !captions;
      b.setAttribute('aria-pressed', String(captions));
      theatre.classList.toggle('no-captions', !captions);
    }
  });
  scrub.addEventListener('input', () => seek(Number(scrub.value)));
  speedSelect.addEventListener('change', () => { speed = Number(speedSelect.value) || 1; });
  document.addEventListener('keydown', (e) => {
    if (theatre.hidden) return;
    const control = e.target.closest?.('input, select, textarea') ? 'field'
      : e.target.closest?.('button, a[href], summary') ? 'button' : null;
    const action = filmKeyAction(e.key, e.shiftKey, control);
    if (['toggle', 'next', 'prev', 'forward', 'back'].includes(action)) e.preventDefault();
    if (action === 'toggle') setPlaying(!playing);
    else if (action === 'next') skip(1);
    else if (action === 'prev') skip(-1);
    else if (action === 'forward') seek(t + 5);
    else if (action === 'back') seek(t - 5);
    else if (action === 'close') close();
    else if (action === 'captions') $('[data-film="captions"]', bar).click();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden && playing) setPlaying(false); });
  window.addEventListener('resize', () => { if (!theatre.hidden) { scene?.resize(); draw(); } });
  document.addEventListener('pointermove', () => {
    if (!present) return;
    document.body.classList.add('wf-awake');
    clearTimeout(wakeTimer);
    wakeTimer = setTimeout(() => document.body.classList.remove('wf-awake'), 2500);
  });

  return {
    open,
    close,
    onCell: () => { if (!theatre.hidden) draw(); },
    setCell,
    ctx,
  };
}
