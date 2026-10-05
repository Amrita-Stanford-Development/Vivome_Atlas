"""v4, Phase 3c: v3.1's answers with v4's best guess, the correlation term
gated by upload agreement (research/todo.md, Track G;
service/pipeline/fusion.py).

Phase 3b (research/notebook-run-history.md, entry 23) failed two checks, both
from single-type uploads: coverage, because the fused guess replaced v3.1's
best guess in the set instead of joining it, and the single-type scenario,
because z-scoring each gene within an upload leaves a single type no contrast
for the correlation term. An exploration followed, on NB3c's calibration
cells and the development data only (research/notebook-outputs/v4_phase3c/
exploration.json): the per-cell ingredients cached through the service's code
reproduced Phase 3b's records exactly, and the owner chose the rule below from
its finalists (2026-10-05).

Rules fixed before the run (the script records its own sha256, the
exploration record's and the start time in rules.json before computing
anything):

- The rule, one candidate, nothing chosen in this run: answers are v3.1's
  (T1 NB2's conformal sets, abstention and answer levels), and v4's best guess
  joins every non-empty set beside v3.1's. The best guess: an upload's
  agreement is the share of its cells with at least 200 observed genes whose
  top class under the correlation term is v3.1's top class. At or above 0.4,
  0.7 x (0.5 x smoothed + 0.5 x unsmoothed class-balanced encoder) + 0.3 x
  softmax(r / 0.05); below, the correlation term is flat and the encoder is
  the smoothed query's alone.
- Cells and references, as in Phases 3 and 3b: T1 NB3c's split (Drive
  NB3c/suites.json); v4's centroids and class means from the
  train-plus-validation bundle, v3.1's centroids recomputed from its latents
  on those rows. Every upload goes through the service's own code:
  pipeline._prepare_query, then fusion.project_prepared (v4) or
  ensemble.project_prepared (v3.1).
- Implementation check, first: on NB3c's calibration suite, both methods'
  best guess, coverage, committed share and correct-when-committed must equal
  the exploration's calibration_check within 0.01. Otherwise the run stops
  before the evaluation suite is drawn: the service is not the explored rule.
- Development figures, the served all-cells bundle: Fulcher 2026, PBMC240,
  SCoPE2 and Furtwangler 2025, with each upload's agreement. Reported, not
  checked.
- A fresh evaluation suite: 240 new uploads from NB3c's te_eval cells,
  sim_generator.make_suite("eval_v4c", ..., seed 20261005), written before it
  is scored. Declared: these cells were never fitted on, but Phases 3 and 3b
  scored them in other uploads, and Phase 3b's per-type diagnosis of them
  (CD8T and neutrophil single-type uploads) prompted this design. So this
  evaluation is weaker evidence than Phase 3b's; a public claim needs the
  sealed test. The generator's SCoPE2-like uploads keep NB1's macrophage
  share of 394 / 1490, which came from SCoPE2's swapped labels (entry 22);
  their labels are right, only the mix is the reverse of SCoPE2's.
- Evaluation, scored once, v4 against v3.1, cells with at least 200 observed
  genes: coverage (true class in the set, before abstention), false
  abstention (out of distribution), committed share, correct when committed
  at the stated level, answer levels, and the best guess's mean per-upload
  balanced accuracy, overall and per scenario group.
- GO only if all hold: coverage not below v3.1's (the owner's decision,
  2026-10-05: v4's sets contain v3.1's, so a floor would test v3.1's
  calibrator; the absolute figure is reported); false abstention at most 3%;
  correct when committed at least 94%; committed share at least v3.1's minus
  2 points; best guess at least v3.1 + 2 points; no scenario group more than
  3 points below v3.1.
- Khoury 2026 is not read.

Writes research/notebook-outputs/v4_phase3c/: rules.json, the calibration
check, the development figures, the evaluation suite, the evaluation, and
spec_block.json for scripts/build_v4_bundle.py --spec-only.

    python research/notebooks/v4_phase3c.py      # from the repository root
    python research/notebooks/v4_phase3c.py --smoke DIR
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
import v4_calibration as phase3  # noqa: E402  (its helpers: raw_upload, restricted, centroids_from, GROUP)
import v4_pretest  # noqa: E402  (the development metrics)
import sim_generator as sg  # noqa: E402  (on NB1's path, added by v4_calibration)

from benchmark import baselines_v31, datasets  # noqa: E402
from service.pipeline import abstention, alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v4_phase3c"
EXPLORATION = REPO / "research" / "notebook-outputs" / "v4_phase3c" / "exploration.json"
RULE = {"smoothed_share": 0.5, "agreement_threshold": 0.4, "fusion_weight": 0.7, "correlation_temperature": 0.05}
MIN_GENES, N_UPLOADS, EVAL_SEED, CHECK_TOLERANCE = 200, 240, 20261005, 0.01
CHECKED = ("best_guess_per_upload_balanced", "coverage", "committed", "correct_when_committed")
GO = {"coverage": "not below v3.1", "false_abstention_max": 3.0, "correct_min": 94.0, "committed_drop_max": 2.0,
      "best_guess_gain": 2.0, "scenario_drop_max": 3.0}


def per_upload_balanced(d: pd.DataFrame) -> pd.Series:
    return d.groupby("upload").apply(lambda u: 100 * (balanced_accuracy_score(u["true"], u["best_guess"])
                                                      if u["true"].nunique() > 1 else float((u["true"] == u["best_guess"]).mean())))


def summary(d: pd.DataFrame) -> dict:
    up = per_upload_balanced(d)
    com = d[d["committed"]]
    return {"cells": int(len(d)), "committed": round(100 * d["committed"].mean(), 2),
            "correct_when_committed": round(100 * com["correct"].mean(), 2) if len(com) else None,
            "false_abstention": round(100 * d["ood_abstained"].mean(), 2),
            "levels": {k: round(100 * v, 2) for k, v in d["level"].value_counts(normalize=True).items()},
            "best_guess_per_upload_balanced": round(float(up.mean()), 2),
            "coverage": round(100 * d["covered"].mean(), 2)}


def cell_rows(response: dict, truth_names: list[str], covered: np.ndarray, hierarchy: dict, upload: str, group: str,
              method: str) -> list[dict]:
    rows = []
    for i, cell in enumerate(response["cells"]):
        if cell["observed_genes"] < MIN_GENES:
            continue
        t = truth_names[i]
        committed = not cell["abstained"]
        rows.append({"method": method, "upload": upload, "group": group, "true": t,
                     "ood_abstained": cell.get("abstain_reason") == abstention.AbstainReason.OUT_OF_DISTRIBUTION.value,
                     "committed": committed, "level": cell["label_level"] if committed else "abstain",
                     "correct": committed and phase3.correct_at_level(cell["label"], cell["label_level"], t, hierarchy),
                     "best_guess": cell.get("best_guess", {}).get("label"), "covered": bool(covered[i])})
    return rows


def coverage(bundle, smoothed, aligned, truth_pos, components) -> np.ndarray:
    """Whether each cell's set (before abstention) holds its true class, the
    set built exactly as the response builds it."""
    names = bundle.class_names
    answers = bundle.answers if bundle.pipeline_version == "v4" else bundle
    Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
    P_all = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, answers.members)])
    space = components.label_space.estimate(None, names, False)
    P = components.label_space.probabilities(P_all, space)
    guess = None
    if bundle.pipeline_version == "v4":
        counted = aligned.per_cell_observed_genes >= MIN_GENES
        G = fusion.best_guess_probabilities(bundle, Z, aligned.values, aligned.mask, P_all, counted).probabilities
        guess = ensemble.best_guess(components.label_space.probabilities(G, space), space.positions)[0]
    sets = components.calibrator.calibrate(P, None, space, guess_positions=guess).label_sets
    return np.array([t in set(s) for t, s in zip(truth_pos, sets)])


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    (OUT / "rules.json").write_text(json.dumps({"script_sha256": sha256(Path(__file__)), "exploration_sha256": sha256(EXPLORATION),
                                                "started": datetime.now().isoformat(timespec="seconds"), "rule": RULE,
                                                "check_tolerance": CHECK_TOLERANCE, "go": GO, "eval_seed": EVAL_SEED},
                                               indent=2) + "\n", newline="\n")
    t0 = time.time()
    exploration = json.loads(EXPLORATION.read_text())
    v4 = fusion.V4Bundle.load(require_evaluation=False)
    served = {k: getattr(v4, k) for k in RULE}
    if served != RULE:
        raise SystemExit(f"service/model/v4/spec_v4.json carries {served}, not the rule {RULE}: run scripts/build_v4_bundle.py --spec-only")
    v31 = v4.answers
    names, n = v4.class_names, len(v4.class_names)
    table = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    y = np.array([names.index(c) for c in table["class_name"]])
    split = np.load(phase3.NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    if smoke:
        suites["calib"] = suites["calib"][:4]
    calib_spec = json.loads((phase3.CALIB_BUNDLE / "spec_v4.json").read_text())
    if calib_spec.get("reference_rows") != "trainval":
        raise SystemExit(f"{phase3.CALIB_BUNDLE} is not the train-plus-validation bundle")
    v31_centroids = [phase3.centroids_from(m.reference_latents[trainval], y[trainval], n) for m in v31.members]
    v31c = dataclasses.replace(v31, members=phase3.restricted(v31.members, trainval, v31_centroids),
                               property_values=v31.property_values[trainval])
    cb = [np.load(phase3.CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy") for m in v4.members]
    v4c = dataclasses.replace(v4, answers=v31c, members=phase3.restricted(v4.members, trainval, cb),
                              class_means=np.load(phase3.CALIB_BUNDLE / "class_means_cb.npy"))
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_X = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_X[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    genes = v4.feature_genes
    resolution = gene_ids.resolve_identifiers(genes)
    comps31, comps4 = v31.components, v4.components
    print(f"ready ({time.time() - t0:.0f}s)", flush=True)

    def prepared(spec_):
        raw = phase3.raw_upload(spec_, get_raw, profiles, len(genes))
        ids = [f"{spec_['id']}_{i}" for i in range(len(raw))]
        return pipeline._prepare_query(genes, alignment.RawMatrix(gene_names=genes, cell_ids=ids, values=raw.T))

    def score(specs) -> tuple[pd.DataFrame, list[dict]]:
        rows, uploads = [], []
        for s in specs:
            smoothed, aligned, scale = prepared(s)
            truth_pos = y[np.asarray(s["cell_idx"])]
            truth = [names[k] for k in truth_pos]
            group = phase3.GROUP[s["scenario"]]
            rows += cell_rows(ensemble.project_prepared(v31c, smoothed, aligned, scale, resolution, False, comps31), truth,
                              coverage(v31c, smoothed, aligned, truth_pos, comps31), v4.hierarchy, s["id"], group, "v3.1")
            response = fusion.project_prepared(v4c, smoothed, aligned, scale, resolution, False, comps4)
            rows += cell_rows(response, truth, coverage(v4c, smoothed, aligned, truth_pos, comps4), v4.hierarchy, s["id"], group, "v4")
            uploads.append({"upload": s["id"], "group": group, "scenario": s["scenario"], "classes": "|".join(s["classes"]),
                            "cells": len(truth), **{k: v for k, v in response["best_guess_rule"].items() if k != "rule"}})
        return pd.DataFrame(rows), uploads

    # 1. the implementation check, on the calibration suite
    calib, calib_uploads = score(suites["calib"])
    found = {m: {k: summary(calib[calib["method"] == m])[k] for k in CHECKED} for m in ("v3.1", "v4")}
    expected = exploration["calibration_check"]
    differences = {m: {k: round(found[m][k] - expected[m][k], 4) for k in CHECKED} for m in found}
    passed = all(abs(d) <= CHECK_TOLERANCE for m in differences.values() for d in m.values())
    check = {"found": found, "expected": expected, "differences": differences, "tolerance": CHECK_TOLERANCE,
             "passed": passed, "enforced": not smoke}
    (OUT / "calibration_check.json").write_text(json.dumps(check, indent=2) + "\n", newline="\n")
    pd.DataFrame(calib_uploads).to_csv(OUT / "calibration_uploads.csv", index=False, lineterminator="\n")
    print(json.dumps(check, indent=1), f"({time.time() - t0:.0f}s)", flush=True)
    if not passed and not smoke:
        (OUT / "spec_block.json").write_text(json.dumps({"evaluation": {
            "status": "not run", "record": "research/notebook-outputs/v4_phase3c/calibration_check.json",
            "reason": "the service did not reproduce the explored rule on the calibration suite"}}, indent=2) + "\n", newline="\n")
        raise SystemExit("STOP: the implementation check failed; nothing evaluated")

    # 2. development figures, the served all-cells bundle
    lineage = table.groupby("class_name")["lineage"].first().to_dict()
    cidx = {c: i for i, c in enumerate(names)}
    pbmc_meta = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    dev_uploads = [("fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels()),
                   ("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), pbmc_meta),
                   ("scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")),
                   ("furtwangler2025", datasets.load_furtwangler2025_upload(), datasets.load_furtwangler2025_labels())]
    dev, predictions, maxp = {}, [], {}
    for name, raw, info in dev_uploads:
        smoothed, aligned, scale = pipeline._prepare_query(genes, raw)
        rows_ = np.arange(len(aligned.values))
        if name == "pbmc240":
            at = {c: i for i, c in enumerate(raw.cell_ids)}
            rows_ = np.array([at[c] for c in info["cell_id"].astype(str)])
        res = gene_ids.resolve_identifiers(raw.gene_names)
        runs = {"v3.1": ensemble.project_prepared(v31, smoothed, aligned, scale, res, False, comps31),
                "v4": fusion.project_prepared(v4, smoothed, aligned, scale, res, False, comps4)}
        for m, resp in runs.items():
            cells = [resp["cells"][i] for i in rows_]
            pred = np.array([c.get("best_guess", {}).get("label") or "" for c in cells])
            prob = np.array([c.get("best_guess", {}).get("probability", np.nan) for c in cells])
            P = np.zeros((len(pred), n))  # the best guess's probability in its column: enough for the max-probability figures
            P[np.arange(len(pred)), [cidx.get(p, 0) for p in pred]] = prob
            fig = v4_pretest.metrics(name, pred, info, P, cidx, lineage) if name != "scope2" else {
                "balanced_accuracy_unrestricted": round(100 * balanced_accuracy_score(info["class_name"].to_numpy(), pred), 2)}
            fig["committed"] = round(100 * float(np.mean([not c["abstained"] for c in cells])), 2)
            if m == "v4":
                fig.update({k: v for k, v in resp["best_guess_rule"].items() if k != "rule"})
            dev.setdefault(name, {})[m] = fig
            maxp[(name, m)] = prob
            predictions += [{"dataset": name, "method": m, "cell_id": c["cell_id"], "best_guess": p} for c, p in zip(cells, pred)]
    for m in ("v3.1", "v4"):
        a_, b_ = maxp[("fulcher2026", m)], maxp[("furtwangler2025", m)]
        dev.setdefault("out_of_reference_auroc", {})[m] = round(float(roc_auc_score(np.r_[np.ones(len(a_)), np.zeros(len(b_))], np.r_[a_, b_])), 4)
    (OUT / "development.json").write_text(json.dumps(dev, indent=2) + "\n", newline="\n")
    pd.DataFrame(predictions).to_csv(OUT / "development_predictions.csv.gz", index=False, lineterminator="\n")
    print(json.dumps({k: {m: v for m, v in d.items()} for k, d in dev.items()}, indent=1), f"({time.time() - t0:.0f}s)", flush=True)

    # 3. the fresh evaluation suite, written before it is scored
    y_all = np.load(phase3.NB1 / "y_all.npy")
    te_eval = np.asarray(suites["te_cal" if smoke else "te_eval"])
    if set(te_eval.tolist()) & set(trainval.tolist()):
        raise SystemExit("an evaluation cell is in the reference rows")
    fresh = sg.make_suite("eval_v4c", te_eval, y_all[te_eval], names, N_UPLOADS, EVAL_SEED)
    if smoke:
        fresh = fresh[:4]
    (OUT / "eval_suite.json").write_text(json.dumps(fresh) + "\n", newline="\n")
    print(f"fresh suite written: {len(fresh)} uploads, {sum(len(s['cell_idx']) for s in fresh)} cells", flush=True)

    # 4. evaluate once
    df, eval_uploads = score(fresh)
    df.to_csv(OUT / "eval_cells.csv.gz", index=False, lineterminator="\n")
    pd.DataFrame(eval_uploads).to_csv(OUT / "eval_uploads.csv", index=False, lineterminator="\n")
    result = {m: summary(df[df["method"] == m]) for m in ("v4", "v3.1")}
    by_group = {m: {g: summary(df[(df["method"] == m) & (df["group"] == g)]) for g in sorted(df["group"].unique())} for m in ("v4", "v3.1")}
    pd.DataFrame([{"method": m, "group": g, **{k: v for k, v in r.items() if k != "levels"}} for m, gs in by_group.items() for g, r in gs.items()]).to_csv(
        OUT / "eval_by_scenario.csv", index=False, lineterminator="\n")
    a, b = result["v4"], result["v3.1"]
    drops = {g: round(by_group["v3.1"][g]["best_guess_per_upload_balanced"] - by_group["v4"][g]["best_guess_per_upload_balanced"], 2) for g in by_group["v4"]}
    checks = {k: bool(v) for k, v in {
        "coverage": a["coverage"] >= b["coverage"],
        "false_abstention": a["false_abstention"] <= GO["false_abstention_max"],
        "correct_when_committed": a["correct_when_committed"] >= GO["correct_min"],
        "committed": a["committed"] >= b["committed"] - GO["committed_drop_max"],
        "best_guess_gain": a["best_guess_per_upload_balanced"] >= b["best_guess_per_upload_balanced"] + GO["best_guess_gain"],
        "no_scenario_drop": all(d <= GO["scenario_drop_max"] for d in drops.values()),
    }.items()}
    go = all(checks.values())
    gate = pd.DataFrame(eval_uploads).groupby("group")["correlation_term"].apply(lambda s: round(100 * float((s == "used").mean()), 1)).to_dict()
    record = {"rule": RULE, "result": result, "by_scenario": by_group, "scenario_drop_vs_v31": drops,
              "correlation_term_used_pct_of_uploads": gate, "checks": checks, "go": go, "seconds": round(time.time() - t0)}
    (OUT / "summary.json").write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    (OUT / "spec_block.json").write_text(json.dumps({"evaluation": {
        "status": "passed" if go else "failed", "record": "research/notebook-outputs/v4_phase3c/summary.json",
        "suite": "eval_v4c: 240 new uploads from T1 NB3c's te_eval cells, seed 20261005",
        "date": datetime.now().date().isoformat()}}, indent=2) + "\n", newline="\n")
    print(json.dumps({k: record[k] for k in ("result", "scenario_drop_vs_v31", "correlation_term_used_pct_of_uploads", "checks", "go")}, indent=1), flush=True)


if __name__ == "__main__":
    main()
