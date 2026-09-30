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

import numpy as np
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


def benchmark_gene_space() -> list[str]:
    """The baselines' shared gene space: the 2,907 genes the atlas RNA
    reference and SCoPE2 files both carry (load.py writes results/gene_cols.txt)."""
    path = Path(__file__).resolve().parent / "results" / "gene_cols.txt"
    return [line.strip()[len("gene_"):] for line in path.read_text().split("\n") if line.strip()]


def load_fulcher2026_benchmark_matrix(variant: str) -> tuple[np.ndarray, list[str], list[str]]:
    """The Fulcher upload as the baselines receive it: (cells x genes) over
    benchmark_gene_space(), NaN wherever Fulcher has no value (a gene it never
    measured, or a cell where that gene is missing).
    variant "log2": log2 of the linear intensities; "log2_cellmedian": the
    same minus each cell's median over its observed proteins in the full
    1,661-protein table. No labels involved."""
    raw = load_fulcher2026_upload()
    assert np.nanmin(raw.values) > 0, "log2 needs positive intensities"
    logx = np.log2(raw.values.astype(np.float64))
    if variant == "log2_cellmedian":
        logx = logx - np.nanmedian(logx, axis=0, keepdims=True)
    elif variant != "log2":
        raise ValueError(f"unknown variant {variant!r}")
    genes = benchmark_gene_space()
    df = pd.DataFrame(logx.T, index=raw.cell_ids, columns=[g.upper() for g in raw.gene_names])
    return df.reindex(columns=genes).to_numpy(dtype=np.float32), raw.cell_ids, genes


_KHOURY = REPO / "data" / "incoming" / "Khoury2026"

# SEALED: the final test set. Scored exactly once, at the final v3.1
# evaluation (research/benchmark/protocol-khoury2026.md). Until then, per-cell
# labels cannot be loaded; only aggregate type counts can.
KHOURY2026 = {
    "name": "Khoury 2026: PBMC single-cell proteomics, timsTOF, mTRAQ 2-plex (Zenodo 22649483)",
    "role": "SEALED final test set; scored once, at the final v3.1 evaluation; never used to train, tune or select",
    "sealed": True,
    "protocol": "research/benchmark/protocol-khoury2026.md",
    "files": {
        # log2, column-normalised only, ComBat-corrected, original missing values restored as NA.
        # Never the Normalized_Centered or Imputed matrices.
        "matrix": _KHOURY / "Protein_x_Cell_Matrix_Column_Normalized.csv",
        "cell_metadata": _KHOURY / "PBMC_covariation_protein_cell_metadata.csv",
    },
    "sha256": {
        "matrix": "514c08ca01dac2d58a2cfed97fb574a3c555c82ab6169eb68946c86bf25f1c1b",
        "cell_metadata": "61622d71e7540791d445cd024254694082714579de90741093be14bb0ea348e6",
    },
    "label_column": "cell_type",
    "label_source": "protein-only Seurat clustering of these data, clusters named by canonical protein markers; no RNA reference",
    "type_names": {"CD4 T cells": "CD4T", "CD8 T cells": "CD8T", "NK cells": "NK", "B cells": "B", "Monocytes": "monocyte"},
    "types": ("CD4T", "CD8T", "NK", "B", "monocyte"),
}


def load_khoury2026_upload() -> alignment.RawMatrix:
    """All 1,651 matrix cells as the service would receive them, parsed by the
    service's own parser. Every cell must be QC-passed and included in the
    authors' analysis. The values are already log2."""
    entry = KHOURY2026
    _check_hashes(entry)
    raw = alignment.parse_matrix_csv(entry["files"]["matrix"].read_text())
    meta = pd.read_csv(entry["files"]["cell_metadata"]).set_index("cell_id").reindex(raw.cell_ids)
    bad = meta.index[(meta["qc_status"] != "Pass") | (meta["included_in_analysis"] != "Yes")].tolist()
    if bad:
        raise ValueError(f"{len(bad)} matrix cells are not QC-passed/included, e.g. {bad[:3]}")
    return raw


def khoury2026_type_counts() -> dict[str, int]:
    """Aggregate label counts over the upload's cells: the only label
    information readable while the dataset is sealed."""
    entry = KHOURY2026
    raw = load_khoury2026_upload()
    meta = pd.read_csv(entry["files"]["cell_metadata"]).set_index("cell_id").reindex(raw.cell_ids)
    labels = meta[entry["label_column"]].map(entry["type_names"])
    if labels.isna().any():
        raise ValueError("unexpected or missing cell types among matrix cells")
    return {t: int((labels == t).sum()) for t in entry["types"]}


def load_khoury2026_labels(*, unseal: bool = False) -> pd.DataFrame:
    """cell_id, label in upload order. Refuses while sealed: only the final
    v3.1 evaluation, following protocol-khoury2026.md, passes unseal=True."""
    entry = KHOURY2026
    if entry["sealed"] and not unseal:
        raise PermissionError(f"Khoury 2026 is sealed; labels load only at the final v3.1 evaluation ({entry['protocol']})")
    raw = load_khoury2026_upload()
    meta = pd.read_csv(entry["files"]["cell_metadata"]).set_index("cell_id").reindex(raw.cell_ids)
    return pd.DataFrame({"cell_id": raw.cell_ids, "label": meta[entry["label_column"]].map(entry["type_names"]).to_numpy()})


if __name__ == "__main__":
    raw = load_fulcher2026_upload()
    print(f"Fulcher 2026 upload: {len(raw.gene_names)} genes x {len(raw.cell_ids)} cells (hashes verified)")
    raw = load_khoury2026_upload()
    print(f"Khoury 2026 upload (sealed): {len(raw.gene_names)} genes x {len(raw.cell_ids)} cells (hashes verified); "
          f"type counts {khoury2026_type_counts()}")
