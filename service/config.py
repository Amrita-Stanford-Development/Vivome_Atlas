"""Configuration for the projection service — every path is overridable by an
environment variable so swapping the dev placeholder for the production
export means changing a path, not touching pipeline code.

See service/model/README.md for what each path is, what is present today,
and what is still blocked on the full v3 training run.
"""
from __future__ import annotations

import os
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent
MODEL_DIR = SERVICE_ROOT / "model"


def _env_path(name: str, default: Path) -> Path:
    override = os.environ.get(name)
    return Path(override) if override else default


# --- Contract artifacts (docs/projection-service.md's backend, not the page) ---
# These three exist today, are architecture-independent, and do not change
# when the production checkpoint lands.
FEATURE_SPACE_GENES_PATH = _env_path(
    "VIVOME_FEATURE_SPACE_GENES", MODEL_DIR / "feature_space_genes.csv"
)
REFERENCE_METADATA_PATH = _env_path(
    "VIVOME_REFERENCE_METADATA", MODEL_DIR / "reference_metadata.csv"
)

# These three are the pending half of the contract (see Download_Checklist.md
# "Still waiting on"). REFERENCE_MODEL_PATH documents where the real v3
# export conventionally lands; it is not read directly (see
# ENCODER_WEIGHTS_PATH below). Loading a pending artifact before it exists
# raises a clear, typed error rather than a bare FileNotFoundError, so the
# pipeline fails legibly.
REFERENCE_MODEL_PATH = _env_path(
    "VIVOME_REFERENCE_MODEL", MODEL_DIR / "reference_model.pt"
)
REFERENCE_EMBEDDING_PATH = _env_path(
    "VIVOME_REFERENCE_EMBEDDING", MODEL_DIR / "reference_embedding.npy"
)
REFERENCE_CENTROIDS_PATH = _env_path(
    "VIVOME_REFERENCE_CENTROIDS", MODEL_DIR / "reference_centroids.npy"
)
REFERENCE_PROVENANCE_PATH = _env_path(
    "VIVOME_REFERENCE_PROVENANCE", MODEL_DIR / "provenance.json"
)

# Not part of the six-file contract: per-reference-cell continuous property
# values (ribosome content, antigen presentation, ...), computed once on
# RNA's full transcriptome (Stage 8). No such artifact has been produced yet
# for any reference version — see service/model/README.md. Property transfer
# is wired and tested against synthetic fixtures until this lands.
REFERENCE_PROPERTIES_PATH = _env_path(
    "VIVOME_REFERENCE_PROPERTIES", MODEL_DIR / "reference_properties.csv"
)

# --- Development-only placeholder ---
# Answers "which architecture generalises best", not the production model.
# It is missing the class imbalance correction, the hubness penalty, the
# sink penalty, and query-time smoothing was never combined with it during
# training. See service/model/dev/README.md.
DEV_CHECKPOINT_PATH = _env_path(
    "VIVOME_DEV_CHECKPOINT", MODEL_DIR / "dev" / "H_seed4.pt"
)

# --- The single knob the encoder actually loads from ---
# Right now this defaults to the dev placeholder above. When
# service/model/reference_model.pt (the real v3 export) lands, swapping to
# it means setting the VIVOME_ENCODER_WEIGHTS environment variable, or
# changing this one default — encoder.py and every pipeline stage downstream
# of it read only this path and never touch DEV_CHECKPOINT_PATH or
# REFERENCE_MODEL_PATH directly.
ENCODER_WEIGHTS_PATH = _env_path("VIVOME_ENCODER_WEIGHTS", DEV_CHECKPOINT_PATH)

# Architecture family decision. Preferred source is the production
# provenance.json once it exists (REFERENCE_PROVENANCE_PATH); until then this
# falls back to the decisive test's own record. See encoder.py.
DECISIVE_SUMMARY_PATH = _env_path(
    "VIVOME_DECISIVE_SUMMARY", MODEL_DIR / "decisive_summary.json"
)

ATLAS_VERSION = "0.1.0"

# Stage 5 / Stage 6 — fraction of the query drawn as the random calibration
# slice. Brief Stage 5: must be a random subset, never confidence-filtered.
CALIBRATION_FRACTION = 0.2
CALIBRATION_MIN_CELLS = 20

# Stage 5 — conformal target: 1 - alpha nominal coverage.
CONFORMAL_ALPHA = 0.1

# Stage 4 — unbalanced OT. epsilon ~0.05, marginal relaxation tau ~0.1 are the
# brief's validated settings. tau=50 (this project's old config) is the
# tightened value that collapsed SCoPE2 accuracy 72->47%; do not reuse it.
OT_EPSILON = 0.05
OT_TAU = 0.1
OT_MAX_ITER = 1000

# Stage 6 — below this fraction of genes observed, refuse rather than score.
COVERAGE_FLOOR = 0.15

# Stage 2 — fuzzy smoothing neighbourhood size within the query's own full
# feature set (brief Stage 2, the MaxFuse idea).
SMOOTHING_K = 15
SMOOTHING_ALPHA = 0.6

# Stage 8 — k nearest reference neighbours for property transfer, and the
# minimum validation correlation for a property to ship (brief Stage 8).
TRANSFER_K = 15
PROPERTY_RELIABILITY_THRESHOLD = 0.5

# The 4 of 8 candidate properties that passed the >=0.5 correlation
# threshold in the one validation run performed (brief Stage 8; also
# service/model/legacy_v2/provenance.json's shipped_properties from the v2
# export). Interferon response and cell cycle scored poorly and are
# deliberately excluded. Re-validate and replace this list once the v3
# reference has its own property validation run — do not assume it carries
# over unchanged.
SHIPPED_PROPERTIES = ("ribosome", "antigen_presentation", "oxphos", "glycolysis")

MASK_OBSERVED = 1.0
MASK_MISSING = 0.0
