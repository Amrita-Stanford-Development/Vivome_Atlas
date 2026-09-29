"""scANVI on the real, raw PBMC240 arm (Track D task 2) -- adapted from
scanvi_run.py, which does the same thing for SCoPE2. A separate script, not
a parameter to the original, because the query side here needs its own
NaN-aware z-scoring (PBMC240 has ~75% missing values in the shared gene
space; SCoPE2 has none) and its own lineage-level scoring (PBMC240's
weak labels are lineage, not the fine-grained class SCoPE2 uses).

Requires results/pbmc_X.npy + results/pbmc_meta.csv
(pbmc240_lineage_prep.py) and results/rna_X.npy + results/rna_meta.csv
(load.py) to already exist.

Explicit seeding, like scanvi_run.py -- run once per seed (0, 1, 2):

    python3 scanvi_run_pbmc240.py 0
    python3 scanvi_run_pbmc240.py 1
    python3 scanvi_run_pbmc240.py 2

This is a development-dataset comparison point (PBMC240 raw was used to
choose V2 over v3 -- see docs/plans/nb1d/nb1d_summary.json's "note"), not a
held-out evaluation; label it that way wherever it's reported.

Always saves its trained embeddings and lineage predictions to results/
(gitignored, but not disposable -- see the comment in .gitignore), so a
lineage-recall or composition analysis never requires retraining scANVI a
second time.
"""
import sys, time, json, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import anndata as ad
import scvi
import torch
from scvi.model import SCVI, SCANVI
from sklearn.neighbors import KNeighborsClassifier

D = Path(__file__).resolve().parent / "results"
REPO = Path(__file__).resolve().parents[2]

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 0
scvi.settings.seed = SEED
torch.manual_seed(SEED)
np.random.seed(SEED)

t0 = time.time()
rna_X = np.load(f"{D}/rna_X.npy")
pbmc_X = np.load(f"{D}/pbmc_X.npy")
rna_meta = pd.read_csv(f"{D}/rna_meta.csv")
pbmc_meta = pd.read_csv(f"{D}/pbmc_meta.csv")
print(f"RNA cells: {len(rna_meta)}, PBMC240 cells: {len(pbmc_meta)}. elapsed {time.time()-t0:.1f}s", flush=True)

rna_labels = rna_meta["class_name"].to_numpy()
class_to_lineage = pd.read_csv(REPO / "service/model/reference_metadata.csv") \
    .groupby("class_name")["lineage"].first().to_dict()
true_lineage = pbmc_meta["weak_lineage"].to_numpy()
scored_mask = np.isin(true_lineage, ["lymphoid", "myeloid"])  # excludes "unassigned"


def zscore_cols(X, eps=1e-8):
    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    return (X - mean) / np.clip(std, eps, None)


def zscore_cols_nan_aware(X, eps=1e-8):
    """PBMC240's shared-space matrix has real missing values (a gene it
    never detected). Column mean/std computed over observed values only,
    then unobserved entries fall back to 0 (the post-scaling mean) --
    matching this project's "zero for unmeasured, never a guessed value"
    convention rather than imputing."""
    mean = np.nanmean(X, axis=0, keepdims=True)
    std = np.nanstd(X, axis=0, keepdims=True)
    scaled = (X - mean) / np.clip(std, eps, None)
    return np.nan_to_num(scaled, nan=0.0)


rna_Z = zscore_cols(rna_X).astype(np.float32)
pbmc_Z = zscore_cols_nan_aware(pbmc_X).astype(np.float32)
combined = np.vstack([rna_Z, pbmc_Z])
modality = np.array(["RNA"] * len(rna_Z) + ["Protein"] * len(pbmc_Z))
labels = np.array(list(rna_labels) + ["Unknown"] * len(pbmc_Z))

adata = ad.AnnData(X=combined.astype(np.float32))
adata.obs["modality"] = modality
adata.obs["cell_type"] = labels
adata.obs["cell_type"] = adata.obs["cell_type"].astype("category")
adata.obs["size_factor"] = 1.0

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    SCVI.setup_anndata(adata, batch_key="modality", labels_key="cell_type", size_factor_key="size_factor")
    scvi_model = SCVI(adata, n_latent=30, n_layers=2, n_hidden=128,
                       gene_likelihood="normal", log_variational=False)
    print(f"SCVI model built. elapsed {time.time()-t0:.1f}s", flush=True)
    scvi_model.train(max_epochs=200, early_stopping=True, early_stopping_patience=15)
    print(f"SCVI pretrain done. elapsed {time.time()-t0:.1f}s", flush=True)

    scanvi_model = SCANVI.from_scvi_model(scvi_model, unlabeled_category="Unknown", labels_key="cell_type")
    print(f"SCANVI model built. elapsed {time.time()-t0:.1f}s", flush=True)
    scanvi_model.train(max_epochs=100, early_stopping=True, early_stopping_patience=15)
    print(f"SCANVI train done. elapsed {time.time()-t0:.1f}s", flush=True)

emb = scanvi_model.get_latent_representation()
diverged = bool(np.isnan(emb).sum() or np.isinf(emb).sum())
print(f"embeddings {emb.shape}, NaN {np.isnan(emb).sum()}. elapsed {time.time()-t0:.1f}s", flush=True)

rna_emb, pbmc_emb = emb[:len(rna_Z)], emb[len(rna_Z):]
np.save(f"{D}/rna_scanvi_pbmc240_seed{SEED}.npy", rna_emb)
np.save(f"{D}/pbmc_scanvi_seed{SEED}.npy", pbmc_emb)


def to_lineage(pred_classes):
    return np.array([class_to_lineage.get(c, "unknown") for c in pred_classes])


# Shared kNN rule, same k as evaluate.py's SUPPORTED protocol
clf = KNeighborsClassifier(n_neighbors=30, metric="cosine", weights="distance")
clf.fit(rna_emb, rna_labels)
knn_pred_class = clf.predict(pbmc_emb)
knn_pred_lineage = to_lineage(knn_pred_class)

# scANVI's own native label-transfer classifier
native_pred_class = np.asarray(scanvi_model.predict())[len(rna_Z):]
native_pred_lineage = to_lineage(native_pred_class)

acc_knn = float((knn_pred_lineage[scored_mask] == true_lineage[scored_mask]).mean() * 100)
acc_native = float((native_pred_lineage[scored_mask] == true_lineage[scored_mask]).mean() * 100)
print(f"lineage accuracy on {scored_mask.sum()} labelled cells (unassigned excluded): "
      f"shared-kNN {acc_knn:.2f}%, native scANVI classifier {acc_native:.2f}%")

np.save(f"{D}/pbmc_scanvi_knn_pred_lineage_seed{SEED}.npy", knn_pred_lineage, allow_pickle=True)
np.save(f"{D}/pbmc_scanvi_native_pred_lineage_seed{SEED}.npy", native_pred_lineage, allow_pickle=True)

result = {
    "method": "scArches / scANVI",
    "arm": "PBMC240 raw, development dataset used to choose V2",
    "n_rna_cells": len(rna_labels),
    "n_pbmc_cells": len(pbmc_meta),
    "n_scored_cells": int(scored_mask.sum()),
    "diverged": diverged,
    "seed": SEED,
    "lineage_accuracy_pct": {
        "shared_knn_rule": acc_knn,
        "native_scanvi_classifier": acc_native,
    },
}
print(json.dumps(result, indent=2, default=str))
with open(f"{D}/result_scanvi_pbmc240_seed{SEED}.json", "w") as f:
    json.dump(result, f, indent=2, default=str)
print(f"\nTOTAL elapsed {time.time()-t0:.1f}s")
