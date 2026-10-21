"""Candidate v5.3 (owner, 2026-10-21): v4.1's rule on five V2 members trained
with RNA pools added to the training rows, on the original labels
(research/notebooks/v5_train.py clean --variant v5.3; built by
research/notebooks/v5_build.py build --variant v5.3). Development data only;
the gates are fixed here, before the members are trained, and nothing is
tuned.

Why: the blood_pools diagnostic (research/notebook-outputs/blood_pools, run
history entry 61) raised every measure in both seeds, but its fixed reading
said "not promising" (seed 1's Fulcher gain 1.82, bar 2). The owner chose to
build the candidate anyway. That reading stands; this is a new candidate
with its own gates.

Each development upload goes through the service as served (pipeline.
run_projection), for v4.1 and v5.3 alike:
- Fulcher 2026: six-type balanced accuracy of the best guess (v4_pretest.
  metrics); the answers' committed share and correct when committed, at the
  stated level (single_type_uploads.scores), over the scored cells;
- PBMC240: lymphoid recall of the best guess (weak lineage labels);
- SCoPE2, published and reprocessed: unrestricted balanced accuracy,
  reported only (development data that guided the design);
- the out-of-reference AUROC: the best guess's probability, Fulcher's cells
  against Furtwängler 2025's progenitors.

Self-check first: v4.1 must reproduce its committed development figures,
Fulcher 69.05 and PBMC240 92.31 (research/benchmark/v41_development/, as
v4.2's gate read them), within 0.01, else stop.

GO for v5.3 (development evidence), all of:
1. Fulcher balanced accuracy at least v4.1 + 2;
2. PBMC240 lymphoid recall at least v4.1 - 2;
3. Fulcher committed share at least v4.1 - 2, and correct when committed at
   least v4.1 - 1;
4. out-of-reference AUROC at least v4.1 - 0.03.
Fulcher also chose v4.1's weight, which v5.3 keeps, so a gain there is
development evidence only. A GO makes v5.3 a frozen candidate for the
sorted CD4/CD8 test (its protocol's next amendment); it is not served:
the held-out protein sets are spent, and the sorted cells are the test.
The evaluation block it writes keeps the service refusing v5.3 either way.

Writes rules.json (first), development.json, decision.json and
spec_block.json into its own folder of research/notebook-outputs (OUT).

    python research/notebooks/v53_gates.py      # from the repository root
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
import single_type_uploads as stu  # noqa: E402
import v4_pretest  # noqa: E402
from benchmark import baselines_v31, datasets  # noqa: E402
from benchmark import fulcher2026_score as fulcher  # noqa: E402
from benchmark.baselines_score import hierarchy  # noqa: E402
from service import config  # noqa: E402
from service.pipeline import alignment, fusion, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v53_gates"
VERSION = "v5.3"
V41_EXPECTED = {"fulcher2026": 69.05, "pbmc240": 92.31}
TOL = 0.01
GO = {"fulcher_gain_min": 2.0, "pbmc240_drop_max": 2.0, "committed_drop_max": 2.0, "correct_drop_max": 1.0,
      "auroc_drop_max": 0.03}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def uploads() -> list:
    pbmc_meta = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    return [("fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels()),
            ("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()),
             pbmc_meta),
            ("scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")),
            ("scope2_reprocessed", datasets.load_scope2_reprocessed_upload(),
             datasets.load_scope2_reprocessed_labels().rename(columns={"label": "class_name"})),
            ("furtwangler2025", datasets.load_furtwangler2025_upload(), datasets.load_furtwangler2025_labels())]


def expected_levels() -> dict:
    hier, expected = hierarchy(), {}
    for level in ("group", "lineage"):
        found = {}
        for name, t in fulcher.COARSE.items():
            found.setdefault(t, set()).add(hier[name][level])
        expected[level] = {t: v.pop() for t, v in found.items() if len(v) == 1}
    return expected


def figures(name: str, response: dict, info: pd.DataFrame, raw, names: list, lineage: dict, expected: dict) -> tuple:
    cells = response["cells"]
    if name == "pbmc240":
        at = {c: i for i, c in enumerate(raw.cell_ids)}
        cells = [cells[at[c]] for c in info["cell_id"].astype(str)]
    pred = np.array([c.get("best_guess", {}).get("label") or "" for c in cells])
    prob = np.array([c.get("best_guess", {}).get("probability", np.nan) for c in cells], dtype=float)
    cidx = {c: i for i, c in enumerate(names)}
    P = np.zeros((len(pred), len(names)))
    P[np.arange(len(pred)), [cidx.get(p, 0) for p in pred]] = np.nan_to_num(prob)
    fig = v4_pretest.metrics(name, pred, info, P, cidx, lineage)
    fig["committed"] = round(100 * float(np.mean([not c["abstained"] for c in cells])), 2)
    if name == "fulcher2026":
        truth = info.set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
        scored = np.isin(truth, fulcher.TYPES)
        per = stu.scores({"cells": [c for c, s in zip(cells, scored) if s]}, truth[scored], expected)
        n = sum(v["n"] for v in per.values())
        fig["answers_committed"] = round(sum(v["committed_pct"] * v["n"] for v in per.values()) / n, 2)
        committed = sum(v["committed_pct"] * v["n"] / 100 for v in per.values())
        fig["answers_correct_when_committed"] = round(
            100 * sum(v["correct_when_committed_pct"] / 100 * v["committed_pct"] / 100 * v["n"] for v in per.values()) / committed, 2)
    return fig, prob


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "decision.json").exists():
        raise SystemExit("v5.3's gates were run; they are read once")
    (OUT / "rules.json").write_text(json.dumps({
        "script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
        "go": GO, "v41_expected": V41_EXPECTED, "tolerance": TOL}, indent=2) + "\n", encoding="utf-8", newline="\n")
    t0 = time.time()
    bundles = {"v4.1": pipeline.load_bundle("v4.1"), VERSION: fusion.V4Bundle.load(require_evaluation=False, version=VERSION)}
    names = bundles["v4.1"].class_names
    table = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    lineage = table.groupby("class_name")["lineage"].first().to_dict()
    expected = expected_levels()
    dev, prob = {}, {}
    for name, raw, info in uploads():
        for version, bundle in bundles.items():
            fig, p = figures(name, pipeline.run_projection(bundle, raw), info, raw, names, lineage, expected)
            dev.setdefault(name, {})[version] = fig
            prob[(name, version)] = p
        print(name, json.dumps(dev[name]), f"({time.time() - t0:.0f}s)", flush=True)
    for version in bundles:
        a, b = prob[("fulcher2026", version)], prob[("furtwangler2025", version)]
        dev.setdefault("out_of_reference_auroc", {})[version] = round(
            float(roc_auc_score(np.r_[np.ones(len(a)), np.zeros(len(b))], np.nan_to_num(np.r_[a, b]))), 4)
    (OUT / "development.json").write_text(json.dumps(dev, indent=2) + "\n", encoding="utf-8", newline="\n")

    got = {"fulcher2026": dev["fulcher2026"]["v4.1"]["balanced_accuracy_6_types"],
           "pbmc240": dev["pbmc240"]["v4.1"]["lymphoid_recall"]}
    self_check = {k: {"expected": V41_EXPECTED[k], "got": got[k], "passed": abs(got[k] - V41_EXPECTED[k]) <= TOL}
                  for k in V41_EXPECTED}
    if not all(v["passed"] for v in self_check.values()):
        (OUT / "decision.json").write_text(json.dumps({"self_check": self_check, "go": None,
                                                       "reason": "v4.1 did not reproduce its development figures"},
                                                      indent=2) + "\n", encoding="utf-8", newline="\n")
        raise SystemExit(f"STOP: v4.1 did not reproduce its figures: {self_check}")

    f, p, oor = dev["fulcher2026"], dev["pbmc240"], dev["out_of_reference_auroc"]
    checks = {
        "fulcher_gain": f[VERSION]["balanced_accuracy_6_types"] >= f["v4.1"]["balanced_accuracy_6_types"] + GO["fulcher_gain_min"],
        "pbmc240_guardrail": p[VERSION]["lymphoid_recall"] >= p["v4.1"]["lymphoid_recall"] - GO["pbmc240_drop_max"],
        "fulcher_committed": f[VERSION]["answers_committed"] >= f["v4.1"]["answers_committed"] - GO["committed_drop_max"],
        "fulcher_correct_when_committed": (f[VERSION]["answers_correct_when_committed"]
                                           >= f["v4.1"]["answers_correct_when_committed"] - GO["correct_drop_max"]),
        "out_of_reference_auroc": oor[VERSION] >= oor["v4.1"] - GO["auroc_drop_max"],
    }
    go = all(checks.values())
    decision = {"finished": datetime.now().isoformat(timespec="seconds"), "self_check": self_check,
                "checks": checks, "go": go, "seconds": round(time.time() - t0)}
    (OUT / "decision.json").write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8", newline="\n")
    status = "development gates passed" if go else "development gates missed"
    (OUT / "spec_block.json").write_text(json.dumps({"evaluation": {
        "status": status, "record": (OUT / "decision.json").relative_to(REPO).as_posix(),
        "note": "not served: a development result; the sorted CD4/CD8 cells are the test"}}, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(decision, indent=1))


if __name__ == "__main__":
    main()
