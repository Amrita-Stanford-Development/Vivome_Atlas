"""scANVI on Fulcher 2026, the held-out TMT PBMC dataset. The setup is fixed
by research/benchmark/protocol-fulcher2026.md.

The architecture and training are copied unchanged from scanvi_run_pbmc240.py.
Only the query side differs: the 1,275 QC-passed Fulcher cells, loaded through
datasets.load_fulcher2026_upload() (hash-checked, and unable to return
labels), in one of two input variants:

- "log2": log2 of the observed linear TMT intensities.
- "log2_cellmedian": the same, minus each cell's median over its observed
  proteins in the full 1,661-protein table.

Both variants are then reduced to load.py's shared gene space
(results/gene_cols.txt; 932 of its 2,907 genes are present in Fulcher),
z-scored per gene over observed values, and unobserved entries are set to 0.
This is the same final treatment the PBMC240 arm uses.

This script never reads a label. It saves embeddings and predicted reference
classes, from scANVI's native classifier and from the shared kNN rule, to
results/fulcher2026/. All scoring happens in fulcher2026_score.py.

    python3 benchmark/scanvi_run_fulcher2026.py SEED VARIANT   # SEED in 0,1,2; VARIANT log2 | log2_cellmedian

Each run is roughly an hour of CPU training. The outputs are gitignored but
not disposable (see .gitignore).
"""
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anndata as ad
import numpy as np
import pandas as pd
import scvi
import torch
from scvi.model import SCANVI, SCVI

import datasets
from evaluate import KNN_K
from sklearn.neighbors import KNeighborsClassifier

D = Path(__file__).resolve().parent / "results"
OUT = D / "fulcher2026"
VARIANTS = ("log2", "log2_cellmedian")

SEED = int(sys.argv[1])
VARIANT = sys.argv[2]
assert VARIANT in VARIANTS, f"unknown variant {VARIANT!r}, expected one of {VARIANTS}"
scvi.settings.seed = SEED
torch.manual_seed(SEED)
np.random.seed(SEED)
OUT.mkdir(parents=True, exist_ok=True)
t0 = time.time()


def query_matrix(variant: str) -> tuple[np.ndarray, list[str]]:
    raw = datasets.load_fulcher2026_upload()  # genes x cells, linear, NaN = missing
    assert np.nanmin(raw.values) > 0, "log2 needs positive intensities"
    logx = np.log2(raw.values.astype(np.float64))
    if variant == "log2_cellmedian":
        logx = logx - np.nanmedian(logx, axis=0, keepdims=True)  # per cell (column)
    df = pd.DataFrame(logx.T, index=raw.cell_ids, columns=[g.upper() for g in raw.gene_names])
    shared_genes = [line.strip()[len("gene_"):] for line in open(D / "gene_cols.txt")]
    return df.reindex(columns=shared_genes).to_numpy(dtype=np.float32), raw.cell_ids


def zscore_cols(X, eps=1e-8):
    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    return (X - mean) / np.clip(std, eps, None)


def zscore_cols_nan_aware(X, eps=1e-8):
    mean = np.nanmean(X, axis=0, keepdims=True)
    std = np.nanstd(X, axis=0, keepdims=True)
    return np.nan_to_num((X - mean) / np.clip(std, eps, None), nan=0.0)


rna_X = np.load(D / "rna_X.npy")
rna_labels = pd.read_csv(D / "rna_meta.csv")["class_name"].to_numpy()
query_X, cell_ids = query_matrix(VARIANT)
print(f"variant={VARIANT} seed={SEED} RNA cells {len(rna_labels)}, Fulcher cells {len(cell_ids)}, "
      f"{int(np.isfinite(query_X).any(axis=0).sum())} shared genes observed. {time.time()-t0:.1f}s", flush=True)

with warnings.catch_warnings():
    # Degenerate all-NaN shared-gene columns warn in nanmean/nanstd; they become 0.
    warnings.simplefilter("ignore", RuntimeWarning)
    query_Z = zscore_cols_nan_aware(query_X).astype(np.float32)
rna_Z = zscore_cols(rna_X).astype(np.float32)

adata = ad.AnnData(X=np.vstack([rna_Z, query_Z]).astype(np.float32))
adata.obs["modality"] = ["RNA"] * len(rna_Z) + ["Protein"] * len(query_Z)
adata.obs["cell_type"] = pd.Categorical(list(rna_labels) + ["Unknown"] * len(query_Z))
adata.obs["size_factor"] = 1.0

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    SCVI.setup_anndata(adata, batch_key="modality", labels_key="cell_type", size_factor_key="size_factor")
    scvi_model = SCVI(adata, n_latent=30, n_layers=2, n_hidden=128, gene_likelihood="normal", log_variational=False)
    scvi_model.train(max_epochs=200, early_stopping=True, early_stopping_patience=15)
    print(f"SCVI pretrain done. {time.time()-t0:.1f}s", flush=True)
    scanvi_model = SCANVI.from_scvi_model(scvi_model, unlabeled_category="Unknown", labels_key="cell_type")
    scanvi_model.train(max_epochs=100, early_stopping=True, early_stopping_patience=15)
    print(f"SCANVI train done. {time.time()-t0:.1f}s", flush=True)

emb = scanvi_model.get_latent_representation()
diverged = not bool(np.isfinite(emb).all())
rna_emb, query_emb = emb[:len(rna_Z)], emb[len(rna_Z):]
stem = OUT / f"scanvi_{VARIANT}_seed{SEED}"
np.save(f"{stem}_rna_emb.npy", rna_emb)
np.save(f"{stem}_query_emb.npy", query_emb)

pred = pd.DataFrame({"cell_id": cell_ids})
pred["native"] = np.asarray(scanvi_model.predict())[len(rna_Z):]
if not diverged:
    clf = KNeighborsClassifier(n_neighbors=KNN_K, metric="cosine", weights="distance").fit(rna_emb, rna_labels)
    pred["shared_knn"] = clf.predict(query_emb)
pred.to_csv(f"{stem}_pred.csv", index=False)

meta = {"method": "scANVI", "dataset": "Fulcher 2026 (held out)", "variant": VARIANT, "seed": SEED,
        "n_rna_cells": int(len(rna_Z)), "n_query_cells": int(len(query_Z)), "diverged": diverged,
        "elapsed_s": round(time.time() - t0, 1)}
json.dump(meta, open(f"{stem}.json", "w"), indent=2)
print(json.dumps(meta), flush=True)
