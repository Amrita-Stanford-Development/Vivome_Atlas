"""Goal 2, Phase 1.3: why SCoPE2's macrophages are called monocytes. A
diagnosis; it changes no model.

On SCoPE2 (PMA-differentiated U-937 macrophages against undifferentiated
U-937 monocytes; development data), v4.1 restricted to the two classes scores
38.0 and 33.3 balanced accuracy on the published and reprocessed matrices,
below chance, recalling 17% of macrophages and 59% of monocytes. Every
corrected baseline sits at or below chance on the reprocessed matrix. Three
questions, each answered from data before anything is decided:

1. What the reference's "macrophage" class is (Tabula Sapiens blood, 1,228
   cells): its donors, assay, the atlas's own free annotation, and marker
   RNA against the "monocyte" and "classical monocyte" classes.
2. Which proteins separate SCoPE2's macrophages from its monocytes (each
   protein's AUC, macrophage against monocyte, over cells that measure it),
   on both matrices.
3. Whether the reference RNA differs the same way: for every gene in both,
   the class-balanced difference between the reference's macrophage class
   and its two monocyte classes, against SCoPE2's protein difference
   (Spearman over shared genes, and sign agreement among the 50 strongest
   protein differences); and the correlation term's own lean, each SCoPE2
   cell's correlation with the macrophage class mean minus the monocyte
   class mean, by true label.

Outcome, decided by the findings and stated with them: keep classifying
cell-line macrophages, or treat them as outside the reference (abstain).

Writes research/notebook-outputs/mac_mono_diagnosis/diagnosis.json and
protein_vs_rna.csv.

    python research/notebooks/mac_mono_diagnosis.py      # from the repository root
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from benchmark import baselines_v31, datasets  # noqa: E402
from service.pipeline import alignment, fusion  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "mac_mono_diagnosis"
H5 = REPO.parent / "drive" / "Data" / "scRNA-seq" / "Blood_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad"
RUNTIME = REPO / "service" / "model" / "runtime"
MARKERS = ("CD68", "CD163", "MRC1", "MARCO", "APOE", "C1QA", "C1QB", "SPP1", "CD14", "FCGR3A", "LYZ", "S100A8",
           "S100A9", "VCAN", "FCN1", "CSF1R", "ITGAM", "CD36", "HLA-DRA", "CD74", "MKI67", "TOP2A", "HBB", "PPBP")
MONO = ("monocyte", "classical monocyte")


def obs_column(f, key):
    v = f["obs"][key]
    return v["categories"][:].astype(str)[v["codes"][:]] if isinstance(v, h5py.Group) else v[:].astype(str)


def reference() -> tuple[dict, pd.Series]:
    """Part 1, and the reference's class-balanced macrophage-minus-monocyte
    difference per gene (Part 3's RNA side)."""
    meta = pd.read_csv(RUNTIME / "reference_metadata.csv")
    with h5py.File(H5, "r") as f:
        ids = f["obs"][f["obs"].attrs["_index"]][:].astype(str)
        onto, free = obs_column(f, "cell_ontology_class"), obs_column(f, "free_annotation")
        donor, method = obs_column(f, "donor"), obs_column(f, "method")
        sym = f["var"]["gene_symbol"]
        sym = sym["categories"][:].astype(str)[sym["codes"][:]] if isinstance(sym, h5py.Group) else sym[:].astype(str)
        X = sp.csr_matrix((f["X"]["data"][:], f["X"]["indices"][:], f["X"]["indptr"][:]), shape=tuple(f["X"].attrs["shape"]))
    if list(ids) != meta["cell"].tolist() or list(onto) != meta["class_name"].tolist():
        raise SystemExit("the h5ad's cells or labels are not reference_metadata.csv's")
    mac, mono = onto == "macrophage", np.isin(onto, MONO)
    part1 = {"macrophage_cells": int(mac.sum()),
             "free_annotation": pd.Series(free[mac]).value_counts().head(10).to_dict(),
             "donors": pd.Series(donor[mac]).value_counts().to_dict(),
             "donors_of_monocytes": pd.Series(donor[mono]).value_counts().to_dict(),
             "method": pd.Series(method[mac]).value_counts().to_dict()}
    first = {}
    for j, s in enumerate(sym):
        first.setdefault(s.upper(), j)
    groups = {"macrophage": mac, "monocyte": onto == "monocyte", "classical monocyte": onto == "classical monocyte"}
    markers = {}
    for m in MARKERS:
        if m in first:
            e = X[:, first[m]].toarray().ravel()
            markers[m] = {g: {"detected_pct": round(100 * float((e[c] > 0).mean()), 1),
                              "mean": round(float(e[c].mean()), 3)} for g, c in groups.items()}
    part1["markers"] = markers
    # Class-balanced difference per gene: macrophage mean minus the mean of the two monocyte classes' means.
    cols = sorted(set(first.values()))
    names = {j: s for s, j in first.items()}
    Xc = X[:, cols].tocsc()
    mean = lambda rows: np.asarray(Xc[rows].mean(axis=0)).ravel()  # noqa: E731
    diff = mean(mac) - (mean(onto == "monocyte") + mean(onto == "classical monocyte")) / 2
    return part1, pd.Series(diff, index=[names[j] for j in cols])


def protein_auc(raw: alignment.RawMatrix, labels: np.ndarray, min_cells: int = 20) -> pd.DataFrame:
    """Each protein's AUC, macrophage against monocyte, over cells that
    measure it (log scale as the service detects it)."""
    values, _ = alignment.detect_and_transform_value_scale(raw.values)
    rows = []
    mac = labels == "macrophage"
    for i, name in enumerate(raw.gene_names):
        v = values[i]
        ok = np.isfinite(v)
        if ok.sum() < min_cells or len(set(labels[ok])) < 2:
            continue
        rows.append({"gene": fusion.first_symbol(name), "n": int(ok.sum()),
                     "auc_macrophage": roc_auc_score(mac[ok], v[ok])})
    return pd.DataFrame(rows).groupby("gene", as_index=False).first()


def lean(raw: alignment.RawMatrix, labels: np.ndarray) -> dict:
    """The correlation term's lean: r(macrophage mean) - r(monocyte mean), v4.1's RNA class means."""
    feature_genes = pd.read_csv(RUNTIME / "feature_space_genes.csv")["gene"].str.upper().tolist()
    names = (pd.read_csv(RUNTIME / "reference_metadata.csv").drop_duplicates("class_idx")
             .sort_values("class_idx")["class_name"].tolist())
    means = np.load(REPO / "service" / "model" / "v4" / "class_means_cb.npy")
    v, m = fusion.protein_query(raw, feature_genes)
    r = fusion.masked_pearson(v, m, means)
    d = r[:, names.index("macrophage")] - r[:, names.index("monocyte")]
    return {lab: round(float(np.median(d[labels == lab])), 4) for lab in ("macrophage", "monocyte")}


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    part1, rna_diff = reference()
    sets = {"published": (baselines_v31.scope2_raw(),
                          pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")["class_name"].to_numpy()),
            "reprocessed": (datasets.load_scope2_reprocessed_upload(),
                            datasets.load_scope2_reprocessed_labels()["label"].to_numpy())}
    out, tables = {"reference": part1}, []
    for name, (raw, labels) in sets.items():
        auc = protein_auc(raw, labels)
        auc["rna_diff"] = auc["gene"].map(rna_diff)
        shared = auc.dropna(subset=["rna_diff"])
        top = shared.reindex((shared["auc_macrophage"] - 0.5).abs().sort_values(ascending=False).index).head(50)
        rho = spearmanr(shared["auc_macrophage"] - 0.5, shared["rna_diff"]).correlation
        agree = float(((top["auc_macrophage"] > 0.5) == (top["rna_diff"] > 0)).mean())
        out[name] = {"proteins_scored": int(len(auc)), "shared_with_reference": int(len(shared)),
                     "spearman_protein_vs_rna": round(float(rho), 3),
                     "sign_agreement_top50": round(agree, 3),
                     "top_up_in_macrophages": shared.nlargest(12, "auc_macrophage")[["gene", "auc_macrophage", "rna_diff"]]
                     .round(3).to_dict("records"),
                     "top_down_in_macrophages": shared.nsmallest(12, "auc_macrophage")[["gene", "auc_macrophage", "rna_diff"]]
                     .round(3).to_dict("records"),
                     "correlation_term_lean_median": lean(raw, labels)}
        tables.append(auc.assign(matrix=name))
    (OUT / "diagnosis.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    pd.concat(tables).round(4).to_csv(OUT / "protein_vs_rna.csv", index=False, lineterminator="\n")
    print(json.dumps({k: v for k, v in out.items() if k != "reference"}, indent=1)[:4000])
    print(json.dumps({k: part1[k] for k in ("macrophage_cells", "free_annotation", "donors", "method")}, indent=1))


if __name__ == "__main__":
    main()
