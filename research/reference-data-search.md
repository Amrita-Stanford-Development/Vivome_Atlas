# Data search, 2026-10-21: RNA references and protein data

The owner asked for a second deep search (2026-10-21), this time for RNA as
well as proteomics: downloadable RNA atlases that could make the references
themselves more accurate, beside protein data for tests and gates. Five
agents searched in parallel, each on one area, reading repository pages,
file listings, metadata APIs and papers only. Nothing was downloaded, no
sealed set was opened, and no label table of a possible future test was
read. The key facts of the top picks were checked again against their
repositories (marked in the tables). The proteomics register stays
[side-tests.md](benchmark/side-tests.md); its amendment 19 records what this
search changed there.

## What it found

1. **Every Tabula Sapiens reference rests on few, shared donors.** Lung has
   4 donors, large intestine 5, lymph node 6, and the spleen file has the
   same 6 donors as the lymph node (CELLxGENE donor lists). Open atlases
   with 24 to 265 donors and consensus or protein-checked labels now exist
   for every organ we build, and for blood.
2. **Blood's empty classes can be filled from one atlas.** The Allen Human
   Immune Health Atlas (108 healthy donors) ships a dendritic-cell file of
   23,287 cells labelled cDC1, cDC2, pDC and AXL+ DC, and an "other cells"
   file with progenitors, in Cell Ontology terms.
3. **CD8 T against NK needs protein-backed labels, not more RNA.** The
   sources whose CD8 and NK labels come from surface antibodies or sorting
   are Wells 2025 (127 antibodies), Stephenson 2021 (188) and the sorted bulk
   sets (ImmuNexUT, Monaco, DICE).
4. **The lymph node's B-as-T error has a direct remedy in RNA:** Wells 2025
   gates naive, memory and germinal-centre B cells, plasma cells and
   plasmablasts with surface protein, in three lymph-node sites and spleen
   from 24 donors.
5. **No immune cells have been measured for RNA and MS protein in the same
   cell** in public data. The bridges are sorted populations profiled both
   ways (T cells, B cells) and tissues profiled both ways (29 and 32 tissues).
6. **No new public protein set can gate an organ.** Progress there needs
   data requests or a raw-file search of a set already registered.
7. **A public set with FACS-sorted CD4 and CD8 T cells, from bone marrow,**
   was missed on 2026-10-14: MSV000102427. It is the nearest thing to the
   main test that is public, and it stays unopened.

## Blood reference: RNA

Weaknesses: **W1** CD8 T against NK (and naive CD8 T filed under CD4 in
Tabula Sapiens); **W2** classes too rare to calibrate (myeloid DC, pDC,
basophil, Treg, HSC, CMP); **W3** few donors.

| Rank | Source | Where | Size | Cells, donors | How labels were made | Fixes |
|---|---|---|---|---|---|---|
| 1 | Allen Human Immune Health Atlas (Gong 2025, *Nature*) | CELLxGENE collection `77f9d7e9-5675-49c3-abed-ce02f39eef1b` (checked) | DCs 0.35 GB; other cells 0.06 GB; CD8 T 3.1 GB; NK/ILC 1.2 GB; all 11.5 GB | 1.82 M PBMCs, 108 healthy donors, 10x 3' v3 | Reference transfer, subclustering and expert annotation; 71 types; RNA only | W2, W3, part of W1 |
| 2 | ImmuNexUT (Ota 2021, *Cell*), bulk RNA of 28 FACS-sorted subsets | DDBJ `E-GEAD-397` (checked: processed 273 MB, with IDF and SDRF) | 273 MB | 79 healthy donors of 416 | FACS | W1 and W2 anchors: CD8 naive to effector memory, NK, Tregs, mDC, pDC |
| 3 | Wells 2025 (*Nat Immunol*), immune ageing in organ donors | CELLxGENE `cc431242-35ea-41e1-a100-41e0dec2665b` (checked); GEO GSE299043 | T cells 5.5 GB; B cells 2.7 GB; all 12.7 GB | 1.28 M cells, 24 donors, blood and 9 tissues; CITE-seq | Classifier trained on surface-protein gates plus RNA | W1 (protein-gated CD8 and NK subsets); Tregs, MAIT, γδ T |
| 4 | Stephenson 2021, COVID PBMC CITE-seq (known) | ArrayExpress E-MTAB-10026 | 7.2 GB | 647k cells, 120 donors | RNA markers backed by 188 antibodies | W1, W2; use healthy donors only |
| 5 | Terekhova 2023 (*Immunity*), healthy ageing | Synapse `syn49637038` (login), CC BY 4.0 | per-lineage archives | about 2 M cells, 166 donors; 20 antibodies | 55 subsets; method not read (paywall) | W1, W3 |
| 6 | AIDA (Kock 2025, *Cell*) | CELLxGENE, 14.2 GB | 14.2 GB | 1.27 M cells, 625 Asian donors | Manual, marker-based | W3; cDC1, cDC2, pDC, Treg |

For single gaps:
- **Monaco 2019** (GEO GSE107011, 15 MB of TPM): sorted bulk of 29 types,
  the only open one with basophils, pDC, mDC and progenitors together.
- **DICE** (91 donors, 15 sorted types, CC BY 4.0).
- **The Protein Atlas's immune-cell RNA** (18 sorted types).
- **Furer 2025** (GSE285943): CD34+ cells from the blood of 148 people,
  about 14,000 of them HSCs.
- **BoneMarrowMap** (Zeng 2025): progenitor states, from bone marrow.
- **GSE287976:** FACS-sorted basophils, 4 donors, the only single-cell
  source of mature basophils found.

Hao 2021 (in use) and Triana 2021 (mostly a 462-gene targeted panel) were
confirmed and add nothing new.

## Organ references: RNA

| Organ | Source | Where | Size | Cells, donors | Labels | Fixes |
|---|---|---|---|---|---|---|
| Lung | HLCA core (Sikkema 2023, *Nat Med*) | CELLxGENE dataset `066943a2-fdac-4b29-b348-40cede398e4e` (checked) | 5.9 GB | 584,944 cells, 107 healthy donors | Six-expert consensus, 61 finest types; every sample scored from nose to parenchyma | Airway guessed as alveolar; the generic monocyte class |
| Lung | Tabula Sapiens trachea | CELLxGENE `d8732da6-8d1d-42d9-b625-f2416c30054b` | 965 MB | 22,671 cells, 6 donors (3 new to lung) | Tabula Sapiens; basal, ciliated, goblet, serous; no club | Airway epithelium in the current format |
| Lung | Madissoon 2023, five locations (*Nat Genet*) | Sanger cellgeni `5-locations-lung` | epithelium 514 MB | 193,108 cells and nuclei, trachea to parenchyma | 80 types, checked by imaging | Proximal-to-distal epithelium |
| Colon | Pan-GI Gut Cell Atlas (Oliver 2024, *Nature*) | CELLxGENE `f11cb29c-b546-4738-9bd8-66ea621a7bd5`; healthy large-intestine epithelium on the Sanger gutcellatlas bucket | 719 MB | 1.08 M healthy cells, 189 donors | 136 states, 51 epithelial | Stem, TA, colonocyte, BEST4, goblet across many donors |
| Colon | HCA Human Gut Cell Atlas v1.0 (bioRxiv 2026-10-12) | Cell Annotation Platform project 1070; CC BY 4.0 | format not checked | 944,390 cells, 265 donors | Five-level community consensus, 94 identities; 9,717 stem and 18,299 TA cells | The strongest stem/TA labels |
| Lymph node | Wells 2025 (above) | CELLxGENE `cc431242-…` (checked) | B cells 2.7 GB | 24 donors; inguinal, mesenteric and thoracic nodes, spleen | Surface-protein-gated B subsets (naive, memory, germinal centre, plasma cell, plasmablast) | B read as T; the generic "t cell" class |
| Lymph node | Tonsil atlas (Massoni-Badosa 2024, *Immunity*) | Zenodo 6340174 and 10373041; HCATonsilData | 4.4 to 10 GB | 17 donors | 121 types checked with CITE-seq, imaging and flow | Germinal-centre, plasma, follicular DC, mast cell and neutrophil detail |
| Lymph node | Domínguez Conde 2022 (*Science*) | CELLxGENE `62ef75e4-cbea-454e-a0ce-998ec40223d3` | 3.0 GB | 329,762 immune cells, 12 donors | Expert annotation (CellTypist) | Fine immune labels in lymph node and spleen |

Notes:
- **Tabula Sapiens 2.0** is now published (*Cell* 2026,
  10.1016/j.cell.2026.08.010). Its CELLxGENE organ counts equal the files
  the references use; whether its labels changed was not checked.
- **Colon stem cells:** Burclaff 2022 (GSE185224) shows that accepted
  stem-cell markers do not mark all human intestinal stem cells, and that
  OLFM4 is higher in TA than in stem cells. That supports the merged
  stem/TA class the organ work proposed.
- **No open healthy whole-lymph-node atlas has both immune and stromal
  cells:** the stromal atlas (Abe 2022) is controlled access.

## RNA and protein together

| Source | Pairing | What | Where | Use |
|---|---|---|---|---|
| The Protein Atlas DVP (Weiss 2026) | same study | MS pools of 27 imaged cell types, lymph-node CD4 T, CD8 T, B and macrophage and lung AT1/AT2 among them, beside RNA | proteinatlas.org (already development data here: `HPA2026_DVP` in `scripts/fetch_public_sets.py`) | Per-gene protein against RNA for the lymph-node and lung classes |
| Wang 2019 (*Mol Syst Biol*) | same sample | 29 healthy tissues, tonsil, spleen, lung and colon among them | PXD010154 (CC0) and E-MTAB-2836 | Tissue-level protein-to-RNA ratios |
| Jiang 2020 (*Cell*), GTEx | same sample | 201 samples, 32 tissues, 14 donors | PXD016999 (CC0) and GTEx | Which genes' RNA follows protein, across donors |
| Weerakoon 2024 | same sample | Blood CD4 and CD8 T cells, 3 donors, 6 time points | PXD038810; RNA counts in a supplementary table | T-cell protein against RNA |
| Koers 2026 | same sample | 9 sorted B-cell subsets, 8 donors | PXD060953 and GSE298777 | B-cell protein against RNA |
| Rieckmann 2017 (in use) with Monaco 2019 and Calderon 2019 RNA | same cell types, other donors | 28 sorted immune populations both ways | PXD004352, GSE107011, GSE118165 | Per-class protein-to-RNA offsets for NK, CD8 T, B and monocytes, from data mostly on disk |
| nanoSPLITS (Fulcher 2024) | same cell | 95 human islet cells | MSV000093330 and GSE247519 | A single-cell noise model only |

The Protein Atlas merges CD4 and CD8 T cells, and AT1 and AT2, for its own
RNA-protein comparison, "to reflect high protein overlap" (its DVP method
page): independent evidence that some RNA-defined splits blur on protein.

## Organ protein data

Nothing new can gate an organ. Found:
- **PXD051795** (CC0): laser-captured germinal-centre B, lymphoma B and
  Hodgkin cells from one patient's lymph node (checked). B cells only, so at
  most a development check. Same lab group as the sealed lymph-node test:
  confirm the donors differ before any use.
- **MSV000090561:** 8 airway regions, no alveolar comparator.
- **MSV000098036:** an unlabelled 72-voxel spleen map, probably PXD045043's
  source.

Routes that remain:
- a DIA-NN search of PXD043807's raw files (CC0; listed on 2026-10-19 as
  "COVID lungs; raw only"). Checked: laser-microdissected regions chosen on
  histology, alveolar against bronchial epithelium among them, from 71
  post-mortem specimens with non-COVID controls (how many is not stated);
  diaPASEF on a timsTOF Pro;
- data requests:
  - Schiller lab (now a 2026 dissertation: 135 histology-defined regions
    along the airway tree);
  - Leiden University Medical Center (van der Pan, de Laat: FACS-sorted
    colon epithelial populations from 7 patients, shown at HUPO 2024);
  - the authors of the Oncogene 2026 lymphoid-structure study.

## Blood single-cell proteomics

The sweep covered everything announced to ProteomeXchange (iProX and jPOST
through its PROXI API) from 2026-10-01, PRIDE from 2026-10-05, MassIVE,
Zenodo, Figshare, Mendeley Data (now searchable), and every bioRxiv and
medRxiv preprint since 2026-05-01. No new single-cell set with sorted CD4
and CD8 blood T cells appeared. But one public set that the 2026-10-14 search
missed comes close:
- **MSV000102427 (PXD080865), Foster lab, UBC, the GIRAFI preprint:**
  public since 2026-08-10 (checked); timsTOF SCP and Ultra 2. Its preprint
  describes about 311 FACS-sorted **bone-marrow** mononuclear cells stained
  for CD4, CD8, CD19 and CD13, with CD4 and CD8 T-cell populations, and 116
  PBMCs after magnetic enrichment. Labels from sorting, so independent of
  the MS data. Not stated: whether each gate went to its own wells, and how
  many cells each class has. **A candidate sealed CD4/CD8 test** (bone
  marrow, not blood); nothing of it was opened.
- **PXD064083** (iProX; Immunity & Inflammation 2025): about 78 single CD3+
  T cells and 70 single CD19+ B cells from ALS patients and controls, timsTOF
  diaPASEF. A possible T-against-B test; no CD4/CD8 split.
- **PXD049099** (iProX): 8 single CD3+ and 10 single CD19+ cells. Too small
  for a test.

Status changes:
- **PXD070599** is published (*Nat Commun*, 2026-09-19).
- **PXD080834** (still embargoed) is the CNPEM head-and-neck cancer PBMC set:
  unsorted, so development only once released.
- **The HUPO benchmark** holds cell lines only.
- **Krisp, O'Connor, Brenes and Lange** are still not public. The CD8 paper
  in a Chinese journal is identified (*J Chin Mass Spectrom Soc* 2025,
  10.7538/zpxb.2025.0091); CD8 cells only, no accession.

New bulk sorted class means:
- **PXD056050** (CC0): FACS-sorted B, naive B, T, CD8 T, monocytes and
  activated NK; DIA with a DIA-NN output.
- **MSV000099890** (PXD070689, CC0): six MACS-sorted types, with RNA-seq of
  the same sorted cells (GSE286042); TMT, 1.25 TB.

## Recommended next steps

In order of value for effort:
1. **Protein-aware gene weights for blood, from data mostly on disk.**
   Monaco's sorted RNA (15 MB) beside Rieckmann's sorted protein gives each
   gene's protein-to-RNA agreement per class. Genes whose CD8-against-NK or
   B-against-T contrast vanishes on protein can be down-weighted. Cheap, and
   aimed at the weakness the pooled v5.3 did not move.
2. **Blood's rare classes:** add the Allen atlas's DC and "other cells" files
   (0.4 GB together) as reference cells for cDC1, cDC2, pDC and progenitors.
3. **CD8 T against NK with protein-gated labels:** check first, on RNA, whether
   Wells 2025's antibody-gated CD8 and NK cells are more separable than
   Tabula Sapiens' (the T and NK/ILC files, about 7 GB).
4. **A lymph node v4 from Wells 2025's B and T cells and the tonsil atlas**,
   keeping Tabula Sapiens' stromal cells. It needs a fresh protein gate set
   (the data requests above).
5. **Lung from the HLCA core**, colon from the Pan-GI healthy epithelium.
6. **MSV000102427 as a sealed CD4/CD8 test** (the owner's decision): a
   protocol written before anything is opened, and a request to the authors
   for the gate of each well if the deposit does not carry it.

Each would be a new candidate under the project's rules: its gates fixed
before training, development data only, and the owner's decision before
any sealed test is opened.

## Not reached

- Per-class cell counts in the CELLxGENE files (the expression API failed).
- Terekhova 2023's labelling method, and how OneK1K's CELLxGENE labels were
  made.
- The HCA gut atlas's download format, and the LungMAP CellRef object.
- Whether Tabula Sapiens 2.0 changed labels (paper paywalled).
- Licences of Pan-GI, Wells 2025 and Domínguez Conde on their own pages.
