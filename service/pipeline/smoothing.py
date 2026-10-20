"""Stage 2 — fuzzy smoothing (docs/service/pipeline-brief.md, "Stage 2").

Before the query touches the encoder, build a nearest-neighbour graph within
the query dataset using its own complete feature set — not just the 9,002
shared genes — then smooth the shared feature values along that graph. This
is the MaxFuse idea: denoise the weakly linked shared features using the
richer within-modality structure the query has but the reference doesn't
need. The evidence for it: +0.026 zero-shot AUC on SCoPE2 for the first
model, CrossModalNet (Reference_Projection_v2.ipynb; 0.642 raw, 0.668
smoothed, service/model/legacy/v2/provenance.json), monotone across every
setting tried. That AUC was scored against SCoPE2's labels as VivOME then
had them, swapped (research/benchmark/bugs-and-fixes.md, 8). If it was
macrophage against monocyte, as v3's was, the corrected labels reverse its
sign; the notebook is not in this repository, so that is not checked.

The graph is a 50-component PCA of the query's own full feature set
(L2-normalized), with a per-cell Gaussian kernel over cosine distance to the
k nearest neighbours (bandwidth = that cell's own k-th neighbour distance).
This matches VivOME_Prototype_Export.ipynb, the notebook that produced the
shipped support_restricted_assignment.csv (v3 on SCoPE2, corrected labels:
0.40%/0.68% unrestricted, 13.83%/20.21% restricted, accuracy/balanced
accuracy). An earlier version of this file built the graph
on the raw un-reduced feature set with a softmax kernel, and blended
`alpha` as the *original*-value weight instead of the *neighbour*-value
weight — same constants, silently different math, diverging from the
methodology that was actually measured. Do not reintroduce either change
without re-measuring against real SCoPE2 data.

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
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

from service import config


def _knn_weights(
    full_query_values: np.ndarray, k: int, n_pca: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Cosine-similarity k-NN on an L2-normalized PCA(n_pca) of the query's
    own full feature set. Returns (neighbour_indices, neighbour_weights),
    both (n_cells, k): a Gaussian kernel over distance, bandwidth set per
    cell by its own k-th neighbour distance, normalised to sum to 1."""
    n_cells = full_query_values.shape[0]
    k = min(k, n_cells - 1)
    n_components = min(n_pca, full_query_values.shape[1], n_cells - 1)

    projected = PCA(n_components=n_components, random_state=seed).fit_transform(
        np.asarray(full_query_values, dtype=np.float32)
    )
    projected = projected / np.clip(np.linalg.norm(projected, axis=1, keepdims=True), 1e-8, None)

    neighbours = NearestNeighbors(n_neighbors=k + 1, metric="cosine").fit(projected)
    dist, idx = neighbours.kneighbors(projected)
    idx, dist = idx[:, 1:], dist[:, 1:]  # drop self, always the nearest at distance 0

    weights = np.exp(-(dist**2) / (dist[:, -1:] ** 2 + 1e-8))
    weights = (weights / (weights.sum(axis=1, keepdims=True) + 1e-8)).astype(np.float32)
    return idx, weights


def fuzzy_smooth(
    shared_values: np.ndarray,
    full_query_values: np.ndarray,
    k: int = config.SMOOTHING_K,
    alpha: float = config.SMOOTHING_ALPHA,
    n_pca: int = config.SMOOTHING_N_PCA,
    seed: int = config.SMOOTHING_SEED,
) -> np.ndarray:
    """shared_values: (n_cells, n_feature_genes), already aligned/zero-filled
    onto the fixed feature space (alignment.align_to_feature_space output).
    full_query_values: (n_cells, n_native_features), the query's own
    complete feature set — used only to build the graph, per the brief.

    Returns smoothed values of the same shape as shared_values:
    (1 - alpha) * original + alpha * neighbour-weighted average.
    """
    n_cells = shared_values.shape[0]
    if n_cells <= 1 or full_query_values.shape[1] == 0:
        # No graph to build from a single cell, or from no native features;
        # nothing to smooth against.
        return shared_values.copy()

    neighbour_idx, weights = _knn_weights(full_query_values, k, n_pca, seed)
    neighbour_avg = np.einsum("nk,nkf->nf", weights, shared_values[neighbour_idx])
    return ((1 - alpha) * shared_values + alpha * neighbour_avg).astype(shared_values.dtype)
