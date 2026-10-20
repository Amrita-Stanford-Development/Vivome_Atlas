"""Organ references v2, an explanation after the lung v2's gates
(research/organ-references.md, "The lung v2's outcome"): how much did
FragPipe's contaminant rows move the lung's G3?

A review of the upload path after the gate run found that
organ_v2_gates.read_fragpipe_intensity keeps the rows FragPipe marks as
contaminants or decoys (a "Protein" starting with contam_ or rev_). In
PXD058626, 12 such rows have a gene name. They resolve to human feature
genes: bovine albumin as ALB, chicken lysozyme as LYZ, bovine trypsin as
PRSS1, and the caseins. The duplicate-gene median then merges them with
the human rows.

This runs G3 once more with those rows left out. Everything else is as in
the gate run: the same frozen bundle (checked against the registry), the
same score, the same regions and the same code (organ_v2_gates.g3_lung).

**It is an explanation only.** The lung v2's verdict is NO GO under the
stop rules, and stays so whatever this shows, because a change after a gate
result makes a v3. It tells the owner whether the reader caused the miss.

Writes research/notebook-outputs/organ_v2_lung_g3_contaminants/:
rules.json (first), result.json.

    python research/notebooks/organ_v2_lung_g3_contaminants.py      # from the repository root
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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import organ_v2_gates as gates  # noqa: E402  (its own path setup, the readers and g3_lung)
from organ_reference import bundle, data  # noqa: E402

from service.pipeline import alignment  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_lung_g3_contaminants"
ORGAN = "lung_v2"
GATE_G3 = REPO / "research" / "notebook-outputs" / "lung_v2_development" / "g3.json"
DECOY_PREFIXES = ("contam_", "rev_")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_contaminants(path: Path) -> alignment.RawMatrix:
    """organ_v2_gates.read_fragpipe_intensity, with FragPipe's contaminant and
    decoy rows left out."""
    t = pd.read_csv(path, sep="\t", low_memory=False)
    t = t[~t["Protein"].astype(str).str.startswith(DECOY_PREFIXES)]
    cols = [c for c in t.columns if c.endswith(" Intensity") and not c.endswith("MaxLFQ Intensity")]
    v = t[cols].apply(pd.to_numeric, errors="coerce").to_numpy(np.float32)
    v[v <= 0] = np.nan
    genes = t["Gene"].fillna("").astype(str)
    keep = (genes != "").to_numpy()
    return alignment.RawMatrix(gene_names=genes[keep].tolist(), cell_ids=[c[: -len(" Intensity")] for c in cols], values=v[keep])


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    build_dir = data.WORK / ORGAN
    registry = json.loads(gates.REGISTRY.read_text(encoding="utf-8"))[ORGAN]
    if sha256(build_dir / "bundle" / "MANIFEST.json") != registry["bundle_manifest_sha256"]:
        raise SystemExit("the bundle is not the frozen lung v2")
    path = gates.DEV / "Herrera2025_PXD058626" / "combined_protein.tsv"
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "gates_script_sha256": sha256(Path(gates.__file__)), "table_sha256": sha256(path),
                                        "bundle_manifest_sha256": registry["bundle_manifest_sha256"], "decoy_prefixes": DECOY_PREFIXES})
    full = pd.read_csv(path, sep="\t", low_memory=False)
    dropped = full[full["Protein"].astype(str).str.startswith(DECOY_PREFIXES) & full["Gene"].fillna("").astype(str).ne("")]
    b = bundle.load(build_dir / "bundle")
    original = gates.read_fragpipe_intensity
    try:
        gates.read_fragpipe_intensity = without_contaminants
        with bundle.gene_map(build_dir / "bundle"):
            r = gates.g3_lung(b)
    finally:
        gates.read_fragpipe_intensity = original
    gate = json.loads(GATE_G3.read_text(encoding="utf-8"))
    result = {"finished": datetime.now().isoformat(timespec="seconds"),
              "rows_left_out": [{"protein": p, "gene": g} for p, g in zip(dropped["Protein"], dropped["Gene"])],
              "auroc_gate_run": gate["auroc"], "auroc_without_contaminants": r["auroc"],
              "mean_score_by_region": r["mean_score_by_region"], "argmax_lineage": r["argmax_lineage"],
              "verdict": "unchanged: NO GO under the stop rules (explanation only)"}
    data.save_json(OUT / "result.json", result)
    print(json.dumps({k: result[k] for k in ("auroc_gate_run", "auroc_without_contaminants")}, indent=1),
          len(result["rows_left_out"]), "rows left out")


if __name__ == "__main__":
    main()
