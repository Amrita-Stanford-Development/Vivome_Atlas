"""Goal 2, after Phase 3: the record behind serving v4.2 (release 0.5.0;
research/notebook-run-history.md, entry 45). It computes nothing new about a
held-out set; it gathers what decides the choice between v4.1 and v4.2.

- The internal held-out test's primaries for both (research/benchmark/
  heldout/): its protein primaries do not read the best guess (two are
  reference similarity, which v4.2 does not change) or found v4.2's term
  flat, so they cannot separate the two; on RNA, v4.2 now takes v4.1's path
  (service/tests/test_v42.py, test_an_rna_upload_answers_exactly_as_v41),
  so its Hao score as served then (its protein term run on RNA) is replaced
  by v4.1's.
- Fulcher 2026, six types, each cell's best guess under both
  (research/notebook-outputs/v42_protein_means/guesses.csv.gz): balanced
  accuracy, the difference with a cell-level bootstrap (2,000 draws, seed
  0), and recall per type. Development data: Fulcher chose v4.1's weight and
  gated v4.2.
- PBMC240 and both SCoPE2 versions: whether any guess differs.

Writes research/notebook-outputs/v42_release/summary.json.

    python research/notebooks/v42_release.py      # from the repository root
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from benchmark import datasets  # noqa: E402
from benchmark.fulcher2026_score import COARSE  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v42_release"
GUESSES = REPO / "research" / "notebook-outputs" / "v42_protein_means" / "guesses.csv.gz"
HELDOUT = REPO / "research" / "benchmark" / "heldout"


def heldout() -> dict:
    out = {}
    for path in sorted(HELDOUT.glob("*/summary.json")):
        s = json.loads(path.read_text(encoding="utf-8"))
        name = path.parent.name
        if name == "hao2021":
            out[name] = {m: {"minus_correlation": round(s["comparisons"][f"{k} - correlation"]["mean"], 2),
                             "lower_95": round(s["comparisons"][f"{k} - correlation"]["lower_95_one_sided"], 2)}
                         for k, m in (("v41", "v4.1"), ("v42", "v4.2 as served then (its protein term on RNA)"))}
            out[name]["v4.2 now"] = "v4.1's, exactly: RNA uploads take v4.1's path"
            continue
        if s.get("void"):
            out[name] = {"void": True, "reason": s.get("reason", "")[:200]}
            continue
        out[name] = {m: {k: s["candidates"][m]["primary"].get(k) for k in ("auroc", "p", "pass", "void", "pairs", "won")
                         if k in s["candidates"][m]["primary"]} for m in ("v4.1", "v4.2")}
    return out


def development() -> dict:
    g = pd.read_csv(GUESSES)
    out = {}
    fu = g[g["dataset"] == "fulcher2026"]
    labels = datasets.load_fulcher2026_labels().set_index("cell_id")["label"]
    fu = fu.assign(label=fu["cell_id"].astype(str).map(labels))
    fu = fu[fu["label"].isin(datasets.FULCHER2026["types"])]
    truth = fu["label"].to_numpy()
    coarse = {m: np.array([COARSE.get(x, "other") for x in fu[m]]) for m in ("v41", "v42")}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ba = {m: 100 * balanced_accuracy_score(truth, coarse[m]) for m in coarse}
        rng = np.random.default_rng(0)
        draws = []
        for _ in range(2000):
            i = rng.integers(0, len(truth), len(truth))
            draws.append(100 * (balanced_accuracy_score(truth[i], coarse["v42"][i]) - balanced_accuracy_score(truth[i], coarse["v41"][i])))
    out["fulcher2026"] = {
        "cells": int(len(truth)), "balanced_accuracy": {m: round(v, 2) for m, v in ba.items()},
        "v42_minus_v41": round(ba["v42"] - ba["v41"], 2),
        "ci95": [round(float(x), 2) for x in np.percentile(draws, [2.5, 97.5])],
        "recall": {t: {m: round(100 * float((coarse[m][truth == t] == t).mean()), 1) for m in coarse}
                   for t in datasets.FULCHER2026["types"]}}
    for name in ("pbmc240", "scope2", "scope2_reprocessed", "furtwangler2025"):
        d = g[g["dataset"] == name]
        out[name] = {"cells": int(len(d)), "guesses_that_differ": int((d["v41"] != d["v42"]).sum())}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {
        "question": "which model to serve: v4.1 (release 0.4.0) or v4.2",
        "heldout": heldout(),
        "development": development(),
        "rna_uploads": "v4.2 answers exactly as v4.1 (service/tests/test_v42.py, test_an_rna_upload_answers_exactly_as_v41)",
        "licence": ("Rieckmann 2017 (PXD004352) is in PRIDE under the EMBL-EBI terms of use, which add no restriction "
                    "beyond the data owner's and ask for attribution; v4.2 credits it"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
