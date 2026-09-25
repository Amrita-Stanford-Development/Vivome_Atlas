"""The orchestrator: wires Stages 1-8 together and builds the response dict
for `POST /api/project` (docs/projection-service.md).

All six contract artifacts plus per-cell reference properties are real
(service/model/README.md). `ReferenceBundle.load()` still surfaces a missing
file as `PendingArtifactError` rather than fabricating centroids, in case a
path override points somewhere empty — the same principle as the manifest's
pending records, applied at request time, now guarding against
misconfiguration rather than an artifact that genuinely doesn't exist yet.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np

from service import config
from service.pipeline import abstention, alignment, assignment, calibration, coordinates, encoder, fallback, gene_ids, reference, smoothing, transfer


@dataclass(frozen=True)
class ReferenceBundle:
    """Everything the pipeline needs about the reference side, loaded once
    and reused across requests."""
    encoder_handle: "encoder.EncoderHandle"
    feature_genes: list[str]
    metadata: "reference.ReferenceMetadata"
    reference_embeddings: np.ndarray  # (n_ref, 128), L2 normalised
    reference_centroids: np.ndarray  # (n_classes, 128), L2 normalised, ordered by class_idx
    reference_class_positions: np.ndarray  # (n_ref,) int, each cell's centroid row position
    pca: "coordinates.PcaTransform"
    property_names: list[str]
    property_values: np.ndarray  # (n_ref, n_properties)
    provenance: dict  # service/model/provenance.json — recorded, see pipeline.py's abstain-threshold note

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
        provenance = reference.load_provenance()
        pca = coordinates.fit_pca_3d(reference_embeddings)

        # metadata.class_idx_by_cell is in class_idx space; the centroids
        # array (and everything assignment.py does) is in row-POSITION
        # space (0..n_classes-1, sorted by class_idx) — translate once here,
        # at load time, rather than in every request.
        reference_class_positions = metadata.class_positions_by_cell()

        return cls(
            encoder_handle=encoder_handle, feature_genes=feature_genes, metadata=metadata,
            reference_embeddings=reference_embeddings, reference_centroids=reference_centroids,
            reference_class_positions=reference_class_positions,
            pca=pca, property_names=property_names, property_values=property_values,
            provenance=provenance,
        )


def run_projection(bundle: ReferenceBundle, raw: alignment.RawMatrix, rng: np.random.Generator | None = None) -> dict:
    """Runs Stages 1-8 and returns the response dict. `cells` entries match
    docs/projection-service.md exactly; `properties` and `model_version` are
    additive fields not yet in that published contract (see
    service/README.md) and should not be assumed by a strict reader of the
    doc alone.
    """
    rng = rng or np.random.default_rng()

    # assign_labels/top_label/calibrate_and_build_sets all work in centroid
    # ROW POSITION (0..n_classes-1), not the dataset's class_idx — the two
    # only coincide because this reference's class_idx happens to be a
    # contiguous 0-based range. Translate through metadata.classes' own
    # order (sorted by class_idx, matching the centroids array per the
    # contract) rather than assume position == class_idx. Computed up front
    # because Stage 4 needs it too, to restrict assignment by class name.
    class_name_by_position = [c.class_name for c in bundle.metadata.classes]
    allowed_positions = {
        position for position, name in enumerate(class_name_by_position)
        if name in config.CROSS_MODAL_SUPPORTED_CLASSES
    }

    # Track B: resolve this upload's gene identifiers (symbol, Ensembl ID,
    # UniProt accession, or a DIA-NN-style semicolon group) for reporting —
    # align_to_feature_space (Stage 1, below) does its own, identical
    # resolution internally to actually match genes; this second call
    # exists only so the response can report matched/unmapped/ambiguous
    # counts without changing align_to_feature_space's return type.
    gene_id_resolution = gene_ids.resolve_identifiers(raw.gene_names)

    # Stage 0 — detect and correct linear-scale intensity input (e.g. a raw
    # DIA-NN report) before anything else touches it. Never transforms data
    # already on a log scale (see alignment.detect_and_transform_value_scale).
    transformed_values, value_scale = alignment.detect_and_transform_value_scale(raw.values)
    raw = dataclasses.replace(raw, values=transformed_values)

    # Stage 1
    aligned = alignment.align_to_feature_space(raw, bundle.feature_genes)

    # Stage 2 — smooth using the query's own complete feature set, not just
    # the genes that also happen to be in the shared space. Z-scored per
    # gene (alignment.zscore_per_gene — the same convention Stage 1 uses for
    # the 9,002-gene subset), not raw units: raw units let the highest-
    # abundance proteins dominate the neighbour graph's PCA, a real,
    # measured divergence from the methodology that produced this
    # project's headline numbers (Documentation/known-limitations.md in
    # the fair-benchmark work; T1 NB1 independently found the same gap on
    # PBMC240, median cosine 0.78 against the notebook convention).
    full_query_values = alignment.zscore_per_gene(raw.values).T  # (n_cells, n_native_features)
    smoothed_values = smoothing.fuzzy_smooth(aligned.values, full_query_values)

    # Stage 3
    query_embeddings = bundle.encoder_handle.encode(smoothed_values, aligned.mask)

    # Stage 4 — restricted to config.CROSS_MODAL_SUPPORTED_CLASSES (see
    # assignment.py's module docstring for the measured justification).
    probs = assignment.assign_labels(
        query_embeddings, bundle.reference_centroids,
        reference_embeddings=bundle.reference_embeddings,
        reference_class_positions=bundle.reference_class_positions,
        allowed_positions=allowed_positions,
    )
    top_position, confidence = assignment.top_label(probs)

    # Stage 5
    calibrated = calibration.calibrate_and_build_sets(probs, rng=rng)

    # Stage 6 (raw pass — Stage 7 may downgrade an AMBIGUOUS verdict below)
    max_similarity = abstention.max_cosine_to_reference(query_embeddings, bundle.reference_embeddings)
    abstention_result = abstention.score_abstention(
        max_similarity=max_similarity,
        per_cell_observed_genes=aligned.per_cell_observed_genes,
        label_sets=calibrated.label_sets,
        calibration_indices=calibrated.calibration_indices,
    )

    # Stage 7 — resolve any AMBIGUOUS cell whose conformal set is exactly a
    # known confusable pair into the shared broader label; leave every other
    # verdict from Stage 6 untouched. The reported confidence is the winning
    # class's share *within the pair* (normalised so it doesn't depend on how
    # much mass leaked outside the pair) — not the pair's summed probability.
    # That was the original design, and it was right for an *unrestricted*
    # assignment (Stage 4 competing across all classes, so the sum genuinely
    # reflected how much of the total mass this broader claim captured). But
    # config.CROSS_MODAL_SUPPORTED_CLASSES now restricts Stage 4 to exactly
    # the two classes in the only confusable pair that can still trigger this
    # branch — so the two probabilities always sum to ~1.0 by construction,
    # and reporting that sum as "confidence" would report 1.0 for every
    # resolved cell regardless of whether the split was 50/50 or 99/1. The
    # winning share is what actually varies and is worth reporting.
    resolved_label = [None] * len(calibrated.label_sets)
    resolved_confidence = [None] * len(calibrated.label_sets)
    for i, reason in enumerate(abstention_result.reason):
        if reason != abstention.AbstainReason.AMBIGUOUS:
            continue
        names = [class_name_by_position[c] for c in calibrated.label_sets[i]]
        fallback_label = fallback.resolve_fallback(names)
        if fallback_label is not None:
            abstention_result.abstained[i] = False
            abstention_result.reason[i] = abstention.AbstainReason.NONE
            resolved_label[i] = fallback_label
            pair_mass = probs[i, calibrated.label_sets[i]]
            resolved_confidence[i] = float(pair_mass.max() / pair_mass.sum())

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
            "observed_genes": int(aligned.per_cell_observed_genes[i]),
        }
        if abstention_result.abstained[i]:
            entry.update(label=None, label_set=[], confidence=None, abstained=True,
                         abstain_reason=abstention_result.reason[i].value)
        else:
            label_set_names = [class_name_by_position[c] for c in calibrated.label_sets[i]]
            entry.update(
                label=resolved_label[i] or class_name_by_position[top_position[i]],
                label_set=label_set_names,
                confidence=resolved_confidence[i] if resolved_confidence[i] is not None else float(confidence[i]),
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
        "value_scale": {"detected": value_scale.detected, "transformed": value_scale.transformed},
        "gene_id_resolution": {
            "matched": gene_id_resolution.matched,
            "unmapped": gene_id_resolution.unmapped,
            "ambiguous": gene_id_resolution.ambiguous,
            "unmapped_identifiers": gene_id_resolution.unmapped_identifiers,
            "ambiguous_identifiers": gene_id_resolution.ambiguous_identifiers,
        },
        # Recorded for comparison, not the abstain decision itself — Stage 6
        # still uses abstention.py's live per-request quantile. This is the
        # reference's own pre-calibrated value (provenance.json), which
        # answers a related but not identical question (calibrated once
        # against RNA masked to realistic per-dataset coverage, vs. computed
        # per-request against this query's own calibration slice). Nobody
        # has yet verified the two agree across varied real coverage; this
        # field exists to make that comparison possible.
        "reference_abstain_threshold": bundle.provenance.get("abstain_threshold"),
        "cells": cells,
    }
