"""Top-k cosine similarity search, shared by Stage 4's kNN assignment
method (assignment.py) and Stage 8's property transfer (transfer.py) —
both needed the identical top-k-among-candidates search, previously
duplicated between them almost line-for-line.

FAISS-backed (Track B): `IndexFlatIP` is an *exact* brute-force search over
the inner product (cosine similarity, since every embedding in this
codebase is L2-normalised) — not an approximate index — so its results
match the original chunked-numpy implementation to floating-point
precision, verified by `_chunked_topk_numpy_reference`'s equivalence test
in `service/tests/test_topk.py`. `assignment.py` and `transfer.py` call
`chunked_topk` unchanged; this file's public signature and return shape
are untouched, only the internal search algorithm is new.
"""
from __future__ import annotations

import os

# faiss-cpu and torch each bundle their own copy of libomp on macOS; loading
# both in one process aborts at faiss's OpenMP init ("Error #15: ... libomp
# already initialized", then a pthread_mutex_init crash even once that's
# suppressed) unless faiss is told up front to tolerate the duplicate and
# stick to a single thread. Set before `import faiss` so it applies no
# matter which module imports faiss (or torch) first; `setdefault` leaves an
# explicit external override alone.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import faiss


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

    `chunk_size` is accepted for backward compatibility but unused: FAISS
    batches internally in C++ and never materialises a full
    (n_query, n_candidates) matrix in Python regardless of candidate count,
    which is what the original chunking loop existed to avoid.
    """
    n_candidates = candidate_embeddings.shape[0]
    if candidate_labels is None:
        candidate_labels = np.arange(n_candidates, dtype=np.int64)
    k_eff = min(k, n_candidates)

    index = faiss.IndexFlatIP(candidate_embeddings.shape[1])
    index.add(np.ascontiguousarray(candidate_embeddings, dtype=np.float32))
    similarities, positions = index.search(
        np.ascontiguousarray(query_embeddings, dtype=np.float32), k_eff
    )
    labels = np.asarray(candidate_labels)[positions]
    return labels, similarities


def _chunked_topk_numpy_reference(
    query_embeddings: np.ndarray,
    candidate_embeddings: np.ndarray,
    k: int,
    candidate_labels: np.ndarray | None = None,
    chunk_size: int = 4096,
) -> tuple[np.ndarray, np.ndarray]:
    """The original, pre-FAISS implementation. Kept only as the reference
    `chunked_topk`'s equivalence test checks against — not called anywhere
    in the pipeline."""
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
