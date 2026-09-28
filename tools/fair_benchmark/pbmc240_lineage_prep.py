"""Reduces the real DIA-NN PBMC240 raw report
(service/examples/pbmc240_proteins_raw.tsv) to the same shared raw gene
space load.py built for the RNA reference and SCoPE2 (results/gene_cols.txt)
-- so scanvi_run_pbmc240.py, or any other fair_benchmark arm, can score
PBMC240 exactly the way the existing arms score SCoPE2.

Row order is pinned to T1 NB1d's own pbmc240_raw_cell_ids.csv (237 cells,
weak lineage labels from the same notebook run that produced the
per-model-seed pbmc240_raw_latent.npy embeddings) so "ours" and every
baseline score literally the same cells in the same order. Gene reduction
mirrors pbmc240_convention_check.py: first gene symbol per DIA-NN
semicolon-separated protein group, duplicate gene rows collapsed by
median. Genes PBMC240 never detected are left NaN in the shared space --
real missingness, not imputed -- consistent with this project's "zero/NaN
for unmeasured, never a guessed value" rule.
"""
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "results"
NB1D_LABELS = REPO / "docs" / "plans" / "nb1d" / "pbmc240_raw_cell_ids.csv"


def _clean_dia_nn_cell_id(raw_header: str) -> str:
    """DIA-NN report columns are Windows raw-file paths. Duplicated from
    service/pipeline/alignment.py's helper of the same name (Track B,
    branch hardening/b, not yet merged here) rather than cross-branch
    importing -- this branch only owns tools/fair_benchmark/."""
    basename = PureWindowsPath(raw_header).name
    if basename.lower().endswith(".raw"):
        basename = basename[: -len(".raw")]
    return basename


def main():
    raw_df = pd.read_csv(REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv", sep="\t")
    raw_df = raw_df.dropna(subset=["Genes"])
    raw_df["gene"] = raw_df["Genes"].astype(str).str.split(";").str[0].str.upper()
    annotation_cols = {
        "Protein.Group", "Protein.Names", "Genes",
        "First.Protein.Description", "N.Sequences", "N.Proteotypic.Sequences", "gene",
    }
    sample_cols = [c for c in raw_df.columns if c not in annotation_cols]

    mat = raw_df.set_index("gene")[sample_cols]
    mat = mat.groupby(level=0).median()  # collapse duplicate gene rows
    df = mat.T  # cells x genes
    df.index = [_clean_dia_nn_cell_id(c) for c in df.index]

    labels = pd.read_csv(NB1D_LABELS)
    missing_cells = set(labels["cell_id"]) - set(df.index)
    assert not missing_cells, f"cells in pbmc240_raw_cell_ids.csv missing from the raw report: {missing_cells}"
    df = df.reindex(labels["cell_id"])  # pin row order to T1 NB1d's

    shared_genes = [line.strip()[len("gene_"):] for line in open(OUT / "gene_cols.txt")]
    pbmc_X = df.reindex(columns=shared_genes).to_numpy(dtype=np.float32)  # NaN = never detected
    n_observed = np.isfinite(pbmc_X).sum()
    print(f"pbmc_X {pbmc_X.shape}: {n_observed}/{pbmc_X.size} observed "
          f"({100 * n_observed / pbmc_X.size:.1f}%), {len(set(shared_genes) & set(df.columns))} "
          f"of {len(shared_genes)} shared genes ever detected by PBMC240")

    np.save(OUT / "pbmc_X.npy", pbmc_X)
    labels.to_csv(OUT / "pbmc_meta.csv", index=False)


if __name__ == "__main__":
    main()
