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

ATLAS_VERSION = "0.6.0"

# --- Which pipeline answers a request ---
# "v3" is the single-encoder pipeline, byte for byte as before the switch
# existed (service/tests/test_pipeline_versions.py pins it against frozen
# responses). "v3.1" is T1 NB2's ensemble (service/pipeline/ensemble.py):
# five V2 encoders, per-class conformal sets, a fixed out-of-distribution
# threshold and hierarchical answers. It was the default from release 0.3.0
# (owner sign-off, Track F) and stays selectable, as does v3. The bundle the
# service loads decides which pipeline runs.
# "v4" (Track G, service/pipeline/fusion.py): v3.1's answers with a better best
# guess. Its evaluation passed (Phase 3c), so it is served when selected with
# VIVOME_PIPELINE_VERSION=v4. A spec whose evaluation has not passed answers 503.
# "v4.1" (Track G, v4.1): v4 with the encoder weighted 0.5 instead of 0.7 where
# the correlation term is used, chosen on Fulcher 2026. Its evaluation passed
# (Phase C); it was the default in release 0.4.0, and is again since release
# 0.6.0 (the owner's decision, 2026-10-17, after v4.2 fell short of it on
# Khoury 2026; research/notebook-run-history.md, entry 47).
# "v4.2" (Goal 2, Phase 2a): v4.1 with protein class means from sorted cells
# (Rieckmann 2017) in its correlation term, for the classes they cover, on
# protein uploads (an RNA upload takes v4.1's path). Its evaluation passed
# (research/notebook-run-history.md, entries 44 and 45); it was the default in
# release 0.5.0 and stays selectable.
# "v5" (Track H): v4.1's rule on five V2 members retrained on cleaned reference
# labels, with its own calibration; selectable, refused (503) until its
# evaluation passes. "v5.1": v5 with the NK T class folded into NK in training.
# "v5.2": v5.1 with CD4/CD8 T labels corrected by a classifier trained on Hao et
# al. 2021. Both are likewise refused until their evaluation passes.
PIPELINE_VERSIONS = ("v3", "v3.1", "v4", "v4.1", "v4.2", "v5", "v5.1", "v5.2", "v5.3", "v5.4", "v5.5")
PIPELINE_VERSION = os.environ.get("VIVOME_PIPELINE_VERSION", "v4.1")
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

# v4's files: only what v4 changes (scripts/build_v4_bundle.py). Its members and
# reference latents are v3.1's, checked by v3.1's MANIFEST.
V4_DIR = _env_path("VIVOME_V4_DIR", MODEL_DIR / "v4")
V4_SPEC_PATH = V4_DIR / "spec_v4.json"
V4_MANIFEST_PATH = V4_DIR / "MANIFEST.json"

# v4.1's files: its own spec only (scripts/build_v41_spec.py). Its MANIFEST also
# lists v4's data files, as ../v4/..., which it loads from V4_DIR.
V41_DIR = _env_path("VIVOME_V41_DIR", MODEL_DIR / "v4_1")
V41_SPEC_PATH = V41_DIR / "spec_v41.json"
V41_MANIFEST_PATH = V41_DIR / "MANIFEST.json"

# v4.2's files: its spec and protein class means (scripts/build_v42_spec.py);
# its MANIFEST also pins v4's data files, as ../v4/..., which it loads from V4_DIR.
V42_DIR = _env_path("VIVOME_V42_DIR", MODEL_DIR / "v4_2")
V42_SPEC_PATH = V42_DIR / "spec_v42.json"
V42_MANIFEST_PATH = V42_DIR / "MANIFEST.json"

# v5's files, all its own (research/notebooks/v5_build.py): members, latents and
# centroids, the answers' spec (NB2's layout), the best guess's spec (v4.1's
# layout) and one MANIFEST over them. The checkpoints are kept outside git.
V5_DIR = _env_path("VIVOME_V5_DIR", MODEL_DIR / "v5")
V5_ANSWERS_SPEC_PATH = V5_DIR / "nb2_spec_v5.json"
V5_SPEC_PATH = V5_DIR / "spec_v5.json"
V5_MANIFEST_PATH = V5_DIR / "MANIFEST.json"
V5_MEMBERS_DIR = V5_DIR / "members"

# v5.1's files, laid out as v5's (research/notebooks/v5_build.py --variant v5.1).
V51_DIR = _env_path("VIVOME_V51_DIR", MODEL_DIR / "v5_1")
V51_ANSWERS_SPEC_PATH = V51_DIR / "nb2_spec_v51.json"
V51_SPEC_PATH = V51_DIR / "spec_v51.json"
V51_MANIFEST_PATH = V51_DIR / "MANIFEST.json"
V51_MEMBERS_DIR = V51_DIR / "members"

V52_DIR = _env_path("VIVOME_V52_DIR", MODEL_DIR / "v5_2")
V53_DIR = _env_path("VIVOME_V53_DIR", MODEL_DIR / "v5_3")
V54_DIR = _env_path("VIVOME_V54_DIR", MODEL_DIR / "v5_4")
V55_DIR = _env_path("VIVOME_V55_DIR", MODEL_DIR / "v5_5")

# Every version built by research/notebooks/v5_build.py: (directory, answers'
# spec, best guess's spec). fusion.py reads its files from here.
V5_FAMILY = {
    "v5": (V5_DIR, "nb2_spec_v5.json", "spec_v5.json"),
    "v5.1": (V51_DIR, "nb2_spec_v51.json", "spec_v51.json"),
    "v5.2": (V52_DIR, "nb2_spec_v52.json", "spec_v52.json"),
    "v5.3": (V53_DIR, "nb2_spec_v53.json", "spec_v53.json"),
    "v5.4": (V54_DIR, "nb2_spec_v54.json", "spec_v54.json"),
    "v5.5": (V55_DIR, "nb2_spec_v55.json", "spec_v55.json"),
}

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

# Stages 1 and 2 — a gene whose observed values agree to about five
# significant digits (spread at most this share of its largest absolute
# value) is constant but for rounding, and z-scores to 0 like a constant gene
# (alignment.zscore_per_gene). No gene of the diagnostic bank's 30 tables is
# that close under their own readings; 10 of furtwangler_batchcorr's are when
# it is read as linear (research/notebook-outputs/value_scale_phaseA/notes.md).
ZSCORE_NEAR_CONSTANT_SPREAD = 1e-5

# Stage 2 — fuzzy smoothing neighbourhood size within the query's own full
# feature set (brief Stage 2, the MaxFuse idea). k, alpha, and the PCA
# dimension match VivOME_Prototype_Export.ipynb exactly — that notebook is
# what smoothing.py's SCoPE2 evidence refers to, and what
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
# assignment to them moves v3's balanced accuracy on real SCoPE2 data from
# 0.68% (all 22 classes candidate) to 20.21% (these 2 candidate), still far
# below the two classes' 50% chance: v3 calls most SCoPE2 macrophages
# monocytes. (31.08% and 79.79% until 2026-10-04, against swapped labels;
# research/benchmark/bugs-and-fixes.md, 8.)
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

# The Atlas page's Your data tab (web/atlas.html) calls this service from the
# browser, so the service says which origins may read its responses (CORS).
# The default is the site served locally, as web/README.md documents; a
# deployment lists its own origins, comma separated.
ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get("VIVOME_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if origin.strip()
)

# --- Hosting: where the server listens and how much one request may ask ---
# The defaults serve this machine only; the hosted copy (deploy/huggingface/)
# sets VIVOME_HOST=0.0.0.0 and VIVOME_PORT=7860.
HOST = os.environ.get("VIVOME_HOST", "127.0.0.1")
PORT = int(os.environ.get("VIVOME_PORT", "8001"))
# One projection's time grows faster than its cell count: measured on this
# project's Windows PC (24 cores, PBMC240's cells tiled, 2026-10-16, with
# another heavy job running, so upper bounds) 1.7 s for 238 cells, 6.7 s for
# 1,000, 21 s for 2,000, 45 s for 3,000 and 119 s for 5,000, with a peak of
# 3.6 GB at 3,000 against 1.5 GB idle. The hosted copy
# runs on 2 CPU cores, so 2,000 cells keeps one request within a couple of
# minutes; a larger dataset goes in several mixed uploads, or to a service run
# locally with these raised.
MAX_UPLOAD_CELLS = int(os.environ.get("VIVOME_MAX_UPLOAD_CELLS", "2000"))
# A DIA-NN report of 2,000 cells over about 8,000 proteins is near 200 MB of
# text. 100 MB is the default for a copy run at home, which can raise it. The
# hosted copy takes less: Cloud Run takes at most 32 MiB in an HTTP/1 request,
# so its Dockerfile sets 31 (deploy/huggingface/Dockerfile).
MAX_UPLOAD_BYTES = int(float(os.environ.get("VIVOME_MAX_UPLOAD_MB", "100")) * 1024 * 1024)
# Projections running at once. Each takes every core it can and up to about
# 3.6 GB, so the hosted copy runs one at a time and answers 503 to the next
# request, with a Retry-After, until it is done.
MAX_CONCURRENT_PROJECTIONS = int(os.environ.get("VIVOME_MAX_CONCURRENT_PROJECTIONS", "1"))
BUSY_RETRY_AFTER_SECONDS = int(os.environ.get("VIVOME_BUSY_RETRY_AFTER_SECONDS", "30"))

# The hosted copy answers only through its website: the site's /api door
# (deploy/pages/api-proxy.js) adds this secret to every request it forwards,
# and with VIVOME_PROXY_SECRET set the service refuses any request without it
# (403). Unset, as for a copy run at home, every request is answered.
PROXY_SECRET = os.environ.get("VIVOME_PROXY_SECRET") or None
PROXY_SECRET_HEADER = "X-VivOME-Proxy-Secret"
