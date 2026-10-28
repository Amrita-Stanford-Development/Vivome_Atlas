"""Labelled variants of a bank table: the same measurements on another scale,
offset, normalisation, size or missingness, each with a label fixed by how
it was made (research/value-scale-plan.md, Step 1c).

Values are genes x cells, NaN where missing, as alignment.parse_matrix_csv
returns them. A variant's label follows what a reading must do with it:
- "linear": still needs a log (any c * x, a normalisation that divides, 2**x
  of a log table);
- "log": already on a log scale (log of a linear table in any base, plus an
  offset, times a constant);
- "foreign": neither reading is right (z-scores, presence calls, ranks); a
  detector should say so rather than pick one.

log2(x + 1) is labelled "log" only because the table is first divided by its
smallest positive value, so the +1 is small beside every value; on values
far below 1 the same formula leaves a linear shape (the labelling rule in
the plan's B0). Every random draw comes from a generator seeded by the
entry and variant name, so a variant is the same on every run.
"""
from __future__ import annotations

import hashlib
from typing import Callable, Iterator

import numpy as np

SUBSAMPLE_SIZES = (20, 50, 300)
INDUCED_MISSING = (0.4, 0.7)


def rng_for(*names: str) -> np.random.Generator:
    seed = int.from_bytes(hashlib.sha256("/".join(names).encode()).digest()[:8], "little")
    return np.random.default_rng(seed)


def _positive(values: np.ndarray) -> np.ndarray:
    """A linear table with its zeros as missing (0 is "not detected")."""
    out = np.array(values, dtype=np.float64)
    out[out <= 0] = np.nan
    return out


def _subsample(values: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    cells = np.sort(rng.choice(values.shape[1], size=n, replace=False))
    return values[:, cells]


def induce_missing(values: np.ndarray, target: float, rng: np.random.Generator, log_values: np.ndarray) -> np.ndarray:
    """Removes observed values with a chance that falls with log intensity
    (logit-linear, Li & Smyth 2023), until about `target` of all entries are
    missing. `log_values` gives each entry's log intensity (the same table on
    a log scale); a table already more missing than `target` is unchanged."""
    out = np.array(values, dtype=np.float64)
    observed = ~np.isnan(out) & ~np.isnan(log_values)
    have = 1.0 - observed.mean()
    if have >= target or not observed.any():
        return out
    remove = (target - have) / observed.mean()  # share of observed values to drop
    z = log_values[observed]
    z = (z - np.median(z)) / max(np.std(z), 1e-12)
    lo, hi = -20.0, 20.0  # intercept solving mean(sigmoid(a - 2 z)) = remove
    for _ in range(60):
        mid = (lo + hi) / 2
        if (1 / (1 + np.exp(-(mid - 2.0 * z)))).mean() < remove:
            lo = mid
        else:
            hi = mid
    p = 1 / (1 + np.exp(-(lo - 2.0 * z)))
    drop = rng.random(p.size) < p
    idx = np.flatnonzero(observed.ravel())[drop]
    out.ravel()[idx] = np.nan
    return out


def _zscore_genes(log_values: np.ndarray) -> np.ndarray:
    mean = np.nanmean(log_values, axis=1, keepdims=True)
    sd = np.nanstd(log_values, axis=1, keepdims=True)
    return (log_values - mean) / np.where(sd > 0, sd, 1.0)


def _ranks(values: np.ndarray) -> np.ndarray:
    out = np.full(values.shape, np.nan)
    for j in range(values.shape[1]):
        col = values[:, j]
        ok = ~np.isnan(col)
        out[ok, j] = np.argsort(np.argsort(col[ok])) + 1.0
    return out


def variants(entry_id: str, values: np.ndarray, label: str) -> Iterator[tuple[str, np.ndarray, str]]:
    """(variant name, values, label) for one bank table whose own label is
    "linear" or "log". Log tables are taken as log2 (every log table in the
    bank is), so 2**x gives its linear form."""
    if label not in ("linear", "log"):
        raise ValueError(f"{entry_id}: variants need a linear or log table, not {label!r}")
    with np.errstate(all="ignore"):
        if label == "linear":
            lin = _positive(values)
            log2 = np.log2(lin)
        else:
            log2 = np.array(values, dtype=np.float64)
            lin = np.exp2(log2)
        made: list[tuple[str, Callable[[], np.ndarray], str]] = [
            ("times_1e-6", lambda: lin * 1e-6, "linear"),
            ("times_1e-3", lambda: lin * 1e-3, "linear"),
            ("times_1e3", lambda: lin * 1e3, "linear"),
            ("per_protein_median", lambda: lin / np.nanmedian(lin, axis=1, keepdims=True), "linear"),
            ("per_cell_cpm", lambda: lin / np.nansum(lin, axis=0, keepdims=True) * 1e6, "linear"),
            ("per_cell_percent", lambda: lin / np.nansum(lin, axis=0, keepdims=True) * 100, "linear"),
            ("log2", lambda: log2, "log"),
            ("log10", lambda: log2 * np.log10(2), "log"),
            ("ln", lambda: log2 * np.log(2), "log"),
            ("log2_plus1_after_min", lambda: np.log2(lin / np.nanmin(lin) + 1), "log"),
            ("log2_plus10", lambda: log2 + 10, "log"),
            ("log2_minus_min", lambda: log2 - np.nanmin(log2), "log"),
            ("log2_times_0.5", lambda: log2 * 0.5, "log"),
            ("log2_zeros_imputed", lambda: np.nan_to_num(log2 - np.nanmin(log2) + 1, nan=0.0), "log"),
            ("zscore_genes", lambda: _zscore_genes(log2), "foreign"),
            ("presence", lambda: np.where(np.isnan(log2), 0.0, 1.0), "foreign"),
            ("ranks", lambda: _ranks(log2), "foreign"),
        ]
        for name, make, variant_label in made:
            yield name, make(), variant_label
        own = lin if label == "linear" else log2
        for n in SUBSAMPLE_SIZES:
            if values.shape[1] > n:
                yield f"subsample_{n}", _subsample(own, n, rng_for(entry_id, f"subsample_{n}")), label
        for target in INDUCED_MISSING:
            name = f"missing_{int(target * 100)}"
            yield name, induce_missing(own, target, rng_for(entry_id, name), log2), label
