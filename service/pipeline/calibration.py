"""Stage 5 — conformal calibration (Claude_Code_Context_Brief.md, "Stage 5").

Calibrate on a random subset of the query, never a confidence-filtered one.
This was gotten wrong once already in this project: calibrating only on the
query's most confident cells gave 36.2% empirical coverage against a 90%
target, because confidence filtering violates the exchangeability
assumption conformal prediction depends on. A random subset recovered 70%
coverage; calibrating against true labels in a controlled test reached
92.3%. There is no ground truth for a new upload, so the calibration
"labels" are the model's own top prediction on the random slice — that is
the documented, validated design here, not a shortcut.

If there is ever a temptation to hand-pick "good" calibration examples to
make the coverage guarantee look tighter, that is the bug already found and
fixed once.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from service import config


@dataclass(frozen=True)
class CalibrationResult:
    qhat: float
    calibration_indices: np.ndarray
    label_sets: list[list[int]]  # one per query cell, in probs row order


def _select_calibration_indices(n_query: int, rng: np.random.Generator) -> np.ndarray:
    n_cal = max(config.CALIBRATION_MIN_CELLS, int(np.ceil(config.CALIBRATION_FRACTION * n_query)))
    n_cal = min(n_cal, n_query)
    return rng.choice(n_query, size=n_cal, replace=False)


def calibrate_and_build_sets(
    probs: np.ndarray,
    alpha: float = config.CONFORMAL_ALPHA,
    rng: np.random.Generator | None = None,
) -> CalibrationResult:
    """probs: (n_query, n_classes) row-stochastic label probabilities
    (assignment.assign_labels output). Returns a qhat threshold and, for
    every query cell, the conformal label_set at nominal coverage 1-alpha:
    {c : probs[c] >= 1 - qhat}. An empty set is a valid, honest outcome —
    it means no class met the calibrated confidence bar for that cell, and
    is left to Stage 6 to interpret as ambiguity, not silently backfilled
    with a top-1 guess.
    """
    rng = rng or np.random.default_rng()
    n_query = probs.shape[0]

    calibration_indices = _select_calibration_indices(n_query, rng)
    calibration_top_prob = probs[calibration_indices].max(axis=1)
    nonconformity = 1.0 - calibration_top_prob

    n_cal = len(calibration_indices)
    level = min(1.0, np.ceil((n_cal + 1) * (1 - alpha)) / n_cal)
    qhat = float(np.quantile(nonconformity, level, method="higher"))

    threshold = 1.0 - qhat
    label_sets = [
        np.flatnonzero(probs[i] >= threshold).tolist() for i in range(n_query)
    ]
    return CalibrationResult(qhat=qhat, calibration_indices=calibration_indices, label_sets=label_sets)
