# valuescale

Is a quantification table (cells or samples × proteins) still on a linear
scale, so it needs a log? Or is it already log-transformed? Every tool we
found answers with a size threshold set by hand, with no measured error rate
(`research/value-scale-detection.md`). This package is being built to answer
with a guaranteed error rate, and to say "can't tell" when the numbers can't
decide. The plan is `research/value-scale-plan.md`.

It imports nothing from the projection service (`service/`), so it can leave
this repository unchanged later.

## Where it stands

Phase B builds the calibrated detector in steps, each checked against
expectations written before it runs (`bank/expectations/`):
- **B0, the protocol** (`research/benchmark/protocol-value-scale.md`);
- **B1, what each mistake costs:** on "can't tell" the service reads linear;
- **B2, the method** (below);
- **B3, the corpus** (below);
- **B4, calibration** (below), with the score as amended before any
  calibration score (protocol amendment 5).

The service still uses its median rule until B5 wires this package in. Each
step's report and notes are in `research/notebook-outputs/value_scale_<step>/`,
and its entry is in `research/notebook-run-history.md`.

## What is built

Step 1, the diagnostic bank (`corpus/`), the design split:
- `bank.json` lists 37 real tables from public deposits and this project's
  data, each labelled linear or log from provenance before any statistic was
  computed: software documentation, a column or layer name, or the authors'
  own code, quoted with its source.
- `fetch.py` downloads the bank's tables and records every source file's
  sha256 in `bank-files.json`.
- `extract.py` turns each table into the file a user would upload.
- `variants.py` makes labelled variants of each table: rescaled, logged in
  another base, offset, normalised, subsampled, with extra missing values,
  and "foreign" tables that neither reading fits.
- `denylist.py` refuses the sealed test sets.

Phase B, B2, the method (numpy and the standard library only):
- `gates.py`: a real share of negatives means already transformed; whole
  numbers mean linear; stray negatives and ties at a cell's minimum are
  made missing.
- `statistics.py`: shape statistics unchanged by each class's nuisance
  (per-cell skew, kurtosis and tail, and how a protein's spread follows its
  level).
- `score.py`: one score per class, the probability of a ridge logistic
  regression fitted on design tables grouped by deposit (B2 took the
  smaller of it and a typicality rank; amendment 5 keeps the rank as a
  warning only).
- `conformal.py`: thresholds with a guarantee (the umbrella order
  statistic), exact intervals, the answer set.
- `method.py`: `assess`, from a table to a verdict (linear, log, can't
  tell, unlike either) with its reason; since B4, a table with no missing
  value gets "can't tell" (it may have been filled in), and a warning says
  when a table is farther from the design tables than any of them is from
  the rest.
- `corpus/strata.py`: the protocol's size groups (strata), one seeded
  subsample per stratum, and the constructed log variant of a linear
  subsample, for B4.

Phase B, B3, the corpus (`corpus/`, not shipped):
- `frame.py`: the draw's frame from ProteomeXchange's index, with the sealed
  and tracked accessions dropped, shuffled with the protocol's seed, and
  each deposit's split by its hash (`frame.json`: 18,813 deposits).
- `remote.py`: a deposit's files listed and read remotely (PRIDE's API and
  FTP, MassIVE's FTP folder over TLS, zip archives and their members through
  range requests, cut-short transfers resumed).
- `tables.py`: which file is a deposit's table, the readers the service's
  parser lacks, and the provenance labels.
- `draw.py`: the walk, its log in the frame's order (`walk.jsonl`), the
  quotas and the stop rule, and the revisits: of failed reads, or of a
  chosen set (B3's third and fourth visits), each keeping what it replaced. The runner is
  `research/notebooks/value_scale_corpus.py`, which brings the service's
  parser.
- `audit.json`: the hand audit's sample (a seeded 20% of each split's kept
  tables), the tables the clean-up's visits added, and their verdicts.

B3's result, after the clean-up's fourth visit: 10,000 deposits listed, 455
linear tables kept after the audit (218 calibration, 237 test), and no real
log table. Each kept table is parsed
into `data/incoming/value-scale-corpus/<accession>/table.npz`, which is not
tracked.

Phase B, B4, the package and its calibration:
- `__init__.py`: `detect(matrix)` returns a scale report (`report.py`): the
  verdict, the answer set, the reading to use (linear when the detector
  can't tell, as B1 found cheaper), the stratum, the probabilities and
  thresholds, the warning and the guarantee. `apply(matrix, reading)` reads
  the values as the service reads a protein table.
- `calibrated.py` reads the frozen calibration, `calibration/protein-v1.json`:
  per stratum (S1, 20 to 49 columns; S2+S3, 50 to 2,000) and class, the
  umbrella threshold with its n and k, the design model, and the calibration
  corpus's manifest.
- `baselines.py`: the rules other tools use (GEO2R, ExpressAnalyst, scGPT,
  Omics Playground, ProteoPy, Gemma, CellTypist, CIBERSORT) and the
  service's median-50, each copied from its source at a pinned commit.
- Not shipped: `corpus/calibrate.py` builds the calibration from the
  calibration split; `corpus/score_test.py` scores the sealed test once
  (B7), and `--rehearse` runs it on the calibration split instead.

B4's result (2026-11-07): `protein-v1`, from the 218 calibration deposits.
In S1 (20 to 49 columns) linear is in the answer from a probability of
0.812 and log from 0.931; in S2+S3 (50 to 2,000 columns), from 0.114 and
0.919. Every expectation was met but one, the no-gaps rule's, which the
owner accepted (`research/notebook-outputs/value_scale_b4/notes.md`).

`bank/expectations/` holds each step's expected outcomes, written before the
step runs. Each step has its own runner in `research/notebooks/`:
`value_scale_diagnostics.py` (Step 1, Phase A, A2 and the z-score step),
`value_scale_cost.py` (B1), `value_scale_method.py` (B2),
`value_scale_corpus.py` (B3) and `value_scale_calibrate.py` (B4).

## Commands

From the repository root, with the vivome environment:

```bash
python -m valuescale.corpus.fetch                    # download the bank, record sha256s
python -m valuescale.corpus.extract                  # upload-ready files
python research/notebooks/value_scale_diagnostics.py --step step1
python research/notebooks/value_scale_cost.py        # B1: what each mistake costs
python research/notebooks/value_scale_method.py      # B2: the method on the bank and its variants
python -m valuescale.corpus.frame                    # B3: the draw's frame
python research/notebooks/value_scale_corpus.py walk # B3: the walk (hours; resumes)
python research/notebooks/value_scale_corpus.py revisit       # B3: failed reads again, once the walk has stopped
python research/notebooks/value_scale_corpus.py cleanup-selection # B3: the records the clean-up of 2026-11-06 touches
python research/notebooks/value_scale_corpus.py revisit --cleanup # B3: the third visit of those records
python research/notebooks/value_scale_corpus.py fourth-visit-selection # B3: the records the fixes of 2026-11-07 touch
python research/notebooks/value_scale_corpus.py revisit --fourth  # B3: the fourth visit of those records
python research/notebooks/value_scale_corpus.py audit-sample  # B3: the hand audit's seeded sample
python research/notebooks/value_scale_corpus.py audit-cleanup # B3: the tables the clean-up's visits added, to be judged
python research/notebooks/value_scale_corpus.py audit-packets # B3: the audit's packets (headers and methods, never values)
python research/notebooks/value_scale_corpus.py report        # B3: the report against b3.json
python research/notebooks/value_scale_calibrate.py --part design    # B4: B2's model refitted, the no-gaps rule (bank only)
python research/notebooks/value_scale_calibrate.py --part calibrate # B4: writes calibration/protein-v1.json once, then the checks
python -m valuescale.corpus.score_test --rehearse OUT.json   # B4: the test's scorer, on the calibration split
python -m unittest discover -s valuescale/tests -t .
```

Downloads and extracted files go to `data/incoming/value-scale-bank/` and
`data/incoming/value-scale-corpus/`, which are not tracked.
