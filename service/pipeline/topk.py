"""Chunked top-k cosine similarity search, shared by Stage 4's kNN
assignment method (assignment.py) and Stage 8's property transfer
(transfer.py) — both needed the identical "never materialise one
(n_query, n_candidates) similarity matrix" chunking loop, previously
duplicated between them almost line-for-line.
"""
from __future__ import annotations

import numpy as np


def chunked_topk(
    query_embeddings: np.ndarray,
    candidate_embeddings: np.ndarray,
    k: int,
    candidate_labels: np.ndarray | None = None,
    chunk_size: int = 4096,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (labels, similarities), both (n_query, k), the k highest
    cosine similarities per query row and the label of the candidate each
    came from.

    `candidate_labels` defaults to the candidate's own row index
    (0..n_candidates-1) — what transfer.py wants, to look up that
    reference cell's property values afterward. assignment.py's kNN
    method instead passes each candidate's class *position*, so the
    caller tallies votes directly without a second indirection.
    """
    n_query = query_embeddings.shape[0]
    n_candidates = candidate_embeddings.shape[0]
    if candidate_labels is None:
        candidate_labels = np.arange(n_candidates, dtype=np.int64)

    best_sim = np.full((n_query, 0), -np.inf, dtype=np.float32)
    best_label = np.full((n_query, 0), -1, dtype=np.int64)

    for start in range(0, n_candidates, chunk_size):
        chunk = candidate_embeddings[start:start + chunk_size]
        chunk_labels = candidate_labels[start:start + chunk_size]
        sim = query_embeddings @ chunk.T
        chunk_k = min(k, chunk.shape[0])
        top = np.argpartition(-sim, kth=chunk_k - 1, axis=1)[:, :chunk_k]
        top_sim = np.take_along_axis(sim, top, axis=1)
        top_label = chunk_labels[top]

        merged_sim = np.concatenate([best_sim, top_sim], axis=1)
        merged_label = np.concatenate([best_label, top_label], axis=1)
        keep = np.argsort(-merged_sim, axis=1)[:, :k]
        best_sim = np.take_along_axis(merged_sim, keep, axis=1)
        best_label = np.take_along_axis(merged_label, keep, axis=1)

    return best_label, best_sim
