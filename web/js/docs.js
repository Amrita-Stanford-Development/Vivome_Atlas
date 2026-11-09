// The Docs pages (web/docs.html and one web/docs-<topic>.html per topic): a
// topic page's tabs and addresses, then the numbers and figures from
// web/data/docs.json. The words are the page's; every number is a record
// (docs-data.js), and a failed load shows the error and leaves every slot
// Pending. Without this script a topic page shows its three panels in order.

import { PENDING_LABEL } from './manifest.js';
import { errorPanel } from './panels.js';
import { TABS, docsBasis, docsFact, loadDocs, nextTab, tabForHash } from './docs-data.js';
import { drawFigure } from './docs-svg.js';

const $ = (id) => document.getElementById(id);

// ---- the tabs, on a topic page ----

// An address this page answers to: a tab, or a part inside one. Anything
// else (the skip link's #main, say) leaves the tabs as they are.
const known = (hash) => {
  const { tab, target } = tabForHash(hash);
  return target !== null || hash === `#${tab}`;
};

function mountTabs() {
  const list = document.querySelector('.tabs[role="tablist"]');
  const tab = (name) => $(`tab-${name}`);
  const panel = (name) => $(name);
  if (!list || !TABS.every((name) => tab(name) && panel(name))) return;
  let current = TABS[0];

  function show(name) {
    current = name;
    for (const other of TABS) {
      const on = other === name;
      tab(other).setAttribute('aria-selected', String(on));
      tab(other).tabIndex = on ? 0 : -1;
      panel(other).hidden = !on;
    }
  }

  // #did opens that tab; #did-b7 opens it and the step B7 in it; #how-promise
  // and #words-log are a chapter and a term, scrolled to.
  function follow({ scroll }) {
    if (!known(location.hash)) return;
    const { tab: name, target, open } = tabForHash(location.hash);
    show(name);
    const el = target ? document.getElementById(target) : null;
    if (el && panel(name).contains(el)) {
      if (open && el.tagName === 'DETAILS') el.open = true;
      if (scroll) el.scrollIntoView({ block: 'start' });
    } else if (scroll) {
      list.scrollIntoView({ block: 'start' });
    }
  }

  function choose(name, { focus = false } = {}) {
    show(name);
    history.replaceState(null, '', `#${name}`);
    if (focus) tab(name).focus();
  }

  for (const name of TABS) tab(name).addEventListener('click', () => choose(name));
  // The tab pattern's keys: the arrows move along and wrap, Home and End go to the ends.
  list.addEventListener('keydown', (e) => {
    const next = nextTab(current, e.key);
    if (!next) return;
    e.preventDefault();
    choose(next, { focus: true });
  });
  // Opening a step names it in the address, so the link can be shared.
  panel('did').addEventListener('toggle', (e) => {
    const step = e.target;
    if (step.tagName === 'DETAILS' && step.open && /^did-[a-z0-9-]+$/.test(step.id)) {
      history.replaceState(null, '', `#${step.id}`);
    }
  }, true);
  window.addEventListener('hashchange', () => follow({ scroll: true }));

  // Hiding the other panels moves what the browser scrolled to on arrival,
  // so an address is followed once more, with a scroll.
  show(current);
  follow({ scroll: Boolean(location.hash) });
  list.hidden = false;
  document.querySelector('main').classList.add('docs-tabbed');
}

// ---- the numbers and figures ----

function fill(docs) {
  for (const el of document.querySelectorAll('[data-docs]')) {
    el.innerHTML = docsFact(docs, el.dataset.docs);
    el.title = docsBasis(docs, el.dataset.docs);
  }
  // A figure that cannot draw shows why; the rest of the page stays.
  for (const el of document.querySelectorAll('[data-docs-figure]')) {
    try {
      el.innerHTML = drawFigure(el.dataset.docsFigure, docs);
    } catch (err) {
      el.innerHTML = errorPanel(err);
    }
  }
}

mountTabs();
loadDocs().then(fill).catch((err) => {
  $('docs-error').innerHTML = errorPanel(err);
  for (const el of document.querySelectorAll('[data-docs]')) el.textContent = PENDING_LABEL;
});
