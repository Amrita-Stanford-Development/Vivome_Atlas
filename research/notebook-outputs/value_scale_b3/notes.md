# B3 notes, written after the run

The report beside this file is generated. These notes explain it against
`valuescale/bank/expectations/b3.json`. That file was written before the
frame was built and was not edited after the run. Two sections were added
to it later, each committed before the run it covers: `revisit` (a727c39)
and `audit_rubric` (5a3b44a). The clean-up's third visit has its own
expectations, `valuescale/bank/expectations/b3_revisit2.json` (`3963fcd`),
also written before it ran. The report and the counts below are as after
that visit.

No detector statistic, gate or verdict was computed on any drawn deposit.

## What B3 is, in plain words

**Where it fits.** Phase B builds the automatic raw-or-log detector, for
uploaders who don't know whether their protein table holds raw (linear) or
logged values. It is to come with a measured promise: "a real linear table
is missed at most 5% of the time, and the same for log". The steps:
- B0 wrote the rules;
- B1 measured what each mistake costs;
- B2 built the detector on the bank of known tables;
- B3 gathers fresh tables with known answers;
- B4 sets the thresholds on half of them;
- B5 to B7 wire it in, check the assembly, and score the other half once
  before it goes live.

**Why it was needed.** The detector was tuned on the bank, so the bank
cannot also prove its error rate. The promise needs tables the detector has
never seen, whose answer is already known. With α = δ = 0.05, 59 is the
smallest number per size group and half for which the promise can be made
at all.

**How it worked:**
1. **The list.** Every human PRIDE and MassIVE deposit of 2020 to 2026 in
   ProteomeXchange's index, without the sealed sets and anything this
   project had already used: 18,813 deposits.
2. **No picking.** The list was shuffled with a fixed seed. Each deposit
   went to calibration or test by a fixed coin flip (a hash of its
   accession). The walk went down the list in order and took each
   deposit's *first* table by a fixed rule. It kept the table when it had
   at least 20 columns and 200 rows and could be read. Nobody chose which
   tables went in: tables chosen for looking clean would make the promise
   look better than it is for real uploads.
3. **Answers from where a table came from, never from its numbers.**
   - A program's own output (MaxQuant's proteinGroups.txt, DIA-NN's
     pg_matrix and so on) is linear, because those programs write linear
     intensities.
   - A column named "log2 …" is log.
   - Labels read from the values would only test whether the detector
     agrees with a reading of the same kind of evidence it uses.
4. **A hand check of the labels.** A random 20% were judged from their file
   names, folders, column names and methods text, again never their
   values. The check catches, for example, a table normalised by someone
   and saved under MaxQuant's name.
5. **Size groups.** Thresholds are set separately for 20 to 49 columns, 50
   to 300, and 301 to 2,000. Each needs 59 tables in each half.

Calibration sets the thresholds in B4. The test half is not scored until B7,
and then once. B3 computed no detector number, so how the detector does on
these tables is not yet known.

## What the findings mean

- **The promise can be made for two size groups, not three.** Only 11
  tables reached 301 columns, as expected: large single-cell-style tables
  are rare in public deposits. A table with 500 columns gets the "50 to
  2,000" promise, learned mostly from smaller tables. B2 found that the
  detector's measures don't drift with size, which supports this, but it is
  an assumption.
- **The pooled group is only just full** (62 and 61, against 59). If B4 has
  to drop more than 3 calibration or 2 test tables with 50 or more columns,
  it goes back to the owner before calibration.
- **The labels can be trusted:** 80 of 81 passed the hand check.
- **The promise is an average over the corpus's software mix:** MaxQuant
  211, DIA-NN 119, Spectronaut 54, FragPipe 12, Proteome Discoverer 5. A
  software with few tables could fare worse without the average showing
  it.
- **No real log table was found.** The log side's promise rests on log
  copies made from linear tables, so it means "log files that look like a
  plain log of a program's output". Real log files are often normalised,
  imputed or batch-corrected as well. B2 already saw a heavily imputed log
  table read as linear. This is why the site asks uploaders for the reading
  (B5), and why the detector's reply must say so to those who don't know.
- **The one failed row is a miscount in the expectation,** not a fault in
  the data (below).
- **The read fixes did not change how a table was judged.** Every
  prediction for the second visit held. A failed read says nothing about a
  table's values.

## The corpus

- **The frame:** 18,813 deposits. These are human PRIDE and MassIVE
  deposits announced from 2020-01-01 to 2026-10-31, after dropping the 3
  sealed accessions and the 53 accessions already tracked in the
  repository. 50.6% fall in calibration.
- **The walk:** it listed 10,000 deposits in the frame's order (5,051
  calibration, 4,949 test) and kept 402: 188 in calibration and 214 in
  test.
- **The third visit** (the clean-up, 2026-11-06; see below) kept 49 more,
  29 in calibration and 20 in test. 451 are kept now: 217 in calibration
  and 234 in test. 412 come from PRIDE and 39 from MassIVE.
- **After the audit:** 449 are kept. Two deposits are excluded: PXD039540
  (test) and PXD001608 (calibration, one of the third visit's; see below).
- **Labels:** every kept table is labelled linear. None is labelled log.
- **Software, after the audit:** MaxQuant 253, DIA-NN 120, Spectronaut 59,
  FragPipe 12, Proteome Discoverer 5.
- **Layouts, after the audit:** 372 wide tables, 50 Spectronaut pivots, 18
  long DIA-NN reports and 9 long Spectronaut reports.
- **Where the tables are:** each kept deposit's parsed table is in
  `data/incoming/value-scale-corpus/<accession>/table.npz`, ready for B4.

Kept linear deposits per stratum. A table counts in every stratum it
reaches, so a table with 400 columns counts in S1, S2 and S3. The report
counts after the audit:

| Stratum | Calibration | Test | Quota |
|---|---|---|---|
| S1, 20 or more columns | 216 | 233 | 59 |
| S2, 50 or more columns | 67 | 65 | 59 |
| S3, 301 or more columns | 3 | 8 | 59 |

Before the third visit these were 188 and 213, 62 and 61, and 3 and 8.

Why the 10,000 listed deposits were skipped or kept, after the third visit:

| Outcome | Deposits |
|---|---|
| no candidate table | 7,776 |
| too few columns | 1,568 |
| kept | 451 |
| unparseable | 96 |
| too large (one file over 500 MB) | 69 |
| too few rows | 14 |
| fetch failed | 14 |
| no file list | 12 |

69 of the 96 unparseable tables were refused on their header alone, as
SILAC or TMT MaxQuant searches, in the parser's own words. 11 more were
refused so on their full read: they were walked before the header refusal.
The other 16 are under "Found after the third visit", below.

## Rows that pass as expected

- **B3_records:** all 451 kept records have their file's URL, size and
  sha256 (for an archive member, the member's own sha256). Each parses
  into at least 20 columns and 200 rows, and has a label with its quote.
- **B3_quota_S1 and B3_quota_S2:** met in both splits.
- **B3_quota_S3:** short, as expected (see below).
- **B3_stop:** the walk stopped at 10,000 listed, because S3 could not be
  met.
- **B3_yield:** 4.51 kept per 100 listed, 4.02 before the third visit
  (expected 3 to 15).
- **B3_skips:** "no candidate" is the most common outcome, at 77.8% of
  listed deposits (expected over half).
- **B3_real_log:** fewer than 59 real log tables in each split. In fact
  there are none (see below).
- **B3_software:** MaxQuant is the most common software (expected DIA-NN or
  MaxQuant).
- **B3_audit:** 80 of 81 agree, 98.8% (expected at least 90%, hoped for at
  least 95%).
- **B3_audit_cleanup:** 48 of the 49 tables the third visit added agree,
  98.0% (b3_revisit2.json asked at least 90%).
- **B3_sealed:** no sealed accession was listed or opened.
- **B3_no_statistic:** a test, run in the valuescale suite: the draw imports
  none of the detector's gates, statistics, scores or methods.

## B3_frame fails: the expected count was wrong, not the frame

The row has four parts. Three pass:

- 3 sealed accessions dropped (expected at most 4);
- 53 tracked accessions dropped (expected 20 to 101);
- a calibration share of 0.5056 (expected 0.48 to 0.52).

The fourth part fails. Before the denylist, the frame keeps 18,869
deposits, against the 18,859 written in b3.json. That number was counted on
the index while frame.py was being written, and the counting made two
mistakes. Together they account for exactly the 10 extra deposits:

- **6 PRIDE deposits** (PXD054297, PXD061890, PXD064897, PXD065947,
  PXD066290, PXD069739). Each has a line break inside its title in the
  index file. For example, PXD061890's title "MDM2 degradation overcomes
  feedback regulation of p53 signaling in Merkel cell carcinoma" breaks
  after "Merkel cell".
  - The count read the index with Python's csv module, which starts a new
    row at every line break. Each of these records became two broken rows.
    The first holds only the accession and the start of the title. The
    second starts with the rest of the title, so its repository and species
    sit one column off. Neither row was counted.
  - In the whole index, 34 records are split this way: 57,944 records read
    as 57,978 rows. 6 of them are human PRIDE deposits of 2020 to 2026.
  - frame.py joins each record's lines back together at its own GetDataset
    link (a ruling made before the frame was built), and reads all six.
  - Corrected on 2026-11-06: an earlier version of these notes, and the
    message of commit `5c9e521`, said stray quote marks made the csv
    module merge records. Every record holds quote marks (its web links),
    and the csv module merged none; the cause is the line break.
- **4 MassIVE deposits** (PXD003148, PXD011903, PXD054458, PXD058144). Their
  species is written "homo sapiens" or "Homo Sapiens". The count matched
  "Homo sapiens" letter for letter. frame.py ignores letter case.

Recounting with the csv module and the exact-case match gives 17,346 PRIDE
and 1,513 MassIVE: 18,859, the expected number exactly. The frame itself
reads the index correctly. The owner accepted this row's failure on
2026-11-06 (below).

## S3 is short, as designed

S3 holds 3 linear deposits in calibration and 8 in test, against a quota of
59. The protocol plans for this: S3 pools with S2 into one stratum, "50 to
2,000", and the detector's reply names the pooled stratum.

The pooled stratum's counts are the S2 row: 62 in calibration and 61 in
test. That clears 59 by only 3 and 2. The audit's one exclusion has 24
columns, so it touches S1 only. If B4 ever has to drop more than 3
calibration tables or 2 test tables with 50 or more columns, the pooled
stratum falls short. The protocol says a short S1 or S2 goes to the owner
before calibration, and it would come back to you then.

## No real log tables

The walk found no table whose value columns name a log. The expectation,
fewer than 59 per split, holds, but zero is the far end of it. Native file
names (pg_matrix, proteinGroups, combined_protein, Proteins, reports) hold
the software's own output, and those programs write linear values. This
means:

- the log class is calibrated on the constructed variants alone (log2,
  log10, ln, or log2(x + 1), one per linear subsample), as the protocol
  allows;
- the real-log test stratum is empty, so it reports no rates and claims no
  guarantee;
- real log tables have been seen only in the design bank, in B2. The
  site's question to uploaders (B5) matters most for these tables.

## Faults found and fixed during the walk

Each fix was made test first, and each changed how the walk reads files,
never how it judges a table.

1. **One slow download held up the walk** (5c80051). The log is written in
   the frame's order, and only 64 deposits were in flight, so a 296 MB
   report at 250 KB/s stopped the log for over 10 minutes. Now 64
   deposits are in flight per worker, and one file uses at most 4
   connections.
2. **SILAC and TMT MaxQuant tables were fetched before being refused**
   (0c5ed21). A quarter of the bytes went to tables the parser then turned
   away on their header alone. The walk now applies the parser's own check
   to the header it has already read. Checked on the 56 wide tables already
   on disk: 56 of 56 got the same outcome, and the refused ones got the
   same words.
3. **A transfer PRIDE cut short was taken as complete, and MassIVE's
   "530" at an anonymous login was not retried** (bfd6451). A cut transfer
   now resumes where it stopped, on a new connection, and 530 is retried.
   Every read that had failed was visited once more after the walk (below).
4. **Parsed tables were saved in subfolders** for 95 of the deposits kept
   by then (37d44bf). There is now one place per deposit.
5. **The audit packets hid evidence** (5a3b44a, edd0281); see the audit
   below.

Before the walk proper there were four more read fixes: the old MassIVE
host (f08b8c5); raw-data archives not listed (0f3bf58); an archive member
fetched alone, by range (7c5e319); and shorter header reads (fb645a7).

## The second visit of failed reads

The second visit covered 93 records: 78 fetch failed and 15 no file list.
36 of them are now kept. The expectations for it were written at deposit
8,255, before it ran (b3.json, `revisit`):

| Failed at 8,255 | Expected | Found |
|---|---|---|
| short reads, 47 | at least 40 no longer fail | 47 |
| damaged zip, 15 | at least 8 no longer fail | 10; the other 5 are damaged in the repository (one archive is exactly 200 MiB and has no end record) |
| MassIVE 530, 5 | at least 4 listed | 5 |
| MassIVE listing after 5 tries, 6 | no expectation | all fail again: MassIVE ends the connection during a long listing |
| line endings of a lone CR, 4 | fail again | fail again |
| 550 Failed to open, 2 | fail again | fail again |
| MassIVE folder missing, 2 | fail again | fail again |
| any other record | unchanged, order kept | unchanged, order kept |

Every expectation was met. The visited records keep their first outcome as
`revisited_from`.

## The third visit (the clean-up)

The clean-up of 2026-11-06 fixed the faults in our own code that the walk
met (`76d490a`, then a code review's fixes in `3b4f162`), and visited the
103 records they touch a third time (`valuescale/corpus/cleanup_20261106.json`).
Its expectations, `valuescale/bank/expectations/b3_revisit2.json`, were
committed before the visit. A dated note in it, `changed_before_the_run`,
records the review's changes, also made before the visit.

Before, the 103 were 69 unparseable, 19 fetch failed, 12 no file list, 2
kept and 1 too few columns. After, 51 are kept (49 of them new), 14 fetch
failed, 12 too few columns, 12 no file list, 6 too few rows, 5 unparseable
(the SILAC and TMT searches) and 3 no candidate.

| Group | Expected | Found |
|---|---|---|
| header probe, 199 headers | no expectation | none names a quantity column now |
| line endings, 6 | none fails on a new-line again; PXD005285 and at least 4 of the 5 failed reads reach a later rule | none does; all 6 reach one (3 too few columns, 3 no candidate) |
| MaxQuant, 54 | none fails on text in an annotation column; the 4 SILAC and 1 TMT searches refused by name, on the header; at least 44 of the other 49 kept | none does; refused so; **43 kept** |
| Spectronaut, 5 | read, PXD038040 too (by the dated note) | all 5 kept |
| the 2 kept pivots that change reader | the same label, rows and columns | the same |
| macOS files, 7 | none chosen again | none: 1 kept, 6 too few columns |
| Windows-1252 long reports, 3 | no decoding failure | none: all 3 too few columns |
| damaged archives 10, missing MassIVE folders 3, not on the host 1 | fail again | fail again |
| "550 Failed to open" 4, MassIVE listings 8 | no expectation | fail again |
| any other record | unchanged, the order kept, earlier outcomes kept | so |
| the corpus | S1 and S2 still meet 59; S3 short, pooled with S2; no real log table | so |
| the report | every B3 row keeps its pass or fail | so; B3_frame still fails, as accepted |

**One row fails: MaxQuant, 43 kept against at least 44.** The other 6 of
the 49 stop at the row bar of 200: PXD002127, PXD003185, PXD017116,
PXD063561, PXD070622 and PXD080805. They are small tables. Their files hold
26 to 276 data rows. The reader leaves out what MaxQuant marks as a
contaminant, a reverse hit or identified only by site, as it does in a
table with gene names, and that leaves 1 to 110. This was counted from the
identifier and flag columns, not from the values. The parser is right. The
expected count was a guess made without row counts. The expectation stands
as written. The owner accepted the miss on 2026-11-07, after a closer look
(below, "The owner's decisions after the third visit").

The visited records keep their earlier outcomes in `revisited_from`, nested
when the second visit had already replaced one, and their reasons in
`revisited_for`.

## The audit

- **The sample:** a seeded 20% of each split's kept deposits, 38 in
  calibration and 43 in test, drawn by sha256("20261103:audit:" +
  accession).
- **The rubric:** written into b3.json and committed before any packet was
  made.
- **The packets:** each gives the table's headers, its place in the deposit
  and the deposit's methods text, never a value.
- **Who judged:** subagents judged each packet. Claude reread the
  disagreement and every tenth agreement (8). All nine verdicts stand.
- **The verdicts:** `valuescale/corpus/audit.json`.

**The first packets were faulty.** They cut the column list at 120 names,
and MaxQuant's Intensity and LFQ columns often come later (50 packets).
They cut the file list at 300 names (1 packet). And they read parquet
headers as text (3 packets).

The packets were rebuilt for all 81, and the 53 affected were judged again
by fresh subagents who were not told the first verdicts. Both judgements
agreed on all 53. The other 28 packets changed only in layout and keep
their first verdict.

**The one disagreement: PXD039540, excluded.** Its table is
`b_analysis_global_normalization/proteinGroups.txt` inside
`R_result.zip`. That is a folder named for a normalisation after MaxQuant,
which is the rubric's name rule. The deposit's MaxQuant output,
`MaxQuant_result_txt.zip`, is 678 MB, over the 500 MB archive bar, which is
why this copy was the first candidate. Its columns are MaxQuant's own set,
so it may be an unchanged copy. The rubric excludes it anyway.

**The one close call: PXD043293, agrees.** The file name ends "full_norm",
but the Spectronaut .params, .setup.txt and .log.txt files beside it show
it is Spectronaut's own report (directDIA, default settings). The
normalisation is Spectronaut's.

**Side notes from the judges.** None changes a verdict:

- PXD055784: the methods say Proteome Discoverer, but the deposit holds
  MaxQuant output;
- PXD035199: `txt_190614.zip` is 698 MB, so the walk took the deposit's
  other archive;
- PXD048456: the columns name runs DRIX033, the raw files DRIX055;
- PXD073754: the columns look like DIA-NN 2.x, but the methods say 1.8.1.

**The third visit's 49 tables** were judged the same way
(b3_revisit2.json, `audit`). Fresh subagents used the same rubric, on
packets built as the rebuilt ones were. 48 agree (98.0%; at least 90% was
asked). Claude reread the disagreement, the four verdicts marked doubt, two
close calls a judge named, and every tenth agreement in accession order
(4). All eleven verdicts stand.

- **The disagreement: PXD001608, excluded.** Its proteinGroups.txt, in
  `CombinedTxtFiles.zip`, has a Perseus annotation row ("#!{Type}E ...")
  under its header, so it was saved from Perseus: the rubric's first line.
  That is also why its first column is a sample.
- **The doubts, all agreements:**
  - PXD016620: the methods load a "modified" proteinGroups.txt into
    Perseus, but the change is a filter, and the log2 is done in Perseus;
  - PXD017104: a quantile normalisation, not placed in the deposited
    table;
  - PXD029954: a normalisation of the viral proteins alone;
  - PXD065519: a total-sum scaling, not placed in Spectronaut's own
    report.
- **A side note, PXD054457:** it is in MaxQuant 1.0 to 1.2's spelling, with
  "LFQ Intensity" columns. The parser's quantity patterns are
  case-sensitive, so it read the "Intensity" columns, not LFQ. Both are
  MaxQuant's own linear output, so the label stands. It is the only such
  table among the 291 local MaxQuant tables.

## Reads that still fail

26 deposits are skipped because a read failed even after the third visit.
They are counted under the two skip reasons b3.json added to the
protocol's list. A failed read says nothing about a table's values, so
these skips do not lean the labels either way.

- **Fetch failed, 14:**
  - 10 archives that zipfile cannot open (damaged or truncated in the
    repository);
  - 4 files PRIDE's FTP lists but will not open ("550 Failed to open
    file").
- **No file list, 12:**
  - 8 MassIVE listings the server cut off on every one of 5 tries;
  - 3 MassIVE folders that do not exist;
  - 1 dataset not on MassIVE's FTP host.

The 5 tables whose lines end in a lone CR read now: 2 have too few columns
and 3 deposits have no candidate table.

## Found after the third visit

The 27 unparseable tables the clean-up did not select were read again for
their structure alone: sizes, first bytes, delimiters and identifier
columns, never a value.

- **11 SILAC or TMT MaxQuant searches,** refused in words on their full
  read.
- **6 are the files' own:**
  - two files of zero bytes in PRIDE itself (PXD055195, PXD055196);
  - a pg_matrix with no data rows (PXD046550);
  - a Spectronaut report named "Perseus_filtered_Imputed" (PXD084424);
  - a placeholder proteinGroups.txt, "PRM no search was performed"
    (PXD063781);
  - a DIA-NN report with decimal points and decimal commas mixed in its
    rows (PXD062541).
- **7 are faults in our own code, not yet fixed:**
  - a DIA-NN pg_matrix whose Genes column is empty (its FASTA gave no gene
    names) is refused, though Protein.Group names every row by UniProt
    accessions: PXD064789 (test), PXD070147 and PXD059079 (calibration). It
    is the DIA-NN twin of MaxQuant without "Gene names";
  - the delimiter is chosen from the header alone, so a tab-separated
    pg_matrix whose run names hold commas is split on commas: PXD053397
    (test) and PXD053298 (calibration). The service, the site's check and
    the corpus header reader share this rule;
  - an empty archive member was chosen as the table: PXD056559 (test) and
    PXD046085 (calibration).
- **3 write decimal commas,** as Spectronaut does under a European locale:
  two long reports (PXD047604, PXD036850) and a pivot (PXD043761). Reading
  them needs a rule that tells a decimal comma from a thousands separator.

## PRIDE's speed

EBI's transfer host was the limit throughout:

- 0.70 MB/s at the smoke test;
- 120 to 180 KB/s during most of the walk;
- 57 KB/s at its slowest.

The same PC got 4.8 to 6.8 MB/s from GitHub. The header refusal (fix 2)
saved the most time. The faster routes raised earlier, EBI's Aspera tool or
a stop below 10,000, are no longer needed, because the walk finished at
10,000.

## Asked of the owner (answered below)

1. **Accept B3_frame's failure:** the expected count was wrong, as
   explained above.
2. **For review, no decision needed:**
   - the protocol's amendment 2 lists every way B3 found and read the
     tables that differs from the protocol's text. Each was Claude's ruling
     during the walk;
   - `research/benchmark/side-tests.md` amendment 25 records the detector's
     sealed test and calibration deposits.

## The owner's decisions (2026-11-06)

1. **B3_frame's failure is accepted,** as explained above.
2. **A clean-up before B4.** It began with the line endings. The same
   day the owner widened it to every fault in our own code that B3's walk
   met:
   - fixed test first, in the service's parser, the site's file check and
     the corpus tool: lone-CR line endings; MaxQuant tables without "Gene
     names" (named by their protein IDs), and MaxQuant 1.0 to 1.2's
     title-case names; Spectronaut pivots without PG.Genes or without the
     "PG." prefix (a code review dropped a refusal of peptide-level pivots
     before the third visit ran: the parser already read them); macOS
     companion files ("._"), never chosen again; long reports in
     Windows-1252, read as the service reads an upload;
   - every record these touch, and B3's 31 remaining failed reads, visited
     a third time, with the expectations committed first;
   - every table this adds judged under the audit rubric.

   The fixes are in `76d490a`. The expectations are in
   `valuescale/bank/expectations/b3_revisit2.json` and protocol amendment 3
   (`3963fcd`). The selection is 103 records (`05f544d`); the header probe
   added none. The visit's results are under "The third visit", above.
3. **The 8,813 deposits the walk did not list stay unlisted,** as a
   reserve. If B4's calibration shows the method must change, the
   calibration split becomes design data and fresh calibration is drawn
   from the reserve. The test split stays sealed either way.

## Asked of the owner after the third visit (answered below)

1. **Accept the MaxQuant row's miss** (43 kept against at least 44), as
   explained under "The third visit".
2. **The 7 faults found after the visit:** fix them, test first, with a
   fourth visit of their records and expectations written first, or go to
   B4 with them as stated limits.
3. **Decimal commas:** read them, or refuse them in words.
4. **PXD054457's "LFQ Intensity":** match MaxQuant's quantity columns in any
   case, or leave it.

## The owner's decisions after the third visit (2026-11-07)

1. **The MaxQuant row's miss is accepted,** after a closer look at the six
   tables. Each is small because of what was measured, and the reader leaves
   out only MaxQuant's own contaminant, reverse and site-only rows, as in
   every MaxQuant table. Deposit names and file sizes only:

   | Table | Split | Experiment | Rows in the file | Read |
   |---|---|---|---|---|
   | PXD002127 | calibration | the phosphoproteome of PINK1 in HEK293 cells | 276 | 110 |
   | PXD003185 | calibration | an in vitro kinase assay on recombinant FLNc | 98 | 18 |
   | PXD017116 | test | the vitreous body in diabetic retinopathy | 102 | 87 |
   | PXD063561 | test | purified engineered albumin variants | 26 | 1 |
   | PXD070622 | test | the protein corona of lipid nanoparticles | 91 | 72 |
   | PXD080805 | calibration | the paleoproteomics of teeth | 43 | 6 |

   Two follow the walk's fixed rules, which stay as they are:
   - PXD063561 holds a larger table, `txt_exp1/proteinGroups_Jeannette_P10524-P10559.txt`
     (2.7 MB), which the walk's name order passes over;
   - PXD002127's other archive is 549 MB, over the 500 MB bar. Its table
     would reach 247 rows if the 137 site-only rows were kept.
2. **The seven faults found after the third visit are fixed,** test first,
   in the service, the site's check and the corpus tool. A fourth visit of
   the records they touch follows, with its expectations written first.
3. **A table with decimal commas is refused in clear words:** the refusal
   says what the file holds and asks for a decimal point. A reading that
   took "1,234" for 1.234, or the reverse, would be a thousandfold error,
   the very mistake the detector is for.
4. **MaxQuant's quantity columns are matched in any case,** so PXD054457
   is read from its "LFQ Intensity" columns. It is visited again with the
   seven.
