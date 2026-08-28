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


def class_stats(rows: list[dict]) -> dict:
    """-> {class_idx: {"name": str, "count": int, "centroid": (x, y, z)}}"""
    acc = defaultdict(lambda: {"name": None, "n": 0, "sx": 0.0, "sy": 0.0, "sz": 0.0})
    for row in rows:
        entry = acc[int(row["class_idx"])]
        entry["name"] = row["class_name"]
        entry["n"] += 1
        entry["sx"] += float(row["PC1"])
        entry["sy"] += float(row["PC2"])
        entry["sz"] += float(row["PC3"])
    return {
        idx: {
            "name": e["name"],
            "count": e["n"],
            "centroid": (e["sx"] / e["n"], e["sy"] / e["n"], e["sz"] / e["n"]),
        }
        for idx, e in acc.items()
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


def build_manifest(rna_rows: list[dict], prot_rows: list[dict]) -> dict:
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
    manifest = build_manifest(
        read_metadata(ATLAS_DIR / "metadata_RNA_lat128.csv"),
        read_metadata(ATLAS_DIR / "metadata_PROT_lat128.csv"),
    )
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    s = manifest["summary"]
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {s['total']} cell types: {s['cross_modal']} cross-modal, {s['rna_only']} RNA-only")


if __name__ == "__main__":
    main()
