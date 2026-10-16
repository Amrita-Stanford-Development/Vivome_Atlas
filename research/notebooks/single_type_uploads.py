"""Goal 2, Phase 1.5: what happens to real protein cells uploaded one type at
a time. A measurement on development data; it changes nothing.

Every gene is z-scored within its upload, so an upload of a single cell type
loses the contrast between types; on simulated RNA, single-type uploads score
far below mixed ones (research/notebook-run-history.md, entries 14 and 24).
Users who upload a sorted population meet exactly this. Here, on Fulcher 2026
(development data, six author types), each type's cells go through the served
service three ways:
- mixed: the full 1,275-cell upload, as it was scored;
- alone: only that type's cells, one upload per type;
- paired: CD4 T with CD8 T, and B with monocytes.
For v3.1 and v4.1 (and v4.2, loaded for evaluation): the best guess's recall
of the type (through COARSE in benchmark/fulcher2026_score.py), and the
answers' committed share and correct when committed, at the stated level.

Writes research/notebook-outputs/single_type_uploads/summary.json.

    python research/notebooks/single_type_uploads.py      # from the repository root
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from benchmark import datasets  # noqa: E402
from benchmark import fulcher2026_score as fulcher  # noqa: E402
from benchmark.baselines_score import hierarchy  # noqa: E402
from service.pipeline import alignment, fusion, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "single_type_uploads"
PAIRS = {"CD4T+CD8T": ("CD4T", "CD8T"), "B+monocyte": ("B", "monocyte")}


def subset(raw: alignment.RawMatrix, keep: np.ndarray) -> alignment.RawMatrix:
    return alignment.RawMatrix(gene_names=raw.gene_names, cell_ids=[c for c, k in zip(raw.cell_ids, keep) if k],
                               values=raw.values[:, keep])


def scores(response: dict, truth: np.ndarray, expected: dict) -> dict:
    cells = response["cells"]
    guess = np.array([fulcher.COARSE.get(c.get("best_guess", {}).get("label", ""), "other") for c in cells])
    committed = np.array([not c["abstained"] for c in cells])
    correct = np.array([(not c["abstained"]) and (
        fulcher.COARSE.get(c["label"]) == t if c["label_level"] == "class" else expected[c["label_level"]].get(t) == c["label"])
        for c, t in zip(cells, truth)])
    out = {}
    for t in sorted(set(truth)):
        m = truth == t
        out[t] = {"n": int(m.sum()), "recall_pct": round(100 * float((guess[m] == t).mean()), 2),
                  "committed_pct": round(100 * float(committed[m].mean()), 2),
                  "correct_when_committed_pct": round(100 * float(correct[m & committed].sum() / max(1, (m & committed).sum())), 2)}
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    raw = datasets.load_fulcher2026_upload()
    labels = datasets.load_fulcher2026_labels().set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
    hier = hierarchy()
    expected = {}
    for level in ("group", "lineage"):
        found = {}
        for name, t in fulcher.COARSE.items():
            found.setdefault(t, set()).add(hier[name][level])
        expected[level] = {t: v.pop() for t, v in found.items() if len(v) == 1}
    bundles = {"v3.1": pipeline.load_bundle("v3.1"), "v4.1": pipeline.load_bundle("v4.1"),
               "v4.2": fusion.V4Bundle.load(require_evaluation=False, version="v4.2")}
    summary = {}
    for name, bundle in bundles.items():
        res = {}
        full = pipeline.run_projection(bundle, raw)
        scored = np.isin(labels, fulcher.TYPES)
        mixed = scores({"cells": [c for c, s in zip(full["cells"], scored) if s]}, labels[scored], expected)
        res["mixed"] = mixed
        res["alone"] = {}
        for t in fulcher.TYPES:
            keep = labels == t
            response = pipeline.run_projection(bundle, subset(raw, keep))
            res["alone"][t] = {**scores(response, labels[keep], expected)[t],
                               "correlation_term": (response.get("best_guess_rule") or {}).get("correlation_term")}
        res["paired"] = {}
        for pair, types in PAIRS.items():
            keep = np.isin(labels, types)
            response = pipeline.run_projection(bundle, subset(raw, keep))
            res["paired"][pair] = scores(response, labels[keep], expected)
        summary[name] = res
        print(name, "recall, mixed -> alone:",
              {t: (mixed[t]["recall_pct"], res["alone"][t]["recall_pct"]) for t in fulcher.TYPES}, flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
