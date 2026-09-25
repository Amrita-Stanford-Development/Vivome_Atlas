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
from pathlib import PureWindowsPath

import numpy as np

from service import config
from service.pipeline import gene_ids


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
        has per-cell dropout. Diagnostic only; Stage 6's coverage floor
        checks `per_cell_observed_genes` (an absolute count) instead — see
        that property's docstring for why."""
        n_genes = self.mask.shape[1]
        return self.mask.mean(axis=1) if n_genes else np.zeros(self.mask.shape[0])

    @property
    def per_cell_observed_genes(self) -> np.ndarray:
        """(n_cells,) int: the absolute count of feature-space genes
        observed for each cell. What Stage 6's coverage floor
        (config.MIN_OBSERVED_GENES) checks against, replacing the old
        fractional COVERAGE_FLOOR — a fixed gene count is comparable across
        datasets with very different native panel sizes (a 200-gene panel
        at 80% coverage and a 9,000-gene panel at 80% coverage carry very
        different amounts of actual signal), where a fraction of one fixed
        9,002-gene denominator isn't."""
        return self.mask.sum(axis=1).astype(int)


_DIA_NN_ANNOTATION_COLUMNS = frozenset({
    "Protein.Group", "Protein.Names", "Genes",
    "First.Protein.Description", "N.Sequences", "N.Proteotypic.Sequences",
})


def _clean_dia_nn_cell_id(raw_header: str) -> str:
    """DIA-NN report columns are Windows raw-file paths (e.g.
    r"E:\\...\\Astral_TopMedPBMC1_041025_SP_1.raw"). PureWindowsPath parses
    the backslashes correctly regardless of the host OS running this
    service."""
    basename = PureWindowsPath(raw_header).name
    if basename.lower().endswith(".raw"):
        basename = basename[: -len(".raw")]
    return basename


def parse_matrix_csv(text: str) -> RawMatrix:
    """Contract shape (docs/projection-service.md, project.html): features
    in rows, cells in columns; first column is the feature name, header row
    is cell IDs. Comma or tab separated, auto-detected from the header
    line -- a real DIA-NN report is tab separated.

    A DIA-NN report also carries its own annotation columns
    (Protein.Group, Protein.Names, Genes, First.Protein.Description,
    N.Sequences, N.Proteotypic.Sequences) ahead of the per-cell columns.
    When a "Genes" column is present, its values become the gene
    identifiers (may be semicolon-separated protein groups -- gene_ids.py
    already resolves those), the other annotation columns are excluded
    from the cell columns, and each surviving cell column's Windows
    raw-file-path header is cleaned to its basename without ".raw"."""
    first_line = text.split("\n", 1)[0]
    delimiter = "\t" if first_line.count("\t") > first_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader)

    is_dia_nn_report = "Genes" in header
    gene_col_idx = header.index("Genes") if is_dia_nn_report else 0
    cell_col_indices = [
        i for i, name in enumerate(header)
        if i != gene_col_idx and name not in _DIA_NN_ANNOTATION_COLUMNS
    ]
    cell_ids = [
        _clean_dia_nn_cell_id(header[i]) if is_dia_nn_report else header[i]
        for i in cell_col_indices
    ]

    gene_names: list[str] = []
    rows: list[list[float]] = []
    for row in reader:
        if not row or not row[gene_col_idx]:
            continue
        gene_names.append(row[gene_col_idx])
        rows.append([float(row[i]) if row[i] != "" else np.nan for i in cell_col_indices])
    values = np.array(rows, dtype=np.float32) if rows else np.empty((0, len(cell_ids)), dtype=np.float32)
    return RawMatrix(gene_names=gene_names, cell_ids=cell_ids, values=values)


@dataclass(frozen=True)
class ValueScale:
    detected: str  # "linear" | "log" | "unknown" (no observed values at all)
    transformed: bool


def detect_and_transform_value_scale(
    raw_values: np.ndarray,
    median_threshold: float = config.LINEAR_SCALE_MEDIAN_THRESHOLD,
) -> tuple[np.ndarray, ValueScale]:
    """raw_values: (n_raw_genes, n_cells), NaN for missing (this dataset's
    raw units, before any z-scoring). A DIA-NN or similar linear-intensity
    report arrives in units of hundreds to tens of thousands; the encoder
    was trained on log-scale, then z-scored values, and z-scoring linear
    intensities directly does not recover that distribution — the highest-
    abundance proteins still dominate.

    Detected as linear scale, and log2-transformed, when every observed
    value is non-negative AND the median observed value exceeds
    `median_threshold`. Real log-scale data (what this pipeline expects) is
    typically single or low double digits and commonly has negative values
    (a log-ratio relative to a reference), so a single negative observed
    value is enough to skip the transform entirely — never transform data
    that might already be on a log scale.

    An observed value of exactly 0 is treated as "not detected" (set to
    NaN, matching this dataset's existing missing-value semantics) rather
    than log2-transformed to -inf.
    """
    observed = ~np.isnan(raw_values)
    if not observed.any():
        return raw_values, ValueScale(detected="unknown", transformed=False)

    observed_values = raw_values[observed]
    has_negative = bool((observed_values < 0).any())
    median_value = float(np.median(observed_values))
    is_linear = (not has_negative) and (median_value > median_threshold)
    if not is_linear:
        return raw_values, ValueScale(detected="log", transformed=False)

    transformed = raw_values.copy()
    zero_mask = observed & (transformed == 0)
    transformed[zero_mask] = np.nan
    log_mask = observed & ~zero_mask
    transformed[log_mask] = np.log2(transformed[log_mask])
    return transformed, ValueScale(detected="linear", transformed=True)


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

    # Track B: resolve whatever identifier convention this upload used
    # (symbol, Ensembl ID, UniProt accession, or a semicolon-separated
    # DIA-NN protein group) to feature-space gene symbols before matching.
    # An identifier that doesn't resolve becomes None here, which
    # gene_index.get(None) already treats as "not in the feature space" —
    # exactly like an unrecognised symbol always has.
    resolved_gene_names = gene_ids.resolve_to_feature_symbols(raw.gene_names)

    z = zscore_per_gene(raw.values) if raw.values.size else raw.values

    values = np.zeros((n_cells, n_genes), dtype=np.float32)
    mask = np.full((n_cells, n_genes), config.MASK_MISSING, dtype=np.float32)
    matched_columns: set[int] = set()

    for raw_i, gene in enumerate(resolved_gene_names):
        col = gene_index.get(gene)
        if col is None:
            continue
        observed = ~np.isnan(raw.values[raw_i, :])
        values[:, col] = z[raw_i, :]  # already 0 where observed is False, via zscore_per_gene's nan_to_num
        mask[:, col] = np.where(observed, config.MASK_OBSERVED, config.MASK_MISSING)
        matched_columns.add(col)

    n_matched_rows = sum(1 for g in resolved_gene_names if g in gene_index)
    return AlignedQuery(
        values=values,
        mask=mask,
        cell_ids=list(raw.cell_ids),
        n_features_matched=len(matched_columns),
        n_features_unmatched=len(raw.gene_names) - n_matched_rows,
    )
