"""Organ references v2, diagnostic A7 (research/organ-references.md, "Version
2"): would a user-declared upload make-up let the colon answer?

A2 (research/notebooks/organ_v2_calibration.py) found that calibrating mixed
and narrow uploads apart lets the colon commit 97% of mixed-upload cells at
96% correct when committed (arm O2, held halves). A4
(research/notebooks/organ_v2_band_key.py) found no label-free key that tells
the two apart safely, so the colon v2 was not built. The one key left is the
user: the upload form could ask "is this a mixed sample (whole tissue, or at
least 3 cell types across at least 2 lineages)?". This diagnostic measures
what that question would give and what a wrong answer to it would cost. It
is evidence for a written proposal only; nothing here is served.

**The rule studied**
- Declared mixed: v1's colon bundle answers with the mixed band's thresholds
  (`organ_v2_band_key.band_qhats`, fitted on all of v1's calibration cache).
- Declared narrow, or not declared: v1's pooled thresholds, as v1 answers now.

**Real uploads through the colon's v1 bundle** (A4's list, all seen
development data). Each is answered twice: pooled, and as if declared mixed.
- Truth used, where known:
  - Kabatnik's pools by class (classes 1 and 2 epithelial, class 4 stromal),
    alone and together;
  - Zheng's pools (immune; myeloid or T cell/ILC alone);
  - Fulcher 2026 by its labels (immune; CD4T, CD8T and NK as T cell/ILC, B as
    B cell, monocyte and DC as myeloid; Unknown unscored);
  - PBMC240 and SCoPE2 as immune.
- The polyp plate has no labels: its committed share and the lineages of
  its answers are reported.

**Simulated misdeclaration** (A2's folds; no new run): for a share p of
declared-mixed uploads that are really narrow, correct when committed among
declared-mixed uploads is
  ((1-p) c_m a_m + p c_n a_n) / ((1-p) c_m + p c_n),
with c_m, a_m arm O2's mixed committed and correct when committed, and c_n,
a_n arm M's narrow ones (narrow uploads under the mixed thresholds), per
fold, then the median over the 10 folds. p is 0, 5, 10, 25 and 50%.

**Reading, fixed here**
- The proposal is "supported" if all of:
  1. Kabatnik classes 1, 2 and 4 together (the one labelled real mixed
     upload) declared mixed commits more cells than pooled, with at most 10%
     of its cells committed and wrong;
  2. the polyp plate declared mixed commits more cells than pooled;
  3. the simulated correct when committed at p = 10% is at least 90.
- Otherwise "not supported".
- The hazard is reported either way: the largest rise in committed and wrong,
  over the real narrow uploads, when they are declared mixed.

Writes research/notebook-outputs/organ_v2_declared/: rules.json (first),
real.json, misdeclared.json, decision.json.

    python research/notebooks/organ_v2_declared.py      # from the repository root (GPU)
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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import organ_v2_band_key as a4  # noqa: E402
from organ_reference import bundle, data  # noqa: E402

from benchmark import datasets  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_declared"
A2 = REPO / "research" / "notebook-outputs" / "organ_v2_calibration" / "a2.json"
ORGAN = "large_intestine"
SHARES = (0.0, 0.05, 0.10, 0.25, 0.50)
BARS = {"kabatnik_wrong_max": 10.0, "cwc_at_10": 90.0}
FULCHER_GROUP = {"CD4T": "T cell/ILC", "CD8T": "T cell/ILC", "NK": "T cell/ILC", "B": "B cell",
                 "monocyte": "myeloid", "DC": "myeloid"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lineage_and_group(h: dict, label: str, level: str) -> tuple[str, "str | None"]:
    if level == "lineage":
        return label, None
    if level == "class":
        return h[label]["lineage"], h[label]["group"]
    return next(v["lineage"] for v in h.values() if v["group"] == label), label


def tally(h: dict, answers: list, lin: np.ndarray, grp: np.ndarray) -> dict:
    """lin and grp per cell; "" means not scored at that level, and a cell with
    no lineage is left out of the wrong counts."""
    committed = [a is not None for a in answers]
    scored = lin != ""
    wrong = np.zeros(len(answers), bool)
    lineages = {}
    for i, a in enumerate(answers):
        if a is None:
            continue
        L, G = lineage_and_group(h, *a)
        lineages[L] = lineages.get(L, 0) + 1
        if scored[i]:
            wrong[i] = L != lin[i] or (grp[i] != "" and G is not None and G != grp[i])
    c = np.array(committed)
    out = {"committed": round(100 * float(c.mean()), 2),
           "levels": {lv: int(sum(1 for a in answers if a is not None and a[1] == lv)) for lv in ("class", "group", "lineage")},
           "committed_lineages": lineages}
    if scored.any():
        out["committed_and_wrong"] = round(100 * float(wrong[scored].mean()), 2)
        out["correct_when_committed"] = (round(100 * float(1 - wrong[scored & c].mean()), 2) if (scored & c).any() else None)
    return out


def truths(name: str, raw) -> tuple[np.ndarray, np.ndarray]:
    n = len(raw.cell_ids)
    lin, grp = np.full(n, "", object), np.full(n, "", object)
    if name.startswith("Kabatnik"):
        lin[:] = ["stromal" if "Class4" in c else "epithelial" for c in raw.cell_ids]
    elif name.startswith("Zheng"):
        lin[:] = "immune"
        if name.endswith("alone"):
            grp[:] = "myeloid" if "macrophage" in name else "T cell/ILC"
    elif name.startswith("Fulcher"):
        labels = datasets.load_fulcher2026_labels().set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
        for i, t in enumerate(labels):
            if t in FULCHER_GROUP:
                lin[i], grp[i] = "immune", FULCHER_GROUP[t]
    elif name in ("PBMC240", "SCoPE2, published"):
        lin[:] = "immune"
    return lin, grp


def misdeclared() -> dict:
    folds = json.loads(A2.read_text(encoding="utf-8"))[ORGAN]
    out = {}
    for p in SHARES:
        vals = []
        for o2, m in zip(folds["O2"], folds["M"]):
            cm, am = o2["mixed"]["committed"] / 100, o2["mixed"]["correct_when_committed"] / 100
            cn, an = m["narrow"]["committed"] / 100, m["narrow"]["correct_when_committed"] / 100
            vals.append(100 * ((1 - p) * cm * am + p * cn * an) / ((1 - p) * cm + p * cn))
        out[f"{round(100 * p)}%"] = {"median": round(float(np.median(vals)), 2), "min": round(float(np.min(vals)), 2)}
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    work = data.WORK / ORGAN
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "organ": ORGAN, "shares": SHARES, "bars": BARS, "a2_sha256": sha256(A2),
                                        "cache_sha256": sha256(work / "v2_diagnostics" / "cache_calib.npz")})
    t0 = time.time()
    b = bundle.load(work / "bundle")
    cache = dict(np.load(work / "v2_diagnostics" / "cache_calib.npz"))
    uploads = json.loads((work / "v2_diagnostics" / "uploads_calib.json").read_text(encoding="utf-8"))
    q = a4.band_qhats(cache, uploads, len(b.class_names))
    real = []
    with bundle.gene_map(work / "bundle"):
        for name, raw, expected, _, _ in a4.real_uploads(b):
            r = a4.run(b, raw)
            lin, grp = truths(name, raw)
            entry = {"upload": name, "cells": int(len(r["P"])), "expected": expected,
                     "pooled": tally(b.hierarchy, a4.answers_with(b, r, q["pooled"]), lin, grp),
                     "declared_mixed": tally(b.hierarchy, a4.answers_with(b, r, q["mixed"]), lin, grp)}
            real.append(entry)
            print(f"{name}: pooled {entry['pooled']['committed']} declared mixed {entry['declared_mixed']['committed']} "
                  f"({time.time() - t0:.0f}s)", flush=True)
    data.save_json(OUT / "real.json", real)
    mis = misdeclared()
    data.save_json(OUT / "misdeclared.json", mis)
    by = {e["upload"]: e for e in real}
    kab, polyp = by["Kabatnik classes 1, 2 and 4"], by["Polyp plate"]
    checks = {"kabatnik_mixed": bool(kab["declared_mixed"]["committed"] > kab["pooled"]["committed"]
                                     and kab["declared_mixed"]["committed_and_wrong"] <= BARS["kabatnik_wrong_max"]),
              "polyp_plate": bool(polyp["declared_mixed"]["committed"] > polyp["pooled"]["committed"]),
              "simulated_cwc_at_10": bool(mis["10%"]["median"] >= BARS["cwc_at_10"])}
    hazard = max(((e["declared_mixed"]["committed_and_wrong"] - e["pooled"]["committed_and_wrong"], e["upload"])
                  for e in real if e["expected"] == "narrow" and "committed_and_wrong" in e["pooled"]), default=(None, None))
    decision = {"finished": datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - t0), "checks": checks,
                "supported": all(checks.values()),
                "hazard": {"largest_rise_in_committed_and_wrong": None if hazard[0] is None else round(hazard[0], 2), "upload": hazard[1]}}
    data.save_json(OUT / "decision.json", decision)
    print(json.dumps(decision, indent=1))


if __name__ == "__main__":
    main()
