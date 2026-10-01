"""v3.1's two service flags (service/pipeline/ensemble.py, SERVICE_FLAGS),
before and after, on the three development datasets through the service
parser: NB2's rule as specified (both off) against the served default (both
on). Neither flag has been evaluated on RNA; that is an open item for the
next notebook (research/todo.md, Track F).

- set_includes_best_guess: every conformal set also contains the argmax.
- restricted_renormalise: a restricted request rescales probabilities over
  the allowed classes before its sets are built. It acts only on the
  restricted SCoPE2 run below.

Labels are read after each projection, for scoring only: SCoPE2's own
(web/data/metadata_PROT_lat128.csv, class_name), PBMC240's weak lineage
labels (research/notebook-outputs/nb1d/pbmc240_raw_cell_ids.csv), Fulcher's
authors' types. Writes research/benchmark/v31_service_flags.json.

    python3 -m benchmark.v31_service_flags      # from the repository root
"""
from __future__ import annotations

import collections
import json

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

from benchmark import datasets, fulcher2026_v31, v31_dev_gate
from service.pipeline import alignment, ensemble, pipeline

REPO = datasets.REPO
OUT = REPO / "research" / "benchmark" / "v31_service_flags.json"
PBMC240_WEAK = REPO / "research" / "notebook-outputs" / "nb1d" / "pbmc240_raw_cell_ids.csv"
CONFIGS = {"nb2_rule": False, "served": True}  # every flag off / on


def scope2_raw() -> alignment.RawMatrix:
    df = pd.read_csv(v31_dev_gate.SCOPE2, sep="\t", index_col=0)
    return alignment.RawMatrix(gene_names=df.columns.astype(str).tolist(), cell_ids=df.index.astype(str).tolist(),
                               values=df.to_numpy(dtype=np.float32).T)


def describe(response: dict, hierarchy: dict) -> dict:
    """What came back, label-free: shares, composition, and the class-level
    answers (how many, how many are the best guess, their lowest confidence)."""
    cells = response["cells"]
    share, composition = v31_dev_gate.summarise(response, hierarchy)
    levels = collections.Counter(c["label_level"] for c in cells if not c["abstained"])
    one_class = [c for c in cells if c.get("label_level") == "class"]
    return {
        "cells": len(cells),
        "share_pct": {**{k: round(v, 2) for k, v in share.items()},
                      "group": round(100 * levels["group"] / len(cells), 2),
                      "lineage": round(100 * levels["lineage"] / len(cells), 2)},
        "composition_pct": {k: round(v, 2) for k, v in sorted(composition.items(), key=lambda kv: -kv[1])},
        "class_answers": len(one_class),
        "class_answers_equal_best_guess": sum(c["label"] == c["best_guess"]["label"] for c in one_class),
        "class_answer_min_confidence": round(min(c["confidence"] for c in one_class), 4) if one_class else None,
    }


def score_scope2(response: dict, hierarchy: dict) -> dict:
    truth = pd.read_csv(v31_dev_gate.SCOPE2_TRUTH)["class_name"].tolist()
    stated = v31_dev_gate.correct_at_stated_level(response, truth, hierarchy)
    guess = [c["best_guess"]["label"] if "best_guess" in c else "none" for c in response["cells"]]
    return {"correct_at_stated_level": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in stated.items()},
            "best_guess_balanced_accuracy_pct": round(100 * balanced_accuracy_score(truth, guess), 2)}


def score_pbmc240(response: dict, hierarchy: dict) -> dict:
    """Per weak lineage: the share of labelled cells whose committed answer
    names that lineage only (the lineages of its label set's classes)."""
    weak = pd.read_csv(PBMC240_WEAK).set_index("cell_id")["weak_lineage"]
    tally = collections.Counter()
    for cell in response["cells"]:
        lineage = weak.get(cell["cell_id"])
        if lineage not in ("lymphoid", "myeloid"):
            continue
        tally[f"{lineage}_n"] += 1
        if not cell["abstained"] and {hierarchy[c]["lineage"] for c in cell["label_set"]} == {lineage}:
            tally[f"{lineage}_correct"] += 1
    return {**tally, **{f"{lin}_correct_pct": round(100 * tally[f"{lin}_correct"] / tally[f"{lin}_n"], 2)
                        for lin in ("lymphoid", "myeloid")}}


def main() -> None:
    bundle = pipeline.load_bundle("v3.1")
    pbmc240 = alignment.parse_matrix_csv(v31_dev_gate.PBMC240.read_text())
    fulcher = datasets.load_fulcher2026_upload()
    runs = (("SCoPE2", scope2_raw(), False), ("SCoPE2, restricted", scope2_raw(), True),
            ("PBMC240", pbmc240, False), ("Fulcher 2026", fulcher, False))
    record = {"what": "v3.1's service flags off (NB2's rule) and on (served default), service parser",
              "flags": sorted(ensemble.SERVICE_FLAGS), "runs": {}}
    for name, raw, restrict in runs:
        record["runs"][name] = {}
        for config_name, on in CONFIGS.items():
            components = ensemble.build_components(
                {**bundle.spec, "service_flags": {k: on for k in ensemble.SERVICE_FLAGS}})
            response = pipeline.run_projection(bundle, raw, restrict_to_supported_classes=restrict,
                                               components=components)
            entry = describe(response, bundle.hierarchy)
            if name.startswith("SCoPE2"):
                entry.update(score_scope2(response, bundle.hierarchy))
            elif name == "PBMC240":
                entry["weak_lineage"] = score_pbmc240(response, bundle.hierarchy)
            else:
                full = fulcher2026_v31.score(response, bundle.hierarchy, datasets.load_fulcher2026_labels())
                entry.update({k: full[k] for k in ("committed_scored", "correct_scored", "correct_when_committed_pct",
                                                   "by_author_type", "best_guess_balanced_accuracy_6types_pct")})
            record["runs"][name][config_name] = entry
            print(name, config_name, json.dumps(entry["share_pct"]))
    OUT.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
