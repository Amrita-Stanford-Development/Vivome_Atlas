"""Candidate v5.5 (owner, 2026-10-26; side-tests amendment 23): v5.4's
members, centroids and best-guess layer, its answers recalibrated with the
Allen atlas's cells of donors held out of v5.4's training
(research/notebooks/v5_build.py build --variant v5.5). Development data
only; the gates are fixed here, before the build, and nothing is tuned.

Why: v5.4 missed on its answers (Fulcher committed 53.56, bar 86.57; run
history entry 66). Its calibration suite held no myeloid DC, pDC, CMP or
regulatory T cell, so those classes took the marginal threshold and joined
sets from a 5% probability. Its other miss, the out-of-reference AUROC
(0.7575, bar 0.7598), is the best guess's probability on Furtwängler 2025's
progenitors, which v5.4 now often calls progenitors (11.89%, from 0.32%):
the recalibration moves it only through the temperatures. The owner kept
that gate unchanged (2026-10-26).

Measures, as v54_gates.py does (its figures and uploads):
- RNA, the 11 check donors of v5_build.py's split: nearest-centroid recall
  per class, each version's members the reference's way under its own
  class-balanced statistics; and, from v5.5's build record, each class's
  conformal coverage on the 60 check uploads;
- RNA, Tabula Sapiens: the calibration suite's top-1 on its 240 uploads
  under v5.5's temperatures (the build record), against v3.1's members'
  62.448;
- protein, through pipeline.run_projection as served, for v4.1, v5.4 and
  v5.5: Fulcher 2026, PBMC240, both SCoPE2 versions, Furtwängler 2025,
  PXD056050's sorted pools, and the out-of-reference AUROC.

Self-check first, else stop: v4.1 reproduces Fulcher 69.05 and PBMC240
92.31, and v5.4 its Fulcher 76.00 and committed 53.56, within 0.01, and
its AUROC 0.7575 within 0.0001.

GO for v5.5 (development evidence), all of v5.4's gates with v5.4's bars,
and one more:
1. the check donors: myeloid DC recall at least 50% and pDC recall at
   least 50%;
2. the calibration suite's top-1 (Tabula Sapiens's uploads) at least 60.448;
3. Fulcher balanced accuracy at least v4.1 + 2;
4. PXD056050, balanced accuracy over its five sorted groups at least v4.1's;
5. PBMC240 lymphoid recall at least v4.1 - 2;
6. Fulcher committed share at least v4.1 - 2, and correct when committed at
   least v4.1 - 1;
7. out-of-reference AUROC at least v4.1 - 0.03;
8. new: on the check uploads, coverage at least 85% for each of myeloid DC,
   pDC, CMP and regulatory T (the true class in the conformal set, before
   the best guess joins it; the target is 90%).
Reported: Fulcher's DC and CD8 T recall, the check donors' recall and
coverage of every class, PXD056050's calls, SCoPE2, Furtwängler's
progenitor share. A GO makes v5.5 a frozen candidate for the sorted CD4/CD8
test (its protocol's next amendment); it is not served before then, and the
evaluation block it writes keeps the service refusing v5.5 either way until
then.

Writes rules.json (first), development.json, decision.json and
spec_block.json into its own folder of research/notebook-outputs (OUT).

    python research/notebooks/v55_gates.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import allen_rows  # noqa: E402
import gene_weights  # noqa: E402  (PXD056050's upload and its figures)
import v53_gates  # noqa: E402  (the development uploads and their figures)
import v54_gates  # noqa: E402  (heldout_recall)
import v5_build  # noqa: E402  (the held-out donors' split)
from service import config  # noqa: E402
from service.pipeline import fusion, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v55_gates"
BUILD_RECORD = REPO / "research" / "notebook-outputs" / "v55_build" / "build_record.json"
VERSION = "v5.5"
V41_EXPECTED = {"fulcher2026": 69.05, "pbmc240": 92.31}
V54_EXPECTED = {"fulcher2026": 76.00, "answers_committed": 53.56, "out_of_reference_auroc": 0.7575}
TOL, TOL_AUROC = 0.01, 0.0001
V31_SUITE_TOP1 = 62.448  # research/notebook-outputs/v5_build/reproduce.json
MDC, PDC = "myeloid dendritic cell", "plasmacytoid dendritic cell"
GO = {**v54_gates.GO, "check_coverage_min": 85.0}
COVERAGE_CLASSES = v5_build.ALLEN_TARGETS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "decision.json").exists():
        raise SystemExit("v5.5's gates were run; they are read once")
    record = json.loads(BUILD_RECORD.read_text())
    write(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                               "go": GO, "coverage_classes": list(COVERAGE_CLASSES), "v41_expected": V41_EXPECTED,
                               "v54_expected": V54_EXPECTED, "tolerance": TOL, "tolerance_auroc": TOL_AUROC,
                               "build_record_sha256": sha256(BUILD_RECORD)})
    t0 = time.time()
    bundles = {"v4.1": pipeline.load_bundle("v4.1"),
               "v5.4": fusion.V4Bundle.load(require_evaluation=False, version="v5.4"),
               VERSION: fusion.V4Bundle.load(require_evaluation=False, version=VERSION)}
    names = bundles["v4.1"].class_names
    dev, prob = {}, {}

    rows = np.load(allen_rows.ROWS, allow_pickle=True)
    calib_rows, _, check_donors = v5_build.allen_split(rows["donor_hold"])
    if check_donors != record["donors"]["check"]:
        raise SystemExit("the check donors are not the ones v5.5's build kept out")
    X, y = rows["X_hold"][~calib_rows], rows["y_hold"][~calib_rows]
    for version, bundle in bundles.items():
        dev.setdefault("allen_check_donors", {})[version] = v54_gates.heldout_recall(version, bundle, X, y, names)
    print("allen_check_donors", json.dumps({v: {c: r["recall"] for c, r in d.items()}
                                            for v, d in dev["allen_check_donors"].items()}), flush=True)
    dev["allen_check_coverage"] = record["check"]
    dev["calibration_suite_top1"] = {"v3.1 members": V31_SUITE_TOP1, VERSION: record["suite_top1_accuracy"],
                                     f"{VERSION}, Allen uploads": record["suite_top1_accuracy_allen"]}

    table = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    lineage = table.groupby("class_name")["lineage"].first().to_dict()
    expected = v53_gates.expected_levels()
    for name, raw, info in v53_gates.uploads():
        for version, bundle in bundles.items():
            fig, p = v53_gates.figures(name, pipeline.run_projection(bundle, raw), info, raw, names, lineage, expected)
            dev.setdefault(name, {})[version] = fig
            prob[(name, version)] = p
        print(name, json.dumps(dev[name]), f"({time.time() - t0:.0f}s)", flush=True)
    raw, groups = gene_weights.pxd056050_upload()
    for version, bundle in bundles.items():
        dev.setdefault("pxd056050", {})[version] = gene_weights.pool_figures(pipeline.run_projection(bundle, raw), groups, names)
    print("pxd056050", {v: dev["pxd056050"][v]["balanced_accuracy"] for v in dev["pxd056050"]}, flush=True)
    for version in bundles:
        a, b = prob[("fulcher2026", version)], prob[("furtwangler2025", version)]
        dev.setdefault("out_of_reference_auroc", {})[version] = round(
            float(roc_auc_score(np.r_[np.ones(len(a)), np.zeros(len(b))], np.nan_to_num(np.r_[a, b]))), 4)
    write(OUT / "development.json", dev)

    f, oor = dev["fulcher2026"], dev["out_of_reference_auroc"]
    got = {"v4.1 fulcher2026": (f["v4.1"]["balanced_accuracy_6_types"], V41_EXPECTED["fulcher2026"], TOL),
           "v4.1 pbmc240": (dev["pbmc240"]["v4.1"]["lymphoid_recall"], V41_EXPECTED["pbmc240"], TOL),
           "v5.4 fulcher2026": (f["v5.4"]["balanced_accuracy_6_types"], V54_EXPECTED["fulcher2026"], TOL),
           "v5.4 answers_committed": (f["v5.4"]["answers_committed"], V54_EXPECTED["answers_committed"], TOL),
           "v5.4 out_of_reference_auroc": (oor["v5.4"], V54_EXPECTED["out_of_reference_auroc"], TOL_AUROC)}
    self_check = {k: {"expected": e, "got": g, "passed": abs(g - e) <= t} for k, (g, e, t) in got.items()}
    if not all(v["passed"] for v in self_check.values()):
        write(OUT / "decision.json", {"self_check": self_check, "go": None,
                                      "reason": "v4.1 or v5.4 did not reproduce its development figures"})
        raise SystemExit(f"STOP: a version did not reproduce its figures: {self_check}")

    h, p, x, cov = dev["allen_check_donors"][VERSION], dev["pbmc240"], dev["pxd056050"], record["check"]["by_class"]
    checks = {
        "check_donors_dc_recall": (h.get(MDC, {}).get("recall", 0) >= GO["heldout_dc_recall_min"]
                                   and h.get(PDC, {}).get("recall", 0) >= GO["heldout_dc_recall_min"]),
        "suite_top1": dev["calibration_suite_top1"][VERSION] >= GO["suite_top1_min"],
        "fulcher_gain": f[VERSION]["balanced_accuracy_6_types"] >= f["v4.1"]["balanced_accuracy_6_types"] + GO["fulcher_gain_min"],
        "pxd056050_no_loss": x[VERSION]["balanced_accuracy"] >= x["v4.1"]["balanced_accuracy"] - GO["pxd056050_drop_max"],
        "pbmc240_guardrail": p[VERSION]["lymphoid_recall"] >= p["v4.1"]["lymphoid_recall"] - GO["pbmc240_drop_max"],
        "fulcher_committed": f[VERSION]["answers_committed"] >= f["v4.1"]["answers_committed"] - GO["committed_drop_max"],
        "fulcher_correct_when_committed": (f[VERSION]["answers_correct_when_committed"]
                                           >= f["v4.1"]["answers_correct_when_committed"] - GO["correct_drop_max"]),
        "out_of_reference_auroc": oor[VERSION] >= oor["v4.1"] - GO["auroc_drop_max"],
        "check_coverage": all(cov.get(c, {}).get("coverage", 0) >= GO["check_coverage_min"] for c in COVERAGE_CLASSES),
    }
    go = all(checks.values())
    decision = {"finished": datetime.now().isoformat(timespec="seconds"), "self_check": self_check,
                "checks": checks, "go": go, "seconds": round(time.time() - t0)}
    write(OUT / "decision.json", decision)
    status = "development gates passed" if go else "development gates missed"
    write(OUT / "spec_block.json", {"evaluation": {
        "status": status, "record": (OUT / "decision.json").relative_to(REPO).as_posix(),
        "note": "not served: a development result; the sorted CD4/CD8 cells are the test"}})
    print(json.dumps(decision, indent=1))


if __name__ == "__main__":
    main()
