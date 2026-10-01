# Documentation

`docs/` explains how the products work. `research/` records how they came
to be that way. Start with the repository [README](../README.md) for setup,
and read [CLAUDE.md](../CLAUDE.md) before changing anything.

## Orientation

| Document | Covers |
|---|---|
| [project-structure.md](project-structure.md) | The folder layout, where new files go, naming rules, deliberate oddities |
| [file-index.md](file-index.md) | One line for every tracked file |
| [setup-windows.md](setup-windows.md) | Setting up on a Windows GPU workstation, including the files git doesn't carry |

## The website

| Document | Covers |
|---|---|
| [web/manifest.md](web/manifest.md) | The manifest: schema, the measured/pending contract, regeneration, release protocol |
| [web/data.md](web/data.md) | The site's data files, Git LFS, what ships and what doesn't |
| [web/design.md](web/design.md) | The design system: the world, the four UI objects, colour meanings, copy rules |
| [webpage_concept.md](webpage_concept.md) | The site concept the redesign follows: intro, landing, scroll story, dashboard, tools |

## The projection service

| Document | Covers |
|---|---|
| [service/projection-api.md](service/projection-api.md) | The `POST /api/project` contract: request, response, conformal label sets, abstention |
| [service/pipeline-brief.md](service/pipeline-brief.md) | The original per-stage design brief (Stages 1–8) the pipeline code cites |
| [service/context-brief.md](service/context-brief.md) | The post-training brief: serving constants, restricted assignment, abstention, measured constraints |
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
