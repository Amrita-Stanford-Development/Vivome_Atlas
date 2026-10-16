# The Workflow page

`web/workflow.html` shows how VivOME works, start to end: the data, the
shared genes, the training, one cell's path from an uploaded file to its
answer, and how the results were calculated. It is for people new to the
project: a guide, a collaborator, a reviewer.

## What it shows

A cold open and 13 chapters, each a pinned scroll story. When a chapter's
stage (its heading, its sentences and its figure) reaches the middle of the
window it holds still, and scrolling plays the figure's animation instead
of moving the page; when the animation ends, the stage lets go and the page
moves on. The scroll it takes is the chapter's runway, 0.8 of the window's
height per sentence (`RUNWAY_PER_BEAT` in `web/js/workflow.js`). Each
chapter's sentences are its beats (`<p data-beat>`); its progress, 0 to 1,
is split evenly between them, and the sentence being played is highlighted.
Where the sentences do not all fit beside the figure, and on narrow screens,
they share one place and cross-fade, with dots for the chapter's progress.
A chapter's details, lookups and readouts follow its stage, unpinned.

| Chapter | Figure | Data |
|---|---|---|
| One cell, start to end | the cell's raw column, then its path to an answer | `trace.detail` |
| Two kinds of data | cells per reference type, grouped by lineage; the protein lists | `reference.classes`, `gene_space.sources` |
| What the files look like | PBMC240's report, its headers, detection histograms | `trace.detail[].raw_row`, `raw.pbmc240.parse`, `raw.snippets` |
| One vocabulary of genes | the funnel to the shared genes, the source combinations, module sizes; a gene lookup | `gene_space` |
| Trained on RNA only | the encoders, a batch, masked views, the training forces, the encoder choice | `training` |
| An upload arrives | the scale, merged rows, identifier matching | `raw.pbmc240` |
| Matching and the mask | the 9,002-gene mask, observed genes per cell, a heatmap from log2 to scaled | `raw.pbmc240.align`, `trace.heatmap` |
| Smoothing | the upload's neighbour graph, own and smoothed values, the mask | `trace.stages.smoothing`, `trace.heatmap` |
| The encoder pass | the layers, the cell's 128 numbers, module coverage | `trace.stages.encoder`, `trace.detail[].embedding` |
| From a point to probabilities | the class compass: cosines, each encoder's probabilities, the mean | `trace.detail[].members`, `.ensemble` |
| The best guess | encoders, correlation and fused; the agreement gate; the simulated uploads | `trace.detail[].guess`, `trace.stages.fusion`, `evaluation.uploads` |
| The answer, or the reason | each type's bar, similarity against the threshold, the hierarchy, every outcome | `trace.cells`, `trace.stages.calibration`, `.ood` |
| Where the cell lands | the reference in 3D, the uploaded runs, the cell's neighbours and properties; its JSON response | `reference.sample`, `trace.cells[].xyz`, `trace.detail[].neighbours`, `.response` |
| How the results were calculated | the simulated suite, the Fulcher 2026 benchmark, the internal held-out test, the live service | `evaluation`, the manifest's `benchmark`, `service` |

**The followed cell.** Every figure follows one PBMC240 run: by default the
file's first, or any other picked by outcome or searched for. The trace
records the full arrays (raw column, every encoder's probabilities, the
best guess's three views, the neighbours, the JSON response) for the story
runs only: the first run and the first run of each outcome. For another run
the figures that need them show the story run with the same outcome, and
say so. PBMC240's labels from markers are weak; the page calls them that.

**The film.** "Play the whole story" opens a theatre over the page and
plays every chapter in turn, about eight minutes, with the chapter's beats
as captions (`web/js/film.js`; the clock is `web/js/timeline.js`). Space
pauses, the arrows skip chapters (with Shift, five seconds), C turns
captions off, Esc closes. The address keeps the place, so a link opens the
film there: `workflow.html#film&t=95.5&cell=3`. Adding `&present` gives a
16:9 frame for screen recording. A hidden tab pauses the film.

## Where the numbers come from

- **The release's facts** (model name, evaluation, benchmark) come from the
  manifest, through `factText` (`web/js/panels.js`), as on every page.
- **Everything else** comes from `web/data/workflow.json`, the page's
  companion to the manifest, built by `scripts/build_workflow.py` (standard
  library only). `scripts/build_manifest.py` runs it at the end of its main,
  so the two files are always built together. Its `facts` hold every number
  a sentence cites, as records shown through `wfFact`
  (`web/js/workflow-data.js`) and the same `isMeasured` guard. The arrays the
  figures draw are raw data from the same sources; `sources` holds the
  sha256 of each.
- **The trace.** `scripts/trace_workflow.py` runs
  `service/examples/pbmc240_proteins_raw.tsv` through the served model's own
  functions, stage by stage, checks its answers against
  `pipeline.run_projection` on every cell before writing anything, and
  writes `service/model/evidence/workflow/pbmc240_trace_v42.json.gz` and
  `input_snippets.json`. It needs torch and v3.1's members, so it is run by
  hand, not by `build_manifest.py`.
- **The browser computes no model output.** Every control chooses among
  recorded values; `web/tests/workflow.test.js` fails if a workflow module
  calls `Math.exp`. The mechanism pictures (a training batch, the four
  training forces, a bootstrap draw) are illustrations with no numbers, and
  say so.

## When the served model changes

1. `python scripts/trace_workflow.py` (the trace is named for the version it
   traces; a new version means a new file name, its citations and its index
   line).
2. `python scripts/build_manifest.py`, which rebuilds `workflow.json`.
3. The tests below.

`workflow.json`'s `built_for` must equal the manifest's release
(`scripts/test_build_workflow.py`), the trace must equal a fresh run
(`service/tests/test_workflow_trace.py`), and the page shows a banner if
the two files it loads come from different releases (`checkSync`).

## Code

| File | Role |
|---|---|
| `web/workflow.html` | the page: chapters, beats, number slots, figures, the film bar and theatre |
| `web/css/workflow.css` | its layout, the film, reduced motion and print |
| `web/js/workflow.js` | the controller: loads both files, fills slots, the followed cell, scroll progress, lazy scenes |
| `web/js/film.js` | film mode |
| `web/js/timeline.js` | the chapters, their lengths and beats, the clock and the address (pure) |
| `web/js/workflow-data.js` | loading, checking and reading `workflow.json`; the class colours (pure) |
| `web/js/workflow-panels.js` | HTML builders: tables, cards, the ladder, the JSON response (pure) |
| `web/js/workflow-svg.js` | static SVG figures: tree, heatmap, ROC (pure) |
| `web/js/workflow-layout.js` | layout maths: scales, Sankey, compass, colour ramps, the 3D view (pure) |
| `web/js/scene-kit.js` | canvas helpers shared by the scenes |
| `web/js/scenes-input.js`, `scenes-model.js`, `scenes-evidence.js` | the chapters' figures, loaded when their chapter comes near |

Each scene is `createScene(el, ctx) -> {render(p, state), resize(),
dispose(), describe(state), table(state)}`; a frame depends only on the
chapter's progress and the followed cell, so scrolling, the film and
scrubbing draw the same frame. Figures are canvas 2D; the page loads no
WebGL of its own, so it works where the living water is switched off.

## Rules it keeps

- The site's copy rules (`docs/web/design.md`): sentence case, no em dashes,
  none of the banned words, the reserved colours only for what they mean
  (RNA and protein in the data chapters and the 3D view).
- Cell-type colours are the atlas viewer's palette, by class position
  (pinned by `web/tests/workflow.test.js`).
- Under reduced motion nothing animates: each figure shows the finished
  frame of the beat being read, and the film steps from beat to beat.
- In print, the text, the panels and the static figures show; the chrome
  and the film do not.

## Tests

- `web/tests/workflow.test.js`: every number slot is measured in the real
  files; the copy rules; the chapters match the film's; escaping; the
  palette; the service address; no model maths in the browser.
- `web/tests/timeline.test.js`, `web/tests/workflow-layout.test.js`: the
  clock, the address, the layouts and the colour ramps.
- `scripts/test_build_workflow.py`: the committed file is the builder's
  output, within its size budget, built for the manifest's release.
- `service/tests/test_workflow_trace.py`: the trace equals a fresh run.
