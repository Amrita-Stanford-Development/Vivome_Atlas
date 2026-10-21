"""Candidate v5.4 (owner, 2026-10-21; step 2 of research/reference-data-search.md,
route B of run history entry 65): v4.1's rule on five V2 members trained
with the Allen Human Immune Health Atlas's cells of its training donors
added to the training rows (research/notebooks/allen_rows.py), on the
original labels, those cells also counted in every centroid and in v4.1's
class means (research/notebooks/v5_train.py clean --variant v5.4;
research/notebooks/v5_build.py build --variant v5.4). Development data
only; the gates are fixed here, before the members are trained, and
nothing is tuned.

Why: the encoder trained on 1 myeloid dendritic cell and 29 pDCs never
learned a dendritic cell: the Allen atlas's DCs land on monocytes and T
cells under v4.1's members (entry 65). The Allen atlas has thousands of DCs
from 108 donors, and its cells of every other class go in beside them so
that the atlas cannot stand in for the class.

Measures:
- RNA, the Allen donors held out of training (allen_rows.py's split):
  nearest-centroid recall per class, each version's members embedding the
  cells the reference's way under its own class-balanced statistics,
  against its own class-balanced centroids;
- RNA, Tabula Sapiens: the calibration suite's top-1 accuracy (the build
  record), against v3.1's members' 62.448 (v5_build.py's reproduction);
- protein, through pipeline.run_projection as served, for v4.1 and v5.4:
  Fulcher 2026, PBMC240, both SCoPE2 versions and Furtwängler 2025 (as
  v53_gates.py reads them), PXD056050's sorted pools (as gene_weights.py
  reads them), and the out-of-reference AUROC.

Self-check first: v4.1 reproduces Fulcher 69.05 and PBMC240 92.31 within
0.01, else stop.

GO for v5.4 (development evidence), all of:
1. the held-out Allen donors: myeloid DC recall at least 50% and pDC recall
   at least 50% (the members learned dendritic cells beyond their training
   donors);
2. the calibration suite's top-1 at least 60.448 (v3.1's minus 2);
3. Fulcher balanced accuracy at least v4.1 + 2;
4. PXD056050, balanced accuracy over its five sorted groups at least v4.1's;
5. PBMC240 lymphoid recall at least v4.1 - 2;
6. Fulcher committed share at least v4.1 - 2, and correct when committed at
   least v4.1 - 1;
7. out-of-reference AUROC at least v4.1 - 0.03.
Reported: Fulcher's DC and CD8 T recall, the held-out Allen recall of every
class, PXD056050's calls, SCoPE2 and Furtwängler. A GO makes v5.4 a frozen
candidate for the sorted CD4/CD8 test (its protocol's next amendment); it is
not served before then, and the evaluation block it writes keeps the
service refusing v5.4 either way until then.

Writes rules.json (first), development.json, decision.json and
spec_block.json into its own folder of research/notebook-outputs (OUT).

    python research/notebooks/v54_gates.py      # from the repository root
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
from service import config  # noqa: E402
from service.pipeline import fusion, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v54_gates"
BUILD_RECORD = REPO / "research" / "notebook-outputs" / "v54_build" / "build_record.json"
VERSION = "v5.4"
V41_EXPECTED = {"fulcher2026": 69.05, "pbmc240": 92.31}
TOL = 0.01
V31_SUITE_TOP1 = 62.448  # research/notebook-outputs/v5_build/reproduce.json
MDC, PDC = "myeloid dendritic cell", "plasmacytoid dendritic cell"
GO = {"heldout_dc_recall_min": 50.0, "suite_top1_min": V31_SUITE_TOP1 - 2.0, "fulcher_gain_min": 2.0,
      "pxd056050_drop_max": 0.0, "pbmc240_drop_max": 2.0, "committed_drop_max": 2.0, "correct_drop_max": 1.0,
      "auroc_drop_max": 0.03}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def heldout_recall(version: str, bundle, X: np.ndarray, y: np.ndarray, names: list) -> dict:
    """Nearest class-balanced centroid, member by member, the reference's way
    under the version's own class-balanced statistics; recall per class over
    all members' calls."""
    stats = np.load(fusion.data_dir(version) / "class_balanced_stats.npz")
    values = ((X.astype(np.float32) - stats["mu"]) / (stats["sd"] + 1e-8)).astype(np.float32)
    ones = np.ones_like(values)
    unit = lambda M: M / np.linalg.norm(M, axis=-1, keepdims=True)  # noqa: E731
    calls = np.array([(unit(np.asarray(m.encoder_handle.encode(values, ones), dtype=np.float64))
                       @ unit(np.asarray(m.centroids, dtype=np.float64)).T).argmax(1) for m in bundle.members])
    out = {}
    for c in np.unique(y):
        at = y == c
        out[names[c]] = {"n": int(at.sum()), "recall": round(100 * float((calls[:, at] == c).mean()), 2)}
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "decision.json").exists():
        raise SystemExit("v5.4's gates were run; they are read once")
    write(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                               "go": GO, "v41_expected": V41_EXPECTED, "tolerance": TOL})
    t0 = time.time()
    bundles = {"v4.1": pipeline.load_bundle("v4.1"), VERSION: fusion.V4Bundle.load(require_evaluation=False, version=VERSION)}
    names = bundles["v4.1"].class_names
    dev, prob = {}, {}

    rows = np.load(allen_rows.ROWS)
    for version, bundle in bundles.items():
        dev.setdefault("allen_heldout", {})[version] = heldout_recall(version, bundle, rows["X_hold"], rows["y_hold"], names)
    print("allen_heldout", json.dumps({v: {c: r["recall"] for c, r in d.items()} for v, d in dev["allen_heldout"].items()}),
          flush=True)
    dev["calibration_suite_top1"] = {"v3.1 members": V31_SUITE_TOP1,
                                     VERSION: json.loads(BUILD_RECORD.read_text())["suite_top1_accuracy"]}

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

    got = {"fulcher2026": dev["fulcher2026"]["v4.1"]["balanced_accuracy_6_types"],
           "pbmc240": dev["pbmc240"]["v4.1"]["lymphoid_recall"]}
    self_check = {k: {"expected": V41_EXPECTED[k], "got": got[k], "passed": abs(got[k] - V41_EXPECTED[k]) <= TOL}
                  for k in V41_EXPECTED}
    if not all(v["passed"] for v in self_check.values()):
        write(OUT / "decision.json", {"self_check": self_check, "go": None,
                                      "reason": "v4.1 did not reproduce its development figures"})
        raise SystemExit(f"STOP: v4.1 did not reproduce its figures: {self_check}")

    h, f, p, x, oor = (dev["allen_heldout"][VERSION], dev["fulcher2026"], dev["pbmc240"], dev["pxd056050"],
                       dev["out_of_reference_auroc"])
    checks = {
        "heldout_dc_recall": (h.get(MDC, {}).get("recall", 0) >= GO["heldout_dc_recall_min"]
                              and h.get(PDC, {}).get("recall", 0) >= GO["heldout_dc_recall_min"]),
        "suite_top1": dev["calibration_suite_top1"][VERSION] >= GO["suite_top1_min"],
        "fulcher_gain": f[VERSION]["balanced_accuracy_6_types"] >= f["v4.1"]["balanced_accuracy_6_types"] + GO["fulcher_gain_min"],
        "pxd056050_no_loss": x[VERSION]["balanced_accuracy"] >= x["v4.1"]["balanced_accuracy"] - GO["pxd056050_drop_max"],
        "pbmc240_guardrail": p[VERSION]["lymphoid_recall"] >= p["v4.1"]["lymphoid_recall"] - GO["pbmc240_drop_max"],
        "fulcher_committed": f[VERSION]["answers_committed"] >= f["v4.1"]["answers_committed"] - GO["committed_drop_max"],
        "fulcher_correct_when_committed": (f[VERSION]["answers_correct_when_committed"]
                                           >= f["v4.1"]["answers_correct_when_committed"] - GO["correct_drop_max"]),
        "out_of_reference_auroc": oor[VERSION] >= oor["v4.1"] - GO["auroc_drop_max"],
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
