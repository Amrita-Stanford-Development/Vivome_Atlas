"""Track D extension: scores every baseline run (baselines_run.py) and v3.1 as
served (baselines_v31.py) on SCoPE2, PBMC240 and Fulcher 2026, the only step
that reads their labels. Writes research/benchmark/baselines/:

- inputs.csv: what every tool received, per dataset (the gene-fairness record);
- scope2_per_seed.csv, scope2_summary.csv: accuracy and balanced accuracy,
  restricted (macrophage/monocyte) and unrestricted, per rule;
- pbmc240_per_seed.csv, pbmc240_summary.csv: lymphoid and myeloid recall over
  the 122 weakly labelled cells (myeloid: 5 cells, anecdotal) and the
  lineage composition over all 237;
- fulcher2026_per_seed.csv, fulcher2026_summary.csv: balanced accuracy over
  the six types, recall per type and lineage, composition, scored exactly as
  fulcher2026_score.py scores the held-out table (its score() and mapping);
- v31_confident.csv: v3.1's confident answers, per dataset: committed share
  and correctness at the stated level;
- paired_bootstrap.csv: v3.1's best guess against each baseline seed and rule
  (evaluate.paired_bootstrap_diff, 2,000 stratified resamples, seed 0), on
  SCoPE2 (both regimes) and Fulcher.

The correlation baseline is deterministic, so it has one run (seed 0).
v3.1 is scored on its best guess, since the baselines give fine labels only.
Fulcher rows are baselines added after the held-out scoring; Seurat on
Fulcher is biased in its favour (its labels came from Seurat transfer).

    python -m benchmark.baselines_score      # from the repository root
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

from benchmark import baselines_inputs, datasets
from benchmark import fulcher2026_score as protocol
from benchmark.evaluate import paired_bootstrap_diff, score

RUNS = baselines_inputs.D / "baselines_ext"
OUT = datasets.REPO / "research" / "benchmark" / "baselines"
TOOLS = ("maxfuse", "scglue", "harmony", "seurat", "correlation")
RULES = {"knn": "shared kNN", "nc": "nearest centroid", "native": "Seurat native transfer",
         "corr": "correlation to class mean", "best_guess": "best guess (served)"}
BASELINE_RULES = ("knn", "nc", "native", "corr")  # a run is scored on the ones its table has
V31 = "v3.1 (served)"


def runs(dataset: str):
    """(tool, seed, predictions) for every finished baseline run."""
    for tool in TOOLS:
        for seed in (0, 1, 2):
            stem = RUNS / dataset / f"{tool}_seed{seed}"
            if Path(f"{stem}.json").exists() and not json.loads(Path(f"{stem}.json").read_text())["diverged"]:
                yield tool, seed, pd.read_csv(f"{stem}_pred.csv", dtype={"cell_id": str})


def summarise(per_seed: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    metrics = [c for c in per_seed.columns if c.endswith("_pct")]
    return (per_seed.groupby(keys, sort=False)[metrics].agg(["mean", "std", "min", "max", "count"])
            .stack(level=0, future_stack=True).rename_axis(keys + ["metric"]).reset_index())


def read_v31(dataset: str, name: str = "v31") -> pd.DataFrame:
    """A baselines_v31.py table, empty strings kept as strings (an abstained
    cell has no label or level)."""
    df = pd.read_csv(RUNS / dataset / f"{name}_pred.csv", keep_default_na=False, dtype={"cell_id": str})
    df["abstained"] = df["abstained"].astype(str).eq("True")
    return df


def hierarchy() -> dict:
    return json.loads((datasets.REPO / "service" / "model" / "v3_1" / "nb2_spec_v31.json").read_text())["hierarchy"]


def scope2(paired: list) -> tuple[pd.DataFrame, dict]:
    truth = pd.read_csv(baselines_inputs.D / "prot_meta.csv")["class_name"].to_numpy()
    rows, preds = [], {}
    for tool, seed, pred in runs("scope2"):
        for rule in BASELINE_RULES:
            for regime in ("unrestricted", "restricted"):
                column = f"{rule}_{regime}"
                if column in pred:
                    rows.append({"tool": tool, "seed": seed, "rule": RULES[rule], "regime": regime,
                                 **score(truth, pred[column].to_numpy(), 22 if regime == "unrestricted" else 2)})
                    preds[(tool, seed, RULES[rule], regime)] = pred[column].to_numpy()
    v31 = {"unrestricted": read_v31("scope2"), "restricted": read_v31("scope2", "v31_restricted")}
    for regime, pred in v31.items():
        rows.append({"tool": V31, "seed": 0, "rule": RULES["best_guess"], "regime": regime,
                     **score(truth, pred["best_guess"].to_numpy(), 22 if regime == "unrestricted" else 2)})
    for (tool, seed, rule, regime), baseline in preds.items():
        result = paired_bootstrap_diff(truth, v31[regime]["best_guess"].to_numpy(), baseline)
        paired.append({"dataset": f"SCoPE2 {regime}", "baseline": tool, "seed": seed, "baseline_rule": rule, **result})
    confident = confident_scope2(v31["unrestricted"], truth)
    return pd.DataFrame(rows), confident


def confident_scope2(pred: pd.DataFrame, truth: np.ndarray) -> dict:
    h = hierarchy()
    committed = ~pred["abstained"].to_numpy()
    correct = np.array([c and lbl == (t if lvl == "class" else h[t][lvl])
                        for c, lbl, lvl, t in zip(committed, pred["label"], pred["label_level"], truth)])
    return {"dataset": "SCoPE2", "cells": len(pred), "committed_pct": 100 * committed.mean(),
            "correct_when_committed_pct": 100 * correct.sum() / committed.sum()}


def pbmc240() -> tuple[pd.DataFrame, dict]:
    meta = pd.read_csv(baselines_inputs.D / "pbmc_meta.csv")
    truth = meta["weak_lineage"].to_numpy()
    _, _, lineage = protocol.reference_classes()

    def row(pred_class):
        pred = np.array([lineage.get(c, "none") for c in pred_class])
        comp = pd.Series(pred).value_counts(normalize=True) * 100
        return {"lymphoid_recall_pct": (pred[truth == "lymphoid"] == "lymphoid").mean() * 100,
                "myeloid_recall_pct": (pred[truth == "myeloid"] == "myeloid").mean() * 100,
                "pred_lymphoid_pct": comp.get("lymphoid", 0.0), "pred_myeloid_pct": comp.get("myeloid", 0.0),
                "pred_erythroid_pct": comp.get("erythroid", 0.0),
                "pred_other_pct": comp.drop(["lymphoid", "myeloid", "erythroid"], errors="ignore").sum()}
    rows = []
    for tool, seed, pred in runs("pbmc240"):
        assert pred["cell_id"].tolist() == meta["cell_id"].tolist()
        for rule in BASELINE_RULES:
            if f"{rule}_unrestricted" in pred:
                rows.append({"tool": tool, "seed": seed, "rule": RULES[rule], **row(pred[f"{rule}_unrestricted"])})
    v31 = read_v31("pbmc240")
    assert v31["cell_id"].tolist() == meta["cell_id"].tolist()
    rows.append({"tool": V31, "seed": 0, "rule": RULES["best_guess"], **row(v31["best_guess"])})
    labelled = np.isin(truth, ["lymphoid", "myeloid"])
    committed = ~v31["abstained"].to_numpy()
    named = np.array([{lineage[c] for c in json.loads(s)} == {t} for s, t in zip(v31["label_set"], truth)])
    confident = {"dataset": "PBMC240", "cells": len(v31), "committed_pct": 100 * committed.mean(),
                 "correct_when_committed_pct": 100 * (named & committed & labelled).sum() / (committed & labelled).sum()}
    return pd.DataFrame(rows), confident


def fulcher(paired: list) -> tuple[pd.DataFrame, dict]:
    labels = datasets.load_fulcher2026_labels()  # scoring only
    scored = (labels["label"] != datasets.FULCHER2026["unscored_label"]).to_numpy()
    truth = labels["label"].to_numpy()[scored]
    _, _, lineage = protocol.reference_classes()
    rows, preds = [], {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # "other" is never a true class
        for tool, seed, pred in runs("fulcher2026"):
            assert pred["cell_id"].tolist() == labels["cell_id"].tolist()
            for rule in BASELINE_RULES:
                if f"{rule}_unrestricted" in pred:
                    fine = pred[f"{rule}_unrestricted"].to_numpy()[scored]
                    metrics, composition, _ = protocol.score(fine, truth, lineage)
                    rows.append({"tool": tool, "seed": seed, "rule": RULES[rule], **metrics,
                                 **{f"pred_{t}_pct": v for t, v in composition.items()}})
                    preds[(tool, seed, RULES[rule])] = fine
        v31 = read_v31("fulcher2026")
        assert v31["cell_id"].tolist() == labels["cell_id"].tolist()
        guess = v31["best_guess"].to_numpy()[scored]
        metrics, composition, _ = protocol.score(guess, truth, lineage)
        rows.append({"tool": V31, "seed": 0, "rule": RULES["best_guess"], **metrics,
                     **{f"pred_{t}_pct": v for t, v in composition.items()}})
    guess_type = np.array([protocol.COARSE.get(c, "other") for c in guess])
    for (tool, seed, rule), fine in preds.items():
        baseline_type = np.array([protocol.COARSE.get(c, "other") for c in fine])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = paired_bootstrap_diff(truth, guess_type, baseline_type)
        paired.append({"dataset": "Fulcher 2026", "baseline": tool, "seed": seed, "baseline_rule": rule, **result})
    from benchmark import fulcher2026_v31
    full = fulcher2026_v31.score(_as_response(v31), hierarchy(), labels)
    confident = {"dataset": "Fulcher 2026", "cells": full["n_cells"],
                 "committed_pct": full["share_of_all_cells_pct"]["committed"],
                 "correct_when_committed_pct": full["correct_when_committed_pct"]}
    return pd.DataFrame(rows), confident


def _as_response(pred: pd.DataFrame) -> dict:
    """The saved per-cell table, back in the response shape fulcher2026_v31.score reads."""
    cells = [{"cell_id": r.cell_id, "abstained": bool(r.abstained), "label": r.label or None,
              "label_level": r.label_level or None, "label_set": json.loads(r.label_set),
              "abstain_reason": r.abstain_reason or None,
              **({"best_guess": {"label": r.best_guess}} if r.best_guess else {})}
             for r in pred.itertuples()]
    return {"cells": cells}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records = [json.loads(p.read_text()) for p in sorted(RUNS.glob("*/*_seed0.json")) if p.parent.name != "smoke"]
    pd.DataFrame([{k: r[k] for k in ("dataset", "tool", "n_rna_cells", "n_query_cells", "n_genes", "gene_set",
                                     "rna_input", "query_input", "scaling", "missing_values", "settings")}
                  for r in records]).to_csv(OUT / "inputs.csv", index=False)
    paired, confident = [], []
    for name, build, keys in (("scope2", lambda: scope2(paired), ["tool", "rule", "regime"]),
                              ("pbmc240", pbmc240, ["tool", "rule"]),
                              ("fulcher2026", lambda: fulcher(paired), ["tool", "rule"])):
        per_seed, conf = build()
        per_seed.to_csv(OUT / f"{name}_per_seed.csv", index=False)
        summarise(per_seed, keys).to_csv(OUT / f"{name}_summary.csv", index=False)
        confident.append(conf)
        print(name, len(per_seed), "rows")
    pd.DataFrame(confident).to_csv(OUT / "v31_confident.csv", index=False)
    table = pd.DataFrame([{**{k: v for k, v in p.items() if k != "ci_95_pct"}, "ci_lo": p["ci_95_pct"][0],
                           "ci_hi": p["ci_95_pct"][1]} for p in paired])
    table["favours"] = np.where(table["ci_lo"] > 0, "v3.1", np.where(table["ci_hi"] < 0, "baseline", "neither"))
    table.to_csv(OUT / "paired_bootstrap.csv", index=False)
    print(table.groupby(["dataset", "baseline", "baseline_rule"]).favours.value_counts().unstack(fill_value=0))


if __name__ == "__main__":
    main()
