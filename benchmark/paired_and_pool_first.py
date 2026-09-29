"""Follow-up analyses added after the initial fair-baseline-comparison
round: a paired bootstrap on ours-minus-scANVI balanced accuracy (more
powerful than eyeballing two independent CIs), and a pool-first restricted
kNN variant that mirrors service/pipeline/assignment.py's real algorithm
(candidate pool restricted before the neighbour search, not after -- what
the product would actually deliver if kNN were the selected assignment
method, distinct from the post-hoc-masking approximation every other
number in this benchmark uses).

Reads cached embeddings only -- no retraining. Requires load.py,
maxfuse_run.py, scglue_run.py, and scanvi_run.py (run once per seed: 0, 1,
2, each producing rna_scanvi_seed{N}.npy/prot_scanvi_seed{N}.npy) to have
already populated results/ -- see research/benchmark/harness.md.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
import harmonypy

from service.pipeline import reference
from evaluate import knn_classifier_predict, pool_first_knn_predict, score, bootstrap_ci, paired_bootstrap_diff

D = Path(__file__).resolve().parent / "results"
REPO = Path(__file__).resolve().parents[1]
MISSING_ROW = 42616  # see research/benchmark/bugs-and-fixes.md#7

rna_X = np.load(D / "rna_X.npy")
prot_X = np.load(D / "prot_X.npy")
rna_meta = pd.read_csv(D / "rna_meta.csv")
prot_meta = pd.read_csv(D / "prot_meta.csv")
rna_labels_bench = rna_meta["class_name"].to_numpy()
true_labels_bench = prot_meta["class_name"].to_numpy()


def zscore_cols(X, eps=1e-8):
    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    return (X - mean) / np.clip(std, eps, None)


arms = {}

rna_Z, prot_Z = zscore_cols(rna_X), zscore_cols(prot_X)
combined = np.vstack([rna_Z, prot_Z]).astype(np.float32)
pca = PCA(n_components=50, random_state=0)
emb = pca.fit_transform(combined)
arms["PCA floor"] = (emb[:len(rna_Z)], emb[len(rna_Z):], rna_labels_bench, true_labels_bench)

meta_df = pd.DataFrame({"modality": np.array(["RNA"] * len(rna_Z) + ["Protein"] * len(prot_Z))})
ho = harmonypy.run_harmony(pca.fit_transform(combined), meta_df, ["modality"], max_iter_harmony=30)
hemb = np.asarray(ho.Z_corr)
if hemb.shape[0] == 50:
    hemb = hemb.T
arms["Harmony"] = (hemb[:len(rna_Z)], hemb[len(rna_Z):], rna_labels_bench, true_labels_bench)

arms["MaxFuse"] = (np.load(D / "rna_maxfuse.npy"), np.load(D / "prot_maxfuse.npy"), rna_labels_bench, true_labels_bench)
arms["scGLUE"] = (np.load(D / "rna_scglue.npy"), np.load(D / "prot_scglue.npy"), rna_labels_bench, true_labels_bench)

for seed in (0, 1, 2):
    arms[f"scANVI (seed {seed})"] = (
        np.load(D / f"rna_scanvi_seed{seed}.npy"), np.load(D / f"prot_scanvi_seed{seed}.npy"),
        rna_labels_bench, true_labels_bench,
    )

metadata = reference.load_reference_metadata()
class_names_by_idx = [c.class_name for c in metadata.classes]
ours_rna_labels_full = np.array([class_names_by_idx[i] for i in metadata.class_idx_by_cell])
ours_rna_emb_full = np.load(REPO / "service" / "model" / "runtime" / "reference_embedding.npy")
keep = np.ones(ours_rna_emb_full.shape[0], dtype=bool)
keep[MISSING_ROW] = False
ours_rna_emb, ours_rna_labels = ours_rna_emb_full[keep], ours_rna_labels_full[keep]
ours_prot_emb = np.load(REPO / "service" / "model" / "source" / "app_export" / "prot_embedding_scope2.npy")
ours_prot_meta = pd.read_csv(REPO / "service" / "model" / "source" / "app_export" / "atlas_PROT_v3_meta.csv")
ours_true_labels = ours_prot_meta["true_class_name"].to_numpy()
arms["Ours"] = (ours_rna_emb, ours_prot_emb, ours_rna_labels, ours_true_labels)

# --- pool-first restricted kNN vs post-hoc masking, every arm ---
pool_first_results = {}
for name, (rna_emb, prot_emb, rna_lab, true_lab) in arms.items():
    posthoc = knn_classifier_predict(rna_emb, rna_lab, prot_emb)["restricted"]
    poolfirst = pool_first_knn_predict(rna_emb, rna_lab, prot_emb)
    pool_first_results[name] = {
        "post_hoc_masking": {**score(true_lab, posthoc, 2), **bootstrap_ci(true_lab, posthoc)},
        "pool_first": {**score(true_lab, poolfirst, 2), **bootstrap_ci(true_lab, poolfirst)},
    }
json.dump(pool_first_results, open(D / "result_pool_first_knn.json", "w"), indent=2)
print(json.dumps(pool_first_results, indent=2))

# --- paired bootstrap: ours minus scANVI, shared kNN rule, both regimes ---
ours_rna_emb, ours_prot_emb, ours_rna_lab, ours_true_lab = arms["Ours"]
ours_knn = knn_classifier_predict(ours_rna_emb, ours_rna_lab, ours_prot_emb)

paired_results = {}
for seed in (0, 1, 2):
    s_rna_emb, s_prot_emb, s_rna_lab, s_true_lab = arms[f"scANVI (seed {seed})"]
    assert (ours_true_lab == s_true_lab).all(), "protein query order must match for a valid paired bootstrap"
    scanvi_knn = knn_classifier_predict(s_rna_emb, s_rna_lab, s_prot_emb)
    for regime in ("restricted", "unrestricted"):
        paired_results.setdefault(regime, {})[f"seed_{seed}"] = paired_bootstrap_diff(
            ours_true_lab, ours_knn[regime], scanvi_knn[regime]
        )
json.dump(paired_results, open(D / "result_paired_bootstrap.json", "w"), indent=2)
print(json.dumps(paired_results, indent=2))
