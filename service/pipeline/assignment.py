"""Stage 4 — label assignment (docs/service/pipeline-brief.md, "Stage 4";
docs/service/context-brief.md §3, §6 for the measured evidence below).

Two independent, measured decisions, both encoded in service/config.py
rather than here — this module reads them, it doesn't restate them:

**Restrict the candidate set to classes with cross-modal support**
(`config.CROSS_MODAL_SUPPORTED_CLASSES`) — opt-in per request since
2026-09-30. `pipeline.run_projection` passes `allowed_positions=None`
(every class a candidate) by default, because on a PBMC upload the
restriction leaves every lymphoid cell without a correct label. The SCoPE2
evidence below is why the option exists. Letting all 22 reference classes
compete lets the 20 with zero protein evidence win, and on real SCoPE2 data
they frequently do — restricting the candidate set alone moves balanced
accuracy from 31.08% to 79.79%. This restriction is a hard mask: an
unsupported class is never a candidate, not merely disfavoured. It is
applied here (`assign_labels`) rather than upstream in `pipeline.py`, so
`top_label`, `calibrate_and_build_sets`, and the caller's own centroid-
position translation never need to know a restriction happened — the
returned array is always the full (n_query, n_classes) shape, zeros in the
disallowed columns.

**Which method wins is not settled, and has flipped once already**
(`config.ASSIGNMENT_METHOD`). An earlier RNA-vs-RNA-only comparison found
unbalanced optimal transport beating k-nearest-neighbour by 14.46 points of
balanced accuracy, and an earlier brief accordingly mandated OT and warned
against kNN. On real protein data that inverted, twice — nearest-centroid
beat both OT and kNN. All three are implemented and selectable; do not
delete either of the other two on the strength of one regime's result. That
comparison was also measured *unrestricted*; re-running it *inside* the
restricted candidate set above has not been done and is open follow-up
work, not something this module resolves.

OT's marginal constraint must stay relaxed regardless of which method is
selected. `config.OT_TAU` (0.1) is deliberately permissive — tightening it
(this project's own earlier config used tau=50) collapsed SCoPE2 accuracy
from 72% to 47% and neutrophil recall from 100% to 55.9%, because the
reference has far more classes than most queries will ever contain
evidence for. Do not "fix" this to look more conservative without
rerunning that comparison.
"""
from __future__ import annotations

import numpy as np
import ot as pot

from service import config
from service.pipeline.topk import chunked_topk


def _restrict(reference_centroids: np.ndarray, allowed_positions):
    """(restricted_centroids, allowed_idx) — allowed_idx are the original
    row positions kept, in ascending order, so results can be scattered
    back into the full-width array afterward."""
    if allowed_positions is None:
        idx = np.arange(reference_centroids.shape[0])
    else:
        idx = np.asarray(sorted(allowed_positions), dtype=np.int64)
    return reference_centroids[idx], idx


def _scatter(restricted_probs: np.ndarray, allowed_idx: np.ndarray, n_classes: int) -> np.ndarray:
    out = np.zeros((restricted_probs.shape[0], n_classes), dtype=np.float32)
    out[:, allowed_idx] = restricted_probs
    return out


def _assign_ot(query_embeddings, centroids, epsilon, tau, max_iter):
    n_query = query_embeddings.shape[0]
    n_classes = centroids.shape[0]
    row_marginal = np.full(n_query, 1.0 / n_query)
    column_marginal = np.full(n_classes, 1.0 / n_classes)

    # Cosine distance: both sides are L2-normalised, so this is exactly
    # 1 - cosine similarity, consistent with the max-cosine language used
    # throughout the brief (Stage 6 in particular).
    cost = np.clip(1.0 - query_embeddings @ centroids.T, 0.0, None)

    plan = pot.unbalanced.sinkhorn_unbalanced(
        row_marginal, column_marginal, cost, reg=epsilon, reg_m=tau, numItermax=max_iter,
    )
    row_sums = plan.sum(axis=1, keepdims=True)
    return plan / np.clip(row_sums, 1e-12, None)


def _assign_nearest_centroid(query_embeddings, centroids):
    """Softmax over cosine similarity to each candidate centroid. Both sides
    are L2-normalised, so this is a similarity-weighted distribution rather
    than a hard argmax — top_label still recovers the argmax downstream."""
    sim = query_embeddings @ centroids.T
    sim = sim - sim.max(axis=1, keepdims=True)  # numerically stable softmax
    weights = np.exp(sim)
    return weights / weights.sum(axis=1, keepdims=True)


def _assign_knn(query_embeddings, reference_embeddings, reference_class_positions, allowed_idx, k, chunk_size=4096):
    """Vote share among the k nearest reference cells whose class is
    allowed. The candidate *pool* is restricted up front, not just the
    tally — so a query surrounded entirely by unsupported-class cells still
    gets a distribution over the allowed classes, rather than a search that
    finds no allowed neighbours nearby. The chunked search itself
    (topk.chunked_topk) is shared with transfer.py's Stage 8 k-nearest
    lookup — same problem, same chunking, different label to carry
    alongside each candidate (here, its class position; there, its own row
    index)."""
    pool_mask = np.isin(reference_class_positions, allowed_idx)
    pool_embeddings = reference_embeddings[pool_mask]
    pool_positions = reference_class_positions[pool_mask]

    best_pos, _ = chunked_topk(query_embeddings, pool_embeddings, k, candidate_labels=pool_positions, chunk_size=chunk_size)

    votes = np.zeros((query_embeddings.shape[0], len(allowed_idx)), dtype=np.float32)
    for column, position in enumerate(allowed_idx):
        votes[:, column] = (best_pos == position).sum(axis=1)
    row_sums = votes.sum(axis=1, keepdims=True)
    return votes / np.clip(row_sums, 1e-12, None)


def assign_labels(
    query_embeddings: np.ndarray,
    reference_centroids: np.ndarray,
    reference_embeddings: np.ndarray | None = None,
    reference_class_positions: np.ndarray | None = None,
    allowed_positions: "set[int] | None" = None,
    method: str = config.ASSIGNMENT_METHOD,
    epsilon: float = config.OT_EPSILON,
    tau: float = config.OT_TAU,
    max_iter: int = config.OT_MAX_ITER,
    knn_k: int = config.TRANSFER_K,
) -> np.ndarray:
    """query_embeddings: (n_query, dim), reference_centroids: (n_classes,
    dim), both L2 normalised (contract). `allowed_positions`, if given,
    restricts which centroid rows can receive any assigned mass (see module
    docstring) — the returned array is always the full (n_query, n_classes)
    shape regardless, zeros in disallowed columns, so callers never need a
    second index space for a restricted vs. unrestricted result.

    `method='knn'` requires `reference_embeddings` (n_ref, dim) and
    `reference_class_positions` (n_ref,) — the reference-cell-to-centroid-
    row-position mapping, same indexing as `reference_centroids`. `knn_k`
    borrows `config.TRANSFER_K`'s value by default; no dedicated measurement
    has chosen a k specifically for this method.
    """
    n_classes = reference_centroids.shape[0]
    restricted_centroids, allowed_idx = _restrict(reference_centroids, allowed_positions)
    if allowed_idx.size == 0:
        raise ValueError(
            "allowed_positions is empty — no candidate class survived the restriction. "
            "This means config.CROSS_MODAL_SUPPORTED_CLASSES matched none of the "
            "reference's class names (a rename or a reference swap), not a real query "
            "result; check the class names, don't silently score against zero candidates."
        )

    if method == "ot":
        restricted_probs = _assign_ot(query_embeddings, restricted_centroids, epsilon, tau, max_iter)
    elif method == "nearest_centroid":
        restricted_probs = _assign_nearest_centroid(query_embeddings, restricted_centroids)
    elif method == "knn":
        if reference_embeddings is None or reference_class_positions is None:
            raise ValueError("method='knn' requires reference_embeddings and reference_class_positions")
        restricted_probs = _assign_knn(
            query_embeddings, reference_embeddings, reference_class_positions, allowed_idx, k=knn_k,
        )
    else:
        raise ValueError(
            f"Unrecognised assignment method {method!r}; expected 'nearest_centroid', 'ot', or 'knn'."
        )

    return _scatter(restricted_probs, allowed_idx, n_classes)


def top_label(probs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Returns (centroid_position_per_cell, confidence_per_cell).

    The first array indexes *rows of the centroids array passed to
    assign_labels* (0..n_classes-1) — it is not the dataset's class_idx
    value. The two only coincide when class_idx happens to be a contiguous
    0-based range, as it is in the current 22-class reference; callers must
    translate through the reference's own class ordering (e.g.
    ReferenceMetadata.classes, sorted by class_idx per the contract) rather
    than assume position == class_idx. A restricted-out class has
    probability exactly 0 in every row (assign_labels), so it can never be
    the argmax here. confidence is the top class's probability mass."""
    position = probs.argmax(axis=1)
    confidence = probs[np.arange(probs.shape[0]), position]
    return position, confidence
