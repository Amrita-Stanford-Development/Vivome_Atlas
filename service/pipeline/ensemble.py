"""v3.1: the ensemble pipeline specified by T1 NB2 (research/roadmap.md,
Track F). Every setting below comes from service/model/v3_1/nb2_spec_v31.json,
NB2's own export; nothing here is re-derived.

What changes against v3:
- Five V2 encoders (NB1b's mini-upload gene z variant: v3's architecture and
  input shape). Each member scores softmax(cosine to its class centroids / T),
  with its own fitted temperature T; the ensemble probability is the mean of
  the members' probabilities.
- No per-upload label space estimate (NB2 chose "none").
- Mondrian conformal sets, one qhat per class (calibration.MondrianCalibrator).
- Out of distribution: the mean over members of the max cosine to any
  reference cell, below NB2's fixed threshold (abstention.V31AbstentionScorer).
- Hierarchical answers: one class; or, when the set spans several classes,
  the group they share (e.g. "T cell"); or the lineage they share; or abstain.
- Every cell not refused for coverage also gets a best guess: the ensemble's
  argmax class and its probability.

Stages 0-2 (value scale, alignment, smoothing) are v3's and run once, shared
by every member. Coordinates and property transfer use one member
(config.V31_COORDINATE_MEMBER), the same one the site's atlas coordinates
come from, so a projected cell lands on the displayed atlas.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

import numpy as np

from service import config
from service.pipeline import (
    abstention, calibration, coordinates, encoder, gene_ids, label_space, pipeline, reference, search, transfer,
)

MODEL_VERSION_LABEL = "v3.1 ensemble (T1 NB2: V2 seeds 0 to 4)"


# ---- the math, pure ----

def member_probabilities(embeddings: np.ndarray, centroids: np.ndarray, temperature: float) -> np.ndarray:
    """softmax(cosine to each class centroid / temperature). Both sides are
    L2 normalised, so the dot product is the cosine."""
    logits = (embeddings.astype(np.float64) @ centroids.astype(np.float64).T) / temperature
    logits -= logits.max(axis=1, keepdims=True)
    weights = np.exp(logits)
    return weights / weights.sum(axis=1, keepdims=True)


def ensemble_probabilities(member_probs: list[np.ndarray]) -> np.ndarray:
    """The mean of the members' probabilities (NB2: "mean of per member
    probabilities"), not of their logits."""
    return np.mean(np.stack(member_probs), axis=0)


def resolve(set_names: list[str], hierarchy: dict) -> "tuple[str, str] | None":
    """NB2's output rule for a conformal set: one class, that class; several
    classes in one group, the group; several groups in one lineage, the
    lineage; otherwise None (ambiguous). Returns (label, level)."""
    if not set_names:
        return None
    if len(set_names) == 1:
        return set_names[0], "class"
    groups = {hierarchy[name]["group"] for name in set_names}
    if len(groups) == 1:
        return groups.pop(), "group"
    lineages = {hierarchy[name]["lineage"] for name in set_names}
    if len(lineages) == 1:
        return lineages.pop(), "lineage"
    return None


def best_guess(probs: np.ndarray, positions: "set[int] | None") -> tuple[np.ndarray, np.ndarray]:
    """(argmax position, its probability) per cell, within the label space."""
    if positions is None:
        masked = probs
    else:
        masked = np.full_like(probs, -1.0)
        idx = sorted(positions)
        masked[:, idx] = probs[:, idx]
    top = masked.argmax(axis=1)
    return top, probs[np.arange(len(top)), top]


def sign_fixed(pca: "coordinates.PcaTransform") -> "coordinates.PcaTransform":
    """eigh's eigenvector signs depend on the LAPACK build. Flip each axis so
    its largest loading is positive, so the site's atlas file
    (scripts/export_atlas_coordinates.py) and the service agree on any machine."""
    largest = pca.components[np.arange(len(pca.components)), np.abs(pca.components).argmax(axis=1)]
    return coordinates.PcaTransform(mean=pca.mean, components=pca.components * np.sign(largest)[:, None])


# ---- the bundle ----

@dataclass(frozen=True)
class Member:
    name: str
    encoder_handle: "encoder.EncoderHandle"
    reference_latents: np.ndarray  # (n_ref, 128) float32, reference_metadata.csv row order
    centroids: np.ndarray  # (n_classes, 128), class position order
    temperature: float


def _verify_manifest() -> dict:
    """Every v3.1 file must match the sha256 in MANIFEST.json: a stale or
    half-copied file fails loudly here instead of serving wrong answers.
    Either way the service answers 503 with the reason until the right
    file is in place (scripts/fetch_v31_members.py)."""
    manifest_path = config.V31_MANIFEST_PATH
    if not manifest_path.exists():
        raise reference.PendingArtifactError(
            f"{manifest_path} does not exist. v3.1's files are T1 NB2's export (service/model/README.md, v3_1/)."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Every file's presence first (cheap), so a missing file is named without
    # hashing half a gigabyte; the service rechecks on every request until it loads.
    for rel in manifest["files"]:
        path = config.V31_DIR / rel
        if not path.exists():
            raise reference.PendingArtifactError(
                f"{path} does not exist (listed in {manifest_path}). Run scripts/fetch_v31_members.py."
            )
    for rel, entry in manifest["files"].items():
        path = config.V31_DIR / rel
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise reference.PendingArtifactError(
                f"{path} does not match its sha256 in {manifest_path}: a partial copy, or a file "
                "changed after the manifest was written. Run scripts/fetch_v31_members.py."
            )
    return manifest


def load_spec() -> dict:
    if not config.V31_SPEC_PATH.exists():
        raise reference.PendingArtifactError(f"{config.V31_SPEC_PATH} does not exist. It is T1 NB2's export.")
    return json.loads(config.V31_SPEC_PATH.read_text(encoding="utf-8"))


# Service-side behaviour flags. NB2's export carries none, so each takes its
# default; a later notebook's spec can set them under "service_flags".
# Neither has been evaluated on RNA yet (research/todo.md, Track F).
SERVICE_FLAGS = {
    "set_includes_best_guess": True,  # calibration.MondrianCalibrator
    "restricted_renormalise": True,  # label_space.V31LabelSpace
}


def service_flags(spec: dict) -> dict:
    return {**SERVICE_FLAGS, **spec.get("service_flags", {})}


def validate_spec(spec: dict, class_names: list[str]) -> None:
    """Every check v3.1 relies on, once, when the bundle loads. A spec that
    fails any of them is refused (the service answers 500 with the list)
    rather than served with a silent misreading."""
    problems = []
    try:
        if spec["class_order"] != class_names:
            problems.append("class_order is not the reference's class order; the centroids would be misread")
        if spec["preprocessing"]["convention"] != "service" or not spec["preprocessing"]["smoothing"]:
            problems.append("preprocessing asks for something other than the service convention with smoothing")
        if not int(spec["preprocessing"]["min_observed_genes"]) > 0:
            problems.append("min_observed_genes must be positive")
        if spec["assignment"]["rule"] != "centroid" or spec["label_space"]["method"] != "none":
            problems.append("assignment rule or label space is not one this module implements")
        members = spec["encoder"]["members"]
        if config.V31_COORDINATE_MEMBER not in members:
            problems.append(f"the coordinate member {config.V31_COORDINATE_MEMBER} is not a member")
        for name in members:
            t = spec["assignment"]["temperature"].get(name)
            if not (isinstance(t, (int, float)) and np.isfinite(t) and t > 0):
                problems.append(f"no positive temperature for {name}")
        if spec["conformal"]["type"] != "mondrian" or not 0 < float(spec["conformal"]["alpha"]) < 1:
            problems.append("conformal must be mondrian with 0 < alpha < 1")
        qhat = spec["conformal"]["qhat_by_class"]
        for name in class_names:
            q = qhat.get(name)
            if not (isinstance(q, (int, float)) and 0 <= q <= 1):
                problems.append(f"no qhat in [0, 1] for {name!r}")
            node = spec["hierarchy"].get(name, {})
            if not (isinstance(node.get("group"), str) and isinstance(node.get("lineage"), str)):
                problems.append(f"no group and lineage for {name!r}")
        if not -1 <= float(spec["ood"]["threshold"]) <= 1:
            problems.append("ood threshold is not a cosine")
        unknown = set(spec.get("service_flags", {})) - set(SERVICE_FLAGS)
        if unknown or not all(isinstance(v, bool) for v in spec.get("service_flags", {}).values()):
            problems.append(f"service_flags must be booleans among {sorted(SERVICE_FLAGS)}")
    except (KeyError, TypeError, ValueError) as exc:
        problems.append(f"missing or malformed field: {exc!r}")
    if problems:
        raise ValueError(f"{config.V31_SPEC_PATH} is not a usable v3.1 spec: " + "; ".join(problems))


def build_components(spec: dict) -> "pipeline.Components":
    """The label space, conformal and abstention stages, from one spec.
    qhat is read by class name, in class_order."""
    flags = service_flags(spec)
    conformal = spec["conformal"]
    return pipeline.Components(
        version="v3.1",
        label_space=label_space.V31LabelSpace(renormalise=flags["restricted_renormalise"]),
        calibrator=calibration.MondrianCalibrator(
            np.array([conformal["qhat_by_class"][name] for name in spec["class_order"]]),
            conformal["marginal_qhat"], conformal["alpha"], conformal["calibrated_on"],
            include_best_guess=flags["set_includes_best_guess"],
        ),
        abstention=abstention.V31AbstentionScorer(
            float(spec["ood"]["threshold"]), int(spec["preprocessing"]["min_observed_genes"]),
        ),
    )


@dataclass(frozen=True)
class V31Bundle:
    members: "tuple[Member, ...]"
    coordinate_member: int
    feature_genes: list[str]
    metadata: "reference.ReferenceMetadata"
    class_names: list[str]
    hierarchy: dict
    ood_threshold: float
    min_observed_genes: int
    pca: "coordinates.PcaTransform"
    property_names: list[str]
    property_values: np.ndarray
    spec: dict
    components: "pipeline.Components"  # built from `spec` at load; every request uses these

    pipeline_version = "v3.1"

    @property
    def model_version(self) -> str:
        return MODEL_VERSION_LABEL

    @classmethod
    def load(cls) -> "V31Bundle":
        _verify_manifest()
        spec = load_spec()  # the one read; components and thresholds below all come from it
        metadata = reference.load_reference_metadata()
        class_names = [c.class_name for c in metadata.classes]
        validate_spec(spec, class_names)

        members = []
        for name in spec["encoder"]["members"]:
            seed = int(re.search(r"seed(\d+)", name).group(1))
            members.append(Member(
                name=name,
                encoder_handle=encoder.load_encoder(config.V31_MEMBERS_DIR / name),
                reference_latents=np.load(config.V31_MEMBERS_DIR / f"V2_seed{seed}_reference_latent_f16.npy").astype(np.float32),
                centroids=np.load(config.V31_MEMBERS_DIR / f"V2_seed{seed}_centroids.npy").astype(np.float32),
                temperature=float(spec["assignment"]["temperature"][name]),
            ))
        coordinate_member = spec["encoder"]["members"].index(config.V31_COORDINATE_MEMBER)
        property_names, property_values = reference.load_reference_properties()
        return cls(
            members=tuple(members), coordinate_member=coordinate_member,
            feature_genes=reference.load_feature_space_genes(), metadata=metadata,
            class_names=class_names, hierarchy=spec["hierarchy"],
            ood_threshold=float(spec["ood"]["threshold"]),
            min_observed_genes=int(spec["preprocessing"]["min_observed_genes"]),
            pca=sign_fixed(coordinates.fit_pca_3d(members[coordinate_member].reference_latents)),
            property_names=property_names, property_values=property_values, spec=spec,
            components=build_components(spec),
        )


# ---- the request ----

def project(bundle: V31Bundle, raw, restrict_to_supported_classes: bool, components: "pipeline.Components") -> dict:
    """The v3.1 response: every v3 field, with the label answered at the
    level the evidence supports, plus label_level and best_guess per cell and
    the v3.1 blocks (docs/service/projection-api.md, "v3.1")."""
    # Stages 0-2 (v3's, once for every member).
    smoothed_values, aligned, value_scale = pipeline._prepare_query(bundle.feature_genes, raw)
    return project_prepared(bundle, smoothed_values, aligned, value_scale,
                            gene_ids.resolve_identifiers(raw.gene_names), restrict_to_supported_classes, components)


def project_prepared(bundle, smoothed_values, aligned, value_scale, gene_id_resolution,
                     restrict_to_supported_classes, components) -> dict:
    """Stages 3-8 on a query already aligned and smoothed. project() calls
    it after the service's Stages 0-2; benchmark/notebook_convention.py calls
    it after NB2's own parse, for the development-data gate."""
    names = bundle.class_names
    # Stage 3 per member.
    embeddings = [m.encoder_handle.encode(smoothed_values, aligned.mask) for m in bundle.members]

    # Stage 4: each member's tempered softmax, averaged.
    probs = ensemble_probabilities([
        member_probabilities(z, m.centroids, m.temperature) for z, m in zip(embeddings, bundle.members)
    ])
    space = components.label_space.estimate(None, names, restrict_to_supported_classes)
    probs = components.label_space.probabilities(probs, space)  # renormalised over a restricted space

    # Stage 5: Mondrian sets. Stage 6: coverage, then out of distribution.
    calibrated = components.calibrator.calibrate(probs, None, space)
    ood_score = np.mean([
        search.faiss_max_cosine_to_reference(z, m.reference_latents) for z, m in zip(embeddings, bundle.members)
    ], axis=0)
    verdict = components.abstention.score(
        max_similarity=ood_score, hidden_features=None,
        per_cell_observed_genes=aligned.per_cell_observed_genes,
        label_sets=calibrated.label_sets, calibration_indices=calibrated.calibration_indices,
    )
    guess_position, guess_probability = best_guess(probs, space.positions)

    # Stage 8 and the coordinates: the coordinate member's latent space.
    anchor = bundle.members[bundle.coordinate_member]
    z_anchor = embeddings[bundle.coordinate_member]
    property_result = transfer.transfer_properties(
        z_anchor, anchor.reference_latents, bundle.property_names, bundle.property_values,
    )
    coords = bundle.pca.project(z_anchor)

    cells = []
    for i, cell_id in enumerate(aligned.cell_ids):
        reason = verdict.reason[i]
        set_names = [names[c] for c in calibrated.label_sets[i]]
        resolved = None
        if reason in (abstention.AbstainReason.NONE, abstention.AbstainReason.AMBIGUOUS):
            # Stage 7, v3.1's way: the level the set's classes share.
            resolved = resolve(set_names, bundle.hierarchy)
            reason = abstention.AbstainReason.NONE if resolved else abstention.AbstainReason.AMBIGUOUS
        entry = {
            "cell_id": cell_id,
            "coordinates": [float(x) for x in coords[i]],
            "observed_genes": int(aligned.per_cell_observed_genes[i]),
            # The out-of-distribution score, compared against reference_abstain_threshold.
            "reference_similarity": float(ood_score[i]),
        }
        if resolved:
            label, level = resolved
            entry.update(
                label=label, label_level=level, label_set=set_names,
                # The ensemble's probability that the cell is one of the classes it names.
                confidence=float(probs[i, calibrated.label_sets[i]].sum()),
                abstained=False,
            )
        else:
            entry.update(label=None, label_level=None, label_set=[], confidence=None, abstained=True,
                         abstain_reason=reason.value,
                         abstain_category=abstention.CATEGORY_BY_REASON[reason].value)
        if reason is not abstention.AbstainReason.LOW_COVERAGE:
            entry["best_guess"] = {"label": names[guess_position[i]], "probability": float(guess_probability[i])}
        entry["properties"] = {
            name: {"value": float(property_result.values[i, j]), "uncertainty": float(property_result.uncertainty[i, j])}
            for j, name in enumerate(property_result.property_names)
        }
        cells.append(entry)

    positions = sorted(space.positions) if space.positions is not None else range(len(names))
    return {
        "atlas_version": config.ATLAS_VERSION,
        "model_version": bundle.model_version,
        "pipeline_version": "v3.1",
        "n_cells": len(aligned.cell_ids),
        "n_features_matched": aligned.n_features_matched,
        "n_features_unmatched": aligned.n_features_unmatched,
        "value_scale": {"detected": value_scale.detected, "transformed": value_scale.transformed},
        "label_space": {
            "restricted_to_supported_classes": restrict_to_supported_classes,
            "candidate_classes": [names[p] for p in positions],
        },
        "supported_classes": {
            "names": [names[p] for p in positions],
            "method": space.method,
            "support": None,
            "renormalised": space.positions is not None and components.label_space.renormalise,
        },
        "calibration": components.calibrator.describe(calibrated),
        "gene_id_resolution": {
            "matched": gene_id_resolution.matched,
            "unmapped": gene_id_resolution.unmapped,
            "ambiguous": gene_id_resolution.ambiguous,
            "unmapped_identifiers": gene_id_resolution.unmapped_identifiers,
            "ambiguous_identifiers": gene_id_resolution.ambiguous_identifiers,
        },
        # The decision threshold itself in v3.1 (NB2's), not a comparison value.
        "reference_abstain_threshold": bundle.ood_threshold,
        "cells": cells,
    }
