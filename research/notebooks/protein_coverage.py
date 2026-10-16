"""Goal 2, Phase 1.4: conformal coverage on real protein data. A measurement;
it changes nothing.

v3.1's conformal sets were calibrated on simulated RNA uploads to hold the true
class 90% of the time (coverage on protein is stated as approximate in every
response). This measures how often they do on the development protein data,
from the served per-cell tables (benchmark/baselines_v4.py, benchmark/
baselines_v31.py: results/baselines_ext/<dataset>/<model>_pred.csv), for v3.1
and v4.1 (v4.1's sets are v3.1's with its guess joined):
- Fulcher 2026: a cell is covered when its set holds a class of its author
  type (COARSE in benchmark/fulcher2026_score.py), per type;
- SCoPE2, published and reprocessed: when its set holds its class;
- PBMC240: when its set holds a class of its weak lineage.
Reported over all labelled cells (an empty set, or a refused cell, is not
covered) and over the cells given a set.

Writes research/notebook-outputs/protein_coverage/coverage.json.

    python research/notebooks/protein_coverage.py      # from the repository root
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from benchmark import datasets  # noqa: E402
from benchmark import fulcher2026_score as fulcher  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "protein_coverage"
RUNS = REPO / "benchmark" / "results" / "baselines_ext"
RESULTS = REPO / "benchmark" / "results"
TARGET = 90.0


def sets(dataset: str, model: str) -> pd.DataFrame:
    table = pd.read_csv(RUNS / dataset / f"{model}_pred.csv", dtype={"cell_id": str}, keep_default_na=False)
    table["set"] = table["label_set"].map(json.loads)
    return table.set_index("cell_id")


def summarise(covered: np.ndarray, has_set: np.ndarray) -> dict:
    return {"n": int(len(covered)), "coverage_pct": round(100 * float(covered.mean()), 2),
            "with_a_set_pct": round(100 * float(has_set.mean()), 2),
            "coverage_among_sets_pct": round(100 * float(covered[has_set].mean()), 2) if has_set.any() else None}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lineage = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv") \
        .groupby("class_name")["lineage"].first().to_dict()
    truth = {
        "fulcher2026": datasets.load_fulcher2026_labels().set_index("cell_id")["label"],
        "scope2": pd.Series(pd.read_csv(RESULTS / "prot_meta.csv")["class_name"].to_numpy(),
                            index=pd.read_csv(RESULTS / "prot_meta.csv")["orig_index"].astype(str)),
        "scope2_reprocessed": datasets.load_scope2_reprocessed_labels().set_index("cell_id")["label"],
        "pbmc240": pd.read_csv(RESULTS / "pbmc_meta.csv", dtype={"cell_id": str}).set_index("cell_id")["weak_lineage"],
    }
    out = {"target_pct": TARGET}
    for model in ("v31", "v41"):
        res = {}
        for name, labels in truth.items():
            table = sets(name, model)
            labels = labels[labels.index.isin(table.index)]
            if name == "fulcher2026":
                labels = labels[labels.isin(fulcher.TYPES)]
                hit = lambda s, t: any(fulcher.COARSE.get(c) == t for c in s)  # noqa: E731
            elif name == "pbmc240":
                labels = labels[labels.isin(("lymphoid", "myeloid"))]
                hit = lambda s, t: any(lineage.get(c) == t for c in s)  # noqa: E731
            else:
                hit = lambda s, t: t in s  # noqa: E731
            s = table.loc[labels.index, "set"]
            covered = np.array([hit(x, t) for x, t in zip(s, labels)])
            has_set = np.array([len(x) > 0 for x in s])
            entry = summarise(covered, has_set)
            entry["by_class"] = {t: summarise(covered[(labels == t).to_numpy()], has_set[(labels == t).to_numpy()])
                                 for t in sorted(labels.unique())}
            res[name] = entry
        out[model] = res
    (OUT / "coverage.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    for model in ("v31", "v41"):
        for name, e in out[model].items():
            per = ", ".join(f"{t} {v['coverage_pct']}" for t, v in e["by_class"].items())
            print(f"{model} {name:20} coverage {e['coverage_pct']:6} (sets {e['with_a_set_pct']}, among sets "
                  f"{e['coverage_among_sets_pct']}) | {per}")


if __name__ == "__main__":
    main()
