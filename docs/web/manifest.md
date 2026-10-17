# The manifest

`web/data/atlas_manifest.json` is the single source of truth for every number the
web pages display. It is generated, never hand-edited.

```bash
python scripts/build_manifest.py
```

The builder reads `web/data/metadata_RNA_lat128.csv` and
`web/data/metadata_PROT_lat128.csv`, the model's evidence tables, and the
committed evaluation and benchmark tables, and writes the manifest. It prints
the cell type summary, the releases and the benchmark's tables so you can
sanity-check the result.

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

`isMeasured()` in `web/js/manifest.js` is the single guard on the display path:

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
- `model` is the current release, v4.1 (first released in 0.4.0, served
  again from 0.6.0):
  - `model.seeds` — the ensemble's member *count* (5), from the v3.1 spec,
    rendered with 0 decimal places (`web/js/panels.js:buildModelCard`);
  - the architecture facts it shares with v3 (`feature_space_size`,
    `encoder_family`, `detected_by_source`); `mask_sampling` is `null`, since
    the members' training setting (T1 NB1b) is not recorded here, and renders
    Pending;
  - `model.evaluation`:
    - `suite`: a title and v4.1's pre-registered evaluation on simulated
      uploads (`research/notebook-outputs/v41_phase3/summary.json`);
    - `served`: SCoPE2, PBMC240 and Fulcher as served
      (`research/benchmark/v41_development/confident.csv`);
    - `recall`: the best guess's recall per type on Fulcher (in-sample) and
      on Khoury (post-hoc).
- `previous_release` is v4.2 (0.5.0), with the same fields and its own
  `evaluation` (`research/benchmark/v42_development/`; its Khoury recall is
  post-hoc, from its one check after release). v4.1's and v3.1's release-card
  builders stay in `scripts/build_manifest.py` without a card.
- `earlier_release` is v3: its seed count (from `v3_tables/reference_seeds.csv`,
  accuracy and CI in `basis`), its architecture facts, its latent centroid
  cosines and modality probe (`v3_tables/`), and its atlas version.
  `first_release` is CrossModalNet's own numbers, kept as the first baseline.
- `benchmark` — signed off by the owner for release 0.4.0; the current
  model's rows were v4.2's in 0.5.0 and are v4.1's again from 0.6.0. `datasets`, one
  per table on `benchmark.html`: Khoury 2026 (post-hoc), Fulcher 2026, PBMC240 and
  both SCoPE2 versions. Each has its `measure`, `chance` (one over the number
  of types scored, or `null`), its `role` (what kind of evidence it is) and
  `rows`: VivOME's two releases first (v4.1, then v4.2), then every corrected
  baseline arm by score. A row's `score` is a measured record, with `sd`, `min`
  and `max` over seeds; `vs_current` is the current model minus that arm by
  paired bootstrap (the counts favouring each side, and the difference with
  its CI or its range); the tables comparing v4.2 with v4.1 hold v4.2 minus
  v4.1, and the builder turns them round. On Khoury 2026, every row is
  post-hoc. Sources: `research/benchmark/v41_development/`, `research/benchmark/v42_development/`,
  `research/benchmark/baselines_corrected/`,
  `research/benchmark/khoury2026_posthoc/` and
  `research/benchmark/khoury2026_posthoc_v41_check/`.
- `latent_centroid_cosine`, `modality_probe_accuracy` — measured for the 2
  cross-modal classes (macrophage, monocyte) in v3.1's coordinate member's
  latent space, from `service/model/evidence/v3_1_tables/latent_centroid_cosine.csv`
  and `modality_probe.json` (`scripts/v31_evidence.py`, which first reproduces
  v3's committed tables by the same method). The probe is one **global** score
  (a linear classifier's accuracy telling RNA from protein in the latent
  space), repeated on both cross-modal rows — not a per-class measurement,
  hence the "global metric, not per-class" wording in its `basis`.

- `model_card` — v3's accuracy table on `web/versions.html` ("v3 model card"):
  - RNA to RNA on test cells, from `research/notebook-outputs/nb1/rna_to_rna_membership_corrected.csv`;
  - SCoPE2 protein, restricted and unrestricted, shipped checkpoint and
    5-seed mean, each under both decision rules, from the nb1d seed scores
    and family summary.

  Every row names its rule (`nearest centroid (the service's rule)` or
  `shared kNN (the benchmark's rule)`), because a seed and a mean compare
  only under the same one. `vs_scanvi` counts the seed pairings v3 wins
  against scANVI, from `paired_bootstrap_ours_vs_scanvi.csv`. The page's
  prose reads these through `factText` data-fact slots, so no model-card
  number is typed into HTML.

Emitted as pending, with the phase that will produce each:

| Metric | Phase | Blocked on |
|---|---|---|
| `latent_centroid_cosine`, `modality_probe_accuracy` for RNA-only/protein-only classes | N/A | No cross-modal coverage for those classes — a correct record, not a gap to fill |
| `transfer_accuracy` (any class) | N/A | A real measurement exists, but only per *dataset* (`service/model/evidence/v3_tables/rna_to_rna_real_masks.csv`), not per class — no per-class version has been computed |

A class present in only one modality gets a Phase 2 pending record for
`pca_centroid_cosine` — there is no paired coverage to compute it from. A
degenerate centroid (zero norm) also yields pending rather than a fabricated
cosine; `cosine()` returns `None` and the builder converts it.

## Architecture

`next_reference` is `null` in the current manifest — the last architecture
change it described (`CrossModalNet` to the frozen RNA-only v3 reference) is
complete, so there is nothing "next" to report. `web/js/panels.js:buildNextReferenceCard`
still renders a non-null value, kept as real, tested code for whenever the
next change starts — but `build_deployed_architecture_facts` is **not** a
drop-in source for it: that function now returns only the facts folded into
`model` (`feature_space_size`, `previous_feature_space_size`,
`detected_by_source`, `encoder_family`, `mask_sampling`). Populating
`next_reference` again means also supplying `trained` (`false`) and `note`
(why it isn't trained yet) — `buildNextReferenceCard` reads both and
`escapeHtml(undefined)` renders the literal string `"undefined"` if `note`
is missing. Until then, those facts live on `model` directly. `first_release` is a
separate, permanent record of `CrossModalNet`'s own numbers, and
`previous_release` and `earlier_release` of v4.1's and v3's, all kept as
documented history rather than erased.

## Current output

Atlas version `0.6.0`, schema `1.0`. 22 cell types: 2 cross-modal, 20
RNA-only, 0 protein-only. RNA 85,233 cells across 22 classes; protein 1,490
cells (SCoPE2 mass spectrometry).

## The Workflow page's companion file

`web/data/workflow.json` holds what only the Workflow page needs: the trace
of the PBMC240 example through the served model, a sample of the atlas, the
gene space, the training recipe and the evaluation records. It is built by
`scripts/build_workflow.py`, which `main()` here runs after writing the
manifest, so the two are always built together; its `built_for` must equal
this manifest's release. Its numbers are records in the same measured or
pending shape. See [workflow.md](workflow.md).

## Consumers

`web/js/manifest.js` loads, validates, and formats. `web/js/panels.js` turns the
result into HTML strings. Both are pure — no DOM, no side effects — which is
what lets the same code be unit-tested under Node and assigned to `innerHTML`
in the browser.

| Panel builder | Page |
|---|---|
| `buildSupportSummary`, `buildSupportTable`, `buildDiagnosticsTable` | `atlas.html` |
| `buildBenchmarkTable` | `benchmark.html` |
| `buildModelCard`, `buildEvaluationTable`, `buildPreviousReleaseCard`, `buildPreviousEvaluationTable`, `buildEarlierReleaseCard`, `buildPriorBaselineCard`, `buildAvailabilityTable` | `versions.html` |
| `buildSupportedLabelSpace` | `project.html` |
| `buildModelCardTable` | `versions.html` |
| `buildReleaseStatus`, `buildNextReferenceCard` | `home.html` |
| `buildProofPoints`, `factText` (the `data-fact` slots in prose) | `index.html`, `versions.html`, `benchmark.html` |

Every interpolated value goes through `escapeHtml()`. Cell-type names come
from data, and `web/tests/fixtures.js` deliberately names one class
`<script>alert(1)</script>` so the suite proves it.

## Release protocol

1. Freeze inputs — record accession numbers, download dates, and checksums for every dataset.
2. Train and export. If the served model changed, re-run
   `python scripts/trace_workflow.py` (the Workflow page's trace,
   [workflow.md](workflow.md)). Then regenerate the manifest, which also
   rebuilds `web/data/workflow.json`.
3. Bump `ATLAS_VERSION` in `scripts/build_manifest.py` and commit the regenerated manifest.
4. Tag the release and archive it for a persistent identifier.
5. Record label stability against the previous version and add it to `versions.html`.

Label stability is not yet measured for any release. 0.6.0 answers every
upload exactly as 0.4.0 (both serve v4.1). 0.5.0 answered RNA uploads as
0.4.0; on protein uploads its best guess changed, and with it some answers,
since each set holds the best guess, so the share that changed still needs
computing. v3 answers at class level only, so
comparing it with the later releases needs a definition first.

## Tests

```bash
node --test                                  # web/tests/manifest.test.js, panels.test.js, lfs.test.js
python -m unittest discover -s scripts     # test_build_manifest.py + repo path check
```

The JS suites share `web/tests/fixtures.js`, one manifest shaped like the real
generated file. If you change the schema, change the fixture — the suites
read the key set and the metric records from it.
