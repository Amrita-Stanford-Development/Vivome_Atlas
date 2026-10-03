"""Scores the corrected baselines (baselines_corrected.py) and v3.1 as served on
SCoPE2, PBMC240 and Fulcher 2026, exactly as baselines_score.py scores the
original runs: its functions, mapping and bootstrap, pointed at the corrected
runs (research/benchmark/baseline-corrections.md). v3.1's tables are the same
ones baselines_score.py reads.

Writes research/benchmark/baselines_corrected/: the tables baselines_score.py
writes (inputs.csv, <dataset>_per_seed.csv, <dataset>_summary.csv,
v31_confident.csv, paired_bootstrap.csv), plus setup_checks.csv: every run's
RNA-side checks, which use RNA labels only.

    python -m benchmark.baselines_corrected_score      # from the repository root
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import baselines_corrected, baselines_inputs, datasets
from benchmark import baselines_score as original

OUT = datasets.REPO / "research" / "benchmark" / "baselines_corrected"
RULES = {**original.RULES, "clf": "scANVI classifier", "match": "MaxFuse matching"}
BASELINE_RULES = ("knn", "nc", "native", "corr", "clf", "match")


def records(dataset: str):
    for tool in baselines_corrected.TOOLS:
        for seed in (0, 1, 2):
            path = baselines_corrected.OUT / dataset / f"{tool}_seed{seed}.json"
            if path.exists():
                yield tool, seed, path.with_name(path.stem), json.loads(path.read_text())


def runs(dataset: str):
    """(tool, seed, predictions) for every completed corrected run."""
    for tool, seed, stem, record in records(dataset):
        if record.get("status") == "completed":
            yield tool, seed, pd.read_csv(f"{stem}_pred.csv", dtype={"cell_id": str}, keep_default_na=False)


def setup_table(names) -> pd.DataFrame:
    rows = []
    for dataset in names:
        for tool, seed, _, record in records(dataset):
            checks = record.get("setup_checks", {})
            rows.append({"dataset": dataset, "tool": tool, "seed": seed, "status": record.get("status"),
                         **checks, "matched_query_cells_pct": record.get("matched_query_cells_pct"),
                         "input_shift": record.get("input_shift"),
                         "epochs_trained": json.dumps(record["epochs_trained"]) if "epochs_trained" in record else None,
                         "elapsed_s": record.get("elapsed_s")})
    return pd.DataFrame(rows)


def main() -> None:
    # baselines_score's functions read these module names when they run
    original.runs, original.RULES, original.BASELINE_RULES = runs, RULES, BASELINE_RULES
    OUT.mkdir(parents=True, exist_ok=True)
    found = [r for name in baselines_inputs.DATASETS for _, seed, _, r in records(name) if seed == 0]
    pd.DataFrame([{k: r.get(k) for k in ("dataset", "tool", "n_rna_cells", "n_query_cells", "n_genes", "gene_set",
                                         "rna_input", "query_input", "scaling", "missing_values", "settings")}
                  for r in found]).to_csv(OUT / "inputs.csv", index=False)
    setup_table(baselines_inputs.DATASETS).to_csv(OUT / "setup_checks.csv", index=False)
    paired, confident = [], []
    for name, build, keys in (("scope2", lambda: original.scope2(paired), ["tool", "rule", "regime"]),
                              ("pbmc240", original.pbmc240, ["tool", "rule"]),
                              ("fulcher2026", lambda: original.fulcher(paired), ["tool", "rule"])):
        per_seed, conf = build()
        per_seed.to_csv(OUT / f"{name}_per_seed.csv", index=False)
        original.summarise(per_seed, keys).to_csv(OUT / f"{name}_summary.csv", index=False)
        confident.append(conf)
        print(name, len(per_seed), "rows")
    pd.DataFrame(confident).to_csv(OUT / "v31_confident.csv", index=False)
    table = pd.DataFrame([{**{k: v for k, v in p.items() if k != "ci_95_pct"}, "ci_lo": p["ci_95_pct"][0],
                           "ci_hi": p["ci_95_pct"][1]} for p in paired],
                         columns=["dataset", "baseline", "seed", "baseline_rule", "ci_lo", "ci_hi"] if not paired else None)
    table["favours"] = np.where(table["ci_lo"] > 0, "v3.1", np.where(table["ci_hi"] < 0, "baseline", "neither"))
    table.to_csv(OUT / "paired_bootstrap.csv", index=False)
    print(table.groupby(["dataset", "baseline", "baseline_rule"]).favours.value_counts().unstack(fill_value=0))


if __name__ == "__main__":
    main()
