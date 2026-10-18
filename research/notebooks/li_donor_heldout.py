"""Track I, Stage 2 (research/organ-references.md), G2: how much the colon
encoder leans on its training donors. A diagnosis, reported, never a gate:
the colon's classes follow donors so closely (TSP2 holds 1,307 of the 1,732
stem cells) that leaving a donor out can remove most of a class.

research/notebooks/donor_heldout.py's design on the colon, fixed before the
run:
- five folds, one donor each held out;
- per fold, one member (seed 1) trained with the colon's recipe
  (scripts/organ_reference/calibrate.train_member) on the other donors'
  training cells, early stopping on their validation cells;
- scored on the split's test cells as uploads of up to 500 cells per side
  (the held-out donor's, and the others'), 10 uploads per side, the polyp
  plate's missingness with per-cell dropout, genes z-scored within the
  upload, nearest class centroid (centroids from the member's embedding of
  its training cells);
- classes measurable in a fold: at least 20 test cells on both sides.
Reported per fold, unseen against seen: class balanced accuracy, group
recall and lineage recall (the nearest centroid's class mapped up the
hierarchy), and per-class recall.

Writes research/notebook-outputs/li_donor_heldout/summary.json.

    python research/notebooks/li_donor_heldout.py      # from the repository root (GPU, about 10 minutes)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import build_organ_reference as bor  # noqa: E402
from organ_reference import calibrate, data  # noqa: E402
from organ_reference import sim_generator as sg  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "li_donor_heldout"
UPLOADS, CELLS, MIN_CLASS, SEED = 10, 500, 20, 1
PROFILE = "polyp"


@torch.no_grad()
def centroids(model, s: dict, rows: np.ndarray) -> np.ndarray:
    Z = calibrate.core.reference_embedding(model, s["XG"][torch.from_numpy(rows).to(s["device"])], "batch_gene",
                                           s["mu"], s["sd"], s["device"])
    Z /= np.linalg.norm(Z, axis=1, keepdims=True)
    return calibrate.core.centroids_from(Z, s["y"][rows], s["C"])


@torch.no_grad()
def predict(model, s: dict, C: np.ndarray, uploads) -> np.ndarray:
    out = []
    for rows, observed in uploads:
        x = s["XG"][torch.from_numpy(rows).to(s["device"])].float()
        m = torch.from_numpy(observed.astype(np.float32)).to(s["device"])
        z = model.encoder(calibrate.core.standardize_t(x, m, "batch_gene"), m).cpu().numpy()
        z /= np.linalg.norm(z, axis=1, keepdims=True)
        out.append((z @ C.T).argmax(1))
    return np.concatenate(out)


def make_uploads(pool: np.ndarray, profiles: dict, seed: int):
    rng = np.random.default_rng(seed)
    gs = profiles[f"gene_set_{PROFILE}"].astype(bool)
    uploads = []
    for _ in range(UPLOADS):
        rows = np.sort(rng.choice(pool, min(CELLS, len(pool)), replace=False))
        missing = sg.sample_missingness(len(rows), gs, profiles[f"det_prob_{PROFILE}"], profiles[f"cell_frac_{PROFILE}"], rng)
        uploads.append((rows, np.broadcast_to(gs, (len(rows), len(gs))) & ~missing))
    return uploads


def scores(truth: np.ndarray, pred: np.ndarray, names: list[str], hierarchy: dict, classes: list[int]) -> dict:
    up = {lvl: np.array([hierarchy[names[k]][lvl] for k in range(len(names))]) for lvl in ("group", "lineage")}
    return {"balanced_accuracy": round(100 * float(balanced_accuracy_score(truth, pred)), 2),
            "group_recall": round(100 * float((up["group"][truth] == up["group"][pred]).mean()), 2),
            "lineage_recall": round(100 * float((up["lineage"][truth] == up["lineage"][pred]).mean()), 2),
            "recall": {names[c]: round(100 * float((pred[truth == c] == c).mean()), 1) for c in classes},
            "cells": int(len(truth))}


def main() -> None:
    t0 = time.time()
    b = bor.Build("large_intestine")
    s, arch = bor._setup(b), b.cfg["train"]
    names = b.names()
    hierarchy = json.loads(b.path("classes.json").read_text(encoding="utf-8"))["hierarchy"]
    donor = b.table()["donor"].to_numpy()
    TE = np.load(b.path("splits_seed0.npz"))["test"]
    profiles = dict(np.load(b.path("mask_profiles.npz")))
    y = s["y"]
    summary = {"design": {"uploads_per_side": UPLOADS, "cells_per_upload": CELLS, "min_class_cells": MIN_CLASS,
                          "profile": PROFILE, "seed": SEED}, "folds": {}}
    for held in sorted(set(donor)):
        out_d = donor == held
        s_fold = {**s, "TR": s["TR"][~out_d[s["TR"]]], "VA": s["VA"][~out_d[s["VA"]]]}
        model, info = calibrate.train_member(s_fold, SEED, arch)
        C = centroids(model, s, s_fold["TR"])
        unseen, seen = TE[out_d[TE]], TE[~out_d[TE]]
        classes = [int(c) for c in np.unique(y[TE]) if (y[unseen] == c).sum() >= MIN_CLASS and (y[seen] == c).sum() >= MIN_CLASS]
        result = {"train_cells": int(len(s_fold["TR"])), "classes": [names[c] for c in classes],
                  "best_val_loss": float(info["best_val_loss"]), "epochs_run": info["epochs_run"]}
        if classes:
            for side, pool in (("unseen", unseen), ("seen", seen)):
                pool = pool[np.isin(y[pool], classes)]
                ups = make_uploads(pool, profiles, seed=0 if side == "unseen" else 1)
                truth = np.concatenate([y[r] for r, _ in ups])
                result[side] = scores(truth, predict(model, s, C, ups), names, hierarchy, classes)
            result["gap_seen_minus_unseen"] = {k: round(result["seen"][k] - result["unseen"][k], 2)
                                               for k in ("balanced_accuracy", "group_recall", "lineage_recall")}
        summary["folds"][held] = result
        print(f"{held}: {len(classes)} classes; " + (f"unseen {result['unseen']['balanced_accuracy']} / group "
              f"{result['unseen']['group_recall']} / lineage {result['unseen']['lineage_recall']}; seen "
              f"{result['seen']['balanced_accuracy']} / {result['seen']['group_recall']} / {result['seen']['lineage_recall']}"
              if classes else "nothing measurable") + f" ({time.time() - t0:.0f}s)", flush=True)
        del model
        torch.cuda.empty_cache()
    measured = [f for f in summary["folds"].values() if "unseen" in f]
    summary["mean"] = {side: {k: round(float(np.mean([f[side][k] for f in measured])), 2)
                              for k in ("balanced_accuracy", "group_recall", "lineage_recall")} for side in ("unseen", "seen")}
    summary["seconds"] = round(time.time() - t0)
    OUT.mkdir(parents=True, exist_ok=True)
    data.save_json(OUT / "summary.json", summary)
    print(json.dumps(summary["mean"], indent=1))


if __name__ == "__main__":
    main()
