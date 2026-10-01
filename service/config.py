"""Configuration for the projection service — every path is overridable by an
environment variable so swapping the dev placeholder for the production
export means changing a path, not touching pipeline code.

See service/model/README.md for what each path is and what it holds.
"""
from __future__ import annotations

import os
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent
MODEL_DIR = SERVICE_ROOT / "model"
# What the server loads at runtime (a deployment ships this folder); see
# service/model/README.md for the other folders (evidence/, source/, legacy/).
RUNTIME_DIR = MODEL_DIR / "runtime"
LEGACY_DIR = MODEL_DIR / "legacy"


def _env_path(name: str, default: Path) -> Path:
    override = os.environ.get(name)
    return Path(override) if override else default


# --- Contract artifacts (docs/service/projection-api.md's backend, not the page) ---
# These three exist today, are architecture-independent, and do not change
# when the production checkpoint lands.
FEATURE_SPACE_GENES_PATH = _env_path(
    "VIVOME_FEATURE_SPACE_GENES", RUNTIME_DIR / "feature_space_genes.csv"
)

# Track B: frozen, versioned gene identifier cross-reference (symbol,
# Ensembl gene ID, UniProt accession) for the 9,002 feature-space genes.
# Built once, offline, from HGNC's public bulk dataset — see
# gene_id_map_v1_provenance.json alongside it for the source URL, download
# date, and sha256. Never re-fetched or looked up live at request time.
GENE_ID_MAP_PATH = _env_path(
    "VIVOME_GENE_ID_MAP", RUNTIME_DIR / "gene_id_map_v1.tsv"
)
REFERENCE_METADATA_PATH = _env_path(
    "VIVOME_REFERENCE_METADATA", RUNTIME_DIR / "reference_metadata.csv"
)

# The real v3 export. REFERENCE_MODEL_PATH documents where it lands; it is
# not read directly (see ENCODER_WEIGHTS_PATH below). Loading any of these
# before the file exists raises a clear, typed error rather than a bare
# FileNotFoundError, so the pipeline fails legibly — a guard that matters
# again the moment someone points one of these at a scratch/override path.
REFERENCE_MODEL_PATH = _env_path(
    "VIVOME_REFERENCE_MODEL", RUNTIME_DIR / "reference_model.pt"
)
REFERENCE_EMBEDDING_PATH = _env_path(
    "VIVOME_REFERENCE_EMBEDDING", RUNTIME_DIR / "reference_embedding.npy"
)
REFERENCE_CENTROIDS_PATH = _env_path(
    "VIVOME_REFERENCE_CENTROIDS", RUNTIME_DIR / "reference_centroids.npy"
)
REFERENCE_PROVENANCE_PATH = _env_path(
    "VIVOME_REFERENCE_PROVENANCE", RUNTIME_DIR / "provenance.json"
)

# Not part of the six-file contract: per-reference-cell continuous property
# values (ribosome content, antigen presentation, ...), computed once on
# RNA's full transcriptome (Stage 8). Row order matches REFERENCE_EMBEDDING_PATH
# and REFERENCE_METADATA_PATH; column order and names come from
# PROPERTY_NAMES_PATH's `property_names` list, not from this file's own header
# (it's a raw float32 array, not a CSV).
REFERENCE_PROPERTIES_PATH = _env_path(
    "VIVOME_REFERENCE_PROPERTIES", RUNTIME_DIR / "reference_properties.npy"
)
PROPERTY_NAMES_PATH = _env_path(
    "VIVOME_PROPERTY_NAMES", RUNTIME_DIR / "property_names.json"
)

# --- Development-only placeholder ---
# Answers "which architecture generalises best", not the production model.
# It is missing the class imbalance correction, the hubness penalty, the
# sink penalty, and query-time smoothing was never combined with it during
# training. See service/model/legacy/dev/README.md.
DEV_CHECKPOINT_PATH = _env_path(
    "VIVOME_DEV_CHECKPOINT", LEGACY_DIR / "dev" / "H_seed4.pt"
)

# --- The single knob the encoder actually loads from ---
# Defaults to the real v3 export now that it exists. Falling back to the dev
# placeholder means setting VIVOME_ENCODER_WEIGHTS=service/model/legacy/dev/H_seed4.pt
# (or overriding this default directly) — encoder.py and every pipeline stage
# downstream of it read only this path and never touch DEV_CHECKPOINT_PATH or
# REFERENCE_MODEL_PATH directly.
ENCODER_WEIGHTS_PATH = _env_path("VIVOME_ENCODER_WEIGHTS", REFERENCE_MODEL_PATH)

# Architecture family decision. provenance.json now exists but nests this
# under a different key (`encoder`, not `winner_config`) than
# decisive_summary.json uses — encoder.py's _read_encoder_family looks for
# `winner_config`, so this stays pointed at decisive_summary.json, which is
# still the accurate record (the architecture hasn't changed since that test).
DECISIVE_SUMMARY_PATH = _env_path(
    "VIVOME_DECISIVE_SUMMARY", RUNTIME_DIR / "decisive_summary.json"
)

ATLAS_VERSION = "0.3.0"

# --- Which pipeline answers a request ---
# "v3" is the single-encoder pipeline, byte for byte as before the switch
# existed (service/tests/test_pipeline_versions.py pins it against frozen
# responses). "v3.1" is T1 NB2's ensemble (service/pipeline/ensemble.py):
# five V2 encoders, per-class conformal sets, a fixed out-of-distribution
# threshold and hierarchical answers. v3.1 is the default (owner sign-off,
# Track F); v3 stays selectable. The bundle the service loads decides which
# pipeline runs.
PIPELINE_VERSIONS = ("v3", "v3.1")
PIPELINE_VERSION = os.environ.get("VIVOME_PIPELINE_VERSION", "v3.1")
if PIPELINE_VERSION not in PIPELINE_VERSIONS:
    raise ValueError(f"VIVOME_PIPELINE_VERSION={PIPELINE_VERSION!r}; expected one of {PIPELINE_VERSIONS}.")

# v3.1's files (service/model/README.md, "v3_1/"). The spec is T1 NB2's own
# export; MANIFEST.json holds the sha256 of every file, checked at load.
V31_DIR = _env_path("VIVOME_V31_DIR", MODEL_DIR / "v3_1")
V31_SPEC_PATH = V31_DIR / "nb2_spec_v31.json"
V31_MANIFEST_PATH = V31_DIR / "MANIFEST.json"
V31_MEMBERS_DIR = V31_DIR / "members"
# Coordinates and property transfer use one member's latent space, so a
# projected cell lands on the atlas the site displays: web/data/
# metadata_*_lat128.csv are generated from this same member
# (scripts/export_atlas_coordinates.py).
V31_COORDINATE_MEMBER = "V2_batchgene_aug_seed4.pt"

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

# Stage 6 — below this many observed genes (absolute count, not a fraction
# of the 9,002-gene feature space), refuse rather than score. Replaces the
# old fractional COVERAGE_FLOOR = 0.15 (1,350 of 9,002 genes), which
# refused 79% of real PBMC240 cells and 100% of real Fulcher cells outright
# (T1 NB1) — a fixed count is robust across datasets with very different
# native panel sizes in a way a fraction of one fixed denominator isn't.
# CALIBRATED ON SIMULATIONS, REVISIT: T1 NB1b's accuracy-vs-observed-genes
# curve shows chance-level accuracy below 100 genes (8.8% unrestricted,
# 34 cells) and stable accuracy from about 300 on. The range in between is
# barely sampled: no cells at all in 100-200, and 19 in 200-300. So this
# value is evidence-backed, not an arbitrary placeholder, but where exactly
# between 100 and 300 the floor belongs is untested. See
# research/notebook-outputs/nb1b/coverage_curve_v0.csv.
MIN_OBSERVED_GENES = 200
PROVISIONAL_CONSTANTS = ("MIN_OBSERVED_GENES",)

# Stage 1 — a query is treated as linear-scale intensity data (needing a
# log2 transform before z-scoring) when it has no negative observed values
# and its median observed value exceeds this. Real log-intensity data is
# typically single or low double digits; linear-scale intensities (e.g. a
# raw DIA-NN report) are typically in the hundreds to tens of thousands.
# Never transforms data with any negative values, which log-scale data
# commonly has and linear-scale intensity data cannot.
LINEAR_SCALE_MEDIAN_THRESHOLD = 50.0

# Stage 2 — fuzzy smoothing neighbourhood size within the query's own full
# feature set (brief Stage 2, the MaxFuse idea). k, alpha, and the PCA
# dimension match VivOME_Prototype_Export.ipynb exactly — that notebook is
# what measured the +0.026 AUC on SCoPE2 cited in smoothing.py, and what
# produced service/model/evidence/v3_tables/support_restricted_assignment.csv.
SMOOTHING_K = 15
SMOOTHING_ALPHA = 0.6
SMOOTHING_N_PCA = 50
SMOOTHING_SEED = 0

# Stage 8 — k nearest reference neighbours for property transfer, and the
# minimum validation correlation for a property to ship (brief Stage 8).
TRANSFER_K = 15
PROPERTY_RELIABILITY_THRESHOLD = 0.5

# The 6 of 8 candidate properties that passed the >=0.5 correlation threshold
# in the v3 reference's own validation run (service/model/v3_tables/property_
# validation.csv, matching provenance.json's shipped_properties). Only
# cell_cycle_G2M (r=0.4975) and interferon (r=0.3290) failed — cell_cycle_S
# and inflammatory both passed and are new relative to the v2 export's list.
SHIPPED_PROPERTIES = (
    "ribosome", "antigen_presentation", "oxphos", "glycolysis",
    "inflammatory", "cell_cycle_S",
)

# Phase 3 (label assignment) — see service/pipeline/assignment.py's module
# docstring for the measured evidence behind both of these.
#
# Only these classes have any protein cells anywhere in the reference
# (service/model/evidence/v3_tables/support_restricted_assignment.csv): restricting
# assignment to them moves balanced accuracy from 31.08% (all 22 classes
# candidate) to 79.79% (these 2 candidate) on real SCoPE2 data.
# Opt-in per request since 2026-09-30 (restrict_to_supported_classes), not
# the default: a SCoPE2 upload is only ever macrophage/monocyte, but a PBMC
# upload restricted this way has no correct label for its lymphoid cells.
CROSS_MODAL_SUPPORTED_CLASSES = ("macrophage", "monocyte")

# On real protein data, nearest-centroid beat both OT and kNN — the opposite
# of the RNA-only result an earlier brief used to mandate OT. Re-running this
# comparison *inside* the restricted regime above is open follow-up work, not
# done here; this default reflects current evidence, not a settled question.
ASSIGNMENT_METHOD = "nearest_centroid"  # "nearest_centroid" | "ot" | "knn"

# Stage 7 — the confidence reported for a cell resolved to a confusable pair's
# broader label, per label-space method (label_space.LabelSpace.method):
#   "within_pair_share": the winning class's share within the pair
#   "pair_mass": the pair's summed probability
# Under a restriction to exactly that pair the two probabilities sum to ~1 by
# construction, so pair_mass would read 1.0 for every resolved cell; the
# winning share is what varies. With every class a candidate, pair_mass may
# carry information again. Which rule suits which mode is open (research/todo.md,
# Track C); both modes keep the v3 rule until it is measured.
FALLBACK_CONFIDENCE = {
    "all_classes": "within_pair_share",
    "cross_modal_supported": "within_pair_share",
}

MASK_OBSERVED = 1.0
MASK_MISSING = 0.0

# The site's projection page (web/project.html) calls this service from the
# browser, so the service says which origins may read its responses (CORS).
# The default is the site served locally, as web/README.md documents; a
# deployment lists its own origins, comma separated.
ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get("VIVOME_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if origin.strip()
)
