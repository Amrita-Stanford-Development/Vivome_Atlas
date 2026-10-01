"""Track F gate: the served v3.1 pipeline on T1 NB2's development datasets
must reproduce research/notebook-outputs/nb2/tables/dev_datasets.csv within
0.5 points (committed share, each abstention reason, each composition entry).

Both datasets are read with NB2's own parse (benchmark/notebook_convention.py),
then run through service/pipeline/ensemble.py unchanged. Nothing is tuned to
pass. The service parser's numbers are printed too, for the record.

    python3 -m benchmark.v31_dev_gate        # from the repository root; exit 1 on a miss
"""
from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

import pandas as pd

from benchmark import notebook_convention as nc
from service.pipeline import alignment, ensemble, gene_ids, pipeline

REPO = Path(__file__).resolve().parents[1]
DEV_TABLE = REPO / "research" / "notebook-outputs" / "nb2" / "tables" / "dev_datasets.csv"
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


def compare(dataset: str, share: dict, composition: dict) -> list[str]:
    want_share, want_comp = expected(dataset)
    misses = []
    for key, want in want_share.items():
        got = share[key]
        flag = "" if abs(got - want) <= TOLERANCE else "   <-- MISS"
        print(f"  {key:18s} NB2 {want:6.2f}   v3.1 {got:6.2f}{flag}")
        if flag:
            misses.append(f"{dataset} {key}")
    for key in sorted(set(want_comp) | set(composition), key=lambda k: -want_comp.get(k, 0)):
        want, got = want_comp.get(key, 0.0), composition.get(key, 0.0)
        # NB2 rounds its composition to one decimal; allow for that rounding too.
        flag = "" if abs(got - want) <= TOLERANCE + 0.05 else "   <-- MISS"
        print(f"  {key:22s} NB2 {want:5.1f}   v3.1 {got:5.1f}{flag}")
        if flag:
            misses.append(f"{dataset} composition {key}")
    return misses


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


def main() -> int:
    bundle = pipeline.load_bundle("v3.1")
    components = pipeline.components_for("v3.1")
    misses = []
    for dataset, frame, scale in (
        ("SCoPE2", scope2_frame(), alignment.ValueScale(detected="log", transformed=False)),
        ("PBMC240", nc.read_dia_nn(PBMC240), alignment.ValueScale(detected="linear", transformed=True)),
    ):
        print(f"{dataset}, notebook parse ({frame.shape[0]} cells)")
        response = run(bundle, components, frame, scale)
        share, composition = summarise(response, bundle.hierarchy)
        misses += compare(dataset, share, composition)
        if dataset == "SCoPE2":
            # For the record (not gated): SCoPE2 is the one dataset here with per-cell labels.
            truth = pd.read_csv(SCOPE2_TRUTH)["class_name"].tolist()
            print(f"  SCoPE2 correct at the stated level: {correct_at_stated_level(response, truth, bundle.hierarchy)}")

    # The product parser, for the record (not gated).
    service_resp = pipeline.run_projection(bundle, alignment.parse_matrix_csv(PBMC240.read_text()))
    share, _ = summarise(service_resp, bundle.hierarchy)
    print(f"PBMC240 through the service parser: committed {share['committed']:.1f}")

    print("GATE PASSED" if not misses else f"GATE FAILED: {', '.join(misses)}")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
