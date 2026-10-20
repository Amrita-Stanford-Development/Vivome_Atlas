# Protocol: the lung reference's locked test, MSV000094189 (Ushakumary 2025)

**No file of this set has been opened or downloaded.** This protocol was
written on 2026-10-18 from the MassIVE record's file listing (names and sizes
only) and the paper (Ushakumary et al., Am J Respir Cell Mol Biol 2025,
72:484, doi 10.1165/rcmb.2024-0105OC), before any label, sample name or
protein list of the set was read. Its role is set in
`research/benchmark/side-tests.md`, amendment 9; the reference it tests is
planned in `research/organ-references.md`, "Lung".

- **Freezing.** This file is frozen at the commit that adds it. Anything that
  must change before unsealing goes in a dated amendment at the end,
  committed first. Nothing changes after unsealing except format fixes
  (rule 10).
- **One scoring,** after the lung candidate is frozen (rule 1).
- **What a result means.** An internal held-out test of the lung reference
  on pooled, FACS-sorted lineage proteomes, never external validation and
  never a single-cell accuracy. Every report states:
  - the samples are pools of sorted cells, labelled at lineage level only;
  - the donors are children (0 to 8 years), while the reference is Tabula
    Sapiens adult lung;
  - the development set MSV000094373 comes from the same lab and
    biorepository, and may share donors (the owner's choice, amendment 9);
  - the sorting antigens (PTPRC, PECAM1, EPCAM) are themselves measured in
    the proteomes.

## Data (MassIVE record and the paper)

- **Files used** (`quant/MaxQuant/`):
  - `proteinGroups.txt` (52,208,897 bytes), MaxQuant protein groups;
  - `Protein_metadata.csv` (26,370 bytes);
  - `summary.txt` (25,536 bytes), MaxQuant's run summary, for linking runs
    to experiments.
  - Not used: `peptides.txt`, and the raw files.
- **Samples (the paper's methods):**
  - Lungs of 11 pediatric donors, not placeable for transplant, through the
    BRINDL biorepository.
  - Dissociated cells were sorted sequentially: CD45+ mixed immune cells,
    PECAM1+ endothelial cells, EpCAM+ epithelial cells, and mesenchymal cells
    (CD45−, PECAM1−, EpCAM−).
  - The paper's figures abbreviate the populations END, EPI, MES and MIC.
- **Acquisition:**
  - MPLEx extraction, 500 ng of digested peptides;
  - nanoACQUITY with a Q Exactive Plus, 180-minute gradient, top-12 DDA;
  - MaxQuant 1.6.0.16 against UniProt human, MaxLFQ, match-between-runs.

## Rules

1. **Candidate.** Exactly one: the lung bundle "lung v1". An amendment to
   this file freezes it, with the sha256 of its MANIFEST, before unsealing. If
   its development gates (`research/organ-references.md`, "Lung") are not
   passed, there is no candidate and the set stays sealed.
2. **Scores come from the service's own code.** The candidate runs through
   the served pipeline, with the lung bundle's own gene map. The per-class
   fused best-guess probabilities are recomputed with the same functions,
   and their argmax must equal the served best guess on every sample.
3. **Inclusion,** read at unsealing from the sample names, `summary.txt` and
   `Protein_metadata.csv`:
   - sorted samples of the four populations;
   - excluded: unsorted or pre-sort mixes, pools, QC, blank and library runs.
   - If the samples cannot be assigned a population and a donor without
     doubt, the map is written by hand by these rules, with the reason
     (rule 10).
4. **Lineages.** Each included sample maps to one lineage of the reference:

   | Population | Lineage | Reference classes |
   |---|---|---|
   | EPI (EpCAM+) | epithelial | every epithelial class |
   | END (PECAM1+) | endothelial | every endothelial class |
   | MES (triple negative) | stromal | every stromal class |
   | MIC (CD45+) | immune | every immune class |

   Names are matched by meaning: "epi"; "end" or "endo"; "mes"; "mic",
   "immune" or "cd45". The label map is written once, with its sha256.
5. **Upload.** One upload: every included sample from all donors together.
   With fewer than 20 samples the test is void.
6. **Reader.** MaxQuant protein groups, by
   `benchmark/heldout_formats.read_maxquant` (protocol-heldout.md, rule 7):
   - rows flagged only by site, reverse or contaminant dropped;
   - the first gene name;
   - the LFQ intensities where any is non-zero, otherwise the intensities;
   - 0 counts as missing.
7. **Primary.**
   - For each sample, P(lineage) is the sum of its fused best-guess
     probabilities over the lineage's classes. The predicted lineage is the
     argmax over the four.
   - The measure is balanced accuracy over the true lineages (chance 25%).
   - **p-value:** a one-sided permutation p with 10,000 permutations of the
     true lineages within donor, seed 0.
   - **Pass if p < 0.05.**
   - A lineage with fewer than 3 samples is left out and reported. Fewer
     than 3 lineages left: void.
8. **Secondary,** reported and never deciding:
   - recall per lineage, and the confusion table;
   - each sample's answer (class, group, lineage or abstention), abstention
     per lineage, and correct when committed at the stated level;
   - balanced accuracy per donor;
   - the baselines (correlation, and PCA with kNN, against Tabula Sapiens
     Lung with the candidate's labels), as for the colon.
9. **Scripts:** `benchmark/lung_heldout_intake.py` and
   `benchmark/lung_heldout_score.py`, rehearsed before unsealing.
10. **Unsealing, and format fixes:**
    - The order is the colon protocol's rule 10
      (`research/benchmark/protocol-colon-pxd052341.md`): the candidate
      amendment, the label map, the intake, the baselines, the scorer once.
    - Only reader or identifier fixes are allowed after unsealing, each by
      amendment before scoring.

## Rehearsal, before unsealing

The intake and scorer run end to end on RNA pseudobulk pools of the four
lineages, built from the lung reference's test cells and written as a
MaxQuant proteinGroups table with sample names in the deposit's style. The
record goes to `research/benchmark/heldout/rehearsals/`.

## Outputs, at scoring only

`research/benchmark/heldout/msv000094189/` (`summary.json`, `scores.csv`).

## Amendments

**Amendment 1, 2026-10-19: the candidate is "lung v2".** The v1 bundle
missed its development gates, so under rule 1 it is no candidate. The
organ's v2 (`scripts/organs/lung_v2.json`; `research/organ-references.md`,
"Version 2"; `side-tests.md`, amendment 14) replaces it as the one
candidate. Its intake reads the v2 work folder (`CANDIDATE` in the intake
script). Its bundle's MANIFEST.json sha256 is added below at freeze, before
any unsealing, and only if the v2 gates pass. Nothing else in this
protocol changes.

**Amendment 2, 2026-10-20: where the baselines run.** Rule 8's two
baselines, correlation and PCA with kNN, run in `benchmark/organ_baselines.py`.

- **Inputs:** the candidate's reference cells over its own gene space,
  scaled with every class weighted equally, as in
  `benchmark/baselines_corrected.py`.
- **When:** after the intake and before the scorer. The intake now also
  saves the upload over the organ's genes (`query_organ.npz`).
- **Scoring:** each baseline is scored by this protocol's primary measure,
  and the scorer copies `baselines.json` into `summary.json`.
- **Guard:** the scorer refuses to score the real set before the baselines
  exist.
- **Rehearsal:** done on the rehearsal intake.

They remain secondary and never decide.
