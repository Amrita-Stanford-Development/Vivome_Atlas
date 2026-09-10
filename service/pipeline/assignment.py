"""Stage 4 — label assignment (Claude_Code_Context_Brief.md, "Stage 4").

Unbalanced optimal transport onto the reference centroids, at a *relaxed*
marginal setting — never k-nearest-neighbour voting, and never a tightened
marginal.

kNN measurably loses here: OT beat it by 14.46 points of balanced accuracy
in a controlled RNA-vs-RNA test, and separately gave the best AUC on real
SCoPE2 data.

The marginal constraint is the single most important warning in the brief.
Forcing transport mass to spread evenly across all reference classes
(tightening `reg_m`/tau) collapsed SCoPE2 accuracy from 72% to 47% and
neutrophil recall from 100% to 55.9%, because the reference has far more
classes than most queries will ever contain evidence for. `config.OT_TAU`
(0.1) is deliberately permissive — this project's own earlier config used
tau=50 for the same knob and that is the mistake being guarded against here,
not a safer default to fall back to. Do not "fix" this to look more
conservative without rerunning the comparison in the brief.
"""
from __future__ import annotations

import numpy as np
import ot as pot

from service import config


def assign_labels(
    query_embeddings: np.ndarray,
    reference_centroids: np.ndarray,
    epsilon: float = config.OT_EPSILON,
    tau: float = config.OT_TAU,
    max_iter: int = config.OT_MAX_ITER,
) -> np.ndarray:
    """query_embeddings: (n_query, dim), reference_centroids: (n_classes,
    dim), both L2 normalised (contract). Returns (n_query, n_classes),
    each row a probability distribution over reference classes — the
    row-normalised unbalanced transport plan, not a softmax over distances.
    """
    n_query = query_embeddings.shape[0]
    n_classes = reference_centroids.shape[0]

    row_marginal = np.full(n_query, 1.0 / n_query)
    column_marginal = np.full(n_classes, 1.0 / n_classes)

    # Cosine distance: both sides are L2-normalised, so this is exactly
    # 1 - cosine similarity, consistent with the max-cosine language used
    # throughout the brief (Stage 6 in particular).
    cost = np.clip(1.0 - query_embeddings @ reference_centroids.T, 0.0, None)

    plan = pot.unbalanced.sinkhorn_unbalanced(
        row_marginal, column_marginal, cost, reg=epsilon, reg_m=tau, numItermax=max_iter,
    )

    row_sums = plan.sum(axis=1, keepdims=True)
    return plan / np.clip(row_sums, 1e-12, None)


def top_label(probs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Returns (class_idx_per_cell, confidence_per_cell) — confidence is the
    top class's probability mass under the transport plan."""
    class_idx = probs.argmax(axis=1)
    confidence = probs[np.arange(probs.shape[0]), class_idx]
    return class_idx, confidence
