# Protocol: the sorted CD4/CD8 test

**No data yet.** This protocol was written on 2026-10-13, before any
qualifying dataset was received. Two data requests are pending: O'Connor et
al. 2026 (Pirrotte lab, TGen) and Krisp et al. (AUS-oMicS 2025, Bruker).

- **Freezing.** This file is frozen at the commit that adds it. Anything that
  must change before the labels are opened goes in a dated amendment at the
  end, committed before unsealing. Nothing changes after unsealing.
- **One scoring.** A qualifying dataset is scored once, following this file.

## Why this test

CD8 T is where every method fails on protein data.
- **On Khoury 2026,** v4.1 recalls 2.7% of CD8 T cells, PCA kNN 0.9% and
  Harmony 3–6% (`research/benchmark/khoury2026_posthoc/per_seed_scores.csv`).
- **Khoury's own labels** split naive against memory T cells rather than
  CD4 against CD8 (`research/notebook-run-history.md`, entry 28).
- **Fulcher 2026** measures no CD8A.

So only cells whose CD4 or CD8 identity comes from physical sorting can test
the question. Two candidates are frozen now:
- **v4.1,** Track G's candidate, served on request;
- **v5.2,** Track H's CD4/CD8 candidate: members retrained on reference labels
  with CD4/CD8 T corrected using Hao et al. 2021 (entry 29). Its simulated
  pre-registered evaluation was not run, because the development guardrail
  on PBMC240 already fails by about one cell (89.7 against at least 90.3).
  A result here does not release it by itself.

## A qualifying dataset

- **Cells:** human blood immune cells measured by single-cell mass
  spectrometry proteomics.
- **Labels:** each cell's population comes from physical sorting (FACS or
  MACS) or from index-sorting fluorescence recorded per cell. They are not
  from clustering or annotation of the protein data.
- **Populations:** at least CD4 T and CD8 T, sorted separately, with at least
  50 cells each after quality control.
- **More than one:** the first qualifying dataset received is the test; a
  second is scored, likewise once, as a replication.

## Rules

1. **Sealed on receipt.** The per-cell labels are stored apart from the
   data, with their sha256 recorded. They are not opened until the intake
   and scoring scripts are committed and rehearsed on Fulcher 2026.
2. **Label-free intake.** The protein × cell matrix is built by a script
   committed before unsealing:
   - from the authors' search output (protein groups to gene symbols through
     the service's gene identifier map);
   - log2, with missing values kept missing and nothing imputed;
   - with the authors' own normalisation when they provide a normalised
     matrix, recorded in an amendment.
   Only label-free facts (cell, protein and missingness counts; presence of
   CD8A, CD8B and CD4) may be looked at before unsealing.
3. **Our models are frozen now.** They are scored as served, with every
   reference cell.

   | Model | Files, sha256 |
   |---|---|
   | v3.1 | `service/model/v3_1/MANIFEST.json`, as committed |
   | v4.1 | `service/model/v4_1/spec_v41.json` `0b4d7ba486345af8ee04622c625c42d0c3dd14729764cec61446d26c38ca77de`; MANIFEST `5e9cdc71496af5238b4ad5a4bc9ccfb7fce90a0a43d63b1948d14a0f3054382b` |
   | v5.2 | `service/model/v5_2/spec_v52.json` `61d76d2815b4bd534691fd3f64fa559296afd52e78cd843b9aa3d23fd4f4e2c1`; `nb2_spec_v52.json` `6596bb188ce6420ccf53646ee64fdc3606bb59d30ccbbef1e65e0e62bb04674a`; MANIFEST `72f419d4c1098fc492a274e758894a9bc704853f4c6b9d43d68a7d836a656e8c`; labels `research/notebook-outputs/v52_labels/reference_labels_v52.csv.gz` `123c05eb84d6ff502ba121a97b3a123eaddd08ac01c46647381ce7aa78160280` |

4. **The corrected baselines run unchanged,** with their committed scripts
   and settings, as on Khoury (`research/benchmark/protocol-khoury2026.md`,
   amendment 3): correlation, PCA with kNN, Harmony × 3, scANVI × 3, Seurat,
   MaxFuse × 3 and scGLUE × 3.
   - **Original reference labels,** for the comparison with v3.1 and v4.1,
     which use them.
   - **v5.2's labels,** for the comparison with v5.2, so a gain from better
     labels is not credited to the model. These runs are made and committed
     before unsealing; if they are missing at unsealing, v5.2 is compared
     with v4.1 only.
5. **Class mapping,** fixed now (`benchmark/fulcher2026_score.py`, `COARSE`):

   | Type | Reference classes |
   |---|---|
   | CD4T | CD4 T, naive CD4 T, Treg |
   | CD8T | CD8 T |
   | NK | NK |
   | B | B, plasma cell |
   | monocyte | classical, intermediate and non-classical monocyte; monocyte |
   | DC | myeloid and plasmacytoid DC |

   Every other prediction counts as "other", and so as wrong. Only the types
   the dataset sorted are scored.
6. **Metrics,** on every cell that passes the authors' quality control,
   from each model's best guess:
   - **primary:** balanced accuracy over the sorted types;
   - **secondary:** CD8 T recall; CD4 T recall; the CD4/CD8 confusion among
     the sorted T cells;
   - **answers,** for v3.1, v4.1 and v5.2: coverage, committed share and
     correct when committed.
7. **Paired bootstrap:** `benchmark/evaluate.paired_bootstrap_diff`, 2,000
   stratified resamples, seed 0, for every comparison below.

## Decision rules, fixed now

- **"Beats the corrected baselines,"** for v4.1 or v5.2: a balanced-accuracy
  lead of at least 3 points over every corrected arm, each paired 95% CI
  above 0 (Track G, Phase 5). Each candidate is compared with the baselines
  that used its own reference labels (rule 4).
- **"v5.2 improves CD4/CD8 over v4.1"** needs both:
  - CD8 T recall above v4.1's, the paired CI above 0;
  - balanced accuracy no more than 1 point below v4.1's.

  This is evidence for the owner's release decision, not a release.
- **Every result is reported,** whichever way it falls.

## Caveats, stated alongside every result

- **Batch can stand in for the label.** Sorted populations are often prepared
  or run separately, and the amendment at intake records how this dataset
  did it.
- **The panel decides what is possible.** Whether CD8A, CD8B and CD4 are
  measured, and in what share of cells, is recorded at intake.
- **Donors are few.** The donor count is reported beside every figure.

## Outputs, at scoring only

`research/benchmark/sorted_cd4cd8/`: the scores, the per-type recall, the
CD4/CD8 confusion, the paired bootstraps and the verdicts.

## Amendment 1, 2026-10-14, before any data

A five-agent search of the repositories and the literature
(`research/benchmark/side-tests.md`) found what the two requested datasets
contain. The models, metrics and decision rules do not change.

- **O'Connor et al. (TGen) does not qualify.** Its cells were sorted by
  negative-selection magnetic sorting into T, B, NK and monocytes, and the T
  cells are pan-T, with no CD4/CD8 split. If it is received, it is scored as
  a lineage-level side test under its own protocol, not here.
- **Krisp et al. (Bruker, Cellenion) is the one known qualifying design.**
  Abstracts describe FACS-presorted CD4+ T cells, CD8+ T cells, CD19+ B cells
  and CD14+ monocytes, as single cells and as 10-cell bulks, plus 48 unsorted
  PBMCs. For it:
  - only single-cell runs count towards the 50-cell minimum and the
    metrics, and balanced accuracy is over CD4T, CD8T, B and monocyte;
  - the 10-cell bulks are scored apart, as a population-level check, and
    never mixed into the single-cell figures;
  - the unsorted PBMCs have no independent label and are not scored.
- **Neither deposit exists yet**, and none is public. If another qualifying
  dataset appears, it goes in a further amendment, before its labels are
  opened.
