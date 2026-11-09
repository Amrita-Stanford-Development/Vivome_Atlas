"""The raw-or-log plan's B7, a probe written after the one scoring (not an
expectation row, and not a test result): what the sealed test's misses are.

The sealed test was scored once (valuescale/corpus/score_test.py, 2026-11-09)
and its record stands as scored. This probe reads that record and never runs
the detector. It answers three questions:

1. **Tables the corpus should not have kept.** Every kept table, in both
   splits, that holds no observed value, or that is labelled linear though
   99% of its values sit below LOG_CEILING. A linear intensity table spans
   several decades above that; a log2 table stays under it.
2. **The constructed-log tail in S1.** The detector's log probability on each
   S1 subsample's constructed log variant, calibration against test, below
   the S1 log threshold: overall, and by the whole table's missing share.
   The calibration side is B4's rehearsal (score_test.py on the calibration
   split), which recomputes the calibration scores; the probe checks that
   they agree.
3. **The results with the faulty tables of (1) set aside:** the guarantee
   check and the primary comparison. Post hoc; the scored record does not
   change.

Reads research/benchmark/value-scale-test/results.json,
research/notebook-outputs/value_scale_b4/rehearsal.json and
calibration_rows.json, valuescale/calibration/protein-v1.json,
valuescale/corpus/walk.jsonl, and the cached tables under
data/incoming/value-scale-corpus/. Writes posthoc.md and posthoc.json beside
B7's report.

    python research/notebooks/value_scale_b7_posthoc.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from valuescale import calibrated, conformal  # noqa: E402
from valuescale.corpus import score_test  # noqa: E402  (its constants and outcome rules; it is not run)

OUT = REPO / "research" / "notebook-outputs" / "value_scale_b7"
B4 = REPO / "research" / "notebook-outputs" / "value_scale_b4"
WALK = REPO / "valuescale" / "corpus" / "walk.jsonl"
LOG_CEILING = 64.0  # 2**6: the 99th percentile of a log2 table's values is well under it, a linear table's far above
BANDS = ((0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.0))
ALPHA = 0.05


def table_values(accession: str) -> np.ndarray:
    with np.load(score_test.DATA / accession / "table.npz") as z:
        return z["values"].astype(np.float64)


def missing_share(values: np.ndarray) -> float:
    return float(1.0 - (np.isfinite(values) & (values > 0)).mean())


def faulty_tables(kept: list[dict]) -> list[dict]:
    found = []
    for w in kept:
        v = table_values(w["accession"])
        observed = v[np.isfinite(v) & (v > 0)]
        if observed.size == 0:
            found.append({"accession": w["accession"], "split": w["split"], "software": w.get("software"),
                          "fault": "empty", "detail": f"no observed value in {v.shape[0]} rows x {v.shape[1]} columns"})
        elif w.get("label") == "linear" and np.quantile(observed, 0.99) < LOG_CEILING:
            q = np.quantile(observed, [0.0, 0.5, 1.0])
            found.append({"accession": w["accession"], "split": w["split"], "software": w.get("software"),
                          "fault": "log values labelled linear",
                          "detail": f"values {q[0]:.2f} to {q[2]:.2f}, median {q[1]:.2f}"})
    return found


def s1_log_scores(rows: list[dict]) -> list[tuple[str, float]]:
    return [(r["accession"], r["probabilities"]["log"]) for r in rows
            if r["class"] == "constructed_log" and r["stratum"] == "S1" and r["probabilities"]]


def tail(rows: list[dict], threshold: float, shares: dict) -> dict:
    scored = s1_log_scores(rows)
    p = np.array([s for _, s in scored])
    m = np.array([shares[a] for a, _ in scored])
    bands = []
    for lo, hi in BANDS:
        sel = (m >= lo) & ((m < hi) if hi < 1.0 else (m <= hi))
        bands.append({"band": [lo, hi], "tables": int(sel.sum()), "below": int((p[sel] < threshold).sum())})
    return {"scored": int(p.size), "below": int((p < threshold).sum()), "bands": bands,
            "spearman_missing": float(stats.spearmanr(p, m)[0]), "scores": p.tolist()}


def guarantee(rows: list[dict], drop: set[str]) -> dict:
    out = {}
    for name, members in (("S1", ("S1",)), ("S2+S3", ("S2", "S3"))):
        for cls in ("linear", "constructed_log"):
            by_deposit: dict[str, bool] = {}
            for r in rows:
                if r["class"] == cls and r["stratum"] in members and r["accession"] not in drop:
                    by_deposit[r["accession"]] = by_deposit.get(r["accession"], False) or score_test.is_miss(r["outcome"])
            n, miss = len(by_deposit), sum(by_deposit.values())
            lower = conformal.clopper_pearson_lower(miss, n)
            out[f"{name} {cls}"] = {"n": n, "miss": miss, "rate": miss / n, "lower": lower, "contradicted": lower > ALPHA}
    return out


def mcnemar_one_sided(b: int, c: int) -> float:
    n = b + c
    return sum(math.comb(n, i) for i in range(b, n + 1)) / 2 ** n if n else 1.0


def cleanup_split(rows: list[dict], added: set[str]) -> dict:
    """S1 constructed-log misses among the deposits the clean-up added (audit.json 'cleanup') and the rest."""
    s1 = [r for r in rows if r["class"] == "constructed_log" and r["stratum"] == "S1"]
    out = {}
    for name, sel in (("clean-up", [r for r in s1 if r["accession"] in added]), ("rest", [r for r in s1 if r["accession"] not in added])):
        out[name] = {"n": len(sel), "miss": sum(score_test.is_miss(r["outcome"]) for r in sel)}
    return out


def value_summary(accession: str) -> str:
    v = table_values(accession)
    observed = v[np.isfinite(v) & (v > 0)]
    q = np.quantile(observed, [0.0, 0.5, 1.0])
    return f"values {q[0]:.3g} to {q[2]:.3g}, median {q[1]:.3g}"


def primary(tables: list[dict], drop: set[str]) -> dict:
    kept = [t for t in tables if t["accession"] not in drop]
    det = [t["detector"] == "linear" for t in kept]
    med = [t["baselines"]["median_50"] == "linear" for t in kept]
    b = sum(d and not m for d, m in zip(det, med))
    c = sum(m and not d for d, m in zip(det, med))
    return {"tables": len(kept), "detector_wrong": det.count(False), "median_50_wrong": med.count(False),
            "detector_only_right": b, "median_50_only_right": c, "p_value": mcnemar_one_sided(b, c),
            "discordant": [{"accession": t["accession"], "detector": t["detector"], "median_50": t["baselines"]["median_50"]}
                           for t, d, m in zip(kept, det, med) if d != m],
            "whole_constructed_log_read_log": sum(t["log_detector"] == "log" for t in kept),
            "whole_constructed_log_read_log_median_50": sum(t["log_baselines"]["median_50"] == "log" for t in kept)}


def main() -> int:
    results = json.loads(score_test.RESULTS.read_text(encoding="utf-8"))
    rehearsal = json.loads((B4 / "rehearsal.json").read_text(encoding="utf-8"))
    cal_rows = json.loads((B4 / "calibration_rows.json").read_text(encoding="utf-8"))["rows"]
    threshold = calibrated.load().stratum_for(20).thresholds["log"]
    kept = [w for w in map(json.loads, WALK.read_text(encoding="utf-8").splitlines()) if w.get("outcome") == "kept"]

    # The rehearsal recomputes the calibration scores: check, subsample by subsample.
    cal = {(r["accession"], r["stratum"]): r["score"] for r in cal_rows if r["label"] == "log"}
    pairs = [(cal[(r["accession"], r["stratum"])], r["probabilities"]["log"]) for r in rehearsal["rows"]
             if r["class"] == "constructed_log" and r["probabilities"] and (r["accession"], r["stratum"]) in cal]
    agree = sum(abs(a - b) < 1e-12 for a, b in pairs)

    faults = faulty_tables(kept)
    drop = {f["accession"] for f in faults if f["split"] == "test"}
    shares = {w["accession"]: missing_share(table_values(w["accession"])) for w in kept}
    cal_tail, test_tail = tail(rehearsal["rows"], threshold, shares), tail(results["rows"], threshold, shares)
    a, b = cal_tail["below"], test_tail["below"]
    fisher = stats.fisher_exact([[a, cal_tail["scored"] - a], [b, test_tail["scored"] - b]], alternative="less").pvalue
    ks = stats.ks_2samp(cal_tail["scores"], test_tail["scores"]).pvalue
    audit = json.loads((REPO / "valuescale" / "corpus" / "audit.json").read_text(encoding="utf-8"))
    payload = {
        "written": "after the one scoring; post hoc, not a test result",
        "cleanup": {"calibration": cleanup_split(rehearsal["rows"], set(audit["cleanup"]["calibration"])),
                    "test": cleanup_split(results["rows"], set(audit["cleanup"]["test"]))},
        "kept_tables": len(kept), "rehearsal_scores_equal_calibration": [agree, len(pairs)],
        "faulty_tables": faults, "s1_log_threshold": threshold,
        "tail": {"calibration": {k: v for k, v in cal_tail.items() if k != "scores"},
                 "test": {k: v for k, v in test_tail.items() if k != "scores"},
                 "fisher_one_sided_p": fisher, "ks_p": ks},
        "guarantee_as_scored": guarantee(results["rows"], set()),
        "guarantee_faulty_set_aside": guarantee(results["rows"], drop),
        "primary_as_scored": primary(results["tables"], set()),
        "primary_faulty_set_aside": primary(results["tables"], drop),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "posthoc.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8", newline="\n")

    lines = ["# B7, a probe written after the one scoring", "",
             "Generated by `research/notebooks/value_scale_b7_posthoc.py`. Post hoc: it explains the scored record "
             "(`research/benchmark/value-scale-test/results.json`) and changes none of it. It never runs the detector.", "",
             "## Tables the corpus should not have kept", "",
             f"Over all {len(kept)} kept tables, both splits: empty tables, and tables labelled linear whose values "
             f"sit below {LOG_CEILING:g} (99th percentile).", "",
             "| accession | split | software | fault | values |", "|---|---|---|---|---|"]
    lines += [f"| {f['accession']} | {f['split']} | {f['software']} | {f['fault']} | {f['detail']} |" for f in faults]
    lines += ["", "## The constructed-log tail in S1", "",
              f"The detector's log probability on each S1 subsample's constructed log, against the S1 log threshold "
              f"({threshold:.4f}). Calibration side: B4's rehearsal, whose scores equal calibration's on {agree} of "
              f"{len(pairs)} subsamples.", "",
              "| missing share of the table | calibration: below / tables | test: below / tables |", "|---|---|---|"]
    for cb, tb in zip(cal_tail["bands"], test_tail["bands"]):
        lines.append(f"| {cb['band'][0]:.1f} to {cb['band'][1]:.1f} | {cb['below']} / {cb['tables']} | {tb['below']} / {tb['tables']} |")
    lines += [f"| all | {a} / {cal_tail['scored']} | {b} / {test_tail['scored']} |", "",
              f"- Spearman correlation of the log probability with the missing share: calibration "
              f"{cal_tail['spearman_missing']:.3f}, test {test_tail['spearman_missing']:.3f}.",
              f"- Below the threshold, calibration against test: Fisher one-sided p = {fisher:.4f} (a comparison "
              f"chosen after the result). The whole distributions: two-sample KS p = {ks:.3f}.",
              "- Misses (wrong or unlike either) among the deposits B3's clean-up added (`audit.json` \"cleanup\") "
              "and the rest: " + "; ".join(
                  f"{split}: clean-up {c['clean-up']['miss']} of {c['clean-up']['n']}, rest {c['rest']['miss']} of {c['rest']['n']}"
                  for split, c in payload["cleanup"].items()) + ".", "",
              "## The guarantee, as scored and with the faulty test tables set aside", "",
              "| stratum, class | as scored: miss / n | one-sided lower | faulty set aside: miss / n | one-sided lower |",
              "|---|---|---|---|---|"]
    for key, g in payload["guarantee_as_scored"].items():
        h = payload["guarantee_faulty_set_aside"][key]
        mark = lambda x: " (contradicted)" if x["contradicted"] else ""
        lines.append(f"| {key} | {g['miss']} / {g['n']} | {g['lower']:.4f}{mark(g)} | {h['miss']} / {h['n']} | {h['lower']:.4f}{mark(h)} |")
    lines += ["", "## The primary comparison and the whole constructed logs", "",
              "| | tables | detector wrong | median-50 wrong | detector alone right | median-50 alone right | one-sided p | constructed logs read log: detector | median-50 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for name, key in (("as scored", "primary_as_scored"), ("faulty set aside", "primary_faulty_set_aside")):
        p = payload[key]
        lines.append(f"| {name} | {p['tables']} | {p['detector_wrong']} | {p['median_50_wrong']} | {p['detector_only_right']} | "
                     f"{p['median_50_only_right']} | {p['p_value']:.4f} | {p['whole_constructed_log_read_log']} | "
                     f"{p['whole_constructed_log_read_log_median_50']} |")
    lines += ["", "The discordant tables, with the faulty set aside:", ""]
    lines += [f"- {d['accession']}: the detector reads {d['detector']}, median-50 {d['median_50']}; {value_summary(d['accession'])}"
              for d in payload["primary_faulty_set_aside"]["discordant"]]
    (OUT / "posthoc.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT / "posthoc.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
