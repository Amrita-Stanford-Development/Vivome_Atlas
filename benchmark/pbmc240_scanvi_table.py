"""Rebuilds research/notebook-outputs/nb1d/scanvi_pbmc240_input_variants.csv
from scanvi_run_pbmc240.py's cached per-cell lineage predictions
(results/pbmc_scanvi_{knn,native}_pred_lineage*_seed*.npy) and the weak
lineage labels in results/pbmc_meta.csv. That covers every scANVI PBMC240
arm (input variant x gene set) and seed, under both rules.

The Track D rows were first assembled by hand. This script reproduces every
value but one, and adds any arm since, such as the measured-genes arm. The
exception: the hand-built "processed, shared kNN, seed 0" row counted only
the "other" lineage in pred_pct_other and dropped one cell predicted as
progenitor, so its composition summed to 99.58%. Here pred_pct_other is
everything that isn't lymphoid, myeloid or erythroid, so every row sums to
100%. Recall is over the 122 weakly labelled cells (117
lymphoid, 5 myeloid; myeloid recall is anecdotal). Composition is over all
237 cells.

    python benchmark/pbmc240_scanvi_table.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

RESULTS = Path(__file__).resolve().parent / "results"
OUT = Path(__file__).resolve().parents[1] / "research" / "notebook-outputs" / "nb1d" / "scanvi_pbmc240_input_variants.csv"
RULES = {"knn": "shared_knn_rule", "native": "native_scanvi_classifier"}
ARM_ORDER = ("raw", "processed", "raw_measuredgenes", "processed_measuredgenes")


def main() -> None:
    true = pd.read_csv(RESULTS / "pbmc_meta.csv")["weak_lineage"].to_numpy()
    rows = []
    for path in RESULTS.glob("pbmc_scanvi_*_pred_lineage*_seed*.npy"):
        m = re.fullmatch(r"pbmc_scanvi_(?P<rule>knn|native)_pred_lineage(?P<suffix>(?:_[a-z]+)*)_seed(?P<seed>\d+)\.npy", path.name)
        suffix = m["suffix"].lstrip("_")
        arm = "raw" if suffix == "" else "raw_measuredgenes" if suffix == "measuredgenes" else suffix
        pred = np.load(path, allow_pickle=True).astype(str)
        comp = pd.Series(pred).value_counts(normalize=True) * 100
        rows.append({
            "input_variant": arm, "protocol": RULES[m["rule"]], "seed": int(m["seed"]),
            "lymphoid_recall_pct": (pred[true == "lymphoid"] == "lymphoid").mean() * 100,
            "myeloid_recall_pct_anecdotal": (pred[true == "myeloid"] == "myeloid").mean() * 100,
            "pred_pct_lymphoid": comp.get("lymphoid", 0.0),
            "pred_pct_myeloid": comp.get("myeloid", 0.0),
            "pred_pct_erythroid": comp.get("erythroid", 0.0),
            "pred_pct_other": comp.drop(["lymphoid", "myeloid", "erythroid"], errors="ignore").sum(),
        })
    table = pd.DataFrame(rows)
    table["_arm"] = table["input_variant"].map(ARM_ORDER.index)
    table["_rule"] = table["protocol"].map({"shared_knn_rule": 0, "native_scanvi_classifier": 1})
    table = table.sort_values(["_arm", "seed", "_rule"]).drop(columns=["_arm", "_rule"])
    table.to_csv(OUT, index=False)
    print(table.groupby(["input_variant", "protocol"], sort=False)[["lymphoid_recall_pct", "myeloid_recall_pct_anecdotal"]]
          .agg(["mean", "min", "max"]).round(2).to_string())


if __name__ == "__main__":
    main()
