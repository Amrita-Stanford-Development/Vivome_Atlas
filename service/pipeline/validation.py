"""Upload input validation (Track B).

Runs on the parsed RawMatrix, before Stage 1 alignment, refusing an upload
that's ambiguous or too small rather than silently guessing at it or
scoring something meaningless. Value-scale detection already exists from
A2 (`alignment.detect_and_transform_value_scale`) — this module does not
duplicate it, only orientation and cell-count checks, which are genuinely
new.
"""
from __future__ import annotations

from dataclasses import dataclass

from service.pipeline import alignment, gene_ids

MIN_CELLS_REFUSE = 20
MIN_CELLS_WARN = 100


class ValidationError(ValueError):
    """An upload that should be refused with a clear, specific message,
    rather than silently guessed at or allowed to produce a meaningless
    result."""


@dataclass(frozen=True)
class ValidationWarnings:
    low_cell_count: bool


def validate_orientation(raw: alignment.RawMatrix, gene_map: gene_ids.GeneIdMap | None = None) -> None:
    """The contract is features in rows, cells in columns. There's no
    reliable way to tell a correctly-oriented upload from its transpose by
    shape alone (many real datasets have more cells than genes, and vice
    versa) — the actual signal is whether the declared "gene names" (first
    column) resolve as gene identifiers better than the declared "cell IDs"
    (header row) do. If the header looks at least as gene-like as the
    column that's supposed to hold genes, refuse rather than guess which
    way is right.
    """
    gene_map = gene_map or gene_ids.load_gene_id_map()
    gene_side = gene_ids.resolve_identifiers(raw.gene_names, gene_map)
    cell_side = gene_ids.resolve_identifiers(raw.cell_ids, gene_map)

    gene_side_rate = gene_side.matched / len(raw.gene_names) if raw.gene_names else 0.0
    cell_side_rate = cell_side.matched / len(raw.cell_ids) if raw.cell_ids else 0.0

    if cell_side_rate > 0 and cell_side_rate >= gene_side_rate:
        raise ValidationError(
            "could not tell whether this upload is oriented correctly (features in rows, "
            f"cells in columns): {gene_side_rate*100:.0f}% of the first column's values "
            f"resolve as gene identifiers, versus {cell_side_rate*100:.0f}% of the header "
            "row's values -- this looks like it may be transposed. Refusing rather than "
            "guessing; see docs/projection-service.md for the expected orientation."
        )


def validate_cell_count(raw: alignment.RawMatrix) -> ValidationWarnings:
    """Refuses fewer than MIN_CELLS_REFUSE cells outright — Stage 2's
    smoothing graph and any per-upload statistic need a real population to
    work from, not a handful of cells. Flags, but does not refuse, fewer
    than MIN_CELLS_WARN."""
    n_cells = len(raw.cell_ids)
    if n_cells < MIN_CELLS_REFUSE:
        raise ValidationError(
            f"upload has {n_cells} cell(s); at least {MIN_CELLS_REFUSE} are required — "
            "smoothing and per-upload statistics need a real population to work from."
        )
    return ValidationWarnings(low_cell_count=n_cells < MIN_CELLS_WARN)


def validate(raw: alignment.RawMatrix, gene_map: gene_ids.GeneIdMap | None = None) -> ValidationWarnings:
    """The one call site wires: orientation first (a wrong-orientation
    upload makes the cell count meaningless too, since "cells" would
    actually be genes), then cell count."""
    validate_orientation(raw, gene_map)
    return validate_cell_count(raw)
