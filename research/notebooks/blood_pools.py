"""Blood, a diagnostic after the organs' A6 (research/notebooks/organ_v2_pools.py):
does training on pooled RNA as well as single cells help blood's encoder?

A6 trained one lymph node, lung and colon member each with and without
pseudobulk pools. The pools did not remove the organs' sinks, but they raised
single-cell validation balanced accuracy by 0.7 to 6.5 points in every
organ. Blood's served encoder (v4.1's V2 members) never saw pools. This asks
whether they would help blood too, on single cells and on real protein. It
is a diagnostic only: blood v4.1 stays as served, and any candidate built on
it is the owner's call, with its own pre-registered gates.

**Members.** Blood's organ-layout work folder (the builder's blood, proven
to give v4.1's frozen responses) gives the split, modules, statistics and
settings (calibrate.train_member). Per seed in SEEDS, two members:
- control: the training rows;
- pooled: the training rows plus A6's pools, made from them with A6's
  settings and seed (organ_v2_pools.make_pools).

**Measures, per member** (nearest centroid of the training cells' latents):
- validation balanced accuracy (train_member's own);
- top-1 on the first 120 uploads of blood's calibration suite (A6's
  suite_top1);
- Fulcher 2026, the whole upload through the service's preprocessing: the
  argmax mapped to the six author types by fulcher2026_score.COARSE (other
  classes count as "other"), balanced accuracy over the six types, Unknown
  cells left out. Fulcher is development data.

**Reading, fixed here:** pools are "promising for blood" if, in every seed,
the pooled member's Fulcher balanced accuracy is at least GAIN points above
its control's, and its validation balanced accuracy and calibration-suite
top-1 are at most COST points below. Otherwise "not promising". Either way
the numbers are reported.

Writes research/notebook-outputs/blood_pools/: rules.json (first),
results.json, decision.json. The members go to blood's work folder,
v2_diagnostics/pools/.

    python research/notebooks/blood_pools.py      # from the repository root (GPU)
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
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import organ_v2_pools as a6  # noqa: E402
from organ_reference import bundle, calibrate, data  # noqa: E402

from benchmark import datasets  # noqa: E402
from benchmark import fulcher2026_score as fulcher  # noqa: E402
from service.pipeline import encoder  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "blood_pools"
ORGAN = "blood"
SEEDS = (1, 2)
GAIN, COST = 2.0, 2.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fulcher_balanced(member: "a6.Member", b) -> float:
    raw = datasets.load_fulcher2026_upload()
    labels = datasets.load_fulcher2026_labels()
    if labels["cell_id"].tolist() != list(raw.cell_ids):
        raise SystemExit("Fulcher's labels and upload are not in the same order")
    _, P, _ = member.run_upload(b, raw)
    guess = np.array([fulcher.COARSE.get(member.names[i], "other") for i in P.argmax(1)])
    scored = labels["label"].to_numpy() != datasets.FULCHER2026["unscored_label"]
    return round(100 * float(balanced_accuracy_score(labels["label"].to_numpy()[scored], guess[scored])), 2)


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "seeds": SEEDS, "gain": GAIN, "cost": COST,
                                        "pools": {"seed": a6.SEED_POOLS, "share": a6.POOL_SHARE, "min": a6.POOL_MIN, "max": a6.POOL_MAX,
                                                  "sizes": a6.POOL_SIZES, "pure": a6.PURE, "majority": a6.MAJORITY},
                                        "a6_script_sha256": sha256(Path(a6.__file__))})
    t0 = time.time()
    log = lambda m: print(f"{m} ({time.time() - t0:.0f}s)", flush=True)  # noqa: E731
    build_dir = data.WORK / ORGAN
    cfg = data.load_organ(ORGAN)
    b = bundle.load(build_dir / "bundle")
    names = b.class_names
    table = pd.read_csv(build_dir / "labels.csv.gz", keep_default_na=False)
    y = table["class_idx"].to_numpy()
    X = data.load_rna(data.resolve(cfg["rna"]), b.feature_genes)[table["row"].to_numpy()]
    split = np.load(build_dir / "splits_seed0.npz")
    TR, VA = np.sort(split["train"]), np.sort(split["val"])
    stats = np.load(build_dir / "rna_global_stats.npz")
    modules = np.load(build_dir / "module_assignment.npy")
    temperatures = json.loads((build_dir / "calibration.json").read_text(encoding="utf-8"))["temperature"]
    profiles = dict(np.load(build_dir / "mask_profiles.npz"))
    suite = json.loads((build_dir / "sim_suite_calib_v1.json").read_text(encoding="utf-8"))
    pools, pool_y = a6.make_pools(X, y, TR, len(names))
    log(f"blood: {len(X):,} cells, {len(pools):,} pools over {len(names)} classes")
    folder = build_dir / "v2_diagnostics" / "pools"
    folder.mkdir(parents=True, exist_ok=True)
    results = {"pools": int(len(pools)), "seeds": {}}
    for seed in SEEDS:
        results["seeds"][seed] = {}
        for arm in ("control", "pooled"):
            if arm == "pooled":
                Xa, ya = np.vstack([X, pools]), np.concatenate([y, pool_y])
                tra = np.concatenate([TR, np.arange(len(X), len(Xa))])
            else:
                Xa, ya, tra = X, y, TR
            s = calibrate.setup(Xa, stats["mu"], stats["sd"], modules, ya, {"train": tra, "val": VA})
            torch.manual_seed(seed)
            model, info = calibrate.train_member(s, seed, cfg["train"])
            path = folder / f"{arm}_seed{seed}.pt"
            torch.save(model.state_dict(), path)
            best = min(info["history"], key=lambda r: r["val_loss"])
            Z = calibrate.core.reference_embedding(model, s["XG"][: len(X)], "batch_gene", s["mu"], s["sd"], s["device"])
            cen = calibrate.core.centroids_from(Z[TR], y[TR], len(names))
            del model, s, Xa
            torch.cuda.empty_cache()
            member = a6.Member(encoder.load_encoder(path), cen, float(temperatures[f"V2_batchgene_aug_seed{seed}.pt"]), names)
            with bundle.gene_map(build_dir / "bundle"):
                entry = {"validation_balanced": round(100 * best["val_bal"], 2), "epochs_run": info["epochs_run"],
                         "calib_top1": a6.suite_top1(member, b, suite, X, y, profiles),
                         "fulcher_balanced_6types": fulcher_balanced(member, b), "checkpoint_sha256": sha256(path)}
            results["seeds"][seed][arm] = entry
            log(f"seed {seed} {arm}: {json.dumps(entry)}")
            data.save_json(OUT / "results.json", results)
    checks = {}
    for seed, arms in results["seeds"].items():
        c, p = arms["control"], arms["pooled"]
        checks[seed] = {"fulcher_gain": round(p["fulcher_balanced_6types"] - c["fulcher_balanced_6types"], 2),
                        "validation_change": round(p["validation_balanced"] - c["validation_balanced"], 2),
                        "calib_top1_change": round(p["calib_top1"] - c["calib_top1"], 3)}
    promising = all(v["fulcher_gain"] >= GAIN and v["validation_change"] >= -COST and v["calib_top1_change"] >= -COST
                    for v in checks.values())
    data.save_json(OUT / "decision.json", {"finished": datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - t0),
                                           "by_seed": checks, "promising_for_blood": bool(promising)})
    print(json.dumps({"by_seed": checks, "promising": promising}, indent=1))


if __name__ == "__main__":
    main()
