"""v5.1 (research/todo.md, Track H): v5's cleaned reference labels with the
NK T class folded into NK.

Why: v5's diagnosis (research/notebooks/v5_diagnose.py) found that v5's
new NK errors go to "mature nk t cell" (34% of NK cells in multi-type
uploads of the calibration suite). By markers that class is NK, not T.
After v5's cleaning (research/notebook-outputs/v5_labels/audit.json), its
cells express:
- CD3D 6.6%, CD3G 5.8%, TRAC 13.4% (cleaned CD8 T: 66%, 63%, 55%);
- KLRF1 92.1% and NCAM1 71.4% (NK: 94% and 61%).
Before cleaning it was the same: CD3D 7.4%, KLRF1 86.1%. The decision rests
on the reference's markers; no protein label is read.

Rule, fixed before the run: every cell whose v5 cleaned label is "mature nk
t cell" becomes "natural killer cell". Nothing else changes. The class stays
in the 22-class set and the hierarchy, with no cells: its centroid and class
mean are zero, so it is never chosen. The service already treats a class
without cells so (fusion.class_balanced_stats, class_means,
masked_pearson).

Reads research/notebook-outputs/v5_labels/reference_labels_clean.csv.gz;
writes research/notebook-outputs/v51_labels/reference_labels_v51.csv.gz
(same columns; reason "v5.1: NK T folded into NK" where it changed) and
audit.json.

    python research/notebooks/v51_labels.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
V5_LABELS = REPO / "research" / "notebook-outputs" / "v5_labels" / "reference_labels_clean.csv.gz"
OUT = REPO / "research" / "notebook-outputs" / "v51_labels"
NKT, NK = "mature nk t cell", "natural killer cell"


def main() -> None:
    table = pd.read_csv(V5_LABELS, keep_default_na=False)
    names = (table.drop_duplicates("class_idx_clean").set_index("class_idx_clean")["class_clean"].to_dict())
    nk_idx = next(k for k, v in names.items() if v == NK)
    fold = (table["class_clean"] == NKT).to_numpy()
    out = table.copy()
    out.loc[fold, "class_clean"] = NK
    out.loc[fold, "class_idx_clean"] = nk_idx
    out.loc[fold, "reason"] = [f"{r}; v5.1: NK T folded into NK" if r else "v5.1: NK T folded into NK"
                               for r in out.loc[fold, "reason"]]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "reference_labels_v51.csv.gz"
    out.to_csv(path, index=False, lineterminator="\n", compression={"method": "gzip", "mtime": 0})
    audit = {
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"),
        "from": {"labels": "research/notebook-outputs/v5_labels/reference_labels_clean.csv.gz",
                 "sha256": hashlib.sha256(V5_LABELS.read_bytes()).hexdigest()},
        "labels_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "folded": int(fold.sum()),
        "folded_by_original_label": {k: int(v) for k, v in table.loc[fold, "class_original"].value_counts().items()},
        "class_counts": {c: {"v5": int((table["class_clean"] == c).sum()), "v5.1": int((out["class_clean"] == c).sum())}
                         for c in (NKT, NK, "cd8-positive, alpha-beta t cell")},
    }
    (OUT / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", newline="\n")
    print(json.dumps(audit, indent=1))


if __name__ == "__main__":
    main()
