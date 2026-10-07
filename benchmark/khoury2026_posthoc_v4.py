"""Khoury 2026, POST-HOC: v4 as served (Track G, Phase 4), scored beside v3.1
and the corrected baselines.

Khoury's labels were read at its one scoring under its protocol, on
2026-10-03, and v4 was designed afterwards. Its spec was frozen (Phase 3c,
2026-10-05) before this script ran, and Khoury played no part in v4's design
or settings, but this is not a held-out result: it is reported as post-hoc,
beside research/benchmark/khoury2026/ (the protocol's result, unchanged) and
research/benchmark/khoury2026_posthoc/ (the corrected baselines).

Two steps, in order:
1. Label-free: v4 on the full upload (datasets.load_khoury2026_upload),
   through pipeline.run_projection, unrestricted, default settings, exactly
   as khoury2026_embed.py ran v3.1; saved to benchmark/results/khoury2026/
   v4_pred.csv and v4.json.
2. Post-hoc scoring with khoury2026_score.py's metric code, class mapping,
   paired bootstrap and confident-answer rule, unchanged. v3.1's row is
   rebuilt from its saved table and checked against the sealed scoring
   first. Pairs: v4's best guess against v3.1's, and against every completed
   corrected baseline run under each of its rules.

Writes research/benchmark/khoury2026_posthoc_v4/: per_model_scores.csv,
paired_bootstrap.csv, confident.json, summary.json.

    python -m benchmark.khoury2026_posthoc_v4      # from the repository root
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from benchmark import baselines_v31, datasets
from benchmark import khoury2026_posthoc_score as posthoc
from benchmark import khoury2026_score as protocol
from benchmark.evaluate import paired_bootstrap_diff
from service.pipeline import pipeline

OUT = datasets.REPO / "research" / "benchmark" / "khoury2026_posthoc_v4"


def run_v4(src) -> None:
    bundle = pipeline.load_bundle("v4")
    response = pipeline.run_projection(bundle, datasets.load_khoury2026_upload())
    baselines_v31.table(response).to_csv(src.out / "v4_pred.csv", index=False, lineterminator="\n")
    (src.out / "v4.json").write_text(json.dumps({
        "model": response["model_version"], "pipeline_version": response["pipeline_version"],
        "atlas_version": response["atlas_version"], "n_cells": len(response["cells"]),
        "best_guess_rule": response["best_guess_rule"]}, indent=2) + "\n", newline="\n")
    print("v4 run:", response["best_guess_rule"])


def confident_for(src, table: str, scored: np.ndarray, true_type: np.ndarray) -> dict:
    """protocol.confident, on `table` in place of v31_pred.csv."""
    read = protocol.read_v31_table
    protocol.read_v31_table = lambda path: read(path.with_name(table))
    try:
        return protocol.confident(src, scored, true_type)
    finally:
        protocol.read_v31_table = read


def main() -> None:
    src = protocol.sources(False)
    cell_ids = (src.out / "cell_ids.txt").read_text().splitlines()
    run_v4(src)
    v4 = protocol.read_v31_table(src.out / "v4_pred.csv")
    v31 = protocol.read_v31_table(src.out / "v31_pred.csv")
    protocol.same_rows(v4["cell_id"].tolist(), cell_ids, "v4_pred.csv")
    protocol.same_rows(v31["cell_id"].tolist(), cell_ids, "v31_pred.csv")
    corrected, excluded = posthoc.corrected_predictions(cell_ids)

    labels = datasets.load_khoury2026_labels(unseal=True)  # read at the 2026-10-03 scoring; post-hoc use
    protocol.same_rows(labels["cell_id"].tolist(), cell_ids, "labels")
    scored = labels["label"].isin(protocol.TYPES).to_numpy()
    true_type = labels["label"].to_numpy()[scored]
    _, _, lineage = protocol.reference_classes()

    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for model, table in (("v3.1", v31), ("v4", v4)):
            row, _, _ = protocol.score(table["best_guess"].to_numpy()[scored], true_type, lineage)
            rows.append({"family": model, "model": model, "seed": 0, "rule": "best_guess", "n_scored": int(scored.sum()), **row})
    per_model = pd.DataFrame(rows)
    sealed = pd.read_csv(posthoc.SEALED / "per_seed_scores.csv").query("family == 'v3.1' and rule == 'best_guess'")
    worst = float(np.abs(per_model.iloc[0][[c for c in per_model if c.endswith("_pct")]].to_numpy(float)
                         - sealed[[c for c in per_model if c.endswith("_pct")]].to_numpy(float)[0]).max())
    if len(sealed) != 1 or worst > 1e-4:
        raise ValueError(f"v3.1's best guess does not reproduce the sealed scoring (difference {worst})")

    guess = protocol.to_type(v4["best_guess"].to_numpy()[scored])
    pairs = [("v3.1", "v3.1", "best_guess", protocol.to_type(v31["best_guess"].to_numpy()[scored]))]
    pairs += [(family, model, rule, protocol.to_type(pred[scored])) for (family, model, _, rule), pred in corrected.items()]
    boot = []
    for family, model, rule, other in pairs:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # "other" is never a true type
            d = paired_bootstrap_diff(true_type, guess, other)
        lo, hi = d["ci_95_pct"]
        boot.append({"comparison": f"v4 vs {family}", "model_b": model, "rule_b": rule, "diff_bal_acc_pct": d["point_estimate_pct"],
                     "ci_lo": lo, "ci_hi": hi, "favours": "v4" if lo > 0 else model if hi < 0 else "neither"})
    boot = pd.DataFrame(boot)
    confident = {"v3.1": confident_for(src, "v31_pred.csv", scored, true_type),
                 "v4": confident_for(src, "v4_pred.csv", scored, true_type)}

    OUT.mkdir(parents=True, exist_ok=True)
    fmt = {"index": False, "float_format": "%.4f", "lineterminator": "\n"}
    per_model.to_csv(OUT / "per_model_scores.csv", **fmt)
    boot.to_csv(OUT / "paired_bootstrap.csv", **fmt)
    (OUT / "confident.json").write_text(json.dumps(confident, indent=2) + "\n", newline="\n")
    counts = {c: g["favours"].map(lambda f: "v4" if f == "v4" else "neither" if f == "neither" else "the other").value_counts().to_dict()
              for c, g in boot.groupby("comparison", sort=False)}
    (OUT / "summary.json").write_text(json.dumps({
        "dataset": "Khoury 2026", "posthoc": True,
        "note": ("Post-hoc: Khoury's labels were read at its one scoring (2026-10-03), before v4 was designed. v4's spec "
                 "was frozen (Phase 3c, 2026-10-05) before this run; Khoury played no part in it. The protocol's result "
                 "is research/benchmark/khoury2026/."),
        "best_guess_balanced_accuracy_pct": {r["model"]: round(r["balanced_accuracy_pct"], 2) for _, r in per_model.iterrows()},
        "excluded_runs": excluded, "ci_excludes_zero_counts": counts,
    }, indent=2) + "\n", newline="\n")
    print(per_model.round(2).to_string(index=False))
    print(boot.round(2).to_string(index=False))
    print(json.dumps({m: {k: c[k] for k in ("committed_pct", "correct_when_committed_pct")} for m, c in confident.items()}))


if __name__ == "__main__":
    main()
