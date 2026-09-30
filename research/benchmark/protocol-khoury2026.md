# Protocol: Khoury 2026 sealed final test set

**Khoury 2026 is sealed.** It is scored exactly once, at the final v3.1
evaluation, following this file.

- **Before then.** Nothing is embedded and nothing is scored. No label is
  read per cell: `load_khoury2026_labels()` in `benchmark/datasets.py`
  refuses unless it is called with `unseal=True`. Only the aggregate type
  counts below are known.
- **Freezing.** This file is frozen at the commit that adds it. Anything that
  must change before unsealing goes in a dated amendment at the end, and it
  must be committed before unsealing. Nothing changes after unsealing.

## Why this dataset

- **Fulcher 2026 is no longer an untouched test.** It is the first held-out
  set, but it has now been scored once, and its results informed a decision:
  V2 was selected as the v3.1 candidate encoder.
- **Khoury 2026 has not informed anything.** It is the test that no decision
  in this project has been allowed to see.

## Rules

1. **Sealed until the final v3.1 evaluation.** No model, checkpoint,
   preprocessing constant, class mapping, decision rule or metric is chosen,
   tuned or checked on Khoury 2026. Label-free facts (below) may be computed.
   There is one declared exception, scANVI's headline arm (see scANVI
   below), and it can only favour the baseline.
2. **Labels are used only for scoring.** Embedding code loads the upload with
   `load_khoury2026_upload()`, which cannot return labels.
3. **Scored once.** One run of the scoring script, on the frozen candidates.
   There is no rerun after changing anything. A rerun that only checks the
   tables reproduce byte for byte is allowed.

## Data

Source: Zenodo record 22649483 (the PBMC_covariation study). The files are
kept locally in `data/incoming/Khoury2026` (gitignored). Their sha256 hashes
are registered in `benchmark/datasets.py` and checked on every load.

| File | sha256 |
|---|---|
| `Protein_x_Cell_Matrix_Column_Normalized.csv` | `514c08ca01dac2d58a2cfed97fb574a3c555c82ab6169eb68946c86bf25f1c1b` |
| `PBMC_covariation_protein_cell_metadata.csv` | `61622d71e7540791d445cd024254694082714579de90741093be14bb0ea348e6` |

- **Matrix.** Genes × cells, log2. The authors column-normalised it only,
  ComBat-corrected it, and restored the original missing values as `NA`. The
  `Normalized_Centered` and `Imputed` matrices are never used.
  - The service's parser reads it through its `Genes`-column path. There are
    no annotation columns, and the cell IDs are unchanged.
  - **Value scale:** the service detects `log` and does not transform.
    Observed values run from 0.43 to 26.40, with a median of 10.64 and
    nothing negative. The service would log-transform only if the median
    exceeded `LINEAR_SCALE_MEDIAN_THRESHOLD = 50`, so this file cannot be
    double-logged.
- **Labels.** The metadata's `cell_type` column. The authors' protein-only
  Seurat clustering produced it, with clusters named by canonical protein
  markers (their `Protein_data_integration_annotation.R`, which is not in our
  copy of the inputs). No RNA reference was used. Mapped to five types:
  "CD4 T cells" → CD4T, "CD8 T cells" → CD8T, "NK cells" → NK,
  "B cells" → B, "Monocytes" → monocyte.

### Label-free facts, recorded at sealing

- **Cells.** 1,651, every matrix column. All are single cells, QC `Pass`, and
  `included_in_analysis = Yes`. The metadata lists 2,660 cells; the other
  1,009 are not in the matrix.
- **Genes.** 3,732 rows, of which 65 are multi-gene protein groups.
- **Overlap with the 9,002-gene feature space.**
  - 3,110 genes with the service's identifiers. The service leaves
    ambiguous groups unmatched.
  - 3,137 with the first symbol of each group, NB1d's convention.
  - 618 upload genes are unmatched.
- **Observed feature-space genes per cell.** Minimum 879, median 1,316,
  maximum 1,715.
- **The 200-gene floor** (`MIN_OBSERVED_GENES`) passes all 1,651 cells.
- **Overlap with scANVI's 2,907-gene space.** 1,252 genes by exact symbol,
  1,261 by first symbol.
- **Donors.** 2: donor 1 (21TL228108) has 791 cells and donor 2 (21TL132828)
  has 860.
- **Acquisition.**
  - Five batches: n2p1 368 cells, n2p2 236, n3p1 310, n6p1 375, n6p2 362.
  - Three instruments: timsTOF Ultra 2 (1,047 cells), Ultra AIP (368),
    Ultra (236).
  - Two mTRAQ channels: d0 856, d4 795.
  - The `cytokine_carrier` flag is "Yes" for 1,105 cells.
- **Type counts** (aggregate only): monocyte 434, CD4T 407, CD8T 333, B 246,
  NK 231. There are no Unknown cells, so all 1,651 are scored.

## Caveats, stated alongside every result

1. **The labels are not independent ground truth.** They are clusters of
   these same protein measurements, named by marker proteins. A model that
   recovers this matrix's dominant structure agrees with them partly by
   construction. The labels differ from Fulcher's, which came from an RNA
   reference.
2. **The input is already batch-corrected.** The authors applied ComBat
   upstream. We add no correction of our own, as with Fulcher, but unlike
   Fulcher this input is already corrected.
3. **Different technology.** timsTOF with mTRAQ 2-plex. Fulcher is TMT
   (Orbitrap, FragPipe), PBMC240 is label-free DIA (DIA-NN), and SCoPE2 is
   different again.

## Models

- **The final v3.1 candidates.** V2 is the currently selected candidate
  encoder. The exact checkpoints (file names and sha256) and seeds are fixed
  in an amendment committed before unsealing. If a candidate has more than
  one seed, every seed is scored and summarised per family.
- **v3 as served:** `service/model/runtime/reference_model.pt`.
- **scANVI's best arm** (see scANVI below).

Each model's reference centroids and latents come from its own export, in
`reference_metadata.csv` row order. The amendment names their paths.

## Gate, before any Khoury embedding

Each v3.1 candidate must pass a reproduction gate like Fulcher's. Its
latents on PBMC240 raw (NB1d's cells and gene convention), run through
`pipeline.embed_query`, must reach a median cosine of at least 0.999
against the latents from the candidate's own export. The amendment names
that reference file. If a candidate fails, it is not scored.

## Our query path

`pipeline.embed_query`, unchanged, on the full 1,651-cell upload:

- no log transform (the detected scale is log);
- a per-cell mask;
- per-upload, per-gene z-scores;
- smoothing;
- the 200-gene floor, which excludes no cell.

We add no batch correction.

## Decision rules for our models

As for Fulcher. Both rules choose among all 22 reference classes, because
the restricted {macrophage, monocyte} label space cannot represent four of
the five types.

1. **Nearest centroid** (the product rule).
2. **Shared kNN rule:** `evaluate.knn_classifier_predict`, k = 30, cosine,
   distance-weighted, fitted on the model's reference latents.

There is no abstention.

## scANVI

- **Setup.** Training is the same as for Fulcher
  (`scanvi_run_fulcher2026.py`'s setup), seeds 0–2. It is transductive: it
  trains on all 1,651 upload cells as unlabelled query cells.
- **Three arms,** mirroring Fulcher's. The values are already log2 and are
  not transformed again:
  - `as_provided`: the matrix values, over load.py's 2,907-gene space;
  - `cellmedian`: the same, minus each cell's median over its observed
    proteins;
  - `measuredgenes`: `as_provided`, with the RNA reference and query
    restricted to the benchmark genes Khoury measures.
- **Scaling.** Each gene is z-scored over its observed values, and
  unobserved query entries are set to 0.
- **Headline arm.** The headline is the arm with the highest 3-seed mean
  shared-kNN balanced accuracy, as in Fulcher amendment 2. That choice uses
  Khoury labels, and it can only favour scANVI. Every arm is reported.

## Class mapping, fixed now

| Reference class | Type |
|---|---|
| cd4-positive, alpha-beta t cell; naive thymus-derived cd4-positive, alpha-beta t cell; regulatory t cell | CD4T |
| cd8-positive, alpha-beta t cell | CD8T |
| natural killer cell | NK |
| b cell; plasma cell | B |
| classical monocyte; intermediate monocyte; non-classical monocyte; monocyte | monocyte |
| everything else: macrophage, myeloid dendritic cell, plasmacytoid dendritic cell, mature nk t cell, basophil, common myeloid progenitor, erythrocyte, hematopoietic precursor cell, hematopoietic stem cell, neutrophil, platelet | other |

This is Fulcher's mapping, with one change: Khoury has no DC type, so both
DC classes map to "other".

## Metrics, on all 1,651 cells

- **Balanced accuracy over the five types (primary).** A prediction of
  "other" is wrong for every true type. Chance is 20%.
- **Recall per type.**
- **Lineage recall.**
  - True lineages: lymphoid = CD4T, CD8T, NK, B (1,217 cells); myeloid =
    monocyte (434 cells).
  - A prediction's lineage is the `reference_metadata.csv` lineage of the
    predicted class.
  - Lymphoid and myeloid recall are always reported together.
- **Predicted composition.** Over the five types plus "other", and over
  reference classes.
- **Confusion matrix.** 5 true × 6 predicted.
- **Summaries.** Mean, sample SD, minimum and maximum per family and rule.
- **Paired bootstrap.** `evaluate.paired_bootstrap_diff` (2,000 stratified
  resamples, seed 0) on five-type balanced accuracy:
  - each v3.1 candidate vs v3 as served;
  - each candidate vs scANVI's headline arm;
  - v3 as served vs scANVI's headline arm.

  Both rules are compared: shared kNN vs shared kNN, and the product rule vs
  scANVI's native classifier. The number of pairings whose CI excludes zero
  is reported in each direction.

No other metric is added after unsealing. A merged-T score, or any other
secondary score, has to be added by an amendment committed before
unsealing.

## Outputs, at the final evaluation only

- **Scripts** in `benchmark/`, following the Fulcher pattern.
- **Caches** in `benchmark/results/` (gitignored).
- **Committed tables** under `research/benchmark/khoury2026`.
- **Write-up** in `research/benchmark/results.md`, with the three caveats
  stated in plain sentences.
