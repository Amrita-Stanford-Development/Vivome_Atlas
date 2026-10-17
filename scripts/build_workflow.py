"""Builds web/data/workflow.json, the Workflow page's companion to the
manifest (web/workflow.html; docs/web/workflow.md).

Standard library only, deterministic. scripts/build_manifest.py calls
build() at the end of its main, so the two files are always built
together, and workflow.json's `built_for` must equal the manifest's release.
It reads:
- the trace of the PBMC240 example through the served model
  (service/model/evidence/workflow/, written by scripts/trace_workflow.py);
- the reference's atlas coordinates (web/data/metadata_RNA_lat128.csv), for
  a stratified sample of points and the class centres;
- the gene space's records (service/model/evidence/feature_space_*,
  service/model/runtime/gene_id_map_v1_provenance.json);
- the training recipe (research/notebook-outputs/nb2/nb1b_core.py's
  train_variant defaults, research/notebooks/v5_train.py's arguments and its
  reproduction record) and the encoder choice (decisive_summary.json);
- the evaluation records: v4.1's pre-registered suite, conformal coverage
  on RNA and protein, and the
  internal held-out test (research/benchmark/heldout/);
- the hosted service's settings (deploy/huggingface/PUBLISH.md,
  service/config.py, web/project.html).

Every number a page sentence cites is a record in `facts`, measured with its
basis or pending, so web/js/workflow-data.js shows it through the same
isMeasured guard as the manifest. The arrays the figures draw are raw data
from the same sources.

    python scripts/build_workflow.py      # from the repository root (build_manifest.py also runs it)
"""
from __future__ import annotations

import ast
import csv
import gzip
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "web" / "data" / "workflow.json"
MANIFEST = REPO / "web" / "data" / "atlas_manifest.json"
TRACE = REPO / "service" / "model" / "evidence" / "workflow" / "pbmc240_trace_v41.json.gz"
SNIPPETS = REPO / "service" / "model" / "evidence" / "workflow" / "input_snippets.json"
ATLAS_RNA = REPO / "web" / "data" / "metadata_RNA_lat128.csv"
FEATURE_PROVENANCE = REPO / "service" / "model" / "evidence" / "feature_space_provenance.json"
FEATURE_DETAIL = REPO / "service" / "model" / "evidence" / "feature_space_detail.csv"
GENE_ID_PROVENANCE = REPO / "service" / "model" / "runtime" / "gene_id_map_v1_provenance.json"
DECISIVE = REPO / "service" / "model" / "runtime" / "decisive_summary.json"
CORE = REPO / "research" / "notebook-outputs" / "nb2" / "nb1b_core.py"
TRAIN = REPO / "research" / "notebooks" / "v5_train.py"
REPRODUCE = REPO / "research" / "notebook-outputs" / "v5_train" / "reproduce.json"
SPEC_V31 = REPO / "service" / "model" / "v3_1" / "nb2_spec_v31.json"
SPEC_SERVED = REPO / "service" / "model" / "v4_1" / "spec_v41.json"  # the served model's spec (v4.1)
PHASE3 = REPO / "research" / "notebook-outputs" / "v41_phase3"
RNA_COVERAGE = REPO / "research" / "notebook-outputs" / "nb2" / "tables" / "eval_per_class_coverage.csv"
PROTEIN_COVERAGE = REPO / "research" / "notebook-outputs" / "protein_coverage" / "coverage.json"
HELDOUT = REPO / "research" / "benchmark" / "heldout"
ASTRAL = REPO / "research" / "notebook-outputs" / "astral_abstention" / "summary.json"
PUBLISH = REPO / "deploy" / "huggingface" / "PUBLISH.md"
SERVICE_CONFIG = REPO / "service" / "config.py"
PROJECT_PAGE = REPO / "web" / "project.html"

SCHEMA_VERSION = "1"
READING_STAGES = ("parse", "scale", "collapse", "ids", "align")
SIZE_BUDGET = 900_000  # bytes; scripts/test_build_workflow.py enforces it
SAMPLE_POINTS, SAMPLE_FLOOR, SAMPLE_SEED = 6000, 60, 0
GENE_SOURCES = (  # feature_space_detail.csv's columns, as the page names them
    ("bubis_hela", "Bubis et al. 2025, HeLa", "gene space only"),
    ("bubis_lung", "Bubis et al. 2025, lung lines", "gene space only"),
    ("bubis_candidates", "Bubis et al. 2025, candidates", "gene space only"),
    ("pbmc240", "PBMC240", "development; the example traced here"),
    ("scope2", "SCoPE2", "development"),
    ("fulcher", "Fulcher 2026", "development; chose v4.1's one tuned weight"),
)
HELDOUT_SETS = (  # (folder, the question in words, positive group, negative group, score column)
    ("pxd043355", "Is a T-cell line (Jurkat) more blood-like than HeLa?", "Jurkat", "HeLa", "v41_similarity"),
    ("pxd073250", "Are immune cells more blood-like than keratinocytes from the same tumour?", "immune",
     "keratinocyte", "v41_similarity"),
    ("pxd046211", "Do PMA-treated monocyte lines lean to macrophage over untreated ones?", "PMA", "untreated",
     "v41_score"),
)


def measured(value, basis: str, fmt: str = "count") -> dict:
    return {"value": value, "status": "measured", "basis": basis, "format": fmt}


def pending(phase: str, note: str) -> dict:
    return {"value": None, "status": "pending", "phase": phase, "note": note}


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ---- the reference: a sample of the atlas, and the class centres ----

def reference(class_order: list[str], hierarchy: dict) -> dict:
    """A stratified sample of the atlas's RNA cells (web/data/
    metadata_RNA_lat128.csv), ordered so that any prefix holds every class in
    proportion: a phone can draw the first 2,500 and still see all of them.
    Coordinates are stored as integers, thousandths of a PC unit."""
    rows = read_csv(ATLAS_RNA)
    position = {name: i for i, name in enumerate(class_order)}
    by_class: dict[int, list[list[float]]] = {}
    for row in rows:
        by_class.setdefault(position[row["class_name"]], []).append(
            [float(row["PC1"]), float(row["PC2"]), float(row["PC3"])])
    total = len(rows)
    rng = random.Random(SAMPLE_SEED)
    quota = {c: min(len(v), max(SAMPLE_FLOOR, round(SAMPLE_POINTS * len(v) / total))) for c, v in by_class.items()}
    keyed = []
    for c in sorted(by_class):
        points = by_class[c][:]
        rng.shuffle(points)
        n = quota[c]
        keyed += [(i / n, c, p) for i, p in enumerate(points[:n])]  # every class leads with one point
    keyed.sort(key=lambda item: (item[0], item[1]))
    centres = []
    for c in range(len(class_order)):
        pts = by_class.get(c, [])
        centres.append([round(1000 * sum(p[k] for p in pts) / len(pts)) for k in range(3)] if pts else None)
    return {
        "basis": f"{rel(ATLAS_RNA)}: the coordinate member's PCA, as the atlas page draws it",
        "classes": [{"name": name, "group": hierarchy[name]["group"], "lineage": hierarchy[name]["lineage"],
                     "cells": measured(len(by_class.get(i, [])), rel(ATLAS_RNA))}
                    for i, name in enumerate(class_order)],
        "total": measured(total, rel(ATLAS_RNA)),
        "sample_rule": f"each class in proportion to its size out of {SAMPLE_POINTS:,}, with at least "
                       f"{SAMPLE_FLOOR} cells (all of a smaller class); shuffled with seed {SAMPLE_SEED} and "
                       "ordered so every prefix is stratified",
        "sampled": measured(len(keyed), rel(ATLAS_RNA)),
        "sample": [[round(1000 * p[0]), round(1000 * p[1]), round(1000 * p[2]), c] for _, c, p in keyed],
        "centres": centres,
    }


# ---- the gene space ----

def gene_space(trace: dict) -> dict:
    prov = json.loads(FEATURE_PROVENANCE.read_text(encoding="utf-8"))
    ids = json.loads(GENE_ID_PROVENANCE.read_text(encoding="utf-8"))
    detail = read_csv(FEATURE_DETAIL)
    keys = [k for k, _, _ in GENE_SOURCES]
    combos = Counter("".join("1" if row[k] == "True" else "0" for k in keys) for row in detail)
    basis = rel(FEATURE_PROVENANCE)
    genes = sorted(detail, key=lambda row: row["gene"])
    flags = [int("".join("1" if row[k] == "True" else "0" for k in keys), 2) for row in genes]
    return {
        "sources": [{"key": k, "name": name, "role": role,
                     "genes": measured(sum(row[k] == "True" for row in detail), rel(FEATURE_DETAIL))}
                    for k, name, role in GENE_SOURCES],
        "funnel": {
            "union": measured(prov["union_raw"], basis),
            "ig_tcr_excluded": measured(prov["ig_tcr_excluded"], basis),
            "union_without_ig_tcr": measured(prov["union_no_ig"], basis),
            "rna_genes": measured(prov["rna_genes"], basis),
            "feature_space": measured(prov["feature_space"], basis),
            "old_reference": measured(prov["old_reference"], basis),
            "newly_added": measured(prov["newly_added"], basis),
        },
        "combinations": [{"sources": combo, "genes": n} for combo, n in sorted(combos.items(), key=lambda kv: (-kv[1], kv[0]))],
        "id_matching": {k: measured(v, rel(GENE_ID_PROVENANCE)) for k, v in ids["match_counts"].items()},
        "id_source": {"name": ids["source"]["name"], "downloaded": ids["source"]["downloaded"]},
        "modules": measured(trace["stages"]["encoder"]["modules"], "the encoders' gene-to-module assignment (buffer A)"),
        "module_sizes": trace["stages"]["encoder"]["module_sizes"],
        # Packed for the gene lookup: one name per gene, sorted, and its
        # sources as a bit field in GENE_SOURCES order (first source = top bit).
        "genes": [row["gene"] for row in genes],
        "gene_flags": flags,
        "source_order": keys,
    }


# ---- training ----

def _defaults(source: str, function: str) -> dict:
    """A function's keyword defaults, read from its source with ast (no import, no torch)."""
    tree = ast.parse(source)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
    args = node.args.kwonlyargs
    return {a.arg: ast.literal_eval(d) for a, d in zip(args, node.args.kw_defaults)
            if d is not None and not isinstance(d, ast.Name)}


def training(trace: dict) -> dict:
    core = CORE.read_text(encoding="utf-8")
    d = _defaults(core, "train_variant")
    sizes = [int(x) for x in re.search(r"rng\.choice\(\[([\d, ]+)\]\)", core).group(1).split(",")]
    train = TRAIN.read_text(encoding="utf-8")
    std = re.search(r'std="(\w+)"', train).group(1)
    sampler = re.search(r'sampler="(\w+)"', train).group(1)
    reproduce = json.loads(REPRODUCE.read_text(encoding="utf-8"))
    decisive = json.loads(DECISIVE.read_text(encoding="utf-8"))
    v31 = json.loads(SPEC_V31.read_text(encoding="utf-8"))
    served = json.loads(SPEC_SERVED.read_text(encoding="utf-8"))
    recipe = f"{rel(CORE)}, train_variant's defaults; {rel(TRAIN)}'s arguments"
    return {
        "recipe": {
            "epochs": measured(d["epochs"], recipe), "batch": measured(d["bs"], recipe),
            "learning_rate": measured(d["lr"], recipe, "plain"), "weight_decay": measured(d["wd"], recipe, "plain"),
            "patience": measured(d["patience"], recipe),
            "coverage_low": measured(d["cov_range"][0], recipe, "percent"),
            "coverage_high": measured(d["cov_range"][1], recipe, "percent"),
            "validation_coverage": measured(d["val_cov"], recipe, "percent"),
            "hidden": [measured(h, recipe) for h in d["hidden"]], "latent": measured(d["latent"], recipe),
            "dropout": measured(d["dropout"], recipe, "plain"),
            "natural_share": measured(d["p_natural"], recipe, "percent"),
            "loss_weights": {"cross_entropy": measured(d["w_ce"], recipe, "plain"),
                             "supervised_contrastive": measured(d["w_supcon"], recipe, "plain"),
                             "hubness": measured(d["w_hub"], recipe, "plain"),
                             "consistency": measured(d["w_consist"], recipe, "plain")},
            "contrastive_temperature": measured(d["temp"], recipe, "plain"),
            "margin": measured(d["margin"], recipe, "plain"),
            "standardisation": std, "sampler": sampler,
            "mini_upload_classes": sizes,
        },
        "reproduction": {
            "recorded_loss": measured(round(reproduce["recorded_best_val_loss"], 4), rel(REPRODUCE), "fixed4"),
            "retrained_loss": measured(round(reproduce["retrained"]["best_val_loss"], 4), rel(REPRODUCE), "fixed4"),
            "passed": reproduce["passed"], "seed": reproduce["seed"],
        },
        "encoder_choice": {
            "candidates": [{"name": name, "balanced_accuracy": measured(round(v / 100, 6), rel(DECISIVE), "percent"),
                            "seed_sd": measured(round(decisive["seed_sd"][name] / 100, 6), rel(DECISIVE), "percent")}
                           for name, v in decisive["mean_bal_acc_realistic_coverage"].items()],
            "seeds": measured(decisive["n_seeds"], rel(DECISIVE)),
            "decisively_separated": decisive["decisively_separated"],
            "target_module_size": measured(decisive["target_module_size"], rel(DECISIVE)),
        },
        "members": [{"name": name, "answer_temperature": measured(round(v31["assignment"]["temperature"][name], 4),
                                                                   rel(SPEC_V31), "fixed4"),
                     "guess_temperature": measured(round(served["best_guess"]["temperature"][name], 4),
                                                   rel(SPEC_SERVED), "fixed4")}
                    for name in v31["encoder"]["members"]],
        "history": pending("not recorded",
                           "per-epoch curves of the served members are on Drive, not in this repository"),
        "parameters": measured(trace["stages"]["encoder"]["parameters"],
                               "the coordinate member's checkpoint, counted by scripts/trace_workflow.py"),
    }


# ---- evaluation ----

def _auroc_and_curve(positive: list[float], negative: list[float]) -> tuple[float, list[list[float]]]:
    wins = sum((p > n) + 0.5 * (p == n) for p in positive for n in negative)
    auroc = wins / (len(positive) * len(negative))
    scores = sorted(set(positive) | set(negative), reverse=True)
    curve = [[0.0, 0.0]]
    for s in scores:
        curve.append([round(sum(n >= s for n in negative) / len(negative), 4),
                      round(sum(p >= s for p in positive) / len(positive), 4)])
    return auroc, curve


def _histogram(values: list[float], lo: float, hi: float, bins: int = 20) -> list[int]:
    counts = [0] * bins
    for v in values:
        counts[min(bins - 1, max(0, int((v - lo) / (hi - lo) * bins)))] += 1
    return counts


def heldout() -> list[dict]:
    cards = []
    hao = json.loads((HELDOUT / "hao2021" / "summary.json").read_text(encoding="utf-8"))
    comparison = hao["comparisons"]["v41 - correlation"]
    basis = rel(HELDOUT / 'hao2021' / 'summary.json')
    cards.append({
        "key": "hao2021", "question": "Does typing hold on held-out donors of another blood atlas (RNA made protein-like)?",
        "result": "pass", "statistic": "coarse balanced accuracy minus the correlation baseline's, one-sided 95% lower bound",
        "value": measured(round(comparison["mean"] / 100, 6), basis, "points"),
        "lower": measured(round(comparison["lower_95_one_sided"] / 100, 6), basis, "points"),
        "donors": hao["donors"],
        "scores": {k: measured(round(hao["by_model"][m]["coarse_ba_mean"] / 100, 6), basis, "percent")
                   for k, m in (("model", "v41"), ("correlation", "correlation"), ("pca_knn", "pca_knn"))},
    })
    for key, question, pos, neg, column in HELDOUT_SETS:
        summary = json.loads((HELDOUT / key / "summary.json").read_text(encoding="utf-8"))
        primary = summary["candidates"]["v4.1"]["primary"]
        rows = [r for r in read_csv(HELDOUT / key / "scores.csv") if r["scored"] == "True" and r[column] != ""]
        p = [float(r[column]) for r in rows if r["group"] == pos]
        n = [float(r[column]) for r in rows if r["group"] == neg]
        auroc, curve = _auroc_and_curve(p, n)
        assert abs(auroc - primary["auroc"]) < 6e-5, f"{key}: AUROC {auroc} against the recorded {primary['auroc']}"
        lo, hi = min(p + n), max(p + n)
        basis = rel(HELDOUT / key / "summary.json")
        cards.append({
            "key": key, "question": question, "result": "pass" if primary["pass"] else "fail",
            "statistic": primary["statistic"],
            "value": measured(primary["auroc"], basis, "fixed2"), "p": measured(primary["p"], basis, "fixed3"),
            "groups": {pos: len(p), neg: len(n)},
            "curve": curve, "range": [round(lo, 4), round(hi, 4)],
            "histograms": {pos: _histogram(p, lo, hi), neg: _histogram(n, lo, hi)},
        })
    tian = json.loads((HELDOUT / "tian" / "summary.json").read_text(encoding="utf-8"))
    cards.append({"key": "tian", "question": "Are sorted CD8 T bulks scored more CD8-like than their CD4 pairs?",
                  "result": "void", "statistic": tian["candidates"]["v4.1"]["primary"]["statistic"],
                  "reason": f"{tian['candidates']['v4.1']['primary']['reason']}: the deposit holds "
                            f"{tian['candidates']['v4.1']['primary']['pairs']} matched pair"})
    pools = json.loads((HELDOUT / "pxd021882" / "summary.json").read_text(encoding="utf-8"))
    cards.append({"key": "pxd021882", "question": "Are B-cell pools told from T-cell pools?", "result": "void",
                  "reason": "the deposited table holds no B or T pools"})
    assert pools["void"] is True
    return cards


def evaluation() -> dict:
    basis = f"{rel(PHASE3 / 'eval_by_scenario.csv')}: v4.1's pre-registered evaluation"
    scenarios = [{"group": r["group"], "cells": measured(int(r["cells"]), basis),
                  **{k: measured(round(float(r[k]) / 100, 6), basis, "percent")
                     for k in ("committed", "correct_when_committed", "best_guess_per_upload_balanced", "coverage")}}
                 for r in read_csv(PHASE3 / "eval_by_scenario.csv") if r["method"] == "v4.1"]
    upload_rows = read_csv(PHASE3 / "eval_uploads.csv")
    uploads = [[r["group"], float(r["agreement"]), r["correlation_term"] == "used"] for r in upload_rows]
    thresholds = {float(r["agreement_threshold"]) for r in upload_rows}
    assert len(thresholds) == 1, f"{rel(PHASE3 / 'eval_uploads.csv')} mixes agreement thresholds" 
    rna = [{"class": r[""], "cells": int(r["n"]), "coverage": round(float(r["coverage"]) / 100, 4)}
           for r in read_csv(RNA_COVERAGE)]
    protein = json.loads(PROTEIN_COVERAGE.read_text(encoding="utf-8"))
    fulcher = protein["v41"]["fulcher2026"]
    return {
        "scenarios": scenarios,
        "uploads": {"basis": rel(PHASE3 / "eval_uploads.csv"),
                    "threshold": measured(thresholds.pop(), rel(PHASE3 / "eval_uploads.csv"), "percent"),
                    "rows": uploads, "count": measured(len(uploads), rel(PHASE3 / "eval_uploads.csv")),
                    "used": measured(sum(u[2] for u in uploads), rel(PHASE3 / "eval_uploads.csv"))},
        "coverage": {
            "target": measured(round(protein["target_pct"] / 100, 4), rel(PROTEIN_COVERAGE), "percent"),
            "rna": {"basis": rel(RNA_COVERAGE), "classes": rna},
            "protein": {"basis": f"{rel(PROTEIN_COVERAGE)}, v4.1's sets",
                        "fulcher": measured(round(fulcher["coverage_pct"] / 100, 4), rel(PROTEIN_COVERAGE), "percent"),
                        "classes": {k: round(v["coverage_pct"] / 100, 4) for k, v in fulcher["by_class"].items()}},
        },
        "heldout": heldout(),
    }


# ---- the hosted service ----

def service() -> dict:
    command = next(line for line in PUBLISH.read_text(encoding="utf-8").splitlines()
                   if line.startswith("gcloud run deploy"))
    flag = lambda name: re.search(rf"--{name} (\S+)", command).group(1)  # noqa: E731
    config = SERVICE_CONFIG.read_text(encoding="utf-8")
    env = lambda name: re.search(rf'"{name}", "([^"]+)"', config).group(1)  # noqa: E731
    url = re.search(r"DEFAULT_SERVICE_URL = '([^']+)'", PROJECT_PAGE.read_text(encoding="utf-8")).group(1)
    basis = rel(PUBLISH)
    return {
        "url": url, "platform": "Google Cloud Run", "region": flag("region"),
        "memory": flag("memory"), "cpu": measured(int(flag("cpu")), basis),
        "max_instances": measured(int(flag("max-instances")), basis),
        "min_instances": measured(int(flag("min-instances")), basis),
        "concurrency": measured(int(flag("concurrency")), basis),
        "timeout_seconds": measured(int(flag("timeout")), basis),
        "max_cells": measured(int(env("VIVOME_MAX_UPLOAD_CELLS")), rel(SERVICE_CONFIG)),
        "max_mb": measured(int(float(env("VIVOME_MAX_UPLOAD_MB"))), rel(SERVICE_CONFIG)),
        "concurrent_projections": measured(int(env("VIVOME_MAX_CONCURRENT_PROJECTIONS")), rel(SERVICE_CONFIG)),
        "endpoints": ["GET /api/status", "POST /api/project"],
    }


# ---- the page's facts ----

def facts(trace: dict, manifest: dict) -> dict:
    s = trace["stages"]
    t = rel(TRACE)
    f = {
        "rows": measured(s["parse"]["rows"], t), "runs": measured(s["parse"]["runs"], t),
        "missing_share": measured(s["parse"]["missing_share"], t, "percent"),
        "median_linear": measured(s["scale"]["median_observed"], t, "plain"),
        "scale_threshold": measured(s["scale"]["threshold"], "service/config.py, LINEAR_SCALE_MEDIAN_THRESHOLD", "plain"),
        "rows_after_collapse": measured(s["collapse"]["rows_after"], t),
        "genes_merged": measured(s["collapse"]["genes_merged"], t),
        "ids_matched": measured(s["ids"]["matched"], t), "ids_unmapped": measured(s["ids"]["unmapped"], t),
        "ids_ambiguous": measured(s["ids"]["ambiguous"], t),
        "matched": measured(s["align"]["matched"], t), "unmatched_rows": measured(s["align"]["unmatched_rows"], t),
        "feature_space": measured(s["align"]["feature_space"], t),
        "observed_median": measured(s["align"]["observed_median"], t),
        "floor": measured(s["align"]["floor"], "service/config.py, MIN_OBSERVED_GENES (provisional)"),
        "below_floor": measured(s["align"]["below_floor"], t),
        "smoothing_k": measured(s["smoothing"]["k"], "service/config.py, SMOOTHING_K"),
        "smoothing_alpha": measured(s["smoothing"]["alpha"], "service/config.py, SMOOTHING_ALPHA", "percent"),
        "smoothing_pca": measured(s["smoothing"]["pca_components"], t),
        "smoothing_own": measured(round(1 - s["smoothing"]["alpha"], 6), "service/config.py, 1 - SMOOTHING_ALPHA", "percent"),
        "transfer_k": measured(len(trace["detail"][0]["neighbours"]), "service/config.py, TRANSFER_K, as traced"),
        "members": measured(len(s["encoder"]["members"]), t),
        "genes": measured(s["encoder"]["genes"], t), "modules": measured(s["encoder"]["modules"], t),
        "input_width": measured(s["encoder"]["layers"][0]["width"], t),
        "hidden1": measured(s["encoder"]["layers"][1]["width"], t),
        "hidden2": measured(s["encoder"]["layers"][2]["width"], t),
        "latent": measured(s["encoder"]["layers"][3]["width"], t),
        "parameters": measured(s["encoder"]["parameters"], t),
        "agreement": measured(s["fusion"]["agreement"], t, "percent"),
        "agreement_threshold": measured(s["fusion"]["threshold"], rel(SPEC_SERVED), "percent"),
        "counted": measured(s["fusion"]["counted"], t), "agreeing": measured(s["fusion"]["agreeing"], t),
        "weight_flat": measured(s["fusion"]["encoder_weight_flat"], rel(SPEC_SERVED), "plain"),
        "weight_used": measured(s["fusion"]["encoder_weight_used"], rel(SPEC_SERVED), "plain"),
        "correlation_temperature": measured(s["fusion"]["correlation_temperature"], rel(SPEC_SERVED), "plain"),
        "smoothed_share": measured(s["fusion"]["smoothed_share"], rel(SPEC_SERVED), "percent"),
        "target_coverage": measured(round(1 - s["calibration"]["alpha"], 4), "service/model/v3_1/nb2_spec_v31.json", "percent"),
        "ood_threshold": measured(round(s["ood"]["threshold"], 4), "service/model/v3_1/nb2_spec_v31.json", "fixed3"),
        "classes": measured(len(trace["class_order"]), t),
        "rna_cells": measured(manifest["modalities"]["rna"]["cells"], "web/data/atlas_manifest.json"),
    }
    for kind, n in trace["outcomes"].items():
        f[f"outcome_{kind}"] = measured(n, t)
    committed = sum(trace["outcomes"][k] for k in ("class", "group", "lineage"))
    f["committed"] = measured(committed, t)
    f["committed_share"] = measured(round(committed / len(trace["cells"]), 4), t, "percent")
    return f


def build(manifest: dict | None = None) -> dict:
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text(encoding="utf-8"))
    trace = json.loads(gzip.decompress(TRACE.read_bytes()))
    snippets = json.loads(SNIPPETS.read_text(encoding="utf-8"))
    built_for = {"atlas_version": manifest["atlas_version"], "model_name": manifest["model"]["name"],
                 "pipeline_version": trace["built_for"]["pipeline_version"]}
    if trace["built_for"]["atlas_version"] != manifest["atlas_version"] or \
            not manifest["model"]["name"].endswith(trace["built_for"]["pipeline_version"]):
        raise SystemExit(f"{rel(TRACE)} was traced for {trace['built_for']}, not the manifest's "
                         f"{manifest['atlas_version']} / {manifest['model']['name']}: re-run scripts/trace_workflow.py")
    astral = json.loads(ASTRAL.read_text(encoding="utf-8"))["PBMC240"]
    s = trace["stages"]["align"]
    if (s["matched"], s["unmatched_rows"]) != (astral["features_matched"], astral["features_unmatched"]):
        raise SystemExit(f"the trace's gene matching disagrees with {rel(ASTRAL)}")
    sources = [TRACE, SNIPPETS, ATLAS_RNA, FEATURE_PROVENANCE, FEATURE_DETAIL, GENE_ID_PROVENANCE, DECISIVE, CORE,
               TRAIN, REPRODUCE, SPEC_V31, SPEC_SERVED, PHASE3 / "eval_by_scenario.csv", PHASE3 / "eval_uploads.csv",
               RNA_COVERAGE, PROTEIN_COVERAGE, ASTRAL, PUBLISH, SERVICE_CONFIG]
    sources += sorted(HELDOUT.glob("*/summary.json")) + sorted(HELDOUT.glob("*/scores.csv"))
    workflow = {
        "schema_version": SCHEMA_VERSION,
        "built_for": built_for,
        "sources": {rel(p): sha256(p) for p in sources},
        "facts": facts(trace, manifest),
        "reference": reference(trace["class_order"], trace["hierarchy"]),
        "class_order": trace["class_order"],
        "gene_space": gene_space(trace),
        "raw": {"pbmc240": {k: trace["stages"][k] for k in READING_STAGES},
                "snippets": snippets},
        "training": training(trace),
        # The file-reading stages are under raw.pbmc240; the rest of the trace here.
        "trace": {"stages": {k: v for k, v in trace["stages"].items() if k not in READING_STAGES},
                  **{k: trace[k] for k in ("outcomes", "cells", "story", "detail", "heatmap")}},
        "evaluation": evaluation(),
        "service": service(),
    }
    return workflow


def write(workflow: dict) -> int:
    data = (json.dumps(workflow, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    OUTPUT.write_bytes(data)
    return len(data)


def main() -> None:
    size = write(build())
    print(f"Wrote {rel(OUTPUT)} ({size:,} bytes)")


if __name__ == "__main__":
    main()
