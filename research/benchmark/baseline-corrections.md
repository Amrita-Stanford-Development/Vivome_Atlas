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

## Results

Pending: the queue has not run yet.
