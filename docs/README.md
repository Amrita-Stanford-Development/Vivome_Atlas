# Documentation

`docs/` explains how the products work. `research/` records how they came
to be that way. Start with the repository [README](../README.md) for setup,
and read [CLAUDE.md](../CLAUDE.md) before changing anything.

## Orientation

| Document | Covers |
|---|---|
| [project-structure.md](project-structure.md) | The folder layout, where new files go, naming rules, deliberate oddities |
| [file-index.md](file-index.md) | One line for every tracked file |

## The website

| Document | Covers |
|---|---|
| [web/manifest.md](web/manifest.md) | The manifest: schema, the measured/pending contract, regeneration, release protocol |
| [web/data.md](web/data.md) | The site's data files, Git LFS, what ships and what doesn't |

## The projection service

| Document | Covers |
|---|---|
| [service/projection-api.md](service/projection-api.md) | The `POST /api/project` contract: request, response, conformal label sets, abstention |
| [service/context-brief.md](service/context-brief.md) | The build brief: the eight pipeline stages and the evidence behind each |
| [service/download-checklist.md](service/download-checklist.md) | Which files the service needed from Google Drive, and where each one landed |
| [../service/README.md](../service/README.md) | Design rationale for each stage, what's real vs. pending, how to run and test |
| [../service/model/README.md](../service/model/README.md) | The model files, grouped by role |
| [../service/model/MODEL_CARD.md](../service/model/MODEL_CARD.md) | What the model claims, how it performs, known failure modes |

## The research record

| Document | Covers |
|---|---|
| [../research/README.md](../research/README.md) | Index of plans, progress, notebook outputs, and the benchmark write-up |

The scientific plan this work serves is
[research/implementation-plan.md](../research/implementation-plan.md).
The manifest's pending records, and these documents, refer to its phase
numbers (Phase 0 through Phase 6).
