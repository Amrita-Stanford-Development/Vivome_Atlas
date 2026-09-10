"""The orchestrator: wires Stages 1-8 together and builds the response dict
for `POST /api/project` (docs/projection-service.md).

Only the encoder (Stage 3) has a working artifact today — the dev
placeholder checkpoint. `reference_embedding.npy`, `reference_centroids.npy`,
and per-cell reference property values are all blocked on the full v3
training run and do not exist anywhere in this repo (Download_Checklist.md,
"Still waiting on"; there is also no raw RNA expression data in this repo to
derive them from independently). `ReferenceBundle.load()` surfaces that
honestly as `PendingArtifactError` rather than fabricating centroids to keep
the service responding — the same principle as the manifest's pending
records, applied at request time. Every stage is nonetheless fully
implemented and tested against synthetic reference fixtures (see
service/tests/), so activating the service end-to-end is a matter of
supplying the three missing files, not writing more code.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from service import config
from service.pipeline import abstention, alignment, assignment, calibration, coordinates, encoder, fallback, reference, smoothing, transfer


@dataclass(frozen=True)
class ReferenceBundle:
    """Everything the pipeline needs about the reference side, loaded once
    and reused across requests."""
    encoder_handle: "encoder.EncoderHandle"
    feature_genes: list[str]
    metadata: "reference.ReferenceMetadata"
    reference_embeddings: np.ndarray  # (n_ref, 128), L2 normalised
    reference_centroids: np.ndarray  # (n_classes, 128), L2 normalised, ordered by class_idx
    pca: "coordinates.PcaTransform"
    property_names: list[str]
    property_values: np.ndarray  # (n_ref, n_properties)

    @property
    def model_version(self) -> str:
        return encoder.model_version_label(self.encoder_handle)

    @classmethod
    def load(cls) -> "ReferenceBundle":
        """Raises reference.PendingArtifactError naming whichever contract
        file is missing. Callers (the HTTP layer) should turn that into an
        honest "not yet available" response, not a 500."""
        encoder_handle = encoder.load_encoder()
        feature_genes = reference.load_feature_space_genes()
        metadata = reference.load_reference_metadata()
        reference_embeddings = reference.load_reference_embedding()
        reference_centroids = reference.load_reference_centroids()
        property_names, property_values = reference.load_reference_properties()
        pca = coordinates.fit_pca_3d(reference_embeddings)
        return cls(
            encoder_handle=encoder_handle, feature_genes=feature_genes, metadata=metadata,
            reference_embeddings=reference_embeddings, reference_centroids=reference_centroids,
            pca=pca, property_names=property_names, property_values=property_values,
        )


def run_projection(bundle: ReferenceBundle, raw: alignment.RawMatrix, rng: np.random.Generator | None = None) -> dict:
    """Runs Stages 1-8 and returns the response dict. `cells` entries match
    docs/projection-service.md exactly; `properties` and `model_version` are
    additive fields not yet in that published contract (see
    service/README.md) and should not be assumed by a strict reader of the
    doc alone.
    """
    rng = rng or np.random.default_rng()

    # Stage 1
    aligned = alignment.align_to_feature_space(raw, bundle.feature_genes)

    # Stage 2 — smooth using the query's own complete feature set, not just
    # the genes that also happen to be in the shared space.
    full_query_values = np.nan_to_num(raw.values.T, nan=0.0)  # (n_cells, n_native_features)
    smoothed_values = smoothing.fuzzy_smooth(aligned.values, full_query_values)

    # Stage 3
    query_embeddings = bundle.encoder_handle.encode(smoothed_values, aligned.mask)

    # Stage 4
    probs = assignment.assign_labels(query_embeddings, bundle.reference_centroids)
    top_class_idx, confidence = assignment.top_label(probs)

    # Stage 5
    calibrated = calibration.calibrate_and_build_sets(probs, rng=rng)

    # Stage 6 (raw pass — Stage 7 may downgrade an AMBIGUOUS verdict below)
    max_similarity = abstention.max_cosine_to_reference(query_embeddings, bundle.reference_embeddings)
    abstention_result = abstention.score_abstention(
        max_similarity=max_similarity,
        per_cell_coverage=aligned.per_cell_coverage,
        label_sets=calibrated.label_sets,
        calibration_indices=calibrated.calibration_indices,
    )

    # Class-idx -> class-name lookup, once.
    idx_to_name = {c.class_idx: c.class_name for c in bundle.metadata.classes}

    # Stage 7 — resolve any AMBIGUOUS cell whose conformal set is exactly a
    # known confusable pair into the shared broader label; leave every other
    # verdict from Stage 6 untouched.
    resolved_label = [None] * len(calibrated.label_sets)
    for i, reason in enumerate(abstention_result.reason):
        if reason != abstention.AbstainReason.AMBIGUOUS:
            continue
        names = [idx_to_name[c] for c in calibrated.label_sets[i]]
        fallback_label = fallback.resolve_fallback(names)
        if fallback_label is not None:
            abstention_result.abstained[i] = False
            abstention_result.reason[i] = abstention.AbstainReason.NONE
            resolved_label[i] = fallback_label

    # Stage 8 — property transfer, independent of the label/abstention path.
    property_result = transfer.transfer_properties(
        query_embeddings, bundle.reference_embeddings, bundle.property_names, bundle.property_values,
    )

    coords = bundle.pca.project(query_embeddings)

    cells = []
    for i, cell_id in enumerate(aligned.cell_ids):
        entry = {
            "cell_id": cell_id,
            "coordinates": [float(x) for x in coords[i]],
        }
        if abstention_result.abstained[i]:
            entry.update(label=None, label_set=[], confidence=None, abstained=True,
                         abstain_reason=abstention_result.reason[i].value)
        else:
            label_set_names = [idx_to_name[c] for c in calibrated.label_sets[i]]
            entry.update(
                label=resolved_label[i] or idx_to_name[top_class_idx[i]],
                label_set=label_set_names,
                confidence=float(confidence[i]),
                abstained=False,
            )
        entry["properties"] = {
            name: {"value": float(property_result.values[i, j]), "uncertainty": float(property_result.uncertainty[i, j])}
            for j, name in enumerate(property_result.property_names)
        }
        cells.append(entry)

    return {
        "atlas_version": config.ATLAS_VERSION,
        "model_version": bundle.model_version,
        "n_cells": len(aligned.cell_ids),
        "n_features_matched": aligned.n_features_matched,
        "n_features_unmatched": aligned.n_features_unmatched,
        "cells": cells,
    }
