"""Stage 1 — query alignment (Claude_Code_Context_Brief.md, "Stage 1").

Reindex the uploaded matrix onto the fixed 9,002-gene feature space, in
`feature_space_genes.csv` order, with an explicit observed/missing mask.
Genes the dataset didn't measure get zero, not an imputed guess — this was
tested directly against gaussian noise and hot-deck imputation, and zero
fill won in every comparison. Do not restrict the space to well-covered
genes either: that cost 0.005 AUC on SCoPE2, worse than doing nothing.

Z-scoring is per dataset, per gene, using only this upload's own cells —
never a statistic carried over from RNA training or from another dataset.

Coverage is expected to be low (SCoPE2 32.3%, PBMC240 34.8%, Fulcher 18.4%
against the 9,002 space). That is the normal case, not a failure signal —
see abstention.py for where low coverage actually gets acted on.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import numpy as np

from service import config


@dataclass(frozen=True)
class RawMatrix:
    """The uploaded matrix before alignment: whatever genes/proteins this
    particular dataset happened to measure, in its own order."""
    gene_names: list[str]
    cell_ids: list[str]
    values: np.ndarray  # (n_raw_genes, n_cells), this dataset's raw units


@dataclass(frozen=True)
class AlignedQuery:
    values: np.ndarray  # (n_cells, n_feature_genes) float32, z-scored, zero-filled
    mask: np.ndarray  # (n_cells, n_feature_genes) float32, 1.0 observed / 0.0 missing
    cell_ids: list[str]
    n_features_matched: int
    n_features_unmatched: int

    @property
    def coverage(self) -> float:
        """Dataset-level: what fraction of the feature space this upload's
        schema covers at all, for the n_features_matched/unmatched fields
        in the response contract."""
        n_genes = self.mask.shape[1]
        return self.n_features_matched / n_genes if n_genes else 0.0

    @property
    def per_cell_coverage(self) -> np.ndarray:
        """(n_cells,): the fraction of genes actually observed for each
        individual cell — can be lower than `coverage` when a matched gene
        has per-cell dropout, and is what Stage 6's coverage floor checks
        against, since a floor is a per-cell trust decision."""
        n_genes = self.mask.shape[1]
        return self.mask.mean(axis=1) if n_genes else np.zeros(self.mask.shape[0])


def parse_matrix_csv(text: str) -> RawMatrix:
    """Contract shape (docs/projection-service.md, project.html): features
    in rows, cells in columns; first column is the feature name, header row
    is cell IDs."""
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    cell_ids = header[1:]
    gene_names: list[str] = []
    rows: list[list[float]] = []
    for row in reader:
        if not row or not row[0]:
            continue
        gene_names.append(row[0])
        rows.append([float(v) if v != "" else np.nan for v in row[1:]])
    values = np.array(rows, dtype=np.float32) if rows else np.empty((0, len(cell_ids)), dtype=np.float32)
    return RawMatrix(gene_names=gene_names, cell_ids=cell_ids, values=values)


def zscore_per_gene(raw_values: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """raw_values: (n_raw_genes, n_cells). Z-score each row against this
    dataset's own mean/std, computed only from the cells in this upload.
    A zero-variance gene z-scores to 0 rather than +/-inf."""
    mean = np.nanmean(raw_values, axis=1, keepdims=True)
    std = np.nanstd(raw_values, axis=1, keepdims=True)
    z = (raw_values - mean) / np.clip(std, eps, None)
    return np.nan_to_num(z, nan=0.0)


def align_to_feature_space(raw: RawMatrix, feature_genes: list[str]) -> AlignedQuery:
    n_cells = len(raw.cell_ids)
    n_genes = len(feature_genes)
    gene_index = {g: i for i, g in enumerate(feature_genes)}

    z = zscore_per_gene(raw.values) if raw.values.size else raw.values

    values = np.zeros((n_cells, n_genes), dtype=np.float32)
    mask = np.full((n_cells, n_genes), config.MASK_MISSING, dtype=np.float32)
    matched_columns: set[int] = set()

    for raw_i, gene in enumerate(raw.gene_names):
        col = gene_index.get(gene)
        if col is None:
            continue
        observed = ~np.isnan(raw.values[raw_i, :])
        values[:, col] = z[raw_i, :]  # already 0 where observed is False, via zscore_per_gene's nan_to_num
        mask[:, col] = np.where(observed, config.MASK_OBSERVED, config.MASK_MISSING)
        matched_columns.add(col)

    n_matched_rows = sum(1 for g in raw.gene_names if g in gene_index)
    return AlignedQuery(
        values=values,
        mask=mask,
        cell_ids=list(raw.cell_ids),
        n_features_matched=len(matched_columns),
        n_features_unmatched=len(raw.gene_names) - n_matched_rows,
    )
