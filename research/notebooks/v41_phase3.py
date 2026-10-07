"""v4.1, Phase C (research/todo.md, Track G): v4.1's pre-registered
evaluation, scored once. Modelled on research/notebooks/v4_phase3c.py.

v4.1 is v4 with the encoder weighted 0.5 instead of 0.7 where the
correlation term is used (service/model/v4_1/spec_v41.json). The weight was
chosen on Fulcher 2026 under fixed rules (Phase A,
research/notebooks/v41_pretest.py) and checked once on Khoury 2026 (Phase B,
benchmark/khoury2026_posthoc_v41_check.py: carries over).

Rules, fixed before the run (the script records its own sha256, Phase A's
locked rule's and the start time in rules.json before computing anything):

- The rule, one candidate: v4.1 as served (service/pipeline/fusion.py,
  version "v4.1"), on references without test cells as in Phases 3 to 3c
  (v4's train-plus-validation bundle; v3.1's centroids recomputed on those
  rows). Every upload goes through the service's own code.
- Implementation check, first: on T1 NB3c's calibration suite, v4.1's
  best guess, coverage, committed share and correct-when-committed must
  equal Phase A's figures for the locked rule
  (research/notebook-outputs/v41_pretest/candidates.csv) within 0.01.
  Otherwise the run stops before the evaluation suite is drawn.
- Development figures, the served all-cells bundles: v3.1, v4 and v4.1 on
  Fulcher 2026, PBMC240, SCoPE2 (published and reprocessed) and
  Furtwangler 2025. Reported, not checked.
- A fresh evaluation suite: 240 new uploads from NB3c's te_eval cells,
  sim_generator.make_suite("eval_v41", ..., seed 20261007), written before
  it is scored. Declared: these cells were never fitted on, but Phases 3, 3b
  and 3c scored them in other uploads. This is their fourth use, so the
  evaluation is a safety check on simulated RNA uploads, not evidence of
  v4.1's protein gain, which only a sealed test can give.
- Evaluation, scored once, v3.1, v4 and v4.1 on the same uploads, cells
  with at least 200 observed genes: coverage, false abstention, committed
  share, correct when committed at the stated level, answer levels, and the
  best guess's mean per-upload balanced accuracy, overall and per scenario.
- GO only if all hold, v4.1 against v3.1 (Phase 3c's checks): coverage not
  below v3.1's; false abstention at most 3%; correct when committed at least
  94%; committed share at least v3.1's minus 2 points; best guess at least
  v3.1 + 2 points; no scenario group more than 3 points below v3.1. And
  against v4: best guess at least v4's minus 1.0 overall, and no scenario
  group more than 2 points below v4.
- Khoury 2026 is not read.

Writes research/notebook-outputs/v41_phase3/: rules.json, the calibration
check, the development figures, the evaluation suite, the evaluation, and
spec_block.json for scripts/build_v41_spec.py.

    python research/notebooks/v41_phase3.py      # from the repository root
    python research/notebooks/v41_phase3.py --smoke DIR
    # a plumbing check: 4 uploads per stage, its test uploads drawn from the
    # calibration cells (never the evaluation pool), written to DIR; the
    # implementation check is printed, not enforced
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v4_calibration as phase3  # noqa: E402  (raw_upload, restricted, centroids_from, GROUP)
import v4_phase3c  # noqa: E402  (per_upload_balanced, summary, cell_rows)
import v4_pretest  # noqa: E402  (the development metrics)
import sim_generator as sg  # noqa: E402  (on NB1's path, added by v4_calibration)

from benchmark import baselines_v31, datasets  # noqa: E402
from service.pipeline import alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v41_phase3"
PRETEST = REPO / "research" / "notebook-outputs" / "v41_pretest"
MIN_GENES, N_UPLOADS, EVAL_SEED, CHECK_TOLERANCE = 200, 240, 20261007, 0.01
CHECKED = {"best_guess_per_upload_balanced": "suite_overall", "coverage": "answers_coverage",
           "committed": "answers_committed", "correct_when_committed": "answers_correct_when_committed"}
GO = {"coverage": "not below v3.1", "false_abstention_max": 3.0, "correct_min": 94.0, "committed_drop_max": 2.0,
      "best_guess_gain": 2.0, "scenario_drop_max": 3.0, "v4_best_guess_drop_max": 1.0, "v4_scenario_drop_max": 2.0}
FUSED = ("v4", "v4.1")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coverage(bundle, smoothed, aligned, truth_pos, components) -> np.ndarray:
    """v4_phase3c.coverage, for v3.1, v4 and v4.1: whether each cell's set
    (before abstention) holds its true class, built as the response builds it."""
    names = bundle.class_names
    answers = bundle.answers if bundle.pipeline_version in FUSED else bundle
    Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
    P_all = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, answers.members)])
    space = components.label_space.estimate(None, names, False)
    P = components.label_space.probabilities(P_all, space)
    guess = None
    if bundle.pipeline_version in FUSED:
        counted = aligned.per_cell_observed_genes >= MIN_GENES
        G = fusion.best_guess_probabilities(bundle, Z, aligned.values, aligned.mask, P_all, counted).probabilities
        guess = ensemble.best_guess(components.label_space.probabilities(G, space), space.positions)[0]
    sets = components.calibrator.calibrate(P, None, space, guess_positions=guess).label_sets
    return np.array([t in set(s) for t, s in zip(truth_pos, sets)])


def project(bundle, smoothed, aligned, scale, resolution):
    if bundle.pipeline_version in FUSED:
        return fusion.project_prepared(bundle, smoothed, aligned, scale, resolution, False, bundle.components)
    return ensemble.project_prepared(bundle, smoothed, aligned, scale, resolution, False, bundle.components)


def main() -> None:
    global OUT
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", type=Path, help="plumbing check into this directory (no evaluation-pool cell is read)")
    smoke = parser.parse_args().smoke
    if smoke:
        OUT = smoke
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    locked = json.loads((PRETEST / "locked_rule.json").read_text())
    (OUT / "rules.json").write_text(json.dumps({
        "script_sha256": sha256(Path(__file__)), "locked_rule_sha256": sha256(PRETEST / "locked_rule.json"),
        "spec_v41_sha256": sha256(REPO / "service" / "model" / "v4_1" / "spec_v41.json"),
        "started": datetime.now().isoformat(timespec="seconds"), "locked_rule": locked,
        "check_tolerance": CHECK_TOLERANCE, "go": GO, "eval_seed": EVAL_SEED}, indent=2) + "\n", newline="\n")
    t0 = time.time()
    v41 = fusion.V4Bundle.load(require_evaluation=False, version="v4.1")
    v4 = fusion.V4Bundle.load(require_evaluation=False)
    if (v41.gate_on_fusion_weight, v41.correlation_temperature) != (locked["w_on"], locked["tau"]):
        raise SystemExit("service/model/v4_1/spec_v41.json does not carry Phase A's locked rule: run scripts/build_v41_spec.py")
    v31 = v4.answers
    names, n = v4.class_names, len(v4.class_names)
    table = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    y = np.array([names.index(c) for c in table["class_name"]])
    split = np.load(phase3.NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    if smoke:
        suites["calib"] = suites["calib"][:4]
    if json.loads((phase3.CALIB_BUNDLE / "spec_v4.json").read_text()).get("reference_rows") != "trainval":
        raise SystemExit(f"{phase3.CALIB_BUNDLE} is not the train-plus-validation bundle")
    v31_centroids = [phase3.centroids_from(m.reference_latents[trainval], y[trainval], n) for m in v31.members]
    v31c = dataclasses.replace(v31, members=phase3.restricted(v31.members, trainval, v31_centroids),
                               property_values=v31.property_values[trainval])
    cb = [np.load(phase3.CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy") for m in v4.members]
    calib_means = np.load(phase3.CALIB_BUNDLE / "class_means_cb.npy")
    held_out = {"v3.1": v31c}
    for name, b in (("v4", v4), ("v4.1", v41)):
        held_out[name] = dataclasses.replace(b, answers=v31c, members=phase3.restricted(b.members, trainval, cb), class_means=calib_means)
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_X = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_X[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    genes = v4.feature_genes
    resolution = gene_ids.resolve_identifiers(genes)
    print(f"ready ({time.time() - t0:.0f}s)", flush=True)

    def prepared(spec_):
        raw = phase3.raw_upload(spec_, get_raw, profiles, len(genes))
        ids = [f"{spec_['id']}_{i}" for i in range(len(raw))]
        return pipeline._prepare_query(genes, alignment.RawMatrix(gene_names=genes, cell_ids=ids, values=raw.T))

    def score(specs, models) -> tuple[pd.DataFrame, list[dict]]:
        rows, uploads = [], []
        for s in specs:
            smoothed, aligned, scale = prepared(s)
            truth_pos = y[np.asarray(s["cell_idx"])]
            truth = [names[k] for k in truth_pos]
            group = phase3.GROUP[s["scenario"]]
            for m in models:
                b = held_out[m]
                response = project(b, smoothed, aligned, scale, resolution)
                rows += v4_phase3c.cell_rows(response, truth, coverage(b, smoothed, aligned, truth_pos, b.components),
                                             v4.hierarchy, s["id"], group, m)
                if m == "v4.1":
                    uploads.append({"upload": s["id"], "group": group, "scenario": s["scenario"], "classes": "|".join(s["classes"]),
                                    "cells": len(truth), **{k: v for k, v in response["best_guess_rule"].items() if k != "rule"}})
        return pd.DataFrame(rows), uploads

    # 1. the implementation check, on the calibration suite
    calib, calib_uploads = score(suites["calib"], ("v4.1",))
    found = {k: v4_phase3c.summary(calib)[k] for k in CHECKED}
    candidates = pd.read_csv(PRETEST / "candidates.csv")
    row = candidates[(candidates["w_on"] == locked["w_on"]) & (candidates["tau"] == locked["tau"])].iloc[0]
    expected = {k: round(float(row[c]), 2) for k, c in CHECKED.items()}
    differences = {k: round(found[k] - expected[k], 4) for k in CHECKED}
    passed = all(abs(d) <= CHECK_TOLERANCE for d in differences.values())
    check = {"found": found, "expected": expected, "differences": differences, "tolerance": CHECK_TOLERANCE,
             "passed": passed, "enforced": not smoke}
    (OUT / "calibration_check.json").write_text(json.dumps(check, indent=2) + "\n", newline="\n")
    pd.DataFrame(calib_uploads).to_csv(OUT / "calibration_uploads.csv", index=False, lineterminator="\n")
    print(json.dumps(check, indent=1), f"({time.time() - t0:.0f}s)", flush=True)
    if not passed and not smoke:
        (OUT / "spec_block.json").write_text(json.dumps({"evaluation": {
            "status": "not run", "record": "research/notebook-outputs/v41_phase3/calibration_check.json",
            "reason": "the service did not reproduce Phase A's locked rule on the calibration suite"}}, indent=2) + "\n", newline="\n")
        raise SystemExit("STOP: the implementation check failed; nothing evaluated")

    # 2. development figures, the served all-cells bundles
    lineage = table.groupby("class_name")["lineage"].first().to_dict()
    cidx = {c: i for i, c in enumerate(names)}
    pbmc_meta = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    dev_uploads = [("fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels()),
                   ("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), pbmc_meta),
                   ("scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")),
                   ("scope2_reprocessed", datasets.load_scope2_reprocessed_upload(),
                    datasets.load_scope2_reprocessed_labels().rename(columns={"label": "class_name"})),
                   ("furtwangler2025", datasets.load_furtwangler2025_upload(), datasets.load_furtwangler2025_labels())]
    served = {"v3.1": v31, "v4": v4, "v4.1": v41}
    dev, maxp = {}, {}
    for name, raw, info in dev_uploads:
        smoothed, aligned, scale = pipeline._prepare_query(genes, raw)
        rows_ = np.arange(len(aligned.values))
        if name == "pbmc240":
            at = {c: i for i, c in enumerate(raw.cell_ids)}
            rows_ = np.array([at[c] for c in info["cell_id"].astype(str)])
        res = gene_ids.resolve_identifiers(raw.gene_names)
        for m, b in served.items():
            resp = project(b, smoothed, aligned, scale, res)
            cells = [resp["cells"][i] for i in rows_]
            pred = np.array([c.get("best_guess", {}).get("label") or "" for c in cells])
            prob = np.array([c.get("best_guess", {}).get("probability", np.nan) for c in cells])
            P = np.zeros((len(pred), n))
            P[np.arange(len(pred)), [cidx.get(p, 0) for p in pred]] = prob
            if name.startswith("scope2"):
                fig = {"balanced_accuracy_unrestricted": round(100 * balanced_accuracy_score(info["class_name"].to_numpy(), pred), 2)}
            else:
                fig = v4_pretest.metrics(name, pred, info, P, cidx, lineage)
            fig["committed"] = round(100 * float(np.mean([not c["abstained"] for c in cells])), 2)
            if "best_guess_rule" in resp:
                fig.update({k: v for k, v in resp["best_guess_rule"].items() if k != "rule"})
            dev.setdefault(name, {})[m] = fig
            maxp[(name, m)] = prob
    for m in served:
        a_, b_ = maxp[("fulcher2026", m)], maxp[("furtwangler2025", m)]
        dev.setdefault("out_of_reference_auroc", {})[m] = round(float(roc_auc_score(np.r_[np.ones(len(a_)), np.zeros(len(b_))], np.r_[a_, b_])), 4)
    (OUT / "development.json").write_text(json.dumps(dev, indent=2) + "\n", newline="\n")
    print(json.dumps({k: {m: {f: v for f, v in d.items() if f in ("balanced_accuracy_6_types", "lymphoid_recall", "balanced_accuracy_unrestricted")}
                          for m, d in ds.items()} if isinstance(ds, dict) and k != "out_of_reference_auroc" else ds
                      for k, ds in dev.items()}, indent=1), f"({time.time() - t0:.0f}s)", flush=True)

    # 3. the fresh evaluation suite, written before it is scored
    y_all = np.load(phase3.NB1 / "y_all.npy")
    te_eval = np.asarray(suites["te_cal" if smoke else "te_eval"])
    if set(te_eval.tolist()) & set(trainval.tolist()):
        raise SystemExit("an evaluation cell is in the reference rows")
    fresh = sg.make_suite("eval_v41", te_eval, y_all[te_eval], names, N_UPLOADS, EVAL_SEED)
    if smoke:
        fresh = fresh[:4]
    (OUT / "eval_suite.json").write_text(json.dumps(fresh) + "\n", newline="\n")
    print(f"fresh suite written: {len(fresh)} uploads, {sum(len(s['cell_idx']) for s in fresh)} cells", flush=True)

    # 4. evaluate once
    df, eval_uploads = score(fresh, ("v3.1", "v4", "v4.1"))
    df.to_csv(OUT / "eval_cells.csv.gz", index=False, lineterminator="\n")
    pd.DataFrame(eval_uploads).to_csv(OUT / "eval_uploads.csv", index=False, lineterminator="\n")
    models = ("v4.1", "v4", "v3.1")
    result = {m: v4_phase3c.summary(df[df["method"] == m]) for m in models}
    by_group = {m: {g: v4_phase3c.summary(df[(df["method"] == m) & (df["group"] == g)]) for g in sorted(df["group"].unique())}
                for m in models}
    pd.DataFrame([{"method": m, "group": g, **{k: v for k, v in r.items() if k != "levels"}} for m, gs in by_group.items()
                  for g, r in gs.items()]).to_csv(OUT / "eval_by_scenario.csv", index=False, lineterminator="\n")
    a, b, c4 = result["v4.1"], result["v3.1"], result["v4"]
    bg = lambda m, g: by_group[m][g]["best_guess_per_upload_balanced"]  # noqa: E731
    drops31 = {g: round(bg("v3.1", g) - bg("v4.1", g), 2) for g in by_group["v4.1"]}
    drops4 = {g: round(bg("v4", g) - bg("v4.1", g), 2) for g in by_group["v4.1"]}
    checks = {k: bool(v) for k, v in {
        "coverage": a["coverage"] >= b["coverage"],
        "false_abstention": a["false_abstention"] <= GO["false_abstention_max"],
        "correct_when_committed": a["correct_when_committed"] >= GO["correct_min"],
        "committed": a["committed"] >= b["committed"] - GO["committed_drop_max"],
        "best_guess_gain": a["best_guess_per_upload_balanced"] >= b["best_guess_per_upload_balanced"] + GO["best_guess_gain"],
        "no_scenario_drop_vs_v31": all(d <= GO["scenario_drop_max"] for d in drops31.values()),
        "best_guess_vs_v4": a["best_guess_per_upload_balanced"] >= c4["best_guess_per_upload_balanced"] - GO["v4_best_guess_drop_max"],
        "no_scenario_drop_vs_v4": all(d <= GO["v4_scenario_drop_max"] for d in drops4.values()),
    }.items()}
    go = all(checks.values())
    gate = pd.DataFrame(eval_uploads).groupby("group")["correlation_term"].apply(lambda s: round(100 * float((s == "used").mean()), 1)).to_dict()
    record = {"rule": locked, "result": result, "by_scenario": by_group, "scenario_drop_vs_v31": drops31,
              "scenario_drop_vs_v4": drops4, "correlation_term_used_pct_of_uploads": gate, "checks": checks, "go": go,
              "seconds": round(time.time() - t0)}
    (OUT / "summary.json").write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    (OUT / "spec_block.json").write_text(json.dumps({"evaluation": {
        "status": "passed" if go else "failed", "record": "research/notebook-outputs/v41_phase3/summary.json",
        "suite": "eval_v41: 240 new uploads from T1 NB3c's te_eval cells, seed 20261007 (their fourth use)",
        "date": datetime.now().date().isoformat()}}, indent=2) + "\n", newline="\n")
    print(json.dumps({k: record[k] for k in ("result", "scenario_drop_vs_v31", "scenario_drop_vs_v4",
                                             "correlation_term_used_pct_of_uploads", "checks", "go")}, indent=1), flush=True)


if __name__ == "__main__":
    main()
