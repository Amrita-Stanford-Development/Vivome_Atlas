"""FAISS-based max-cosine-to-reference search (Track B).

`abstention.py` is on the forbidden-to-edit list for this track (see the
Track B section of docs/plans/VivOME_Improvement_Roadmap.md), so the FAISS
replacement for its `max_cosine_to_reference` lives here instead; only
pipeline.py's Stage 6 call site was changed, to call this function, and
`abstention.py` itself is untouched. Equivalence against the original numpy
implementation (same tolerance as topk.py's) is pinned in
service/tests/test_search.py.
"""
from __future__ import annotations

import os

# See the matching comment in topk.py: faiss and torch each bundle their own
# libomp on macOS, so this must be set before `import faiss` regardless of
# which module gets there first.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import faiss


def faiss_max_cosine_to_reference(
    query_embeddings: np.ndarray, reference_embeddings: np.ndarray
) -> np.ndarray:
    """(n_query,): max cosine similarity of each query embedding to any
    single reference cell (both L2 normalised, so inner product equals
    cosine similarity) -- exact search via FAISS's IndexFlatIP."""
    index = faiss.IndexFlatIP(reference_embeddings.shape[1])
    index.add(np.ascontiguousarray(reference_embeddings, dtype=np.float32))
    similarities, _ = index.search(
        np.ascontiguousarray(query_embeddings, dtype=np.float32), 1
    )
    return similarities[:, 0]
