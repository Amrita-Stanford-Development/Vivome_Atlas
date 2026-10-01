"""Which reference classes a query may be labelled with (Track C: the
socket T1 NB2's label space estimate plugs into; research/roadmap.md).

Stage 4 only ever scores classes inside the label space. v3 has no
estimate of its own: every class is a candidate, or, when a request opts in,
only config.CROSS_MODAL_SUPPORTED_CLASSES (assignment.py's module docstring
has the evidence for that restriction, and pipeline.run_projection's for why
it is no longer the default). T1 NB2 evaluated per-upload estimates (EM label
shift with a prior floor) and chose none for v3.1: every class a candidate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from service import config


@dataclass(frozen=True)
class LabelSpace:
    positions: "set[int] | None"  # centroid row positions allowed; None means every class
    support: "dict[int, float] | None"  # per-class support score; None when the method has none
    method: str  # names the rule, and keys config.FALLBACK_CONFIDENCE


class LabelSpaceEstimator(Protocol):
    def estimate(self, query_embeddings: np.ndarray, class_names: list[str], restrict: bool) -> LabelSpace:
        ...


class V3LabelSpace:
    """Today's behaviour, unchanged: all classes, or the cross-modal supported
    classes when the request opts in. No per-class support score."""

    def estimate(self, query_embeddings: np.ndarray, class_names: list[str], restrict: bool) -> LabelSpace:
        if not restrict:
            return LabelSpace(positions=None, support=None, method="all_classes")
        positions = {p for p, name in enumerate(class_names) if name in config.CROSS_MODAL_SUPPORTED_CLASSES}
        return LabelSpace(positions=positions, support=None, method="cross_modal_supported")


class V31LabelSpace:
    """v3.1 (T1 NB2 chose method "none"): no per-upload estimate, every class
    a candidate. A request may still opt in to the cross-modal supported
    classes, as in v3; NB2 did not evaluate that option."""

    def estimate(self, query_embeddings, class_names, restrict):
        if restrict:
            return V3LabelSpace().estimate(query_embeddings, class_names, True)
        return LabelSpace(positions=None, support=None, method="none")
