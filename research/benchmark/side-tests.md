# Public data: the internal held-out test, development sets and alternatives

Written 2026-10-14, from a five-agent search followed by spot checks of the
key facts against the repositories. No public dataset can replace the main
test (`research/benchmark/protocol-sorted-cd4cd8.md`: CD4 T and CD8 T sorted
separately, single cells). These can each answer one narrower question.

**Roles changed on 2026-10-15** (amendment 1, below): most of what is on disk
is development data, a fixed part is held out as the internal test, and
external testing waits for the requested sorted cells.

## Amendment 1, 2026-10-15: roles, before any development (owner's decision)

The owner chose to develop on most of the data we have and to hold out a fixed
part as an internal test, so that a paper can say the model works on data set
aside before development and scored once. External testing waits for the
sorted cells requested by email.

| Weak spot | Development (free to use) | Held out (internal test) |
|---|---|---|
| Dendritic cells, B, monocytes | Hao 2021 donors P1–P4; every donor's T/NK cells | Hao 2021 donors P5–P8, non-T/NK cells, as simulated uploads |
| CD8 vs CD4 T, NK | Rieckmann 2017 (PXD004352), sorted proteomes | Tian (MSV000087462), sorted T-cell bulk |
| Macrophage vs monocyte | SCoPE2 | PXD046211 (THP-1 and U-937, with and without PMA) |
| Refusing foreign cells | MSV000099294 (microglia, HMC3), PXD077946, Furtwängler 2025 | PXD043355 (Jurkat and HeLa) |
| Neutrophils | PXD061052 (pools) | none: PXD061065 moved to reserve (amendment 3) |
| Immune vs non-immune | | PXD073250 (whole) |
| B vs T lineage | | PXD021882 (whole) |
| General | Fulcher 2026, PBMC240, PXD070599 PBMC runs DS18 and DS19, PXD020586 | |

- **Hao 2021's split is by donor, and so by batch** (P1–P4 are its Batch1,
  P5–P8 its Batch2). Its T/NK cells built v5.2's labels
  (`research/notebooks/v52_labels.py`, all 8 donors), so they are development
  everywhere and may appear in held-out uploads only as unscored context. The
  held-out suite is RNA: it tests transfer across donors and atlases, never
  protein.
- **Locked means:** no label table, sort gate, per-cell annotation or protein
  list of a held-out set is opened before its scoring. Each gets a committed
  protocol with one primary comparison and a committed intake script before
  then; the intake is written from the deposit's documentation and
  rehearsed on a development set of the same format.
- **Scored once, at the end,** on the final candidates and the frozen v4.1 and
  v5.2, and reported as an internal held-out test, never as external
  validation.
- **Khoury 2026 stays post-hoc only;** its bulk file stays diagnosis only.
- **The sorted CD4/CD8 cells, if they arrive mid-plan,** are scored at once
  under their protocol with v4.1 and v5.2.

### Amendment 2, 2026-10-16: the candidates for the internal held-out test

The held-out sets are scored once, at the end, on the candidates frozen by
then. So far: v4.1 (the served default), v5.2, and v4.2, frozen on
2026-10-16 with the sha256s in `research/benchmark/protocol-sorted-cd4cd8.md`,
amendment 3. A later Phase 2 candidate joins only if it is frozen the same way
before any held-out file is opened.

### Amendment 3, 2026-10-16: the designs rehearsed on RNA; PXD061065 moved to reserve

Each held-out design was run through v4.1 on RNA calibration cells, with real
protein mask profiles, before its protocol was written
(`research/notebooks/heldout_rehearsal.py`; run history, entry 39). Five
designs pass the bar their protocol would need. Neutrophils uploaded alone
(PXD061065's design) do not: median best-guess recall was 34.7% with
Fulcher's mask and 52.0% with PBMC240's, against 50% under both. So
PXD061065 leaves the internal test unopened and joins the reserve: it can
serve a future test once an upload of one cell type no longer depends on the
upload's own scaling (run history, entries 35 to 37). Its role is `reserve`
in `scripts/fetch_public_sets.py` and in the download record.

### Amendment 4, 2026-10-16: the held-out test's protocols

The five protein sets (Tian, PXD021882, PXD043355, PXD073250, PXD046211) are
scored under `research/benchmark/protocol-heldout.md`, and Hao 2021's
held-out donors under `research/benchmark/protocol-heldout-hao2021.md`. Both
were committed before any of their files or cells was read, and their intake
and scoring scripts were rehearsed on development data or synthetic files
(run history, entry 42).

### Amendment 5, 2026-10-16: the candidates for the held-out test are final

Phase 2 froze no new candidate (run history, entries 36, 40 and 41), so the
internal held-out test scores v4.1, v4.2 and v5.2 (amendment 2), with v3.1 for
reference. Both protocols carry this as their amendment 1. Unsealing may
begin, each set once, in the protocols' order.

### Amendment 6, 2026-10-16: the internal held-out test is scored and spent

Each set was scored once under its protocol (run history, entry 44). v4.1:
- **Passed:**
  - Hao 2021's held-out donors: +4.73 points over the correlation baseline;
  - PXD043355: AUROC 0.674 of reference similarity, T-cell line over HeLa.
- **Failed:**
  - PXD073250, immune cells over keratinocytes: 0.442;
  - PXD046211, PMA over untreated: 0.517, as predicted.
- **Void:**
  - Tian: one matched pair;
  - PXD021882: no B or T pools in the deposited table.

The sets are now spent. From here on they are development data, and any new
test comes from the alternatives below. Their role in
`scripts/fetch_public_sets.py` stays `held_out` as the record of how they
were assigned and scored.

### Amendment 7, 2026-10-18: the colon reference's data (owner's decisions)

The owner chose to build a second, separate reference for the large
intestine from Tabula Sapiens (`research/organ-references.md`). The blood
roles above are unchanged.

**The search.** It ran on 2026-10-17, reading repository pages and papers
only, with no file opened. It covered:
- PRIDE and ProteomeCentral, MassIVE, jPOST, iProX, the Proteomic Data
  Commons and HTAN;
- the literature.

It found no human colon set of single cells with labels independent of the
protein data. The best are Deep Visual Proteomics pools: cells classified on
stained images, then cut out together.

| Role | Set | What it is |
|---|---|---|
| held_out: the colon's locked test | PXD052341, Post 2025 | Normal colon mucosa, 3 donors: crypt-bottom and upper-crypt epithelium, goblet cells, PDGFR+ fibroblasts, CD45+ immune cells; pools of about 500 cells. Protocol: `research/benchmark/protocol-colon-pxd052341.md` |
| development | PXD057118, Zheng 2025 | One colorectal tumour (and a tonsil tumour). Processed tables exist for its macrophages, CD8 T and CD4 T cells; its other classes are in raw files only (`ColorectalCancer.zip`, 49.5 GB) |
| development | PXD046999, Kabatnik 2024 | FFPE colorectal adenomas: CDX2-high and CDX2-medium epithelium, CDX2-negative stroma; pools of about 100 cells |
| development | The polyp plate | 516 single colon polyp cells × 4,535 proteins; no labels; origin unknown; local only. `drive/Data/scProteomics/Protein_polyps_p2.h5ad` in the project folder, sha256 `da0e99bd7798d9d960cd590551bf2fe5303f642f7ea267bcf2b76ddf2bea7f1e`. The owner allowed full use: derived files may be committed and shown |

- **Locked means what amendment 1 says.** PXD052341's file listing (names and
  sizes) was read to write its protocol, which the rule for local copies
  allows. Its protocol was committed before any of its files was
  downloaded.
- **PXD051891,** Zheng's other accession, is not public.
- **Caveat for any colon report:** the three Deep Visual Proteomics sets come
  from one lab and one chemistry. The locked test is therefore not
  independent of the development data's acquisition.
- **Raw-only data** may be searched with DIA-NN on this PC (owner,
  2026-10-18), with settings fixed before the search.
- **Roles in code:** `scripts/fetch_public_sets.py`, tier C.

### Amendment 8, 2026-10-18: the colon reference closed; PXD052341 stays sealed

The colon reference missed its development gates (run history, entry 52),
and the owner closed it. That decision moves the colon's data as follows:
- **PXD052341 is not scored and stays sealed:** downloaded and checksummed,
  never opened. It stays the locked test for any future colon reference,
  under its protocol, which a new candidate amendment would have to name.
- **Zheng (PXD057118), Kabatnik (PXD046999) and the polyp plate stay
  development.** They were read for the colon's gate G3.
- **Their role in `scripts/fetch_public_sets.py` is unchanged.**

### Amendment 9, 2026-10-18: the lung reference's data (owner's decisions)

The next organ is the lung, from Tabula Sapiens Lung
(`research/organ-references.md`, "Lung").

**The search.** It ran on 2026-10-18, reading repository pages, file listings
and papers only, with no file opened. It covered:
- PRIDE, ProteomeCentral, MassIVE, jPOST, iProX, LungMAP, HuBMAP, PDC and the
  Human Protein Atlas;
- the literature.

It found no human lung single-cell MS set with fine independent labels. The
best are FACS-sorted lineage pools from one PNNL/LungMAP group.

| Role | Set | What it is |
|---|---|---|
| held_out: the lung's locked test | MSV000094189, Ushakumary 2025 | 11 pediatric donors; sequentially sorted CD45+ immune, PECAM1+ endothelial, EpCAM+ epithelial and triple-negative mesenchymal pools. MaxQuant 1.6 MaxLFQ, DDA. Protocol: `research/benchmark/protocol-lung-msv000094189.md` |
| development | MSV000094373, Ushakumary 2025 (BPD) | 5 bronchopulmonary dysplasia and 5 control lungs; sorted EpCAM+ epithelial and CD31+/CD144+ endothelial pools; FragPipe `combined_protein.tsv` |
| development | The Human Protein Atlas DVP atlas (Weiss 2026) | One donor; image-classified pools of 27 cell types from 14 tissues, lung AT1/AT2 among them. `dvp_sample_data.tsv.zip` |
| development | PXD029341, Herrera 2022 | Laser-microdissected IPF and control lung regions (fibroblastic foci, scar, alveoli); MaxQuant `results.zip` |
| reserve | MSV000081973, Kyle 2018 and Du 2019 | 3 donors, the same four sorted lineages; raw files only |

- **Locked means what amendment 1 says.** MSV000094189's MassIVE folder
  listing (names and sizes) was read to write its protocol. Its protocol is
  committed before any of its files is downloaded.
- **Caveat, the owner's choice:** the development set MSV000094373 comes from
  the same lab and biorepository as the locked test and may share donors.
  Its development check can therefore preview the test, and every lung
  report says so.
- **Alternatives, not used:**
  - PXD014762: alveoli against vessels, 3 donors, 6 samples, a group-level
    quant table only;
  - region sets PXD043807, PXD040654, PXD036465 and PXD058805 (PXD058626 became
    v2's fresh lung set, amendment 13);
  - cultured and iPSC-derived lung cells (PXD034135, PXD019240 and others).
- **Roles in code:** `scripts/fetch_public_sets.py`, tier L.

### Amendment 10, 2026-10-18: the lung reference missed its gates; MSV000094189 stays sealed

The lung reference missed two development gates (run history, entry 55).
- **MSV000094189 is not scored and stays sealed:** downloaded and
  checksummed, never opened. Its protocol's rule 1 allows no candidate that
  missed its gates, so it waits for a lung reference that passes.
- **MSV000094373, the Protein Atlas DVP samples and PXD029341** were read for
  G3 and stay development.

### Amendment 11, 2026-10-18: the lymph node reference's data (owner's decisions)

After the lung, the owner chose the lymph node, from Tabula Sapiens Lymph
Node, with the same recipe (`research/organ-references.md`, "Lymph node").

**The search.** It ran on 2026-10-18 over repositories and the literature,
reading pages, file listings and papers only. It found:
- no human lymph node, tonsil or spleen single-cell MS set with independent
  labels;
- no sorted lymph-node stroma.

The usable sets are tonsil micro-regions and sorted B cells.

| Role | Set | What it is |
|---|---|---|
| held_out: the lymph node's locked test | PXD042367, Makhmut 2023 (Coscia lab), its Fig. 4 | 146 tonsil micro-regions from one section: germinal-centre zones, mantle zone, interfollicular T zone and epithelium, annotated on immunofluorescence. Protocol: `research/benchmark/protocol-ln-pxd042367.md` |
| development | PXD047762, Makhmut 2024 (Coscia lab) | Tonsil B-cell, T-cell and epithelial micro-regions; DIA-NN results and a raw-file description |
| development | PXD057118, Zheng 2025, its tonsil tables | Tonsil cancer DVP pools: B, CD8 T, CD4 T, macrophage, plasma and tumour cells (the deposit was already development for the colon) |
| development | The Human Protein Atlas DVP samples | Lymph-node macrophage, CD4 T, CD8 T and B-cell pools from one donor (already development for the lung) |
| development | PXD011683, Duś-Szachniewicz 2021 | CD19+ B cells from reactive lymph-node aspirates and follicular lymphoma; MaxQuant |
| reserve | PXD006191 (Díez 2021, sorted tonsil B subsets; peptide files only), PXD009569 (sorted Treg and Teff from lymph nodes; Mascot files only) | — |

- **Locked means what amendment 1 says.**
- **Caveat, the owner's choice:** PXD047762 comes from the same lab as the
  locked test and may share its tonsils. Its development check can preview
  the test.
- **The locked set is one section of one donor.**
- **Roles in code:** `scripts/fetch_public_sets.py`, tier N.

### Amendment 12, 2026-10-18: the lymph node reference missed its gates; PXD042367 stays sealed

The lymph node reference missed two development gates (run history, entry
57): Zheng's tonsil pools and PXD011683.
- **PXD042367 is not scored and stays sealed:** downloaded and checksummed,
  never opened. Its protocol's rule 1 allows no candidate that missed its
  gates, so it waits for a lymph node reference that passes.
- **PXD047762, Zheng's tonsil tables, the Protein Atlas lymph-node pools and
  PXD011683** were read for G3 and stay development.

### Amendment 13, 2026-10-19: fresh development sets for the organ references' v2 (owner's decisions)

The v2 diagnostics (`research/organ-references.md`, "Version 2") read every
v1 development set again, so those sets are now **seen**. The owner
(2026-10-18) chose to judge v2 on sets never read before. The search ran on
2026-10-18 over repositories and the literature, reading pages, file
listings and papers only. Its report is summarised here.

| Organ | Role | Set | What it is |
|---|---|---|---|
| Lymph node | development, fresh | PXD045043 (jPOST JPST002191), Kitata 2025 (PNNL) | Normal human spleen from one donor: red-pulp and white-pulp voxels of 20 to 200 µm, picked by eye before any MS (labels in the raw-file names). DIA-NN results (`Report_DIA-NN_Spleen.zip`). The 42-voxel map is excluded: its region calls came from the protein data. |
| Lung | development, fresh | PXD058626, Herrera 2025 | Laser-captured lung regions on H&E, confirmed by a pathologist: 12 non-fibrotic control airways and 12 control alveoli (paired by donor), plus IPF regions. A FragPipe table (`combined_protein.tsv`) with its annotation. Same lab leader as the seen PXD029341; different samples. |
| Colon | reserve | PXD069723 (Adv Sci 2026) | Colon wall of 4 patients: enteric nervous system against muscle layers, 24 runs, with DIA-NN results. It is kept unread for the next colon candidate, because no colon v2 is built: A2 and A4's rules stop it (no label-free band key). |

- **Seen sets.** The v1 development sets of all three organs stay
  development, marked seen. The v2 diagnostics used them to choose
  settings, so they no longer carry a gate.
- **Locked tests.** PXD052341, MSV000094189 and PXD042367 are unchanged and
  sealed.
- **Searched, not usable now:**
  - PXD046567 (colon; iProX unreachable from this PC, raw only);
  - PXD043807 (COVID lungs; raw only);
  - PXD069877 (tonsil T zones; the locked set's lab);
  - PXD006191 and PXD009569 (lymph-node reserves; raw only).
- **Data requests worth making:** PSPro (Tian lab), the Castleman niches,
  the Schiller COPD data, and the label maps of PXD040654 and PXD046176.
- **Roles in code:** `scripts/fetch_public_sets.py`, tier V.

### Amendment 14, 2026-10-19: the organ references' v2 candidates and their gates

The v2 plan is `research/organ-references.md`, "Version 2".
- **Candidates:** "lymph_node v2" (`scripts/organs/lymph_node_v2.json`)
  and "lung v2" (`scripts/organs/lung_v2.json`). No colon v2 is built: the
  diagnostics A2 and A4 stop it.
- **G1 is split** (the owner's decision of 2026-10-18). Mixed uploads carry
  the four bars; narrow uploads only the 90% safety bar.
- **G3 runs on amendment 13's fresh sets:** PXD045043 (lymph node) and
  PXD058626 (lung). The v1 development sets are seen and reported only.
- **The locked tests are unchanged and sealed.** PXD042367 and
  MSV000094189 are each unsealed only if its organ's v2 passes, then scored
  once under its protocol's amendment 1. PXD052341 stays sealed.

### Amendment 15, 2026-10-21: the v2 gate runs read both fresh sets

The lymph node v2 and lung v2 each ran their gates once on 2026-10-20
(`research/organ-references.md`, both v2 outcomes). Both are NO GO.
- **PXD045043** (spleen) and **PXD058626** (lung regions) have now been
  read. They are development, marked seen: a later candidate's G3 cannot
  count on them as fresh, unless the owner decides otherwise for a change
  that cannot move its G3 score (organ-references, "Options for a v3").
- **PXD069723** (colon) stays reserved and unread.
- **The locked tests** PXD042367, MSV000094189 and PXD052341 are unchanged
  and sealed.

### Amendment 16, 2026-10-21: the lymph node v3 candidate (the owner's go-ahead)

The owner chose to build a lymph node v3 (2026-10-21):
`research/organ-references.md`, "Version 3: the lymph node".
- **Candidate:** "lymph_node v3" (`scripts/organs/lymph_node_v3.json`):
  v2's members and calibration suite, with v1's calibration rule (no chance
  floor), and a new evaluation suite.
- **G3 reuses PXD045043**, already read for v2 (amendment 15). The owner
  allowed it: v3's change cannot move its score, which comes from the fused
  best guess, and v3 keeps v2's temperatures.
- **The locked test PXD042367 stays sealed.** If v3 passes its gates, it is
  frozen (the protocol's amendment 6), and the owner is asked before the set
  is opened. MSV000094189 and PXD052341 are unchanged and sealed.

### Amendment 17, 2026-10-21: the lymph node v3 missed; PXD042367 stays sealed

The lymph node v3 ran its gates once (run history entry 62): NO GO, by 0.01
points (narrow uploads 89.99% correct when committed, bar 90). PXD045043 was
read a third time (G3 0.9172, unchanged). PXD042367 is not opened and stays
sealed; MSV000094189 and PXD052341 are unchanged and sealed.

### Amendment 18, 2026-10-21: the pooled blood candidate v5.3 (the owner's go-ahead)

The owner chose to build a pooled blood candidate (2026-10-21), although the
blood_pools diagnostic's fixed reading said "not promising" (run history
entry 61). That reading stands; v5.3 is a new candidate with its own gates.
- **Candidate:** v5.3, v4.1's rule on five V2 members trained with RNA pools
  added to the training rows (the diagnostic's pools), on the original
  labels (`research/notebooks/v5_train.py clean --variant v5.3`;
  `research/notebooks/v5_build.py build --variant v5.3`).
- **Gates,** fixed in `research/notebooks/v53_gates.py` before training, on
  development data only: Fulcher at least v4.1 + 2; PBMC240 lymphoid recall
  at least v4.1 - 2; Fulcher committed at least v4.1 - 2 and correct when
  committed at least v4.1 - 1; out-of-reference AUROC at least v4.1 - 0.03.
  SCoPE2 is reported, as development data.
- **Not served either way.** The held-out protein sets are spent; a GO makes
  v5.3 a frozen candidate for the sorted CD4/CD8 test, by that protocol's
  next amendment. The simulated evaluation suite's `te_eval` cells are not
  used (they would be on their sixth use).
- **Outcome, 2026-10-21: development gates missed** (run history entry
  63). Fulcher 69.39 (bar 71.05), PBMC240 lymphoid recall 87.18 (bar
  90.31), answers committed 85.69 and correct when committed 95.43 (bars
  86.57 and 96.93); only the out-of-reference AUROC passed (0.7985). v5.3
  stays refused and is not a sorted-test candidate.

### Alternatives kept unused, for future tests or future development

Nothing below has been downloaded or opened, so each can still serve as a
future test; once a test is used, it becomes development and the next one
comes from here. Keep this list current.

- **Downloaded, sealed, in reserve:** PXD061065 (277 single glioblastoma
  neutrophils after QC; amendment 3).
- **Requested by email:** Krisp et al. (sorted CD4, CD8, CD19, CD14 single
  cells; the main test) and O'Connor et al. (sorted T, B, NK, monocytes).
- **Data requests not yet made:** Brenes et al. (sorted blood neutrophils) and
  Lange et al. (CD19-sorted B cells).
- **Embargoed or restricted, to re-check:** PXD084266, PXD080834, PXD076177,
  the HUPO inter-lab benchmark (Zenodo 21181080). Re-checked 2026-10-20:
  PRIDE still answers 404 for all three PXDs, and the Zenodo record is still
  restricted, with no files listed.
- **Public, not downloaded:**
  - PXD070599's single HeLa and HEK293T (tier B, 24 GB; role `reserve` in
    `scripts/fetch_public_sets.py`);
  - PXD070599's empty-well runs beside DS18 and DS19, 8 per run set, 32 in
    all (raw files only, searched into none of the deposited matrices; they
    need a DIA-NN search). Development, not a test: they would settle
    whether the platelet and red-cell proteins in every Astral well are
    shared material (run history, entry 38);
  - MSV000093867 (HEK293T and THP-1 ± LPS, raw only);
  - PXD026604 (sorted monocyte subsets, 31 GB `.msf`);
  - MSV000097303 (CD14+/CD19+/CD3+ pools, surfaceome), PXD076140 (PBMC
    subsets by CD14), MSV000093644 (CD4, CD8, NK, B library);
  - cell-line sets MSV000097281, MSV000090792, MSV000102108, PXD070341,
    PXD054944, PXD070012, PXD036211;
  - Hao 2021's ADT matrix and its 5' dataset (GEO GSE164378);
  - the unverified Peking University iProX leads PXD064083 and PXD049099.
- **Colon (amendment 7), public, not downloaded:**
  - PXD052341's raw archives named scDVP: in vivo 754 GB; organoid 353 GB
    and 341 GB. They may hold single cells, and need a DIA-NN search. They
    are the same donors as the locked test.
  - PXD073051 (iProX): CD8 T cells microdissected from 3 colon cancers; T
    cells only.
  - PXD046176: microdissected epithelium and stroma of normal mucosa,
    adenoma and carcinoma; 22 patients.
  - PXD036591: small intestine in Crohn's disease, FACS EpCAM+, CD45+ and
    double-negative.
  - **Searched again 2026-10-21** (PRIDE, ProteomeCentral across its members,
    MassIVE, PDC, HuBMAP, Zenodo, figshare and the 2023 to 2026 literature;
    iProX-only projects not reached). Nothing new can gate a colon reference:
    no public set has independently labelled colon cell types beyond the
    locked test. Found, none downloaded:
    - PXD050335 (Crohn's colon resections): mucosa against submucosa/wall,
      by dissection; 52 label-free runs (17 of them from non-IBD resections),
      as two separate MaxQuant searches. Two compartments only;
    - PXD041366 (iProX): MACS-sorted CD4 and CD8 T cells from colorectal
      tumours and distant normal tissue, 13 patients, TMT. T cells only;
    - PXD073004 and PXD073053: laser-microdissected submucosa and muscularis
      of the ileum (Crohn's strictures and controls). Small intestine;
    - an LCM study of four cell types from one colon tumour and its normal
      tissue (Anal Chem 2018), in its supporting tables only. One donor.
  - **Leads, no public data yet:** a DVP atlas of 27 cell types in 14
    tissues (bioRxiv 2026, data on publication; the colon is not among its
    DVP tissues); an LCM study of lymphoid structures in colorectal cancer
    (Oncogene 2026, no accession); FACS-sorted colon epithelial populations
    from 7 patients shown at HUPO 2024 (no paper; a data request could be
    made).

## What counts as a side test

- A public proteomics dataset whose labels for the question at hand do not
  come from clustering or annotating the same protein data.
- It answers ONE question: a weak class, or whether the model declines cells
  its reference does not contain.
- It gets its own pre-registered protocol before any label is opened, modelled
  on the sorted CD4/CD8 protocol, and is scored once.
- It is reported as a side test, never as a headline result. Every report
  states the caveats below: cell lines and tissue cells are outside the blood
  reference's domain; most deposits use different acquisition than the
  reference's protein data (TMT or DDA, for instance).
- Check label provenance every time. PRIDE's community-made SDRFs are often
  wrong (PXD043355, PXD021882, and PXD070599 by the authors' own account).

## Single-cell candidates (file listings read on 2026-10-14)

| Accession | Cells and labels | Question | Caveats |
|---|---|---|---|
| PXD070599 (Hendriks, Olsen) | Hundreds of single HeLa cells (datasets DS12 to DS16) and 52 HEK293T. The cell type is in the raw-file name and in `DataSet_to_rawfile_mapping_methods.txt`. DIA-NN output is deposited. | Abstention | The PRIDE SDRF is declared wrong by the authors. A matched PBMC run (DS18) exists on the same instrument and method but on another day, and its labels come from clustering, so only HeLa and HEK are used. |
| PXD043355 | 30 single Jurkat and 24 single HeLa cells; labels in file names | Abstention; a T-cell line | The PRIDE SDRF is wrong; acquisition mode not verified. |
| PXD020586 (Schoof 2021); MassIVE MSV000090570 | OCI-AML8227 leukaemia culture, 3,432 single cells in four CD34/CD38 gates (blasts, progenitors, stem-like). Per-cell index-sort values are deposited, inside `SCeptre_FINAL.zip` (981 MB). | HSC-like vs progenitor vs blast | The best-documented independent labels, but TMT with DDA and leukaemic. The MassIVE copy has no raw files. |
| PXD073250 | Skin tumour, 419 single cells: 204 CD45+/CD74+ (immune), 176 CD45-/CD200+ (keratinocyte), 39 headed CD45+/CD200+ | Immune vs non-immune; abstention on keratinocytes | Only the sort gate is independent. DC, macrophage and monocyte labels come from clustering the protein data plus an AI-assisted naming step, and per-cell FACS values are not deposited, so it is NOT a DC-vs-macrophage test. The cell-to-file map is in the paper's Supplemental Data 1. Plate partly confounds the groups. |
| PXD061065 | 330 single glioblastoma neutrophils sorted as CD45+CD66b+CD49d-; 277 after QC | Neutrophil recall | One class only, so precision cannot be tested; brain tissue. |
| PXD046211 (Gregoire 2023); Zenodo 8417228 | THP-1 and U-937, with and without PMA, 372 single cells; per-channel labels | Monocyte vs macrophage-like | Cell lines; TMTpro with DDA and a 50-cell carrier. |
| MSV000099294 (PNNL) | 47 post-mortem human brain microglia (CD11b+/CD45+ FACS) and 46 HMC3 cell-line cells | Does a macrophage-like type absent from the reference map to macrophage or abstain? Does the cell line abstain? | The microglia raw files are not in the deposit; only a Spectronaut report with 57 per-cell columns is. |
| MSV000093867 (Ctortecka 2024) | HEK293T and THP-1 single cells, THP-1 with and without LPS; 8,128 files | Monocyte-like vs non-immune | Raw only; labels inferred from file names. |

More cell-line abstention sets exist (MSV000097281, MSV000090792, MSV000102108, PXD077946, PXD070341, PXD054944, PXD070012, PXD036211), judged from titles and descriptions only.

## Population-level candidates (pools, not single cells)

- **Khoury's bulk sorted populations**: `Bulk_R1_LibGen_Global.zip` in
  Zenodo 22649483 (577 MB, CC-BY): a DIA-NN report for FACS-isolated paired
  populations of the five cell types, at least 2 samples per type according
  to the authors' code. Downloaded (see "Local copies"). It could also test
  whether Khoury's single-cell "CD8" cluster looks like sorted CD8 cells.
- **MSV000087462 = iProX PXD049159** (Tian lab): 8 FACS-sorted T-cell
  subtypes from 5 myeloma patients, including CD4 and CD8 naive and memory
  (70 to 500 ng of lysate per subtype). The best public bulk reference for
  CD4 against CD8 naive; patient cells.
- PXD026604 (sorted classical, intermediate and non-classical monocytes,
  2,500 or 50,000 cells per sample); PXD021882 (B vs T pools of about 145
  cells); PXD061052 (500-cell neutrophil pools); MSV000097303 (500-cell
  CD14+/CD19+/CD3+ pools, surfaceome only); PXD076140 (PBMC subsets graded
  by CD14, cell numbers not verified); MSV000093644 (a bulk spectral library
  of CD4, CD8, NK and B cells).

## Local copies (downloaded 2026-10-14)

`scripts/fetch_public_sets.py` fetched the processed outputs of the sets
above into `data/incoming/public_sets/<group>/` (gitignored). Every file's
size was checked against the server's, 18 files also against a published
checksum, and every file's sha256 is in
`research/benchmark/public-sets-downloads.json`. No raw instrument files were
fetched. Each group has one role, fixed in the script's table:

| Role | Groups | Size | Use |
|---|---|---|---|
| Role (since amendment 1) | Groups | Use |
|---|---|---|
| reference | Rieckmann 2017 (PXD004352: 28 sorted primary immune populations, MaxQuant output); Khoury's sorted bulk populations | Rieckmann: free for development. Khoury's: diagnosis only (see below) |
| development | PXD070599 PBMC runs DS18 and DS19, MSV000099294, PXD077946, PXD061052, PXD020586 | Free for development |
| held_out | Tian (MSV000087462), PXD046211, PXD043355, PXD073250, PXD021882 | The internal test: locked until the end (amendment 1) |
| reserve | PXD061065 (sealed, amendment 3); PXD070599 single HeLa and HEK293T (tier B, not downloaded) | A future test or future development |

- **Locked means:** downloaded and checksummed, nothing else, until scoring.
  Listing file names and checking file sizes are allowed.
- **Khoury's bulk file is diagnosis only.** Khoury 2026 is a post-hoc study
  and its single cells are already used up for the CD8 diagnosis. The bulk
  file may be used to ask what Khoury's own "CD8" cluster is. It is never
  used to build a reference, a class mean or any setting of a model, and a
  result from it is not a test of the model.
- **A set changes role only by amendment,** dated and committed before the
  change takes effect. A set once used to develop or diagnose cannot become a
  test afterwards.
- **Not downloaded:** PXD070599's single HeLa and HEK293T search outputs
  (tier B, 24 GB; they repeat what the smaller abstention sets give);
  PXD026604 (31 GB `.msf` only); MSV000093867 (raw only); Zenodo 8417228's
  large files; Rieckmann's supernatant zips.
- **Resuming:** `python scripts/fetch_public_sets.py` skips complete files and
  continues partial ones. With 16 connections Zenodo closed one connection
  in the end; 4 connections finished it.

## Not public yet

- **Krisp et al. (Bruker, Cellenion, CISTAR)**: FACS-presorted CD4+, CD8+,
  CD19+ and CD14+ cells as single cells and 10-cell bulks, plus 48 unsorted
  PBMCs. Shown at six venues since February 2024 and never deposited. The
  only CD4-vs-CD8 single-cell design found; the main test.
- **O'Connor et al. (TGen)**: negative-selection magnetic sorting into T, B,
  NK and monocytes (T cells are pan-T). About 1,540 sorted single cells. The
  preprint has no data statement and one version. A lineage-level test, not
  CD4 against CD8.
- **Brenes et al.** (FACS-sorted blood neutrophils, bioRxiv
  10.64898/2026.06.12.731618) and **Lange et al.** (CD19-sorted B cells,
  10.64898/2026.08.27.747627): no accession, so data requests.
- Embargoed or restricted, to re-check in a few weeks: PXD084266, PXD080834,
  PXD076177, and the HUPO inter-lab benchmark (Zenodo 21181080, restricted).

## Leads not verified

- PXD064083 and PXD049099 (Peking University, iProX): single T and B cells
  by file name, no CD4/CD8 split. iProX could not be reached from this PC, so
  neither was opened.

## Nothing found for

- DC against macrophage with independent labels.
- A public set of single cells with sorted CD4 and CD8 labels.

## Coverage and gaps of the 2026-10-14 search

- **Covered:** PRIDE's whole project list (42,027 projects, to 2026-10-12);
  MassIVE's whole list (20,376 datasets); the other ProteomeXchange members
  through its API records; Zenodo, Figshare, OSF, Dryad and GitHub; the
  Bioconductor `scpdata` index; Europe PMC and PubMed, with citation chains
  of the main single-cell papers; lab pages, conference abstracts and vendor
  notes.
- **Gaps:**
  - Mendeley Data cannot be searched anonymously.
  - iProX and the jPOST file lists could not be opened.
  - The bioRxiv scan covered only four categories for September and October
    2026.
  - The HUPO 2024 programme, several abstract books and science.org were
    blocked.
  - The primary CD8 T-cell paper in a Chinese journal (reported to use
    cellenONE sorting on a timsTOF Ultra 2) could not be reached: it is a
    search-snippet only, with no accession.
- Fulcher 2026 is PXD073881 = MSV000100684; MSV000100682 and MSV000100683 are
  its library and optimisation sets.
