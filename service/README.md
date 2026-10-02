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

Two pipeline versions share stages 1, 2 and 8. **v3.1** (the default, T1
NB2's specification in `model/v3_1/nb2_spec_v31.json`, built in
`pipeline/ensemble.py`) replaces stages 3 to 7. **v3** (the previous
release) keeps them. Stage by stage:

| Stage | v3.1 (default) | v3 (previous release): file, and the decision that looks wrong at first glance |
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
serves real predictions end to end. It is not hosted: `web/project.html`
sends uploads to a service the visitor runs locally, checking
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
Restricting Stage 4 to `config.CROSS_MODAL_SUPPORTED_CLASSES` lifts SCoPE2's
balanced accuracy from 31.08% to 79.79%, because SCoPE2 only contains those
two types. It is wrong for anything else. Given a Fulcher 2026 PBMC upload,
the restricted service labelled every cell it didn't abstain on as
macrophage or monocyte. Restricted, `resolve_fallback` can match only that
one pair. Unrestricted, the default, all five `CONFUSABLE_PAIRS` are
reachable.

**Identical uploads give identical responses.** The Stage 5 calibration
subset is drawn from a generator seeded with a hash of the upload
(`pipeline.upload_seed`). Before this, it was unseeded, and the same file
could return different abstentions.

**Two pipeline versions.** `config.PIPELINE_VERSION` (env
`VIVOME_PIPELINE_VERSION`) chooses which bundle loads, and with it the label
space, conformal and abstention components (`pipeline.components_for`).
- **`v3.1`, the default,** is T1 NB2's five-encoder ensemble
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

Both response schemas are in
[`../docs/service/projection-api.md`](../docs/service/projection-api.md).

## Running it

```bash
pip install -r service/requirements.txt
python -m service.app        # from the repository root
```

## Tests

```bash
python -m unittest discover -s service/tests -t .   # from the repository root
```
