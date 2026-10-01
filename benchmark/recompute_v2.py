"""Recompute predictions + scores + bootstrap CIs for every arm that already
has embeddings on disk or is cheap/deterministic to re-derive (PCA, Harmony,
MaxFuse, scGLUE). Does NOT retrain anything -- MaxFuse and scGLUE embeddings
are loaded from the .npy files already saved during their original runs;
PCA and Harmony are refit fresh (seconds, deterministic with fixed seeds,
not a "rerun of a baseline" in the sense of re-training a model).
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
import harmonypy
from evaluate import knn_classifier_predict, nearest_centroid_predict, evaluate_arm, score, bootstrap_ci

D = Path(__file__).resolve().parent / "results"

rna_X = np.load(f"{D}/rna_X.npy")
prot_X = np.load(f"{D}/prot_X.npy")
rna_meta = pd.read_csv(f"{D}/rna_meta.csv")
prot_meta = pd.read_csv(f"{D}/prot_meta.csv")
rna_labels = rna_meta["class_name"].to_numpy()
true_labels = prot_meta["class_name"].to_numpy()


def zscore_cols(X, eps=1e-8):
    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    return (X - mean) / np.clip(std, eps, None)


def build_result(method, role, rna_emb, prot_emb, diverged=False):
    knn = knn_classifier_predict(rna_emb, rna_labels, prot_emb)
    nc = nearest_centroid_predict(rna_emb, rna_labels, prot_emb)
    n_classes = len(set(rna_labels))
    return {
        "method": method, "role": role, "n_rna_cells": len(rna_labels), "subsample": None,
        "diverged": diverged,
        "knn_classifier": evaluate_arm(true_labels, knn["unrestricted"], knn["restricted"], n_classes, 2),
        "native_nearest_centroid": evaluate_arm(true_labels, nc["unrestricted"], nc["restricted"], n_classes, 2),
    }


# --- PCA floor (refit, seconds, deterministic) ---
rna_Z, prot_Z = zscore_cols(rna_X), zscore_cols(prot_X)
combined = np.vstack([rna_Z, prot_Z]).astype(np.float32)
pca = PCA(n_components=50, random_state=0)
emb = pca.fit_transform(combined)
result = build_result("PCA + nearest-centroid/kNN floor", "unsupervised floor", emb[:len(rna_Z)], emb[len(rna_Z):])
json.dump(result, open(f"{D}/result_pca_nn_v2.json", "w"), indent=2)
print("PCA done")

# --- Harmony (refit, ~15s, deterministic) ---
meta_df = pd.DataFrame({"modality": np.array(["RNA"] * len(rna_Z) + ["Protein"] * len(prot_Z))})
ho = harmonypy.run_harmony(pca.fit_transform(combined), meta_df, ["modality"], max_iter_harmony=30)
hemb = np.asarray(ho.Z_corr)
if hemb.shape[0] == 50:
    hemb = hemb.T
result = build_result("Harmony", "batch-correction floor, not cross-modal integration", hemb[:len(rna_Z)], hemb[len(rna_Z):])
json.dump(result, open(f"{D}/result_harmony_v2.json", "w"), indent=2)
print("Harmony done")

# --- MaxFuse (load cached embeddings, no retraining) ---
rna_emb, prot_emb = np.load(f"{D}/rna_maxfuse.npy"), np.load(f"{D}/prot_maxfuse.npy")
result = build_result("MaxFuse", "unsupervised cross-modal integration (CCA-based fuzzy matching)", rna_emb, prot_emb)
json.dump(result, open(f"{D}/result_maxfuse_v2.json", "w"), indent=2)
print("MaxFuse done")

# --- scGLUE (load cached embeddings, no retraining) ---
rna_emb, prot_emb = np.load(f"{D}/rna_scglue.npy"), np.load(f"{D}/prot_scglue.npy")
result = build_result("scGLUE", "unsupervised cross-modal integration (graph-linked VAE)", rna_emb, prot_emb)
json.dump(result, open(f"{D}/result_scglue_v2.json", "w"), indent=2)
print("scGLUE done")

# --- majority-class baseline (deterministic, no embedding at all) ---
# Majority class of the PROTEIN QUERY's true labels, not the RNA reference's
# (RNA's majority class is "neutrophil", which never appears among the
# protein query's true labels at all -- predicting it would score 0%).
maj_class = pd.Series(true_labels).value_counts().idxmax()
pred_maj = np.full(len(true_labels), maj_class)
result = {
    "method": "Majority class (always predict the protein query's most common class)",
    "role": "trivial baseline",
    "n_rna_cells": len(rna_labels), "subsample": None, "diverged": False,
    "knn_classifier": None,
    "native_nearest_centroid": {
        "unrestricted": {**score(true_labels, pred_maj, 22), **bootstrap_ci(true_labels, pred_maj)},
        "restricted": {**score(true_labels, pred_maj, 2), **bootstrap_ci(true_labels, pred_maj)},
    },
}
json.dump(result, open(f"{D}/result_majority_v2.json", "w"), indent=2)
print("Majority-class baseline done:", maj_class)
