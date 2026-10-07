# Results

All numbers below: full 85,232-cell RNA reference for every method (no
subsampling anywhere; "ours" aligned down from 85,233 by dropping one
CSV-split-dropped neutrophil cell — see
[bugs-and-fixes.md](bugs-and-fixes.md#7)), RNA labels used freely, **protein
labels touched only at this final scoring step, in every arm**. 95%
bootstrap confidence intervals (2,000 stratified resamples) in brackets.
Ranked by **balanced accuracy**, not accuracy.

**"Ours" is now scored across all five seeds of two model families, not one
checkpoint (Track D, T1 NB1d):** `v3_seed0` is the shipped model —
everything in this document before this revision scored that one seed
only, labeled just "Ours." `v3_seed1`–`v3_seed4` are four more independently
trained runs of the same architecture; `V2_seed0`–`V2_seed4` are a second
candidate architecture (mini-upload gene z-scoring, same shape as v3)
evaluated as a possible replacement. Every "Ours" row below is a 5-seed
mean ± SD (min–max in parentheses), computed by
`benchmark/evaluate.py`'s real, unchanged scoring functions
against each seed's own RNA reference and SCoPE2 protein embeddings
(`data/incoming/NB1d/embeddings/`, gitignored — the small tables anything here
cites are committed at `research/notebook-outputs/nb1d/`). A single seed's number is never
reported alone again in this section: `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv`
has every individual seed's score if you need one.
**This is a real, material correction, not just more decimal places:**
the single-seed "Ours" number this document reported before was `v3_seed0`
specifically, and `v3_seed0` turns out to be the best-performing of the
five v3 seeds by a wide margin on SCoPE2 restricted (79.79% balanced vs.
a 5-seed mean of 63.32% ± 10.84 — see the table below) — the original
number was real, but not representative of the architecture, only of the
one seed that happened to ship. (Those SCoPE2 figures were scored against
swapped labels. Corrected, `v3_seed0` is the *lowest* of the five, 20.21%
against 36.68% ± 10.84; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04).)

An earlier version of this table (before the corrections above existed)
scored a from-scratch *reconstruction* of the protein embedding instead of
any real saved artifact; that reconstruction turned out to be distorted by
two real bugs (one in the protein-side file used, one — the larger effect —
in `service/pipeline/encoder.py`'s activation function; see
[bugs-and-fixes.md](bugs-and-fixes.md)) and has been removed from this
table entirely, not kept as a labeled row. Every "Ours" number in this
document, single-seed or five-seed, is scored on real saved embeddings —
either `service/model/runtime/reference_embedding.npy` /
`service/model/source/app_export/prot_embedding_scope2.npy` (the shipped
`v3_seed0`) or T1 NB1d's own per-seed exports (everything else) — never a
reconstruction, and protein labels come from
`research/notebook-outputs/nb1d/scope2_cell_ids.csv` for the 5-seed numbers (confirmed
identical, row for row, to `atlas_PROT_v3_meta.csv`'s `true_class_name` and
to `web/data/atlas_PROT_lat128.csv`'s `class_name`) — never a file with an
unverified row order (see [known-limitations.md](known-limitations.md)).

**Sanity check (run before trusting anything else here, `v3_seed0`/shipped
model specifically):** the real
protein embedding, scored by cosine-argmax against
`service/model/runtime/reference_centroids.npy` (the trained centroids, not
recomputed class means), reproduces the historical figures to 4 decimal
places: 45.3691%/31.0833% unrestricted, 86.1745%/79.7915% restricted
(targets: 45.37/31.08, 86.17/79.79), with the labels the export used, which
were swapped (`benchmark/scope2_labels.py` reproduces them the same way
before correcting them). The trained centroids and
harness-computed RNA class-mean centroids are cosine-identical (1.0000) for
all 22 classes — there is no meaningful difference between "the trained
centroids" and "class means of the real RNA embedding" in this model.

**A separate, open caveat that does *not* affect any number in this
document:** "ours" here is scored directly against
`prot_embedding_scope2.npy` (the notebook's own saved embedding), never
re-derived through `service/pipeline`. Whether a live user uploading a
similar file to the real API would get an embedding this close to the
notebook's depended on a convention gap between
`service/pipeline/pipeline.py` and the notebook — see
[known-limitations.md](known-limitations.md#the-full_query_values-convention-gap--service-vs-notebook--resolved).
On dense data like SCoPE2 the gap was small (~0.9985 median cosine); on data
with substantial missing values (typical for real single-cell proteomics)
it was severe (~0.78 median, some cells anti-correlated). It was resolved in
`2334e48`. On PBMC240 raw (63% missing) the service now reproduces the
notebooks' latents at a median cosine of 0.9995 or higher. This is about
the *live service's* fidelity, not about anything reported below.

**A methodological asymmetry that applies to every scANVI comparison in
this document:** scANVI trains on the query cells (transductive). Our
encoder is fixed and zero-shot on the query. This should, if anything,
favor scANVI, which makes scANVI's weaker showings elsewhere in this
document (e.g. the PBMC240 lineage arm) more notable, not less.

## SCoPE2 with its labels corrected (2026-10-04)

VivOME's copy of SCoPE2 had macrophage and monocyte swapped on every cell
([bugs-and-fixes.md](bugs-and-fixes.md), 8). The authors' curated object
has 1,096 macrophages and 394 monocytes, and every copy now carries those
labels (`service/tests/test_scope2_labels.py`). Every SCoPE2 table was
rescored from saved predictions. Restricted figures became exactly 100
minus the old ones; unrestricted figures changed in no simple way.

**The SCoPE2 sections below**, from "Restricted regime" to "Pool-first
kNN" and the SCoPE2 parts of "Baselines beyond scANVI", were scored
against the swapped labels. They are superseded, and kept as written as the
record. This section replaces them.

### Restricted (macrophage or monocyte; chance 50%)

The baselines are the corrected runs
([baseline-corrections.md](baseline-corrections.md)), which replace Track
D's first runs. "Ours" is NB1d's five seeds per family under each rule.
Seeded rows show mean ± SD (min–max).

| Rank | Method | Rule | Accuracy % | Balanced accuracy % |
|---|---|---|---|---|
| 1 | Harmony (3 seeds) | nearest centroid | 52.98 ± 0.95 (51.95–53.83) | 62.97 ± 0.40 (62.52–63.28) |
| 2 | scGLUE (3 seeds) | shared kNN | 73.76 ± 0.29 (73.56–74.09) | 50.76 ± 1.01 (50.00–51.91) |
| 3 | MaxFuse (3 seeds) | nearest centroid | 50.36 ± 1.20 (49.33–51.68) | 49.19 ± 1.60 (47.92–50.98) |
| 4 | Seurat CCA | native transfer | 28.93 | 46.73 |
| 5 | PCA | nearest centroid | 25.57 | 45.42 |
| 6 | MaxFuse (3 seeds) | shared kNN | 50.16 ± 1.21 (48.93–51.34) | 42.38 ± 1.61 (40.65–43.84) |
| 7 | **Ours (V2, 5 seeds)** | pool-first kNN | 23.40 ± 4.24 (16.31–26.58) | 42.37 ± 10.87 (23.85–50.09) |
| 8 | **Ours (V2, 5 seeds)** | shared kNN | 25.19 ± 4.83 (20.67–33.36) | 41.74 ± 6.40 (36.89–51.77) |
| 9 | scGLUE (3 seeds) | nearest centroid | 48.75 ± 2.98 (45.57–51.48) | 40.13 ± 4.19 (35.45–43.53) |
| 10 | **Ours (V2, 5 seeds)** | nearest centroid | 30.36 ± 7.62 (23.83–42.82) | 39.04 ± 10.03 (26.77–48.57) |
| 11 | **v3.1 as served** | best guess | 25.37 | 38.70 |
| 12 | **Ours (v3, 5 seeds)** | pool-first kNN | 21.89 ± 4.69 (16.71–25.77) | 38.36 ± 11.80 (22.50–48.65) |
| 13 | **Ours (v3, 5 seeds)** | nearest centroid | 20.62 ± 4.71 (13.83–26.24) | 36.68 ± 10.84 (20.21–49.21) |
| 14 | Correlation to class mean | its own rule | 39.33 | 35.35 |
| 15 | PCA | shared kNN | 51.14 | 34.76 |
| 16 | scANVI (3 seeds) | nearest centroid | 35.21 ± 10.03 (25.10–45.17) | 33.09 ± 9.64 (24.54–43.55) |
| 17 | Harmony (3 seeds) | shared kNN | 43.56 ± 0.84 (42.68–44.36) | 29.69 ± 0.57 (29.10–30.24) |
| 18 | **Ours (v3, 5 seeds)** | shared kNN | 24.68 ± 11.79 (15.03–44.97) | 28.50 ± 10.60 (11.60–40.96) |
| 19 | scANVI (3 seeds) | scANVI classifier | 34.12 ± 2.25 (31.68–36.11) | 27.39 ± 3.03 (23.89–29.26) |
| 20 | scANVI (3 seeds) | shared kNN | 32.13 ± 6.05 (27.58–38.99) | 22.32 ± 4.28 (18.99–27.16) |
| — | `v3_seed0` (shipped as v3) | nearest centroid | 13.83 | 20.21 |
| — | `v3_seed0` (shipped as v3) | shared kNN | 15.03 | 11.60 |
| — | Majority class ("macrophage") | trivial floor | 73.56 | 50.00 |

Sources: `research/benchmark/baselines_corrected/scope2_summary.csv`,
`research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv`.

### Unrestricted (all 22 classes)

| Rank | Method | Rule | Accuracy % | Balanced accuracy % |
|---|---|---|---|---|
| 1 | **Ours (v3, 5 seeds)** | shared kNN | 4.94 ± 5.53 (0.00–11.54) | 8.32 ± 9.93 (0.00–20.36) |
| 2 | scANVI (3 seeds) | nearest centroid | 8.86 ± 3.21 (5.91–12.28) | 6.05 ± 2.18 (4.01–8.35) |
| 3 | scANVI (3 seeds) | scANVI classifier | 8.12 ± 4.77 (4.36–13.49) | 5.55 ± 3.23 (2.97–9.17) |
| 4 | **Ours (v3, 5 seeds)** | nearest centroid | 3.13 ± 4.23 (0.00–9.87) | 5.38 ± 7.57 (0.00–17.92) |
| 5 | MaxFuse (3 seeds) | nearest centroid | 5.79 ± 0.44 (5.37–6.24) | 3.99 ± 0.30 (3.73–4.32) |
| 6 | Seurat CCA | native transfer | 2.01 | 3.73 |
| 7 | Correlation to class mean | its own rule | 4.09 | 2.78 |
| 8 | scANVI (3 seeds) | shared kNN | 3.04 ± 1.41 (1.48–4.23) | 2.12 ± 1.01 (1.00–2.96) |
| 9 | MaxFuse (3 seeds) | MaxFuse matching | 1.83 ± 0.34 (1.48–2.15) | 2.06 ± 0.76 (1.25–2.76) |
| 10 | MaxFuse (3 seeds) | shared kNN | 1.23 ± 0.14 (1.07–1.34) | 1.70 ± 0.23 (1.54–1.97) |
| 11 | **Ours (V2, 5 seeds)** | shared kNN | 0.87 ± 0.64 (0.00–1.68) | 1.57 ± 1.24 (0.00–3.17) |
| 12 | scGLUE (3 seeds) | nearest centroid | 0.69 ± 0.88 (0.00–1.68) | 0.50 ± 0.64 (0.00–1.22) |
| 13 | **Ours (V2, 5 seeds)** | nearest centroid | 0.27 ± 0.18 (0.00–0.47) | 0.35 ± 0.27 (0.00–0.76) |
| 14 | Harmony (3 seeds) | shared kNN | 0.02 ± 0.04 (0.00–0.07) | 0.04 ± 0.07 (0.00–0.13) |
| 15 | PCA, Harmony (nearest centroid), scGLUE (shared kNN), **v3.1 as served** | | 0.00 | 0.00 |
| — | `v3_seed0` (shipped as v3) | shared kNN | 2.28 | 2.20 |
| — | `v3_seed0` (shipped as v3) | nearest centroid | 0.40 | 0.68 |

### Paired bootstraps

- **v3.1's best guess against each corrected baseline**
  (`research/benchmark/baselines_corrected/paired_bootstrap.csv`):
  - restricted, behind (CI excluding zero):
    - Harmony with nearest centroid (−24 points);
    - scGLUE with shared kNN (−11 to −13);
    - MaxFuse with nearest centroid (−9 to −12), and with shared kNN in 2
      of 3 seeds;
    - Seurat (−8.0);
    - PCA with nearest centroid (−6.7);
  - restricted, ahead:
    - scANVI in 8 of 9 runs (+7.5 to +19.7; one nearest-centroid seed is
      ahead of v3.1 by 4.8);
    - Harmony with shared kNN (+8.5 to +9.6);
    - PCA with shared kNN (+3.9);
    - the correlation baseline (+3.4);
  - unrestricted: behind or level with every baseline, by up to 9 points.
- **NB1d's seeds against Track D's three scANVI seeds**
  (`research/notebook-outputs/nb1d/paired_bootstrap_ours_vs_scanvi.csv`):
  - restricted, shared kNN: 12 of 15 v3 pairings favour v3 (mean +5.7),
    and all 15 V2 pairings favour V2 (+18.9);
  - unrestricted: 12 of 15 favour v3 (+8.1);
  - `v3_seed0` is behind every scANVI seed when restricted, under both
    kNN rules.

  Both sides are below chance when restricted.

### What the corrected numbers show

1. **SCoPE2's two classes defeat almost every method.** Only Harmony with
   nearest centroid is clearly above chance (63.0). Most methods, VivOME's
   among them, place SCoPE2's PMA-differentiated U-937 macrophages nearest
   the RNA reference's blood monocytes. v3's macrophage-vs-monocyte AUROC
   is 0.072: the separation is there, the wrong way round.
2. **The class-level SCoPE2 results no longer support any ranking claim.**
   That covers the old "v3 beats scANVI", the "scANVI leads v3" that
   replaced it, and the "79.8% restricted" headline. With the labels right,
   no VivOME seed exceeds 51.8 on the two classes (chance 50), and no
   scANVI run exceeds 43.6.
3. **SCoPE2's group- and lineage-level figures are unchanged.** For example,
   v3.1's "myeloid" answers stand. So do its committed share and abstention.
4. **A U-937 cell line's differentiation states need not match primary
   blood cells' RNA classes.** SCoPE2 stays a development set for coverage
   and lineage, not for macrophage against monocyte. The reprocessed
   SCoPE2 (`benchmark/scope2_reprocess.py`, design labels) will test the
   same question without the published matrix's imputation and centring.
5. **The v4 candidate (development only) is behind v3.1 here.** On SCoPE2
   restricted / unrestricted it scores 32.6 / 0.7, against v3.1's 39.7 /
   0.0 in the same run (`research/notebook-outputs/v4_pretest/summary.json`).
   With the swapped labels it had looked 7 points ahead.

## Restricted regime (candidates = {macrophage, monocyte})

**Superseded:** scored against swapped SCoPE2 labels; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04).
Every restricted figure below is 100 minus the true one.

The only regime with real cross-modal ground truth for every candidate
class — every one of the 1,490 protein query cells is either macrophage or
monocyte.

| Rank | Method | Protocol | Accuracy % | Balanced accuracy % |
|---|---|---|---|---|
| 1 | scANVI (3-seed mean) | native scANVI classifier | 77.76 (±10.60) | 78.35 (±12.86) |
| 2 | scANVI (3-seed mean) | shared kNN rule | 71.25 (±1.54) | 77.15 (±1.77) |
| 3 | **Ours (v3, 5-seed)** | shared kNN rule | 75.32 ± 11.79 (55.03–84.97) | **71.50 ± 10.60** (59.04–88.40) |
| 4 | scANVI (3-seed mean) | native nearest-centroid | 62.37 (±15.64) | 64.18 (±27.37) |
| 5 | **Ours (v3, 5-seed)** | native nearest-centroid | 79.38 ± 4.71 (73.76–86.17) | 63.32 ± 10.84 (50.79–79.79) |
| 6 | **Ours (v3, 5-seed)** | pool-first restricted (real) | 78.11 ± 4.69 (74.23–83.29) | 61.64 ± 11.80 (51.35–77.50) |
| 7 | **v3.1 as served** (release 0.3.0) | best guess (served) | 74.63† | 61.30† |
| 8 | **Ours (V2, 5-seed)** | native nearest-centroid | 69.64 ± 7.62 (57.18–76.17) | 60.96 ± 10.03 (51.43–73.23) |
| 9 | Correlation to class mean | its own rule | 57.05† | 59.59† |
| 10 | **Ours (V2, 5-seed)** | shared kNN rule | 74.81 ± 4.83 (66.64–79.33) | 58.26 ± 6.40 (48.23–63.11) |
| 11 | scGLUE (3-seed) | native nearest-centroid | 50.54 ± 3.08 (47.85–53.89) | 58.25 ± 3.29 (54.80–61.34) |
| 12 | PCA floor | native nearest-centroid | 55.97 [53.42, 58.52]\* | 58.21 [55.42, 60.96]\* |
| 13 | PCA floor | shared kNN rule | 67.25 [65.17, 69.40]\* | 57.66 [55.04, 60.37]\* |
| 14 | **Ours (V2, 5-seed)** | pool-first restricted (real) | 76.60 ± 4.24 (73.42–83.69) | 57.63 ± 10.87 (49.91–76.15) |
| 15 | MaxFuse (3-seed) | native nearest-centroid | 54.90 ± 5.44 (48.66–58.66) | 56.66 ± 6.83 (48.84–61.49) |
| 16 | Harmony (3-seed) | native nearest-centroid | 47.02 ± 10.96 (34.83–56.04) | 54.56 ± 12.54 (42.21–67.27) |
| 17 | Seurat CCA label transfer | native transfer | 70.67‡ | 53.48‡ |
| 18 | MaxFuse (3-seed) | shared kNN rule | 70.76 ± 0.70 (70.20–71.54) | 50.51 ± 0.57 (50.08–51.15) |
| — | **Majority class ("monocyte", the protein query's own)** | trivial floor | 73.56 [71.34, 75.77]\* | 50.00 [50.00, 50.00]\* |
| 19 | Harmony (3-seed) | shared kNN rule | 43.76 ± 13.84 (28.66–55.84) | 49.98 ± 14.33 (35.41–64.05) |
| 20 | scGLUE (3-seed) | shared kNN rule | 26.51 ± 0.64 (25.91–27.18) | 49.40 ± 1.28 (47.93–50.26) |

\* 95% bootstrap CI (single run). MaxFuse, scGLUE and Harmony rows are
3-seed mean ± SD (min–max) under the gene-fair inputs of
[Baselines beyond scANVI](#baselines-beyond-scanvi-track-d-extension); they
replace the earlier single-run rows. † One run: v3.1 as served is
deterministic, and so is the correlation baseline. ‡ Seeds 0, 1 and 2 gave
identical predictions: Seurat CCA is deterministic given its inputs. Its
rows come from the corrected runs ([Runs](#runs)). scANVI rows show
3-seed mean (±spread — **range, max−min**, across seeds 0/1/2, not
standard deviation) — see [scANVI across seeds](#scanvi-across-seeds) for
the per-seed breakdown. "Ours" rows show 5-seed mean ± SD (min–max) —
see [Ours across seeds](#ours-across-five-seeds-v3-and-v2) below; no
single seed is representative, in either direction, of either family.
Rank ordering above is by mean balanced accuracy; ranking any individual
"Ours" seed against scANVI's per-seed spread is a materially different,
noisier comparison — see the paired bootstrap section.

**Reading this table:** the picture is far less one-sided than the
original single-seed version of this document reported, and this reverses
the original headline. Under the shared kNN rule, v3's 5-seed mean
balanced accuracy (71.50%) is **below** scANVI's 3-seed mean (77.15%) —
the original claim that "ours" beats
scANVI by double digits under this rule was true only for `v3_seed0`
specifically (88.40%, the best of the five v3 seeds by a wide margin), not
for the v3 architecture generally. Under native nearest-centroid, v3's
5-seed mean (63.32%) also trails scANVI's native-classifier mean (78.35%,
though that number itself has a 12.86-point seed spread) and its
native-centroid mean (64.18%, statistically indistinguishable from v3's
63.32%). V2 does no better than v3 against scANVI on SCoPE2 under any
protocol. The **only** regime and seed where "ours" clearly, robustly beats
scANVI is `v3_seed0` — the one seed that happened to ship — which is why
the paired-bootstrap section below reports the comparison per seed, not as
a single family-level verdict. The unsupervised integration methods
(MaxFuse, Harmony, scGLUE) stay near the 50.00% trivial floor over three
seeds: 54.6 to 58.2 under nearest centroid and 49.4 to 50.5 under the
shared kNN rule, with seed ranges up to 28.6 points (Harmony, shared kNN).
Seurat CCA transfer scores 53.48. v3.1 as served (61.30) and the
correlation baseline (59.59) sit just above them, below scANVI.

### Ours across five seeds (v3 and V2)

**Superseded:** scored against swapped SCoPE2 labels; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04).

| Family | Protocol | Accuracy % (mean ± SD, min–max) | Balanced accuracy % (mean ± SD, min–max) |
|---|---|---|---|
| v3 | shared kNN rule | 75.32 ± 11.79 (55.03–84.97) | 71.50 ± 10.60 (59.04–88.40) |
| v3 | native nearest-centroid | 79.38 ± 4.71 (73.76–86.17) | 63.32 ± 10.84 (50.79–79.79) |
| v3 | pool-first restricted (real) | 78.11 ± 4.69 (74.23–83.29) | 61.64 ± 11.80 (51.35–77.50) |
| V2 | shared kNN rule | 74.81 ± 4.83 (66.64–79.33) | 58.26 ± 6.40 (48.23–63.11) |
| V2 | native nearest-centroid | 69.64 ± 7.62 (57.18–76.17) | 60.96 ± 10.03 (51.43–73.23) |
| V2 | pool-first restricted (real) | 76.60 ± 4.24 (73.42–83.69) | 57.63 ± 10.87 (49.91–76.15) |

Source: `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` (per-seed),
`research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` (this table),
computed by `benchmark/evaluate.py`'s unchanged
`knn_classifier_predict`, `nearest_centroid_predict`, and
`pool_first_knn_predict` against T1 NB1d's per-seed embeddings. v3's
shared-kNN-rule SD (10.60 points) is comparable in size to the entire gap
this document previously reported between "ours" and scANVI (11.5 points)
— a single seed's number was never a safe stand-in for the architecture.

**For the record, since it materially changed once real data replaced the
reconstruction:** the earlier reconstruction-based table had scANVI's
shared-kNN-rule restricted balanced accuracy (77.26%) *ahead* of the
reconstruction's own shared-kNN-rule number (74.50%) — i.e., "ours" looked
like it was *behind* scANVI under that one specific protocol. That
reconstruction was computed through `service/pipeline` before the
`service/pipeline/encoder.py` ReLU/GELU fix (commit `056f136` — see
[bugs-and-fixes.md](bugs-and-fixes.md#0)), so every number it produced,
including this one, is invalid on its own terms, not just "distorted." On
the real embedding, `v3_seed0` leads scANVI's 3-seed mean under every
protocol tested, and every scANVI seed in all 9 paired-bootstrap checks
(shared kNN rule, three regimes). It does not lead every scANVI seed under
every rule: seed 2's native classifier (86.37%) is above `v3_seed0`'s
nearest-centroid (79.79%) and pool-first (77.50%) results. And per the
5-seed table above, all of this is `v3_seed0`'s own result, not a result of
the v3 architecture in general.

## Unrestricted regime (all 22 RNA classes as candidates)

**Superseded:** scored against swapped SCoPE2 labels; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04).

Every RNA class competes for every prediction, even though only two classes
have any real protein ground truth. Much harder for every method.

| Rank | Method | Protocol | Accuracy % | Balanced accuracy % |
|---|---|---|---|---|
| 1 | **Ours (v3, 5-seed)** | shared kNN rule | 38.36 ± 25.71 (1.88–69.26) | **29.07 ± 18.34** (1.28–49.84) |
| 2 | **Ours (v3, 5-seed)** | native nearest-centroid | 34.09 ± 25.25 (0.20–66.24) | 25.60 ± 17.35 (0.14–48.20) |
| 3 | scANVI (3-seed mean) | native scANVI classifier | 17.70 (±19.26) | 12.76 (±15.04) |
| 4 | PCA floor | shared kNN rule | 15.84 [14.09, 17.72]\* | 11.01 [9.79, 12.37]\* |
| 5 | scANVI (3-seed mean) | shared kNN rule | 16.04 (±7.38) | 10.93 (±5.02) |
| 6 | **Ours (V2, 5-seed)** | shared kNN rule | 12.17 ± 8.12 (2.89–22.48) | 8.63 ± 5.40 (1.96–15.28) |
| 7 | scANVI (3-seed mean) | native nearest-centroid | 11.72 (±5.17) | 8.24 (±4.33) |
| 8 | Harmony (3-seed) | shared kNN rule | 6.02 ± 2.56 (3.09–7.85) | 4.14 ± 1.73 (2.18–5.42) |
| 9 | Seurat CCA label transfer | native transfer | 5.50‡ | 3.74‡ |
| 10 | MaxFuse (3-seed) | native nearest-centroid | 4.36 ± 0.94 (3.69–5.44) | 3.67 ± 0.80 (3.16–4.59) |
| 11 | **Ours (V2, 5-seed)** | native nearest-centroid | 4.05 ± 5.12 (0.34–13.09) | 3.08 ± 3.40 (0.23–8.98) |
| 12 | PCA floor | native nearest-centroid | 3.69 [2.82, 4.70]\* | 2.59 [1.96, 3.31]\* |
| 13 | Correlation to class mean | its own rule | 3.56† | 2.58† |
| 14 | Harmony (3-seed) | native nearest-centroid | 3.09 ± 1.52 (1.34–4.16) | 2.10 ± 1.04 (0.91–2.83) |
| 15 | **v3.1 as served** (release 0.3.0) | best guess (served) | 1.48† | 1.08† |
| 16 | scGLUE (3-seed) | native nearest-centroid | 0.49 ± 0.38 (0.07–0.81) | 0.74 ± 0.60 (0.05–1.12) |
| 17 | MaxFuse (3-seed) | shared kNN rule | 0.98 ± 0.34 (0.67–1.34) | 0.70 ± 0.27 (0.46–0.99) |
| 18 | scGLUE (3-seed) | shared kNN rule | 0.00 ± 0.00 (0.00–0.00) | 0.00 ± 0.00 (0.00–0.00) |

\* 95% bootstrap CI (single run). MaxFuse, scGLUE and Harmony: 3-seed
mean ± SD (min–max), replacing the earlier single-run rows. † One run
(deterministic). ‡ Three identical seeds (deterministic), from the
corrected Seurat runs ([Runs](#runs)). scANVI rows show 3-seed mean (±spread,
max−min across seeds 0/1/2) — see
[scANVI across seeds](#scanvi-across-seeds). "Ours" rows show 5-seed mean
± SD (min–max) — see [Ours across seeds](#ours-across-five-seeds-v3-and-v2).

*(Majority-class floor omitted here: predicting "monocyte" scores the same
73.56%/50.00% regardless of candidate-class count, since it never varies
its prediction. It is the protein query's own majority class, so the
73.56% accuracy floor uses the query's labels; the RNA reference's
majority class is neutrophil.)*

**Reading this table:** everyone is far worse here than in the restricted
regime — full 22-way transfer from RNA to a genuinely different
measurement modality, at real SCoPE2 noise levels, is hard for every
method. Unlike the restricted regime, v3's 5-seed mean (29.07% balanced)
*does* clearly lead scANVI's 3-seed mean (12.76% at best) here, and by a
wide margin under either protocol — 12 of the 15 v3-seed × scANVI-seed
paired-bootstrap comparisons in this regime have a CI excluding zero in
v3's favor (see the paired bootstrap section). V2, however, does **not**
clearly beat scANVI here (8.63% mean vs. scANVI's 10.93–12.76%) — only 4 of
15 V2-seed × scANVI-seed pairings favor V2 significantly, 8 favor scANVI.
The unrestricted regime is the one place in this document where v3 and
scANVI are not close: v3 wins decisively, and V2 does not inherit that win.
v3.1 as served, a V2 ensemble, scores 1.08% here. Its best guess sends
SCoPE2's macrophages and monocytes to other classes, as NB1d and NB2
found for V2. All four new baselines and the correlation baseline average
below 5% as well.

**Correcting an earlier claim in this document:** a previous version of
this table, using the (now-removed) reconstruction, observed that its
shared-kNN-rule unrestricted balanced accuracy (60.39%) was much higher
than its own native-nearest-centroid number (6.98%), and concluded this
showed "classifier choice matters more than embedding quality." **That
conclusion does not hold on the real embedding and should not have been
stated as generally as it was — and the reconstruction numbers it was based
on (60.39%, 6.98%, and every other reconstruction figure this document ever
cited) were computed through `service/pipeline` before the encoder's
ReLU/GELU fix (commit `056f136`), so they were never trustworthy evidence
about classifier choice, embedding quality, or anything else in the first
place.** Under the *same* native-nearest-centroid rule, the real embedding
(`v3_seed0` specifically, the number this document reported before the
5-seed correction above) scores 31.08% — more than 4× the reconstruction's
(invalid) 6.98% on that identical rule. The embedding itself — corrected
for both the file-panel issue and the ReLU bug — was the dominant source
of the earlier gap, not the choice of decision rule. (Classifier choice
still matters at the margins — `v3_seed0`'s shared-kNN unrestricted,
55.37% acc / 38.69% bal, is higher than its own native-centroid
unrestricted, 45.37% acc / 31.08% bal — but this is a real, secondary
effect on top of a correct embedding, not the primary explanation for a
large discrepancy. The 5-seed family means above are lower than either of
`v3_seed0`'s own numbers, consistent with `v3_seed0` being the strongest
of the five seeds on SCoPE2.)

## scANVI across seeds

**Superseded:** scored against swapped SCoPE2 labels; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04).

All 3 seeds (0, 1, 2) complete, same architecture and training budget
(200 pretrain epochs + 100 fine-tune epochs, early stopping) each time.

**Gene space (checked 2026-09-30, after the Fulcher gene-space finding).**
scANVI is trained and queried on load.py's 2,907-gene space. SCoPE2 has a
value for every one of those genes in every one of its 1,490 cells: there
are no NaN values, no zero columns and no constant columns. Its published
gene-level matrix was already imputed by its authors. So nothing on SCoPE2
was zero-filled, the arm needs no gene-restricted rerun, and the numbers
below stand. Fulcher and PBMC240 differ; see their sections.

**These are a fresh re-run (Track D, T1 NB1d follow-up), not the original
numbers** — scANVI was retrained from scratch to get real per-cell
predictions to pair-bootstrap against the new 5-seed "ours" data (none were
cached from the original run). Seeds 1 and 2 reproduced their original
numbers closely; **seed 0 did not** (its native-scANVI-classifier restricted
balanced accuracy moved from 57.89% originally to 73.51% here) — scVI/scANVI
training on this hardware (Apple MPS backend) is not bit-for-bit
deterministic even with an explicit seed set, unlike a CUDA run would be.
The table below is what this document's other sections (including the
paired bootstrap) actually use; the original run's numbers are kept in git
history, not reproduced here.

| Protocol | Regime | Seed 0 bal | Seed 1 bal | Seed 2 bal | Mean bal | Spread (max−min) |
|---|---|---|---|---|---|---|
| Shared kNN rule | restricted | 78.04 | 77.16 | 76.26 | **77.15** | **1.77** |
| Shared kNN rule | unrestricted | 12.73 | 7.71 | 12.35 | 10.93 | 5.02 |
| Native scANVI classifier | restricted | 73.51 | 75.18 | 86.37 | 78.35 | **12.86** |
| Native scANVI classifier | unrestricted | 12.38 | 5.43 | 20.47 | 12.76 | 15.04 |
| Native nearest-centroid | restricted | 49.99 | 65.20 | 77.36 | 64.18 | 27.37 |
| Native nearest-centroid | unrestricted | 7.07 | 6.66 | 10.99 | 8.24 | 4.33 |

(Accuracy figures, for completeness — shared kNN rule restricted:
71.28/70.47/72.01; native scANVI classifier restricted: 74.90/73.89/84.50;
native nearest-centroid restricted: 55.84/59.80/71.48.)

**Reading this table — and answering the question this whole investigation
started with, now against the 5-seed "ours" data above:**

- **Under the shared kNN rule — the one apples-to-apples protocol applied
  identically to every method — scANVI is remarkably *stable* across seeds
  (76.26–78.04%, a spread of under 2 points), and its 3-seed mean (77.15%)
  is now *higher* than v3's 5-seed mean (71.50%) under the same rule.
  Only `v3_seed0` (88.40%) individually beats every scANVI seed; the other
  four v3 seeds (59.04–71.01%) do not. This comparison is solid precisely
  because it is stable — and what it now shows is that v3 does not reliably
  beat scANVI here, `v3_seed0` does.**
- Under scANVI's *own* native classifier, the picture is far noisier: a
  12.9-point spread across 3 seeds (73.51% to 86.37%) this run (was a
  28.5-point spread, 57.89–86.37%, in the original run — itself evidence of
  how much a single scANVI training run can move). Seed 2's native
  classifier (86.37%) exceeds every restricted "ours" number on SCoPE2
  except `v3_seed0`'s shared kNN result (88.40%). Averaged across seeds (78.35%), scANVI's
  own classifier is now *ahead* of v3's native-nearest-centroid mean
  (63.32%).
- The honest summary: **`v3_seed0` — the one seed that shipped — beats
  scANVI's 3-seed mean under every protocol tested, and every scANVI seed
  in all 9 paired-bootstrap checks. The v3 architecture generally
  does not: its 5-seed mean trails scANVI's 3-seed mean under both the
  shared kNN rule (71.50% vs. 77.15%) and native protocols (63.32% vs.
  scANVI's 64.18–78.35% depending on protocol). This reverses what this
  document said before the 5-seed correction — it is not evidence the two
  methods perform similarly in general; it is evidence that a single
  seed, in either direction, is not a safe basis for that comparison.**

Context: this document now has training-variance data for "ours" too,
not just sampling-uncertainty CIs on one trained model. Restricted-regime
shared-kNN-rule balanced accuracy spans 59.04–88.40% across v3's own 5
training seeds (SD 10.60) — a wider spread than scANVI's 3-seed spread
under the same rule (76.26–78.04%, SD 0.89). The production reference's
separate 5-seed training run on its own RNA-only validation task
(`service/model/evidence/v3_tables/reference_seeds.csv`, mean balanced accuracy
0.7143) is a different task and dataset from this benchmark's
protein-transfer scoring and not directly comparable to any number above —
but it is notable that RNA-only validation shows far less seed-to-seed
spread than this document's real cross-modal SCoPE2 scoring does, meaning
whatever makes v3 unstable here is specific to the RNA→protein transfer
step, not the RNA-side training itself.

## Paired bootstrap: ours minus scANVI

**Superseded:** scored against swapped SCoPE2 labels; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04).

The tables above compare two *independent* 95% CIs and note whether they
overlap. A **paired** bootstrap is the statistically correct way to compare
two methods scored on the identical query set: the same resampled cell
indices are applied to *both* methods in every one of 2,000 resamples, and
the balanced-accuracy difference is computed per resample, directly giving
a CI on the difference itself.

**This section changed the most of anything in this document under Track
D.** The original version ran this comparison for `v3_seed0` only — every
number in it was real, but it silently generalized a single seed's result
to "ours vs. scANVI." This version runs all **90** pairings (10 "ours"
model-seeds × 3 scANVI seeds × 3 regimes) and reports how many actually
support a claim of "ours ahead." Full table:
`research/notebook-outputs/nb1d/paired_bootstrap_ours_vs_scanvi.csv`.

### `v3_seed0` (the shipped model) — unchanged conclusion

| scANVI seed | Regime | Δ balanced accuracy (v3_seed0 − scANVI), pts | 95% CI |
|---|---|---|---|
| 0 | restricted, shared kNN rule | +10.36 | [+8.21, +12.55] |
| 1 | restricted, shared kNN rule | +11.24 | [+9.14, +13.35] |
| 2 | restricted, shared kNN rule | +12.14 | [+9.88, +14.43] |
| 0 | restricted, pool-first | +22.15 | [+18.84, +25.39] |
| 1 | restricted, pool-first | +15.51 | [+12.31, +18.68] |
| 2 | restricted, pool-first | +9.84 | [+6.50, +13.13] |
| 0 | unrestricted | +25.97 | [+24.16, +27.69] |
| 1 | unrestricted | +30.98 | [+29.27, +32.71] |
| 2 | unrestricted | +26.34 | [+24.50, +28.11] |

Every one of `v3_seed0`'s 9 pairings excludes zero, in `v3_seed0`'s favor.
This specific claim — about this specific, shipped checkpoint — is
unchanged and still correct.

### All 10 "ours" model-seeds × all 3 scANVI seeds — the claim does not generalize

| Family | Regime | CI excludes zero, ours ahead | CI excludes zero, scANVI ahead | Not significant | Mean Δ ± SD, pts |
|---|---|---|---|---|---|
| v3 | unrestricted | 12 / 15 | 3 / 15 | 0 / 15 | +18.14 ± 17.14 |
| v3 | restricted, shared kNN rule | 3 / 15 | 12 / 15 | 0 / 15 | −5.65 ± 9.84 |
| v3 | restricted, pool-first | 5 / 15 | 8 / 15 | 2 / 15 | −0.03 ± 12.10 |
| V2 | unrestricted | 4 / 15 | 8 / 15 | 3 / 15 | −2.30 ± 5.53 |
| V2 | restricted, shared kNN rule | 0 / 15 | 15 / 15 | 0 / 15 | −18.89 ± 5.97 |
| V2 | restricted, pool-first | 4 / 15 | 11 / 15 | 0 / 15 | −4.04 ± 11.33 |

**Reading this table:** of the 90 pairings, only **28 exclude zero in
"ours"'s favor** (62 either exclude zero in scANVI's favor or are not
significant). The **unrestricted regime is the one place v3 reliably beats
scANVI** (12 of 15 pairings, mean +18.14 points) — consistent with the
unrestricted-regime table above. Everywhere restricted candidates are
involved, the picture reverses: v3's shared-kNN-rule restricted mean is
**negative** (scANVI ahead by 5.65 points on average), and pool-first is a
coin flip. V2 never reliably beats scANVI under any regime tested, and is
reliably *behind* under the restricted shared-kNN rule (15 of 15 pairings
favor scANVI). **The corrected claim: "ours beats scANVI by +9 to +14
points under the shared kNN restricted rule" is true of `v3_seed0`
specifically and does not hold for the v3 architecture, or for V2, in
general.** This is the single most important correction Track D made to
this document.

(scANVI's spread figures elsewhere in this document are reported as
**range** (max−min) across seeds, not SD, because n=3 is too small for SD
to be a very meaningful summary on its own — see the scANVI-across-seeds
section above for both figures on scANVI's own numbers. "Ours" now has 5
seeds per family, where SD is a more meaningful summary; both tables above
use it directly.)

## Pool-first kNN: what the product would actually deliver

**Superseded:** scored against swapped SCoPE2 labels; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04).

Every kNN number elsewhere in this document uses **post-hoc masking**: fit
one kNN classifier on all 22 RNA classes, then restrict the *output*
probability columns to `{macrophage, monocyte}` before taking the argmax.
This is a clean, method-agnostic evaluation rule, but it is **not** what
`service/pipeline/assignment.py`'s real `method="knn"` option actually
does in production. The real code (`_assign_knn`) restricts the *candidate
pool* of RNA cells to the supported classes **before** running the
nearest-neighbour search — a structurally different algorithm, not just a
different bookkeeping step. `pool_first_knn_predict` in
`benchmark/evaluate.py` mirrors `_assign_knn` exactly (same
`chunked_topk` helper, same pool-restriction-then-vote logic), so this
table shows what the product would actually deliver if `ASSIGNMENT_METHOD`
were set to `"knn"` — distinct from `nearest_centroid`, the method
currently configured as the shipped default.

| Method | Post-hoc masking bal. acc. % | Pool-first (real) bal. acc. % | Δ |
|---|---|---|---|
| **Ours (`v3_seed0`, shipped)** | 88.40 [86.85, 89.92] | 77.50 [74.92, 80.02] | −10.9 |
| **Ours (v3, 5-seed mean)** | 71.50 ± 10.60 | 61.64 ± 11.80 | −9.9 (mean) |
| **Ours (V2, 5-seed mean)** | 58.26 ± 6.40 | 57.63 ± 10.87 | −0.6 (mean) |
| scANVI (seed 0) | 78.04 [76.02, 79.98] | 55.35 [53.29, 57.69] | −22.7 |
| scANVI (seed 1) | 77.16 [75.24, 79.14] | 61.99 [59.55, 64.45] | −15.2 |
| scANVI (seed 2) | 76.26 [73.96, 78.54] | 67.66 [65.27, 70.28] | −8.6 |
| PCA floor | 57.66 [55.04, 60.37] | 53.37 [51.23, 55.65] | −4.3 |
| Harmony | 50.49 [47.70, 53.38] | 52.86 [50.46, 55.30] | +2.4 |
| MaxFuse | 50.05 [48.49, 51.63] | 50.00 [50.00, 50.00] | −0.1 |
| scGLUE | 48.21 [46.52, 49.78] | 49.80 [48.09, 51.55] | +1.6 |

(scANVI's seed-0 numbers here are this run's re-trained model — see the
reproducibility note in the scANVI-across-seeds section; seed 0's earlier
pool-first number, 49.85%, is not reproduced this run.)

**Reading this table:** pool-first restriction costs a large amount of
balanced accuracy for the embeddings that actually carry real cell-type
signal (v3's 5-seed mean: −9.9 points; scANVI: −8.6 to −22.7 points,
itself highly seed-dependent), and costs essentially nothing for the
near-chance embeddings (MaxFuse, scGLUE — restricting the pool barely
matters when the full-pool search was already close to random). This makes
sense mechanically: if a query cell's true nearest neighbours in a *good*
embedding happen to be an easy, well-separated set that includes some
non-restricted-class cells, post-hoc masking still benefits from finding
those genuinely close neighbours first and only tallying the restricted
subset among them; pool-first forces the search into a smaller,
sometimes-worse-matching subset from the start.

**Unlike the post-hoc-masking comparison above, "ours" does not clearly
lead scANVI under pool-first either** — v3's 5-seed pool-first mean
(61.64%) sits inside scANVI's 3-seed pool-first range (55.35–67.66%), and
V2's mean (57.63%) is below two of scANVI's three seeds. Only `v3_seed0`
(77.50%) clearly leads every scANVI pool-first number. This matches the
paired-bootstrap finding above: pool-first restricted is one of the
regimes where "ours" does not reliably beat scANVI once more than one seed
is considered — worth knowing before assuming the live service's actual
kNN option (if ever selected over the current `nearest_centroid` default)
would deliver a number resembling `v3_seed0`'s specifically.

## PBMC240 lineage arm — a development dataset, not a held-out evaluation

The real PBMC240 DIA-NN report (237 cells, ~75% missing values in the
shared gene space — nothing like SCoPE2's zero missingness) is scored here
at **lineage level** (myeloid vs. lymphoid), using weak labels from
clustering, not curated ground truth. **Label this arm plainly: it is a
development dataset used to choose V2 over v3, not a held-out evaluation of
either.** 122 of the 237 cells have a confident weak label (**117
lymphoid, 5 myeloid**); the other 115 ("unassigned") are excluded from
scoring, matching how T1 NB1d itself scored this arm.

### What scANVI actually received on PBMC240

"Ours" (v3, V2) never sees PBMC240 in a preprocessing choice — the live
service's own fixed pipeline runs identically regardless of input. scANVI,
by contrast, is trained from scratch on whatever matrix it's handed, so
its input is a real methodological choice that needs stating exactly, not
assumed neutral. Two variants were tested:

| | **raw** | **processed** |
|---|---|---|
| Source | `service/examples/pbmc240_proteins_raw.tsv` (the real DIA-NN report) | `service/examples/pbmc240_zscored_all_genes.csv` (this project's own earlier A2-investigation recipe) |
| Scale | Linear (as-measured intensity units) — **not log-transformed** | log2(x+1) |
| Per-cell normalization | None | Median-normalized (subtract each cell's own median, add back the global median of medians) |
| Missing values, within-panel | Left as NaN | Imputed: left-censored `Normal(1st percentile, 0.3)` |
| Genes | Reduced to the shared 2,907-gene fair-benchmark space; PBMC240 detected 1,215 of them | This file's own ≥5% detection-rate filter kept 2,402 genes; 1,111 of those overlap the shared 2,907-gene space |
| Final step, both variants | Per-gene z-score over observed values only, then **any entry still missing after reindexing to the shared 2,907-gene space set to 0** (genes never detected, for "raw"; genes outside this file's own filtered panel, for "processed" — 1,796 columns, 61.8% of the matrix) | (same) |

**The measured-genes arm (added 2026-09-30, after the Fulcher gene-space
finding).** Both variants above leave most of the 2,907-gene space
unmeasured for every PBMC240 cell: 1,692 genes for raw and 1,796 for
processed. Those genes are set to 0 after scaling, and scANVI reads them as
measurements. The `processed_measuredgenes` arm instead restricts both the
RNA reference and the query to the 1,111 genes the processed input
measures, run with 3 seeds (`scanvi_run_pbmc240.py SEED processed
measured`). The gene set is chosen from measurement alone, with no labels
involved. It is scANVI's best arm, and it is the scANVI result reported
below.

**Neither variant is NaN-free once reindexed to the full shared gene
space** — "processed" is not "raw, but complete"; it differs in how the
genes it does have are prepared (log-transformed, per-cell normalized,
imputed within its own smaller panel) and in exactly which genes those
are, not in whether missingness exists. The result reported as scANVI's
number in the table below is **its best arm** (the measured-genes arm),
so no version of "scANVI underperforms because of a preprocessing or
gene-space disadvantage" survives uncorrected. Every arm's own numbers are
also shown. Source for both:
`benchmark/pbmc240_lineage_prep.py`; per-seed results:
`research/notebook-outputs/nb1d/scanvi_pbmc240_input_variants.csv`.

**Plain accuracy is not reported here — it is uninformative at 117 vs. 5.**
A single overall accuracy number is dominated almost entirely by lymphoid
performance (117 of 122 cells) and can hide a method that gets every
myeloid cell wrong, or hide a method that gets suspiciously many "right" by
predicting one lineage for nearly everyone. Recall per lineage, plus what
each method actually predicts across the full sample, shows both failure
modes directly; accuracy alone shows neither.

| Method | Protocol | Lymphoid recall % (n=117) | Myeloid recall % (n=5, anecdotal) | Predicted composition (all 237 cells) |
|---|---|---|---|---|
| **Ours (v3, 5-seed)** | native nearest-centroid → lineage | 52.82 ± 7.73 (43.59–63.25) | 100.0 ± 0.0 (5/5, every seed) | ~47% lymphoid, ~50% myeloid, ~3% other lineages |
| **Ours (V2, 5-seed)** | native nearest-centroid → lineage | 92.82 ± 0.76 (92.31–94.02) | 80.0 ± 0.0 (4/5, every seed) | ~78% lymphoid, ~17% myeloid, ~5% other lineages |
| scANVI, **measured genes, processed input (best arm — reported result)** | shared kNN rule → lineage | 38.75 ± 2.75 (36.75–41.88) | 100.0 (5/5, every seed) | ~33% lymphoid, **~51% myeloid**, ~15% erythroid, ~1% other |
| scANVI, **measured genes, processed input (best arm — reported result)** | native scANVI classifier → lineage | 39.60 ± 5.56 (34.19–45.30) | 100.0 (5/5, every seed) | ~34% lymphoid, **~59% myeloid**, ~7% erythroid |
| scANVI, processed input, 2,907-gene space | shared kNN rule → lineage | 17.95 (15.38–19.66) | 100.0 (5/5, every seed) | ~16% lymphoid, **~66% myeloid**, ~18% erythroid/other |
| scANVI, processed input, 2,907-gene space | native scANVI classifier → lineage | 21.37 (5.13–50.43) | 100.0 (5/5, every seed) | ~17% lymphoid, **~82% myeloid** |
| scANVI, raw input | shared kNN rule → lineage | 8.83 (5.13–11.97) | 100.0 (5/5, every seed) | ~15% lymphoid, **~74% myeloid**, ~11% erythroid/other |
| scANVI, raw input | native scANVI classifier → lineage | 6.55 (3.42–12.82) | 100.0 (5/5, every seed) | ~9% lymphoid, **~91% myeloid** |

Source: `research/notebook-outputs/nb1d/real_data_per_seed.csv` ("ours" recall and
predicted-composition columns) and
`research/notebook-outputs/nb1d/scanvi_pbmc240_input_variants.csv` (scANVI, every arm,
built by `benchmark/pbmc240_scanvi_table.py` from the cached per-cell predictions
`benchmark/results/pbmc_scanvi_{knn,native}_pred_lineage*_seed{0,1,2}.npy`.
The script replaced a hand-assembled table and reproduces it except for one
cell: the processed, shared kNN, seed 0 row had dropped one
progenitor-predicted cell from "other", so it summed to 99.58%. The cached
predictions are gitignored but not disposable; see `benchmark/.gitignore`.
They were produced by `benchmark/scanvi_run_pbmc240.py`, a fresh
integration of RNA + this arm's own real PBMC240 matrix in the shared gene
space, not the SCoPE2 scANVI run above; a different query set needs its
own joint embedding). Class→lineage mapping is
`service/model/runtime/reference_metadata.csv`'s own `lineage` column, the same one
the live service and every other lineage figure in this project use.

**Reading this table — recall and composition tell a different, more
specific story than the accuracy number this section previously led with.**
The right way to read a per-class recall is paired with its counterpart,
not against overall accuracy: **a trivial model that calls every cell
"lymphoid" scores 100% lymphoid recall and 0% myeloid recall** — a single
recall number in isolation says nothing until read alongside the other
one. Read as pairs: v3 (52.82% lymphoid, 100.0% myeloid) and V2 (92.82%
lymphoid, 80.0% myeloid) both show real, non-trivial separation between
the two lineages — neither is the trivial "call everything one class"
failure mode. scANVI's best arm (38.75–39.60% lymphoid on the measured genes, 100.0%
myeloid) looks superficially similar to "ours" on myeloid recall alone,
but its predicted composition shows it still leans toward that trivial
failure mode: 51–59% of all 237 cells are labelled "myeloid", which
catches the 5 real myeloid cells while missing most of the 117 real
lymphoid ones. Restricting to the measured genes roughly doubles its
lymphoid recall, from 17.95–21.37% on the 2,907-gene space. The raw
input's numbers (8.83%/6.55% lymphoid, 74–91% myeloid composition) are
worse still. Even at its best arm, scANVI stays below v3 (52.82%) and far
below V2 (92.82%) on lymphoid recall. **With only 5 myeloid
cells, every method's myeloid recall is anecdotal — one misclassified cell
moves it by 20 points — and is reported alongside lymphoid recall only so
a method's overall behavior (real separation vs. one-class collapse) is
visible, never to rank methods on it in isolation.** The comparison that
matters here is not "which method wins" but the one T1 NB1d actually used
PBMC240 for: V2's lymphoid recall is a large, low-variance improvement
over v3's on real data with substantial missingness — the reason V2 was
carried forward as a candidate (`research/notebook-outputs/nb1d/nb1d_summary.json`'s
`decision.carry_V2: true`) — even though V2 does not carry that advantage
onto SCoPE2 (see the tables above, where V2 is no better than v3 against
scANVI). **Report both findings together, honestly:** V2 is the right
call for real, messy, high-missingness uploads; it is not a strictly
better encoder than v3 in every respect measured in this document. (See
the transductive-vs.-zero-shot caveat near the top of this document — it
applies here too, and if anything makes scANVI's near-collapse into
predicting one dominant lineage more notable, not less.)

### v3.1 on PBMC240

`benchmark/v31_dev_gate.py` runs the served v3.1 pipeline on PBMC240 and
SCoPE2, read with NB2's own parse (`benchmark/notebook_convention.py`), under
NB2's rule as specified (the two service flags off; see "v3.1's two service
flags" below). Its record is [v31_dev_gate.json](v31_dev_gate.json).
- **Shares.** Every share in NB2's development table
  (`research/notebook-outputs/nb2/tables/dev_datasets.csv`) matches to two
  decimals: committed, class level, and each abstention reason. For
  PBMC240 that is 73.95% committed, 23.95% ambiguous and 1.68% out of
  distribution.
- **Composition.** PBMC240's matches NB2 entry for entry. SCoPE2's differs
  by one cell: 462 "T cell" answers (31.0%; NB2 printed 30.9%) and 105
  lymphoid-lineage answers (7.0%; NB2 7.1%).
- **Tolerance.** The gate allows 0.5 point; nothing comes near it.

Through the service, PBMC240 first differed from NB2 by 1.3 points of
committed cells (72.7 against 73.9). The cause was a service bug: when several
upload rows mapped to the same gene, only the last row was kept. With
duplicates collapsed by per cell median, as NB2 does, the service reproduces
NB2's committed, out of distribution and ambiguous figures exactly; two
composition entries differ by up to 0.8 point.

## Fulcher 2026 — the first held-out evaluation

**What this is.** Fulcher 2026 is TMT32-multiplexed single-cell proteomics
of human PBMCs, processed with FragPipe. Nothing in this project was fitted,
tuned or selected on it.

- **Protocol.** [protocol-fulcher2026.md](protocol-fulcher2026.md) was
  committed at `2bcb657`, before any score existed. Amendment 1 (a
  label-free centroid check) was also made before scoring. Amendment 2 was
  added after the first results, on the owner's instruction. It added a
  scANVI arm restricted to the genes Fulcher measures, made scANVI's
  headline its best arm, and added an exploratory five-type score.
- **Scored cells.** 1,251 labelled cells in six types: CD4T 308, CD8T 181,
  NK 150, B 102, monocyte 456, DC 54. The upload holds all 1,275 QC-passed
  cells; 24 Unknown cells are kept in but not scored.
- **Scoring.** Every model classifies against all 22 reference classes,
  mapped to the six types or "other" by the protocol's fixed table. Chance
  balanced accuracy is 16.7%.
- **Tables** are in [`fulcher2026`](fulcher2026/per_seed_scores.csv).
- **Held-out result, then development data.** The results in this section
  are Fulcher's one held-out scoring under the frozen protocol. Since
  2026-09-30, by owner decision, Fulcher is a development dataset like
  PBMC240. Later scores on it are development numbers, and Khoury 2026 is
  the only sealed final test.

**Two caveats, stated plainly.**

- **The labels are not independent ground truth.** They are the authors' own
  annotation: a Seurat label transfer from an scRNA-seq reference, then
  cluster refinement. A score here measures agreement with that annotation.
- **This is a different technology from PBMC240.** Fulcher 2026 is TMT
  (FragPipe). PBMC240 is label-free DIA (DIA-NN), and SCoPE2 is a third
  technology again.

**Setup.**

- **Our models.** The five v3 seeds (seed 0 is the served model) and the
  five V2 seeds all ran through the service's own query path,
  `pipeline.embed_query`, with no batch correction.
- **The gate passed before anything was embedded.** V2_seed0 reproduces
  NB1d's PBMC240 latents at a median cosine of 0.99965
  ([gate.json](fulcher2026/gate.json)).
- **scANVI** ran three arms, three seeds each, with the same training setup
  as the PBMC240 arm. It is transductive: it trains on the Fulcher cells
  themselves. Its headline is `log2_measuredgenes`, its best arm
  (amendment 2). Under the original protocol rule, the better of the first
  two arms, it would be `log2`. Both are reported.

### What scANVI was trained and queried on

The per-gene record is in
[scanvi_gene_space.csv](fulcher2026/scanvi_gene_space.csv).

- **The original two arms (`log2`, `log2_cellmedian`)** use load.py's gene
  space: the 2,907 genes the atlas RNA reference and SCoPE2 share. That
  space was fixed before Fulcher existed.
  - Fulcher measures only 932 of those genes. The other 1,975 are unmeasured
    for every query cell.
  - Within the 932, a cell observes 402 to 932 genes (median 571).
  - Each gene is z-scored over its observed values, separately for the RNA
    reference and the query, and every unobserved query entry is then set
    to 0.
  - So about two thirds of every query cell's input is a constant 0 that
    scANVI's model reads as a measurement.
- **The measured-genes arm (`log2_measuredgenes`)** restricts both the RNA
  reference and the query to the 932 measured genes, with the same scaling
  and zero-fill for within-gene missingness. The gene set is chosen from
  measurement alone; no labels are involved.
- **Our encoders see more Fulcher genes.** v3 and V2 see 1,654 Fulcher
  genes through their 9,002-gene feature space. scANVI's best arm sees 932,
  because the RNA expression the benchmark has for the reference covers
  only the 2,907 atlas genes. Neither side's gene set was chosen on Fulcher
  labels.

### Balanced accuracy over the six types

Mean ± SD (min–max), over 5 seeds for our models and 3 for scANVI.

| Model | Nearest centroid (product rule) / scANVI native | Shared kNN rule |
|---|---|---|
| **V2** | **57.3 ± 2.2** (54.8–59.2) | **55.5 ± 2.6** (51.8–58.1) |
| v3 | 42.3 ± 3.4 (39.9–47.6) | 42.0 ± 2.9 (39.5–46.8) |
| `v3_seed0` (served) | 44.1 | 41.8 |
| scANVI, `log2_measuredgenes` (**best arm, headline**) | 37.7 ± 2.1 (35.4–39.6) | 47.8 ± 0.9 (46.9–48.6) |
| scANVI, `log2` (original-protocol headline) | 19.0 ± 11.4 | 21.4 ± 2.2 |
| scANVI, `log2_cellmedian` | 17.2 ± 9.3 | 17.8 ± 8.1 |

Source: [family_summary.csv](fulcher2026/family_summary.csv) and
[per_seed_scores.csv](fulcher2026/per_seed_scores.csv).

### Paired bootstrap

Balanced accuracy difference, 2,000 stratified resamples; the source is
[paired_bootstrap.csv](fulcher2026/paired_bootstrap.csv).

| Comparison | Rules | Pairings with CI excluding 0 | Mean difference (range) |
|---|---|---|---|
| V2 − v3 | nearest centroid | **25 of 25**, all favour V2 | +15.0 (+7.2 to +19.3) |
| V2 − v3 | shared kNN | **25 of 25**, all favour V2 | +13.4 (+5.0 to +18.7) |
| V2 − scANVI best arm | nearest centroid vs native | **15 of 15**, all favour V2 | +19.7 (+15.1 to +23.7) |
| V2 − scANVI best arm | shared kNN | **15 of 15**, all favour V2 | +7.6 (+3.2 to +11.3) |
| v3 − scANVI best arm | nearest centroid vs native | 9 of 15 favour v3, 6 inconclusive | +4.7 (+0.3 to +12.2) |
| v3 − scANVI best arm | shared kNN | **12 of 15 favour scANVI**, 3 inconclusive | −5.8 (−9.1 to −0.1) |
| v3 − scANVI `log2` (original headline) | nearest centroid vs native | 15 of 15 favour v3 | +23.4 (+8.2 to +37.8) |
| v3 − scANVI `log2` (original headline) | shared kNN | 15 of 15 favour v3 | +20.7 (+15.6 to +26.8) |
| V2 − scANVI `log2` (original headline) | nearest centroid vs native | 15 of 15 favour V2 | +38.3 (+23.0 to +49.4) |
| V2 − scANVI `log2` (original headline) | shared kNN | 15 of 15 favour V2 | +34.1 (+27.9 to +38.1) |

**The first write-up of this section compared us only against scANVI's
`log2` arm, and so overstated v3's lead.** That arm is near chance because
two thirds of its input columns are zero-filled. Against scANVI's best arm:

- **V2 still wins every pairing.**
- **v3 loses under the shared kNN rule,** by 5.8 points on average.
- **v3's product rule against scANVI's native classifier** leads in 9 of 15
  pairings, and the other 6 are inconclusive.

### What the numbers show

1. **V2 beats v3 on held-out data, in every seed pairing under both rules.**
   V2 was chosen over v3 on PBMC240, which is why PBMC240 can no longer test
   that choice. Fulcher can, and it agrees: +13 to +15 points of balanced
   accuracy, with every one of the 50 CIs above zero.
2. **V2 also beats the strongest baseline arm we have.** It beats scANVI on
   the genes Fulcher measures by +7.6 (shared kNN) and +19.7 (product rule
   vs native), in 30 of 30 pairings. v3 does not beat that arm under the
   shared rule.
3. **The two models fail differently.** The patterns below are nearest
   centroid, summed over seeds, with rows as true types
   ([confusion.csv](fulcher2026/confusion.csv)).
   - **v3's lymphoid errors.** It calls 41% of CD4T cells CD8T and 43% of NK
     cells CD8T, and sends 23% of CD4T and 40% of B cells to "other".
   - **v3's lineage recall.** Lymphoid 78.3% and myeloid 98.9%: about a fifth
     of lymphoid cells land in non-lymphoid classes.
   - **V2 separates lineages almost perfectly.** Lymphoid recall is 98.5% and
     myeloid 93.1%, with B recall at 96.1%.
   - **V2's weakness is CD8T.** It calls 63% of CD8T cells CD4T.
   - **scANVI's best arm, shared kNN.** Lymphoid recall is 81.7% and myeloid
     94.0%, with CD8T recall at 29.3%.
4. **v3 overuses "macrophage".** It calls 9.6% of all cells macrophage, a
   class absent from blood. Under the protocol's mapping that counts as
   "other" (owner decision, fixed before scoring). V2 uses it for 1.2%. Even
   so, v3's monocyte recall is 84.1%.
5. **DC is essentially unrecognised by every method.** DC recall is at most
   8.9% (V2, nearest centroid), and 0% for every scANVI arm. The reference
   holds 1 myeloid DC and 29 plasmacytoid DC cells out of 85,233, so the DC
   classes barely exist to be matched. True DCs are mostly called monocyte
   (76% for v3, 45% for V2).
6. **scANVI depends on its gene space.** With the 1,975 unmeasured genes
   zero-filled, it is near chance: 21.4% at best, predicting neutrophil,
   basophil or erythrocyte (none of them PBMC types) for about half of all
   cells. Restricted to the 932 measured genes, it reaches 47.8%. Its best
   arm's native classifier (37.7%) trails its shared-kNN rule by 10 points.

### Exploratory, added after results: five types (T = CD4T + CD8T)

Added on the owner's instruction after the six-type results were known
(amendment 2). It does not replace the primary metric. Balanced accuracy
over T, NK, B, monocyte and DC; the source is
[exploratory_5type_summary.csv](fulcher2026/exploratory_5type_summary.csv).

| Model | Nearest centroid / scANVI native | Shared kNN | T recall (NC / kNN) |
|---|---|---|---|
| V2 | 65.5 ± 2.6 | 63.0 ± 3.2 | 81.7 / 83.4 |
| v3 | 46.8 ± 3.8 | 46.8 ± 3.7 | 67.7 / 67.6 |
| scANVI, `log2_measuredgenes` | 42.0 ± 1.8 | 53.9 ± 1.1 | 59.4 / 60.1 |
| scANVI, `log2` | 23.5 ± 13.4 | 24.3 ± 3.5 | 16.4 / 39.9 |
| scANVI, `log2_cellmedian` | 21.2 ± 11.6 | 21.1 ± 9.6 | 28.6 / 24.2 |

Merging CD4T and CD8T raises every model's score. It doesn't change the
ordering under either rule. Under the shared kNN rule it is V2, then
scANVI's best arm, then v3. Comparing our product rule with scANVI's native
classifier, it is V2, then v3, then scANVI.

### Product check: the Fulcher upload through the running service

`benchmark/fulcher2026_product_check.py` POSTs the upload exactly as a user
would, with default settings: the FragPipe table as written, filtered to the
1,275 QC-passed cells. It records only what comes back, never an accuracy
([product_check.json](fulcher2026/product_check.json)).

**Before the interim fix, when the default restricted labels to
macrophage/monocyte.** The service returned only macrophage (43.5%) or
monocyte (44.3%), and abstained on the rest (12.2%). By the authors'
annotation, 741 of the 1,251 labelled cells are lymphoid. The same file
also gave different abstentions on a repeat POST (15.6%), because the Stage 5
calibration subset was unseeded.

**After the interim fix.** The restriction is now opt-in, via the
`restrict_to_supported_classes` request field, and the calibration subset
is seeded from a hash of the upload. The committed check now shows the new
default. Two POSTs of the same file return identical records, and the
output is no longer restricted:

| Returned | Share of 1,275 cells |
|---|---|
| abstained: ambiguous between classes | 40.4% |
| abstained: no confident label | 4.5% |
| abstained: outside supported region | 3.5% |
| cytotoxic lymphocyte (CD8 T / NK fallback) | 20.5% |
| CD8 T | 11.5% |
| neutrophil | 6.1% |
| macrophage | 5.4% |
| B cell | 2.6% |
| NK cell | 2.3% |
| classical monocyte, monocyte | 2.1% |
| regulatory T, plasma cell, myeloid DC, mature NK T | 1.1% |

Lymphoid cells now get lymphoid labels, and four of the five confusable
pairs can be reached again. The result is still far from usable:

- **Almost half the cells abstain,** mostly because their conformal sets
  span several of the 22 classes.
- **Monocytes are almost never called monocyte.** By the authors'
  annotation, 36% of cells are monocytes. The service labels 2.1% of cells
  monocyte and sends the rest to neutrophil, macrophage or abstention.

This check ran on v3, the default pipeline at the time
(`product_check.json`, `model_version` "production"). v3.1 has been the
default since; its result on the same upload is in "v3.1 on Fulcher" below.
This check reports composition only. It is not scored, and Fulcher is
development data now.

### v3.1 on Fulcher (development data)

Fulcher is development data now, so this is not a second held-out score.
`benchmark/fulcher2026_v31.py` sends the 1,275-cell upload through the
service parser to the served v3.1 pipeline, with default settings (both
service flags on). It reads the authors' labels afterwards, for scoring
only ([v31_development.json](fulcher2026/v31_development.json)).

A committed answer is judged at the level it is stated:
- **A class** is judged through the protocol's fixed mapping, so
  "macrophage" for a monocyte is wrong.
- **A group or lineage** is judged against the one the author type's
  classes share, so "T cell" is right for CD4T and CD8T.

| Author type | Cells | Committed | Correct at the stated level | Class / group / lineage answers |
|---|---|---|---|---|
| CD4T | 308 | 88.3% | 91.2% | 24 / 181 / 67 |
| CD8T | 181 | 93.4% | 98.8% | 1 / 100 / 68 |
| NK | 150 | 92.0% | 99.3% | 0 / 1 / 137 |
| B | 102 | 85.3% | 98.9% | 82 / 4 / 1 |
| monocyte | 456 | 92.1% | 99.8% | 0 / 1 / 419 |
| DC | 54 | 51.9% | 96.4% | 1 / 0 / 27 |
| **All 1,251** | 1,251 | 89.0% | **97.3%** | 108 / 287 / 719 |

- **All 1,275 cells:** 89.2% committed, 8.5% at class level;
  10.4% abstain ambiguous, 0.39% out of distribution.
- **Composition**, with a class counted under its group: lineage:myeloid 35.0%; lineage:lymphoid 23.1%; T cell 22.4%; abstain 10.8%; B cell 8.6%; monocyte/macrophage 0.1%.
- **Best guess:** 57.9% balanced accuracy over the six
  types, mapped by the same table. Every scored cell has one. For
  comparison, single V2 seeds under nearest centroid score 57.3 ± 2.2.

**What this shows.** v3.1 commits on nine cells in ten, and its committed
answers almost always hold at the level stated. The cost is resolution:
- **Most answers are a lineage.** "Myeloid" covers nearly every monocyte,
  and "lymphoid" nearly every NK cell.
- **T cells mostly stop at "T cell".** CD4T and CD8T are rarely separated.
- **DC is committed on only about half its cells.**

The best guess, which carries no coverage guarantee, is no better than one
V2 seed.

### Decision taken

V2 is v3.1's encoder, as NB2's five-seed ensemble, and v3.1 is the
service's default pipeline. v3 stays selectable.

### Still open from this evaluation

- CD4T/CD8T separation (V2, and scANVI) and lymphoid placement (v3) on real
  protein data.
- DC is effectively unsupported by the reference.
- scANVI's native classifier trails its own kNN rule by 10 points on
  Fulcher. It is not investigated here.

## v3.1's two service flags (development data)

The review of 2026-10-01 found two behaviours that follow NB2's rule but
mislead on protein. Two service flags answer them, both on by default
(`service/pipeline/ensemble.py`, `SERVICE_FLAGS`; a later spec can set them
under `service_flags`):
- **`set_includes_best_guess`.** Every non-empty conformal set also
  contains the cell's argmax class; an empty set still abstains. Sets only
  grow, so coverage is kept, and a one-class answer is always the best guess. Under NB2's rule a class whose qhat is
  near 1 could be named alone at about 1% probability: mature nk t cell's
  bar is 0.011.
- **`restricted_renormalise`.** A restricted request rescales each cell's
  probabilities over the allowed classes before its set is built, as
  `nb2_core.estimate_label_space` does for a restricted label space.

`benchmark/v31_service_flags.py` runs each dataset through the service
parser under NB2's rule (both flags off) and as served (both on). Labels are
read after each projection
([v31_service_flags.json](v31_service_flags.json)).

| Run | Rule | Committed | Class / group / lineage % | Abstain: ambiguous / empty set / out of distribution % | Correct | One-class answers that are the best guess | Lowest one-class confidence |
|---|---|---|---|---|---|---|---|
| SCoPE2 | NB2's rule | 72.6% | 10.2 / 26.6 / 35.7 | 24.5 / 3.0 / 0.0 | 39.5% | 24 of 152 | 0.011 |
| SCoPE2 | served | 53.0% | 1.6 / 16.6 / 34.8 | 44.0 / 3.0 / 0.0 | 58.9% | 24 of 24 | 0.407 |
| SCoPE2, restricted | NB2's rule | 31.2% | 28.2 / 3.0 / 0.0 | 0.0 / 68.8 / 0.0 | 17.4% | 396 of 420 | 0.051 |
| SCoPE2, restricted | served | 100.0% | 2.1 / 97.9 / 0.0 | 0.0 / 0.0 / 0.0 | 97.9% | 32 of 32 | 0.950 |
| PBMC240 | NB2's rule | 73.9% | 2.1 / 23.1 / 48.7 | 23.9 / 0.0 / 1.7 | lymphoid 93 of 117, myeloid 3 of 5 | 5 of 5 | 0.386 |
| PBMC240 | served | 73.1% | 2.1 / 22.7 / 48.3 | 24.8 / 0.0 / 1.7 | lymphoid 92 of 117, myeloid 3 of 5 | 5 of 5 | 0.386 |
| Fulcher 2026 | NB2's rule | 89.4% | 8.5 / 22.7 / 58.2 | 10.2 / 0.0 / 0.4 | 97.2% | 108 of 109 | 0.163 |
| Fulcher 2026 | served | 89.2% | 8.5 / 22.7 / 58.0 | 10.4 / 0.0 / 0.4 | 97.3% | 108 of 108 | 0.355 |

"Correct" is judged at the stated level, against SCoPE2's labels and
Fulcher's author types. For PBMC240 it counts labelled cells whose
committed answer names their weak lineage only. PBMC240's remaining 0.4%
is its one cell refused for coverage.

**What changes:**
- **SCoPE2.**
  - Committed falls from 72.6% to 53.0%. One-class answers
    that were not the best guess become multi-class sets, mostly ones the
    hierarchy cannot resolve.
  - Correct when committed rises from 39.5% to 58.9%. Still, no
    class or group answer is right: every correct answer is "myeloid".
- **Empty sets still abstain.** The 3.0% of SCoPE2 cells with an empty set
  keep "no confident label" under both rules.
- **PBMC240 and Fulcher barely move:** under a point of committed cells,
  one PBMC240 lymphoid cell, and 0.1 point of Fulcher's correctness.
- **Restricted SCoPE2.**
  - Under NB2's rule, 68.8% of cells have an empty set.
  - Renormalised, every set is non-empty and every cell commits.
  - But 97.9% of cells answer "monocyte/macrophage". That group is exactly
    the two allowed classes, so the answer adds nothing to the restriction
    itself.
  - None of the 32 one-class answers is right; every group answer is.
    Under NB2's rule, 36 of its 420 class answers are right.
  - The best guess (38.7% balanced accuracy, below the two classes' 50%
    chance) is the same under both rules.
  - These use the corrected labels ([bugs-and-fixes.md](bugs-and-fixes.md), 8).
  - Restricted mode was never evaluated in NB2 and is not recommended
    under v3.1 (`docs/service/projection-api.md`).

**Open:** neither flag has been evaluated on RNA. The next notebook should
measure both on NB1's evaluation suite (coverage, correct when committed,
answer levels) before they are trusted beyond these development datasets
(`research/todo.md`, Track F).

## v3.1 on out-of-reference cells: CD34+ progenitors (development data)

**The test.**
- **Cells:** 2,506 healthy human bone-marrow CD34+ stem and progenitor
  cells (Furtwängler et al. 2025, *Science*; Zenodo 15554000, CC BY 4.0),
  registered in `benchmark/datasets.py`.
- **Why they are out of reference:** the 85,233-cell reference holds only
  198 such cells (64 HSC, 131 hematopoietic precursor, 3 common myeloid
  progenitor).
- **Input:** the authors' log2 values, with missing values kept missing
  (68%). 2,734 of the 9,002 feature genes match, and every cell passes the
  200-gene floor.
- **Run:** `benchmark/furtwangler2025_v31.py` projects them through v3.1 as
  served ([furtwangler2025/v31_ood_check.json](furtwangler2025/v31_ood_check.json)).
- **What honest behaviour looks like:** mostly abstention, ideally as
  "outside supported region".

| Answer | Cells | Share |
|---|---|---|
| Abstain: ambiguous between classes | 1,454 | 58.0% |
| Group: T cell | 392 | 15.6% |
| Lineage: lymphoid | 341 | 13.6% |
| Lineage: myeloid | 208 | 8.3% |
| Group: monocyte/macrophage | 37 | 1.5% |
| **Abstain: outside supported region** | **32** | **1.3%** |
| Other answers | 42 | 1.7% |

- **The out-of-distribution filter barely fires.** It flags 32 of 2,506
  cells. Of the 85 cells the authors' FACS gates call HSCs, it flags none,
  and 22 get a committed answer.
- **The committed answers are wrong in kind.** Stem and progenitor cells
  are called "T cell" or "lymphoid". Their best guesses are mostly T cell
  classes and plasma cells.
- **This matches NB2's warning** that the filter passes 99% of scrambled
  cells. It is the clearest case yet for T1 NB3b's better
  out-of-distribution score. These cells are now that notebook's
  out-of-reference test set, which makes them development data.

## Baselines beyond scANVI (Track D extension)

Four established tools, plus a deliberately simple baseline, on SCoPE2,
PBMC240 and Fulcher 2026. They are compared with **v3.1 as served**
(release 0.3.0, both service flags on), scored on its best guess, on the
same cells as the tables above. The settings are the ones fixed for the
sealed Khoury test in protocol amendments 3 (`65bfc10`), 4 and 7.

| Tool | What it is | Rule scored |
|---|---|---|
| MaxFuse | matches cells across modalities that share few features | shared kNN, nearest centroid |
| scGLUE | graph-linked deep integration (one self-loop per gene) | shared kNN, nearest centroid |
| Harmony + kNN | batch correction of RNA and query PCs | shared kNN, nearest centroid |
| Seurat CCA | `FindTransferAnchors` (CCA) then `TransferData` | its native transfer |
| Correlation to class mean | each cell takes the RNA class whose mean profile it correlates with best | its own argmax |

Scripts: `benchmark/baselines_inputs.py` (inputs),
`benchmark/baselines_run.py` and `benchmark/seurat_cca_transfer.R` (runs),
`benchmark/baselines_v31.py` (v3.1 through the service's own parser),
`benchmark/baselines_score.py` (every table in
[baselines/](baselines/)). Predictions are cached in
`benchmark/results/baselines_ext/`.

### What every tool received

The same inputs for every tool, the ones scANVI's measured-genes arm got
([baselines/inputs.csv](baselines/inputs.csv)):

- the benchmark's 85,232-cell RNA reference and the query, restricted to the
  benchmark genes the query measures;
- each gene z-scored over its observed values, RNA and query separately;
- unobserved query entries set to 0 after scaling.

| Dataset | Query cells | Genes measured | Query entries unobserved |
|---|---|---|---|
| SCoPE2 | 1,490 | 2,907 | 0.0% |
| PBMC240 (processed file) | 237 | 1,111 | 0.0% |
| Fulcher 2026 (log2) | 1,275 | 932 | 39.3% |

### Runs

- **Seeds.** MaxFuse, scGLUE and Harmony ran seeds 0–2. Seurat CCA ran
  seeds 0–2 and gave identical predictions on all three datasets: it is
  deterministic given its inputs. The correlation baseline and v3.1 ran
  once.
- **Where.**
  - On the Mac (2026-10-01): Harmony and v3.1.
  - On the Windows PC: MaxFuse and the correlation baseline (2026-10-01/02),
    Seurat CCA (2026-10-02) and scGLUE (on the GPU, 2026-10-03).
  - The PC reproduces the Mac's Harmony within its own seed variation
    (protocol amendment 3).
- **Seurat CCA, corrected.** Until 2026-10-02, `baselines_run.py` wrote
  Seurat's input matrices in the wrong byte order, so each "cell" Seurat
  saw was one gene's values across consecutive cells. Every Seurat result
  from before the fix is void. The rows here are from nine reruns with the
  fix (protocol amendment 7).
- **scGLUE, balancing off.** scGLUE runs with its cluster balancing off
  (`skip_balance=True`) on every dataset, by the owner's decision of
  2026-10-02 (protocol amendment 7). With it on, every Fulcher run failed:
  no RNA and query cluster pair reached the balancing's 0.5 similarity
  cutoff, every weight was 0/0, and training went NaN at the first step.
  All nine runs completed, and none diverged (logs in
  `benchmark/results/baselines_ext/logs/`).

### SCoPE2

**Superseded:** scored against swapped SCoPE2 labels; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04).

The rows are in the [restricted](#restricted-regime-candidates--macrophage-monocyte)
and [unrestricted](#unrestricted-regime-all-22-rna-classes-as-candidates)
tables above.

- **Restricted.** v3.1's best guess, at 61.30% balanced, is ahead of every
  new baseline's mean and below scANVI's three rules. The correlation
  baseline is close behind at 59.59%.
- **Unrestricted.** Every method in this extension averages under 5%
  balanced, v3.1 included (1.08%). The best single seed is Harmony's at
  5.42% (shared kNN). scGLUE's shared kNN rule scores 0.00% on all three
  seeds.

### PBMC240 (development dataset)

Lineage recall over the 122 weakly labelled cells (117 lymphoid, 5
myeloid), and the share of all 237 cells predicted myeloid. Myeloid
recall rests on 5 cells and is anecdotal.

| Method | Rule | Lymphoid recall % | Myeloid recall % | Predicted myeloid % |
|---|---|---|---|---|
| **v3.1 as served** | best guess | **92.31** | 80.00 | 16.0 |
| Correlation to class mean | its own rule | 59.83 | 100.00 | 35.4 |
| Harmony (3-seed) | shared kNN | 38.75 ± 0.49 | 100.00 | 27.7 |
| MaxFuse (3-seed) | nearest centroid | 37.89 ± 3.24 | 86.67 ± 11.55 | 48.4 |
| Harmony (3-seed) | nearest centroid | 34.76 ± 2.15 | 100.00 | 29.8 |
| scGLUE (3-seed) | nearest centroid | 29.91 ± 2.26 | 80.00 | 47.7 |
| scGLUE (3-seed) | shared kNN | 24.50 ± 1.97 | 100.00 | 78.6 |
| Seurat CCA | native transfer | 21.37 | 100.00 | 71.3 |
| MaxFuse (3-seed) | shared kNN | 2.28 ± 1.31 | 100.00 | 82.4 |

A method that calls nearly everything myeloid scores 100% myeloid recall
and almost no lymphoid recall, so the two recalls are read as a pair. For
comparison, scANVI's best PBMC240 arm reached 38.75% lymphoid recall
(above).

### Fulcher 2026: baselines added after the held-out scoring

Fulcher's held-out result is its first scoring
([above](#fulcher-2026--the-first-held-out-evaluation)). These rows were
added after it, on what is now a development dataset. Balanced accuracy is
over the six types, scored with `fulcher2026_score.py`'s mapping.

| Method | Rule | Balanced accuracy % | Lymphoid recall % | Myeloid recall % | Predicted "other" % |
|---|---|---|---|---|---|
| **v3.1 as served** | best guess | **57.94** | 98.8 | 92.7 | 2.4 |
| Correlation to class mean | its own rule | 46.86 | 77.3 | 96.9 | 31.9 |
| Harmony (3-seed) | shared kNN | 31.98 ± 6.09 | 61.8 | 94.8 | 42.0 |
| Harmony (3-seed) | nearest centroid | 30.43 ± 5.60 | 60.7 | 85.6 | 36.3 |
| scGLUE (3-seed) | nearest centroid | 24.24 ± 0.62 | 44.3 | 68.6 | 40.8 |
| Seurat CCA, **biased in its favour**§ | native transfer | 18.87 | 33.6 | 97.1 | 55.7 |
| scGLUE (3-seed) | shared kNN | 18.34 ± 2.12 | 30.5 | 97.1 | 65.5 |
| MaxFuse (3-seed) | nearest centroid | 11.06 ± 1.23 | 35.8 | 61.0 | 42.3 |
| MaxFuse (3-seed) | shared kNN | 1.36 ± 0.45 | 1.0 | 93.9 | 92.4 |

§ Fulcher's labels came from a Seurat label transfer, so Seurat transfer
is biased in its favour here. It still scores 18.87%, 39.1 points below
v3.1.

"Other" is any class outside the six types: neutrophil, erythroid,
progenitor and the like. MaxFuse's kNN rule sends over 90% of Fulcher
cells there, and scGLUE's kNN rule and Seurat over half. For comparison, from the held-out scoring above: V2
5-seed 57.3, v3 5-seed 42.3, scANVI's best arm 47.8 (shared kNN).

### v3.1's confident answers

The best guess is what the baselines are compared with. The answer v3.1
commits to is a separate one, which may sit at group or lineage level
([baselines/v31_confident.csv](baselines/v31_confident.csv)):

| Dataset | Cells | Committed | Correct at the stated level, when committed |
|---|---|---|---|
| SCoPE2 | 1,490 | 53.0% | 58.9% |
| PBMC240 | 237 | 73.4% | 96.9% of labelled cells |
| Fulcher 2026 | 1,275 | 89.2% | 97.3% |

### Paired bootstrap: v3.1's best guess minus each baseline seed

**Its SCoPE2 rows are superseded** (swapped labels; see
[SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04)).
Its Fulcher rows stand.

`evaluate.paired_bootstrap_diff`, 2,000 stratified resamples, seed 0, on
balanced accuracy ([baselines/paired_bootstrap.csv](baselines/paired_bootstrap.csv)).
Each count is the number of baseline seeds whose 95% CI excludes zero in
that direction. Seurat's three seeds are one result counted three times.

| Dataset | Baseline | Rule | Favours v3.1 | Neither | Favours baseline | Difference, points |
|---|---|---|---|---|---|---|
| SCoPE2 restricted | MaxFuse | shared kNN | 3 | 0 | 0 | +10.1 to +11.2 |
| | MaxFuse | nearest centroid | 1 | 2 | 0 | −0.2 to +12.5 |
| | scGLUE | shared kNN | 3 | 0 | 0 | +11.0 to +13.4 |
| | scGLUE | nearest centroid | 1 | 2 | 0 | 0.0 to +6.5 |
| | Harmony | shared kNN | 2 | 1 | 0 | −2.8 to +25.9 |
| | Harmony | nearest centroid | 2 | 0 | 1 | −6.0 to +19.1 |
| | Seurat CCA | native | 3 | 0 | 0 | +7.8 |
| | Correlation | its own rule | 0 | 1 | 0 | +1.7 [−1.7, +5.0] |
| SCoPE2 unrestricted | MaxFuse | shared kNN | 1 | 2 | 0 | +0.1 to +0.6 |
| | MaxFuse | nearest centroid | 0 | 0 | 3 | −3.5 to −2.1 |
| | scGLUE | shared kNN | 3 | 0 | 0 | +1.1 |
| | scGLUE | nearest centroid | 1 | 2 | 0 | 0.0 to +1.0 |
| | Harmony | shared kNN | 0 | 0 | 3 | −4.3 to −1.1 |
| | Harmony | nearest centroid | 0 | 1 | 2 | −1.7 to +0.2 |
| | Seurat CCA | native | 0 | 0 | 3 | −2.7 |
| | Correlation | its own rule | 0 | 0 | 1 | −1.5 [−2.4, −0.6] |
| Fulcher 2026 | MaxFuse | shared kNN | 3 | 0 | 0 | +56.1 to +56.9 |
| | MaxFuse | nearest centroid | 3 | 0 | 0 | +46.1 to +48.3 |
| | scGLUE | shared kNN | 3 | 0 | 0 | +38.0 to +42.0 |
| | scGLUE | nearest centroid | 3 | 0 | 0 | +33.1 to +34.3 |
| | Harmony | shared kNN | 3 | 0 | 0 | +21.0 to +32.8 |
| | Harmony | nearest centroid | 3 | 0 | 0 | +23.2 to +33.8 |
| | Seurat CCA | native | 3 | 0 | 0 | +39.1 |
| | Correlation | its own rule | 1 | 0 | 0 | +11.1 [+7.3, +14.7] |

The scorer runs no paired bootstrap on PBMC240. There, the comparison is
the pair of recalls in the table above.

### What the numbers show

- **These comparisons are superseded.** The baselines here were run with
  a scaling mismatch, MaxFuse without its dimension-reduction settings and
  scANVI with a likelihood that cannot fit its inputs (see the correction
  in "Khoury 2026" below). The corrected reruns are in
  [baseline-corrections.md](baseline-corrections.md): on Fulcher, Harmony
  (60.8–63.0) and the correlation baseline (62.1) are ahead of v3.1's 57.9;
  on SCoPE2 restricted, with its labels corrected, only Harmony with
  nearest centroid is above chance; on PBMC240, v3.1's lymphoid recall (92.3) is still the
  highest, with PCA at 88.9.
- **As run, on the two PBMC datasets, v3.1 is ahead of every new baseline.** On
  Fulcher, every pairing favours v3.1, by 11 to 57 points. On PBMC240 it
  keeps 92.3% lymphoid recall. The tools that call most cells myeloid
  (MaxFuse's and scGLUE's kNN rules, Seurat) keep 2 to 25%.
- **The simple baseline is the strongest of the new comparators.** On
  Fulcher, correlation to the class mean scores 46.86%, against 57.94%
  for v3.1 (+11.1, CI excludes zero) and 47.8% for scANVI's best arm. On
  SCoPE2 restricted, v3.1 is not distinguishable from it (+1.7, CI
  includes zero). So the learned model adds about 11 points over the
  simplest use of the same reference on Fulcher, and nothing measurable on
  SCoPE2.
- **The SCoPE2 points below used swapped labels** (see
  [SCoPE2 with its labels corrected](#scope2-with-its-labels-corrected-2026-10-04)).
- **SCoPE2 unrestricted is a failure for every method here.** Every mean is
  under 5% balanced. The baselines' leads over v3.1 (up to 4.3 points,
  Harmony under the kNN rule) are differences between scores near the
  floor.
- **The integration methods are unstable.** Seed ranges reach 28.6 points
  (Harmony on SCoPE2 restricted), and scGLUE completes on Fulcher only
  with its cluster balancing off. A single run of any of them was never a
  safe stand-in.
- **scANVI stays ahead of v3.1 on SCoPE2 restricted** (77–78% against
  61.3%), as above.

## Khoury 2026: the sealed final evaluation

**What this is.** Khoury 2026 is single-cell proteomics of human PBMCs on
timsTOF instruments with mTRAQ 2-plex: 1,651 cells from two donors. It was
sealed on 2026-09-30, so no decision in this project could see it, and it
was scored once, on 2026-10-03, at the final v3.1 evaluation.

- **Protocol.** [protocol-khoury2026.md](protocol-khoury2026.md), frozen at
  `6d67d32`, with seven amendments, all committed before unsealing (the
  last, amendment 7, at `c516d98`; the owner's go-ahead at `74942f2`).
  Nothing was changed after a label was read.
- **Scored cells.** All 1,651, in five types: monocyte 434, CD4T 407, CD8T
  333, B 246, NK 231. Chance balanced accuracy is 20%.
- **Scoring.** Every model classifies against all 22 reference classes,
  mapped to the five types or "other" by the protocol's fixed table. "Other"
  is wrong for every type.
- **Tables** are in [`khoury2026`](khoury2026/per_seed_scores.csv), written
  by `benchmark/khoury2026_score.py`.

**Correction, 2026-10-03, after scoring: the baseline comparisons below are
not fair to the baselines.** A review after the scoring found that the
scoring code is right, but the baselines and scANVI were run in ways that
handicap them, on every dataset in this document:

1. **Scaling mismatch.** The RNA reference is z-scored over all its cells, a
   whole-blood mix (38% neutrophil, 14% erythrocyte); each protein query
   over its own PBMCs. Zero means a different cell on each side, which pulls
   PBMCs towards neutrophil and erythrocyte.
   - Positive control: held-out RNA cells in a PBMC mix lose about 15
     points of balanced accuracy under this recipe.
   - With the RNA side z-scored class-balanced (RNA labels only), the
     correlation baseline scores 62.1 on Fulcher (six types; v3.1 57.9) and
     49.8 on Khoury (v3.1 56.9). This is a post-hoc diagnostic, not a
     result.
2. **MaxFuse was configured without its dimension-reduction settings.** Its
   CCA was fitted on fewer cell pairs than features, so its embedding
   carries no cell-type signal. Every MaxFuse number is void.
3. **scANVI's likelihood mean cannot go below zero, but it was fitted to
   z-scores,** which are mostly negative. Every scANVI number in this
   document is affected.
4. Harmony assumes both sides share cell populations, and does worse here
   than plain PCA. Seurat CCA rescales the inputs it receives. scGLUE runs
   without its cluster balancing.

So the claim that v3.1 is ahead of every comparator rests on handicapped
comparators. The comparisons with v3, and v3.1's own numbers, are
unaffected. Khoury's rows below stay as scored, under the protocol.

**The corrected reruns (2026-10-04),** with the fixes committed before any
result was scored ([baseline-corrections.md](baseline-corrections.md)):

- **On Khoury (post-hoc),** PCA with the shared kNN rule scores 62.8 and
  scANVI 61.5 ± 2.1, against v3.1's best guess at 56.9 and its members
  alone at 60.0 ± 3.3. Their bootstraps against the members mostly favour
  the baseline or are inconclusive. Harmony (56.9) is level; the
  correlation baseline (49.8), scGLUE (38.9), MaxFuse (31.6) and Seurat CCA
  (29.7) stay behind v3.1.
- **On Fulcher (development),** Harmony (60.8–63.0) and the correlation
  baseline (62.1) are ahead of v3.1's 57.9, with CIs favouring them.
- **So v3.1's best guess is level with the best simple baselines, not
  ahead.** It stays ahead of MaxFuse, scGLUE and Seurat CCA. What it adds
  is its committed answers (93.8% committed, 96.7% correct at the stated
  level), which no baseline here offers.

**Three caveats, stated plainly.**

1. **The labels are not independent ground truth.** The authors clustered
   this same protein matrix and named the clusters by marker proteins. No
   RNA reference was involved. A method that recovers the matrix's dominant
   structure agrees with these labels partly by construction. Fulcher's
   labels, by contrast, came from an RNA reference.
2. **The input was already batch-corrected.** The authors applied ComBat
   before the matrix reached us. We added no correction of our own, as with
   Fulcher, but unlike Fulcher this input arrived corrected.
3. **This is a different technology.** Khoury 2026 is timsTOF with mTRAQ
   2-plex. Fulcher is TMT (Orbitrap, FragPipe), PBMC240 is label-free DIA
   (DIA-NN), and SCoPE2 is different again.

As everywhere in this document, scANVI is transductive: it trains on the
Khoury cells themselves, while our encoders are fixed and zero-shot.

**What ran.**

- **v3.1 as served** (release 0.3.0, both service flags on), through
  `pipeline.embed_query` with no batch correction. Its gate passed before
  anything was embedded: each of the five V2 members reproduces its NB1d
  PBMC240 latents at a median cosine of 1.0, and the dev gate passed
  ([gate.json](khoury2026/gate.json)). It is scored on its best guess, and
  each member alone under the shared kNN rule.
- **v3 as served**, under nearest centroid and the shared kNN rule.
- **scANVI**, three arms, three seeds each. Its headline is
  `measuredgenes`, the arm with the highest 3-seed mean shared-kNN
  balanced accuracy. That choice used Khoury's labels, as the protocol
  allows, and can only favour scANVI.
- **Baselines** (amendment 3): MaxFuse, scGLUE and Harmony with seeds 0–2
  under the shared kNN rule; Seurat CCA's native transfer and the
  correlation baseline once each.

All 20 training runs completed; none diverged and none failed. Two things
went wrong along the way, both before any label was read:

- **A false start (13:00).** The first launch ran under the system Python,
  not the project's environment. Every step stopped at import within
  seconds, before loading any data or writing any record. The queue was
  restarted in the right environment at 13:05.
- **MaxFuse seed 0 failed once.** At 17:24 it stopped with "SVD did not
  converge", inside scikit-learn's CCA during MaxFuse's pivot refinement.
  Amendment 7 allows a failed run one rerun before any label is read. The
  rerun, with the same seed and settings, completed at 22:52. MaxFuse's
  matching is not deterministic (its record says so), which fits one run
  failing where the next did not. A first launch of the rerun script
  stopped before Python started, because a path in the script was garbled;
  nothing ran. Both attempts' logs are kept in
  `benchmark/results/khoury2026_logs/` (gitignored).

The scorer ran once, from 22:53 to 23:00. Before reading a label it
checked the gate, the sha256 of all 21 model files, all 20 run records and
every prediction file's rows and columns. The one rerun the protocol allows,
to check reproduction only, followed at 23:02. All seven tables matched
the first run's byte for byte (sha256), and so did the printed summary.

### Balanced accuracy over the five types

Mean ± SD (min–max) over seeds, where a family has more than one run.

| Model | Product rule / native / own rule | Shared kNN rule |
|---|---|---|
| **v3.1 as served** | **56.9** (best guess) | |
| v3.1's members (V2), each alone | | **60.0 ± 3.3** (57.1–65.2) |
| v3 as served | 40.9 (nearest centroid) | 39.8 |
| scGLUE | | 42.8 ± 1.7 (41.0–44.3) |
| Correlation to class mean | 38.7 | |
| scANVI, `measuredgenes` (**best arm, headline**) | 30.9 ± 3.0 (27.4–32.8) | 36.1 ± 0.8 (35.5–37.0) |
| scANVI, `cellmedian` | 33.3 ± 2.5 (30.4–34.9) | 30.4 ± 7.4 (22.4–37.1) |
| scANVI, `as_provided` | 24.1 ± 5.8 (20.3–30.8) | 26.4 ± 2.1 (24.0–27.7) |
| Seurat CCA | 30.4 (native transfer) | |
| Harmony | | 27.6 ± 1.3 (26.4–29.0) |
| MaxFuse | | 0.8 ± 0.3 (0.6–1.2) |

Source: [family_summary.csv](khoury2026/family_summary.csv) and
[per_seed_scores.csv](khoury2026/per_seed_scores.csv).

### Recall per type

Mean over seeds, %. Lineage recall is the share of lymphoid (CD4T, CD8T,
NK, B; 1,217 cells) or myeloid (monocyte; 434) cells whose predicted class
is in the right lineage.

| Model, rule | CD4T | CD8T | NK | B | Monocyte | Lymphoid | Myeloid |
|---|---|---|---|---|---|---|---|
| v3.1, best guess | 84.5 | 2.7 | 29.0 | 81.3 | 87.1 | 98.1 | 97.2 |
| v3.1's members, shared kNN | 63.4 | 37.5 | 22.6 | 79.8 | 97.0 | 96.3 | 97.4 |
| v3, nearest centroid | 9.1 | 61.0 | 3.5 | 40.7 | 90.3 | 70.3 | 98.2 |
| scGLUE, shared kNN | 16.6 | 5.8 | 53.7 | 79.3 | 58.7 | 67.5 | 84.8 |
| Correlation to class mean | 60.2 | 1.2 | 16.0 | 48.4 | 67.5 | 59.0 | 96.5 |
| scANVI best arm, shared kNN | 27.4 | 3.0 | 12.7 | 45.4 | 91.9 | 47.8 | 97.2 |

### Paired bootstrap

Balanced accuracy difference, 2,000 stratified resamples, seed 0
([paired_bootstrap.csv](khoury2026/paired_bootstrap.csv)). Every one of the
77 pairings has a 95% CI that excludes zero, and every one favours the
first-named model.

| Comparison | Rules | Pairings with CI excluding 0 | Mean difference (range) |
|---|---|---|---|
| v3.1 − v3 | best guess vs nearest centroid | 1 of 1, favours v3.1 | +16.0 [+13.6, +18.5] |
| v3.1 − v3 | shared kNN, each member vs v3 | 5 of 5, favour v3.1 | +20.3 (+17.3 to +25.4) |
| v3.1 − scANVI best arm | best guess vs native | 3 of 3, favour v3.1 | +26.0 (+24.1 to +29.5) |
| v3.1 − scANVI best arm | shared kNN | 15 of 15, favour v3.1 | +24.0 (+20.1 to +29.7) |
| v3 − scANVI best arm | nearest centroid vs native | 3 of 3, favour v3 | +10.0 (+8.1 to +13.5) |
| v3 − scANVI best arm | shared kNN | 3 of 3, favour v3 | +3.7 (+2.8 to +4.3); lowest CI bound +0.5 |
| v3.1 − scGLUE | shared kNN | 15 of 15, favour v3.1 | +17.2 (+12.8 to +24.2) |
| v3.1 − correlation | best guess vs its own rule | 1 of 1, favours v3.1 | +18.3 [+15.9, +20.5] |
| v3.1 − Seurat CCA | best guess vs native | 1 of 1, favours v3.1 | +26.5 [+24.2, +28.8] |
| v3.1 − Harmony | shared kNN | 15 of 15, favour v3.1 | +32.4 (+28.1 to +38.8) |
| v3.1 − MaxFuse | shared kNN | 15 of 15, favour v3.1 | +59.2 (+55.9 to +64.7) |

### v3.1's confident answers

The best guess is what the comparators are scored against. The answer
v3.1 commits to may sit at group or lineage level, and is judged at the
level it states, as on Fulcher
([v31_confident.json](khoury2026/v31_confident.json)).

| Author type | Cells | Committed | Correct at the stated level | Class / group / lineage answers |
|---|---|---|---|---|
| CD4T | 407 | 97.8% | 99.7% | 1 / 312 / 85 |
| CD8T | 333 | 92.8% | 98.7% | 4 / 286 / 19 |
| NK | 231 | 90.5% | 87.1% | 0 / 26 / 183 |
| B | 246 | 86.6% | 91.5% | 183 / 18 / 12 |
| monocyte | 434 | 96.5% | 99.8% | 1 / 5 / 413 |
| **All 1,651** | 1,651 | 93.8% | **96.7%** | 189 / 647 / 712 |

- **Abstentions:** 5.9% ambiguous between classes, 0.2% out of
  distribution, 0.2% empty.
- **Composition:** T cell 38.8%; lineage:myeloid 25.1%; lineage:lymphoid
  18.0%; B cell 11.4%; abstain 6.2%; monocyte/macrophage 0.4%.
- **Class-level answers** are 11.5% of all cells, nearly all of them B cells.

### What the numbers show

1. **As run, v3.1 is ahead of every comparator, in every pairing.** The
   comparators were handicapped (see the correction above), so this
   overstates its lead over the baselines and scANVI. Its best guess
   scores 56.9%. The strongest comparators are scGLUE (42.8%), v3 (40.9%),
   the correlation baseline (38.7%) and scANVI's best arm (36.1%, shared
   kNN). All 77 bootstrap CIs exclude zero in v3.1's favour, or in v3's
   against scANVI.
2. **V2 beats v3 again, now on the sealed test.** Each V2 member alone
   beats v3 by 17 to 25 points under the shared kNN rule, 5 of 5, as all 50
   pairings did on Fulcher.
3. **v3.1 separates lineages almost perfectly, but not T and NK subsets.**
   Its best guess has lymphoid recall 98.1% and myeloid 97.2%. It calls
   94% of CD8T cells CD4T, so CD8T recall is 2.7%, and half of NK cells
   CD8T, so NK recall is 29.0%. The members alone split CD8T somewhat
   better (37.5%), at CD4T's cost (63.4%). This is Fulcher's weakness
   again, where V2 called 63% of CD8T cells CD4T. CD4T, B and monocyte are
   the three types it mostly gets right (81–87%).
4. **Its committed answers hold, mostly at a coarse level.** v3.1 commits
   on 93.8% of cells, and 96.7% of those answers are right at the level
   stated. But T cells mostly stop at "T cell", and monocytes and NK cells
   at their lineage. NK is the weak type: 87.1% correct when committed.
5. **v3 is ahead of scANVI here under both rules,** by 10.0 points (product
   rule vs native) and 3.7 points (shared kNN, the narrowest margin in the
   table). On Fulcher, scANVI's best arm beat v3 under the shared kNN rule.
   v3's errors: it calls 74% of CD4T cells CD8T, and sends 66% of NK and
   49% of B cells to "other". Across all cells, 23% go to "other", mostly
   neutrophil (10.6%) and macrophage (9.6%).
6. **scANVI is weak on Khoury in every arm.** Its best is 36.1%, sending
   38% of cells to "other", mostly neutrophil.
7. **The integration tools spread widely.** scGLUE is the strongest
   baseline (42.8%), and the only comparator with real NK recall (53.7%),
   but it calls half of CD4T cells monocyte. Seurat CCA (30.4%) and Harmony
   (27.6%) send about half of all cells to "other". **MaxFuse scores
   0.8%:** its kNN rule calls 91% of cells neutrophil, whatever their type.
   That is what the same script and settings did on Fulcher (1.36%, over
   90% "other"), so it is how MaxFuse behaves under the protocol's fixed
   settings on these sparse queries, not a Khoury-only fault. Nothing was
   tuned, then or since.
8. **The simple baseline is again competitive with the learned tools.**
   Correlation to the class mean (38.7%) beats every scANVI arm, Seurat,
   Harmony and MaxFuse, and trails v3.1 by 18.3 points.

**What this result does not show.** It is one dataset, two donors and five
common types, with labels that come from the same protein measurements
(caveat 1). It says nothing about rare types, other tissues, or how well
v3.1 separates CD4T from CD8T, which it does not.

## v4 against the corrected baselines (Track G, Phase 4)

v4 is v3.1's answers with a better best guess (`service/pipeline/fusion.py`;
`research/notebook-run-history.md`, entry 24). It is scored here exactly as
v3.1 was scored against the corrected baselines
([baseline-corrections.md](baseline-corrections.md)), with the same
functions and the same paired bootstrap: 2,000 resamples stratified by true
type, seed 0, 95% CI.

- **Development data:** SCoPE2 (both versions), PBMC240 and Fulcher.
  - Script: `benchmark/baselines_v4_score.py`.
  - Tables: [v4_development/](v4_development/).
  - Fulcher shaped v4's design, so its rows are not evidence of a held-out
    gain.
- **Khoury 2026, post-hoc:** its labels were read at its one scoring, before
  v4 existed. v4 was frozen before this run and played no part in Khoury.
  - Script: `benchmark/khoury2026_posthoc_v4.py`.
  - Tables: [khoury2026_posthoc_v4/](khoury2026_posthoc_v4/).

### Development data

| Dataset | v3.1 | v4 | v4 − v3.1 (95% CI) | Best corrected baseline, v4 minus it |
|---|---|---|---|---|
| Fulcher 2026, six types | 57.9 | 65.0 | **+7.1 (5.2 to 9.1)** | Harmony NC 63.0: +2.0 (CI −1.5 to 5.3); correlation 62.1: +2.9 (−0.2 to 5.8) |
| PBMC240, lymphoid recall | 92.3 | 92.3 | 0 | PCA 88.9 |
| SCoPE2 published, restricted | 38.7 | 38.0 | −0.7 (−2.3 to 0.8) | Harmony NC 63.0: −25.0, CI favours Harmony |
| SCoPE2 reprocessed, restricted | 32.9 | 33.3 | +0.4 (−0.8 to 1.5) | Seurat 51.8, PCA NC 50.5, Harmony NC 48.9 ± 1.9: all at chance; 27 of 31 CIs favour the baseline |

**The Phase 4 checks pass.** They were set in the v4 plan:
- no paired CI favours v3.1 on any development dataset;
- correct-when-committed falls by at most 2 points. The changes are SCoPE2
  −0.05, PBMC240 0, Fulcher +0.53 and SCoPE2 reprocessed 0.

**v4's confident answers are v3.1's sets, with v4's guess joined.**
- Fulcher: 88.2% of cells committed, 97.8% of those correct, against v3.1's
  89.2% and 97.3%.
- PBMC240: 73.4% and 96.9% for both.

### Khoury 2026, post-hoc

| Five types | v3.1 | v4 |
|---|---|---|
| Best guess, balanced accuracy | 56.9 | **61.8** |
| v4 − v3.1 (95% CI) | | +4.9 (3.4 to 6.3) |
| Recall CD4T / CD8T / NK / B / monocyte | 84.5 / 2.7 / 29.0 / 81.3 / 87.1 | 83.8 / 2.4 / 45.9 / 82.1 / 94.9 |
| Committed; correct when committed | 93.8%; 96.7% | 93.7%; 96.7% |

v4's correlation term was used on Khoury: its upload agreement was 0.497.

Against the corrected baselines:
- **The CI includes zero:**
  - PCA with shared kNN (62.8): −1.0 (−2.8 to 0.7);
  - scANVI with shared kNN, seeds 0–2: +1.3, −2.2 and +1.8.
- **v4 is ahead, with every CI excluding zero:** Harmony (3 seeds), the
  correlation baseline (+12.0), scANVI's classifier (3 seeds), Seurat CCA
  (+32.1), MaxFuse (6 runs) and scGLUE (3 seeds).

### What the numbers show

1. **v4 closes v3.1's gap to the best simple baselines, but does not open
   one.**
   - Before: those baselines were ahead of v3.1 with CIs favouring them,
     Harmony and correlation on Fulcher, and PCA with kNN and scANVI on
     Khoury.
   - Now: v4 is level with them on both datasets, and ahead of every other
     comparator.
2. **No method separates SCoPE2's macrophages from its monocytes.**
   - **The published matrix:** restricted to macrophage or monocyte, only
     Harmony with nearest centroid beats chance (63.0).
   - **The reprocessed matrix,** with missing values kept missing and no
     centring or batch correction: Harmony falls to 48.9 ± 1.9. Every
     baseline lands between 41.8 and 51.8, at or below chance. Harmony's
     63.0 came from the published matrix's preprocessing, not from the
     cells.
   - **v4 is below chance on both versions** (38.0 and 33.3), so its errors
     are systematic. It calls PMA-treated U-937 macrophages monocytes more
     often than the reverse: on the published matrix it recalls 17% of
     macrophages and 59% of monocytes. The baselines' CIs favour them over
     v4 because they are coin flips where v4 is reliably inverted.
   - **v4 is v3.1's encoder here.** Its correlation term is not used on
     either SCoPE2 version (agreement 0.17), so v4 is v3.1's encoder with
     class-balanced centroids.
   - **Across all 22 types,** every method stays under 9% on the reprocessed
     matrix.
3. **The gains are in NK and monocyte** on Khoury, and in NK, monocyte and
   CD4T on Fulcher.
4. **CD8T stays unsolved for every method.** On Khoury v4's CD8T recall is
   2.4%; on Fulcher it is 24%. Fulcher measures neither CD8A, CD8B nor CD4.
5. **The reprocessed SCoPE2 is harder still.** Its missing values are kept
   missing.
   - Both models commit on 31% of cells, and 49.4% of those answers are
     right at the level stated.
   - Unrestricted balanced accuracy is 5.5%.

## Two protocols, not a chosen one

Per the repository owner's explicit instruction: the choice between the
shared kNN-classifier rule and native nearest-centroid is **not** made
based on which one favors "ours" on this SCoPE2 evaluation set — doing so
would be tuning a product decision on the test set. Both are reported for
every method, in both tables above, and no recommendation is made here
about which one the live service should use. The same non-tuning
discipline applies to the pool-first-vs-post-hoc-masking kNN choice above.

## What's still open

- **Why v3's SCoPE2 restricted-regime performance varies so much by seed
  (59.04–88.40% balanced, shared kNN rule) is not explained here** — only
  measured. `v3_seed0` shipping was not a principled choice among the five;
  it is simply the seed that was trained first. Not addressed by Track D;
  a real open question for whichever notebook takes it up next.
- MaxFuse, scGLUE and Harmony now have three seeds each
  ([Baselines beyond scANVI](#baselines-beyond-scanvi-track-d-extension)),
  and their seed-to-seed spread is large. scGLUE's failure on Fulcher was
  traced to its cluster balancing (protocol amendment 7); with balancing
  off it completes on every dataset. How much balancing changes its scores
  where it can run is not measured.
- **scANVI training on this hardware (Apple MPS) is not fully
  reproducible even with an explicit seed** — seed 0's re-run this round
  landed meaningfully differently from its original run (see the
  scANVI-across-seeds section). Seeds 1 and 2 reproduced closely. Not
  investigated further here; worth knowing before treating any single
  scANVI seed's number as fixed.
- `web/data/atlas_manifest.json`'s `benchmark.rows` is untouched — still `[]`,
  `status: "pending"` — regardless of everything above. Nothing here is
  wired into the live site.
