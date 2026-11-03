"""Strata, subsamples and the constructed log class, as the protocol fixes
them (research/benchmark/protocol-value-scale.md, "Strata, subsamples and
the log class").

- Strata by the number of columns (cells or samples): S1 20 to 49, S2 50 to
  300, S3 301 to 2,000.
- One subsample per deposit per stratum it reaches: the size drawn
  uniformly from the stratum's range, capped by the table; the columns drawn
  without replacement and kept in order; every row kept. The generator is
  seeded by sha256("20261103:" + key + ":" + stratum), where the key is the
  accession (the bank, which holds several tables per deposit, uses the
  table's id).
- Each linear subsample gets one constructed log variant, chosen by the same
  seed: log2, log10 or ln with zeros missing, or log2(x + 1) with zeros kept
  as 0, which is used only when the median positive value is at least 10
  (otherwise log2: a log1p of small values is still linear-shaped).
"""
from __future__ import annotations

import hashlib

import numpy as np

from valuescale.conformal import STRATA, stratum_of  # noqa: F401  (the shipped definition)

LOG_FORMS = ("log2", "log10", "ln", "log2p1")
LOG1P_MIN_MEDIAN = 10.0


def strata_reached(columns: int) -> list[str]:
    return [name for name, (lo, _) in STRATA.items() if columns >= lo]


def seed_for(key: str, stratum: str) -> int:
    return int(hashlib.sha256(f"20261103:{key}:{stratum}".encode()).hexdigest(), 16)


def subsample(values: np.ndarray, key: str, stratum: str) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = STRATA[stratum]
    n = values.shape[1]
    if n < lo:
        raise ValueError(f"{key}: {n} columns do not reach {stratum} ({lo} to {hi})")
    rng = np.random.default_rng(seed_for(key, stratum))
    size = int(rng.integers(lo, min(hi, n) + 1))
    columns = np.sort(rng.choice(n, size=size, replace=False))
    return values[:, columns], columns


def constructed_log(values: np.ndarray, key: str, stratum: str) -> tuple[str, np.ndarray]:
    x = np.asarray(values, dtype=np.float64)
    form = LOG_FORMS[seed_for(key, stratum) % len(LOG_FORMS)]
    positive = x[x > 0]
    if form == "log2p1" and (positive.size == 0 or np.median(positive) < LOG1P_MIN_MEDIAN):
        form = "log2"
    with np.errstate(divide="ignore", invalid="ignore"):
        if form == "log2p1":
            return form, np.log2(x + 1)
        logged = {"log2": np.log2, "log10": np.log10, "ln": np.log}[form](np.where(x > 0, x, np.nan))
    return form, logged
