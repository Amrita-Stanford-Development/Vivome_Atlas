"""Builds web/data/manuscript.json, the Manuscript page's data
(web/manuscript.html; docs/web/manuscript.md).

Standard library only, deterministic. scripts/build_manifest.py calls
build() after it builds the manifest and the Workflow page's data, so all
three files are built together for one release; `built_for` must equal the
manifest's.

The page is an evidence bank for a manuscript about the served model: one
claim per line, each number a record here. This file reads only committed
results: v4.1's development, post-hoc and held-out records, the evaluation
suite, the benchmark tables, the diagnoses, and the records of designs that
were tried and not kept (research/notebook-outputs/, research/benchmark/,
service/model/). Records the Workflow page already holds (settings, the
encoder, the hosted service) are copied from web/data/workflow.json with
their basis, not recomputed.

Every record is {value, status, basis, format}, or pending with a note, so
web/js/manuscript-data.js shows it through manifest.js's isMeasured guard.
Values are fractions for shares and differences ("pct1", "pct2"; "points"
signed, "pp" a size without sign), counts, or plain numbers ("fixed2",
"fixed3", "fixed4", "plain"); the Workflow page's own formats ("percent")
pass through on the records copied from it.

    python scripts/build_manuscript.py      # from the repository root (build_manifest.py also runs it)
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from build_workflow import REPO, measured, pending, rel, sha256

OUTPUT = REPO / "web" / "data" / "manuscript.json"
MANIFEST = REPO / "web" / "data" / "atlas_manifest.json"
WORKFLOW = REPO / "web" / "data" / "workflow.json"
SCHEMA_VERSION = "1"
SIZE_BUDGET = 150_000  # bytes; scripts/test_build_manuscript.py enforces it

NO = REPO / "research" / "notebook-outputs"
RB = REPO / "research" / "benchmark"
MODEL = REPO / "service" / "model"

PHASE3 = NO / "v41_phase3" / "summary.json"
PHASE3_UPLOADS = NO / "v41_phase3" / "eval_uploads.csv"
DEVELOPMENT = NO / "v41_phase3" / "development.json"
SELECTION = NO / "v41_pretest" / "selection.json"
CANDIDATES = NO / "v41_pretest" / "candidates.csv"
RESEARCH_ARM = NO / "v41_pretest" / "research_arm.csv"
EXPLORATION = NO / "v4_phase3c" / "exploration.json"
SMOOTHED_SHARE = NO / "v4_phase3b" / "selection.json"
JOINED = NO / "v4_phase3b" / "summary.json"
NB2 = NO / "nb2" / "nb2_summary.json"
TEMPERATURE = NO / "nb2" / "tables" / "temperature.csv"
MONDRIAN = NO / "nb2" / "tables" / "conformal_choice_calsel.csv"
FLAGS = NO / "nb3b" / "eval_flags_summary.csv"
NB3B = NO / "nb3b" / "summary.json"
NB3C = NO / "nb3c" / "summary.json"
NB1B = NO / "nb1b" / "nb1b_summary.json"
NB1D = NO / "nb1d" / "nb1d_summary.json"
UPLOAD_PROBE = NO / "upload_independent_probe" / "summary.json"
COVERAGE = NO / "protein_coverage" / "coverage.json"
SINGLE = NO / "single_type_uploads" / "summary.json"
ASTRAL = NO / "astral_abstention" / "summary.json"
DONOR = NO / "donor_heldout" / "summary.json"
CD8_CD4 = NO / "cd8_cd4_diagnosis" / "diagnosis.json"
MARKERS = NO / "marker_audit" / "detection.csv"
FOREIGN = NO / "ood_candidates" / "summary.json"
HAO_DC = NO / "hao_dc_centres" / "summary.json"
NARROW = NO / "narrow_upload" / "committed.json"
V51_PHASE4 = NO / "v51_phase4" / "summary.json"
CONFIDENT = RB / "v41_development" / "confident.csv"
FULCHER_V41 = RB / "v41_development" / "fulcher2026.csv"
PAIRED = RB / "v41_development" / "paired_bootstrap_v41.csv"
PAIRED_ABLATION = RB / "v41_development" / "paired_bootstrap_v41_vs_v31.csv"
GATE = RB / "v41_dev_gate.json"
KHOURY = RB / "khoury2026_posthoc_v41_check" / "summary.json"
KHOURY_PAIRED = RB / "khoury2026_posthoc_v41_check" / "paired_bootstrap.csv"
KHOURY_SEALED = RB / "khoury2026" / "summary.json"
KHOURY_PROTEIN_MEANS = RB / "khoury2026_posthoc_v42_check" / "summary.json"
KHOURY_RELABELLED = RB / "khoury2026_posthoc_v51_check" / "summary.json"
FULCHER_ENCODERS = RB / "fulcher2026" / "paired_bootstrap.csv"
CORRECTED_FULCHER = RB / "baselines_corrected" / "fulcher2026_summary.csv"
INPUTS = RB / "baselines_corrected" / "inputs.csv"
FURTWANGLER = RB / "furtwangler2025" / "v31_ood_check.json"
HELDOUT = RB / "heldout"
SPEC_ANSWERS = MODEL / "v3_1" / "nb2_spec_v31.json"
SPEC_SERVED = MODEL / "v4_1" / "spec_v41.json"
REFERENCE = MODEL / "runtime" / "reference_metadata.csv"
FEATURE_PROVENANCE = MODEL / "evidence" / "feature_space_provenance.json"
PROBE = MODEL / "evidence" / "v3_1_tables" / "modality_probe.json"
LATENT_COSINE = MODEL / "evidence" / "v3_1_tables" / "latent_centroid_cosine.csv"

# The Workflow page's records this page cites, under its own names.
WORKFLOW_FACTS = (
    "missing_share", "scale_threshold", "floor", "smoothing_k", "smoothing_alpha", "smoothing_own", "smoothing_pca",
    "members", "genes", "modules", "input_width", "hidden1", "hidden2", "latent", "parameters",
    "agreement_threshold", "weight_used", "weight_flat", "correlation_temperature", "smoothed_share",
    "target_coverage", "ood_threshold", "ood_share_above", "classes", "rna_cells",
)
WORKFLOW_RECIPE = (
    "epochs", "batch", "learning_rate", "weight_decay", "patience", "coverage_low", "coverage_high",
    "validation_coverage", "dropout", "natural_share", "contrastive_temperature", "margin",
)
WORKFLOW_SERVICE = ("cpu", "max_instances", "max_cells", "max_mb", "timeout_seconds")
COARSE_TYPES = ("CD4T", "CD8T", "NK", "B", "monocyte", "DC")


def dig(node, keys):
    for key in keys:
        node = node[key]
    return node


class Records:
    """The page's records, each with the file and keys it came from."""

    def __init__(self):
        self.records: dict[str, dict] = {}
        self.sources: set[Path] = set()
        self._cache: dict[Path, object] = {}

    def json(self, path: Path):
        if path not in self._cache:
            self._cache[path] = json.loads(path.read_text(encoding="utf-8"))
            self.sources.add(path)
        return self._cache[path]

    def csv(self, path: Path) -> list[dict]:
        if path not in self._cache:
            with path.open(newline="", encoding="utf-8") as handle:
                self._cache[path] = list(csv.DictReader(handle))
            self.sources.add(path)
        return self._cache[path]

    def row(self, path: Path, **match) -> dict:
        found = [r for r in self.csv(path) if all(r[k] == v for k, v in match.items())]
        assert len(found) == 1, f"{rel(path)}: {len(found)} rows match {match}"
        return found[0]

    def put(self, key: str, value, basis: str, fmt: str) -> None:
        assert key not in self.records, f"duplicate record {key}"
        assert value is not None and value == value, f"{key}: no value"  # value == value rejects NaN
        self.records[key] = measured(value, basis, fmt)

    def at(self, key: str, path: Path, keys: tuple, fmt: str, scale: float = 1.0, digits: int = 6) -> None:
        """A value from a JSON file; scale 0.01 turns a percentage into a fraction."""
        value = dig(self.json(path), keys)
        value = round(float(value) * scale, digits) if fmt != "count" else int(value)
        self.put(key, value, f"{rel(path)}: {' > '.join(map(str, keys))}", fmt)

    def pct(self, key: str, path: Path, *keys, fmt: str = "pct1") -> None:
        self.at(key, path, keys, fmt, scale=0.01)

    def cell(self, key: str, path: Path, column: str, fmt: str, scale: float = 1.0, **match) -> None:
        r = self.row(path, **match)
        value = int(r[column]) if fmt == "count" else round(float(r[column]) * scale, 6)
        where = ", ".join(f"{k} {v}" for k, v in match.items())
        self.put(key, value, f"{rel(path)}: {column} where {where}", fmt)

    def copy(self, key: str, record: dict) -> None:
        assert key not in self.records, f"duplicate record {key}"
        assert record.get("status") == "measured", f"{key}: the copied record is not measured"
        self.records[key] = dict(record)

    def wait(self, key: str, phase: str, note: str) -> None:
        assert key not in self.records, f"duplicate record {key}"
        self.records[key] = pending(phase, note)


# ---- 2. Experimental procedures ----

def reference(r: Records) -> None:
    rows = r.csv(REFERENCE)
    basis = f"{rel(REFERENCE)}: the served reference's cells"
    classes = Counter(row["class_name"] for row in rows)
    r.put("ref_cells", len(rows), basis, "count")
    r.put("ref_donors", len({row["cell"].split("_")[0] for row in rows}), f"{basis}, donors from the cell names", "count")
    r.put("ref_classes", len(classes), basis, "count")
    r.put("ref_neutrophil_share", round(classes["neutrophil"] / len(rows), 6), basis, "pct1")
    r.put("ref_neutrophils", classes["neutrophil"], basis, "count")
    r.put("ref_mdc", classes["myeloid dendritic cell"], basis, "count")
    r.put("ref_pdc", classes["plasmacytoid dendritic cell"], basis, "count")
    r.put("ref_macrophage", classes["macrophage"], basis, "count")
    r.put("ref_cd8", classes["cd8-positive, alpha-beta t cell"], basis, "count")
    hierarchy = r.json(SPEC_SERVED)["hierarchy"]
    basis = f"{rel(SPEC_SERVED)}: hierarchy"
    r.put("ref_groups", len({h["group"] for h in hierarchy.values()}), basis, "count")
    r.put("ref_lineages", len({h["lineage"] for h in hierarchy.values()}), basis, "count")
    r.at("ref_reference_cells_spec", SPEC_SERVED, ("reference", "n_cells"), "count")


def gene_space(r: Records) -> None:
    p = r.json(FEATURE_PROVENANCE)
    basis = rel(FEATURE_PROVENANCE)
    r.put("gs_sources", len(p["sources"]), f"{basis}: sources", "count")
    r.at("gs_union", FEATURE_PROVENANCE, ("union_raw",), "count")
    r.at("gs_ig_tcr", FEATURE_PROVENANCE, ("ig_tcr_excluded",), "count")
    r.at("gs_size", FEATURE_PROVENANCE, ("feature_space",), "count")


def from_workflow(r: Records, workflow: dict) -> None:
    for key in WORKFLOW_FACTS:
        r.copy(f"wf_{key}", workflow["facts"][key])
    for key in WORKFLOW_RECIPE:
        r.copy(f"wf_recipe_{key}", workflow["training"]["recipe"][key])
    for key in WORKFLOW_SERVICE:
        r.copy(f"wf_service_{key}", workflow["service"][key])


def answer_layer(r: Records) -> None:
    spec = r.json(SPEC_ANSWERS)
    temps = spec["assignment"]["temperature"].values()
    basis = f"{rel(SPEC_ANSWERS)}: assignment > temperature"
    r.put("temp_min", round(min(temps), 4), basis, "fixed3")
    r.put("temp_max", round(max(temps), 4), basis, "fixed3")
    qhat = spec["conformal"]["qhat_by_class"]
    basis = f"{rel(SPEC_ANSWERS)}: conformal > qhat_by_class"
    r.put("qhat_min", round(min(qhat.values()), 4), basis, "fixed3")
    r.put("qhat_max", round(max(qhat.values()), 4), basis, "fixed3")
    r.at("qhat_marginal", SPEC_ANSWERS, ("conformal", "marginal_qhat"), "fixed3", digits=4)
    r.at("alpha", SPEC_ANSWERS, ("conformal", "alpha"), "plain")


# ---- 2.7 The design rationale: each part, the problem it fixes ----

def rationale(r: Records) -> None:
    # Per-upload, gene-wise scaling: a probe of what the scaling buys on Fulcher.
    for key, arm in (("within", "within upload"), ("raw", "raw profile"), ("centred", "reference-centred")):
        r.pct(f"ra_scaling_{key}", UPLOAD_PROBE, "fulcher_mixed", arm, "balanced_accuracy", fmt="pct2")
    # The training recipe (varied upload composition) against the earlier recipe, five seeds each.
    for model, key in (("V2", "now"), ("v3", "before")):
        r.pct(f"ra_rna_{key}", NB1D, "rna_eval_slice", "bal_unres", model, "mean")
        r.pct(f"ra_single_{key}", NB1D, "rna_eval_slice", "single_class", model, "mean")
        r.pct(f"ra_pbmc_lineage_{key}", NB1D, "real_smooth_on", "pbmc_lineage_acc", model, "mean")
    rows = [x for x in r.csv(FULCHER_ENCODERS) if x["comparison"] == "V2 vs v3"]
    basis = f"{rel(FULCHER_ENCODERS)}: comparison V2 vs v3"
    r.put("ra_fulcher_pairings", len(rows), basis, "count")
    r.put("ra_fulcher_pairings_won", sum(x["favours"] == "V2" for x in rows), f"{basis}, favours V2", "count")
    # Seed instability of a single encoder, and what the temperature fit fixed.
    r.pct("ra_seed_min", NB1D, "real_smooth_on", "scope2_restr", "v3", "min")
    r.pct("ra_seed_max", NB1D, "real_smooth_on", "scope2_restr", "v3", "max")
    members = [x for x in r.csv(TEMPERATURE) if x["model"].startswith("V2_") and x["rule"] == "centroid"]
    basis = f"{rel(TEMPERATURE)}: the five V2 members, centroid rule, mean"
    r.put("ra_ece_before", round(sum(float(x["ece_T1"]) for x in members) / len(members), 4), basis, "fixed2")
    r.put("ra_ece_after", round(sum(float(x["ece_fitted"]) for x in members) / len(members), 4), basis, "fixed2")
    # Calibration on labelled RNA instead of each upload's own guesses.
    for config, key in (("eval_service_today_v3", "before"), ("eval_candidate", "now")):
        r.pct(f"ra_abstain_{key}", NB2, config, "abstain_rate")
        r.pct(f"ra_correct_{key}", NB2, config, "correct_when_committed")
    for kind in ("marginal", "mondrian"):
        r.cell(f"ra_{kind}_worst", MONDRIAN, "min_class_cov", "pct1", 0.01, **{"": kind})
        r.cell(f"ra_{kind}_mean", MONDRIAN, "mean_cov", "pct1", 0.01, **{"": kind})
    # The best guess added to every non-empty set.
    for rule, key in (("NB2 rule", "before"), ("set_includes_best_guess", "now")):
        r.cell(f"ra_flag_coverage_{key}", FLAGS, "coverage", "pct1", 0.01, rule=rule, ood="OOD today")
        r.cell(f"ra_flag_correct_{key}", FLAGS, "correct_when_committed", "pct1", 0.01, rule=rule, ood="OOD today")
    # Linear-scale detection: the service's pipeline with and without the log transform.
    for pipe, key in (("B_service_log", "log"), ("C_service_lin", "linear")):
        row = next(x for x in r.json(NB1B)["a2_ablation"] if x["pipeline"] == pipe)
        r.put(f"ra_log_{key}", round(row["bal_unres"] / 100, 6), f"{rel(NB1B)}: a2_ablation, {pipe}, bal_unres", "pct1")
    # Smoothing: the share of the smoothed query in the best guess.
    for share, key in (("v4 s=0.0", "off"), ("v4 s=0.5", "half")):
        r.pct(f"ra_smooth_single_{key}", SMOOTHED_SHARE, "calibration_suite", share, "by_group", "single")
    r.pct("ra_smooth_single_before", SMOOTHED_SHARE, "calibration_suite", "v3.1", "by_group", "single")
    r.at("ra_smooth_drop_off", SMOOTHED_SHARE, ("calibration_suite", "v4 s=0.0", "largest_scenario_drop"),
         "pp", scale=0.01)
    # Class-balanced statistics, the correlation term, and its gate.
    encoder_only = ("finalists", "class-balanced encoder only, s=1")
    r.pct("ra_cb_suite", EXPLORATION, *encoder_only, "calibration_suite", "overall", fmt="pct2")
    r.pct("ra_cb_suite_before", SELECTION, "v31", "suite", "overall", fmt="pct2")
    r.pct("ra_cb_fulcher", EXPLORATION, *encoder_only, "development", "fulcher", fmt="pct2")
    r.pct("ra_cb_fulcher_before", EXPLORATION, "v31", "development", "fulcher", fmt="pct2")
    r.pct("ra_corr_fulcher", DEVELOPMENT, "fulcher2026", "v4.1", "balanced_accuracy_6_types", fmt="pct2")
    ungated = ("finalists", "Phase 3b: s=0.5, correlation in every upload")
    gated = ("finalists", "B: s=0.5, agreement gate 0.4 (chosen)")
    looser = ("finalists", "B: s=0.5, agreement gate 0.35")
    r.at("ra_gate_fail_ungated", EXPLORATION, ungated + ("extra_single_type_uploads", "p_fail"), "fixed3")
    r.at("ra_gate_fail_gated", EXPLORATION, gated + ("extra_single_type_uploads", "p_fail"), "fixed3")
    r.pct("ra_gate_pbmc_looser", EXPLORATION, *looser, "development", "pbmc_lymphoid")
    r.pct("ra_gate_pbmc_gated", EXPLORATION, *gated, "development", "pbmc_lymphoid")
    r.at("ra_gate_pbmc_agreement", EXPLORATION, ("upload_agreement", "development", "pbmc240"), "fixed3")
    for group in ("single", "mixed", "pbmc"):
        r.at(f"ra_gate_median_{group}", EXPLORATION,
             ("upload_agreement", "calibration_suite_by_scenario", group, "50%"), "fixed2")
    rejected = r.json(EXPLORATION)["rejected"]
    per_cell = next(k for k in rejected if k.startswith("s=0.5, per-cell gate"))
    r.at("ra_gate_fail_per_cell", EXPLORATION, ("rejected", per_cell, "extra_single_type_uploads", "p_fail"), "fixed3")
    r.at("ra_gate_fail_w08", EXPLORATION, ("rejected", "s=0.5, fusion weight 0.8", "extra_single_type_uploads",
                                           "p_fail"), "fixed3")
    # The guess joins the set beside the answer path's top label; replacing it lost coverage.
    r.pct("ra_join_replace", JOINED, "result", "v4", "coverage")
    r.pct("ra_join_replace_before", JOINED, "result", "v3.1", "coverage")
    r.pct("ra_join_now", PHASE3, "result", "v4.1", "coverage", fmt="pct2")
    r.pct("ra_join_now_before", PHASE3, "result", "v3.1", "coverage", fmt="pct2")
    # The one tuned weight: the candidates, those within the guardrails, those stable.
    selection = r.json(SELECTION)
    r.put("ra_weight_candidates", len(r.csv(CANDIDATES)), f"{rel(CANDIDATES)}: rows", "count")
    r.put("ra_weight_eligible", len(selection["eligible"]), f"{rel(SELECTION)}: eligible", "count")
    r.put("ra_weight_stable", len(selection["stable"]), f"{rel(SELECTION)}: stable", "count")


# ---- 2.8-2.10 Datasets, the evaluation suite, the benchmark ----

def datasets(r: Records) -> None:
    for key in ("pbmc240", "scope2", "fulcher2026", "furtwangler2025"):
        r.at(f"ds_{key}_cells", GATE, ("datasets", key, "cells"), "count")
    r.at("ds_fulcher_scored", COVERAGE, ("v41", "fulcher2026", "n"), "count")
    r.at("ds_pbmc240_labelled", COVERAGE, ("v41", "pbmc240", "n"), "count")
    r.at("ds_khoury_cells", KHOURY_SEALED, ("n_scored",), "count")
    r.cell("ds_scope2_reprocessed_cells", CONFIDENT, "cells", "count", model="v41", dataset="SCoPE2 reprocessed")
    hao = r.json(HELDOUT / "hao2021" / "summary.json")
    r.at("ds_hao_uploads", HELDOUT / "hao2021" / "summary.json", ("uploads",), "count")
    r.put("ds_hao_donors", len(hao["donors"]), f"{rel(HELDOUT / 'hao2021' / 'summary.json')}: donors", "count")
    for key in ("pxd043355", "pxd073250", "pxd046211"):
        path = HELDOUT / key / "summary.json"
        r.at(f"ds_{key}_positive", path, ("candidates", "v4.1", "primary", "n_positive"), "count")
        r.at(f"ds_{key}_negative", path, ("candidates", "v4.1", "primary", "n_negative"), "count")
    for key, name in (("pbmc240", "PBMC240"), ("fulcher2026", "Fulcher 2026")):
        r.at(f"ds_{key}_proteins_per_cell", ASTRAL, (name, "proteins_per_cell_median"), "count")


def suite(r: Records) -> None:
    r.at("suite_cells", PHASE3, ("result", "v4.1", "cells"), "count")
    r.put("suite_uploads", len(r.csv(PHASE3_UPLOADS)), f"{rel(PHASE3_UPLOADS)}: rows", "count")
    checks = r.json(PHASE3)["checks"]
    r.put("suite_checks", len(checks), f"{rel(PHASE3)}: checks", "count")
    r.put("suite_checks_passed", sum(bool(v) for v in checks.values()), f"{rel(PHASE3)}: checks passed", "count")
    for key in ("committed", "correct_when_committed", "false_abstention", "coverage",
                "best_guess_per_upload_balanced"):
        r.pct(f"suite_{key}", PHASE3, "result", "v4.1", key, fmt="pct2")
    for level in ("class", "group", "lineage", "abstain"):
        r.pct(f"suite_level_{level}", PHASE3, "result", "v4.1", "levels", level)
    for group in ("single", "narrow", "mixed", "lineage", "pbmc", "scope2"):
        for key in ("best_guess_per_upload_balanced", "coverage", "committed", "correct_when_committed"):
            r.pct(f"suite_{group}_{key}", PHASE3, "by_scenario", "v4.1", group, key)
        r.at(f"suite_{group}_cells", PHASE3, ("by_scenario", "v4.1", group, "cells"), "count")
        r.pct(f"suite_{group}_term_used", PHASE3, "correlation_term_used_pct_of_uploads", group)
        r.pct(f"suite_{group}_without", PHASE3, "by_scenario", "v3.1", group, "best_guess_per_upload_balanced")
    r.pct("suite_without_best_guess", PHASE3, "result", "v3.1", "best_guess_per_upload_balanced", fmt="pct2")


def benchmark(r: Records) -> None:
    for key in ("scope2", "pbmc240", "fulcher2026"):
        first = next(x for x in r.csv(INPUTS) if x["dataset"] == key)
        r.put(f"bm_genes_{key}", int(first["n_genes"]), f"{rel(INPUTS)}: n_genes where dataset {key}", "count")
    r.at("bm_genes_v41_fulcher", ASTRAL, ("Fulcher 2026", "features_matched"), "count")
    rows = [x for x in r.csv(PAIRED) if x["dataset"] == "Fulcher 2026"]
    basis = f"{rel(PAIRED)}: dataset Fulcher 2026"
    r.put("bm_fulcher_pairings", len(rows), basis, "count")
    r.put("bm_fulcher_favour", sum(x["favours"] == "v4.1" for x in rows), f"{basis}, favours v4.1", "count")
    r.put("bm_fulcher_lowest_ci", round(min(float(x["ci_lo"]) for x in rows) / 100, 6), f"{basis}, smallest ci_lo",
          "points")
    r.put("bm_baselines", len({x["baseline"] for x in rows}), f"{basis}, distinct baselines", "count")
    for baseline, rule, key in (("correlation", "correlation to class mean", "correlation"),
                                ("pca", "shared kNN", "pca_knn")):
        r.cell(f"bm_fulcher_vs_{key}", PAIRED, "point_estimate_pct", "points", 0.01,
               dataset="Fulcher 2026", baseline=baseline, seed="0", baseline_rule=rule)
    harmony = [float(x["point_estimate_pct"]) for x in rows if x["baseline"] == "harmony"]
    r.put("bm_fulcher_vs_harmony_min", round(min(harmony) / 100, 6), f"{basis}, harmony, smallest", "points")
    r.put("bm_fulcher_vs_harmony_max", round(max(harmony) / 100, 6), f"{basis}, harmony, largest", "points")
    # Khoury, post-hoc: v4.1 against each corrected baseline.
    k = r.csv(KHOURY_PAIRED)
    basis = rel(KHOURY_PAIRED)
    for name, model_b, rule in (("pca", "pca_seed0", "shared_knn"), ("correlation", "correlation_seed0", "correlation"),
                                ("seurat", "seurat_seed0", "native")):
        row = next(x for x in k if x["model_b"] == model_b and x["rule_b"] == rule)
        r.put(f"bm_khoury_vs_{name}", round(float(row["diff_bal_acc_pct"]) / 100, 6), f"{basis}: {model_b}, {rule}", "points")
        r.put(f"bm_khoury_vs_{name}_lo", round(float(row["ci_lo"]) / 100, 6), f"{basis}: {model_b}, {rule}, ci_lo", "points")
        r.put(f"bm_khoury_vs_{name}_hi", round(float(row["ci_hi"]) / 100, 6), f"{basis}: {model_b}, {rule}, ci_hi", "points")
    scanvi = [x for x in k if x["model_b"].startswith("scanvi") and x["rule_b"] == "shared_knn"]
    r.put("bm_khoury_scanvi_knn_runs", len(scanvi), f"{basis}: scANVI, shared kNN", "count")
    r.put("bm_khoury_scanvi_knn_neither", sum(x["favours"] == "neither" for x in scanvi),
          f"{basis}: scANVI, shared kNN, favours neither", "count")
    for prefix, label in (("harmony", "harmony"), ("maxfuse", "maxfuse"), ("scglue", "scglue")):
        values = [float(x["diff_bal_acc_pct"]) for x in k if x["model_b"].startswith(prefix)]
        r.put(f"bm_khoury_vs_{label}_min", round(min(values) / 100, 6), f"{basis}: {label}, smallest", "points")
        r.put(f"bm_khoury_vs_{label}_max", round(max(values) / 100, 6), f"{basis}: {label}, largest", "points")
    ahead = [x for x in k if x["comparison"] != "v4.1 vs v4" and x["comparison"] != "v4.1 vs v3.1"]
    r.put("bm_khoury_baseline_runs", len(ahead), f"{basis}: every baseline run", "count")
    r.put("bm_khoury_baseline_favour", sum(x["favours"] == "v4.1" for x in ahead), f"{basis}: favours v4.1", "count")
    # Where a single baseline does better on a single type (Fulcher, corrected baselines).
    for key, tool, rule, metric in (("cd8_harmony_knn", "harmony", "shared kNN", "recall_CD8T_pct"),
                                    ("dc_pca_nc", "pca", "nearest centroid", "recall_DC_pct"),
                                    ("dc_correlation", "correlation", "correlation to class mean", "recall_DC_pct")):
        r.cell(f"bm_fulcher_{key}", CORRECTED_FULCHER, "mean", "pct1", 0.01, tool=tool, rule=rule, metric=metric)


# ---- 3. Results ----

def transfer(r: Records) -> None:
    r.pct("fulcher_ba", DEVELOPMENT, "fulcher2026", "v4.1", "balanced_accuracy_6_types", fmt="pct2")
    for t in COARSE_TYPES:
        r.pct(f"fulcher_recall_{t}", DEVELOPMENT, "fulcher2026", "v4.1", f"recall_{t}")
    for side in ("lymphoid", "myeloid"):
        r.cell(f"fulcher_{side}", FULCHER_V41, f"{side}_recall_pct", "pct1", 0.01, tool="v4.1 (served)")
    r.pct("khoury_ba", KHOURY, "scores", "v4.1", "balanced_accuracy_pct", fmt="pct2")
    for t in ("CD4T", "CD8T", "NK", "B", "monocyte"):
        r.pct(f"khoury_recall_{t}", KHOURY, "scores", "v4.1", f"recall_{t}_pct")
    r.pct("khoury_lymphoid", KHOURY, "scores", "v4.1", "lymphoid_recall_pct")
    r.pct("khoury_myeloid", KHOURY, "scores", "v4.1", "myeloid_recall_pct")
    r.pct("pbmc240_lymphoid", DEVELOPMENT, "pbmc240", "v4.1", "lymphoid_recall")
    r.pct("pbmc240_myeloid", DEVELOPMENT, "pbmc240", "v4.1", "myeloid_recall")
    r.pct("probe", PROBE, "modality_probe_balanced_accuracy_pct", fmt="pct2")
    for row in r.csv(LATENT_COSINE):
        if row["status"] == "measured":
            r.cell(f"latent_cosine_{row['class_name']}", LATENT_COSINE, "latent_centroid_cosine", "fixed2",
                   class_name=row["class_name"])


def answers(r: Records) -> None:
    for name, key in (("Fulcher 2026", "fulcher"), ("PBMC240", "pbmc240"), ("SCoPE2", "scope2")):
        r.cell(f"committed_{key}", CONFIDENT, "committed_pct", "pct2", 0.01, model="v41", dataset=name)
        r.cell(f"correct_{key}", CONFIDENT, "correct_when_committed_pct", "pct2", 0.01, model="v41", dataset=name)
    r.pct("coverage_target", COVERAGE, "target_pct", fmt="pct1")
    r.pct("coverage_fulcher", COVERAGE, "v41", "fulcher2026", "coverage_pct")
    r.pct("coverage_fulcher_given_set", COVERAGE, "v41", "fulcher2026", "coverage_among_sets_pct")
    r.pct("coverage_pbmc240", COVERAGE, "v41", "pbmc240", "coverage_pct")
    r.pct("coverage_scope2", COVERAGE, "v41", "scope2", "coverage_pct")
    for t in COARSE_TYPES:
        r.pct(f"coverage_fulcher_{t}", COVERAGE, "v41", "fulcher2026", "by_class", t, "coverage_pct")


def second_opinion(r: Records) -> None:
    row = r.row(PAIRED_ABLATION, dataset="Fulcher 2026")
    basis = f"{rel(PAIRED_ABLATION)}: Fulcher 2026"
    r.put("so_fulcher_gain", round(float(row["point_estimate_pct"]) / 100, 6), basis, "points")
    r.put("so_fulcher_gain_lo", round(float(row["ci_lo"]) / 100, 6), f"{basis}, ci_lo", "points")
    r.put("so_fulcher_gain_hi", round(float(row["ci_hi"]) / 100, 6), f"{basis}, ci_hi", "points")
    r.cell("so_khoury_gain", KHOURY_PAIRED, "diff_bal_acc_pct", "points", 0.01, comparison="v4.1 vs v3.1")
    r.cell("so_khoury_gain_lo", KHOURY_PAIRED, "ci_lo", "points", 0.01, comparison="v4.1 vs v3.1")
    r.cell("so_khoury_gain_hi", KHOURY_PAIRED, "ci_hi", "points", 0.01, comparison="v4.1 vs v3.1")
    r.pct("so_khoury_without", KHOURY, "scores", "v3.1", "balanced_accuracy_pct", fmt="pct2")
    r.pct("so_fulcher_without", DEVELOPMENT, "fulcher2026", "v3.1", "balanced_accuracy_6_types", fmt="pct2")
    for key in ("pbmc240", "scope2", "fulcher2026", "furtwangler2025"):
        r.at(f"so_agreement_{key}", GATE, ("datasets", key, "upload_agreement"), "fixed2")
    r.at("so_agreement_khoury", KHOURY, ("upload_agreement",), "fixed2")
    r.pct("so_fulcher_ncv_recall_NK_without", DEVELOPMENT, "fulcher2026", "v3.1", "recall_NK")
    r.pct("so_fulcher_ncv_recall_DC_without", DEVELOPMENT, "fulcher2026", "v3.1", "recall_DC")
    r.pct("so_khoury_nk_without", KHOURY, "scores", "v3.1", "recall_NK_pct")


def heldout(r: Records) -> None:
    hao = HELDOUT / "hao2021" / "summary.json"
    for comparison, key in (("v41 - correlation", "correlation"), ("v41 - pca_knn", "pca"), ("v31 - v41", "without")):
        r.at(f"ho_hao_vs_{key}", hao, ("comparisons", comparison, "mean"), "points", scale=0.01)
        r.at(f"ho_hao_vs_{key}_lower", hao, ("comparisons", comparison, "lower_95_one_sided"), "points", scale=0.01)
    for model, key in (("v41", "model"), ("correlation", "correlation"), ("pca_knn", "pca")):
        r.pct(f"ho_hao_{key}", hao, "by_model", model, "coarse_ba_mean")
    r.pct("ho_hao_dc", hao, "by_model", "v41", "dc_recall")
    r.pct("ho_hao_dc_correlation", hao, "by_model", "correlation", "dc_recall")
    for key in ("pxd043355", "pxd073250", "pxd046211"):
        path = HELDOUT / key / "summary.json"
        r.at(f"ho_{key}_auroc", path, ("candidates", "v4.1", "primary", "auroc"), "fixed3", digits=4)
        r.at(f"ho_{key}_p", path, ("candidates", "v4.1", "primary", "p"), "fixed3", digits=4)
    path = HELDOUT / "pxd043355" / "summary.json"
    for group in ("Jurkat", "HeLa"):
        r.pct(f"ho_pxd043355_abstained_{group}", path, "candidates", "v4.1", "secondary", "abstained_pct_by_group", group)
    r.at("ho_tian_pairs", HELDOUT / "tian" / "summary.json", ("candidates", "v4.1", "primary", "pairs"), "count")
    assert r.json(HELDOUT / "pxd021882" / "summary.json")["void"] is True
    # v4.1 against its own answer path's guess on the held-out donors: the
    # recorded comparison is the other way round, so its sign and bound turn.
    without = r.json(hao)["comparisons"]["v31 - v41"]
    basis = f"{rel(hao)}: comparisons > v31 - v41, negated"
    r.put("ho_hao_gain", round(-without["mean"] / 100, 6), basis, "points")
    r.put("ho_hao_gain_lower", round(-without["upper_95_one_sided"] / 100, 6),
          f"{basis} (its one-sided upper bound becomes this lower bound)", "points")
    # The six sets' outcomes, as their summaries record them.
    outcomes = {"hao2021": "pass" if r.json(hao)["comparisons"]["v41 - correlation"]["lower_95_one_sided"] > 0 else "fail"}
    for key in ("pxd043355", "pxd073250", "pxd046211"):
        primary = r.json(HELDOUT / key / "summary.json")["candidates"]["v4.1"]["primary"]
        outcomes[key] = "void" if primary["void"] else "pass" if primary["pass"] else "fail"
    outcomes["tian"] = "void" if r.json(HELDOUT / "tian" / "summary.json")["candidates"]["v4.1"]["primary"]["void"] else "scored"
    outcomes["pxd021882"] = "void"
    basis = f"{rel(HELDOUT)}/*/summary.json: each set's primary outcome for v4.1"
    for result in ("pass", "fail", "void"):
        r.put(f"ho_{result}", sum(v == result for v in outcomes.values()), basis, "count")
    r.put("ho_sets", len(outcomes), basis, "count")


def robustness(r: Records) -> None:
    # One type uploaded alone, against the same cells in their whole upload.
    for t in ("B", "NK", "monocyte", "CD4T"):
        r.pct(f"single_alone_correct_{t}", SINGLE, "v4.1", "alone", t, "correct_when_committed_pct")
        r.pct(f"single_mixed_correct_{t}", SINGLE, "v4.1", "mixed", t, "correct_when_committed_pct")
    for t in ("CD4T", "CD8T"):
        r.pct(f"single_pair_recall_{t}", SINGLE, "v4.1", "paired", "CD4T+CD8T", t, "recall_pct")
    # Cells outside the reference.
    answers_ = r.json(FURTWANGLER)["answers"]
    r.put("ood_furtwangler_flagged", round(answers_["abstain: outside_supported_region"]["pct"] / 100, 6),
          f"{rel(FURTWANGLER)}: answers > abstain: outside_supported_region (v4.1's answers are these: "
          f"{rel(GATE)}, furtwangler2025, v31_abstentions_differing 0)", "pct1")
    r.pct("ood_furtwangler_committed", DEVELOPMENT, "furtwangler2025", "v4.1", "committed")
    r.pct("ood_furtwangler_progenitor", DEVELOPMENT, "furtwangler2025", "v4.1", "progenitor_share")
    r.pct("ood_furtwangler_t_cell", DEVELOPMENT, "furtwangler2025", "v4.1", "t_cell_share")
    r.at("ood_auroc", DEVELOPMENT, ("out_of_reference_auroc", "v4.1"), "fixed3", digits=4)
    foreign = r.json(FOREIGN)["foreign_development"]
    lines = [k for k in foreign if k.startswith("PXD077946")]
    r.put("ood_lines_flagged_max", round(max(foreign[k]["below_threshold_pct"]["S0"] for k in lines) / 100, 6),
          f"{rel(FOREIGN)}: foreign_development, PXD077946 lines, below_threshold_pct > S0 (served), largest", "pct1")
    r.put("ood_lines_cells", sum(foreign[k]["cells"] for k in lines), f"{rel(FOREIGN)}: PXD077946 lines, cells", "count")
    r.put("ood_lines_answered", sum(n for k in lines for a, n in foreign[k]["v41_served"].items()
                                    if a.startswith("answer:")),
          f"{rel(FOREIGN)}: PXD077946 lines, v41_served answers", "count")
    hmc3 = next(k for k in foreign if k.endswith("HMC3"))
    r.put("ood_hmc3_cells", foreign[hmc3]["cells"], f"{rel(FOREIGN)}: {hmc3}, cells", "count")
    r.put("ood_hmc3_answered", sum(n for a, n in foreign[hmc3]["v41_served"].items() if a.startswith("answer:")),
          f"{rel(FOREIGN)}: {hmc3}, v41_served answers", "count")
    # Astral PBMC runs commit less than the development sets.
    astral = r.json(ASTRAL)
    runs = [k for k in astral if k.startswith("DS1") and "," not in k]  # the files as uploaded, not the probes
    committed = [astral[k]["reasons_pct"]["committed"] for k in runs]
    basis = f"{rel(ASTRAL)}: {', '.join(runs)}, reasons_pct > committed"
    r.put("astral_runs", len(runs), f"{rel(ASTRAL)}: {', '.join(runs)}", "count")
    r.put("astral_committed_min", round(min(committed) / 100, 6), f"{basis}, smallest", "pct1")
    r.put("astral_committed_max", round(max(committed) / 100, 6), f"{basis}, largest", "pct1")
    r.pct("astral_committed_fulcher", ASTRAL, "Fulcher 2026", "reasons_pct", "committed")
    r.pct("astral_committed_subsample", ASTRAL, "Fulcher 2026, 90-cell subsamples", "committed_pct", "median")
    # Donors outside training (one retrained member, not the served ensemble).
    r.at("donor_gap", DONOR, ("mean_gap",), "pp", scale=0.01)
    gaps = [f["gap_seen_minus_unseen"] for f in r.json(DONOR)["folds"].values()]
    r.put("donor_gap_min", round(min(gaps) / 100, 6), f"{rel(DONOR)}: folds, gap_seen_minus_unseen, smallest", "pp")
    r.put("donor_gap_max", round(max(gaps) / 100, 6), f"{rel(DONOR)}: folds, gap_seen_minus_unseen, largest", "pp")
    # CD8 against CD4 T cells: what Khoury's clusters separate, and the reference's labels.
    called = ("khoury_posthoc", "fine_classes_called", "v4.1", "CD8T")
    for label, key in (("naive CD4 T", "naive_cd4"), ("CD4 T", "cd4"), ("CD8 T", "cd8")):
        r.pct(f"cd8_called_{key}", CD8_CD4, *called, label)
    auc = ("khoury_posthoc", "auc_cd8_cluster_vs_cd4_cluster")
    r.at("cd8_auc_cd8a", CD8_CD4, auc + ("CD8A", "auc_cd8_cluster"), "fixed2")
    for marker in ("S100A4", "ANXA1"):
        value = dig(r.json(CD8_CD4), auc + (marker, "auc_cd8_cluster"))
        r.put(f"cd8_auc_{marker.lower()}", round(1 - value, 4),
              f"{rel(CD8_CD4)}: {' > '.join(auc)} > {marker}, 1 - auc_cd8_cluster (higher in the CD4 cluster)", "fixed2")
    r.at("cd8_naive_like", CD8_CD4, ("reference", "naive_cd8_like_cells"), "count")
    r.at("cd8_naive_like_in_cd4", CD8_CD4, ("reference", "naive_cd8_like_by_class", "CD4 T"), "count")
    # Markers the gene space lacks are rarely measured in single cells anyway.
    rows = r.csv(MARKERS)
    absent = [x for x in rows if x["in_feature_space"] == "False"]
    detected = [float(v) for x in absent for k, v in x.items() if k not in ("marker", "in_feature_space") and v]
    basis = f"{rel(MARKERS)}: markers not in the feature space"
    r.put("markers_checked", len(rows), f"{rel(MARKERS)}: rows", "count")
    r.put("markers_datasets", len(rows[0]) - 2, f"{rel(MARKERS)}: dataset columns", "count")
    r.put("markers_absent", len(absent), basis, "count")
    r.put("markers_absent_max", round(max(detected) / 100, 6), f"{basis}, largest share of cells detected", "pct1")


def negative(r: Records) -> None:
    arm = r.row(RESEARCH_ARM, arm="v4.1 + Harmony NC", beta="0.3300")
    basis = f"{rel(RESEARCH_ARM)}: v4.1 + Harmony NC, beta 0.33"
    r.put("neg_stack_fulcher", round(float(arm["fulcher"]) / 100, 6), basis, "pct2")
    r.put("neg_stack_pbmc", round(float(arm["pbmc240_lymphoid"]) / 100, 6), basis, "pct1")
    r.at("neg_energy_false", NB3B, ("eval_chosen", "false_abstention"), "pct1")
    r.at("neg_energy_scrambled", NB3B, ("eval_chosen", "rejected_scrambled"), "pct1")
    r.at("neg_energy_rule_false", NB3B, ("rules", "go", "false_overall"), "pct1")
    r.at("neg_energy_rule_scrambled", NB3B, ("rules", "go", "scrambled_rejected"), "pct1")
    r.at("neg_band_false", NB3C, ("eval_chosen", "false_abstention"), "pct1")
    r.at("neg_band_worst", NB3C, ("eval_chosen", "worst_scenario"), "pct1")
    r.at("neg_band_scrambled", NB3C, ("eval_chosen", "rejected_scrambled"), "pct1")
    tuning = r.json(FOREIGN)["tuning_mean"]
    r.put("neg_protein_score_gain", round(tuning["S2"] - tuning["S0"], 4),
          f"{rel(FOREIGN)}: tuning_mean S2 - S0", "fixed3")
    r.at("neg_relabelled_khoury", KHOURY_RELABELLED, ("v51_minus_v41", "point"), "points", scale=0.01)
    r.at("neg_relabelled_khoury_lo", KHOURY_RELABELLED, ("v51_minus_v41", "ci_95", 0), "points", scale=0.01)
    r.at("neg_relabelled_khoury_hi", KHOURY_RELABELLED, ("v51_minus_v41", "ci_95", 1), "points", scale=0.01)
    r.pct("neg_relabelled_cd8", KHOURY_RELABELLED, "scores", "v5.1", "recall_CD8T_pct")
    r.at("neg_relabelled_scope2_drop", V51_PHASE4, ("scenario_drop_vs_v41", "scope2"), "pp", scale=0.01)
    hao = HELDOUT / "hao2021" / "summary.json"
    r.at("neg_relabelled_hao", hao, ("comparisons", "v52 - v41", "mean"), "points", scale=0.01)
    r.at("neg_relabelled_hao_lower", hao, ("comparisons", "v52 - v41", "lower_95_one_sided"), "points", scale=0.01)
    r.at("neg_protein_means_khoury", KHOURY_PROTEIN_MEANS, ("v42_minus_v41", "point"), "points", scale=0.01)
    r.at("neg_protein_means_khoury_lo", KHOURY_PROTEIN_MEANS, ("v42_minus_v41", "ci_95", 0), "points", scale=0.01)
    r.at("neg_protein_means_khoury_hi", KHOURY_PROTEIN_MEANS, ("v42_minus_v41", "ci_95", 1), "points", scale=0.01)
    r.pct("neg_dc_before", HAO_DC, "hao_suite_mean", "v4.1", "dc_recall")
    r.pct("neg_dc_after", HAO_DC, "hao_suite_mean", "v4.1+DC", "dc_recall")
    r.pct("neg_narrow_single_flagged", NARROW, "simulated_flagged_pct_by_group", "single")
    r.pct("neg_narrow_mixed_flagged", NARROW, "simulated_flagged_pct_by_group", "mixed")
    assert r.json(NARROW)["pass_rule_met"] is False and r.json(HAO_DC)["verdicts"]["v4.1+DC"]["GO"] is False
    assert r.json(FOREIGN)["GO"] is False and r.json(V51_PHASE4)["go"] is False


def waiting(r: Records) -> None:
    r.wait("open_sorted_test", "External test",
           "Sorted CD4/CD8 single cells, requested by email; protocol research/benchmark/protocol-sorted-cd4cd8.md")
    r.wait("open_khoury_committed", "Khoury post-hoc",
           "v4.1's committed share and correct-when-committed on Khoury are not recorded")
    r.wait("open_probe_v41", "Diagnostics", "the modality probe has not been run on v4.1's fused best guess")
    r.wait("open_doi", "Release protocol", "a DOI needs the owner's archive account")


def build(manifest: dict | None = None, workflow: dict | None = None) -> dict:
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text(encoding="utf-8"))
    workflow = workflow if workflow is not None else json.loads(WORKFLOW.read_text(encoding="utf-8"))
    if workflow["built_for"]["atlas_version"] != manifest["atlas_version"] or \
            workflow["built_for"]["model_name"] != manifest["model"]["name"]:
        raise SystemExit(f"{rel(WORKFLOW)} was built for {workflow['built_for']}, not the manifest's release: "
                         "run python scripts/build_manifest.py")
    if not manifest["model"]["name"].endswith("v4.1"):
        raise SystemExit("the Manuscript page describes v4.1; the manifest's model is "
                         f"{manifest['model']['name']}: rewrite the page before rebuilding its data")
    r = Records()
    reference(r)
    gene_space(r)
    from_workflow(r, workflow)
    answer_layer(r)
    rationale(r)
    datasets(r)
    suite(r)
    benchmark(r)
    transfer(r)
    answers(r)
    second_opinion(r)
    heldout(r)
    robustness(r)
    negative(r)
    waiting(r)
    sources = sorted(r.sources | {WORKFLOW}, key=rel)
    return {
        "schema_version": SCHEMA_VERSION,
        "built_for": {"atlas_version": manifest["atlas_version"], "model_name": manifest["model"]["name"]},
        "sources": {rel(p): sha256(p) for p in sources},
        "records": dict(sorted(r.records.items())),
    }


def write(manuscript: dict) -> int:
    data = (json.dumps(manuscript, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    OUTPUT.write_bytes(data)
    return len(data)


def main() -> None:
    size = write(build())
    print(f"Wrote {rel(OUTPUT)} ({size:,} bytes)")


if __name__ == "__main__":
    main()
