#!/usr/bin/env python3
"""Generate web/data/atlas_manifest.json from the repository's data.

Every number emitted here is computed from data present in this repository:
the metadata CSVs, the model's evidence tables, and the committed evaluation
and benchmark tables. Metrics with no source data yet (per-class transfer
accuracy: a per-*dataset* version exists, see `transfer_accuracy`'s note
below, but nothing decomposes it per class) are emitted as explicit pending
records so the web layer renders them as pending instead of inventing a value.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ATLAS_DIR = REPO_ROOT / "web" / "data"
OUTPUT_PATH = ATLAS_DIR / "atlas_manifest.json"
SERVICE_MODEL_DIR = REPO_ROOT / "service" / "model"
V3_TABLES_DIR = SERVICE_MODEL_DIR / "evidence" / "v3_tables"
V31_TABLES_DIR = SERVICE_MODEL_DIR / "evidence" / "v3_1_tables"
NB1_DIR = REPO_ROOT / "research" / "notebook-outputs" / "nb1"
NB1D_DIR = REPO_ROOT / "research" / "notebook-outputs" / "nb1d"
NB2_SUMMARY = REPO_ROOT / "research" / "notebook-outputs" / "nb2" / "nb2_summary.json"
FLAGS_RECORD = REPO_ROOT / "research" / "benchmark" / "v31_service_flags.json"
V41_PHASE3 = REPO_ROOT / "research" / "notebook-outputs" / "v41_phase3" / "summary.json"
V41_DEV_DIR = REPO_ROOT / "research" / "benchmark" / "v41_development"
V42_DEV_DIR = REPO_ROOT / "research" / "benchmark" / "v42_development"
CORRECTED_DIR = REPO_ROOT / "research" / "benchmark" / "baselines_corrected"
KHOURY_POSTHOC_DIR = REPO_ROOT / "research" / "benchmark" / "khoury2026_posthoc"
KHOURY_V41_DIR = REPO_ROOT / "research" / "benchmark" / "khoury2026_posthoc_v41_check"
KHOURY_V42_DIR = REPO_ROOT / "research" / "benchmark" / "khoury2026_posthoc_v42_check"
ORGANS_DIR = ATLAS_DIR / "organs"

# decisive_summary.json's winner_config.enc -> a readable label for the manifest.
# Keep this in sync with service/pipeline/encoder.py's _ENCODER_FAMILIES table;
# an unrecognised value there raises loudly for the same reason it does here.
ENCODER_FAMILY_LABELS = {"module": "module pooling"}

SCHEMA_VERSION = "1.0"
ATLAS_VERSION = "0.6.0"
PREVIOUS_ATLAS_VERSION = "0.5.0"  # v4.2's release, now previous_release
V41_FIRST_ATLAS_VERSION = "0.4.0"  # v4.1's first release; 0.6.0 serves it again
V31_ATLAS_VERSION = "0.3.0"  # v3.1's release; its builders stay, with no release card since 0.5.0
EARLIER_ATLAS_VERSION = "0.2.0"  # v3's release, now earlier_release


def read_metadata(path: Path) -> list[dict]:
    """Read a metadata CSV. Uses csv.DictReader so quoted class names
    containing commas (class_idx 2, 3, 14) parse correctly."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


PC_COLUMNS = ("PC1", "PC2", "PC3")


def class_stats(rows: list[dict]) -> dict:
    """-> {class_idx: {"name": str, "count": int, "centroid": (x, y, z)}}"""
    groups = defaultdict(list)
    for row in rows:
        groups[int(row["class_idx"])].append(row)
    return {
        idx: {
            "name": group[0]["class_name"],
            "count": len(group),
            "centroid": tuple(
                sum(float(r[pc]) for r in group) / len(group) for pc in PC_COLUMNS
            ),
        }
        for idx, group in groups.items()
    }


def cosine(a, b):
    """Cosine similarity of two 3-vectors. None if either has zero norm."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return None
    return dot / (norm_a * norm_b)


def pending(phase: str, note: str) -> dict:
    return {"value": None, "status": "pending", "phase": phase, "note": note}


def measured(value, basis: str) -> dict:
    return {"value": value, "status": "measured", "basis": basis}


def build_deployed_architecture_facts(decisive_summary: dict, feature_space_detail_rows: list[dict]) -> dict:
    """Architecture facts about the currently *deployed* v3 reference,
    folded into `model` — sourced from the decisive masking test's own
    record (architecture unchanged since that test settled it) and the
    actual feature-space union, not a rerun of provenance.json's own
    precomputed totals."""
    winner_config = decisive_summary["winner_config"]
    encoder_family = ENCODER_FAMILY_LABELS.get(winner_config["enc"])
    if encoder_family is None:
        raise ValueError(
            f"Unrecognised encoder family {winner_config['enc']!r} in decisive_summary.json; "
            "add it to ENCODER_FAMILY_LABELS (and service/pipeline/encoder.py's _ENCODER_FAMILIES)."
        )

    source_columns = [
        c for c in feature_space_detail_rows[0] if c not in ("gene", "n_sources", "in_old_reference")
    ]
    detected_by_source = {
        source: sum(1 for row in feature_space_detail_rows if row[source] == "True")
        for source in source_columns
    }
    retained_from_old = sum(1 for row in feature_space_detail_rows if row["in_old_reference"] == "True")

    return {
        "feature_space_size": len(feature_space_detail_rows),
        "previous_feature_space_size": retained_from_old,
        "detected_by_source": detected_by_source,
        "encoder_family": encoder_family,
        "mask_sampling": winner_config["sampler"],
    }


def build_model_seeds(reference_seeds_rows: list[dict], provenance: dict) -> dict:
    """model.seeds: a seed COUNT (rendered with 0 decimal places,
    web/js/panels.js:buildModelCard), not an accuracy — the accuracy and its CI
    go in `basis`, which is exactly what the UI surfaces alongside it."""
    n_seeds = len(reference_seeds_rows)
    mean_bal_acc = provenance["reference_seed_mean_bal_acc"]
    ci_low, ci_high = provenance["reference_seed_ci95"]
    return measured(
        n_seeds,
        f"balanced accuracy {mean_bal_acc:.4f}, 95% CI [{ci_low:.4f}, {ci_high:.4f}]",
    )


def read_latent_centroid_cosine(rows: list[dict], space: str = "") -> dict[int, dict]:
    """A latent_centroid_cosine.csv (service/model/evidence/v3_tables/ or
    v3_1_tables/) -> {class_idx: metric}. Measured only for the 2 classes with
    cross-modal coverage; the pending rows use an empty string for
    latent_centroid_cosine, never "0.0". `space` names whose latent it is."""
    out = {}
    for row in rows:
        idx = int(row["class_idx"])
        if row["status"] == "measured" and row["latent_centroid_cosine"] != "":
            n_prot = row["n_prot_cells"]
            out[idx] = measured(
                round(float(row["latent_centroid_cosine"]), 6),
                f"128-d latent centroid cosine{space}, {n_prot} protein cells",
            )
        else:
            out[idx] = pending("N/A", row["reason"])
    return out


def read_modality_probe_accuracy(modality_probe: dict) -> dict:
    """A single global metric (5-fold CV over all cross-modal cells), not
    per-class — reused as-is for every cross-modal row. The "global metric,
    not per-class" wording is load-bearing: this schema slot is per-row, and
    without it a reader would take the repeated value for a genuine
    per-class measurement."""
    pct = modality_probe["modality_probe_balanced_accuracy_pct"]
    return measured(round(pct / 100, 6), f"{modality_probe['basis']}; global metric, not per-class")


def build_first_release_facts(legacy_provenance: dict) -> dict:
    """The superseded model's own numbers, kept as the documented prior
    baseline rather than erased now that the architecture has moved on
    (docs/service/context-brief.md, "For the model card"). CrossModalNet
    was jointly trained on RNA and proteomics together and had implicitly
    seen SCoPE2 during training — part of why these zero-shot numbers read
    higher than the honestly separated v3 architecture's own zero-shot
    results do. Both are real; they answer different questions, and were
    measured under different methodologies (this is a raw/smoothed AUC
    pair from the old joint-training evaluation, not a single number
    directly comparable to v3's own per-dataset zero-shot table in
    service/model/evidence/v3_tables/zero_shot_all_datasets.csv)."""
    return {
        "model_name": "CrossModalNet",
        "n_shared_genes": legacy_provenance["n_shared_genes"],
        "zero_shot_auc_raw": measured(legacy_provenance["zero_shot_auc_raw"], "jointly trained, had seen SCoPE2"),
        "zero_shot_auc_smoothed": measured(legacy_provenance["zero_shot_auc_smoothed"], "jointly trained, had seen SCoPE2, query-time smoothing"),
        "shipped_properties": legacy_provenance["shipped_properties"],
        "note": (
            "CrossModalNet was jointly trained on RNA and proteomics together, so it had "
            "implicitly seen SCoPE2 during training, part of why these numbers read higher "
            "than an honestly separated architecture's would. Kept here as the documented "
            "first baseline, not erased, now that RNA-only references (v3, then v3.1) have "
            "superseded it."
        ),
    }


NB2_BASIS = "NB2 evaluation, before the two conservative flags; research/notebook-outputs/nb2/nb2_summary.json"
SERVED_BASIS = "served settings (both service flags on), development data; research/benchmark/v31_service_flags.json"
NB2_MEASURES = (  # (key, measure, nb2_summary eval_candidate field)
    ("correct_when_committed", "Correct when committed, at the stated level", "correct_when_committed"),
    ("abstention", "Abstention", "abstain_rate"),
    ("coverage", "Conformal coverage (target 90%)", "coverage"),
    ("class_level", "Answered at class level", "fine_rate"),
    ("group_level", "Answered at group level", "group_rate"),
    ("lineage_level", "Answered at lineage level", "lineage_rate"),
)


def _exact_share(share_pct: float, n: int) -> float:
    """A share recorded to two decimals, back to its cell count, as a fraction."""
    return round(round(share_pct * n / 100) / n, 6)


def build_v31_evaluation(nb2_summary: dict, flags_record: dict) -> dict:
    """v3.1's numbers, each labelled with what it describes. NB2's evaluation
    suite measured NB2's rule, before the two service flags; the development
    datasets are measured as served (flags on)."""
    ev = nb2_summary["eval_candidate"]
    suite = {"title": "NB2's evaluation suite: simulated uploads of held-out RNA cells", "rows": [
        {"key": key, "measure": measure, "value": measured(round(ev[field] / 100, 6), NB2_BASIS)}
        for key, measure, field in NB2_MEASURES]}
    served = []
    for dataset, run in (("SCoPE2", "SCoPE2"), ("PBMC240", "PBMC240"), ("Fulcher 2026", "Fulcher 2026")):
        e = flags_record["runs"][run]["served"]
        if "correct_at_stated_level" in e:
            correct, label = e["correct_at_stated_level"]["correct_when_committed"] / 100, "correct when committed, at the stated level"
        elif "weak_lineage" in e:
            w = e["weak_lineage"]
            correct, label = w["lymphoid_correct"] / w["lymphoid_n"], "lymphoid cells given their lineage"
        else:
            correct, label = e["correct_when_committed_pct"] / 100, "correct when committed, at the stated level"
        served.append({
            "dataset": dataset,
            "committed": measured(_exact_share(e["share_pct"]["committed"], e["cells"]), SERVED_BASIS),
            "correct": measured(round(correct, 6), SERVED_BASIS),
            "correct_label": label,
        })
    return {"suite": suite, "served": served}


V41_SUITE_BASIS = ("v4.1's pre-registered evaluation: 240 simulated uploads of te_eval cells, the suite's fourth "
                   "use; research/notebook-outputs/v41_phase3/summary.json")
V41_SUITE_MEASURES = (  # (key, measure, path into summary.json's result["v4.1"])
    ("correct_when_committed", "Correct when committed, at the stated level", ("correct_when_committed",)),
    ("abstention", "Abstention", ("levels", "abstain")),
    ("coverage", "Conformal coverage (target 90%)", ("coverage",)),
    ("class_level", "Answered at class level", ("levels", "class")),
    ("group_level", "Answered at group level", ("levels", "group")),
    ("lineage_level", "Answered at lineage level", ("levels", "lineage")),
    ("best_guess", "Best guess, balanced accuracy per upload", ("best_guess_per_upload_balanced",)),
)
V41_SERVED_BASIS = "served settings, development data; research/benchmark/v41_development/confident.csv"


def _field(record: dict, path: tuple) -> float:
    for key in path:
        record = record[key]
    return record


def build_v41_evaluation(phase3: dict, confident_rows: list[dict], fulcher_rows: list[dict],
                         khoury_check: dict) -> dict:
    """v4.1's numbers: its pre-registered suite, the development datasets as
    served, and the best guess's recall per type on the two datasets with
    fine labels. Fulcher chose v4.1's one tuned weight and Khoury is
    post-hoc, and each basis says so."""
    result = phase3["result"]["v4.1"]
    suite = {"title": "Simulated uploads of held-out RNA cells (v4.1's pre-registered evaluation)", "rows": [
        {"key": key, "measure": measure, "value": measured(_fraction(_field(result, path)), V41_SUITE_BASIS)}
        for key, measure, path in V41_SUITE_MEASURES]}
    served = []
    for dataset in ("SCoPE2", "PBMC240", "Fulcher 2026"):
        r = next(x for x in confident_rows if x["model"] == "v41" and x["dataset"] == dataset)
        served.append({
            "dataset": dataset,
            "committed": measured(_fraction(r["committed_pct"]), V41_SERVED_BASIS),
            "correct": measured(_fraction(r["correct_when_committed_pct"]), V41_SERVED_BASIS),
            "correct_label": ("labelled cells whose answer names their lineage" if dataset == "PBMC240"
                              else "correct when committed, at the stated level"),
        })
    fulcher = next(r for r in fulcher_rows if r["tool"] == "v4.1 (served)")
    khoury = khoury_check["scores"]["v4.1"]
    recall = [{"dataset": "Fulcher 2026", "type": key[len("recall_"):-len("_pct")],
               "value": measured(_fraction(fulcher[key]), "best guess as served, in-sample for v4.1; "
                                 "research/benchmark/v41_development/fulcher2026.csv")}
              for key in fulcher if key.startswith("recall_")]
    recall += [{"dataset": "Khoury 2026", "type": key[len("recall_"):-len("_pct")],
                "value": measured(_fraction(khoury[key]), "best guess, post-hoc; "
                                  "research/benchmark/khoury2026_posthoc_v41_check/summary.json")}
               for key in khoury if key.startswith("recall_")]
    return {"suite": suite, "served": served, "recall": recall}


V42_SUITE_BASIS = ("v4.1's pre-registered evaluation (240 simulated uploads of te_eval cells, the suite's fourth "
                   "use; research/notebook-outputs/v41_phase3/summary.json). v4.2 answers an RNA upload exactly as "
                   "v4.1 (service/tests/test_v42.py), so these are its numbers too")
V42_SERVED_BASIS = "served settings, development data; research/benchmark/v42_development/confident.csv"
KHOURY_V42_BASIS = ("best guess as served, post-hoc, scored once after release on the owner's decision (2026-10-17); "
                    "research/benchmark/khoury2026_posthoc_v42_check/summary.json")


def _served(confident_rows: list[dict], model_key: str, basis: str) -> list[dict]:
    served = []
    for dataset in ("SCoPE2", "PBMC240", "Fulcher 2026"):
        r = next(x for x in confident_rows if x["model"] == model_key and x["dataset"] == dataset)
        served.append({
            "dataset": dataset,
            "committed": measured(_fraction(r["committed_pct"]), basis),
            "correct": measured(_fraction(r["correct_when_committed_pct"]), basis),
            "correct_label": ("labelled cells whose answer names their lineage" if dataset == "PBMC240"
                              else "correct when committed, at the stated level"),
        })
    return served


def build_v42_evaluation(phase3: dict, confident_rows: list[dict], fulcher_rows: list[dict],
                         khoury_current: dict) -> dict:
    """v4.2's numbers. It answers an RNA upload exactly as v4.1, so its suite
    is v4.1's and the basis says why; the development datasets are measured
    as served. Its Khoury 2026 recall is post-hoc, from the one check after
    its release (khoury_current: that check's summary)."""
    result = phase3["result"]["v4.1"]
    suite = {"title": "Simulated uploads of held-out RNA cells (v4.1's pre-registered evaluation; v4.2 answers "
                      "RNA uploads exactly as v4.1)", "rows": [
        {"key": key, "measure": measure, "value": measured(_fraction(_field(result, path)), V42_SUITE_BASIS)}
        for key, measure, path in V41_SUITE_MEASURES]}
    fulcher = next(r for r in fulcher_rows if r["tool"] == "v4.2 (served)")
    recall = [{"dataset": "Fulcher 2026", "type": key[len("recall_"):-len("_pct")],
               "value": measured(_fraction(fulcher[key]), "best guess as served, in-sample (v4.1's weight was "
                                 "chosen and v4.2 checked here); research/benchmark/v42_development/fulcher2026.csv")}
              for key in fulcher if key.startswith("recall_")]
    khoury = khoury_current["scores"]["v4.2"]
    recall += [{"dataset": "Khoury 2026", "type": key[len("recall_"):-len("_pct")],
                "value": measured(_fraction(khoury[key]), KHOURY_V42_BASIS)}
               for key in khoury if key.startswith("recall_")]
    return {"suite": suite, "served": _served(confident_rows, "v42", V42_SERVED_BASIS), "recall": recall}


def build_v42_model(n_members: int, deployed_architecture: dict, evaluation: dict) -> dict:
    """The current release (0.5.0). v4.2 is v4.1 with protein class means in
    the best guess's correlation term, for protein uploads; its encoders,
    coordinates and latent cosines are v3.1's, as v4.1's are. The mask
    sampling the members were trained with (T1 NB1b) is not recorded in this
    repository, so it reads Pending."""
    return {
        "name": "VivOME v4.2",
        "latent_dim": 128,
        "training_regime": "supervised",
        "seeds": measured(n_members, "v3.1's ensemble members: V2 seeds 0 to 4 (T1 NB1b), probabilities averaged"),
        "notes": (
            "v4.1's answers and best guess, with one change for protein uploads: each cell's correlation is "
            "taken with protein class means from sorted immune cells (Rieckmann et al. 2017, PXD004352) for the "
            "reference classes they cover, and with the reference's RNA class means for the rest. Each answer's "
            "set holds the best guess, so a protein cell's answer can change with it. An RNA upload is answered "
            "exactly as by v4.1. The five encoders are trained only on labelled blood "
            "scRNA-seq and no protein labels are used: proteomics queries are projected at inference and never "
            "used to retrain anything. v4.1's one tuned weight was chosen on Fulcher 2026. Coordinates shown in "
            "the viewer are a 3-component PCA projection of the coordinate member's (V2 seed 4) 128-d latent "
            "space, as in v3.1; the latent coordinates themselves are not distributed with this build."
        ),
        **deployed_architecture,
        "mask_sampling": None,
        "evaluation": evaluation,
    }


def build_v42_release(n_members: int, deployed_architecture: dict, evaluation: dict) -> dict:
    """v4.2, the previous release (0.5.0), with its own numbers."""
    return {
        "model_name": "VivOME v4.2",
        "atlas_version": PREVIOUS_ATLAS_VERSION,
        "seeds": measured(n_members, "v3.1's ensemble members: V2 seeds 0 to 4 (T1 NB1b), probabilities averaged"),
        **deployed_architecture,
        "mask_sampling": None,
        "evaluation": evaluation,
        "note": (
            "v4.1 with protein class means from sorted immune cells (Rieckmann et al. 2017, PXD004352) in the best "
            "guess's correlation term, for protein uploads. It gained on Fulcher 2026, where it was checked, and "
            "fell short of v4.1 on Khoury 2026 (post-hoc), so release 0.6.0 serves v4.1 again. It stays selectable "
            "in the service (VIVOME_PIPELINE_VERSION=v4.2)."
        ),
    }


def build_v41_release(n_members: int, deployed_architecture: dict, evaluation: dict) -> dict:
    """v4.1's release card (0.4.0), with its own numbers. Unused while v4.1 is
    the current release again (0.6.0); kept for when it is not."""
    return {
        "model_name": "VivOME v4.1",
        "atlas_version": V41_FIRST_ATLAS_VERSION,
        "seeds": measured(n_members, "v3.1's ensemble members: V2 seeds 0 to 4 (T1 NB1b), probabilities averaged"),
        **deployed_architecture,
        "mask_sampling": None,
        "evaluation": evaluation,
        "note": (
            "v3.1's answers with a fused best guess: the encoders' probability joined with each cell's "
            "correlation to the reference's RNA class means, where that correlation carries signal. Its one "
            "tuned weight was chosen on Fulcher 2026. v4.2 keeps all of it and adds protein class means for "
            "protein uploads. It stays selectable in the service (VIVOME_PIPELINE_VERSION=v4.1)."
        ),
    }


def build_v41_model(n_members: int, deployed_architecture: dict, evaluation: dict) -> dict:
    """The current release: v4.1, first released in 0.4.0 and served again from
    0.6.0. Its answers are v3.1's, from the same
    five members, so the architecture facts, the atlas coordinates and the
    cell types' latent cosines are v3.1's; the best guess is v4.1's own. The
    mask sampling the members were trained with (T1 NB1b) is not recorded in
    this repository, so it reads Pending."""
    return {
        "name": "VivOME v4.1",
        "latent_dim": 128,
        "training_regime": "supervised",
        "seeds": measured(n_members, "v3.1's ensemble members: V2 seeds 0 to 4 (T1 NB1b), probabilities averaged"),
        "notes": (
            "v3.1's answers, from five encoders trained only on labelled blood scRNA-seq, with a better "
            "best guess: the encoders' probability joined with each cell's correlation to the reference's "
            "class means, where that correlation carries signal. Its one tuned weight was chosen on "
            "Fulcher 2026, and no protein labels are used: proteomics queries are projected at inference "
            "and never used to retrain anything. Coordinates shown in the viewer are a 3-component PCA "
            "projection of the coordinate member's (V2 seed 4) 128-d latent space, as in v3.1; the latent "
            "coordinates themselves are not distributed with this build."
        ),
        **deployed_architecture,
        "mask_sampling": None,
        "evaluation": evaluation,
    }


def build_v31_release(n_members: int, deployed_architecture: dict, evaluation: dict) -> dict:
    """v3.1, the previous release (0.3.0): the answers v4.1 keeps, with its own
    best guess and its own numbers. Its mask sampling reads Pending, as v4.1's."""
    return {
        "model_name": "VivOME v3.1",
        "atlas_version": V31_ATLAS_VERSION,
        "seeds": measured(n_members, "ensemble members: V2 seeds 0 to 4 (T1 NB1b), probabilities averaged"),
        **deployed_architecture,
        "mask_sampling": None,
        "evaluation": evaluation,
        "note": (
            "Five encoders trained only on labelled blood scRNA-seq answer together, at class, group or "
            "lineage level, or abstain; no protein labels are used. v4.1 keeps these answers and changes "
            "the best guess. It stays selectable in the service (VIVOME_PIPELINE_VERSION=v3.1)."
        ),
    }


def build_v3_release(model_seeds: dict, deployed_architecture: dict,
                     latent_rows: list[dict], modality_probe: dict) -> dict:
    """v3, an earlier release, with its own measurements kept as measured:
    the seeds behind it and its cross-modal evidence (v3_tables/)."""
    latent = {row["class_name"]: measured(round(float(row["latent_centroid_cosine"]), 6),
                                          f"v3 128-d latent centroid cosine, {row['n_prot_cells']} protein cells")
              for row in latent_rows if row["status"] == "measured" and row["latent_centroid_cosine"] != ""}
    return {
        "model_name": "VivOME v3 reference",
        "atlas_version": EARLIER_ATLAS_VERSION,
        "seeds": model_seeds,
        **deployed_architecture,
        "latent_centroid_cosine": latent,
        "modality_probe_accuracy": read_modality_probe_accuracy(modality_probe),
        "note": (
            "The single-encoder release before v3.1: a frozen, RNA-only reference. It stays "
            "selectable in the service (VIVOME_PIPELINE_VERSION=v3), and its model card below "
            "is kept as it was measured."
        ),
    }


# ---- The benchmark (benchmark.html) ----
# Every method scored under one protocol, the baselines with the corrections
# in research/benchmark/baseline-corrections.md. Signed off by the owner for
# release 0.4.0 (2026-10-15); the current model's rows moved to v4.2 for
# 0.5.0 at the owner's request (2026-10-16). A score is each method's one answer per cell
# (VivOME's best guess), over seeds where a method has several; the
# comparison is the current model minus each run, by paired bootstrap.

TOOL_NAMES = {
    "correlation": "Correlation to class mean", "pca": "PCA, no correction", "harmony": "Harmony",
    "scanvi": "scANVI", "maxfuse": "MaxFuse", "scglue": "scGLUE", "seurat": "Seurat CCA",
}
# Khoury's post-hoc tables name their arms (family, rule) their own way.
KHOURY_ARMS = {
    ("correlation", "correlation"): ("correlation", "correlation to class mean"),
    ("pca", "shared_knn"): ("pca", "shared kNN"),
    ("harmony", "shared_knn"): ("harmony", "shared kNN"),
    ("scANVI_corrected", "native"): ("scanvi", "scANVI classifier"),
    ("scANVI_corrected", "shared_knn"): ("scanvi", "shared kNN"),
    ("maxfuse", "shared_knn"): ("maxfuse", "shared kNN"),
    ("maxfuse_matching", "matching"): ("maxfuse", "MaxFuse matching"),
    ("scglue", "shared_knn"): ("scglue", "shared kNN"),
    ("seurat", "native"): ("seurat", "Seurat native transfer"),
}
CURRENT = "VivOME v4.1"
CURRENT_SHORT, CURRENT_TOOL = "v4.1", "v4.1 (served)"
PREVIOUS, PREVIOUS_SHORT, PREVIOUS_TOOL = "VivOME v4.2", "v4.2", "v4.2 (served)"
OUR_RULE = "best guess, as served"
PAIRED_BASIS = "current model minus this run; paired bootstrap, 2,000 resamples stratified by true type, seed 0, 95% CI"


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _turned(text: str) -> float:
    """A difference from the other side; a zero stays 0.0, not -0.0."""
    return 0.0 - float(text)


def _favours(text: str) -> str:
    """A bootstrap table's verdict, from the current model's side."""
    return "current" if text == CURRENT_SHORT else "neither" if text == "neither" else "other"


def _score(mean_pct: float, basis: str, sd=None, low=None, high=None, runs: int = 1) -> dict:
    record = measured(_fraction(mean_pct), basis)
    if runs > 1:
        record.update(sd=_fraction(sd), min=_fraction(low), max=_fraction(high))
    return record


def _versus(pairs: list[tuple]) -> dict | None:
    """pairs: (difference, CI low, CI high, favours), in points, one per run."""
    if not pairs:
        return None
    diffs = [p[0] for p in pairs]
    difference = measured(_fraction(sum(diffs) / len(diffs)), PAIRED_BASIS)
    if len(pairs) == 1:
        difference.update(ci_low=_fraction(pairs[0][1]), ci_high=_fraction(pairs[0][2]))
    else:
        difference.update(min=_fraction(min(diffs)), max=_fraction(max(diffs)))
    return {"pairings": len(pairs), "favour_current": sum(p[3] == "current" for p in pairs),
            "favour_other": sum(p[3] == "other" for p in pairs), "neither": sum(p[3] == "neither" for p in pairs),
            "difference": difference}


def _summary_arms(rows: list[dict], metric: str, regime: str | None = None):
    """(tool, rule, mean, sd, min, max, runs) from a *_summary.csv."""
    for r in rows:
        if r["metric"] == metric and r["tool"] in TOOL_NAMES and (regime is None or r["regime"] == regime):
            runs = int(r["count"])
            yield (r["tool"], r["rule"], float(r["mean"]), float(r["std"]) if runs > 1 else None,
                   float(r["min"]), float(r["max"]), runs)


def _per_seed_arms(rows: list[dict], metric: str, regime: str):
    """The same, aggregated from a per-seed table; SD over seeds as in the summaries."""
    values = defaultdict(list)
    for r in rows:
        if r["tool"] in TOOL_NAMES and r["regime"] == regime:
            values[(r["tool"], r["rule"])].append(float(r[metric]))
    for (tool, rule), v in values.items():
        yield tool, rule, sum(v) / len(v), statistics.stdev(v) if len(v) > 1 else None, min(v), max(v), len(v)


def _rows(ours: list[tuple], arms, pairs: dict, ours_basis: str, arms_basis: str) -> list[dict]:
    """ours: (name, score in points or a pending record, pairs); arms as
    _summary_arms yields. Ours first, then every other arm by score."""
    rows = [{"method": f"{name} (ours)", "rule": OUR_RULE, "ours": True, "runs": 1,
             "score": value if isinstance(value, dict) else _score(value, ours_basis), "vs_current": _versus(p)}
            for name, value, p in ours]
    others = [{"method": TOOL_NAMES[tool], "rule": rule, "ours": False, "runs": runs,
               "score": _score(mean, arms_basis, sd, low, high, runs), "vs_current": _versus(pairs.get((tool, rule), []))}
              for tool, rule, mean, sd, low, high, runs in arms]
    return rows + sorted(others, key=lambda r: -r["score"]["value"])


def _dataset(key: str, name: str, measure: str, types: int | None, role: str, rows: list[dict]) -> dict:
    return {"key": key, "name": name, "measure": measure,
            "chance": measured(round(1 / types, 6), f"one of {types} types at random") if types else None,
            "role": role, "rows": rows}


def build_benchmark(t: dict) -> dict:
    """t: the committed tables, by name (read in main). The current model is
    v4.1, with v4.2, the previous release, beside it. The tables comparing the
    two were written as v4.2 minus v4.1, so they are turned round here.
    Khoury 2026 is post-hoc for every method."""
    def dev_pairs(dataset):
        out = defaultdict(list)
        for r in t["paired_current"]:
            if r["dataset"] == dataset:
                out[(r["baseline"], r["baseline_rule"])].append(
                    (float(r["point_estimate_pct"]), float(r["ci_lo"]), float(r["ci_hi"]), _favours(r["favours"])))
        return out

    def vs_previous(dataset):
        # previous minus current, turned round: current minus previous, its interval negated and swapped.
        return [(_turned(r["point_estimate_pct"]), _turned(r["ci_hi"]), _turned(r["ci_lo"]), _favours(r["favours"]))
                for r in t["paired_previous_vs_current"] if r["dataset"] == dataset]

    def ours(table, metric, pairs_name, regime=None):
        by_tool = {r["tool"]: r for r in table if regime is None or r["regime"] == regime}
        return [(CURRENT, float(by_tool[CURRENT_TOOL][metric]), []),
                (PREVIOUS, float(by_tool[PREVIOUS_TOOL][metric]), vs_previous(pairs_name))]

    dev_basis = "development data, as served; research/benchmark/v42_development/ (both models)"
    corrected_basis = "corrected baselines; research/benchmark/baselines_corrected/"

    # Khoury 2026, post-hoc.
    k_current = t["khoury_current"]["scores"][CURRENT_SHORT]
    k_previous_score = t["khoury_previous"]["scores"][PREVIOUS_SHORT]
    k_pairs = defaultdict(list)
    for r in t["khoury_current_pairs"]:
        family = r["comparison"].split(" vs ", 1)[1]
        arm = KHOURY_ARMS.get((family, r["rule_b"]))
        if arm:
            k_pairs[arm].append((float(r["diff_bal_acc_pct"]), float(r["ci_lo"]), float(r["ci_hi"]),
                                 _favours(r["favours"])))
    # The previous model's check holds previous minus current; turned round here.
    k_previous = [(_turned(r["diff_bal_acc_pct"]), _turned(r["ci_hi"]), _turned(r["ci_lo"]), _favours(r["favours"]))
                  for r in t["khoury_previous_pairs"] if r["comparison"] == f"{PREVIOUS_SHORT} vs {CURRENT_SHORT}"]
    k_arms = []
    for r in t["khoury_family"]:
        arm = KHOURY_ARMS.get((r["family"], r["rule"]))
        if arm and r["metric"] == "balanced_accuracy_pct":
            runs = int(r["count"])
            k_arms.append((*arm, float(r["mean"]), float(r["std"]) if runs > 1 else None,
                           float(r["min"]), float(r["max"]), runs))
    k_types = sum(1 for key in k_current if key.startswith("recall_"))
    khoury = _dataset(
        "khoury2026", "Khoury 2026", f"Balanced accuracy over {k_types} types",
        k_types,
        "Held out from development: no method was developed or tuned on it. Post-hoc for every method, "
        "since its labels were read at its one scoring (2026-10-03). The labels are the authors' clusters of "
        "the protein data, and its CD8 T label largely separates naive from memory T cells.",
        _rows([(CURRENT, k_current["balanced_accuracy_pct"], []),
               (PREVIOUS, k_previous_score["balanced_accuracy_pct"], k_previous)],
              k_arms, k_pairs,
              "post-hoc; research/benchmark/khoury2026_posthoc_v41_check/summary.json and "
              "research/benchmark/khoury2026_posthoc_v42_check/summary.json",
              "corrected baselines, post-hoc; research/benchmark/khoury2026_posthoc/family_summary.csv"))

    f_types = sum(1 for key in t["dev_fulcher"][0] if key.startswith("recall_"))
    fulcher = _dataset(
        "fulcher2026", "Fulcher 2026", f"Balanced accuracy over {f_types} types", f_types,
        "Development data. In-sample for v4.1 and v4.2: v4.1's one tuned weight was chosen here and v4.2 "
        "was checked here, so a lead here is not evidence of a held-out gain. Fulcher measures neither "
        "CD8A, CD8B nor CD4.",
        _rows(ours(t["dev_fulcher"], "balanced_accuracy_pct", "Fulcher 2026"),
              _summary_arms(t["corrected_fulcher"], "balanced_accuracy_pct"), dev_pairs("Fulcher 2026"),
              dev_basis + "fulcher2026.csv", corrected_basis + "fulcher2026_summary.csv"))

    pbmc240 = _dataset(
        "pbmc240", "PBMC240", "Lymphoid recall", None,
        "Development data with lineage labels only, for some of its cells: the share of lymphoid-labelled "
        "cells whose single answer is lymphoid.",
        _rows(ours(t["dev_pbmc240"], "lymphoid_recall_pct", "PBMC240"),
              _summary_arms(t["corrected_pbmc240"], "lymphoid_recall_pct"), {},
              dev_basis + "pbmc240.csv", corrected_basis + "pbmc240_summary.csv"))

    s_types = int(next(r for r in t["dev_scope2"] if r["regime"] == "restricted")["n_candidate_classes"])
    scope2 = _dataset(
        "scope2", "SCoPE2, published matrix", "Balanced accuracy, restricted to macrophage or monocyte",
        s_types,
        "Development data: PMA-differentiated U-937 macrophages and undifferentiated monocytes, two "
        "states of one cell line. The published matrix arrives centred and batch-corrected.",
        _rows(ours(t["dev_scope2"], "balanced_accuracy_pct", "SCoPE2 restricted", "restricted"),
              _summary_arms(t["corrected_scope2"], "balanced_accuracy_pct", "restricted"),
              dev_pairs("SCoPE2 restricted"),
              dev_basis + "scope2.csv", corrected_basis + "scope2_summary.csv"))

    scope2_reprocessed = _dataset(
        "scope2_reprocessed", "SCoPE2, reprocessed", "Balanced accuracy, restricted to macrophage or monocyte",
        s_types,
        "The same cells from the authors' search output, with missing values kept missing and no "
        "centring or batch correction.",
        _rows(ours(t["dev_scope2_reprocessed"], "balanced_accuracy_pct", "SCoPE2 reprocessed restricted",
                   "restricted"),
              _per_seed_arms(t["dev_scope2_reprocessed"], "balanced_accuracy_pct", "restricted"),
              dev_pairs("SCoPE2 reprocessed restricted"),
              dev_basis + "scope2_reprocessed.csv", "corrected baselines; " + dev_basis + "scope2_reprocessed.csv"))

    return {
        "status": "measured",
        "current": CURRENT,
        "note": "Every method gets the same reference, the same genes and the same scoring. Each score is a "
                "method's one answer per cell (for VivOME, its best guess), with the mean and SD over seeds "
                "where a method has several.",
        "datasets": [khoury, fulcher, pbmc240, scope2, scope2_reprocessed],
    }


def pending_benchmark() -> dict:
    return {"status": "pending", "phase": "Phase 4",
            "note": "Its rows are published here once the owner signs them off.", "datasets": []}


def build_manifest(
    rna_rows: list[dict], prot_rows: list[dict],
    model: dict,
    latent_centroid_cosine_by_idx: dict[int, dict], modality_probe_accuracy: dict,
    previous_release: dict | None = None,
    earlier_release: dict | None = None,
    first_release: dict | None = None,
    model_card: dict | None = None,
    benchmark: dict | None = None,
) -> dict:
    rna = class_stats(rna_rows)
    prot = class_stats(prot_rows)

    cell_types = []
    for idx in sorted(set(rna) | set(prot)):
        r = rna.get(idx)
        p = prot.get(idx)
        if r and p:
            support = "cross_modal"
            cos = cosine(r["centroid"], p["centroid"])
            pca_cos = (
                measured(round(cos, 6), "3-PC projection")
                if cos is not None
                else pending("Phase 2", "Degenerate centroid; cosine undefined")
            )
        else:
            support = "rna_only" if r else "prot_only"
            pca_cos = pending("Phase 2", "No paired modality coverage for this class")

        cell_types.append({
            "class_idx": idx,
            "name": (r or p)["name"],
            "rna_cells": r["count"] if r else 0,
            "prot_cells": p["count"] if p else 0,
            "support": support,
            "pca_centroid_cosine": pca_cos,
            "latent_centroid_cosine": latent_centroid_cosine_by_idx.get(
                idx, pending("N/A", "No cross modal coverage")
            ),
            "modality_probe_accuracy": modality_probe_accuracy if support == "cross_modal" else pending(
                "N/A", "No cross modal coverage"
            ),
            "transfer_accuracy": pending(
                "N/A",
                "Measured per dataset at realistic coverage, not per class; see "
                "docs/service/context-brief.md §1 and service/model/evidence/v3_tables/"
                "rna_to_rna_real_masks.csv for the real numbers.",
            ),
        })

    summary = {
        "total": len(cell_types),
        "cross_modal": sum(1 for c in cell_types if c["support"] == "cross_modal"),
        "rna_only": sum(1 for c in cell_types if c["support"] == "rna_only"),
        "prot_only": sum(1 for c in cell_types if c["support"] == "prot_only"),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "atlas_version": ATLAS_VERSION,
        "generated": date.today().isoformat(),
        "model": model,
        "modalities": {
            "rna": {
                "label": "RNA",
                "cells": len(rna_rows),
                "classes": len(rna),
                "source": "scRNA-seq",
            },
            "prot": {
                "label": "Protein",
                "cells": len(prot_rows),
                "classes": len(prot),
                "source": "SCoPE2 mass spectrometry",
            },
        },
        "cell_types": cell_types,
        "summary": summary,
        # No architecture change is currently in flight, so there is no "next"
        # to report; the schema keeps the field (docs/web/manifest.md).
        "next_reference": None,
        "previous_release": previous_release,
        "earlier_release": earlier_release,
        "first_release": first_release,
        # v3's accuracy table ("v3 model card"; no page shows it).
        "model_card": model_card,
        "benchmark": benchmark or pending_benchmark(),
        "data_availability": {
            "rna_expression": {
                "status": "lfs_not_fetched",
                "note": "Git LFS object (~1.43 GB) is not present in this checkout.",
                "remedy": "git lfs install && git lfs pull",
            },
            "prot_expression": {"status": "available", "note": "web/data/atlas_PROT_lat128.csv"},
            "latent_coordinates": {
                "status": "not_distributed",
                "note": "Only the 3-component PCA projection ships with this build.",
            },
        },
    }


# The atlas's organs: every organ of the RNA atlas the references come from
# (web/data/organs/tabula_sapiens.json, scripts/tabula_sapiens_organs.py),
# each marked by what VivOME has of it. "labelling": the served reference's
# organ, whose files the service labels; "map": an organ reference built and
# shown on the Atlas page without labelling (web/data/organs/index.json);
# "to_build": the rest.
def build_organs(atlas: dict, organ_maps: dict, served_rna: str) -> dict:
    maps = {o["atlas"]: o for o in organ_maps["organs"]}
    organs = []
    for o in atlas["organs"]:
        if o["file"] == served_rna:
            organs.append({"name": o["name"], "status": "labelling"})
        elif o["file"] in maps:
            m = maps[o["file"]]
            organs.append({"name": o["name"], "status": "map", "id": m["id"],
                           "cells": m["cells"], "types": len(m["class_order"])})
        else:
            organs.append({"name": o["name"], "status": "to_build"})
    if sum(o["status"] == "labelling" for o in organs) != 1:
        raise ValueError(f"the served reference {served_rna} is not one of the atlas's organs")
    if sum(o["status"] == "map" for o in organs) != len(maps):
        raise ValueError("an organ map's atlas file is not in the atlas's organ list")
    return {
        "atlas": atlas["source"]["atlas"],
        "source": (f"web/data/organs/tabula_sapiens.json (Figshare article {atlas['source']['figshare_article']}, "
                   f"retrieved {atlas['source']['retrieved']}); web/data/organs/index.json"),
        "total": len(organs),
        "labelling": sum(o["status"] == "labelling" for o in organs),
        "maps": sum(o["status"] == "map" for o in organs),
        "to_build": sum(o["status"] == "to_build" for o in organs),
        "list": organs,
    }


# The model card's accuracy table (v3's; no page shows it). Each row names the
# decision rule it was scored with, because the two rules in use differ:
# nearest centroid is what the service runs; shared kNN is the rule every
# benchmark method is scored with. A shipped-checkpoint number and a 5-seed
# mean are only comparable under the same rule.
MODEL_CARD_RULES = {
    "restricted_native_centroid": ("restricted", "nearest centroid (the service's rule)"),
    "restricted_shared_knn": ("restricted", "shared kNN (the benchmark's rule)"),
    "unrestricted_native_centroid": ("unrestricted", "nearest centroid (the service's rule)"),
    "unrestricted": ("unrestricted", "shared kNN (the benchmark's rule)"),
}
RNA_TO_RNA_SOURCE = "research/notebook-outputs/nb1/rna_to_rna_membership_corrected.csv"
SEED_SCORES_SOURCE = "research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv"
FAMILY_SOURCE = "research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv"
PAIRED_SOURCE = "research/notebook-outputs/nb1d/paired_bootstrap_ours_vs_scanvi.csv"


def _fraction(percent) -> float:
    """The notebooks write percentages; the manifest stores fractions, as
    web/js/manifest.js:formatPercent expects."""
    return round(float(percent) / 100, 6)


def read_family_summary(lines: list[list[str]]) -> dict[tuple[str, str], dict]:
    """ours_scope2_5seed_family_summary.csv is a pandas describe() export
    with three header rows; returns {(family, regime): {acc_mean, ...}}."""
    keys = ("acc_mean", "acc_std", "acc_min", "acc_max", "bal_mean", "bal_std", "bal_min", "bal_max")
    out = {}
    for row in lines[3:]:
        if len(row) == 10 and row[0]:
            out[(row[0], row[1])] = dict(zip(keys, (float(v) for v in row[2:])))
    return out


def build_model_card(rna_rows: list[dict], score_rows: list[dict], family: dict, paired_rows: list[dict]) -> dict:
    test = next(r for r in rna_rows if r["mask"] == "scope2" and "test cells only" in r["cells"])
    published = next(r for r in rna_rows if r["mask"] == "scope2" and r["cells"].startswith("published"))
    rows = [{
        "key": "rna_to_rna_test",
        "measure": "RNA to RNA, SCoPE2 mask, test cells only",
        "rule": "optimal transport",
        "accuracy": measured(_fraction(test["acc_ot"]), RNA_TO_RNA_SOURCE),
        "balanced_accuracy": measured(_fraction(test["bal_ot"]), RNA_TO_RNA_SOURCE),
    }]
    seed0 = {r["regime"]: r for r in score_rows if r["model"] == "v3_seed0"}
    n_seeds = len({r["model"] for r in score_rows if r.get("family", "v3") == "v3"})
    for regime, (scope, rule) in MODEL_CARD_RULES.items():
        s = seed0[regime]
        f = family[("v3", regime)]
        rows.append({
            "key": f"{regime}:seed0",
            "measure": f"Protein (SCoPE2), {scope}, shipped checkpoint (v3_seed0)",
            "rule": rule,
            "accuracy": measured(_fraction(s["accuracy_pct"]), SEED_SCORES_SOURCE),
            "balanced_accuracy": measured(_fraction(s["balanced_accuracy_pct"]), SEED_SCORES_SOURCE),
        })
        rows.append({
            "key": f"{regime}:mean",
            "measure": f"Protein (SCoPE2), {scope}, {n_seeds}-seed mean of the architecture",
            "rule": rule,
            "accuracy": {**measured(_fraction(f["acc_mean"]), FAMILY_SOURCE), "sd": _fraction(f["acc_std"])},
            "balanced_accuracy": {
                **measured(_fraction(f["bal_mean"]), FAMILY_SOURCE),
                "sd": _fraction(f["bal_std"]), "min": _fraction(f["bal_min"]), "max": _fraction(f["bal_max"]),
            },
        })

    # v3 against scANVI, seed pairing by seed pairing, balanced accuracy.
    vs_scanvi = {}
    for regime in ("restricted_shared_knn", "unrestricted"):
        diffs = [float(r["diff_point_pct"]) for r in paired_rows if r["family"] == "v3" and r["regime"] == regime]
        vs_scanvi[regime] = {
            "pairings": len(diffs),
            "v3_ahead": sum(d > 0 for d in diffs),
            "mean_difference": measured(_fraction(sum(diffs) / len(diffs)), PAIRED_SOURCE),
        }
    # The figure first published, superseded: its test split included cells
    # the model had trained on.
    superseded = {
        "measure": "RNA to RNA, SCoPE2 mask, published sample (included training cells)",
        "accuracy": measured(_fraction(published["acc_ot"]), RNA_TO_RNA_SOURCE),
        "balanced_accuracy": measured(_fraction(published["bal_ot"]), RNA_TO_RNA_SOURCE),
    }
    return {"rows": rows, "vs_scanvi": vs_scanvi, "rna_to_rna_superseded": superseded}


def main() -> None:
    with (SERVICE_MODEL_DIR / "runtime" / "decisive_summary.json").open(encoding="utf-8") as handle:
        decisive_summary = json.load(handle)
    with (SERVICE_MODEL_DIR / "evidence" / "feature_space_detail.csv").open(newline="", encoding="utf-8") as handle:
        feature_space_detail_rows = list(csv.DictReader(handle))
    with (SERVICE_MODEL_DIR / "legacy" / "v2" / "provenance.json").open(encoding="utf-8") as handle:
        legacy_provenance = json.load(handle)
    with (SERVICE_MODEL_DIR / "runtime" / "provenance.json").open(encoding="utf-8") as handle:
        provenance = json.load(handle)
    with (V3_TABLES_DIR / "reference_seeds.csv").open(newline="", encoding="utf-8") as handle:
        reference_seeds_rows = list(csv.DictReader(handle))
    with (V3_TABLES_DIR / "latent_centroid_cosine.csv").open(newline="", encoding="utf-8") as handle:
        latent_centroid_cosine_rows = list(csv.DictReader(handle))
    with (V3_TABLES_DIR / "modality_probe.json").open(encoding="utf-8") as handle:
        modality_probe = json.load(handle)
    with (V31_TABLES_DIR / "latent_centroid_cosine.csv").open(newline="", encoding="utf-8") as handle:
        v31_latent_rows = list(csv.DictReader(handle))
    with (V31_TABLES_DIR / "modality_probe.json").open(encoding="utf-8") as handle:
        v31_modality_probe = json.load(handle)
    with (SERVICE_MODEL_DIR / "v3_1" / "nb2_spec_v31.json").open(encoding="utf-8") as handle:
        v31_members = json.load(handle)["encoder"]["members"]
    tables = {
        "dev_fulcher": read_csv(V42_DEV_DIR / "fulcher2026.csv"),
        "dev_pbmc240": read_csv(V42_DEV_DIR / "pbmc240.csv"),
        "dev_scope2": read_csv(V42_DEV_DIR / "scope2.csv"),
        "dev_scope2_reprocessed": read_csv(V42_DEV_DIR / "scope2_reprocessed.csv"),
        "paired_current": read_csv(V41_DEV_DIR / "paired_bootstrap_v41.csv"),
        "paired_previous_vs_current": read_csv(V42_DEV_DIR / "paired_bootstrap_v42_vs_v41.csv"),
        "corrected_fulcher": read_csv(CORRECTED_DIR / "fulcher2026_summary.csv"),
        "corrected_pbmc240": read_csv(CORRECTED_DIR / "pbmc240_summary.csv"),
        "corrected_scope2": read_csv(CORRECTED_DIR / "scope2_summary.csv"),
        "khoury_family": read_csv(KHOURY_POSTHOC_DIR / "family_summary.csv"),
        "khoury_current": json.loads((KHOURY_V41_DIR / "summary.json").read_text(encoding="utf-8")),
        "khoury_current_pairs": read_csv(KHOURY_V41_DIR / "paired_bootstrap.csv"),
        "khoury_previous": json.loads((KHOURY_V42_DIR / "summary.json").read_text(encoding="utf-8")),
        "khoury_previous_pairs": read_csv(KHOURY_V42_DIR / "paired_bootstrap.csv"),
    }
    phase3 = json.loads(V41_PHASE3.read_text(encoding="utf-8"))
    v42_evaluation = build_v42_evaluation(phase3, read_csv(V42_DEV_DIR / "confident.csv"),
                                          tables["dev_fulcher"], tables["khoury_previous"])
    v41_evaluation = build_v41_evaluation(phase3, read_csv(V41_DEV_DIR / "confident.csv"),
                                          read_csv(V41_DEV_DIR / "fulcher2026.csv"), tables["khoury_current"])

    deployed_architecture = build_deployed_architecture_facts(decisive_summary, feature_space_detail_rows)
    model_seeds = build_model_seeds(reference_seeds_rows, provenance)
    model = build_v41_model(len(v31_members), deployed_architecture, v41_evaluation)
    member = v31_modality_probe["member"].removesuffix(".pt")
    latent_centroid_cosine_by_idx = read_latent_centroid_cosine(v31_latent_rows, f" ({member}, the coordinate member)")
    modality_probe_accuracy = read_modality_probe_accuracy(v31_modality_probe)
    previous_release = build_v42_release(len(v31_members), deployed_architecture, v42_evaluation)
    earlier_release = build_v3_release(model_seeds, deployed_architecture, latent_centroid_cosine_rows, modality_probe)
    first_release = build_first_release_facts(legacy_provenance)
    with (NB1_DIR / "rna_to_rna_membership_corrected.csv").open(newline="", encoding="utf-8") as handle:
        rna_to_rna_rows = list(csv.DictReader(handle))
    with (NB1D_DIR / "ours_scope2_5seed_scores.csv").open(newline="", encoding="utf-8") as handle:
        seed_score_rows = list(csv.DictReader(handle))
    with (NB1D_DIR / "ours_scope2_5seed_family_summary.csv").open(newline="", encoding="utf-8") as handle:
        family = read_family_summary(list(csv.reader(handle)))
    with (NB1D_DIR / "paired_bootstrap_ours_vs_scanvi.csv").open(newline="", encoding="utf-8") as handle:
        paired_rows = list(csv.DictReader(handle))
    model_card = build_model_card(rna_to_rna_rows, seed_score_rows, family, paired_rows)

    rna_rows = read_metadata(ATLAS_DIR / "metadata_RNA_lat128.csv")
    prot_rows = read_metadata(ATLAS_DIR / "metadata_PROT_lat128.csv")
    manifest = build_manifest(
        rna_rows,
        prot_rows,
        model=model,
        latent_centroid_cosine_by_idx=latent_centroid_cosine_by_idx,
        modality_probe_accuracy=modality_probe_accuracy,
        previous_release=previous_release,
        earlier_release=earlier_release,
        first_release=first_release,
        model_card=model_card,
        benchmark=build_benchmark(tables),
    )
    served_rna = json.loads((SERVICE_MODEL_DIR / "v4_1" / "spec_v41.json").read_text(encoding="utf-8"))["reference"]["rna"]
    manifest["organs"] = build_organs(json.loads((ORGANS_DIR / "tabula_sapiens.json").read_text(encoding="utf-8")),
                                      json.loads((ORGANS_DIR / "index.json").read_text(encoding="utf-8")), served_rna)
    OUTPUT_PATH.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    s = manifest["summary"]
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {s['total']} cell types: {s['cross_modal']} cross-modal, {s['rna_only']} RNA-only")
    print(f"  model={model['name']!r} ({model['seeds']['value']} members), previous={previous_release['model_name']!r}, "
          f"earlier={earlier_release['model_name']!r}, feature_space_size={deployed_architecture['feature_space_size']}")
    print(f"  benchmark: {', '.join(f'''{d['name']} ({len(d['rows'])} rows)''' for d in manifest['benchmark']['datasets'])}")
    # The Workflow page's companion file, built for this same release.
    import build_workflow
    workflow = build_workflow.build(manifest)
    size = build_workflow.write(workflow)
    print(f"Wrote {build_workflow.rel(build_workflow.OUTPUT)} ({size:,} bytes)")
    # The Manuscript page's records, after the workflow data whose records it cites.
    import build_manuscript
    size = build_manuscript.write(build_manuscript.build(manifest, workflow))
    print(f"Wrote {build_workflow.rel(build_manuscript.OUTPUT)} ({size:,} bytes)")


if __name__ == "__main__":
    main()
