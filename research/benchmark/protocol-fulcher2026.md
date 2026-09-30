# Protocol: Fulcher 2026 held-out evaluation

**Frozen at the commit that adds this file, before any Fulcher 2026 score
exists.** It is not edited after results. If something has to change, a dated
amendment goes below the last section, saying what changed and why, and the
results report both versions.

## Why this dataset

SCoPE2's published matrix is centred per gene and per cell, so it cannot test
a real upload. PBMC240 was used to choose V2 over v3, so it is now a
development dataset. Fulcher 2026 is the first mass-spectrometry dataset that
no model, constant or rule in this project has been fitted, tuned or selected
on.

## Rules

1. **Held out.** Nothing is chosen on Fulcher: no model, checkpoint,
   preprocessing constant, class mapping, decision rule or metric. There is
   one declared exception, scANVI's headline input variant (see scANVI below),
   and it can only favour the baseline.
2. **Labels are used only for scoring.** Embedding code loads the upload with
   `load_fulcher2026_upload()` in `benchmark/datasets.py`, which cannot return
   labels. Labels are read by the scoring step alone, through
   `load_fulcher2026_labels()`.
3. **This file is committed before any score is computed.** `git log` shows
   that it precedes every result table.

## Data

Source: Fulcher et al. 2026, *Single-Cell Proteomics of Human Peripheral Blood
Mononuclear Cells Exceeding 600 Cells per Day*. The data come from the
authors' `RTLS-and-TMT32-scProteomics-of-PBMCs` repository, folder
`Single_PBMCs_Fig4`, plus the paper's Table S5. The files are kept locally in
`data/incoming/Fulcher2026` (gitignored). Their sha256 hashes are registered in
`benchmark/datasets.py` and checked on every load.

| File | sha256 |
|---|---|
| `Data/abundance_protein_MD.tsv` | `85bce484c75c5510d3725093fb690d157d2c85a4cc5b7b51eae6b0a0cada4467` |
| `Metadata/First_Pass_PBMCs_KEEP.csv` | `ae0a5f8305f282e3c7b8b883fa63ce12c4421ab32e2fa893cc10c290b485f59c` |
| `Fulcher2026_TableS5_cell_metadata.xlsx` | `f308176c534bc55a49d7a94b411ad7a19c87bd007b0d0ac07336a1830a4bdef4` |

- **Matrix.** A FragPipe TMT-Integrator protein table: 1,661 proteins,
  identified by the `Gene` column, with linear intensities and `NA` for
  missing values. It is parsed by the service's own upload parser (commit
  `b18f90e`), which drops the 11 annotation columns and the 143
  reference-channel columns (`ReferenceIntensity`, `RefInt_*`, `RefDInt_*`).
- **Upload.** The 1,275 cells in `First_Pass_PBMCs_KEEP.csv`, in that file's
  order. They are matched to matrix channels after removing `_rerun` from the
  channel names; all 1,275 match, with no collisions.
- **Labels.** Table S5 `Cell_Type_Second_Pass`, with the cluster suffix `_<n>`
  removed. Counts: CD4T 308, CD8T 181, NK 150, B 102, monocyte 456, DC 54,
  Unknown 24.
- **Scored cells.** 1,251: every cell except the 24 Unknown. The Unknown cells
  stay in the upload and in scANVI's query, because per-upload scaling and
  smoothing depend on the whole upload.
- **Coverage, checked without labels.** 1,654 of the 1,661 proteins map to the
  9,002-gene feature space. Every QC-passed cell has at least 518 observed
  feature-space genes (median 773), so the 200-gene floor excludes no cell.

## Caveats, stated alongside every result

1. **The labels are not independent ground truth.** They come from the
   authors' Seurat label transfer from an scRNA-seq reference, plus cluster
   refinement. A score measures agreement with that annotation.
2. **Different technology.** The data are TMT-multiplexed and processed with
   FragPipe. PBMC240 is label-free DIA processed with DIA-NN, and SCoPE2 is a
   third technology again.

## Models

| Family | Seeds | Checkpoints |
|---|---|---|
| v3 | 0–4 | `reference_seed{0..4}.pt` (Drive `/Data/Results/ReferenceProjection_v3/ckpt/`). Seed 0 is the served model, loaded from `service/model/runtime/reference_model.pt`. |
| V2 | 0–4 | `V2_batchgene_aug_seed{0..4}.pt` (Drive `/Data/Results/Tier1_v31/NB1b/ckpt/`) |
| scANVI | 0, 1, 2 | trained here, see below |

- **Reference side.** Each model's reference comes from T1 NB1d:
  `embeddings/<model>/centroids.npy` (22 × 128, `class_idx` order) and
  `reference_latent_f16.npy` (85,233 × 128, in `reference_metadata.csv` row
  order).
- **Checkpoint hashes.** The checkpoints were not on disk at freeze time. The
  embedding step records each one's sha256 in the gate table before anything
  is scored.

## Gate, before any Fulcher embedding

- **Input.** PBMC240 raw (`service/examples/pbmc240_proteins_raw.tsv`),
  restricted to the 237 cells of NB1d's `pbmc240_raw_cell_ids.csv`, in that
  order.
- **Gene identifiers.** Each DIA-NN protein group is reduced to its first gene
  symbol, which is NB1d's convention. The service instead leaves the 58
  ambiguous groups unmatched, and that difference alone lowers v3_seed0's
  agreement with NB1d from 0.99954 to 0.99774.
- **Path.** The upload goes through `pipeline.embed_query`, the service's own
  Stages 0–3.
- **Pass criterion.** V2_seed0's median cosine to NB1d's
  `embeddings/V2_seed0/pbmc240_raw_latent.npy` is at least 0.999.
- **Also reported.** v3_seed0 under the same convention, and both models under
  the service's unchanged identifiers.
- **Also checked.** NB1d's v3_seed0 `centroids.npy` equals
  `service/model/runtime/reference_centroids.npy` (max absolute difference
  below 1e-5).
- **If V2_seed0 fails,** the evaluation stops and nothing is scored.

## Our query path

`pipeline.embed_query` runs at this commit's `service/config.py` values, in
one call per model on the full 1,275-cell upload:

- log2 of the linear input;
- a per-cell mask;
- per-upload, per-gene z-scores;
- a smoothing graph built from the upload's own z-scored full matrix.

There is no batch correction. The upload spans several TMT plexes and LC
columns, and none of them is corrected for, as in the product. All ten
models use the same path.

## Decision rules for our models

Both rules choose among all 22 reference classes. The product's restricted
label space, {macrophage, monocyte}, cannot represent five of the six types
(`MODEL_CARD.md`, failure mode 1), so it is not scored.

1. **Nearest centroid.** This is the product's decision rule: the argmax of
   cosine similarity to the model's 22 centroids.
2. **Shared kNN rule.** `evaluate.knn_classifier_predict` (k = 30, cosine
   distance, distance-weighted), fitted on the model's 85,233 reference
   latents with `class_name` labels from `reference_metadata.csv`. Its
   unrestricted output is used.

There is no abstention: every cell receives a label.

## scANVI

- **Setup.** Architecture and training are exactly those of
  `benchmark/scanvi_run_pbmc240.py`:
  - scVI: 30 latent dimensions, 2 layers, 128 hidden units, normal likelihood,
    up to 200 epochs, early-stopping patience 15;
  - scANVI: up to 100 epochs, patience 15.
- **RNA side.** `load.py`'s `rna_X.npy` and `rna_meta.csv` (85,232 cells, the
  shared gene space `results/gene_cols.txt`), z-scored per gene.
- **Query.** All 1,275 upload cells, unlabelled. This is transductive: scANVI
  trains on the query cells, and our models never see them.
- **Query genes.** Fulcher `Gene` symbols, uppercased and reduced to the
  shared gene space. Genes Fulcher lacks are missing.
- **Two input variants:**
  - `log2`: the log2 of observed intensities;
  - `log2_cellmedian`: the same, minus each cell's median over its observed
    proteins in the full 1,661-protein table.

  Both variants are then z-scored per gene over observed values, and
  unobserved entries are set to 0.
- **Predictions.** Two per run: scANVI's native classifier, and the shared kNN
  rule (k = 30) on scANVI's own RNA embedding. The run saves predicted
  classes only and never reads labels.
- **Headline variant.** Both variants are reported under both rules. The
  headline is the variant with the higher 3-seed mean balanced accuracy under
  the shared kNN rule. That choice uses Fulcher labels (the one exception to
  rule 1) and can only favour scANVI.
- **Divergence.** A run that diverges (NaN embeddings) is reported as
  diverged, not rerun with a different seed.

## Class mapping, fixed before scoring

| Reference class | Coarse type |
|---|---|
| cd4-positive, alpha-beta t cell | CD4T |
| naive thymus-derived cd4-positive, alpha-beta t cell | CD4T |
| regulatory t cell | CD4T |
| cd8-positive, alpha-beta t cell | CD8T |
| natural killer cell | NK |
| b cell | B |
| plasma cell | B (Azimuth's level-1 "B" includes plasmablasts) |
| classical monocyte | monocyte |
| intermediate monocyte | monocyte |
| non-classical monocyte | monocyte |
| monocyte | monocyte |
| myeloid dendritic cell | DC |
| plasmacytoid dendritic cell | DC |
| macrophage | other (macrophages are not in blood; owner decision) |
| mature nk t cell | other |
| basophil | other |
| common myeloid progenitor | other |
| erythrocyte | other |
| hematopoietic precursor cell | other |
| hematopoietic stem cell | other |
| neutrophil | other |
| platelet | other |

## Metrics, on the 1,251 scored cells

- **Balanced accuracy over the six types (primary).** The mean of the six
  per-type recalls, computed as sklearn `balanced_accuracy_score` on coarse
  labels. A prediction of "other" is wrong for every true type. Chance level
  is 1/6.
- **Recall per type,** for all six types.
- **Lineage recall.**
  - True lineages: lymphoid = CD4T, CD8T, NK, B (741 cells); myeloid =
    monocyte, DC (510 cells).
  - A prediction's lineage is the `reference_metadata.csv` lineage of the
    predicted class, as in Track D. So a monocyte predicted as neutrophil
    counts as myeloid, and one predicted as erythrocyte counts as neither.
  - Lymphoid and myeloid recall are always reported together, never alone.
- **Predicted composition.** The percentage of the 1,251 cells in each
  predicted coarse type (the six types plus "other"), and in each reference
  class.
- **Confusion matrix.** Counts of 6 true types × 7 predicted types.
- **Summaries.** For each family (v3, V2, and scANVI per variant) and each
  rule: the mean, sample SD, minimum and maximum over seeds.

## Paired bootstrap

`evaluate.paired_bootstrap_diff` on six-type balanced accuracy, with 2,000
stratified resamples and seed 0.

- **V2 vs v3:** all 25 seed pairings, under each rule.
- **v3 vs scANVI and V2 vs scANVI:** 15 pairings each (5 seeds × 3 scANVI
  seeds, headline variant). Two comparisons:
  - shared kNN vs scANVI's shared kNN;
  - nearest centroid vs scANVI's native classifier.
- **Reported:** the point difference and 95% CI for each pairing, and the
  number of pairings whose CI excludes zero, in each direction.

## Outputs

- **Scripts** in `benchmark/`:
  - `fulcher2026_embed.py`: the gate, then the embeddings;
  - `scanvi_run_fulcher2026.py`;
  - `fulcher2026_score.py`: the only step that reads labels.
- **Caches** in `benchmark/results/` (gitignored).
- **Committed tables** under `research/benchmark/fulcher2026`.
- **Write-up** in `research/benchmark/results.md`.

The served model, the service defaults, `MODEL_CARD.md` and the manifest do
not change. `benchmark.rows` stays pending.
