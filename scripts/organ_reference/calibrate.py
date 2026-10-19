"""Training, calibration and the best-guess layer, with the organ's data
passed in rather than blood's NB1 files read.

- train_member: NB1d's training cell (research/notebooks/v5_train.py's
  train), research/notebook-outputs/nb2/nb1b_core.train_variant with
  NB1d's arguments: std batch_gene, sampler mini, the labels' class prior,
  the whole-reference statistics, the split's train cells for training and
  validation cells for early stopping.
- calibrate: NB2's sections 2, 4 and 6 as research/notebooks/v5_build.py's
  build runs them: the five-member ensemble, the service's query convention
  with smoothing, the centroid rule, Mondrian conformal at alpha 0.1 with at
  least 50 cells per class (else the marginal quantile), and the 1st
  percentile of the members' mean maximum cosine as the out-of-distribution
  threshold. References are the train split, so a calibration cell never
  matches itself.
- best_guess_layer: scripts/build_v4_bundle.py's steps, class-balanced gene
  statistics, class means and each member's centroids under them.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebook-outputs" / "nb2"))
sys.path.insert(0, str(REPO / "scripts"))
import nb1b_core as core  # noqa: E402
import nb2_core as n2  # noqa: E402
from build_v4_bundle import encode  # noqa: E402

from service.pipeline import encoder  # noqa: E402
from service.pipeline.fusion import class_balanced_stats, class_means  # noqa: E402

from . import sim_generator as sg  # noqa: E402


def setup(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, modules: np.ndarray, y: np.ndarray, split) -> dict:
    device = torch.device("cuda")
    G = X.shape[1]
    assign = torch.zeros(G, int(modules.max() + 1))
    assign[torch.arange(G), torch.from_numpy(modules.astype(np.int64))] = 1.0
    return {"device": device, "XG": torch.from_numpy(X).to(device, dtype=torch.float16), "assign": assign.to(device),
            "mu": torch.from_numpy(mu.astype(np.float32)).to(device), "sd": torch.from_numpy(sd.astype(np.float32)).to(device),
            "y": y, "TR": split["train"], "VA": split["val"], "C": int(y.max() + 1)}


def load_model(path: Path, s: dict, arch: dict):
    m = core.RefModelV(s["XG"].shape[1], s["C"], tuple(arch["hidden"]), arch["dropout"], arch["latent"], s["assign"], 1).to(s["device"])
    m.load_state_dict(torch.load(path, map_location=s["device"]), strict=True)
    return m.eval()


def train_member(s: dict, seed: int, arch: dict):
    prior = np.bincount(s["y"], minlength=s["C"]) / len(s["y"])
    return core.train_variant(s["XG"], s["y"], s["TR"], s["VA"], std="batch_gene", sampler="mini", seed=seed,
                              assign=s["assign"], prior=prior, mu_t=s["mu"], sd_t=s["sd"], device=s["device"],
                              n_classes=s["C"], hidden=tuple(arch["hidden"]), dropout=arch["dropout"], latent=arch["latent"])


@torch.no_grad()
def validation(model, s: dict, seed: int) -> dict:
    """train_variant's validation for this seed: the same mask, loss and balanced accuracy."""
    G = s["XG"].shape[1]
    gen = torch.Generator(device="cpu").manual_seed(seed + 1000)
    VA_t = torch.from_numpy(np.asarray(s["VA"])).to(s["device"])
    vm = (torch.rand(len(s["VA"]), G, generator=gen) < 0.35).float().to(s["device"])
    xsv = core.standardize_t(s["XG"][VA_t].float(), vm, "batch_gene", s["mu"], s["sd"])
    L = torch.cat([model([x[i:i + 4096] for x in xsv], vm[i:i + 4096])[1] for i in range(0, len(s["VA"]), 4096)])
    yv = torch.from_numpy(s["y"][s["VA"]].astype(np.int64)).to(s["device"])
    pv = L.argmax(1).cpu().numpy()
    return {"loss": float(F.cross_entropy(L, yv).item()),
            "balanced": 100 * float(balanced_accuracy_score(s["y"][s["VA"]], pv)),
            "recall": {int(c): 100 * float((pv[s["y"][s["VA"]] == c] == c).mean()) for c in np.unique(s["y"][s["VA"]])}}


@torch.no_grad()
def member_scores(model, xs, M, ref_tr, cen_tr, device, knn: int, chunk=4096):
    """v5_build.member_scores: cosines to the centroids and the maximum cosine
    to the reference, both float16 as NB2 stored them."""
    Z = torch.from_numpy(core.encode_inputs(model, xs, M, device)).to(device)
    cos = (Z @ cen_tr.T).cpu().numpy().astype(np.float16)
    Zh, mx = Z.half(), []
    for i in range(0, len(Zh), chunk):
        v, _ = (Zh[i:i + chunk] @ ref_tr.T).topk(knn, dim=1)
        mx.append(v[:, 0].float().cpu())
    return cos, torch.cat(mx).numpy().astype(np.float16)


def fit_qhat_v2(scores: np.ndarray, y: np.ndarray, cells: np.ndarray, C: int, cal: dict, group_of: np.ndarray) -> tuple:
    """nb2_core.fit_qhat (Mondrian per true class), with organ references v2's
    two options (research/notebook-outputs/organ_v2_calibration/decisions.json):
    - "rare_min": a class with fewer unique calibration cells than this takes
      its group's pooled quantile, or the marginal one if its group is also short;
    - "floor": "chance" keeps every entry bar at or above chance, qhat at most 1 - 1/C.
    Without them it is nb2_core.fit_qhat exactly."""
    q, marg = n2.fit_qhat(scores, y, C, cal["alpha"], True, cal["min_n"])
    if cal.get("rare_min"):
        for c in range(C):
            if len(np.unique(cells[y == c])) < cal["rare_min"]:
                same = np.isin(y, np.flatnonzero(group_of == group_of[c]))
                if len(np.unique(cells[same])) >= cal["rare_min"]:
                    q[c] = float(np.quantile(scores[same], n2.conformal_level(int(same.sum()), cal["alpha"]), method="higher"))
                else:
                    q[c] = marg
    if cal.get("floor") == "chance":
        q = np.minimum(q, 1.0 - 1.0 / C)
    return q, marg


def calibrate(models: dict, s: dict, X_raw: np.ndarray, profiles: dict, suite: list, names: list[str], cal: dict,
              log=print, hierarchy: dict | None = None) -> dict:
    """v5_build.build on any organ: latents, centroids and the calibration."""
    t0 = time.time()
    y, TR, C, device = s["y"], s["TR"], s["C"], s["device"]
    lat, cen_all, ref_tr, cen_tr = {}, {}, {}, {}
    for name, m in models.items():
        Z = core.reference_embedding(m, s["XG"], "batch_gene", s["mu"], s["sd"], device)
        lat[name] = Z.astype(np.float16)
        cen_all[name] = core.centroids_from(Z, y, C)
        ref = torch.from_numpy(Z).to(device, torch.float16)
        ref_tr[name] = ref[torch.from_numpy(TR).to(device)]
        cen_tr[name] = torch.from_numpy(core.centroids_from(Z[TR], y[TR], C)).to(device)
    log(f"reference latents for {len(models)} members ({time.time() - t0:.0f}s)")
    G = s["XG"].shape[1]
    cos = {k: [] for k in models}
    maxcos = {k: [] for k in models}
    ys, ups, cells = [], [], []
    for u, spec in enumerate(suite):
        raw, gs = core.raw_upload(spec, X_raw, profiles, G, sg)
        xs, M = core.query_inputs(raw, gs, "gene", convention="service", graph_input="zscored", smooth=True)
        for k, m in models.items():
            c, mx = member_scores(m, xs, M, ref_tr[k], cen_tr[k], device, cal["knn"])
            cos[k].append(c)
            maxcos[k].append(mx)
        ys.append(y[np.asarray(spec["cell_idx"])])
        ups.append(np.full(len(spec["cell_idx"]), u, np.int32))
        cells.append(np.asarray(spec["cell_idx"]))
        if (u + 1) % 50 == 0:
            log(f"calibration suite: {u + 1}/{len(suite)} uploads ({time.time() - t0:.0f}s)")
    yy = np.concatenate(ys)
    temps, P = {}, 0.0
    for k in models:
        L = np.concatenate(cos[k]).astype(np.float64)
        temps[k] = n2.fit_temperature(L, yy)[0]
        P = P + n2.softmax(L, temps[k])
    P = P / len(models)
    scores = 1.0 - P[np.arange(len(yy)), yy]
    options = {k: cal[k] for k in ("rare_min", "floor") if k in cal}
    if options:
        groups = sorted({hierarchy[n]["group"] for n in names})
        group_of = np.array([groups.index(hierarchy[n]["group"]) for n in names])
        q, marg = fit_qhat_v2(scores, yy, np.concatenate(cells), C, cal, group_of)
    else:
        q, marg = n2.fit_qhat(scores, yy, C, cal["alpha"], True, cal["min_n"])
    mc = np.mean([np.concatenate(maxcos[k]).astype(np.float32) for k in models], 0)
    return {"latents": lat, "centroids": cen_all, "temperature": temps, "scores": scores, "y": yy,
            "upload": np.concatenate(ups), **({"qhat_options": options} if options else {}),
            "qhat_by_class": {names[c]: float(q[c]) for c in range(C)}, "marginal_qhat": float(marg),
            "ood_threshold": float(np.quantile(mc, 0.01)), "n_uploads": len(suite), "n_cells": int(len(yy)),
            "cells_per_class": {names[c]: int((yy == c).sum()) for c in range(C)},
            "suite_top1_accuracy": round(100 * float((P.argmax(1) == yy).mean()), 3)}


def best_guess_layer(paths: dict, y: np.ndarray, X_raw: np.ndarray, n_classes: int) -> dict:
    """v5_build.best_guess_layer on any organ."""
    mu, sd = class_balanced_stats(X_raw, y, n_classes)
    means = class_means(X_raw, y, n_classes, mu, sd)
    cb = {}
    for name, path in paths.items():
        Z = encode(encoder.load_encoder(path), X_raw, mu, sd)
        Cn = np.stack([Z[y == k].mean(0) if (y == k).any() else np.zeros(Z.shape[1]) for k in range(n_classes)])
        cb[name] = (Cn / np.maximum(np.linalg.norm(Cn, axis=1, keepdims=True), 1e-12)).astype(np.float32)
    return {"mu": mu, "sd": sd, "means": means.astype(np.float32), "centroids_cb": cb}
