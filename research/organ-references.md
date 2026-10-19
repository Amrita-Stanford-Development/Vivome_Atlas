# Organ references: the large intestine first

Planned 2026-10-17 and 2026-10-18 with the owner; Track I in
`research/todo.md`. Where this conflicts with older plans, this file wins for
organ work.

**Status, 2026-10-18:**
- **The large intestine is closed, NO GO as built.** The owner's decision:
  document every failure and move to the next organ. "The large intestine's
  outcome" lists them all.
- **The lung missed narrowly, NO GO as built.** G1 committed 73.4% against
  75%, and G3's LungMAP check gave AUROC 0.62 against 0.8. See "The lung's
  outcome".
- The rest of this file is the plan as it was run.

## Why

Instead of only chasing blood's weak classes, VivOME widens to other organs.
As far as we know, no tool labels single-cell proteomics against an RNA
reference outside blood. VivOME's encoders learn from RNA alone, so an organ
needs:
- an RNA atlas;
- a reference built from it;
- whatever protein data with independent labels exists for that organ.

**The claim this can support:** the method extends to a second organ from
RNA alone. It rests on:
- measured RNA-side numbers;
- development checks on pooled protein profiles;
- one locked test on pooled profiles.

Colon accuracy on single protein cells stays Pending (the manifest rule).

## Owner's decisions

1. **Separate references.** Blood v4.1 stays exactly as served: not retrained
   and not re-validated. Mixing tissue cells into the blood reference lowered
   blood scores (`research/notebook-run-history.md`, entry 20).
2. **First organ: the large intestine**, from Tabula Sapiens Large Intestine
   only. HTAN's polyp RNA may come later. The atlas is
   `Large_Intestine_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad`, in
   the project Drive's `scRNA-seq` folder:
   - 30,084 cells from 5 donors, 29 `cell_ontology_class` values;
   - compartments: immune 16,560, epithelium 9,649, stroma 2,679, glia 848,
     endothelium 348.
3. **Protein data roles** are in `research/benchmark/side-tests.md`,
   amendment 7:
   - **Locked test:** PXD052341 (Post 2025, normal colon), protocol
     `research/benchmark/protocol-colon-pxd052341.md`.
   - **Development:** PXD057118 (Zheng 2025), PXD046999 (Kabatnik 2024) and
     the unlabelled polyp plate (516 cells).
4. **The polyp plate is used fully.** Its genes join the gene list and its
   detection pattern shapes the simulated uploads. Files derived from it may
   be committed and shown.
5. **Raw-only deposits** may be searched with DIA-NN on this PC, with
   settings fixed before the search.
6. **The aim (2026-10-18): every organ of Tabula Sapiens.** Tabula Sapiens
   v2 has 28 organs (`web/data/organs/tabula_sapiens.json`, from its
   Figshare record). The site presents VivOME as a growing atlas: blood labels
   files, built organs are maps, the rest are to build (the manifest's
   `organs`).

## Lung (the second organ, from 2026-10-18)

**The owner's decisions:**
- After the colon closed, lung is next, from Tabula Sapiens Lung only.
- The recipe is unchanged, and so are the gates.
- **Data roles,** in `research/benchmark/side-tests.md`, amendment 9:
  - **Locked test:** MSV000094189, 11 pediatric donors × 4 sorted lineages.
    Protocol: `research/benchmark/protocol-lung-msv000094189.md`.
  - **Development:**
    - MSV000094373 (sorted epithelium and endothelium, BPD and control; the
      same lab, possibly the same donors);
    - the Human Protein Atlas DVP pools (AT1/AT2 among 27 cell types);
    - PXD029341 (IPF and control regions).
  - **Reserve:** MSV000081973.

**The atlas:**
- 65,847 cells from 4 donors;
- immune 29,636, epithelium 22,779, endothelium 10,648, stroma 2,784.
- It mixes lineages as whole tissue, the case the colon's best guess handled
  well.

**Classes** (`scripts/organs/lung.json`; the colon's class rule):
- **Six classes fail the rule** and have no kept ancestor among the classes,
  so they are dropped (113 cells): myeloid and plasmacytoid dendritic cells,
  mast cells, pulmonary ionocytes, bronchial serous cells, mesothelial cells.
- **28 classes,** in four lineages:

  | Lineage | Group | Classes |
  |---|---|---|
  | epithelial | alveolar | AT1, AT2 |
  | epithelial | airway | basal, club, ciliated, goblet |
  | endothelial | blood vessel | capillary, artery, vein |
  | endothelial | lymphatic | lymphatic |
  | stromal | fibroblast | alveolar fibroblast, adventitial |
  | stromal | smooth muscle/pericyte | pericyte, bronchial and vascular smooth muscle |
  | immune | T/NK | CD4 T, CD8 T, NK, NK T |
  | immune | B | B cell, plasma cell |
  | immune | monocyte/macrophage | macrophage, three monocyte subsets, generic monocyte |
  | immune | granulocyte | basophil, neutrophil |

**Label audit** (`research/notebooks/organ_labels.py lung`, run 2026-10-18;
`research/notebook-outputs/lung_labels/`):
- **Most classes express their own markers in every donor:**
  - AT2 98 to 99%;
  - lymphatic endothelium 82 to 90%;
  - intermediate monocytes 90 to 96%;
  - basophils 64 to 71% (genuine basophils).
- **Four class–donor groups stand out:**
  - TSP14's club and adventitial cells carry strong AT2 (surfactant) signal,
    likely ambient RNA;
  - the generic "monocyte" class is mixed, as it was in blood;
  - TSP2's arterial cells look venous;
  - goblet cells look club-like.
- **Each doubt stays within its group,** where the answer layer can fall
  back. No class is wrong in every donor, so nothing more is dropped.

**Gates, fixed before any lung model exists.** G1, G2 and G4 are the colon's.
G3 uses the lung's development data:
- **MSV000094373:** AUROC ≥ 0.8 of P(epithelial lineage), epithelial pools
  over endothelial pools.
- **The Human Protein Atlas DVP samples,** uploaded together (every tissue,
  so the upload is mixed):
  - if AT1 and AT2 are separate: AUROC ≥ 0.8 of P(AT2) − P(AT1), AT2 pools
    over AT1 pools;
  - if they are merged: at least 80% of the lung pools with epithelial as
    the argmax lineage.
- **PXD029341:** AUROC ≥ 0.7 of P(stromal lineage), fibroblastic-focus
  regions over alveolar regions.

The wording may be fixed to a deposit's real layout by a dated note before
the lung model is built, never after.

**Note, 2026-10-18: G3 against the deposits as fetched,** before the lung
model:
- MSV000094373's 20 pools are named `_Epi_` and `_Endo_`;
- the Protein Atlas keeps AT1 and AT2 apart (5 pools each), so the AUROC
  form holds;
- PXD029341's 25 regions are named `FF`, `MtrScr` and `NmlAlv`/`NmAlv`.

The lung's gene space takes the Protein Atlas proteins only where they are
detected in pools of cell types this reference holds (its table lists every
gene): 12,614 genes.

### The lung's outcome (2026-10-18): NO GO as built, narrowly

Run history, entry 55. Records: `research/notebook-outputs/lung_build/`,
`lung_development/`, `lung_donor_heldout/`.

**The model:**
- 28 classes and 12,614 genes;
- five members at 72 to 75% validation balanced accuracy (colon 63%, blood
  66%);
- calibration top-1 60.5%;
- marginal conformal threshold 0.961 (colon 0.987, blood 0.91).

| Gate | Result | Bar | Verdict |
|---|---|---|---|
| G1, simulated lung uploads: committed | 73.4% | ≥ 75% | **miss** |
| G1: correct when committed | 97.4% | ≥ 90% | pass |
| G1: coverage | 90.3% | ≥ 85% | pass |
| G1: false abstention | 0.01% | ≤ 2% | pass |
| G3, MSV000094373: epithelial over endothelial pools | AUROC 0.62 | ≥ 0.8 | **miss** |
| G3, the Protein Atlas: AT2 over AT1 pools | AUROC 1.0 | ≥ 0.8 | pass |
| G3, PXD029341: fibroblastic foci over alveoli | AUROC 0.88 | ≥ 0.7 | pass |
| G4, the locked test's rehearsal | runs end to end | runs | pass |
| G2, one donor held out (a diagnosis) | 68.4 unseen, 72.1 seen | reported | gap 3.7 (colon 12.5, blood 9.8) |

**What the results show:**
- **Whole-tissue uploads work.** They commit 99.1% of cells, with a best
  guess of 81.9%.
- **Narrow uploads stay weak, the colon's cause in milder form.**
  Single-class uploads commit 31.6% and lineage-only uploads 55.7%. They pull
  the overall rate just under the bar.
- **MSV000094373: 4 of the 5 control donors' epithelial pools are called
  macrophage** (corrected 2026-10-19; it said 4 of 4), mostly at class level. The BPD donors'
  epithelial pools are mostly called epithelial, and the endothelial pools
  are mostly right (7 of 10).
  - Whether those control EpCAM+ sorts carry macrophage material cannot be
    told from here.
  - The upload holds only two lineages.
- **The Protein Atlas:** every AT1 pool's argmax lineage is immune, yet AT2
  over AT1 separates perfectly. The heart's capillary pools are called
  stromal.
- **Across donors the encoder holds up:** group recall is 94.2 unseen
  against 98.3 seen, and lineage recall 97.9 against 99.7.

**What stays:**
- **MSV000094189 stays sealed** (`side-tests.md`, amendment 10). Its
  protocol's rule 1 allows no candidate that missed its gates.
- The lung's work folder and bundle stay on Drive
  (`drive/Data/Results/Organs/lung/`).

## Lymph node (the third organ, from 2026-10-18)

**The owner's decisions:**
- After the lung's narrow miss, the lymph node is next, from Tabula Sapiens
  Lymph Node only.
- The recipe and the gates are unchanged.
- **Data roles,** in `side-tests.md`, amendment 11:
  - **Locked test:** PXD042367's tonsil niches (one section, 146
    micro-regions). Protocol: `research/benchmark/protocol-ln-pxd042367.md`.
  - **Development:** PXD047762 (the same lab's tonsil micro-regions; the
    owner's choice despite the shared lab), Zheng's tonsil pools, the
    Protein Atlas lymph-node pools, and PXD011683's lymph-node B cells.

**The atlas:** 129,062 cells from 6 donors, 99.8% immune.

**Classes** (`scripts/organs/lymph_node.json`):
- **The class rule drops three classes** (70 cells): erythrocytes,
  plasmacytoid dendritic cells and hematopoietic precursors.
- **The label audit** (`research/notebooks/organ_labels.py lymph_node`;
  `research/notebook-outputs/lymph_node_labels/`):
  - **the "thymocytes" are mature T cells.** 181 cells, nearly all TSP7, with
    CD1A, RAG1 and DNTT at 0% and CD3E at 100%. They are merged into CD4 T
    and CD8 T.
  - **the generic "monocyte" class is dropped** (766 cells). It expresses
    CD14, FCN1 and LYZ in only 9 to 32% of its cells, and resembles T cells or
    endothelium in four of six donors.
  - **the generic "T cell" class and the ILCs are weak but lymphoid.** They
    stay, and the answer layer can fall back to their group.
- **The result: 19 classes** under blood's lineages, lymphoid and myeloid,
  plus stromal.
- **Simulated uploads** use blood's three real protein profiles, computed
  over the lymph node's gene space. Its cells are immune, so they are not
  rank-transferred.

**Gates, fixed before any lymph node model.** G1, G2 and G4 are the colon's.
G3:
- **PXD047762's micro-regions:** AUROC ≥ 0.8 of P(B cell group) − P(T cell
  group), B-cell regions over T-cell regions.
- **Zheng's tonsil pools,** as one upload: at least 80% of the B, CD8 T,
  CD4 T, macrophage and plasma pools get their group as the argmax:
  - B and plasma pools: B cell;
  - CD8 T and CD4 T pools: T cell;
  - macrophage pools: monocyte/macrophage.

  Tumour pools are uploaded but not scored.
- **The Protein Atlas samples,** all in one upload: at least 80% of the
  lymph-node macrophage, CD4 T, CD8 T and B-cell pools get their group as
  the argmax.
- **PXD011683:** at least 80% of the reactive lymph-node (control) B-cell
  samples get the B cell group as the argmax. Lymphoma samples are uploaded
  but not scored. (Superseded by the note below: the groups are not
  documented, so every sample counts.)

The wording may be fixed to a deposit's real layout by a dated note before
the model, never after.

**Note, 2026-10-18: G3 against the deposits as fetched,** before the lymph
node model:
- **PXD047762:** the tonsil experiment is its Fig. 3 table (14 regions: B1 to
  B6 without B3, T1 to T6 without T5, and 4 epithelium regions). The check is
  the 5 B-cell regions over the 5 T-cell regions.
- **Zheng's six tonsil tables** carry UniProt accessions ("Protein") and log2
  values, one table per population. They are read as one upload, resolved by
  the lymph node's identifier map.
- **PXD011683:**
  - its 45 samples are named C, D and F (15 each), and neither the deposit
    nor the abstract says which group is the control;
  - every sample is a CD19+ magnetically enriched B-cell sample, normal or
    lymphoma.
  - So the gate counts every sample: at least 80% with the B cell group as
    the argmax.

**Gene space:** the base six sources, plus:
- Zheng's colorectal table (the tonsil tables give accessions, not symbols);
- the Protein Atlas proteins detected in the cell types this reference holds;
- PXD047762's Fig. 3;
- PXD011683.

### The lymph node's outcome (2026-10-18): NO GO as built

Run history, entry 57. Records: `research/notebook-outputs/lymph_node_build/`,
`lymph_node_development/`, `lymph_node_donor_heldout/`.

**The model:**
- 19 classes and 12,668 genes;
- five members at 69.8 to 72.5% validation balanced accuracy;
- calibration top-1 60.5%;
- marginal conformal threshold 0.923 (lung 0.961, colon 0.987, blood 0.91).

| Gate | Result | Bar | Verdict |
|---|---|---|---|
| G1, simulated lymph node uploads: committed | 84.4% | ≥ 75% | pass |
| G1: correct when committed | 95.5% | ≥ 90% | pass |
| G1: coverage | 89.2% | ≥ 85% | pass |
| G1: false abstention | 0.65% | ≤ 2% | pass |
| G3, PXD047762's Fig. 3: B-cell over T-cell regions | AUROC 1.0 | ≥ 0.8 | pass |
| G3, Zheng's tonsil pools: group as the argmax | 41.0% (16 of 39) | ≥ 80% | **miss** |
| G3, the Protein Atlas lymph-node pools: group as the argmax | 100% (20 of 20) | ≥ 80% | pass |
| G3, PXD011683: B cell as the argmax group | 71.1% (32 of 45) | ≥ 80% | **miss** |
| G4, the locked test's rehearsal | runs end to end | runs | pass |
| G2, one donor held out (a diagnosis) | 53.7 unseen, 57.2 seen | reported | gap 3.5 (lung 3.7, colon 12.5, blood 9.8) |

**What the results show:**
- **The first organ to pass G1, narrow uploads included.** One-class
  uploads commit 86.8% and one-lineage uploads 79.3% (lung 31.6% and 55.7%).
  Whole-tissue uploads commit 90.2%, with a best guess of 74.9%.
  - The colon's and the lung's cause does not show here.
  - One difference: the lymph node's simulated uploads use blood's real
    protein profiles as measured, where the colon and the lung used them
    rank-transferred. Whether that explains it was not tested.
- **Rare myeloid cells are named but seldom answered.** The best guess names
  94% of neutrophils, 81% of macrophages and 80% of mast cells. The answer
  layer commits on only 9 to 12% of them, and is right at the stated level
  for 4.7%, 5.7% and 0.1% of all of them.
  - B, T, NK and plasma cells are right for 83 to 97%.
  - The atlas holds 54,746 B cells against 1,794 macrophages, 303
    neutrophils and 212 mast cells.
- **Zheng's tonsil pools: a plasma-cell sink.** In the one upload of 48
  pools, 44 are guessed plasma cell: every B, plasma, macrophage and tumour
  pool, 5 of 6 CD4 T and 12 of 15 CD8 T pools. Only 4 of the 21 T-cell pools
  get the T cell group.
- **PXD047762: perfect ranking, a wrong name for epithelium.** B-cell
  regions rank above T-cell regions (AUROC 1.0), but all 4 epithelium
  regions are called plasma cell at class level, not refused. The reference
  holds no epithelial class, and the out-of-distribution score does not flag
  these regions.
- **PXD011683:** sample group F has 15 of 15 called B cell, D 10 of 15 and C
  7 of 15; the rest are called T cell. Which group is the control is not
  documented, so the gate counted every sample, as the note above fixed.
- **The Protein Atlas:** all 20 lymph-node macrophage, CD4 T, CD8 T and
  B-cell pools are called by their group.
- **Across donors the encoder holds up:** group recall is 89.9 unseen
  against 93.4 seen, and lineage recall 96.6 against 97.3.
- **The rehearsal (G4):** the RNA pseudobulk T-zone regions are abstained
  on 8 of 12 times, while every B-zone region is answered.

**The maps on the site** (owner, 2026-10-18): the three organs' maps are
shown on the Atlas page without labelling (`web/data/organs/`,
`docs/web/atlas.md`, "Other organs").

**What stays:**
- **PXD042367 stays sealed** (`side-tests.md`, amendment 12). Its
  protocol's rule 1 allows no candidate that missed its gates.
- The lymph node's work folder and bundle stay on Drive
  (`drive/Data/Results/Organs/lymph_node/`).

## Version 2: correcting the organs (from 2026-10-18)

The owner asked to correct the three organs. The plan explored every
failure, tested each suspected cause with a diagnostic committed before its
run, and builds v2 candidates only from what the diagnostics support.

**The owner's decisions (2026-10-18):**
- **G1 is split.** Mixed uploads (at least 3 classes spanning at least 2
  lineages, or a whole tissue) must meet G1's four bars. Narrow uploads (one
  or two classes, or one lineage) must only be safe: correct when committed
  at least 90%. G1 as v1 wrote it is always reported. This was fixed before
  any diagnostic ran.
- **Fresh G3 sets.** v2 is judged on development sets never read before
  (`side-tests.md`, amendment 13). The v1 sets are seen and reported only.
- **Order.** The lymph node, then the lung, then the colon.
- **Settings.** Gene exclusions and pool training are decided by
  diagnostics, with rules fixed before each ran.

**The diagnostics** (`research/notebook-outputs/organ_v2_*`):

| Step | Question | Result and decision |
|---|---|---|
| A1 | Do immunoglobulin or serum proteins make the sinks? | No: removing them moves nothing in any organ. v2 removes no genes. |
| A1b | What draws pools to one class? | The encoder, on deep, mixed pools. Removing plasma's own markers changes nothing; thinning pools to single-cell depth halves the lymph node's sink; B-cell pools uploaded alone are never plasma. An explanation only. |
| A0 | Can calibration be replayed offline? | Yes: the cache equals the service on every replayed cell. Its refit check was amended after the first run, from rank to a qhat bound of 0.005 (the largest shift is 0.0008). |
| A2 | What can calibration do under the split G1? | Lung: v1's own rule already gives mixed uploads 96.6% committed. Lymph node: mixed 78.5%. Colon: 16.8%, and 97% only if each upload's band were known. Calibrating on mixed uploads only is unsafe for narrow ones. |
| A3 | Rare and hard classes | Lymph node: the chance floor (committed 82 → 97 on the rare-class suite, coverage 91.1 → 88.2). Lung and colon: the group fallback for classes with under 30 calibration cells. |
| A4 | Can the colon's band be read without labels? | No key passes: each reads some real narrow upload as mixed, or no real mixed upload as mixed. **The colon v2 is not built.** |
| A6 | Does training on RNA pools remove the sinks? | Short of its bar: the lymph node's plasma guesses fall 44 → 35 of 48 (the bar was 12 fewer). v2 does not train on pools. Pools helped single cells in every organ (validation +0.7 to +6.5 points). |
| A5 | Profiles, explanation only | Not run. No v2 decision depends on it once G1 is split. |

**The candidates.** Each is its v1 file with the decided changes only:

| | lymph node v2 (`scripts/organs/lymph_node_v2.json`) | lung v2 (`scripts/organs/lung_v2.json`) |
|---|---|---|
| Classes | v1's minus the generic "t cell" (18) | v1's minus the generic "monocyte" (27) |
| Split | v1's, carried through the atlas rows | v1's, carried through the atlas rows |
| Suites | new seeds; every class with at least 5 cells, short classes capped | the same |
| Calibration | the chance floor | the group fallback (under 30 cells) |
| Unchanged | gene space, identifier map, profiles, module settings, training, fusion | the same |

**The gates, fixed now, before any v2 model** (`research/notebooks/organ_v2_gates.py`):
- **G1, split:**
  - mixed uploads: committed ≥ 75, correct when committed ≥ 90, coverage
    ≥ 85, false abstention ≤ 2;
  - narrow uploads: correct when committed ≥ 90.
- **G3, fresh**, AUROC ≥ 0.8:
  - **lung v2, PXD058626:** every run's FragPipe "Intensity" in one upload.
    The score is P(airway epithelial group) − P(alveolar epithelial group),
    control airways (12) over control alveoli (12). IPF regions are
    reported.
  - **lymph node v2, PXD045043:** P(B cell group), white pulp over red pulp,
    over the single labelled DIA voxels. The 42-voxel map (its labels came
    from the protein data) and technical replicates are excluded. The
    reader is fixed by a dated note on the deposit's layout once it is
    downloaded (jPOST refused this network's connections on 2026-10-19),
    before the lymph node's gate run.
- **G2:** one donor held out, a diagnosis.
- **G4:** the locked test's rehearsal on the v2 bundle.
- **Seen sets:** each organ's v1 G3 sets, reported only.

**Registry.** Each v2 suite's sha256 is recorded in
`research/notebook-outputs/organ_v2_registry.json` before training. Each
bundle's MANIFEST sha256 is added at freeze, before its gates. The gate
script refuses anything else.

**Stop rules:**
- Each v2 candidate's gates run once.
- A miss stops that organ; nothing is tuned.
- A change after any v2 gate result is a v3.
- A pass unseals that organ's locked test, which is scored once under its
  protocol's amendment 1.

**Correction, 2026-10-19.** The lung's outcome said "4 of 4" control
donors' epithelial pools were called macrophage. MSV000094373 has five
control donors, and D119's pool is called epithelial, so it is 4 of 5. The
text above and run history entry 55 are corrected.

## The large intestine's outcome: every failure, in one place

Run history, entries 49 to 52; the records are under
`research/notebook-outputs/` (`organ_builder_blood/`, `li_labels/`,
`li_build/`, `li_development/`, `li_donor_heldout/`).

**The gates (Stage 2), fixed before any colon model existed:**

| Gate | Result | Bar | Verdict |
|---|---|---|---|
| G1, simulated colon uploads: committed | 12.0% | ≥ 75% | **miss** |
| G1: correct when committed | 99.4% | ≥ 90% | pass |
| G1: coverage | 85.3% | ≥ 85% | pass |
| G1: false abstention | 0.24% | ≤ 2% | pass |
| G3, Kabatnik: epithelium over stroma | AUROC 1.0 | ≥ 0.8 | pass |
| G3, Zheng: T cell vs myeloid pools | 16.7% | ≥ 80% | **miss** |
| G3, polyp plate: marker concordance | 2 of 6 groups | all ≥ 0.7 | **miss** |
| G4, the locked test's rehearsal | runs end to end | runs | pass |
| G2, one donor held out (a diagnosis) | 43.1 unseen, 55.6 seen | reported | gap 12.5 (blood 9.8) |

**Why the gates missed:**
- Every upload is scaled against itself. Narrow uploads (one lineage or one
  class) lose their signal, far more on the colon than on blood.
- Median nonconformity score by kind of upload:

  | Kind of upload | Median score |
  |---|---|
  | one class | 0.99 |
  | one lineage | 0.91 |
  | whole tissue | 0.39 |

- Conformal sets fitted over every kind of upload come out too wide: the
  marginal threshold is 0.987, against blood's 0.91. Most sets then span
  lineages and the cell abstains.
- Leaving single-class uploads out of the fit moves the threshold only to
  0.970, so they are not the whole cause.
- Whole-tissue uploads are answered well (best guess 86.5%, coverage
  99.7%), yet commit only 22%.
- Real data follow the same pattern:
  - Kabatnik's mixed upload separates perfectly;
  - Zheng's immune-only upload fails, its T-cell pools guessed mast cells,
    monocytes or endothelial cells;
  - the polyp plate is almost all epithelium, and every cell abstained.

**Failures and faults found on the way, all recorded:**
1. **Blood acceptance, tier 5.** "Every class's recall within 5 points" of
   the served seed missed: hematopoietic stem cells −10.0, naive CD4 T +9.5.
   The five served seeds differ by more than 5 points among themselves on 11
   of 20 classes, so the check was ill-posed. It is reported, not changed.
2. **Modules are not reproduced** (adjusted Rand 0.30; another
   scikit-learn). Blood keeps its served modules. The port is deterministic
   and is used for other organs; one colon module ended up empty (harmless).
3. **Tabula Sapiens' "Paneth cell of colon" is not Paneth cells.** No donor's
   cells express DEFA5 or DEFA6. The class is dropped (217 cells).
4. **The audit's marker-signature score was misleading.** It z-scores
   near-zero genes across groups, so ambient RNA showed as matches. The
   decisions used absolute shares instead.
5. **A builder bug:** the class rule judged dropped classes when the audit
   kept them. A unit test caught it, and it is fixed.
6. **A service bug, live:** the DIA-NN parser read DIA-NN 1.8's `Protein.Ids`
   column as a cell, so 1.8 protein tables could not be uploaded. It is fixed
   with a test (`service/pipeline/alignment.py`) but not yet deployed.
7. **A service limit:** the identifier map covers blood's 9,002 genes only,
   so colon uploads lost every colon gene (2,446).
   - Each organ now builds its own map from HGNC; blood's is reproduced
     exactly.
   - Research runs use it through `bundle.gene_map`.
   - The served service does not yet load organ maps.
8. **The first gate run was stopped,** at 40 of 240 uploads and before
   anything was written, to take faults 6 and 7's fixes. The run that counts
   is the second.

**Limits of the data, known from the start:**
- No human colon single-cell MS set with independent labels exists.
- All three Deep Visual Proteomics sets come from one lab and one chemistry.
- PXD051891 is not public.
- Zheng's colorectal tables hold only macrophages, CD8 T and CD4 T cells.
- The polyp plate's origin is unknown.
- Tabula Sapiens' colon classes follow donors (TSP2 holds most stem cells,
  TSP26 most best4+ cells).

**What worked:**
- The builder: blood's references rebuilt exactly, and v4.1's frozen
  responses reproduced through the new loader.
- The label audit.
- Kabatnik's mixed upload (AUROC 1.0).
- The sealed test's intake and scorer (rehearsed).
- Whole-tissue simulated uploads' best guess (86.5%).

**What stays:**
- **PXD052341 stays sealed,** unopened, for any future colon reference
  (`research/benchmark/side-tests.md`, amendment 8).
- The colon's work folder and bundle stay on Drive
  (`drive/Data/Results/Organs/large_intestine/`); nothing of it is served.
- Stages 3 and 4 do not run for the colon.

**Carried to the next organ:**
- **The recipe is unchanged,** so an organ whose uploads are narrow (one
  lineage) will likely miss G1 in the same way. Mixed, multi-lineage
  uploads, as in blood, are where it works.
- **Build the gene map with the gene space.**
- **Read every development deposit with the service's own parser** before
  any gate.
- **Run the label audit before training.**

## What the code and data showed

- **No script builds a reference from an h5ad.** Blood's came from the Colab
  notebooks NB1 and NB2. The in-repo pieces reuse blood's NB1 files.
- **The upload simulator lives only on Drive** (`sim_generator.py`, in
  Drive's `Results/Tier1_v31/NB1/`). `research/notebooks/v5_build.py` imports
  it from there.
  - Its scenarios are blood-specific: they call `classes.index("macrophage")`
    and use blood lineage words.
  - Training uses uniform random masks; the real-protein masks are used only
    for the test and calibration uploads.
- **Gene space.** The 9,002 genes miss the colon's markers: KRT20, MUC2, TFF3,
  OLFM4, LGR5, CD68, PDGFRA, CDX2, BEST4, CHGA, SPINK4 and REG4. So the colon
  needs its own gene space and its own encoders, about 125 MB per member at
  about 11,000 genes (blood's are 98 MB).
- **The donors confound the classes:**
  - TSP2 holds 1,307 of 1,732 stem cells and 2,620 of 4,567 enterocytes;
  - TSP14 holds 726 of 848 enteroglia;
  - TSP26 has 593 "best4+" cells, 3 enterocytes and no goblet cells;
  - naive CD4 T is 214 of 228 from TSP27;
  - all 47 "mature nk t" cells are annotated "innate lymphoid cell";
  - "myeloid leukocyte" is a catch-all.

  So a label audit comes first, and leaving one donor out is a diagnosis,
  not a clean test.
- **Blood-only pieces of the service and site:**
  - `service/config.py`'s cross-modal classes;
  - restricted mode (`service/pipeline/label_space.py`);
  - property transfer;
  - `web/js/atlas/answers.js`, which places cells by `pipeline_version` alone;
  - the 22 `CLASS_COLOURS` in `web/js/workflow-data.js`.

  The service loads one bundle per process (`service/app.py`). The pipeline
  modules take their classes, hierarchy and centroids from files.

## Classes

**Rule.** Keep a class with at least 50 cells and at least 5 cells in each of
at least 2 donors. Otherwise merge it into its nearest kept Cell Ontology
ancestor.

**Merges:**
- enterochromaffin-like + type L enteroendocrine → enteroendocrine cell (71);
- NK + ILC + "mature nk t" → innate lymphoid cell (74);
- myeloid DC + neutrophil → myeloid leukocyte (403);
- naive CD4 T → CD4 T. This is one donor's annotation, and blood's CD4 /
  naive CD4 pair is a known confusion.

**23 classes,** answered as class, then group, then lineage:

| Lineage | Group | Classes |
|---|---|---|
| epithelial | stem/TA | crypt stem cell, transit amplifying cell |
| epithelial | absorptive | enterocyte, best4+ cell |
| epithelial | secretory | goblet, Paneth, tuft, enteroendocrine |
| immune | T/ILC | CD4 T, CD8 T, gamma-delta T, Treg, innate lymphoid cell |
| immune | B lineage | B cell, plasma cell |
| immune | myeloid | colon macrophage, monocyte, myeloid leukocyte, mast cell |
| stromal | fibroblast | fibroblast, myofibroblast |
| stromal | endothelial | endothelial cell |
| stromal | glial | enteroglial cell |

**Note, 2026-10-18: the label audit drops Paneth.** "Paneth cell of
colon" (217 cells) has no Paneth markers in any donor (DEFA5 and DEFA6 at
0%). It is dropped, so the reference has **22 classes**; the secretory
group is goblet, tuft and enteroendocrine (run history, entry 50).

**Splits:**
- train / validation / test: 65 / 15 / 20, stratified by class × donor;
- leaving one donor out: a separate diagnosis. A class and donor pair counts
  only when both sides have at least 20 cells.

The label audit (markers per class × donor) runs before training and may
change the merges, by a dated note here.

## Stage 0: roles first, then the locked protocol

**Commit A, before any PXD052341 file:**
- amendment 7;
- tier C in `scripts/fetch_public_sets.py`;
- the protocol, written from PRIDE's file listing and the paper;
- this file;
- the Track I entries.

**Commit B:** fetch tier C into `data/incoming/public_sets/` and record the
sha256s. PXD052341 is downloaded and checksummed only.

**DIA-NN.** A development deposit with only raw files gets a DIA-NN search
with fixed settings:
- the version pinned and recorded in `docs/setup-windows.md`;
- a human UniProt FASTA;
- library-free, 1% FDR.

Free disk space is checked before each download.

**Gate:** Zheng or Kabatnik yields a per-sample protein matrix with its
class labels.

## Stage 1: a reference builder, proven on blood

**New:**
- `scripts/build_organ_reference.py`. Its stages: labels, space, stats,
  profiles, modules, suites, train, calibrate, layer, bundle, evaluate.
- `scripts/organ_reference/`:
  - the simulator copied byte for byte from Drive, its sha256 recorded;
  - scenarios built from each organ's hierarchy (blood keeps its old ones
    exactly);
  - modules for labels, gene space, profiles, modules and calibration.
- `scripts/organs/`: one JSON per organ (blood and large intestine) naming
  the h5ad, columns, relabels, merges, hierarchy, gene and mask sources, and
  seeds.
- A unit test on a tiny synthetic h5ad, CPU only.

**Reused:**

| What | Where |
|---|---|
| `load_rna`, `encode` | `scripts/build_v4_bundle.py` |
| `class_balanced_stats`, `class_means` | `service/pipeline/fusion.py` |
| `train_variant`, `reference_embedding`, `centroids_from`, `query_inputs`, `raw_upload` | `research/notebook-outputs/nb2/nb1b_core.py` |
| `fit_temperature`, `fit_qhat` | `research/notebook-outputs/nb2/nb2_core.py` |
| `build`, `best_guess_layer`, `write_manifest` | `research/notebooks/v5_build.py` |
| leaving one donor out | `research/notebooks/donor_heldout.py` |
| answers, suite scores, coverage | `research/notebooks/v41_core.py`, `research/notebooks/v41_phase3.py` |
| ported from the notebooks | NB1's `stratified_split` and `profile_from_obs`; Reference_Projection_v3's MiniBatchKMeans modules (target size 18) |

**Simulated-upload missingness for the colon.** It sets the conformal,
temperature and out-of-distribution calibration, and the gates G1 and G4.
Four sources:
- the polyp plate's per-cell detection, the only single-cell colon profile;
- blood's SCoPE2, PBMC240 and Fulcher profiles, re-indexed by RNA-abundance
  rank in the colon gene space, so that detection follows expression level
  rather than blood gene identity;
- random coverage, as for blood;
- a pool profile from Zheng's and Kabatnik's detection, used only for the
  pool rehearsal.

**Gene space (colon).** It is built from:
- the six existing sources (`service/model/evidence/feature_space_detail.csv`);
- the development colon protein lists;
- the polyp plate's genes.

Immunoglobulin and T-cell receptor genes are removed, and the result is
intersected with Tabula Sapiens' genes. The locked set's protein list is
never read.

**Blood acceptance,** in tiers. Exact retraining is impossible because of
GPU nondeterminism and the Colab L4. The builder's outputs stay outside the
repository; the record goes to
`research/notebook-outputs/organ_builder_blood/`.
1. **Exact:**
   - NB1's `y_all.npy` and `splits_seed0.npz`, and its calibration and
     evaluation suites;
   - the 9,002 genes;
   - the hierarchy and class order of `service/model/v3_1/nb2_spec_v31.json`.
2. **Within tolerance:**
   - the RNA statistics, to 1e-4;
   - the mask profiles, to 1e-6;
   - v4's class-balanced statistics and class means, to 1e-5;
   - centroids at cosine ≥ 0.999999.
3. **Calibration on the served members,** by the rules of
   `research/notebook-outputs/v5_build/reproduce.json`:
   - temperatures exact;
   - the conformal threshold within one rank;
   - the out-of-distribution threshold within 1e-3;
   - latents at cosine ≥ 0.9999.
4. **Loader and layout.** A blood bundle assembled from the served
   statistics, centroids and calibration, and loaded by the new loader,
   reproduces the `v41_full` fixtures in `service/tests/fixtures/` exactly.
   The bundle from the rebuilt files is only reported (label agreement).
5. **Training path.** Retrain seed 1 and compare it with the served seed-1
   member alone:
   - best validation loss within 0.02 (0.45517,
     `research/notebook-outputs/v5_train/reproduce.json`);
   - balanced accuracy within 2 points;
   - each class's recall within 5 points;
   - top-1 on the calibration uploads within 2 points of the served member's
     own, computed in the same run.

## Stage 2: the colon bundle, development checks, go or no go

**The bundle.** `service/model/organs/large_intestine/`, in v4.1's layout:
metadata, genes, specs, class-balanced statistics, class means, members,
latents, centroids and MANIFEST.
- The checkpoints are gitignored and fetched like v3.1's members.
- v4.1's fusion settings are reused untuned.

**Records.** `research/notebook-outputs/li_labels/` (the audit, first),
`research/notebook-outputs/li_build/` and
`research/notebook-outputs/li_donor_heldout/`.

**Scripts:**
- `research/notebooks/li_development.py` (G1 and G3) and
  `research/notebooks/li_donor_heldout.py` (G2);
- `benchmark/colon_heldout_intake.py` and `benchmark/colon_heldout_score.py`;
  their `--rehearse` builds RNA pseudobulk pools shaped like DVP (G4). They
  reuse:
  - `auroc_with_p` (`benchmark/heldout_score.py`);
  - the download check (`benchmark/heldout_intake.py`);
  - the DIA-NN reader (`benchmark/heldout_formats.py`);
- a colon option in `benchmark/baselines_corrected.py`.

**Gates.** Fixed now, before any colon model exists. A miss stops the work
and goes to the owner. No setting is tuned to pass a gate.
- **G1, simulated uploads from the colon's RNA test cells:**
  - correct when committed ≥ 90% (blood: 96.3);
  - committed ≥ 75% (blood: 85.8);
  - conformal coverage ≥ 85%;
  - false abstention ≤ 2%.
- **G2, one donor left out:** reported, not a gate. It uses one member per
  fold and the nearest centroid under the colon masks
  (`research/notebooks/donor_heldout.py`'s pattern), and reports lineage and
  group recall.
- **G3, development protein:**
  - Kabatnik: AUROC ≥ 0.8 for epithelium (CDX2-high and CDX2-medium) over
    stroma (CDX2-negative), on P(epithelial lineage);
  - Zheng's colorectal tables: group accuracy ≥ 80% for T/ILC (CD8 T and
    CD4 T tables) against myeloid (macrophage table);
  - the polyp plate: for each called group with at least 20 cells, AUROC
    ≥ 0.7 of a marker score taken from Tabula Sapiens class means.

  If a deposit's layout turns out to differ (for example, no sample
  annotation), the gate's wording may be fixed by a dated note before the
  colon is built, never after.
- **G4:** the locked test's rehearsal runs end to end on RNA pseudobulk.

**Note, 2026-10-18: G3 against the deposits as fetched.** Fixed before any
colon model exists.
- **Zheng (PXD057118).** Its colorectal data are immune cells only: 18
  pools, each a macrophage, CD8 T or CD4 T pool, 3 from lamina propria and 3
  from tumour epithelium. The three tables share one protein list (5,295
  groups), so they are read as one upload. The service needs at least 20
  rows, so the development script runs the pipeline's functions directly.
  The gate stays T/ILC against myeloid, with CD8 T against CD4 T reported.
- **Kabatnik (PXD046999).** The deposit's metadata defines:
  - class 1: CDX2-high epithelium;
  - class 2: CDX2-medium epithelium;
  - class 4: CDX2-negative stroma ("class 3" in the paper's own wording).

  The gate's input is `C3_region1k_DIANN181_MBR_c124.pg_matrix.tsv`: all
  three classes from one search, 27 pools. The class 1 and class 4 tables
  were searched apart, and are reported only.

When all gates pass, an amendment to the protocol freezes the bundle's
sha256s.

**Result, 2026-10-18: NO GO as built** (run history, entries 51 and 52).
- **Passed:** G4, and G3's Kabatnik check (AUROC 1.0).
- **G1 missed on commitment:** 12% committed against 75%. Correct when
  committed is 99%, and coverage 85%.
- **G3 missed** on Zheng (16.7% group accuracy) and on four of the polyp
  plate's six marker checks.
- **Cause:** per-upload scaling costs narrow uploads (one lineage, one class)
  far more on the colon than on blood. Conformal sets fitted over every kind
  of upload then come out too wide to commit. Whole-tissue mixtures are
  answered well (best guess 86.5%, coverage 99.7%) but still commit only
  22%.
- **What next is the owner's decision.** The locked test stays sealed.
  Stage 3 does not start.

## Stage 3: service and site (after the beta sign-in work lands)

**Service:**
- **`service/config.py`:** the organs, with blood the default, the served
  organs from an environment variable, and per-organ directories through
  `_env_path`.
- **Loading:** a new `organs.py` in `service/pipeline/`. Blood still loads
  through `pipeline.load_bundle`, unchanged. The bundle loaders take paths;
  their defaults are unchanged.
- **The `organ` field** in `POST /api/project` is optional:
  - absent means blood, and the response is byte-identical;
  - an unknown organ gets 400;
  - the colon with restricted mode gets 400;
  - colon responses name the organ and carry no properties.
- **`/api/status`** lists the organs only when more than one is served.
- **Memory.** A memory check measures peak RSS with both organs loaded and a
  2,000-cell upload each.
  - At 3.0 GiB or below: one process, with the colon loaded lazily.
  - Above that: a second Cloud Run service from the same image, serving the
    colon only. It scales to zero.
- **Tests:** blood's fixtures are untouched; the colon gets its own goldens.
  The deploy build and check scripts cover every served organ.

**Site:**
- **Atlas page, Your data:** an organ choice. The landing places cells by
  organ and pipeline together.
- **The colon map** is written by `scripts/export_atlas_coordinates.py` with
  an organ option.
- **`web/js/workflow-data.js`:** colon plain names and groups, and 23 colours
  of their own. `CLASS_COLOURS` and blood's tests stay as they are.
- **The manifest:** an organs block.
  - The colon's RNA records are measured.
  - Its protein accuracy stays Pending until the locked test's summary
    exists.
- **The Workflow page** stays blood-only. Blood is unchanged, so it needs no
  re-trace.

## Stage 4: score once, write up, release

1. The candidate amendment.
2. The intake: labels, then the upload.
3. The baselines.
4. The scorer, once.
5. An amendment marks the set spent.
6. The manifest, the Manuscript page's section and the figures are rebuilt.
7. Atlas 0.7.0, with the colon reference named "large_intestine v1".
8. Deploys only on the owner's explicit approval; the owner runs
   `gcloud run deploy`.

## Working rules

- Commit by stage, naming files explicitly.
- LF line endings.
- `docs/file-index.md` in the same commit.
- Tick `research/todo.md` with commit hashes.
- UI checks are the owner's; Claude runs the automated tests only.
