# Protocol: the Hao 2021 held-out suite

**Written 2026-10-16, before any held-out cell was read.** Hao et al. 2021's
donors P5 to P8 (its Batch2), minus their T and NK cells, have been held out
since amendment 1 of `research/benchmark/side-tests.md`. This file is frozen
at the commit that adds it. Anything that must change before unsealing goes
in a dated amendment at the end; nothing changes after.

## Why this test

- **The weak classes have almost no reference cells.** The reference has one
  myeloid dendritic cell and 29 pDCs; B cells and monocytes come from few
  donors.
- **Hao 2021 is another atlas.** It is CITE-seq of 161,764 PBMCs from 8
  donors (GEO GSE164378; 10x 3'), labelled with RNA and 228 surface
  antibodies, so its labels do not come from our model or our reference.
- **It is RNA, never protein evidence.** Its uploads are made protein-like
  with the real mask profiles, as NB1's simulated suites are. A result here
  is about transfer to other donors and another atlas.
- **Held out by donor and batch, not by atlas.** Hao's Batch1 (P1 to P4) was
  used in development (run history, entry 40), so the test's
  novelty is its donors and its batch.

## Data

- Counts: GSM5008737 (3' RNA) and its metadata (`celltype.l2`, `donor`).
- Genes: Hao's symbols resolved to the input space by the service's own gene
  map; counts of genes that resolve to one input gene add; values are
  log1p(counts / nCount_RNA × 10,000), the reference's convention
  (`research/notebooks/hao2021.py`). Input genes Hao lacks are unobserved.
- Label map, fixed now:

  | Hao `celltype.l2` | Reference class |
  |---|---|
  | B naive, B intermediate, B memory | B cell |
  | Plasmablast | plasma cell |
  | CD14 Mono | classical monocyte |
  | CD16 Mono | non-classical monocyte |
  | cDC1, cDC2 | myeloid dendritic cell |
  | pDC | plasmacytoid dendritic cell |
  | HSPC; Platelet; Eryth | hematopoietic precursor cell; platelet; erythrocyte |
  | CD4 and CD8 T types, Treg, NK, NK_CD56bright | their T and NK classes: in uploads, never scored |
  | ASDC, MAIT, gdT, dnT, ILC, proliferating types, Doublet | excluded |

- **Scored cells** are the mapped non-T/NK cells. T and NK cells of every
  donor built v5.2's labels (`research/notebooks/v52_labels.py`), so they
  are development data: they ride along in the uploads and are never scored.

## Uploads

Per held-out donor, three scenarios, each under three mask profiles
(Fulcher, PBMC240, SCoPE2, with per-cell missingness) and three seeds: 108
uploads (`benchmark/heldout_hao2021.py`, which draws them with fixed seeds):
- **pbmc:** 500 cells at the donor's own proportions among the mapped types;
- **myeloid:** 100 CD14 monocytes, 100 CD16 monocytes, 100 dendritic cells
  (cDC1, cDC2 and pDC at their proportions);
- **mixed:** 60 each of B cells, CD14 monocytes, NK cells, CD4 T cells and
  dendritic cells.
A scenario takes every available cell when a donor has fewer.

## Models

- **Candidates:** those frozen under `side-tests.md` amendment 2 (v4.1, v4.2
  and v5.2, with the sha256s of `protocol-sorted-cd4cd8.md` amendment 3,
  checked by the script before anything runs), and any later candidate
  frozen the same way before unsealing, added by amendment. v3.1 is
  reported for reference. Each runs as served (`pipeline.run_projection`);
  its best guess is scored.
- **Baselines:** correlation and PCA kNN, as `benchmark/baselines_corrected.py`
  runs them (reference RNA z-scored class-balanced over the benchmark genes
  the upload measures; the upload z-scored over its observed values;
  nearest centroid on row-centred profiles; 50 principal components and 30
  nearest neighbours by cosine), original reference labels, per upload.

## Scoring

- Per upload, over its scored cells: balanced accuracy over coarse types
  (`benchmark/fulcher2026_score.py`, `COARSE`; HSPC, platelet and
  erythrocyte count as "other").
- **Primary comparison:** v4.1's per-upload coarse balanced accuracy minus
  that of the correlation baseline, the stronger baseline in the rehearsal below,
  averaged over the 108 uploads. A donor-blocked bootstrap (donors drawn
  with replacement, then uploads within each, 10,000 draws, seed 0) gives a
  one-sided 95% lower bound. **v4.1 passes if the bound is above 0.**
- **Secondary, reported, never deciding:** the same comparison for each
  candidate and against the other baseline; each candidate minus v4.1;
  dendritic-cell recall at the fine class, B and monocyte recall at the
  coarse type; all of it per scenario and mask.

## Rehearsal (development donors P1 to P4)

The same code on the development donors, 108 uploads
(`python -m benchmark.heldout_hao2021 --rehearse`; record
`research/benchmark/heldout/rehearsals/hao2021.json`):

| Model | Coarse balanced accuracy, mean per upload | DC recall (fine class) | B recall | Monocyte recall |
|---|---|---|---|---|
| v4.1 | 60.7 | 7.3 | 98.1 | 81.9 |
| v4.2 | 54.9 | 4.0 | 98.1 | 80.7 |
| v5.2 | 62.3 | 11.1 | 98.2 | 82.1 |
| v3.1 | 54.1 | 20.1 | 98.1 | 57.4 |
| correlation | 57.6 | 17.0 | 94.4 | 65.0 |
| PCA kNN | 48.0 | 1.3 | 92.5 | 54.7 |

- **The stronger baseline is correlation,** so it is the primary's
  comparator. v4.1 minus correlation: +3.08 points, one-sided 95% lower
  bound +1.19; it would pass here.
- **v4.2's protein term meets RNA here.** The service applies it to any
  upload, and on RNA it costs 5.7 points against v4.1. Its result on this
  suite is reported, but RNA is outside its design.
- **Dendritic cells are rarely found** by any model (run history, entry 40).

## Unsealing

`python -m benchmark.heldout_hao2021 --unseal`, once, after the candidate
amendment and at the end of Goal 2's development (the plan's Phase 3). The
first run caches P5 to P8's counts; the script refuses a second scoring.

## Reporting

An internal held-out test, never external validation. Every report states:
RNA made protein-like by masking, not protein; held out by donor and batch,
not by atlas; Hao's labels come from RNA and surface protein, not sorting.

## Amendments

### 1, 2026-10-16: the candidates are final

Phase 2 of the Goal 2 plan froze no new candidate: Hao's dendritic cells in
the class centres and the out-of-distribution scores were NO GO (run history,
entries 40 and 41), and the single-type-upload candidate was dropped after
its probe (entry 36). The candidates are those of "Models" as written: v4.1
(the headline), v4.2 and v5.2, with v3.1 for reference. Unsealing may begin
(`side-tests.md`, amendment 5).
