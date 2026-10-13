"""v5.2 (research/todo.md, Track H): naive CD8 T cells given a home in the
reference, using Hao et al. 2021's labels.

Why: research/notebooks/cd8_cd4_diagnosis.py (run-history entry 28) found
that Tabula Sapiens files naive CD8 T cells under CD4 T. Of 356
naive-CD8-like cells, 320 are labelled CD4 T, and free_annotation names only
6 naive CD8 T. Every model then calls naive CD8 T cells CD4. Hao et al. 2021
(Cell 184:3573; GEO GSE164378) labelled 161,764 PBMCs from 8 donors using
RNA and a 228-antibody surface panel. Its celltype.l2 separates CD8 Naive,
TCM and TEM from CD4 Naive, TCM, TEM and CTL. The owner chose (2026-10-13) to
relabel Tabula Sapiens with a classifier trained on Hao, keeping our 22
classes. No protein MS label is read.

Rules, fixed before the first run:

- Hao training cells (3' data; GSM5008737 and its metadata), celltype.l2
  mapped to five targets:
  - naive CD4 T: CD4 Naive;
  - CD4 T: CD4 TCM, CD4 TEM, CD4 CTL;
  - Treg: Treg;
  - CD8 T: CD8 Naive, CD8 TCM, CD8 TEM;
  - NK: NK, NK_CD56bright.
  Every other Hao cell (MAIT, gamma-delta T, dnT, proliferating, ILC, B,
  myeloid, doublets) is left out.
- Features: genes in both Hao and Tabula Sapiens. The classifier uses the
  2,000 most variable by dispersion (variance over mean of log-normalised
  values, among genes with mean at least 0.01 on the training cells), plus
  these markers wherever present: CD8A, CD8B, CD4, CD3D, CD3E, CCR7, SELL,
  LEF1, TCF7, IL7R, GZMA, GZMB, GZMH, GZMK, CCL5, NKG7, GNLY, KLRB1, FOXP3,
  IL2RA, CD27, CD28, S100A4, ANXA1.
- Values: log1p(counts / total counts x 10,000) for Hao (nCount_RNA as the
  total); Tabula Sapiens's X, already log-normalised (checked). Each gene
  is z-scored with the Hao training cells' mean and SD, clipped at +-10.
- Classifier: multinomial logistic regression (scikit-learn, C 0.1,
  class_weight balanced, max_iter 2,000).
- Gate, on Hao's held-out donors (train on P1-P6, test on P7 and P8), before
  any Tabula Sapiens cell is relabelled (0.9 below is 0.95 since the
  amendment):
  - among held-out CD4-lineage cells (naive CD4 T, CD4 T, Treg), at most 1%
    may get P(CD8 T) >= 0.9;
  - among held-out CD8 T cells, at most 1% may get P(CD4 lineage) >= 0.9.
  Otherwise the run stops and nothing is relabelled. The final classifier is
  then trained on all eight donors.
- Relabelling, of Tabula Sapiens cells under v5.1's labels
  (research/notebook-outputs/v51_labels/reference_labels_v51.csv.gz),
  between the CD4 and CD8 lineages only:
  - a cell labelled CD4 T or naive CD4 T with P(CD8 T) >= 0.9 becomes CD8 T;
  - a cell labelled CD8 T with P(CD4 lineage) >= 0.9 becomes naive CD4 T if
    P(naive CD4 T) >= P(CD4 T), else CD4 T. P(CD4 lineage) is P(naive CD4
    T) + P(CD4 T) + P(Treg).
  Everything else keeps its v5.1 label: naive against memory CD4, Treg, NK
  and every other class. The 22 classes and their order stay.
- Reported only, never used to change the rules:
  - marker detection in moved and kept cells;
  - the overlap with the diagnosis's 356 naive-CD8-like cells;
  - moves by assay and donor;
  - the classifier's full call on every Tabula Sapiens T and NK cell.

Amendment (2026-10-13, the owner's decision, after the first run's gate and
before anything was relabelled). The first run, at P >= 0.9, failed the
gate by 0.004 points:
- held-out CD4-lineage cells called CD8 T: 1.004% (bound 1%);
- CD8 T cells called CD4 lineage: 0.998%.
Both are about the noise level of Hao's own CD4/CD8 labels. The threshold
for the gate and for every move is now 0.95. That is stricter, so it moves
fewer cells; the 1% bound is unchanged. audit.json records the first run's
gate as first_run_gate.

Writes research/notebook-outputs/v52_labels/reference_labels_v52.csv.gz (the
v5.1 table's columns, updated, with p_cd8 and p_cd4_lineage added) and
audit.json. Hao's filtered counts are cached in data/incoming/Hao2021/.

    python research/notebooks/v52_labels.py      # from the repository root
"""
from __future__ import annotations

import gzip
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.linear_model import LogisticRegression

REPO = Path(__file__).resolve().parents[2]
HAO = REPO / "data" / "incoming" / "Hao2021"
H5 = REPO.parent / "drive" / "Data" / "scRNA-seq" / "Blood_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad"
V51 = REPO / "research" / "notebook-outputs" / "v51_labels" / "reference_labels_v51.csv.gz"
OUT = REPO / "research" / "notebook-outputs" / "v52_labels"
NAIVE4, CD4, TREG, CD8, NK = ("naive thymus-derived cd4-positive, alpha-beta t cell", "cd4-positive, alpha-beta t cell",
                              "regulatory t cell", "cd8-positive, alpha-beta t cell", "natural killer cell")
TARGET = {"CD4 Naive": NAIVE4, "CD4 TCM": CD4, "CD4 TEM": CD4, "CD4 CTL": CD4, "Treg": TREG,
          "CD8 Naive": CD8, "CD8 TCM": CD8, "CD8 TEM": CD8, "NK": NK, "NK_CD56bright": NK}
CLASSES = (NAIVE4, CD4, TREG, CD8, NK)
MARKERS = ("CD8A", "CD8B", "CD4", "CD3D", "CD3E", "CCR7", "SELL", "LEF1", "TCF7", "IL7R", "GZMA", "GZMB", "GZMH", "GZMK",
           "CCL5", "NKG7", "GNLY", "KLRB1", "FOXP3", "IL2RA", "CD27", "CD28", "S100A4", "ANXA1")
N_HVG, MIN_MEAN, C, THRESHOLD, GATE = 2000, 0.01, 0.1, 0.95, 1.0  # THRESHOLD was 0.9 (the amendment above)
FIRST_RUN_GATE = {"threshold": 0.9, "cd4_lineage_to_cd8_pct": 1.004, "cd8_to_cd4_lineage_pct": 0.998, "passed": False}
TRAIN_DONORS, TEST_DONORS = ("P1", "P2", "P3", "P4", "P5", "P6"), ("P7", "P8")
CACHE = HAO / "hao_tnk_counts.npz"


def hao_counts(meta: pd.DataFrame) -> tuple[sp.csr_matrix, list[str]]:
    """The training cells' raw counts (cells x all genes), streamed from the
    3' matrix (genes x barcodes, 1-based), cached after the first read."""
    genes = pd.read_csv(HAO / "GSM5008737_RNA_3P-features.tsv.gz", sep="\t", header=None)[1].astype(str).str.upper().tolist()
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=True)  # this script's own cache; the first run saved barcodes as objects
        if z["barcodes"].tolist() != meta.index.tolist():
            raise SystemExit(f"{CACHE} is for other cells: delete it")
        return sp.csr_matrix((z["data"], z["indices"], z["indptr"]), shape=tuple(z["shape"])), genes
    barcodes = pd.read_csv(HAO / "GSM5008737_RNA_3P-barcodes.tsv.gz", header=None)[0].tolist()
    pos = {b: i for i, b in enumerate(barcodes)}
    keep_col = np.full(len(barcodes) + 1, -1, np.int64)  # 1-based barcode -> row in meta, or -1
    for r, b in enumerate(meta.index):
        keep_col[pos[b] + 1] = r
    rows, cols, vals = [], [], []
    t0 = time.time()
    with gzip.open(HAO / "GSM5008737_RNA_3P-matrix.mtx.gz", "rt") as fh:
        line = fh.readline()
        while line.startswith("%"):
            line = fh.readline()
        n_genes, n_cells, nnz = map(int, line.split())
        if (n_genes, n_cells) != (len(genes), len(barcodes)):
            raise SystemExit("the matrix's shape is not its features' and barcodes'")
        for chunk in pd.read_csv(fh, sep=" ", header=None, names=["g", "c", "v"], dtype={"g": np.int32, "c": np.int32,
                                 "v": np.float32}, chunksize=25_000_000, engine="c"):
            r = keep_col[chunk["c"].to_numpy()]
            m = r >= 0
            rows.append(r[m].astype(np.int32))
            cols.append(chunk["g"].to_numpy()[m] - 1)
            vals.append(chunk["v"].to_numpy()[m])
            print(f"  read {sum(len(x) for x in rows):,} kept entries ({time.time() - t0:.0f}s)", flush=True)
    X = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(len(meta), len(genes)))
    np.savez(CACHE, data=X.data, indices=X.indices, indptr=X.indptr, shape=np.array(X.shape),
             barcodes=np.array(meta.index, dtype=str))
    return X, genes


def obs_column(f, key):
    v = f["obs"][key]
    return v["categories"][:].astype(str)[v["codes"][:]] if isinstance(v, h5py.Group) else v[:].astype(str)


def main() -> None:
    t0 = time.time()
    meta = pd.read_csv(HAO / "GSE164378_sc.meta.data_3P.csv.gz", index_col=0)
    meta = meta[meta["celltype.l2"].isin(TARGET)]
    target = meta["celltype.l2"].map(TARGET).to_numpy()
    counts, hao_genes = hao_counts(meta)
    print(f"Hao training cells {counts.shape[0]:,} x {counts.shape[1]:,} genes ({time.time() - t0:.0f}s)", flush=True)

    with h5py.File(H5, "r") as f:
        ids = f["obs"][f["obs"].attrs["_index"]][:].astype(str)
        method, donor = obs_column(f, "method"), obs_column(f, "donor")
        sym = f["var"]["gene_symbol"]
        sym = sym["categories"][:].astype(str)[sym["codes"][:]] if isinstance(sym, h5py.Group) else sym[:].astype(str)
        TS = sp.csr_matrix((f["X"]["data"][:], f["X"]["indices"][:], f["X"]["indptr"][:]), shape=tuple(f["X"].attrs["shape"]))
    lab = pd.read_csv(V51, keep_default_na=False)
    if lab["cell"].tolist() != list(ids):
        raise SystemExit(f"{V51} is not in the h5ad's order")
    ten = np.flatnonzero(method == "10X")[:200]
    sums = np.asarray(np.expm1(TS[ten]).sum(1)).ravel()
    if not np.allclose(np.median(sums), 1e4, rtol=0.05):
        raise SystemExit(f"Tabula Sapiens's X is not log1p(CP10k): median 10X row sum {np.median(sums):.0f}")

    ts_first, hao_first = {}, {}
    for j, g in enumerate(s.upper() for s in sym):
        ts_first.setdefault(g, j)
    for j, g in enumerate(hao_genes):
        hao_first.setdefault(g, j)
    shared = [g for g in hao_first if g in ts_first]
    H = counts[:, [hao_first[g] for g in shared]].tocsr().astype(np.float64)
    H = sp.diags(1e4 / meta["nCount_RNA"].to_numpy()) @ H
    H.data = np.log1p(H.data)
    mean = np.asarray(H.mean(0)).ravel()
    var = np.asarray(H.multiply(H).mean(0)).ravel() - mean ** 2
    disp = np.where(mean >= MIN_MEAN, var / np.maximum(mean, 1e-12), -np.inf)
    chosen = set(np.argsort(-disp)[:N_HVG].tolist()) | {shared.index(g) for g in MARKERS if g in shared}
    chosen = sorted(chosen)
    genes = [shared[i] for i in chosen]
    mu, sd = mean[chosen], np.sqrt(np.maximum(var[chosen], 1e-12))
    Xh = np.clip((H[:, chosen].toarray() - mu) / sd, -10, 10).astype(np.float32)
    print(f"{len(genes)} features ({len(set(MARKERS) & set(genes))} markers) ({time.time() - t0:.0f}s)", flush=True)

    def model():
        return LogisticRegression(C=C, class_weight="balanced", max_iter=2000)

    # the gate, on held-out donors
    tr, te = meta["donor"].isin(TRAIN_DONORS).to_numpy(), meta["donor"].isin(TEST_DONORS).to_numpy()
    clf = model().fit(Xh[tr], target[tr])
    P = clf.predict_proba(Xh[te])
    col = {c: list(clf.classes_).index(c) for c in CLASSES}
    p_cd8, p_cd4 = P[:, col[CD8]], P[:, col[NAIVE4]] + P[:, col[CD4]] + P[:, col[TREG]]
    held = target[te]
    cd4_lineage = np.isin(held, [NAIVE4, CD4, TREG])
    false_to_cd8 = 100 * float((p_cd8[cd4_lineage] >= THRESHOLD).mean())
    false_to_cd4 = 100 * float((p_cd4[held == CD8] >= THRESHOLD).mean())
    pred = clf.classes_[P.argmax(1)]
    naive_cd8 = (meta["celltype.l2"].to_numpy()[te] == "CD8 Naive")
    gate = {"held_out_donors": list(TEST_DONORS), "cells": int(te.sum()),
            "cd4_lineage_to_cd8_pct": round(false_to_cd8, 3), "cd8_to_cd4_lineage_pct": round(false_to_cd4, 3),
            "bound_pct": GATE, "recall_argmax": {c: round(100 * float((pred[held == c] == c).mean()), 2) for c in CLASSES},
            "naive_cd8_confident_pct": round(100 * float((p_cd8[naive_cd8] >= THRESHOLD).mean()), 2),
            "passed": bool(false_to_cd8 <= GATE and false_to_cd4 <= GATE)}
    print(json.dumps(gate, indent=1), flush=True)
    if not gate["passed"]:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "audit.json").write_text(json.dumps({"script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                    "gate": gate, "first_run_gate": FIRST_RUN_GATE, "relabelled": None}, indent=2) + "\n", newline="\n")
        raise SystemExit("STOP: the gate failed; nothing relabelled")

    # the final classifier on all donors, applied to Tabula Sapiens's T and NK cells
    clf = model().fit(Xh, target)
    col = {c: list(clf.classes_).index(c) for c in CLASSES}
    cls = lab["class_clean"].to_numpy()
    tnk = np.flatnonzero(np.isin(cls, [NAIVE4, CD4, TREG, CD8, NK]))
    T = TS[tnk][:, [ts_first[g] for g in genes]].toarray()
    Pt = clf.predict_proba(np.clip((T - mu) / sd, -10, 10).astype(np.float32))
    p8 = np.full(len(cls), np.nan)
    p4 = np.full(len(cls), np.nan)
    p8[tnk] = Pt[:, col[CD8]]
    p4[tnk] = Pt[:, col[NAIVE4]] + Pt[:, col[CD4]] + Pt[:, col[TREG]]
    pn = np.full(len(cls), np.nan)
    pm = np.full(len(cls), np.nan)
    pn[tnk], pm[tnk] = Pt[:, col[NAIVE4]], Pt[:, col[CD4]]
    new = cls.copy()
    to_cd8 = np.isin(cls, [CD4, NAIVE4]) & (p8 >= THRESHOLD)
    to_cd4 = (cls == CD8) & (p4 >= THRESHOLD)
    new[to_cd8] = CD8
    new[to_cd4] = np.where(pn[to_cd4] >= pm[to_cd4], NAIVE4, CD4)
    names = lab.drop_duplicates("class_idx_clean").set_index("class_clean")["class_idx_clean"].to_dict()
    out = lab.copy()
    changed = new != cls
    out["class_clean"] = new
    out["class_idx_clean"] = [names[c] for c in new]
    out.loc[changed, "reason"] = [f"{r}; v5.2: Hao 2021 classifier" if r else "v5.2: Hao 2021 classifier"
                                  for r in out.loc[changed, "reason"]]
    out["p_cd8"], out["p_cd4_lineage"] = np.round(p8, 4), np.round(p4, 4)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "reference_labels_v52.csv.gz"
    out.to_csv(path, index=False, lineterminator="\n", compression={"method": "gzip", "mtime": 0})

    # reported only
    mk =[g for g in ("CD8A", "CD8B", "CD4", "CCR7", "SELL", "LEF1", "GZMA", "CCL5", "S100A4", "ANXA1") if g in ts_first]
    E = TS[:, [ts_first[g] for g in mk]].toarray() > 0
    D = pd.DataFrame(E, columns=mk)
    naive_like = ((D["CD8A"] | D["CD8B"]) & D["CCR7"] & (D["LEF1"] | D["SELL"]) & ~D["GZMA"] & ~D["CCL5"] & ~D["CD4"]).to_numpy()

    def detection(mask):
        return {g: round(100 * float(D[g][mask].mean()), 1) for g in mk} if mask.any() else None
    full_call = pd.crosstab(pd.Series(cls[tnk], name="v5.1 label"), pd.Series(clf.classes_[Pt.argmax(1)], name="Hao call"))
    audit = {
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"),
        "hao": {"cells": int(len(meta)), "by_target": {k: int(v) for k, v in pd.Series(target).value_counts().items()},
                "features": len(genes), "markers_used": [g for g in MARKERS if g in genes]},
        "gate": gate, "first_run_gate": FIRST_RUN_GATE, "labels_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "moved": {"cd4_to_cd8": int(to_cd8.sum()), "cd8_to_cd4_lineage": int(to_cd4.sum()),
                  "cd4_to_cd8_from": {k: int(v) for k, v in pd.Series(cls[to_cd8]).value_counts().items()},
                  "cd8_to": {k: int(v) for k, v in pd.Series(new[to_cd4]).value_counts().items()},
                  "by_method": {k: int(v) for k, v in pd.Series(method[changed]).value_counts().items()},
                  "by_donor": {k: int(v) for k, v in pd.Series(donor[changed]).value_counts().items()}},
        "class_counts": {c: {"v5.1": int((cls == c).sum()), "v5.2": int((new == c).sum())} for c in CLASSES},
        "naive_cd8_like_moved": {"cells": int(naive_like.sum()), "moved_to_cd8": int((naive_like & to_cd8).sum()),
                                 "already_cd8": int((naive_like & (cls == CD8)).sum())},
        "marker_detection_pct": {"moved_to_cd8": detection(to_cd8), "moved_to_cd4": detection(to_cd4),
                                 "kept_cd4": detection(np.isin(new, [CD4]) & ~to_cd4),
                                 "kept_cd8": detection((new == CD8) & ~to_cd8)},
        "full_call_tnk": {r: {c: int(full_call.loc[r, c]) for c in full_call.columns} for r in full_call.index},
        "seconds": round(time.time() - t0),
    }
    (OUT / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", newline="\n")
    print(json.dumps({k: audit[k] for k in ("moved", "class_counts", "naive_cd8_like_moved", "marker_detection_pct")}, indent=1))


if __name__ == "__main__":
    main()
