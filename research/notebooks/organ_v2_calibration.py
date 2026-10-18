"""Organ references v2, diagnostics A2 and A3 (research/organ-references.md,
"Version 2"; the plan of 2026-10-18), offline on A0's caches
(research/notebooks/organ_v2_cache.py).

Every arm fits on half of a suite's uploads and is scored on the other half,
then the halves swap: FOLD_SEEDS seeds, so 10 folds, the halves stratified by
scenario. Answers are built with the service's own calibrator, abstention
and resolve (A0's replay check shows the cache reproduces the service).

The owner's split G1 (2026-10-18) defines the bands:
- an upload is mixed when its classes number at least 3 and span at least 2
  lineages, or when it is a whole tissue;
- every other upload is narrow.

**A2, the calibration's population** (v1's calibration suite):
- P0: v1's rule (Mondrian per true class, alpha 0.1, min_n 50), refitted on
  the fitting half;
- P1: as P0, without one-class uploads;
- O2: oracle bands, a P0 fit on each band's uploads, applied by the true band;
- O2b: as O2, with "mixed" meaning at least 5 classes;
- M: a P0 fit on mixed uploads only, applied to every upload;
- M+T: as M, with the temperatures also refitted on mixed uploads (the fused
  guess is held at v1's).

Decision rules, fixed here:
- banding goes on to A4 only if O2 lifts mixed commitment by at least 10
  points over P0, with mixed coverage at least 85 and correct when committed
  at least 90, in at least 8 of the 10 folds;
- M (or M+T) is eligible only if narrow uploads keep correct when committed
  at least 90 in at least 8 of the 10 folds (and later pass A4's real-data
  check);
- the colon v2 is built only if an eligible arm (P0, M, M+T, or O2 when
  banding goes on) brings the colon's mixed commitment to at least 75 in at
  least 8 of the 10 folds.

**A3, rare and hard classes** (A0's rare-class suite: every class with at
least 5 validation cells):
- R0: P0;
- R1: no entry bar below chance, qhat at most 1 - 1/C;
- R2: a class with fewer than RARE_MIN unique calibration cells takes its
  group's pooled quantile, else the marginal;
- R1+R2;
- R3: group-level conformal sets: groups enter by a per-group threshold
  fitted on group probabilities, a class answer needs a one-class set inside
  them.

Decision rules, on fold medians against R0:
- R2 is adopted unless coverage falls by more than 1 point;
- R1 is adopted if commitment rises by at least 3 points with coverage at
  least 87 and correct when committed at least 92;
- R3 is adopted only if it beats R1+R2 by at least 5 points of commitment
  under the same bars.

Writes research/notebook-outputs/organ_v2_calibration/: rules.json (first),
a2.json, a3.json, decisions.json.

    python research/notebooks/organ_v2_calibration.py      # from the repository root
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
sys.path.insert(0, str(REPO / "research" / "notebook-outputs" / "nb2"))
import nb2_core as n2  # noqa: E402
from organ_reference import data  # noqa: E402

from service.pipeline import abstention, calibration, ensemble  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_calibration"
ORGANS = ("lymph_node", "lung", "large_intestine")
FOLD_SEEDS = 5
ALPHA, MIN_N = 0.1, 50
RARE_MIN = 30
BARS = {"banding_lift": 10.0, "mixed_coverage": 85.0, "cwc": 90.0, "folds": 8, "colon_mixed_committed": 75.0,
        "r2_coverage_drop": 1.0, "r1_lift": 3.0, "r1_coverage": 87.0, "r1_cwc": 92.0, "r3_over_r1r2": 5.0}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Organ:
    def __init__(self, organ: str):
        self.organ = organ
        self.dir = data.WORK / organ
        spec = json.loads((self.dir / "bundle" / "answers_spec.json").read_text(encoding="utf-8"))
        self.names = spec["class_order"]
        self.hierarchy = spec["hierarchy"]
        self.C = len(self.names)
        self.ood_threshold = float(spec["ood"]["threshold"])
        self.min_genes = int(spec["preprocessing"]["min_observed_genes"])
        self.calib = json.loads((self.dir / "calibration.json").read_text(encoding="utf-8"))
        self.members = list(self.calib["temperature"])
        self.groups = sorted({self.hierarchy[c]["group"] for c in self.names})
        self.group_of = np.array([self.groups.index(self.hierarchy[c]["group"]) for c in self.names])

    def suite(self, name: str) -> dict:
        d = dict(np.load(self.dir / "v2_diagnostics" / f"cache_{name}.npz"))
        uploads = json.loads((self.dir / "v2_diagnostics" / f"uploads_{name}.json").read_text(encoding="utf-8"))
        d["uploads"] = uploads
        d["mixed"] = np.array([(u["classes"] >= 3 and u["lineages"] >= 2) or u["scenario"] == "tissue" for u in uploads])
        d["broad5"] = np.array([(u["classes"] >= 5 and u["lineages"] >= 2) or u["scenario"] == "tissue" for u in uploads])
        d["scenario"] = np.array([u["scenario"].split(":")[0] for u in uploads])
        d["unique_cells"] = None
        return d

    def probs(self, cos: np.ndarray, temps: dict) -> np.ndarray:
        return np.mean([n2.softmax(cos[:, k, :].astype(np.float64), temps[m]) for k, m in enumerate(self.members)], 0)


def folds(scenario: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    a = np.zeros(len(scenario), bool)
    for s in np.unique(scenario):
        idx = np.flatnonzero(scenario == s)
        rng.shuffle(idx)
        a[idx[: len(idx) // 2]] = True
    return a, ~a


def fit(scores: np.ndarray, y: np.ndarray, C: int) -> tuple[np.ndarray, float]:
    return n2.fit_qhat(scores, y, C, ALPHA, True, MIN_N)


def answer(o: Organ, P, guess, ood, observed, y, qhat_rows: np.ndarray, group_sets=None) -> dict:
    """The service's answers per cell: committed, correct at the stated level, covered, OOD."""
    keep = observed >= o.min_genes
    P, guess, ood, observed, y, qhat_rows = P[keep], guess[keep], ood[keep], observed[keep], y[keep], qhat_rows[keep]
    member = P >= (1.0 - qhat_rows)
    nonempty = member.any(1)
    member[nonempty, P[nonempty].argmax(1)] = True
    member[nonempty, guess[nonempty]] = True
    if group_sets is not None:
        g = group_sets[keep]
        member &= g[:, o.group_of]
        # no class of the entered groups passes its own bar: the groups themselves are the answer
        empty = ~member.any(1) & g.any(1)
        member[empty] = g[empty][:, o.group_of]
    sets = [np.flatnonzero(r).tolist() for r in member]
    verdict = abstention.score_abstention(ood.astype(np.float64), observed, sets, np.zeros(0, np.int64),
                                          min_observed_genes=o.min_genes, threshold=o.ood_threshold)
    committed = np.zeros(len(y), bool)
    correct = np.zeros(len(y), bool)
    for i, reason in enumerate(verdict.reason):
        if reason not in (abstention.AbstainReason.NONE, abstention.AbstainReason.AMBIGUOUS):
            continue
        r = ensemble.resolve([o.names[c] for c in sets[i]], o.hierarchy)
        if r is None:
            continue
        committed[i] = True
        label, level = r
        truth = o.names[y[i]]
        correct[i] = label == (truth if level == "class" else o.hierarchy[truth][level])
    covered = member[np.arange(len(y)), y]
    ood_abst = np.array([r == abstention.AbstainReason.OUT_OF_DISTRIBUTION for r in verdict.reason])
    return {"keep": keep, "committed": committed, "correct": correct, "covered": covered, "ood": ood_abst, "y": y}


def summarise(res: dict, rows: np.ndarray | None = None) -> dict:
    sel = np.ones(len(res["y"]), bool) if rows is None else rows
    if sel.sum() == 0:
        return {"cells": 0}
    com = res["committed"][sel]
    return {"cells": int(sel.sum()), "committed": round(100 * float(com.mean()), 2),
            "correct_when_committed": round(100 * float(res["correct"][sel][com].mean()), 2) if com.any() else None,
            "coverage": round(100 * float(res["covered"][sel].mean()), 2),
            "false_abstention": round(100 * float(res["ood"][sel].mean()), 2)}


def per_class(o: Organ, res: dict) -> dict:
    out = {}
    for c in range(o.C):
        rows = res["y"] == c
        if rows.any():
            out[o.names[c]] = {"cells": int(rows.sum()), "committed_correct": round(100 * float((res["committed"] & res["correct"])[rows].mean()), 2),
                               "coverage": round(100 * float(res["covered"][rows].mean()), 2)}
    return out


def a2(o: Organ) -> dict:
    s = o.suite("calib")
    cell_upload = s["upload"]
    mixed_cell = s["mixed"][cell_upload]
    y = s["y"].astype(np.int64)
    P0 = s["P"].astype(np.float64)
    scores0 = 1.0 - P0[np.arange(len(y)), y]
    out = {arm: [] for arm in ("P0", "P1", "O2", "O2b", "M", "M+T")}
    for seed in range(FOLD_SEEDS):
        A, B = folds(s["scenario"], seed)
        for fit_up, test_up in ((A, B), (B, A)):
            fit_cell, test_cell = fit_up[cell_upload], test_up[cell_upload]
            arms = {}
            q, _ = fit(scores0[fit_cell], y[fit_cell], o.C)
            arms["P0"] = (P0, np.tile(q, (len(y), 1)))
            single = s["scenario"][cell_upload] == "random_1"
            q, _ = fit(scores0[fit_cell & ~single], y[fit_cell & ~single], o.C)
            arms["P1"] = (P0, np.tile(q, (len(y), 1)))
            for arm, band in (("O2", s["mixed"]), ("O2b", s["broad5"])):
                band_cell = band[cell_upload]
                qm, _ = fit(scores0[fit_cell & band_cell], y[fit_cell & band_cell], o.C)
                qn, _ = fit(scores0[fit_cell & ~band_cell], y[fit_cell & ~band_cell], o.C)
                arms[arm] = (P0, np.where(band_cell[:, None], qm[None, :], qn[None, :]))
            qm, _ = fit(scores0[fit_cell & mixed_cell], y[fit_cell & mixed_cell], o.C)
            arms["M"] = (P0, np.tile(qm, (len(y), 1)))
            sel = fit_cell & mixed_cell
            temps = {m: n2.fit_temperature(s["cos"][sel, k, :].astype(np.float64), y[sel])[0] for k, m in enumerate(o.members)}
            PT = o.probs(s["cos"], temps)
            scoresT = 1.0 - PT[np.arange(len(y)), y]
            qt, _ = fit(scoresT[sel], y[sel], o.C)
            arms["M+T"] = (PT, np.tile(qt, (len(y), 1)))
            for arm, (P, Q) in arms.items():
                rows = test_cell
                res = answer(o, P[rows], s["guess"][rows].astype(np.int64), s["ood"][rows], s["observed"][rows], y[rows], Q[rows])
                band = mixed_cell[rows][res["keep"]]
                scen = s["scenario"][cell_upload][rows][res["keep"]]
                out[arm].append({"all": summarise(res), "mixed": summarise(res, band), "narrow": summarise(res, ~band),
                                 "by_scenario": {k: summarise(res, scen == k) for k in np.unique(scen)}})
    return out


def rare_qhat(o: Organ, scores, y, cells_idx, rule: set) -> np.ndarray:
    q, marg = fit(scores, y, o.C)
    if "R2" in rule:
        unique = {c: len(np.unique(cells_idx[y == c])) for c in range(o.C)}
        for c in range(o.C):
            if unique[c] < RARE_MIN:
                same = np.isin(y, [k for k in range(o.C) if o.group_of[k] == o.group_of[c]])
                if len(np.unique(cells_idx[same])) >= RARE_MIN:
                    q[c] = float(np.quantile(scores[same], n2.conformal_level(int(same.sum()), ALPHA), method="higher"))
                else:
                    q[c] = marg
    if "R1" in rule:
        q = np.minimum(q, 1.0 - 1.0 / o.C)
    return q


def a3(o: Organ) -> dict:
    out = {"suites": {}}
    for suite_name in ("rare", "calib"):
        s = o.suite(suite_name)
        cell_upload = s["upload"]
        y = s["y"].astype(np.int64)
        P = s["P"].astype(np.float64)
        scores = 1.0 - P[np.arange(len(y)), y]
        specs = json.loads((o.dir / ("v2_diagnostics/sim_suite_rare_v2diag.json" if suite_name == "rare"
                                     else "sim_suite_calib_v1.json")).read_text(encoding="utf-8"))
        cells_idx = np.concatenate([np.asarray(spec["cell_idx"]) for spec in specs])
        Pg = np.stack([P[:, o.group_of == g].sum(1) for g in range(len(o.groups))], 1)
        yg = o.group_of[y]
        gscores = 1.0 - Pg[np.arange(len(y)), yg]
        mixed_cell = s["mixed"][cell_upload]
        arms = {arm: [] for arm in ("R0", "R1", "R2", "R1+R2", "R3")}
        for seed in range(FOLD_SEEDS):
            A, B = folds(s["scenario"], seed)
            for fit_up, test_up in ((A, B), (B, A)):
                fit_cell, test_cell = fit_up[cell_upload], test_up[cell_upload]
                for arm, rule in (("R0", set()), ("R1", {"R1"}), ("R2", {"R2"}), ("R1+R2", {"R1", "R2"})):
                    q = rare_qhat(o, scores[fit_cell], y[fit_cell], cells_idx[fit_cell], rule)
                    rows = test_cell
                    res = answer(o, P[rows], s["guess"][rows].astype(np.int64), s["ood"][rows], s["observed"][rows], y[rows],
                                 np.tile(q, (int(rows.sum()), 1)))
                    band = mixed_cell[rows][res["keep"]]
                    arms[arm].append({"all": summarise(res), "mixed": summarise(res, band), "narrow": summarise(res, ~band),
                                      "per_class": per_class(o, res)})
                qg, _ = n2.fit_qhat(gscores[fit_cell], yg[fit_cell], len(o.groups), ALPHA, True, MIN_N)
                q = rare_qhat(o, scores[fit_cell], y[fit_cell], cells_idx[fit_cell], {"R2"})
                rows = test_cell
                gsets = Pg[rows] >= (1.0 - qg)[None, :]
                gsets[np.arange(int(rows.sum())), Pg[rows].argmax(1)] |= gsets.any(1)
                res = answer(o, P[rows], s["guess"][rows].astype(np.int64), s["ood"][rows], s["observed"][rows], y[rows],
                             np.tile(q, (int(rows.sum()), 1)), group_sets=gsets)
                band = mixed_cell[rows][res["keep"]]
                arms["R3"].append({"all": summarise(res), "mixed": summarise(res, band), "narrow": summarise(res, ~band),
                                   "per_class": per_class(o, res)})
        out["suites"][suite_name] = arms
    return out


def median(rows: list[dict], part: str, key: str) -> float | None:
    vals = [r[part][key] for r in rows if r[part].get(key) is not None]
    return float(np.median(vals)) if vals else None


def count(rows: list[dict], test) -> int:
    return int(sum(bool(test(r)) for r in rows))


def decide(results: dict) -> dict:
    d = {}
    for organ, r in results.items():
        f2 = r["a2"]
        lift_ok = count(range(len(f2["O2"])), lambda i: (
            f2["O2"][i]["mixed"]["committed"] - f2["P0"][i]["mixed"]["committed"] >= BARS["banding_lift"]
            and f2["O2"][i]["mixed"]["coverage"] >= BARS["mixed_coverage"]
            and (f2["O2"][i]["mixed"]["correct_when_committed"] or 0) >= BARS["cwc"]))
        m_ok = {arm: count(f2[arm], lambda x: (x["narrow"]["correct_when_committed"] or 100) >= BARS["cwc"]) >= BARS["folds"]
                for arm in ("M", "M+T")}
        banding = lift_ok >= BARS["folds"]
        eligible = ["P0"] + [a for a in ("M", "M+T") if m_ok[a]] + (["O2"] if banding else [])
        mixed75 = {a: count(f2[a], lambda x: x["mixed"]["committed"] >= BARS["colon_mixed_committed"]) for a in eligible}
        f3 = r["a3"]["suites"]["rare"]
        med = {arm: {k: median(f3[arm], "all", k) for k in ("committed", "coverage", "correct_when_committed")} for arm in f3}
        r2 = med["R2"]["coverage"] >= med["R0"]["coverage"] - BARS["r2_coverage_drop"]
        r1 = (med["R1"]["committed"] - med["R0"]["committed"] >= BARS["r1_lift"] and med["R1"]["coverage"] >= BARS["r1_coverage"]
              and med["R1"]["correct_when_committed"] >= BARS["r1_cwc"])
        r3 = (med["R3"]["committed"] - med["R1+R2"]["committed"] >= BARS["r3_over_r1r2"] and med["R3"]["coverage"] >= BARS["r1_coverage"]
              and med["R3"]["correct_when_committed"] >= BARS["r1_cwc"])
        d[organ] = {"banding_goes_to_a4": banding, "banding_folds": lift_ok, "M_eligible": m_ok,
                    "eligible_arms": eligible, "mixed_committed_75_folds": mixed75,
                    "build": organ != "large_intestine" or any(v >= BARS["folds"] for v in mixed75.values()),
                    "a3_medians": med, "adopt": {"R2": bool(r2), "R1": bool(r1), "R3": bool(r3)}}
    return d


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "organs": list(ORGANS), "fold_seeds": FOLD_SEEDS, "alpha": ALPHA, "min_n": MIN_N,
                                        "rare_min": RARE_MIN, "bars": BARS,
                                        "caches": {o: {s: sha256(data.WORK / o / "v2_diagnostics" / f"cache_{s}.npz") for s in ("calib", "rare")}
                                                   for o in ORGANS}})
    t0 = time.time()
    results = {}
    for organ in ORGANS:
        o = Organ(organ)
        results[organ] = {"a2": a2(o), "a3": a3(o)}
        print(f"{organ} done ({time.time() - t0:.0f}s)", flush=True)
    data.save_json(OUT / "a2.json", {o: r["a2"] for o, r in results.items()})
    data.save_json(OUT / "a3.json", {o: r["a3"] for o, r in results.items()})
    decisions = decide(results)
    data.save_json(OUT / "decisions.json", {"finished": datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - t0),
                                             "decisions": decisions})
    print(json.dumps({o: {k: v for k, v in d.items() if k != "a3_medians"} for o, d in decisions.items()}, indent=1))


if __name__ == "__main__":
    main()
