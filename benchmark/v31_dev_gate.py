"""Track F gate: the served v3.1 pipeline on T1 NB2's development datasets
must reproduce research/notebook-outputs/nb2/tables/dev_datasets.csv within
0.5 points (committed share, each abstention reason, each composition entry).

Both datasets are read with NB2's own parse (benchmark/notebook_convention.py),
then run through service/pipeline/ensemble.py unchanged, under NB2's rule as
specified: both service flags (ensemble.SERVICE_FLAGS) off, since NB2 did not
have them. Nothing is tuned to pass. PBMC240 through the service's own parser
is compared too, for the record, not gated.

Every figure it prints is also written to research/benchmark/v31_dev_gate.json.
service/tests/test_v31_gate.py runs the same gate as a test.

    python -m benchmark.v31_dev_gate        # from the repository root; exit 1 on a miss
"""
from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

import pandas as pd

from benchmark import notebook_convention as nc
from service.pipeline import alignment, ensemble, gene_ids, pipeline

REPO = Path(__file__).resolve().parents[1]
DEV_TABLE = REPO / "research" / "notebook-outputs" / "nb2" / "tables" / "dev_datasets.csv"
RECORD = REPO / "research" / "benchmark" / "v31_dev_gate.json"
SCOPE2 = REPO / "service" / "model" / "source" / "app_export" / "blood_joint_cells_by_proteins_GENELEVEL.tsv"
SCOPE2_TRUTH = REPO / "web" / "data" / "metadata_PROT_lat128.csv"  # class_name: SCoPE2's own labels, same row order
PBMC240 = REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv"
TOLERANCE = 0.5

REASON_COLUMNS = {
    "outside_supported_region": "abstain_ood",
    "ambiguous_between_classes": "abstain_ambiguous",
    "no_confident_label": "abstain_empty",
}


def summarise(response: dict, hierarchy: dict) -> tuple[dict, dict]:
    """NB2's dev-table figures from a v3.1 response: shares of all cells, and
    the composition with every committed answer shown at its group (a class
    counts under its group) or as lineage:<name>."""
    cells = response["cells"]
    n = len(cells)
    counts = collections.Counter()
    composition = collections.Counter()
    for c in cells:
        if c["abstained"]:
            counts[c["abstain_reason"]] += 1
            composition["abstain"] += 1
            continue
        counts["committed"] += 1
        if c["label_level"] == "class":
            counts["fine"] += 1
            composition[hierarchy[c["label"]]["group"]] += 1
        elif c["label_level"] == "group":
            composition[c["label"]] += 1
        else:
            composition[f"lineage:{c['label']}"] += 1
    share = {"committed": 100 * counts["committed"] / n, "fine": 100 * counts["fine"] / n}
    share.update({col: 100 * counts[reason] / n for reason, col in REASON_COLUMNS.items()})
    return share, {k: 100 * v / n for k, v in composition.items()}


def expected(dataset: str) -> tuple[dict, dict]:
    with DEV_TABLE.open(newline="") as handle:
        row = next(r for r in csv.DictReader(handle) if r["dataset"] == dataset and r["config"] == "candidate")
    share = {k: float(row[k]) for k in ("committed", "fine", *REASON_COLUMNS.values())}
    composition = {}
    for part in row["composition"].split(";"):
        name, value = part.strip().rsplit(" ", 1)
        composition[name] = float(value)
    return share, composition


def compare(dataset: str, share: dict, composition: dict) -> list[dict]:
    """One row per figure: NB2's value, v3.1's, and whether it is within
    tolerance. NB2 rounds its composition to one decimal, so composition
    allows for that rounding too."""
    want_share, want_comp = expected(dataset)
    rows = [{"figure": key, "kind": "share", "nb2": want, "v31": share[key],
             "within": abs(share[key] - want) <= TOLERANCE} for key, want in want_share.items()]
    for key in sorted(set(want_comp) | set(composition), key=lambda k: -want_comp.get(k, 0)):
        want, got = want_comp.get(key, 0.0), composition.get(key, 0.0)
        rows.append({"figure": key, "kind": "composition", "nb2": want, "v31": got,
                     "within": abs(got - want) <= TOLERANCE + 0.05})
    return rows


def print_rows(rows: list[dict]) -> None:
    for r in rows:
        flag = "" if r["within"] else "   <-- MISS"
        if r["kind"] == "share":
            print(f"  {r['figure']:18s} NB2 {r['nb2']:6.2f}   v3.1 {r['v31']:6.2f}{flag}")
        else:
            print(f"  {r['figure']:22s} NB2 {r['nb2']:5.1f}   v3.1 {r['v31']:5.1f}{flag}")


def correct_at_stated_level(response: dict, truth: list[str], hierarchy: dict) -> dict:
    """Committed answers right at the level stated (NB2's output_metrics):
    a class against the true class, a group or lineage against the true
    class's group or lineage. Counts per level, then the overall share."""
    tally = collections.Counter()
    for cell, true_class in zip(response["cells"], truth):
        if cell["abstained"]:
            continue
        level = cell["label_level"]
        expected = true_class if level == "class" else hierarchy[true_class][level]
        tally[level] += 1
        tally[f"{level}_correct"] += cell["label"] == expected
    committed = sum(tally[lvl] for lvl in ("class", "group", "lineage"))
    correct = sum(tally[f"{lvl}_correct"] for lvl in ("class", "group", "lineage"))
    return {**tally, "correct_when_committed": 100 * correct / committed if committed else float("nan")}


def scope2_frame() -> pd.DataFrame:
    df = pd.read_csv(SCOPE2, sep="\t", index_col=0)
    # NB2's clean_numeric: numeric, NaN filled by the column median, then 0.
    # The published matrix is already complete, so this changes nothing.
    df = df.apply(pd.to_numeric, errors="coerce")
    return df.apply(lambda c: c.fillna(c.median()), axis=0).fillna(0.0)


def run(bundle, components, frame: pd.DataFrame, value_scale) -> dict:
    smoothed, aligned = nc.prepare(frame, bundle.feature_genes)
    resolution = gene_ids.resolve_identifiers(list(nc.collapse_genes(frame).columns))
    return ensemble.project_prepared(bundle, smoothed, aligned, value_scale, resolution, False, components)


def nb2_components(bundle):
    """The bundle's components with every service flag off: NB2's rule."""
    return ensemble.build_components({**bundle.spec, "service_flags": {k: False for k in ensemble.SERVICE_FLAGS}})


def run_gate(bundle=None) -> dict:
    """The whole gate, as a record: every figure compared, the misses, and
    the figures kept for the record (SCoPE2 correctness, the service parser)."""
    bundle = bundle or pipeline.load_bundle("v3.1")
    components = nb2_components(bundle)
    record = {"what": "T1 NB2's development table, reproduced by the served v3.1 pipeline",
              "rule": "NB2's as specified: service flags off", "tolerance": {"share": TOLERANCE, "composition": TOLERANCE + 0.05},
              "datasets": {}}
    misses = []
    for dataset, frame, scale in (
        ("SCoPE2", scope2_frame(), alignment.ValueScale(detected="log", transformed=False)),
        ("PBMC240", nc.read_dia_nn(PBMC240), alignment.ValueScale(detected="linear", transformed=True)),
    ):
        response = run(bundle, components, frame, scale)
        share, composition = summarise(response, bundle.hierarchy)
        rows = compare(dataset, share, composition)
        misses += [f"{dataset} {r['figure']}" for r in rows if not r["within"]]
        entry = {"parse": "notebook", "cells": len(response["cells"]), "figures": rows}
        if dataset == "SCoPE2":
            # Not gated: SCoPE2 is the one dataset here with per-cell labels.
            truth = pd.read_csv(SCOPE2_TRUTH)["class_name"].tolist()
            entry["correct_at_stated_level"] = correct_at_stated_level(response, truth, bundle.hierarchy)
        record["datasets"][dataset] = entry

    # The product parser, compared the same way, not gated.
    service = pipeline.run_projection(bundle, alignment.parse_matrix_csv(PBMC240.read_text()), components=components)
    share, composition = summarise(service, bundle.hierarchy)
    record["pbmc240_service_parser"] = {"parse": "service", "cells": len(service["cells"]),
                                        "figures": compare("PBMC240", share, composition)}
    record["misses"] = misses
    record["passed"] = not misses
    return record


def main() -> int:
    record = run_gate()
    for dataset, entry in record["datasets"].items():
        print(f"{dataset}, notebook parse ({entry['cells']} cells)")
        print_rows(entry["figures"])
        if "correct_at_stated_level" in entry:
            print(f"  SCoPE2 correct at the stated level: {entry['correct_at_stated_level']}")
    print(f"PBMC240, service parser ({record['pbmc240_service_parser']['cells']} cells; not gated)")
    print_rows(record["pbmc240_service_parser"]["figures"])
    print("GATE PASSED" if record["passed"] else f"GATE FAILED: {', '.join(record['misses'])}")
    RECORD.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Wrote {RECORD.relative_to(REPO)}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
