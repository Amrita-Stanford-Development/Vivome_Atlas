"""The statistics: shape properties that tell a linear table from a log one.

Values are genes x cells, NaN where missing, after the gates' clean-up
(valuescale/gates.py). Each feature is unchanged by the nuisance of every
class it is used for:
- a linear table is known only up to x -> c*x (units, normalisation);
- a log table only up to x -> a + c*x (base, offset, units).

**Core** (both classes; unchanged by x -> a + c*x, so by both):
- `bowley`: per cell, (Q75 + Q25 - 2 Q50)/(Q75 - Q25); the median over cells.
  Linear values are right-skewed, logs about symmetric.
- `moors`: per cell, ((E7 - E5) + (E3 - E1))/(E6 - E2) on octiles; the median.
- `tail`: per cell, (Q99 - Q50)/(Q75 - Q25); the median.
- `level_spread`: over up to 1,000 proteins, the Spearman correlation of a
  protein's spread (Q75 - Q50) on its level (median) across cells, missing
  values ranked lowest. On a linear scale the spread grows with the level
  (multiplicative error); after a log it does not.

**Side, both classes:** `missing_share`; `row_median_spread`, the IQR of
protein medians over the median of protein IQRs, which turns `level_spread`
off on per-protein-normalised tables; `cell_bowley_iqr`, how much the
per-cell skew varies across cells.

**Side, linear only** (unchanged by x -> c*x but not by x -> a + c*x):
`decades`, per cell log10(Q95/Q05), the median; `column_sum_cv`, the SD over
the mean of the column sums.

A per-cell statistic needs MIN_CELL_VALUES observed values in the cell, and
a table feature from them needs MIN_CELLS such cells; otherwise it is
missing (NaN), which the score allows for.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

CORE = ("bowley", "moors", "tail", "level_spread")
BOTH = ("missing_share", "row_median_spread", "cell_bowley_iqr")
LINEAR_ONLY = ("decades", "column_sum_cv")
FEATURES = CORE + BOTH + LINEAR_ONLY

MIN_CELL_VALUES = 20
MIN_CELLS = 5
MIN_PROTEIN_VALUES = 3  # for a protein's median and IQR in row_median_spread
LEVEL_SPREAD_PROTEINS = 1000
MIN_LEVEL_SPREAD_PROTEINS = 20
ROW_NORMALISED_BAR = 0.1

_PROBS = (0.05, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 0.95, 0.99)


def per_cell(values: np.ndarray) -> dict[str, np.ndarray]:
    """Each cell's bowley, moors, tail and decades (NaN for a cell with fewer
    than MIN_CELL_VALUES observed values, or no spread)."""
    x = np.asarray(values, dtype=np.float64)
    out = {name: np.full(x.shape[1], np.nan) for name in ("bowley", "moors", "tail", "decades")}
    for j in range(x.shape[1]):
        v = x[:, j]
        v = v[~np.isnan(v)]
        if v.size < MIN_CELL_VALUES:
            continue
        q05, e1, q25, e3, q50, e5, q75, e7, q95, q99 = np.quantile(v, _PROBS)
        iqr = q75 - q25
        if iqr > 0:
            out["bowley"][j] = (q75 + q25 - 2 * q50) / iqr
            out["moors"][j] = ((e7 - e5) + (e3 - e1)) / iqr  # E6 - E2 is Q75 - Q25
            out["tail"][j] = (q99 - q50) / iqr
        if q05 > 0:
            out["decades"][j] = math.log10(q95 / q05)
    return out


def _median_of(values: np.ndarray) -> float:
    v = values[np.isfinite(values)]
    return float(np.median(v)) if v.size >= MIN_CELLS else math.nan


def _row_quantiles(x: np.ndarray, probs) -> tuple[np.ndarray, np.ndarray]:
    """Per row, np.quantile's (linear) quantiles over the observed values,
    vectorised; returns (quantiles probs x rows, observed counts)."""
    s = np.sort(x, axis=1)  # NaN sorts last
    n = (~np.isnan(x)).sum(axis=1)
    rows = np.arange(x.shape[0])
    out = np.full((len(probs), x.shape[0]), np.nan)
    ok = n > 0
    for i, p in enumerate(probs):
        pos = p * (n[ok] - 1)
        lo = np.floor(pos).astype(int)
        hi = np.minimum(lo + 1, n[ok] - 1)
        frac = pos - lo
        a, b = s[rows[ok], lo], s[rows[ok], hi]
        out[i, ok] = a + (b - a) * frac
    return out, n


def row_median_spread(values: np.ndarray) -> float:
    (q25, q50, q75), n = _row_quantiles(np.asarray(values, dtype=np.float64), (0.25, 0.5, 0.75))
    keep = n >= MIN_PROTEIN_VALUES
    if keep.sum() < MIN_LEVEL_SPREAD_PROTEINS:
        return math.nan
    medians, iqrs = q50[keep], (q75 - q25)[keep]
    denominator = float(np.median(iqrs))
    if denominator <= 0:
        return math.nan
    return float(np.subtract(*np.quantile(medians, (0.75, 0.25))) / denominator)


def protein_level_spread(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per protein, its level (median over all cells) and spread (Q75 - Q50),
    missing values ranked lowest, as order statistics (no interpolation, so
    unchanged by x -> a + c*x). A protein missing in half the cells or more
    has no level (NaN), and then no spread."""
    filled = np.where(np.isnan(values), -np.inf, np.asarray(values, dtype=np.float64))
    q50, q75 = np.quantile(filled, (0.5, 0.75), axis=1, method="inverted_cdf")
    level = np.where(np.isfinite(q50), q50, np.nan)
    with np.errstate(invalid="ignore"):
        spread = np.where(np.isfinite(q50), q75 - q50, np.nan)
    return level, spread


def pattern_seed(values: np.ndarray) -> int:
    """A seed from the table's shape and missing-value pattern only, so the
    protein draw is the same under both nuisances."""
    mask = np.isnan(values)
    digest = hashlib.sha256(np.asarray(mask.shape, dtype=np.int64).tobytes() + np.packbits(mask).tobytes())
    return int.from_bytes(digest.digest()[:8], "little")


def _ranks(v: np.ndarray) -> np.ndarray:
    """Average ranks, ties shared."""
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(v.size)
    ranks[order] = np.arange(1, v.size + 1)
    _, inverse, counts = np.unique(v, return_inverse=True, return_counts=True)
    sums = np.bincount(inverse, weights=ranks)
    return sums[inverse] / counts[inverse]


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = _ranks(a), _ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return math.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def level_spread(values: np.ndarray) -> float:
    """Spreads are ranked at float32 precision, relative to their median:
    many tables hold exactly equal spreads (float32 or whole-number values),
    and a rescaled copy computes them with different last digits in float64,
    which would break those ties and move the correlation in its 6th digit."""
    level, spread = protein_level_spread(values)
    eligible = np.flatnonzero(np.isfinite(level) & np.isfinite(spread))
    if eligible.size < MIN_LEVEL_SPREAD_PROTEINS:
        return math.nan
    if eligible.size > LEVEL_SPREAD_PROTEINS:
        rng = np.random.default_rng(pattern_seed(values))
        eligible = np.sort(rng.choice(eligible, LEVEL_SPREAD_PROTEINS, replace=False))
    s = spread[eligible]
    typical = float(np.median(np.abs(s)))
    s = (s / (typical if typical > 0 else 1.0)).astype(np.float32).astype(np.float64)
    return spearman(level[eligible], s)


def column_sum_cv(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=np.float64)
    has = (~np.isnan(x)).any(axis=0)
    sums = np.nansum(x[:, has], axis=0)
    if sums.size < 2 or sums.mean() <= 0:
        return math.nan
    return float(sums.std() / sums.mean())


def features(values: np.ndarray) -> dict[str, float]:
    x = np.asarray(values, dtype=np.float64)
    cells = per_cell(x)
    bowley = cells["bowley"][np.isfinite(cells["bowley"])]
    out = {
        "bowley": _median_of(cells["bowley"]),
        "moors": _median_of(cells["moors"]),
        "tail": _median_of(cells["tail"]),
        "missing_share": float(np.isnan(x).mean()),
        "row_median_spread": row_median_spread(x),
        "cell_bowley_iqr": float(np.subtract(*np.quantile(bowley, (0.75, 0.25)))) if bowley.size >= MIN_CELLS else math.nan,
        "decades": _median_of(cells["decades"]),
        "column_sum_cv": column_sum_cv(x),
    }
    rms = out["row_median_spread"]
    out["level_spread"] = level_spread(x) if (not math.isnan(rms) and rms >= ROW_NORMALISED_BAR) else math.nan
    return {name: out[name] for name in FEATURES}
