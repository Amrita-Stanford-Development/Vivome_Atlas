"""Which reference classes a query may be labelled with (Track C: the
socket T1 NB2's label space estimate plugs into; research/roadmap.md).

Stage 4 only ever scores classes inside the label space. v3 has no
estimate of its own: every class is a candidate, or, when a request opts in,
only config.CROSS_MODAL_SUPPORTED_CLASSES (assignment.py's module docstring
has the evidence for that restriction, and pipeline.run_projection's for why
it is no longer the default). v3.1 replaces this with a per-upload estimate
of which classes are actually present, with a support score for each; its
implementation lands in Track F from NB2's `label_space_config.json` and
`bcts_params.json`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from service import config
from service.pipeline import reference


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


def load_v31_artifacts() -> dict:
    """T1 NB2's label space estimator and calibration parameters, parsed.
    PendingArtifactError until the export lands."""
    out = {}
    for key, path in (("label_space_config", config.V31_LABEL_SPACE_CONFIG_PATH),
                      ("bcts_params", config.V31_BCTS_PARAMS_PATH)):
        with open(reference.require_v31_artifact(path, "T1 NB2"), encoding="utf-8") as handle:
            out[key] = json.load(handle)
    return out
