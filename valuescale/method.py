"""The method end to end: gates, statistics, class scores, answer set.

`assess` is what B4's `detect` will wrap. It returns a plain dict:
- `gate`: the gate that decided the table ("negatives", "counts") or None;
- `features`, `scores`, `parts`: the statistics and the class scores (None
  when a gate or the table's size decided);
- `set`: the classes whose score reaches their threshold;
- `verdict`: "linear", "log", "cant_tell" or "unlike_either";
- `reason`: why, for "cant_tell" and "unlike_either"; None otherwise.

Fewer than MIN_COLUMNS columns is "can't tell" (no calibrated stratum); a
table on which no per-cell statistic can be computed is "unlike either". A
per-protein-normalised table (every protein divided by, or centred on, its
own level: `row_median_spread` below statistics.ROW_NORMALISED_BAR) is
"can't tell": with the protein levels gone, a linear table's values are
ratios near 1 and look like logs (B2's diagnostics,
research/notebook-outputs/value_scale_b2/notes.md).
"""
from __future__ import annotations

import math
from typing import Mapping

import numpy as np

from valuescale import conformal, gates, score
from valuescale import statistics as st

PER_CELL = ("bowley", "moors", "tail")
PER_PROTEIN_REASON = "per-protein normalised: each protein's level was removed, so its shape cannot tell"


def _fmt(v: float) -> str:
    return "none" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.3g}"


def assess(values: np.ndarray, model: score.Model, thresholds: Mapping[str, float]) -> dict:
    x = np.asarray(values, dtype=np.float64)
    g = gates.gate(x)
    out = {
        "columns": int(x.shape[1]), "stratum": conformal.stratum_of(int(x.shape[1])),
        "gate": g.gate, "negative_share": g.negative_share, "stray_negatives": g.stray_negatives,
        "non_finite": g.non_finite, "min_ties": g.min_ties,
        "features": None, "scores": None, "parts": None, "thresholds": dict(thresholds),
    }
    if g.gate is not None:
        return {**out, "set": [g.reading], "verdict": g.reading, "reason": None}
    if x.shape[1] < conformal.MIN_COLUMNS:
        return {**out, "set": list(conformal.CLASSES), "verdict": "cant_tell", "reason": "too few columns"}
    f = st.features(g.values)
    out["features"] = f
    if all(math.isnan(f[name]) for name in PER_CELL):
        return {**out, "set": [], "verdict": "unlike_either", "reason": "no spread"}
    if not math.isnan(f["row_median_spread"]) and f["row_median_spread"] < st.ROW_NORMALISED_BAR:
        return {**out, "set": list(conformal.CLASSES), "verdict": "cant_tell", "reason": PER_PROTEIN_REASON}
    parts = score.class_parts(f, model)
    scores = {y: min(p["typicality"], p["discriminative"]) for y, p in parts.items()}
    answer = conformal.answer_set(scores, thresholds)
    verdict = conformal.verdict(answer)
    reason = None
    if verdict in ("cant_tell", "unlike_either"):
        said = "both readings fit" if verdict == "cant_tell" else "neither reading fits"
        detail = "; ".join(
            f"{y} score {_fmt(scores[y])} {'>=' if scores[y] >= thresholds[y] else '<'} {_fmt(thresholds[y])}"
            f" (typicality {_fmt(parts[y]['typicality'])}, probability {_fmt(parts[y]['probability'])})"
            for y in conformal.CLASSES)
        reason = f"{said}: {detail}"
    return {**out, "scores": scores, "parts": parts, "set": list(answer), "verdict": verdict, "reason": reason}
