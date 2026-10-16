"""The sorted CD4/CD8 test, step 1: the label-free intake
(research/benchmark/protocol-sorted-cd4cd8.md, rules 1 to 3). Written and
rehearsed on Fulcher 2026 before any sorted data exists.

Without reading any label, it:
1. checks the frozen models' files against the protocol's sha256s (rule 3);
2. parses the authors' search output with the service's own parser, as a user
   would upload it: every QC-passed cell in one upload, so no sorted
   population is ever projected alone;
3. records the label-free facts the protocol allows (rule 2): cells, proteins,
   missingness, and whether CD8A, CD8B and CD4 are measured and in what share
   of cells;
4. runs v3.1, v4.1 and v5.2 as served (pipeline.run_projection; v5.2 loads
   with require_evaluation=False, since this test is its evaluation) and saves
   each model's per-cell table (the table of benchmark/baselines_v31.py);
5. writes the baselines' query matrix over the benchmark gene space.

    python -m benchmark.sorted_cd4cd8_intake --rehearse              # on Fulcher 2026
    python -m benchmark.sorted_cd4cd8_intake --matrix PATH [--cells CSV]

PATH is the authors' search output (a protein x cell matrix or a DIA-NN report,
anything the service parser reads). CSV, if given, lists the QC-passed cells
(column cell_id); the upload keeps those, in that order. The sorting labels
never pass through here: they are stored apart (rule 1) and only
benchmark/sorted_cd4cd8_score.py reads them.

Writes results/sorted_cd4cd8/ (or results/sorted_cd4cd8_rehearsal/): intake.json,
cell_ids.txt, v31_pred.csv, v41_pred.csv, v52_pred.csv, query_benchmark.npz.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import datasets
from benchmark.baselines_v31 import table
from benchmark.khoury2026_embed import refuse_overrides
from service.pipeline import alignment, fusion, gene_ids, pipeline

REPO = datasets.REPO
RESULTS = REPO / "benchmark" / "results"
MODEL = REPO / "service" / "model"
# Rule 3's table, verbatim: the files that freeze each model.
FROZEN = {
    "v4.1": {"service/model/v4_1/spec_v41.json": "0b4d7ba486345af8ee04622c625c42d0c3dd14729764cec61446d26c38ca77de",
             "service/model/v4_1/MANIFEST.json": "5e9cdc71496af5238b4ad5a4bc9ccfb7fce90a0a43d63b1948d14a0f3054382b"},
    "v5.2": {"service/model/v5_2/spec_v52.json": "61d76d2815b4bd534691fd3f64fa559296afd52e78cd843b9aa3d23fd4f4e2c1",
             "service/model/v5_2/nb2_spec_v52.json": "6596bb188ce6420ccf53646ee64fdc3606bb59d30ccbbef1e65e0e62bb04674a",
             "service/model/v5_2/MANIFEST.json": "72f419d4c1098fc492a274e758894a9bc704853f4c6b9d43d68a7d836a656e8c",
             "research/notebook-outputs/v52_labels/reference_labels_v52.csv.gz":
                 "123c05eb84d6ff502ba121a97b3a123eaddd08ac01c46647381ce7aa78160280"},
}
MODELS = {"v31": "v3.1", "v41": "v4.1", "v52": "v5.2"}  # table name -> pipeline version
MARKERS = ("CD8A", "CD8B", "CD4")


def out_dir(rehearse: bool) -> Path:
    return RESULTS / ("sorted_cd4cd8_rehearsal" if rehearse else "sorted_cd4cd8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_frozen() -> dict:
    """Every frozen file's sha256 equals the protocol's; v3.1's MANIFEST is
    recorded (the protocol freezes it "as committed", and the bundle checks
    every member against it when it loads)."""
    found = {}
    for version, files in FROZEN.items():
        for rel, want in files.items():
            got = sha256(REPO / rel)
            if got != want:
                raise SystemExit(f"{version}: {rel} has sha256 {got}, the protocol froze {want}")
            found[rel] = got
    found["service/model/v3_1/MANIFEST.json"] = sha256(MODEL / "v3_1" / "MANIFEST.json")
    return found


def load_bundle(version: str):
    """As served; v5.2 is refused until evaluated, and this is its evaluation."""
    if version == "v5.2":
        return fusion.V4Bundle.load(require_evaluation=False, version=version)
    return pipeline.load_bundle(version)


def marker_facts(raw: alignment.RawMatrix) -> dict:
    """Rule 2's allowed facts about the panel: is each marker measured, and in
    what share of cells (identifiers resolved by the service's gene map)."""
    symbols = gene_ids.resolve_to_feature_symbols(raw.gene_names)
    facts = {}
    for marker in MARKERS:
        rows = [i for i, s in enumerate(symbols) if s == marker]
        observed = np.isfinite(raw.values[rows]).any(axis=0) if rows else np.zeros(len(raw.cell_ids), bool)
        facts[marker] = {"rows": len(rows), "cells_observed_pct": round(100 * float(observed.mean()), 2)}
    return facts


def benchmark_matrix(raw: alignment.RawMatrix) -> np.ndarray:
    """The baselines' query matrix: cells x benchmark genes, on the log scale
    the service would use, a gene's rows merged by per-cell median, NaN where
    the gene is not measured."""
    values, _ = alignment.detect_and_transform_value_scale(raw.values)
    symbols = gene_ids.resolve_to_feature_symbols(raw.gene_names)
    genes = datasets.benchmark_gene_space()
    index = {g: i for i, g in enumerate(genes)}
    out = np.full((len(raw.cell_ids), len(genes)), np.nan, dtype=np.float32)
    rows_by_gene: dict[int, list[int]] = {}
    for row, symbol in enumerate(symbols):
        if symbol in index:
            rows_by_gene.setdefault(index[symbol], []).append(row)
    for col, rows in rows_by_gene.items():
        block = values[rows]
        with np.errstate(all="ignore"):
            out[:, col] = np.nanmedian(block, axis=0) if len(rows) > 1 else block[0]
    return out


def received(matrix: Path, cells: Path | None) -> alignment.RawMatrix:
    raw = alignment.parse_matrix_csv(matrix.read_text(encoding="utf-8"))
    if cells is None:
        return raw
    keep = pd.read_csv(cells, dtype={"cell_id": str})["cell_id"].tolist()
    position = {c: i for i, c in enumerate(raw.cell_ids)}
    missing = [c for c in keep if c not in position]
    if missing:
        raise SystemExit(f"{len(missing)} QC-passed cells are not in the matrix, e.g. {missing[:3]}")
    columns = [position[c] for c in keep]
    return alignment.RawMatrix(gene_names=raw.gene_names, cell_ids=keep, values=raw.values[:, columns])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--rehearse", action="store_true", help="Fulcher 2026's upload, a development dataset")
    source.add_argument("--matrix", type=Path, help="the authors' search output, as received")
    parser.add_argument("--cells", type=Path, help="CSV of the QC-passed cell ids (column cell_id)")
    args = parser.parse_args(argv)
    refuse_overrides()  # the repository's model files, not an export elsewhere
    out = out_dir(args.rehearse)
    if not args.rehearse and (out / "intake.json").exists():
        sys.exit(f"{out / 'intake.json'} exists: the intake runs once on the received data")
    frozen = check_frozen()
    if args.rehearse:
        raw, source_files = datasets.load_fulcher2026_upload(), {"dataset": "Fulcher 2026 (rehearsal)"}
    else:
        raw = received(args.matrix, args.cells)
        source_files = {"matrix": str(args.matrix), "matrix_sha256": sha256(args.matrix)}
        if args.cells:
            source_files.update(cells=str(args.cells), cells_sha256=sha256(args.cells))
    out.mkdir(parents=True, exist_ok=True)

    observed = np.isfinite(raw.values)
    facts = {"cells": len(raw.cell_ids), "proteins": len(raw.gene_names),
             "missing_pct": round(100 * float(1 - observed.mean()), 2),
             "proteins_per_cell_median": int(np.median(observed.sum(axis=0))),
             "markers": marker_facts(raw)}
    (out / "cell_ids.txt").write_text("\n".join(raw.cell_ids) + "\n", encoding="utf-8")
    runs = {}
    for name, version in MODELS.items():
        bundle = load_bundle(version)
        response = pipeline.run_projection(bundle, raw)
        table(response).to_csv(out / f"{name}_pred.csv", index=False, lineterminator="\n")
        runs[name] = {"pipeline_version": response["pipeline_version"], "model_version": response["model_version"],
                      "atlas_version": response["atlas_version"],
                      "best_guess_rule": response.get("best_guess_rule"), "n_cells": response["n_cells"]}
    matrix = benchmark_matrix(raw)
    np.savez_compressed(out / "query_benchmark.npz", x=matrix, cell_ids=np.array(raw.cell_ids, dtype=object))
    record = {"protocol": "research/benchmark/protocol-sorted-cd4cd8.md", "rehearsal": args.rehearse,
              "source": source_files, "frozen_files": frozen, "label_free_facts": facts, "runs": runs,
              "outputs": {p.name: sha256(p) for p in sorted(out.iterdir())
                          if p.suffix in (".csv", ".txt", ".npz")}}
    (out / "intake.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"facts": facts, "runs": runs}, indent=2))


if __name__ == "__main__":
    main()
