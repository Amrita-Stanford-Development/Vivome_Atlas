"""Builds the PBMC240 inputs scanvi_run_pbmc240.py scores, in the same
shared raw gene space load.py built for the RNA reference and SCoPE2
(results/gene_cols.txt) -- so scanvi_run_pbmc240.py, or any other
fair_benchmark arm, can score PBMC240 exactly the way the existing arms
score SCoPE2.

Row order for both variants is pinned to T1 NB1d's own
pbmc240_raw_cell_ids.csv (237 cells, weak lineage labels from the same
notebook run that produced the per-model-seed pbmc240_raw_latent.npy
embeddings) so "ours" and every baseline score literally the same cells in
the same order.

Two variants, because scANVI's input fairness on PBMC240 is a real,
documented question (Track D follow-up) -- see scanvi_run_pbmc240.py's
module docstring for exactly what each one gives scANVI and why:

- "raw" (pbmc_X.npy): first gene symbol per DIA-NN semicolon-separated
  protein group, duplicate gene rows collapsed by median (mirrors
  pbmc240_convention_check.py). Genes PBMC240 never detected are left NaN
  -- real missingness, not imputed. No log transform. This is the
  as-received DIA-NN report, reduced only enough to line up columns with
  the shared gene space -- nothing done to make it more scANVI-friendly.
- "processed" (pbmc_X_processed.npy): service/examples/pbmc240_zscored_all_genes.csv,
  the file this project already produced by the notebook-style recipe
  (>=5% detection filter, log2(x+1), per-cell median normalization,
  left-censored imputation from Normal(1st percentile, 0.3), gene-wise
  z-score) for the A2 divergence investigation. Complete (no NaN),
  already on a sane per-gene scale. Reduced to the same shared gene space
  and cell order as the raw variant, nothing else changed.
"""
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "results"
NB1D_LABELS = REPO / "research" / "notebook-outputs" / "nb1d" / "pbmc240_raw_cell_ids.csv"


def _clean_dia_nn_cell_id(raw_header: str) -> str:
    """DIA-NN report columns are Windows raw-file paths. Duplicated from
    service/pipeline/alignment.py's helper of the same name (Track B,
    branch hardening/b, not yet merged here) rather than cross-branch
    importing -- this branch only owns benchmark/."""
    basename = PureWindowsPath(raw_header).name
    if basename.lower().endswith(".raw"):
        basename = basename[: -len(".raw")]
    return basename


def _shared_genes() -> list[str]:
    return [line.strip()[len("gene_"):] for line in open(OUT / "gene_cols.txt")]


def _build_raw(labels: pd.DataFrame, shared_genes: list[str]) -> np.ndarray:
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

    missing_cells = set(labels["cell_id"]) - set(df.index)
    assert not missing_cells, f"cells in pbmc240_raw_cell_ids.csv missing from the raw report: {missing_cells}"
    df = df.reindex(labels["cell_id"])  # pin row order to T1 NB1d's

    pbmc_X = df.reindex(columns=shared_genes).to_numpy(dtype=np.float32)  # NaN = never detected
    n_observed = np.isfinite(pbmc_X).sum()
    print(f"pbmc_X (raw) {pbmc_X.shape}: {n_observed}/{pbmc_X.size} observed "
          f"({100 * n_observed / pbmc_X.size:.1f}%), {len(set(shared_genes) & set(df.columns))} "
          f"of {len(shared_genes)} shared genes ever detected by PBMC240")
    return pbmc_X


def _build_processed(labels: pd.DataFrame, shared_genes: list[str]) -> np.ndarray:
    zdf = pd.read_csv(REPO / "service" / "examples" / "pbmc240_zscored_all_genes.csv")
    zdf = zdf.set_index("gene")
    zdf.columns = zdf.columns.astype(str)
    df = zdf.T  # cells x genes, already gene-wise z-scored, no NaN
    df.columns = df.columns.astype(str).str.upper()

    missing_cells = set(labels["cell_id"]) - set(df.index)
    assert not missing_cells, f"cells in pbmc240_raw_cell_ids.csv missing from the zscored file: {missing_cells}"
    df = df.reindex(labels["cell_id"])

    pbmc_X = df.reindex(columns=shared_genes).to_numpy(dtype=np.float32)
    n_shared_detected = len(set(shared_genes) & set(df.columns))
    n_nan = np.isnan(pbmc_X).sum()
    print(f"pbmc_X (processed) {pbmc_X.shape}: {n_shared_detected}/{len(shared_genes)} shared genes "
          f"present in the processed file, {n_nan} NaN after reindexing "
          f"(genes the processed file's own >=5% detection filter dropped)")
    return pbmc_X


def main():
    labels = pd.read_csv(NB1D_LABELS)
    shared_genes = _shared_genes()

    pbmc_X_raw = _build_raw(labels, shared_genes)
    np.save(OUT / "pbmc_X.npy", pbmc_X_raw)

    pbmc_X_processed = _build_processed(labels, shared_genes)
    np.save(OUT / "pbmc_X_processed.npy", pbmc_X_processed)

    labels.to_csv(OUT / "pbmc_meta.csv", index=False)


if __name__ == "__main__":
    main()
