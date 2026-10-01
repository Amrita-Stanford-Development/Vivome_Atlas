"""Scores Fulcher 2026, the only step that reads its labels. Everything here
is fixed by research/benchmark/protocol-fulcher2026.md: the class mapping,
both decision rules, the metrics, the scANVI headline-variant rule, and the
paired bootstrap. It reuses evaluate.py unchanged.

Needs, in results/fulcher2026/: the ten <model>_latent.npy files and
cell_ids.txt (from fulcher2026_embed.py), and all nine scANVI runs, three arms (from
scanvi_run_fulcher2026.py). Writes CSV tables and summary.json to
research/benchmark/fulcher2026. Deterministic, so a rerun reproduces the
tables byte for byte.

    python benchmark/fulcher2026_score.py
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datasets  # noqa: E402
from evaluate import knn_classifier_predict, paired_bootstrap_diff  # noqa: E402

REPO = datasets.REPO
RESULTS = Path(__file__).resolve().parent / "results" / "fulcher2026"
TABLES = REPO / "research" / "benchmark" / "fulcher2026"
NB1D = REPO / "data" / "incoming" / "NB1d" / "embeddings"
TYPES = datasets.FULCHER2026["types"]
PREDICTED = TYPES + ("other",)
LINEAGE_OF_TYPE = {"CD4T": "lymphoid", "CD8T": "lymphoid", "NK": "lymphoid", "B": "lymphoid",
                   "monocyte": "myeloid", "DC": "myeloid"}
FAMILIES = {"v3": [f"v3_seed{s}" for s in range(5)], "V2": [f"V2_seed{s}" for s in range(5)]}
SCANVI_SEEDS = (0, 1, 2)
# scANVI arms: the protocol's two input variants, then amendment 2's
# measured-genes arm. The original headline rule picks among the first two;
# amendment 2's picks among all three.
SCANVI_ARMS_ORIGINAL = ("log2", "log2_cellmedian")
SCANVI_ARMS = SCANVI_ARMS_ORIGINAL + ("log2_measuredgenes",)
# Exploratory, added after results (amendment 2): CD4T and CD8T merged into T.
TYPES_5 = ("T", "NK", "B", "monocyte", "DC")
MERGE_T = {"CD4T": "T", "CD8T": "T"}

# The protocol's class mapping. Any reference class not listed is "other".
COARSE = {
    "cd4-positive, alpha-beta t cell": "CD4T",
    "naive thymus-derived cd4-positive, alpha-beta t cell": "CD4T",
    "regulatory t cell": "CD4T",
    "cd8-positive, alpha-beta t cell": "CD8T",
    "natural killer cell": "NK",
    "b cell": "B",
    "plasma cell": "B",
    "classical monocyte": "monocyte",
    "intermediate monocyte": "monocyte",
    "non-classical monocyte": "monocyte",
    "monocyte": "monocyte",
    "myeloid dendritic cell": "DC",
    "plasmacytoid dendritic cell": "DC",
}


def reference_classes() -> tuple[np.ndarray, list[str], dict]:
    meta = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    class_names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    lineage = meta.groupby("class_name")["lineage"].first().to_dict()
    assert len(class_names) == 22 and set(COARSE) <= set(class_names)
    return meta["class_name"].to_numpy(), class_names, lineage


def predict_ours(model: str, cell_names: np.ndarray, class_names: list[str]) -> dict[str, np.ndarray]:
    z = np.load(RESULTS / f"{model}_latent.npy").astype(np.float32)
    centroids = np.load(NB1D / model / "centroids.npy").astype(np.float32)
    unit = lambda x: x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-8, None)  # noqa: E731
    nearest = np.array(class_names)[(unit(z) @ unit(centroids).T).argmax(axis=1)]
    reference_z = np.load(NB1D / model / "reference_latent_f16.npy").astype(np.float32)
    knn = knn_classifier_predict(reference_z, cell_names, z)["unrestricted"]
    return {"nearest_centroid": nearest, "shared_knn": np.asarray(knn)}


def score(pred_fine: np.ndarray, true_type: np.ndarray, lineage: dict) -> tuple[dict, pd.Series, pd.DataFrame]:
    pred_type = np.array([COARSE.get(c, "other") for c in pred_fine])
    row = {"balanced_accuracy_pct": balanced_accuracy_score(true_type, pred_type) * 100}
    for t in TYPES:
        row[f"recall_{t}_pct"] = (pred_type[true_type == t] == t).mean() * 100
    pred_lineage = np.array([lineage.get(c, "none") for c in pred_fine])
    true_lineage = np.array([LINEAGE_OF_TYPE[t] for t in true_type])
    for lin in ("lymphoid", "myeloid"):
        row[f"{lin}_recall_pct"] = (pred_lineage[true_lineage == lin] == lin).mean() * 100
    composition = pd.Series(pred_type).value_counts(normalize=True).reindex(PREDICTED, fill_value=0) * 100
    confusion = pd.crosstab(pd.Categorical(true_type, TYPES), pd.Categorical(pred_type, PREDICTED), dropna=False)
    return row, composition, confusion


def main() -> None:
    labels = datasets.load_fulcher2026_labels()
    cell_ids = (RESULTS / "cell_ids.txt").read_text().split()
    assert cell_ids == labels["cell_id"].tolist(), "embedding rows are not in label order"
    scored = (labels["label"] != datasets.FULCHER2026["unscored_label"]).to_numpy()
    true_type = labels["label"].to_numpy()[scored]
    cell_names, class_names, lineage = reference_classes()

    # (family, model, seed, rule) -> predicted reference class for each scored cell
    predictions, diverged = {}, []
    for family, models in FAMILIES.items():
        for seed, model in enumerate(models):
            for rule, pred in predict_ours(model, cell_names, class_names).items():
                predictions[(family, model, seed, rule)] = pred[scored]
    for arm in SCANVI_ARMS:
        for seed in SCANVI_SEEDS:
            stem = RESULTS / f"scanvi_{arm}_seed{seed}"
            if json.loads(Path(f"{stem}.json").read_text())["diverged"]:
                diverged.append(f"scanvi_{arm}_seed{seed}")
                continue
            pred = pd.read_csv(f"{stem}_pred.csv")
            assert pred["cell_id"].tolist() == cell_ids
            for rule in ("native", "shared_knn"):
                predictions[(f"scANVI_{arm}", f"scanvi_{arm}_seed{seed}", seed, rule)] = pred[rule].to_numpy()[scored]

    rows, compositions, confusions = [], [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # "other" is never a true class
        for (family, model, seed, rule), pred in predictions.items():
            row, composition, confusion = score(pred, true_type, lineage)
            key = {"family": family, "model": model, "seed": seed, "rule": rule}
            rows.append({**key, "n_scored": int(scored.sum()), **row})
            compositions.append({**key, **{f"pred_{t}_pct": v for t, v in composition.items()}})
            confusions += [{**key, "true": t, "predicted": p, "count": int(confusion.loc[t, p])}
                           for t in TYPES for p in PREDICTED]
            fine = pd.Series(pred).value_counts(normalize=True) * 100
            compositions[-1].update({f"pred_class::{c}": fine.get(c, 0.0) for c in class_names})
    per_seed = pd.DataFrame(rows)
    metrics = [c for c in per_seed.columns if c.endswith("_pct")]
    summary = (per_seed.groupby(["family", "rule"])[metrics]
               .agg(["mean", "std", "min", "max", "count"]).stack(level=0, future_stack=True)
               .rename_axis(["family", "rule", "metric"]).reset_index())

    knn_rows = per_seed[per_seed["rule"] == "shared_knn"]
    knn_means = {arm: knn_rows.loc[knn_rows["family"] == f"scANVI_{arm}", "balanced_accuracy_pct"].mean()
                 for arm in SCANVI_ARMS}
    headlines = {"original_protocol": max(SCANVI_ARMS_ORIGINAL, key=lambda a: knn_means[a]),
                 "amendment_2_best_arm": max(SCANVI_ARMS, key=lambda a: knn_means[a])}

    comparisons = [("V2 vs v3", rule, "V2", rule, "v3", rule) for rule in ("nearest_centroid", "shared_knn")]
    for arm in dict.fromkeys(headlines.values()):  # each distinct headline arm, once
        for family in FAMILIES:
            comparisons += [(f"{family} vs scANVI_{arm}", "shared_knn", family, "shared_knn", f"scANVI_{arm}", "shared_knn"),
                            (f"{family} vs scANVI_{arm}", "nearest_centroid vs native", family, "nearest_centroid", f"scANVI_{arm}", "native")]
    boot = []
    for name, label, fam_a, rule_a, fam_b, rule_b in comparisons:
        runs_a = [(k[1], p) for k, p in predictions.items() if k[0] == fam_a and k[3] == rule_a]
        runs_b = [(k[1], p) for k, p in predictions.items() if k[0] == fam_b and k[3] == rule_b]
        for model_a, pred_a in runs_a:
            for model_b, pred_b in runs_b:
                to_type = lambda p: np.array([COARSE.get(c, "other") for c in p])  # noqa: E731
                d = paired_bootstrap_diff(true_type, to_type(pred_a), to_type(pred_b))
                lo, hi = d["ci_95_pct"]
                boot.append({"comparison": name, "rules": label, "model_a": model_a, "model_b": model_b,
                             "diff_bal_acc_pct": d["point_estimate_pct"], "ci_lo": lo, "ci_hi": hi,
                             "ci_excludes_zero": lo > 0 or hi < 0,
                             "favours": model_a.split("_seed")[0] if lo > 0 else model_b.split("_seed")[0] if hi < 0 else "neither"})
    boot = pd.DataFrame(boot)
    counts = {key: {"pairings": len(g), **g["favours"].value_counts().to_dict()}
              for key, g in boot.groupby(["comparison", "rules"])}

    # Exploratory, added after results (amendment 2): five types, T = CD4T + CD8T.
    true_5 = np.array([MERGE_T.get(t, t) for t in true_type])
    rows_5 = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for (family, model, seed, rule), pred in predictions.items():
            pred_5 = np.array([MERGE_T.get(COARSE.get(c, "other"), COARSE.get(c, "other")) for c in pred])
            row = {"family": family, "model": model, "seed": seed, "rule": rule,
                   "balanced_accuracy_5type_pct": balanced_accuracy_score(true_5, pred_5) * 100}
            row.update({f"recall_{t}_pct": (pred_5[true_5 == t] == t).mean() * 100 for t in TYPES_5})
            rows_5.append(row)
    per_seed_5 = pd.DataFrame(rows_5)
    summary_5 = (per_seed_5.groupby(["family", "rule"])["balanced_accuracy_5type_pct"]
                 .agg(["mean", "std", "min", "max", "count"]).reset_index())

    # Which genes scANVI saw (label-free): every gene of the benchmark space,
    # whether Fulcher measured it, and in how many of the 1,275 cells.
    bench_x, _, bench_genes = datasets.load_fulcher2026_benchmark_matrix("log2")
    observed_cells = np.isfinite(bench_x).sum(axis=0)
    gene_space = pd.DataFrame({"gene": bench_genes, "fulcher_cells_observed": observed_cells,
                               "in_arm_log2": True, "in_arm_log2_cellmedian": True,
                               "in_arm_log2_measuredgenes": observed_cells > 0})

    TABLES.mkdir(parents=True, exist_ok=True)
    fmt = {"index": False, "float_format": "%.4f"}
    per_seed.to_csv(TABLES / "per_seed_scores.csv", **fmt)
    summary.to_csv(TABLES / "family_summary.csv", **fmt)
    pd.DataFrame(compositions).to_csv(TABLES / "predicted_composition.csv", **fmt)
    pd.DataFrame(confusions).to_csv(TABLES / "confusion.csv", **fmt)
    boot.to_csv(TABLES / "paired_bootstrap.csv", **fmt)
    per_seed_5.to_csv(TABLES / "exploratory_5type_per_seed.csv", **fmt)
    summary_5.to_csv(TABLES / "exploratory_5type_summary.csv", **fmt)
    gene_space.to_csv(TABLES / "scanvi_gene_space.csv", **fmt)
    (TABLES / "summary.json").write_text(json.dumps({
        "n_scored": int(scored.sum()),
        "scanvi_headline_arm": headlines,
        "scanvi_shared_knn_mean_bal_acc_pct": {a: round(m, 4) for a, m in knn_means.items()},
        "scanvi_gene_space": {"genes": len(bench_genes), "measured_in_fulcher": int((observed_cells > 0).sum()),
                              "never_measured_zero_filled": int((observed_cells == 0).sum()),
                              "per_cell_observed_min": int(np.isfinite(bench_x).sum(1).min()),
                              "per_cell_observed_median": float(np.median(np.isfinite(bench_x).sum(1)))},
        "scanvi_diverged_runs": diverged,
        "ci_excludes_zero_counts": {f"{c} [{r}]": v for (c, r), v in counts.items()},
    }, indent=2) + "\n")
    print(summary.query("metric == 'balanced_accuracy_pct'")[["family", "rule", "mean", "std", "min", "max"]].to_string(index=False))
    print(json.dumps({f"{c} [{r}]": v for (c, r), v in counts.items()}, indent=2))
    print("exploratory 5-type (added after results):")
    print(summary_5.to_string(index=False))


if __name__ == "__main__":
    main()
