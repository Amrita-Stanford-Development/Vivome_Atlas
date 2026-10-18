"""Track I (research/organ-references.md): an organ's label audit, before any
model of it is trained; research/notebooks/li_labels.py generalised, its
markers read from the organ file ("audit_markers", fixed before the run).

Tabula Sapiens annotated each donor separately. This checks, on RNA only,
whether each class means the same cells in every donor:
- for each class and donor with at least 20 cells, the share of cells
  expressing each canonical marker (any count above zero) and its mean;
- the free_annotation labels behind each class, per donor.
Decisions rest on the absolute shares: the colon's audit showed that a
z-scored signature flags ambient RNA (run history, entry 50). Every class
the atlas annotates is audited, dropped ones included.

Writes research/notebook-outputs/<organ>_labels/:
markers_by_class_donor.csv, free_annotation_by_class_donor.csv and
own_markers.csv (each class and donor's mean share over its own markers).

    python research/notebooks/organ_labels.py lung      # from the repository root
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

MIN_CELLS = 20


def main(organ: str) -> None:
    cfg = data.load_organ(organ)
    markers = cfg["audit_markers"]
    table, names = labels.build(cfg, apply_drop=False)
    table["free_annotation"] = data.read_obs(data.resolve(cfg["rna"]), ["free_annotation"])["free_annotation"].to_numpy()
    rna = set(data.rna_genes(data.resolve(cfg["rna"])))
    genes = sorted({g for gs in markers.values() for g in gs if g in rna})
    missing = sorted({g for gs in markers.values() for g in gs} - set(genes))
    X = data.load_rna(data.resolve(cfg["rna"]), genes)
    rows = []
    for (cls, donor), idx in table.groupby(["class_name", "donor"]).groups.items():
        if len(idx) < MIN_CELLS:
            continue
        sub = X[np.asarray(idx)]
        for j, g in enumerate(genes):
            rows.append({"class_name": cls, "donor": donor, "cells": len(idx), "gene": g,
                         "share_expressing": round(float((sub[:, j] > 0).mean()), 4), "mean": round(float(sub[:, j].mean()), 4)})
    m = pd.DataFrame(rows)
    out = REPO / "research" / "notebook-outputs" / f"{organ}_labels"
    out.mkdir(parents=True, exist_ok=True)
    m.to_csv(out / "markers_by_class_donor.csv", index=False, lineterminator="\n")
    table.groupby(["class_name", "donor", "free_annotation"]).size().rename("cells").reset_index().to_csv(
        out / "free_annotation_by_class_donor.csv", index=False, lineterminator="\n")
    own = []
    for (cls, donor), g in m.groupby(["class_name", "donor"]):
        mk = [x for x in markers.get(cls, []) if x in genes]
        own.append({"class_name": cls, "donor": donor, "cells": int(g["cells"].iloc[0]),
                    "own_markers_mean_share": round(float(g[g.gene.isin(mk)]["share_expressing"].mean()), 4) if mk else None})
    pd.DataFrame(own).to_csv(out / "own_markers.csv", index=False, lineterminator="\n")
    data.save_json(out / "audit.json", {"script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                         "run": datetime.now().isoformat(timespec="seconds"), "organ": organ,
                                         "min_cells": MIN_CELLS, "markers": markers, "markers_not_in_atlas": missing})
    print(f"{organ}: {len(m.groupby(['class_name', 'donor']))} (class, donor) groups; markers not in the atlas: {missing}")


if __name__ == "__main__":
    main(sys.argv[1])
