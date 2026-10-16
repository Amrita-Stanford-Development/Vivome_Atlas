"""Hao et al. 2021 (Cell 184:3573; GEO GSE164378, the 3' data) in the
reference's 9,002-gene input space, for Goal 2's dendritic-cell work and the
Hao held-out suite (research/benchmark/side-tests.md, amendment 1).

Roles: donors P1-P4 (Hao's Batch1) are development; donors P5-P8 (Batch2)
are the held-out suite, except their T and NK cells, which built v5.2's
labels and are development everywhere. load() reads only the donors it is
given; nothing here reads P5-P8 unless asked to by name.

- Genes: Hao's symbols resolved to feature-space symbols by the service's own
  gene map (gene_ids.resolve_to_feature_symbols), as an upload's would be;
  where several Hao genes resolve to one feature gene, their counts add.
- Values: log1p(counts / nCount_RNA x 10,000), the convention of the
  reference's RNA (research/notebooks/v52_labels.py checked it on Tabula
  Sapiens); feature genes Hao lacks stay 0.
- Labels: celltype.l2 mapped to reference classes (L2_TO_CLASS); the types
  the plan excludes map to None.

The first load() of a donor set streams the 1.1 GB count matrix and caches
the set's feature-space counts in data/incoming/Hao2021/ (gitignored).
"""
from __future__ import annotations

import gzip
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from service.pipeline import gene_ids, reference  # noqa: E402

HAO = REPO / "data" / "incoming" / "Hao2021"
DEVELOPMENT_DONORS = ("P1", "P2", "P3", "P4")
HELD_OUT_DONORS = ("P5", "P6", "P7", "P8")
TNK = ("CD4 Naive", "CD4 TCM", "CD4 TEM", "CD4 CTL", "Treg", "CD8 Naive", "CD8 TCM", "CD8 TEM", "NK", "NK_CD56bright")
L2_TO_CLASS = {
    "B naive": "b cell", "B intermediate": "b cell", "B memory": "b cell", "Plasmablast": "plasma cell",
    "CD14 Mono": "classical monocyte", "CD16 Mono": "non-classical monocyte",
    "cDC1": "myeloid dendritic cell", "cDC2": "myeloid dendritic cell", "pDC": "plasmacytoid dendritic cell",
    "HSPC": "hematopoietic precursor cell", "Platelet": "platelet", "Eryth": "erythrocyte",
    "CD4 Naive": "naive thymus-derived cd4-positive, alpha-beta t cell", "CD4 TCM": "cd4-positive, alpha-beta t cell",
    "CD4 TEM": "cd4-positive, alpha-beta t cell", "CD4 CTL": "cd4-positive, alpha-beta t cell", "Treg": "regulatory t cell",
    "CD8 Naive": "cd8-positive, alpha-beta t cell", "CD8 TCM": "cd8-positive, alpha-beta t cell",
    "CD8 TEM": "cd8-positive, alpha-beta t cell", "NK": "natural killer cell", "NK_CD56bright": "natural killer cell",
}  # ASDC, MAIT, gdT, dnT, ILC, the proliferating types and doublets: excluded (None)


def metadata(donors: tuple[str, ...]) -> pd.DataFrame:
    meta = pd.read_csv(HAO / "GSE164378_sc.meta.data_3P.csv.gz", index_col=0)
    meta = meta[meta["donor"].isin(donors)].copy()
    meta["class_name"] = meta["celltype.l2"].map(L2_TO_CLASS)
    return meta


def _feature_columns(feature_genes: list[str]) -> tuple[np.ndarray, int]:
    """For each Hao gene, its feature-space column or -1."""
    symbols = pd.read_csv(HAO / "GSM5008737_RNA_3P-features.tsv.gz", sep="\t", header=None)[1].astype(str).tolist()
    index = {g: i for i, g in enumerate(feature_genes)}
    resolved = gene_ids.resolve_to_feature_symbols(symbols)
    cols = np.array([index.get(s, -1) if s is not None else -1 for s in resolved], dtype=np.int64)
    return cols, len(symbols)


def _stream(meta: pd.DataFrame, cols: np.ndarray, n_genes: int, n_features: int) -> sp.csr_matrix:
    barcodes = pd.read_csv(HAO / "GSM5008737_RNA_3P-barcodes.tsv.gz", header=None)[0].tolist()
    pos = {b: i for i, b in enumerate(barcodes)}
    keep = np.full(len(barcodes) + 1, -1, np.int64)  # 1-based barcode -> row in meta, or -1
    for r, b in enumerate(meta.index):
        keep[pos[b] + 1] = r
    gene_col = np.r_[-1, cols]  # 1-based gene -> feature column, or -1
    rows, out_cols, vals = [], [], []
    t0 = time.time()
    with gzip.open(HAO / "GSM5008737_RNA_3P-matrix.mtx.gz", "rt") as fh:
        line = fh.readline()
        while line.startswith("%"):
            line = fh.readline()
        shape = tuple(map(int, line.split()))
        if shape[:2] != (n_genes, len(barcodes)):
            raise SystemExit("the matrix's shape is not its features' and barcodes'")
        for chunk in pd.read_csv(fh, sep=" ", header=None, names=["g", "c", "v"], chunksize=25_000_000, engine="c",
                                 dtype={"g": np.int32, "c": np.int32, "v": np.float32}):
            r = keep[chunk["c"].to_numpy()]
            c = gene_col[chunk["g"].to_numpy()]
            m = (r >= 0) & (c >= 0)
            rows.append(r[m].astype(np.int32))
            out_cols.append(c[m].astype(np.int32))
            vals.append(chunk["v"].to_numpy()[m])
            print(f"  Hao: {sum(len(x) for x in rows):,} kept entries ({time.time() - t0:.0f}s)", flush=True)
    X = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(out_cols))),
                      shape=(len(meta), n_features)).tocsr()  # duplicates (several genes, one feature) add
    X.sum_duplicates()
    return X


def load(donors: tuple[str, ...], cache_name: str) -> tuple[sp.csr_matrix, pd.DataFrame, list[str]]:
    """(log-normalised cells x feature genes as CSR float32, the cells' metadata with class_name, feature genes)."""
    feature_genes = reference.load_feature_space_genes()
    meta = metadata(donors)
    cache = HAO / cache_name
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        if z["barcodes"].tolist() != meta.index.astype(str).tolist():
            raise SystemExit(f"{cache} is for other cells: delete it")
        counts = sp.csr_matrix((z["data"], z["indices"], z["indptr"]), shape=tuple(z["shape"]))
    else:
        cols, n_genes = _feature_columns(feature_genes)
        counts = _stream(meta, cols, n_genes, len(feature_genes))
        np.savez(cache, data=counts.data, indices=counts.indices, indptr=counts.indptr, shape=np.array(counts.shape),
                 barcodes=np.array(meta.index.astype(str).tolist()))
    total = meta["nCount_RNA"].to_numpy(dtype=np.float64)
    X = sp.diags(1e4 / total) @ counts.astype(np.float64)
    X.data = np.log1p(X.data)
    return X.astype(np.float32).tocsr(), meta, feature_genes
