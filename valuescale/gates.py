"""The gates: what decides a table by definition, before any statistic.

Values are genes x cells, NaN where missing. In order:
1. Non-finite values are missing.
2. **Negatives.** When at least NEGATIVE_SHARE of the observed values are
   below 0, the table is already transformed (log, centred, z-scored), so
   no log is taken. Fewer negatives are stray: they are made missing and the
   detector runs.
3. **Counts.** When every observed value is a non-negative integer, with at
   least MIN_DISTINCT_COUNTS distinct values, the table holds counts, so it
   is linear.
4. **Clean-up.** In each cell, values tied at the cell's minimum (two or
   more equal values) are made missing: zeros written for "not detected"
   and imputation spikes. Ties and minima are unchanged by x -> c*x and by
   x -> a + c*x, so the clean-up is too.

`clean` applies steps 1, 2's making-missing and 4 to any table, whatever the
gates would say: calibration scores every subsample on it (protocol
amendment 5).

The numbers are the B2 expectations' (valuescale/bank/expectations/b2.json):
real transformed tables are 15 to 50% negative, while a log2 of a linear
table on a small scale is 1 to 2% negative (the values below 1).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

NEGATIVE_SHARE = 0.01
MIN_DISTINCT_COUNTS = 20


@dataclass(frozen=True)
class GateResult:
    gate: str | None  # "negatives", "counts" or None
    reading: str | None  # "log", "linear" or None (the detector decides)
    values: np.ndarray  # float64, cleaned as above (when a gate fires: only non-finite made missing)
    negative_share: float
    stray_negatives: int
    non_finite: int
    min_ties: int


def _ties_at_minimum(values: np.ndarray) -> np.ndarray:
    """A mask of the values tied at their cell's minimum, in cells where two
    or more values share it."""
    observed = ~np.isnan(values)
    lowest = np.where(observed, values, np.inf).min(axis=0)
    at_min = observed & (values == lowest[None, :])
    return at_min & (at_min.sum(axis=0) >= 2)[None, :]


def gate(values: np.ndarray) -> GateResult:
    x = np.array(values, dtype=np.float64)  # a copy: the input is not changed
    bad = ~np.isfinite(x) & ~np.isnan(x)
    x[bad] = np.nan
    observed = ~np.isnan(x)
    n_observed = int(observed.sum())
    negative = observed & (x < 0)
    share = float(negative.sum() / n_observed) if n_observed else 0.0
    if n_observed and share >= NEGATIVE_SHARE:
        return GateResult("negatives", "log", x, share, 0, int(bad.sum()), 0)
    stray = int(negative.sum())
    x[negative] = np.nan
    seen = x[~np.isnan(x)]
    if seen.size and np.all(seen == np.floor(seen)) and np.unique(seen).size >= MIN_DISTINCT_COUNTS:
        return GateResult("counts", "linear", x, share, stray, int(bad.sum()), 0)
    ties = _ties_at_minimum(x)
    x[ties] = np.nan
    return GateResult(None, None, x, share, stray, int(bad.sum()), int(ties.sum()))


def clean(values: np.ndarray) -> np.ndarray:
    """The values cleaned as for a table no gate decides (non-finite values,
    negatives and ties at a cell's minimum made missing), whatever the gates
    would say. Calibration scores every subsample on these, gated or not
    (research/benchmark/protocol-value-scale.md, amendment 5)."""
    x = np.array(values, dtype=np.float64)
    x[~np.isfinite(x)] = np.nan
    x[x < 0] = np.nan
    x[_ties_at_minimum(x)] = np.nan
    return x
