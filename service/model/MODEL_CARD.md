# VivOME model card

The service runs **v4.2** by default, release 0.5.0. It is v4.1 with
protein class means in its best guess, for protein uploads. **v4.1**
(release 0.4.0), **v3.1** (release 0.3.0) and **v3** (release 0.2.0) stay
selectable (`VIVOME_PIPELINE_VERSION=v4.1`, `v3.1` or `v3`) and are
described after it. All are trained on RNA only and applied zero-shot to
protein; no protein labels are used.

## v4.2: v4.1 with protein class means

### What it is

- **Everything is v4.1's** (below) except one input to the best guess, for
  protein uploads (`modality` `"prot"`): each cell's correlation r is taken
  with protein class means instead of the reference's RNA class means, for
  the 16 reference classes those means cover. The other classes, macrophage
  among them, keep their RNA class means.
- **The protein class means** come from sorted immune cell populations:
  Rieckmann et al. 2017, *Nature Immunology* 18:583, PRIDE PXD004352,
  steady-state LFQ intensities, mean log2 over donors per population, each
  population mapped to a reference class
  (`research/notebooks/rieckmann_feasibility.py`). They cover 15,314
  proteins. PRIDE's terms ask for attribution and add no other restriction.
- **On the upload's side,** each protein row is matched by its first listed
  gene symbol, rows of one gene are merged by per-cell median, and each gene
  is z-scored over its observed values within the upload.
- **An RNA upload is answered exactly as by v4.1**
  (`service/tests/test_v42.py`, `test_an_rna_upload_answers_exactly_as_v41`).
- **Nothing was tuned for it:** v4.1's weight, temperature and agreement
  threshold, unchanged.
- **Each answer's set holds the best guess,** so a protein cell's answer
  can change with its guess.

Spec: `service/model/v4_2/spec_v42.json` (`scripts/build_v42_spec.py`), with
its data file `protein_class_means.npz`, on v4.1's spec. Record:
`research/notebook-run-history.md`, entries 36, 44 and 45;
`research/notebook-outputs/v42_release/summary.json`.

### Evidence

- **The internal held-out test** (entry 44): on protein, its primaries equal
  v4.1's on every set (PXD043355 pass; PXD073250 and PXD046211 fail; Tian
  and PXD021882 void). On RNA it takes v4.1's path, so Hao 2021's result is
  v4.1's pass. That routing was fixed after the test was scored: as scored,
  v4.2 ran its protein term on RNA and lost there (+1.88, lower bound
  -0.95), a path an RNA upload should never take.
- **Fulcher 2026, six types** (development data; it also chose v4.1's
  weight, so these figures are in-sample): best guess 75.8% balanced
  accuracy against v4.1's 69.0% (+6.7; 95% CI 4.4 to 9.2, stratified paired
  bootstrap, `research/benchmark/v42_development/`). Recall: CD4 T 83.1%,
  CD8 T 23.2%, NK 92.0%, B 98.0%, monocyte 95.4%, DC 63.0% (v4.1: 82.5,
  23.8, 90.0, 98.0, 97.8 and 22.2). 87.3% of cells committed, 98.3% of
  those correct at the stated level (v4.1: 87.0% and 97.9%).
- **PBMC240, both SCoPE2 versions and Furtwängler 2025:** not one best
  guess differs from v4.1's (the correlation term is flat there).
- **The simulated suite** is v4.1's, since RNA uploads are answered as by
  v4.1.
- **Khoury 2026 is not scored for v4.2:** each use of it needs the owner's
  decision. v4.1's post-hoc figures are below.

### Known limits

v4.1's known limits apply (below), with two changes:
1. **Dendritic cells** improve on Fulcher (63.0% recall, from 22.2%), on
   development data. On held-out RNA (Hao 2021) they stay at v4.1's 10.4%.
2. **The protein class means come from one study,** of sorted cells from
   healthy donors measured with one instrument. Where an upload's protein
   profiles differ from those populations, the correlation term can mislead,
   and the agreement gate is the only guard.

## v4.1: v3.1's answers, a fused best guess

### What it is

- **The answers are v3.1's** (below): its five members, conformal sets,
  out-of-distribution threshold, hierarchy, coordinates and properties.
- **The best guess is fused** (`service/pipeline/fusion.py`):
  best guess probability = w × encoder + (1 − w) × softmax(r / 0.05).
  - The encoder term is the mean over v3.1's members of softmax(cosine to
    class-balanced centroids / T), half from the smoothed query and half
    from the unsmoothed one.
  - r is each cell's Pearson correlation, over the genes it measured, with
    the reference's class means, z-scored class-balanced.
- **The correlation term is used only where it carries signal.** When at
  least 40% of an upload's cells have the same top class under r as under
  v3.1, w is 0.5. Otherwise the term is flat, w is 0.7, and the guess is the
  encoder's. An upload of one cell type usually falls below 40%: per-upload
  z-scoring removes the contrast r needs.
- **The fused guess joins every non-empty set** beside v3.1's own guess, so
  v4.1's sets contain v3.1's.
- **How each setting was chosen:**
  - the 0.7 weight and the correlation temperature on NB1's calibration
    suite (v4);
  - the smoothed share and the 40% threshold on NB3c's calibration cells
    and the development data;
  - the 0.5 weight on Fulcher 2026, under rules fixed beforehand
    (`research/notebooks/v41_pretest.py`), with the temperature confirmed
    there at 0.05; then checked once on Khoury 2026.

Spec: `service/model/v4_1/spec_v41.json`, on v4's
`service/model/v4/spec_v4.json` and data files. Record:
`research/notebook-run-history.md`, entries 20 to 26.

### Evaluation suite (simulated uploads)

240 fresh simulated RNA uploads from `te_eval` cells, scored once
(`research/notebook-outputs/v41_phase3/summary.json`). It was that suite's
fourth use, so it is a safety check, not a fresh test. All eight
pre-registered checks passed.

| Measure | v4.1 | v3.1 |
|---|---|---|
| Best guess, balanced accuracy per upload | **64.97%** | 60.57% |
| Committed | 85.83% | 86.90% |
| Correct when committed, at the stated level | 96.28% | 95.98% |
| Conformal coverage (target 90%) | 87.21% | 86.69% |
| False abstention | 0.48% | 0.48% |

### Development data, as served

`research/benchmark/v41_development/` (`benchmark/baselines_v4_score.py
--version v4.1`). Fulcher 2026 chose v4.1's weight, so its Fulcher
figures are in-sample.

- **Fulcher 2026, six types:** best guess 69.05% balanced accuracy against
  v3.1's 57.9% (+11.1, CI 8.5 to 14.0). Recall: CD4 T 82.5%, CD8 T 23.8%,
  NK 90.0%, B 98.0%, monocyte 97.8%, DC 22.2%. 87.0% of cells committed,
  97.9% of those correct at the stated level (v3.1: 89.2% and 97.3%).
- **PBMC240 and both SCoPE2 versions:** the correlation term is flat there,
  so v4.1 answers exactly as v4. PBMC240 lymphoid recall stays 92.3%.
  SCoPE2 restricted to macrophage or monocyte is 38.0% balanced accuracy,
  below chance (50%), as for v3.1.

### Khoury 2026, post-hoc

Khoury's labels were read at its one scoring (2026-10-03), before v4.1
existed, and nothing was chosen on it afterwards
(`research/benchmark/khoury2026_posthoc_v41_check/`).

- **Best guess:** 62.5% balanced accuracy over five types, against v3.1's
  56.9% (+5.6, CI 4.0 to 7.1).
- **Recall:** CD4 T 82.8%, CD8 T 2.7%, NK 50.7%, B 81.7%, monocyte 94.7%.
- **Against the corrected baselines:** level with PCA and kNN (62.8%; −0.3,
  CI −2.1 to 1.4) and with scANVI and kNN on two of three seeds; ahead of
  every other run, each CI above zero
  (`research/benchmark/results.md`, "v4.1 against the corrected baselines").

### The internal held-out test

Six sets were set aside before Goal 2's development and scored once, each
under a protocol committed before its files were opened
(`research/benchmark/protocol-heldout.md`, `protocol-heldout-hao2021.md`;
results in `research/benchmark/heldout/`). It is an internal test, not
external validation.
- **Hao 2021's held-out donors** (RNA made protein-like, another atlas):
  - coarse balanced accuracy 62.2%, 4.73 points above the correlation
    baseline (one-sided 95% lower bound +2.82): pass;
  - B cells 98.6%, monocytes 83.4%, dendritic cells 10.4%.
- **Jurkat over HeLa** (PXD043355): reference similarity AUROC 0.674 (p
  0.015), a pass. A third of the HeLa cells still get a committed answer.
- **Immune cells over keratinocytes** (PXD073250): AUROC 0.442, a fail.
- **PMA-treated over untreated monocyte lines** (PXD046211): 0.517, a fail,
  as predicted.
- **Tian and PXD021882** were void: their deposits hold no matched CD4/CD8
  pairs and no B or T pools.

### Known limits

1. **CD8 T cells.** Recall is 2.7% on Khoury and 23.8% on Fulcher, and every
   method fails them. Khoury's CD8 and CD4 clusters largely separate naive
   from memory T cells, and the reference files naive CD8 T cells under
   CD4 T (`research/notebooks/cd8_cd4_diagnosis.py`). Fulcher measures
   neither CD8A, CD8B nor CD4.
2. **Dendritic cells.** Recall is 22.2% on Fulcher (v3.1: 5.6%). The
   reference has 1 myeloid dendritic cell and 29 plasmacytoid ones.
3. **SCoPE2's macrophages and monocytes** are not separated. v4.1 is below
   chance there, and on the reprocessed matrix every method is at or below
   chance.
4. **No external test yet.** Fulcher chose v4.1's weight, Khoury is
   post-hoc, and the internal held-out test (above) used data set aside by
   us, not by an independent group. Its one test of CD4 against CD8 was
   void, so that question waits for the sorted cells
   (`research/benchmark/protocol-sorted-cd4cd8.md`).
5. **Uploads of one cell type.** Every gene is z-scored within its upload,
   so an upload of a single sorted population loses the contrast the model
   needs. On Fulcher, each type uploaded alone: answers correct when
   committed fall from 93-100% (mixed) to 6-73% (B cells 6%, monocytes 37%,
   NK 44%), and CD4 T with CD8 T together collapses too
   (`research/notebook-outputs/single_type_uploads/summary.json`). Upload
   mixed cells, never one sorted population alone.
6. **The guess's probability.** Its out-of-reference AUROC is 0.790, against
   v4's 0.829 and v3.1's 0.744. Out-of-distribution abstention is v3.1's,
   unchanged. On PXD077946's cell lines (development data) its threshold
   flags none of the HEK293T, HCT116 or K562 cells; most abstain as
   ambiguous, but some get a committed blood-cell answer
   (`research/notebook-run-history.md`, entry 41).
7. **v3.1's known limits apply to the answers** (below).

## v3.1: the T1 NB2 ensemble

### What it is

- **Encoders.** Five V2 encoders from T1 NB1b
  (`service/model/v3_1/members/V2_batchgene_aug_seed{0..4}.pt`). They have
  v3's architecture and input shape, trained on mini uploads with
  per-upload gene z-scoring.
- **Ensemble probability.** Each member scores softmax(cosine to its class
  centroids / T). T is fitted per member: 0.141 for seed 0, 0.153 for the
  others. The ensemble probability is the mean of the five.
- **Conformal sets.** Mondrian, at α = 0.1, with one qhat per class. There
  is no per-upload label space estimate.
- **Out of distribution.** The mean over members of the max cosine to any
  reference cell, below 0.779 (the 1st percentile of in-distribution
  simulated cells).
- **Answers** come at the level the set supports: one class, the group the
  set's classes share, the lineage they share, or abstain. Every cell not
  refused for coverage also gets a best guess.
- **Two service flags, on by default** (`ensemble.SERVICE_FLAGS`; NB2's
  spec has neither):
  - every non-empty set also contains the best guess, so a one-class answer
    is always the best guess (an empty set still abstains);
  - a restricted request renormalises probabilities over the allowed
    classes before its sets are built.

  NB3b measured both on RNA (Known limits, 7).

Spec: `service/model/v3_1/nb2_spec_v31.json`. Code:
`service/pipeline/ensemble.py`. Response:
`docs/service/projection-api.md`, v3.1.

### Evaluation suite

The suite is T1 NB1's 240 simulated RNA uploads from test-split cells,
masked like real mass-spectrometry data. The v3.1 column is NB2's rule,
without the two service flags. "v3 as served" is NB2's replica of the v3
service: Stages 4 to 6, without the Stage 7 fallback. Source:
`research/notebook-outputs/nb2/nb2_summary.json` and
`research/notebook-outputs/nb2/tables/eval_summary.csv`.

| Measure | v3.1 | v3 as served (seed 0) |
|---|---|---|
| Correct when committed, at the stated level | **94.9%** | 35.0% |
| Abstention | **19.2%** | 45.5% |
| Conformal coverage (target 90%) | 87.1% | not measured |
| Committed at class level | 19.1% | 54.5% |
| Committed at group level | 17.7% | 0% |
| Committed at lineage level | 44.0% | 0% |
| Mean set size | 2.8 | 1.35 |
| Strict fine balanced accuracy (only a correct single class counts) | 17.5% | 23.2% |
| Best guess balanced accuracy | 56.1% | not reported |

**Most answers are group or lineage answers.** v3.1 trades fine labels for
answers that hold: 61.7% of cells get a group or lineage label, and 19.1%
get one class.

Under NB2's missing-not-at-random masking, v3.1 scores:
- 93.8% correct when committed;
- 22.4% abstention;
- 85.0% coverage.

### Development data

- **The gate.** NB2 scored SCoPE2 and PBMC240 with its own parse.
  `benchmark/v31_dev_gate.py` runs the served pipeline on the same parse,
  under NB2's rule (service flags off). Every share in
  `research/notebook-outputs/nb2/tables/dev_datasets.csv` matches to two
  decimals: committed, class level, and each abstention reason.
  - PBMC240's composition matches entry for entry.
  - SCoPE2's composition differs by one cell.
  - The record is `research/benchmark/v31_dev_gate.json`. The gate's
    tolerance is 0.5 point, and it also runs as
    `service/tests/test_v31_gate.py`.
- **SCoPE2.** 1,490 cells, all macrophage or monocyte.
  - **Under NB2's rule:**
    - 72.6% of cells are committed.
    - 39.5% of committed answers are correct at the stated level, all of them "myeloid" lineage answers.
    - None of its 152 class answers or 397 group answers is correct.
    - "T cell" alone is 462 cells, 31.0%.
  - **As served (flags on):**
    - 53.0% of cells are committed.
    - 58.9% of committed answers are correct, still all "myeloid".
  - Source: `research/benchmark/v31_service_flags.json`.
- **PBMC240.** 238 cells, 122 of them with weak lineage labels (117
  lymphoid, 5 myeloid).
  - Under NB2's rule: 73.95% committed, 2.1% of cells at class level through
    the service (1.7% under NB2's parse).
  - 79.5% of lymphoid cells (93 of 117) and 3 of 5 myeloid cells get their
    lineage. The myeloid figure is anecdotal.
  - As served: 73.1% committed; 92 of 117 lymphoid cells.

Through the service, PBMC240 first differed from NB2 by 1.3 points of
committed cells (72.7 against 73.9). The cause was a service bug: when several
upload rows mapped to the same gene, only the last row was kept. With
duplicates collapsed by per cell median, as NB2 does, the service reproduces
NB2's committed, out of distribution and ambiguous figures exactly; two
composition entries differ by up to 0.8 point.

**Fulcher 2026** has been development data since 2026-09-30. Its numbers
below come from 1,275 cells through the service parser with default settings
(both flags on). 1,251 of them are scored against the authors' six types
(`research/benchmark/fulcher2026/v31_development.json`):
- **Committed:** 89.2% of cells. 97.3% of committed answers are correct at the
  stated level.
- **Mostly group or lineage answers.**
  - CD4T and CD8T are mostly answered at group level ("T cell").
  - NK and monocyte are almost all answered at lineage level.
  - B is mostly answered at class level.
- **DC** is committed on only 51.9% of cells.
- **Best guess:** 57.9% balanced accuracy over the six types. Single V2
  seeds under nearest centroid score 57.3 ± 2.2.

### Final evaluation: Khoury 2026

Khoury 2026 is the sealed final test: timsTOF single-cell proteomics with
mTRAQ 2-plex, 1,651 PBMCs from two donors, five types, chance 20%. Nothing
in this model was chosen with it. It was scored once, on 2026-10-03, under
`research/benchmark/protocol-khoury2026.md`. v3.1 ran as served, release
0.3.0, both flags on (`research/benchmark/khoury2026/`):

- **Best guess:** 56.9% balanced accuracy over the five types. Each V2
  member alone, under the shared kNN rule, scores 60.0 ± 3.3.
- **Against the corrected baselines (post-hoc), v3.1 is level with the
  best, not ahead.** As first run, v3.1 led every comparator in every
  paired bootstrap, but a review then found the baselines and scANVI
  handicapped by our setup (a scaling mismatch, MaxFuse misconfigured,
  scANVI's likelihood unable to fit its inputs). Rerun with fixes committed
  in advance (`research/benchmark/baseline-corrections.md`), PCA with kNN
  scores 62.8 and scANVI 61.5 on Khoury, against v3.1's 56.9 (its members
  alone, 60.0); Harmony is level at 56.9; the correlation baseline (49.8),
  scGLUE (38.9), MaxFuse (31.6) and Seurat CCA (29.7) stay behind. On
  Fulcher, Harmony and the correlation baseline (61–63) are ahead of v3.1.
  The first-run comparators, kept for the record:
  - v3 as served: 40.9% (+16.0);
  - scANVI's best arm: 30.9% native, 36.1% shared kNN (+24 to +26);
  - scGLUE 42.8%, correlation to the class mean 38.7%, Seurat CCA 30.4%,
    Harmony 27.6%, MaxFuse 0.8%.
- **Committed:** 93.8% of cells. 96.7% of committed answers are correct at
  the stated level. They are mostly group answers ("T cell") for T cells,
  lineage answers for NK and monocyte cells, and class answers for B cells.
- **Lineage recall** of the best guess: lymphoid 98.1%, myeloid 97.2%.
- **CD8T and NK are not separated.** The best guess calls 94% of CD8T
  cells CD4T (CD8T recall 2.7%) and half of NK cells CD8T (NK recall
  29.0%).

Three caveats go with these numbers. The labels are the authors' clusters
of the same protein matrix, not independent ground truth. The matrix
arrived already ComBat-corrected. And it is a different technology from
every other dataset here.

### Known limits

1. **The out-of-distribution filter passes 99% of scrambled cells.** In
   NB2's negative control it rejects 0.96% of gene-shuffled cells and 5.5%
   of real ones (AUC 0.845; `research/notebook-outputs/nb2/tables/ood_negative_control.csv`).
   The max-cosine score barely separates a scrambled profile from a real
   one. A better score is an open problem.
2. **B cell coverage is 69%,** against the 90% target, and 64% under
   missing-not-at-random masking. It is the lowest class. The others range
   from 84% to 96% under standard masking (`eval_per_class_coverage.csv`)
   and from 76% to 95% under missing-not-at-random masking, where
   erythrocyte is next lowest (`eval_mnar_per_class_coverage.csv`).
3. **SCoPE2 still fails.** See Development data above: under either rule no
   class or group answer is right, and the best guess is right for 0.0%
   balanced (`research/benchmark/v31_service_flags.json`). In
   v3.1's coordinate member's latent space, the SCoPE2 macrophage and
   monocyte centroids sit far from their RNA classes: latent centroid cosine
   0.14 and 0.25, against v3's 0.37 and 0.14
   (`service/model/evidence/v3_1_tables/latent_centroid_cosine.csv`, by the
   same method as v3's). RNA and protein are also more separable there:
   the modality probe reads 99.93%, against v3's 98.99%
   (`service/model/evidence/v3_1_tables/modality_probe.json`).
4. **Coverage is guaranteed on RNA simulations only.** On protein it is
   approximate, which is why `calibration.applies_to` says so in every
   response.
5. **The threshold was fitted with training-split references; the service
   uses every reference cell.** That raises max cosine slightly, so the
   service abstains as out of distribution a little less often than NB2
   measured (the spec's `caveats`).
6. **The calibration suite comes from the validation split,** which also
   set the encoders' early stopping.
7. **The two service flags were measured on RNA after NB2** (NB3b,
   `research/notebook-run-history.md`, entry 18;
   `research/notebook-outputs/nb3b/eval_flags_summary.csv` and
   `eval_restricted_summary.csv`), so the evaluation-suite figures above are
   NB2's rule without them.
   - `set_includes_best_guess` raises coverage from 87.1% to 88.3% (target
     90%) and correct when committed from 94.9% to 95.5%.
   - Restricted mode, renormalised, on macrophage and monocyte uploads:
     99.5% of cells committed, 96.2% of those correct, but class answers fall
     from 56.7% to 28.6%, because the two allowed classes share a group.
8. **Restricted mode was not evaluated under v3.1.**
   - On SCoPE2 with the flags on, every cell commits.
   - But 97.9% of answers are "monocyte/macrophage", the group made of
     exactly the two allowed classes, and none of its 32 class answers is
     right.
   - It is not recommended under v3.1.
9. **T cell and NK subsets on real protein data.** On Khoury 2026, the best
   guess calls 94% of CD8T cells CD4T and half of NK cells CD8T. On Fulcher,
   V2 called 63% of CD8T cells CD4T. The committed answers stay right
   because they stop at "T cell" or "lymphoid". CD8T fails for the
   corrected baselines on Khoury too (PCA 0.9%, scANVI 14.2%), but they
   find NK better (PCA 52.8%, scANVI 47.5%, against 29.0%).

## v3 reference

### The claim, precisely

The reference encoder (`ModulePoolingEncoder`, `reference_model.pt`) is
**trained, supervised, on RNA only** — 85,233 cells across 22 immune/blood
cell classes (`reference_metadata.csv`). It is applied **zero-shot to
proteomics uploads**: no protein labels and no paired RNA-protein cells were
used at any point in training or in choosing the architecture. Every number
below cites the committed file that measured it —
`research/todo.md` §5 ("Current verified numbers") is the running
index of those files, not a source in its own right.

### Architecture

- Module-pooling encoder: a fixed gene→module assignment (`A`, row-normalised),
  concatenated masked values + mask + module-level value + module-level mask
  fraction, two LayerNorm/GELU/Dropout blocks, a linear projection to a
  128-dim latent space, L2-normalised. See `service/pipeline/encoder.py`.
- 9,002-gene feature space (`feature_space_provenance.json`): the union of
  six proteomics datasets' detected genes, replacing an earlier 2,903-gene
  space entirely.
- Winning config from a 5-seed architecture comparison (`decisive_summary.json`):
  "H module, uniform" (module-pooling encoder, uniform mask sampling,
  consistency loss on). Mean balanced accuracy 71.43%, 95% CI
  [68.51%, 74.35%] across the 5 seeds (`provenance.json:reference_seed_mean_bal_acc`).
- Served via TorchScript (`encoder.trace_encoder`), not the eager module —
  proven numerically identical to <1e-5 max absolute difference on 1,000
  cells (`service/tests/test_encoder.py`).

### Performance

| Measure | Value | Source |
|---|---|---|
| RNA→RNA, SCoPE2 mask, **test cells only** | 93.2% acc / 65.7% bal (OT); 67.3% bal (nearest-centroid) | `research/notebook-outputs/nb1/rna_to_rna_membership_corrected.csv` |
| RNA→RNA, full coverage, **test cells only** | 94.6% acc / 80.0% bal (OT) | `research/notebook-outputs/nb1/rna_to_rna_membership_corrected.csv` |
| Protein (SCoPE2, 1,490 real cells), **restricted** to the two supported classes (chance 50%), **shipped checkpoint (`v3_seed0`)**, nearest centroid (the service's rule) | 13.8% acc / 20.2% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **restricted, 5-seed mean of the shipped architecture**, nearest centroid | 20.6% ± 4.7 acc / 36.7% ± 10.8 bal (range 20.2–49.2 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein (SCoPE2), **restricted, shipped checkpoint (`v3_seed0`)**, shared kNN (the benchmark's rule) | 15.0% acc / 11.6% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **restricted, 5-seed mean of the shipped architecture**, shared kNN | 24.7% ± 11.8 acc / 28.5% ± 10.6 bal (range 11.6–41.0 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein (SCoPE2), **unrestricted** across all 22 classes, **shipped checkpoint (`v3_seed0`)**, nearest centroid | 0.4% acc / 0.7% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **unrestricted, 5-seed mean of the shipped architecture**, nearest centroid | 3.1% ± 4.2 acc / 5.4% ± 7.6 bal (range 0.0–17.9 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein (SCoPE2), **unrestricted, shipped checkpoint (`v3_seed0`)**, shared kNN | 2.3% acc / 2.2% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **unrestricted, 5-seed mean of the shipped architecture**, shared kNN | 4.9% ± 5.5 acc / 8.3% ± 9.9 bal (range 0.0–20.4 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein, **Fulcher 2026** (held-out scoring; TMT PBMCs, 1,251 cells, 6 types, chance 16.7%), unrestricted, **shipped checkpoint (`v3_seed0`)** | 44.1% bal (nearest centroid) / 41.8% (shared kNN) | `research/benchmark/fulcher2026/per_seed_scores.csv` |
| Protein, Fulcher 2026, **5-seed mean of the shipped architecture** | 42.3% ± 3.4 / 42.0% ± 2.9 bal | `research/benchmark/fulcher2026/family_summary.csv` |
| Protein, **Khoury 2026** (the sealed final test, scored once; timsTOF mTRAQ PBMCs, 1,651 cells, 5 types, chance 20%), unrestricted, **v3 as served (`v3_seed0`)** | 40.9% bal (nearest centroid) / 39.8% (shared kNN) | `research/benchmark/khoury2026/per_seed_scores.csv` |
| Modality probe (RNA vs. protein separability in latent space) | 98.99% ± 0.28% | `service/model/evidence/v3_tables/modality_probe.json` |

**A previously published RNA→RNA figure of 95.5% / 74.8% (SCoPE2 mask) is
superseded by the 93.2% / 65.7% figures above.** The published number
included cells the model had trained on in its own test split — an invalid
measurement. The corrected numbers here score test cells only.

**On SCoPE2's two classes, every v3 seed is at or below chance.** The
labels are the authors' curated ones; VivOME's copy had them swapped
until 2026-10-04 (`research/benchmark/bugs-and-fixes.md`, 8), and the
"79.8% restricted balanced accuracy" published before then was 100 minus
the true 20.2%. `v3_seed0`, the checkpoint shipped, is the worst of the
five seeds: 20.2% against a 5-seed mean of 36.7% ± 10.8 under nearest
centroid, and 11.6% against 28.5% ± 10.6 under shared kNN. v3 separates
the two U-937 states well (macrophage-vs-monocyte AUROC 0.072, so 0.928
ranked the other way round) but places the PMA-differentiated macrophages
nearest the RNA monocytes. Restricting Stage 4's candidates to the two
classes (`config.CROSS_MODAL_SUPPORTED_CLASSES`) is, on this one dataset,
restricting to the true label set, and on any upload with other cell types
(PBMC240's T and NK cells) it is wrong; that is why it is opt-in, see
failure mode 1 below.

**Against scArches/scANVI on SCoPE2 (Track D's runs), both are below
chance on the two classes, so the comparison ranks two failures.** Under
the shared kNN rule, restricted, v3's 5-seed mean (28.5% bal) is ahead of
scANVI's 3-seed mean (22.8%): 12 of 15 seed pairings favour v3 (mean +5.7
points), 3 favour scANVI. `v3_seed0`, the shipped checkpoint, is behind
every scANVI seed there (−10.4 to −12.1 points) and under pool-first kNN.
Across all 22 classes, 12 of 15 pairings favour v3 (mean +8.1 points), all
under 21% balanced accuracy. Full breakdown:
`research/notebook-outputs/nb1d/paired_bootstrap_ours_vs_scanvi.csv`. These
replace a comparison scored against swapped labels
(`research/benchmark/bugs-and-fixes.md`, 8).

**On Fulcher 2026, the held-out PBMC dataset, the shipped architecture
does not beat scANVI's best arm.** That arm has its RNA reference
restricted to the 932 genes Fulcher measures.
- **Under the shared kNN rule,** scANVI is ahead in 12 of 15 seed pairings
  (mean −5.8 points). The other 3 are inconclusive.
- **Product rule vs scANVI's native classifier,** v3 is ahead in 9 of 15
  (6 inconclusive).
- **V2, the selected v3.1 candidate encoder,** is ahead in all 30 pairings.

**On Khoury 2026, the sealed final test, v3 as served is ahead of
scANVI's best arm** (its RNA reference restricted to the 1,252 genes
Khoury measures) in all 6 pairings: +10.0 points on average, product rule
vs native, and +3.7 under the shared kNN rule, the narrowest margin in that
evaluation (lowest CI bound +0.5). That arm was handicapped (a likelihood
unable to fit its inputs, and the scaling mismatch). **Corrected
(post-hoc), scANVI is ahead of v3 in all 6 pairings** (61.5 shared kNN,
51.6 native, against 39.8 and 40.9;
`research/benchmark/baseline-corrections.md`).

The first Fulcher write-up had v3 ahead in all 30 pairings. That was
against a scANVI arm with two thirds of its genes zero-filled, and it has
been corrected (`research/benchmark/results.md`, section "Fulcher 2026").
The SCoPE2 comparison above is unaffected: SCoPE2 has a value for all 2,907
benchmark genes in every cell, so nothing there was zero-filled.

**A methodological asymmetry in scANVI's favor, throughout the comparison
above: scANVI trains on the query cells (transductive); this encoder is
fixed and zero-shot on the query.**

**v3.1 as served against four more baselines and a simple one (Track D
extension, development data).** MaxFuse, scGLUE and Harmony with kNN (3
seeds each), Seurat CCA label transfer, and correlation to the RNA class
mean ran on the same gene-fair inputs. v3.1 is scored on its best guess.
**Superseded:** these runs were handicapped by our setup; corrected, on
Fulcher, Harmony (60.8–63.0) and the correlation baseline (62.1) are ahead
of v3.1's 57.9, and on SCoPE2 restricted, with its labels corrected, only
Harmony with nearest centroid (63.0) is above chance
(`research/benchmark/baseline-corrections.md`).
The first-run numbers, kept for the record:

- **Fulcher 2026** (added after the held-out scoring): v3.1 at 57.9% balanced
  is ahead in all 22 seed pairings.
  - The correlation baseline is next at 46.9% (v3.1 +11.1, CI excludes
    zero).
  - Seurat CCA, biased in its favour here, scores 18.9%.
  - scGLUE, run with its cluster balancing off (protocol amendment 7),
    scores 24.2% at best.
- **PBMC240:** lymphoid recall is 92.3% for v3.1 and 59.8% for the
  correlation baseline. Every integration tool is at 38.8% or below.
- **SCoPE2 restricted** (chance 50%, labels corrected,
  `research/benchmark/bugs-and-fixes.md`, 8): v3.1 at 38.7% is below
  every new tool's mean (40.4% to 50.6%). Against the correlation baseline
  the difference is −1.7 (CI includes zero).
- **SCoPE2 unrestricted:** every method averages under 5%, v3.1 at 0.0%.

Every Seurat CCA number from before 2026-10-02 is void: its inputs were
written in the wrong byte order (protocol amendment 7). The numbers above
are from the corrected runs.

Tables: `research/benchmark/baselines/`. Narrative:
`research/benchmark/results.md`, "Baselines beyond scANVI".

### Known failure modes

1. **The two-class label space, now opt-in.**
   `config.CROSS_MODAL_SUPPORTED_CLASSES = ("macrophage", "monocyte")`.
   - **When restricted,** a protein upload of any non-myeloid cell type
     (T cell, NK cell, B cell, etc.) can only ever be assigned "macrophage",
     "monocyte", or abstain. It can never get its true label, however
     well-separated its embedding is. Confirmed on real data twice:
     - PBMC240: restricted, no lymphoid cell can be labelled lymphoid.
       Unrestricted, the shipped v3 recalls 43.6% of them
       (`research/notebook-outputs/nb1c/pbmc240_raw_service_path.csv`,
       `v3_shipped`, smoothing on).
     - The held-out Fulcher 2026 PBMC upload: the restricted service labelled
       every cell it didn't abstain on as macrophage or monocyte.
   - **Since 2026-09-30 the restriction is opt-in per request**
     (`restrict_to_supported_classes`), and the default assigns among all 22
     classes. Under v3 that default abstains on 48% of Fulcher cells and
     labels only 2.1% monocyte, against 36% in the annotation
     (`research/benchmark/fulcher2026/product_check.json`).
   - **Under v3.1, and v4.1 (the default), which keeps its answers,**
     lymphoid cells get lymphoid answers: on
     Fulcher, 89% of cells are committed and 97% of committed answers are
     correct at the stated level (v3.1, Development data above).
2. **Macrophage and monocyte placement.** Cross-modal alignment is weak for
   both SCoPE2 classes, and the macrophages land on the RNA monocytes.
   - **Latent centroid cosine:** 0.37 for macrophage and 0.14 for monocyte
     (`service/model/evidence/v3_tables/latent_centroid_cosine.csv`); the
     macrophages' centroid sits at 0.83 to the RNA monocyte centroid.
   - **Restricted to the two supported classes,** `v3_seed0` recalls 6.7%
     of protein macrophage cells and 33.8% of monocytes
     (`research/notebook-outputs/nb1d/real_data_per_seed.csv`,
     `scope2_mac_recall_restr`, `scope2_mon_recall_restr`).
   - **Across all 22 classes** it recalls 0.09% of macrophages, sending 61.4%
     of them to monocyte, and 1.3% of monocytes, sending 78.7% of them to
     CD8 T cells
     (`research/notebook-outputs/nb1d/scope2_prediction_distribution.csv`).
3. **2 of 22 reference classes have any protein-side validation.**
   Macrophage and monocyte are the only classes ever checked against real
   protein ground truth. The other 20 classes' embeddings have not been
   validated against protein data at all.
4. **No donor-level holdout in training.** All nine donors contributed
   roughly 65% of their own cells to training (`research/todo.md`
   §4) — not a subset of donors, all of them. Published RNA→RNA numbers
   reflect this; a true held-out-donor evaluation does not yet exist.
   Planned for v4 (T2 NB8).
5. **High seed-to-seed variance on real cross-modal transfer, not yet
   explained.** Retraining the identical architecture with a different seed
   moves SCoPE2 restricted balanced accuracy by up to 29 points (11.6% to
   41.0% across 5 seeds, shared kNN) — `v3_seed0`, the shipped checkpoint,
   happens to be the worst of the five, not a principled choice among them. The RNA-only
   validation task this architecture was selected on shows far less
   seed-to-seed spread (95% CI [68.5%, 74.4%] — `provenance.json`), so
   whatever drives this instability is specific to the RNA→protein transfer
   step, not the RNA-side training. A separate development-only check
   (PBMC240 raw, real ~75%-missing data, lineage-level labels — see
   `research/notebook-outputs/nb1d/`) is scored by recall per lineage, not plain accuracy —
   accuracy is uninformative at this sample's 117-lymphoid-vs-5-myeloid
   split, and a per-class recall is only meaningful read against its
   counterpart, not against an overall accuracy figure: a trivial model
   that calls every cell "lymphoid" scores 100% lymphoid recall and 0%
   myeloid recall. The shipped architecture's 5-seed mean **lymphoid
   recall** (52.8% ± 7.7%, n=117) paired with its **myeloid recall**
   (100.0%, n=5, anecdotal) shows real separation between lineages, not a
   one-class collapse; a second candidate architecture ("V2") reaches
   92.8% ± 0.8% lymphoid recall (80.0% myeloid, n=5, anecdotal) — a large,
   low-variance margin over the shipped architecture on real messy data
   specifically. (With only 5 myeloid cells, myeloid recall for every
   architecture is anecdotal — one misclassified cell moves it 20
   points — reported alongside lymphoid recall only to show overall
   behavior, never to rank on its own.) scANVI's best PBMC240 arm, with the
   RNA reference restricted to the 1,111 genes PBMC240 measures, reaches
   38.75% (shared kNN) and 39.60% (native) lymphoid recall. That is below
   both architectures. V2 does not carry its PBMC240 margin onto SCoPE2 (see
   `research/benchmark/results.md`). On the held-out Fulcher 2026 data it
   beats v3 in all 50 seed pairings. V2 is v3.1's encoder, as a five-seed
   ensemble.

## Versioning

- v4.2 files: `service/model/v4_2/MANIFEST.json`.
- v4.1 files: `service/model/v4_1/MANIFEST.json`, which also pins v4's data
  files (`service/model/v4/MANIFEST.json`).
- v3.1 files: `service/model/v3_1/MANIFEST.json` (sha256, size and origin of each).

- Model artifact provenance: `service/model/runtime/provenance.json` (`created`,
  `gene_list_hash`, training config).
- Gene identifier mapping table: `service/model/runtime/gene_id_map_v1.tsv`, built
  from a one-time HGNC bulk download — provenance, source sha256, and the
  derived table's own sha256 in `service/model/runtime/gene_id_map_v1_provenance.json`.
- Site-facing atlas version: `ATLAS_VERSION` in `service/config.py` /
  `scripts/build_manifest.py`.
