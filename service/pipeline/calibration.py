"""Stage 5 — conformal calibration (docs/service/pipeline-brief.md, "Stage 5").

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
from typing import Protocol

import numpy as np

from service import config


@dataclass(frozen=True)
class CalibrationResult:
    qhat: float
    calibration_indices: np.ndarray
    label_sets: list[list[int]]  # one per query cell, values are `probs` COLUMN positions (0..n_classes-1), not the dataset's class_idx — see assignment.top_label


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


# --- Track C: the socket T1 NB3's conformal calibration plugs into ---

class ConformalCalibrator(Protocol):
    def calibrate(self, probs: np.ndarray, rng: np.random.Generator, label_space) -> CalibrationResult:
        ...

    def describe(self, result: CalibrationResult) -> dict:
        """The response's `calibration` block: what the coverage target is,
        and what it is a guarantee about."""
        ...


class V3ConformalCalibrator:
    """Today's behaviour, unchanged: calibrate_and_build_sets above."""

    def calibrate(self, probs, rng, label_space):
        return calibrate_and_build_sets(probs, rng=rng)

    def describe(self, result):
        return {
            "method": "split conformal on a random slice of this upload",
            "target_coverage": 1 - config.CONFORMAL_ALPHA,
            # There is no ground truth for an upload, so the slice's labels are
            # the model's own top predictions: the target is nominal, not a
            # guarantee about true cell types.
            "applies_to": "the model's own top predictions on this upload, not true labels",
            "n_calibration_cells": int(len(result.calibration_indices)),
        }


class MondrianCalibrator:
    """v3.1 (T1 NB2): class-conditional conformal sets with a fixed qhat per
    class, fitted on labelled RNA simulated uploads. A class is in a cell's
    set when p(class) >= 1 - qhat[class] and the class is in the label
    space. Nothing is drawn from the upload, so there is no calibration slice.

    With `include_best_guess` (the spec's service flag
    `set_includes_best_guess`), every set also contains the cell's argmax
    class within the label space. Sets only grow, so coverage is kept, and a
    one-class answer is always the best guess: without it, a class whose qhat
    is near 1 (mature nk t cell: bar 0.011) could be named alone at about 1%
    probability while another class held far more."""

    def __init__(self, qhat_by_position: np.ndarray, marginal_qhat: float, alpha: float, calibrated_on: str,
                 include_best_guess: bool = True):
        self.qhat = np.asarray(qhat_by_position, dtype=np.float64)
        self.marginal_qhat = float(marginal_qhat)
        self.alpha = float(alpha)
        self.calibrated_on = calibrated_on
        self.include_best_guess = include_best_guess

    def calibrate(self, probs, rng, label_space):
        threshold = 1.0 - self.qhat
        member = probs >= threshold
        allowed = np.ones(probs.shape[1], dtype=bool)
        if label_space.positions is not None:
            allowed[:] = False
            allowed[sorted(label_space.positions)] = True
            member &= allowed
        if self.include_best_guess:
            member[np.arange(len(probs)), np.where(allowed, probs, -1.0).argmax(axis=1)] = True
        label_sets = [np.flatnonzero(row).tolist() for row in member]
        return CalibrationResult(qhat=self.marginal_qhat, calibration_indices=np.zeros(0, dtype=np.int64),
                                 label_sets=label_sets)

    def describe(self, result):
        return {
            "method": "Mondrian (class-conditional) split conformal, fitted in T1 NB2",
            "target_coverage": 1 - self.alpha,
            "applies_to": f"{self.calibrated_on}; approximate on protein",
            "n_calibration_cells": 0,
            "set_includes_best_guess": self.include_best_guess,
        }
