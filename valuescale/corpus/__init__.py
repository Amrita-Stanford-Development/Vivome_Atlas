"""The tables the detector is built and checked on, never shipped with it.

- The diagnostic bank (Step 1, the design split): which tables, where they
  come from, how each one is labelled linear or log before any statistic is
  computed (bank.json), and the tools that fetch them, turn them into
  upload-ready files and make labelled variants of them.
- The calibration and test corpus (B3): the frame (frame.py, frame.json),
  remote listing and reading (remote.py), each deposit's table and label
  (tables.py), the walk and its log (draw.py, walk.jsonl), and the hand
  audit's verdicts (audit.json). strata.py makes the protocol's subsamples
  and constructed log variants for B4."""
