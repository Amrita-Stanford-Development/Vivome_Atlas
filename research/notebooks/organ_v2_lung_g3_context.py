"""Organ references v2, an explanation after the lung v2's gates
(research/organ-references.md, "The lung v2's outcome"): was PXD058626's
airway-against-alveoli question hard in itself, or is the model behind simple
methods on it?

The lung v2 missed G3 at AUROC 0.764 (bar 0.8): control airways against
control alveoli, scored as P(airway epithelial group) - P(alveolar
epithelial group). This puts two references beside that figure, on the same
24 control regions, read without FragPipe's contaminant rows
(organ_v2_gates.read_fragpipe_intensity).

1. **A marker positive control**, from the protein data alone. The score is
   each region's mean within-upload z of the airway markers minus that of the
   alveolar markers (both lists fixed here; a marker the table lacks is
   skipped and named):
   - airway: SCGB1A1, SCGB3A1, MUC5B, MUC5AC, KRT5, FOXJ1, TPPP3, BPIFB1;
   - alveolar: SFTPC, SFTPB, SFTPA1, SFTPA2, AGER, NAPSA, LAMP3, EMP2.
2. **The locked tests' two baselines** (benchmark/organ_baselines.py:
   correlation, and PCA with kNN projected around the class-balanced
   centre), on the lung v2's own gene space and labels. Each is scored as the
   model was: airway epithelial group minus alveolar epithelial group
   (correlation: each group's best class; kNN: each group's vote share).

**It is an explanation only.** The lung v2's verdict is NO GO under the stop
rules, whatever this shows. It tells the owner, for a v3 decision, whether
the set separates the two regions at all, and where simple methods stand.

Writes research/notebook-outputs/organ_v2_lung_g3_context/: rules.json
(first), result.json.

    python research/notebooks/organ_v2_lung_g3_context.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import organ_v2_gates as gates  # noqa: E402  (its path setup, the reader and the region names)
from organ_reference import data  # noqa: E402

from benchmark import organ_baselines as ob  # noqa: E402
from benchmark.baselines_corrected import class_balanced_z  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_lung_g3_context"
ORGAN = "lung_v2"
AIRWAY = ("SCGB1A1", "SCGB3A1", "MUC5B", "MUC5AC", "KRT5", "FOXJ1", "TPPP3", "BPIFB1")
ALVEOLAR = ("SFTPC", "SFTPB", "SFTPA1", "SFTPA2", "AGER", "NAPSA", "LAMP3", "EMP2")
GATE_G3 = REPO / "research" / "notebook-outputs" / "lung_v2_development" / "g3.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def marker_score(q: np.ndarray, genes: list[str]) -> tuple[np.ndarray, dict]:
    z = ob.query_z(q)
    index = {g: i for i, g in enumerate(genes)}
    used = {name: [g for g in markers if g in index] for name, markers in (("airway", AIRWAY), ("alveolar", ALVEOLAR))}
    side = {name: z[:, [index[g] for g in gs]].mean(1) for name, gs in used.items()}
    missing = {name: [g for g in markers if g not in index] for name, markers in (("airway", AIRWAY), ("alveolar", ALVEOLAR))}
    return side["airway"] - side["alveolar"], {"used": used, "missing": missing}


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    work = data.WORK / ORGAN
    candidate = work / "bundle"
    registry = json.loads(gates.REGISTRY.read_text(encoding="utf-8"))[ORGAN]
    if sha256(candidate / "MANIFEST.json") != registry["bundle_manifest_sha256"]:
        raise SystemExit("the bundle is not the frozen lung v2")
    path = gates.DEV / "Herrera2025_PXD058626" / "combined_protein.tsv"
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "table_sha256": sha256(path), "airway": AIRWAY, "alveolar": ALVEOLAR,
                                        "baselines_sha256": sha256(Path(ob.__file__)),
                                        "bundle_manifest_sha256": registry["bundle_manifest_sha256"]})
    raw = gates.read_fragpipe_intensity(path)
    region = np.array([gates.herrera_region(s) for s in raw.cell_ids])
    keep = np.isin(region, ["control airway", "control alveoli"])
    truth = region[keep] == "control airway"
    q = ob.organ_matrix(raw, candidate)
    genes = [g.upper() for g in pd.read_csv(candidate / "feature_space_genes.csv")["gene"].astype(str)]
    markers, marker_record = marker_score(q, genes)
    X, labels, hierarchy = ob.reference(work, ORGAN)
    rna_z = class_balanced_z(X, labels)
    del X
    classes = sorted(set(labels))
    cor, cor_classes = ob.correlation_scores(rna_z, labels, q)
    space = ob.knn_space(rna_z, labels, q)
    knn, knn_classes = ob.knn_votes(*space, classes)
    result = {"finished": None, "regions": {"control airway": int(truth.sum()), "control alveoli": int((~truth).sum())},
              "auroc_model_gate_run": json.loads(GATE_G3.read_text(encoding="utf-8"))["auroc"],
              "auroc_markers": round(float(roc_auc_score(truth, markers[keep])), 4), "markers": marker_record,
              "setup_checks_knn": ob.setup_checks(*space, classes)}
    for name, scores, cls, how in (("correlation", cor, cor_classes, "max"), ("pca_knn", knn, knn_classes, "sum")):
        groups = ob.by_level(scores, cls, hierarchy, "group", how)
        s = (groups["airway epithelial"] - groups["alveolar epithelial"]).to_numpy()
        ok = keep & np.isfinite(s)
        result[f"auroc_{name}"] = round(float(roc_auc_score(region[ok] == "control airway", s[ok])), 4)
    result["finished"] = datetime.now().isoformat(timespec="seconds")
    result["verdict"] = "unchanged: NO GO under the stop rules (explanation only)"
    data.save_json(OUT / "result.json", result)
    print(json.dumps({k: v for k, v in result.items() if k.startswith("auroc")}, indent=1))


if __name__ == "__main__":
    main()
