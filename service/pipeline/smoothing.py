"""Stage 2 — fuzzy smoothing (Claude_Code_Context_Brief.md, "Stage 2").

Before the query touches the encoder, build a nearest-neighbour graph within
the query dataset using its own complete feature set — not just the 9,002
shared genes — then smooth the shared feature values along that graph. This
is the MaxFuse idea: denoise the weakly linked shared features using the
richer within-modality structure the query has but the reference doesn't
need. Measured +0.026 AUC on SCoPE2, monotone across every setting tried.

This step runs regardless of which encoder architecture is production
(brief: "independent of which encoder architecture won the masking
comparison. Keep it regardless.").

Only the *values* channel is smoothed. The mask channel keeps recording
genuine per-cell detection status — smoothing borrows signal from neighbours
for denoising, it does not manufacture a measurement, and the encoder was
trained on a mask that means "was this gene observed", not "do we now have
an estimate for it".
"""
from __future__ import annotations

import numpy as np

from service import config


def _knn_weights(full_query_values: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Cosine-similarity k-NN within the query's own full feature set.
    Returns (neighbour_indices, neighbour_weights), both (n_cells, k),
    weights softmax-normalised per row and excluding self."""
    n_cells = full_query_values.shape[0]
    norms = np.linalg.norm(full_query_values, axis=1, keepdims=True)
    unit = full_query_values / np.clip(norms, 1e-8, None)
    similarity = unit @ unit.T
    np.fill_diagonal(similarity, -np.inf)  # exclude self

    k = min(k, n_cells - 1)
    neighbour_idx = np.argpartition(-similarity, kth=k - 1, axis=1)[:, :k]
    row_idx = np.arange(n_cells)[:, None]
    neighbour_sim = similarity[row_idx, neighbour_idx]

    # Softmax over each cell's k neighbour similarities.
    shifted = neighbour_sim - neighbour_sim.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    weights = exp / exp.sum(axis=1, keepdims=True)
    return neighbour_idx, weights


def fuzzy_smooth(
    shared_values: np.ndarray,
    full_query_values: np.ndarray,
    k: int = config.SMOOTHING_K,
    alpha: float = config.SMOOTHING_ALPHA,
) -> np.ndarray:
    """shared_values: (n_cells, n_feature_genes), already aligned/zero-filled
    onto the fixed feature space (alignment.align_to_feature_space output).
    full_query_values: (n_cells, n_native_features), the query's own
    complete feature set — used only to build the graph, per the brief.

    Returns smoothed values of the same shape as shared_values:
    alpha * original + (1 - alpha) * neighbour-weighted average.
    """
    n_cells = shared_values.shape[0]
    if n_cells <= 1:
        # No graph to build from a single cell; nothing to smooth against.
        return shared_values.copy()

    neighbour_idx, weights = _knn_weights(full_query_values, k)
    neighbour_avg = np.einsum("nk,nkf->nf", weights, shared_values[neighbour_idx])
    return (alpha * shared_values + (1 - alpha) * neighbour_avg).astype(shared_values.dtype)
