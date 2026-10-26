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

## Amendment 2, 2026-10-15, before any data: the scripts

The intake and scoring scripts are written and rehearsed on Fulcher 2026, as
rule 1 requires. Nothing above changes; this records how the scripts read it.

- **Intake** (`benchmark/sorted_cd4cd8_intake.py`), label-free:
  - checks every frozen file of rule 3 against its sha256 and refuses to run on
    a mismatch, or with any `VIVOME_*` override set;
  - parses the authors' search output with the service's own parser and uploads
    every QC-passed cell in one upload, so no sorted population is projected
    alone. If the data warrant another grouping (for instance the 10-cell bulks
    apart), it is set by a further amendment at intake;
  - records rule 2's label-free facts, including whether CD8A, CD8B and CD4
    are measured and in what share of cells;
  - runs v3.1, v4.1 and v5.2 as served and saves each model's per-cell table,
    and writes the baselines' query matrix
    (`benchmark/baselines_inputs.py`, dataset `sorted_cd4cd8`), so rule 4's
    runs are `benchmark/baselines_corrected.py TOOL sorted_cd4cd8 SEED`, with
    and without `--labels v52`.
- **The labels, stored apart on receipt:** a CSV with `cell_id`, `type`
  (CD4T, CD8T, NK, B, monocyte, DC, or empty) and `unit` (single, bulk or
  unsorted), its sha256 recorded in the intake amendment. The scorer refuses a
  file with another sha256.
- **Scoring** (`benchmark/sorted_cd4cd8_score.py --unseal LABELS --sha256 HEX`),
  once; it refuses to run again:
  - the arms of rule 4 are those scored on Khoury post-hoc: correlation; PCA,
    Harmony, scANVI, MaxFuse and scGLUE with the shared kNN rule; scANVI's
    classifier, MaxFuse's matching and Seurat's transfer; three seeds where
    the tool has them;
  - "beats the corrected baselines" is read run by run: at least 3 points and
    a CI above zero against every run of every arm. A run that failed or
    diverged is listed and not scored, as on Khoury; if any run was never
    made, that verdict is not judged, and v5.2 is compared with v4.1 only;
  - CD8 T recall's paired bootstrap runs on the sorted CD8 T cells, where
    balanced accuracy is recall;
  - coverage is the share of scored cells whose set holds a class of their
    sorted type; correct when committed is judged at the stated level against
    NB2's hierarchy, as Khoury's scorer judges it.
- **The rehearsal** (`--rehearse` on both scripts, Fulcher's six types as if
  sorted): the intake's per-cell tables equal the committed served tables
  (labels, sets and guesses identical; probabilities within 3e-6), its query
  matrix equals the benchmark loader's (932 genes, values within 2e-6), and
  the scorer reproduces 21 committed Fulcher runs to 0.000000 points (v3.1
  57.94, v4.1 69.05, every original-label baseline run).

## Amendment 3, 2026-10-16, before any data: v4.2 added as a candidate

v4.2 passed its development gates (`research/notebook-run-history.md`, entry
32): v4.1 with protein class means from sorted cells (Rieckmann 2017) in its
correlation term. The owner chose to freeze it as a candidate. Nothing above
changes for v3.1, v4.1 or v5.2.

- **Frozen files** (rule 3), scored as served with every reference cell,
  loaded with its evaluation pending, since this test is part of it:

  | Model | Files, sha256 |
  |---|---|
  | v4.2 | `service/model/v4_2/spec_v42.json` `654a612b5d38220222d77ededf97791c58295126b5c8801b2500663380abe303`; MANIFEST `8fa42d4437523e89d2d5b033b535439f59e71fa63f91d00300d197b06771d565`; protein class means `3afacd88777433488087d433ee8cb2e22bbce92011bcd6f36db01b1d527bec1b` |

- **Its baselines** (rule 4) are those on the original reference labels,
  which v4.2's encoders and RNA class means use, as v4.1's do.
- **Decision rules:** "beats the corrected baselines" applies to v4.2 as to
  v4.1. v4.2 against v4.1 is reported with its paired bootstrap (balanced
  accuracy, and CD8 T recall on the sorted CD8 T cells); there is no
  decision rule for it here.
- **The scripts:** the intake checks v4.2's files and runs it; the scorer
  adds it to every table. Both were rehearsed again on Fulcher; the scorer
  reproduces v4.2's development figure there (75.79, from
  `research/notebook-outputs/v42_protein_means/summary.json`).

## Amendment 4, 2026-10-16, before any data: v4.2 served

v4.2 became the served model (release 0.5.0; run history, entry 45). Two of
its frozen files changed, and nothing it does to a protein upload:
- **`spec_v42.json`** records its evaluation as passed; no other field
  changed. sha256 now `c58912c6b0eaf2673b05138a9213dbb43dccbbd065cf860152e443bb5f6e8ae0`.
- **`MANIFEST.json`** holds the spec's new sha256. sha256 now `89af5192c1e8dc4f5fa0bca6b0d1a34770f26b91c22ee84684401cf7bc426144`.
- **The protein class means** are unchanged
  (`3afacd88777433488087d433ee8cb2e22bbce92011bcd6f36db01b1d527bec1b`).
- **The service now passes an upload's modality to v4.2:** an RNA upload
  takes v4.1's RNA class means, as v4.2's design said. The sorted cells are
  protein, so they take v4.2's protein path as before
  (`service/tests/test_v42.py`).

v4.2 is still scored as amendment 3 says: as served, a candidate, reported
against v4.1. The intake checks the new sha256s.

## Amendment 5, 2026-10-21, before any data: the scripts held to this protocol

A read-only review compared the scripts with this protocol. The scripts now
do what the protocol already said (tests in
`service/tests/test_sorted_cd4cd8.py`).
- **"A qualifying dataset" is checked before any score.**
  - At least 50 single cells each of CD4 T and CD8 T after quality control
    (amendment 1: only single cells count).
  - A dataset short of that gets no scores and no verdicts. Its labels have
    been read, so `summary.json` records "qualifies": false with the
    counts, and the scored-once guard holds.
- **"Caveats, stated alongside every result":** the three caveats are
  written into `summary.json`, with the single cells per type.
- **"The donor count is reported beside every figure":**
  - the labels file may carry a `donor` column (cell_id, type, unit,
    donor). The donors among the scored single cells, overall and for CD4 T
    and CD8 T, go into `summary.json`;
  - without the column, it says "not given in the labels file", and the
    intake amendment records the donor count from the authors.
- **The panel's markers** (amendment 2) are found by the uploaded
  identifiers: a row counts for CD8A, CD8B or CD4 when any member of its
  identifier group is the marker's symbol or UniProt accession (P01732,
  P10966, P01730).
  - The service's gene map does not hold CD8B, so through the map CD8B was
    always "not measured".
  - Values are first put on the service's scale, so a 0 in a linear upload
    is "not detected".
- **The rehearsal on Fulcher reproduces its committed tables exactly**
  (largest balanced-accuracy difference 0.000000 points).

## Amendment 6, 2026-10-27, before any data: the requests, and when the test runs

Nothing above changes for the models, the metrics or the decision rules.
- **No request had been sent.** The opening note ("Two data requests are
  pending") and amendment 1 read as if both had gone out. The drafts were
  ready on 2026-10-09 and 2026-10-14, but none was sent. The owner sends
  both now, from a Stanford address:
  - O'Connor et al. to Dr Pirrotte, the preprint's correspondence address;
  - Krisp et al. through Dr Coscia, his co-author at the MDC-Bruker Center
    (Klingeberg et al., Mol Cell Proteomics 2026), since no address for
    Dr Krisp is public.
- **The two sets, checked against their sources on 2026-10-27:**
  - Krisp et al. is two posters: Lorne Proteomics 2024 (timsTOF Ultra,
    Spectronaut 18) and AUS-oMicS 2025 (timsTOF Ultra 2, single cells and
    10-cell bulks, Spectronaut 19 with directDIA+). The request asks for
    either. The service reads Spectronaut reports, so the intake
    (amendment 2) is unchanged.
  - O'Connor et al. (bioRxiv 2026): one healthy donor; 1,540 sorted and 887
    unsorted cells; Spectronaut 20. The authors re-annotated 32 dendritic
    cells in the monocyte pool and 17 monocytes in the T-cell pool, and
    marked 142 dim NK cells "Unknown". If received, it is scored under its
    own lineage-level protocol (amendment 1), which says how those cells
    count before its labels are opened.
- **When the test runs (owner, 2026-10-27).** Every candidate and every
  corrected baseline fails CD8 T on protein (on Khoury, v4.1 2.7%, PCA kNN
  0.9%), and no blood candidate since v4.2 has passed its development
  gates. A qualifying dataset that arrives is stored sealed (rule 1) and may
  go through the label-free intake, but its labels are opened only when the
  owner chooses: normally once a candidate has improved CD8 T recall on
  development data, so that the one scoring does not just confirm a known
  failure. The preprint does not wait for this test.
