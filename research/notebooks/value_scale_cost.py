"""Phase B, B1 of the raw-or-log plan (research/value-scale-plan.md): what
each mistake costs. v4.1 runs on every bank table under three conditions:
read linear (log2 taken, zeros missing), read as log with zeros measured
(today's reading of a table it calls log), and read as log with zeros
missing. Each is compared with the table's right reading (its bank label;
a log table's zeros mean "not measured"). The result fixes, by the rules in
valuescale/bank/expectations/b1.json (written first), the reading the
service uses on "can't tell" and whether a protein 0 is missing under both
readings.

Measures per table and condition: the share of cells whose best guess and
whose answer differ from the right reading's, the share answered, and, where
labels exist, the balanced accuracy of the best guess over coarse groups.
The stage invariants are checked under every condition.

    python research/notebooks/value_scale_cost.py

Writes research/notebook-outputs/value_scale_b1/ (report.md, report.json).
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import value_scale_diagnostics as vsd  # noqa: E402
from benchmark import datasets  # noqa: E402
from benchmark.fulcher2026_score import COARSE  # noqa: E402
from service.pipeline import alignment, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "value_scale_b1"
EXPECTATIONS = REPO / "valuescale" / "bank" / "expectations" / "b1.json"
CONDITIONS = {"linear": ("linear", None), "log_zeros_measured": ("log", "measured"),
              "log_zeros_missing": ("log", "missing")}
GROUP = {"CD4T": "T", "CD8T": "T", "NK": "NK", "B": "B", "monocyte": "monocyte", "DC": "DC"}
PBMC240_GROUP = {"T cell": "T", "NK cell": "NK", "Dendritic": "DC", "Monocyte": "monocyte"}
MIN_GROUP = 5
ZERO_SHARE = 0.05


def union_t_b(t: alignment.RawMatrix, b: alignment.RawMatrix) -> alignment.RawMatrix:
    """The T and B tables side by side: the genes either reports (first row of
    a repeated name), NaN where a table lacks a gene; cell ids prefixed T_, B_."""
    genes, seen = [], set()
    for r in (t, b):
        for g in r.gene_names:
            if g not in seen:
                seen.add(g)
                genes.append(g)
    row = {g: i for i, g in enumerate(genes)}
    blocks, ids = [], []
    for r, prefix in ((t, "T_"), (b, "B_")):
        block = np.full((len(genes), len(r.cell_ids)), np.nan, dtype=np.float32)
        first: dict[str, int] = {}
        for i, g in enumerate(r.gene_names):
            first.setdefault(g, i)
        for g, i in first.items():
            block[row[g]] = r.values[i]
        blocks.append(block)
        ids += [prefix + c for c in r.cell_ids]
    return alignment.RawMatrix(genes, ids, np.concatenate(blocks, axis=1))


def label_groups(table: str, cell_ids: list[str]) -> np.ndarray | None:
    """Each cell's coarse group, or None when the table has no labels (or the
    cell has none)."""
    if table == "pxd064083_union":
        return np.array(["T" if c.startswith("T_") else "B" for c in cell_ids], dtype=object)
    if table == "fulcher_tmt":
        lab = datasets.load_fulcher2026_labels().set_index("cell_id")["label"]
        return np.array([GROUP.get(lab.get(c)) for c in cell_ids], dtype=object)
    if table == "pbmc240_diann":
        meta = pd.read_csv(REPO / "service" / "examples" / "pbmc240_cell_metadata.csv").set_index("cell")["label"]
        return np.array([PBMC240_GROUP.get(meta.get(c)) for c in cell_ids], dtype=object)
    return None


def accuracy(reply: dict, groups: np.ndarray) -> float | None:
    guesses = [GROUP.get(COARSE.get(c.get("best_guess", {}).get("label") or "")) for c in reply["cells"]]
    right = np.array([g is not None and g == want for g, want in zip(guesses, groups)])
    present = [g for g in sorted({x for x in groups if x}) if (groups == g).sum() >= MIN_GROUP]
    if len(present) < 2:
        return None
    return round(100 * float(np.mean([right[groups == g].mean() for g in present])), 2)


def run_table(table: str, label: str, raw: alignment.RawMatrix, bundle, protein_genes) -> dict:
    finite = raw.values[np.isfinite(raw.values)]
    row = {"id": table, "label": label, "cells": len(raw.cell_ids),
           "zero_share": round(float((finite == 0).sum() / raw.values.size), 4),
           "negative": bool((finite < 0).any())}
    right = "linear" if label == "linear" else "log_zeros_missing"
    row["right"] = right
    groups = label_groups(table, raw.cell_ids)
    replies, checks = {}, {}
    for name, (scale, zeros) in CONDITIONS.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                reply = json.loads(vsd.canonical(pipeline.run_projection(
                    bundle, raw, modality="prot", stated_scale=scale, stated_zeros=zeros)))
        except alignment.NotIntensities:
            replies[name] = None
            continue
        replies[name] = reply
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            inv = vsd._reading_invariants(bundle, raw, scale, protein_genes, zeros)
        inv["every_cell_answered_or_abstained"] = all(c.get("label") is not None or c.get("abstain_reason")
                                                      for c in reply["cells"])
        checks[name] = inv
    row["refused"] = [n for n, r in replies.items() if r is None]
    row["failed_invariants"] = {n: [k for k, ok in c.items() if not ok] for n, c in checks.items()
                                if not all(c.values())}
    base = replies.get(right)
    row["conditions"] = {}
    for name, reply in replies.items():
        if reply is None:
            continue
        out = {"answered": round(float(np.mean([c.get("label") is not None for c in reply["cells"]])), 4)}
        if base is not None:
            out["changed_best_guess"] = round(float(np.mean(
                [a.get("best_guess", {}).get("label") != b.get("best_guess", {}).get("label")
                 for a, b in zip(reply["cells"], base["cells"])])), 4)
            out["changed_answer"] = round(float(np.mean(
                [vsd.answer_of(a) + str(a.get("label_level")) != vsd.answer_of(b) + str(b.get("label_level"))
                 for a, b in zip(reply["cells"], base["cells"])])), 4)
        if groups is not None:
            out["accuracy"] = accuracy(reply, groups)
        row["conditions"][name] = out
    if groups is not None:
        row["labelled_cells"] = {g: int((groups == g).sum()) for g in sorted({x for x in groups if x})}
    return row


def median(values: list[float]) -> float | None:
    return round(float(np.median(values)), 4) if values else None


def summarise(rows: list[dict]) -> dict:
    accepted = [r for r in rows if not r.get("not_traced")]
    lin = [r for r in accepted if r["label"] == "linear" and "log_zeros_measured" in r["conditions"]]
    log = [r for r in accepted if r["label"] == "log" and "linear" in r["conditions"]]
    lin_cost = [r["conditions"]["log_zeros_measured"]["changed_best_guess"] for r in lin]
    log_cost = [r["conditions"]["linear"]["changed_best_guess"] for r in log]
    zero_rows = [r for r in accepted if r["zero_share"] >= ZERO_SHARE
                 and {"log_zeros_missing", "log_zeros_measured"} <= set(r["conditions"])]
    zero_votes = {r["id"]: (r["conditions"]["log_zeros_missing"]["changed_best_guess"]
                            < r["conditions"]["log_zeros_measured"]["changed_best_guess"]) for r in zero_rows}
    zero_votes_linear = {k: v for k, v in zero_votes.items() if next(r for r in zero_rows if r["id"] == k)["label"] == "linear"}
    acc_rows = {}
    for r in accepted:
        conds = r["conditions"]
        if r["label"] == "linear" and conds.get("linear", {}).get("accuracy") is not None \
                and conds.get("log_zeros_measured", {}).get("accuracy") is not None:
            acc_rows[r["id"]] = {"right": conds["linear"]["accuracy"], "wrong": conds["log_zeros_measured"]["accuracy"],
                                 "pass": conds["linear"]["accuracy"] >= conds["log_zeros_measured"]["accuracy"] - 2}
    inv_failures = {r["id"]: r["failed_invariants"] for r in accepted if r["failed_invariants"]}
    refusal_ok = {r["id"]: (("linear" in r["refused"]) == r["negative"]) and r["refused"] in ([], ["linear"])
                  for r in accepted}
    rows_out = {
        "B1_invariants": {"pass": not inv_failures, "failures": inv_failures},
        "B1_refusals": {"pass": all(refusal_ok.values()), "wrong": [k for k, ok in refusal_ok.items() if not ok]},
        "B1_direction": {"pass": bool(log_cost and lin_cost and median(log_cost) < median(lin_cost)),
                         "median_log_read_linear": median(log_cost), "median_linear_read_as_log": median(lin_cost),
                         "n_log": len(log_cost), "n_linear": len(lin_cost)},
        "B1_log_read_linear_small": {"pass": bool(log_cost) and median(log_cost) <= 0.10,
                                     "median_log_read_linear": median(log_cost)},
        "B1_zeros": {"pass": bool(zero_votes) and sum(zero_votes.values()) > len(zero_votes) / 2,
                     "missing_better_on": sorted(k for k, v in zero_votes.items() if v),
                     "measured_at_least_as_good_on": sorted(k for k, v in zero_votes.items() if not v),
                     "linear_tables_only": {"missing_better": sum(zero_votes_linear.values()),
                                            "of": len(zero_votes_linear)}},
        "B1_accuracy": {"pass": all(v["pass"] for v in acc_rows.values()) and bool(acc_rows), "tables": acc_rows},
    }
    decisions = {
        "cant_tell_reading": "linear" if (log_cost and lin_cost and median(log_cost) <= median(lin_cost)) else "log",
        "zeros": "missing under both readings" if rows_out["B1_zeros"]["pass"] else "measured under a log reading, as today",
    }
    return {"rows": rows_out, "decisions": decisions}


def report(rows: list[dict], summary: dict) -> str:
    lines = ["# B1: what each mistake costs", "",
             f"Run {datetime.now().date().isoformat()}, v4.1, every bank table as Phase A traced it, plus "
             "pxd064083_union. Expectations and decision rules: `valuescale/bank/expectations/b1.json`, written "
             "before this script existed. \"Changed\" is the share of cells whose best guess differs from the "
             "table's right reading.", "", "## Expectations", "", "| Row | Result | Detail |", "|---|---|---|"]
    for name, r in summary["rows"].items():
        detail = {k: v for k, v in r.items() if k != "pass"}
        lines.append(f"| {name} | {'PASS' if r['pass'] else 'FAIL'} | `{json.dumps(detail)[:300]}` |")
    lines += ["", "## Decisions, by the rules written first", ""]
    lines += [f"- **{k}:** {v}" for k, v in summary["decisions"].items()]
    lines += ["", "## Per table", "",
              "| Table | Label | Cells | Zeros | Right | linear: answered / changed / acc | log, 0 measured | log, 0 missing |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("not_traced"):
            lines.append(f"| {r['id']} | {r['label']} | refused by validation | | | | | |")
            continue

        def cell(name):
            c = r["conditions"].get(name)
            if c is None:
                return "refused"
            acc = f" / {c['accuracy']}" if c.get("accuracy") is not None else ""
            return f"{100 * c['answered']:.1f}% / {100 * c.get('changed_best_guess', float('nan')):.1f}%{acc}"
        lines.append(f"| {r['id']} | {r['label']} | {r['cells']} | {100 * r['zero_share']:.1f}% | {r['right']} | "
                     f"{cell('linear')} | {cell('log_zeros_measured')} | {cell('log_zeros_missing')} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    bank = vsd.fetch.load_bank()
    bundle = pipeline.load_bundle(vsd.VERSION)
    protein_genes = pipeline.load_bundle("v4.2").protein_genes
    entries = {e["id"]: e for e in bank["entries"]}
    tables = [(e["id"], e["label"], vsd.traced_table(e, vsd.load_entry(e)[0])) for e in bank["entries"]]
    union = union_t_b(vsd.load_entry(entries["pxd064083_t"])[0], vsd.load_entry(entries["pxd064083_b"])[0])
    tables.append(("pxd064083_union", "linear", union))
    rows = []
    for table, label, raw in tables:
        if raw is None:
            rows.append({"id": table, "label": label, "not_traced": True})
            print(f"  {table}: refused by validation", flush=True)
            continue
        rows.append(run_table(table, label, raw, bundle, protein_genes))
        print(f"  {table}: done", flush=True)
    summary = summarise(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"step": "b1", "run": datetime.now().isoformat(timespec="seconds"), "pipeline_version": vsd.VERSION,
               **summary, "tables": rows}
    (OUT / "report.json").write_bytes((json.dumps(payload, indent=1, default=str) + "\n").encode("utf-8"))
    (OUT / "report.md").write_bytes(report(rows, summary).encode("utf-8"))
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
