"""Goal 2: a second design for the narrow-upload check, after the first failed
its pass rule (research/notebooks/narrow_upload_calibration.py: a principal-
component structure score flagged 1 of Fulcher's 6 single-type uploads). Rules
fixed here before the run; development and calibration data only. This is a
second look at the same protein development data, and is recorded as such.

The score is the model's own: the share of an upload's cells, among those
with at least the coverage floor's observed genes, that v3.1's answers commit
on (v4.1's answers are v3.1's). Fulcher's single-type uploads committed on
30-46% of cells against 85-92% mixed (research/notebook-run-history.md, entry
35), and NB3b saw single-type RNA uploads abstain far more than broad ones.

1. Simulated RNA: the calibration suite's uploads from v4.1's development
   cache (research/notebooks/v41_core.py; te_cal cells, 240 uploads plus 60
   single-type ones). The threshold is the 5th percentile of the committed
   share among uploads of five or more types (the mixed and PBMC-like
   groups); the share flagged is reported per group.
2. Protein development data, as served by v4.1, with the first design's pass
   rule unchanged: not flagged, Fulcher's full upload, PBMC240, DS18 (three
   searches) and DS19; flagged, at least 5 of Fulcher's 6 single-type
   uploads. Reported without a rule: Fulcher's pairs, both SCoPE2 versions,
   Furtwangler 2025.
If the rule fails, no check is served.

Writes research/notebook-outputs/narrow_upload/committed.json.

    python research/notebooks/narrow_upload_committed.py      # from the repository root
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v41_core as core  # noqa: E402
from benchmark import baselines_v31, datasets  # noqa: E402
from service import config  # noqa: E402
from service.pipeline import alignment, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "narrow_upload"
PUBLIC = REPO / "data" / "incoming" / "public_sets" / "PXD070599_PBMC" / "extracted"
BROAD = ("mixed", "pbmc")


def committed_share(cells: list[dict]) -> "float | None":
    counted = [c for c in cells if c.get("abstain_reason") != "coverage_too_low"]
    return float(np.mean([not c["abstained"] for c in counted])) if counted else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    calib, _, _, _ = core.load()  # cells with at least the coverage floor's genes
    by_upload = calib.groupby("upload").agg(group=("group", "first"), committed=("abstained", lambda a: float((~a.astype(bool)).mean())))
    threshold = round(float(np.percentile(by_upload.loc[by_upload["group"].isin(BROAD), "committed"], 5)), 4)
    flagged = {g: round(100 * float((d["committed"] < threshold).mean()), 1) for g, d in by_upload.groupby("group")}

    bundle = pipeline.load_bundle("v4.1")
    raw = datasets.load_fulcher2026_upload()
    labels = datasets.load_fulcher2026_labels().set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
    sub = lambda r, keep: alignment.RawMatrix(gene_names=r.gene_names,  # noqa: E731
                                               cell_ids=[c for c, k in zip(r.cell_ids, keep) if k], values=r.values[:, keep])
    uploads = [("Fulcher 2026, full", raw, "not flagged")]
    uploads += [(f"Fulcher 2026, {t} alone", sub(raw, labels == t), "flagged")
                for t in ("CD4T", "CD8T", "NK", "B", "monocyte", "DC")]
    uploads += [(f"Fulcher 2026, {' with '.join(p)}", sub(raw, np.isin(labels, p)), None)
                for p in (("CD4T", "CD8T"), ("B", "monocyte"))]
    uploads.append(("PBMC240", alignment.parse_matrix_csv(
        (REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), "not flagged"))
    for name, path in (("DS18 FAIMS Astral-Zoom", PUBLIC / "DS18" / "FAIMS_Astral-Zoom_MBR"),
                       ("DS18 FAIMS Astral", PUBLIC / "DS18" / "FAIMS_Astral_MBR"),
                       ("DS18 Standard Astral", PUBLIC / "DS18" / "Standard_Astral_MBR"), ("DS19", PUBLIC / "DS19" / "MBR")):
        uploads.append((name, alignment.parse_matrix_csv((path / "report.pg_matrix.tsv").read_text(encoding="utf-8")),
                        "not flagged"))
    uploads += [("SCoPE2, published", baselines_v31.scope2_raw(), None),
                ("SCoPE2, reprocessed", datasets.load_scope2_reprocessed_upload(), None),
                ("Furtwangler 2025", datasets.load_furtwangler2025_upload(), None)]
    prot = []
    for name, r, expected in uploads:
        share = committed_share(pipeline.run_projection(bundle, r)["cells"])
        prot.append({"upload": name, "cells": len(r.cell_ids), "committed": None if share is None else round(share, 4),
                     "flagged": bool(share is not None and share < threshold), "expected": expected})
        print(f"  {name:32} cells {len(r.cell_ids):5}  committed {share:.3f}  flagged {prot[-1]['flagged']}  "
              f"expected {expected}", flush=True)
    must_pass = [p for p in prot if p["expected"] == "not flagged"]
    must_flag = [p for p in prot if p["expected"] == "flagged"]
    passed = all(not p["flagged"] for p in must_pass) and sum(p["flagged"] for p in must_flag) >= 5
    summary = {"score": "share of cells committed, among those above the coverage floor (v3.1's answers)",
               "min_observed_genes": config.MIN_OBSERVED_GENES, "threshold": threshold,
               "threshold_rule": "5th percentile of broad simulated uploads",
               "simulated_flagged_pct_by_group": flagged,
               "simulated_median_by_group": {g: round(float(d["committed"].median()), 3) for g, d in by_upload.groupby("group")},
               "protein": prot, "pass_rule_met": bool(passed), "second_look": True}
    (OUT / "committed.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "protein"}, indent=1))


if __name__ == "__main__":
    main()
