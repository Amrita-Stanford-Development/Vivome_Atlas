# Projection service

Implements the Phase 5 backend behind `POST /api/project`, whose contract
is published at [`../docs/projection-service.md`](../docs/projection-service.md)
(unchanged by this work — see that file for the wire schema). This directory
is a separate concern from the rest of the repo: the static app at the
repository root has zero dependencies by design (`CLAUDE.md`); this backend
does real inference and has real dependencies (`requirements.txt`), kept
entirely contained here.

## Design source

Every pipeline decision below came from a specific measured failure in this
project, documented in full in [`docs/context-brief.md`](docs/context-brief.md)
and [`docs/download-checklist.md`](docs/download-checklist.md) — relocated
here verbatim from the staging area they were written in, so the original
rationale stays in the repo, not just this document's paraphrase of it. The
short version, stage by stage:

| Stage | File | Decision that looks wrong at first glance |
|---|---|---|
| 1. Query alignment | `pipeline/alignment.py` | Zero-fill the full 9,002-gene space; never restrict to well-covered genes |
| 2. Fuzzy smoothing | `pipeline/smoothing.py` | Build the neighbour graph from the query's own full feature set, not the shared space |
| 3. Reference encoder | `pipeline/encoder.py` | Module pooling + explicit mask channel; uniform random masking beat detection-mimicking masking twice |
| 4. Label assignment | `pipeline/assignment.py` | Unbalanced OT with a **relaxed** marginal (tau ~0.1) — tightening it once collapsed accuracy 72%→47% |
| 5. Conformal calibration | `pipeline/calibration.py` | Calibrate on a **random** query slice, never confidence-filtered |
| 6. Abstention | `pipeline/abstention.py` | Max cosine similarity to any single reference cell, never neighbour vote share |
| 7. Hierarchical fallback | `pipeline/fallback.py` | Six confusable pairs collapse to a shared label instead of forcing a guess |
| 8. Property transfer | `pipeline/transfer.py` | Only 4 of 8 candidate properties passed validation; ship those with an uncertainty, not all with a caveat |

Read the module docstrings for the numbers behind each of these — they are
not defaults, they are validated findings, several of them counter to what
looks like the safer or more obvious choice.

## What exists today vs. what's pending

The encoder (Stage 3) runs against a real, working artifact: a development
placeholder checkpoint (`model/dev/H_seed4.pt`) that answers "which
architecture generalises best", not the production model. Everything
downstream of it — reference embeddings, centroids, and per-cell property
values — is blocked on the full v3 training run and does not exist anywhere
in this repo yet. See `model/README.md` for the complete list.

This means: every pipeline stage is implemented and tested (`tests/`,
against synthetic reference fixtures at the real 85,233-cell scale), but the
live service cannot yet serve a real prediction — `POST /api/project`
answers `503` naming which artifact is missing, rather than fabricating a
result or crashing.

## The one path that changes when production lands

`config.ENCODER_WEIGHTS_PATH` (env override `VIVOME_ENCODER_WEIGHTS`)
defaults to the dev placeholder today. Swapping in the real
`reference_model.pt` — once it exists, has "encoder."/"classifier." prefixed
keys per the contract, and is dropped at `model/reference_model.pt` — means
pointing this one path at it. No pipeline code changes: `encoder.py`'s
loader adapts to prefixed or bare keys and infers every dimension from the
checkpoint's own tensor shapes.

Once `model/reference_model.pt`, `model/reference_embedding.npy`, and
`model/reference_centroids.npy` all exist, `ReferenceBundle.load()` stops
raising `PendingArtifactError` and the service is live. Per-cell reference
property values (Stage 8) are a separate, still-unproduced artifact — see
`model/README.md`.

## Running it

```bash
pip install -r service/requirements.txt
python3 -m service.app        # from the repository root
```

## Tests

```bash
python3 -m unittest discover -s service/tests -t .   # from the repository root
```
