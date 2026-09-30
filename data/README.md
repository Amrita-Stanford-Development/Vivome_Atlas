# data/

External datasets the project works from, kept separate from the site's
own data (`web/data/`) and the model's files (`service/model/`).

- `incoming/` — local staging for notebook deliveries and datasets, all
  gitignored as large inputs:
  - `NB1b/`, `NB1d/`: T1 notebook deliveries (checkpoints, embeddings, tables);
  - `Reference_Projection_V3_ckpt/`: the five v3 reference seeds;
  - `Fulcher2026/`: the held-out Fulcher 2026 dataset (see
    `benchmark/datasets.py`).
  - `Khoury2026/`: the SEALED Khoury 2026 final test set. Don't embed or
    score it before the final v3.1 evaluation (see
    `research/benchmark/protocol-khoury2026.md`). The small tables any reported number
  cites are copied into `research/notebook-outputs/` and committed there.

Track E (held-out mass-spectrometry data; see `research/roadmap.md`) will
add a dataset registry and download scripts here.
