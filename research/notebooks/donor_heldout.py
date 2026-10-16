"""Goal 2, Phase 1.6: how much does the encoder lean on its training donors?
A diagnosis on the reference RNA only; it changes nothing and decides
nothing. Rules fixed here before the run.

Tabula Sapiens's blood comes from 9 donors of very different sizes. Three
folds of about equal cell counts, fixed before the run:
F1 TSP7, TSP1, TSP25; F2 TSP14, TSP8, TSP27; F3 TSP21, TSP2, TSP10.
For each fold, one member (seed 1) is trained with the served recipe
(research/notebooks/v5_train.py: NB1d's train_variant, v3.1's labels, NB1's
statistics) on the training cells (NB1's split) of the other donors, early
stopping on their validation cells. The fold's donors are never seen.

Scored on NB1's test cells, as uploads: 10 uploads of 500 cells per side
(unseen donors: the fold's; seen donors: the others'), Fulcher's mask profile
with per-cell missingness, genes z-scored within the upload (the service's
convention), nearest class centroid (centroids from the trained member's
reference-side embedding of its training cells). Reported per fold:
- balanced accuracy, unseen against seen donors, over the classes with at
  least 20 test cells on both sides;
- recall per class on both sides;
- the served seed 1 member (trained on every donor) on the same uploads,
  for scale.
A large gap says the encoder learned donors as well as cell types, so a new
donor (and every protein dataset is one) costs accuracy before any
technology shift.

Writes research/notebook-outputs/donor_heldout/summary.json.

    python research/notebooks/donor_heldout.py      # from the repository root (GPU, about 15 minutes)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import torch
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v5_train as trainer  # noqa: E402  (setup, load_model, train, the recipe)

sys.path.insert(0, str(trainer.bundle.NB1))
import sim_generator as sg  # noqa: E402

from service import config  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "donor_heldout"
FOLDS = {"F1": ("TSP7", "TSP1", "TSP25"), "F2": ("TSP14", "TSP8", "TSP27"), "F3": ("TSP21", "TSP2", "TSP10")}
UPLOADS, CELLS, MIN_CLASS = 10, 500, 20


def donors() -> np.ndarray:
    with h5py.File(trainer.bundle.RNA, "r") as f:
        v = f["obs"]["donor"]
        return v["categories"][:].astype(str)[v["codes"][:]] if isinstance(v, h5py.Group) else v[:].astype(str)


@torch.no_grad()
def centroids(model, s: dict, rows: np.ndarray, y: np.ndarray) -> np.ndarray:
    Z = trainer.core.reference_embedding(model, s["XG"][torch.from_numpy(rows).to(s["device"])], "batch_gene",
                                         s["mu"], s["sd"], s["device"])
    Z /= np.linalg.norm(Z, axis=1, keepdims=True)
    return trainer.core.centroids_from(Z, y[rows], len(s["names"]))


@torch.no_grad()
def predict(model, s: dict, C: np.ndarray, uploads: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    out = []
    for rows, observed in uploads:
        x = s["XG"][torch.from_numpy(rows).to(s["device"])].float()
        m = torch.from_numpy(observed.astype(np.float32)).to(s["device"])
        z = model.encoder(trainer.core.standardize_t(x, m, "batch_gene"), m).cpu().numpy()
        z /= np.linalg.norm(z, axis=1, keepdims=True)
        out.append((z @ C.T).argmax(1))
    return np.concatenate(out)


def make_uploads(pool: np.ndarray, profiles: dict, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    gs = profiles["gene_set_fulcher"].astype(bool)
    uploads = []
    for _ in range(UPLOADS):
        rows = np.sort(rng.choice(pool, min(CELLS, len(pool)), replace=False))
        missing = sg.sample_missingness(len(rows), gs, profiles["det_prob_fulcher"], profiles["cell_frac_fulcher"], rng)
        uploads.append((rows, np.broadcast_to(gs, (len(rows), len(gs))) & ~missing))
    return uploads


def recall(y: np.ndarray, p: np.ndarray, classes: list[int]) -> dict:
    return {int(c): 100 * float((p[y == c] == c).mean()) for c in classes}


def main() -> None:
    t0 = time.time()
    s = trainer.setup(trainer.LABELS)
    y = s["y_all"]
    donor = donors()
    if len(donor) != len(y):
        raise SystemExit("the h5ad's donors do not match the reference")
    split = np.load(trainer.bundle.NB1 / "splits_seed0.npz")
    TE = split["test"]
    profiles = dict(np.load(trainer.bundle.NB1 / "mask_profiles.npz"))
    served = trainer.load_model(config.V31_MEMBERS_DIR / "V2_batchgene_aug_seed1.pt", s)
    C_served = centroids(served, s, s["TR"], y)
    summary = {"folds": {}}
    for name, held in FOLDS.items():
        out_d = np.isin(donor, held)
        s_fold = {**s, "TR": s["TR"][~out_d[s["TR"]]], "VA": s["VA"][~out_d[s["VA"]]]}
        model, info = trainer.train(s_fold, y, trainer.REPRO_SEED)
        C = centroids(model, s, s_fold["TR"], y)
        unseen, seen = TE[out_d[TE]], TE[~out_d[TE]]
        classes = [int(c) for c in np.unique(y[TE]) if (y[unseen] == c).sum() >= MIN_CLASS and (y[seen] == c).sum() >= MIN_CLASS]
        result = {"held_out_donors": list(held), "train_cells": int(len(s_fold["TR"])), "classes": [s["names"][c] for c in classes],
                  "best_val_loss": float(info["best_val_loss"]), "epochs_run": info["epochs_run"]}
        for side, pool in (("unseen", unseen), ("seen", seen)):
            pool = pool[np.isin(y[pool], classes)]
            ups = make_uploads(pool, profiles, seed=0 if side == "unseen" else 1)
            truth = np.concatenate([y[r] for r, _ in ups])
            for model_name, mdl, cen in (("fold", model, C), ("served", served, C_served)):
                p = predict(mdl, s, cen, ups)
                result[f"{model_name}_{side}"] = {"balanced_accuracy": 100 * float(balanced_accuracy_score(truth, p)),
                                                  "recall": {s["names"][c]: round(v, 1) for c, v in recall(truth, p, classes).items()},
                                                  "cells": int(len(truth))}
        result["gap_seen_minus_unseen"] = result["fold_seen"]["balanced_accuracy"] - result["fold_unseen"]["balanced_accuracy"]
        summary["folds"][name] = result
        print(f"{name}: unseen {result['fold_unseen']['balanced_accuracy']:.1f}  seen {result['fold_seen']['balanced_accuracy']:.1f}  "
              f"gap {result['gap_seen_minus_unseen']:.1f}  (served: unseen-side {result['served_unseen']['balanced_accuracy']:.1f}) "
              f"({time.time() - t0:.0f}s)", flush=True)
        del model
        torch.cuda.empty_cache()
    gaps = [f["gap_seen_minus_unseen"] for f in summary["folds"].values()]
    summary["mean_gap"] = float(np.mean(gaps))
    summary["seconds"] = round(time.time() - t0)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"mean gap {summary['mean_gap']:.1f} points")


if __name__ == "__main__":
    main()
