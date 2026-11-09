"""Diagnostics for the raw-or-log framework (research/value-scale-plan.md):
every step is run on the diagnostic bank (valuescale/corpus/bank.json) and
checked against the expectations written before it ran
(valuescale/bank/expectations/<step>.json).

    python research/notebooks/value_scale_diagnostics.py --step step1    # from the repository root
    python research/notebooks/value_scale_diagnostics.py --step phaseA-baseline   # before Phase A's change
    python research/notebooks/value_scale_diagnostics.py --step phaseA
    python research/notebooks/value_scale_diagnostics.py --step phaseA2
    python research/notebooks/value_scale_diagnostics.py --step zscore
    python research/notebooks/value_scale_diagnostics.py --step b5
    python research/notebooks/value_scale_diagnostics.py --step b6     # from a clean tree: it builds the Space

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

Phase A (the request may state the scale, value_scale):
- A0, before the change: every traced table's full reply, its sha256 kept.
- A1, the automatic reply is the baseline's byte for byte, and its summary D3's.
- A2, a stated reading is applied and said, and a linear reading of negative
  values refused; A3, the stage invariants under each reading; A4, the
  answers that change with the reading; A5, the same through the app.
- Phase A2 (what a 0 means, zeros, with a log reading): the automatic reply
  still the baseline's; zeros applied, said and refused without a log
  reading; the invariants; the app; the final review's smaller points.
- The z-score step (the float64 z-score and the near-constant rule): the
  invariant under every reading, the genes zeroed, and the replies against
  Phase A's baseline.
- B5 (Stage 0 reads a protein table with the calibrated check, valuescale):
  each traced table's verdict against B4's, its reply against the median
  method's on the frozen keys, RNA unchanged, the invariants, the check's
  time, refusals, and the same through the app (expectations/b5.json).
- B6 (the deploy assembly): deploy/huggingface/build_space.py stages the
  Space, which then runs on its own, in a fresh interpreter with the hosted
  settings, against this repository's service run the same way: the build
  and its import check, the pipeline's replies on every traced table, GET
  /api/status, every bank file that fits the upload limit through both
  servers, zeros_read, and the reply summaries against B5's
  (expectations/b6.json).

Writes research/notebook-outputs/value_scale_<step>/report.md (expected
against observed, one row per table) and report.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import warnings
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import valuescale  # noqa: E402
from service import app, config  # noqa: E402
from service.pipeline import alignment, fusion, gene_ids, pipeline, smoothing, validation  # noqa: E402
from valuescale.corpus import extract, fetch, variants  # noqa: E402

EXPECTATIONS = REPO / "valuescale" / "bank" / "expectations"
OUT = REPO / "research" / "notebook-outputs"
VERSION = "v4.1"
MAX_CELLS = config.MAX_UPLOAD_CELLS
QUANTILES = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)


def r4(x) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), 4)


def layout_of(text: str) -> str:
    """The parser path a file takes (alignment.header_layout)."""
    text = text[1:] if text.startswith("﻿") else text
    first = re.split(r"\r\n|\r|\n", text, maxsplit=1)[0]
    header = next(csv.reader(io.StringIO(first), delimiter="\t" if first.count("\t") > first.count(",") else ","))
    return alignment.header_layout(header)


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


def _align_and_zscore(bundle, collapsed: alignment.RawMatrix) -> tuple:
    """Stage 1's alignment and the per-gene z-scores of a table after
    duplicates are merged, with two invariants: the mask counts exactly the
    observed values of the matched genes, and each z-scored gene has mean 0
    and SD 1 (or is all 0 when constant, or constant but for rounding:
    config.ZSCORE_NEAR_CONSTANT_SPREAD)."""
    aligned = alignment.align_to_feature_space(collapsed, bundle.feature_genes)
    index = {g: i for i, g in enumerate(bundle.feature_genes)}
    last_row = {}
    for i, g in enumerate(gene_ids.resolve_to_feature_symbols(collapsed.gene_names)):
        if g in index:
            last_row[index[g]] = i
    expected_mask = sum(int((~np.isnan(collapsed.values[i])).sum()) for i in last_row.values())
    z = alignment.zscore_per_gene(collapsed.values)
    observed = ~np.isnan(collapsed.values)
    worst_mean, worst_sd, constant_ok = 0.0, 0.0, True
    for i in range(z.shape[0]):
        obs = observed[i]
        if not obs.any():
            continue
        zi, xi = z[i, obs].astype(np.float64), collapsed.values[i, obs].astype(np.float64)
        if xi.max() - xi.min() <= config.ZSCORE_NEAR_CONSTANT_SPREAD * np.abs(xi).max():
            constant_ok &= bool(np.all(zi == 0))
            continue
        worst_mean = max(worst_mean, abs(zi.mean()))
        worst_sd = max(worst_sd, abs(zi.std() - 1))
    checks = {"mask_sum_equals_observed": int(aligned.mask.sum()) == expected_mask,
              "zscore_mean0_sd1": bool(worst_mean < 1e-4 and worst_sd < 1e-4 and constant_ok)}
    return aligned, z, checks, worst_mean, worst_sd


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
    aligned, z, checks, worst_mean, worst_sd = _align_and_zscore(bundle, collapsed)
    inv.update(checks)
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
        # None is "does not apply"; a NumPy False counts too (Step 1's run tested `is False`
        # and missed four z-score failures: value_scale_step1/notes.md).
        failed = [k for k, ok in inv.items() if ok is not None and not ok]
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


# ---------------------------------------------------------------- Phase A

BASELINE_REPLIES = fetch.ROOT / "phaseA-baseline"  # full replies, untracked; their sha256s are in baseline.json


def traced_table(entry: dict, raw: alignment.RawMatrix) -> alignment.RawMatrix | None:
    """The table D3 traced: None when the service refuses it, otherwise at
    most MAX_CELLS cells, drawn with D3's seed."""
    try:
        validation.validate(raw)
    except validation.ValidationError:
        return None
    if len(raw.cell_ids) > MAX_CELLS:
        keep = np.sort(variants.rng_for(entry["id"], "d3").choice(len(raw.cell_ids), MAX_CELLS, replace=False))
        raw = alignment.RawMatrix(raw.gene_names, [raw.cell_ids[i] for i in keep], raw.values[:, keep])
    return raw


def canonical(response: dict) -> str:
    return json.dumps(json.loads(json.dumps(response)), sort_keys=True)


def phase_a_baseline() -> None:
    """A0: every traced table's full reply on the code before Phase A's change."""
    bank = fetch.load_bank()
    bundle = pipeline.load_bundle(VERSION)
    BASELINE_REPLIES.mkdir(parents=True, exist_ok=True)
    out = OUT / "value_scale_phaseA"
    out.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for entry in bank["entries"]:
        raw = traced_table(entry, load_entry(entry)[0])
        if raw is None:
            hashes[entry["id"]] = None
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            text = canonical(pipeline.run_projection(bundle, raw, modality="prot"))
        (BASELINE_REPLIES / f"{entry['id']}.json").write_bytes(text.encode("utf-8"))
        hashes[entry["id"]] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        print(f"  A0 {entry['id']}: {hashes[entry['id']][:12]}", flush=True)
    payload = {"step": "phaseA-baseline", "run": datetime.now().isoformat(timespec="seconds"),
               "pipeline_version": VERSION, "about": "sha256 of each traced table's full reply (canonical JSON, keys "
               "sorted) on the code before Phase A's change; null for a table the service refuses", "sha256": hashes}
    (out / "baseline.json").write_bytes((json.dumps(payload, indent=1) + "\n").encode("utf-8"))
    print(f"wrote {(out / 'baseline.json').relative_to(REPO).as_posix()}")


READINGS = ("linear", "log")
APP_TABLES = ("pbmc240_diann", "khoury_column_normalized", "scope2_export")


def summary_of(response: dict) -> dict:
    """The reply's summary, as D3 recorded it."""
    levels, reasons, labels = {}, {}, {}
    for c in response["cells"]:
        if c.get("label") is not None:
            levels[c["label_level"]] = levels.get(c["label_level"], 0) + 1
            labels[c["label"]] = labels.get(c["label"], 0) + 1
        else:
            reasons[c["abstain_reason"]] = reasons.get(c["abstain_reason"], 0) + 1
    return {"value_scale": response["value_scale"], "n_cells": len(response["cells"]),
            "n_features_matched": response["n_features_matched"], "levels": levels, "abstain_reasons": reasons,
            "top_labels": dict(sorted(labels.items(), key=lambda x: -x[1])[:5])}


def answer_of(cell: dict) -> str:
    return cell["label"] if cell.get("label") is not None else f"no answer: {cell.get('abstain_reason')}"


def _reading_invariants(bundle, raw: alignment.RawMatrix, stated: str | None, protein_genes,
                        zeros: str | None = None) -> dict:
    """A3: Stage 0 under a reading (and, with a log one, what a 0 means), then
    the stages up to the encoder's input."""
    values0 = raw.values
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scaled, scale = alignment.detect_and_transform_value_scale(values0, stated=stated, zeros=zeros)
        inv = {"no_inf_after_stage0": not np.isinf(scaled).any()}
        made_missing = int((np.isnan(scaled) & ~np.isnan(values0)).sum())
        infinities = int(np.isinf(values0).sum())
        zeros_missing = scale.transformed or scale.zeros_applied == "missing"  # zeros, under the median method
        inv["stage0_missing_as_expected"] = made_missing == (int((values0 == 0).sum()) + infinities if zeros_missing
                                                             else infinities)
        collapsed = alignment.collapse_duplicate_genes(alignment.RawMatrix(raw.gene_names, raw.cell_ids, scaled))
        aligned, _, checks, _, _ = _align_and_zscore(bundle, collapsed)
        inv.update(checks)
        smoothed, aligned_again, _ = pipeline._prepare_query(bundle.feature_genes, raw, "prot", stated, zeros)
        inv["prepare_query_matches_trace"] = bool(np.array_equal(aligned.values, aligned_again.values)
                                                  and np.array_equal(aligned.mask, aligned_again.mask))
        inv["encoder_input_finite"] = bool(np.isfinite(smoothed).all() and np.isfinite(aligned.mask).all())
        got = fusion.protein_query(raw, protein_genes, scale)
        want = fusion.protein_query(alignment.RawMatrix(raw.gene_names, raw.cell_ids, scaled), protein_genes,
                                    alignment.ValueScale("log", False))
        inv["protein_query_reads_as_stage0"] = all(np.array_equal(a, b) for a, b in zip(got, want))
    return inv


def _post(url: str, fields: dict[str, bytes], matrix: bytes) -> tuple[int, dict]:
    boundary = "VALUESCALEDIAGNOSTICS"
    body = b"".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'.encode() + v + b"\r\n"
                    for k, v in fields.items())
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="matrix"; filename="m.tsv"\r\n\r\n'.encode()
             + matrix + f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def a5_through_the_app(bank: dict, replies: dict) -> list[dict]:
    """A5: the request the site sends, to service.app's handler in this process."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.ProjectionHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    rows = []
    try:
        with urllib.request.urlopen(f"{base}/api/status", timeout=600) as response:
            status = json.loads(response.read())
        rows.append({"check": "GET /api/status lists auto, linear and log",
                     "pass": status.get("value_scale", {}).get("choices") == ["auto", "linear", "log"]})
        entries = {e["id"]: e for e in bank["entries"]}
        for table in APP_TABLES:
            matrix = load_entry(entries[table])[2].read_bytes()
            url = f"{base}/api/project"
            got = {}
            for name, fields in (("absent", {}), ("auto", {"value_scale": b"auto"}),
                                 ("linear", {"value_scale": b"linear"}), ("log", {"value_scale": b"log"})):
                code, payload = _post(url, {"modality": b"prot", **fields}, matrix)
                payload.pop("warnings", None)
                got[name] = (code, payload)
            for name in ("absent", "auto", "linear", "log"):
                code, payload = got[name]
                local = replies[table].get("auto" if name in ("absent", "auto") else name)
                if local is None:  # refused locally: a linear reading of negative values
                    ok = code == 400 and "negative" in payload.get("error", "")
                    what = f"{table}, value_scale {name}: 400 naming the negative values"
                else:
                    ok = code == 200 and canonical(payload) == local
                    what = f"{table}, value_scale {name}: 200, equal to pipeline.run_projection's reply"
                rows.append({"check": what, "pass": ok, "status": code,
                             "error": payload.get("error") if code != 200 else None})
            rows.append({"check": f"{table}: absent and auto give the same reply", "pass": got["absent"] == got["auto"]})
        matrix = load_entry(entries[APP_TABLES[0]])[2].read_bytes()
        for value in (b"linear", b"log"):
            code, payload = _post(f"{base}/api/project", {"modality": b"rna", "value_scale": value}, matrix)
            rows.append({"check": f"modality rna, value_scale {value.decode()}: 400 (protein only)",
                         "pass": code == 400 and "protein" in payload.get("error", ""), "status": code,
                         "error": payload.get("error")})
        code, payload = _post(f"{base}/api/project", {"modality": b"prot", "value_scale": b"raw"}, matrix)
        rows.append({"check": "value_scale raw: 400 naming auto, linear and log",
                     "pass": code == 400 and all(c in payload.get("error", "") for c in ("auto", "linear", "log")),
                     "status": code, "error": payload.get("error")})
    finally:
        server.shutdown()
        server.server_close()
    return rows


def phase_a() -> None:
    bank = fetch.load_bank()
    expect = json.loads((EXPECTATIONS / "phaseA.json").read_text(encoding="utf-8"))
    out = OUT / "value_scale_phaseA"
    baseline = json.loads((out / "baseline.json").read_text(encoding="utf-8"))["sha256"]
    d3 = {r["id"]: r for r in json.loads((OUT / "value_scale_step1" / "report.json").read_text(encoding="utf-8"))["D3"]}
    bundle = pipeline.load_bundle(VERSION)
    protein_genes = pipeline.load_bundle("v4.2").protein_genes
    negatives_expected = set(expect["A2_stated_reading"]["refused_linear_tables"])
    rows, replies = [], {}
    for entry in bank["entries"]:
        raw = traced_table(entry, load_entry(entry)[0])
        row = {"id": entry["id"], "label": entry["label"]}
        if raw is None:
            row.update(refused=True, pass_=baseline.get(entry["id"]) is None)
            rows.append(row)
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            auto = json.loads(canonical(pipeline.run_projection(bundle, raw, modality="prot")))
        text = canonical(auto)
        checks = {
            "A1_sha256_as_baseline": hashlib.sha256(text.encode("utf-8")).hexdigest() == baseline.get(entry["id"]),
            "A1_no_stated_key": sorted(auto["value_scale"]) == ["detected", "transformed"],
            "A1_summary_as_D3": all(summary_of(auto)[k] == d3[entry["id"]]["answers"][k]
                                    for k in ("value_scale", "n_cells", "n_features_matched", "levels",
                                              "abstain_reasons", "top_labels")),
        }
        replies[entry["id"]] = {"auto": text}
        has_negative = bool((raw.values[np.isfinite(raw.values)] < 0).any())
        detected = auto["value_scale"]["detected"]
        answers = {"auto": [answer_of(c) for c in auto["cells"]]}
        for stated in READINGS:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    reply = json.loads(canonical(pipeline.run_projection(bundle, raw, modality="prot", stated_scale=stated)))
            except alignment.NotIntensities:
                checks[f"A2_{stated}_refused_as_expected"] = stated == "linear" and has_negative
                replies[entry["id"]][stated] = None
                continue
            replies[entry["id"]][stated] = canonical(reply)
            checks[f"A2_{stated}_refused_as_expected"] = not (stated == "linear" and has_negative)
            checks[f"A2_{stated}_value_scale"] = reply["value_scale"] == {
                "detected": detected, "transformed": stated == "linear", "stated": stated}
            if stated == detected:
                same = json.loads(json.dumps(reply))
                del same["value_scale"]["stated"]
                checks[f"A2_{stated}_equals_automatic"] = canonical(same) == text
            checks[f"A3_{stated}_every_cell_answered_or_abstained"] = all(
                c.get("label") is not None or c.get("abstain_reason") for c in reply["cells"])
            for k, ok in _reading_invariants(bundle, raw, stated, protein_genes).items():
                checks[f"A3_{stated}_{k}"] = ok
            answers[stated] = [answer_of(c) for c in reply["cells"]]
        row.update(refused=False, cells=len(raw.cell_ids), detected=detected, negative=has_negative,
                   expected_negative_refusal=entry["id"] in negatives_expected, checks=checks,
                   failed=[k for k, ok in checks.items() if not ok],
                   answered={k: sum(not a.startswith("no answer") for a in v) for k, v in answers.items()},
                   differ_linear_log=(sum(a != b for a, b in zip(answers["linear"], answers["log"]))
                                      if "linear" in answers and "log" in answers else None),
                   differ_auto_linear=(sum(a != b for a, b in zip(answers["auto"], answers["linear"]))
                                       if "linear" in answers else None))
        row["pass_"] = not row["failed"] and row["negative"] == row["expected_negative_refusal"]
        rows.append(row)
        print(f"  A {entry['id']}: {'PASS' if row['pass_'] else 'FAIL ' + ','.join(row['failed'])}", flush=True)
    print("A5, through the app", flush=True)
    app_rows = a5_through_the_app(bank, replies)
    payload = {"step": "phaseA", "run": datetime.now().isoformat(timespec="seconds"), "pipeline_version": VERSION,
               "tables": rows, "app": app_rows}
    (out / "report.json").write_bytes((json.dumps(payload, indent=1, default=str) + "\n").encode("utf-8"))
    (out / "report.md").write_bytes(report_phase_a(rows, app_rows).encode("utf-8"))
    print(f"wrote {(out / 'report.md').relative_to(REPO).as_posix()}")


def report_phase_a(rows: list, app_rows: list) -> str:
    traced = [r for r in rows if not r["refused"]]
    lines = ["# Value-scale diagnostics, Phase A: the stated reading", "",
             f"Run {datetime.now().strftime('%Y-%m-%d %H:%M')} by research/notebooks/value_scale_diagnostics.py. "
             "Expectations: valuescale/bank/expectations/phaseA.json, written before the change. Baseline: "
             "baseline.json beside this file, the replies before the change.", ""]
    n = sum(r["pass_"] for r in rows)
    lines += [f"## A1 to A3, every bank table: {n} of {len(rows)} pass", "",
              "A1: the automatic reply is the baseline's, byte for byte, and its summary is D3's. A2: a stated reading "
              "is applied and said; stating the rule's own reading changes nothing else; a linear reading of negative "
              "values is refused. A3: the stage invariants hold under each reading.", ""]
    table = []
    for r in rows:
        if r["refused"]:
            table.append([r["id"], "", "", "", "", "", "refused (fewer than 20 cells)" + ("" if r["pass_"] else ", NOT as the baseline")])
            continue
        a = r["answered"]
        table.append([r["id"], r["label"], r["detected"], f"{a.get('auto')}/{a.get('linear', 'refused')}/{a.get('log')}",
                      r["differ_auto_linear"] if r["differ_auto_linear"] is not None else "refused",
                      r["differ_linear_log"] if r["differ_linear_log"] is not None else "",
                      "PASS" if r["pass_"] else "FAIL: " + ", ".join(r["failed"] or ["negative refusal not as expected"])])
    lines += [_md_table(["table", "label", "rule reads", "answered auto/linear/log", "answers changed, auto to linear",
                         "answers differing, linear vs log", "result"], table), ""]
    misread = [r for r in traced if r["label"] == "linear" and r["detected"] == "log"]
    if misread:
        lines += ["## A4, the linear tables the rule reads as log", "",
                  "Reported, not judged: their stated linear reading is the right one.", "",
                  _md_table(["table", "cells", "answered, rule's reading", "answered, stated linear", "answers changed"],
                            [[r["id"], r["cells"], r["answered"]["auto"], r["answered"].get("linear"), r["differ_auto_linear"]]
                             for r in misread]), ""]
    m = sum(r["pass"] for r in app_rows)
    lines += [f"## A5, through the app: {m} of {len(app_rows)} pass", "",
              _md_table(["check", "status", "result"],
                        [[r["check"], r.get("status", ""), "PASS" if r["pass"] else "FAIL" + (f" ({r['error']})" if r.get("error") else "")]
                         for r in app_rows]), ""]
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


APP_TABLES_A2 = ("pbmc240_diann", "furtwangler_log2")


def _without_zeros(reply_text: str) -> str:
    reply = json.loads(reply_text)
    reply["value_scale"].pop("zeros", None)
    return canonical(reply)


def matrix_tsv(raw: alignment.RawMatrix) -> bytes:
    """A traced table as a plain matrix the service reads back to the same
    float32 values (9 significant digits; a missing value empty)."""
    lines = ["gene\t" + "\t".join(raw.cell_ids)]
    for name, row in zip(raw.gene_names, raw.values):
        lines.append(name + "\t" + "\t".join("" if np.isnan(x) else f"{x:.9g}" for x in row.tolist()))
    return ("\n".join(lines) + "\n").encode("utf-8")


def b4_through_the_app(bank: dict, replies: dict, reply_of) -> list[dict]:
    """B4: the zeros field as the site sends it, to service.app's handler in
    this process. A table D3 traced on a subsample (over the service's 2,000
    cells) is sent as that subsample, and compared with the pipeline's reply
    to the subsample as the service parses it back: the parser's row-major
    table and the column-major subsample sum in another order, which moves
    the reply's last digits (notes.md)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.ProjectionHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    url = f"{base}/api/project"
    rows = []
    try:
        with urllib.request.urlopen(f"{base}/api/status", timeout=600) as response:
            status = json.loads(response.read())
        rows.append({"check": "GET /api/status lists the zeros choices",
                     "pass": status.get("value_scale", {}).get("zeros") == ["auto", "missing", "measured"]})
        entries = {e["id"]: e for e in bank["entries"]}
        for table in APP_TABLES_A2:
            raw, reply = replies[table]
            whole, _, upload = load_entry(entries[table])
            sent = upload.read_bytes() if len(raw.cell_ids) == len(whole.cell_ids) else matrix_tsv(raw)
            how = "its file" if len(raw.cell_ids) == len(whole.cell_ids) else f"its {len(raw.cell_ids):,}-cell subsample"
            if len(raw.cell_ids) != len(whole.cell_ids):
                parsed = alignment.parse_matrix_csv(sent.decode("utf-8"))
                assert np.array_equal(parsed.values, raw.values, equal_nan=True), "the subsample reads back exactly"
                reply = reply_of(parsed)
            code, payload = _post(url, {"modality": b"prot", "value_scale": b"log", "zeros": b"missing"}, sent)
            payload.pop("warnings", None)
            rows.append({"check": f"{table} ({how}), value_scale log with zeros missing: 200, equal to "
                                  "pipeline.run_projection's reply",
                         "pass": code == 200 and canonical(payload) == reply, "status": code,
                         "error": payload.get("error") if code != 200 else None})
        matrix = load_entry(entries[APP_TABLES_A2[0]])[2].read_bytes()
        for fields, what in (({"modality": b"prot", "zeros": b"missing"}, "zeros missing without value_scale"),
                             ({"modality": b"prot", "value_scale": b"linear", "zeros": b"missing"},
                              "zeros missing with value_scale linear")):
            code, payload = _post(url, fields, matrix)
            rows.append({"check": f"{what}: 400 naming value_scale log", "status": code, "error": payload.get("error"),
                         "pass": code == 400 and "value_scale log" in payload.get("error", "")})
        code, payload = _post(url, {"modality": b"rna", "zeros": b"missing"}, matrix)
        rows.append({"check": "modality rna with zeros missing: 400", "pass": code == 400, "status": code,
                     "error": payload.get("error")})
        code, payload = _post(url, {"modality": b"prot", "value_scale": b"log", "zeros": b"none"}, matrix)
        rows.append({"check": "zeros none: 400 naming missing and measured", "status": code, "error": payload.get("error"),
                     "pass": code == 400 and "missing" in payload.get("error", "") and "measured" in payload.get("error", "")})
    finally:
        server.shutdown()
        server.server_close()
    return rows


def b5_review_fixes(bundle, raw: alignment.RawMatrix) -> list[dict]:
    """B5: the final review's smaller points, on a bank table and two small arrays."""
    rows = []
    for kw in ({"stated_scale": "log"}, {"stated_scale": "log", "stated_zeros": "missing"}):
        try:
            pipeline.run_projection(bundle, raw, modality="rna", **kw)
            ok = False
        except ValueError as err:
            ok = "RNA" in str(err)
        rows.append({"check": f"the pipeline refuses {kw} on an RNA upload", "pass": ok})
    try:
        alignment.apply_reading(np.array([[1.0]]), "Linear")
        ok = False
    except ValueError:
        ok = True
    rows.append({"check": "apply_reading refuses the reading 'Linear'", "pass": ok})
    try:
        alignment.detect_and_transform_value_scale(np.array([[-5.0, 4000.0]]), stated="linear")
        ok = False
    except alignment.NotIntensities as err:
        ok = str(err).startswith("1 value is negative")
    rows.append({"check": "one negative value is said as '1 value is negative'", "pass": ok})
    return rows


def phase_a2() -> None:
    bank = fetch.load_bank()
    out = OUT / "value_scale_phaseA2"
    out.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((OUT / "value_scale_phaseA" / "baseline.json").read_text(encoding="utf-8"))["sha256"]
    bundle = pipeline.load_bundle(VERSION)
    protein_genes = pipeline.load_bundle("v4.2").protein_genes
    run = lambda raw, **kw: canonical(pipeline.run_projection(bundle, raw, modality="prot", **kw))  # noqa: E731
    rows, app_replies, first_raw = [], {}, None
    for entry in bank["entries"]:
        raw = traced_table(entry, load_entry(entry)[0])
        row = {"id": entry["id"], "label": entry["label"]}
        if raw is None:
            row.update(refused=True, pass_=baseline.get(entry["id"]) is None)
            rows.append(row)
            continue
        first_raw = first_raw or raw
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            auto = run(raw)
            as_log = run(raw, stated_scale="log")
            measured = run(raw, stated_scale="log", stated_zeros="measured")
            missing = run(raw, stated_scale="log", stated_zeros="missing")
        if entry["id"] in APP_TABLES_A2:
            app_replies[entry["id"]] = (raw, missing)
        zeros = int((raw.values == 0).sum())
        reply_missing = json.loads(missing)
        checks = {
            "B1_sha256_as_baseline": hashlib.sha256(auto.encode("utf-8")).hexdigest() == baseline.get(entry["id"]),
            "B2_measured_equals_log": _without_zeros(measured) == as_log,
            "B2_missing_value_scale": reply_missing["value_scale"] == {
                "detected": json.loads(auto)["value_scale"]["detected"], "transformed": False, "stated": "log",
                "zeros": "missing"},
            "B2_no_zeros_no_change": zeros > 0 or _without_zeros(missing) == as_log,
            "B3_every_cell_answered_or_abstained": all(c.get("label") is not None or c.get("abstain_reason")
                                                       for c in reply_missing["cells"]),
        }
        for stated in (None, "linear"):
            try:
                alignment.detect_and_transform_value_scale(raw.values, stated=stated, zeros="missing")
                checks[f"B2_zeros_refused_with_{stated or 'auto'}"] = False
            except alignment.NotIntensities:
                checks[f"B2_zeros_refused_with_{stated or 'auto'}"] = False
            except ValueError:
                checks[f"B2_zeros_refused_with_{stated or 'auto'}"] = True
        for k, ok in _reading_invariants(bundle, raw, "log", protein_genes, zeros="missing").items():
            if k != "zscore_mean0_sd1":  # the next step's (expectations/phaseA2.json, B3_note)
                checks[f"B3_{k}"] = bool(ok)
        before = [answer_of(c) for c in json.loads(measured)["cells"]]
        after = [answer_of(c) for c in reply_missing["cells"]]
        row.update(refused=False, cells=len(raw.cell_ids), zero_share=round(zeros / raw.values.size, 4), checks=checks,
                   failed=[k for k, ok in checks.items() if not ok],
                   answered={"zeros measured": sum(not a.startswith("no answer") for a in before),
                             "zeros missing": sum(not a.startswith("no answer") for a in after)},
                   changed=sum(a != b for a, b in zip(before, after)))
        row["pass_"] = not row["failed"]
        rows.append(row)
        print(f"  B {entry['id']}: {'PASS' if row['pass_'] else 'FAIL ' + ','.join(row['failed'])}", flush=True)
    print("B4, through the app; B5, the review's fixes", flush=True)
    app_rows = b4_through_the_app(bank, app_replies, lambda raw: run(raw, stated_scale="log", stated_zeros="missing"))
    fix_rows = b5_review_fixes(bundle, first_raw)
    payload = {"step": "phaseA2", "run": datetime.now().isoformat(timespec="seconds"), "pipeline_version": VERSION,
               "tables": rows, "app": app_rows, "review_fixes": fix_rows}
    (out / "report.json").write_bytes((json.dumps(payload, indent=1, default=str) + "\n").encode("utf-8"))
    (out / "report.md").write_bytes(report_phase_a2(rows, app_rows, fix_rows).encode("utf-8"))
    print(f"wrote {(out / 'report.md').relative_to(REPO).as_posix()}")


def report_phase_a2(rows: list, app_rows: list, fix_rows: list) -> str:
    lines = ["# Value-scale diagnostics, Phase A2: what a 0 means", "",
             f"Run {datetime.now().strftime('%Y-%m-%d %H:%M')} by research/notebooks/value_scale_diagnostics.py. "
             "Expectations: valuescale/bank/expectations/phaseA2.json, written before the change. Baseline: "
             "../value_scale_phaseA/baseline.json. Explained in notes.md beside this file.", ""]
    n = sum(r["pass_"] for r in rows)
    lines += [f"## B1 to B3, every bank table: {n} of {len(rows)} pass", "",
              "B1: the automatic reply is the baseline's, byte for byte. B2: with a log reading, zeros measured changes "
              "nothing but value_scale.zeros, zeros missing is applied and said, and zeros is refused without a log "
              "reading. B3: the stage invariants under a log reading with zeros missing (the z-score check is the next "
              "step's).", ""]
    table = []
    for r in rows:
        if r["refused"]:
            table.append([r["id"], "", "", "", "", "refused (fewer than 20 cells)" + ("" if r["pass_"] else ", NOT as the baseline")])
            continue
        a = r["answered"]
        table.append([r["id"], r["zero_share"], f"{a['zeros measured']}/{a['zeros missing']}", r["changed"], r["cells"],
                      "PASS" if r["pass_"] else "FAIL: " + ", ".join(r["failed"])])
    lines += [_md_table(["table", "share of 0", "answered, zeros measured/missing", "answers changed", "cells", "result"],
                        table), ""]
    m = sum(r["pass"] for r in app_rows)
    lines += [f"## B4, through the app: {m} of {len(app_rows)} pass", "",
              _md_table(["check", "status", "result"],
                        [[r["check"], r.get("status", ""), "PASS" if r["pass"] else "FAIL" + (f" ({r['error']})" if r.get("error") else "")]
                         for r in app_rows]), ""]
    k = sum(r["pass"] for r in fix_rows)
    lines += [f"## B5, the final review's smaller points: {k} of {len(fix_rows)} pass", "",
              _md_table(["check", "result"], [[r["check"], "PASS" if r["pass"] else "FAIL"] for r in fix_rows]), ""]
    return "\n".join(lines) + "\n"


def _near_constant_genes(values: np.ndarray) -> int:
    """Genes the near-constant rule zeroes: observed in two or more cells, not
    one value, and a spread of at most config.ZSCORE_NEAR_CONSTANT_SPREAD of
    the largest absolute value (alignment.zscore_per_gene)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        top, bottom = np.nanmax(values, axis=1).astype(np.float64), np.nanmin(values, axis=1).astype(np.float64)
    spread, size = top - bottom, np.maximum(np.abs(top), np.abs(bottom))
    return int(((spread > 0) & (spread <= config.ZSCORE_NEAR_CONSTANT_SPREAD * size)).sum())


def _floats(a, b, out: list) -> None:
    if isinstance(b, dict):
        for k in b:
            if k in a:
                _floats(a[k], b[k], out)
    elif isinstance(b, list):
        for x, y in zip(a, b):
            _floats(x, y, out)
    elif isinstance(b, float) and isinstance(a, (int, float)):
        out.append(abs(a - b))


def zscore_step() -> None:
    """Z1 to Z3 and Z5 (expectations/zscore.json): the float64 z-score with the
    near-constant rule, on every traced table, against Phase A's baseline."""
    bank = fetch.load_bank()
    out = OUT / "value_scale_zscore"
    out.mkdir(parents=True, exist_ok=True)
    bundle = pipeline.load_bundle(VERSION)
    protein_genes = pipeline.load_bundle("v4.2").protein_genes
    rows = []
    for entry in bank["entries"]:
        raw = traced_table(entry, load_entry(entry)[0])
        row = {"id": entry["id"], "label": entry["label"]}
        if raw is None:
            row.update(refused=True, pass_=True)
            rows.append(row)
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            fresh = json.loads(canonical(pipeline.run_projection(bundle, raw, modality="prot")))
        before = json.loads((BASELINE_REPLIES / f"{entry['id']}.json").read_text(encoding="utf-8"))
        changed = sum((a.get("label"), a.get("abstain_reason")) != (b.get("label"), b.get("abstain_reason"))
                      for a, b in zip(fresh["cells"], before["cells"]))
        diffs: list = []
        for a, b in zip(fresh["cells"], before["cells"]):
            _floats(a.get("coordinates", []), b.get("coordinates", []), diffs)
        checks, near = {}, {}
        checks["Z3_fields_but_cells_unchanged"] = {k: v for k, v in fresh.items() if k != "cells"} == \
            {k: v for k, v in before.items() if k != "cells"}
        checks["Z3_answers_kept_99pct"] = changed <= 0.01 * len(fresh["cells"])
        checks["Z3_coordinates_within_0.01"] = (max(diffs) if diffs else 0.0) < 0.01
        for stated in (None, "linear", "log"):
            name = stated or "auto"
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    scaled, _ = alignment.detect_and_transform_value_scale(raw.values, stated=stated)
            except alignment.NotIntensities:
                continue
            collapsed = alignment.collapse_duplicate_genes(alignment.RawMatrix(raw.gene_names, raw.cell_ids, scaled))
            near[name] = _near_constant_genes(collapsed.values)
            for k, ok in _reading_invariants(bundle, raw, stated, protein_genes).items():
                checks[f"{'Z1' if k == 'zscore_mean0_sd1' else 'Z5'}_{name}_{k}"] = bool(ok)
        checks["Z2_no_near_constant_gene_under_auto"] = near.get("auto", 0) == 0
        row.update(refused=False, cells=len(raw.cell_ids), answers_changed=changed,
                   largest_coordinate_change=r4(max(diffs) if diffs else 0.0), near_constant=near, checks=checks,
                   failed=[k for k, ok in checks.items() if not ok])
        row["pass_"] = not row["failed"]
        rows.append(row)
        print(f"  Z {entry['id']}: {'PASS' if row['pass_'] else 'FAIL ' + ','.join(row['failed'])} "
              f"(answers changed {changed}, near-constant {near})", flush=True)
    payload = {"step": "zscore", "run": datetime.now().isoformat(timespec="seconds"), "pipeline_version": VERSION,
               "near_constant_spread": config.ZSCORE_NEAR_CONSTANT_SPREAD, "tables": rows}
    (out / "report.json").write_bytes((json.dumps(payload, indent=1, default=str) + "\n").encode("utf-8"))
    traced = [r for r in rows if not r["refused"]]
    lines = ["# Value-scale diagnostics: the float64 z-score", "",
             f"Run {datetime.now().strftime('%Y-%m-%d %H:%M')} by research/notebooks/value_scale_diagnostics.py. "
             "Expectations: valuescale/bank/expectations/zscore.json, written before the change. Baseline: "
             "../value_scale_phaseA/baseline.json (the replies before Phase A). Explained in notes.md beside this file.",
             "", f"## Z1 to Z3 and Z5, every traced table: {sum(r['pass_'] for r in traced)} of {len(traced)} pass", "",
             "Z1: the z-score invariant under the automatic, linear and log readings. Z2: no near-constant gene under "
             "the automatic reading. Z3: against the baseline, every field but the cells unchanged, at least 99% of "
             "answers kept, coordinates within 0.01. Z5: Phase A's other invariants.", "",
             _md_table(["table", "cells", "answers changed", "largest coordinate change", "near-constant genes "
                        "(auto/linear/log)", "result"],
                       [[r["id"], r["cells"], r["answers_changed"], r["largest_coordinate_change"],
                         "/".join(str(r["near_constant"].get(k, "refused")) for k in ("auto", "linear", "log")),
                         "PASS" if r["pass_"] else "FAIL: " + ", ".join(r["failed"])] for r in traced]), ""]
    (out / "report.md").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    print(f"wrote {(out / 'report.md').relative_to(REPO).as_posix()}")


# ---------------------------------------------------------------- B5

B5_APP_TABLES = ("pbmc240_diann", "scope2_export", "pxd064083_t", "furtwangler_log2")
ADDED = ("verdict", "zeros_read", "evidence")  # the reply's fields since B5


def _frozen(reply_text: str) -> str:
    """A reply without B5's fields: what it had before B5."""
    reply = json.loads(reply_text)
    for key in ADDED:
        reply["value_scale"].pop(key, None)
    return canonical(reply)


def _differing_fields(a: dict, b: dict) -> list[str]:
    keys = sorted(set(a) | set(b))
    out = [k for k in keys if k != "value_scale" and a.get(k) != b.get(k)]
    out += [f"value_scale.{k}" for k in sorted(set(a["value_scale"]) | set(b["value_scale"]))
            if a["value_scale"].get(k) != b["value_scale"].get(k)]
    return out


def _with_negatives(raw: alignment.RawMatrix, n: int) -> alignment.RawMatrix:
    values = raw.values.copy()
    for i, j in np.argwhere(np.isfinite(values) & (values > 0))[:n]:
        values[i, j] = -values[i, j]
    return alignment.RawMatrix(raw.gene_names, raw.cell_ids, values)


def b5_through_the_app(bank: dict, traced: dict, reply_of) -> list[dict]:
    """B5_app: the request the site sends when the uploader does not know (no
    value_scale, no zeros), to service.app's handler in this process, as
    b4_through_the_app sends a subsample."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.ProjectionHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    url = f"{base}/api/project"
    rows = []
    try:
        with urllib.request.urlopen(f"{base}/api/status", timeout=600) as response:
            status = json.loads(response.read()).get("value_scale", {})
        rows.append({"check": "GET /api/status lists auto, linear and log, and the zeros choices",
                     "pass": status.get("choices") == ["auto", "linear", "log"]
                     and status.get("zeros") == ["auto", "missing", "measured"]})
        entries = {e["id"]: e for e in bank["entries"]}
        for table in B5_APP_TABLES:
            raw = traced[table]
            whole, _, upload = load_entry(entries[table])
            if len(raw.cell_ids) == len(whole.cell_ids):
                sent, how, reply = upload.read_bytes(), "its file", reply_of(raw)
            else:
                sent, how = matrix_tsv(raw), f"its {len(raw.cell_ids):,}-cell subsample"
                parsed = alignment.parse_matrix_csv(sent.decode("utf-8"))
                assert np.array_equal(parsed.values, raw.values, equal_nan=True), "the subsample reads back exactly"
                reply = reply_of(parsed)
            code, payload = _post(url, {"modality": b"prot"}, sent)
            payload.pop("warnings", None)
            has = code == 200 and all(k in payload.get("value_scale", {}) for k in ADDED)
            rows.append({"check": f"{table} ({how}), nothing stated: 200, equal to pipeline.run_projection's reply, "
                                  "with verdict, zeros_read and evidence",
                         "pass": has and canonical(payload) == reply, "status": code,
                         "error": payload.get("error") if code != 200 else None})
        negative = matrix_tsv(_with_negatives(traced["pbmc240_diann"], 2))
        code, payload = _post(url, {"modality": b"prot"}, negative)
        rows.append({"check": "pbmc240_diann with 2 values made negative, nothing stated: 400, naming them and the "
                              "service's check, with UNDECIDED_NEGATIVES_REASON",
                     "pass": code == 400 and payload.get("error", "").startswith("2 values are negative")
                     and "the service's check" in payload.get("error", "")
                     and payload.get("reason") == alignment.UNDECIDED_NEGATIVES_REASON,
                     "status": code, "error": payload.get("error"), "reason": payload.get("reason")})
        code, payload = _post(url, {"modality": b"prot", "value_scale": b"linear"}, negative)
        rows.append({"check": "the same, value_scale linear: 400 with the stated reading's reason",
                     "pass": code == 400 and payload.get("reason") == app.STATED_LINEAR_REASON,
                     "status": code, "error": payload.get("error"), "reason": payload.get("reason")})
        code, payload = _post(url, {"modality": b"prot", "value_scale": b"log"}, negative)
        rows.append({"check": "the same, value_scale log: 200", "pass": code == 200, "status": code,
                     "error": payload.get("error") if code != 200 else None})
    finally:
        server.shutdown()
        server.server_close()
    return rows


def b5_step() -> None:
    bank = fetch.load_bank()
    expect = json.loads((EXPECTATIONS / "b5.json").read_text(encoding="utf-8"))
    out = OUT / "value_scale_b5"
    out.mkdir(parents=True, exist_ok=True)
    b4 = {r["id"]: r for r in json.loads((OUT / "value_scale_b4" / "report.json").read_text(encoding="utf-8"))["bank"]}
    d3 = {r["id"]: r for r in json.loads((OUT / "value_scale_step1" / "report.json").read_text(encoding="utf-8"))["D3"]}
    bundle = pipeline.load_bundle(VERSION)
    protein_genes = pipeline.load_bundle("v4.2").protein_genes
    changed_expected = expect["B5_frozen_keys"]["changed"]
    started = time.time()

    def reply(raw, method, modality="prot"):
        with warnings.catch_warnings(), alignment.scale_method(method):
            warnings.simplefilter("ignore", RuntimeWarning)
            return canonical(pipeline.run_projection(bundle, raw, modality=modality))

    rows, traced = [], {}
    for entry in bank["entries"]:
        raw = traced_table(entry, load_entry(entry)[0])
        row = {"id": entry["id"], "label": entry["label"]}
        if raw is None:
            row.update(refused="validation")
            rows.append(row)
            continue
        traced[entry["id"]] = raw
        t0 = time.perf_counter()
        report = valuescale.detect(alignment.finite_or_missing(raw.values))
        seconds = time.perf_counter() - t0
        try:
            cal = reply(raw, "calibrated")
        except alignment.NotIntensities as exc:
            row.update(refused="stage0", error=str(exc), detect_seconds=round(seconds, 3))
            rows.append(row)
            continue
        med = reply(raw, "median")
        rna_cal, rna_med = reply(raw, "calibrated", "rna"), reply(raw, "median", "rna")
        c, m = json.loads(cal), json.loads(med)
        scale = c["value_scale"]
        same = _frozen(cal) == med
        with alignment.scale_method("calibrated"):
            invariants = _reading_invariants(bundle, raw, None, protein_genes)
        invariants["every_cell_answered_or_abstained"] = all(x.get("label") is not None or x.get("abstain_reason")
                                                             for x in c["cells"])
        before = [answer_of(x) for x in m["cells"]]
        after = [answer_of(x) for x in c["cells"]]
        row.update(
            refused=None, cells=len(raw.cell_ids), detect_seconds=round(seconds, 3),
            verdict=scale.get("verdict"), b4_verdict=b4[entry["id"]]["verdict"], gate=scale["evidence"].get("gate"),
            reason=scale["evidence"].get("reason"), warning=bool(scale["evidence"].get("warning")),
            calibration=scale["evidence"].get("calibration"),
            median_reads=m["value_scale"]["detected"], detected=scale["detected"], transformed=scale["transformed"],
            zeros_read=scale.get("zeros_read"), frozen_keys_equal=same,
            fields_differing=[] if same else _differing_fields(json.loads(_frozen(cal)), m),
            answers_changed=sum(a != b for a, b in zip(before, after)),
            answered={"median": sum(not a.startswith("no answer") for a in before),
                      "calibrated": sum(not a.startswith("no answer") for a in after)},
            summary=summary_of(c), median_summary=summary_of(m),
            rna_identical=rna_cal == rna_med and not any(k in json.loads(rna_cal)["value_scale"] for k in ADDED),
            invariants=invariants, invariants_failed=[k for k, ok in invariants.items() if not ok])
        rows.append(row)
        print(f"  B5 {entry['id']}: {row['median_reads']}->{row['detected']} verdict {row['verdict']} zeros "
              f"{row['zeros_read']} frozen {'same' if same else 'CHANGED'} answers changed {row['answers_changed']} "
              f"rna {'same' if row['rna_identical'] else 'DIFFERS'} invariants "
              f"{'ok' if not row['invariants_failed'] else row['invariants_failed']} ({seconds:.2f} s)", flush=True)

    print("the golden fixtures' 50-cell slices", flush=True)
    from service.tests.test_golden_fixtures import _load_pbmc240_50, _load_scope2_50
    slices = {}
    for name, loader in (("pbmc240_50", _load_pbmc240_50), ("scope2_50", _load_scope2_50)):
        raw = loader()
        _, s = alignment.detect_and_transform_value_scale(raw.values)
        cal, med = reply(raw, "calibrated"), reply(raw, "median")
        slices[name] = {"verdict": s.verdict, "gate": (s.evidence or {}).get("gate"), "detected": s.detected,
                        "transformed": s.transformed, "zeros_read": s.zeros_read, "frozen_keys_equal": _frozen(cal) == med}

    print("B5_app, through the app", flush=True)
    app_rows = b5_through_the_app(bank, traced, lambda raw: reply(raw, "calibrated"))

    by = {r["id"]: r for r in rows}
    ok = [r for r in rows if r["refused"] is None]
    changed = {r["id"] for r in ok if not r["frozen_keys_equal"]}
    reading_changes = {k for k, v in changed_expected.items() if v.startswith("reading")}
    verdicts = expect["B5_verdicts"]["predicted"]
    predicted_verdict = {i.split(" (")[0]: v for v, ids in verdicts.items() for i in ids}
    p, s = by.get("pbmc240_diann", {}), by.get("scope2_export", {})
    results = {
        "B5_pbmc240": (p.get("verdict"), p.get("detected"), p.get("transformed"), p.get("zeros_read"),
                       p.get("frozen_keys_equal")) == ("linear", "linear", True, "missing", True)
        and (slices["pbmc240_50"]["verdict"], slices["pbmc240_50"]["transformed"],
             slices["pbmc240_50"]["frozen_keys_equal"]) == ("linear", True, True),
        "B5_scope2": (s.get("verdict"), s.get("gate"), s.get("transformed"), s.get("zeros_read"),
                      s.get("frozen_keys_equal")) == ("log", "negatives", False, "measured", True)
        and (slices["scope2_50"]["verdict"], slices["scope2_50"]["transformed"],
             slices["scope2_50"]["frozen_keys_equal"]) == ("log", False, True),
        "B5_pxd064083": all(by.get(t, {}).get("verdict") == "linear" and by.get(t, {}).get("transformed")
                            for t in ("pxd064083_t", "pxd064083_b")),
        "B5_verdicts": all(r["verdict"] == predicted_verdict.get(r["id"]) == r["b4_verdict"]
                           and r["calibration"] == "protein-v1" for r in ok)
        and {r["id"] for r in ok if r["warning"]} == {"pxd043355_pd"},
        "B5_frozen_keys": changed == set(changed_expected)
        and all(by[t]["detected"] == "linear" and by[t]["transformed"] for t in reading_changes)
        and all((by[t]["detected"], by[t]["transformed"], by[t]["zeros_read"]) == ("log", False, "missing")
                for t in set(changed_expected) - reading_changes),
        "B5_rna": all(r["rna_identical"] for r in ok),
        "B5_invariants": all(not r["invariants_failed"] for r in ok),
        "B5_time": max(r["detect_seconds"] for r in ok) < 3,
        "B5_refusals": not [r for r in rows if r["refused"] == "stage0"]
        and len([r for r in rows if r["refused"] == "validation"]) == 7,
        "B5_app": all(r["pass"] for r in app_rows),
    }
    slowest = max(ok, key=lambda r: r["detect_seconds"])
    payload = {"step": "b5", "run": datetime.now().isoformat(timespec="seconds"), "pipeline_version": VERSION,
               "method": config.VALUE_SCALE_METHOD, "seconds": round(time.time() - started),
               "results": results, "slowest_detect": {"id": slowest["id"], "seconds": slowest["detect_seconds"]},
               "slices": slices, "tables": rows, "app": app_rows}
    (out / "report.json").write_bytes((json.dumps(payload, indent=1, default=str) + "\n").encode("utf-8"))
    (out / "report.md").write_bytes(report_b5(payload, d3).encode("utf-8"))
    print(f"wrote {(out / 'report.md').relative_to(REPO).as_posix()}")


def report_b5(payload: dict, d3: dict) -> str:
    rows, results = payload["tables"], payload["results"]
    ok = [r for r in rows if r["refused"] is None]
    lines = ["# Value-scale diagnostics, B5: Stage 0 with the calibrated check", "",
             f"Run {datetime.now().strftime('%Y-%m-%d %H:%M')} by research/notebooks/value_scale_diagnostics.py "
             f"({payload['seconds']:,} s). Expectations: valuescale/bank/expectations/b5.json, written before the run. "
             "Baseline: the same code under the median method (alignment.scale_method), in the same run. Explained in "
             "notes.md beside this file.", "",
             "## The rows", "",
             _md_table(["row", "result"], [[k, "PASS" if v else "FAIL"] for k, v in results.items()]), "",
             f"The slowest check: {payload['slowest_detect']['id']}, {payload['slowest_detect']['seconds']} s.", "",
             f"## Every traced table ({len(ok)})", "",
             _md_table(["table", "label", "cells", "B4 verdict", "verdict", "median rule read", "now read", "a 0 read as",
                        "frozen keys", "answers changed", "answered median/check", "RNA", "invariants", "check s"],
                       [[r["id"], r["label"], r["cells"], r["b4_verdict"], r["verdict"], r["median_reads"],
                         r["detected"], r["zeros_read"],
                         "equal" if r["frozen_keys_equal"] else "changed: " + ", ".join(r["fields_differing"]),
                         r["answers_changed"], f"{r['answered']['median']}/{r['answered']['calibrated']}",
                         "same" if r["rna_identical"] else "DIFFERS",
                         "ok" if not r["invariants_failed"] else ", ".join(r["invariants_failed"]), r["detect_seconds"]]
                        for r in ok]), ""]
    refused = [r for r in rows if r["refused"]]
    lines += ["## Refused", "", _md_table(["table", "by", "error"],
                                         [[r["id"], r["refused"], r.get("error", "fewer than 20 cells")] for r in refused]), ""]
    lines += ["## The golden fixtures' 50-cell slices", "",
              _md_table(["slice", "verdict", "gate", "read", "transformed", "a 0 read as", "frozen keys"],
                        [[k, v["verdict"], v["gate"], v["detected"], v["transformed"], v["zeros_read"],
                          "equal" if v["frozen_keys_equal"] else "changed"] for k, v in payload["slices"].items()]), ""]
    lines += ["## PXD064083 against D3 (reported, not judged)", ""]
    for t in ("pxd064083_t", "pxd064083_b"):
        r = next((x for x in ok if x["id"] == t), None)
        if r is None:
            continue
        lines += [f"**{t}**, {r['cells']} cells:", "",
                  _md_table(["", "levels", "no answer, by reason", "top labels"],
                            [["D3 (median rule, read log)", d3[t]["answers"]["levels"], d3[t]["answers"]["abstain_reasons"],
                              d3[t]["answers"]["top_labels"]],
                             ["B5 (the check, read linear)", r["summary"]["levels"], r["summary"]["abstain_reasons"],
                              r["summary"]["top_labels"]]]), ""]
    lines += [f"## B5_app, through the app: {sum(r['pass'] for r in payload['app'])} of {len(payload['app'])} pass", "",
              _md_table(["check", "status", "result"],
                        [[r["check"], r.get("status", ""), "PASS" if r["pass"] else "FAIL"
                          + (f" ({r.get('error')}; {r.get('reason')})" if r.get("error") else "")]
                         for r in payload["app"]]), ""]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- B6

SPACE = REPO / "deploy" / "huggingface" / "space"
FORM_SLACK = 4096  # bytes of the multipart form around a file

# Every B6 child runs this first (python -I -B -c): its root is the only place
# service and valuescale can come from, and it says where they came from.
B6_CHILD = """\
import json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
import service, valuescale
where = {m.__name__: str(pathlib.Path(m.__file__).resolve()) for m in (service, valuescale)}
if not all(pathlib.Path(p).is_relative_to(root) for p in where.values()):
    raise SystemExit("not imported from " + str(root) + ": " + json.dumps(where))
print(json.dumps(where), flush=True)
"""
# The pipeline on each table saved in argv[2] (.npz), its replies to argv[3].
B6_PIPELINE = B6_CHILD + """\
import warnings
import numpy as np
from service.pipeline import alignment, pipeline, validation
tables, out = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
bundle = pipeline.load_bundle("v4.1")
canonical = lambda r: json.dumps(json.loads(json.dumps(r)), sort_keys=True)
for path in sorted(tables.glob("*.npz")):
    with np.load(path, allow_pickle=False) as z:
        raw = alignment.RawMatrix([str(g) for g in z["genes"]], [str(c) for c in z["cells"]], z["values"])
    result = {}
    try:
        validation.validate(raw)
    except validation.ValidationError as exc:
        result["validation"] = str(exc)
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            for modality in ("prot", "rna"):
                result[modality] = canonical(pipeline.run_projection(bundle, raw, modality=modality))
    (out / (path.stem + ".json")).write_bytes(json.dumps(result).encode("utf-8"))
"""
# The service's server, as the Dockerfile's CMD starts it (python -m service.app).
B6_SERVER = B6_CHILD + """\
import runpy
runpy.run_module("service.app", run_name="__main__", alter_sys=True)
"""


def _rehearse():
    spec = importlib.util.spec_from_file_location("rehearse", REPO / "deploy" / "huggingface" / "rehearse.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _b6_env(port: int | None = None) -> dict:
    """This environment without any VIVOME_ setting, with the hosted ones
    (and, for a server, 127.0.0.1:port without the site's secret)."""
    base = {k: v for k, v in os.environ.items() if not k.startswith("VIVOME_")}
    rehearse = _rehearse()
    return rehearse.rehearsal_env(port, base) if port else {**base, **rehearse.hosted_env()}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _where(lines: list[str]) -> dict | None:
    """The child's first line: where it imported service and valuescale from."""
    for line in lines:
        try:
            found = json.loads(line)
        except ValueError:
            continue
        if isinstance(found, dict) and set(found) == {"service", "valuescale"}:
            return found
    return None


def b6_build() -> dict:
    """B6_build: build_space.py from this tree, and what it staged."""
    run = subprocess.run([sys.executable, str(REPO / "deploy" / "huggingface" / "build_space.py")], cwd=REPO,
                         capture_output=True, text=True)
    printed = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else ""
    found = re.search(r"\((\d+) modules import from the staged folder alone\)", printed)
    manifest = json.loads((SPACE / "space_manifest.json").read_text(encoding="utf-8")) if run.returncode == 0 else {}
    staged = {p: f for p, f in manifest.get("files", {}).items() if p.split("/")[0] in ("service", "valuescale")}
    differing = [p for p, f in staged.items() if not (REPO / p).is_file() or _sha256_file(REPO / p) != f["sha256"]]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return {"exit": run.returncode, "printed": printed,
            "stderr_tail": run.stderr.strip().splitlines()[-3:] if run.returncode else [],
            "modules": int(found.group(1)) if found else None, "commit": manifest.get("commit"), "head": head.strip(),
            "uncommitted_changes": manifest.get("uncommitted_changes"),
            "pipeline_version": manifest.get("pipeline_version"), "staged_files": len(staged), "differing": differing,
            "valuescale_files": sorted(p for p in staged if p.startswith("valuescale/")),
            "valuescale_expected": sorted([f"valuescale/{p.name}" for p in (REPO / "valuescale").glob("*.py")]
                                          + ["valuescale/calibration/protein-v1.json"])}


def b6_pipeline(root: Path, tables: Path, out: Path) -> dict:
    """B6_pipeline's side for one root: every saved table through its pipeline."""
    out.mkdir(parents=True, exist_ok=True)
    run = subprocess.run([sys.executable, "-I", "-B", "-c", B6_PIPELINE, str(root), str(tables), str(out)], cwd=root,
                         env=_b6_env(), capture_output=True, text=True)
    return {"exit": run.returncode, "where": _where(run.stdout.splitlines()),
            "stderr_tail": run.stderr.strip().splitlines()[-3:] if run.returncode else []}


def b6_server(root: Path, requests: list) -> dict:
    """B6_status and B6_app's side for one root: its server, started as the
    Dockerfile starts it with the hosted settings, and every request sent to it."""
    rehearse = _rehearse()
    port = rehearse.free_port()
    base = f"http://127.0.0.1:{port}"
    replies = {}
    with tempfile.TemporaryFile() as log:
        server = subprocess.Popen([sys.executable, "-I", "-B", "-u", "-c", B6_SERVER, str(root)], cwd=root,
                                  env=_b6_env(port), stdout=log, stderr=subprocess.STDOUT)
        try:
            rehearse.wait_until_ready(base, server)
            with urllib.request.urlopen(f"{base}/api/status", timeout=600) as response:
                status = json.loads(response.read())
            for key, fields, matrix in requests:
                code, payload = _post(f"{base}/api/project", fields, matrix())
                replies[key] = {"status": code, "sha256": hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest(),
                                "error": payload.get("error") if code != 200 else None,
                                "reason": payload.get("reason") if code != 200 else None}
        finally:
            server.terminate()
            server.wait(timeout=60)
        log.seek(0)
        lines = log.read().decode("utf-8", "replace").splitlines()
    return {"status": status, "replies": replies, "where": _where(lines)}


def b6_step() -> None:
    bank = fetch.load_bank()
    expect = json.loads((EXPECTATIONS / "b6.json").read_text(encoding="utf-8"))
    out = OUT / "value_scale_b6"
    out.mkdir(parents=True, exist_ok=True)
    b5 = {r["id"]: r for r in json.loads((OUT / "value_scale_b5" / "report.json").read_text(encoding="utf-8"))["tables"]}
    started = time.time()

    print("B6_build: build_space.py", flush=True)
    build = b6_build()
    print(f"  {build['printed']}", flush=True)

    limit = int(float(_rehearse().hosted_env()["VIVOME_MAX_UPLOAD_MB"]) * 2**20)
    rows, requests, traced = [], [], {}
    with tempfile.TemporaryDirectory() as tmp:
        tables = Path(tmp) / "tables"
        tables.mkdir()
        for entry in bank["entries"]:
            whole, _, upload = load_entry(entry)
            raw = traced_table(entry, whole)
            row = {"id": entry["id"], "label": entry["label"], "refused": "validation" if raw is None else None}
            kept = whole if raw is None else raw
            if raw is not None:
                traced[entry["id"]] = raw
            np.savez(tables / f"{entry['id']}.npz", genes=np.array(kept.gene_names), cells=np.array(kept.cell_ids),
                     values=kept.values)
            if raw is None or len(raw.cell_ids) == len(whole.cell_ids):
                row["sent_as"], size = "its file", upload.stat().st_size
                matrix = (lambda path=upload: path.read_bytes())
            else:
                row["sent_as"] = f"its {len(raw.cell_ids):,}-cell subsample"
                matrix = (lambda r=raw: matrix_tsv(r))
                size = len(matrix())
            row.update(cells=len(kept.cell_ids), mib=round(size / 2**20, 2), over_limit=size + FORM_SLACK > limit)
            if not row["over_limit"]:
                for modality in ("prot", "rna"):
                    requests.append((f"{entry['id']}|{modality}", {"modality": modality.encode()}, matrix))
            rows.append(row)
        negative = matrix_tsv(_with_negatives(traced["pbmc240_diann"], 2))
        cases = {"nothing stated": {"modality": b"prot"},
                 "value_scale linear": {"modality": b"prot", "value_scale": b"linear"},
                 "value_scale log": {"modality": b"prot", "value_scale": b"log"},
                 "value_scale log, zeros measured": {"modality": b"prot", "value_scale": b"log", "zeros": b"measured"}}
        requests += [(f"case|{name}", fields, (lambda m=negative: m)) for name, fields in cases.items()]

        sides = {"space": SPACE, "repo": REPO}
        pipe = {}
        for side, root in sides.items():
            print(f"B6_pipeline: {side}", flush=True)
            pipe[side] = b6_pipeline(root, tables, Path(tmp) / side)
        results_of = {side: {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (Path(tmp) / side).glob("*.json")}
                      for side in sides}
        serve = {}
        for side, root in sides.items():
            print(f"B6_app: {side}'s server, {len(requests)} requests", flush=True)
            serve[side] = b6_server(root, requests)

        for row in rows:
            space, repo = results_of["space"].get(row["id"], {}), results_of["repo"].get(row["id"], {})
            if row["refused"]:
                row["pipeline_identical"] = {"validation": "validation" in space and space == repo}
                row["validation_error"] = space.get("validation")
            else:
                row["pipeline_identical"] = {m: m in space and space.get(m) == repo.get(m) for m in ("prot", "rna")}
                reply = json.loads(space["prot"]) if "prot" in space else {"value_scale": {}, "cells": []}
                scale = reply["value_scale"]
                row.update(verdict=scale.get("verdict"), detected=scale.get("detected"),
                           transformed=scale.get("transformed"), zeros_read=scale.get("zeros_read"))
                if "prot" in space:
                    now = summary_of(reply)
                    before = json.loads(json.dumps(b5[row["id"]]["summary"]))
                    now["value_scale"].pop("zeros_read", None)
                    before["value_scale"].pop("zeros_read", None)
                    row["same_as_b5"] = now == before
            if not row["over_limit"]:
                row["app"] = {m: {side: serve[side]["replies"][f"{row['id']}|{m}"]["status"] for side in sides}
                              | {"identical": serve["space"]["replies"][f"{row['id']}|{m}"]
                                 == serve["repo"]["replies"][f"{row['id']}|{m}"]} for m in ("prot", "rna")}
            print(f"  {row['id']}: pipeline {row['pipeline_identical']} app "
                  f"{ {m: v['identical'] for m, v in row.get('app', {}).items()} or 'over the limit'} "
                  f"zeros_read {row.get('zeros_read')}", flush=True)

    case_rows = [{"case": name, **{side: serve[side]["replies"][f"case|{name}"] for side in sides},
                  "identical": serve["space"]["replies"][f"case|{name}"] == serve["repo"]["replies"][f"case|{name}"]}
                 for name in cases]
    ok = [r for r in rows if not r["refused"]]
    small = [r for r in rows if r["refused"]]
    sent = [r for r in rows if not r["over_limit"]]
    zeros = expect["B6_zeros"]["predicted"]
    predicted_zeros = {i.split(" (")[0]: v for v, ids in zeros.items() for i in ids}
    status = serve["space"]["status"]
    wheres = {f"pipeline {s}": pipe[s]["where"] for s in sides} | {f"server {s}": serve[s]["where"] for s in sides}
    case = {c["case"]: c for c in case_rows}
    results = {
        "B6_build": build["exit"] == 0 and build["modules"] == 31 and build["commit"] == build["head"]
        and build["uncommitted_changes"] is False and build["pipeline_version"] == "v4.1" and not build["differing"]
        and build["valuescale_files"] == build["valuescale_expected"],
        "B6_isolated": all(w is not None for w in wheres.values())
        and all(Path(p).is_relative_to(sides[k.split()[1]].resolve()) for k, w in wheres.items() if w for p in w.values()),
        "B6_pipeline": all(pipe[s]["exit"] == 0 for s in sides) and len(ok) == 30 and len(small) == 7
        and all(all(r["pipeline_identical"].values()) for r in rows),
        "B6_status": status == serve["repo"]["status"] and status.get("status") == "ready"
        and status.get("pipeline_version") == "v4.1"
        and status.get("limits") == {"max_cells": 2000, "max_upload_mb": 31.0, "concurrent_projections": 1}
        and status.get("value_scale", {}).get("choices") == ["auto", "linear", "log"]
        and status.get("value_scale", {}).get("zeros") == ["auto", "missing", "measured"],
        "B6_app": len(sent) == 33 and all(r["app"][m]["identical"] for r in sent for m in ("prot", "rna"))
        and all(r["app"][m]["space"] == (400 if r["refused"] else 200) for r in sent for m in ("prot", "rna"))
        and {r["id"] for r in rows if r["over_limit"]} == {"dusszachniewicz_maxquant", "scope2_export",
                                                         "khoury_column_normalized", "furtwangler_log2_imputed"}
        and all(c["identical"] for c in case_rows)
        and (case["nothing stated"]["space"]["status"], case["nothing stated"]["space"]["reason"])
        == (400, alignment.UNDECIDED_NEGATIVES_REASON)
        and (case["value_scale linear"]["space"]["status"], case["value_scale linear"]["space"]["reason"])
        == (400, app.STATED_LINEAR_REASON)
        and case["value_scale log"]["space"]["status"] == 200
        and case["value_scale log, zeros measured"]["space"]["status"] == 200,
        "B6_zeros": all(r["zeros_read"] == predicted_zeros.get(r["id"]) for r in ok),
        "B6_since_b5": all(r.get("same_as_b5") for r in ok),
    }
    payload = {"step": "b6", "run": datetime.now().isoformat(timespec="seconds"), "pipeline_version": VERSION,
               "seconds": round(time.time() - started), "results": results, "build": build,
               "children": {"pipeline": pipe, "where": wheres}, "status": {s: serve[s]["status"] for s in sides},
               "tables": rows, "cases": case_rows}
    (out / "report.json").write_bytes((json.dumps(payload, indent=1, default=str) + "\n").encode("utf-8"))
    (out / "report.md").write_bytes(report_b6(payload).encode("utf-8"))
    print(f"wrote {(out / 'report.md').relative_to(REPO).as_posix()}")


def report_b6(payload: dict) -> str:
    rows, results, build = payload["tables"], payload["results"], payload["build"]
    yes = lambda v: "same" if v else "DIFFERS"  # noqa: E731
    lines = ["# Value-scale diagnostics, B6: the staged Space against this repository's service", "",
             f"Run {datetime.now().strftime('%Y-%m-%d %H:%M')} by research/notebooks/value_scale_diagnostics.py "
             f"({payload['seconds']:,} s). Expectations: valuescale/bank/expectations/b6.json, written before the run. "
             "Each side ran in its own fresh interpreter with the hosted settings: the Space from "
             "deploy/huggingface/space alone, the repository's service from the repository root. Explained in "
             "notes.md beside this file.", "",
             "## The rows", "",
             _md_table(["row", "result"], [[k, "PASS" if v else "FAIL"] for k, v in results.items()]), "",
             "## The build", "",
             f"- build_space.py exit {build['exit']}: {build['printed']}",
             f"- space_manifest.json: commit {build['commit']} (HEAD {build['head']}), uncommitted_changes "
             f"{build['uncommitted_changes']}, pipeline_version {build['pipeline_version']}",
             f"- {build['staged_files']} staged files under service/ and valuescale/; differing from the repository's: "
             f"{build['differing'] or 'none'}",
             f"- the staged valuescale/: {', '.join(build['valuescale_files'])}", "",
             "## Where each child imported from", "",
             _md_table(["child", "service", "valuescale"],
                       [[k, (w or {}).get("service"), (w or {}).get("valuescale")]
                        for k, w in payload["children"]["where"].items()]), "",
             f"## Every bank table ({len(rows)})", "",
             _md_table(["table", "label", "cells", "sent as", "MiB", "pipeline prot", "pipeline rna",
                        "app prot (Space/repo)", "app rna (Space/repo)", "verdict", "a 0 read as", "summary vs B5"],
                       [[r["id"], r["label"], r["cells"], r["sent_as"], r["mib"],
                         yes(r["pipeline_identical"].get("prot", r["pipeline_identical"].get("validation"))),
                         yes(r["pipeline_identical"].get("rna", r["pipeline_identical"].get("validation"))),
                         *(["over 31 MiB, not sent"] * 2 if r["over_limit"] else
                           [f"{r['app'][m]['space']}/{r['app'][m]['repo']} {yes(r['app'][m]['identical'])}"
                            for m in ("prot", "rna")]),
                         r.get("verdict", "refused by validation"), r.get("zeros_read"),
                         "" if r["refused"] else yes(r.get("same_as_b5"))]
                        for r in rows]), "",
             "## pbmc240_diann with 2 values made negative, through both servers", "",
             _md_table(["request", "Space", "repo", "identical", "reason"],
                       [[c["case"], c["space"]["status"], c["repo"]["status"], yes(c["identical"]),
                         c["space"].get("reason") or ""] for c in payload["cases"]]), "",
             "## GET /api/status", "",
             f"- the Space: `{json.dumps(payload['status']['space'], sort_keys=True)}`",
             f"- the repository: `{json.dumps(payload['status']['repo'], sort_keys=True)}`", ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    steps = {"step1": step1, "phaseA-baseline": phase_a_baseline, "phaseA": phase_a, "phaseA2": phase_a2, "zscore": zscore_step,
             "b5": b5_step, "b6": b6_step}
    parser.add_argument("--step", choices=tuple(steps), required=True)
    args = parser.parse_args()
    steps[args.step]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
