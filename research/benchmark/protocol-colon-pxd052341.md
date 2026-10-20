# Protocol: the colon reference's locked test, PXD052341 (Post 2025)

**No file of this set has been opened or downloaded.** This protocol was
written on 2026-10-18 from the PRIDE record's file listing (names and sizes
only) and the paper (Post et al., Cell Systems 2025,
doi 10.1016/j.cels.2025.101396; preprint doi 10.1101/2024.05.13.593888),
before any label, sample name or protein list of the set was read. Its role
is set in `research/benchmark/side-tests.md`, amendment 7; the reference it
tests is planned in `research/organ-references.md`.

- **Freezing.** This file is frozen at the commit that adds it. Anything that
  must change before unsealing goes in a dated amendment at the end,
  committed first. Nothing changes after unsealing except format fixes
  (rule 10).
- **One scoring,** after the colon candidate is frozen (rule 1).
- **What a result means.** An internal held-out test of the colon reference
  on pooled cell-type proteomes, never external validation and never a
  single-cell accuracy. Every report states:
  - the samples are pools of about 500 image-classified cells, not single cells;
  - the set comes from the same lab and chemistry as the development sets
    PXD057118 and PXD046999 (Deep Visual Proteomics, Evosep, DIA-NN);
  - the reference is Tabula Sapiens normal colon from other donors.

## Data (PRIDE record and the paper)

- **Files used:**
  - `DVP_data.pg_matrix.tsv` (8,222,603 bytes), DIA-NN protein groups;
  - `Post_et_al_organoid_DVP_metadata.tsv` (71,245 bytes), the deposit's
    experimental design.
  - Not used: `bulk_data.*` (organoid bulk), the precursor matrices, and the
    raw archives (about 1.9 TB in all).
- **Samples (the paper's methods):**
  - Native colon mucosa from cancer-associated resections or screening
    biopsies (Herlev Hospital); three donors, 11 cryosections of 5 µm.
  - Cells classified on images stained for EPCAM, PDGFR and CD45, by a
    multi-layer perceptron in BIAS. The crypt bottom was set by a hand-drawn
    line.
  - Each sample pools 500 contours (700 for upper-crypt immune cells); one
    contour is about one cell.
  - Also in the deposit, and excluded here:
    - organoids in vitro (an LGR5-TdTomato line);
    - organoids transplanted into NOG mice.
- **Acquisition:** Evosep One (Whisper40), Orbitrap Astral, DIA-NN 1.8.1
  with an in-silico library, match-between-runs, protein inference by genes.
- **Single cells?** The published abstract speaks of proteomics "at the
  single-cell level", and the deposit's raw archives are named scDVP (in
  vivo, organoid in vitro, organoid transplant). Whether the processed
  matrix holds single-contour samples is not known (rule 4).

## Rules

1. **Candidate.** Exactly one: the colon bundle "large_intestine v1". An
   amendment to this file freezes it, with the sha256 of its spec, MANIFEST
   and member checkpoints, before unsealing. If its development gates
   (`research/organ-references.md`, Stage 2) are not passed, there is no
   candidate and the set stays sealed.
2. **Scores come from the service's own code.** The candidate runs through
   the service's pipeline as served for the colon. The per-class fused
   best-guess probabilities are recomputed with the same functions. The
   intake refuses to go on if their argmax differs from the served best
   guess on any sample.
3. **Inclusion,** read from the metadata at unsealing:
   - samples of native human colon tissue only;
   - excluded: organoid (in vitro), transplant (mouse), blank, QC and library
     runs.
   - If the metadata cannot separate native human samples from organoid and
     transplant samples without doubt, the test is void, recorded and not
     scored.
4. **Pooled and single.**
   - The primary uses pooled native samples: more than one contour, or every
     native DVP sample if the metadata gives no contour count.
   - Native single-contour samples with a class, if present, form a
     secondary single-cell analysis (rule 8). It never decides.
5. **Groups.** Each included sample's class maps to one of five groups, and
   each group to reference classes:

   | Group | Post 2025 class | Colon reference classes |
   |---|---|---|
   | crypt bottom | EPCAM+ epithelium below the line, not goblet | crypt stem cell, transit amplifying cell |
   | upper crypt | EPCAM+ epithelium above the line, not goblet | enterocyte, best4+ cell |
   | goblet | goblet cells | goblet cell |
   | fibroblast | PDGFR+ fibroblasts | fibroblast, myofibroblast |
   | immune | CD45+ cells, at any location | every class of the immune lineage |

   - The metadata's names are matched to the five groups by their meaning
     ("bottom", "upper" or "top", "goblet", "fibroblast" or "PDGFR", "immune"
     or "CD45").
   - The label map is written once, with its sha256. A sample whose class
     matches none of the five is excluded and counted.
6. **Upload.** One upload: every included pooled sample from all donors
   together. With fewer than 20 samples (the service's minimum) the test is
   void.
7. **Primary.**
   - For each sample, P(group) is the sum of its fused best-guess
     probabilities over the group's reference classes. The predicted group is
     the argmax over the five groups.
   - The measure is balanced accuracy over the true groups (chance 20%).
   - **p-value:** a one-sided permutation p with 10,000 permutations of the
     true groups, within donor where the metadata names donors, seed 0:
     p = (1 + count at or above the observed) / 10,001.
   - **Pass if p < 0.05.**
   - A group with fewer than 3 samples is left out and reported. Fewer than 3
     groups left: void.
8. **Secondary,** reported and never deciding:
   - crypt bottom against upper crypt: the AUROC of
     S = P(crypt bottom) − P(upper crypt), with its permutation p;
   - each sample's answer (class, group, lineage or abstention), abstention
     per group, and correct when committed at the stated level;
   - the confusion table of predicted groups;
   - native single-contour samples (rule 4): the same balanced accuracy and
     p, reported as a single-cell result;
   - the baselines: correlation, and PCA with kNN
     (`benchmark/baselines_corrected.py`, its colon option, against Tabula
     Sapiens Large Intestine with the candidate's labels), each with its
     predicted groups and balanced accuracy.
9. **Reader.**
   - The DIA-NN protein-group matrix is read by the service's own parser.
   - Its run columns are linked to the metadata by raw-file name.
10. **Unsealing, in this order:**
    1. the candidate amendment, committed;
    2. the label map, from the metadata by rules 3 to 5, written once with
       its sha256. If the automatic reading fails, the map is written by hand
       by the same rules, with the reason recorded;
    3. the intake. Each input file is checked against its sha256 in
       `research/benchmark/public-sets-downloads.json`, and the frozen files
       against rule 1. It builds the upload and runs the candidate once,
       saving the per-sample tables and probabilities;
    4. the baselines;
    5. the scorer, once. It refuses to run again and writes
       `research/benchmark/heldout/pxd052341/`.

    The scripts are `benchmark/colon_heldout_intake.py` and
    `benchmark/colon_heldout_score.py`, rehearsed before unsealing.
11. **Format fixes.** After unsealing, only a reader or identifier fix is
    allowed (a column spelled differently, run names laid out otherwise),
    each in an amendment with its reason, before the scoring. No rule,
    group, statistic or threshold changes.

## Rehearsal, before unsealing

The intake and scorer run end to end on two inputs:
- RNA pseudobulk pools of the five groups, built from the colon reference's
  test cells with a detection mask shaped like the development DVP sets;
- a synthetic file in DIA-NN's layout.

The record goes to `research/benchmark/heldout/rehearsals/`. Its result is
added here by amendment before unsealing.

## Outputs, at scoring only

`research/benchmark/heldout/pxd052341/`:
- `summary.json`: the primary, the secondary measures, the baselines and the
  statement above;
- `scores.csv`: per sample.

## Amendments

**Amendment 1, 2026-10-21: the code's guards, before the set is opened.**
A review of the lymph node's and lung's locked tests found these gaps,
which the colon's code shared. The colon has no candidate (it missed its
gates), so the set is sealed and stays so.
- **Rule 1:** the labels step (`--labels`) now checks for the frozen
  candidate before it reads any sealed file. Before, only the later intake
  step did.
- **Overrides:** the intake and the scorer refuse VIVOME_* overrides, as
  the other locked tests do.
- **The intake's files:** the scorer stops if any file the intake recorded
  (the label map, the predictions, the query matrices) has changed since.

Tests are in `service/tests/test_organ_heldout.py`.
