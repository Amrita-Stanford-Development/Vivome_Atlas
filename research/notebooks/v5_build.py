"""v5, Phase 3 (research/todo.md, Track H): v5's reference and calibration,
by NB1d's and NB2's recipes, from the retrained members
(research/notebooks/v5_train.py) and the cleaned labels
(research/notebooks/v5_labels.py).

Per member, as NB1d and NB2 did:
- the reference latents: nb1b_core.reference_embedding over every reference
  cell, with NB1's whole-reference statistics;
- the centroids: the class means of the latents under the labels, both
  over every cell (served) and over the train split (the calibration
  references, so a simulated cell never matches itself).

The calibration is NB2's sections 2, 4 and 6, with the choices NB2 made and
v3.1 serves:
- encoder: the five-member ensemble;
- query: smoothing on, the service convention, graph on z-scores;
- assignment: the centroid rule;
- label space: none;
- conformal: Mondrian, alpha 0.1, at least 50 cells per class (else the
  marginal quantile).
Its steps:
1. Every upload of NB1's calibration suite (sim_suite_calib_v1.json; its
   cells come from the validation split) is materialised by
   nb1b_core.raw_upload and query_inputs. Each member's cosines to the
   train-split centroids are kept, as are its maximum cosines to the
   train-split reference latents, both in float16, as NB2 kept them.
2. Each member's temperature is NB2's grid search (nb2_core.fit_temperature)
   over the whole suite.
3. Each cell's probability is the members' mean softmax. The conformal
   thresholds come from nb2_core.fit_qhat on 1 - p(true class).
4. The out-of-distribution threshold is the 1st percentile of the members'
   mean maximum cosine.

Mode "reproduce" (run first; it must pass) applies all of this to v3.1's
own members and the original labels. It must reproduce
service/model/v3_1/nb2_spec_v31.json:
- the same temperatures;
- every conformal threshold and the out-of-distribution threshold within
  1e-3;
- latents and centroids matching v3.1's served member files (median cosine
  at least 0.9999).

Amendment to the conformal check (2026-10-12, after the first reproduction,
before anything was built from v5's members). The first run reproduced:
- the temperatures and the out-of-distribution threshold exactly;
- the latents and centroids at cosine 1.0;
- 15 of the 22 classes' thresholds to 1e-8.
It failed the 1e-3 bound on plasma cell (0.666464 against NB2's 0.669117)
and was off by 2e-5 on the marginal threshold (used by the six classes
without calibration cells). NB2's plasma value is exactly this run's next
order statistic: one cell sits on the other side of the 90% quantile. The
float16 cast NB2 used moves a plasma cell's score by up to 2.3e-4, and NB2
ran on another GPU (a Colab L4). The check is therefore made rank-based:
- every class with at least 50 calibration cells, and the marginal, must
  have NB2's threshold between this run's order statistics at ranks k - 1
  and k + 1, k being the conformal rank;
- each bound is widened by 3e-4, the float16 rounding of a score.
A different recipe would move thresholds by many ranks, which this still
catches.

Mode "build" applies it to the retrained members (Drive Tier1_v31/V5/ckpt,
checked against research/notebook-outputs/v5_train/train_record.json) with
the cleaned labels. It also builds v4.1's best-guess layer on them, as
scripts/build_v4_bundle.py does for v3.1's members:
- class-balanced gene statistics and z-scored RNA class means under the
  cleaned labels;
- each member's centroids of the reference re-encoded with those
  statistics.
v4.1's settings stay fixed: fusion weight 0.7 (gate off), gate-on weight
0.5, correlation temperature 0.05, smoothed share 0.5, agreement gate 0.4.

It writes, into service/model/v5/:
- members/: the checkpoints (kept outside git like v3.1's), latents,
  centroids and class-balanced centroids;
- class_balanced_stats.npz and class_means_cb.npy;
- nb2_spec_v5.json (the answers, in v3.1's layout);
- spec_v5.json (the best guess, in v4.1's layout, evaluation pending);
- one MANIFEST.json over all of them.
Its record goes to research/notebook-outputs/v5_build/build_record.json.

Mode "spec" rewrites spec_v5.json and the MANIFEST only, taking the
evaluation from research/notebook-outputs/v5_phase4/spec_block.json once that
run has written it.

Variant v5.1 (--variant v5.1) builds the same way from v5.1's members and
labels (NK T folded into NK; research/notebooks/v51_labels.py) into
service/model/v5_1/: nb2_spec_v51.json, spec_v51.json and its MANIFEST, with
its record in research/notebook-outputs/v51_build/. The reproduction is
shared. A class without cells (NK T in v5.1) gets zero centroids and a zero
class mean, so it is never chosen.

Variant v5.4 (route B of run history entry 65) also counts the Allen
atlas's training-donor cells (research/notebooks/allen_rows.py), the rows
its members trained on, in every centroid (served and calibration) and in
v4.1's class-balanced statistics, class means and centroids. The reference
latents, the calibration suite and the out-of-distribution reference stay
Tabula Sapiens's, the cells the service holds one by one.

Variant v5.5 (side-tests amendment 23; research/notebooks/v55_gates.py)
trains nothing: v5.4's members, centroids and best-guess layer, copied
from service/model/v5_4/ and checked against its MANIFEST, with the answers
recalibrated. v5.4's calibration suite had no myeloid DC, pDC, CMP or
regulatory T cell, so those classes took the marginal threshold (run
history entry 66). Fixed before the run:
- **Cells:** the 22 Allen donors held out of v5.4's training
  (allen_rows.py's rows; never trained on), sorted and shuffled with seed
  0: the first 11 calibrate, the other 11 check.
- **Uploads:** NB1's generator (sim_generator.make_suite's steps, its sizes
  and profiles) over each half's rows: 120 calibration uploads (seed 0) and
  60 check uploads (seed 1), without the scope2_like scenario, since the
  Allen atlas has no macrophages.
- **Fit:** NB2's recipe as above, the temperatures and the conformal
  thresholds on Tabula Sapiens's 240 uploads and the 120 Allen uploads
  together. The out-of-distribution threshold stays the Tabula Sapiens
  uploads' (v5.4's): its reference is Tabula Sapiens's cells.
- **Self-check first:** Tabula Sapiens's uploads alone must give v5.4's
  temperatures and out-of-distribution threshold, and its thresholds
  within one rank (the reproduction's check), else stop.
- **Recorded:** the suite's top-1 on Tabula Sapiens's uploads (comparable
  with v3.1's), on the Allen uploads and on both; and on the check uploads,
  each class's coverage (the true class in the conformal set, before the
  best guess joins it) and the share of one-class sets.

    python research/notebooks/v5_build.py reproduce      # from the repository root
    python research/notebooks/v5_build.py build
    python research/notebooks/v5_build.py spec
    python research/notebooks/v5_build.py build --variant v5.1
    python research/notebooks/v5_build.py build --variant v5.2      # into service/model/v5_2/, likewise
    python research/notebooks/v5_build.py build --variant v5.5      # v5.4's members, recalibrated
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v5_train as train  # noqa: E402  (setup, load_model, core, bundle)

from service import config  # noqa: E402
from service.pipeline import encoder  # noqa: E402
from service.pipeline.fusion import class_balanced_stats, class_means  # noqa: E402

core, bundle = train.core, train.bundle
sys.path.insert(0, str(bundle.NB1))
import sim_generator as sg  # noqa: E402  (NB1's own copy on Drive)

sys.path.insert(0, str(REPO / "research" / "notebook-outputs" / "nb2"))
import nb2_core as n2  # noqa: E402

V5_DIR = REPO / "service" / "model" / "v5"
OUT = REPO / "research" / "notebook-outputs" / "v5_build"
PHASE4_BLOCK = REPO / "research" / "notebook-outputs" / "v5_phase4" / "spec_block.json"
VARIANTS = {
    "v5": {"dir": V5_DIR, "out": OUT, "phase4": PHASE4_BLOCK, "answers": "nb2_spec_v5.json", "spec": "spec_v5.json"},
    "v5.1": {"dir": REPO / "service" / "model" / "v5_1", "out": REPO / "research" / "notebook-outputs" / "v51_build",
             "phase4": REPO / "research" / "notebook-outputs" / "v51_phase4" / "spec_block.json",
             "answers": "nb2_spec_v51.json", "spec": "spec_v51.json"},
    "v5.2": {"dir": REPO / "service" / "model" / "v5_2", "out": REPO / "research" / "notebook-outputs" / "v52_build",
             "phase4": REPO / "research" / "notebook-outputs" / "v52_phase4" / "spec_block.json",
             "answers": "nb2_spec_v52.json", "spec": "spec_v52.json"},
    # v5.3: pooled training on the original labels; its evaluation is v53_gates.py's block
    "v5.3": {"dir": REPO / "service" / "model" / "v5_3", "out": REPO / "research" / "notebook-outputs" / "v53_build",
             "phase4": REPO / "research" / "notebook-outputs" / "v53_gates" / "spec_block.json",
             "answers": "nb2_spec_v53.json", "spec": "spec_v53.json"},
    # v5.4: the Allen atlas's training-donor cells in training and in the centroids; v54_gates.py's block
    "v5.4": {"dir": REPO / "service" / "model" / "v5_4", "out": REPO / "research" / "notebook-outputs" / "v54_build",
             "phase4": REPO / "research" / "notebook-outputs" / "v54_gates" / "spec_block.json",
             "answers": "nb2_spec_v54.json", "spec": "spec_v54.json"},
    # v5.5: v5.4's members, recalibrated with Allen cells of donors held out of training; v55_gates.py's block
    "v5.5": {"dir": REPO / "service" / "model" / "v5_5", "out": REPO / "research" / "notebook-outputs" / "v55_build",
             "phase4": REPO / "research" / "notebook-outputs" / "v55_gates" / "spec_block.json",
             "answers": "nb2_spec_v55.json", "spec": "spec_v55.json", "members_of": "v5.4"},
}
K_NN, ALPHA, MIN_N = 15, 0.10, 50
# v5.5 (the docstring): the held-out donors' split and the Allen uploads
ALLEN_SPLIT_SEED, CALIB_DONORS = 0, 11
ALLEN_CALIB_UPLOADS, ALLEN_CALIB_SEED = 120, 0
ALLEN_CHECK_UPLOADS, ALLEN_CHECK_SEED = 60, 1
ALLEN_SCENARIOS = ["random_1", "random_2", "random_3", "random_5", "random_8"] * 2 + ["myeloid", "lymphoid", "pbmc_like"]
ALLEN_TARGETS = ("myeloid dendritic cell", "plasmacytoid dendritic cell", "common myeloid progenitor", "regulatory t cell")
TOL_Q, TOL_COS = 1e-3, 0.9999
RANK_SLACK = 3e-4  # the float16 rounding of a conformal score (the amendment above)


@torch.no_grad()
def member_scores(model, xs, M, ref_tr, cen_tr, device, chunk=4096):
    """NB2's class_scores, centroid half: cosines to the centroids and the
    maximum cosine to the reference, both float16 as NB2 stored them."""
    Z = torch.from_numpy(core.encode_inputs(model, xs, M, device)).to(device)
    cos = (Z @ cen_tr.T).cpu().numpy().astype(np.float16)
    Zh, mx = Z.half(), []
    for i in range(0, len(Zh), chunk):
        v, _ = (Zh[i:i + chunk] @ ref_tr.T).topk(K_NN, dim=1)
        mx.append(v[:, 0].float().cpu())
    return cos, torch.cat(mx).numpy().astype(np.float16)


def suite_scores(models: dict, suite: list, X: np.ndarray, y: np.ndarray, ref_tr: dict, cen_tr: dict, G: int,
                 device, t0: float, what: str = "calibration suite") -> tuple:
    """Step 1 on one suite whose cell_idx index X's rows: each member's cosines
    to the train-split centroids and maximum cosines to the train-split
    reference latents (float16), and the cells' labels."""
    profiles = dict(np.load(bundle.NB1 / "mask_profiles.npz"))
    cos = {k: [] for k in models}
    maxcos = {k: [] for k in models}
    ys = []
    for u, spec in enumerate(suite):
        raw, gs = core.raw_upload(spec, X, profiles, G, sg)
        xs, M = core.query_inputs(raw, gs, "gene", convention="service", graph_input="zscored", smooth=True)
        for k, m in models.items():
            c, mx = member_scores(m, xs, M, ref_tr[k], cen_tr[k], device)
            cos[k].append(c)
            maxcos[k].append(mx)
        ys.append(y[np.asarray(spec["cell_idx"])])
        if (u + 1) % 50 == 0:
            print(f"{what}: {u + 1}/{len(suite)} uploads ({time.time() - t0:.0f}s)", flush=True)
    return ({k: np.concatenate(v) for k, v in cos.items()}, {k: np.concatenate(v) for k, v in maxcos.items()},
            np.concatenate(ys))


def mean_probabilities(cos: dict, temps: dict) -> np.ndarray:
    """The members' mean softmax of their cosines under their temperatures."""
    P = 0.0
    for k, L in cos.items():
        P = P + n2.softmax(L.astype(np.float64), temps[k])
    return P / len(cos)


def fit_answers(cos: dict, maxcos: dict, yy: np.ndarray, names: list) -> dict:
    """Steps 2 to 4 on one suite's scores."""
    C = len(names)
    temps = {k: n2.fit_temperature(L.astype(np.float64), yy)[0] for k, L in cos.items()}
    P = mean_probabilities(cos, temps)
    scores = 1.0 - P[np.arange(len(yy)), yy]
    q, marg = n2.fit_qhat(scores, yy, C, ALPHA, True, MIN_N)
    mc = np.mean([v.astype(np.float32) for v in maxcos.values()], 0)
    return {"temperature": temps, "scores": scores, "y": yy, "qhat": q,
            "qhat_by_class": {names[c]: float(q[c]) for c in range(C)}, "marginal_qhat": float(marg),
            "ood_threshold": float(np.quantile(mc, 0.01)), "n_cells": int(len(yy)),
            "cells_per_class": {names[c]: int((yy == c).sum()) for c in range(C)},
            "suite_top1_accuracy": round(100 * float((P.argmax(1) == yy).mean()), 3)}


def build(members: dict, y: np.ndarray, s: dict, X_raw: np.ndarray, t0: float, extra: "dict | None" = None,
          allen: "dict | None" = None) -> dict:
    """members: name -> checkpoint path. Returns latents, centroids, calibration.
    extra (v5.4): another atlas's training rows, counted in every centroid.
    allen (v5.5): the held-out Allen rows ("X", "y") and two suites over
    them: "calib" joins the fit, "check" is scored under it. Then the
    out-of-distribution threshold and the top-1 are Tabula Sapiens's
    uploads', and "ts_only" is the fit on those uploads alone."""
    names, C, device = s["names"], len(s["names"]), s["device"]
    TR = s["TR"]
    if extra is not None:
        XE = torch.from_numpy(extra["X"]).to(device, dtype=torch.float16)
        yE = extra["y"].astype(y.dtype)
    models, lat, cen_all, ref_tr, cen_tr = {}, {}, {}, {}, {}
    for name, path in members.items():
        m = train.load_model(path, s)
        Z = core.reference_embedding(m, s["XG"], "batch_gene", s["mu"], s["sd"], device)
        models[name], lat[name] = m, Z.astype(np.float16)
        ref = torch.from_numpy(Z).to(device, torch.float16)
        ref_tr[name] = ref[torch.from_numpy(TR).to(device)]
        if extra is None:
            cen_all[name] = core.centroids_from(Z, y, C)
            cen_tr[name] = torch.from_numpy(core.centroids_from(Z[TR], y[TR], C)).to(device)
        else:
            ZE = core.reference_embedding(m, XE, "batch_gene", s["mu"], s["sd"], device)
            cen_all[name] = core.centroids_from(np.vstack([Z, ZE]), np.concatenate([y, yE]), C)
            cen_tr[name] = torch.from_numpy(core.centroids_from(np.vstack([Z[TR], ZE]),
                                                                np.concatenate([y[TR], yE]), C)).to(device)
    print(f"reference latents for {len(models)} members ({time.time() - t0:.0f}s)", flush=True)
    suite = json.loads((bundle.NB1 / "sim_suite_calib_v1.json").read_text())
    G = s["XG"].shape[1]
    cos, maxcos, yy = suite_scores(models, suite, X_raw, y, ref_tr, cen_tr, G, device, t0)
    ts = fit_answers(cos, maxcos, yy, names)
    if allen is None:
        return {"latents": lat, "centroids": cen_all, **ts, "n_uploads": len(suite)}
    cos_a, maxcos_a, ya = suite_scores(models, allen["calib"], allen["X"], allen["y"], ref_tr, cen_tr, G, device, t0,
                                       "Allen calibration uploads")
    both = fit_answers({k: np.concatenate([cos[k], cos_a[k]]) for k in models},
                       {k: np.concatenate([maxcos[k], maxcos_a[k]]) for k in models}, np.concatenate([yy, ya]), names)
    cos_c, _, yc = suite_scores(models, allen["check"], allen["X"], allen["y"], ref_tr, cen_tr, G, device, t0,
                                "Allen check uploads")
    def top1(scores: dict, labels: np.ndarray) -> float:
        return round(100 * float((mean_probabilities(scores, both["temperature"]).argmax(1) == labels).mean()), 3)

    P_c = mean_probabilities(cos_c, both["temperature"])
    sets = n2.prediction_sets(P_c, both["qhat"], np.ones(C, dtype=bool))
    check = {}
    for c in np.unique(yc):
        at = yc == c
        check[names[c]] = {"n": int(at.sum()), "coverage": round(100 * float(sets[at, c].mean()), 2),
                           "one_class_sets": round(100 * float((sets[at].sum(1) == 1).mean()), 2),
                           "top1": round(100 * float((P_c[at].argmax(1) == c).mean()), 2)}
    return {"latents": lat, "centroids": cen_all, **both, "ts_only": ts,
            "ood_threshold": ts["ood_threshold"], "n_uploads": len(suite) + len(allen["calib"]),
            "n_uploads_allen": len(allen["calib"]),
            "allen_cells_per_class": {names[c]: int((ya == c).sum()) for c in range(C)},
            "suite_top1_accuracy": top1(cos, yy), "suite_top1_accuracy_allen": top1(cos_a, ya),
            "suite_top1_accuracy_both": both["suite_top1_accuracy"],
            "check": {"n_uploads": len(allen["check"]), "n_cells": int(len(yc)), "by_class": check}}


def within_one_rank(scores: np.ndarray, y: np.ndarray, names: list, conformal: dict) -> dict:
    """The reproduction's conformal check (the amendment above): a spec's
    threshold for the marginal and for every class with at least MIN_N cells
    lies between this run's order statistics at ranks k - 1 and k + 1, k the
    conformal rank, each bound widened by RANK_SLACK."""
    out = {}
    for label, sc, target in ([("marginal", scores, conformal["marginal_qhat"])]
                              + [(c, scores[y == names.index(c)], conformal["qhat_by_class"][c])
                                 for c in names if (y == names.index(c)).sum() >= MIN_N]):
        ordered = np.sort(sc)
        k = int(np.ceil(n2.conformal_level(len(ordered), ALPHA) * (len(ordered) - 1)))  # np.quantile's "higher" index
        lo, hi = ordered[max(k - 1, 0)] - RANK_SLACK, ordered[min(k + 1, len(ordered) - 1)] + RANK_SLACK
        out[label] = bool(lo <= target <= hi)
    return out


def reproduce(s: dict, X_raw: np.ndarray) -> None:
    t0 = time.time()
    spec = json.loads(config.V31_SPEC_PATH.read_text())
    members = {n: config.V31_MEMBERS_DIR / n for n in spec["encoder"]["members"]}
    got = build(members, s["y_all"], s, X_raw, t0)
    checks, detail = {}, {}
    detail["temperature"] = {k: (got["temperature"][k], spec["assignment"]["temperature"][k]) for k in members}
    checks["temperature"] = all(abs(a - b) < 1e-12 for a, b in detail["temperature"].values())
    gap = {c: abs(got["qhat_by_class"][c] - spec["conformal"]["qhat_by_class"][c]) for c in got["qhat_by_class"]}
    detail["qhat_largest_gap"] = max(gap.values())
    detail["qhat_within_one_rank"] = within_one_rank(got["scores"], got["y"], s["names"], spec["conformal"])
    checks["qhat"] = all(detail["qhat_within_one_rank"].values())
    detail["ood"] = (got["ood_threshold"], spec["ood"]["threshold"])
    checks["ood_threshold"] = abs(got["ood_threshold"] - spec["ood"]["threshold"]) <= TOL_Q
    cosines = {}
    for name in members:
        seed = name.split("seed")[1].split(".")[0]
        served = np.load(config.V31_MEMBERS_DIR / f"V2_seed{seed}_reference_latent_f16.npy").astype(np.float32)
        mine = got["latents"][name].astype(np.float32)
        served_c = np.load(config.V31_MEMBERS_DIR / f"V2_seed{seed}_centroids.npy")
        cosines[name] = {"latents_median": float(np.median((mine * served).sum(1) / np.linalg.norm(mine, axis=1)
                                                           / np.linalg.norm(served, axis=1))),
                         "centroids_min": float(((got["centroids"][name] * served_c).sum(1)).min())}
    detail["member_files"] = cosines
    checks["member_files"] = all(v["latents_median"] >= TOL_COS and v["centroids_min"] >= TOL_COS for v in cosines.values())
    passed = all(checks.values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reproduce.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"), "gpu": torch.cuda.get_device_name(0),
        "checks": checks, "detail": detail, "passed": passed, "suite_top1_accuracy": got["suite_top1_accuracy"],
        "seconds": round(time.time() - t0)}, indent=2) + "\n", newline="\n")
    print(json.dumps({"checks": checks, "detail": detail}, indent=1, default=str))
    print("reproduction " + ("PASSED" if passed else "FAILED: do not build v5"))


def write_spec(got: dict, record: dict, variant: str = "v5") -> dict:
    v31 = json.loads(config.V31_SPEC_PATH.read_text())
    spec = json.loads(json.dumps(v31))
    spec["created"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    spec["source"] = (f"research/notebooks/v5_build.py: NB2's recipe on {variant}'s members (research/notebooks/v5_train.py), "
                      f"labels {record['labels']}")
    spec["encoder"]["family"] = "V2, retrained on the cleaned labels (same architecture, recipe and split as NB1d)"
    spec["assignment"]["temperature"] = got["temperature"]
    spec["conformal"]["qhat_by_class"] = got["qhat_by_class"]
    spec["conformal"]["marginal_qhat"] = got["marginal_qhat"]
    spec["conformal"]["calibrated_on"] = ("labelled RNA simulated uploads (NB1 calibration suite, validation split cells), "
                                          "cleaned labels")
    spec["ood"]["threshold"] = got["ood_threshold"]
    spec["labels"] = record["labels"]
    return spec


def best_guess_layer(members: dict, y: np.ndarray, X_raw: np.ndarray, n_classes: int,
                     extra: "dict | None" = None) -> dict:
    """v4.1's reference side on v5's members (scripts/build_v4_bundle.py's
    steps): class-balanced statistics, class means, and each member's
    centroids of the reference re-encoded under those statistics. extra
    (v5.4): another atlas's training rows, counted in all three."""
    if extra is not None:
        X_raw = np.vstack([X_raw, extra["X"].astype(np.float32)])
        y = np.concatenate([y, extra["y"].astype(y.dtype)])
    mu, sd = class_balanced_stats(X_raw, y, n_classes)
    means = class_means(X_raw, y, n_classes, mu, sd)
    cb = {}
    for name, path in members.items():
        Z = bundle.encode(encoder.load_encoder(path), X_raw, mu, sd)
        C = np.stack([Z[y == k].mean(0) if (y == k).any() else np.zeros(Z.shape[1]) for k in range(n_classes)])
        cb[name] = (C / np.maximum(np.linalg.norm(C, axis=1, keepdims=True), 1e-12)).astype(np.float32)
    return {"mu": mu, "sd": sd, "means": means.astype(np.float32), "centroids_cb": cb}


def make_v5_spec(answers: dict, labels: str, variant: str = "v5") -> dict:
    """v4.1's spec (service/model/v4_1/spec_v41.json) with v5's members,
    answers and labels, its fusion settings unchanged. The evaluation comes
    from Phase 4's spec block once written; pending until then."""
    v41 = json.loads(config.V41_SPEC_PATH.read_text(encoding="utf-8"))
    spec = json.loads(json.dumps(v41))
    v = VARIANTS[variant]
    home = v["dir"].relative_to(REPO).as_posix()
    spec["version"] = variant
    spec["created"] = datetime.now().strftime("%Y-%m-%d")
    spec["source"] = (f"v4.1's spec (service/model/v4_1/spec_v41.json) on {variant}'s members and labels; "
                      "built by research/notebooks/v5_build.py")
    spec["based_on"] = {"spec": "service/model/v4_1/spec_v41.json",
                        "sha256": hashlib.sha256(config.V41_SPEC_PATH.read_bytes()).hexdigest()}
    spec["encoder"] = {"members": answers["encoder"]["members"], "files": f"{home} (its MANIFEST)"}
    spec["reference"]["ood_and_coordinates"] = f"{variant}'s reference latents"
    spec["reference"]["labels"] = labels
    spec["answers"] = {"from": variant, "spec": f"{home}/{v['answers']}",
                       "what": (f"conformal sets, abstention, answer levels, coordinates and properties from {variant}'s members; "
                                f"the fused best guess joins non-empty sets beside {variant}'s")}
    spec["best_guess"]["temperature"] = answers["assignment"]["temperature"]
    block = json.loads(v["phase4"].read_text(encoding="utf-8")) if v["phase4"].exists() else {}
    spec["evaluation"] = block.get("evaluation", {"status": "pending", "record": None})
    return spec


def write_manifest(files: dict, directory: Path = V5_DIR) -> None:
    manifest = {"source": ("research/notebooks/v5_build.py (members from research/notebooks/v5_train.py, "
                           "labels from research/notebooks/v5_labels.py)"),
                "files": {rel: {"sha256": hashlib.sha256((directory / rel).read_bytes()).hexdigest(),
                                "bytes": (directory / rel).stat().st_size, "from": what} for rel, what in files.items()}}
    (directory / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", newline="\n")


def build_v5(s: dict, X_raw: np.ndarray, variant: str = "v5") -> None:
    t0 = time.time()
    rep = json.loads((OUT / "reproduce.json").read_text()) if (OUT / "reproduce.json").exists() else {}
    if not rep.get("passed"):
        raise SystemExit("the reproduction has not passed (research/notebook-outputs/v5_build/reproduce.json)")
    v, tv = VARIANTS[variant], train.VARIANTS[variant]
    target, record_dir = v["dir"], v["out"]
    trained = json.loads((tv["out"] / "train_record.json").read_text())
    members = {}
    for name, entry in trained["members"].items():
        path = tv["ckpt"] / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"{path} is not the checkpoint v5_train.py recorded")
        members[name] = path
    extra = None
    if tv.get("extra"):
        rows = np.load(tv["extra"])
        if hashlib.sha256(tv["extra"].read_bytes()).hexdigest() != trained["extra"]["sha256"]:
            raise SystemExit(f"{tv['extra']} is not the file the members trained on")
        extra = {"X": rows["X_train"], "y": rows["y_train"]}
    got = build(members, s["y_clean"], s, X_raw, t0, extra)
    layer = best_guess_layer(members, s["y_clean"], X_raw, len(s["names"]), extra)
    which = ("the original labels" if variant == "v5.3" else
             "the original labels, with the Allen atlas's training-donor cells" if variant == "v5.4" else
             "the cleaned labels")
    print(f"best-guess layer built ({time.time() - t0:.0f}s)", flush=True)
    (target / "members").mkdir(parents=True, exist_ok=True)
    files = {}
    for name, path in members.items():
        seed = name.split("seed")[1].split(".")[0]
        shutil.copyfile(path, target / "members" / name)
        np.save(target / "members" / f"V2_seed{seed}_reference_latent_f16.npy", got["latents"][name])
        np.save(target / "members" / f"V2_seed{seed}_centroids.npy", got["centroids"][name].astype(np.float32))
        np.save(target / "members" / f"V2_seed{seed}_centroids_cb.npy", layer["centroids_cb"][name])
        files[f"members/{name}"] = f"v5_train.py checkpoint ({tv['ckpt_record']}/{name})"
        files[f"members/V2_seed{seed}_reference_latent_f16.npy"] = "all reference cells, reference_metadata.csv row order"
        files[f"members/V2_seed{seed}_centroids.npy"] = f"class means of the reference latents under {which}, class_idx order"
        files[f"members/V2_seed{seed}_centroids_cb.npy"] = f"{name} centroids under class-balanced statistics ({which})"
    np.savez(target / "class_balanced_stats.npz", mu=layer["mu"], sd=layer["sd"])
    np.save(target / "class_means_cb.npy", layer["means"])
    files["class_balanced_stats.npz"] = f"per-gene class-balanced mean and SD over all reference cells, {which}"
    files["class_means_cb.npy"] = f"class-balanced z-scored RNA class means under {which}, class position order (22 x 9,002)"
    labels = tv["labels"]
    record = {"labels": f"{labels.relative_to(REPO).as_posix()} (sha256 {hashlib.sha256(labels.read_bytes()).hexdigest()})"}
    if extra is not None:
        record["extra_rows"] = {"file": tv["extra"].name, "sha256": trained["extra"]["sha256"], "rows": int(len(extra["y"])),
                                "counted_in": "every centroid; the class-balanced statistics and class means"}
    answers = write_spec(got, record, variant)
    (target / v["answers"]).write_text(json.dumps(answers, indent=2) + "\n", newline="\n")
    files[v["answers"]] = f"{variant}'s answers: temperatures, conformal thresholds, out-of-distribution threshold (NB2's layout)"
    (target / v["spec"]).write_text(json.dumps(make_v5_spec(answers, record["labels"], variant), indent=2) + "\n", newline="\n")
    files[v["spec"]] = f"{variant}'s best guess (v4.1's layout and settings)"
    write_manifest(files, target)
    record_dir.mkdir(parents=True, exist_ok=True)
    (record_dir / "build_record.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "variant": variant,
        "run": datetime.now().isoformat(timespec="seconds"), "gpu": torch.cuda.get_device_name(0), **record,
        "temperature": got["temperature"], "marginal_qhat": got["marginal_qhat"], "ood_threshold": got["ood_threshold"],
        "qhat_by_class": got["qhat_by_class"], "n_uploads": got["n_uploads"], "n_cells": got["n_cells"],
        "cells_per_class": got["cells_per_class"], "suite_top1_accuracy": got["suite_top1_accuracy"],
        "files": files, "seconds": round(time.time() - t0)}, indent=2) + "\n", newline="\n")
    print(f"wrote {len(files)} files to {target} ({time.time() - t0:.0f}s)")


def allen_split(donors: np.ndarray) -> tuple:
    """v5.5's split of the held-out donors (the docstring): a calibration mask
    over the rows, and the calibration and check donors."""
    order = [str(d) for d in np.random.default_rng(ALLEN_SPLIT_SEED).permutation(sorted({str(d) for d in donors}))]
    calib = order[:CALIB_DONORS]
    return np.isin(donors.astype(str), calib), sorted(calib), sorted(order[CALIB_DONORS:])


def allen_suite(name: str, idx: np.ndarray, y: np.ndarray, classes: list, n_uploads: int, seed: int) -> list:
    """sim_generator.make_suite's steps (its sizes, profiles, proportions and
    draws, in its order) over the rows idx, with ALLEN_SCENARIOS."""
    rng = np.random.default_rng(seed)
    by_class = {c: idx[y[idx] == c] for c in np.unique(y[idx])}
    eligible = np.array([c for c, v in by_class.items() if len(v) >= 20])
    specs = []
    for u in range(n_uploads):
        sc = ALLEN_SCENARIOS[u % len(ALLEN_SCENARIOS)]
        cls = sg._scenario_classes(sc, eligible, classes, rng)
        props = rng.dirichlet(np.ones(len(cls)))
        want = np.maximum(5, np.round(props * int(rng.choice(sg.SIZES)))).astype(int)
        scale = min(1.0, float(np.min(np.array([len(by_class[c]) for c in cls]) / want)))
        take = np.maximum(3, np.floor(want * scale)).astype(int)
        cell_idx = np.concatenate([rng.choice(by_class[c], min(t, len(by_class[c])), replace=False)
                                   for c, t in zip(cls, take)])
        prof = str(rng.choice(sg.PROFILE_CHOICES))
        miss = "per_cell" if (not prof.startswith("random") and rng.random() < 0.5) else "none"
        specs.append({"id": f"{name}_{u:04d}", "suite": name, "scenario": sc, "classes": [classes[c] for c in cls],
                      "cell_idx": [int(i) for i in cell_idx], "profile": prof, "missingness": miss,
                      "stress": bool(rng.random() < 0.15), "seed": int(rng.integers(0, 2**31 - 1))})
    return specs


def build_v55(s: dict, X_raw: np.ndarray) -> None:
    """v5.5 (the docstring): v5.4's files and members, its answers refitted
    with the held-out Allen donors' calibration uploads."""
    t0 = time.time()
    rep = json.loads((OUT / "reproduce.json").read_text()) if (OUT / "reproduce.json").exists() else {}
    if not rep.get("passed"):
        raise SystemExit("the reproduction has not passed (research/notebook-outputs/v5_build/reproduce.json)")
    variant = "v5.5"
    v = VARIANTS[variant]
    src, tv = VARIANTS[v["members_of"]], train.VARIANTS[v["members_of"]]
    names = s["names"]
    trained = json.loads((tv["out"] / "train_record.json").read_text())
    members = {}
    for name, entry in trained["members"].items():
        path = tv["ckpt"] / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"{path} is not the checkpoint v5_train.py recorded")
        members[name] = path
    if hashlib.sha256(tv["extra"].read_bytes()).hexdigest() != trained["extra"]["sha256"]:
        raise SystemExit(f"{tv['extra']} is not the file the members trained on")
    rows = np.load(tv["extra"], allow_pickle=True)  # the donors are strings
    extra = {"X": rows["X_train"], "y": rows["y_train"]}
    calib_rows, calib_donors, check_donors = allen_split(rows["donor_hold"])
    yh = rows["y_hold"]
    allen = {"X": rows["X_hold"], "y": yh,
             "calib": allen_suite("allen_calib", np.flatnonzero(calib_rows), yh, names, ALLEN_CALIB_UPLOADS, ALLEN_CALIB_SEED),
             "check": allen_suite("allen_check", np.flatnonzero(~calib_rows), yh, names, ALLEN_CHECK_UPLOADS, ALLEN_CHECK_SEED)}
    drawn = np.concatenate([yh[np.asarray(u["cell_idx"])] for u in allen["calib"]])
    short = {c: int((drawn == names.index(c)).sum()) for c in ALLEN_TARGETS if (drawn == names.index(c)).sum() < MIN_N}
    if short:
        raise SystemExit(f"the Allen calibration uploads hold fewer than {MIN_N} cells of {short}: no member was run")
    old = json.loads((src["dir"] / "MANIFEST.json").read_text(encoding="utf-8"))
    for rel, entry in old["files"].items():
        if hashlib.sha256((src["dir"] / rel).read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"{src['dir'] / rel} is not v5.4's file: rebuild v5.4 first")
    got = build(members, s["y_clean"], s, X_raw, t0, extra, allen)

    a54 = json.loads((src["dir"] / src["answers"]).read_text(encoding="utf-8"))
    ts = got["ts_only"]
    detail = {"temperature": {k: (ts["temperature"][k], a54["assignment"]["temperature"][k]) for k in members},
              "ood": (ts["ood_threshold"], a54["ood"]["threshold"]),
              "qhat_within_one_rank": within_one_rank(ts["scores"], ts["y"], names, a54["conformal"]),
              "centroids_min_cosine": {}}
    for name in members:
        seed = name.split("seed")[1].split(".")[0]
        served = np.load(src["dir"] / "members" / f"V2_seed{seed}_centroids.npy")
        detail["centroids_min_cosine"][name] = float((got["centroids"][name] * served).sum(1).min())
    self_check = {"temperature": all(abs(a - b) < 1e-12 for a, b in detail["temperature"].values()),
                  "ood_threshold": abs(ts["ood_threshold"] - a54["ood"]["threshold"]) <= TOL_Q,
                  "qhat": all(detail["qhat_within_one_rank"].values()),
                  "centroids": all(c >= TOL_COS for c in detail["centroids_min_cosine"].values())}
    v["out"].mkdir(parents=True, exist_ok=True)
    if not all(self_check.values()):
        (v["out"] / "self_check.json").write_text(json.dumps({"checks": self_check, "detail": detail}, indent=2,
                                                             default=str) + "\n", newline="\n")
        raise SystemExit(f"STOP: Tabula Sapiens's uploads alone did not give v5.4's answers: {self_check}")
    print(f"self-check passed; refitted with the Allen uploads ({time.time() - t0:.0f}s)", flush=True)

    target = v["dir"]
    files = {}
    for rel, entry in old["files"].items():
        if rel in (src["answers"], src["spec"]):
            continue
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src["dir"] / rel, target / rel)
        files[rel] = f"v5.4's file: {entry['from']}"
    labels = tv["labels"]
    record = {"labels": f"{labels.relative_to(REPO).as_posix()} (sha256 {hashlib.sha256(labels.read_bytes()).hexdigest()})"}
    answers = write_spec(got, record, variant)
    answers["source"] = (f"research/notebooks/v5_build.py: NB2's recipe on v5.4's members (variant v5.5), "
                         f"labels {record['labels']}")
    answers["encoder"] = a54["encoder"]
    answers["conformal"]["calibrated_on"] = (
        "labelled RNA simulated uploads: NB1's calibration suite (Tabula Sapiens validation-split cells) and "
        f"{ALLEN_CALIB_UPLOADS} uploads of the Allen atlas's cells from {CALIB_DONORS} donors held out of v5.4's training")
    answers["ood"]["threshold"] = a54["ood"]["threshold"]
    answers["ood"]["fit"] = a54["ood"]["fit"] + " (Tabula Sapiens's uploads: v5.4's)"
    (target / v["answers"]).write_text(json.dumps(answers, indent=2) + "\n", newline="\n")
    files[v["answers"]] = f"{variant}'s answers: temperatures, conformal thresholds, out-of-distribution threshold (NB2's layout)"
    (target / v["spec"]).write_text(json.dumps(make_v5_spec(answers, record["labels"], variant), indent=2) + "\n", newline="\n")
    files[v["spec"]] = f"{variant}'s best guess (v4.1's layout and settings)"
    write_manifest(files, target)
    keep = ("temperature", "marginal_qhat", "ood_threshold", "qhat_by_class", "n_uploads", "n_uploads_allen", "n_cells",
            "cells_per_class", "allen_cells_per_class", "suite_top1_accuracy", "suite_top1_accuracy_allen",
            "suite_top1_accuracy_both", "check")
    (v["out"] / "build_record.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "variant": variant,
        "run": datetime.now().isoformat(timespec="seconds"), "gpu": torch.cuda.get_device_name(0), **record,
        "members_of": v["members_of"], "self_check": self_check, "self_check_detail": detail,
        "donors": {"calibration": calib_donors, "check": check_donors},
        **{k: got[k] for k in keep}, "files": files, "seconds": round(time.time() - t0)}, indent=2, default=str) + "\n",
        newline="\n")
    print(json.dumps({k: got[k] for k in ("temperature", "suite_top1_accuracy", "suite_top1_accuracy_allen")}, indent=1))
    print(f"wrote {len(files)} files to {target} ({time.time() - t0:.0f}s)")


def rewrite_spec(variant: str = "v5") -> None:
    """spec_v5.json and the MANIFEST only; every other file must be unchanged."""
    v = VARIANTS[variant]
    target = v["dir"]
    old = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
    for rel, entry in old["files"].items():
        if rel != v["spec"] and hashlib.sha256((target / rel).read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"{rel} changed since it was built: rebuild in full")
    answers = json.loads((target / v["answers"]).read_text(encoding="utf-8"))
    previous = json.loads((target / v["spec"]).read_text(encoding="utf-8"))
    spec = make_v5_spec(answers, previous["reference"]["labels"], variant)
    (target / v["spec"]).write_text(json.dumps(spec, indent=2) + "\n", newline="\n")
    write_manifest({rel: e["from"] for rel, e in old["files"].items()}, target)
    print(f"rewrote {v['spec']} and MANIFEST.json: evaluation {spec['evaluation']['status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("reproduce", "build", "spec"))
    parser.add_argument("--variant", choices=tuple(VARIANTS), default="v5")
    args = parser.parse_args()
    mode = args.mode
    if mode == "spec":
        rewrite_spec(args.variant)
        return
    s = train.setup(train.VARIANTS[VARIANTS[args.variant].get("members_of", args.variant)]["labels"])
    meta = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    X_raw = bundle.load_rna(bundle.RNA, [g for g in pd.read_csv(config.FEATURE_SPACE_GENES_PATH)["gene"]],
                            meta["cell"].astype(str).tolist())
    if mode == "reproduce":
        reproduce(s, X_raw)
    elif args.variant == "v5.5":
        build_v55(s, X_raw)
    else:
        build_v5(s, X_raw, args.variant)


if __name__ == "__main__":
    main()
