# B3 notes, written after the run

The report beside this file is generated. These notes explain it against
`valuescale/bank/expectations/b3.json`. That file was written before the
frame was built and was not edited after the run. Two sections were added
to it later, each committed before the run it covers: `revisit` (a727c39)
and `audit_rubric` (5a3b44a).

No detector statistic, gate or verdict was computed on any drawn deposit.

## The corpus

- **The frame:** 18,813 deposits. These are human PRIDE and MassIVE
  deposits announced from 2020-01-01 to 2026-10-31, after dropping the 3
  sealed accessions and the 53 accessions already tracked in the
  repository. 50.6% fall in calibration.
- **The walk:** it listed 10,000 deposits in the frame's order (5,051
  calibration, 4,949 test) and kept 402: 188 in calibration and 214 in
  test. 368 come from PRIDE and 34 from MassIVE.
- **After the audit:** 401 are kept. One test deposit, PXD039540, is
  excluded (see below).
- **Labels:** every kept table is labelled linear. None is labelled log.
- **Software:** MaxQuant 211, DIA-NN 119, Spectronaut 54, FragPipe 12,
  Proteome Discoverer 5.
- **Layouts:** 330 wide tables, 45 Spectronaut pivots, 18 long DIA-NN
  reports and 9 long Spectronaut reports.
- **Where the tables are:** each kept deposit's parsed table is in
  `data/incoming/value-scale-corpus/<accession>/table.npz`, ready for B4.

Kept linear deposits per stratum. A table counts in every stratum it
reaches, so a table with 400 columns counts in S1, S2 and S3:

| Stratum | Calibration | Test | Quota |
|---|---|---|---|
| S1, 20 or more columns | 188 | 213 (212 after the audit) | 59 |
| S2, 50 or more columns | 62 | 61 | 59 |
| S3, 301 or more columns | 3 | 8 | 59 |

Why the 10,000 listed deposits were skipped or kept:

| Outcome | Deposits |
|---|---|
| no candidate table | 7,773 |
| too few columns | 1,557 |
| kept | 402 |
| unparseable | 160 |
| too large (one file over 500 MB) | 69 |
| fetch failed | 19 |
| no file list | 12 |
| too few rows | 8 |

64 of the 160 unparseable tables were refused on their header alone, as
SILAC or TMT MaxQuant searches, in the parser's own words.

## Rows that pass as expected

- **B3_records:** all 402 kept records have their file's URL, size and
  sha256 (for an archive member, the member's own sha256). Each parses
  into at least 20 columns and 200 rows, and has a label with its quote.
- **B3_quota_S1 and B3_quota_S2:** met in both splits.
- **B3_quota_S3:** short, as expected (see below).
- **B3_stop:** the walk stopped at 10,000 listed, because S3 could not be
  met.
- **B3_yield:** 4.02 kept per 100 listed (expected 3 to 15).
- **B3_skips:** "no candidate" is the most common outcome, at 77.7% of
  listed deposits (expected over half).
- **B3_real_log:** fewer than 59 real log tables in each split. In fact
  there are none (see below).
- **B3_software:** MaxQuant is the most common software (expected DIA-NN or
  MaxQuant).
- **B3_audit:** 80 of 81 agree, 98.8% (expected at least 90%, hoped for at
  least 95%).
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
  PXD066290, PXD069739). The count read the index with Python's csv
  module. Stray quotes in some titles made it merge each of these records
  into its neighbour, so they went uncounted. frame.py splits the index at
  each record's own GetDataset link and reads all six (a ruling in the
  ledger, made before the frame was built).
- **4 MassIVE deposits** (PXD003148, PXD011903, PXD054458, PXD058144). Their
  species is written "homo sapiens" or "Homo Sapiens". The count matched
  "Homo sapiens" letter for letter. frame.py ignores letter case.

Recounting with the csv module and the exact-case match gives 17,346 PRIDE
and 1,513 MassIVE: 18,859, the expected number exactly. The frame itself
reads the index correctly. **The owner is asked to accept this row's
failure before B4.**

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

## Reads that still fail

31 deposits are skipped because a read failed even after the second visit.
They are counted under the two skip reasons b3.json added to the
protocol's list. A failed read says nothing about a table's values, so
these skips do not lean the labels either way.

- **Fetch failed, 19:**
  - 10 archives that zipfile cannot open (damaged or truncated in the
    repository);
  - 5 tables whose lines end in a lone CR, which the csv reader refuses;
  - 4 files PRIDE's FTP lists but will not open ("550 Failed to open
    file").
- **No file list, 12:**
  - 8 MassIVE listings the server cut off on every one of 5 tries;
  - 3 MassIVE folders that do not exist;
  - 1 dataset not on MassIVE's FTP host.

## PRIDE's speed

EBI's transfer host was the limit throughout:

- 0.70 MB/s at the smoke test;
- 120 to 180 KB/s during most of the walk;
- 57 KB/s at its slowest.

The same PC got 4.8 to 6.8 MB/s from GitHub. The header refusal (fix 2)
saved the most time. The faster routes raised earlier, EBI's Aspera tool or
a stop below 10,000, are no longer needed, because the walk finished at
10,000.

## For the owner

1. **Accept B3_frame's failure:** the expected count was wrong, as
   explained above.
