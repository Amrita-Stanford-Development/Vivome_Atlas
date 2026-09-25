# VivOME TODO

Tracks progress against `VivOME_Improvement_Roadmap.md`. Update after each
Claude Code round or notebook run: tick the box, add the commit hash or the
notebook output path, and log it in the changelog at the bottom.

Status markers: `[x]` done, `[~]` in progress, `[ ]` not started, `[!]` blocked.

Last updated: 2026-09-25 (Track B follow-up: real DIA-NN upload support, OpenMP fix scoped to macOS, UniProt isoform resolution, model-card corrections and citations)

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
- [x] **The coverage floor refuses almost every real dataset** under the per cell mask. Replaced the fractional 0.15 floor with an absolute gene count, calibrated by NB1b's accuracy-vs-observed-genes curve to `MIN_OBSERVED_GENES = 200` (chance-level below 100, stable from ~200; 100-300 thinly sampled, marked "calibrated on simulations, revisit"). Owner: A2, using NB1b's evidence.
- [ ] **Smoothing costs 10 points of balanced accuracy on natural compositions** (75.7 to 65.6 on RNA) while helping narrow uploads by 4 to 6 points. Keep it only where it is measured to help. Owner: NB1b ablation.
- [ ] **Non-myeloid uploads can only ever be labelled macrophage or monocyte, or abstain.** `CROSS_MODAL_SUPPORTED_CLASSES` is hardcoded to the two classes with real cross-modal support; a T cell or NK cell upload has no possible correct label under the current restricted assignment, regardless of how good its embedding is (confirmed: unrestricted 22-class scoring on real PBMC240 gets 46.6% lymphoid recall on the same embeddings that score 0% restricted). This is a correctness limitation, not only an accuracy one. Owner: T1 NB2 (label space estimation).

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
- [x] ~~Weak-lineage accuracy... Stage 6's out-of-distribution threshold essentially never fires...~~ **Correction below — this explanation was wrong.**

**A2 close-out (from T1 NB1b):**

- [x] Coverage floor calibrated: `MIN_OBSERVED_GENES` 100 -> **200** (`config.py`). NB1b's accuracy-vs-observed-genes curve shows chance-level accuracy below 100 genes, stable from about 200 — evidence-backed now, not a placeholder, though 100-300 is thinly sampled so it's marked "calibrated on simulations, revisit" in `canonical_preprocessing.json`, not fully closed. No golden-fixture regression (none of the 100 frozen cells sit in the 100-199 range).
- [x] Mask convention **settled**: per-cell beat dataset-level median fill by 3.2 points unrestricted and 4.7 points oracle-restricted in NB1b's 2x2 ablation; skipping log2 cost about 3 points (independent confirmation of the log-transform fix above). Recorded as settled in `canonical_preprocessing.json` — no further ablation needed, no code change (per-cell was already the service's behavior).
- [x] **Corrected the PBMC240 lineage explanation.** The 0% lymphoid recall reported in the review round above was NOT caused by the OOD-abstention threshold failing to fire — it was mechanically forced by `config.CROSS_MODAL_SUPPORTED_CLASSES = ("macrophage", "monocyte")`: Stage 4's restricted candidate space cannot output a lymphoid label under any circumstance, abstention or not. Rescored all three variants **unrestricted** (22-class nearest-centroid, predicted class mapped to lineage), scores only:
  - (a) fixed service, raw PBMC240: 50.0% overall, 87.5% myeloid recall, **46.6% lymphoid recall**
  - (b) processed comparison file: 38.9% overall, 81.2% myeloid recall, 35.1% lymphoid recall
  - (c) fixed service + per-cell median norm, no imputation: 26.8% overall, 81.2% myeloid recall, 21.8% lymphoid recall
  - Abstention rates all ~0-0.4% (min_observed_genes=200). Unrestricted, the model clearly *can* recognize lymphoid identity for a real fraction of T/NK cells (mostly correctly as cd8+/cd4+ T cell, NK cell, regulatory T cell) — it just structurally never gets the chance to say so under the current restricted default. The largest confusion is T/NK cells predicted as "neutrophil" (54/174 for variant a).
  - Notable, unexpected, and *not* used to change anything: **(a) the untouched fixed service outperforms both (b) the heavily-preprocessed comparison file and (c) the per-cell-normalization variant** on this one real, limited comparison. This is a single real-data spot check, not NB1b's controlled simulation — it should inform, not decide, the per-cell-normalization question below.
  - **Known limitation, recorded plainly:** until T1 NB2 (label space estimation) lands, the live service labels every non-myeloid upload as macrophage or monocyte (or abstains) — it has no way to say "T cell" or "NK cell" even when the embedding clearly supports it. This is a real, current correctness limitation, not just an accuracy one.

### Track B, deployment hardening (branch `hardening/b`)

- [x] `gene_ids.py` plus the frozen `gene_id_map_v1.tsv` (`cf3b98e`)
- [x] Accept symbols, Ensembl IDs, UniProt groups and DIA-NN reports (`cf3b98e`)
- [x] Orientation detection, rejecting ambiguous input (`cf3b98e`)
- [x] Minimum cell count and value scale detection (the detection feeds A2's log transform) (`cf3b98e`)
- [x] TorchScript or ONNX export with an equivalence test (`3c7da75`)
- [x] FAISS search with an exact equivalence test (`3c7da75`)
- [x] `MODEL_CARD.md` and `versions.html` content, using the corrected test cell numbers below (`f09c3be`)
- [x] Per upload logging (`f09c3be`)

**Track B follow-up round:**

- [x] Real DIA-NN upload support: TSV auto-detection, annotation-column handling (a "Genes" column becomes the identifier, DIA-NN's other annotation columns are excluded, Windows raw-file-path headers are cleaned to their basename without `.raw`). Verified end to end through `app.py` against the actual `PBMC_240cells_proteins.tsv` (`service/examples/pbmc240_proteins_raw.tsv`): 237/238 cells pass the 200-gene floor (observed_genes min=0, median=1040, max=2254). Integration test added (`b5a15a8`)
- [x] OpenMP workaround scoped to `sys.platform == "darwin"` only — the faiss-cpu/torch duplicate-libomp collision is a macOS packaging issue specifically; documented that a Linux deployment must not set these, since forcing FAISS to a single thread there would just throttle every search for no reason it has (`9109ce2`)
- [x] UniProt isoform accessions (e.g. `P12345-2`) now resolve to their base accession (`9109ce2`)
- [x] `MODEL_CARD.md` / `versions.html` corrected: **all nine donors** (not only TSP14/21/25, which was a naming example, not the full list) had about 65% of their cells in training; the restricted 79.8% balanced accuracy is **exact for SCoPE2 by construction** (its protein cells are only ever macrophage or monocyte, so restricting to those two classes matches the true label set on this one dataset — not a generalizable result); added the SCoPE2-unrestricted seed-variance caveat (a faithful retrain scored 9.1% balanced accuracy against the 31.1% shipped, seed variance measurement pending T1 NB1c); every number now cites its committed source file directly (`docs/plans/nb1/rna_to_rna_membership_corrected.csv`, `service/model/v3_tables/support_restricted_assignment.csv`) instead of pointing generically at this file's own summary table (`d5b426a`)

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
  - [x] Training membership: all nine donors contributed about 65 percent of their cells to training. No donor level holdout exists for v3
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
| Mask convention | NB1b ablation, then A2 | **Settled:** per cell, +3.2 points unrestricted / +4.7 oracle-restricted vs. dataset-level median fill (NB1b's 2x2 ablation). No code change needed — per cell was already the service's behavior |
| Smoothing graph input | A2 | **Settled and implemented (`2334e48`):** z-scored, filled. Raw with zeros is unsafe on protein intensities |
| Log transform of linear scale input | A2 with B | **Settled and implemented (`2334e48`):** yes, when linear scale is detected. NB1b independently confirms: skipping it costs about 3 points |
| Coverage floor definition | NB1b curve, then A2 | **Calibrated:** `MIN_OBSERVED_GENES = 200` (chance below 100, stable from ~200; 100-300 thinly sampled — "calibrated on simulations, revisit", not fully closed) |
| Per-cell loading normalization (subtract each cell's own median after log2, e.g. to correct for loading/depth differences between cells) | NB1b, then A2 | Open. Not in the service. Unrestricted (22-class) real-data rescoring on PBMC240 found the untouched fixed service (46.6% lymphoid recall) actually *beats* the per-cell-normalization variant (21.8%) and the heavily-preprocessed comparison file (35.1%) — a real result, but one real dataset's spot check, not NB1b's controlled simulation. Decide from NB1b's ablation, not this |
| Keep smoothing on by default | NB1b | Open. It hurts natural compositions by 10 points |
| Were TSP14, TSP21, TSP25 in production training | NB1 | **Settled: yes, about 65 percent of their cells — and so was every other donor (all nine), see §3 above, not only these three** |
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
| 2026-09-25 | A2 review: PBMC240 divergence explained — the comparison file uses a deliberately different recipe (5% detection filter, log2(x+1), per-cell median normalization, ~52.6% values imputed from Normal(1st pct, 0.3)), not a service bug. Reproducing that exact recipe as a diagnostic gets median cosine 0.9969 to the real file. Cell alignment re-confirmed correct (237/237 matched by cleaned ID). 3-way *restricted* weak-lineage accuracy (service / processed file / service+per-cell-norm-no-imputation) came out identical across all three (8.4% overall, 100% myeloid recall, 0% lymphoid recall) — initially misattributed to the OOD-abstention threshold; see the next entry for the correction. Added "per-cell loading normalization" as an open decision for NB1b. No service code changed this round | diagnostics only, not committed to `service/` |
| 2026-09-25 | A2 close-out from T1 NB1b: `MIN_OBSERVED_GENES` calibrated 100 -> 200 (chance below 100, stable from ~200 in NB1b's curve); mask convention settled (per cell beats median fill by 3.2/4.7 points); log transform's value independently confirmed (~3 points). Corrected the lineage explanation: 0% lymphoid recall was forced by the hardcoded `CROSS_MODAL_SUPPORTED_CLASSES` restriction, not the OOD threshold — unrestricted (22-class) rescoring gets 46.6%/35.1%/21.8% lymphoid recall for the three variants respectively, with the untouched fixed service unexpectedly *beating* both alternatives. Recorded as a known correctness limitation (not just accuracy) until T1 NB2 lands | `config.py` (`MIN_OBSERVED_GENES=200`), `canonical_preprocessing.json` |
| 2026-09-25 | Track B complete: `gene_ids.py` + frozen `gene_id_map_v1.tsv` (HGNC bulk download, sha256'd) resolving symbols/Ensembl/UniProt/DIA-NN groups; upload orientation and minimum-cell-count validation; `topk.py`'s kNN and a new `search.py`'s max-cosine both moved to FAISS `IndexFlatIP` (exact, not approximate) with equivalence tests against the original numpy code; the encoder now serves through a TorchScript trace, equivalent to the eager model to <1e-5 max abs diff on 1,000 cells; `MODEL_CARD.md` and a matching `versions.html` section state the RNA-supervised/zero-shot-proteomics claim, the corrected SCoPE2-mask test-cells-only numbers (93.2/65.7, not the invalid published 95.5/74.8), and the four known failure modes; per-upload logging (input hash, coverage, observed genes, value scale, supported classes, abstention rate by reason, model/mapping versions). `abstention.py`, `assignment.py`, `calibration.py`, `smoothing.py` untouched, per the track's forbidden-files list. Golden fixtures from A2 pass unchanged; 131 backend tests pass | `cf3b98e`, `3c7da75`, `f09c3be` |
| 2026-09-25 | Track B follow-up: real DIA-NN TSV upload support (Genes-column identifiers, annotation columns excluded, Windows raw-file-path headers cleaned) verified end to end against the actual PBMC_240cells_proteins.tsv (237/238 cells pass the 200-gene floor); OpenMP workaround scoped to macOS only, documented that Linux must not set it; UniProt isoform accessions resolve to their base accession; `MODEL_CARD.md`/`versions.html` corrected — all nine donors (not three) had ~65% of cells in training, the restricted 79.8% is exact for SCoPE2 by construction and not a general result, added the SCoPE2-unrestricted seed-variance caveat (9.1% on a faithful retrain vs. 31.1% shipped, T1 NB1c pending), and every number now cites its committed source file directly. 136 backend tests pass | `b5a15a8`, `9109ce2`, `d5b426a` |
