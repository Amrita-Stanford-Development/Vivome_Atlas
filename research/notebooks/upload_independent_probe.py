"""Goal 2, Phase 2d probe: can a cell be typed without scaling genes within its
upload? Exploratory, on development data; it decides nothing by itself.

Phase 1.5 (run history, entry 35) found that an upload of one cell type
collapses, because every gene is z-scored within the upload. Scaling within
the upload is what removes each dataset's per-protein offsets (detectability,
instrument), so it cannot simply be dropped. This probe measures what is left
without it, on Fulcher 2026's mixed upload (six author types), against
Rieckmann's protein class means (research/notebooks/rieckmann_feasibility.py):
- "within upload": the Phase 2a feasibility rule (genes z-scored within the
  upload, class means z-scored across classes), for reference;
- "raw profile": each cell's log intensities, centred within the cell only,
  correlated with each class's mean log2 profile (not z-scored);
- "reference-centred": each cell's log intensities minus each protein's mean
  across Rieckmann's classes, centred within the cell, correlated with the
  class means minus that same protein mean.
The last two depend on nothing else in the upload, so a single-type upload
scores exactly as the same cells in a mixed one.

Writes research/notebook-outputs/upload_independent_probe/summary.json.

    python research/notebooks/upload_independent_probe.py      # from the repository root
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import rieckmann_feasibility as feas  # noqa: E402
from benchmark import datasets  # noqa: E402
from benchmark import fulcher2026_score as fulcher  # noqa: E402
from service.pipeline import alignment, fusion  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "upload_independent_probe"


def raw_class_means(class_names: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    """Mean log2 LFQ per reference class (not z-scored), proteins x classes."""
    header = [c.strip('"') for c in feas.RIECKMANN.open(encoding="utf-8").readline().rstrip("\n").split("\t")]
    cols = {}
    for c in header:
        m = re.match(r"LFQ\.intensity\.(.+)_(\d\d) \(steady-state\)$", c)
        if m and m.group(1) in feas.POPULATIONS:
            cols[c] = feas.POPULATIONS[m.group(1)]
    table = pd.read_csv(feas.RIECKMANN, sep="\t", usecols=["Gene.names"] + list(cols), dtype={"Gene.names": str})
    table["symbol"] = table["Gene.names"].fillna("").map(feas.first_symbol)
    table = table[table["symbol"] != ""].groupby("symbol").max(numeric_only=True)
    logged = np.log2(table.where(table > 0))
    means = pd.DataFrame({k: logged[[c for c, v in cols.items() if v == k]].mean(axis=1) for k in sorted(set(cols.values()))})
    means = means[means.notna().all(axis=1)]  # proteins every class shows: an absolute profile needs them all
    covered = np.array([c in means.columns for c in class_names])
    return means, covered


def cell_log_profile(raw: alignment.RawMatrix, genes: list[str]) -> np.ndarray:
    """Cells x genes, log scale as the service detects it, rows merged by median, NaN unobserved; no scaling."""
    values, _ = alignment.detect_and_transform_value_scale(raw.values)
    index = {g: i for i, g in enumerate(genes)}
    x = np.full((len(raw.cell_ids), len(genes)), np.nan)
    rows: dict[int, list[int]] = {}
    for r, name in enumerate(raw.gene_names):
        if (col := index.get(feas.first_symbol(name))) is not None:
            rows.setdefault(col, []).append(r)
    for col, rs in rows.items():
        x[:, col] = np.nanmedian(values[rs], axis=0) if len(rs) > 1 else values[rs[0]]
    return x


def predict(x: np.ndarray, means: np.ndarray, allowed: np.ndarray, names: list[str]) -> np.ndarray:
    mask = np.isfinite(x)
    r = fusion.masked_pearson(np.where(mask, x, 0.0), mask.astype(np.float32), means)
    r[:, ~allowed] = -np.inf
    return np.array(names)[r.argmax(axis=1)]


def score(pred: np.ndarray, truth: np.ndarray) -> dict:
    t = np.array([fulcher.COARSE.get(c, "other") for c in pred])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = {"balanced_accuracy": round(100 * balanced_accuracy_score(truth, t), 2)}
    out.update({f"recall_{k}": round(100 * float((t[truth == k] == k).mean()), 2) for k in fulcher.TYPES})
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    raw = datasets.load_fulcher2026_upload()
    labels = datasets.load_fulcher2026_labels().set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
    scored = np.isin(labels, fulcher.TYPES)
    zmeans, zgenes, covered = feas.protein_means(names)
    v, m = feas.query(raw, zgenes)
    arms = {"within upload": predict(np.where(m > 0, v, np.nan), zmeans, covered, names)}
    means, covered_raw = raw_class_means(names)
    genes = means.index.tolist()
    x = cell_log_profile(raw, genes)
    M = np.zeros((len(names), len(genes)))
    for k, c in enumerate(names):
        if c in means.columns:
            M[k] = means[c].to_numpy()
    arms["raw profile"] = predict(x, M, covered_raw, names)
    mu = means.mean(axis=1).to_numpy()
    arms["reference-centred"] = predict(x - mu, M - mu * covered_raw[:, None], covered_raw, names)
    summary = {"proteins_all_classes_show": len(genes),
               "median_observed_per_cell": int(np.median(np.isfinite(x).sum(1))),
               "fulcher_mixed": {k: score(p[scored], labels[scored]) for k, p in arms.items()}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
