"""The conformal code: thresholds with a guarantee, intervals, the answer set.

For each class y, a table's class score s_y (valuescale/score.py) is higher
the more the table looks like class y. Class y joins the answer set when s_y
is at least y's threshold t_y. The threshold is the k-th smallest of n
calibration scores of class y, with k the largest value for which
P(Binomial(n, alpha) <= k - 1) <= delta (the Neyman-Pearson umbrella order
statistic; Tong, Feng & Li, Sci Adv 2018). Then, with probability at least
1 - delta over the calibration draw, a new table of class y is left out of
the set with probability at most alpha. At alpha = delta = 0.05 that needs
n >= 59 (research/benchmark/protocol-value-scale.md, "The claim").

numpy and the standard library only: the binomial and Clopper-Pearson
calculations are exact sums and bisection, not scipy.
"""
from __future__ import annotations

import math
from typing import Mapping, Sequence

import numpy as np

ALPHA = 0.05
DELTA = 0.05
CLASSES = ("linear", "log")
# Thresholds are set per stratum of the number of columns (cells or samples).
STRATA = {"S1": (20, 49), "S2": (50, 300), "S3": (301, 2000)}
MIN_COLUMNS = STRATA["S1"][0]


def stratum_of(columns: int) -> str | None:
    for name, (lo, hi) in STRATA.items():
        if lo <= columns <= hi:
            return name
    return None


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(Binomial(n, p) <= k)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
             for i in range(k + 1)]
    top = max(terms)
    return min(1.0, math.exp(top) * math.fsum(math.exp(t - top) for t in terms))


def umbrella_k(n: int, alpha: float = ALPHA, delta: float = DELTA) -> int | None:
    """The largest k with P(Binomial(n, alpha) <= k - 1) <= delta, or None
    when even k = 1 fails (too few calibration scores)."""
    if binom_cdf(0, n, alpha) > delta:
        return None
    k = 1
    while k < n and binom_cdf(k, n, alpha) <= delta:
        k += 1
    return k


def umbrella_threshold(scores: Sequence[float], alpha: float = ALPHA, delta: float = DELTA) -> float | None:
    s = np.sort(np.asarray(scores, dtype=np.float64))
    k = umbrella_k(s.size, alpha, delta)
    return None if k is None else float(s[k - 1])


def rehearsal_threshold(scores: Sequence[float], alpha: float = ALPHA) -> float:
    """The plain split-conformal threshold, floor(alpha (n + 1))-th smallest
    score (-inf when that is 0). Used only to rehearse verdicts on the design
    split, where no calibration split exists: no guarantee is claimed."""
    s = np.sort(np.asarray(scores, dtype=np.float64))
    j = math.floor(alpha * (s.size + 1))
    return -math.inf if j == 0 else float(s[j - 1])


def _solve(f, target: float) -> float:
    """p in [0, 1] with f(p) = target, f decreasing in p, by bisection."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(x: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """The two-sided exact interval for a binomial proportion x / n."""
    tail = (1 - confidence) / 2
    lower = 0.0 if x == 0 else _solve(lambda p: -(1 - binom_cdf(x - 1, n, p)), -tail)
    upper = 1.0 if x == n else _solve(lambda p: binom_cdf(x, n, p), tail)
    return lower, upper


def clopper_pearson_lower(x: int, n: int, confidence: float = 0.95) -> float:
    """The one-sided exact lower bound: the guarantee is contradicted for a
    class when this bound on its miss rate is above alpha."""
    if x == 0:
        return 0.0
    return _solve(lambda p: -(1 - binom_cdf(x - 1, n, p)), -(1 - confidence))


def answer_set(scores: Mapping[str, float], thresholds: Mapping[str, float]) -> tuple[str, ...]:
    return tuple(y for y in CLASSES if scores[y] >= thresholds[y])


def verdict(answer: Sequence[str]) -> str:
    return {("linear",): "linear", ("log",): "log", ("linear", "log"): "cant_tell", (): "unlike_either"}[tuple(answer)]
