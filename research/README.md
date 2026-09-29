# research/

The R&D record: what is planned, what has been done, and what was found.
Nothing here ships. The products are `web/` and `service/`, documented in
[docs/](../docs/README.md).

## Plans and progress

| File | Scope |
|---|---|
| [implementation-plan.md](implementation-plan.md) | The governing Nature Communications plan; its phases (0–6) are referenced across the repo |
| [roadmap.md](roadmap.md) | The v3.1 / v4 plan: Colab notebooks (T1, T2), code tracks (A2–F), go/no-go gates, file ownership, track prompts |
| [todo.md](todo.md) | Progress against the roadmap, current verified numbers, open decisions, changelog |
| [notebook-run-history.md](notebook-run-history.md) | Every notebook run, in order, and what each one found |
| [tier1-tier2-report.md](tier1-tier2-report.md) | The research report the roadmap's Tier 1 and Tier 2 work draws on |

Before starting a roadmap task, read `todo.md` and the relevant track in
`roadmap.md`. When you finish, tick the item in `todo.md` with its commit
hashes and add a changelog line.

## Findings

| Folder | Holds |
|---|---|
| [benchmark/](benchmark/README.md) | The fair baseline comparison write-up: methodology, harness guide, results, bugs and fixes, known limitations |
| [notebook-outputs/nb1/](notebook-outputs/nb1/) | T1 NB1 tables: simulation bench, corrected RNA→RNA numbers |
| [notebook-outputs/nb1c/](notebook-outputs/nb1c/) | T1 NB1c tables: real-data diagnostics (v3 seed variance, matrix structure, twelve models on raw PBMC240) |
| [notebook-outputs/nb1d/](notebook-outputs/nb1d/) | T1 NB1d tables (five-seed v3 vs. V2), plus the Track D benchmark outputs built on them |

Notebook deliveries arrive in `data/incoming/` (local, gitignored). Only the
small tables that reported numbers cite are copied here and committed.

## Archive

| File | Scope |
|---|---|
| [archive/2026-08-29-resource-layer-plan.md](archive/2026-08-29-resource-layer-plan.md) | The finished resource-layer build plan (manifest pipeline, projection, benchmark and versions pages), frozen as written; its paths predate the current layout |
