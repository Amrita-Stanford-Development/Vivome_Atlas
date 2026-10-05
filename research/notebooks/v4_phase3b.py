"""v4, Phase 3b: v3.1's answers with v4's fused best guess (research/todo.md,
Track G; service/pipeline/fusion.py).

Phase 3 refitted conformal sets on the fused probability, with query smoothing
off: NO GO (research/notebook-run-history.md, entry 21). Its sets were too
wide (56.7% of cells committed, against v3.1's 88.6%) and single-type uploads
fell 8.6 points. An exploration on the calibration suite and the development
data (never the evaluation pool) traced both: the wide sets to the fused
probability, the single-type loss to smoothing off. Hence this design: the
answers stay v3.1's, and only the best guess changes.

Rules fixed before the run (the script records its own sha256 and the start
time in rules.json before computing anything):

- Candidates: the best guess's smoothed_share s in {0, 0.5, 1}, with the
  fusion weight 0.7 and correlation temperature 0.05 unchanged (entry 20).
  Answers: v3.1's conformal sets, abstention and answer levels, unchanged
  (T1 NB2's qhat and threshold); the fused best guess joins non-empty sets.
- Cells and references, as in Phase 3: T1 NB3c's split of NB1's test cells
  (Drive NB3c/suites.json), and references without test cells: v4's
  centroids and class means from the train-plus-validation bundle, v3.1's
  centroids recomputed from its latents on those rows.
- Every upload goes through the service's own code: pipeline._prepare_query,
  then fusion.project_prepared (v4) or ensemble.project_prepared (v3.1).
- Selection, on the calibration suite only (NB3c te_cal, 240 uploads; cells
  with at least 200 observed genes): a candidate is eligible if its mean
  per-upload best-guess balanced accuracy is no more than 3 points below
  v3.1's in every scenario group, and its committed share is at least v3.1's
  minus 2 points. The eligible candidate with the highest overall figure
  wins. Candidates within 0.5 points of it tie, and the tie goes to the
  higher Fulcher 2026 six-type balanced accuracy (development data, the
  served all-cells bundle). If none is eligible: NO GO, nothing evaluated.
- A fresh evaluation suite: 240 new uploads from NB3c's te_eval cells,
  sim_generator.make_suite("eval_v4b", ..., seed 20261004). These cells
  were never fitted on; Phase 3 scored them once, in other uploads. The
  suite is written before it is scored.
- Evaluation, scored once, the chosen v4 against v3.1, cells with at least
  200 observed genes: coverage (true class in the set, before abstention),
  false abstention (out of distribution), committed share, correct when
  committed at the stated level, answer levels, and the best guess's mean
  per-upload balanced accuracy, overall and per scenario group.
- GO only if all hold: coverage at least 88% and not below v3.1's; false
  abstention at most 3%; correct when committed at least 94%; committed
  share at least v3.1's minus 2 points; best guess at least v3.1 + 2 points;
  no scenario group more than 3 points below v3.1.
- Declared: the candidates' calibration-suite and development figures were
  seen in the exploration before these rules were written. The evaluation
  suite is the clean test. Khoury 2026 is not read.

Writes research/notebook-outputs/v4_phase3b/: rules.json, the evaluation
suite, the selection, the evaluation, the chosen candidate's development
figures, and spec_block.json for scripts/build_v4_bundle.py --spec-only.

    python research/notebooks/v4_phase3b.py      # from the repository root
    python research/notebooks/v4_phase3b.py --smoke DIR
    # a plumbing check: 4 uploads per stage, its test uploads drawn from the
    # calibration cells (never the evaluation pool), written to DIR
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

OUT = REPO / "research" / "notebook-outputs" / "v4_phase3b"
CANDIDATES = (0.0, 0.5, 1.0)
MIN_GENES, N_UPLOADS, EVAL_SEED = 200, 240, 20261004
SELECT = {"scenario_drop_max": 3.0, "committed_drop_max": 2.0, "tie": 0.5}
GO = {"coverage_min": 88.0, "false_abstention_max": 3.0, "correct_min": 94.0, "committed_drop_max": 2.0,
      "best_guess_gain": 2.0, "scenario_drop_max": 3.0}


def per_upload_balanced(d: pd.DataFrame) -> pd.Series:
    return d.groupby("upload").apply(lambda u: 100 * (balanced_accuracy_score(u["true"], u["best_guess"])
                                                      if u["true"].nunique() > 1 else float((u["true"] == u["best_guess"]).mean())))


def summary(d: pd.DataFrame) -> dict:
    up = per_upload_balanced(d)
    com = d[d["committed"]]
    out = {"cells": int(len(d)), "committed": round(100 * d["committed"].mean(), 2),
           "correct_when_committed": round(100 * com["correct"].mean(), 2) if len(com) else None,
           "false_abstention": round(100 * d["ood_abstained"].mean(), 2),
           "levels": {k: round(100 * v, 2) for k, v in d["level"].value_counts(normalize=True).items()},
           "best_guess_per_upload_balanced": round(float(up.mean()), 2)}
    if "covered" in d:
        out["coverage"] = round(100 * d["covered"].mean(), 2)
    return out


def cell_rows(response: dict, truth_names: list[str], hierarchy: dict, upload: str, group: str, method: str,
              covered: "np.ndarray | None" = None) -> list[dict]:
    rows = []
    for i, cell in enumerate(response["cells"]):
        if cell["observed_genes"] < MIN_GENES:
            continue
        t = truth_names[i]
        committed = not cell["abstained"]
        row = {"method": method, "upload": upload, "group": group, "true": t,
               "ood_abstained": cell.get("abstain_reason") == abstention.AbstainReason.OUT_OF_DISTRIBUTION.value,
               "committed": committed, "level": cell["label_level"] if committed else "abstain",
               "correct": committed and phase3.correct_at_level(cell["label"], cell["label_level"], t, hierarchy),
               "best_guess": cell.get("best_guess", {}).get("label")}
        if covered is not None:
            row["covered"] = bool(covered[i])
        rows.append(row)
    return rows


def coverage(bundle, smoothed, aligned, truth_pos, components) -> np.ndarray:
    """Whether each cell's set (before abstention) holds its true class, the
    set built exactly as the response builds it."""
    names = bundle.class_names
    answers = bundle.answers if bundle.pipeline_version == "v4" else bundle
    Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
    P = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, answers.members)])
    space = components.label_space.estimate(None, names, False)
    P = components.label_space.probabilities(P, space)
    guess = None
    if bundle.pipeline_version == "v4":
        G = components.label_space.probabilities(fusion.best_guess_probabilities(bundle, Z, aligned.values, aligned.mask), space)
        guess = ensemble.best_guess(G, space.positions)[0]
    sets = components.calibrator.calibrate(P, None, space, guess_positions=guess).label_sets
    return np.array([t in set(s) for t, s in zip(truth_pos, sets)])


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
    me = Path(__file__).read_bytes()
    (OUT / "rules.json").write_text(json.dumps({"script_sha256": hashlib.sha256(me).hexdigest(),
                                                "started": datetime.now().isoformat(timespec="seconds"),
                                                "candidates": CANDIDATES, "select": SELECT, "go": GO,
                                                "eval_seed": EVAL_SEED}, indent=2) + "\n", newline="\n")
    t0 = time.time()
    v4 = fusion.V4Bundle.load(require_evaluation=False)
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

    # 1. selection, on the calibration suite
    rows = []
    for s in suites["calib"]:
        smoothed, aligned, scale = prepared(s)
        truth = [names[k] for k in y[np.asarray(s["cell_idx"])]]
        group = phase3.GROUP[s["scenario"]]
        rows += cell_rows(ensemble.project_prepared(v31c, smoothed, aligned, scale, resolution, False, comps31),
                          truth, v4.hierarchy, s["id"], group, "v3.1")
        for share in CANDIDATES:
            b = dataclasses.replace(v4c, smoothed_share=share)
            rows += cell_rows(fusion.project_prepared(b, smoothed, aligned, scale, resolution, False, comps4),
                              truth, v4.hierarchy, s["id"], group, f"v4 s={share}")
    calib = pd.DataFrame(rows)
    calib.to_csv(OUT / "selection_cells.csv.gz", index=False, lineterminator="\n")
    methods = ["v3.1"] + [f"v4 s={c}" for c in CANDIDATES]
    sel = {m: {"all": summary(calib[calib["method"] == m]),
               "by_group": {g: summary(calib[(calib["method"] == m) & (calib["group"] == g)])["best_guess_per_upload_balanced"]
                            for g in sorted(calib["group"].unique())}} for m in methods}
    base = sel["v3.1"]
    eligible = []
    for c in CANDIDATES:
        r = sel[f"v4 s={c}"]
        worst = max(base["by_group"][g] - r["by_group"][g] for g in r["by_group"])
        ok = worst <= SELECT["scenario_drop_max"] and r["all"]["committed"] >= base["all"]["committed"] - SELECT["committed_drop_max"]
        r["largest_scenario_drop"], r["eligible"] = round(worst, 2), bool(ok)
        if ok:
            eligible.append(c)
    print(json.dumps({m: {"overall": sel[m]["all"]["best_guess_per_upload_balanced"], "committed": sel[m]["all"]["committed"],
                          "drop": sel[m].get("largest_scenario_drop"), "eligible": sel[m].get("eligible")} for m in methods}, indent=1), flush=True)
    selection = {"calibration_suite": sel, "eligible": eligible}
    if not eligible:
        selection["chosen"] = None
        (OUT / "selection.json").write_text(json.dumps(selection, indent=2) + "\n", newline="\n")
        (OUT / "spec_block.json").write_text(json.dumps({"smoothed_share": None, "evaluation": {
            "status": "failed", "record": "research/notebook-outputs/v4_phase3b/selection.json"}}, indent=2) + "\n", newline="\n")
        print("NO GO: no candidate is eligible on the calibration suite", flush=True)
        return
    best = max(sel[f"v4 s={c}"]["all"]["best_guess_per_upload_balanced"] for c in eligible)
    tied = [c for c in eligible if sel[f"v4 s={c}"]["all"]["best_guess_per_upload_balanced"] >= best - SELECT["tie"]]

    # development: Fulcher for the tie, and the chosen candidate's record
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
        runs = {"v3.1": ensemble.project_prepared(v31, smoothed, aligned, scale, res, False, comps31)}
        for c in CANDIDATES:
            runs[f"v4 s={c}"] = fusion.project_prepared(dataclasses.replace(v4, smoothed_share=c), smoothed, aligned, scale, res, False, comps4)
        for m, resp in runs.items():
            cells = [resp["cells"][i] for i in rows_]
            pred = np.array([c.get("best_guess", {}).get("label") or "" for c in cells])
            prob = np.array([c.get("best_guess", {}).get("probability", np.nan) for c in cells])
            P = np.zeros((len(pred), n))  # the best guess's probability in its column: enough for the max-probability figures
            P[np.arange(len(pred)), [cidx.get(p, 0) for p in pred]] = prob
            fig = v4_pretest.metrics(name, pred, info, P, cidx, lineage) if name != "scope2" else {
                "balanced_accuracy_unrestricted": round(100 * balanced_accuracy_score(info["class_name"].to_numpy(), pred), 2)}
            fig["committed"] = round(100 * float(np.mean([not c["abstained"] for c in cells])), 2)
            dev.setdefault(name, {})[m] = fig
            maxp[(name, m)] = prob
            predictions += [{"dataset": name, "method": m, "cell_id": c["cell_id"], "best_guess": p} for c, p in zip(cells, pred)]
    for m in ["v3.1"] + [f"v4 s={c}" for c in CANDIDATES]:
        a_, b_ = maxp[("fulcher2026", m)], maxp[("furtwangler2025", m)]
        dev.setdefault("out_of_reference_auroc", {})[m] = round(float(roc_auc_score(np.r_[np.ones(len(a_)), np.zeros(len(b_))], np.r_[a_, b_])), 4)
    chosen = max(tied, key=lambda c: (dev["fulcher2026"][f"v4 s={c}"]["balanced_accuracy_6_types"], -abs(c - 0.5)))
    selection.update(tied=tied, chosen=chosen, fulcher_for_the_tie={f"v4 s={c}": dev["fulcher2026"][f"v4 s={c}"]["balanced_accuracy_6_types"] for c in tied})
    (OUT / "selection.json").write_text(json.dumps(selection, indent=2) + "\n", newline="\n")
    (OUT / "development.json").write_text(json.dumps(dev, indent=2) + "\n", newline="\n")
    pd.DataFrame(predictions).to_csv(OUT / "development_predictions.csv.gz", index=False, lineterminator="\n")
    print(f"chosen: smoothed_share {chosen} (tied {tied}) ({time.time() - t0:.0f}s)", flush=True)

    # 2. the fresh evaluation suite, written before it is scored
    y_all = np.load(phase3.NB1 / "y_all.npy")
    te_eval = np.asarray(suites["te_cal" if smoke else "te_eval"])
    if set(te_eval.tolist()) & set(trainval.tolist()):
        raise SystemExit("an evaluation cell is in the reference rows")
    fresh = sg.make_suite("eval_v4b", te_eval, y_all[te_eval], names, N_UPLOADS, EVAL_SEED)
    if smoke:
        fresh = fresh[:4]
    (OUT / "eval_suite.json").write_text(json.dumps(fresh) + "\n", newline="\n")
    print(f"fresh suite written: {len(fresh)} uploads, {sum(len(s['cell_idx']) for s in fresh)} cells", flush=True)

    # 3. evaluate once
    v4e = dataclasses.replace(v4c, smoothed_share=chosen)
    rows = []
    for s in fresh:
        smoothed, aligned, scale = prepared(s)
        truth_pos = y[np.asarray(s["cell_idx"])]
        truth = [names[k] for k in truth_pos]
        group = phase3.GROUP[s["scenario"]]
        rows += cell_rows(ensemble.project_prepared(v31c, smoothed, aligned, scale, resolution, False, comps31), truth,
                          v4.hierarchy, s["id"], group, "v3.1", coverage(v31c, smoothed, aligned, truth_pos, comps31))
        rows += cell_rows(fusion.project_prepared(v4e, smoothed, aligned, scale, resolution, False, comps4), truth,
                          v4.hierarchy, s["id"], group, "v4", coverage(v4e, smoothed, aligned, truth_pos, comps4))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "eval_cells.csv.gz", index=False, lineterminator="\n")
    result = {m: summary(df[df["method"] == m]) for m in ("v4", "v3.1")}
    by_group = {m: {g: summary(df[(df["method"] == m) & (df["group"] == g)]) for g in sorted(df["group"].unique())} for m in ("v4", "v3.1")}
    pd.DataFrame([{"method": m, "group": g, **{k: v for k, v in r.items() if k != "levels"}} for m, gs in by_group.items() for g, r in gs.items()]).to_csv(
        OUT / "eval_by_scenario.csv", index=False, lineterminator="\n")
    a, b = result["v4"], result["v3.1"]
    drops = {g: round(by_group["v3.1"][g]["best_guess_per_upload_balanced"] - by_group["v4"][g]["best_guess_per_upload_balanced"], 2) for g in by_group["v4"]}
    checks = {k: bool(v) for k, v in {
        "coverage": a["coverage"] >= GO["coverage_min"] and a["coverage"] >= b["coverage"],
        "false_abstention": a["false_abstention"] <= GO["false_abstention_max"],
        "correct_when_committed": a["correct_when_committed"] >= GO["correct_min"],
        "committed": a["committed"] >= b["committed"] - GO["committed_drop_max"],
        "best_guess_gain": a["best_guess_per_upload_balanced"] >= b["best_guess_per_upload_balanced"] + GO["best_guess_gain"],
        "no_scenario_drop": all(d <= GO["scenario_drop_max"] for d in drops.values()),
    }.items()}
    go = all(checks.values())
    record = {"chosen_smoothed_share": chosen, "result": result, "by_scenario": by_group, "scenario_drop_vs_v31": drops,
              "checks": checks, "go": go, "seconds": round(time.time() - t0)}
    (OUT / "summary.json").write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    (OUT / "spec_block.json").write_text(json.dumps({"smoothed_share": chosen, "evaluation": {
        "status": "passed" if go else "failed", "record": "research/notebook-outputs/v4_phase3b/summary.json",
        "suite": "eval_v4b: 240 new uploads from T1 NB3c's te_eval cells, seed 20261004",
        "date": datetime.now().date().isoformat()}}, indent=2) + "\n", newline="\n")
    print(json.dumps({k: record[k] for k in ("chosen_smoothed_share", "result", "scenario_drop_vs_v31", "checks", "go")}, indent=1), flush=True)


if __name__ == "__main__":
    main()
