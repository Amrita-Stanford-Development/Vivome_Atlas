"""The class scores: how much a table looks like each class.

One score per class (research/benchmark/protocol-value-scale.md, "The
claim"). **Since protocol amendment 5 (2026-11-07, before any calibration
statistic), a class's score is the discriminative probability alone**
(`class_scores`). The typicality part below is still computed, and the
reply warns when it is 0 (valuescale/method.py), but it no longer enters
the score. The design rank floors at 0 for any table farther from the
design rows than every one of them, and at the umbrella threshold's k = 1
one such calibration table would have put its class in every answer set.

B2 combined the two kinds by a rule fixed on the design split before any
calibration statistic (valuescale/bank/expectations/b2.json):

- **Typicality:** the distance from the table's features to the class's
  design rows. Each feature is standardised by the class's median and
  IQR/1.349; a row's distance is the root mean square over the features both
  have; the typicality distance is the mean over the K_NEIGHBOURS nearest.
  Uses the class's own features (`CLASS_FEATURES`): the linear class also
  uses `decades` and `column_sum_cv`, which a log table's offset would move.
- **Discriminative:** a ridge logistic regression of log against linear on
  the features both classes share, standardised by the pooled median and
  IQR/1.349, a missing feature at 0 (the median).
- **Combination (B2, replaced by amendment 5):** the typicality distance
  becomes a design rank for class y, the share of class y's design rows
  (each scored with its deposit left out) at least as far from the rest;
  B2's class score was the smaller of that rank and the probability of
  class y. (The probability is not ranked: design rows are so confidently
  classed that a rank would score 0 for any table less extreme than all of
  them, however clearly it belongs to y.) `class_parts` still gives the
  rank, as `typicality`.

Thresholds on the class scores come from valuescale/conformal.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

from valuescale import statistics as st

CLASSES = ("linear", "log")
CLASS_FEATURES = {"linear": st.FEATURES, "log": st.CORE + st.BOTH}
SHARED_FEATURES = st.CORE + st.BOTH
K_NEIGHBOURS = 3
RIDGE = 1.0


@dataclass(frozen=True)
class DesignRow:
    features: Mapping[str, float]
    label: str  # "linear" or "log"
    deposit: str
    stratum: str


def _matrix(features: Sequence[Mapping[str, float]], names: Sequence[str]) -> np.ndarray:
    return np.array([[float(f.get(n, math.nan)) for n in names] for f in features], dtype=np.float64).reshape(-1, len(names))


def _standardiser(m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centre, scale = np.zeros(m.shape[1]), np.ones(m.shape[1])
    for j in range(m.shape[1]):
        v = m[:, j][np.isfinite(m[:, j])]
        if v.size == 0:
            continue
        centre[j] = np.median(v)
        s = np.subtract(*np.quantile(v, (0.75, 0.25))) / 1.349
        if not s > 0:
            s = v.std()
        scale[j] = s if s > 0 else 1.0
    return centre, scale


def _distances(point: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """Root mean square difference over the features both have (inf when
    they share none)."""
    diff = rows - point[None, :]
    both = np.isfinite(diff)
    n = both.sum(axis=1)
    sq = np.where(both, diff, 0.0) ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, np.sqrt(sq.sum(axis=1) / np.maximum(n, 1)), np.inf)


def _knn(distances: np.ndarray) -> float:
    d = np.sort(distances[np.isfinite(distances)])
    return float(d[:K_NEIGHBOURS].mean()) if d.size else math.inf


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def _logistic(x: np.ndarray, y: np.ndarray, ridge: float = RIDGE) -> np.ndarray:
    """Ridge logistic regression by Newton's method; x without an intercept
    column, missing values already 0. The intercept is not penalised."""
    a = np.column_stack([np.ones(x.shape[0]), x])
    penalty = np.full(a.shape[1], ridge)
    penalty[0] = 0.0
    w = np.zeros(a.shape[1])
    for _ in range(100):
        p = _sigmoid(a @ w)
        hessian = a.T @ (a * (p * (1 - p))[:, None]) + np.diag(penalty)
        gradient = a.T @ (y - p) - penalty * w
        step = np.linalg.solve(hessian, gradient)
        w = w + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return w


@dataclass
class Model:
    typicality: dict  # class -> {"features", "centre", "scale", "rows" (standardised), "deposits"}
    discriminative: dict  # {"features", "centre", "scale", "weights"}
    reference: dict = field(default_factory=dict)  # class -> {"typicality": [...], "discriminative": [...]}

    def to_json(self) -> dict:
        def clean(v):
            if isinstance(v, np.ndarray):
                v = v.tolist()
            if isinstance(v, list):
                return [clean(x) for x in v]
            if isinstance(v, dict):
                return {k: clean(x) for k, x in v.items()}
            if isinstance(v, float) and not math.isfinite(v):
                return None if math.isnan(v) else ("inf" if v > 0 else "-inf")
            return v
        return clean({"typicality": self.typicality, "discriminative": self.discriminative, "reference": self.reference})

    @classmethod
    def from_json(cls, data: Mapping) -> "Model":
        def back(v):
            if v is None:
                return math.nan
            if v in ("inf", "-inf"):
                return math.inf if v == "inf" else -math.inf
            if isinstance(v, list):
                return [back(x) for x in v]
            return v
        typ = {y: {"features": list(t["features"]), "centre": np.array(back(t["centre"])), "scale": np.array(back(t["scale"])),
                   "rows": np.array(back(t["rows"]), dtype=np.float64).reshape(-1, len(t["features"])), "deposits": list(t["deposits"])}
               for y, t in data["typicality"].items()}
        d = data["discriminative"]
        disc = {"features": list(d["features"]), "centre": np.array(back(d["centre"])), "scale": np.array(back(d["scale"])),
                "weights": np.array(back(d["weights"]))}
        ref = {y: {k: [float(x) for x in back(v)] for k, v in r.items()} for y, r in data["reference"].items()}
        return cls(typ, disc, ref)


def _probability_log(features: Mapping[str, float], disc: Mapping) -> float:
    x = (_matrix([features], disc["features"])[0] - disc["centre"]) / disc["scale"]
    x = np.where(np.isfinite(x), x, 0.0)
    return float(_sigmoid(disc["weights"][0] + x @ disc["weights"][1:]))


def fit(rows: Sequence[DesignRow]) -> Model:
    typicality = {}
    for y in CLASSES:
        mine = [r for r in rows if r.label == y]
        m = _matrix([r.features for r in mine], CLASS_FEATURES[y])
        centre, scale = _standardiser(m)
        typicality[y] = {"features": list(CLASS_FEATURES[y]), "centre": centre, "scale": scale,
                         "rows": (m - centre) / scale, "deposits": [r.deposit for r in mine]}
    m = _matrix([r.features for r in rows], SHARED_FEATURES)
    centre, scale = _standardiser(m)
    x = (m - centre) / scale
    x = np.where(np.isfinite(x), x, 0.0)
    target = np.array([1.0 if r.label == "log" else 0.0 for r in rows])
    disc = {"features": list(SHARED_FEATURES), "centre": centre, "scale": scale, "weights": _logistic(x, target)}
    model = Model(typicality, disc)

    # Reference ranks: each design row scored with its deposit left out.
    deposits = np.array([r.deposit for r in rows])
    p_own = np.empty(len(rows))
    for d in np.unique(deposits):
        out = deposits == d
        w = _logistic(x[~out], target[~out]) if (~out).any() else disc["weights"]
        p_log = _sigmoid(w[0] + x[out] @ w[1:])
        p_own[out] = np.where(target[out] == 1.0, p_log, 1.0 - p_log)
    for y in CLASSES:
        t = typicality[y]
        mine = np.array([r.label == y for r in rows])
        own_deposits = np.array(t["deposits"])
        dist = [_knn(_distances(t["rows"][i], t["rows"][own_deposits != own_deposits[i]])) for i in range(len(own_deposits))]
        model.reference[y] = {"typicality": dist, "discriminative": p_own[mine].tolist()}
    return model


def _typicality_rank(model: Model, y: str, distance: float) -> float:
    return float(np.mean(np.asarray(model.reference[y]["typicality"]) >= distance))


def class_parts(features: Mapping[str, float], model: Model) -> dict[str, dict[str, float]]:
    p_log = _probability_log(features, model.discriminative)
    out = {}
    for y in CLASSES:
        t = model.typicality[y]
        point = (_matrix([features], t["features"])[0] - t["centre"]) / t["scale"]
        distance = _knn(_distances(point, t["rows"]))
        probability = p_log if y == "log" else 1.0 - p_log
        out[y] = {"distance": distance, "probability": probability,
                  "typicality": _typicality_rank(model, y, distance), "discriminative": probability}
    return out


def class_scores(features: Mapping[str, float], model: Model) -> dict[str, float]:
    """Each class's score: its probability (protocol amendment 5)."""
    return {y: p["probability"] for y, p in class_parts(features, model).items()}


def design_scores(model: Model) -> dict[str, list[float]]:
    """Each class's design rows' own scores, deposit left out: their
    probabilities of their own class."""
    return {y: list(model.reference[y]["discriminative"]) for y in CLASSES}
