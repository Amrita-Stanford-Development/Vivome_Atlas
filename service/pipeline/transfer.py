"""Stage 8 — property transfer (Claude_Code_Context_Brief.md, "Stage 8").

Continuous properties transfer by similarity-weighted averaging over the k
nearest reference neighbours in embedding space — computed on RNA's full
transcriptome, not the 9,002-gene feature space, since the reference side
is not limited by what proteomics can measure. The k-nearest search below
is over the shared 128-d embedding (the one space both sides actually live
in); only the per-reference-cell property *values* being averaged come from
outside the feature space.

Only ship properties that pass validation — do not ship all of them with a
caveat. In the one validation run performed, 4 of 8 candidates passed a
0.5 correlation threshold (config.SHIPPED_PROPERTIES); ribosome content and
antigen presentation scored well, interferon response and cell cycle
scored poorly.

Report an uncertainty alongside every value: the weighted spread across the
contributing neighbours, not just the point estimate. A value averaged from
neighbours that agree is a different claim than one averaged from
neighbours that disagree sharply.

No artifact of real per-reference-cell property values exists in this repo
yet (see service/model/README.md) — this stage is wired and tested against
synthetic fixtures until one does.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from service import config


def _topk_query_to_reference(
    query_embeddings: np.ndarray, reference_embeddings: np.ndarray, k: int, chunk_size: int = 4096
) -> tuple[np.ndarray, np.ndarray]:
    """Chunked top-k cosine similarity search so a large reference is never
    materialised as one (n_query, n_reference) matrix. Returns
    (neighbour_indices, neighbour_similarities), both (n_query, k)."""
    n_query = query_embeddings.shape[0]
    best_sim = np.full((n_query, 0), -np.inf, dtype=np.float32)
    best_idx = np.full((n_query, 0), -1, dtype=np.int64)

    for start in range(0, reference_embeddings.shape[0], chunk_size):
        chunk = reference_embeddings[start:start + chunk_size]
        sim = query_embeddings @ chunk.T
        chunk_k = min(k, chunk.shape[0])
        top = np.argpartition(-sim, kth=chunk_k - 1, axis=1)[:, :chunk_k]
        top_sim = np.take_along_axis(sim, top, axis=1)
        top_idx = top + start

        merged_sim = np.concatenate([best_sim, top_sim], axis=1)
        merged_idx = np.concatenate([best_idx, top_idx], axis=1)
        keep = np.argsort(-merged_sim, axis=1)[:, :k]
        best_sim = np.take_along_axis(merged_sim, keep, axis=1)
        best_idx = np.take_along_axis(merged_idx, keep, axis=1)

    return best_idx, best_sim


def _similarity_weights(similarities: np.ndarray) -> np.ndarray:
    """Non-negative, row-normalised. A negative cosine similarity is not a
    meaningful weight, so it is clipped to zero; if every neighbour clips to
    zero (degenerate: nothing similar at all), fall back to a uniform
    average over the k neighbours rather than dividing by zero."""
    clipped = np.clip(similarities, 0.0, None)
    row_sums = clipped.sum(axis=1, keepdims=True)
    uniform = np.full_like(clipped, 1.0 / clipped.shape[1])
    return np.where(row_sums > 0, clipped / np.clip(row_sums, 1e-12, None), uniform)


@dataclass(frozen=True)
class PropertyTransferResult:
    property_names: list[str]
    values: np.ndarray  # (n_query, n_properties) weighted mean
    uncertainty: np.ndarray  # (n_query, n_properties) weighted spread


def transfer_properties(
    query_embeddings: np.ndarray,
    reference_embeddings: np.ndarray,
    reference_property_names: list[str],
    reference_property_values: np.ndarray,
    k: int = config.TRANSFER_K,
    shipped_properties: tuple[str, ...] = config.SHIPPED_PROPERTIES,
) -> PropertyTransferResult:
    """reference_property_values: (n_reference_cells, n_reference_properties)
    aligned to reference_embeddings row for row. Only columns named in
    `shipped_properties` are transferred and returned — everything else was
    a validation candidate that did not pass and must not reach a user."""
    keep_columns = [i for i, name in enumerate(reference_property_names) if name in shipped_properties]
    kept_names = [reference_property_names[i] for i in keep_columns]
    kept_values = reference_property_values[:, keep_columns]

    neighbour_idx, neighbour_sim = _topk_query_to_reference(query_embeddings, reference_embeddings, k)
    weights = _similarity_weights(neighbour_sim)  # (n_query, k)

    neighbour_values = kept_values[neighbour_idx]  # (n_query, k, n_properties)
    weighted_mean = np.einsum("nk,nkp->np", weights, neighbour_values)

    deviation = neighbour_values - weighted_mean[:, None, :]
    weighted_var = np.einsum("nk,nkp->np", weights, deviation ** 2)
    uncertainty = np.sqrt(np.clip(weighted_var, 0.0, None))

    return PropertyTransferResult(property_names=kept_names, values=weighted_mean, uncertainty=uncertainty)
