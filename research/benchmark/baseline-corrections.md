# Baseline corrections, 2026-10-03

After the Khoury 2026 scoring, the owner asked why some baselines scored so
poorly, suspecting a mistake on our side. A four-part review (shared inputs,
MaxFuse and Harmony, scANVI / Seurat / scGLUE, and scoring) found that the
scoring is right but the comparators were run in ways that handicap them.
This file fixes the corrections **before any corrected run**, then records
the results. Nothing below is tuned on any query's labels.

The original runs and tables stay as they are: `benchmark/results/baselines_ext/`,
`research/benchmark/baselines/` and, for Khoury's one scoring under its
protocol, `research/benchmark/khoury2026/`.

## What the review found

| # | Finding | Evidence |
|---|---|---|
| 1 | **Scaling mismatch.** The RNA reference is z-scored over all its cells, a whole-blood mix (37.8% neutrophil, 13.5% erythrocyte); each query over its own cells (PBMCs). Zero means a different cell on each side, and PBMCs are pulled towards neutrophil and erythrocyte. | Positive control: 1,501 held-out RNA cells in Khoury's type mix, correlation rule, 76.8% balanced accuracy with the reference's scaling, 62.2% under the recipe, neutrophil + erythrocyte calls 1.5% → 23.3%. Correlation baseline with the RNA side z-scored class-balanced: Fulcher 46.9 → 62.1 (six types), Khoury 38.7 → 49.8; reproduced independently. |
| 2 | **MaxFuse ran without its dimension-reduction settings.** Its CCA was fitted on fewer pivot pairs (about 1,050–1,340) than features (932–2,907), so every canonical correlation is 1 and the embedding is arbitrary. | On held-out RNA cells, kNN in MaxFuse's RNA embedding gives 5.5–6.3% balanced accuracy over 22 classes (chance 4.5%); random vectors through the same kNN give the same ~90% neutrophil as the real queries. |
| 3 | **scANVI's likelihood mean cannot be negative, but it was fitted to z-scores.** With a size factor set, scvi's decoder mean is `exp(library) * softplus(...)` (`scvi/module/_vae.py:283`, `scvi/nn/_base_components.py:428`), passed to `Normal`; 31% of Khoury's query entries and 72% of RNA entries are negative. scvi's warning about this was silenced. | Its query cells barely mix with the RNA cells: in the best arm, 73% of a query cell's 30 neighbours are query cells, against 7.6% under full mixing. |
| 4 | **Harmony assumes both sides share cell populations.** Half the reference is neutrophil and erythrocyte, absent from PBMCs. | On Fulcher, plain PCA with the same kNN beats every Harmony seed (42.5 vs 25.2–36.9). |
| 5 | **Seurat CCA rescales what it receives.** `FindTransferAnchors(reduction = "cca")` runs `ScaleData` on both objects (Seurat 5.5.1, lines 231–234 of its source), re-centring and re-scaling every gene; our records said it used our z-scores as given. | Read from Seurat's source; no run needed. |
| 6 | **The RNA input was misdescribed.** `rna_X.npy` holds per-gene z-scores over all 85,232 cells, not log-normalised values. | Per-gene mean 0, SD 1. Re-z-scoring it is a no-op, so no number changes. |

Checked and correct: the scoring (all 30 Khoury runs recomputed independently),
class-name mapping, row order of every prediction file, the RNA labels'
alignment with every embedding, gene matching, and v3.1's and v3's numbers.

## The corrections, fixed before running

Each tool keeps its earlier settings except where listed. Seeds, datasets,
the class mapping, the shared kNN rule (k = 30, cosine, distance weighted)
and the scoring are unchanged.

1. **Scaling, for every tool.** The RNA side is z-scored **class-balanced**:
   each gene's mean and SD are taken with every one of the 22 reference
   classes weighted equally. It uses RNA labels only, nothing about any
   query. The query side is unchanged: each gene z-scored over its observed
   values, unobserved entries 0.
   - It reaches the correlation baseline, PCA, Harmony, scGLUE and scANVI.
   - It cannot reach Seurat CCA or MaxFuse: both re-centre each gene within
     each modality internally, as they are documented to. Seurat's rerun is
     therefore also a reproduction check of its earlier predictions.
2. **MaxFuse: the settings of its own PBMC CITE-seq tutorial**
   ([citeseq_pbmc_evaluate.ipynb](https://github.com/shuxiaoc/maxfuse/blob/main/docs/citeseq_pbmc_evaluate.ipynb),
   protein against RNA on PBMCs, the closest to this benchmark), verbatim:
   `split_into_batches(max_outward_size=5000, matching_ratio=3,
   metacell_size=2)`; `construct_graphs(n_neighbors1=15, n_neighbors2=15,
   svd_components1=30, svd_components2=30, resolution1=2, resolution2=2,
   resolution_tol=0.1)`; `find_initial_pivots(wt1=0.7, wt2=0.7,
   svd_components1=25, svd_components2=20)`; `refine_pivots(wt1=0.7,
   wt2=0.7, svd_components1=30, svd_components2=30, cca_components=20,
   n_iters=3, randomized_svd=False, svd_runs=1)`;
   `filter_bad_matches(target='pivot', filter_prop=0.3)`;
   `get_embedding(active arrays)`; `propagate(svd_components1=30,
   svd_components2=30, wt1=0.7, wt2=0.7)`;
   `filter_bad_matches(target='propagated', filter_prop=0)`. The seed
   passes to the batching and the Leiden clustering.
   - Two rules: the shared kNN rule on its embedding, and **its native
     transfer**: each query cell takes the label of the RNA cell it is
     matched to (`get_matching(order=(2, 1), target='full_data')`; several
     matches vote by matching score; an unmatched cell has no answer and
     counts as wrong).
3. **scANVI.** It gets the same inputs as every other tool (the benchmark
   genes the query measures, scaled as in 1), plus one constant per dataset
   so that every value is non-negative (the constant is the negative of the
   smallest value, and is recorded). Everything else as before: n_latent
   30, 2 layers of 128, Normal likelihood, batch = modality, 200 + 100
   epochs with early stopping (patience 15), seeds 0–2. Rules: its native
   classifier and the shared kNN rule (and nearest centroid, as for the
   other embedding tools).
   - Its earlier arms (`as_provided` with unmeasured genes zero-filled,
     `cellmedian`) are not rerun; the shared-input arm was its best
     wherever both existed.
4. **Harmony** is unchanged apart from 1. A **plain PCA arm** is added: the
   same 50-component PCA of RNA and query stacked, no correction, one run.
5. **Seurat CCA** runs as documented, unchanged; its record now says that
   Seurat re-centres and re-scales every gene itself.
6. **scGLUE** is unchanged apart from 1. Its cluster balancing stays off,
   by the owner's decision of 2026-10-02 (protocol-khoury2026.md,
   amendment 7).
7. **Correlation to class mean** is unchanged apart from 1.

**Setup checks, recorded for every embedding run** (RNA labels only, never a
query label). They are reported beside the results and are not used to
change anything:

- RNA-side kNN: the shared kNN rule fitted on a random 80% of the RNA cells'
  embedding, scored on up to 10,000 of the rest (balanced accuracy over 22
  classes; chance 4.5%). An embedding that fails this has no cell-type
  signal.
- Query mixing: the median share of a query cell's 30 nearest neighbours in
  the joint embedding that are query cells, beside the share under full
  mixing.

If a corrected tool still fails its setup check, it is reported as failing,
not adjusted.

## Runs

- **Order, one at a time:** SCoPE2, PBMC240, Fulcher 2026 (development
  data), then Khoury 2026. Per dataset: correlation, PCA, Harmony (3 seeds),
  Seurat, MaxFuse (3), scGLUE (3), scANVI (3).
- **Khoury 2026 is post-hoc.** Its labels were read at the 2026-10-03
  scoring. The corrected Khoury runs and their scores are a post-hoc
  analysis, labelled so wherever they appear, beside the protocol's result,
  which stays as scored.
- **Code:** `benchmark/baselines_corrected.py` (runs),
  `benchmark/baselines_corrected_score.py` (SCoPE2, PBMC240, Fulcher tables)
  and `benchmark/khoury2026_posthoc_score.py` (Khoury). Runs go to
  `benchmark/results/baselines_corrected/`; tables to
  `research/benchmark/baselines_corrected/` and
  `research/benchmark/khoury2026_posthoc/`. v3.1's and v3's predictions are
  reused unchanged.

## Results (2026-10-04)

The corrections above were committed at `d8522cd`, before any corrected
result was scored. Tables: [baselines_corrected/](baselines_corrected/fulcher2026_summary.csv)
(development data) and [khoury2026_posthoc/](khoury2026_posthoc/family_summary.csv)
(Khoury, post-hoc).

### Runs

- **60 runs,** one at a time on the PC, 2026-10-03 23:56 to 2026-10-04 08:57.
  59 completed and none diverged.
- **scANVI seed 2 on Fulcher failed.** At epoch 28 of its scANVI stage,
  torch refused a Normal scale that was NaN or zero. The error text does
  not show which, so the runner records the run as failed, not diverged.
  Its one rerun failed identically, at the same epoch. It is reported as
  failed, and scANVI's Fulcher rows are over seeds 0 and 1.
- **Seurat's rerun is not byte-identical to its earlier runs,** as section
  1 predicts it should be in principle: Fulcher 18.9 → 19.4, SCoPE2
  restricted 53.5 → 53.3. Seurat re-standardises its inputs, so only
  float-level differences reach it, and they move a few anchors.

### Setup checks (RNA labels only)

Every completed embedding run now carries cell types on the RNA side:
held-out kNN balanced accuracy over 22 classes (chance 4.5%) is

- 61–63% for PCA and Harmony;
- 59–64% for MaxFuse (5.5–6.3% before the correction);
- 57–63% for scGLUE;
- 72–89% for scANVI;
- 74–75% for the correlation rule (held-out cells against class means).

How much query cells mix with RNA cells differs by tool and dataset. This
is the median share of a query cell's 30 nearest neighbours that are query
cells (under full mixing: 1.7%, 0.3%, 1.5% and 1.9%):

| Tool | SCoPE2 | PBMC240 | Fulcher | Khoury |
|---|---|---|---|---|
| PCA (no correction) | 100% | 30% | 100% | 100% |
| Harmony | 77–87% | 7% | 50–53% | 33–37% |
| MaxFuse | 23–27% | 0–3% | 30–37% | 10–13% |
| scGLUE | 3–10% | 23–27% | 77–80% | 10–40% |
| scANVI | 93–100% | 33–57% | 90–93% | 67–93% |

MaxFuse's matching gives every query cell an answer on every dataset.

### Development data

Balanced accuracy, mean ± SD over seeds; v3.1 as served is unchanged.

**Fulcher 2026** (six types, chance 16.7%):

| Method, rule | Before | Corrected | v3.1 best guess minus it (CI excludes 0) |
|---|---|---|---|
| **v3.1 as served, best guess** | 57.9 | 57.9 | |
| Harmony, nearest centroid | 30.4 ± 5.6 | **63.0 ± 0.5** | −4.6 to −5.6; 3 of 3 favour Harmony |
| Correlation to class mean | 46.9 | **62.1** | −4.2; favours correlation |
| Harmony, shared kNN | 32.0 ± 6.1 | **60.8 ± 0.6** | −2.3 to −3.6; 1 favours Harmony, 2 neither |
| PCA, shared kNN | | 55.5 | +2.5; neither |
| scANVI, shared kNN | 47.8 (best arm) | 51.9 ± 0.6 | +5.6 to +6.4; v3.1 |
| scANVI, its classifier | 37.7 (best arm) | 47.1 ± 4.5 | +7.7 to +14.0; v3.1 |
| PCA, nearest centroid | | 39.2 | +18.8; v3.1 |
| MaxFuse, nearest centroid / shared kNN / matching | 11.1 / 1.4 | 31.1 / 27.6 / 27.0 | +25 to +35; v3.1 |
| scGLUE, nearest centroid / shared kNN | 24.2 / 18.3 | 24.0 / 17.4 | +34 to +43; v3.1 |
| Seurat CCA | 18.9 | 19.4 | +38.5; v3.1 |

**SCoPE2 restricted** (macrophage or monocyte; chance 50; v3.1 38.7),
scored with the corrected labels (`bugs-and-fixes.md`, 8; until
2026-10-04 this paragraph used swapped labels, and every restricted figure
in it was 100 minus the true one).

- **Above chance:** only Harmony with nearest centroid, 63.0 ± 0.4.
- **Ahead of v3.1 but at or below chance** (CI excluding zero): scGLUE with
  shared kNN (50.8), MaxFuse with nearest centroid (49.2), Seurat (46.7),
  PCA with nearest centroid (45.4). MaxFuse with shared kNN (42.4) is ahead
  in 2 of 3 seeds.
- **Behind v3.1:** the correlation baseline (35.4), PCA with shared kNN
  (34.8), Harmony with shared kNN (29.7) and scANVI under every rule
  (22.3 to 33.1).
- **Unrestricted,** every method's mean stays under 7%; v3.1 scores 0.0.

Most methods place PMA-differentiated U-937 cells nearer the RNA
monocytes, so SCoPE2's class-level task no longer ranks the methods in any
useful way.

**PBMC240 lymphoid recall** (117 weakly labelled cells; v3.1 92.3): PCA
88.9, Harmony 82.1 ± 0.9, scANVI 80.1 ± 25.7 and the correlation baseline
75.2, against 38.7 at best before the correction. MaxFuse 28.8, scGLUE
25.4 and Seurat 22.2 stay low.

### Khoury 2026, post-hoc

**Post-hoc:** Khoury's labels were read at its one scoring. These are the
corrected baselines scored beside the sealed result, which stays as scored
([khoury2026/](khoury2026/per_seed_scores.csv)). v3.1's and v3's rows were
rebuilt by the sealed scorer's own code and match the sealed tables.

Balanced accuracy over five types (chance 20%), with the paired bootstrap
against v3.1 (its members' shared kNN against each shared-kNN baseline; its
best guess against every other rule):

| Method, rule | Balanced accuracy | Bootstrap pairings |
|---|---|---|
| PCA, shared kNN | **62.8** | 3 favour PCA, 1 V2, 1 neither; mean −2.8 |
| scANVI, shared kNN | **61.5 ± 2.1** | 7 favour scANVI, 6 neither, 2 V2; mean −1.5 |
| v3.1's members (V2) alone, shared kNN | 60.0 ± 3.3 | |
| **v3.1 as served, best guess** | **56.9** | |
| Harmony, shared kNN | 56.9 ± 1.7 | 8 favour V2, 7 neither; mean +3.2 |
| scANVI, its classifier | 51.6 ± 6.5 | 1 favours v3.1, 2 neither; mean +5.3 |
| Correlation to class mean | 49.8 | favours v3.1, +7.1 |
| scGLUE, shared kNN | 38.9 ± 8.7 | 15 of 15 favour V2 |
| MaxFuse, shared kNN / matching | 31.6 ± 0.3 / 30.4 ± 1.1 | all favour v3.1 |
| Seurat CCA | 29.7 | favours v3.1, +27.2 |
| v3 as served (nearest centroid / shared kNN) | 40.9 / 39.8 | scANVI ahead in 6 of 6 |

Per type, CD8T fails for every method except v3 (which calls most T cells
CD8T): v3.1's best guess 2.7%, PCA 0.9%, scANVI 14.2%, correlation 0.9%.
The fair baselines find NK better than v3.1's best guess (PCA 52.8%, scANVI
47.5%, against 29.0%). Lineage recall is high for the better methods alike:
v3.1 98.1 / 97.2, Harmony 98.7 / 96.2, scANVI 97.1 / 97.9.

### What the corrected numbers show

1. **The handicaps were real and large.** With the corrections, Harmony
   rose from 32 to 61 on Fulcher, the correlation baseline from 47 to 62,
   MaxFuse from 1 to 28, and PBMC240 lymphoid recall from at most 39 to
   82–89. Seurat (which rescales its own inputs) and scGLUE on Fulcher
   barely moved.
2. **v3.1's best guess is level with the best simple baselines, not ahead
   of them.** On Fulcher, Harmony and the correlation baseline score 61–63
   against 57.9, with CIs favouring them. On Khoury (post-hoc), PCA with
   kNN and scANVI score 62.8 and 61.5 against v3.1's 56.9 (its members
   alone, 60.0). On SCoPE2 restricted, with its labels corrected, every
   method but one is at or below chance; Harmony with nearest centroid
   (63.0) is the exception.
3. **v3.1 stays ahead of the integration tools that ran here,** MaxFuse,
   scGLUE and Seurat CCA, on every dataset, and has the best PBMC240
   lymphoid recall.
4. **v3 does not beat corrected scANVI** on Khoury (6 of 6 pairings favour
   scANVI).
5. **What v3.1 adds is not best-guess accuracy but its answers:** on Khoury
   it commits on 93.8% of cells and 96.7% of those answers hold at the level
   stated; on Fulcher 89.2% and 97.3%. No baseline here abstains or answers
   at a coarser level, so that part is not compared.

So the claim that v3.1 beats the baselines does not survive fair inputs.
