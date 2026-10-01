# VivOME model card

The service runs **v3.1** by default. **v3** stays selectable
(`VIVOME_PIPELINE_VERSION=v3`) and is described after it. Both are trained
on RNA only and applied zero-shot to protein.

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

Spec: `service/model/v3_1/nb2_spec_v31.json`. Code:
`service/pipeline/ensemble.py`. Response:
`docs/service/projection-api.md`, v3.1.

### Evaluation suite

The suite is T1 NB1's 240 simulated RNA uploads from test-split cells,
masked like real mass-spectrometry data. "v3 as served" is NB2's replica of
the v3 service: Stages 4 to 6, without the Stage 7 fallback. Source:
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
  `benchmark/v31_dev_gate.py` runs the served pipeline on the same parse
  and reproduces every figure in
  `research/notebook-outputs/nb2/tables/dev_datasets.csv`: committed share,
  each abstention reason, and composition within 0.1 point.
- **SCoPE2.** 1,490 cells, all macrophage or monocyte.
  - 72.6% committed.
  - Of the committed answers, 39.5% are correct at the stated level, and
    all of those are "myeloid" lineage answers. None of its 152 class
    answers or 397 group answers is correct. "T cell" alone is 31.0% of
    all cells.
- **PBMC240.** 238 cells with weak lineage labels.
  - 74.0% committed, 1.7% of cells at class level.
  - NB2 reports 79.5% lymphoid correct and 60% myeloid correct; the myeloid
    figure covers 5 cells and is anecdotal.

v3.1 on PBMC240 through the service parser: committed 72.7 vs 74.0 under the notebook parse; the difference is gene identifier resolution (HGNC map, ambiguous groups unmatched) and the graph input, not the pipeline.

**Fulcher 2026** is development data since 2026-09-30. Its numbers below
come from 1,275 cells through the service parser with default settings,
1,251 of them scored against the authors' six types
(`research/benchmark/fulcher2026/v31_development.json`):
- **Committed:** 89.4%, and 97.2% of committed answers are correct at the
  stated level.
- **Mostly group or lineage answers.**
  - CD4T and CD8T are mostly answered at group level ("T cell").
  - NK and monocyte are almost all answered at lineage level.
  - B is mostly answered at class level.
- **DC** is committed on only 53.7% of cells.
- **Best guess:** 57.9% balanced accuracy over the six types. Single V2
  seeds under nearest centroid score 57.3 ± 2.2.

### Known limits

1. **The out-of-distribution filter passes 99% of scrambled cells.** In
   NB2's negative control it rejects 0.96% of gene-shuffled cells and 5.5%
   of real ones (AUC 0.845; `research/notebook-outputs/nb2/tables/ood_negative_control.csv`).
   The max-cosine score barely separates a scrambled profile from a real
   one. A better score is an open problem.
2. **B cell coverage is 69%,** against the 90% target, and 64% under
   missing-not-at-random masking. It is the lowest class; the others range
   from 84% to 96% (`eval_per_class_coverage.csv`,
   `eval_mnar_per_class_coverage.csv`).
3. **SCoPE2 still fails.** See Development data above: no class or group
   answer is right, and the best guess is right for 1.1% balanced. In
   v3.1's coordinate space the SCoPE2 macrophage and monocyte centroids sit
   far from their RNA classes. The 3-PC centroid cosine for each is in
   `web/data/atlas_manifest.json`.
4. **Coverage is guaranteed on RNA simulations only.** On protein it is
   approximate, which is why `calibration.applies_to` says so in every
   response.
5. **The threshold was fitted with training-split references; the service
   uses every reference cell.** That raises max cosine slightly, so the
   service abstains as out of distribution a little less often than NB2
   measured (the spec's `caveats`).
6. **The calibration suite comes from the validation split,** which also
   set the encoders' early stopping.

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
| Protein (SCoPE2, 1,490 real cells), **restricted** to the two supported classes, **shipped checkpoint (`v3_seed0`)**, nearest centroid (the service's rule) | 86.2% acc / 79.8% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **restricted, 5-seed mean of the shipped architecture**, nearest centroid | 79.4% ± 4.7 acc / 63.3% ± 10.8 bal (range 50.8–79.8 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein (SCoPE2), **restricted, shipped checkpoint (`v3_seed0`)**, shared kNN (the benchmark's rule) | 85.0% acc / 88.4% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **restricted, 5-seed mean of the shipped architecture**, shared kNN | 75.3% ± 11.8 acc / 71.5% ± 10.6 bal (range 59.0–88.4 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein (SCoPE2), **unrestricted** across all 22 classes, **shipped checkpoint (`v3_seed0`)**, nearest centroid | 45.4% acc / 31.1% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **unrestricted, 5-seed mean of the shipped architecture**, nearest centroid | 34.1% ± 25.2 acc / 25.6% ± 17.3 bal (range 0.1–48.2 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein (SCoPE2), **unrestricted, shipped checkpoint (`v3_seed0`)**, shared kNN | 55.4% acc / 38.7% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **unrestricted, 5-seed mean of the shipped architecture**, shared kNN | 38.4% ± 25.7 acc / 29.1% ± 18.3 bal (range 1.3–49.8 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein, **Fulcher 2026** (held-out scoring; TMT PBMCs, 1,251 cells, 6 types, chance 16.7%), unrestricted, **shipped checkpoint (`v3_seed0`)** | 44.1% bal (nearest centroid) / 41.8% (shared kNN) | `research/benchmark/fulcher2026/per_seed_scores.csv` |
| Protein, Fulcher 2026, **5-seed mean of the shipped architecture** | 42.3% ± 3.4 / 42.0% ± 2.9 bal | `research/benchmark/fulcher2026/family_summary.csv` |
| Modality probe (RNA vs. protein separability in latent space) | 98.99% ± 0.28% | `research/todo.md` §5 |

**A previously published RNA→RNA figure of 95.5% / 74.8% (SCoPE2 mask) is
superseded by the 93.2% / 65.7% figures above.** The published number
included cells the model had trained on in its own test split — an invalid
measurement. The corrected numbers here score test cells only.

**The restricted 79.8% balanced accuracy is `v3_seed0`'s own number, is
exact for SCoPE2 by construction, and is not a generalizable result — on
two separate counts.** First: SCoPE2's protein cells are only ever
macrophage or monocyte, so restricting Stage 4's candidate space to exactly
those two classes (`config.CROSS_MODAL_SUPPORTED_CLASSES`) is, on this one
dataset, restricting to the true label set — the number reflects that
match, not a property of the model that holds on other data. On any upload
containing other cell types (e.g. PBMC240, which has T and NK cells), the
same restriction is actively wrong. That is why it is now opt-in; see failure mode 1 below.
Second: `v3_seed0` — the checkpoint actually shipped — is the
best-performing of five independently trained seeds of the same
architecture by a wide margin, under either decision rule: 79.8% vs. a
5-seed mean of 63.3% ± 10.8 (range 50.8–79.8) under nearest centroid, the
service's rule; 88.4% vs. 71.5% ± 10.6 (range 59.0–88.4) under shared kNN.
Compare a seed with a mean only under the same rule. Neither caveat was known when this figure was first
published; both are measured directly in the table above, not inferred.

**Against scArches/scANVI (a real, supervised, label-consuming cross-modal
integration baseline — the strongest available comparison), the shipped
checkpoint's SCoPE2-restricted lead is real but does not generalize either.**
`v3_seed0` beats every scANVI seed under every protocol tested (paired
bootstrap, all 9 checks CI-excludes-zero in `v3_seed0`'s favor). Averaged
across all 5 v3 seeds, though, the architecture's shared-kNN-rule
restricted mean (71.5% bal) *trails* scANVI's 3-seed mean (77.15%) — only
3 of 15 seed-pairings favor "ours" there, 12 favor scANVI. The one regime
the architecture reliably wins is unrestricted (12 of 15 pairings, mean
margin +18.1 points). Full breakdown:
`research/notebook-outputs/nb1d/paired_bootstrap_ours_vs_scanvi.csv`, narrative in
`research/benchmark/results.md`. **The takeaway for anyone reading only this
card: "beats the strongest available baseline" is true of the specific
checkpoint running in production, not a property of the architecture that
would necessarily hold if it were retrained.**

**On Fulcher 2026, the held-out PBMC dataset, the shipped architecture
does not beat scANVI's best arm.** That arm has its RNA reference
restricted to the 932 genes Fulcher measures.
- **Under the shared kNN rule,** scANVI is ahead in 12 of 15 seed pairings
  (mean −5.8 points). The other 3 are inconclusive.
- **Product rule vs scANVI's native classifier,** v3 is ahead in 9 of 15
  (6 inconclusive).
- **V2, the selected v3.1 candidate encoder,** is ahead in all 30 pairings.

The first Fulcher write-up had v3 ahead in all 30 pairings. That was
against a scANVI arm with two thirds of its genes zero-filled, and it has
been corrected (`research/benchmark/results.md`, section "Fulcher 2026").
The SCoPE2 comparison above is unaffected: SCoPE2 has a value for all 2,907
benchmark genes in every cell, so nothing there was zero-filled.

**A methodological asymmetry in scANVI's favor, throughout the comparison
above: scANVI trains on the query cells (transductive); this encoder is
fixed and zero-shot on the query.**

### Known failure modes

1. **The two-class label space, now opt-in.**
   `config.CROSS_MODAL_SUPPORTED_CLASSES = ("macrophage", "monocyte")`.
   - **When restricted,** a protein upload of any non-myeloid cell type
     (T cell, NK cell, B cell, etc.) can only ever be assigned "macrophage",
     "monocyte", or abstain. It can never get its true label, however
     well-separated its embedding is. Confirmed on real data twice:
     - PBMC240: the same embeddings that score 0% lymphoid recall restricted
       score 46.6% unrestricted.
     - The held-out Fulcher 2026 PBMC upload: the restricted service labelled
       every cell it didn't abstain on as macrophage or monocyte.
   - **Since 2026-09-30 the restriction is opt-in per request**
     (`restrict_to_supported_classes`), and the default assigns among all 22
     classes. That default is an interim fix, not a solution. On Fulcher it
     abstains on 48% of cells and labels only 2.1% monocyte, against 36% in
     the annotation (`research/benchmark/results.md`).
   - **Owners:** T1 NB2 (label space estimation) and Track C.
2. **Macrophage placement.** Even within the two supported classes,
   cross-modal alignment is weak for macrophage: latent centroid cosine is
   0.19 for macrophage vs. 0.830 for monocyte, and protein-side macrophage
   recall is 0.76%. The macrophage-vs-monocyte ranking is directionally
   correct (AUC 0.928) but the absolute placement is not — most macrophage
   protein cells are misassigned to monocyte or a distractor class.
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
   moves SCoPE2 restricted balanced accuracy by up to 29 points (59.0% to
   88.4% across 5 seeds) — `v3_seed0`, the shipped checkpoint, happens to be
   the best of the five, not a principled choice among them. The RNA-only
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

- v3.1 files: `service/model/v3_1/MANIFEST.json` (sha256, size and origin of each).

- Model artifact provenance: `service/model/runtime/provenance.json` (`created`,
  `gene_list_hash`, training config).
- Gene identifier mapping table: `service/model/runtime/gene_id_map_v1.tsv`, built
  from a one-time HGNC bulk download — provenance, source sha256, and the
  derived table's own sha256 in `service/model/runtime/gene_id_map_v1_provenance.json`.
- Site-facing atlas version: `ATLAS_VERSION` in `service/config.py` /
  `scripts/build_manifest.py`.
