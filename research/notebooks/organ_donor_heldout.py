"""Track I (research/organ-references.md), G2 for any organ: how much its
encoder leans on its training donors. A diagnosis, reported, never a gate.
research/notebooks/li_donor_heldout.py's design and functions, with the
organ and its missingness profile as arguments:
- one fold per donor; one member (seed 1) trained on the other donors'
  training cells;
- 10 uploads of up to 500 test cells per side (the held-out donor's, the
  others'), the profile's per-cell dropout, nearest class centroid;
- classes measurable in a fold: at least 20 test cells on both sides;
- class balanced accuracy, group recall and lineage recall, unseen
  against seen.

Writes research/notebook-outputs/<organ>_donor_heldout/summary.json.

    python research/notebooks/organ_donor_heldout.py lung fulcher_rank      # from the repository root (GPU)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import build_organ_reference as bor  # noqa: E402
import li_donor_heldout as base  # noqa: E402  (centroids, predict, scores, the design constants)
from organ_reference import calibrate, data  # noqa: E402
from organ_reference import sim_generator as sg  # noqa: E402


def make_uploads(pool: np.ndarray, profiles: dict, profile: str, seed: int):
    rng = np.random.default_rng(seed)
    gs = profiles[f"gene_set_{profile}"].astype(bool)
    uploads = []
    for _ in range(base.UPLOADS):
        rows = np.sort(rng.choice(pool, min(base.CELLS, len(pool)), replace=False))
        missing = sg.sample_missingness(len(rows), gs, profiles[f"det_prob_{profile}"], profiles[f"cell_frac_{profile}"], rng)
        uploads.append((rows, np.broadcast_to(gs, (len(rows), len(gs))) & ~missing))
    return uploads


def main(organ: str, profile: str) -> None:
    t0 = time.time()
    b = bor.Build(organ)
    s, arch = bor._setup(b), b.cfg["train"]
    names = b.names()
    hierarchy = json.loads(b.path("classes.json").read_text(encoding="utf-8"))["hierarchy"]
    donor = b.table()["donor"].to_numpy()
    TE = np.load(b.path("splits_seed0.npz"))["test"]
    profiles = dict(np.load(b.path("mask_profiles.npz")))
    y = s["y"]
    summary = {"organ": organ, "design": {"uploads_per_side": base.UPLOADS, "cells_per_upload": base.CELLS,
                                          "min_class_cells": base.MIN_CLASS, "profile": profile, "seed": base.SEED}, "folds": {}}
    for held in sorted(set(donor)):
        out_d = donor == held
        s_fold = {**s, "TR": s["TR"][~out_d[s["TR"]]], "VA": s["VA"][~out_d[s["VA"]]]}
        model, info = calibrate.train_member(s_fold, base.SEED, arch)
        C = base.centroids(model, s, s_fold["TR"])
        unseen, seen = TE[out_d[TE]], TE[~out_d[TE]]
        classes = [int(c) for c in np.unique(y[TE])
                   if (y[unseen] == c).sum() >= base.MIN_CLASS and (y[seen] == c).sum() >= base.MIN_CLASS]
        result = {"train_cells": int(len(s_fold["TR"])), "classes": [names[c] for c in classes],
                  "best_val_loss": float(info["best_val_loss"]), "epochs_run": info["epochs_run"]}
        if classes:
            for side, pool in (("unseen", unseen), ("seen", seen)):
                pool = pool[np.isin(y[pool], classes)]
                ups = make_uploads(pool, profiles, profile, seed=0 if side == "unseen" else 1)
                truth = np.concatenate([y[r] for r, _ in ups])
                result[side] = base.scores(truth, base.predict(model, s, C, ups), names, hierarchy, classes)
            result["gap_seen_minus_unseen"] = {k: round(result["seen"][k] - result["unseen"][k], 2)
                                               for k in ("balanced_accuracy", "group_recall", "lineage_recall")}
        summary["folds"][held] = result
        print(f"{held}: {len(classes)} classes ({time.time() - t0:.0f}s)", flush=True)
        del model
        torch.cuda.empty_cache()
    measured = [f for f in summary["folds"].values() if "unseen" in f]
    summary["mean"] = {side: {k: round(float(np.mean([f[side][k] for f in measured])), 2)
                              for k in ("balanced_accuracy", "group_recall", "lineage_recall")} for side in ("unseen", "seen")}
    summary["seconds"] = round(time.time() - t0)
    out = REPO / "research" / "notebook-outputs" / f"{organ}_donor_heldout"
    out.mkdir(parents=True, exist_ok=True)
    data.save_json(out / "summary.json", summary)
    print(json.dumps(summary["mean"], indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
