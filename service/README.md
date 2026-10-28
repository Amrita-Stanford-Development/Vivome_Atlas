# Projection service

Implements the Phase 5 backend behind `POST /api/project`, whose contract
is published at [`../docs/service/projection-api.md`](../docs/service/projection-api.md)
(unchanged by this work — see that file for the wire schema). This directory
is a separate concern from the rest of the repo: the static site in
`web/` has zero dependencies by design (`CLAUDE.md`); this backend
does real inference and has real dependencies (`requirements.txt`), kept
entirely contained here.

## Design source

Every pipeline decision below came from a specific measured failure in this
project, documented in full in [`../docs/service/context-brief.md`](../docs/service/context-brief.md)
and [`../docs/service/download-checklist.md`](../docs/service/download-checklist.md) — relocated
here verbatim from the staging area they were written in, so the original
rationale stays in the repo, not just this document's paraphrase of it.

Two pipeline designs share stages 1, 2 and 8. **v3.1** (T1 NB2's
specification in `model/v3_1/nb2_spec_v31.json`, built in
`pipeline/ensemble.py`) replaces stages 3 to 7. **v3** (an earlier
release) keeps them. **v4.1**, the default (release 0.6.0, as in 0.4.0),
is v3.1 with a different best guess (`pipeline/fusion.py`, below), and
**v4.2** (release 0.5.0) is v4.1 with protein class means for protein
uploads; every stage in this table is v3.1's in both. Stage by stage:

| Stage | v3.1 (and v4.1 the default, v4.2) | v3 (an earlier release): file, and the decision that looks wrong at first glance |
|---|---|---|
| 1. Query alignment | shared | `pipeline/alignment.py`: zero-fill the full 9,002-gene space; never restrict to well-covered genes |
| 2. Fuzzy smoothing | shared | `pipeline/smoothing.py`: build the neighbour graph from the query's own full feature set, not the shared space |
| 3. Reference encoder | Five V2 encoders (NB1b's mini-upload gene z variant, v3's architecture and input shape) | `pipeline/encoder.py`: module pooling + explicit mask channel; uniform random masking beat detection-mimicking masking twice |
| 4. Label assignment | Each member: softmax of cosine to its class centroids over its fitted temperature; the ensemble averages the probabilities. All 22 classes; no per-upload label space | `pipeline/assignment.py`: nearest-centroid beat OT on real protein data, inverting an RNA-only-derived recommendation; unbalanced OT (still implemented) needs a **relaxed** marginal (tau ~0.1), and tightening it once collapsed accuracy from 72% to 47%. Restricting to the 2 classes with cross-modal support swings balanced accuracy by 48.7 points on SCoPE2 and is opt-in (below) |
| 5. Conformal calibration | Mondrian: one threshold per class, from NB2 (`calibration.MondrianCalibrator`) | `pipeline/calibration.py`: calibrate on a **random** query slice, never confidence-filtered |
| 6. Abstention | Out of distribution when the members' mean max cosine to any reference cell is below NB2's fixed 0.779 (`abstention.V31AbstentionScorer`) | `pipeline/abstention.py`: max cosine similarity to any single reference cell, never neighbour vote share |
| 7. The answer | One class; or the group or lineage the conformal set shares; or abstain with a reason (`ensemble.resolve`). Every cell not refused for coverage also gets a best guess | `pipeline/fallback.py`: five distinct confusable pairs implemented (the brief names six phrases, but two name the same pair); only one is reachable under restriction, see "Known sharp edges" |
| 8. Property transfer | shared, through one member (`config.V31_COORDINATE_MEMBER`, seed 4), the one the site's atlas coordinates come from | `pipeline/transfer.py`: only 6 of 8 candidate properties passed validation; ship those with an uncertainty, not all with a caveat |

Read the module docstrings for the numbers behind each of these — they are
not defaults, they are validated findings, several of them counter to what
looks like the safer or more obvious choice.

## What exists today

Every contract artifact is real.

- **v3.1:** `model/v3_1/` holds NB2's specification, a `MANIFEST.json` of
  sha256s checked on load, and each member's reference latents and class
  centroids. The five member checkpoints live outside git (below).
- **v3:** `model/runtime/` holds `reference_model.pt` (the trained v3
  checkpoint), `reference_embedding.npy`, `reference_centroids.npy`,
  `provenance.json`, and per-cell property values.

See `model/README.md` for the complete list, and its "Known gaps" for v3's
two items that are real but not fully wired in. The assignment-method
comparison hasn't been re-run inside the restricted candidate set. The
abstain threshold is still computed live, not taken from `provenance.json`'s
calibrated value.

Every pipeline stage is implemented, tested (`tests/`, against synthetic
reference fixtures at the real 85,233-cell scale, deliberately kept
synthetic for speed and determinism rather than loading the real ~130MB of
arrays), and running against the real artifacts above. `POST /api/project`
serves real predictions end to end. It is hosted on Google Cloud Run
(v4.1; `deploy/huggingface/PUBLISH.md`): the Atlas page's Your data tab
(`web/atlas.html`) sends uploads there by default, or to a copy the visitor
runs locally, checking
`GET /api/status` first, and the service answers only allowed origins
(`config.ALLOWED_ORIGINS`).

The dev placeholder checkpoint (`model/legacy/dev/H_seed4.pt`) is no longer the
default — `config.DEV_CHECKPOINT_PATH` still exists and
`service/tests/test_encoder.py` still exercises it explicitly (the warn-path
guard must keep firing for anything that points at it deliberately, e.g. a
`VIVOME_ENCODER_WEIGHTS` override).

## Known sharp edges

Two correctness bugs were found in review after the initial build and are
now fixed and regression-tested; both are the kind of thing that's easy to
reintroduce by accident, so they're documented here rather than only in the
commit that fixed them.

**Centroid row position is not the dataset's `class_idx`.**
`assignment.assign_labels`, `assignment.top_label`, and
`calibration.calibrate_and_build_sets` all work in *positional* centroid-row
space (0..n_classes-1) — they never see the reference's real `class_idx`
values. `pipeline.py` translates position to class name through
`ReferenceMetadata.classes`' own ordering (sorted by `class_idx`, matching
the centroids array per the contract), never by treating a position as if
it *were* the class_idx. The current 22-class reference happens to have
`class_idx` running 0..21 with no gaps, so a position-as-class_idx bug would
not show up against it — `service/tests/test_pipeline.py`'s
`NonContiguousClassIdxRegressionTests` uses a synthetic reference with
`class_idx` values `{10, 20, 30, 40}` specifically so this can't hide again.

**A Stage 7 fallback-resolved label reports the winning share *within the
pair*, not the pair's summed probability.** This inverted once already.
Summed probability was right when Stage 4 competed across all 22 classes —
it measured how much total mass the broader claim captured. It stopped
being meaningful once `config.CROSS_MODAL_SUPPORTED_CLASSES` restricted
Stage 4 to exactly the two classes in the only pair that can still trigger
this branch (macrophage/monocyte). The two probabilities then always sum to
~1.0 by construction, so summed confidence would read 1.0 for every
resolved cell regardless of whether the split was 50/50 or 99/1. The
winning share, normalised within the pair, is what actually varies. See
`service/pipeline/pipeline.py`'s Stage 7 comment and
`service/tests/test_pipeline.py`'s `FallbackConfidenceTests`.

Since the restriction became opt-in (below), the default is unrestricted
again. That is the case where summed confidence carried information, so
which rule to use per mode is open again (Track C in `research/todo.md`).
The rule is now chosen per label-space method (`config.FALLBACK_CONFIDENCE`,
`fallback.pair_confidence`); both modes keep the winning share until it is
measured.

**The macrophage/monocyte restriction is opt-in per request** (form field
`restrict_to_supported_classes`, default false; see
[`../docs/service/projection-api.md`](../docs/service/projection-api.md)).
Restricting Stage 4 to `config.CROSS_MODAL_SUPPORTED_CLASSES` lifts v3's
balanced accuracy on SCoPE2 from 0.68% to 20.21%, because SCoPE2 only
contains those two types. That is still below the two classes' 50% chance:
v3 calls most SCoPE2 macrophages monocytes
([bugs-and-fixes](../research/benchmark/bugs-and-fixes.md), 8). It is wrong
for anything else. Given a Fulcher 2026 PBMC upload,
the restricted service labelled every cell it didn't abstain on as
macrophage or monocyte. Restricted, `resolve_fallback` can match only that
one pair. Unrestricted, the default, all five `CONFUSABLE_PAIRS` are
reachable.

**Identical uploads give identical responses.** The Stage 5 calibration
subset is drawn from a generator seeded with a hash of the upload
(`pipeline.upload_seed`). Before this, it was unseeded, and the same file
could return different abstentions.

**Each gene is z-scored in float64** (`alignment.zscore_per_gene`, Stages
1 and 2), as the notebooks' convention does, and returned in float32. A
gene whose observed values agree to about five significant digits
(`config.ZSCORE_NEAR_CONSTANT_SPREAD`) is 0, like a gene with one value: its
differences are rounding. In float32 the mean of a gene whose few values
differ by far less than their level was off by up to 0.0016
(`research/notebook-outputs/value_scale_zscore/`).

**A request may state a protein upload's value scale** (form field
`value_scale`: `auto`, `linear` or `log`, and with `log` what a 0 means,
`zeros`: `missing` or `measured`; see
[`../docs/service/projection-api.md`](../docs/service/projection-api.md)).
Stage 0's median rule reads linear tables on a small scale as log
(`research/notebook-outputs/value_scale_step1/`), so the user can say which
the file is. `alignment.median_rule` is the rule, `alignment.apply_reading`
applies a reading, and `detect_and_transform_value_scale` runs both, with
the stated reading winning. Every version receives them as `stated_scale`
and `stated_zeros` (`pipeline.run_projection`, which refuses either on an
RNA upload), v4.2's protein query included. With no field,
Stage 0 and the reply are unchanged byte for byte
(`research/notebook-outputs/value_scale_phaseA/`).

**Pipeline versions.** `config.PIPELINE_VERSION` (env
`VIVOME_PIPELINE_VERSION`) chooses which bundle loads, and with it the label
space, conformal and abstention components (`pipeline.components_for`).
- **`v4.2`, the default in release 0.5.0 and selectable since,** is v4.1 with protein class
  means from sorted cells (Rieckmann et al. 2017) in the correlation term,
  for protein uploads and the classes they cover (`model/v4_2/`,
  `scripts/build_v42_spec.py`); an RNA upload is answered exactly as by
  v4.1. `service/tests/test_v42.py` checks it against its notebook cell by
  cell.
- **`v4.1`** is v3.1's answers with a
  fused best guess (`pipeline/fusion.py`): the encoder's probability joined
  with each cell's correlation to the reference's class means, where that
  term carries signal. Its spec is `model/v4_1/spec_v41.json`; it reads v4's
  data files from `model/v4/` (`scripts/build_v4_bundle.py`) and v3.1's
  members. `benchmark/v41_dev_gate.py` and `service/tests/test_v41_gate.py`
  check it per cell. `v4` is the same code with the encoder weighted 0.7
  instead of 0.5.
- **`v3.1`** is T1 NB2's five-encoder ensemble
  (`pipeline/ensemble.py`), with its files in `model/v3_1/`.
  - Its five checkpoints live outside git. Fetch them with
    `python scripts/fetch_v31_members.py`; until then the service answers
    503 and names the missing file.
  - `service/tests/test_ensemble.py` checks it against NB2's own code.
  - `benchmark/v31_dev_gate.py` checks it against NB2's development-data
    table.
- **`v3`** is the single-encoder pipeline.
  `service/tests/test_pipeline_versions.py` pins it against full responses
  frozen before the switch existed, in both label-space modes.

The response schemas are in
[`../docs/service/projection-api.md`](../docs/service/projection-api.md).

## Running it

```bash
pip install -r service/requirements.txt
python -m service.app        # from the repository root
```

It listens on `127.0.0.1:8001`, projects one upload at a time, and accepts
at most 2,000 cells and 100 MB per upload. Every setting comes from the
environment (`VIVOME_HOST`, `VIVOME_PORT`, `VIVOME_MAX_UPLOAD_CELLS`, and the
rest listed in [`../docs/service/projection-api.md`](../docs/service/projection-api.md)).
The hosted copy answers only through its website: with `VIVOME_PROXY_SECRET`
set, a request without that secret in `X-VivOME-Proxy-Secret` gets 403 (the
site's `/api` door, `deploy/pages/api-proxy.js`, adds it). A copy run at home
leaves it unset and answers every request.
The 2,000-cell default comes from timing: one projection's time grows faster
than its cell count (`config.py` has the measurements).

## Hosting

`deploy/huggingface/` packages the service as a Hugging Face Space (Docker,
CPU): `build_space.py` stages the service and only the served version's
model files, `check_space.py` compares a running copy with this repository's
own run, and `PUBLISH.md` has the steps.

## Tests

```bash
python -m unittest discover -s service/tests -t .   # from the repository root
```
