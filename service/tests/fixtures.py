"""Shared synthetic fixtures. Where a real artifact exists (the dev
checkpoint, feature_space_genes.csv, reference_metadata.csv) tests use it
directly; reference_embedding.npy/centroids.npy/properties do not exist
anywhere yet (see service/model/README.md), so fixtures synthesize them at
the real reference's own scale (85,233 cells, 22 classes) — realistic
enough to exercise the chunked top-k/max-similarity code paths honestly,
without claiming to be real biology.
"""
from __future__ import annotations

import numpy as np

from service import config
from service.pipeline import reference


def synthetic_reference_embeddings(metadata: "reference.ReferenceMetadata", dim: int = 128, seed: int = 0):
    """Returns (embeddings, centroids): embeddings (n_ref, dim) L2 normalised,
    clustered around one random unit direction per class; centroids (n_classes,
    dim) L2 normalised, the per-class mean of those embeddings (as a real
    reference_centroids.npy would be, not the literal generating direction)."""
    rng = np.random.default_rng(seed)
    n_ref = len(metadata.cell_ids)
    class_idx_by_cell = metadata.class_idx_by_cell
    classes = [c.class_idx for c in metadata.classes]

    direction_by_class = {
        idx: _unit(rng.normal(size=dim)) for idx in classes
    }
    embeddings = np.empty((n_ref, dim), dtype=np.float32)
    for idx in classes:
        cell_mask = class_idx_by_cell == idx
        n = int(cell_mask.sum())
        noise = rng.normal(scale=0.3, size=(n, dim))
        embeddings[cell_mask] = _unit_rows(direction_by_class[idx] + noise)

    centroids = np.empty((len(classes), dim), dtype=np.float32)
    for i, idx in enumerate(sorted(classes)):
        centroids[i] = _unit(embeddings[class_idx_by_cell == idx].mean(axis=0))

    return embeddings.astype(np.float32), centroids.astype(np.float32)


def synthetic_reference_properties(n_ref: int, seed: int = 0):
    """(names, values): includes every SHIPPED_PROPERTIES name plus one
    unvalidated extra ("interferon_response"), so transfer.py's filtering
    is exercised, not just its arithmetic."""
    rng = np.random.default_rng(seed)
    names = list(config.SHIPPED_PROPERTIES) + ["interferon_response"]
    values = rng.normal(size=(n_ref, len(names))).astype(np.float32)
    return names, values


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.clip(np.linalg.norm(v), 1e-8, None)


def _unit_rows(m: np.ndarray) -> np.ndarray:
    return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-8, None)


def synthetic_matrix_csv(gene_names: list[str], cell_ids: list[str], seed: int = 0) -> str:
    """A minimal upload CSV in the documented shape: features in rows, cells
    in columns, first column the feature name, header row the cell IDs."""
    rng = np.random.default_rng(seed)
    values = rng.normal(size=(len(gene_names), len(cell_ids)))
    lines = ["gene," + ",".join(cell_ids)]
    for gene, row in zip(gene_names, values):
        lines.append(gene + "," + ",".join(f"{v:.4f}" for v in row))
    return "\n".join(lines)
