"""Diagnostics for the raw-or-log framework (research/value-scale-plan.md):
every step is run on the diagnostic bank (valuescale/corpus/bank.json) and
checked against the expectations written before it ran
(valuescale/bank/expectations/<step>.json).

    python research/notebooks/value_scale_diagnostics.py --step step1    # from the repository root

Step 1:
- D1, the bank itself: each source file matches its recorded sha256, parses
  with the service's parser by the listed path, matches the feature space,
  and has its label's quote. Shape, missing, zero and negative shares and
  value quantiles are recorded.
- D2, today's Stage 0 rule (alignment.detect_and_transform_value_scale) on
  every table and every labelled variant (valuescale/corpus/variants.py),
  against its label: the picture before the fix.
- D3, today's pipeline (v4.1, protein) traced stage by stage on every table,
  with the service's own calls as scripts/trace_workflow.py makes them, and
  the stage invariants checked.

Writes research/notebook-outputs/value_scale_<step>/report.md (expected
against observed, one row per table) and report.json.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from service import app, config  # noqa: E402
from service.pipeline import alignment, gene_ids, pipeline, smoothing, validation  # noqa: E402
from valuescale.corpus import extract, fetch, variants  # noqa: E402

EXPECTATIONS = REPO / "valuescale" / "bank" / "expectations"
OUT = REPO / "research" / "notebook-outputs"
VERSION = "v4.1"
MAX_CELLS = config.MAX_UPLOAD_CELLS
QUANTILES = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)


def r4(x) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), 4)


def layout_of(text: str) -> str:
    """The parser path a file takes, by the same header tests in the same
    order as alignment.parse_matrix_csv."""
    text = text[1:] if text.startswith("﻿") else text
    first = text.split("\n", 1)[0]
    header = next(csv.reader(io.StringIO(first), delimiter="\t" if first.count("\t") > first.count(",") else ","))
    if all(m in header for m in alignment._MAXQUANT_MARKERS):
        return "maxquant"
    if alignment._SPECTRONAUT_GENES in header and any(alignment._SPECTRONAUT_QUANTITIES[0].match(h) for h in header):
        return "spectronaut"
    if all(m in header for m in alignment._FRAGPIPE_LFQ_MARKERS):
        return "fragpipe-lfq"
    if "Genes" in header:
        return "dia-nn"
    if "Gene" in header:
        return "fragpipe-tmt"
    return "matrix"


def basis_of(bank: dict, entry: dict) -> dict:
    basis = entry["basis"]
    return bank["quotes"][basis] if isinstance(basis, str) else basis


def load_entry(entry: dict) -> tuple[alignment.RawMatrix, str, Path]:
    upload = extract.extract(entry)
    text = app._decode_matrix(upload.read_bytes())
    return alignment.parse_matrix_csv(text), layout_of(text), upload


def describe(values: np.ndarray) -> dict:
    observed = values[~np.isnan(values)]
    finite = observed[np.isfinite(observed)]
    out = {"entries": int(values.size), "missing_share": r4(np.isnan(values).mean()),
           "zero_share": r4((values == 0).mean()), "negative_share": r4((values < 0).mean())}
    if finite.size:
        out.update({f"q{int(q * 100):02d}": r4(np.quantile(finite, q)) for q in QUANTILES})
        out["max"] = r4(finite.max())
        nonzero = finite[finite != 0]
        out["median_nonzero"] = r4(np.median(nonzero)) if nonzero.size else None
    return out


# ---------------------------------------------------------------- Step 1

def d1(bank: dict, expect: dict, record: dict, feature_genes: list[str]) -> tuple[list[dict], dict]:
    want = expect["D1"]["every_entry"]
    features = set(feature_genes)
    rows, tables = [], {}
    for entry in bank["entries"]:
        row = {"id": entry["id"], "accession": entry["accession"], "label": entry["label"],
               "label_strength": entry["label_strength"], "layout_listed": entry["layout"]}
        source = fetch.source_path(entry)
        key = source.relative_to(REPO).as_posix()
        row["sha256_matches_record"] = key in record and fetch.sha256(source) == record[key]["sha256"]
        try:
            raw, layout, upload = load_entry(entry)
            row.update(parses_with_service_parser=True, layout=layout, upload=upload.relative_to(REPO).as_posix())
        except Exception as err:  # a parse failure is a D1 finding, not a crash
            row.update(parses_with_service_parser=False, error=f"{type(err).__name__}: {str(err)[:300]}")
            raw, layout = None, None
        row["layout_as_listed"] = layout == entry["layout"]
        basis = basis_of(bank, entry)
        row["label_has_quote"] = bool(basis["quote"].strip() and basis["source"].strip())
        if raw is not None:
            resolved = gene_ids.resolve_to_feature_symbols(raw.gene_names)
            row.update(cells=len(raw.cell_ids), proteins=len(raw.gene_names),
                       genes_matched=len({g for g in resolved if g in features}), **describe(raw.values))
            tables[entry["id"]] = raw
        checks = {
            "sha256_matches_record": row["sha256_matches_record"] is want["sha256_matches_record"],
            "parses_with_service_parser": row["parses_with_service_parser"] is want["parses_with_service_parser"],
            "layout_as_listed": row["layout_as_listed"] is want["layout_as_listed"],
            "label_has_quote": row["label_has_quote"] is want["label_has_quote"],
            "min_cells": row.get("cells", 0) >= want["min_cells"],
            "min_genes_matched_to_feature_space": row.get("genes_matched", 0) >= want["min_genes_matched_to_feature_space"],
        }
        row["failed"] = [k for k, ok in checks.items() if not ok]
        row["pass"] = not row["failed"]
        rows.append(row)
        print(f"  D1 {entry['id']}: {'PASS' if row['pass'] else 'FAIL ' + ','.join(row['failed'])}", flush=True)
    return rows, tables


def d2(bank: dict, expect: dict, tables: dict) -> list[dict]:
    predicted = expect["D2"]["predicted_misreads"]
    rows = []
    for entry in bank["entries"]:
        raw = tables.get(entry["id"])
        if raw is None:
            continue
        cases = [("original", raw.values, entry["label"])]
        cases += list(variants.variants(entry["id"], raw.values, entry["label"]))
        for name, values, label in cases:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                _, scale = alignment.detect_and_transform_value_scale(np.asarray(values, dtype=np.float32))
            if name == "original":
                why = predicted["entries"].get(entry["id"])
            else:
                side = "variants_of_linear_tables" if entry["label"] == "linear" else "variants_of_log_tables"
                why = predicted[side].get(name)
            judged = label in ("linear", "log")
            row = {"id": entry["id"], "variant": name, "label": label, "detected": scale.detected,
                   "right": (scale.detected == label) if judged else None, "predicted_misread": why is not None}
            row["as_predicted"] = None if not judged else (row["right"] != row["predicted_misread"])
            rows.append(row)
    return rows


def _trace(bundle, raw: alignment.RawMatrix) -> tuple[dict, dict]:
    """Stages 0-3 by the service's own calls (scripts/trace_workflow.py:166-189),
    the invariants, then the service's whole run on the same table."""
    inv = {}
    values0 = raw.values
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scaled, scale = alignment.detect_and_transform_value_scale(values0)
    inv["no_inf_after_stage0"] = not np.isinf(scaled).any()
    if scale.detected == "linear":
        made_missing = int((np.isnan(scaled) & ~np.isnan(values0)).sum())
        inv["zeros_made_missing_equal_zeros"] = made_missing == int((values0 == 0).sum() + np.isinf(values0).sum())
    else:
        inv["zeros_made_missing_equal_zeros"] = None  # not read as linear: nothing is made missing
    collapsed = alignment.collapse_duplicate_genes(alignment.RawMatrix(raw.gene_names, raw.cell_ids, scaled))
    aligned = alignment.align_to_feature_space(collapsed, bundle.feature_genes)
    index = {g: i for i, g in enumerate(bundle.feature_genes)}
    last_row = {}
    for i, g in enumerate(gene_ids.resolve_to_feature_symbols(collapsed.gene_names)):
        if g in index:
            last_row[index[g]] = i
    expected_mask = sum(int((~np.isnan(collapsed.values[i])).sum()) for i in last_row.values())
    inv["mask_sum_equals_observed"] = int(aligned.mask.sum()) == expected_mask
    z = alignment.zscore_per_gene(collapsed.values)
    observed = ~np.isnan(collapsed.values)
    worst_mean, worst_sd, constant_ok = 0.0, 0.0, True
    for i in range(z.shape[0]):
        obs = observed[i]
        if not obs.any():
            continue
        zi, xi = z[i, obs].astype(np.float64), collapsed.values[i, obs]
        if np.nanmax(xi) - np.nanmin(xi) == 0:
            constant_ok &= bool(np.all(zi == 0))
            continue
        worst_mean = max(worst_mean, abs(zi.mean()))
        worst_sd = max(worst_sd, abs(zi.std() - 1))
    inv["zscore_mean0_sd1"] = worst_mean < 1e-4 and worst_sd < 1e-4 and constant_ok
    smoothed, aligned_again, _ = pipeline._prepare_query(bundle.feature_genes, raw)
    inv["prepare_query_matches_trace"] = bool(np.array_equal(aligned.values, aligned_again.values)
                                              and np.array_equal(aligned.mask, aligned_again.mask))
    inv["encoder_input_finite"] = bool(np.isfinite(smoothed).all() and np.isfinite(aligned.mask).all())
    k, alpha, n_pca, seed = config.SMOOTHING_K, config.SMOOTHING_ALPHA, config.SMOOTHING_N_PCA, config.SMOOTHING_SEED
    knn_idx, knn_w = smoothing._knn_weights(z.T, k, n_pca, seed)
    mine = (1 - alpha) * aligned.values + alpha * np.einsum("nk,nkf->nf", knn_w, aligned.values[knn_idx])
    inv["smoothing_matches_service"] = bool(np.allclose(mine.astype(np.float32), smoothed, atol=1e-6))
    response = json.loads(json.dumps(pipeline.run_projection(bundle, raw, modality="prot")))
    cells = response["cells"]
    inv["every_cell_answered_or_abstained"] = all(c.get("label") is not None or c.get("abstain_reason") for c in cells)
    levels, reasons, labels = {}, {}, {}
    for c in cells:
        if c.get("label") is not None:
            levels[c["label_level"]] = levels.get(c["label_level"], 0) + 1
            labels[c["label"]] = labels.get(c["label"], 0) + 1
        else:
            reasons[c["abstain_reason"]] = reasons.get(c["abstain_reason"], 0) + 1
    answers = {"value_scale": response["value_scale"], "n_cells": len(cells),
               "n_features_matched": response["n_features_matched"], "levels": levels,
               "abstain_reasons": reasons, "top_labels": dict(sorted(labels.items(), key=lambda x: -x[1])[:5]),
               "zscore_worst_mean": r4(worst_mean), "zscore_worst_sd_error": r4(worst_sd)}
    return inv, answers


def d3(bank: dict, expect: dict, tables: dict) -> list[dict]:
    """Expected refusals are a rule (step1.json): the service's validation
    refuses exactly the tables with fewer than MIN_CELLS_REFUSE cells."""
    bundle = pipeline.load_bundle(VERSION)
    rows = []
    for entry in bank["entries"]:
        raw = tables.get(entry["id"])
        if raw is None:
            continue
        row = {"id": entry["id"], "label": entry["label"], "cells_in_table": len(raw.cell_ids)}
        try:
            validation.validate(raw)
        except validation.ValidationError as err:
            expected = len(raw.cell_ids) < validation.MIN_CELLS_REFUSE and "cell(s)" in str(err)
            row.update(refused=True, refusal=str(err)[:200], pass_=expected)
            rows.append(row)
            print(f"  D3 {entry['id']}: refused ({str(err)[:80]})", flush=True)
            continue
        if len(raw.cell_ids) < validation.MIN_CELLS_REFUSE:
            row.update(refused=False, error="not refused despite fewer than 20 cells", pass_=False)
            rows.append(row)
            continue
        if len(raw.cell_ids) > MAX_CELLS:
            keep = np.sort(variants.rng_for(entry["id"], "d3").choice(len(raw.cell_ids), MAX_CELLS, replace=False))
            raw = alignment.RawMatrix(raw.gene_names, [raw.cell_ids[i] for i in keep], raw.values[:, keep])
        started = time.time()
        try:
            inv, answers = _trace(bundle, raw)
        except Exception as err:
            row.update(refused=False, error=f"{type(err).__name__}: {str(err)[:300]}", pass_=False)
            rows.append(row)
            print(f"  D3 {entry['id']}: ERROR {row['error']}", flush=True)
            continue
        failed = [k for k, ok in inv.items() if ok is False]
        row.update(refused=False, cells_traced=len(raw.cell_ids), invariants=inv, failed=failed, answers=answers,
                   seconds=round(time.time() - started, 1), pass_=not failed)
        rows.append(row)
        print(f"  D3 {entry['id']}: {'PASS' if row['pass_'] else 'FAIL ' + ','.join(failed)} "
              f"({row['seconds']} s, read {answers['value_scale']['detected']})", flush=True)
    return rows


def _md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def report_step1(bank: dict, expect: dict, r1: list, r2: list, r3: list) -> str:
    lines = ["# Value-scale diagnostics, Step 1: the bank", "",
             f"Run {datetime.now().strftime('%Y-%m-%d %H:%M')} by research/notebooks/value_scale_diagnostics.py. "
             "Expectations: valuescale/bank/expectations/step1.json, written before this run. "
             "The bank: valuescale/corpus/bank.json.", ""]
    n1 = sum(r["pass"] for r in r1)
    lines += [f"## D1, the bank itself: {n1} of {len(r1)} pass", "",
              _md_table(["table", "label", "strength", "layout", "cells", "proteins", "matched", "missing", "zeros",
                         "negative", "median non-zero", "q99", "result"],
                        [[r["id"], r["label"], r["label_strength"], r.get("layout"), r.get("cells"), r.get("proteins"),
                          r.get("genes_matched"), r.get("missing_share"), r.get("zero_share"), r.get("negative_share"),
                          r.get("median_nonzero"), r.get("q99"),
                          "PASS" if r["pass"] else "FAIL: " + ", ".join(r["failed"]) + (f" ({r['error']})" if r.get("error") else "")]
                         for r in r1]), ""]
    judged = [r for r in r2 if r["right"] is not None]
    wrong = [r for r in judged if not r["right"]]
    unpredicted = [r for r in wrong if not r["predicted_misread"]]
    missed_predictions = [r for r in judged if r["right"] and r["predicted_misread"]]
    lines += ["## D2, today's rule on the bank and its variants", "",
              f"{len(judged)} labelled tables and variants; today's rule reads {len(wrong)} wrongly "
              f"({len(unpredicted)} of them not predicted); {len(missed_predictions)} predicted misreads did not happen.", ""]
    by_variant: dict[str, list] = {}
    for r in judged:
        by_variant.setdefault((r["variant"], r["label"]), []).append(r)
    lines += [_md_table(["variant", "label", "tables", "read wrongly", "predicted"],
                        [[v, lab, len(rs), sum(not r["right"] for r in rs), "yes" if rs[0]["predicted_misread"] else ""]
                         for (v, lab), rs in sorted(by_variant.items())]), ""]
    if wrong:
        lines += ["Read wrongly, by table:", "",
                  _md_table(["table", "variant", "label", "read as", "predicted"],
                            [[r["id"], r["variant"], r["label"], r["detected"], "yes" if r["predicted_misread"] else "no"]
                             for r in wrong]), ""]
    foreign = [r for r in r2 if r["right"] is None]
    if foreign:
        counts: dict[tuple, int] = {}
        for r in foreign:
            counts[(r["variant"], r["detected"])] = counts.get((r["variant"], r["detected"]), 0) + 1
        lines += ["Foreign variants (no right reading; reported only):", "",
                  _md_table(["variant", "read as", "tables"], [[v, d, n] for (v, d), n in sorted(counts.items())]), ""]
    n3 = sum(r["pass_"] for r in r3)
    lines += [f"## D3, today's pipeline traced stage by stage: {n3} of {len(r3)} pass", ""]
    rows = []
    for r in r3:
        if r.get("refused"):
            rows.append([r["id"], r["cells_in_table"], "", "", "", "", "refused" + (" (expected)" if r["pass_"] else " (NOT expected)")])
            continue
        if r.get("error"):
            rows.append([r["id"], r["cells_in_table"], "", "", "", "", "ERROR: " + r["error"]])
            continue
        a = r["answers"]
        answered = sum(a["levels"].values())
        rows.append([r["id"], r.get("cells_traced"), a["value_scale"]["detected"], a["n_features_matched"],
                     f"{answered}/{a['n_cells']}", ", ".join(f"{k} {v}" for k, v in a["abstain_reasons"].items()),
                     "PASS" if r["pass_"] else "FAIL: " + ", ".join(r["failed"])])
    lines += [_md_table(["table", "cells traced", "Stage 0 read", "genes matched", "answered", "abstained (reason count)",
                         "result"], rows), ""]
    return "\n".join(lines) + "\n"


def step1() -> None:
    bank = fetch.load_bank()
    expect = json.loads((EXPECTATIONS / "step1.json").read_text(encoding="utf-8"))
    record = json.loads(fetch.RECORD.read_text(encoding="utf-8"))
    feature_genes = pipeline.load_bundle(VERSION).feature_genes
    print("D1, the bank", flush=True)
    r1, tables = d1(bank, expect, record, feature_genes)
    print("D2, today's rule", flush=True)
    r2 = d2(bank, expect, tables)
    print("D3, today's pipeline", flush=True)
    r3 = d3(bank, expect, tables)
    out = OUT / "value_scale_step1"
    out.mkdir(parents=True, exist_ok=True)
    payload = {"step": "step1", "run": datetime.now().isoformat(timespec="seconds"), "pipeline_version": VERSION,
               "D1": r1, "D2": r2, "D3": r3}
    (out / "report.json").write_bytes((json.dumps(payload, indent=1, default=str) + "\n").encode("utf-8"))
    (out / "report.md").write_bytes(report_step1(bank, expect, r1, r2, r3).encode("utf-8"))
    print(f"wrote {(out / 'report.md').relative_to(REPO).as_posix()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--step", choices=("step1",), required=True)
    args = parser.parse_args()
    {"step1": step1}[args.step]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
