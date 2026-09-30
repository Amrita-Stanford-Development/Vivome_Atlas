#!/usr/bin/env python3
"""Generate web/data/atlas_manifest.json from the metadata CSVs.

Every number emitted here is computed from data present in this repository.
Metrics with no source data yet — currently only benchmark rows against
established integration methods, and per-class transfer accuracy (a
per-*dataset* version exists, see `transfer_accuracy`'s note below, but
nothing decomposes it per class) — are emitted as explicit pending records
so the web layer renders them as pending instead of inventing a value.
"""
from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ATLAS_DIR = REPO_ROOT / "web" / "data"
OUTPUT_PATH = ATLAS_DIR / "atlas_manifest.json"
STORY_PATH = ATLAS_DIR / "story_cells.json"
SERVICE_MODEL_DIR = REPO_ROOT / "service" / "model"
V3_TABLES_DIR = SERVICE_MODEL_DIR / "evidence" / "v3_tables"

# decisive_summary.json's winner_config.enc -> a readable label for the manifest.
# Keep this in sync with service/pipeline/encoder.py's _ENCODER_FAMILIES table;
# an unrecognised value there raises loudly for the same reason it does here.
ENCODER_FAMILY_LABELS = {"module": "module pooling"}

SCHEMA_VERSION = "1.0"
ATLAS_VERSION = "0.2.0"

BENCHMARK_METHODS = [
    "CrossModalNet (ours)",
    "Seurat bridge integration",
    "GLUE",
    "MaxFuse",
    "scArches",
    "Harmony (shared features)",
    "PCA + nearest neighbour (floor)",
]


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


def read_latent_centroid_cosine(rows: list[dict]) -> dict[int, dict]:
    """service/model/evidence/v3_tables/latent_centroid_cosine.csv -> {class_idx: metric}.
    Measured only for the 2 classes with cross-modal coverage; the pending
    rows use an empty string for latent_centroid_cosine, never "0.0"."""
    out = {}
    for row in rows:
        idx = int(row["class_idx"])
        if row["status"] == "measured" and row["latent_centroid_cosine"] != "":
            n_prot = row["n_prot_cells"]
            out[idx] = measured(
                round(float(row["latent_centroid_cosine"]), 6),
                f"128-d latent centroid cosine, {n_prot} protein cells",
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


def build_previous_release_facts(legacy_provenance: dict) -> dict:
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
            "prior baseline, not erased, now that the frozen RNA-only v3 reference (see the "
            "model card above) has superseded it."
        ),
    }


def build_manifest(
    rna_rows: list[dict], prot_rows: list[dict],
    model_seeds: dict, deployed_architecture: dict,
    latent_centroid_cosine_by_idx: dict[int, dict], modality_probe_accuracy: dict,
    previous_release: dict | None = None,
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

    model = {
        "name": "VivOME v3 reference",
        "latent_dim": 128,
        "training_regime": "supervised",
        "seeds": model_seeds,
        "notes": (
            "A frozen, RNA-only reference encoder: proteomics queries are projected at "
            "inference and never used to retrain it. Coordinates shown in the viewer are a "
            "3-component PCA projection of the 128-d latent space; the latent coordinates "
            "themselves are not distributed with this build."
        ),
        **deployed_architecture,
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
        # No architecture change is currently in flight — the last one this
        # field described (CrossModalNet -> the frozen RNA-only reference
        # above) is complete, so there is no "next" to report. The schema
        # keeps supporting this field (web/js/panels.js:buildNextReferenceCard)
        # for whenever the next one starts.
        "next_reference": None,
        "previous_release": previous_release,
        "benchmark": {
            "status": "pending",
            "phase": "Phase 4",
            "note": "No comparison against established methods has been run yet.",
            "methods": BENCHMARK_METHODS,
            "rows": [],
        },
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


# The landing story's field (web/js/field.js) draws real atlas points, but the
# full RNA metadata is 6 MB: too much for a landing page. It gets every
# protein cell and a class-stratified, fixed-seed sample of RNA cells.
STORY_RNA_SAMPLE = 2000
STORY_MIN_PER_CLASS = 12
STORY_SEED = 0


def build_story_cells(rna_rows: list[dict], prot_rows: list[dict], *,
                      sample: int = STORY_RNA_SAMPLE, min_per_class: int = STORY_MIN_PER_CLASS,
                      seed: int = STORY_SEED) -> dict:
    """Select, never compute: the same 3-PC coordinates the atlas viewer plots,
    rounded to 3 places. Each class keeps its share of `sample`, with at least
    `min_per_class` cells so small classes stay visible. Protein rows carry
    the reference's own abstention flag (1 = abstained)."""
    rng = random.Random(seed)
    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in rna_rows:
        by_class[r["class_name"]].append(r)
    picked: list[dict] = []
    for name in sorted(by_class):
        rows = by_class[name]
        k = min(len(rows), max(min_per_class, round(sample * len(rows) / len(rna_rows))))
        picked.extend(rng.sample(rows, k))

    def pcs(r: dict) -> list[float]:
        return [round(float(r[c]), 3) for c in PC_COLUMNS]

    return {
        "source": "web/data/metadata_RNA_lat128.csv (sampled), web/data/metadata_PROT_lat128.csv (all rows)",
        "rna": [pcs(r) for r in picked],
        "prot": [pcs(r) + [1 if r.get("abstained") == "True" else 0] for r in prot_rows],
    }


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

    deployed_architecture = build_deployed_architecture_facts(decisive_summary, feature_space_detail_rows)
    model_seeds = build_model_seeds(reference_seeds_rows, provenance)
    latent_centroid_cosine_by_idx = read_latent_centroid_cosine(latent_centroid_cosine_rows)
    modality_probe_accuracy = read_modality_probe_accuracy(modality_probe)
    previous_release = build_previous_release_facts(legacy_provenance)

    rna_rows = read_metadata(ATLAS_DIR / "metadata_RNA_lat128.csv")
    prot_rows = read_metadata(ATLAS_DIR / "metadata_PROT_lat128.csv")
    manifest = build_manifest(
        rna_rows,
        prot_rows,
        model_seeds=model_seeds,
        deployed_architecture=deployed_architecture,
        latent_centroid_cosine_by_idx=latent_centroid_cosine_by_idx,
        modality_probe_accuracy=modality_probe_accuracy,
        previous_release=previous_release,
    )
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    story = build_story_cells(rna_rows, prot_rows)
    STORY_PATH.write_text(json.dumps(story, separators=(",", ":")) + "\n", encoding="utf-8")
    s = manifest["summary"]
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote {STORY_PATH.relative_to(REPO_ROOT)}: {len(story['rna'])} RNA, {len(story['prot'])} protein cells")
    print(f"  {s['total']} cell types: {s['cross_modal']} cross-modal, {s['rna_only']} RNA-only")
    print(f"  model.seeds={model_seeds['value']}, feature_space_size={deployed_architecture['feature_space_size']}, "
          f"encoder_family={deployed_architecture['encoder_family']!r}")


if __name__ == "__main__":
    main()
