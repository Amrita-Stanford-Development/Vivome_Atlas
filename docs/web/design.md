# Design system

Every page in `web/` is built from one imagined world, so the landing page
and the tools read as one product. This page is the reference; the tokens
and component classes live in `web/css/page.css`. The original concept
(intro, landing, scroll story, dashboard, tools) is
[docs/webpage_concept.md](../webpage_concept.md); the site has no dashboard
page since 2026-10-17, and the landing leads straight to the tools.

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

- **The hero.** A large liquid-glass title panel filling the first screen,
  over the living water; its lines rise in when the page opens. Nothing is
  drawn in front of it.
- **Seven sections**, each a header (eyebrow, display headline, subhead) over
  a grid of cards: white sheets for reading, liquid glass for stats, steps
  and callouts.
  1. **The problem:** protein data rarely comes labelled; RNA references do.
  2. **How it works:** trained on RNA, read on protein, zero-shot.
  3. **Explore:** the reference, open in the browser now, with its counts.
  4. **Your data:** five steps from file to download; the service runs
     online, and the Atlas page's Your data tab sends the file.
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
  block rise in once. The count-up maths is pure, in `web/js/motion.js`. The
  text is real HTML; its hidden start states apply only under `html.js`.
- **Reduced motion** gets all the text at once.

## The Workflow page

`web/workflow.html` explains the product start to end, one chapter per step,
following one cell of the PBMC240 example ([workflow.md](workflow.md)). It
uses the same objects: each chapter's figure is a sheet held in view while
its sentences scroll by, and the film's bar is glass. Its figures are data
encodings: cell types take the atlas viewer's palette, RNA and protein their
reserved colours, z-scores a blue to ochre ramp that avoids every reserved
colour. Mechanism pictures with no data say "illustration".

## The Atlas page

`web/atlas.html` is an app view for PC screens: the header, a sidebar of
sheets with two tabs (Explore and Your data), the viewer as one
white halo card, and a drawer that slides over the viewer's right side
([atlas.md](atlas.md)).

- **Reference cells** are dots shaded as small spheres, in the cell-type
  palette (`CLASS_COLOURS`, one copy). The type list is the colour key.
- **Uploaded cells** wear their answer: one type is filled in its colour with
  a white rim; a family answer is a lighter fill with an ink ring; a
  branch answer a paler fill with no ring; no answer a hollow grey ring;
  a cell that cannot be placed stays in the file's cloud as a broken ring.
  Landed, every cell is a bead: larger than any reference dot, in a soft
  halo of its own colour that pulses slowly. Before it flies, the file
  waits beside the atlas as an irregular cloud that breathes; its shape is
  decoration, since the cells have no answers yet. Under reduced motion the
  cloud does not breathe and the halo does not pulse.
  The legend shows each glyph. Hover and selection add an accent ring. No
  reserved colour is used.
- **The waiting animation is an illustration.** The service sends no
  progress, so while it works the six steps loop with an "Illustration"
  bead and the sentence "It shows the steps the service runs, not its
  progress." Its answer bins are equal, so it implies no proportions.
- **The glow** after a landing lights nearby RNA reference cells of the type
  the cell was given, on this map; the legend says so.
- **Motion:** the camera is guided for about 8 to 9 seconds while cells land,
  with Skip (and Esc); any drag or wheel hands it back at once. Under reduced
  motion nothing flies, the camera moves at once, and the waiting state is a
  still list of the steps.
- **Room for the answer.** The sidebar folds away when a file is sent or the
  example starts, and comes back when the visitor is choosing again. Text
  over the map folds: the receipt is open while the landing plays and folds
  to one line after ("Your file · 216 cells · v4.1"); the key is one row of
  the five looks that opens to what each means; the drawer's sections
  (About this answer, Answers, Cells) open and close, under Download and
  Clear. While the drawer is open, the corner buttons and Replay move into
  the space left of it.
- **The sidebar after an answer.** Your data becomes the file's card
  (answer filters, Replay, Download, Clear, Send another file); the setup
  returns with Send another file or Clear. Explore gains Your cells (a
  switch and the same answer filters) and View: the RNA and protein
  switches, names on the map, Dim the reference and Dot size. The
  cross-modal support and alignment diagnostics are research detail and
  sit on the Manuscript page.
- **One cell at a time.** The drawer's cell browser lists every projected
  cell, grouped by the answer it was given, with a swatch in the colour it
  wears on the map; search by name and sort by confidence, file order or
  likeness. The step bar on the map (Previous, "12 of 42 · T cell (a
  family)", Next, Play) and the arrow keys go through the shown cells in
  that order; a cell's card has its own Previous and Next. Selecting a cell
  keeps its possible types bright on the reference and fades the rest (a
  switch in Explore). Explore's Types given shows, hides or isolates the
  cells of one answer.

## The Manuscript page

`web/manuscript.html` is for researchers writing the paper, not for
beginners: an evidence bank in the journal's sections, one claim per line,
its numbers as slots, its source in code type and a caveat bead
(development, in-sample, post-hoc, internal held-out, simulated RNA,
pending). Earlier designs appear only as the problem a part of the served
model fixes ([manuscript.md](manuscript.md)).

## The Motion page

`web/motion.html` is the storyboard for a film about VivOME
([motion.md](motion.md)). A strip of liquid glass lists every scene; then
each scene's still, a 16:9 image with the sheet's halo, stays in view while
its notes scroll by on a sheet: the words on screen (numbers as slots), the
voice-over, the motion notes and the sound, with the tools that render it
as beads and each result's caveat bead.

The film keeps this design system at 1920 by 1080: the site's stylesheet,
type and objects, the cut motif once per headline, RNA and protein in their
reserved colours only where they mean RNA and protein, the atlas palette for
cell types, and the site's white field and gel under every scene, the same
throughout. Depth shows in the objects, which come closer and larger as the
camera goes down, never in the background's colour. Every word and diagram
sits on one of the site's cards, in the site's dark ink: the white sheet in
odd scenes, liquid glass in even ones.

## Shared chrome

The header (the wordmark, then the tool links) and the footer are static
markup copied into each page, so they work without JS and don't shift the
layout. `web/tests/chrome.test.js` pins every copy byte-identical to
`web/index.html`'s, apart from the one `aria-current="page"` marker. Change
one, change all, and add a new page to the test's `PAGES` list.

## Where new results land

The pages read the runs' outputs from data files; the markup does not change
when a release does.

| Output | Lands in | Shown by |
|---|---|---|
| The deployed model and its facts | `manifest.model` (from `service/model/runtime/`) | the `data-fact` slots of the landing, the Workflow page and the Manuscript page |
| Re-exported atlas cells | `web/data/metadata_*_lat128.csv` | atlas viewer; regenerate the manifest for the Manuscript page's cross-modal support and alignment diagnostics |
| Benchmark rows | `manifest.benchmark` | the Manuscript page's benchmark tables |
| A served model's trace, the gene space, the training recipe, the evaluation records | `web/data/workflow.json` (`scripts/build_workflow.py`, built with the manifest) | the Workflow page ([workflow.md](workflow.md)) |
| The served model's evidence for a paper: development, post-hoc and held-out results, diagnoses, designs not kept | `web/data/manuscript.json` (`scripts/build_manuscript.py`, built with the manifest) | the Manuscript page ([manuscript.md](manuscript.md)) |
