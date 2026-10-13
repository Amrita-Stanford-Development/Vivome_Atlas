"""Track H: why CD8 T fails on protein data. A diagnosis; it chooses nothing.

v5.1's post-hoc Khoury check found Khoury's CD8 T cells mostly called CD4 T
by every method, ours and the corrected baselines alike. This script asks
why, in three parts.

1. Khoury 2026 (post-hoc; its labels were read at its one scoring,
   2026-10-03). Khoury's CD4 T and CD8 T labels are protein-only Seurat
   clusters, named by hand from marker proteins, CD8A and GZMA for CD8 T
   (research/benchmark/protocol-khoury2026.md). Per marker protein, it
   reports detection and mean log2 in the CD4, CD8 and NK clusters, Cohen's
   d between CD8 and CD4, and the AUC of CD8A, S100A4 and ANXA1 for the CD8
   cluster against the CD4 cluster.
2. Where our guesses go. The fine classes v3.1 (its saved Khoury guesses),
   v4.1 and v5.1 (benchmark/khoury2026_posthoc_v51_check.guesses) give
   Khoury's CD4 and CD8 clusters.
3. The reference (Tabula Sapiens blood; no protein label).
   - Mean log-normalised expression and detection of naive, memory and
     CD4/CD8 markers per class, under v5.1's labels.
   - The naive-CD8-like cells and the classes that hold them. A cell counts
     if CD8A or CD8B is detected, CCR7 is detected, LEF1 or SELL is
     detected, none of GZMA, GZMK, CCL5, NKG7 and GNLY is, and CD4 is not.

Writes research/notebook-outputs/cd8_cd4_diagnosis/diagnosis.json.

    python research/notebooks/cd8_cd4_diagnosis.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
from benchmark import datasets  # noqa: E402
from benchmark import khoury2026_posthoc_v51_check as check  # noqa: E402
from benchmark import khoury2026_score as protocol  # noqa: E402
from service.pipeline import fusion, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "cd8_cd4_diagnosis"
H5 = REPO.parent / "drive" / "Data" / "scRNA-seq" / "Blood_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad"
LABELS = REPO / "research" / "notebook-outputs" / "v51_labels" / "reference_labels_v51.csv.gz"
KHOURY_MARKERS = ("CD8A", "CD8B", "CD4", "CD3D", "CD3E", "CD3G", "CD247", "ZAP70", "CD2", "CD5", "CD6", "GZMA", "GZMB",
                  "GZMH", "GZMK", "GZMM", "PRF1", "NKG7", "GNLY", "CCL5", "CST7", "FCGR3A", "IL7R", "CCR7", "SELL", "LEF1",
                  "TCF7", "CD27", "CD28", "LTB", "S100A4", "ANXA1", "LCK", "IL32")
REFERENCE_MARKERS = ("S100A4", "ANXA1", "CD8A", "CD8B", "CD4", "GZMA", "GZMK", "CCL5", "CCR7", "SELL", "LEF1", "IL7R")
REFERENCE_CLASSES = {"naive CD4 T": "naive thymus-derived cd4-positive, alpha-beta t cell",
                     "CD4 T": "cd4-positive, alpha-beta t cell", "Treg": "regulatory t cell",
                     "CD8 T": "cd8-positive, alpha-beta t cell", "NK": "natural killer cell"}
SHORT = {**{v: k for k, v in REFERENCE_CLASSES.items()}, "b cell": "B", "plasma cell": "plasma"}


def obs_column(f, key):
    v = f["obs"][key]
    return v["categories"][:].astype(str)[v["codes"][:]] if isinstance(v, h5py.Group) else v[:].astype(str)


def khoury_part() -> dict:
    raw = datasets.load_khoury2026_upload()
    V = np.asarray(raw.values, dtype=float)  # proteins x cells, log2, NaN where not measured
    idx = {g.upper(): i for i, g in enumerate(raw.gene_names)}
    labels = datasets.load_khoury2026_labels(unseal=True)["label"].to_numpy()  # post-hoc use
    markers = {}
    for g in KHOURY_MARKERS:
        if g not in idx:
            markers[g] = "not in the matrix"
            continue
        x = V[idx[g]]
        r = {}
        for t in ("CD4T", "CD8T", "NK"):
            v = x[labels == t]
            r[t] = {"detected_pct": round(100 * float(np.isfinite(v).mean()), 1),
                    "mean_log2": round(float(np.nanmean(v)), 2) if np.isfinite(v).any() else None}
        a, b = x[labels == "CD8T"], x[labels == "CD4T"]
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if len(a) > 5 and len(b) > 5:
            r["cohens_d_cd8_vs_cd4"] = round(float((a.mean() - b.mean()) / np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)), 2)
        markers[g] = r
    auc = {}
    for g in ("CD8A", "S100A4", "ANXA1"):
        x = V[idx[g]]
        m = np.isin(labels, ["CD4T", "CD8T"]) & np.isfinite(x)
        auc[g] = {"auc_cd8_cluster": round(float(roc_auc_score(labels[m] == "CD8T", x[m])), 3), "cells": int(m.sum())}

    bundles = {"v4.1": fusion.V4Bundle.load(require_evaluation=False, version="v4.1"),
               "v5.1": fusion.V4Bundle.load(require_evaluation=False, version="v5.1")}
    names = np.array(bundles["v4.1"].class_names)
    smoothed, aligned, _ = pipeline._prepare_query(bundles["v4.1"].feature_genes, raw)
    src = protocol.sources(False)
    preds = {"v3.1": protocol.read_v31_table(src.out / "v31_pred.csv")["best_guess"].to_numpy()}
    for m, b in bundles.items():
        preds[m] = check.guesses(b, smoothed, aligned, names, V.shape[1])[0]
    fine = {m: {t: {SHORT.get(k, k): round(float(v), 1) for k, v in
                    pd.Series(p[labels == t]).value_counts(normalize=True).mul(100).head(6).items()}
                for t in ("CD4T", "CD8T")} for m, p in preds.items()}
    return {"cells": {t: int((labels == t).sum()) for t in ("CD4T", "CD8T", "NK")}, "markers": markers,
            "auc_cd8_cluster_vs_cd4_cluster": auc, "fine_classes_called": fine}


def reference_part() -> dict:
    lab = pd.read_csv(LABELS)
    with h5py.File(H5, "r") as f:
        free = obs_column(f, "free_annotation")
        sym = f["var"]["gene_symbol"]
        sym = sym["categories"][:].astype(str)[sym["codes"][:]] if isinstance(sym, h5py.Group) else sym[:].astype(str)
        X = sp.csr_matrix((f["X"]["data"][:], f["X"]["indices"][:], f["X"]["indptr"][:]), shape=tuple(f["X"].attrs["shape"]))
    first = {}
    for j, g in enumerate(s.upper() for s in sym):
        first.setdefault(g, j)
    genes = list(dict.fromkeys(REFERENCE_MARKERS + ("NKG7", "GNLY")))
    E = X[:, [first[g] for g in genes]].toarray()
    D = pd.DataFrame(E > 0, columns=genes)
    cls = lab["class_clean"].to_numpy()
    expression = {k: {g: {"mean": round(float(E[cls == c, genes.index(g)].mean()), 2),
                          "detected_pct": round(100 * float(D[g][cls == c].mean()), 1)} for g in REFERENCE_MARKERS}
                  for k, c in REFERENCE_CLASSES.items()}
    cd8 = D["CD8A"] | D["CD8B"]
    naive = D["CCR7"] & (D["LEF1"] | D["SELL"])
    cytotoxic = D["GZMA"] | D["GZMK"] | D["CCL5"] | D["NKG7"] | D["GNLY"]
    naive_cd8 = (cd8 & naive & ~cytotoxic & ~D["CD4"]).to_numpy()
    per_class = {k: {"cells": int((cls == c).sum()),
                     "cd8ab_detected_pct": round(100 * float(cd8[cls == c].mean()), 1),
                     "naive_cd8_like": int(naive_cd8[cls == c].sum()),
                     "cd8ab_detected_cd4_not": int((cd8 & ~D["CD4"])[cls == c].sum()),
                     "cd8ab_detected_cd4_not_naive_like": int((cd8 & ~D["CD4"] & naive)[cls == c].sum())}
                 for k, c in REFERENCE_CLASSES.items()}
    return {"expression_by_class": expression, "naive_cd8_like_cells": int(naive_cd8.sum()),
            "naive_cd8_like_by_class": {SHORT.get(k, k): int(v) for k, v in pd.Series(cls[naive_cd8]).value_counts().items()},
            "per_class": per_class,
            "free_annotation_naive": {k: int(v) for k, v in pd.Series(free).value_counts().items() if "naive" in k}}


def main() -> None:
    warnings.simplefilter("ignore")
    report = {"khoury_posthoc": khoury_part(), "reference": reference_part()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diagnosis.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"), **report}, indent=2) + "\n", newline="\n")
    k, r = report["khoury_posthoc"], report["reference"]
    print(json.dumps({"auc": k["auc_cd8_cluster_vs_cd4_cluster"], "fine": k["fine_classes_called"],
                      "naive_cd8_like": r["naive_cd8_like_cells"], "by_class": r["naive_cd8_like_by_class"],
                      "per_class": r["per_class"]}, indent=1))


if __name__ == "__main__":
    main()
