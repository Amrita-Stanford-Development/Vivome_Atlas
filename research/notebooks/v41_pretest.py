"""v4.1, Phase A (research/todo.md, Track G): choose v4's gate-on encoder
weight and correlation temperature on real protein data.

Why: v4's fusion weight (0.7 on the encoder, 0.3 on the correlation term)
was chosen on simulated RNA uploads, where the encoder never crosses the
modality gap. On Fulcher 2026 the correlation term alone scores 69.6 and
the encoder alone 61.0, and a 0.3 encoder weight gives about 71.5 against
v4's 65.0 (the owner's diagnosis session, 2026-10-06/07; the plan:
research/todo.md, Track G, v4.1). Fulcher is the only labelled protein
dataset whose uploads pass v4's agreement gate, so the owner decided
(2026-10-07) to choose on it under these rules, with simulation and the
other development data as guardrails, and to check the choice once on
Khoury 2026 afterwards (benchmark/khoury2026_posthoc_v41_check.py), which
chooses nothing.

Rules, fixed before the run (the script records its own sha256, the
helpers' and the cache record's, and the start time in rules.json first):

- Inputs: the per-cell cache (research/notebooks/v41_cache.py; checked
  against research/notebook-outputs/v41_pretest/cache_record.json), which
  reproduces Phase 3c's records exactly.
- Candidates: the gate-on encoder weight w_on in {0.2, 0.3, 0.4, 0.5, 0.7}
  x the correlation temperature tau in {0.05, 0.07, 0.1}. Everything else is
  v4's: the agreement gate (0.4), the smoothed share (0.5) and the gate-off
  branch (0.7 x smoothed encoder + 0.3 x flat). (0.7, 0.05) is v4.
- Guardrails, all required:
  - calibration suite (cells with at least 200 genes), mean per-upload
    best-guess balanced accuracy at least v4's minus 1.0;
  - every scenario group at least v4's minus 2.0 and v3.1's minus 3.0;
  - single-type uploads (the suite's and the 60 extra): p_fail, the share
    of 4,000 resampled 35-upload single-type suites more than 3 points
    below v3.1, at most 0.01;
  - committed share on the calibration suite at least v3.1's minus 2
    (v4's sets with the guess joined beside v3.1's);
  - development: PBMC240 lymphoid recall, and SCoPE2 (published and
    reprocessed) balanced accuracy unrestricted and restricted to
    macrophage/monocyte, each at least v4's minus 2.
- Objective: Fulcher 2026's six-type balanced accuracy.
- Stability: 200 random halvings of Fulcher's 71 runs (the run is a cell
  id's prefix before its last underscore; seed 0). In each, a candidate is
  near-best if its score on the first half is within 1.0 point of the best
  eligible candidate's there; its plateau share is how often. Stable means a
  plateau share of at least 0.8.
- Choice: if v4 is the only eligible candidate, v4 stays and v4.1 stops.
  Otherwise, among stable eligible candidates other than v4, the one
  closest to v4: the highest w_on, then the lowest tau. If none is stable,
  the eligible candidate with the highest calibration-suite score among
  those within 1.0 point of the best Fulcher score (ties: highest w_on, then
  lowest tau).
- Research arm, reported and never selectable (the owner's stacking
  question): the chosen rule blended with a baseline's class scores,
  (1 - beta) x v4.1 + beta x baseline, beta in {0.2, 0.33}. Harmony with
  nearest centroid (softmax(cosine / 0.05) to class centroids, mean over its
  three seeds) and PCA with shared kNN (its 30-neighbour distance-weighted
  vote), rebuilt from the corrected runs' saved embeddings
  (benchmark/results/baselines_corrected/<dataset>/), on Fulcher, PBMC240
  and SCoPE2's published matrix.
- Declared: Fulcher becomes in-sample for v4.1 and no longer counts as
  evidence for it. Khoury 2026 and NB3c's te_eval cells are not read.

Writes research/notebook-outputs/v41_pretest/: rules.json, candidates.csv,
selection.json, locked_rule.json (read by Phase B, which checks its sha256)
and research_arm.csv.

    python research/notebooks/v41_pretest.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v41_core as core  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v41_pretest"
W_ON, TAU = (0.2, 0.3, 0.4, 0.5, 0.7), (0.05, 0.07, 0.1)
GUARD = {"suite_drop_max": 1.0, "group_drop_vs_v4_max": 2.0, "group_drop_vs_v31_max": 3.0, "p_fail_max": 0.01,
         "committed_drop_vs_v31_max": 2.0, "development_drop_max": 2.0}
SPLITS, PLATEAU_WITHIN, PLATEAU_MIN, SPLIT_SEED = 200, 1.0, 0.8, 0
DEV_GUARDED = ("pbmc240_lymphoid", "scope2_unrestricted", "scope2_restricted",
               "scope2_reprocessed_unrestricted", "scope2_reprocessed_restricted")
BETAS = (0.2, 0.33)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fulcher_rows(dev: pd.DataFrame):
    from benchmark import datasets
    f = (dev["dataset"] == "fulcher2026").to_numpy()
    truth = dev.loc[f, "label"].to_numpy()
    scored = truth != datasets.FULCHER2026["unscored_label"]
    runs = np.array([c.rsplit("_", 1)[0] for c in dev.loc[f, "cell_id"]])
    return f, truth, scored, runs


def fulcher_types(P: np.ndarray, names: np.ndarray, f: np.ndarray) -> np.ndarray:
    from benchmark import fulcher2026_score as fulcher
    return np.array([fulcher.COARSE.get(c, "other") for c in names[P[f].argmax(1)]])


def baseline_scores(dev: pd.DataFrame, names: np.ndarray) -> dict:
    """{(baseline, dataset): (dev rows, class probabilities)} from the
    corrected runs' saved embeddings."""
    from sklearn.neighbors import KNeighborsClassifier
    rna_cls = pd.read_csv(REPO / "benchmark" / "results" / "rna_meta.csv")["class_name"].to_numpy()
    out = {}
    for dataset in ("fulcher2026", "pbmc240", "scope2"):
        base = REPO / "benchmark" / "results" / "baselines_corrected" / dataset
        rows_dev = dev.index[dev["dataset"] == dataset].to_numpy()
        at = {c: i for i, c in zip(rows_dev, dev.loc[rows_dev, "cell_id"].astype(str))}
        harmony = []
        for seed in (0, 1, 2):
            rz, qz = np.load(base / f"harmony_seed{seed}_rna_emb.npy"), np.load(base / f"harmony_seed{seed}_query_emb.npy")
            C = np.stack([rz[rna_cls == n].mean(0) for n in names])
            C /= np.linalg.norm(C, axis=1, keepdims=True)
            q = qz / np.linalg.norm(qz, axis=1, keepdims=True)
            harmony.append(core.softmax((q @ C.T) / 0.05))
        ids = pd.read_csv(base / "harmony_seed0_pred.csv", dtype={"cell_id": str}, keep_default_na=False)["cell_id"].astype(str)
        rows = np.array([at[c] for c in ids])
        out[("Harmony NC", dataset)] = (rows, np.mean(harmony, axis=0))
        rz, qz = np.load(base / "pca_seed0_rna_emb.npy"), np.load(base / "pca_seed0_query_emb.npy")
        knn = KNeighborsClassifier(n_neighbors=30, metric="cosine", weights="distance").fit(rz, rna_cls)
        proba = knn.predict_proba(qz)
        order = [list(knn.classes_).index(n) for n in names]
        ids = pd.read_csv(base / "pca_seed0_pred.csv", dtype={"cell_id": str}, keep_default_na=False)["cell_id"].astype(str)
        out[("PCA kNN", dataset)] = (np.array([at[c] for c in ids]), proba[:, order])
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rules.json").write_text(json.dumps({
        "script_sha256": sha256(Path(__file__)), "core_sha256": sha256(REPO / "research" / "notebooks" / "v41_core.py"),
        "cache_record_sha256": sha256(core.RECORD), "started": datetime.now().isoformat(timespec="seconds"),
        "candidates": {"w_on": W_ON, "tau": TAU}, "v4": core.V4, "guardrails": GUARD,
        "stability": {"splits": SPLITS, "within": PLATEAU_WITHIN, "plateau_min": PLATEAU_MIN, "seed": SPLIT_SEED},
        "research_arm_betas": BETAS}, indent=2) + "\n", newline="\n")
    t0 = time.time()
    from service.pipeline import fusion
    v4b = fusion.V4Bundle.load(require_evaluation=False)
    names, hier = np.array(v4b.class_names), v4b.answers.hierarchy
    calib, a, dev, d = core.load()
    cal = (calib["source"] == "calib").to_numpy()
    space = v4b.answers.components.label_space.estimate(None, list(names), False)
    sets = v4b.answers.components.calibrator.calibrate(a["P31"].astype(np.float64), None, space).label_sets
    ag, dag = core.agreement(calib, a, "upload"), core.agreement(dev, d, "dataset")
    g31 = a["P31"].argmax(1)
    ref31 = {"suite": core.suite_scores(calib, g31), **core.answers(calib, sets, names, hier, None, cal)}
    f, truth, scored, runs = fulcher_rows(dev)
    print(f"loaded ({time.time() - t0:.0f}s); development agreement:",
          pd.Series(dag).groupby(dev["dataset"].to_numpy()).first().round(4).to_dict(), flush=True)

    rows, fulcher_pred = [], {}
    for w_on in W_ON:
        for tau in TAU:
            P = core.rule(a, ag, w_on, tau)
            g = P.argmax(1)
            suite = core.suite_scores(calib, g)
            row = {"w_on": w_on, "tau": tau, "is_v4": (w_on, tau) == (core.V4["w_on"], core.V4["tau"]),
                   **{f"suite_{k}": v for k, v in suite.items()}, **core.robustness(calib, g, g31),
                   **{f"answers_{k}": v for k, v in core.answers(calib, sets, names, hier, g, cal).items()},
                   **core.dev_figures(dev, core.rule(d, dag, w_on, tau), names)}
            rows.append(row)
            fulcher_pred[(w_on, tau)] = fulcher_types(core.rule(d, dag, w_on, tau), names, f)
            print(f"w_on {w_on} tau {tau}: suite {suite['overall']:.2f}, Fulcher {row['fulcher']:.2f} ({time.time() - t0:.0f}s)", flush=True)
    table = pd.DataFrame(rows)
    v4 = table[table["is_v4"]].iloc[0]
    groups = [c for c in table if c.startswith("suite_") and c != "suite_overall"]
    checks = pd.DataFrame({
        "g_suite": table["suite_overall"] >= v4["suite_overall"] - GUARD["suite_drop_max"],
        "g_groups_v4": np.all([table[c] >= v4[c] - GUARD["group_drop_vs_v4_max"] for c in groups], axis=0),
        "g_groups_v31": np.all([table[c] >= ref31["suite"][c.removeprefix("suite_")] - GUARD["group_drop_vs_v31_max"]
                                for c in groups], axis=0),
        "g_single": table["single_p_fail"] <= GUARD["p_fail_max"],
        "g_committed": table["answers_committed"] >= ref31["committed"] - GUARD["committed_drop_vs_v31_max"],
        "g_development": np.all([table[k] >= v4[k] - GUARD["development_drop_max"] for k in DEV_GUARDED], axis=0)})
    table = pd.concat([table, checks], axis=1)
    table["eligible"] = checks.all(axis=1)

    # stability over halvings of Fulcher's runs
    rng = np.random.default_rng(SPLIT_SEED)
    unique_runs = np.array(sorted(set(runs)))
    eligible = [(r.w_on, r.tau) for r in table.itertuples() if r.eligible]
    near = {k: 0 for k in eligible}
    for _ in range(SPLITS):
        half = np.isin(runs, rng.permutation(unique_runs)[: len(unique_runs) // 2]) & scored
        s = {k: 100 * balanced_accuracy_score(truth[half], fulcher_pred[k][half]) for k in eligible}
        best = max(s.values())
        for k in eligible:
            near[k] += s[k] >= best - PLATEAU_WITHIN
    table["plateau_share"] = [near.get((r.w_on, r.tau), 0) / SPLITS if r.eligible else np.nan for r in table.itertuples()]
    table.to_csv(OUT / "candidates.csv", index=False, lineterminator="\n", float_format="%.4f")

    others = table[table["eligible"] & ~table["is_v4"]]
    stable = others[others["plateau_share"] >= PLATEAU_MIN]
    if others.empty:
        chosen, reason = (core.V4["w_on"], core.V4["tau"]), "v4 is the only eligible candidate: v4 stays, v4.1 stops"
    elif not stable.empty:
        pick = stable.sort_values(["w_on", "tau"], ascending=[False, True]).iloc[0]
        chosen, reason = (float(pick.w_on), float(pick.tau)), "the stable eligible candidate closest to v4"
    else:
        best_f = table.loc[table["eligible"], "fulcher"].max()
        pool = table[table["eligible"] & (table["fulcher"] >= best_f - PLATEAU_WITHIN)]
        pick = pool.sort_values(["suite_overall", "w_on", "tau"], ascending=[False, False, True]).iloc[0]
        chosen, reason = (float(pick.w_on), float(pick.tau)), "no stable candidate: the best calibration score within 1 point of the best Fulcher"
    chosen_row = table[(table["w_on"] == chosen[0]) & (table["tau"] == chosen[1])].iloc[0]
    selection = {"eligible": [list(k) for k in eligible],
                 "stable": [[float(r.w_on), float(r.tau)] for r in stable.itertuples()],
                 "chosen": {"w_on": chosen[0], "tau": chosen[1]}, "reason": reason,
                 "v31": {"suite": ref31["suite"], "committed": ref31["committed"], "coverage": ref31["coverage"]},
                 "v4": {k: float(v4[k]) for k in ("suite_overall", "fulcher", "pbmc240_lymphoid", "auroc")},
                 "chosen_figures": {k: (bool(v) if isinstance(v, (bool, np.bool_)) else float(v))
                                    for k, v in chosen_row.items() if not k.startswith("g_")}}
    (OUT / "selection.json").write_text(json.dumps(selection, indent=2) + "\n", newline="\n")
    locked = {"w_on": chosen[0], "tau": chosen[1], "smoothed_share": core.V4["smoothed_share"],
              "agreement_threshold": core.V4["agreement_threshold"], "w_off": core.V4["w_off"],
              "is_v4": chosen == (core.V4["w_on"], core.V4["tau"]),
              "chosen_on": "Fulcher 2026 under research/notebooks/v41_pretest.py's rules (rules.json)",
              "date": datetime.now().date().isoformat()}
    (OUT / "locked_rule.json").write_text(json.dumps(locked, indent=2) + "\n", newline="\n")
    print(json.dumps({"chosen": selection["chosen"], "reason": reason, "stable": selection["stable"],
                      "eligible": selection["eligible"]}), flush=True)

    # research arm: the chosen rule blended with a baseline's class scores
    P = core.rule(d, dag, *chosen)
    arm = [{"arm": "v4.1 (chosen rule)", "beta": 0.0, **core.dev_figures(dev, P, names)},
           {"arm": "v4", "beta": 0.0, **core.dev_figures(dev, core.rule(d, dag, core.V4["w_on"], core.V4["tau"]), names)}]
    scores = baseline_scores(dev, names)
    for baseline in ("Harmony NC", "PCA kNN"):
        for beta in BETAS:
            Q = P.copy()
            for (b, dataset), (rows_, probs) in scores.items():
                if b == baseline:
                    Q[rows_] = (1 - beta) * P[rows_] + beta * probs
            fig = core.dev_figures(dev, Q, names)
            arm.append({"arm": f"v4.1 + {baseline}", "beta": beta,
                        **{k: v for k, v in fig.items() if not k.startswith("scope2_reprocessed") and k != "auroc"}})
    pd.DataFrame(arm).to_csv(OUT / "research_arm.csv", index=False, lineterminator="\n", float_format="%.4f")
    print(pd.DataFrame(arm)[["arm", "beta", "fulcher", "pbmc240_lymphoid", "scope2_restricted"]].round(2).to_string(index=False))
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
