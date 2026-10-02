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

## Amendment 2, 2026-10-01, before unsealing: the v3.1 candidate and four more baselines

Khoury 2026 is still sealed. Nothing was embedded or scored for this
amendment, and no label was read.

### The candidate: v3.1 as served

The v3.1 candidate is the served v3.1 pipeline of release 0.3.0 (tag
`atlas-v0.3.0`, commit `eae50af`): T1 NB2's five-encoder ensemble
(`service/pipeline/ensemble.py`), loaded by `pipeline.load_bundle("v3.1")`,
with both service flags on (`set_includes_best_guess`,
`restricted_renormalise`). Its files are checked against
`service/model/v3_1/MANIFEST.json` on load:

| File | sha256 |
|---|---|
| `nb2_spec_v31.json` | `af142e91927214cf877bb2a95779236e6e1a9844a21ad248da77a1bbba442ddd` |
| `members/V2_batchgene_aug_seed0.pt` | `c08c0cf8d4ade284bb18570bfd315905c57f271a0d374732c917dd54f6101063` |
| `members/V2_batchgene_aug_seed1.pt` | `42cdea2a558068d92d23519846da39c691dfcb324dbb6f486e08d8d67044fbd2` |
| `members/V2_batchgene_aug_seed2.pt` | `a2c7424626fdb30960c1e30b4def45e0fe5e6a755197627abc5fe292f54400e7` |
| `members/V2_batchgene_aug_seed3.pt` | `6d5ddefc2155f3fd2f7942464039378f8882e51d71d84a3a889fa2ce009a7724` |
| `members/V2_batchgene_aug_seed4.pt` | `5950061279cb1f6a5e469159effa5de76a3ca7d016a30c68608097980240a1e5` |

Each member's reference latents and centroids are
`service/model/v3_1/members/V2_seed{0..4}_reference_latent_f16.npy` and
`V2_seed{0..4}_centroids.npy`, in `reference_metadata.csv` row order.

**How the protocol's rules apply to it.** The upload goes through
`pipeline.run_projection` unrestricted, on all 1,651 cells.
- **Product rule.** The served `best_guess`, mapped to the five types by the
  class mapping above. It is the ensemble's argmax over all 22 classes, and
  every Khoury cell has one, since all pass the 200-gene floor. It is one
  prediction, scored once.
- **Shared kNN rule.** `evaluate.knn_classifier_predict` on each member's
  query latents against that member's reference latents. That gives five
  member scores, summarised per family as for a multi-seed candidate.
- **Secondary, v3.1 only: the confident answer.** The served `label` at its
  `label_level`, scored exactly as `benchmark/fulcher2026_v31.py` scores
  Fulcher, with the hierarchy in `nb2_spec_v31.json`:
  - committed share, overall and per type;
  - correct at the stated level, overall and per type;
  - answers per level (class, group, lineage);
  - the composition.

  A class answer counts as correct through the class mapping above. A group
  or lineage answer counts as correct against the one the true type's
  classes share.

**Gate.** Before any Khoury embedding, each of the five members must
reproduce its own NB1d latents on PBMC240 raw, as the Fulcher gate did
(`benchmark/fulcher2026_embed.py`): NB1d's 237 cells and first-symbol gene
convention, through `pipeline.embed_query`, with a median cosine of at least
0.999 against `data/incoming/NB1d/embeddings/V2_seed{0..4}/pbmc240_raw_latent.npy`.
The served pipeline must also pass `benchmark/v31_dev_gate.py`, NB2's
development table. If either gate fails, v3.1 is not scored.

V2's single seeds (NB1b `V2_batchgene_aug` checkpoints) are no longer a
separate candidate. They are scored only as the ensemble's members, under
the shared kNN rule above.

### Four more baselines

MaxFuse, scGLUE, Harmony with kNN, and Seurat CCA label transfer join
scANVI. Their settings are the ones the Track D extension fixes on SCoPE2,
PBMC240 and Fulcher. A further dated amendment, committed before
unsealing, names the scripts and their settings. Nothing about them is
chosen on Khoury labels.

- **Gene space: measured genes only.** The RNA reference (the benchmark's
  85,232-cell reference) and the query are restricted to the 2,907-gene
  benchmark genes Khoury measures (1,252 by exact symbol). This is the
  space of scANVI's `measuredgenes` arm.
- **Scaling.** As for scANVI: each gene is z-scored over its observed
  values, and unobserved query entries are set to 0. The matrix is already
  log2 and is not transformed again.
- **Seeds.** Seeds 0–2 for every stochastic method: MaxFuse, scGLUE, and
  Harmony's initialisation. A method that is deterministic given its inputs
  runs once, and the write-up says so.
- **Decision rules.**
  - MaxFuse, scGLUE and Harmony: the shared kNN rule on their joint
    embedding.
  - Seurat CCA: its native label transfer (`FindTransferAnchors` with
    `reduction = "cca"`, then `TransferData`).
  - The baselines have no abstention.
- **One fixed configuration each.** Unlike scANVI's headline-arm exception,
  no arm is chosen on Khoury labels.
- **Same metrics** as above, on all 1,651 cells:
  - five-type balanced accuracy (primary);
  - recall per type;
  - lineage recall;
  - composition;
  - confusion;
  - summaries over seeds.
- **Paired bootstrap, added.** Each candidate is compared with each new
  baseline. Under the shared kNN rule, kNN is paired with kNN. The product
  rule is paired with Seurat CCA's native transfer. The number of pairings
  whose CI excludes zero is reported in each direction, as for scANVI.

**Seurat on Khoury is not circular.** Fulcher's labels came from a Seurat
label transfer, so Seurat transfer is biased in its favour there. Khoury's
labels came from protein-only Seurat clustering, with no RNA reference
(amendment 1). Seurat CCA transfer from RNA is a different procedure. It
shares only the toolkit, and no bias correction is applied.

## Amendment 3, 2026-10-01, before unsealing: the baseline scripts, their settings, and a fifth baseline

Khoury 2026 is still sealed. Nothing was embedded or scored for this
amendment, and no label was read. It fixes what amendment 2 left to "a
further dated amendment". The scripts named here are committed together
with this amendment, and that commit is the reference. Any change to them
before unsealing needs another amendment.

### The scripts

| Script | Role on Khoury |
|---|---|
| `benchmark/baselines_inputs.py` | What every baseline receives: `load("khoury2026")`. |
| `benchmark/datasets.py` | `load_khoury2026_benchmark_matrix()`: the column-normalised matrix as provided (log2, ComBat-corrected by its authors). Genes match the benchmark gene space by exact symbol. A symbol listed twice takes the per-cell median. |
| `benchmark/baselines_run.py` | One tool, one seed: `python -m benchmark.baselines_run TOOL khoury2026 SEED --unseal`. It writes the predictions and a JSON record of the settings and the environment. |
| `benchmark/seurat_cca_transfer.R` | Seurat's half, called by `baselines_run.py`. |

The inputs, as amendment 2 states them:

- the benchmark's 85,232-cell RNA reference and the query, restricted to the
  benchmark genes Khoury measures in at least one cell;
- each gene z-scored over its observed values, RNA and query separately;
- unobserved query entries set to 0 after scaling.

The settings are `SETTINGS` in `baselines_run.py`, quoted here:

| Tool | Settings |
|---|---|
| MaxFuse | Fusor on z-scored shared = active arrays; `split_into_batches(max_outward_size=8000, matching_ratio=3, metacell_size=2, method='random', seed=SEED)`; `construct_graphs(15, 15)`; `refine_pivots(n_iters=1, cca_components=10)`; `filter_bad_matches(pivot, 0.3)`; propagate; `get_embedding` |
| scGLUE | `fit_SCGLUE`, Normal likelihood on z-scored values, one self-loop per gene as the guidance graph, scGLUE's own epoch heuristic, `random_seed=SEED` |
| Harmony | `PCA(50, random_state=SEED)` on RNA and query stacked; `harmonypy.run_harmony` on modality, `max_iter_harmony=30`, `random_state=SEED` |
| Seurat CCA | `FindTransferAnchors(reduction='cca', dims=1:30, features=all genes)`, with the z-scored values as data and scale.data, then `TransferData(dims=1:30)`; `set.seed(SEED)` |
| Correlation | Per RNA class, the mean of its cells' z-scored profiles. Each query cell takes the class with the highest Pearson correlation over all genes (unobserved entries 0, as for every tool). |

### A fifth baseline: correlation to the class mean

A deliberately simple baseline joins the four. It has no embedding, no
training and no parameters: each cell takes the RNA class whose mean
profile it correlates with best. It shows how much the learned models add
over the simplest use of the same reference. It is deterministic, so it
runs once (seed 0).

### Seeds and decision rules on Khoury

- **Seeds.** MaxFuse, scGLUE and Harmony run seeds 0–2. Seurat CCA turned
  out deterministic given its inputs: on SCoPE2, PBMC240 and Fulcher its
  seeds 0, 1 and 2 gave identical predictions. So it runs once (seed 0),
  as amendment 2 allows. The correlation baseline runs once (seed 0).
- **Rules scored.** Khoury has no restricted regime, so only the
  `_unrestricted` columns are scored:
  - MaxFuse, scGLUE and Harmony: `knn_unrestricted` (the shared kNN rule);
  - Seurat CCA: `native_unrestricted`;
  - correlation: `corr_unrestricted`.

  The other columns the script writes (nearest centroid, restricted) are
  not reported for Khoury.
- **Metrics.** As in amendment 2, plus the correlation baseline. Its rule is
  paired with v3.1's product rule in the paired bootstrap, as Seurat
  CCA's native transfer is.
- **Scorer.** The scorer that reads Khoury's labels is written and
  committed before unsealing. It computes only the metrics this protocol
  fixes. `benchmark/baselines_score.py` scores the development datasets,
  and its metric code is the reference.

### Environment

The baselines on Khoury run on the Windows PC that took over the work on
2026-10-01 (`docs/setup-windows.md`):

- Windows 11, Python 3.11.16;
- numpy 2.4.6, scipy 1.17.1, scikit-learn 1.9.1, pandas 2.3.3;
- torch 2.11.0 with CUDA 12.8 on an RTX 4000 Ada;
- maxfuse 0.0.2, scglue 0.4.0, harmonypy 2.0.2 (built against OpenBLAS),
  scanpy 1.11.5, anndata 0.12.19;
- R 4.6.1, Seurat 5.5.1, SeuratObject 5.4.0, Matrix 1.7.5.

The Mac ran Harmony and Seurat on the development datasets with Seurat
5.5.1 and harmonypy 2.0.2 (linked to Apple Accelerate). Each new run's JSON
records its own environment.

**Reproduction check, SCoPE2 seed 0, PC against Mac:**

- **Seurat CCA.**
  - Same anchor count (7,449).
  - Restricted accuracy 71.7 against 71.8, balanced 50.5 against 50.2.
  - 95.4% of restricted and 85.4% of unrestricted predictions identical.
  - The cells that changed are near-ties: median top-two score margin 0.047,
    against 0.188 for the rest.
- **Harmony with kNN.**
  - Restricted balanced accuracy 40.9, inside the Mac's own seed range
    (35.4 to 64.0).
  - 64.4% of unrestricted predictions identical to the Mac's seed 0, more
    than the Mac's seeds agree with each other (51.1% to 53.0%).

The platform difference is smaller than the methods' own seed-to-seed
variation, so it is not corrected for.

### At unsealing

Each tool and seed runs one at a time:
`python -m benchmark.baselines_run TOOL khoury2026 SEED --unseal`. That is
3 seeds each for MaxFuse, scGLUE and Harmony, and 1 run each for Seurat CCA
and the correlation baseline. The committed scorer then runs once. Nothing
about the baselines is changed after a Khoury label has been read.

## Amendment 4, 2026-10-02, before unsealing: a baseline run that diverges

Khoury 2026 is still sealed. Nothing was embedded or scored for this
amendment, and no label was read.

**Why now.** In the Track D extension, scGLUE diverged on Fulcher, seed 0.
Its fine-tune stage produced NaN from the first epoch, and encoding then
failed (`benchmark/results/baselines_ext/logs/scglue_fulcher2026_0.log`).
This protocol had no rule for a diverged run. Fulcher's protocol does
(`protocol-fulcher2026.md`, scANVI).

**The rule, for every baseline on Khoury:**

- A run is diverged when its embedding has a non-finite value, or when
  training produces NaN.
- `baselines_run.py` records such a run with `"diverged": true` and no
  predictions. The scorer skips it.
- A diverged run is reported as diverged, with its count per tool. It is not
  rerun, with the same seed or another, and not replaced.
- The tool's summary is over the runs that completed, and says how many
  that is.

## Amendment 5, 2026-10-02, before unsealing: the final-evaluation scripts, rehearsed on Fulcher

Khoury 2026 is still sealed. No label was read and nothing was embedded or
trained. The only Khoury check was label-free, and the protocol allows it:
the scANVI matrix loads, with 1,252 measured genes, as recorded at sealing.

The scripts below are committed with this amendment, and that commit is the
reference. Each one refuses to touch Khoury without `--unseal`.

| Step | Command | Reads labels |
|---|---|---|
| 1. Gates, embeddings, v3.1 as served | `python -m benchmark.khoury2026_embed --unseal` | no |
| 2. scANVI, 3 arms × 3 seeds | `python -m benchmark.scanvi_run_khoury2026 SEED ARM --unseal` | no |
| 3. Baselines (amendment 3) | `python -m benchmark.baselines_run TOOL khoury2026 SEED --unseal` | no |
| 4. Scoring, once | `python -m benchmark.khoury2026_score --unseal` | yes |

Heavy steps run one at a time, in this order.

**What the scripts fix, where the protocol left a choice:**

- **Gates** (step 1, as amendment 2):
  - each member against its own NB1d PBMC240 latents;
  - `v31_dev_gate.run_gate`;
  - the bundle's MANIFEST sha256s and both service flags on.

  The record goes to `research/benchmark/khoury2026/gate.json`. If a gate
  fails, nothing is embedded.
- **v3 as served** is scored on the served files:
  - `service/model/runtime/reference_model.pt`;
  - nearest centroid on `reference_centroids.npy`;
  - shared kNN on `reference_embedding.npy`.

  Fulcher used NB1d's `v3_seed0` exports. The rehearsal below shows the two
  give the same per-type recalls.
- **v3.1's members** use the shared kNN rule on their own reference latents,
  `service/model/v3_1/members/V2_seed{0..4}_reference_latent_f16.npy`.
  These are byte-identical to NB1d's exports.
- **scANVI's `cellmedian` arm** subtracts each cell's median over the full
  3,732-row table, as Fulcher's did
  (`datasets.load_khoury2026_benchmark_matrix("cellmedian")`).
- **Metric code.** `khoury2026_score.score` is `fulcher2026_score.score`
  with this protocol's five types and class mapping. Lineage comes from
  `reference_metadata.csv`.
- **Paired bootstraps,** on five-type balanced accuracy:
  - v3.1 against v3 as served:
    - best guess against nearest centroid;
    - each member's shared kNN against v3's shared kNN.
  - v3.1 against scANVI's headline arm:
    - best guess against native;
    - members' kNN against each seed's kNN.
  - v3 against scANVI's headline arm: both rules.
  - v3.1 against each baseline:
    - members' kNN against MaxFuse's, scGLUE's and Harmony's kNN;
    - best guess against Seurat CCA's native transfer;
    - best guess against the correlation baseline.
- **Outputs** go to `research/benchmark/khoury2026/`:
  - `gate.json`;
  - `per_seed_scores.csv`;
  - `family_summary.csv`;
  - `predicted_composition.csv`;
  - `confusion.csv`;
  - `paired_bootstrap.csv`;
  - `v31_confident.json`;
  - `summary.json` (headline arm, diverged runs, CI counts).

**Rehearsal.** `--rehearse` runs the same code on Fulcher 2026, a
development dataset, scoring its cells of the five types. Results:

- **Gates.** All passed. Every member's median cosine is 1.0, and the dev
  gate passed.
- **Embeddings.** The latents match `fulcher2026_embed.py`'s to within
  7.6e-7. That is the Mac-to-PC float32 difference.
- **Scores.** Across 34 runs (v3.1, its members, v3, nine scANVI runs,
  MaxFuse, Harmony, Seurat, correlation), every per-type recall matches
  Fulcher's committed tables to within 0.0001 points. That is the
  4-decimal rounding in the CSVs.
- **Confident answers.** v3.1's confident-answer counts per type are
  identical to `fulcher2026/v31_development.json`.
- **Divergence.** scGLUE's diverged runs are listed and not scored.
- **scANVI script.** A smoke rehearsal (3,000 RNA cells, few epochs) ran
  all three arms.

## Amendment 6, 2026-10-02, before unsealing: fixes from a code review

Khoury 2026 is still sealed. No label was read and nothing was embedded or
trained. A review of every script the final evaluation runs found two ways
amendment 4's divergence rule could fail, and one ordering problem. The
fixes are committed with this amendment.

1. **scGLUE.** `fit_SCGLUE` encodes the data itself after pretraining, so a
   NaN there escaped the divergence handling in `baselines_run.py` and
   crashed the run with no record. The handling now wraps the whole fit.
2. **scANVI.** A NaN during training made torch raise, so
   `scanvi_run_khoury2026.py` died with no record. Training, encoding and
   prediction are now wrapped, and such a run is recorded as diverged.
3. **The scorer.** `khoury2026_score.py` read Khoury's labels before
   opening its inputs, so a missing record surfaced only after unsealing.
   It now checks every input first and exits with the list, labels unread.
   A run that crashed for any other reason can then be rerun, and a
   diverged one is recorded, all before any label is read.
4. **Every scANVI run diverging.** If that happens, there is no headline
   arm, and the scANVI comparisons are omitted instead of failing.
5. **Two smaller changes, with no effect on any number:**
   - the scorer reads `v31_pred.csv` directly;
   - it takes the class hierarchy from `nb2_spec_v31.json`, the same file
     `baselines_score.py` reads, instead of loading the whole bundle.

**Checked after the fixes:**

- The Fulcher rehearsal reproduces amendment 5's results: 34 runs, largest
  per-type recall difference 0.000049 points, and identical confident
  answers.
- With a NaN injected inside `fit_SCGLUE`, the run returns NaN embeddings
  and so a diverged record.
- With a NaN injected into scANVI's training, a record is written with
  `"diverged": true`.
- With its inputs missing, the scorer exits listing the 28 missing files,
  without calling the label loader.
