"""v5, Phase 0 (research/todo.md, Track H): cleaned reference labels.

Why: the reference's labels (Tabula Sapiens blood, the h5ad's
cell_ontology_class, copied into service/model/runtime/reference_metadata.csv)
are noisy where every method fails. 1,657 of the 4,572 cells labelled CD8 T
are annotated "natural killer cell" by the atlas's own free_annotation
column, and markers agree: 41% of them express CD3D, against about 80% of
true T cells. The V2 encoder was trained with these labels
(research/notebook-outputs/nb2/nb1b_core.py), so it learned to merge CD8 T
with NK.

Rules, fixed before the first run; no protein label is read:

- T and NK block: only cells labelled "cd8-positive, alpha-beta t cell",
  "natural killer cell" or "mature nk t cell". Their free_annotation
  (lower-cased) decides:
  - "natural killer cell" or "nk cell" -> natural killer cell;
  - containing "nk t" ("type i nk t cell", "mature nk t cell", "nk t cell")
    -> mature nk t cell;
  - containing "cd8" -> cd8-positive, alpha-beta t cell;
  - anything else keeps its label.
- Everything else, including the donor-driven split between "monocyte" and
  "classical monocyte", is unchanged. The 22 classes and their order are
  unchanged.
- Validation, reported: marker detection rates per class before and after;
  the composition of the atlas's scVI clusters for the T and NK classes; the
  relabelled cells by donor and assay.

Amendment (2026-10-12, the owner's decision, before any model was trained or
any protein data scored). The first run also moved cells labelled "monocyte"
out by free_annotation: "dendritic cell" (492) to myeloid DC, "macrophage"
(438) to macrophage. Its marker validation showed them to be monocytes:
- the "dendritic cells": CD14 82%, CD163 90%, CD1C 0.6%, FCER1A 0.2%,
  HLA-DQA1 3%. The reference's pDCs, for contrast: FCER1A 31%, HLA-DQA1 86%.
- the "macrophages": C1QA 6%, like monocytes.
So that rule was dropped. This blood reference has essentially no real myeloid
DCs, so DCs need another source. audit.json keeps the evidence
(dropped_rule_evidence).

reference_metadata.csv and NB1's y_all.npy are never edited (several
notebooks assert they agree).

Writes research/notebook-outputs/v5_labels/reference_labels_clean.csv.gz (cell,
class_original, class_clean, class_idx_clean, reason) and audit.json, and
y_clean.npy to Drive Data/Results/Tier1_v31/V5/.

    python research/notebooks/v5_labels.py      # from the repository root
    python research/notebooks/v5_labels.py --dry-run      # counts only, nothing written
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[2]
H5 = REPO.parent / "drive" / "Data" / "scRNA-seq" / "Blood_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad"
META = REPO / "service" / "model" / "runtime" / "reference_metadata.csv"
OUT = REPO / "research" / "notebook-outputs" / "v5_labels"
DRIVE_OUT = REPO.parent / "drive" / "Data" / "Results" / "Tier1_v31" / "V5"
CD8, NK, NKT = "cd8-positive, alpha-beta t cell", "natural killer cell", "mature nk t cell"
MONO, MDC, PDC, MAC = "monocyte", "myeloid dendritic cell", "plasmacytoid dendritic cell", "macrophage"
PDC_MARKERS, CDC_MARKERS = ("LILRA4", "CLEC4C", "IL3RA"), ("CD1C", "FCER1A", "CLEC10A", "CLEC9A")
REPORT_MARKERS = ("CD3D", "CD3G", "TRAC", "CD8A", "CD8B", "KLRF1", "NCAM1", "FCGR3A", "NKG7", "GNLY",
                  "CD14", "LYZ", "CD1C", "FCER1A", "CLEC10A", "CLEC9A", "LILRA4", "IL3RA", "HLA-DQA1", "C1QA", "C1QB", "APOE")
REPORT_CLASSES = (CD8, NK, NKT, MONO, MDC, PDC, MAC, "classical monocyte", "cd4-positive, alpha-beta t cell")


def obs_column(f, key: str) -> np.ndarray:
    v = f["obs"][key]
    return v["categories"][:].astype(str)[v["codes"][:]] if isinstance(v, h5py.Group) else v[:].astype(str)


def clean_labels(original: np.ndarray, free: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The rules above: (cleaned label, reason; empty where unchanged)."""
    fl = np.char.lower(free.astype(str))
    clean, reason = original.copy(), np.full(len(original), "", dtype=object)

    def move(mask, label, why):
        mask = mask & (clean != label)
        clean[mask], reason[mask] = label, why

    block = np.isin(original, [CD8, NK, NKT])
    move(block & np.isin(fl, ["natural killer cell", "nk cell"]), NK, "free_annotation: natural killer cell")
    move(block & (np.char.find(fl, "nk t") >= 0), NKT, "free_annotation: nk t cell")
    move(block & (np.char.find(fl, "cd8") >= 0), CD8, "free_annotation: cd8 t cell")
    return clean, reason


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print the counts; write nothing")
    dry = parser.parse_args().dry_run
    meta = pd.read_csv(META)
    with h5py.File(H5, "r") as f:
        ids = f["obs"][f["obs"].attrs["_index"]][:].astype(str)
        onto, free = obs_column(f, "cell_ontology_class"), obs_column(f, "free_annotation")
        donor, method, cluster = obs_column(f, "donor"), obs_column(f, "method"), obs_column(f, "scvi_leiden_res05_tissue")
        sym = f["var"]["gene_symbol"]
        sym = sym["categories"][:].astype(str)[sym["codes"][:]] if isinstance(sym, h5py.Group) else sym[:].astype(str)
        X = sp.csr_matrix((f["X"]["data"][:], f["X"]["indices"][:], f["X"]["indptr"][:]), shape=tuple(f["X"].attrs["shape"]))
    if list(ids) != meta["cell"].tolist() or list(onto) != meta["class_name"].tolist():
        raise SystemExit("the h5ad's cells or labels are not reference_metadata.csv's")
    first: dict[str, int] = {}
    for j, g in enumerate(s.upper() for s in sym):
        first.setdefault(g, j)
    genes = [g for g in dict.fromkeys(PDC_MARKERS + CDC_MARKERS + REPORT_MARKERS) if g in first]
    E = X[:, [first[g] for g in genes]].toarray()  # log-normalised (the h5ad's X)
    col = {g: i for i, g in enumerate(genes)}
    original = meta["class_name"].to_numpy()
    clean, reason = clean_labels(original, free)

    changed = clean != original
    transitions = pd.crosstab(pd.Series(original[changed], name="from"), pd.Series(clean[changed], name="to"))
    counts = {c: {"before": int((original == c).sum()), "after": int((clean == c).sum())} for c in REPORT_CLASSES}
    print(f"relabelled {int(changed.sum())} cells"); print(transitions.to_string())
    print(json.dumps(counts, indent=1))
    if dry:
        return

    def detection(labels):
        return {c: {g: round(100 * float((E[labels == c, col[g]] > 0).mean()), 1) for g in REPORT_MARKERS if g in col}
                for c in REPORT_CLASSES if (labels == c).any()}

    def cluster_mix(labels):
        frame = pd.crosstab(pd.Series(cluster, name="cluster"), pd.Series(labels, name="label"))[[CD8, NK, NKT]]
        frame = frame[frame.sum(1) >= 50]
        return {str(k): {c: int(v) for c, v in row.items()} for k, row in frame.iterrows()}

    names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    idx = np.array([names.index(c) for c in clean])
    OUT.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame({"cell": meta["cell"], "class_original": original, "class_clean": clean, "class_idx_clean": idx,
                          "reason": reason})
    path = OUT / "reference_labels_clean.csv.gz"
    table.to_csv(path, index=False, lineterminator="\n", compression={"method": "gzip", "mtime": 0})
    DRIVE_OUT.mkdir(parents=True, exist_ok=True)
    np.save(DRIVE_OUT / "y_clean.npy", idx.astype(np.int64))
    audit = {
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"),
        "h5ad": {"path": "Drive Data/scRNA-seq/" + H5.name, "bytes": H5.stat().st_size},
        "labels_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "y_clean_sha256": hashlib.sha256((DRIVE_OUT / "y_clean.npy").read_bytes()).hexdigest(),
        "relabelled": int(changed.sum()),
        "transitions": {f"{a} -> {b}": int(transitions.loc[a, b]) for a in transitions.index for b in transitions.columns if transitions.loc[a, b]},
        "class_counts": counts,
        "relabelled_by_donor": {k: int(v) for k, v in pd.Series(donor[changed]).value_counts().items()},
        "relabelled_by_method": {k: int(v) for k, v in pd.Series(method[changed]).value_counts().items()},
        "marker_detection_pct": {"before": detection(original), "after": detection(clean)},
        "scvi_cluster_mix_t_nk": {"before": cluster_mix(original), "after": cluster_mix(clean)},
        "dropped_rule_evidence": {  # the amendment: cells labelled monocyte, by free_annotation, against references
            name: {g: round(100 * float((E[m, col[g]] > 0).mean()), 1) for g in REPORT_MARKERS if g in col}
            for name, m in (("monocyte, free_annotation dendritic cell", (original == MONO) & (np.char.lower(free.astype(str)) == "dendritic cell")),
                            ("monocyte, free_annotation macrophage", (original == MONO) & (np.char.lower(free.astype(str)) == "macrophage")),
                            ("monocyte, other", (original == MONO) & ~np.isin(np.char.lower(free.astype(str)), ["dendritic cell", "macrophage"])),
                            ("plasmacytoid dendritic cell", original == PDC), ("macrophage", original == MAC))},
    }
    (OUT / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", newline="\n")
    print(f"wrote {path} and {OUT / 'audit.json'}; {DRIVE_OUT / 'y_clean.npy'}")


if __name__ == "__main__":
    main()
