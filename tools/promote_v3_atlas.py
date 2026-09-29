#!/usr/bin/env python3
"""Promote the v3 bundle's Atlas viewer metadata to the live filenames.

Writes web/data/metadata_RNA_lat128.csv and web/data/metadata_PROT_lat128.csv in
their existing column schema, from service/model/v3_pending/app_export/
atlas_{RNA,PROT}_v3_meta.csv — so atlas.html, tools/build_manifest.py, and
every doc that names these two files needs zero changes; only their content
changes, in place.

Verified this session (0 mismatches, all rows, both files): the v3 files'
`cell` column equals the old files' `orig_index`, and RNA `class_name` /
protein `true_class_name` equal the old `class_name`, row for row — the
join atlas.html's gene-profile feature depends on (matching a raw-LFS-file
row position against `orig_index`) survives this promotion unchanged.

Run once, from the repo root: python3 tools/promote_v3_atlas.py
"""
from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
V3_APP_EXPORT = REPO_ROOT / "service" / "model" / "v3_pending" / "app_export"
ATLAS_DIR = REPO_ROOT / "web" / "data"
REFERENCE_METADATA = REPO_ROOT / "service" / "model" / "reference_metadata.csv"

RNA_COLUMNS = ["latent_dim", "modality", "orig_index", "class_idx", "class_name", "lineage", "PC1", "PC2", "PC3"]
PROT_COLUMNS = [
    "latent_dim", "modality", "orig_index", "class_idx", "class_name",
    "pred_class_name", "max_cos_ref", "abstained", "PC1", "PC2", "PC3",
]


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def promote_rna() -> int:
    rows = _read_rows(V3_APP_EXPORT / "atlas_RNA_v3_meta.csv")
    out_rows = [
        {
            "latent_dim": row["latent_dim"], "modality": row["modality"],
            "orig_index": row["cell"], "class_idx": row["class_idx"],
            "class_name": row["class_name"], "lineage": row["lineage"],
            "PC1": row["PC1"], "PC2": row["PC2"], "PC3": row["PC3"],
        }
        for row in rows
    ]
    _write_rows(ATLAS_DIR / "metadata_RNA_lat128.csv", RNA_COLUMNS, out_rows)
    return len(out_rows)


def promote_prot(class_idx_by_name: dict[str, str]) -> int:
    rows = _read_rows(V3_APP_EXPORT / "atlas_PROT_v3_meta.csv")
    out_rows = [
        {
            "latent_dim": row["latent_dim"], "modality": row["modality"],
            "orig_index": row["cell"],
            "class_idx": class_idx_by_name[row["true_class_name"]],
            "class_name": row["true_class_name"],
            # Extra columns beyond the old schema — real measured data
            # (predicted label, similarity to reference, abstention flag),
            # kept rather than discarded. Both existing consumers
            # (atlas.html, build_manifest.py) read columns by name and
            # ignore ones they don't recognise.
            "pred_class_name": row["pred_class_name"],
            "max_cos_ref": row["max_cos_ref"],
            "abstained": row["abstained"],
            "PC1": row["PC1"], "PC2": row["PC2"], "PC3": row["PC3"],
        }
        for row in rows
    ]
    _write_rows(ATLAS_DIR / "metadata_PROT_lat128.csv", PROT_COLUMNS, out_rows)
    return len(out_rows)


def main() -> None:
    class_idx_by_name = {row["class_name"]: row["class_idx"] for row in _read_rows(REFERENCE_METADATA)}
    n_rna = promote_rna()
    n_prot = promote_prot(class_idx_by_name)
    print(f"Wrote {n_rna} RNA rows to web/data/metadata_RNA_lat128.csv")
    print(f"Wrote {n_prot} protein rows to web/data/metadata_PROT_lat128.csv")


if __name__ == "__main__":
    main()
