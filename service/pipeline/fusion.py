"""v4: v3.1's answers, unchanged, with a better best guess (research/todo.md,
Track G; research/notebook-run-history.md, entries 20 to 24).

The answer to each cell (its conformal set, the abstentions, the class, group
or lineage it names, the coordinates and properties) is v3.1's, from v3.1's
own bundle and spec (service/pipeline/ensemble.py, T1 NB2's calibration). v4
changes only the best guess, fused from three probabilities:

    encoder = s * E(smoothed query) + (1 - s) * E(unsmoothed query)
    best guess probability = w * encoder + (1 - w) * softmax(r / tau)

where E is the mean over v3.1's five V2 members of softmax(cosine to
class-balanced centroids / T) (scripts/build_v4_bundle.py), and r is each
cell's Pearson correlation, over its observed genes only, with the
class-balanced z-scored RNA class means.

The correlation term is used only where it carries signal. Every gene is
z-scored within its upload, so an upload of a single cell type loses the
contrast r needs (entry 23). The upload's agreement, the share of its cells
with at least the coverage floor's observed genes whose top class under r is
v3.1's top class, measures this: below the threshold, the correlation term
is flat (1 / classes) and the encoder is the smoothed query's alone, so the
guess is the class-balanced encoder's, on the fused probability's scale.

The fused best guess joins every non-empty set beside v3.1's own best guess
(the service flag set_includes_best_guess), so v4's sets contain v3.1's.

Phase 3 refitted conformal sets on the fused probability: NO GO (entry 21).
Phase 3b kept v3.1's answers but let the fused guess replace v3.1's in the
set, and used the correlation term in every upload: NO GO (entry 23). Phase 3c
(research/notebooks/v4_phase3c.py) scored this rule once on a fresh
evaluation suite: GO (entry 24). The service refuses a v4 spec whose
evaluation has not passed; such a bundle loads only for the scripts that
evaluate it (require_evaluation=False).

v4.1 is the same code and v4's data files with its own spec
(service/model/v4_1/spec_v41.json, scripts/build_v41_spec.py): where the
correlation term is used, the encoder's weight is the spec's
gate_on_fusion_weight (0.5) instead of fusion_weight (0.7, still the weight
where the term is flat). The weight was chosen on Fulcher 2026 under fixed
rules (research/notebooks/v41_pretest.py) and checked once on Khoury 2026
(benchmark/khoury2026_posthoc_v41_check.py). Its own evaluation passed
(Phase C), and it is the service's default since release 0.4.0.

v4.2 (Goal 2, Phase 2a) is v4.1 with protein class means from sorted cells
(Rieckmann 2017; service/model/v4_2/, scripts/build_v42_spec.py) in its
correlation term: for each class those cells cover, the cell's correlation is
with the protein class mean over its observed proteins, matched by gene
symbol; for the rest, v4.1's RNA class means. The agreement gate reads that
hybrid term. Single-cell proteomics measures abundant proteins only (research/
notebook-run-history.md, entry 30), and sorted cells' protein means separate
them better than RNA means do on the development data (entries 31 and 32). It
is refused until its evaluation passes.

v5 (research/todo.md, Track H) is v4.1's rule with everything underneath
rebuilt from cleaned reference labels (research/notebooks/v5_labels.py):
- five V2 members retrained with NB1d's recipe
  (research/notebooks/v5_train.py);
- their own calibration by NB2's recipe, so v5's answers are v5's, from
  the same code as v3.1's (ensemble.V31Bundle with service/model/v5/'s
  files);
- class-balanced centroids and class means (research/notebooks/v5_build.py).
Every v5 file is listed in service/model/v5/MANIFEST.json. It is refused
until its evaluation passes.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import warnings
from dataclasses import dataclass

import numpy as np

from service import config
from service.pipeline import abstention, ensemble, gene_ids, pipeline, reference, search, transfer

MODEL_VERSION_LABEL = "v4 (v3.1's answers; best guess fused from its V2 members on a class-balanced reference and correlation)"
MODEL_VERSION_LABELS = {
    "v4": MODEL_VERSION_LABEL,
    "v4.1": "v4.1 (v4 with the correlation term weighted more where it is used; chosen on Fulcher 2026)",
    "v4.2": "v4.2 (v4.1 with protein class means from sorted cells, Rieckmann 2017, in its correlation term)",
    "v5": "v5 (v4.1's rule on V2 members retrained on cleaned reference labels, with its own calibration)",
    "v5.1": "v5.1 (v5 with the NK T class folded into NK in training)",
    "v5.2": "v5.2 (v5.1 with CD4/CD8 T labels corrected by a classifier trained on Hao et al. 2021)",
}
ANSWERS_FROM = {"v4": "v3.1", "v4.1": "v3.1", "v4.2": "v3.1", **{v: v for v in config.V5_FAMILY}}
TRACK = {"v4": "Track G", "v4.1": "Track G", "v4.2": "Goal 2", **{v: "Track H" for v in config.V5_FAMILY}}


def version_files(version: str) -> tuple:
    """(spec, MANIFEST, the directory its paths are relative to, the script
    that builds it) for a version of this module. v4.1 is v4's data with its
    own spec (scripts/build_v41_spec.py)."""
    if version == "v4":
        return config.V4_SPEC_PATH, config.V4_MANIFEST_PATH, config.V4_DIR, "scripts/build_v4_bundle.py"
    if version == "v4.1":
        return config.V41_SPEC_PATH, config.V41_MANIFEST_PATH, config.V41_DIR, "scripts/build_v41_spec.py"
    if version == "v4.2":
        return config.V42_SPEC_PATH, config.V42_MANIFEST_PATH, config.V42_DIR, "scripts/build_v42_spec.py"
    if version in config.V5_FAMILY:
        base, _, spec = config.V5_FAMILY[version]
        builder = "research/notebooks/v5_build.py" + ("" if version == "v5" else f" --variant {version}")
        return base / spec, base / "MANIFEST.json", base, builder
    raise ValueError(f"{version!r} is not a version of service/pipeline/fusion.py")


def data_dir(version: str):
    """Where a version's class-balanced centroids and class means live: v4's
    directory for v4, v4.1 and v4.2, each v5 version's own."""
    return config.V5_FAMILY[version][0] if version in config.V5_FAMILY else config.V4_DIR


def load_answers(version: str) -> "ensemble.V31Bundle":
    """The bundle behind a version's answers: v3.1's for v4 and v4.1; for a
    v5 version, its own (the same code, its own files)."""
    if ANSWERS_FROM[version] == "v3.1":
        return ensemble.V31Bundle.load()
    base, answers, _ = config.V5_FAMILY[version]
    return ensemble.V31Bundle.load(spec_path=base / answers, members_dir=base / "members")


# ---- the math, pure ----

def class_balanced_stats(X: np.ndarray, y: np.ndarray, n_classes: int, block: int = 512) -> tuple[np.ndarray, np.ndarray]:
    """Per-gene mean and SD with every class weighted equally: each class
    carries 1/n_classes of the weight, split evenly over its cells. Classes
    with no cells take no weight."""
    counts = np.bincount(y, minlength=n_classes).astype(np.float64)
    present = counts > 0
    w = 1.0 / (present.sum() * counts[y])
    mu = np.empty(X.shape[1], np.float64)
    sd = np.empty(X.shape[1], np.float64)
    for start in range(0, X.shape[1], block):
        cols = X[:, start:start + block].astype(np.float64)
        m = w @ cols
        mu[start:start + block] = m
        sd[start:start + block] = np.sqrt(w @ (cols - m) ** 2)
    return mu.astype(np.float32), sd.astype(np.float32)


def class_means(X: np.ndarray, y: np.ndarray, n_classes: int, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """The z-scored (under mu, sd) mean profile of each class, class position order."""
    out = np.zeros((n_classes, X.shape[1]), np.float64)
    for k in range(n_classes):
        if (y == k).any():
            out[k] = ((X[y == k].astype(np.float64) - mu) / (sd + 1e-8)).mean(0)
    return out


def masked_pearson(values: np.ndarray, mask: np.ndarray, means: np.ndarray) -> np.ndarray:
    """(cells, classes) Pearson r between each cell and each class mean, over
    that cell's observed genes only. values carry 0 where unobserved. A cell
    with fewer than two observed genes, or no variance, gets r = 0."""
    W = (mask > 0).astype(np.float64)
    X = values.astype(np.float64) * W
    M = means.astype(np.float64)
    n = W.sum(1, keepdims=True)
    sx, sxx = X.sum(1, keepdims=True), (X * X).sum(1, keepdims=True)
    sm, smm, sxm = W @ M.T, W @ (M * M).T, X @ M.T
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxm - sx * sm / n
        var = (sxx - sx ** 2 / n) * (smm - sm ** 2 / n)
        r = cov / np.sqrt(var)
    r = np.where((n >= 2) & (var > 1e-12), r, 0.0)
    return np.nan_to_num(r, nan=0.0)


def first_symbol(name: str) -> str:
    """A protein row's gene symbol, as v4.2's protein means are keyed: its
    first listed gene, upper case."""
    return str(name).split(";")[0].strip().upper()


def protein_query(raw, genes) -> tuple[np.ndarray, np.ndarray]:
    """(values, mask), cells x genes: the upload over v4.2's protein means'
    genes, matched by first_symbol, on the log scale the service detects, a
    gene's rows merged by per-cell median, each gene z-scored over its observed
    values within the upload; unobserved entries 0 with mask 0."""
    from service.pipeline import alignment
    values, _ = alignment.detect_and_transform_value_scale(raw.values)
    index = {g: i for i, g in enumerate(genes)}
    x = np.full((len(raw.cell_ids), len(genes)), np.nan, np.float64)
    rows: dict[int, list[int]] = {}
    for r, name in enumerate(raw.gene_names):
        col = index.get(first_symbol(name))
        if col is not None:
            rows.setdefault(col, []).append(r)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # a gene with no observed value in this upload
        for col, rs in rows.items():
            x[:, col] = np.nanmedian(values[rs], axis=0) if len(rs) > 1 else values[rs[0]]
        z = (x - np.nanmean(x, axis=0)) / (np.nanstd(x, axis=0) + 1e-8)
    mask = np.isfinite(z)
    return np.where(mask, z, 0.0), mask.astype(np.float32)


def correlation_probabilities(r: np.ndarray, temperature: float) -> np.ndarray:
    logits = r / temperature
    logits = logits - logits.max(axis=1, keepdims=True)
    weights = np.exp(logits)
    return weights / weights.sum(axis=1, keepdims=True)


def fused_probabilities(encoder_probs: np.ndarray, correlation_probs: np.ndarray, weight: float) -> np.ndarray:
    return weight * encoder_probs + (1.0 - weight) * correlation_probs


def mixed_encoder_probabilities(smoothed_probs: np.ndarray, unsmoothed_probs: np.ndarray, smoothed_share: float) -> np.ndarray:
    return smoothed_share * smoothed_probs + (1.0 - smoothed_share) * unsmoothed_probs


def upload_agreement(r: np.ndarray, answer_probs: np.ndarray, counted: np.ndarray) -> float:
    """The share of counted cells whose top class under r is the answers' top
    class; 0 when no cell is counted."""
    counted = np.asarray(counted, dtype=bool)
    if not counted.any():
        return 0.0
    return float((r.argmax(axis=1)[counted] == answer_probs.argmax(axis=1)[counted]).mean())


# ---- the spec and the bundle ----

def validate_spec(spec: dict, class_names: list[str], require_evaluation: bool = True, version: str = "v4") -> None:
    problems = []
    try:
        if spec.get("version") != version:
            problems.append(f"not a {version} spec")
        if spec["class_order"] != class_names:
            problems.append("class_order is not the reference's class order")
        if spec["preprocessing"]["convention"] != "service" or spec["preprocessing"]["smoothing"] is not True:
            problems.append("v4 uses the service convention with smoothing (its answers are v3.1's)")
        if spec["answers"]["from"] != ANSWERS_FROM[version]:
            problems.append(f"{version}'s answers come from {ANSWERS_FROM[version]}")
        b = spec["best_guess"]
        if b["rule"] != "fusion" or spec["label_space"]["method"] != "none":
            problems.append("best-guess rule or label space is not one this module implements")
        if not 0 <= float(b["fusion_weight"]) <= 1:
            problems.append("fusion_weight must be within [0, 1]")
        if "gate_on_fusion_weight" in b and not 0 <= float(b["gate_on_fusion_weight"]) <= 1:
            problems.append("gate_on_fusion_weight must be within [0, 1]")
        if not float(b["correlation_temperature"]) > 0:
            problems.append("correlation_temperature must be positive")
        if not 0 <= float(b["smoothed_share"]) <= 1:
            problems.append("smoothed_share must be within [0, 1]")
        if not 0 <= float(b["agreement_threshold"]) <= 1:
            problems.append("agreement_threshold must be within [0, 1]")
        for name in spec["encoder"]["members"]:
            t = b["temperature"].get(name)
            if not (isinstance(t, (int, float)) and np.isfinite(t) and t > 0):
                problems.append(f"no positive temperature for {name}")
        if config.V31_COORDINATE_MEMBER not in spec["encoder"]["members"]:
            problems.append(f"the coordinate member {config.V31_COORDINATE_MEMBER} is not a member")
        if require_evaluation and spec["evaluation"]["status"] != "passed":
            problems.append(f"the evaluation has not passed ({TRACK[version]})")
    except (KeyError, TypeError, ValueError) as exc:
        problems.append(f"missing or malformed field: {exc!r}")
    if problems:
        raise ValueError(f"{version_files(version)[0]} is not a usable {version} spec: " + "; ".join(problems))


def _verify_manifest(version: str = "v4") -> None:
    """Every file the version's MANIFEST lists (v4.1's include v4's data
    files, as ../v4/...) must exist and match its sha256."""
    _, path, base, builder = version_files(version)
    if not path.exists():
        raise reference.PendingArtifactError(f"{path} does not exist. Build it with {builder}.")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for rel, entry in manifest["files"].items():
        file = base / rel
        if not file.exists():
            raise reference.PendingArtifactError(f"{file} does not exist (listed in {path}).")
        if hashlib.sha256(file.read_bytes()).hexdigest() != entry["sha256"]:
            raise reference.PendingArtifactError(f"{file} does not match its sha256 in {path}. Rebuild with {builder}.")


def build_components(answers_spec: dict, version: str = "v4") -> "pipeline.Components":
    """v3.1's label space, conformal sets and abstention, from v3.1's spec."""
    return dataclasses.replace(ensemble.build_components(answers_spec), version=version)


@dataclass(frozen=True)
class V4Bundle:
    answers: "ensemble.V31Bundle"  # every answer, coordinate and property (v3.1's; v5's own for v5)
    members: "tuple[ensemble.Member, ...]"  # the answers' encoders and latents; class-balanced centroids
    class_means: np.ndarray
    fusion_weight: float  # the encoder's weight where the correlation term is flat (and, in v4, where it is used)
    correlation_temperature: float
    smoothed_share: float
    agreement_threshold: float
    spec: dict
    components: "pipeline.Components"
    gate_on_fusion_weight: "float | None" = None  # the encoder's weight where the correlation term is used (v4.1)
    protein_means: "np.ndarray | None" = None  # v4.2: classes x proteins, z-scored; zero rows where not covered
    protein_genes: "tuple[str, ...] | None" = None
    protein_covered: "np.ndarray | None" = None  # v4.2: which classes take the protein correlation

    @property
    def pipeline_version(self) -> str:
        return self.spec["version"]

    @property
    def model_version(self) -> str:
        return MODEL_VERSION_LABELS[self.pipeline_version]

    @property
    def encoder_weight_where_used(self) -> float:
        return encoder_weight_where_used(self)

    @property
    def class_names(self) -> list[str]:
        return self.answers.class_names

    @property
    def hierarchy(self) -> dict:
        return self.answers.hierarchy

    @property
    def feature_genes(self) -> list[str]:
        return self.answers.feature_genes

    @classmethod
    def load(cls, require_evaluation: bool = True, version: str = "v4") -> "V4Bundle":
        spec_path = version_files(version)[0]
        _verify_manifest(version)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if require_evaluation and spec.get("evaluation", {}).get("status") != "passed":
            raise reference.PendingArtifactError(
                f"{spec_path}: {version}'s evaluation has not passed (research/todo.md, {TRACK[version]}).")
        answers = load_answers(version)
        validate_spec(spec, answers.class_names, require_evaluation, version)
        if spec["encoder"]["members"] != [m.name for m in answers.members]:
            raise ValueError(f"{spec_path}: its members are not its answers' ({ANSWERS_FROM[version]})")
        b = spec["best_guess"]
        data = data_dir(version)
        members = []
        for m in answers.members:
            seed = m.name.split("seed")[1].split(".")[0]
            members.append(dataclasses.replace(
                m, centroids=np.load(data / "members" / f"V2_seed{seed}_centroids_cb.npy").astype(np.float32),
                temperature=float(b["temperature"][m.name])))
        return cls(
            answers=answers, members=tuple(members),
            class_means=np.load(data / "class_means_cb.npy").astype(np.float32),
            fusion_weight=float(b["fusion_weight"]), correlation_temperature=float(b["correlation_temperature"]),
            smoothed_share=float(b["smoothed_share"]), agreement_threshold=float(b["agreement_threshold"]),
            spec=spec, components=build_components(answers.spec, version),
            gate_on_fusion_weight=float(b["gate_on_fusion_weight"]) if "gate_on_fusion_weight" in b else None,
            **load_protein_means(b, version_files(version)[2], answers.class_names),
        )


def load_protein_means(best_guess: dict, base, class_names: list[str]) -> dict:
    """v4.2's protein class means, checked against its spec; nothing for the
    versions without them."""
    entry = best_guess.get("protein_class_means")
    if entry is None:
        return {}
    saved = np.load(base / entry["file"])
    covered = saved["covered"].astype(bool)
    shape_ok = saved["means"].shape == (len(class_names), len(saved["proteins"]))
    if not shape_ok or [c for c, ok in zip(class_names, covered) if ok] != entry["classes_covered"]:
        raise ValueError(f"{base / entry['file']} does not match its spec's classes")
    return {"protein_means": saved["means"].astype(np.float32), "protein_genes": tuple(str(g) for g in saved["proteins"]),
            "protein_covered": covered}


# ---- the request ----

def encoder_weight_where_used(bundle) -> float:
    """The encoder's weight in uploads where the correlation term is used:
    the spec's gate_on_fusion_weight (v4.1), else fusion_weight (v4)."""
    w = getattr(bundle, "gate_on_fusion_weight", None)
    return bundle.fusion_weight if w is None else w


@dataclass(frozen=True)
class BestGuess:
    probabilities: np.ndarray  # (cells, classes)
    agreement: float
    correlation_used: bool


def best_guess_probabilities(bundle: V4Bundle, smoothed_embeddings: list[np.ndarray], values: np.ndarray,
                             mask: np.ndarray, answer_probs: np.ndarray, counted: np.ndarray,
                             protein: "tuple[np.ndarray, np.ndarray] | None" = None,
                             rna_upload: bool = False) -> BestGuess:
    """v4's best-guess probability. smoothed_embeddings are the members'
    embeddings of the smoothed query (v3.1's, shared with the answers);
    answer_probs is v3.1's probability over all classes, and counted marks
    the cells with at least the coverage floor's observed genes. v4.2's
    protein class means need the upload's protein query; an RNA upload
    (rna_upload) keeps the RNA class means for every class, as v4.1."""
    probs = lambda embeddings: ensemble.ensemble_probabilities([  # noqa: E731
        ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(embeddings, bundle.members)])
    on = probs(smoothed_embeddings)
    r = masked_pearson(values, mask, bundle.class_means)
    if getattr(bundle, "protein_means", None) is not None and not rna_upload:  # v4.2: protein means, covered classes
        if protein is None:
            raise ValueError("v4.2's best guess needs the upload's protein query (fusion.protein_query)")
        covered = bundle.protein_covered
        r[:, covered] = masked_pearson(protein[0], protein[1], bundle.protein_means)[:, covered]
    agreement = upload_agreement(r, answer_probs, counted)
    if agreement < bundle.agreement_threshold:
        flat = np.full_like(on, 1.0 / on.shape[1])
        return BestGuess(fused_probabilities(on, flat, bundle.fusion_weight), agreement, False)
    encoder_probs = on
    if bundle.smoothed_share < 1:
        unsmoothed = [m.encoder_handle.encode(values, mask) for m in bundle.members]
        encoder_probs = mixed_encoder_probabilities(on, probs(unsmoothed), bundle.smoothed_share)
    correlation = correlation_probabilities(r, bundle.correlation_temperature)
    return BestGuess(fused_probabilities(encoder_probs, correlation, encoder_weight_where_used(bundle)), agreement, True)


def project(bundle: V4Bundle, raw, restrict_to_supported_classes: bool, components: "pipeline.Components | None",
            modality: str = "prot") -> dict:
    smoothed, aligned, value_scale = pipeline._prepare_query(bundle.feature_genes, raw)
    rna_upload = modality == "rna"
    uses_protein = getattr(bundle, "protein_means", None) is not None and not rna_upload
    protein = protein_query(raw, bundle.protein_genes) if uses_protein else None
    return project_prepared(bundle, smoothed, aligned, value_scale, gene_ids.resolve_identifiers(raw.gene_names),
                            restrict_to_supported_classes, components or bundle.components, protein=protein,
                            rna_upload=rna_upload)


def project_prepared(bundle, smoothed_values, aligned, value_scale, gene_id_resolution,
                     restrict_to_supported_classes, components, protein=None, rna_upload: bool = False) -> dict:
    """v3.1's Stages 3-8 (ensemble.project_prepared), with v4's fused best guess."""
    answers = bundle.answers
    names = answers.class_names
    embeddings = [m.encoder_handle.encode(smoothed_values, aligned.mask) for m in answers.members]
    all_class_probs = ensemble.ensemble_probabilities([
        ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(embeddings, answers.members)
    ])
    space = components.label_space.estimate(None, names, restrict_to_supported_classes)
    probs = components.label_space.probabilities(all_class_probs, space)
    counted = aligned.per_cell_observed_genes >= int(bundle.spec["preprocessing"]["min_observed_genes"])
    guess = best_guess_probabilities(bundle, embeddings, aligned.values, aligned.mask, all_class_probs, counted,
                                     protein, rna_upload=rna_upload)
    guess_probs = components.label_space.probabilities(guess.probabilities, space)
    guess_position, guess_probability = ensemble.best_guess(guess_probs, space.positions)
    calibrated = components.calibrator.calibrate(probs, None, space, guess_positions=guess_position)
    ood_score = np.mean([
        search.faiss_max_cosine_to_reference(z, m.reference_latents) for z, m in zip(embeddings, answers.members)
    ], axis=0)
    verdict = components.abstention.score(
        max_similarity=ood_score, hidden_features=None,
        per_cell_observed_genes=aligned.per_cell_observed_genes,
        label_sets=calibrated.label_sets, calibration_indices=calibrated.calibration_indices,
    )
    anchor = answers.members[answers.coordinate_member]
    z_anchor = embeddings[answers.coordinate_member]
    property_result = transfer.transfer_properties(z_anchor, anchor.reference_latents, answers.property_names, answers.property_values)
    coords = answers.pca.project(z_anchor)

    cells = []
    for i, cell_id in enumerate(aligned.cell_ids):
        reason = verdict.reason[i]
        set_names = [names[c] for c in calibrated.label_sets[i]]
        resolved = None
        if reason in (abstention.AbstainReason.NONE, abstention.AbstainReason.AMBIGUOUS):
            resolved = ensemble.resolve(set_names, answers.hierarchy)
            reason = abstention.AbstainReason.NONE if resolved else abstention.AbstainReason.AMBIGUOUS
        entry = {"cell_id": cell_id, "coordinates": [float(x) for x in coords[i]],
                 "observed_genes": int(aligned.per_cell_observed_genes[i]), "reference_similarity": float(ood_score[i])}
        if resolved:
            label, level = resolved
            entry.update(label=label, label_level=level, label_set=set_names,
                         confidence=float(probs[i, calibrated.label_sets[i]].sum()), abstained=False)
        else:
            entry.update(label=None, label_level=None, label_set=[], confidence=None, abstained=True,
                         abstain_reason=reason.value, abstain_category=abstention.CATEGORY_BY_REASON[reason].value)
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
        "pipeline_version": bundle.pipeline_version,
        "n_cells": len(aligned.cell_ids),
        "n_features_matched": aligned.n_features_matched,
        "n_features_unmatched": aligned.n_features_unmatched,
        "value_scale": {"detected": value_scale.detected, "transformed": value_scale.transformed},
        "label_space": {"restricted_to_supported_classes": restrict_to_supported_classes,
                        "candidate_classes": [names[p] for p in positions]},
        "supported_classes": {"names": [names[p] for p in positions], "method": space.method, "support": None,
                              "renormalised": space.positions is not None and components.label_space.renormalise},
        "calibration": components.calibrator.describe(calibrated),
        "best_guess_rule": {"rule": "fusion", "agreement": round(guess.agreement, 4),
                            "agreement_threshold": bundle.agreement_threshold,
                            "correlation_term": "used" if guess.correlation_used else "flat"},
        "gene_id_resolution": {
            "matched": gene_id_resolution.matched, "unmapped": gene_id_resolution.unmapped,
            "ambiguous": gene_id_resolution.ambiguous,
            "unmapped_identifiers": gene_id_resolution.unmapped_identifiers,
            "ambiguous_identifiers": gene_id_resolution.ambiguous_identifiers,
        },
        "reference_abstain_threshold": float(answers.spec["ood"]["threshold"]),
        "cells": cells,
    }
