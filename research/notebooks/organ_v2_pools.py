"""Organ references v2, diagnostic A6 (owner's decision of 2026-10-18; after
A1 and A1b): does training on pooled RNA as well as single cells take the
encoder's sinks away on pooled protein, without costing single cells?

A1b found that the sinks (plasma cell in the lymph node, macrophage in the
lung, mast cell in the colon) come from the encoder meeting deep, mixed
pools. These are hundreds of cells averaged; the encoder has only ever seen
single cells. Thinning pools to single-cell depth halved the lymph node's
sink.

For each organ, two members are trained with the same seed (SEED_MEMBER),
split, modules and settings (calibrate.train_member):
- control: v1's training rows;
- pooled: v1's training rows plus pseudobulk pools made from them.

**How the pools are made**
- Per class, clip(round(POOL_SHARE x training cells), POOL_MIN, POOL_MAX)
  pools.
- Each pool averages k cells, k drawn from POOL_SIZES, with replacement
  when the class is smaller.
- A share PURE of the pools are one class; the rest are MAJORITY of their
  class and the remainder drawn from the other training cells.
- Values are log1p(mean(expm1(x))): the pool's normalised expression, as
  the atlas stores cells.
- The label is the pool's majority class.

Validation and test cells are untouched; the pools are training rows only.

**How each member is read**
Its encoder runs through the service's own preprocessing on each organ's
seen G3 uploads, via each organ's own g3 code, exactly as in A1. Its answer
is the nearest centroid of its reference latents over the training cells,
with v1's seed-1 temperature, and its probabilities stand for the fused
ones in g3's group sums. On single cells, two measures:
- train_variant's own validation balanced accuracy;
- top-1 on the first CALIB_UPLOADS uploads of v1's calibration suite.

**Decision rule, fixed before the run.** Pools join every v2 organ's
training if:
1. lymph node, Zheng's tonsil pools: plasma-cell guesses fall by at least
   SINK_DROP of the 48 pools, and group accuracy does not fall;
2. every A1 guard holds for the pooled member in every organ:
   - HPA lymph-node pools ≥ 80;
   - Kabatnik ≥ 0.8;
   - HPA AT2 over AT1 ≥ 0.8;
   - IPF foci ≥ 0.7;
3. in every organ, the pooled member costs at most COST points of
   validation balanced accuracy and of calibration-suite top-1 against its
   control.
The lung's and the colon's sink metrics are reported.

Writes research/notebook-outputs/organ_v2_pools/: rules.json (first),
results.json, decision.json. The members go to each organ's work folder,
v2_diagnostics/pools/.

    python research/notebooks/organ_v2_pools.py      # from the repository root (GPU)
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
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import li_development as li  # noqa: E402
import organ_v2_masking as a1  # noqa: E402
from organ_reference import bundle, calibrate, data  # noqa: E402
from organ_reference import sim_generator as sg  # noqa: E402

from service.pipeline import alignment, encoder, ensemble, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_pools"
ORGANS = ("lymph_node", "lung", "large_intestine")
SEED_MEMBER = 1
SEED_POOLS = 20261018
POOL_SHARE, POOL_MIN, POOL_MAX = 0.10, 20, 400
POOL_SIZES = (10, 30, 100, 300)
PURE, MAJORITY = 0.7, 0.8
CALIB_UPLOADS = 120
SINK_DROP = 12
COST = 2.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_pools(X: np.ndarray, y: np.ndarray, TR: np.ndarray, C: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(SEED_POOLS)
    ytr = y[TR]
    rows, labels = [], []
    for c in range(C):
        own = TR[ytr == c]
        if len(own) == 0:
            continue
        n_pools = int(np.clip(round(POOL_SHARE * len(own)), POOL_MIN, POOL_MAX))
        others = TR[ytr != c]
        for _ in range(n_pools):
            k = int(rng.choice(POOL_SIZES))
            if rng.random() < PURE:
                members = rng.choice(own, k, replace=len(own) < k)
            else:
                k_own = max(1, int(round(MAJORITY * k)))
                members = np.concatenate([rng.choice(own, k_own, replace=len(own) < k_own),
                                          rng.choice(others, k - k_own, replace=len(others) < k - k_own)])
            rows.append(np.log1p(np.expm1(X[members].astype(np.float64)).mean(0)).astype(np.float32))
            labels.append(c)
    return np.stack(rows), np.array(labels, dtype=y.dtype)


class Member:
    """One trained member, read as the answers' encoder path."""

    def __init__(self, handle, centroids: np.ndarray, temperature: float, names: list[str]):
        self.handle, self.centroids, self.temperature, self.names = handle, centroids, temperature, names

    def probabilities(self, smoothed, mask) -> np.ndarray:
        return ensemble.member_probabilities(self.handle.encode(smoothed, mask), self.centroids, self.temperature)

    def run_upload(self, b, raw: alignment.RawMatrix):
        smoothed, aligned, _ = pipeline._prepare_query(b.feature_genes, raw)
        P = self.probabilities(smoothed, aligned.mask)
        cells = [{"label": self.names[i], "label_level": "class", "abstained": False,
                  "best_guess": {"label": self.names[i]}} for i in P.argmax(1)]
        return {"cells": cells}, P, aligned


def suite_top1(member: Member, b, suite, X, y, profiles) -> float:
    right, total = 0, 0
    for spec in suite[:CALIB_UPLOADS]:
        raw, _ = calibrate.core.raw_upload(spec, X, profiles, len(b.feature_genes), sg)
        ids = [f"{spec['id']}_{i}" for i in range(len(raw))]
        smoothed, aligned, _ = pipeline._prepare_query(b.feature_genes, alignment.RawMatrix(gene_names=b.feature_genes, cell_ids=ids, values=raw.T))
        P = member.probabilities(smoothed, aligned.mask)
        keep = aligned.per_cell_observed_genes >= 200
        truth = y[np.asarray(spec["cell_idx"])]
        right += int((P.argmax(1)[keep] == truth[keep]).sum())
        total += int(keep.sum())
    return round(100 * right / total, 3)


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "seed_member": SEED_MEMBER, "seed_pools": SEED_POOLS, "pool_share": POOL_SHARE,
                                        "pool_min": POOL_MIN, "pool_max": POOL_MAX, "pool_sizes": POOL_SIZES, "pure": PURE,
                                        "majority": MAJORITY, "calib_uploads": CALIB_UPLOADS, "sink_drop": SINK_DROP, "cost": COST})
    t0 = time.time()
    log = lambda m: print(f"{m} ({time.time() - t0:.0f}s)", flush=True)  # noqa: E731
    results = {}
    original = li.run_upload
    try:
        for organ in ORGANS:
            build_dir = data.WORK / organ
            cfg = data.load_organ(organ)
            b = bundle.load(build_dir / "bundle")
            names = b.class_names
            table = pd.read_csv(build_dir / "labels.csv.gz", keep_default_na=False)
            y = table["class_idx"].to_numpy()
            X = data.load_rna(data.resolve(cfg["rna"]), b.feature_genes)[table["row"].to_numpy()]
            split = np.load(build_dir / "splits_seed0.npz")
            TR, VA = np.sort(split["train"]), np.sort(split["val"])
            stats = np.load(build_dir / "rna_global_stats.npz")
            modules = np.load(build_dir / "module_assignment.npy")
            arch = cfg["train"]
            temperature = float(json.loads((build_dir / "calibration.json").read_text(encoding="utf-8"))["temperature"][f"V2_batchgene_aug_seed{SEED_MEMBER}.pt"])
            pools, pool_y = make_pools(X, y, TR, len(names))
            log(f"{organ}: {len(pools)} pools over {len(names)} classes")
            folder = build_dir / "v2_diagnostics" / "pools"
            folder.mkdir(parents=True, exist_ok=True)
            profiles = dict(np.load(build_dir / "mask_profiles.npz"))
            suite = json.loads((build_dir / "sim_suite_calib_v1.json").read_text(encoding="utf-8"))
            results[organ] = {"pools": int(len(pools))}
            for arm in ("control", "pooled"):
                if arm == "pooled":
                    Xa = np.vstack([X, pools])
                    ya = np.concatenate([y, pool_y])
                    tra = np.concatenate([TR, np.arange(len(X), len(Xa))])
                else:
                    Xa, ya, tra = X, y, TR
                s = calibrate.setup(Xa, stats["mu"], stats["sd"], modules, ya, {"train": tra, "val": VA})
                torch.manual_seed(SEED_MEMBER)
                model, info = calibrate.train_member(s, SEED_MEMBER, arch)
                path = folder / f"{arm}_seed{SEED_MEMBER}.pt"
                torch.save(model.state_dict(), path)
                best = min(info["history"], key=lambda r: r["val_loss"])
                Z = calibrate.core.reference_embedding(model, s["XG"][: len(X)], "batch_gene", s["mu"], s["sd"], s["device"])
                cen = calibrate.core.centroids_from(Z[TR], y[TR], len(names))
                del model, s
                torch.cuda.empty_cache()
                member = Member(encoder.load_encoder(path), cen, temperature, names)
                with bundle.gene_map(build_dir / "bundle"):
                    li.run_upload = member.run_upload
                    g3 = a1.ORGANS[organ].g3(b)
                    li.run_upload = original
                    top1 = suite_top1(member, b, suite, X, y, profiles)
                results[organ][arm] = {"validation_balanced": round(100 * best["val_bal"], 2), "epochs_run": info["epochs_run"],
                                       "calib_top1": top1, **a1.measure(organ, g3), "checkpoint_sha256": sha256(path)}
                log(f"{organ} {arm}: {json.dumps({k: v for k, v in results[organ][arm].items() if k != 'reported'})}")
                data.save_json(OUT / "results.json", results)
            del X
    finally:
        li.run_upload = original
    ln = results["lymph_node"]
    sink = (ln["control"]["metrics"]["zheng_plasma_guesses"] - ln["pooled"]["metrics"]["zheng_plasma_guesses"] >= SINK_DROP
            and ln["pooled"]["metrics"]["zheng_group_accuracy"] >= ln["control"]["metrics"]["zheng_group_accuracy"])
    guards = {o: {g: results[o]["pooled"]["guards"][g] >= bar for g, (_, bar) in a1.METRICS[o]["guards"].items()} for o in ORGANS}
    cost = {o: {"validation": results[o]["control"]["validation_balanced"] - results[o]["pooled"]["validation_balanced"] <= COST,
                "calib_top1": results[o]["control"]["calib_top1"] - results[o]["pooled"]["calib_top1"] <= COST} for o in ORGANS}
    adopt = bool(sink and all(all(v.values()) for v in guards.values()) and all(all(v.values()) for v in cost.values()))
    data.save_json(OUT / "decision.json", {"finished": datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - t0),
                                           "sink_drop_met": bool(sink), "guards_hold": guards, "cost_within": cost,
                                           "v2_trains_on_pools": adopt})
    print(json.dumps({"sink": sink, "guards": guards, "cost": cost, "adopt": adopt}, indent=1))


if __name__ == "__main__":
    main()
