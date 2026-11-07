"""The method end to end: gates, statistics, class scores, answer set.

`assess` is what `valuescale.detect` wraps. It returns a plain dict:
- `gate`: the gate that decided the table ("negatives", "counts") or None;
- `features`, `scores`, `parts`: the statistics and the class scores (None
  when a gate or the table's size decided);
- `set`: the classes whose score reaches their threshold;
- `verdict`: "linear", "log", "cant_tell" or "unlike_either";
- `reason`: why, for "cant_tell" and "unlike_either"; None otherwise;
- `warning`: UNLIKE_DESIGN_WARNING or None (below).

In order, after the gates:
- fewer than MIN_COLUMNS columns is "can't tell" (no calibrated stratum);
- a table on which no per-cell statistic can be computed is "unlike
  either";
- a per-protein-normalised table (every protein divided by, or centred on,
  its own level: `row_median_spread` below statistics.ROW_NORMALISED_BAR) is
  "can't tell": with the protein levels gone, a linear table's values are
  ratios near 1 and look like logs (B2's diagnostics,
  research/notebook-outputs/value_scale_b2/notes.md);
- a table with no missing value after the gates' clean-up is "can't tell":
  it may have been filled in (imputed), and filled-in values can make a log
  table look linear (furtwangler_log2_imputed, B2), as can a log table
  filtered to the proteins seen in every cell (protocol amendment 5);
- otherwise the class scores decide.

**The score is the probability** (protocol amendment 5): class y is in the
set when its probability reaches its threshold. The two probabilities add up
to 1, so a probability between the thresholds gives both readings ("can't
tell") when the thresholds add up to 1 or less, and neither ("unlike
either") when they add up to more. The typicality rank no longer enters the
set: when it is 0 for every class in the set (for both, when the set is
empty), the table is farther from the design tables than any of them is
from the rest, and `warning` says so.

`calibration_parts` scores a table whatever a gate or rule would answer, on
its cleaned values (gates.clean): calibration scores every subsample.
"""
from __future__ import annotations

import math
from typing import Mapping

import numpy as np

from valuescale import conformal, gates, score
from valuescale import statistics as st

PER_CELL = ("bowley", "moors", "tail")
PER_PROTEIN_REASON = "per-protein normalised: each protein's level was removed, so its shape cannot tell"
NO_GAPS_REASON = ("no value is missing: the table may have been filled in (imputed), and filled-in values "
                  "can make a log table look linear")
UNLIKE_DESIGN_WARNING = ("unlike the tables this detector was built on: farther from them than any of them is "
                         "from the rest")


def _fmt(v: float) -> str:
    return "none" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.3g}"


def _no_per_cell_statistic(f: Mapping[str, float]) -> bool:
    return all(math.isnan(f[name]) for name in PER_CELL)


def calibration_parts(values: np.ndarray, model: score.Model) -> dict | None:
    """The class parts (score.class_parts) of a table on its cleaned values,
    whatever a gate or rule would answer; None when no per-cell statistic
    can be computed (protocol amendment 5: such a subsample scores 0)."""
    f = st.features(gates.clean(values))
    return None if _no_per_cell_statistic(f) else score.class_parts(f, model)


def warning_of(parts: Mapping[str, Mapping[str, float]], answer) -> str | None:
    classes = tuple(answer) or conformal.CLASSES
    return UNLIKE_DESIGN_WARNING if all(parts[y]["typicality"] == 0.0 for y in classes) else None


def assess(values: np.ndarray, model: score.Model, thresholds: Mapping[str, float]) -> dict:
    x = np.asarray(values, dtype=np.float64)
    g = gates.gate(x)
    out = {
        "columns": int(x.shape[1]), "stratum": conformal.stratum_of(int(x.shape[1])),
        "gate": g.gate, "negative_share": g.negative_share, "stray_negatives": g.stray_negatives,
        "non_finite": g.non_finite, "min_ties": g.min_ties,
        "features": None, "scores": None, "parts": None, "thresholds": dict(thresholds), "warning": None,
    }
    if g.gate is not None:
        return {**out, "set": [g.reading], "verdict": g.reading, "reason": None}
    if x.shape[1] < conformal.MIN_COLUMNS:
        return {**out, "set": list(conformal.CLASSES), "verdict": "cant_tell", "reason": "too few columns"}
    f = st.features(g.values)
    out["features"] = f
    if _no_per_cell_statistic(f):
        return {**out, "set": [], "verdict": "unlike_either", "reason": "no spread"}
    if not math.isnan(f["row_median_spread"]) and f["row_median_spread"] < st.ROW_NORMALISED_BAR:
        return {**out, "set": list(conformal.CLASSES), "verdict": "cant_tell", "reason": PER_PROTEIN_REASON}
    if not np.isnan(g.values).any():
        return {**out, "set": list(conformal.CLASSES), "verdict": "cant_tell", "reason": NO_GAPS_REASON}
    parts = score.class_parts(f, model)
    scores = {y: p["probability"] for y, p in parts.items()}
    answer = conformal.answer_set(scores, thresholds)
    verdict = conformal.verdict(answer)
    reason = None
    if verdict in ("cant_tell", "unlike_either"):
        said = ("both readings fit" if verdict == "cant_tell"
                else "neither reading is as clear as on the calibration tables")
        reason = f"{said}: " + "; ".join(
            f"{y} probability {_fmt(scores[y])} {'>=' if scores[y] >= thresholds[y] else '<'} {_fmt(thresholds[y])}"
            for y in conformal.CLASSES)
    return {**out, "scores": scores, "parts": parts, "set": list(answer), "verdict": verdict, "reason": reason,
            "warning": warning_of(parts, answer)}
