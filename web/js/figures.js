// The Manuscript page's figures and Methods illustrations, drawn from the
// repository's data by scripts/build_figures.py (web/figures/: an SVG and a
// CSV of every number drawn, per figure, and index.json with each one's
// title, legend, alt text, section and sources). Each figure fills its slot,
// <div class="ms-figure-slot" data-figure="NAME">, beside the result it
// supports; its numbers show as a table on request. The builders are pure,
// so node --test covers them; mountFigures touches the page.

import { errorPanel, escapeHtml } from './panels.js';

const e = escapeHtml;

// RFC 4180 CSV: a quoted field may hold commas, quotes ("") and line breaks.
export function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  const s = String(text ?? '');
  for (let i = 0; i < s.length; i += 1) {
    const c = s[i];
    if (quoted) {
      if (c === '"' && s[i + 1] === '"') { field += '"'; i += 1; } else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; } else if (c === '\n' || c === '\r') {
      if (c === '\r' && s[i + 1] === '\n') i += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else field += c;
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows;
}

// One figure: the picture, its title and legend, its sources, and the ways
// to take it away (the SVG, and every number drawn as CSV).
export function buildFigure(entry) {
  const sources = (entry.sources ?? []).map((s) => `<code>${e(s)}</code>`).join(', ');
  return `<figure class="ms-figure ms-figure-${e(entry.width)}" id="figure-${e(entry.name)}">`
    + `<img src="${e(entry.svg)}" alt="${e(entry.alt)}" loading="lazy" decoding="async">`
    + `<figcaption><strong>${e(entry.title)}.</strong> ${e(entry.caption)}`
    + (sources ? `<span class="ev-src">${sources}</span>` : '')
    + `<span class="ms-figure-links"><a href="${e(entry.svg)}" download>SVG</a>`
    + `<a href="${e(entry.csv)}" download>The numbers drawn (CSV)</a></span></figcaption>`
    + `<details class="ms-figure-numbers" data-figure-numbers="${e(entry.csv)}">`
    + '<summary>Show the numbers drawn</summary><div class="table-scroll"></div></details>'
    + '</figure>';
}

// The numbers a figure draws, from its CSV, as a table (header row first).
export function buildNumbersTable(csvText) {
  const [head = [], ...rows] = parseCsv(csvText).filter((r) => r.some((c) => c !== ''));
  return '<table class="support-table ms-table ms-figure-table">'
    + `<thead><tr>${head.map((h) => `<th>${e(h)}</th>`).join('')}</tr></thead>`
    + `<tbody>${rows.map((r) => `<tr>${head.map((_, k) => `<td>${e(r[k] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody>`
    + '</table>';
}

// The Figures section: every figure and illustration, linked to its place,
// with its downloads.
export function buildFigureList(entries) {
  if (!entries?.length) return '<p class="pending">No figures yet.</p>';
  return `<ol class="ms-figure-list">${entries.map((f) => `<li><a href="#figure-${e(f.name)}">${e(f.title)}</a>`
    + `<span class="ms-figure-links"><a href="${e(f.svg)}" download>SVG</a><a href="${e(f.csv)}" download>CSV</a></span></li>`).join('')}</ol>`;
}

// Places every figure in its slot and fills the list; a figure's numbers
// load when its "Show the numbers drawn" is first opened.
export async function mountFigures(doc = document, fetchImpl = fetch) {
  const response = await fetchImpl('figures/index.json');
  if (!response.ok) throw new Error(`figures/index.json: ${response.status}`);
  const { figures = [] } = await response.json();
  for (const entry of figures) {
    for (const slot of doc.querySelectorAll(`[data-figure="${entry.name}"]`)) slot.innerHTML = buildFigure(entry);
  }
  const list = doc.getElementById('figure-list');
  if (list) list.innerHTML = buildFigureList(figures);
  for (const details of doc.querySelectorAll('[data-figure-numbers]')) {
    details.addEventListener('toggle', async () => {
      const mount = details.querySelector('.table-scroll');
      if (!details.open || mount.dataset.loaded) return;
      mount.dataset.loaded = 'yes';
      try {
        const csv = await fetchImpl(details.dataset.figureNumbers);
        if (!csv.ok) throw new Error(`${details.dataset.figureNumbers}: ${csv.status}`);
        mount.innerHTML = buildNumbersTable(await csv.text());
      } catch (err) {
        mount.innerHTML = errorPanel(err);
      }
    });
  }
  return figures;
}
