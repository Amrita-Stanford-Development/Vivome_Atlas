"""'Ours' through the same shared harness as every other arm.

No reconstruction: both embeddings are real, already-computed artifacts.

RNA side: service/model/runtime/reference_embedding.npy, the real frozen v3
reference embedding for all 85,233 RNA cells -- the actual artifact the
live service ships. Row 42616 (a neutrophil cell absent from
Atlas/atlas_RNA_lat128-001-part{1,2}.csv, see
Documentation/bugs-and-fixes.md) is dropped so "ours" uses the identical
85,232-cell RNA set every baseline already trained on.

Protein side: service/model/source/app_export/prot_embedding_scope2.npy, the
export notebook's own real, saved embedding for all 1,490 SCoPE2 protein
cells (sha256-verified against BUNDLE_MANIFEST.json when it was added --
see service/model/source/app_export/README.md). Labels come from
service/model/source/app_export/atlas_PROT_v3_meta.csv's true_class_name column,
in that file's own row order -- never web/data/atlas_PROT_lat128.csv, a
legacy file with an unverified row order (see
Documentation/known-limitations.md).

An earlier version of this script reconstructed the protein embedding from
scratch via service.pipeline (alignment -> smoothing -> encoder) because
the real embedding wasn't available in this repository yet. That
reconstruction is gone: once the real files were obtained, scoring them
directly here is what actually matters, and reconstructing when the real
artifact exists would just reintroduce noise for no reason. The
reconstruction *did* serve one purpose on its way out: comparing it against
the real embedding is what caught two real production bugs in
service/pipeline -- see Documentation/bugs-and-fixes.md, and
service/tests/test_e2e_real_export.py for the regression guard that keeps
them fixed.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from service.pipeline import reference
from evaluate import knn_classifier_predict, nearest_centroid_predict, evaluate_arm

D = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[1]
APP_EXPORT = REPO / "service" / "model" / "source" / "app_export"
MISSING_ROW = 42616  # neutrophil cell absent from the Atlas CSVs; drop to match baselines

# --- protein side: real embedding, real labels ---
prot_emb = np.load(APP_EXPORT / "prot_embedding_scope2.npy")
prot_meta = pd.read_csv(APP_EXPORT / "atlas_PROT_v3_meta.csv")
true_labels = prot_meta["true_class_name"].to_numpy()
assert len(true_labels) == prot_emb.shape[0]
print(f"protein: {prot_emb.shape}, labels aligned: {len(true_labels)}")

# --- RNA side: real embedding, dropped to the shared 85,232-cell set ---
rna_emb_full = np.load(REPO / "service" / "model" / "runtime" / "reference_embedding.npy")
metadata = reference.load_reference_metadata()
class_names_by_idx = [c.class_name for c in metadata.classes]
rna_labels_full = np.array([class_names_by_idx[i] for i in metadata.class_idx_by_cell])
print(f"RNA full: {rna_emb_full.shape[0]} cells (before dropping row {MISSING_ROW})")

keep = np.ones(rna_emb_full.shape[0], dtype=bool)
keep[MISSING_ROW] = False
rna_emb = rna_emb_full[keep]
rna_labels = rna_labels_full[keep]
print(f"RNA aligned: {rna_emb.shape[0]} cells (matches baselines' 85,232)")

knn = knn_classifier_predict(rna_emb, rna_labels, prot_emb)
nc = nearest_centroid_predict(rna_emb, rna_labels, prot_emb)
n_classes = len(set(rna_labels))

result = {
    "method": "Ours",
    "role": "supervised, frozen reference",
    "n_rna_cells": int(rna_emb.shape[0]),
    "n_prot_cells": int(prot_emb.shape[0]),
    "subsample": None,
    "diverged": False,
    "note": "Real embeddings, no reconstruction. RNA: service/model/runtime/reference_embedding.npy "
            "(row 42616 dropped to match baselines). Protein: "
            "service/model/source/app_export/prot_embedding_scope2.npy, labels from "
            "atlas_PROT_v3_meta.csv's true_class_name column, same row order.",
    "knn_classifier": evaluate_arm(true_labels, knn["unrestricted"], knn["restricted"], n_classes, 2),
    "native_nearest_centroid": evaluate_arm(true_labels, nc["unrestricted"], nc["restricted"], n_classes, 2),
    "historical_documented_figures": {
        "source": "service/model/evidence/v3_tables/support_restricted_assignment.csv",
        "unrestricted": {"accuracy_pct": 45.369127516778526, "balanced_accuracy_pct": 31.083265404424022},
        "restricted": {"accuracy_pct": 86.1744966442953, "balanced_accuracy_pct": 79.7915354403646},
    },
}
print(json.dumps(result, indent=2))
with open(D / "results" / "result_ours.json", "w") as f:
    json.dump(result, f, indent=2)
