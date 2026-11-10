# The Docs section

`web/docs.html` and one `web/docs-<topic>.html` per topic hold the record of
this project in plain words: what each part does, every step taken to build
and test it, what each step found, and what the owner decided. It is for
any reader, the owner included, and a beginner should be able to follow it.

The words come from committed records only: notes, plans, protocols, the
run history, `research/todo.md` and the git history. Nothing from a
conversation that the repository does not hold. Each step names the files
it draws on.

## Pages

| Page | Holds |
|---|---|
| `docs.html` | The home: how to read a topic, one card per topic, the project's timeline, where the full records are |
| `docs-raw-or-log.html` | Raw or log: how the service tells a raw protein table from a log one, Step 1 to B7, and the plan for protein v2 |

Seven more topics are planned, each written in its own round and agreed by
the owner before it goes up: the cell model and its versions, the data,
testing the model, other organs, the upload service, the website, and how
we work. Until then their cards say "Coming next" and link nowhere.

The Docs link sits after Motion in every page's header. It is
`aria-current="page"` on the home and `aria-current="true"` on a topic page.

## A topic page

Three tabs, whose panels are the page's addresses: How it works (`#how`),
What we did (`#did`) and Words (`#words`). The tab list ships `hidden`;
`web/js/docs.js` shows it once the tabs work, so without JavaScript all
three panels show in order, each under its own heading. A click on a tab
replaces the address (`history.replaceState`), so the tabs add nothing to
the history. `#did-b7` opens What we did and the step B7 in it;
`#how-<chapter>` and `#words-<term>` open their tab and scroll to the part.
Opening a step writes its address, so the link can be shared. A panel
holds no nested `<section>`.

- **How it works:** chapters, each an `<article id="how-…" class="docs-chapter">`
  with an `<h3>`. The side list (`nav.docs-toc`) stays in view and links
  every chapter by its title, in order. Each chapter ends with a
  `p.docs-source` naming its files. Technical detail sits in "For the
  curious" folds (`details.curious`, a shared component in `page.css`).
- **What we did:** one `<details id="did-<step>" class="docs-step">` per
  step in `docs.json`'s `steps`, in the same order (the ids use hyphens:
  `phase_a` is `did-phase-a`). The summary holds the step's dates as
  `<time>` elements, each one of that step's dates, then its title, and a
  bead when part of it is live. The parts are a `dl.docs-step-parts`, in
  this order: What we did, Why, What we expected, What we found, What you
  decided (`dd.docs-decided`, in the accent's tint) and Where it's kept
  (`dd.docs-kept`: only `<code>` paths and commits, the step's report,
  expectations and notes among them).
- **Words:** `<div class="glossary sheet"><dl>`, one `<dt id="words-…">` per
  term, each term once, in alphabetical order.

## Where the numbers come from

No number is typed into a Docs page. Each number is an empty slot,
`<span data-docs="KEY"></span>` (or a `strong`), naming a record in
`web/data/docs.json`. `docs.js` fills it through `docsFact`
(`web/js/docs-data.js`), which goes through `isMeasured` and the
Manuscript page's formats, and sets the record's basis as its tooltip. If
the data fails to load, `#docs-error` shows the error and every slot reads
Pending. Every record is shown somewhere in the section; the one pending
on purpose is `rl_v2_test`, protein v2's sealed test.

`web/tests/docs.test.js` holds a number guard. It reads the page's title
and description, and inside `<main>` the text and every `aria-label`,
`title` and `alt`. It fails on any digit and on number words from three
up, ordinals from third to twelfth, and words such as hundreds or dozen.
It lets through:

- dates (`2026-11-09`), accessions (`PXD064083`), the size groups (S1,
  S2+S3), the steps (Step 1, A2, B0 to B7, R1 to R7) and Stage 0;
- versions (`v4.1`, protein-v2) and service revisions (`00009-hcz`);
- log2, log10, median-50, PBMC240 and SCoPE2;
- a `<code>` that is a path, an identifier or a commit hash.

So a page writes "zero", "one" and "two" in words, and anything larger is
a record.

## Figures

Every `figure.docs-fig` is one of three kinds, and the test checks which:

- **A data figure** is `<div class="docs-figure" data-docs-figure="NAME">`
  inside a `figure.docs-fig`, drawn by `drawFigure` in `web/js/docs-svg.js`
  from the records `FIGURES` names for it (`docs-data.js`), and for a
  figure of many values from its series (`FIGURE_SERIES`, below). Each has
  a "The numbers" fold that gives its numbers in words. Its own words hold
  no number but a record's text or an axis label of its series.
- **An illustration** is a static inline `svg.docs-svg` with `role="img"`
  and an `aria-label`, and no slots, marked with the Illustration bead.
- **A screenshot** is one
  `<img class="docs-shot" src="img/docs/FILE" width="W" height="H" alt="…" loading="lazy">`.
  Its file and size are those `web/img/docs/index.json` records, and its
  caption opens with the bead that index gives it: "Screenshot: live" for
  a picture of the live commit, "Screenshot: not live" for one of the
  working tree. Its `alt` passes the number guard, so it says in words what
  the picture shows. Every listed screenshot is shown, and the folder holds
  nothing else.

The figures use the ink, the greys and the accent only. Where the sealed
test contradicts the promise, the figure says "contradicted" and fills the
marker, never by colour alone; elsewhere it says "not contradicted", since
a test that does not contradict the promise has not proved it.

### Screenshots

`node scripts/docs_screenshots.mjs` takes them again (about half a minute).
It needs Node and the PC's Edge, no package: it starts Edge headless with a
DevTools port and drives it over Node's own WebSocket. It serves two copies
of `web/`: the working tree, and the live site's files read from git at
`LIVE_SITE`, the commit live today (`git show`, nothing checked out). Each
shot is taken at twice its size, as WebP, in light colours with motion
reduced; the menus are opened out in a copy beside the real ones so every
choice shows.

When the live site changes, set `LIVE_SITE` to the new live commit and run
it again. A picture's numbers are the site's own: the pop-up's are what
`checkFile`, `questionFile` and `valueFactsText` compute from the example
file, which `docs.test.js` computes again and compares with the text
`index.json` recorded. Screenshots are pictures for the pages, never a
check of them: the owner still looks at the pages by hand.

## The data: `web/data/docs.json`

`scripts/build_docs.py` writes it, standard library only.
`scripts/build_manifest.py` runs it after the Manuscript page's data, and
it also runs on its own. It holds:

- the records, prefixed `rl_` for Raw or log: each with its value, status,
  format and basis (the file and the field it came from). A prediction is
  quoted from its expectations file by a pattern that must match exactly
  once, and its basis says it was written before the run;
- `steps`: each step's report, expectations, notes, run and dates, which
  the page's test checks every entry against;
- `series`: the many values a data figure draws, each with its basis: the
  bank's medians (the old rule's dot plot), the example file's values as
  two histograms and its spread by level, and S1's lowest log scores in
  calibration and in the test. An axis's labels are written into the
  series as `ticks`, so the figure types none. `docsSeries` hands a figure
  its series only when every number in it is finite, and the figure says
  Pending otherwise;
- `sources`, each source file's sha256, and `built_for`, the manifest's
  release.

`scripts/test_build_docs.py` rebuilds it byte for byte and checks its
budget (80,000 bytes), its formats, the pending set, and the headline
numbers against their sources. It checks the series too: the histograms
count every value, the old rule's line gives each bank table its recorded
reading, and S1's log threshold is the k-th smallest calibration score.

## The home

- **How to read a topic:** a `dl.docs-howto` naming the tabs, which the
  test pins to each topic page's own tab buttons.
- **The topics:** one `<li class="docs-card glass" id="topic-<id>">` per
  topic, in the order `TOPICS` in `docs.test.js` lists them. A written
  topic's title links to `docs-<id>.html`; any other card carries the
  Coming next bead and no link. A card is dated by the first and last of
  its milestones on the timeline.
- **The timeline:** one `<li class="docs-milestone">` per milestone, oldest
  first, each with one `<time>`, its topic (`span.docs-milestone-topic`)
  and a line. Each is tied to a record:
  - `data-step="b7"`: a step of `docs.json` whose dates hold the
    milestone's date; the milestone links to that step's entry;
  - `data-source="research/todo.md"`: a changelog row of that date;
  - `data-source="<path>"`: another file that holds the date.
- **Where the full records are:** the todo and its changelog, the run
  history, `research/` and `docs/`.

A link from one Docs page to another must land on a part that exists.

## Adding a step

Part of that step's doc run-through:

1. its records and its entry in `steps`, in `scripts/build_docs.py`, with a
   check in `scripts/test_build_docs.py`; then rebuild with
   `scripts/build_manifest.py`. A step's dates include its plan's status
   line: `research/value-scale-plan.md` for Step 1 to B7,
   `research/value-scale-v2-plan.md` for protein v2's R steps;
2. its `details.docs-step` at the end of the topic's What we did;
3. How it works, where the step changes it, and Words, for a new term;
4. a milestone on the home's timeline, if it is one;
5. the four test suites.

## Adding a topic

1. `web/docs-<id>.html`, with the raw-or-log page's header, crumb, tabs,
   panels and scripts;
2. its name in `DOCS_PAGES` (`web/tests/site-pages.js`), which brings it
   under the header, beta, motion and contrast tests, and its chapter ids
   in `docs.test.js`;
3. its records and steps in `scripts/build_docs.py`;
4. on the home: its card links to it and shows its status, and its
   milestones;
5. a line in `docs/file-index.md`, and a row in this file's page table.

## Reading it before it is live

The section goes online with the rest of the site after protein v2's R7,
with the owner's OK. Until then, read it on the PC:

```bash
cd web && python -m http.server 8000     # open http://localhost:8000/docs.html
```

`scripts/build_pages_site.py` copies `web/`, so a deploy of the site before
then would put the section online too.
