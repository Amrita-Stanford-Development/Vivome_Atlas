# Side tests: narrower checks on public data with independent labels

Written 2026-10-14, from a five-agent search followed by spot checks of the
key facts against the repositories. No public dataset can replace the main
test (`research/benchmark/protocol-sorted-cd4cd8.md`: CD4 T and CD8 T sorted
separately, single cells). These can each answer one narrower question.

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
| reference | Rieckmann 2017 (PXD004352: 28 sorted primary immune populations, MaxQuant output); Khoury's sorted bulk populations; Tian's sorted T-cell subtypes (MSV000087462) | 1.29 GB | Free for development and diagnosis |
| development | PXD070599 PBMC runs DS18 and DS19 (unsorted, labels from clustering) with their mapping files | 1.56 GB | Free for development |
| side_test | PXD073250, PXD061065, PXD061052, PXD043355, PXD077946, PXD020586, PXD046211, PXD021882, MSV000099294 | 1.43 GB | Sealed |

- **Sealed means:** downloaded and checksummed, nothing else. No label table,
  sort gate or per-cell annotation of a side-test set is opened until that
  side test's own protocol is committed. Listing file names and checking zip
  sizes are allowed.
- **A set changes role only by amendment,** dated and committed before the
  change takes effect. A set once used to develop or diagnose cannot become a
  side test afterwards.
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
