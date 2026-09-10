"""Stage 6 — abstention (Claude_Code_Context_Brief.md, "Stage 6").

Score out-of-distribution risk by maximum cosine similarity to any single
reference cell, never by normalised vote share among nearest neighbours.
Vote share reached 0.974 AUC detecting one unseen population but scored
*below chance* (0.345, 0.239) on two others — a query cell far from the
entire reference can still produce a sharply peaked neighbour vote, which
reads as confident when it should read as unsupported. Max cosine similarity
scored a perfect 1.000 across every held-out class tested. Do not swap this
for a neighbour-vote or softmax-entropy score without rerunning that
comparison.

Below roughly 15-20% feature coverage, results are not just noisier — they
stop being trustworthy in a way a confidence score won't catch (accuracy at
10% coverage was non-monotone against 20%/30% in one comparison, the
signature of a mostly-zero input producing an arbitrary answer). This is
checked first, per cell, and short-circuits straight to abstention.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from service import config


class AbstainReason(str, Enum):
    NONE = "none"
    LOW_COVERAGE = "coverage_too_low"
    OUT_OF_DISTRIBUTION = "outside_supported_region"
    NO_CONFIDENT_LABEL = "no_confident_label"
    AMBIGUOUS = "ambiguous_between_classes"


@dataclass(frozen=True)
class AbstentionResult:
    abstained: np.ndarray  # (n_cells,) bool
    reason: list[AbstainReason]  # (n_cells,)
    max_reference_similarity: np.ndarray  # (n_cells,) float, for the alignment diagnostic panel


def max_cosine_to_reference(query_embeddings: np.ndarray, reference_embeddings: np.ndarray, chunk_size: int = 4096) -> np.ndarray:
    """(n_query,): max cosine similarity of each query embedding to any
    single reference cell (both L2 normalised, so this is a plain dot
    product). Chunked over the reference side so a large reference doesn't
    force one huge (n_query, n_reference) matrix into memory at once."""
    n_query = query_embeddings.shape[0]
    best = np.full(n_query, -1.0, dtype=np.float32)
    for start in range(0, reference_embeddings.shape[0], chunk_size):
        chunk = reference_embeddings[start:start + chunk_size]
        similarity = query_embeddings @ chunk.T
        best = np.maximum(best, similarity.max(axis=1))
    return best


def _ood_threshold(calibration_scores: np.ndarray, quantile: float) -> float:
    """A low quantile of the same random calibration slice used in Stage 5.
    This is a documented placeholder, not a tuned production threshold: it
    assumes the random slice is broadly representative of the query, which
    is the best available signal absent labelled out-of-distribution data
    for this reference (the brief notes the one dataset with experimentally
    sorted rather than inferred labels, O'Connor et al, may never become
    available). Retune once real OOD-labelled examples exist."""
    return float(np.quantile(calibration_scores, quantile))


def score_abstention(
    max_similarity: np.ndarray,
    per_cell_coverage: np.ndarray,
    label_sets: list[list[int]],
    calibration_indices: np.ndarray,
    similarity_quantile: float = 0.05,
    coverage_floor: float = config.COVERAGE_FLOOR,
) -> AbstentionResult:
    """Priority, per cell: coverage floor, then out-of-distribution, then
    an empty or genuinely ambiguous conformal set. Stage 7 (fallback) should
    run before this is treated as final for the AMBIGUOUS case: a label_set
    that collapses to one of the six known confusable pairs is not
    ambiguous, it is a resolvable partial identification.
    """
    n_cells = max_similarity.shape[0]
    threshold = _ood_threshold(max_similarity[calibration_indices], similarity_quantile)

    abstained = np.zeros(n_cells, dtype=bool)
    reasons: list[AbstainReason] = [AbstainReason.NONE] * n_cells

    for i in range(n_cells):
        if per_cell_coverage[i] < coverage_floor:
            abstained[i] = True
            reasons[i] = AbstainReason.LOW_COVERAGE
        elif max_similarity[i] < threshold:
            abstained[i] = True
            reasons[i] = AbstainReason.OUT_OF_DISTRIBUTION
        elif len(label_sets[i]) == 0:
            abstained[i] = True
            reasons[i] = AbstainReason.NO_CONFIDENT_LABEL
        elif len(label_sets[i]) > 1:
            abstained[i] = True
            reasons[i] = AbstainReason.AMBIGUOUS
        # else: exactly one confident class within the supported region — not abstained.

    return AbstentionResult(abstained=abstained, reason=reasons, max_reference_similarity=max_similarity)
