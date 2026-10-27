# Protocol: PXD064083, sorted single T and B cells

**No data file of this deposit has been downloaded or read.** This protocol
was written on 2026-10-27, before any search output, protein value or model
output on PXD064083 existed here. What has been seen is the ProteomeXchange
record (title, description, instruments, contact) and its file list. The
file list's run names carry each cell's population (Tcell, Bcell), its donor
and a replicate number: the search of 2026-10-21 counted about 78 T and 70 B
runs from it (`research/reference-data-search.md`), and the list was printed
again on 2026-10-27 while planning the intake. Nothing here is tuned, so
knowing the labels' design changes no choice below.

- **Freezing.** This file is frozen at the commit that adds it. Anything that
  must change before scoring goes in a dated amendment at the end, committed
  first. After the label map is built, only format fixes (rule 9).
- **One scoring.** The set is scored once.
- **What a result means.** Single T and B cells isolated by their surface
  markers (CD3, CD19), so the labels are independent of the protein data.
  It is a T-against-B lineage test, not a test of finer types, from one lab,
  one instrument family and the blood of ALS patients and healthy controls.
  Its role is set in `research/benchmark/side-tests.md`, amendment 24.

## Data

- **The deposit** (iProX IPX0011993000, ProteomeXchange PXD064083, Wong lab,
  Peking Union Medical College Hospital): "Plasma and single-cell immune
  proteomics in ALS patients", timsTOF Pro and timsTOF SCP, DIA-PASEF.
  - Folder IPX0011993002: the T-cell runs and `SEARCH_T.xlsx`.
  - Folder IPX0011993003: the B-cell runs and `SEARCH_B.xlsx`.
  - Folder IPX0011993001 (plasma) is not used, nor are the raw `.d` files.
- **The inputs** are the authors' two search outputs, `SEARCH_T.xlsx` and
  `SEARCH_B.xlsx`. Each lineage was searched apart.
- **The route.** iProX does not answer from the project's network (port 80,
  443 and 21 time out, 2026-10-27). The two files are fetched by hand from
  another network into `data/incoming/public_sets/PXD064083/`.

## Rules

1. **Sealed on receipt.** `python -m benchmark.pxd064083_intake --receive`
   records both files' sha256 in `research/benchmark/pxd064083/receipt.json`,
   committed before anything reads them. Every later step checks the files
   against it.
2. **Candidates,** as served with every reference cell, frozen by sha256
   (`benchmark/sorted_cd4cd8_intake.py`, `check_frozen`;
   `research/benchmark/protocol-sorted-cd4cd8.md`, rule 3 and amendments 3
   and 4): v4.1 (the headline, the served default), v4.2 and v5.2, with v3.1
   for reference. Scores come from the service's own code, as in
   `research/benchmark/protocol-heldout.md`, rule 2: the per-class best-guess
   probabilities are recomputed with the service's functions and must rank
   as the served best guess does on every cell.
3. **Reading.** Each file's sheets are read in order:
   - a long report is pivoted, one value per run and protein group:
     Spectronaut (`R.FileName`, `PG.Genes`, `PG.Quantity`) or DIA-NN (`Run`,
     `Genes`, `PG.MaxLFQ`);
   - any other sheet goes to the service's parser
     (`alignment.parse_matrix_csv`: a DIA-NN matrix, a Spectronaut
     protein-group pivot, MaxQuant, FragPipe).

   The first sheet read is the file's table.
4. **Labels,** from each run name: T when it contains "Tcell", B when it
   contains "Bcell" (case, spaces, underscores and hyphens ignored); a run
   naming neither or both is excluded and listed. The donor is the leading
   HC<n> or ALS<n>, and the status HC or ALS. Each cell is taken from its own
   lineage's table. If one table holds at least 20 runs of each lineage, it
   is a joint search, and it alone is the upload.
5. **The upload.** Every T and B cell together, since a lineage uploaded
   alone collapses (`research/notebook-run-history.md`, entry 35).
   - Each table goes on the service's log scale, and its rows are merged to
     one per gene by per-cell median: the service's Stage 0 and Stage 1
     rules. A gene is its feature-space symbol, else its first listed
     identifier.
   - Each gene is then one row over every cell, its values from each cell's
     own table. So no row is observed in one lineage only because of the
     search it came from.
   - **Primary:** the genes both searches report.
   - **Secondary:** the union, every gene either reports, reported apart.
   - Two tables on different scales are a format fix (rule 9).
6. **Void** when either lineage has fewer than 20 cells, or no sheet of a
   file holds per-run protein quantities that rule 3 can read (unless a
   format fix reads it). A void test is recorded and not scored.
7. **Primary:** S = P(B) − P(CD4T or CD8T), over the coarse types of
   `benchmark/fulcher2026_score.py` (`COARSE`), on the primary upload. AUROC
   of S, B cells over T cells, with a one-sided p from 10,000 label
   permutations, seed 0, ties counted half. **Pass if p < 0.05.** This is
   the design pre-registered for PXD021882's B and T pools
   (`protocol-heldout.md`), on single cells. v4.1's result is the headline;
   every candidate is reported.
8. **Secondary,** reported and never deciding:
   - the AUROC on the union upload, and by donor status (HC, ALS);
   - the best guess's balanced accuracy over the two lineages. A guess is
     right when its class is in the cell's group in the reference hierarchy
     (B cell, or T cell);
   - the coarse best guesses and the abstention per lineage;
   - answers committed, and correct when committed at the stated level: a
     class or group in the cell's group, or the lymphoid lineage;
   - the corrected baselines, correlation and PCA with kNN
     (`benchmark/baselines_corrected.py`, dataset `heldout_pxd064083`,
     original labels, seed 0): their balanced accuracy and coarse calls.
9. **Format fixes.** After the label map, only a reader or identifier fix
   is allowed (a column spelled differently, a sheet laid out otherwise),
   each in an amendment with its reason, before the scoring. No rule,
   statistic or threshold changes.

## Caveats, stated alongside every result

- **Batch can stand in for the label.** Each lineage was searched apart,
  and may have been acquired apart. The primary upload removes genes whose
  presence depends on the search; it cannot remove a search's own scaling of
  the genes both report.
- **Two lineages make a narrow upload.** With only T and B cells in it, the
  per-upload scaling leaves the finer types less distinct. The rehearsal
  below shows it: v4.1 guessed CD4 or CD8 T for 48.6% of T cells (the rest
  spread over other classes, monocytes, B, DC and NK), though S still ranks
  the lineages apart.
- **Few cells per donor** (about five), and disease (ALS) in half the donors.

## Unsealing, in this order

1. The files fetched by hand; `--receive`; the receipt committed.
2. `python -m benchmark.pxd064083_intake --labels`: the label map, from the
   run names, written once with its sha256.
3. `python -m benchmark.pxd064083_intake`: the intake, once. It writes the
   per-cell tables, the probabilities and the baselines' matrix.
4. The two baselines, seed 0.
5. `python -m benchmark.pxd064083_score`, once; it refuses to run again. It
   writes `research/benchmark/heldout/pxd064083/` (`summary.json`,
   `scores.csv`).

## The rehearsal, before this file was committed

`--rehearse` on both scripts ran end to end. The data was Fulcher 2026
(development data; its labels come from clustering): its 102 B cells and 489
CD4 and CD8 T cells, written as two Spectronaut protein-group pivot reports in
`.xlsx`. Each report held only its lineage's cells and the proteins seen in
them, with the runs named in the deposit's pattern. The merge kept 1,599
genes reported by both (1,593 in the feature space) of 1,660 in either. No
PXD064083 file was read. Record:
`research/benchmark/heldout/rehearsals/pxd064083.json`.

| | v4.1 | v3.1 | v4.2 | v5.2 |
|---|---|---|---|---|
| Primary AUROC, B over T (p) | 0.950 (0.0001) | 0.957 | 0.950 | 0.951 |
| AUROC, union upload | 0.950 | 0.957 | 0.950 | 0.951 |
| Best guess balanced accuracy | 71.0 (B 84.3, T 57.7) | 70.1 | 71.0 | 64.0 |
| Answers committed; correct when committed | 47.6%; 77.6% | 47.7%; 77.3% | 47.6%; 77.6% | 53.5%; 61.1% |

Baselines on the same matrix: correlation 35.7 and PCA with kNN 55.8
balanced accuracy. The narrow upload is visible: on Fulcher's full upload,
v4.1's answers are correct when committed for 97.9% of cells.

## Amendments

### 1, 2026-10-27, before any model output was looked at: a secondary on the log2 scale

**Where it stood.** The files arrived and were received (`da15a5b`). The
label map was built: 148 cells, 78 T and 70 B, 16 donors each, none
excluded. The intake ran both uploads through every candidate and wrote
their outputs, but none of those outputs has been opened.

**What the intake's label-free facts show.**
- Each file holds one sheet ("Sheet3" in `SEARCH_T.xlsx`, "Sheet4" in
  `SEARCH_B.xlsx`): `PG.Genes` and one column per run, with no empty value.
- Both have 2,508 rows with the same gene names in the same order, except
  three rows. Those are unnamed in `SEARCH_T.xlsx` and named by accession in
  `SEARCH_B.xlsx` (P0DOX2, P0DOX7, P0DOX8). The shared protein list suggests
  one search exported per lineage.
- Zeros make up 43.9% and 46.6% of the values.
- The non-zero values run from 0.81 and 0.87 (1st percentile) through a
  median of 6.99 and 7.92 to a maximum of 91,500 and 211,000.
- These are linear quantities on a small scale: a log2 table cannot span
  five orders of magnitude.
- The service's Stage 0 reads a table as linear only when its non-zero median
  is above 50. So it reads these as log: it takes no log2, and it counts a 0
  as a measured value.

**The owner's decision (2026-10-27).**
- **The primary is unchanged** (rule 7), and it alone decides. It measures
  the service on this file as the service reads it.
- **Added, a secondary that never decides.** The primary upload (rule 5) is
  rebuilt from each table read as the service reads a file it recognises as
  linear: 0 not detected, every other value log2. It gets every candidate as
  served, rule 8's measures, and the two baselines on its matrix (dataset
  `heldout_pxd064083_log2`; `benchmark/pxd064083_intake.py --log2`). It is
  reported beside the primary, never instead of it.
- **This departs from rule 9,** which allows only format fixes once the
  label map exists. It adds a measure and changes none. It was decided on
  the label-free facts above, before any model output was looked at.

**Rehearsed** on Fulcher 2026's two reports, which the service already reads
as linear: the secondary equals the primary on every figure, for every
candidate and both baselines (`research/benchmark/heldout/rehearsals/pxd064083.json`).

**The service's misreading** of such a file is a service fault, recorded in
`research/todo.md`. It changes nothing served here.
