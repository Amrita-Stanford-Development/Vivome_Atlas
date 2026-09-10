# Development placeholder — not production

`H_seed4.pt` is one of five seeds (`H_seed0.pt` through `H_seed4.pt`) from
the winning arm of the five-seed masking comparison recorded in
`../decisive_summary.json`. **Only this one seed was fetched** — the other
four were not downloaded into this repo.

At ~94 MB, close to GitHub's 100 MB hard limit for a plain git object, this
is tracked via **Git LFS** (`.gitattributes`) even though the repo's other
non-RNA files under that threshold are not — `git lfs pull` after cloning
to fetch it.

This answers exactly one question: *which architecture generalises best
under masking.* It is not the production model, and its output must never
be treated as one — anywhere it surfaces (logs, API responses, docs), it is
labelled as a development placeholder (`pipeline/encoder.py`'s
`model_version_label()`).

It is missing, relative to the full training recipe:

- the class imbalance correction (logit adjustment)
- the hubness penalty
- the sink penalty
- combination with query-time fuzzy smoothing — it was trained without it

It exists to wire up and test the backend pipeline end to end before the
real model exists, and for nothing else. Its default use is set in
`config.DEV_CHECKPOINT_PATH`, which `config.ENCODER_WEIGHTS_PATH` points at
by default — see `../../README.md` for what changes when the real
`reference_model.pt` lands.
