# Z-score step notes, written after the run

The report beside this file is generated; these notes explain it against
`valuescale/bank/expectations/zscore.json`, written before the change and
not edited after. The change: `alignment.zscore_per_gene` computes each
gene's mean and spread in float64 and returns float32, and a gene whose
observed values agree to about five significant digits
(`config.ZSCORE_NEAR_CONSTANT_SPREAD`, 1e-5 of its largest absolute value)
is 0, as a gene with one value already was.

## What it fixes, as expected

- **Z1, the z-score invariant, holds on all 30 traced tables** under the
  automatic, linear and log readings, Phase A's five failures included
  (`../value_scale_phaseA/notes.md`). On the first run furtwangler_batchcorr
  read as linear still failed: the check itself treated only an exactly
  constant gene as constant. It now applies the same rule as the service,
  as the expectation words it ("all 0 for a constant or near-constant
  gene").
- **Z2, near-constant genes:** none under any table's automatic reading, so
  the rule zeroes nothing there; 10 in furtwangler_batchcorr read as
  linear, as Phase A counted.

## What it changes that I predicted wrongly (Z3)

Against the replies before Phase A, under the automatic reading:

- **Answers:** unchanged on 29 of the 30 tables. msv000099294_hmc3 changes 3
  of its 47 (lymphoid, T cell and myeloid become ambiguous), and with them
  the upload's agreement for the second opinion (0.109 to 0.087, both under
  the 0.4 needed). The prediction was at least 99% kept on every table.
  msv000099294_hmc3 is a linear table the rule reads as log, so its
  automatic reading is wrong either way.
- **Coordinates:** moved by more than the predicted 0.01 on 6 tables, at
  most 0.080 (pxd073250_diann).

The cause is smoothing's neighbour graph, not the z-scores' own error. Each
cell is smoothed with its 15 nearest neighbours, found from the z-scores; a
neighbour at a near-tie can change with the last digits. Comparing the
graphs built from the old and the new z-scores:

| Table | Cells | Neighbours changed | Largest move, those cells | Largest move, the others |
|---|---|---|---|---|
| pbmc240_diann | 238 | 11 | 0.039 | 0.000003 |
| pxd073250_diann | 557 | 93 | 0.080 | 0.0004 |
| msv000099294_hmc3 | 47 | 21 | 0.056 | 0.0001 |
| msv000099294_microglia | 57 | 15 | 0.049 | 0.011 |

Every changed answer is in a cell whose neighbours changed. Neither graph
is more right at a tie, but the new z-scores are the exact ones.

## Z4, the service's frozen comparisons: two fail, for the owner

- **v3's frozen replies** (`service/tests/test_pipeline_versions.py`,
  frozen from base bf315f7): one cell per dataset crosses v3's abstention
  cut-off. SCoPE2's cell 31 goes from basophil to no confident label, and
  PBMC240's cell 42 from no confident label to CD4 T. Every other number is
  within the test's 2.1e-6. The v3.1, v4 and v4.1 frozen comparisons and
  `test_golden_fixtures` pass unchanged.
- **The Workflow page's recorded trace** (`service/tests/test_workflow_trace.py`,
  v4.1 on PBMC240): the same 11 cells whose neighbours changed move beyond
  the trace's rounding (at most 0.009 in a recorded number). Every cell's
  label, level, label set and best guess are unchanged.

As the expectations said, accepting the change was the owner's decision,
and the owner accepted it (2026-10-28). No fixture was regenerated: the v3
test now names the two cells, with their new answers, as changed since
freezing (`CHANGED_SINCE_FREEZING`), and compares their other fields and
every other cell as before. The Workflow page was re-traced
(`scripts/trace_workflow.py`, `scripts/build_manifest.py`), and the one
figure drawn from the changed numbers, methods-reading, redrawn
(`scripts/build_figures.py`): its layout coordinates move in the fourth
decimal.

## Z5

Phase A's other stage invariants hold under each reading on every table.
