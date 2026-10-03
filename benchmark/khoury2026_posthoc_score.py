"""Khoury 2026, POST-HOC: the corrected baselines (baselines_corrected.py
--posthoc) scored beside v3.1 and v3.

Khoury's labels were read at its one scoring under its protocol, on
2026-10-03. A review afterwards found the baselines and scANVI handicapped by
our setup, and the owner asked for corrected reruns, reported on Khoury as a
post-hoc analysis (research/benchmark/baseline-corrections.md). The protocol's
result in research/benchmark/khoury2026/ stays as scored; nothing here
replaces it.

The metric code, class mapping and paired bootstrap are khoury2026_score.py's,
unchanged. v3.1's and v3's predictions are rebuilt from the same saved outputs
by its own collect_predictions, and their scores are checked against the
sealed tables before anything is written.

Writes research/benchmark/khoury2026_posthoc/: per_seed_scores.csv,
family_summary.csv, predicted_composition.csv, confusion.csv,
paired_bootstrap.csv, setup_checks.csv, summary.json.

    python -m benchmark.khoury2026_posthoc_score      # from the repository root
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import baselines_corrected, datasets
from benchmark import khoury2026_score as protocol
from benchmark.baselines_corrected_score import setup_table

OUT = datasets.REPO / "research" / "benchmark" / "khoury2026_posthoc"
SEALED = datasets.REPO / "research" / "benchmark" / "khoury2026"
RUNS = baselines_corrected.OUT / "khoury2026"
SCANVI = "scANVI_corrected"  # one arm: the inputs every tool gets
# family: (tool, prediction column, rule, seeds). A shared-kNN family is compared
# with v3.1's members under the same rule; any other with v3.1's best guess.
FAMILIES = {
    "correlation": ("correlation", "corr_unrestricted", "correlation", (0,)),
    "pca": ("pca", "knn_unrestricted", "shared_knn", (0,)),
    "harmony": ("harmony", "knn_unrestricted", "shared_knn", (0, 1, 2)),
    "seurat": ("seurat", "native_unrestricted", "native", (0,)),
    "maxfuse": ("maxfuse", "knn_unrestricted", "shared_knn", (0, 1, 2)),
    "maxfuse_matching": ("maxfuse", "match_unrestricted", "matching", (0, 1, 2)),
    "scglue": ("scglue", "knn_unrestricted", "shared_knn", (0, 1, 2)),
}


def corrected_predictions(cell_ids: list[str]) -> tuple[dict, dict]:
    predictions, excluded = {}, {"diverged": [], "failed": [], "missing": []}
    runs = [(SCANVI, "scanvi", s, {"native": "clf_unrestricted", "shared_knn": "knn_unrestricted"}) for s in (0, 1, 2)]
    runs += [(family, tool, s, {rule: column}) for family, (tool, column, rule, seeds) in FAMILIES.items() for s in seeds]
    for family, tool, seed, columns in runs:
        stem = RUNS / f"{tool}_seed{seed}"
        if not Path(f"{stem}.json").exists():
            excluded["missing"].append(f"{tool}_seed{seed}")
            continue
        status = json.loads(Path(f"{stem}.json").read_text()).get("status")
        if status != "completed":
            excluded[status].append(f"{tool}_seed{seed}")
            continue
        pred = pd.read_csv(f"{stem}_pred.csv", dtype={"cell_id": str}, keep_default_na=False)
        protocol.same_rows(pred["cell_id"].tolist(), cell_ids, f"{stem}_pred.csv")
        for rule, column in columns.items():
            predictions[(family, f"{tool}_seed{seed}", seed, rule)] = pred[column].to_numpy()
    for key in ("diverged", "failed", "missing"):
        excluded[key] = sorted(set(excluded[key]))
    return predictions, excluded


def main() -> None:
    src = protocol.sources(False)
    cell_ids = (src.out / "cell_ids.txt").read_text().splitlines()
    gate = json.loads((SEALED / "gate.json").read_text())
    if not gate.get("passed"):
        raise SystemExit("v3.1's gate did not pass; the sealed scoring did not score it either")
    saved = protocol.SCANVI_ARMS, protocol.BASELINES
    protocol.SCANVI_ARMS, protocol.BASELINES = (), {}  # v3.1 and v3 only, as the sealed scoring built them
    try:
        predictions, _ = protocol.collect_predictions(src, cell_ids, with_v31=True)
    finally:
        protocol.SCANVI_ARMS, protocol.BASELINES = saved
    corrected, excluded = corrected_predictions(cell_ids)
    predictions.update(corrected)

    labels = datasets.load_khoury2026_labels(unseal=True)  # read at the 2026-10-03 scoring; post-hoc use
    protocol.same_rows(labels["cell_id"].tolist(), cell_ids, "labels")
    scored = labels["label"].isin(protocol.TYPES).to_numpy()
    true_type = labels["label"].to_numpy()[scored]
    _, class_names, lineage = protocol.reference_classes()
    predictions = {key: pred[scored] for key, pred in predictions.items()}

    rows, compositions, confusions = [], [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for (family, model, seed, rule), pred in predictions.items():
            row, composition, confusion = protocol.score(pred, true_type, lineage)
            key = {"family": family, "model": model, "seed": seed, "rule": rule}
            rows.append({**key, "n_scored": int(scored.sum()), **row})
            fine = pd.Series(pred).value_counts(normalize=True) * 100
            compositions.append({**key, **{f"pred_{t}_pct": v for t, v in composition.items()},
                                 **{f"pred_class::{c}": fine.get(c, 0.0) for c in class_names}})
            confusions += [{**key, "true": t, "predicted": p, "count": int(confusion.loc[t, p])}
                           for t in protocol.TYPES for p in protocol.PREDICTED]
    per_seed = pd.DataFrame(rows)
    check_against_sealed(per_seed)
    metrics = [c for c in per_seed.columns if c.endswith("_pct")]
    summary = (per_seed.groupby(["family", "rule"], sort=False)[metrics]
               .agg(["mean", "std", "min", "max", "count"]).stack(level=0, future_stack=True)
               .rename_axis(["family", "rule", "metric"]).reset_index())

    has_scanvi = any(k[0] == SCANVI for k in predictions)
    saved = protocol.BASELINES
    protocol.BASELINES = {family: (column, rule, seeds) for family, (_, column, rule, seeds) in FAMILIES.items()}
    try:
        boot = protocol.bootstrap(predictions, true_type, "corrected" if has_scanvi else None)
    finally:
        protocol.BASELINES = saved
    counts = {f"{c} [{r}]": {"pairings": len(g), **g["favours"].str.split("_seed").str[0].value_counts().to_dict()}
              for (c, r), g in boot.groupby(["comparison", "rules"], sort=False)}

    OUT.mkdir(parents=True, exist_ok=True)
    fmt = {"index": False, "float_format": "%.4f"}
    per_seed.to_csv(OUT / "per_seed_scores.csv", **fmt)
    summary.to_csv(OUT / "family_summary.csv", **fmt)
    pd.DataFrame(compositions).to_csv(OUT / "predicted_composition.csv", **fmt)
    pd.DataFrame(confusions).to_csv(OUT / "confusion.csv", **fmt)
    boot.to_csv(OUT / "paired_bootstrap.csv", **fmt)
    setup_table(["khoury2026"]).to_csv(OUT / "setup_checks.csv", index=False)
    (OUT / "summary.json").write_text(json.dumps({
        "dataset": "Khoury 2026", "posthoc": True,
        "note": "Post-hoc: Khoury's labels were read at its one scoring (2026-10-03). Corrected baselines per "
                "research/benchmark/baseline-corrections.md. The protocol's result is research/benchmark/khoury2026/.",
        "n_scored": int(scored.sum()), "excluded_runs": excluded, "ci_excludes_zero_counts": counts,
    }, indent=2, allow_nan=False) + "\n")
    print(summary.query("metric == 'balanced_accuracy_pct'")[["family", "rule", "mean", "std", "min", "max", "count"]]
          .to_string(index=False))
    print(json.dumps({"excluded_runs": excluded, "counts": counts}, indent=2))


def check_against_sealed(per_seed: pd.DataFrame) -> None:
    """v3.1's and v3's rows must equal the sealed scoring's, to its 4 decimals."""
    sealed = pd.read_csv(SEALED / "per_seed_scores.csv")
    ours = per_seed[per_seed["family"].isin(["v3.1", "v3.1 members", "v3"])]
    merged = ours.merge(sealed, on=["family", "model", "seed", "rule"], suffixes=("", "_sealed"))
    if len(merged) != len(ours) or len(ours) != 8:
        raise ValueError(f"expected the sealed scoring's 8 v3.1/v3 rows, matched {len(merged)} of {len(ours)}")
    cols = [c for c in ours.columns if c.endswith("_pct")]
    worst = float(np.abs(merged[cols].to_numpy() - merged[[f"{c}_sealed" for c in cols]].to_numpy()).max())
    if worst > 1e-4:
        raise ValueError(f"v3.1/v3 scores differ from the sealed tables by up to {worst}")
    print(f"v3.1 and v3 rows match the sealed scoring (largest difference {worst:.2e})")


if __name__ == "__main__":
    main()
