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

`bank/expectations/` holds each step's expected outcomes, written before the
step runs. The diagnostics that check them are
`research/notebooks/value_scale_diagnostics.py`.

## Commands

From the repository root, with the vivome environment:

```bash
python -m valuescale.corpus.fetch                    # download the bank, record sha256s
python -m valuescale.corpus.extract                  # upload-ready files
python research/notebooks/value_scale_diagnostics.py --step step1
python -m unittest discover -s valuescale/tests -t .
```

Downloads and extracted files go to `data/incoming/value-scale-bank/`, which
is not tracked.
