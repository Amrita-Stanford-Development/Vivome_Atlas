"""B4's calibration: the thresholds, set on the calibration split
(research/benchmark/protocol-value-scale.md, "The claim", "Strata,
subsamples and the log class" and amendment 5).

- **The records:** the walk's kept tables labelled linear in the calibration
  split, less those the hand audit disagreed with
  (valuescale/corpus/walk.jsonl, audit.json).
- **The subsamples:** for each deposit, one subsample per stratum its table
  reaches (strata.subsample) and that subsample's constructed log variant
  (strata.constructed_log). The log class is these variants alone: the
  calibration split holds no real log table.
- **The scores:** each subsample's probability of its own class
  (method.calibration_parts), on its cleaned values, whatever a gate or rule
  would answer; 0 when no per-cell statistic can be computed. What would
  have decided it is recorded as `decided_by`.
- **The pooling:** POOLS names the calibrated strata and the protocol strata
  in each. S3 is short in both splits (B3), so it pools with S2. A deposit
  with subsamples in two pooled strata keeps the smaller score, so it counts
  once.
- **The thresholds:** per calibrated stratum and class, the umbrella k-th
  smallest score (conformal.umbrella_threshold); None when n is too small
  for any k.
- **The file:** `build` returns what valuescale/calibrated.py reads, with
  the design model and the corpus manifest (each deposit's accession, file
  sha256, columns and rows) and its sha256.

Not shipped. The B4 notebook (research/notebooks/value_scale_calibrate.py)
runs it once and writes valuescale/calibration/protein-v1.json.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Callable, Iterable, Mapping

import numpy as np

from valuescale import conformal, method, score
from valuescale.corpus import strata

POOLS = {"S1": ("S1",), "S2+S3": ("S2", "S3")}
LABELS = ("linear", "log")
NEUTRAL = {"linear": 0.5, "log": 0.5}  # thresholds for finding what decides a table; the verdict is not used
_RULES = {"too few columns": "too few columns", "no spread": "no spread",
          method.PER_PROTEIN_REASON: "per-protein", method.NO_GAPS_REASON: "no gaps"}


def calibration_records(records: Iterable[Mapping], audit: Mapping) -> list[dict]:
    disagree = {a for a, v in audit.get("verdicts", {}).items() if v.get("agrees") is False}
    kept = [dict(r) for r in records if r.get("outcome") == "kept" and r.get("split") == "calibration"
            and r.get("label") == "linear" and r["accession"] not in disagree]
    return sorted(kept, key=lambda r: r["accession"])


def manifest(records: Iterable[Mapping]) -> dict:
    deposits = sorted(({"accession": r["accession"],
                        "sha256": r["member_sha256"] if r.get("member") else r["sha256"],
                        "columns": int(r["columns"]), "rows": int(r["rows"])} for r in records),
                      key=lambda d: d["accession"])
    text = json.dumps(deposits, sort_keys=True, separators=(",", ":"))
    return {"deposits": deposits, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def decided_by(values: np.ndarray, model: score.Model) -> tuple[str | None, dict | None]:
    """(what would decide the table before its score: a gate or a rule, or
    None; the method's parts when the score decides)."""
    a = method.assess(values, model, NEUTRAL)
    return (a["gate"] or _RULES.get(a["reason"])), a["parts"]


def subsample_scores(accession: str, values: np.ndarray, model: score.Model) -> list[dict]:
    x = np.asarray(values, dtype=np.float64)
    rows = []
    for s in strata.strata_reached(x.shape[1]):
        sub, _ = strata.subsample(x, accession, s)
        form, logged = strata.constructed_log(sub, accession, s)
        for label, v, how in (("linear", sub, "as deposited"), ("log", logged, f"constructed {form}")):
            rule, parts = decided_by(v, model)
            if parts is None:
                parts = method.calibration_parts(v, model)
            rows.append({"accession": accession, "stratum": s, "columns": int(v.shape[1]), "label": label,
                         "form": how, "decided_by": rule if parts is not None else (rule or "no spread"),
                         "score": float(parts[label]["probability"]) if parts else 0.0,
                         "typicality": float(parts[label]["typicality"]) if parts else None})
    return rows


def pooled_scores(rows: Iterable[Mapping], pools: Mapping[str, tuple] = POOLS) -> dict:
    """{(calibrated stratum, label): {accession: score}}, a deposit's smaller
    score where it has subsamples in two of a pool's strata."""
    member_of = {m: name for name, members in pools.items() for m in members}
    out = defaultdict(dict)
    for r in rows:
        key = (member_of[r["stratum"]], r["label"])
        a = r["accession"]
        out[key][a] = min(out[key].get(a, np.inf), r["score"])
    return dict(out)


def threshold(scores: Mapping[str, float]) -> dict:
    values = list(scores.values())
    return {"threshold": conformal.umbrella_threshold(values), "n": len(values),
            "k": conformal.umbrella_k(len(values))}


def build(records: list[Mapping], values_of: Callable[[Mapping], np.ndarray], model: score.Model,
          written: str, calibration_id: str = "protein-v1", progress: Callable[[str], None] | None = None
          ) -> tuple[dict, list[dict]]:
    """(the calibration file's content, every subsample's row)."""
    rows = []
    for i, r in enumerate(records):
        values = values_of(r)
        if values.shape[1] != r["columns"]:
            raise ValueError(f"{r['accession']}: {values.shape[1]} columns on disk, {r['columns']} in its record")
        rows += subsample_scores(r["accession"], values, model)
        if progress:
            progress(f"{i + 1}/{len(records)} {r['accession']}")
    pooled = pooled_scores(rows)
    out_strata = []
    for name, members in POOLS.items():
        lo, hi = conformal.STRATA[members[0]][0], conformal.STRATA[members[-1]][1]
        t = {y: threshold(pooled.get((name, y), {})) for y in LABELS}
        out_strata.append({"name": name, "columns": [lo, hi], "members": list(members),
                           "thresholds": {y: t[y]["threshold"] for y in LABELS},
                           "n": {y: t[y]["n"] for y in LABELS}, "k": {y: t[y]["k"] for y in LABELS}})
    corpus = manifest(records)
    data = {
        "id": calibration_id,
        "written": written,
        "about": ("The raw-or-log detector's frozen calibration (research/benchmark/protocol-value-scale.md, "
                  "amendment 5): per calibrated stratum and class, the umbrella k-th smallest calibration score "
                  "(the class probability of each deposit's subsample, or of its constructed log variant). "
                  "Written once by valuescale/corpus/calibrate.py; never edited."),
        "alpha": conformal.ALPHA, "delta": conformal.DELTA,
        "strata": out_strata,
        "corpus_sha256": corpus["sha256"],
        "corpus": {"split": "calibration", **corpus},
        "model": model.to_json(),
    }
    return data, rows
