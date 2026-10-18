"""Track I, Stage 2 (research/organ-references.md): the large intestine's
label audit, before any colon model is trained.

Tabula Sapiens annotated each donor separately, and the colon's classes
follow donors closely (Stage 1's class-by-donor table: TSP26 has 593
"best4+" cells but 3 enterocytes and no goblet cells; TSP2 holds most stem
cells). This checks, on RNA only, whether each class means the same cells
in every donor:
- for each class and donor with at least 20 cells, the share of cells
  expressing each canonical marker (any count above zero) and its mean
  log-normalised expression;
- the free_annotation labels behind each class, per donor;
- for every class, which class's marker profile each donor's cells match
  best (correlation of the marker means), so a donor whose "best4+" cells
  look like enterocytes stands out.
No protein data is read. The markers were fixed before the run, from the
standard colon atlases' marker lists (below).

Writes research/notebook-outputs/li_labels/:
- markers_by_class_donor.csv: share expressing and mean, per marker;
- free_annotation_by_class_donor.csv;
- audit.json: the best-matching class per (class, donor), and every
  (class, donor) whose best match is another class.

    python research/notebooks/li_labels.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from organ_reference import data, labels  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "li_labels"
MIN_CELLS = 20
MARKERS = {
    "intestinal crypt stem cell of colon": ["LGR5", "OLFM4", "ASCL2", "SMOC2"],
    "transit amplifying cell of colon": ["MKI67", "TOP2A", "PCNA"],
    "enterocyte of epithelium of large intestine": ["CA1", "CA2", "SLC26A3", "AQP8", "CEACAM7", "GUCA2A"],
    "best4+ intestinal epithelial cell, human": ["BEST4", "OTOP2", "CA7", "SPIB", "GUCA2B"],
    "large intestine goblet cell": ["MUC2", "TFF3", "CLCA1", "FCGBP", "ZG16", "SPINK4"],
    "paneth cell of colon": ["DEFA5", "DEFA6", "REG3A", "ITLN2", "REG4"],
    "tuft cell of colon": ["POU2F3", "TRPM5", "IRAG2", "SH2D6"],
    "enteroendocrine cell": ["CHGA", "CHGB", "PYY", "GCG", "TPH1"],
    "cd4-positive, alpha-beta t cell": ["CD3E", "CD4", "IL7R"],
    "cd8-positive, alpha-beta t cell": ["CD3E", "CD8A", "CD8B"],
    "gamma-delta t cell": ["TRDC", "TRGC1", "TRGC2"],
    "regulatory t cell": ["FOXP3", "IL2RA", "CTLA4"],
    "innate lymphoid cell": ["NCAM1", "KLRD1", "GNLY", "KIT"],
    "b cell": ["MS4A1", "CD79A", "CD19"],
    "plasma cell": ["JCHAIN", "MZB1", "IGHA1"],
    "colon macrophage": ["CD68", "C1QA", "C1QB", "APOE"],
    "monocyte": ["CD14", "FCN1", "S100A8"],
    "myeloid leukocyte": ["LYZ", "CD1C", "CLEC10A", "S100A9"],
    "mast cell": ["TPSAB1", "CPA3", "KIT"],
    "fibroblast": ["COL1A1", "DCN", "PDGFRA", "LUM"],
    "myofibroblast cell": ["ACTA2", "MYH11", "DES", "TAGLN"],
    "colon endothelial cell": ["PECAM1", "VWF", "CDH5"],
    "enteroglial cell": ["S100B", "PLP1", "SOX10"],
}


def main() -> None:
    cfg = data.load_organ("large_intestine")
    table, names = labels.build(cfg, apply_drop=False)
    free = data.read_obs(data.resolve(cfg["rna"]), ["free_annotation"])["free_annotation"]
    table["free_annotation"] = free.to_numpy()
    genes = sorted({g for gs in MARKERS.values() for g in gs})
    X = data.load_rna(data.resolve(cfg["rna"]), genes)
    rows = []
    for (cls, donor), idx in table.groupby(["class_name", "donor"]).groups.items():
        if len(idx) < MIN_CELLS:
            continue
        sub = X[np.asarray(idx)]
        for j, g in enumerate(genes):
            rows.append({"class_name": cls, "donor": donor, "cells": len(idx), "gene": g,
                         "share_expressing": round(float((sub[:, j] > 0).mean()), 4), "mean": round(float(sub[:, j].mean()), 4)})
    markers = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    markers.to_csv(OUT / "markers_by_class_donor.csv", index=False, lineterminator="\n")
    fa = table.groupby(["class_name", "donor", "free_annotation"]).size().rename("cells").reset_index()
    fa.to_csv(OUT / "free_annotation_by_class_donor.csv", index=False, lineterminator="\n")

    # each class's marker signature: the mean of its own markers, z-scored over all (class, donor) groups
    wide = markers.pivot_table(index=["class_name", "donor"], columns="gene", values="mean")
    z = (wide - wide.mean()) / (wide.std() + 1e-9)
    score = pd.DataFrame({c: z[MARKERS[c]].mean(1) for c in names})
    best = score.idxmax(1)
    counts = table.groupby(["class_name", "donor"]).size()
    audit, mismatches = {}, []
    for (cls, donor), b in best.items():
        top = score.loc[(cls, donor)].sort_values(ascending=False)
        entry = {"cells": int(counts[(cls, donor)]), "best_match": b, "own_score": round(float(top[cls]), 3),
                 "top3": {k: round(float(v), 3) for k, v in top.head(3).items()}}
        audit.setdefault(cls, {})[donor] = entry
        if b != cls:
            mismatches.append({"class_name": cls, "donor": donor, **entry})
    (OUT / "audit.json").write_bytes((json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"), "min_cells": MIN_CELLS, "markers": MARKERS,
        "mismatches": mismatches, "by_class": audit}, indent=2) + "\n").encode("utf-8"))
    print(f"{len(best)} (class, donor) groups with at least {MIN_CELLS} cells; {len(mismatches)} best match another class:")
    for m in mismatches:
        print(f"  {m['class_name']} / {m['donor']} ({m['cells']} cells): best {m['best_match']}; top3 {m['top3']}")


if __name__ == "__main__":
    main()
