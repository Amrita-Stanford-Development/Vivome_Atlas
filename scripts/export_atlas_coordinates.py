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

    python3 scripts/export_atlas_coordinates.py     # from the repository root
    python3 scripts/build_manifest.py
"""
from __future__ import annotations

import csv
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


def main() -> None:
    bundle = pipeline.load_bundle("v3.1")
    print(f"Wrote {export_rna(bundle)} RNA rows to {RNA.relative_to(REPO)}")
    print(f"Wrote {export_prot(bundle)} protein rows to {PROT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
