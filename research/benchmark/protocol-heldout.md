# Protocol: the internal held-out test, protein sets

**No held-out file has been opened.** This protocol was written on
2026-10-16 from each deposit's public documentation (the PRIDE and MassIVE
project records), before any label table, sample name or protein list of the
five sets below was read. Their roles are set in
`research/benchmark/side-tests.md` (amendments 1 to 3); the Hao 2021 suite,
the sixth held-out part, has its own protocol.

- **Freezing.** This file is frozen at the commit that adds it. Anything that
  must change before unsealing goes in a dated amendment at the end,
  committed first. Nothing changes after unsealing except format fixes
  (below).
- **One scoring.** Each set is scored once, at Phase 3 of the Goal 2 plan,
  after every candidate is frozen.
- **What a result means.** An internal held-out test, never external
  validation. Cell lines and tissue cells are outside the blood reference,
  and every set's acquisition differs from the reference's protein data. Each
  report states this.

## Common rules

1. **Candidates.** Those frozen by unsealing (side-tests.md, amendment 2),
   scored as served with every reference cell:

   | Model | Files, sha256 |
   |---|---|
   | v4.1 (headline; the served default) | `service/model/v4_1/spec_v41.json` `0b4d7ba486345af8ee04622c625c42d0c3dd14729764cec61446d26c38ca77de`; MANIFEST `5e9cdc71496af5238b4ad5a4bc9ccfb7fce90a0a43d63b1948d14a0f3054382b` |
   | v4.2 | `service/model/v4_2/spec_v42.json` `654a612b5d38220222d77ededf97791c58295126b5c8801b2500663380abe303`; MANIFEST `8fa42d4437523e89d2d5b033b535439f59e71fa63f91d00300d197b06771d565`; protein class means `3afacd88777433488087d433ee8cb2e22bbce92011bcd6f36db01b1d527bec1b` |
   | v5.2 | `service/model/v5_2/spec_v52.json` `61d76d2815b4bd534691fd3f64fa559296afd52e78cd843b9aa3d23fd4f4e2c1`; `nb2_spec_v52.json` `6596bb188ce6420ccf53646ee64fdc3606bb59d30ccbbef1e65e0e62bb04674a`; MANIFEST `72f419d4c1098fc492a274e758894a9bc704853f4c6b9d43d68a7d836a656e8c`; labels `research/notebook-outputs/v52_labels/reference_labels_v52.csv.gz` `123c05eb84d6ff502ba121a97b3a123eaddd08ac01c46647381ce7aa78160280` |
   | v3.1 (for reference) | `service/model/v3_1/MANIFEST.json`, as committed |

   A Phase 2 candidate joins only by an amendment that freezes its files the
   same way, committed before any held-out file is opened. Every candidate
   is scored on the same primary comparison and every result is reported;
   v4.1's is the headline.
2. **Scores come from the service's own code.** Answers, abstention and
   reference similarity come from the response (`pipeline.run_projection`).
   The per-class best-guess probabilities are recomputed with the same
   functions: v3.1's ensemble probabilities; for v4.1, v4.2 and v5.2, the fused
   best-guess probabilities, with v4.2's protein term. Both use the label
   space as served. The intake refuses to go on if their argmax differs
   from the served best guess on any cell. Coarse types follow
   `benchmark/fulcher2026_score.py` (`COARSE`).
3. **Statistics.**
   - An AUROC has a one-sided permutation p: 10,000 label permutations,
     seed 0, ties counted half.
   - Paired designs use an exact one-sided sign test.
   - A set passes when p < 0.05.
   - Secondary measures are reported and never decide.
4. **Baselines,** secondary and trimmed (the Goal 2 plan): correlation and
   PCA with kNN, by `benchmark/baselines_corrected.py` on each intake's
   matrix (dataset `heldout_<set>`), with the original reference labels.
   Their coarse predictions per group are reported. Their tools scale the
   query as a whole, so a set with two uploads (Tian) is one query for them.
5. **Unsealing, at Phase 3 only, in this order:**
   1. the candidate amendment, committed;
   2. `python -m benchmark.heldout_intake SET --labels`: the label map is
      built from the deposit's annotation by the set's rules below and
      written once, with its sha256. If the automatic reading fails, the map
      is written by hand by the same rules (`--label-map CSV --reason TEXT`),
      and the reason is recorded;
   3. `python -m benchmark.heldout_intake SET`: every input file is checked
      against its sha256 in `research/benchmark/public-sets-downloads.json`
      and the frozen files against rule 1. Then the uploads are built from
      the map's included samples (one upload per set unless stated) and the
      label-free facts recorded. The intake runs the candidates and saves the
      per-cell tables, the per-class probabilities and the baselines' matrix,
      once;
   4. the two baselines (rule 4);
   5. `python -m benchmark.heldout_score SET`, once; it refuses to run
      again. It writes `research/benchmark/heldout/<set>/`.
6. **Format fixes.** After unsealing, only a reader or identifier fix is
   allowed: a column spelled differently, a file name's extension, an
   annotation laid out otherwise. Each one goes in an amendment with its
   reason before the scoring. No rule, group, statistic or threshold
   changes.
7. **Readers** (`benchmark/heldout_formats.py`), written from the
   documentation:
   - **MaxQuant protein groups** (`.txt`, or exported to `.xlsx`):
     - rows flagged "+" as only identified by site, reverse or potential
       contaminant are dropped;
     - the gene is the first of "Gene names";
     - the "LFQ intensity" columns are used if any holds a non-zero value,
       else "Intensity";
     - 0 is missing.
   - **Proteome Discoverer protein table:**
     - master proteins at high FDR confidence, contaminants dropped, where
       those columns exist;
     - normalised abundances if present, else abundances;
     - each F-number is named by its raw file from the input-file table;
     - the gene comes from "Gene Symbol", else from GN= in the description.
   - **sage TMT PSMs:**
     - spectrum, peptide and protein q-values at most 0.01, where present;
     - the first protein's gene symbol (the service's identifier map, else
       its UniProt entry name);
     - per PSM, each included single-cell channel over the mean of that
       run's included channels, log2;
     - per cell and gene, the median over PSMs.
   - **DIA-NN:** the service's own parser.

## Tian, MSV000087462: CD4 against CD8 in sorted T-cell bulks

- **Data** (MassIVE record): FACS-sorted T-cell subtypes from the peripheral
  blood of multiple myeloma patients, label-free on a Q Exactive HF-X
  (SISPROT). Two protein-group tables, `proteinGroupsCD3CD4CD8.xlsx` and
  `proteinGroupsMMsample.xlsx`. The record does not say which holds
  separately sorted CD4 and CD8 samples.
- **Labels:** from each sample name:
  - lineage CD3, CD4 or CD8 (CD4 or CD8 wins over CD3);
  - state naive, central memory, effector memory, TEMRA, memory or none;
  - patient.
- **Uploads:** every file whose samples include both CD4 and CD8 T cells is
  used, each file its own upload, holding all of its T-cell samples (CD3 ones
  uploaded, unscored).
- **Primary:**
  - S = P(CD8T) − P(CD4T) over the coarse types.
  - A pair is one (file, patient, state) with a CD4 and a CD8 sample;
    replicates are averaged.
  - The pair is won when the CD8 sample's S is higher.
  - Exact one-sided sign test over all pairs; pass if p < 0.05 (9 of 10 gives
    p = 0.011). Void with fewer than 5 pairs.
- **Secondary:** each sample's coarse best guess. On RNA, every pair was won
  while half the CD8 bulks' best guess was NK (run history, entry 39).
- **Caveat:** these are bulk proteomes. v4.2's protein term was built from
  Rieckmann's bulk class means, so its result is reported apart, as bulk
  against bulk.

## PXD021882: B against T pools

- **Data** (PRIDE record): autoPOTS on an Orbitrap Exploris 480. From one
  donor, 5 pools of 145 CD19-sorted B cells and 5 of 145 CD3-sorted T cells,
  plus HeLa runs. The record says MaxQuant processed the HeLa runs and
  FragPipe the HeLa and immune runs; the deposited table is MaxQuant's
  `proteinGroups.txt`.
- **Labels:** B (CD19, B cell) or T (CD3, T cell) from each sample name;
  HeLa and anything else is excluded.
- **Upload:** the B and T pools only. If the table holds no B or no T pool,
  the test is void, recorded and not scored.
- **Primary:** S = P(B) − P(CD4T or CD8T). AUROC, B pools over T pools;
  pass if p < 0.05.
- **Secondary:** each pool's coarse best guess.

## PXD043355: a T-cell line beside HeLa

- **Data** (PRIDE record): single Jurkat and HeLa cells dispensed by an HP
  D100 into 384-well plates, label-free on an Orbitrap Exploris 480. Proteome
  Discoverer 3.0 with CHIMERYS, Percolator at 1% FDR, match-between-runs.
  `HeLa_VS_Jurkat_Proteins.txt` with `HeLa_VS_Jurkat_InputFiles.txt`. About
  30 Jurkat and 24 HeLa cells (side-tests.md).
- **Labels:** Jurkat or HeLa from each raw file's name; any other file is
  excluded.
- **Upload:** every Jurkat and HeLa cell together.
- **Primary:** reference similarity. AUROC, Jurkat over HeLa; pass if
  p < 0.05.
- **Secondary:**
  - abstention rates;
  - the cell-line rule: a Jurkat cell is right when it abstains or its answer
    names the T-cell group or the lymphoid lineage; a HeLa cell is right
    only when it abstains.

## PXD073250: immune cells beside keratinocytes

- **Data** (PRIDE record and the paper): single cells of a CYLD cutaneous
  syndrome skin tumour, FACS-sorted on CD45, CD74 and CD200. diaPASEF on a
  timsTOF HT, DIA-NN 2.0.1 with a library from bulk samples. There are 204
  CD45+ CD74+ (immune), 176 CD45− CD200+ (keratinocyte) and 39 CD45+ CD200+
  cells. The cell-to-file map is in `LSA-2026-03759_Supplemental_Data_1.xlsx`;
  the matrix is `report.pg_matrix.tsv`.
- **Labels:** the gate from the supplement:
  - immune: CD45+ CD74+;
  - keratinocyte: CD45− CD200+;
  - double: CD45+ CD200+.
- **Upload:** every run with a gate. Runs without one (bulk, blanks) are
  excluded; double cells are uploaded, unscored.
- **Primary:** reference similarity. AUROC, immune over keratinocyte; pass
  if p < 0.05.
- **Secondary:** abstention rates; the immune cells' best-guess lineages.
- **Caveat:** the paper's cell-type names beyond the gate come from
  clustering the same protein data. They are not used.

## PXD046211: monocyte lines with and without PMA

- **Data** (PRIDE record):
  - THP-1 and U-937 cells, untreated or treated 48 h with PMA (a
    macrophage-like differentiation), as single cells, by the SCoPE2
    protocol;
  - TMTpro 16-plex with a 50-cell carrier, run on a Lumos and an Exploris 240
    (the CBIO batches) and a timsTOF SCP (GIGA);
  - searched with sage; "Mix" samples combine the two lines;
  - files: `quant.cbio.tsv` (the CBIO batches) and `sampleAnnotations.csv`.
- **Labels:** from the annotation. Single-cell channels of THP-1 or U-937 are
  scored as PMA or untreated. Mixes, carriers, references and empty or blank
  channels are excluded.
- **Upload:** every included cell together (each run's channels are already
  relative to the run, rule 7).
- **Primary:** S = P(macrophage) − P(classical, intermediate or
  non-classical monocyte, or monocyte). AUROC, PMA over untreated, both lines
  pooled; pass if p < 0.05.
- **Secondary:** AUROC per line; coarse best guesses.
- **Expectation, stated now:** a failure. The reference's macrophage class
  is monocyte-like, and SCoPE2's PMA signature is unrelated to it (run
  history, entry 33). The RNA rehearsal (entry 39) separated the reference's
  own classes; the protein rehearsal below, on SCoPE2, did not.

## The rehearsals, before this file was committed

Each intake and the scorer ran end to end (`--rehearse`) on development data
or on a synthetic file in the documented layout. No held-out file was read.
Records: `research/benchmark/heldout/rehearsals/<set>.json`.

| Set | Rehearsed on | v4.1's primary | The others |
|---|---|---|---|
| Tian | Rieckmann 2017 (development), MaxQuant reader: its 13 steady-state T-cell populations from 4 donors in one upload; 16 pairs (donor, state) | 16 of 16 won, p = 1.5e-05 | All 16 won by v3.1, v4.2 and v5.2. CD8 bulks guessed CD8 T: v4.1 25.0% (NK 37.5%), v4.2 56.2%, v5.2 62.5%; correlation and PCA kNN 0%. v4.2 is circular here: its protein means come from these samples |
| PXD021882 | Rieckmann: 8 B and 32 conventional T bulks as the pools | AUROC 1.0, p = 0.0001 | v3.1 and v4.2 1.0, v5.2 0.969 |
| PXD043355 | Synthetic Proteome Discoverer files from PBMC240 (development): 30 lymphoid cells as "Jurkat", 24 cells with their values shuffled among their proteins as "HeLa"; the reader reproduced the matrix exactly | AUROC 0.901, p = 0.0001 | v3.1 and v4.2 0.901, v5.2 0.871. The stand-in lymphoid cells were answered "myeloid" (a narrow upload), so the cell-line rule was right for 10% of them |
| PXD073250 | PXD070599 DS18 Astral-Zoom (development) as 76 immune and 10 double cells, 40 shuffled cells as keratinocytes, 5 runs without a gate left out | AUROC 0.769, p = 0.0001 | v3.1 and v4.2 0.769, v5.2 0.702 |
| PXD046211 | Synthetic sage PSMs from SCoPE2 reprocessed (development): 814 macrophages as "PMA", 314 monocytes as "untreated", runs of 12 cells alternating the two "lines", with carrier, reference, empty and mix channels and a decoy PSM per run | AUROC 0.338, p = 1.0: fails, as predicted | v3.1 0.342, v4.2 0.338, v5.2 0.406 |

The shuffled cells are a low bar: a real HeLa cell or keratinocyte may sit
closer to the reference.

## Outputs, at scoring only

`research/benchmark/heldout/<set>/`: `summary.json` (every candidate's
primary and secondary measures, the baselines' and the statement above) and
`scores.csv` (per sample).

## Amendments

### 1, 2026-10-16: the candidates are final

Phase 2 of the Goal 2 plan froze no new candidate: Hao's dendritic cells in
the class centres and the out-of-distribution scores were NO GO (run history,
entries 40 and 41), and the single-type-upload candidate was dropped after
its probe (entry 36). The candidates are those of rule 1 as written: v4.1
(the headline), v4.2 and v5.2, with v3.1 for reference. Unsealing may begin
(`side-tests.md`, amendment 5).

### 2, 2026-10-16: format fixes found at unsealing

Each fix was needed to read a deposit as its documentation describes. No
rule, group, statistic or threshold changed. The hand-written label maps
(Tian, PXD073250, PXD046211) follow the protocol's rules, and each one's
reason was recorded with it (`labels.json`) before its intake ran. This
amendment was committed after Tian, PXD043355 and PXD073250 were scored,
and before PXD046211 was.

- **Tian.**
  - Sample names use T-cell shorthand: T8 for CD8 (naive, central memory,
    effector memory, TEMRA); Th1, Th2, Th17 and Treg for CD4.
  - One patient's "Tnaive" carries no CD4 or CD8 mark, so it is CD3,
    unscored.
  - Quality-control runs are excluded.
  - The CD3CD4CD8 file names no patient, so its samples are one source.
  - The CD4 samples are functional subsets with no naive or memory state, so
    the MM file yields no (patient, state) pair. The set has one pair: void,
    by the rule as written.
- **PXD021882.**
  - The deposited MaxQuant table holds only HeLa runs of 0 to 500 cells. The
    B and T pools were searched with FragPipe and are not in it.
  - The reader took three empty wells in plate row B ("0cell_B16") for B
    pools. Without that misreading the table has no B or T pool: void, by
    the rule as written. Nothing was scored.
- **PXD073250.**
  - The supplement names cells by plate and well, the matrix names runs by
    plate, population and injection, and no column links the two.
  - Each supplement cell was linked to the run whose log intensities
    correlate best with its own, over proteins observed in both:
    - 419 cells to 419 distinct runs, each on its own plate;
    - median r 0.995, against 0.915 for the next run;
    - smallest margin 0.017.
  - The 110 single-cell runs absent from the supplement have no gate and
    are excluded.
- **PXD046211.**
  - The annotation is separated by semicolons. It spells PMA-treated cells
    "THP1_dif" and "U937_dif".
  - "Single-cell channels" are those of sample type SC holding one cell.
    Excluded:
    - single-cell equivalents (diluted bulk lysate);
    - 2- and 4-cell channels;
    - the GIGA batch, which is not in `quant.cbio.tsv`.
    That leaves 336 cells.
  - The deposit holds sage's two outputs apart. So `quant.cbio.tsv`
    (reporter intensities per scan) is joined to `results.sage.cbio.tsv`
    (identifications, fetched now and checked against the deposit's
    published SHA-1) on run and scan. Each scan keeps its rank-1 target
    match.
  - This sage version names its q-values spectrum_fdr, peptide_fdr and
    protein_fdr.
