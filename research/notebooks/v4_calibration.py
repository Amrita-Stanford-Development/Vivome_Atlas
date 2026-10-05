"""v4, Phase 3: conformal sets and the out-of-distribution threshold refitted on
v4's fused probability (research/todo.md, Track G).

It ran once, NO GO (research/notebook-run-history.md, entry 21), against the
first v4 design of service/pipeline/fusion.py (fused answer sets, smoothing
off). Phases 3b and 3c replaced that design (research/notebooks/v4_phase3b.py
and v4_phase3c.py, which reuse this file's helpers); main() no longer runs
against the current fusion.py, and its outputs in
research/notebook-outputs/v4_calibration/ are the record.

Rules fixed before the run (the script records its own sha256 and the start
time in rules.json before computing anything):

- Cells the encoders never saw: T1 NB3c's split of NB1's test split
  (Drive NB3c/suites.json): the calibration suite (240 uploads) is drawn from
  te_cal, the evaluation suite (240 uploads) from te_eval.
- References without test cells: v4's centroids and class means from the
  train-plus-validation bundle (scripts/build_v4_bundle.py --rows trainval),
  and the out-of-distribution index restricted to train and validation rows,
  for v4 and for the v3.1 comparator alike. v3.1's centroids are recomputed
  from its own latents on those rows; its qhat and threshold are NB2's.
- Every upload goes through the service's own code: a raw matrix (NaN where
  unobserved) into pipeline._prepare_query, then fusion.project_prepared (v4,
  unsmoothed) or ensemble.project_prepared (v3.1, smoothed).
- Conformal: Mondrian LAC (score 1 - fused probability of the true class),
  nb2_core.fit_qhat with alpha 0.1 and min_n 50, on calibration-suite cells
  with at least 200 observed genes. Sets as the service builds them (the best
  guess joins non-empty sets).
- Out of distribution: the members' mean max cosine to the index, threshold
  at the 1st percentile of the same calibration cells (NB2's rule). The
  maximum fused probability is reported as a diagnostic only.
- Evaluation suite, scored once, cells with at least 200 observed genes:
  coverage (true class in the conformal set, before abstention), false
  abstention (out of distribution), committed share, correct when committed
  at the stated level (class: the class; group or lineage: the true class's
  group or lineage in the spec's hierarchy), answer levels, and the best
  guess's mean per-upload balanced accuracy, overall and per scenario.
- GO only if all hold: coverage at least 88% and not below v3.1's; false
  abstention at most 3%; correct when committed at least 94%; best guess at
  least v3.1 + 2 points; no scenario group more than 3 points below v3.1.
- Sensitivity, reported only: qhat refitted with the served all-cells
  bundle; the largest change.
- Development and protein data are not used. Khoury 2026 is not read.

Writes research/notebook-outputs/v4_calibration/. On GO, spec_block.json
holds the conformal and out-of-distribution blocks for service/model/v4/spec_v4.json.

    python research/notebooks/v4_calibration.py      # from the repository root (about 15 minutes)
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
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
DRIVE = REPO.parent / "drive" / "Data"
T1 = DRIVE / "Results" / "Tier1_v31"
NB1 = T1 / "NB1"
CALIB_BUNDLE = T1 / "V4" / "calib"
OUT = REPO / "research" / "notebook-outputs" / "v4_calibration"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(NB1))
sys.path.insert(0, str(REPO / "research" / "notebook-outputs" / "nb2"))
import nb2_core  # noqa: E402
import sim_generator as sg  # noqa: E402

from service.pipeline import abstention, alignment, ensemble, fusion, gene_ids, pipeline, search  # noqa: E402

ALPHA, MIN_N, MIN_GENES, OOD_PERCENTILE = 0.1, 50, 200, 1.0
GO = {"coverage_min": 88.0, "false_abstention_max": 3.0, "correct_min": 94.0, "best_guess_gain": 2.0, "scenario_drop_max": 3.0}
GROUP = {"random_1": "single", "random_2": "narrow", "random_3": "narrow", "random_5": "mixed", "random_8": "mixed",
         "myeloid": "lineage", "lymphoid": "lineage", "pbmc_like": "pbmc", "scope2_like": "scope2"}


def raw_upload(spec, get_raw, profiles, G):
    """materialize()'s steps up to the preprocessing: the upload's raw values,
    NaN wherever unobserved (sim_generator.materialize, before canonical_preprocess)."""
    rng = np.random.default_rng(spec["seed"])
    raw = get_raw(np.asarray(spec["cell_idx"])).astype(np.float32).copy()
    prof = spec["profile"]
    if prof.startswith("random_"):
        gs = sg.random_gene_set(G, float(prof.split("_")[1]), rng)
        det, fracs = np.where(gs, 1.0, np.nan), np.array([1.0])
    else:
        gs = profiles[f"gene_set_{prof}"].astype(bool)
        det, fracs = profiles[f"det_prob_{prof}"], profiles[f"cell_frac_{prof}"]
    raw[:, ~gs] = np.nan
    if spec["stress"]:
        raw = sg.apply_stress(raw, gs, rng)
    if spec["missingness"] == "per_cell":
        raw[sg.sample_missingness(len(raw), gs, det, fracs, rng)] = np.nan
    return raw


def restricted(members, rows, centroids=None):
    out = []
    for i, m in enumerate(members):
        lat = m.reference_latents[rows]
        out.append(dataclasses.replace(m, reference_latents=lat, centroids=m.centroids if centroids is None else centroids[i]))
    return tuple(out)


def centroids_from(latents, y, n):
    Z = latents / np.linalg.norm(latents, axis=1, keepdims=True)
    C = np.stack([Z[y == k].mean(0) for k in range(n)])
    return C / np.linalg.norm(C, axis=1, keepdims=True)


def correct_at_level(label, level, true_name, hierarchy):
    if level == "class":
        return label == true_name
    return label == hierarchy[true_name][level]


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    me = Path(__file__).read_bytes()
    (OUT / "rules.json").write_text(json.dumps({"script_sha256": hashlib.sha256(me).hexdigest(),
                                                "started": datetime.now().isoformat(timespec="seconds"),
                                                "go": GO, "alpha": ALPHA, "min_n": MIN_N}, indent=2) + "\n", newline="\n")
    t0 = time.time()
    v4 = fusion.V4Bundle.load(require_calibration=False)
    v31 = pipeline.load_bundle("v3.1")
    names, n = v4.class_names, len(v4.class_names)
    table = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    y = np.array([names.index(c) for c in table["class_name"]])
    split = np.load(NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    suites = json.loads((T1 / "NB3c" / "suites.json").read_text())
    if set(np.concatenate([np.asarray(s["cell_idx"]) for s in suites["calib"] + suites["eval"]])) & set(trainval):
        raise SystemExit("a suite cell is in the reference rows")

    calib_spec = json.loads((CALIB_BUNDLE / "spec_v4.json").read_text())
    if calib_spec.get("reference_rows") != "trainval":
        raise SystemExit(f"{CALIB_BUNDLE} is not the train-plus-validation bundle")
    cb_centroids = [np.load(CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy") for m in v4.members]
    v4c = dataclasses.replace(v4, members=restricted(v4.members, trainval, cb_centroids),
                              class_means=np.load(CALIB_BUNDLE / "class_means_cb.npy"),
                              property_values=v4.property_values[trainval])
    v31_centroids = [centroids_from(m.reference_latents[trainval], y[trainval], n) for m in v31.members]
    v31c = dataclasses.replace(v31, members=restricted(v31.members, trainval, v31_centroids),
                               property_values=v31.property_values[trainval])
    v4_served = v4  # all cells: for the sensitivity check only
    profiles = dict(np.load(NB1 / "mask_profiles.npz"))
    pool = np.load(NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_X = np.load(NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_X[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    genes = v4.feature_genes
    resolution = gene_ids.resolve_identifiers(genes)
    print(f"ready ({time.time() - t0:.0f}s)", flush=True)

    def prepared(spec_):
        raw = raw_upload(spec_, get_raw, profiles, len(genes))
        ids = [f"{spec_['id']}_{i}" for i in range(len(raw))]
        return pipeline._prepare_query(genes, alignment.RawMatrix(gene_names=genes, cell_ids=ids, values=raw.T))

    # 1. fit on the calibration suite
    scores, ys, ood, scores_served, ys_served = [], [], [], [], []
    for s in suites["calib"]:
        _, aligned, _ = prepared(s)
        truth = y[np.asarray(s["cell_idx"])]
        keep = aligned.per_cell_observed_genes >= MIN_GENES
        P, Z = fusion.probabilities(v4c, aligned.values, aligned.mask)
        o = np.mean([search.faiss_max_cosine_to_reference(z, m.reference_latents) for z, m in zip(Z, v4c.members)], axis=0)
        scores.append(1 - P[np.arange(len(P)), truth][keep]); ys.append(truth[keep]); ood.append(o[keep])
        Ps, _ = fusion.probabilities(v4_served, aligned.values, aligned.mask)
        scores_served.append(1 - Ps[np.arange(len(Ps)), truth][keep]); ys_served.append(truth[keep])
    scores, ys, ood = np.concatenate(scores), np.concatenate(ys), np.concatenate(ood)
    qhat, marginal = nb2_core.fit_qhat(scores, ys, n, ALPHA, True, MIN_N)
    threshold = float(np.percentile(ood, OOD_PERCENTILE))
    q_served, _ = nb2_core.fit_qhat(np.concatenate(scores_served), np.concatenate(ys_served), n, ALPHA, True, MIN_N)
    block = {
        "conformal": {"type": "mondrian", "alpha": ALPHA, "score": "1 - fused probability of the class (LAC)",
                      "qhat_by_class": {c: float(q) for c, q in zip(names, qhat)}, "marginal_qhat": float(marginal),
                      "set_rule": "p >= 1 - qhat; the best guess joins non-empty sets (service flag)",
                      "calibrated_on": "simulated RNA uploads (T1 NB3c calibration suite, test-split cells the encoders never saw)",
                      "min_n": MIN_N, "n_calibration_cells": int(len(scores))},
        "ood": {"score": "max cosine to any reference cell, mean over members", "threshold": threshold,
                "fit": "1st percentile of in-distribution calibration-suite cells (NB3c te_cal), train and validation reference index"},
    }
    sensitivity = float(np.max(np.abs(q_served - qhat)))
    print(f"fitted: marginal qhat {marginal:.4f}, OOD threshold {threshold:.4f}, served-bundle qhat change up to {sensitivity:.4f} ({time.time() - t0:.0f}s)", flush=True)

    # 2. evaluate once
    spec4 = {**v4.spec, **block}
    comps4 = fusion.build_components(spec4)
    v4e = dataclasses.replace(v4c, spec=spec4, components=comps4)
    rows = []
    for s in suites["eval"]:
        smoothed, aligned, value_scale = prepared(s)
        truth_names = [names[k] for k in y[np.asarray(s["cell_idx"])]]
        group = GROUP[s["scenario"]]
        for method, response, probs_fn in (
                ("v4", fusion.project_prepared(v4e, aligned, value_scale, resolution, False, comps4),
                 lambda: fusion.probabilities(v4e, aligned.values, aligned.mask)[0]),
                ("v3.1", ensemble.project_prepared(v31c, smoothed, aligned, value_scale, resolution, False, v31c.components), None)):
            comps = comps4 if method == "v4" else v31c.components
            if probs_fn is not None:
                P = probs_fn()
            else:
                Zs = [m.encoder_handle.encode(smoothed, aligned.mask) for m in v31c.members]
                P = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Zs, v31c.members)])
            space = comps.label_space.estimate(None, names, False)
            sets = comps.calibrator.calibrate(comps.label_space.probabilities(P, space), None, space).label_sets
            hierarchy = v4.hierarchy
            guesses = []
            for i, cell in enumerate(response["cells"]):
                if cell["observed_genes"] < MIN_GENES:
                    continue
                t = truth_names[i]
                committed = not cell["abstained"]
                rows.append({"method": method, "upload": s["id"], "group": group, "true": t,
                             "covered": names.index(t) in set(sets[i]),
                             "ood_abstained": cell.get("abstain_reason") == abstention.AbstainReason.OUT_OF_DISTRIBUTION.value,
                             "committed": committed, "level": cell["label_level"] if committed else "abstain",
                             "correct": committed and correct_at_level(cell["label"], cell["label_level"], t, hierarchy),
                             "best_guess": cell.get("best_guess", {}).get("label")})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "eval_cells.csv.gz", index=False, lineterminator="\n")

    def summary(d):
        up = d.groupby("upload").apply(lambda u: 100 * (balanced_accuracy_score(u["true"], u["best_guess"])
                                                        if u["true"].nunique() > 1 else float((u["true"] == u["best_guess"]).mean())))
        com = d[d["committed"]]
        return {"cells": int(len(d)), "coverage": round(100 * d["covered"].mean(), 2),
                "false_abstention": round(100 * d["ood_abstained"].mean(), 2),
                "committed": round(100 * d["committed"].mean(), 2),
                "correct_when_committed": round(100 * com["correct"].mean(), 2) if len(com) else None,
                "levels": {k: round(100 * v, 2) for k, v in d["level"].value_counts(normalize=True).items()},
                "best_guess_per_upload_balanced": round(float(up.mean()), 2)}
    result = {m: summary(df[df["method"] == m]) for m in ("v4", "v3.1")}
    by_group = {m: {g: summary(df[(df["method"] == m) & (df["group"] == g)]) for g in sorted(df["group"].unique())} for m in ("v4", "v3.1")}
    per_class = (df.groupby(["method", "true"])["covered"].mean().mul(100).round(2).unstack(0))
    per_class.to_csv(OUT / "eval_per_class_coverage.csv", lineterminator="\n")
    pd.DataFrame([{"method": m, "group": g, **{k: v for k, v in r.items() if k != "levels"}} for m, gs in by_group.items() for g, r in gs.items()]).to_csv(
        OUT / "eval_by_scenario.csv", index=False, lineterminator="\n")

    a, b = result["v4"], result["v3.1"]
    drops = {g: round(by_group["v3.1"][g]["best_guess_per_upload_balanced"] - by_group["v4"][g]["best_guess_per_upload_balanced"], 2) for g in by_group["v4"]}
    checks = {k: bool(v) for k, v in {
        "coverage": a["coverage"] >= GO["coverage_min"] and a["coverage"] >= b["coverage"],
        "false_abstention": a["false_abstention"] <= GO["false_abstention_max"],
        "correct_when_committed": a["correct_when_committed"] >= GO["correct_min"],
        "best_guess_gain": a["best_guess_per_upload_balanced"] >= b["best_guess_per_upload_balanced"] + GO["best_guess_gain"],
        "no_scenario_drop": all(d <= GO["scenario_drop_max"] for d in drops.values()),
    }.items()}
    record = {"result": result, "by_scenario": by_group, "scenario_drop_vs_v31": drops, "checks": checks, "go": all(checks.values()),
              "qhat_sensitivity_served_bundle": round(sensitivity, 4), "seconds": round(time.time() - t0)}
    (OUT / "summary.json").write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    (OUT / "spec_block.json").write_text(json.dumps(block, indent=2) + "\n", newline="\n")
    print(json.dumps({k: record[k] for k in ("result", "scenario_drop_vs_v31", "checks", "go", "qhat_sensitivity_served_bundle")}, indent=1), flush=True)


if __name__ == "__main__":
    main()
