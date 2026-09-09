# The manifest

`Atlas/atlas_manifest.json` is the single source of truth for every number the
web pages display. It is generated, never hand-edited.

```bash
python3 tools/build_manifest.py
```

The builder reads `Atlas/metadata_RNA_lat128.csv` and
`Atlas/metadata_PROT_lat128.csv` and writes the manifest. It prints the cell
type summary so you can sanity-check the result.

## The measured/pending contract

Every metric is a record in one of two disjoint shapes:

```json
{ "value": 0.998634, "status": "measured", "basis": "3-PC projection" }
{ "value": null,     "status": "pending",  "phase": "Phase 2", "note": "why" }
```

A `measured` record carries the **basis** on which it was computed. A
`pending` record carries the **phase** of the implementation plan that will
produce it, and a note saying what is missing. `metricBasis()` coalesces the
two, so a panel shows either the basis or the phase without branching.

`isMeasured()` in `js/manifest.js` is the single guard on the display path:

```js
metric?.status === 'measured'
  && metric.value !== null
  && Number.isFinite(Number(metric.value))
```

Anything else renders as `Pending`. This is the one decision that keeps
unmeasured quantities off the page — a metric that later becomes measured
stops looking pending with no edit to any panel.

Counts are bare scalars rather than metric records, so they have their own
guard, `formatCount()`. Without it a truncated manifest would render `NaN` or
`undefined` as an authoritative cell count.

`validateManifest()` checks the required top-level keys and refuses a
`schema_version` other than `1.0`, naming what is wrong. Pages call
`loadManifest()`, which validates before returning, and render `errorPanel()`
on failure — never a blank panel or a stale number.

## What is computed, and what is not

Computed from repository data:

- Per-class cell counts for both modalities
- Cross-modal support classification (`cross_modal`, `rna_only`, `prot_only`)
- `pca_centroid_cosine` — cosine similarity between RNA and protein class
  centroids **in the 3-PC projection**, for classes present in both modalities

Emitted as pending, with the phase that will produce each:

| Metric | Phase | Blocked on |
|---|---|---|
| `latent_centroid_cosine` | Phase 1 | 128-d latent coordinate export |
| `transfer_accuracy` | Phase 1 | Multi-seed transfer evaluation |
| `model.seeds` | Phase 1 | Ten-seed statistics; current build is a single run |
| `modality_probe_accuracy` | Phase 4 | Linear modality probe run |
| `benchmark.rows` | Phase 4 | No comparison against established methods has been run |

A class present in only one modality gets a Phase 2 pending record for
`pca_centroid_cosine` — there is no paired coverage to compute it from. A
degenerate centroid (zero norm) also yields pending rather than a fabricated
cosine; `cosine()` returns `None` and the builder converts it.

## Current output

Atlas version `0.1.0`, schema `1.0`. 22 cell types: 2 cross-modal, 20
RNA-only, 0 protein-only. RNA 85,233 cells across 22 classes; protein 1,490
cells (SCoPE2 mass spectrometry).

## Consumers

`js/manifest.js` loads, validates, and formats. `js/panels.js` turns the
result into HTML strings. Both are pure — no DOM, no side effects — which is
what lets the same code be unit-tested under Node and assigned to `innerHTML`
in the browser.

| Panel builder | Page |
|---|---|
| `buildSupportSummary`, `buildSupportTable`, `buildDiagnosticsTable` | `atlas.html` |
| `buildBenchmarkTable` | `benchmark.html` |
| `buildModelCard`, `buildAvailabilityTable` | `versions.html` |
| `buildSupportedLabelSpace` | `project.html` |

Every interpolated value goes through `escapeHtml()`. Cell-type names come
from data, and `tests/fixtures.js` deliberately names one class
`<script>alert(1)</script>` so the suite proves it.

## Release protocol

1. Freeze inputs — record accession numbers, download dates, and checksums for every dataset.
2. Train and export, then regenerate the manifest.
3. Bump `ATLAS_VERSION` in `tools/build_manifest.py` and commit the regenerated manifest.
4. Tag the release and archive it for a persistent identifier.
5. Record label stability against the previous version and add it to `versions.html`.

Label stability is not yet measured — it is reported from the first release
that has a predecessor to compare against.

## Tests

```bash
node --test                                  # tests/manifest.test.js, panels.test.js, lfs.test.js
cd tools && python3 -m unittest discover     # test_build_manifest.py
```

The JS suites share `tests/fixtures.js`, one manifest shaped like the real
generated file. If you change the schema, change the fixture — the suites
read the key set and the metric records from it.
