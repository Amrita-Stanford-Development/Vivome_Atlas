"""The orchestrator: wires Stages 1-8 together and builds the response dict
for `POST /api/project` (docs/service/projection-api.md).

All six contract artifacts plus per-cell reference properties are real
(service/model/README.md). `ReferenceBundle.load()` still surfaces a missing
file as `PendingArtifactError` rather than fabricating centroids, in case a
path override points somewhere empty — the same principle as the manifest's
pending records, applied at request time, now guarding against
misconfiguration rather than an artifact that genuinely doesn't exist yet.
"""
from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass

import numpy as np

from service import config
from service.pipeline import abstention, alignment, assignment, calibration, coordinates, encoder, fallback, gene_ids, label_space, reference, search, smoothing, transfer


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
    provenance: dict  # service/model/runtime/provenance.json — recorded, see pipeline.py's abstain-threshold note

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


@dataclass(frozen=True)
class Components:
    """The three stages Track C made swappable (research/roadmap.md). v3 is
    today's behaviour; v3.1's implementations land in Track F."""
    version: str
    label_space: "label_space.LabelSpaceEstimator"
    calibrator: "calibration.ConformalCalibrator"
    abstention: "abstention.AbstentionScorer"


def components_for(version: str) -> Components:
    """v3: today's components. v3.1: loads T1 NB2 to NB4's artifacts, which
    raises PendingArtifactError while they are missing. With the artifacts in
    place it still refuses until Track F implements the components that read
    them, rather than silently serving v3 under a v3.1 label."""
    if version == "v3":
        return Components(
            version="v3", label_space=label_space.V3LabelSpace(),
            calibrator=calibration.V3ConformalCalibrator(), abstention=abstention.V3AbstentionScorer(),
        )
    if version == "v3.1":
        label_space.load_v31_artifacts()
        abstention.load_v31_artifacts()
        calibration.load_v31_artifacts()
        raise NotImplementedError(
            "The v3.1 artifacts are present, but the components that read them are built in "
            "Track F from T1 NB4's service_change_spec.md (research/roadmap.md)."
        )
    raise ValueError(f"Unknown pipeline version {version!r}; expected one of {config.PIPELINE_VERSIONS}.")


def _prepare_query(
    feature_genes: list[str], raw: alignment.RawMatrix,
) -> tuple[np.ndarray, alignment.AlignedQuery, alignment.ValueScale]:
    """Stages 0-2, up to the encoder's input."""
    # Stage 0 — detect and correct linear-scale intensity input (e.g. a raw
    # DIA-NN report) before anything else touches it. Never transforms data
    # already on a log scale (see alignment.detect_and_transform_value_scale).
    transformed_values, value_scale = alignment.detect_and_transform_value_scale(raw.values)
    raw = dataclasses.replace(raw, values=transformed_values)

    # Stage 1
    aligned = alignment.align_to_feature_space(raw, feature_genes)

    # Stage 2 — smooth using the query's own complete feature set, not just
    # the genes that also happen to be in the shared space. Z-scored per
    # gene (alignment.zscore_per_gene — the same convention Stage 1 uses for
    # the 9,002-gene subset), not raw units: raw units let the highest-
    # abundance proteins dominate the neighbour graph's PCA, a real,
    # measured divergence from the methodology that produced this
    # project's headline numbers (research/benchmark/known-limitations.md in
    # the fair-benchmark work; T1 NB1 independently found the same gap on
    # PBMC240, median cosine 0.78 against the notebook convention).
    full_query_values = alignment.zscore_per_gene(raw.values).T  # (n_cells, n_native_features)
    smoothed_values = smoothing.fuzzy_smooth(aligned.values, full_query_values)
    return smoothed_values, aligned, value_scale


def embed_query(
    encoder_handle: "encoder.EncoderHandle", feature_genes: list[str], raw: alignment.RawMatrix,
) -> tuple[np.ndarray, alignment.AlignedQuery, alignment.ValueScale]:
    """Stages 0-3: value scale, alignment, smoothing, encoding — the whole
    query side, from a parsed upload to latent vectors. run_projection and
    the benchmark harness (benchmark/) both call this, so an
    evaluation scores exactly what the service computes."""
    smoothed_values, aligned, value_scale = _prepare_query(feature_genes, raw)
    # Stage 3
    query_embeddings = encoder_handle.encode(smoothed_values, aligned.mask)
    return query_embeddings, aligned, value_scale


def embed_query_with_hidden(
    encoder_handle: "encoder.EncoderHandle", feature_genes: list[str], raw: alignment.RawMatrix,
) -> tuple[np.ndarray, np.ndarray, alignment.AlignedQuery, alignment.ValueScale]:
    """embed_query plus the encoder's 512-dimensional pre-projection features,
    which v3.1's out-of-distribution score reads (T1 NB3)."""
    smoothed_values, aligned, value_scale = _prepare_query(feature_genes, raw)
    query_embeddings, hidden = encoder_handle.encode_with_hidden(smoothed_values, aligned.mask)
    return query_embeddings, hidden, aligned, value_scale


def upload_seed(raw: alignment.RawMatrix) -> int:
    """A seed derived from the upload itself: its gene names, cell ids and
    values. Stage 5 draws its random calibration slice from this, so the same
    file always gives the same conformal sets and abstentions. With an
    unseeded generator, identical uploads used to disagree (Fulcher 2026:
    15.6% vs 12.2% abstained)."""
    digest = hashlib.sha256()
    digest.update("\n".join(raw.gene_names).encode("utf-8"))
    digest.update(b"\0")
    digest.update("\n".join(raw.cell_ids).encode("utf-8"))
    digest.update(b"\0")
    digest.update(np.ascontiguousarray(raw.values, dtype=np.float32).tobytes())
    return int.from_bytes(digest.digest()[:8], "big")


def run_projection(
    bundle: ReferenceBundle,
    raw: alignment.RawMatrix,
    rng: np.random.Generator | None = None,
    restrict_to_supported_classes: bool = False,
    components: "Components | None" = None,
) -> dict:
    """Runs Stages 1-8 and returns the response dict. `cells` entries match
    docs/service/projection-api.md exactly; `properties` and `model_version` are
    additive fields not yet in that published contract (see
    service/README.md) and should not be assumed by a strict reader of the
    doc alone.

    Stage 4 chooses among all reference classes by default.
    `restrict_to_supported_classes=True` opts in to the old behaviour:
    labels are limited to config.CROSS_MODAL_SUPPORTED_CLASSES. It is not the
    default because a lymphoid upload then has no correct label: the Fulcher
    2026 PBMC upload came back entirely macrophage/monocyte or abstained.

    Without an explicit `rng`, the calibration slice is seeded from the
    upload (upload_seed), so identical uploads give identical responses.

    `components` defaults to config.PIPELINE_VERSION's (components_for). A v3
    response is exactly today's; any other version adds `pipeline_version`,
    `supported_classes`, `calibration` and a per-cell `abstain_category`
    (docs/service/projection-api.md, "v3.1").
    """
    components = components or components_for(config.PIPELINE_VERSION)
    rng = rng or np.random.default_rng(upload_seed(raw))

    # assign_labels/top_label/calibrate_and_build_sets all work in centroid
    # ROW POSITION (0..n_classes-1), not the dataset's class_idx — the two
    # only coincide because this reference's class_idx happens to be a
    # contiguous 0-based range. Translate through metadata.classes' own
    # order (sorted by class_idx, matching the centroids array per the
    # contract) rather than assume position == class_idx. Computed up front
    # because Stage 4 needs it too, to restrict assignment by class name.
    class_name_by_position = [c.class_name for c in bundle.metadata.classes]

    # Track B: resolve this upload's gene identifiers (symbol, Ensembl ID,
    # UniProt accession, or a DIA-NN-style semicolon group) for reporting —
    # align_to_feature_space (Stage 1, below) does its own, identical
    # resolution internally to actually match genes; this second call
    # exists only so the response can report matched/unmapped/ambiguous
    # counts without changing align_to_feature_space's return type.
    gene_id_resolution = gene_ids.resolve_identifiers(raw.gene_names)

    # Stages 0-3 (with the pre-projection features only when Stage 6 reads them)
    hidden = None
    if components.abstention.needs_hidden:
        query_embeddings, hidden, aligned, value_scale = embed_query_with_hidden(
            bundle.encoder_handle, bundle.feature_genes, raw)
    else:
        query_embeddings, aligned, value_scale = embed_query(bundle.encoder_handle, bundle.feature_genes, raw)

    # Stage 4 — scored only within the label space. v3: all reference classes
    # by default, config.CROSS_MODAL_SUPPORTED_CLASSES when the request opts in
    # (see assignment.py's module docstring for why that restriction exists,
    # and run_projection's docstring for why it is no longer the default).
    space = components.label_space.estimate(query_embeddings, class_name_by_position, restrict_to_supported_classes)
    allowed_positions = space.positions
    probs = assignment.assign_labels(
        query_embeddings, bundle.reference_centroids,
        reference_embeddings=bundle.reference_embeddings,
        reference_class_positions=bundle.reference_class_positions,
        allowed_positions=allowed_positions,
    )
    top_position, confidence = assignment.top_label(probs)

    # Stage 5
    calibrated = components.calibrator.calibrate(probs, rng, space)

    # Stage 6 (raw pass — Stage 7 may downgrade an AMBIGUOUS verdict below)
    max_similarity = search.faiss_max_cosine_to_reference(query_embeddings, bundle.reference_embeddings)
    abstention_result = components.abstention.score(
        max_similarity=max_similarity,
        hidden_features=hidden,
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
    # when config.CROSS_MODAL_SUPPORTED_CLASSES restricts Stage 4 to exactly
    # the two classes in that one confusable pair, the two probabilities
    # always sum to ~1.0 by construction, and reporting that sum as
    # "confidence" would report 1.0 for every resolved cell regardless of
    # whether the split was 50/50 or 99/1. The winning share is what varies.
    # Now that restriction is opt-in, the unrestricted default is the case
    # where the summed probability would again carry information. The rule is
    # chosen per label-space method (config.FALLBACK_CONFIDENCE); choosing
    # between the two is open (research/todo.md, Track C), so both v3 modes
    # keep the winning share.
    confidence_rule = config.FALLBACK_CONFIDENCE[space.method]
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
            resolved_confidence[i] = fallback.pair_confidence(pair_mass, confidence_rule)

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

    response = {
        "atlas_version": config.ATLAS_VERSION,
        "model_version": bundle.model_version,
        "n_cells": len(aligned.cell_ids),
        "n_features_matched": aligned.n_features_matched,
        "n_features_unmatched": aligned.n_features_unmatched,
        "value_scale": {"detected": value_scale.detected, "transformed": value_scale.transformed},
        "label_space": {
            "restricted_to_supported_classes": restrict_to_supported_classes,
            "candidate_classes": [class_name_by_position[p] for p in sorted(allowed_positions)]
                                 if allowed_positions is not None else class_name_by_position,
        },
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
    if components.version != "v3":
        _add_v31_fields(response, components, space, calibrated, abstention_result, class_name_by_position)
    return response


def _add_v31_fields(response, components, space, calibrated, abstention_result, class_name_by_position) -> None:
    """The v3.1 schema's additive blocks (research/roadmap.md, Track C, item
    5; docs/service/projection-api.md, "v3.1"). Every v3 field stays."""
    positions = sorted(space.positions) if space.positions is not None else range(len(class_name_by_position))
    response["pipeline_version"] = components.version
    response["supported_classes"] = {
        "names": [class_name_by_position[p] for p in positions],
        "method": space.method,
        "support": None if space.support is None
        else {class_name_by_position[p]: float(score) for p, score in sorted(space.support.items())},
    }
    response["calibration"] = components.calibrator.describe(calibrated)
    for cell, reason in zip(response["cells"], abstention_result.reason):
        if cell["abstained"]:
            cell["abstain_category"] = abstention.CATEGORY_BY_REASON[reason].value
