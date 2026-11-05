# valuescale

Is a quantification table (cells or samples × proteins) still on a linear
scale, so it needs a log? Or is it already log-transformed? Every tool we
found answers with a size threshold set by hand, with no measured error rate
(`research/value-scale-detection.md`). This package is being built to answer
with a guaranteed error rate, and to say "can't tell" when the numbers can't
decide. The plan is `research/value-scale-plan.md`.

It imports nothing from the projection service (`service/`), so it can leave
this repository unchanged later.

## What is built

Step 1, the diagnostic bank (`corpus/`):
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
- `strata.py` makes the protocol's subsamples per stratum and the
  constructed log variant of a linear subsample.

Phase B, B2, the method (numpy and the standard library only):
- `gates.py`: a real share of negatives means already transformed; whole
  numbers mean linear; stray negatives and ties at a cell's minimum are
  made missing.
- `statistics.py`: shape statistics unchanged by each class's nuisance
  (per-cell skew, kurtosis and tail, and how a protein's spread follows its
  level).
- `score.py`: one score per class, the smaller of a typicality rank and a
  probability, fitted on design tables grouped by deposit.
- `conformal.py`: thresholds with a guarantee (the umbrella order
  statistic), exact intervals, the answer set.
- `method.py`: `assess`, from a table to a verdict (linear, log, can't
  tell, unlike either) with its reason.

Phase B, B3, the corpus (`corpus/`, not shipped):
- `frame.py`: the draw's frame from ProteomeXchange's index, with the sealed
  and tracked accessions dropped, shuffled with the protocol's seed, and
  each deposit's split by its hash (`frame.json`).
- `remote.py`: a deposit's files listed and read remotely (PRIDE's API,
  MassIVE's FTP folder, zip archives through range requests).
- `tables.py`: which file is a deposit's table, the readers the service's
  parser lacks, and the provenance labels.
- `draw.py`: the walk, its log in the frame's order (`walk.jsonl`), the
  quotas and the stop rule, and the second visit of failed reads. The runner is
  `research/notebooks/value_scale_corpus.py`, which brings the service's
  parser.

`bank/expectations/` holds each step's expected outcomes, written before the
step runs. The diagnostics that check them are
`research/notebooks/value_scale_diagnostics.py`.

## Commands

From the repository root, with the vivome environment:

```bash
python -m valuescale.corpus.fetch                    # download the bank, record sha256s
python -m valuescale.corpus.extract                  # upload-ready files
python research/notebooks/value_scale_diagnostics.py --step step1
python -m valuescale.corpus.frame                    # B3: the draw's frame
python research/notebooks/value_scale_corpus.py walk # B3: the walk (hours; resumes)
python research/notebooks/value_scale_corpus.py revisit  # B3: failed reads again, once the walk has stopped
python -m unittest discover -s valuescale/tests -t .
```

Downloads and extracted files go to `data/incoming/value-scale-bank/` and
`data/incoming/value-scale-corpus/`, which are not tracked.
