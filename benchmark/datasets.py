"""Registry of held-out datasets the benchmark scores.

Each entry records where its inputs live (data/incoming/, gitignored), their
sha256, what the dataset may be used for, and how labels are read. The
loaders check the hashes first, so a changed input fails loudly instead of
silently changing a result.

Upload and labels load separately on purpose: embedding code only ever calls
the upload loader, so it can't touch a label. Labels are read at scoring
time and nowhere else.
"""
import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from service.pipeline import alignment  # noqa: E402

_FULCHER = REPO / "data" / "incoming" / "Fulcher2026"
_FIG4 = _FULCHER / "RTLS-and-TMT32-scProteomics-of-PBMCs-main" / "Single_PBMCs_Fig4"

FULCHER2026 = {
    "name": "Fulcher 2026: TMT32 single-cell proteomics of PBMCs (FragPipe TMT-Integrator)",
    "role": "held-out evaluation only; never used to train, tune or select anything",
    "protocol": "research/benchmark/protocol-fulcher2026.md",
    "files": {
        "matrix": _FIG4 / "Data" / "abundance_protein_MD.tsv",
        "qc_keep": _FIG4 / "Metadata" / "First_Pass_PBMCs_KEEP.csv",
        "cell_metadata": _FULCHER / "Fulcher2026_TableS5_cell_metadata.xlsx",
    },
    "sha256": {
        "matrix": "85bce484c75c5510d3725093fb690d157d2c85a4cc5b7b51eae6b0a0cada4467",
        "qc_keep": "ae0a5f8305f282e3c7b8b883fa63ce12c4421ab32e2fa893cc10c290b485f59c",
        "cell_metadata": "f308176c534bc55a49d7a94b411ad7a19c87bd007b0d0ac07336a1830a4bdef4",
    },
    # Matrix channel headers may carry "_rerun" mid-name (..._B9_rerun_127C);
    # removing it gives the SampleID used by the QC list and Table S5.
    "matrix_id_drop": "_rerun",
    # Cell_Type_Second_Pass values carry a cluster suffix ("CD4T_1").
    "label_column": "Cell_Type_Second_Pass",
    "label_suffix": r"_\d+$",
    "label_source": "the authors' Seurat label transfer from an scRNA-seq reference, plus cluster refinement",
    "types": ("CD4T", "CD8T", "NK", "B", "monocyte", "DC"),
    "unscored_label": "Unknown",  # kept in the upload, excluded from scoring
}


def _check_hashes(entry: dict) -> None:
    for key, path in entry["files"].items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"][key]:
            raise ValueError(f"{path} changed: sha256 {digest}, registered {entry['sha256'][key]}")


def load_fulcher2026_upload() -> alignment.RawMatrix:
    """The 1,275 QC-passed cells as the service would receive them: parsed by
    the service's own parser, columns in First_Pass_PBMCs_KEEP.csv order,
    cell ids = SampleIDs."""
    entry = FULCHER2026
    _check_hashes(entry)
    raw = alignment.parse_matrix_csv(entry["files"]["matrix"].read_text())
    sample_ids = [c.replace(entry["matrix_id_drop"], "") for c in raw.cell_ids]
    position = {sid: i for i, sid in enumerate(sample_ids)}
    if len(position) != len(sample_ids):
        raise ValueError("SampleIDs collide after removing _rerun")
    keep = pd.read_csv(entry["files"]["qc_keep"])["SampleID"].tolist()
    missing = [sid for sid in keep if sid not in position]
    if missing:
        raise ValueError(f"{len(missing)} QC-passed cells missing from the matrix, e.g. {missing[:3]}")
    columns = [position[sid] for sid in keep]
    return replace(raw, cell_ids=keep, values=raw.values[:, columns])


def load_fulcher2026_labels() -> pd.DataFrame:
    """cell_id, label for the 1,275 QC-passed cells, in upload order. label is
    one of the six types or "Unknown". Scoring only."""
    entry = FULCHER2026
    _check_hashes(entry)
    keep = pd.read_csv(entry["files"]["qc_keep"])["SampleID"].tolist()
    meta = pd.read_excel(entry["files"]["cell_metadata"]).set_index("SampleID")
    labels = meta.loc[keep, entry["label_column"]].str.replace(entry["label_suffix"], "", regex=True)
    unexpected = set(labels.dropna()) - set(entry["types"]) - {entry["unscored_label"]}
    if labels.isna().any() or unexpected:
        raise ValueError(f"unexpected labels among QC-passed cells: {sorted(unexpected)}, NaN={labels.isna().sum()}")
    return pd.DataFrame({"cell_id": keep, "label": labels.to_numpy()})


if __name__ == "__main__":
    raw = load_fulcher2026_upload()
    print(f"Fulcher 2026 upload: {len(raw.gene_names)} genes x {len(raw.cell_ids)} cells (hashes verified)")
