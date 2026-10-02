"""Out-of-reference check: v3.1 as served on Furtwängler 2025's CD34+
hematopoietic stem and progenitor cells (development data; T1 NB3b's test
cells). The 85,233-cell reference holds only 198 such cells, so an honest
projection mostly abstains, ideally as "outside_supported_region".

The upload is read by datasets.load_furtwangler2025_upload (the authors' log2
values, missing kept missing) and projected with default settings; the
authors' labels are read afterwards, only to break the counts down. Writes
research/benchmark/furtwangler2025/v31_ood_check.json, with counts beside
every percentage.

    python -m benchmark.furtwangler2025_v31        # from the repository root
"""
from __future__ import annotations

import collections
import json

from benchmark import datasets, v31_dev_gate
from service.pipeline import pipeline

OUT = datasets.REPO / "research" / "benchmark" / "furtwangler2025" / "v31_ood_check.json"


def answer(cell: dict) -> str:
    return f"abstain: {cell['abstain_reason']}" if cell["abstained"] else f"{cell['label_level']}: {cell['label']}"


def tally(cells: list[dict], key) -> dict:
    groups = collections.defaultdict(list)
    for cell in cells:
        groups[key(cell)].append(cell)
    out = {}
    for name, members in sorted(groups.items()):
        n = len(members)
        ood = sum(c.get("abstain_reason") == "outside_supported_region" for c in members)
        committed = sum(not c["abstained"] for c in members)
        out[name] = {"n": n, "outside_supported_region": ood, "committed": committed,
                     "outside_supported_region_pct": round(100 * ood / n, 2), "committed_pct": round(100 * committed / n, 2)}
    return out


def main() -> None:
    bundle = pipeline.load_bundle("v3.1")
    upload = datasets.load_furtwangler2025_upload()
    response = pipeline.run_projection(bundle, upload)
    cells = response["cells"]
    labels = datasets.load_furtwangler2025_labels().set_index("cell_id")  # breakdowns only, after the projection
    n = len(cells)
    answers = collections.Counter(answer(c) for c in cells)
    guesses = collections.Counter(c["best_guess"]["label"] for c in cells if "best_guess" in c)
    _, composition = v31_dev_gate.summarise(response, bundle.hierarchy)
    record = {
        "what": "Furtwängler 2025 CD34+ HSPCs (development data) through v3.1 as served, default settings",
        "model_version": response["model_version"], "pipeline_version": response["pipeline_version"],
        "n_cells": n, "n_genes_matched": response["n_features_matched"],
        "answers": {k: {"n": v, "pct": round(100 * v / n, 2)} for k, v in answers.most_common()},
        "composition_pct": {k: round(v, 2) for k, v in sorted(composition.items(), key=lambda kv: -kv[1])},
        "best_guess": {k: {"n": v, "pct": round(100 * v / n, 2)} for k, v in guesses.most_common()},
        "by_cluster": tally(cells, lambda c: labels.loc[c["cell_id"], "cluster"]),
        "by_facs_gate": tally(cells, lambda c: labels.loc[c["cell_id"], "facs_gate"]),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("n_cells", "answers")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
