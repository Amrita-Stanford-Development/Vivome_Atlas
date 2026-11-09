// The site's pages, listed once for every test that walks them: the shared
// header and footer (chrome.test.js), the beta gate's header, the motion
// switch, and the reserved colours. A new page is one line here.
import { readdirSync } from 'node:fs';

// The Docs section: its home, then one page per topic.
export const DOCS_PAGES = ['docs.html', 'docs-raw-or-log.html'];

export const PAGES = ['index.html', 'atlas.html', 'manuscript.html', 'workflow.html', 'motion.html', ...DOCS_PAGES];

// The page every other page's header and footer must match.
export const CANONICAL = 'index.html';

// The atlas is a full-window app view: it carries the header but no footer,
// and its viewer covers the living water.
export const WITHOUT_FOOTER = new Set(['atlas.html']);
export const WITHOUT_WATER = new Set(['atlas.html']);

// Each page that loads data writes its page-level error into this element.
export const PAGE_ERRORS = [
  ['manuscript.html', 'ms-error'],
  ['motion.html', 'reel-error'],
  ['workflow.html', 'sync-banner'],
  ...DOCS_PAGES.map((page) => [page, 'docs-error']),
];

// The nav link a page marks as current: none on the landing (it is reached
// from the wordmark), the Docs link on every Docs page, and otherwise the
// page's own link.
export function currentLink(page) {
  if (page === CANONICAL) return null;
  if (DOCS_PAGES.includes(page)) return 'docs.html';
  return page;
}

// Every stylesheet the site ships, so a new one is always checked.
export const STYLESHEETS = readdirSync(new URL('../css/', import.meta.url))
  .filter((name) => name.endsWith('.css'))
  .sort()
  .map((name) => `css/${name}`);
