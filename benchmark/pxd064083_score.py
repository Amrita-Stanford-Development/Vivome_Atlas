"""PXD064083, sorted single T and B cells: the scoring, once
(research/benchmark/protocol-pxd064083.md, rules 7 and 8). Written and
rehearsed before any of the deposit's data files was downloaded or read.

Inputs: benchmark/pxd064083_intake.py's outputs and, as secondary measures,
the corrected baselines' correlation and PCA kNN runs on the intake's matrix
(benchmark/baselines_corrected.py, dataset heldout_pxd064083, original labels).

Primary, per candidate (v4.1 the headline; every candidate reported), on the
upload of the genes both searches report: S = P(B) - P(CD4T or CD8T) over the
coarse types; AUROC, B cells over T cells; one-sided p from 10,000 label
permutations, seed 0; pass if p < 0.05.

Secondary, reported and never deciding: the same AUROC on the union upload
and by donor status; balanced accuracy of the best guess over the two
lineages, a guess right when its class is in the cell's group (B cell or
T cell, the reference hierarchy); the coarse best guesses and abstention per
lineage; answers committed and correct when committed at the stated level
(a class or group in the cell's group, or the lymphoid lineage); the
baselines' balanced accuracy and coarse calls.

    python -m benchmark.pxd064083_score --rehearse
    python -m benchmark.pxd064083_score              # once

Writes research/benchmark/heldout/pxd064083/ (summary.json, scores.csv); a
rehearsal writes benchmark/results/heldout_pxd064083_rehearsal/tables/ and its
summary to research/benchmark/heldout/rehearsals/pxd064083.json. The real
scoring refuses to run twice.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import baselines_corrected, datasets
from benchmark.baselines_score import hierarchy
from benchmark.fulcher2026_score import COARSE
from benchmark.heldout_intake import MODELS, out_dir
from benchmark.heldout_score import ALPHA, HEADLINE, auroc_with_p, contrast_score, shares
from benchmark.khoury2026_embed import refuse_overrides
from benchmark.pxd064083_intake import NAME, PROTOCOL
from benchmark.sorted_cd4cd8_intake import sha256

REPO = datasets.REPO
GROUP = {"B": "B cell", "T": "T cell"}  # the reference hierarchy's group for each sorted lineage
BASELINE_ARMS = {"correlation": "corr_unrestricted", "pca": "knn_unrestricted"}
STATEMENT = ("Single T and B cells isolated by their surface markers (CD3, CD19), so the labels are independent "
             "of the protein data. One lab, one search per lineage, blood of ALS patients and healthy controls; "
             "a T-against-B lineage test, not a test of finer types.")


def tables_dir(rehearse: bool) -> Path:
    return out_dir(NAME, True) / "tables" if rehearse else REPO / "research" / "benchmark" / "heldout" / NAME


def rehearsal_record() -> Path:
    return REPO / "research" / "benchmark" / "heldout" / "rehearsals" / f"{NAME}.json"


def check_outputs(directory: Path) -> dict:
    """Every file the intake recorded is unchanged since, or the scorer stops."""
    record = json.loads((directory / "intake.json").read_text(encoding="utf-8"))
    if not record.get("outputs"):
        raise SystemExit("intake.json records no outputs, so nothing the scorer reads can be checked")
    changed = [n for n, digest in record["outputs"].items() if sha256(directory / n) != digest]
    if changed:
        raise SystemExit(f"changed since the intake recorded them: {changed}; the scorer reads only what the intake wrote")
    return record


def auroc(score: np.ndarray, groups: np.ndarray) -> dict:
    positive = groups == "B"
    if positive.all() or not positive.any():
        return {"void": True, "reason": "no T cells" if positive.all() else "no B cells",
                "n_b": int(positive.sum()), "n_t": int((~positive).sum())}
    auc, p = auroc_with_p(score, positive)
    return {"auroc": round(auc, 4), "p": round(p, 6), "n_b": int(positive.sum()), "n_t": int((~positive).sum()),
            "void": False}


def in_group(label: str, level: str, lineage: str, h: dict) -> bool:
    """An answer or a guess names the cell's sorted lineage: a class in its
    group, the group itself, or (answers only) the lymphoid lineage."""
    if not label:
        return False
    if level == "class":
        return h[label]["group"] == GROUP[lineage]
    if level == "group":
        return label == GROUP[lineage]
    return level == "lineage" and label == "lymphoid"


def balanced(right: np.ndarray, groups: np.ndarray) -> float:
    return round(100 * float(np.mean([right[groups == g].mean() for g in ("B", "T") if (groups == g).any()])), 2)


def candidate(labels: pd.DataFrame, pred: pd.DataFrame, union_pred: pd.DataFrame, score: np.ndarray,
              union_score: np.ndarray, h: dict) -> dict:
    groups = labels["group"].to_numpy()
    out = {"primary": {"statistic": "AUROC of S = P(B) - P(CD4T or CD8T), B over T, the genes both searches report",
                       **auroc(score, groups)}}
    out["primary"]["pass"] = bool(not out["primary"]["void"] and out["primary"]["p"] < ALPHA)
    guess_right = np.array([in_group(g, "class", lin, h) for g, lin in zip(pred["best_guess"], groups)])
    committed = ~pred["abstained"].to_numpy()
    answer_right = np.array([in_group(l, lv, lin, h) for l, lv, lin in zip(pred["label"], pred["label_level"], groups)])
    coarse = pred["best_guess"].map(lambda c: COARSE.get(c, "other") if c else "none")
    out["secondary"] = {
        "auroc_union": auroc(union_score, groups),
        "auroc_by_status": {s: auroc(score[labels["status"].eq(s).to_numpy()], groups[labels["status"].eq(s).to_numpy()])
                            for s in sorted(labels["status"].unique())},
        "best_guess_balanced_accuracy": balanced(guess_right, groups),
        "best_guess_right_pct": {g: round(100 * float(guess_right[groups == g].mean()), 1) for g in ("B", "T")},
        "best_guess_coarse_pct": {g: shares(coarse[groups == g]) for g in ("B", "T")},
        "abstained_pct": {g: round(100 * float((~committed)[groups == g].mean()), 1) for g in ("B", "T")},
        "answers_committed_pct": round(100 * float(committed.mean()), 2),
        "answers_correct_when_committed_pct": (round(100 * float(answer_right[committed].mean()), 2)
                                               if committed.any() else None),
        "answer_level_pct": shares(pred.loc[committed, "label_level"]) if committed.any() else {},
        "union_best_guess_balanced_accuracy": balanced(
            np.array([in_group(g, "class", lin, h) for g, lin in zip(union_pred["best_guess"], groups)]), groups),
    }
    return out


def baselines(rehearse: bool, labels: pd.DataFrame, h: dict) -> dict:
    dataset = f"heldout_{NAME}_rehearsal" if rehearse else f"heldout_{NAME}"
    groups = labels["group"].to_numpy()
    found = {}
    for tool, column in BASELINE_ARMS.items():
        path = baselines_corrected.out_dir("original") / dataset / f"{tool}_seed0_pred.csv"
        if not path.exists():
            found[tool] = "missing"
            continue
        pred = pd.read_csv(path, keep_default_na=False, dtype={"cell_id": str}).set_index("cell_id")
        calls = pred.reindex(labels["cell_id"])[column].fillna("")
        right = np.array([bool(c) and c in h and in_group(c, "class", lin, h) for c, lin in zip(calls, groups)])
        found[tool] = {"balanced_accuracy": balanced(right, groups),
                       "coarse_pct": {g: shares(calls[groups == g].map(lambda c: COARSE.get(c, "other")))
                                      for g in ("B", "T")}}
    return found


def read_pred(path: Path, cell_ids: list[str]) -> pd.DataFrame:
    pred = pd.read_csv(path, keep_default_na=False, dtype={"cell_id": str})
    pred["abstained"] = pred["abstained"].astype(str).eq("True")
    if pred["cell_id"].tolist() != cell_ids:
        raise SystemExit(f"{path.name} rows are not in cell_ids.txt order")
    return pred


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearse", action="store_true")
    args = parser.parse_args(argv)
    refuse_overrides()
    src, tables = out_dir(NAME, args.rehearse), tables_dir(args.rehearse)
    if not args.rehearse and (tables / "summary.json").exists():
        sys.exit(f"{tables / 'summary.json'} exists: this set is scored once")
    intake = check_outputs(src)
    labels = pd.read_csv(src / "label_map.csv", dtype={"cell_id": str, "sample": str, "donor": str, "status": str})
    cell_ids = [c for c in (src / "cell_ids.txt").read_text(encoding="utf-8").splitlines() if c]
    if labels["cell_id"].tolist() != cell_ids:
        raise SystemExit("label_map.csv and cell_ids.txt disagree")
    groups = labels["group"].to_numpy()
    counts = {g: int((groups == g).sum()) for g in ("B", "T")}
    h = hierarchy()
    summary = {"set": NAME, "protocol": PROTOCOL, "rehearsal": args.rehearse, "statement": STATEMENT,
               "headline": MODELS[HEADLINE], "label_map_sha256": sha256(src / "label_map.csv"),
               "intake_source": intake["source"], "cells": counts,
               "donors": {g: int(labels.loc[groups == g, "donor"].nunique()) for g in ("B", "T")},
               "merge": intake["merge"], "candidates": {}}
    per_cell = labels.copy()
    void = min(counts.values()) < 20
    for key, version in MODELS.items():
        pred, union = read_pred(src / f"{key}_pred.csv", cell_ids), read_pred(src / "union" / f"{key}_pred.csv", cell_ids)
        saved, saved_union = (np.load(d / f"{key}_probs.npz", allow_pickle=True) for d in (src, src / "union"))
        score = contrast_score(saved["probs"], [str(c) for c in saved["class_names"]], "pxd021882")
        union_score = contrast_score(saved_union["probs"], [str(c) for c in saved_union["class_names"]], "pxd021882")
        per_cell[f"{key}_score"] = np.round(score, 6)
        per_cell[f"{key}_best_guess"] = pred["best_guess"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            result = candidate(labels, pred, union, score, union_score, h)
        if void:
            result["primary"].update({"void": True, "pass": False, "reason": "fewer than 20 cells of a lineage (rule 6)"})
        summary["candidates"][version] = result
    summary["baselines_secondary"] = baselines(args.rehearse, labels, h)
    tables.mkdir(parents=True, exist_ok=True)
    per_cell.to_csv(tables / "scores.csv", index=False, lineterminator="\n")
    (tables / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.rehearse:
        record = rehearsal_record()
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({v: c["primary"] for v, c in summary["candidates"].items()}, indent=1))


if __name__ == "__main__":
    main()
