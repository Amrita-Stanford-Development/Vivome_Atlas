# Protocol: the raw-or-log detector's calibration and sealed test (protein v1)

**No calibration or test deposit has been fetched or read.** This protocol
was written on 2026-11-03, before Phase B of `research/value-scale-plan.md`
built any part of the detector. What has been seen:
- the diagnostic bank's 37 tables (`valuescale/corpus/bank.json`), which are
  the design split;
- the ProteomeXchange index (titles, repositories, species, instruments,
  dates);
- the file names of 200 human PRIDE projects, in a yield pilot that read no
  file. 25 named a native protein table, 81 more held only archives, and the
  named tables had a median size of 3.9 MB.

- **Freezing.** This file is frozen at the commit that adds it. Anything that
  must change before the test is scored goes in a dated amendment at the
  end, committed first.
- **One scoring.** The sealed test is scored once
  (`valuescale/corpus/score_test.py`, which refuses a second run).
- **What a result means.** A guarantee and an error rate for public
  processed protein tables like those drawn here (human, PRIDE or MassIVE,
  2020–2026, from the tools listed under "Tables"). It is not a measurement
  on uploads to the site, which may differ: single-cell tables, hand-made
  matrices.

## The claim

For a protein table, the detector returns a set of readings:
- `{linear}`: take the log;
- `{log}`: use as given;
- `{linear, log}`: "can't tell";
- `{}`: "unlike either".

**For each true class y and each cell-count stratum:** the chance that y is
missing from the set is at most **α = 0.05**. This holds with probability at
least **1 − δ = 0.95** over the calibration draw (a Neyman–Pearson
"umbrella" threshold; Tong, Feng & Li, Sci Adv 2018).

**How the threshold is set:**
- **One score per class.** It combines the method's two kinds of score
  (typicality and discriminative, plan B2). The combination rule is fixed on
  the design split before any calibration statistic is computed.
- **Threshold:** the k-th smallest calibration score of class y in the
  stratum, with k the largest value for which P(Binomial(n, α) ≤ k − 1) ≤ δ.
  With n = 59 this is k = 1, the smallest score; n = 120 gives k = 2, and
  n = 200 gives k = 5.
- **Why one score:** two scores tested at α/2 each would need 146 deposits per
  class and stratum, against 59 for one. The ruling is in the plan's ledger
  for B0.

## Splits

- **The unit is the deposit** (one ProteomeXchange dataset). A deposit's
  subsamples and variants stay in its split.
- **Design:** every table already looked at. This is the bank, every data set
  on this PC, and PXD064083. The design split chooses the statistics, the
  gates, the score combination and B1's reading for "can't tell". It makes no
  guarantee claim.
- **Calibration:** fresh deposits, drawn as below, that set the thresholds.
  No detector statistic is computed on any of them until every calibration
  label is fixed and committed.
- **Test:** fresh deposits from the same draw, sealed.
  - Their files are fetched, checksummed, parsed and labelled by script,
    and that record is committed.
  - No detector statistic, gate or verdict is computed on them until the
    one scoring.
- **Assignment:** a deposit goes to calibration when
  int(sha256("20261103:" + accession), 16) is even, and to test otherwise.
  The rule is fixed in advance and independent of the draw order.

## The frame

- **The index:** `data/incoming/value-scale-corpus/px_index_2026-11-03.tsv`,
  ProteomeXchange's dataset index downloaded on 2026-11-03 (sha256
  `4002a4fcb830099561c49daf67d04a1a9e109338850a58c8f56817c5ab1ef0ea`).
- **Rows kept:** repository PRIDE or MassIVE; announced 2020-01-01 to
  2026-10-31; species including Homo sapiens.
- **Rows dropped before the draw:**
  - the sealed sets: PXD042367, MSV000094189, PXD052341 and PXD061065;
  - every PXD, MSV or IPX identifier in any file tracked by git at this
    protocol's commit. That covers the bank, every development and spent set,
    every alternative kept unused for later tests, and every search record.
  - MassIVE rows are checked under both their PXD and MSV identifiers.
- **Order:** the kept accessions sorted, then shuffled with
  `random.Random(20261103)`.

## Tables

The draw walks the order. For each deposit:

1. **File list:** the PRIDE Archive API (`/pride/ws/archive/v2/projects/<PXD>/files`)
   or MassIVE's FTP folder (`curl --ssl-reqd`, three levels deep).
2. **Candidates:** files whose names match a native protein table:
   - DIA-NN: `*pg_matrix.tsv`, or a main report (`*report.tsv`, `*report.parquet`)
     pivoted on PG.MaxLFQ, else PG.Quantity;
   - FragPipe: `combined_protein.tsv`, MaxLFQ Intensity, else Intensity;
   - MaxQuant: `proteinGroups*.txt`, LFQ intensity when any value is above 0,
     else Intensity (the service's rule);
   - Spectronaut: a report with PG.Quantity columns, pivot or long;
   - Proteome Discoverer: `*_Proteins.txt`, Abundance columns.

   Zip archives of 500 MB or less are listed, and their members are matched
   by the same names.
3. **One table per deposit:** the first candidate in this order: DIA-NN
   matrix, FragPipe, MaxQuant, Spectronaut, Proteome Discoverer, DIA-NN long
   report, then archive members. Ties go by file name.
4. **Eligible** when it parses into at least 20 sample columns and 200 protein
   rows, with the service's parser (`alignment.parse_matrix_csv`) or the
   bank's reader (`valuescale/corpus/extract.py`) for long reports.
   - Header lines may be read to count columns before a full fetch.
   - Every fetch records URL, size and sha256.
5. **Stop** when every quota below is met in both splits, or after 10,000
   deposits have been listed. A shortfall is reported, not filled by hand.

Each skipped deposit is counted by its reason: no candidate, too large,
unparseable, too few columns, unclear label, or audit disagreement.

## Labels

Labels are fixed by script, from provenance, before any statistic.

- **Linear:** a native output above. The quotes are the bank's, by software,
  in `bank.json` `quotes`: DIA-NN, MaxQuant, FragPipe, Spectronaut and
  Proteome Discoverer.
- **Log:** a column header naming a log (for example `Log2`, `LOG2(`, or
  `log10` in a column name).
  - These are the real log tables.
  - MSstats `ProteinLevelData` (LogIntensities) is labelled log when it is
    found. It is not sought.
- **Unclear, so excluded and counted:**
  - headers naming ratios, z-scores, imputation or a normalisation that
    changes the scale;
  - TMT-Integrator abundance tables (their documentation disagrees on the
    scale);
  - a table labelled linear that holds any negative value. Its provenance
    is wrong, since no native linear output has negatives.
- **Hand audit:** a seeded 20% sample of each split's labelled deposits.
  - The audit reads each one's headers, its place in the deposit and the
    paper's methods. It never reads values.
  - A deposit the audit disagrees with is excluded.
  - The agreement rate is reported. Below 90%, the work stops and goes to
    the owner.

## Strata, subsamples and the log class

- **Strata by the number of columns (cells or samples):**
  - S1: 20 to 49;
  - S2: 50 to 300;
  - S3: 301 to 2,000.
- **One subsample per deposit per stratum it reaches:**
  - the size is drawn uniformly from the stratum's range, capped by the
    table's own size;
  - the columns are drawn without replacement and kept in the table's order;
  - every row is kept, and missing values stay as the file has them;
  - each draw uses a generator seeded by sha256("20261103:" + accession +
    ":" + stratum).
- **Quotas:** at least 59 linear deposits per stratum in each split.
  - S3 is expected to fall short. If it does, it pools with S2 into one
    stratum "50 to 2,000", and the detector's reply names the pooled
    stratum.
  - A short S1 or S2 is reported to the owner before calibration.
- **The constructed log class:** each linear subsample gets one log variant,
  chosen by the subsample's seed:
  - log2(x), log10(x) or ln(x), with zeros made missing, as log tools do;
  - or log2(x + 1), with zeros kept as 0, the zero-imputed case. This is
    used only when the subsample's median positive value is at least 10.
    Otherwise log2(x) is used: a log1p of small values is still
    linear-shaped, and a label follows what the reading does.
- **Calibration of the log class** uses the constructed variants plus any
  real log tables in the calibration split.
- **Real log tables in the test split** form their own stratum. Their rates
  are reported with intervals. No guarantee is claimed for them unless
  there are at least 59.
- **Foreign tables** are made from calibration deposits only: z-scored per
  protein, 0/1 presence, and per-protein percentile ranks. They measure how
  often "unlike either" fires (power), with no guarantee.

## When the detector can't tell

The method under plan B2:
- If the median per-protein correlation between z(x) and z(log2 x) is at least
  0.98, the reply says the choice barely matters.
- Otherwise the service uses the reading that B1's cost study finds cheaper,
  warns, and offers the other reading.
- "Unlike either" is read the same way and flagged.

## Scoring (once)

On the sealed test, for each class (linear; constructed log; real log), each
stratum and the strata pooled, with Clopper–Pearson 95% intervals:
- **right:** the true class alone;
- **miss:** the true class absent from the set;
- **wrong:** the other class alone;
- **can't tell;**
- **unlike either.**

- **The guarantee check:** the guarantee is contradicted for a class and
  stratum when the one-sided 95% lower bound of its miss rate is above 0.05.
- **The primary comparison:**
  - **Tables:** the real linear test tables, all strata pooled.
  - **What is counted:** the share given the wrong reading by the service,
    against today's median-50 rule on the same tables.
    - The service's reading: a log verdict means no log is taken.
    - "Can't tell" and "unlike either" count by the reading B1 fixes.
  - **Test:** exact one-sided McNemar test, paired by table, α = 0.05.
  - **Hypothesis:** the detector misreads fewer tables.
- **Secondary results:**
  - every baseline rule in `valuescale/baselines.py` on the same tables
    (GEO2R, ExpressAnalyst, scGPT, Omics Playground, ProteoPy, Gemma,
    CellTypist, CIBERSORT, median-50);
  - risk against coverage;
  - results by software and by instrument family;
  - constructed against real log tables;
  - the power on foreign tables.
- **Before the test:** `score_test.py` runs end to end on the calibration
  split as a rehearsal. Its output checks the code, not the method.
- **Release:** the owner decides from the results (plan B7). No result
  releases anything by itself.

## Amendments

### 1. 2026-11-03: no "the choice barely matters" message

Written before any calibration or test deposit was fetched or read.

- **What changes:** "When the detector can't tell" loses its first bullet.
  On "can't tell" the service always reads the table as B1 fixed (linear),
  warns, and offers the other reading. No correlation threshold is applied.
- **Why:** B1's probe (`research/notebook-outputs/value_scale_b1/notes.md`,
  `posthoc.md`) computed the check's statistic on the design split. Seven
  bank tables reach 0.98, and on six of them the other reading changes 8 to
  20% of best guesses. The message would be wrong on most tables that
  reach the bar.
- **Decided by:** the owner, 2026-11-03.
- **Effect on scoring:** none. "Can't tell" was already counted by B1's
  reading.

### 2. 2026-11-06: how B3 found and read the tables

Written after B3's walk (plan B3). No detector statistic, gate or verdict
had been computed on any calibration or test deposit.

The walk differs from "Tables" and "Labels" above in the ways below. Claude
decided each one during B3, as a ruling in the plan's ledger, and made it
test first. Each was committed in code before the deposits it touches were
read, except the second visit, whose expectations were committed before it
ran. Most are also recorded in `valuescale/bank/expectations/b3.json`.

None of them changes the order of candidates, which table is a deposit's
first candidate, or how a table is labelled. They change how files are
found and read, and they add two skip reasons.

- **Reading files (b3.json, before any frame deposit was listed):** PRIDE
  files are read over FTP from ftp.pride.ebi.ac.uk, with at most 8
  connections; its HTTPS took 15 to 30 s to a first byte. MassIVE is read
  over FTP with TLS, with at most 4. The file lists come as in step 1.
- **MassIVE's old host (`f08b8c5`):** 899 of the frame's 1,507 MassIVE rows
  name ftp://massive.ucsd.edu, which no longer answers. Each such dataset is
  listed in its folder on massive-ftp.ucsd.edu. A dataset not on that host
  is "no file list".
- **Zipped raw instrument data is not listed (`0f3bf58`):** `*.d.zip`,
  `*.raw.zip`, `*.wiff.zip`, `*.mzML.zip`, `*.mgf.zip` and the like never
  hold a protein table. One MassIVE deposit had 421 of them. No record in
  the walk's log chose such a file.
- **Too large (b3.json, before the run):** a single file over 500 MB, the
  archives' bar. The text above names no bar for single files.
- **An archive member is fetched alone (`7c5e319`):** the member's bytes and
  the archive's central directory are fetched by range, and zipfile checks
  the member's CRC.
  - The record carries the member's size and sha256, and the archive's URL
    and listed size. It does not carry the archive's sha256.
  - This narrows step 4's "every fetch records URL, size and sha256": the
    table itself is pinned by its own sha256. All 113 kept archive members
    carry one.
- **The parser's refusal on a header (`0c5ed21`):** a MaxQuant table that the
  service's parser refuses on its header alone (a SILAC or TMT search) is
  "unparseable", in the parser's own words, without the full fetch. This
  goes beyond step 4's "header lines may be read to count columns".
  - Checked on the 56 wide tables already fetched: the same outcome on all
    56, and the same words on the 11 refused.
  - 64 deposits were refused on their header, and 11 earlier ones after a
    full fetch.
- **Two skip reasons beyond the list (b3.json):** "no file list", when a
  listing fails after retries, and "fetch failed".
- **A second visit of failed reads (`bfd6451`; expectations `a727c39`):**
  - Why: a transfer that PRIDE's FTP ended early had been taken as complete,
    and MassIVE's "530" at an anonymous login was not tried again.
  - After the walk stopped, every record whose read failed was visited once
    more, in its place in the log, keeping the outcome it replaced
    (`revisited_from`). 36 of the 93 are now kept.
- **Readers:** Proteome Discoverer tables and long reports are read by
  `valuescale/corpus/tables.py`, not `extract.py` as step 4 says.
- **Labels (b3.json):** the names of the chosen value columns only. A log
  needs "log2", "log10", "log(" or "ln(" in such a name; a bare "log" does
  not count. The unclear words are ratio, z-score, zscore, imput, scaled,
  centred, centered, quantile, vsn and combat.
- **The hand audit (b3.json `audit_rubric`, `5a3b44a`; `edd0281`):**
  - Subagents judged each packet under a rubric committed before any packet
    was made. Claude reread the disagreement and every tenth agreement.
  - A packet holds the table's headers (with any Perseus annotation rows),
    its place in the deposit and the methods. It never holds values.
  - The first packets cut the column and file lists short and misread
    parquet headers. The 53 they affected were judged again on rebuilt
    packets, and both judgements agreed on all 53.
- **Effect on scoring:** none on the rules above. The tables differ only in
  which deposits could be read.
- **Shown to the owner:** in B3's notes
  (`research/notebook-outputs/value_scale_b3/notes.md`) and here.

### 3. 2026-11-06: the clean-up before B4, and a third visit

Written after the clean-up's code (`76d490a`) and before its third visit
ran. No detector statistic, gate or verdict had been computed on any
calibration or test deposit.

B3's walk met faults in our own code: tables the walk could not read, or
read wrongly, because of the service's parser or the corpus tool, not
because of the files. The owner chose to fix all of them before B4
(2026-11-06; B3's notes, "The owner's decisions").

- **What changed, test first, in the service's parser, the site's file
  check and the corpus tool:**
  - a lone CR ends a line (Excel's "CSV (Macintosh)");
  - a MaxQuant table is known by "Majority protein IDs" in any case. Without
    "Gene names", its rows are named by their majority protein IDs: UniProt
    accessions, with decoys and contaminants left out;
  - a Spectronaut pivot is named by PG.Genes, else its protein groups, else
    its accessions, with or without the "PG." prefix. A peptide-level report
    is refused on its header, before the full fetch, as amendment 2's
    MaxQuant refusal is;
  - a macOS companion file ("._", or under `__MACOSX/`) is never a
    candidate;
  - every table is decoded as the service decodes an upload (UTF-16 by its
    byte order mark, UTF-8, else Windows-1252), and the header reader knows
    UTF-16 by its byte order mark.
- **Effect on step 4** ("eligible when it parses ... with the service's
  parser"): the wording stands, and the parser reads more tables. A table
  it read before is read as before, with one exception: a Spectronaut pivot
  whose only identifier column is PG.ProteinGroups was read as a plain
  matrix and is now read as Spectronaut's. Its cells are named by run, and a
  0 is missing, as the parser's Spectronaut rule says.
  - In B3's corpus this touches two kept tables, PXD046524 (calibration) and
    PXD037506 (test).
  - On the diagnostic bank it touches MSV000099294's two tables. Their values
    are identical (they hold no 0), and only their cells' names change.
    `valuescale/corpus/bank.json`, frozen on 2026-10-28, still lists their
    layout as "matrix", so a re-run of D1 would show `layout_as_listed`
    false for them.
- **A third visit:** every record the fixes touch is visited again, in its
  place in the log. It keeps its earlier outcomes (`revisited_from`) and its
  reasons (`revisited_for`).
  - The selection rule and the expectations are in
    `valuescale/bank/expectations/b3_revisit2.json`, committed before the
    run.
  - The selection itself is written to
    `valuescale/corpus/cleanup_20261106.json` before the visit.
- **The audit:** the rank-based sample is not redrawn. Every table the third
  visit adds is judged under the same rubric, and recorded under its own key.
- **A stated limit:** a "no candidate" record does not keep its file list.
  - A report missed because its header ended its lines in a lone CR, or was
    UTF-16, cannot be found without listing those 7,773 deposits again, and
    they are not listed again.
  - The walk chose a table in 2,215 deposits. It met 6 with lone CRs, and saw
    none in UTF-16.
- **Decided by:** the owner, 2026-11-06 (the scope). Claude decided the rules
  above, as rulings in the plan's ledger.
- **Effect on scoring:** none on the rules. The corpus gains the tables the
  service reads.
