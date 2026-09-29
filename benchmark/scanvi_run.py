"""scANVI. Explicit seeding (an early, undocumented run had none, so its
point estimate was never reproducible on a rerun -- see
Documentation/bugs-and-fixes.md#6) and always saves embeddings +
predictions to disk, so a bootstrap CI never requires retraining scANVI a
second time. Takes an optional seed argument (default 0); run it once per
seed (0, 1, 2) to build the 3-seed table in Documentation/results.md.

    python3 scanvi_run.py 0
    python3 scanvi_run.py 1
    python3 scanvi_run.py 2
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
from evaluate import knn_classifier_predict, nearest_centroid_predict, evaluate_arm, score, bootstrap_ci

D = Path(__file__).resolve().parent / "results"

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 0
scvi.settings.seed = SEED
torch.manual_seed(SEED)
np.random.seed(SEED)

t0 = time.time()
rna_X = np.load(f"{D}/rna_X.npy")
prot_X = np.load(f"{D}/prot_X.npy")
rna_meta = pd.read_csv(f"{D}/rna_meta.csv")
prot_meta = pd.read_csv(f"{D}/prot_meta.csv")
print(f"RNA cells: {len(rna_meta)} (full reference, no subsample). elapsed {time.time()-t0:.1f}s", flush=True)

rna_labels = rna_meta["class_name"].to_numpy()
true_labels = prot_meta["class_name"].to_numpy()


def zscore_cols(X, eps=1e-8):
    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    return (X - mean) / np.clip(std, eps, None)


rna_Z = zscore_cols(rna_X).astype(np.float32)
prot_Z = zscore_cols(prot_X).astype(np.float32)
combined = np.vstack([rna_Z, prot_Z])
modality = np.array(["RNA"] * len(rna_Z) + ["Protein"] * len(prot_Z))
labels = np.array(list(rna_labels) + ["Unknown"] * len(prot_Z))

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

rna_emb, prot_emb = emb[:len(rna_Z)], emb[len(rna_Z):]
np.save(f"{D}/rna_scanvi_seed{SEED}.npy", rna_emb)
np.save(f"{D}/prot_scanvi_seed{SEED}.npy", prot_emb)

# scANVI's own native label-transfer classifier
native_pred_unrestricted = np.asarray(scanvi_model.predict())[len(rna_Z):]
soft = scanvi_model.predict(soft=True)
soft_prot = np.asarray(soft)[len(rna_Z):]
classes_scanvi = list(soft.columns)
supported = ("macrophage", "monocyte")
supported_idx = [classes_scanvi.index(c) for c in supported if c in classes_scanvi]
native_pred_restricted = np.array(supported)[soft_prot[:, supported_idx].argmax(axis=1)]
np.save(f"{D}/native_scanvi_pred_unrestricted_seed{SEED}.npy", native_pred_unrestricted, allow_pickle=True)
np.save(f"{D}/native_scanvi_pred_restricted_seed{SEED}.npy", native_pred_restricted, allow_pickle=True)

knn = knn_classifier_predict(rna_emb, rna_labels, prot_emb)
nc = nearest_centroid_predict(rna_emb, rna_labels, prot_emb)
n_classes = len(set(rna_labels))

result = {
    "method": "scArches / scANVI",
    "role": "supervised, label-consuming cross-modal integration",
    "n_rna_cells": len(rna_labels),
    "subsample": None,
    "diverged": diverged,
    "seed": SEED,
    "note": f"Explicit seed={SEED}. Point estimates vary meaningfully across seeds -- see Documentation/results.md's 3-seed table before treating any single seed's numbers as representative.",
    "knn_classifier": evaluate_arm(true_labels, knn["unrestricted"], knn["restricted"], n_classes, 2),
    "native_nearest_centroid": evaluate_arm(true_labels, nc["unrestricted"], nc["restricted"], n_classes, 2),
    "native_scanvi_classifier": evaluate_arm(true_labels, native_pred_unrestricted, native_pred_restricted, n_classes, len(supported_idx)),
}
print(json.dumps(result, indent=2, default=str))
with open(f"{D}/result_scanvi_seed{SEED}.json", "w") as f:
    json.dump(result, f, indent=2, default=str)
print(f"\nTOTAL elapsed {time.time()-t0:.1f}s")
