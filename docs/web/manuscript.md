# The Manuscript page

`web/manuscript.html` collects everything in this repository that a journal
paper on the served model can use, sorted under the sections of a Molecular
& Cellular Proteomics "Technological Innovation and Resources" article. It
replaced the Benchmark page; its benchmark tables are in Results
(`manuscript.html#benchmark`), and `scripts/build_pages_site.py` redirects
the old address.

It describes the served model only (v4.1). Earlier designs appear only as
the problem a part of the served model fixes, named by what they did. The
served model's answers without its second opinion are its own answer path,
so a comparison with them is an ablation.

## Sections

| Section | Holds |
|---|---|
| Title, highlights, in brief, abstract | candidate wording and the claims each would make |
| Introduction | the problem as this project's data show it, the contributions, the framing (label transfer, not a mixed space), references to collect |
| Experimental procedures | the reference, the gene space, reading an upload, the encoder, the answer layer, the second opinion, the datasets and their roles, the simulated suite, the benchmark protocol, pre-registration, implementation |
| Why each part is there | one row per part: the problem in an earlier design it fixes, the evidence, the alternative rejected |
| Results | transfer, the atlas's cross-modal support and alignment diagnostics, answer levels and coverage, the second opinion and its gate, the benchmark tables, the internal held-out test, failure modes, other organs (the colon, the lung and the lymph node, each organ's gates from its gate run), what was tried and not adopted |
| Discussion | what the evidence supports and does not yet, lessons, threats to validity, next steps |
| Availability, supplement, figures | accessions and code; the supplemental tables; the list of figures and tables, with downloads |
| Before submission, reviewer questions | open items (pending records) and the answers a reviewer will need |

## The evidence line

Each line is one claim, then its source and a caveat bead:

```html
<li>Fulcher 2026: balanced accuracy <span data-ms="fulcher_ba"></span>; ...
    <span class="ev-src"><code>research/...</code>
    <span class="bead caveat" data-caveat="in-sample">in-sample</span></span></li>
```

The caveat vocabulary is `CAVEATS` in `web/js/manuscript-data.js`:
development, in-sample, post-hoc, internal held-out, simulated RNA,
pending. The page's legend explains each one.

## Where the numbers come from

No number is typed into the page. Each `data-ms` slot names a record in
`web/data/manuscript.json`, and `msFact` shows it through `isMeasured`;
hovering a number shows its basis (the file and field). `data-fact` slots
read the manifest through `factText`. Three panels in Results are built
from the manifest by `web/js/panels.js`, through the same guard: the
cross-modal support (`buildSupportSummary`, `buildSupportTable`), the
alignment diagnostics (`buildDiagnosticsTable`) and the benchmark tables
(`buildBenchmarkTable`). Protocol constants (a 95% interval,
k = 30) are marked `<span class="constant">`, and
`web/tests/manuscript.test.js` fails on any other typed percentage or
decimal.

`scripts/build_manuscript.py` writes the records, standard library only:

- from committed results: `research/notebook-outputs/` (the evaluation
  suite, the weight selection, the gate exploration, the diagnoses, the
  negative results), `research/benchmark/` (development, post-hoc and
  held-out records, the corrected baselines) and `service/model/` (the
  specs, the reference's cells, the gene space);
- from `web/data/workflow.json`: the settings, the encoder and the service
  records the Workflow page already holds, copied with their basis.

Shares and differences are fractions (formats `pct1`, `pct2`, `points`,
and `pp` for a size without its sign); the Workflow page's formats pass
through. The four open items are pending records and read Pending until
the work is done; `scripts/test_build_manuscript.py` pins that set.

## Rebuilding

`python scripts/build_manifest.py` builds the manifest, then the workflow
data, then the manuscript data, so all three are built for one release
(`built_for`). The page refuses to mix files from different releases.

The builder refuses to run if the manifest's model is not v4.1: when the
served model changes, the page's wording changes with it, and the builder
is updated in the same commit.

## Figures

Each figure and Methods illustration is one module in `scripts/figures/`,
drawn by `scripts/build_figures.py` from the repository's committed data
(run it in the vivome environment, which has matplotlib):

- `web/figures/<NAME>.svg` is what the page shows, and `NAME.csv` every number
  it draws, with the file and field it came from (the page shows it as a
  table on request);
- `web/figures/index.json` holds each figure's title, legend, alt text,
  section and sources; `web/js/figures.js` places each one in its slot,
  `<div class="ms-figure-slot" data-figure="NAME">`, at the end of the
  subsection whose result it supports, and lists them all in the Figures
  section;
- `--journal` also writes a PDF and a print-resolution TIFF of each into
  `research/figures/journal/` (gitignored), at the journal's widths.

A module splits what it shows (`data()`, standard library only: every
number a row naming its source file and field) from how it is drawn
(`draw()`), so the scripts suite checks each figure's numbers on any Python,
and, with matplotlib, that the committed pictures are what the data draws
now. Nothing in a figure is typed in, legends included. One style for all
(`scripts/figures/style.py`): the site's colours, RNA and protein in their
reserved colours, cell types named by position rather than by colour.
