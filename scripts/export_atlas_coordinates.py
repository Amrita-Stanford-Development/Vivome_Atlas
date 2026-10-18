"""Write the site's atlas coordinates from the served v3.1 model, so a cell
the service projects lands on the atlas the site displays.

- web/data/metadata_RNA_lat128.csv: PC1-PC3 of every reference cell, from
  the coordinate member's reference latents through the service's own PCA
  (ensemble.V31Bundle.pca). Every other column is kept as it is.
- web/data/metadata_PROT_lat128.csv: the 1,490 SCoPE2 cells projected by
  the service (default settings): PC1-PC3, pred_class_name (the best guess),
  max_cos_ref (reference_similarity, the out-of-distribution score) and
  abstained. orig_index and the true class columns are kept.

Then rebuild the manifest (story_cells.json reads these files):

    python scripts/export_atlas_coordinates.py     # from the repository root
    python scripts/build_manifest.py

With --organ, the map of another organ's reference (research/organ-references.md),
which the Atlas page shows without labelling:
- web/data/organs/<organ>/metadata_RNA.csv: orig_index (the row of the
  bundle's reference_metadata.csv), class_idx (in the bundle's class order)
  and PC1-PC3, from the coordinate member's reference latents through the
  bundle's own PCA (scripts/organ_reference/bundle.py, load), so an upload's
  cells would land on the same map;
- web/data/organs/index.json: each organ's name, class order, hierarchy,
  cell count, bundle MANIFEST sha256 and gate record.

    python scripts/export_atlas_coordinates.py --organ large_intestine lung lymph_node
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from service.pipeline import alignment, pipeline  # noqa: E402

DATA = REPO / "web" / "data"
RNA = DATA / "metadata_RNA_lat128.csv"
PROT = DATA / "metadata_PROT_lat128.csv"
SCOPE2 = REPO / "service" / "model" / "source" / "app_export" / "blood_joint_cells_by_proteins_GENELEVEL.tsv"
ORGANS = DATA / "organs"
# Each organ's name on the page and its gate record (research/organ-references.md).
ORGAN_INFO = {
    "large_intestine": ("Large intestine", "research/notebook-outputs/li_development/gates.json"),
    "lung": ("Lung", "research/notebook-outputs/lung_development/gates.json"),
    "lymph_node": ("Lymph node", "research/notebook-outputs/lymph_node_development/gates.json"),
}


def _read(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def _write(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _set_pcs(row: dict, pcs) -> None:
    row.update({f"PC{k + 1}": str(np.float32(pcs[k])) for k in range(3)})


def export_rna(bundle) -> int:
    columns, rows = _read(RNA)
    if [r["class_name"] for r in rows] != [bundle.metadata.class_name(i) for i in bundle.metadata.class_idx_by_cell]:
        raise ValueError(f"{RNA} is not in reference_metadata.csv row order")
    anchor = bundle.members[bundle.coordinate_member]
    for row, pcs in zip(rows, bundle.pca.project(anchor.reference_latents)):
        _set_pcs(row, pcs)
    _write(RNA, columns, rows)
    return len(rows)


def export_prot(bundle) -> int:
    columns, rows = _read(PROT)
    df = pd.read_csv(SCOPE2, sep="\t", index_col=0)
    if [str(i) for i in df.index] != [r["orig_index"] for r in rows]:
        raise ValueError(f"{PROT} is not in the SCoPE2 matrix's row order")
    raw = alignment.RawMatrix(gene_names=df.columns.astype(str).tolist(), cell_ids=df.index.astype(str).tolist(),
                              values=df.to_numpy(dtype=np.float32).T)
    response = pipeline.run_projection(bundle, raw)
    for row, cell in zip(rows, response["cells"]):
        _set_pcs(row, cell["coordinates"])
        row["pred_class_name"] = cell["best_guess"]["label"] if "best_guess" in cell else ""
        row["max_cos_ref"] = str(np.float32(cell["reference_similarity"]))
        row["abstained"] = str(cell["abstained"])
    _write(PROT, columns, rows)
    return len(rows)


def export_organ(organ: str) -> dict:
    """One organ's map file; returns its entry for index.json."""
    sys.path.insert(0, str(REPO / "scripts"))
    from organ_reference import bundle as organ_bundle, data  # noqa: E402

    directory = data.WORK / organ / "bundle"
    answers = organ_bundle.load(directory).answers
    spec = json.loads((directory / "spec.json").read_text(encoding="utf-8"))
    if list(answers.class_names) != spec["class_order"]:
        raise ValueError(f"{directory}: the bundle's class order is not its spec's")
    anchor = answers.members[answers.coordinate_member]
    pcs = answers.pca.project(anchor.reference_latents)
    codes = np.asarray(answers.metadata.class_idx_by_cell)
    if len(codes) != len(pcs):
        raise ValueError(f"{directory}: {len(codes)} cells in the metadata, {len(pcs)} latents")
    target = ORGANS / organ / "metadata_RNA.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["orig_index", "class_idx", "PC1", "PC2", "PC3"])
        for i, (c, p) in enumerate(zip(codes, pcs)):
            writer.writerow([i, int(c), *(f"{v:.4f}" for v in p)])
    name, gates = ORGAN_INFO[organ]
    return {
        "id": organ, "name": name, "file": f"organs/{organ}/metadata_RNA.csv",
        "atlas": spec["reference"]["rna"], "reference_version": spec["reference_version"],
        "bundle_manifest_sha256": hashlib.sha256((directory / "MANIFEST.json").read_bytes()).hexdigest(),
        "cells": int(len(codes)), "class_order": spec["class_order"], "hierarchy": spec["hierarchy"],
        "labelling": False,
        "gates": {"record": gates, "all_pass": json.loads((REPO / gates).read_text(encoding="utf-8"))["all_pass"]},
    }


def export_organs(organs: list[str]) -> None:
    index_path = ORGANS / "index.json"
    entries = {e["id"]: e for e in json.loads(index_path.read_text(encoding="utf-8"))["organs"]} if index_path.exists() else {}
    for organ in organs:
        entries[organ] = export_organ(organ)
        print(f"Wrote {entries[organ]['cells']} {organ} cells to {(ORGANS / organ / 'metadata_RNA.csv').relative_to(REPO)}")
    index = {
        "schema": "1",
        "about": ("Maps of other organs' references, shown without labelling: each missed its development gates "
                  "(research/organ-references.md). Written by scripts/export_atlas_coordinates.py --organ."),
        "coordinates": ("PC1-PC3 of the coordinate member's reference latents through the bundle's own PCA, "
                        "as the service would place an upload's cells"),
        "organs": [entries[k] for k in ORGAN_INFO if k in entries],
    }
    index_path.write_bytes((json.dumps(index, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--organ", nargs="+", choices=sorted(ORGAN_INFO))
    args = parser.parse_args()
    if args.organ:
        export_organs(args.organ)
        return
    bundle = pipeline.load_bundle("v3.1")
    print(f"Wrote {export_rna(bundle)} RNA rows to {RNA.relative_to(REPO)}")
    print(f"Wrote {export_prot(bundle)} protein rows to {PROT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
