"""'Ours' through the same shared harness as every other arm (fix 1).

RNA side: service/model/reference_embedding.npy, the REAL frozen v3
reference embedding for all 85,233 RNA cells -- no reconstruction, this is
the actual artifact the live service ships.

Protein side: reconstructed via the (now-fixed) production pipeline --
alignment.align_to_feature_space -> smoothing.fuzzy_smooth -> the real
encoder -- with one disclosed, unresolved limitation: the only protein
input available in this repository or on this machine is
Atlas/atlas_PROT_lat128.csv, which git blame confirms predates the entire
v3 model (added in the repo's very first commit, 2025-08-17), and whose
gene columns are restricted to the ~2,907-gene RNA/protein intersection
used for the atlas viewer's gene-click feature. The notebook that produced
the shipped 45.37/31.08 and 86.17/79.79 figures instead read
blood_joint_cells_by_proteins_GENELEVEL.tsv, the protein's own full native
panel (likely far more than 2,907 genes), and used THAT full panel to build
Stage 2's smoothing graph. That raw TSV is not present anywhere in this
repository or on this machine (confirmed by exhaustive search) -- it only
ever lived on the original author's Google Drive. This script is a
best-effort reconstruction from what's actually available, not a faithful
replay of the original pipeline. It is reported as its own harness-derived
number, separate from and not mixed with the historical figures.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import pandas as pd
from service.pipeline import alignment, smoothing, encoder, reference
from evaluate import knn_classifier_predict, nearest_centroid_predict, evaluate_arm

D = Path(__file__).resolve().parent / "results"
REPO = Path(__file__).resolve().parents[2]

# RNA side: the real, live artifact -- no reconstruction.
rna_emb = np.load(f"{REPO}/service/model/reference_embedding.npy")
metadata = reference.load_reference_metadata()
class_names_by_idx = [c.class_name for c in metadata.classes]
rna_labels = np.array([class_names_by_idx[i] for i in metadata.class_idx_by_cell])
print(f"RNA: {rna_emb.shape}, {len(set(rna_labels))} classes (real, live artifact)")

# Protein side: best-effort reconstruction, disclosed limitation above.
prot_df = pd.read_csv(f"{REPO}/Atlas/atlas_PROT_lat128.csv")
gene_cols = [c for c in prot_df.columns if c.startswith("gene_")]
gene_names = [c[len("gene_"):] for c in gene_cols]
dz = prot_df[gene_cols].to_numpy(dtype=np.float32)  # already z-scored (own ~2907-gene panel)
true_labels = prot_df["class_name"].to_numpy()
cell_ids = prot_df["orig_index"].astype(str).tolist()

raw = alignment.RawMatrix(gene_names=gene_names, cell_ids=cell_ids, values=dz.T)
feature_genes = reference.load_feature_space_genes()
aligned = alignment.align_to_feature_space(raw, feature_genes)
print(f"coverage: {aligned.coverage*100:.2f}%")

smoothed = smoothing.fuzzy_smooth(aligned.values, dz)  # X_full_own limited to the ~2907-gene panel (the disclosed limitation)
enc = encoder.load_encoder()
prot_emb = enc.encode(smoothed, aligned.mask)
diverged = bool(np.isnan(prot_emb).sum() or np.isinf(prot_emb).sum())
print(f"protein embeddings {prot_emb.shape}, NaN {np.isnan(prot_emb).sum()}")

knn = knn_classifier_predict(rna_emb, rna_labels, prot_emb)
nc = nearest_centroid_predict(rna_emb, rna_labels, prot_emb)

result = {
    "method": "Ours (harness reconstruction)",
    "role": "supervised, frozen reference -- RECONSTRUCTED, see limitation note",
    "n_rna_cells": len(rna_labels),
    "subsample": None,
    "diverged": diverged,
    "limitation": (
        "Protein embedding reconstructed from Atlas/atlas_PROT_lat128.csv "
        "(pre-v3, ~2907-gene RNA-intersection panel), not the original "
        "blood_joint_cells_by_proteins_GENELEVEL.tsv full native protein "
        "panel the export notebook used to build the Stage-2 smoothing "
        "graph. That raw file is unavailable in this repo/machine. Restricted "
        "regime lands close to the documented figure (see prose); unrestricted "
        "does not -- most likely because of this narrower smoothing graph, "
        "not a scoring-rule difference."
    ),
    "knn_classifier": evaluate_arm(true_labels, knn["unrestricted"], knn["restricted"], len(set(rna_labels)), 2),
    "native_nearest_centroid": evaluate_arm(true_labels, nc["unrestricted"], nc["restricted"], len(set(rna_labels)), 2),
    "historical_documented_figures": {
        "source": "service/model/v3_tables/support_restricted_assignment.csv (export notebook's own methodology, real raw TSV)",
        "unrestricted": {"accuracy_pct": 45.369127516778526, "balanced_accuracy_pct": 31.083265404424022},
        "restricted": {"accuracy_pct": 86.1744966442953, "balanced_accuracy_pct": 79.7915354403646},
    },
}
json.dump(result, open(f"{D}/result_ours_v2.json", "w"), indent=2)
print(json.dumps(result, indent=2))
