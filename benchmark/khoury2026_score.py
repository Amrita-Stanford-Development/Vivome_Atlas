"""Khoury 2026 final evaluation, step 4: the scoring, the only step that reads
Khoury's labels. Everything is fixed by research/benchmark/protocol-khoury2026.md
and its amendments: the class mapping, the decision rules, the metrics, the
scANVI headline-arm rule, the paired bootstraps, and the divergence rule.
It reuses evaluate.py unchanged.

Inputs:
- khoury2026_embed.py: <out>/V2_seed{0..4}_latent.npy (v3.1's members),
  v3_served_latent.npy, cell_ids.txt, v31_pred.csv (v3.1 as served);
- scanvi_run_khoury2026.py: <out>/scanvi_<arm>_seed<seed>_pred.csv, 3 arms x 3 seeds;
- baselines_run.py: results/baselines_ext/khoury2026/<tool>_seed<seed>_pred.csv.

Families and rules scored on all cells (five types; "other" is wrong for every type):
- "v3.1": the served best guess (the product rule), one run;
- "v3.1 members": each member's shared kNN on its own reference latents;
- "v3": v3 as served, nearest centroid (the product rule) and shared kNN;
- "scANVI_<arm>": native classifier and shared kNN, seeds 0-2;
- baselines: MaxFuse, scGLUE, Harmony (shared kNN, seeds 0-2), Seurat CCA
  (native, seed 0), correlation to class mean (its own rule, seed 0).
A diverged run is listed and not scored (amendment 4).

Writes, to research/benchmark/khoury2026/: per_seed_scores.csv,
family_summary.csv, predicted_composition.csv, confusion.csv,
paired_bootstrap.csv, v31_confident.json, summary.json. Deterministic: a rerun
reproduces them byte for byte, the one rerun the protocol allows.

    python -m benchmark.khoury2026_score --unseal       # once, at the final evaluation
    python -m benchmark.khoury2026_score --rehearse     # the same code on Fulcher 2026 (development data)

--rehearse scores Fulcher's cells of the five Khoury types from the inputs
that already exist (khoury2026_embed.py --rehearse, the Fulcher scANVI runs,
the Track D Fulcher runs), into results/khoury2026_rehearsal/tables/, and
checks every per-type recall against Fulcher's committed tables.
"""
from __future__ import annotations

import argparse
import collections
import json
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

from benchmark import datasets, v31_dev_gate
from benchmark import fulcher2026_score as fulcher
from benchmark.baselines_score import _as_response, read_v31
from benchmark.evaluate import knn_classifier_predict, paired_bootstrap_diff
from benchmark.khoury2026_embed import MEMBERS, out_dir, tables_dir
from service.pipeline import pipeline

REPO = datasets.REPO
RESULTS = REPO / "benchmark" / "results"
RUNTIME = REPO / "service" / "model" / "runtime"
MEMBERS_DIR = REPO / "service" / "model" / "v3_1" / "members"
TYPES = datasets.KHOURY2026["types"]
PREDICTED = TYPES + ("other",)
LINEAGE_OF_TYPE = {"CD4T": "lymphoid", "CD8T": "lymphoid", "NK": "lymphoid", "B": "lymphoid", "monocyte": "myeloid"}
# The protocol's class mapping: Fulcher's, with both DC classes mapped to "other".
COARSE = {name: t for name, t in fulcher.COARSE.items() if t in TYPES}
SCANVI_ARMS = ("as_provided", "cellmedian", "measuredgenes")
SCANVI_SEEDS = (0, 1, 2)
REHEARSAL_SCANVI = {"as_provided": "log2", "cellmedian": "log2_cellmedian", "measuredgenes": "log2_measuredgenes"}
# Amendment 3: the rule scored per tool on Khoury, and its seeds.
BASELINES = {"maxfuse": ("knn", "shared_knn", (0, 1, 2)), "scglue": ("knn", "shared_knn", (0, 1, 2)),
             "harmony": ("knn", "shared_knn", (0, 1, 2)), "seurat": ("native", "native", (0,)),
             "correlation": ("corr", "correlation", (0,))}


@dataclass
class Sources:
    dataset: str
    labels: pd.DataFrame  # cell_id, label (one of TYPES, or another label in the rehearsal)
    out: Path  # khoury2026_embed.py's outputs
    scanvi_stem: callable  # (arm, seed) -> path stem
    baselines: Path
    tables: Path


def sources(rehearse: bool) -> Sources:
    if rehearse:
        return Sources("Fulcher 2026 (rehearsal, five Khoury types)", datasets.load_fulcher2026_labels(), out_dir(True),
                       lambda arm, seed: RESULTS / "fulcher2026" / f"scanvi_{REHEARSAL_SCANVI[arm]}_seed{seed}",
                       RESULTS / "baselines_ext" / "fulcher2026", tables_dir(True))
    labels = datasets.load_khoury2026_labels(unseal=True)
    if not labels["label"].isin(TYPES).all():
        raise ValueError("a Khoury cell has no type; the protocol scores all 1,651")
    return Sources("Khoury 2026", labels, out_dir(False),
                   lambda arm, seed: out_dir(False) / f"scanvi_{arm}_seed{seed}",
                   RESULTS / "baselines_ext" / "khoury2026", tables_dir(False))


def reference_classes() -> tuple[np.ndarray, list[str], dict]:
    meta = pd.read_csv(RUNTIME / "reference_metadata.csv")
    class_names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    lineage = meta.groupby("class_name")["lineage"].first().to_dict()
    assert len(class_names) == 22 and set(COARSE) <= set(class_names)
    return meta["class_name"].to_numpy(), class_names, lineage


def to_type(pred_fine: np.ndarray) -> np.ndarray:
    return np.array([COARSE.get(c, "other") for c in pred_fine])


def score(pred_fine: np.ndarray, true_type: np.ndarray, lineage: dict) -> tuple[dict, pd.Series, pd.DataFrame]:
    pred_type = to_type(pred_fine)
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


def collect_predictions(src: Sources, scored: np.ndarray, cell_ids: list[str]) -> tuple[dict, list[str]]:
    """(family, model, seed, rule) -> predicted reference class per scored cell; and the diverged runs."""
    cell_names, class_names, _ = reference_classes()
    unit = lambda x: x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-8, None)  # noqa: E731
    predictions, diverged = {}, []

    v31 = read_v31(src.out, "v31")  # <out>/v31_pred.csv
    assert v31["cell_id"].tolist() == cell_ids
    predictions[("v3.1", "v3.1", 0, "best_guess")] = v31["best_guess"].to_numpy()[scored]
    for seed, model in enumerate(MEMBERS):
        z = np.load(src.out / f"{model}_latent.npy").astype(np.float32)
        reference_z = np.load(MEMBERS_DIR / f"{model}_reference_latent_f16.npy").astype(np.float32)
        predictions[("v3.1 members", model, seed, "shared_knn")] = np.asarray(
            knn_classifier_predict(reference_z, cell_names, z)["unrestricted"])[scored]

    z = np.load(src.out / "v3_served_latent.npy").astype(np.float32)
    centroids = np.load(RUNTIME / "reference_centroids.npy").astype(np.float32)
    predictions[("v3", "v3_served", 0, "nearest_centroid")] = np.array(class_names)[
        (unit(z) @ unit(centroids).T).argmax(axis=1)][scored]
    reference_z = np.load(RUNTIME / "reference_embedding.npy").astype(np.float32)
    predictions[("v3", "v3_served", 0, "shared_knn")] = np.asarray(
        knn_classifier_predict(reference_z, cell_names, z)["unrestricted"])[scored]

    for arm in SCANVI_ARMS:
        for seed in SCANVI_SEEDS:
            stem = src.scanvi_stem(arm, seed)
            if json.loads(Path(f"{stem}.json").read_text())["diverged"]:
                diverged.append(f"scanvi_{arm}_seed{seed}")
                continue
            pred = pd.read_csv(f"{stem}_pred.csv", dtype={"cell_id": str})
            assert pred["cell_id"].tolist() == cell_ids
            for rule in ("native", "shared_knn"):
                predictions[(f"scANVI_{arm}", f"scanvi_{arm}_seed{seed}", seed, rule)] = pred[rule].to_numpy()[scored]

    for tool, (column, rule, seeds) in BASELINES.items():
        for seed in seeds:
            stem = src.baselines / f"{tool}_seed{seed}"
            if json.loads(Path(f"{stem}.json").read_text())["diverged"]:
                diverged.append(f"{tool}_seed{seed}")
                continue
            pred = pd.read_csv(f"{stem}_pred.csv", dtype={"cell_id": str})
            assert pred["cell_id"].tolist() == cell_ids
            predictions[(tool, f"{tool}_seed{seed}", seed, rule)] = pred[f"{column}_unrestricted"].to_numpy()[scored]
    return predictions, diverged


def comparisons(predictions: dict, headline_arm: str) -> list[tuple]:
    """(name, rules, family_a, rule_a, family_b, rule_b): the protocol's paired bootstraps."""
    scanvi = f"scANVI_{headline_arm}"
    pairs = [
        ("v3.1 vs v3", "product rules", "v3.1", "best_guess", "v3", "nearest_centroid"),
        ("v3.1 vs v3", "shared_knn", "v3.1 members", "shared_knn", "v3", "shared_knn"),
        (f"v3.1 vs {scanvi}", "product rule vs native", "v3.1", "best_guess", scanvi, "native"),
        (f"v3.1 vs {scanvi}", "shared_knn", "v3.1 members", "shared_knn", scanvi, "shared_knn"),
        (f"v3 vs {scanvi}", "product rule vs native", "v3", "nearest_centroid", scanvi, "native"),
        (f"v3 vs {scanvi}", "shared_knn", "v3", "shared_knn", scanvi, "shared_knn"),
    ]
    for tool, (_, rule, _) in BASELINES.items():  # amendments 2 and 3
        if rule == "shared_knn":
            pairs.append((f"v3.1 vs {tool}", "shared_knn", "v3.1 members", "shared_knn", tool, "shared_knn"))
        else:
            pairs.append((f"v3.1 vs {tool}", f"product rule vs {rule}", "v3.1", "best_guess", tool, rule))
    return pairs


def bootstrap(predictions: dict, true_type: np.ndarray, headline_arm: str) -> pd.DataFrame:
    rows = []
    for name, rules, fam_a, rule_a, fam_b, rule_b in comparisons(predictions, headline_arm):
        runs_a = [(k[1], p) for k, p in predictions.items() if k[0] == fam_a and k[3] == rule_a]
        runs_b = [(k[1], p) for k, p in predictions.items() if k[0] == fam_b and k[3] == rule_b]
        for model_a, pred_a in runs_a:
            for model_b, pred_b in runs_b:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)  # "other" is never a true type
                    d = paired_bootstrap_diff(true_type, to_type(pred_a), to_type(pred_b))
                lo, hi = d["ci_95_pct"]
                rows.append({"comparison": name, "rules": rules, "model_a": model_a, "model_b": model_b,
                             "diff_bal_acc_pct": d["point_estimate_pct"], "ci_lo": lo, "ci_hi": hi,
                             "ci_excludes_zero": lo > 0 or hi < 0,
                             "favours": model_a if lo > 0 else model_b if hi < 0 else "neither"})
    return pd.DataFrame(rows)


def confident(src: Sources, scored: np.ndarray, true_type: np.ndarray) -> dict:
    """v3.1's confident answers (amendment 2, secondary): judged at the stated
    level, a class through the class mapping, a group or lineage against the
    one the true type's classes share in NB2's hierarchy. Counts beside every
    percentage."""
    hierarchy = pipeline.load_bundle("v3.1").hierarchy
    response = _as_response(read_v31(src.out, "v31"))
    share, composition = v31_dev_gate.summarise(response, hierarchy)  # over all upload cells
    expected = {}
    for level in ("group", "lineage"):
        found = collections.defaultdict(set)
        for name, t in COARSE.items():
            found[t].add(hierarchy[name][level])
        if any(len(v) != 1 for v in found.values()):
            raise ValueError(f"a type spans several {level}s: {dict(found)}")
        expected[level] = {t: v.pop() for t, v in found.items()}
    by_type = {t: collections.Counter() for t in TYPES}
    for cell, t in zip(np.array(response["cells"], dtype=object)[scored], true_type):
        tally = by_type[t]
        tally["n"] += 1
        if not cell["abstained"]:
            level = cell["label_level"]
            tally["committed"] += 1
            tally[f"stated_{level}"] += 1
            tally["correct"] += (COARSE.get(cell["label"], "other") == t) if level == "class" else (expected[level][t] == cell["label"])
    pct = lambda a, b: round(100 * a / b, 2) if b else None  # noqa: E731
    committed, correct = (sum(c[k] for c in by_type.values()) for k in ("committed", "correct"))
    return {
        "n_cells": len(response["cells"]), "n_scored": int(scored.sum()),
        "share_of_all_cells_pct": {k: round(v, 2) for k, v in share.items()},
        "composition_pct": {k: round(v, 2) for k, v in sorted(composition.items(), key=lambda kv: -kv[1])},
        "committed_scored": committed, "correct_scored": correct,
        "committed_pct": pct(committed, int(scored.sum())), "correct_when_committed_pct": pct(correct, committed),
        "by_type": {t: {"n": c["n"], "committed": c["committed"], "correct": c["correct"],
                        "committed_pct": pct(c["committed"], c["n"]),
                        "correct_at_stated_level_pct": pct(c["correct"], c["committed"]),
                        "stated_level_counts": {lvl: c[f"stated_{lvl}"] for lvl in ("class", "group", "lineage")}}
                    for t, c in by_type.items()},
    }


def check_rehearsal(per_seed: pd.DataFrame, conf: dict) -> None:
    """Per-type recall does not depend on which other types are scored, so the
    rehearsal must reproduce Fulcher's committed recalls for the five types."""
    recalls = [f"recall_{t}_pct" for t in TYPES]
    fulcher_seed = pd.read_csv(REPO / "research" / "benchmark" / "fulcher2026" / "per_seed_scores.csv")
    baselines_seed = pd.read_csv(REPO / "research" / "benchmark" / "baselines" / "fulcher2026_per_seed.csv")
    pairs = [(("v3.1 members", f"V2_seed{s}", "shared_knn"), fulcher_seed.query(f"model == 'V2_seed{s}' and rule == 'shared_knn'"))
             for s in range(5)]
    pairs += [(("v3", "v3_served", rule), fulcher_seed.query(f"model == 'v3_seed0' and rule == '{rule}'"))
              for rule in ("nearest_centroid", "shared_knn")]
    pairs += [((f"scANVI_{arm}", f"scanvi_{arm}_seed{s}", rule),
               fulcher_seed.query(f"model == 'scanvi_{REHEARSAL_SCANVI[arm]}_seed{s}' and rule == '{rule}'"))
              for arm in SCANVI_ARMS for s in SCANVI_SEEDS for rule in ("native", "shared_knn")]
    rule_name = {"shared_knn": "shared kNN", "native": "Seurat native transfer", "correlation": "correlation to class mean"}
    pairs += [((tool, f"{tool}_seed{s}", rule), baselines_seed.query(f"tool == '{tool}' and seed == {s} and rule == '{rule_name[rule]}'"))
              for tool, (_, rule, seeds) in BASELINES.items() for s in seeds]
    pairs.append((("v3.1", "v3.1", "best_guess"), baselines_seed.query("tool == 'v3.1 (served)'")))
    worst, missing = 0.0, []
    for (family, model, rule), reference in pairs:
        mine = per_seed.query("family == @family and model == @model and rule == @rule")
        if mine.empty or reference.empty:
            missing.append(f"{model} {rule}: {'not scored here' if mine.empty else 'no Fulcher row'}")
            continue
        worst = max(worst, float(np.abs(mine[recalls].to_numpy() - reference[recalls].to_numpy()).max()))
    print(f"rehearsal check: {len(pairs) - len(missing)} runs, largest per-type recall difference from Fulcher's tables: {worst:.6f} points")
    for m in missing:
        print(f"  not compared: {m}")
    earlier = json.loads((REPO / "research" / "benchmark" / "fulcher2026" / "v31_development.json").read_text())["by_author_type"]
    same = all(conf["by_type"][t][k] == earlier[t][k] for t in TYPES for k in ("n", "committed", "correct"))
    print(f"rehearsal check: v3.1 confident answers per type {'match' if same else 'DIFFER FROM'} v31_development.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--unseal", action="store_true", help="read Khoury's labels: once, at the final evaluation")
    mode.add_argument("--rehearse", action="store_true", help="the same code on Fulcher 2026, a development dataset")
    args = parser.parse_args()
    src = sources(args.rehearse)
    cell_ids = (src.out / "cell_ids.txt").read_text().split()
    if src.labels["cell_id"].tolist() != cell_ids:
        raise ValueError("embedding rows are not in label order")
    scored = src.labels["label"].isin(TYPES).to_numpy()
    true_type = src.labels["label"].to_numpy()[scored]
    _, class_names, lineage = reference_classes()
    predictions, diverged = collect_predictions(src, scored, cell_ids)

    rows, compositions, confusions = [], [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # "other" is never a true type
        for (family, model, seed, rule), pred in predictions.items():
            row, composition, confusion = score(pred, true_type, lineage)
            key = {"family": family, "model": model, "seed": seed, "rule": rule}
            rows.append({**key, "n_scored": int(scored.sum()), **row})
            fine = pd.Series(pred).value_counts(normalize=True) * 100
            compositions.append({**key, **{f"pred_{t}_pct": v for t, v in composition.items()},
                                 **{f"pred_class::{c}": fine.get(c, 0.0) for c in class_names}})
            confusions += [{**key, "true": t, "predicted": p, "count": int(confusion.loc[t, p])}
                           for t in TYPES for p in PREDICTED]
    per_seed = pd.DataFrame(rows)
    metrics = [c for c in per_seed.columns if c.endswith("_pct")]
    summary = (per_seed.groupby(["family", "rule"], sort=False)[metrics]
               .agg(["mean", "std", "min", "max", "count"]).stack(level=0, future_stack=True)
               .rename_axis(["family", "rule", "metric"]).reset_index())

    knn = per_seed[per_seed["rule"] == "shared_knn"]
    knn_means = {arm: knn.loc[knn["family"] == f"scANVI_{arm}", "balanced_accuracy_pct"].mean() for arm in SCANVI_ARMS}
    headline = max((a for a in SCANVI_ARMS if not np.isnan(knn_means[a])), key=lambda a: knn_means[a])
    boot = bootstrap(predictions, true_type, headline)
    counts = {f"{c} [{r}]": {"pairings": len(g), **g["favours"].str.split("_seed").str[0].value_counts().to_dict()}
              for (c, r), g in boot.groupby(["comparison", "rules"], sort=False)}
    conf = confident(src, scored, true_type)

    src.tables.mkdir(parents=True, exist_ok=True)
    fmt = {"index": False, "float_format": "%.4f"}
    per_seed.to_csv(src.tables / "per_seed_scores.csv", **fmt)
    summary.to_csv(src.tables / "family_summary.csv", **fmt)
    pd.DataFrame(compositions).to_csv(src.tables / "predicted_composition.csv", **fmt)
    pd.DataFrame(confusions).to_csv(src.tables / "confusion.csv", **fmt)
    boot.to_csv(src.tables / "paired_bootstrap.csv", **fmt)
    (src.tables / "v31_confident.json").write_text(json.dumps(conf, indent=2) + "\n")
    (src.tables / "summary.json").write_text(json.dumps({
        "dataset": src.dataset, "n_scored": int(scored.sum()),
        "scanvi_headline_arm": headline,
        "scanvi_shared_knn_mean_bal_acc_pct": {a: round(m, 4) for a, m in knn_means.items()},
        "diverged_runs": diverged,
        "ci_excludes_zero_counts": counts,
    }, indent=2) + "\n")
    print(summary.query("metric == 'balanced_accuracy_pct'")[["family", "rule", "mean", "std", "min", "max", "count"]]
          .to_string(index=False))
    print(json.dumps({"scanvi_headline_arm": headline, "diverged_runs": diverged, "counts": counts}, indent=2))
    if args.rehearse:
        check_rehearsal(per_seed, conf)


if __name__ == "__main__":
    main()
