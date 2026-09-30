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

## Amendment 1, 2026-09-30, before unsealing: provenance confirmed from the authors' code

The authors' code is now in `data/incoming/Khoury2026` as
`PBMC_covariation-main.zip` (sha256
`99c37ff79c41e4d97109a76e707bc9ff83b3fb998a89225c7dd62b80b5191e28`), unzipped
beside it. Every claim below cites that code by file and line. The
annotation script, earlier noted as missing from our copy, is present. This
work is label-free: code was read, and no label or score was looked at.

### Labels (`Protein_data_integration_annotation.R`)

Confirmed: protein-only Seurat clustering, 5 clusters renamed by hand from
marker proteins, no RNA reference, and every cell takes its cluster's label.

- **Clustering input.** The row-centred matrix, `Normalized_Centered`
  (read at lines 150–155), with each gene's remaining NAs filled by its
  median (lines 168–173). The top 2,000 genes by variance are the features
  (lines 191–193).
- **Clustering.** `ScaleData(..., vars.to.regress = "sample")` regresses the
  donor (line 194). Then `RunPCA` (line 195), `FindNeighbors(dims = 1:4)`
  (line 198), and `FindClusters(resolution = 0.3, random.seed = 0)`
  (line 199).
- **Markers.** NA-aware Welch-t marker tests per cluster run on the
  NA-preserving centred matrix (lines 237–293), followed by a DotPlot of
  known marker genes (lines 302–319). The canonical marker list is
  CD3D/CD3E/CD247/ZAP70 (T), CD8A/GZMA (CD8 T), GNLY (NK), MS4A1/CD74/CD37
  (B), and CD14/ITGAM/FCER1G (monocyte) (lines 221–228).
- **Hand renaming.** A hard-coded mapping of clusters 0–4 to "Monocytes",
  "CD4 T cells", "CD8 T cells", "B cells" and "NK cells" (lines 326–327),
  applied by `RenameIdents` (line 333).
- **Every cell takes its cluster's label.** The per-cell table is read from
  `active.ident` (lines 352–355), and the object is saved as `SCP_PBMC.rds`
  (lines 653–654).
- **No RNA reference.** No RNA data, reference mapping, label transfer or
  anchors appear anywhere in this script. The repository does process
  scRNA-seq from the same donors (`SS3xpress_preprocessing_and_QC.R`), but
  this script doesn't use it.

**Difference from the owner's description.** The clusters, and so the labels,
came from the row-centred matrix. They did not come from
`Protein_x_Cell_Matrix_Column_Normalized.csv`, the matrix we score. Both
matrices derive from the same MS1 measurements.

### Matrix (`n6p1_preprocessing_and_QC.R`, then `Protein_data_integration_annotation.R`)

**Per batch,** citing `n6p1_preprocessing_and_QC.R`:

1. Read the DIA-NN report (line 22). Filter to Lib.Q.Value ≤ 0.01,
   Lib.PG.Q.Value ≤ 0.05, MS1 area > 0 and human proteins (line 46). Keep
   the d0/d4 single cells (line 153).
2. `diann_maxlfq` on `Ms1.Area`, grouped by gene (lines 158–163).
3. Column-only normalisation and log2: `Normalize_saad_column_only(log = "yes")`
   (line 167).
4. kNN imputation, `hknn(k = 3)` (line 217), then column normalisation
   (line 218).
5. ComBat on the mTRAQ plex (line 224), then column normalisation
   (line 225).
6. **limma `removeBatchEffect` on run order** (line 239), then column
   normalisation (line 240).
7. The per-batch missing values are restored (line 241), and the result is
   saved as `Genes_n6p1_for_abundance_analysis.csv` (lines 341–349).

**Across batches,** citing `Protein_data_integration_annotation.R`:

8. The five per-batch files are stacked (lines 61–68) and pivoted into a
   gene × cell matrix (lines 76–82).
9. Column-only normalisation (line 85).
10. kNN imputation, `hknn(k = 3)` (line 105), then column normalisation
    (line 106).
11. ComBat on the dataset batch (line 108), then column normalisation
    (line 109).
12. The original missing values are restored (line 114). The result is
    written as `Protein_x_Cell_Matrix_Column_Normalized.csv` (lines 131–132).

The same per-batch chain appears in the other four batch scripts, with
maxLFQ, column-only log2, hknn and ComBat on the plex at the corresponding
lines. They differ only in step 6:

| Batch | Run-order limma step |
|---|---|
| n2p1 | present: `n2p1_preprocessing_and_QC.R` line 504, NA restore line 506 |
| n2p2 | present: `n2p2_preprocessing_and_QC.R` line 510, NA restore line 512 |
| n6p1 | present: `n6p1_preprocessing_and_QC.R` line 239, NA restore line 241 |
| n3p1 | absent: `n3p1_preprocessing_and_QC.R` restores NAs straight after ComBat, line 222 |
| n6p2 | absent: `n6p2_preprocessing_and_QC.R` restores NAs straight after ComBat, line 220 |

**Differences from the owner's description:**

- The description omits the limma run-order correction, which applies in
  three of the five batches.
- It also omits the per-batch NA restore that comes before integration.
- It shows one column normalisation at the end. In fact every step is
  followed by a column-only renormalisation.

None of this changes what we do. We still score the `Column_Normalized`
matrix, which the service detects as log scale and does not transform.

### Effect on the caveats

Caveat 1 stands and is now sharper. The labels are clusters of the same
MS1 measurements, computed on a row-centred, median-imputed version of the
matrix we score, with the donor regressed and only PCs 1–4 used. Caveat 2
also stands and is extended. The scored matrix carries ComBat on the mTRAQ
plex in every batch, limma run-order correction in three batches, and a
cross-batch ComBat. These are all the authors' corrections; we add none.
