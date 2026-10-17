# Design system

Every page in `web/` is built from one imagined world, so the landing page,
the dashboard and the tools read as one product. This page is the reference;
the tokens and component classes live in `web/css/page.css`. The original
concept (intro, landing, scroll story, dashboard, tools) is
[docs/webpage_concept.md](../webpage_concept.md).

## The world

A living specimen. The name carries it: **Viv** (living) + **OME** (omics).
The atlas covers two omes, RNA and protein, and the copy never claims more.

- **The field:** `web/js/background.js` draws one fixed canvas behind every
  page: cells, DNA and RNA strands, a molecular network and a flow field
  drifting over a slowly breathing blue gradient. It is the original landing
  and Visuals animation, kept as the site's signature. Under reduced motion it
  draws one still frame. Every page loads it with a one-line module script
  tag, and it mounts itself.
- **The living water:** `web/js/biofield.js` lies over the field and behind
  the page, on every page but the atlas, whose viewer covers the window. 3D
  objects drift and tumble in it: DNA, chromatin, red cells, platelets,
  lymphocytes, monocytes, neutrophils, coiled and long threads, and a long
  cell (`web/js/biocells.js`). They sit in a soft gel: slightly blurred,
  frosted over, and a wake follows the pointer (`web/js/water.js`). It loads
  after `background.js` with its own one-line tag, stays in place as the page
  scrolls, draws one still frame under reduced motion, and removes itself
  without WebGL.
  - The cells and molecules follow their measured shapes; the threads and
    the long cell are drawn shapes. Platelets are drawn 1.5 times larger
    and the molecules far larger than beside the cells, and the mix keeps
    blood's order (red cells most, white cells fewest), not its ratio.
  - Each kind of object has its own colour family. The field is the one
    decorative layer, so red cells and pink threads may sit near the
    reserved hues there; the UI never uses those hues for anything else.
  - `web/preview-biocells.html` and `web/preview-water.html` show the
    objects close up and the water effects side by side. Neither is linked
    from the site.
- **Cards:** the white card with the blue halo from the original landing
  (`.sheet`), and liquid glass (`.liquid`) for what floats over the water.
  Shadows are blue-tinted, never plain black.

## Objects: every UI role is one of five

| Class | Object | Use it for |
|---|---|---|
| `.glass` | frosted glass | chrome: the header, toolbars, sidebars |
| `.well` | pressed in | inputs, the active nav item, empty values |
| `.sheet` | the white card with the blue halo | anything you read at length: tables, prose, explanations |
| `.liquid` | liquid glass: frosted, a bright rim and a soft sheen | short things that float over the water: stats, steps, callouts |
| `.bead` | a small cell | badges and status (`bead-rna`, `bead-prot`, `bead-both`, `bead-open`) |

`.breathe` makes a sheet's halo pulse slowly, as on the original landing.
Use it on one card per page at most.

A new element starts with the question "which object is this?" Reuse one of
the five, or add one class to `@layer components` in `page.css`. No one-off
styles. Page-specific layout (grids, spacing) may live in the page's own
`<style>`; it is unlayered, so it overrides the components when it must.

`.btn` is the one accent-filled button. `.cut` is the motif (below).

## Colour

| Token | Value | Meaning |
|---|---|---|
| `--field` | `#EAF0F6` | the field's resting colour, before the canvas draws |
| `--bench` | `#F5F5F3` | warm neutral for wells and fills |
| `--paper` | `#FFFFFF` | sheets |
| `--ink` / `--ink-soft` / `--ink-faint` | `#1D2B36` / `#4B4B4B` / `#666666` | headings / body / labels and Pending |
| `--line` | `#E4E3DE` | hairlines |
| `--accent` | `#0066A3` | the one accent: links, focus rings |
| `--accent-bright` | `#0073AD` | the cutout and the landing wordmark only |
| `--rna` | `#C8641E` | reserved: RNA, and nothing else |
| `--prot` | `#2F8F6A` | reserved: protein, and nothing else |
| `--dot` | `#E4577A` | reserved: the logo's living dot |
| `--error` | `#B42318` | errors only |

A reserved colour is never decoration in the UI, so when it appears on a
mark it means something. The background field is the one decorative layer;
its red RNA strands and green molecules sit close to the reserved hues on
purpose, so the field and the marks tell the same story. A type present in both modalities gets both colours (the
`bead-both` split dot). RNA, protein and the accent pass the palette
validator as a set, both colour-blind simulations included.
Text contrast is AA or better on the bench.

Cell-type colours in the atlas viewer are a separate categorical palette, a
data encoding rather than UI.

## Type

Poppins throughout: 600 to 700 for headings, with tight tracking, 400/500 for
body and UI. Body lines stay under about 72 characters. Labels are sentence
case, never all caps.

A block of content uses several levels, from `page.css`:

| Class | Level | Size |
|---|---|---|
| `.eyebrow` | what the block is about, in the accent | 14px, 600 |
| `.display` (`.display-xl` in the hero) | the one headline, with its `.cut` word | up to 96px (124px) |
| `.subhead` | the headline's sentence | up to 28px, 500 |
| body (`.card p`) | the explanation | 16.5px |
| `.caption` | context for a number, or a note | 13.5px, faint |
| `.stat` and `.stat-label` | one big number and what it counts | up to 68px |

## The motif

One key word set in a solid accent block: `Viv<span class="cut">OME</span>`,
"Cell-type labels for single-cell <span class="cut">proteomics.</span>" Use it
once per heading at most, always on the word that carries the meaning.

## Copy

- Plain, sentence case, active voice. No hype words. No em dashes in visible
  text; use a colon, comma or full stop.
- The landing stays high level. Detail lives on the tool pages.
- **Honesty.** No page shows a number the manifest doesn't carry
  ([manifest.md](manifest.md)). These words stay off the site until the
  evidence exists:
  - "calibrated": conformal coverage is below its target until T1 NB3 passes;
  - "beats scANVI": true only for the shipped seed;
  - "99%": the modality probe is a diagnostic, not a score;
  - "state of the art": needs the sealed Khoury test;
  - "deployed" or "hosted" for any model but v4.1: the hosted service runs v4.1 only.

## The landing

`web/index.html` says plainly what VivOME is and what a visitor can do with
it.

- **The hero.** A large liquid-glass title panel, with large 3D objects
  from `web/js/biocells.js` in front of it (`web/js/hero.js`): a
  neutrophil, a monocyte, a lymphocyte, red cells, DNA, chromatin, a coiled
  thread, a long cell and platelets, framing the edges.
  - When the page opens they ease in from beyond the edges, one after
    another, over about three seconds, while the panel's lines rise in.
  - The hero is a sticky stage. As it scrolls away, each object flies
    outward along the line from the centre through its place, until all
    have left; then the hero stops drawing.
  - No mouse parallax. The panel works without WebGL.
- **Seven sections**, each a header (eyebrow, display headline, subhead) over
  a grid of cards: white sheets for reading, liquid glass for stats, steps
  and callouts.
  1. **The problem:** protein data rarely comes labelled; RNA references do.
  2. **How it works:** trained on RNA, read on protein, zero-shot.
  3. **Explore:** the reference, open in the browser now, with its counts.
  4. **Your data:** five steps from file to download, and that the service
     runs on your own computer while in preview.
  5. **Honest answers:** the answer ladder (cell type, group, lineage, none
     with its reason), and how often, on simulated RNA uploads.
  6. **Evidence:** Fulcher 2026 as development data, the benchmark and the
     sealed test once signed off, and the limits.
  7. **Releases:** frozen, numbered releases, so results can be traced.
- **The finale:** "No cell placed without evidence", the proof points and
  the links.

Each number names what it measured in the same sentence or caption. The copy
follows the model card: label transfer with honest abstention, never a shared
space where the two modalities mix.

- **Numbers.** Every number is a `data-fact` slot, filled from the manifest
  by `factText` in `web/js/panels.js`; the finale's proof points come from
  `buildProofPoints`. Big numbers count up when they come into view.
  `web/tests/landing.test.js` fails if a slot names a fact that doesn't
  exist.
- **Motion.** `web/js/story.js` runs it: an `IntersectionObserver` lets each
  block rise in once, and the hero's progress comes from its own rect. The
  maths is pure, in `web/js/motion.js`. The text is real HTML; its hidden
  start states apply only under `html.js`.
- **Phones** get fewer, smaller hero objects and one column of cards.
  **Reduced motion** gets a still hero and all the text at once.

## The Workflow page

`web/workflow.html` explains the product start to end, one chapter per step,
following one cell of the PBMC240 example ([workflow.md](workflow.md)). It
uses the same objects: each chapter's figure is a sheet held in view while
its sentences scroll by, and the film's bar is glass. Its figures are data
encodings: cell types take the atlas viewer's palette, RNA and protein their
reserved colours, z-scores a blue to ochre ramp that avoids every reserved
colour. Mechanism pictures with no data say "illustration".

## Shared chrome

The header (wordmark, the tool links, Dashboard) and the footer are static
markup copied into each page, so they work without JS and don't shift the
layout. `web/tests/chrome.test.js` pins every copy byte-identical to
`web/home.html`'s, apart from the one `aria-current="page"` marker. Change
one, change all, and add a new page to the test's `PAGES` list.

## Where new results land

The pages read the runs' outputs from data files; the markup does not change
when a release does.

| Output | Lands in | Shown by |
|---|---|---|
| The deployed model and its facts | `manifest.model` (from `service/model/runtime/`) | dashboard release card, versions model card |
| The next release while it is in progress | `manifest.next_reference` | dashboard "Next release" card (hidden while null) |
| Re-exported atlas cells | `web/data/metadata_*_lat128.csv` | atlas viewer; regenerate the manifest |
| Benchmark rows | `manifest.benchmark` | benchmark page, dashboard status bead |
| Announcements | `web/data/whats_new.json` (text only, no metrics) | dashboard "What's new" |
| A served model's trace, the gene space, the training recipe, the evaluation records | `web/data/workflow.json` (`scripts/build_workflow.py`, built with the manifest) | the Workflow page ([workflow.md](workflow.md)) |
