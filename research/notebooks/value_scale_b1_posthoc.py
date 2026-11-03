"""The raw-or-log plan's B1, a probe written after the run (not an
expectation row): how far log2(x) is from a straight line in x within each
gene, on every bank table B1 scored under its wrong reading.

The z-score removes any a + c*x within a gene, so what a second log (or a
missing one) leaves behind is measured by the per-gene Pearson correlation
between x and log2(x) over the gene's positive values. It is the statistic
B2's "can't tell" check uses. The probe sets it beside B1's cost (the share
of best guesses the wrong reading changes) and the share of cells answered
under the right reading.

Reads research/notebook-outputs/value_scale_b1/report.json and the bank's
traced tables; writes posthoc.md and posthoc.json beside the report.

    python research/notebooks/value_scale_b1_posthoc.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import value_scale_diagnostics as vsd  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "value_scale_b1"
MIN_VALUES = 5
BAR = 0.98  # B2's "can't tell" check (research/value-scale-plan.md)


def gene_correlations(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=np.float64)
    pos = np.isfinite(x) & (x > 0)
    cors = []
    for g in range(x.shape[0]):
        v = x[g, pos[g]]
        if v.size < MIN_VALUES or np.ptp(v) <= 0:
            continue
        r = np.corrcoef(v, np.log2(v))[0, 1]
        if np.isfinite(r):
            cors.append(r)
    return np.array(cors)


def main() -> int:
    report = json.loads((OUT / "report.json").read_text(encoding="utf-8"))
    scored = {}
    for t in report["tables"]:
        if t.get("not_traced"):
            continue
        wrong = "linear" if t["label"] == "log" else "log_zeros_measured"
        if wrong in t["conditions"]:
            scored[t["id"]] = (t, wrong)
    entries = {e["id"]: e for e in vsd.fetch.load_bank()["entries"]}
    rows = []
    for table_id, (t, wrong) in scored.items():
        if table_id not in entries:  # pxd064083_union is built from two bank tables
            continue
        raw = vsd.traced_table(entries[table_id], vsd.load_entry(entries[table_id])[0])
        x = np.asarray(raw.values, dtype=np.float64)
        vals = x[np.isfinite(x) & (x > 0)]
        cors = gene_correlations(x)
        rows.append({
            "id": table_id, "label": t["label"], "wrong_reading": wrong,
            "changed_best_guess": t["conditions"][wrong]["changed_best_guess"],
            "answered_right": t["conditions"][t["right"]]["answered"],
            "median_positive": float(np.median(vals)), "p05_positive": float(np.quantile(vals, 0.05)),
            "share_below_1": float((vals < 1).mean()),
            "median_gene_correlation": float(np.median(cors)),
            "share_genes_at_bar": float((cors >= BAR).mean()), "genes": int(cors.size),
        })
    every = [(t["conditions"][t["right"]]["answered"], t["conditions"][w]["changed_best_guess"])
             for t, w in scored.values()]
    rho = spearmanr([a for a, _ in every], [c for _, c in every])
    summary = {"answered_vs_changed": {"spearman": float(rho.statistic), "p": float(rho.pvalue), "tables": len(every)}}
    (OUT / "posthoc.json").write_text(json.dumps({"rows": rows, "summary": summary}, indent=1) + "\n",
                                      encoding="utf-8", newline="\n")
    lines = [
        "# B1, a probe written after the run",
        "",
        "Not an expectation row: written after B1's report, to explain its one failed row "
        "(`notes.md`). Script: `research/notebooks/value_scale_b1_posthoc.py`. \"Gene correlation\" is the "
        "per-gene Pearson correlation between x and log2(x) over the gene's positive values (genes with at "
        f"least {MIN_VALUES}), the statistic of B2's \"can't tell\" check; \"at {BAR}\" is the share of genes "
        "at or above that check's bar. \"Changed\" is B1's share of best guesses the wrong reading changes "
        "(log tables: read linear; linear tables: read as log, zeros measured).",
        "",
        "| Table | Label | Changed | Answered, right reading | Median value | 5th percentile | Below 1 | Gene correlation | At 0.98 | Genes |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r["label"], r["changed_best_guess"])):
        lines.append(
            f"| {r['id']} | {r['label']} | {r['changed_best_guess']:.3f} | {r['answered_right']:.3f} | "
            f"{r['median_positive']:.3g} | {r['p05_positive']:.3g} | {r['share_below_1']:.3f} | "
            f"{r['median_gene_correlation']:.4f} | {r['share_genes_at_bar']:.2f} | {r['genes']} |")
    s = summary["answered_vs_changed"]
    lines += ["", f"Across all {s['tables']} tables scored under a wrong reading (pxd064083_union included), the "
              f"Spearman correlation between the share answered under the right reading and the share changed "
              f"is {s['spearman']:.2f} (p = {s['p']:.2f}).", ""]
    (OUT / "posthoc.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
