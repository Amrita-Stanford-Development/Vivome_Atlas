"""Fulcher 2026 through v3.1, as development data (research/benchmark/results.md,
"Fulcher 2026 through v3.1"). The upload is read by the service's own parser
(datasets.load_fulcher2026_upload) and projected with default settings; the
authors' labels are read afterwards, for scoring only.

A committed answer is judged at the level it is stated: a class through the
protocol's fixed mapping (fulcher2026_score.COARSE, anything unlisted is
"other"); a group or a lineage against the one the author type's classes
belong to in NB2's hierarchy. The best guess is scored as balanced accuracy
over the six types, mapped the same way. Writes
research/benchmark/fulcher2026/v31_development.json.

    python3 -m benchmark.fulcher2026_v31        # from the repository root
"""
from __future__ import annotations

import collections
import json

from sklearn.metrics import balanced_accuracy_score

from benchmark import datasets, v31_dev_gate
from benchmark import fulcher2026_score as protocol
from service.pipeline import pipeline

OUT = datasets.REPO / "research" / "benchmark" / "fulcher2026" / "v31_development.json"


def level_of_type(hierarchy: dict, level: str) -> dict[str, str]:
    """Each author type's group (or lineage): the one its mapped classes share."""
    found = collections.defaultdict(set)
    for name, author_type in protocol.COARSE.items():
        found[author_type].add(hierarchy[name][level])
    if any(len(v) != 1 for v in found.values()):
        raise ValueError(f"an author type spans several {level}s: {dict(found)}")
    return {t: v.pop() for t, v in found.items()}


def score(response: dict, hierarchy: dict, labels) -> dict:
    """The scoring half, on a response already made: shares, composition,
    correctness at the stated level per author type, best guess. Counts are
    kept beside every percentage, so a reader can round from the counts."""
    share, composition = v31_dev_gate.summarise(response, hierarchy)
    cells = response["cells"]
    if labels["cell_id"].tolist() != [c["cell_id"] for c in cells]:
        raise ValueError("labels and response are not in the same cell order")
    expected = {"group": level_of_type(hierarchy, "group"), "lineage": level_of_type(hierarchy, "lineage")}

    by_type = {t: collections.Counter() for t in protocol.TYPES}
    truth, guess = [], []
    for cell, author_type in zip(cells, labels["label"]):
        if author_type == datasets.FULCHER2026["unscored_label"]:
            continue
        tally = by_type[author_type]
        tally["n"] += 1
        if not cell["abstained"]:
            level = cell["label_level"]
            tally["committed"] += 1
            tally[f"stated_{level}"] += 1
            if level == "class":
                tally["correct"] += protocol.COARSE.get(cell["label"], "other") == author_type
            else:
                tally["correct"] += expected[level][author_type] == cell["label"]
        truth.append(author_type)
        guess.append(protocol.COARSE.get(cell["best_guess"]["label"], "other") if "best_guess" in cell else "none")

    def pct(a, b):
        return round(100 * a / b, 2) if b else None

    committed = sum(t["committed"] for t in by_type.values())
    correct = sum(t["correct"] for t in by_type.values())
    return {
        "n_cells": len(cells),
        "n_scored": len(truth),
        "share_of_all_cells_pct": {k: round(v, 2) for k, v in share.items()},
        "composition_pct": {k: round(v, 2) for k, v in sorted(composition.items(), key=lambda kv: -kv[1])},
        "committed_scored": committed,
        "correct_scored": correct,
        "correct_when_committed_pct": pct(correct, committed),
        "by_author_type": {
            t: {"n": c["n"], "committed": c["committed"], "correct": c["correct"],
                "committed_pct": pct(c["committed"], c["n"]),
                "correct_at_stated_level_pct": pct(c["correct"], c["committed"]),
                "stated_level_counts": {lvl: c[f"stated_{lvl}"] for lvl in ("class", "group", "lineage")}}
            for t, c in by_type.items()
        },
        "best_guess_balanced_accuracy_6types_pct": round(100 * balanced_accuracy_score(truth, guess), 2),
        "best_guess_missing": guess.count("none"),
    }


def main() -> None:
    bundle = pipeline.load_bundle("v3.1")
    response = pipeline.run_projection(bundle, datasets.load_fulcher2026_upload())
    labels = datasets.load_fulcher2026_labels()  # scoring only, after the projection
    record = {
        "what": "Fulcher 2026 (development data) through v3.1, service parser, default settings",
        "pipeline_version": response["pipeline_version"],
        "model_version": response["model_version"],
        "service_flags": {"set_includes_best_guess": response["calibration"]["set_includes_best_guess"],
                          "restricted_renormalise": bundle.components.label_space.renormalise},
        **score(response, bundle.hierarchy, labels),
    }
    OUT.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
