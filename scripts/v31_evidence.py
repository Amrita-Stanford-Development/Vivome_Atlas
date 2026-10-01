"""v3.1's own cross-modal evidence, measured the way the v3 export measured
v3's (service/model/source/VivOME_Prototype_Export.ipynb, sections C and D),
so the two releases are comparable:

- latent_centroid_cosine.csv: for each class with protein cells, the cosine
  between the normalised mean of the SCoPE2 cells' latents (true labels)
  and that class's RNA centroid. Measured in every member's latent space;
  the main column is the coordinate member (config.V31_COORDINATE_MEMBER),
  the space the atlas displays.
- modality_probe.json: 5-fold stratified cross-validated balanced accuracy
  of a logistic regression telling RNA latents from protein latents, RNA
  subsampled to the protein count (seed 0). Same members, same main one.

SCoPE2's latents come from the served pipeline (Stages 0-3). Before writing
anything, the same code must reproduce v3's committed tables from v3's own
latents (to 1e-6), or the script stops.

Writes service/model/evidence/v3_1_tables/. Then run build_manifest.py.

    python scripts/v31_evidence.py      # from the repository root
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from service import config  # noqa: E402
from service.pipeline import alignment, pipeline  # noqa: E402

MODEL = REPO / "service" / "model"
V3_TABLES = MODEL / "evidence" / "v3_tables"
OUT = MODEL / "evidence" / "v3_1_tables"
SCOPE2 = MODEL / "source" / "app_export" / "blood_joint_cells_by_proteins_GENELEVEL.tsv"
SCOPE2_TRUTH = REPO / "web" / "data" / "metadata_PROT_lat128.csv"  # class_idx: SCoPE2's own labels, same row order
PROBE_BASIS = "5-fold CV, logistic regression on 128-d latent, RNA subsampled to protein n"


def centroid_cosines(z_prot: np.ndarray, truth: np.ndarray, centroids: np.ndarray) -> dict[int, float]:
    """{class position: cosine} for every class with at least two protein cells (section C)."""
    out = {}
    for ci in range(len(centroids)):
        m = truth == ci
        if m.sum() >= 2:
            c = z_prot[m].mean(0)
            out[ci] = float(c / (np.linalg.norm(c) + 1e-12) @ centroids[ci])
    return out


def modality_probe(z_ref_all: np.ndarray, z_prot: np.ndarray) -> np.ndarray:
    """Per-fold balanced accuracy, percent (section D)."""
    sub = np.random.default_rng(0).choice(len(z_ref_all), len(z_prot), replace=False)
    x = np.vstack([z_ref_all[sub], z_prot])
    y = np.r_[np.zeros(len(sub), int), np.ones(len(z_prot), int)]
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    return 100 * cross_val_score(LogisticRegression(max_iter=2000, C=1.0), x, y, cv=cv, scoring="balanced_accuracy")


def check_against_v3(truth: np.ndarray) -> None:
    """The method must reproduce v3's committed numbers from v3's latents."""
    z_ref = np.load(MODEL / "runtime" / "reference_embedding.npy")
    z_prot = np.load(MODEL / "source" / "app_export" / "prot_embedding_scope2.npy")
    cos = centroid_cosines(z_prot, truth, np.load(MODEL / "runtime" / "reference_centroids.npy"))
    committed = pd.read_csv(V3_TABLES / "latent_centroid_cosine.csv").dropna(subset=["latent_centroid_cosine"])
    for _, row in committed.iterrows():
        if abs(cos[int(row.class_idx)] - row.latent_centroid_cosine) > 1e-6:
            raise SystemExit(f"v3 check failed for {row.class_name}: {cos[int(row.class_idx)]} vs {row.latent_centroid_cosine}")
    probe = modality_probe(z_ref, z_prot).mean()
    want = json.loads((V3_TABLES / "modality_probe.json").read_text())["modality_probe_balanced_accuracy_pct"]
    if abs(probe - want) > 1e-6:
        raise SystemExit(f"v3 check failed for the modality probe: {probe} vs {want}")
    print(f"v3 reproduced: cosines {[round(cos[i], 6) for i in sorted(cos)]}, probe {probe:.4f}")


def main() -> None:
    truth = pd.read_csv(SCOPE2_TRUTH)["class_idx"].to_numpy()
    check_against_v3(truth)

    bundle = pipeline.load_bundle("v3.1")
    df = pd.read_csv(SCOPE2, sep="\t", index_col=0)
    raw = alignment.RawMatrix(gene_names=df.columns.astype(str).tolist(), cell_ids=df.index.astype(str).tolist(),
                              values=df.to_numpy(dtype=np.float32).T)
    smoothed, aligned, _ = pipeline._prepare_query(bundle.feature_genes, raw)
    if [c.class_idx for c in bundle.metadata.classes] != list(range(len(bundle.class_names))):
        raise SystemExit("class_idx and class position differ; the truth labels would need translating")

    cosines, probes = {}, {}
    for m in bundle.members:
        z = m.encoder_handle.encode(smoothed, aligned.mask)
        cosines[m.name] = centroid_cosines(z, truth, m.centroids)
        probes[m.name] = modality_probe(m.reference_latents, z)
        print(f"{m.name}: cosines {[round(cosines[m.name][i], 4) for i in sorted(cosines[m.name])]}, "
              f"probe {probes[m.name].mean():.2f}")
    main_member = config.V31_COORDINATE_MEMBER

    OUT.mkdir(parents=True, exist_ok=True)
    counts = np.bincount(truth, minlength=len(bundle.class_names))
    with (OUT / "latent_centroid_cosine.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["class_idx", "class_name", "n_prot_cells", "latent_centroid_cosine",
                         "member_min", "member_max", "status", "reason"])
        for ci, name in enumerate(bundle.class_names):
            if ci in cosines[main_member]:
                values = [cosines[m][ci] for m in cosines]
                writer.writerow([ci, name, int(counts[ci]), cosines[main_member][ci], min(values), max(values),
                                 "measured", f"128-d latent of {main_member}, SCoPE2 true labels"])
            else:
                writer.writerow([ci, name, int(counts[ci]), "", "", "", "pending", "no cross modal coverage"])
    folds = probes[main_member]
    probe = {
        "modality_probe_balanced_accuracy_pct": float(folds.mean()),
        "std_pct": float(folds.std()),
        "folds": [float(f) for f in folds],
        "n_per_class": int(len(truth)),
        "member": main_member,
        "members_pct": {m: float(f.mean()) for m, f in probes.items()},
        "basis": f"{PROBE_BASIS}; latent of {main_member}, the coordinate member",
    }
    (OUT / "modality_probe.json").write_text(json.dumps(probe, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(REPO)}/latent_centroid_cosine.csv and modality_probe.json")


if __name__ == "__main__":
    main()
