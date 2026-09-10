#!/usr/bin/env python3
"""Generate Atlas/atlas_manifest.json from the metadata CSVs.

Every number emitted here is computed from data present in this repository.
Metrics that require the training pipeline — latent-space alignment, the
modality probe, transfer accuracy, benchmark rows — are emitted as explicit
pending records so the web layer renders them as pending instead of
inventing a value.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ATLAS_DIR = REPO_ROOT / "Atlas"
OUTPUT_PATH = ATLAS_DIR / "atlas_manifest.json"
SERVICE_MODEL_DIR = REPO_ROOT / "service" / "model"

# decisive_summary.json's winner_config.enc -> a readable label for the manifest.
# Keep this in sync with service/pipeline/encoder.py's _ENCODER_FAMILIES table;
# an unrecognised value there raises loudly for the same reason it does here.
ENCODER_FAMILY_LABELS = {"module": "module pooling"}

SCHEMA_VERSION = "1.0"
ATLAS_VERSION = "0.1.0"

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


def build_next_reference_facts(decisive_summary: dict, feature_space_detail_rows: list[dict]) -> dict:
    """The v3 reference's architecture is decided; the reference itself is
    not trained (Download_Checklist.md, "Still waiting on"). These are
    settled design facts, sourced from the actual decisive-test record and
    the actual feature-space union — not a rerun of provenance.json's own
    precomputed totals — kept in their own section so they are never
    mistaken for a property of `model` above, which describes the currently
    deployed release. transfer_accuracy, model.seeds, and benchmark.rows
    describe that current release and are correctly untouched by this."""
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
        "status": "architecture_decided",
        "trained": False,
        "feature_space_size": len(feature_space_detail_rows),
        "previous_feature_space_size": retained_from_old,
        "detected_by_source": detected_by_source,
        "encoder_family": encoder_family,
        "mask_sampling": winner_config["sampler"],
        "consistency_loss": winner_config["consist"],
        "note": (
            "Architecture settled by a five-seed masking comparison "
            f"(decisive_summary.json, n_seeds={decisive_summary['n_seeds']}). The production "
            "reference has not been trained with it — the checkpoints from that comparison used "
            "a simplified recipe (missing the class imbalance correction, the hubness penalty, and "
            "the sink penalty) and are development placeholders only. `model` above describes the "
            "currently deployed release, not this architecture."
        ),
    }


def build_previous_release_facts(legacy_provenance: dict) -> dict:
    """The currently deployed model's own numbers, kept as the documented
    prior baseline rather than erased when the architecture moves on
    (Claude_Code_Context_Brief.md, "For the model card"). CrossModalNet was
    jointly trained on RNA and proteomics together and had implicitly seen
    SCoPE2 during training — part of why these zero-shot numbers read
    higher than the honestly separated architecture's will. Both numbers
    are real; they answer different questions."""
    return {
        "model_name": "CrossModalNet",
        "n_shared_genes": legacy_provenance["n_shared_genes"],
        "zero_shot_auc_raw": measured(legacy_provenance["zero_shot_auc_raw"], "jointly trained, had seen SCoPE2"),
        "zero_shot_auc_smoothed": measured(legacy_provenance["zero_shot_auc_smoothed"], "jointly trained, had seen SCoPE2, query-time smoothing"),
        "shipped_properties": legacy_provenance["shipped_properties"],
        "note": (
            "CrossModalNet was jointly trained on RNA and proteomics together, so it had "
            "implicitly seen SCoPE2 during training — part of why these numbers read higher "
            "than the frozen-reference architecture's zero-shot number will. Kept here as the "
            "documented prior baseline, not erased; the honestly separated number is pending "
            "until the v3 reference is trained (see next_reference above)."
        ),
    }


def build_manifest(
    rna_rows: list[dict], prot_rows: list[dict],
    next_reference: dict | None = None, previous_release: dict | None = None,
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
            "latent_centroid_cosine": pending("Phase 1", "Requires 128-d latent coordinate export"),
            "modality_probe_accuracy": pending("Phase 4", "Requires linear modality probe run"),
            "transfer_accuracy": pending("Phase 1", "Requires multi-seed transfer evaluation"),
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
        "model": {
            "name": "CrossModalNet",
            "latent_dim": 128,
            "training_regime": "supervised",
            "seeds": pending("Phase 1", "Single run only; ten-seed statistics pending"),
            "notes": (
                "Coordinates shown in the viewer are a 3-component PCA projection of the "
                "128-d latent space. The latent coordinates themselves are not distributed "
                "with this build."
            ),
        },
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
        "next_reference": next_reference,
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
            "prot_expression": {"status": "available", "note": "Atlas/atlas_PROT_lat128.csv"},
            "latent_coordinates": {
                "status": "not_distributed",
                "note": "Only the 3-component PCA projection ships with this build.",
            },
        },
    }


def main() -> None:
    with (SERVICE_MODEL_DIR / "decisive_summary.json").open(encoding="utf-8") as handle:
        decisive_summary = json.load(handle)
    with (SERVICE_MODEL_DIR / "feature_space_detail.csv").open(newline="", encoding="utf-8") as handle:
        feature_space_detail_rows = list(csv.DictReader(handle))
    with (SERVICE_MODEL_DIR / "legacy_v2" / "provenance.json").open(encoding="utf-8") as handle:
        legacy_provenance = json.load(handle)

    next_reference = build_next_reference_facts(decisive_summary, feature_space_detail_rows)
    previous_release = build_previous_release_facts(legacy_provenance)

    manifest = build_manifest(
        read_metadata(ATLAS_DIR / "metadata_RNA_lat128.csv"),
        read_metadata(ATLAS_DIR / "metadata_PROT_lat128.csv"),
        next_reference=next_reference,
        previous_release=previous_release,
    )
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    s = manifest["summary"]
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {s['total']} cell types: {s['cross_modal']} cross-modal, {s['rna_only']} RNA-only")
    print(f"  next_reference: feature_space_size={next_reference['feature_space_size']}, "
          f"encoder_family={next_reference['encoder_family']!r}, trained={next_reference['trained']}")


if __name__ == "__main__":
    main()
