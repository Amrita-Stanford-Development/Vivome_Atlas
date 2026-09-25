# VivOME TODO

Tracks progress against `VivOME_Improvement_Roadmap.md`. Update after each
Claude Code round or notebook run: tick the box, add the commit hash or the
notebook output path, and log it in the changelog at the bottom.

Status markers: `[x]` done, `[~]` in progress, `[ ]` not started, `[!]` blocked.

Last updated: 2026-09-25 (A2 review: PBMC240 divergence explained as a preprocessing-recipe mismatch, not a service bug)

---

## 0. Backlog (from before the roadmap)

- [x] Fix the inverted alpha and the wrong neighbour graph in `smoothing.py`
- [x] Rebuild the fair benchmark under the nine rules
- [x] Fix the encoder: ReLU replaced by GELU, e2e cosine 1.000000 on SCoPE2 (`056f136`)
- [x] Commit `service/model/app_export/`, with LFS for the TSV (`2d3ad76`)
- [x] Rescore ours on the real embedding and delete the reconstruction rows (`f15cbd1`)
- [x] Sanity check reproduced to 4 decimals; trained centroids identical to class mean centroids
- [x] Fix the cell count mismatch (row 42616)
- [x] scANVI with 3 seeds (`ed5c927`)
- [x] Flag every service path number from before `056f136` as invalid (`920971d` / `292aeb7`)
- [x] Correct the provenance explanation, since the ReLU bug confounded it
- [x] The 2 failing JS tests are the documented LFS pointer checks. No fix needed

---

## 1. Critical product defects (found this round, not yet fixed)

Ordered by severity. None of them can be fixed with protein labels, and none needs protein labels.

- [x] **Live service diverges on data with missing values — EXPLAINED, not a service bug.** Fixed the two known causes (log transform, smoothing graph on z-scored values) — `2334e48`. The apparent residual divergence against `pbmc240_zscored_all_genes.csv` (median cosine 0.21, 94/237 anti-correlated) was a mis-specified acceptance test: that file was built with a deliberately different preprocessing recipe (>=5% detection-rate filtering, log2(x+1) not log2(x), per-cell median normalization, and ~52.6% of values imputed from Normal(1st percentile, 0.3) — a left-censored "below detection limit" imputation), not the service's own convention. Reproducing that exact recipe as a standalone diagnostic (not service code) and feeding it through the real fixed pipeline gets median cosine **0.9969** (5th pct 0.9259, min 0.6603) to the actual file's embedding — confirming the service's math is correct and the divergence was entirely the comparison file's own preprocessing choice. SCoPE2 (no missing values, so it can't exercise this at all) reproduces exactly: cosine 1.000000, 45.37/31.08 and 86.17/79.79 to 4 decimals. Owner: A2.
- [x] **Raw intensities are never log transformed.** Fixed: `alignment.detect_and_transform_value_scale`, `2334e48`. Test: a log matrix and its `2**x` version transform to the same values. Owner: A2.
- [ ] **Narrow uploads collapse.** Per upload z scoring removes shared identity. Single cell type uploads score 11.2 percent unrestricted in simulation, and the SCoPE2 like RNA upload loses 15.6 points from preprocessing alone. Owner: new notebook T1 NB1b.
- [~] **The coverage floor refuses almost every real dataset** under the per cell mask. Replaced the fractional 0.15 floor with an absolute `MIN_OBSERVED_GENES = 100` — `2334e48` — but the value itself is PROVISIONAL, not yet calibrated against NB1b's accuracy-vs-observed-genes curve. Owner: A2, using NB1b's evidence.
- [ ] **Smoothing costs 10 points of balanced accuracy on natural compositions** (75.7 to 65.6 on RNA) while helping narrow uploads by 4 to 6 points. Keep it only where it is measured to help. Owner: NB1b ablation.

---

## 2. Claude Code tracks

### Track A2, faithfulness gate (branch `faithfulness/a2`)

- [x] Service reproduces the notebook embedding on SCoPE2 (GELU fix)
- [x] SCoPE2 gene level TSV has 0 NaN (already imputed), so it cannot test mask drift
- [x] e2e test fixed so it exercises `pipeline.py`'s real smoothing input
- [x] Combined drift measured on raw PBMC240: median cosine 0.78
- [x] Separate the drift into its parts: mask convention vs graph input vs missing log transform. Measured graph-input-alone effect (median cosine 0.98, same raw input), combined log+graph effect (median cosine 0.93, same raw input) — `2334e48`. Mask convention deliberately untouched (see below). The remaining apparent divergence against `pbmc240_zscored_all_genes.csv` (median 0.21) turned out to be that file's own different preprocessing recipe, not the service — see item 1 above and the A2 review round below. Reproducing that exact recipe as a diagnostic gets median cosine 0.9969 to the real file.
- [x] Fix: build the smoothing graph on the z scored, filled matrix (`2334e48`) — SCoPE2 now reproduces the notebook embedding at cosine 1.000000, and 45.37/31.08 / 86.17/79.79 to 4 decimals
- [x] Fix: detect linear scale input and log2 transform it (`2334e48`)
- [~] Fix: redefine the coverage floor, from NB1b's accuracy vs observed genes curve. `MIN_OBSERVED_GENES = 100` landed (`2334e48`) but is PROVISIONAL — NB1b's curve hasn't been calibrated against yet
- [ ] Decide the mask convention from NB1b's 2 by 2 ablation (current evidence favours per cell) — untouched this round, per cell mask kept as instructed
- [x] Golden fixtures on a dataset with missing values, not only SCoPE2 (`bb8ce6b`) — 50 real SCoPE2 cells + 50 real raw PBMC240 cells, full response frozen and compared per-cell
- [x] Write `canonical_preprocessing.json` for the notebooks (`bb8ce6b`)

**A2 review round (diagnostics only, no service changes):**

- [x] Confirmed cell alignment was by cleaned ID, not position: raw file has 238 cells, processed file has 237 (`Astral_TopMedPBMC1_041725_SP_217` dropped, under 200 proteins), 237/237 matched correctly.
- [x] Reproduced `pbmc240_zscored_all_genes.csv`'s exact recipe as a standalone diagnostic (not service code): first gene symbol, keep proteins detected in >=5% of cells, collapse duplicates by median, log2(x+1), per-cell median normalization (subtract cell median, add median of medians), impute missing (52.6% of values) from Normal(1st percentile of all values, 0.3), gene-wise z-score. Fed through the real fixed pipeline: median cosine 0.9969 to the actual file's embedding (5th pct 0.9259, min 0.6603) — confirms the service math is right; the divergence was 100% preprocessing choice.
- [x] Weak-lineage accuracy (T cell/NK cell -> lymphoid, Monocyte -> myeloid; Platelet/Dendritic out of scope), scores only: (a) fixed service on raw PBMC240, (b) the processed file, (c) fixed service's log2 + per-cell median normalization with no imputation — **all three identical**: 8.4% overall accuracy, 100% myeloid recall, 0% lymphoid recall, ~0-0.4% abstention rate. The limiting factor at this level isn't preprocessing at all — Stage 6's out-of-distribution threshold essentially never fires for these lymphoid cells (0-0.4% abstained across all three variants), so every T/NK cell gets forced into an incorrect myeloid label regardless of which preprocessing recipe produced its embedding. Consistent with, and likely the same root cause as, "Narrow uploads collapse" above — NB1b's territory, not something per-cell normalization alone fixes.

### Track B, deployment hardening (branch `hardening/b`)

- [ ] `gene_ids.py` plus the frozen `gene_id_map_v1.tsv`
- [ ] Accept symbols, Ensembl IDs, UniProt groups and DIA-NN reports
- [ ] Orientation detection, rejecting ambiguous input
- [ ] Minimum cell count and value scale detection (the detection feeds A2's log transform)
- [ ] TorchScript or ONNX export with an equivalence test
- [ ] FAISS search with an exact equivalence test
- [ ] `MODEL_CARD.md` and `versions.html` content, using the corrected test cell numbers below
- [ ] Per upload logging

### Track C, v3.1 scaffold (branch `integration/v31-scaffold`)

- [ ] `PIPELINE_VERSION` flag, default `v3`
- [ ] Golden test proving v3 behaviour is unchanged
- [ ] `LabelSpaceEstimator`, `AbstentionScorer`, `ConformalCalibrator` interfaces with v3 implementations
- [ ] `encode_with_hidden` returning 512 dimensional features
- [ ] Temperature and bias options in `assignment.py`
- [ ] Response schema v3.1 and a section in `docs/projection-service.md`

### Track D, benchmark extension (branch `benchmark/d`)

- [x] One identical cell set for every arm
- [x] scANVI with 3 seeds; "spread" confirmed as the range (max minus min), now reported alongside SD
- [x] Paired bootstrap, ours minus scANVI, per seed: CI excludes zero on every seed in both regimes
- [x] Ours unrestricted under the shared kNN rule: 55.37 acc / 38.69 bal
- [x] Pool first restricted kNN variant, matching `assignment.py`
- [ ] Freeze `PROTOCOL.md`
- [ ] MaxFuse and scGLUE with 3 seeds each
- [ ] Dataset registry refactor
- [ ] PBMC240 at lineage level as a second dataset
- [ ] Further MS datasets once track E delivers
- [ ] Add the NB1b retrained model as its own arm, and v3.1 once track F lands

### Track E, Tier 2 data ingestion (branch `data/e`)

- [!] Blocked until track B's gene ID mapping table is merged

### Track F, v3.1 integration (branch `integration/v31`)

- [!] Blocked on A2, B, C merged and the T1 NB4 export

---

## 3. Colab notebooks

### Tier 1

- [x] **T1 NB1, simulation bench.** All gates pass; output in `Data/Results/Tier1_v31/NB1/`
  - [x] Re encoding reproduces `reference_embedding.npy` (median cosine 1.000000)
  - [x] Seed 0 split reproduced exactly (0.917341 / 0.724889)
  - [x] Training membership: every donor contributed about 65 percent of its cells to training. No donor level holdout exists for v3
  - [x] Calibration suite (from val) and evaluation suite (from test), 240 uploads each, disjoint from each other and from training
  - [x] Real missingness profiles for SCoPE2, PBMC240 and Fulcher
  - [x] v3 baseline on the evaluation suite
  - [x] Composition experiment (see section 1, narrow uploads)
- [~] **T1 NB1b, composition robust standardization.** Written and dry run end to end on a mock Drive; ready to run on Colab. Four variants (v3 recipe control, per cell z, mini upload gene z, dual), selection on the calibration suite only, plus the A2 preprocessing ablation and the coverage floor curve
- [ ] **T1 NB2, label space and decision rule.** Should start after NB1b, since NB1b may change the encoder
- [ ] **T1 NB3, abstention and conformal.** Needs `abstention.py` and `calibration.py`, plus `encode_with_hidden` from C
- [ ] **T1 NB4, integration, evaluation and export**
- [ ] **T1 NB5, optional modes**

### Tier 2

- [ ] **T2 NB6, external data build**
- [ ] **T2 NB7, wider reference with the Cell Ontology hierarchy**
- [ ] **T2 NB8, v4 training.** Should also train with a donor held out, since v3 never had one

---

## 4. Open decisions

| Decision | Settled in | Status |
|---|---|---|
| Mask convention | NB1b ablation, then A2 | Leaning per cell (better in simulation with realistic dropout); kept unchanged in `2334e48`, pending NB1b |
| Smoothing graph input | A2 | **Settled and implemented (`2334e48`):** z-scored, filled. Raw with zeros is unsafe on protein intensities |
| Log transform of linear scale input | A2 with B | **Settled and implemented (`2334e48`):** yes, when linear scale is detected |
| Coverage floor definition | NB1b curve, then A2 | Provisional value landed (`MIN_OBSERVED_GENES = 100`, `2334e48`); not yet calibrated against NB1b's curve |
| Per-cell loading normalization (subtract each cell's own median after log2, e.g. to correct for loading/depth differences between cells) | NB1b, then A2 | Open. Not in the service. A2 review's diagnostic (log2 + per-cell median norm, no imputation) showed no measurable effect on PBMC240 weak-lineage accuracy, but that comparison was dominated by the OOD-abstention threshold never firing for lymphoid cells, not a fair test of this specific normalization's value — needs NB1b's simulation-based ablation, not a real-data comparison this confounded |
| Keep smoothing on by default | NB1b | Open. It hurts natural compositions by 10 points |
| Were TSP14, TSP21, TSP25 in production training | NB1 | **Settled: yes, about 65 percent of their cells** |
| Product decision rule | NB2, on simulations only | Open. Centroid 79.79 vs pool first kNN 77.50 on SCoPE2 is recorded, not decisive |
| Per request vs binned calibration | NB2 | Open |
| Flat vs hierarchical label space | NB2, T2 NB7 | Open |

---

## 5. Current verified numbers

SCoPE2, 1,490 cells, real embedding, unless marked RNA.

| Measure | Value |
|---|---|
| Ours, unrestricted, native centroid | 45.37 acc / 31.08 bal |
| Ours, restricted, native centroid (what the product delivers today) | 86.17 / 79.79 |
| Ours, unrestricted, shared kNN (benchmark rule) | 55.37 / 38.69 |
| Ours, restricted, shared kNN, post hoc masking (benchmark only) | 88.40 bal |
| Ours, restricted, pool first kNN (what the service would give with kNN) | 77.50 bal |
| Ours minus scANVI, restricted, shared kNN, paired bootstrap | +9.1 to +14.4, CI excludes 0 on every seed |
| Ours minus scANVI, unrestricted, shared kNN, paired bootstrap | +21.7 to +32.7, CI excludes 0 on every seed |
| Unsupervised methods (MaxFuse, Harmony, scGLUE), restricted | about 47 to 54 bal, at chance |
| Majority class floor, restricted | 73.56 / 50.00 |
| RNA to RNA, SCoPE2 mask, **test cells only** (replaces the published 95.5 / 74.8) | 93.19 / 65.71 (OT), centroid 67.29 bal |
| RNA to RNA, full coverage, **test cells only** (replaces the published 97.6 / 85.7) | 94.64 / 80.01 (OT) |
| RNA, SCoPE2 like upload, global z vs per upload z plus smoothing, unrestricted bal | 64.7 vs 49.1 |
| RNA, SCoPE2 like upload, per upload z, oracle restricted bal | 87.9 (protein restricted: 79.8) |
| RNA, single cell type uploads, unrestricted bal (simulation) | 11.2 |
| Modality probe | 98.99 ± 0.28 |
| Latent centroid cosine | monocyte 0.830, macrophage 0.190 |
| Abstention at 0.9779 | 80.2 percent |
| Conformal empirical coverage | 33.7 percent (target 90) |

Still needed before claiming state of the art: at least two more MS datasets.
The published held out cell type AUC of 1.000 is not a valid unseen type test,
because the held out classes were in training.

---

## 6. Changelog

| Date | What | Reference |
|---|---|---|
| 2026-09-22 | Prototype export notebook run, `app_export/` produced, bundle zipped | Drive `_prototype_bundle/` |
| 2026-09-23 | Fair benchmark rebuilt under the nine rules | `tools/fair_benchmark/` |
| 2026-09-23 | `smoothing.py` alpha and graph fixed in the production service | repo |
| 2026-09-24 | Encoder GELU fix, e2e cosine 1.000000 on SCoPE2 | `056f136` |
| 2026-09-24 | `app_export/` committed with LFS | `2d3ad76` |
| 2026-09-24 | Ours rescored on the real embedding, reconstruction rows removed | `f15cbd1` |
| 2026-09-24 | scANVI with 3 seeds | `ed5c927` |
| 2026-09-24 | Roadmap written | `VivOME_Improvement_Roadmap.md` |
| 2026-09-24 | Pre GELU numbers flagged invalid, e2e test fixed, paired CI, pool first kNN, live divergence on missing data found (cosine 0.78) | `920971d`, `292aeb7` |
| 2026-09-24 | T1 NB1 run: all gates pass; composition collapse, training cell inflation, coverage floor problem found | Drive `Tier1_v31/NB1/` |
| 2026-09-25 | Roadmap revised: NB1b inserted before NB2, A2 changed to a fix track | `VivOME_Improvement_Roadmap.md` |
| 2026-09-25 | Track A2: log transform, smoothing graph on z-scored values, coverage floor as an absolute gene count. SCoPE2 now reproduces the notebook embedding exactly (cosine 1.000000; 45.37/31.08, 86.17/79.79 to 4 decimals). Real PBMC240 divergence measured before/after (0.78 -> ~0.93 same-input; still 0.21 against the independently-produced zscored file, not yet explained at this point). Golden fixtures on 50 SCoPE2 + 50 real PBMC240 cells. `canonical_preprocessing.json` written for the notebooks | `2334e48`, `bb8ce6b` |
| 2026-09-25 | A2 review: PBMC240 divergence explained — the comparison file uses a deliberately different recipe (5% detection filter, log2(x+1), per-cell median normalization, ~52.6% values imputed from Normal(1st pct, 0.3)), not a service bug. Reproducing that exact recipe as a diagnostic gets median cosine 0.9969 to the real file. Cell alignment re-confirmed correct (237/237 matched by cleaned ID). 3-way weak-lineage accuracy (service / processed file / service+per-cell-norm-no-imputation) came out identical across all three (8.4% overall, 100% myeloid recall, 0% lymphoid recall) — the OOD-abstention threshold, not preprocessing, is the limiting factor at this level. Added "per-cell loading normalization" as an open decision for NB1b. No service code changed this round | diagnostics only, not committed to `service/` |
