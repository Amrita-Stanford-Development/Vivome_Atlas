"""v5, Phase 2 (research/todo.md, Track H): retrains the five V2 members on
the cleaned reference labels (research/notebooks/v5_labels.py).

This is NB1d's training cell (notebooks/T1_NB1d_V2_Seed_Check.ipynb,
section 1), ported to this PC's GPU. It calls
research/notebook-outputs/nb2/nb1b_core.train_variant, which is NB1d's core
byte for byte, with NB1d's arguments:
- std batch_gene, sampler mini;
- hidden (1024, 512), dropout 0.1, latent 128, 60 epochs, the rest at their
  defaults;
- the class prior of the labels being trained on;
- NB1's whole-reference gene statistics;
- NB1's split (splits_seed0.npz): train cells for training, validation cells
  for early stopping. The test cells are never touched.

The RNA is the h5ad's log-normalised X, through
scripts/build_v4_bundle.load_rna. That loader reproduces v3.1's served
latents at median cosine 1.0, so the inputs are NB1's.

Stage "reproduce" runs first and must pass. Thresholds were fixed before the
first run.
1. Data check. The served seed 1 member
   (service/model/v3_1/members/V2_batchgene_aug_seed1.pt), on the masked
   validation cells train_variant draws for seed 1, must give NB1d's
   recorded best validation loss (Drive NB1b/ckpt/V2_batchgene_aug_seed1.json,
   0.45517) within 0.002. That proves the labels, split, statistics and mask
   are NB1d's.
2. Retraining. Seed 1, trained here on the original labels, must give:
   - best validation loss within 0.02 of 0.45517;
   - validation balanced accuracy at the best epoch within 2 points of the
     served member's on the same cells;
   - nearest-centroid CD8 T recall on the reference's own cells within 5
     points of the served member's;
   - a CD8 T and NK centroid cosine within 0.01 of the served member's.
Seed 1 is used because seed 0 came from NB1b's earlier run, while seeds 1 to
4 came from NB1d's exact code.

Stage "clean" (refused unless the reproduction passed): seeds 0 to 4 on the
cleaned labels. Checkpoints go to Drive Tier1_v31/V5/ckpt/, in NB1d's layout
(the state dict, plus a JSON of the training info). The record, with each
checkpoint's sha256 and its diagnostics on the reference's own cells, goes
to research/notebook-outputs/v5_train/. The diagnostics are:
- nearest-centroid recall per T and NK class, under the cleaned labels;
- the CD8 T and NK centroid cosine;
- validation balanced accuracy.

Variant v5.1 (--variant v5.1) trains the same way on v5.1's labels, which
are v5's with NK T folded into NK (research/notebooks/v51_labels.py). Its
checkpoints go to Drive Tier1_v31/V5/ckpt_v51/ and its record to
research/notebook-outputs/v51_train/. Variant v5.2 uses v5.2's labels, which
are v5.1's with CD4/CD8 lineage relabelled by a classifier trained on Hao
et al. 2021 (research/notebooks/v52_labels.py); its checkpoints go to
ckpt_v52/. Both rest on the same reproduction (same code, same machine).

    python research/notebooks/v5_train.py reproduce      # from the repository root
    python research/notebooks/v5_train.py clean
    python research/notebooks/v5_train.py clean --variant v5.1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebook-outputs" / "nb2"))
sys.path.insert(0, str(REPO / "scripts"))
import build_v4_bundle as bundle  # noqa: E402  (load_rna, RNA, NB1)
import nb1b_core as core  # noqa: E402

from service import config  # noqa: E402
from service.pipeline import reference  # noqa: E402

DRIVE = REPO.parent / "drive" / "Data" / "Results"
V3_EXPORT = DRIVE / "ReferenceProjection_v3" / "export"
NB1B_CKPT = DRIVE / "Tier1_v31" / "NB1b" / "ckpt"
CKPT = DRIVE / "Tier1_v31" / "V5" / "ckpt"
LABELS = REPO / "research" / "notebook-outputs" / "v5_labels" / "reference_labels_clean.csv.gz"
OUT = REPO / "research" / "notebook-outputs" / "v5_train"
VARIANTS = {
    "v5": {"labels": LABELS, "ckpt": CKPT, "out": OUT, "ckpt_record": "Drive Data/Results/Tier1_v31/V5/ckpt"},
    "v5.1": {"labels": REPO / "research" / "notebook-outputs" / "v51_labels" / "reference_labels_v51.csv.gz",
             "ckpt": DRIVE / "Tier1_v31" / "V5" / "ckpt_v51", "out": REPO / "research" / "notebook-outputs" / "v51_train",
             "ckpt_record": "Drive Data/Results/Tier1_v31/V5/ckpt_v51"},
    "v5.2": {"labels": REPO / "research" / "notebook-outputs" / "v52_labels" / "reference_labels_v52.csv.gz",
             "ckpt": DRIVE / "Tier1_v31" / "V5" / "ckpt_v52", "out": REPO / "research" / "notebook-outputs" / "v52_train",
             "ckpt_record": "Drive Data/Results/Tier1_v31/V5/ckpt_v52"},
}
SEEDS, REPRO_SEED = (0, 1, 2, 3, 4), 1
ARCH = {"hidden": (1024, 512), "dropout": 0.1, "latent": 128}
DATA_TOL, LOSS_TOL, BAL_TOL, RECALL_TOL, COS_TOL = 0.002, 0.02, 2.0, 5.0, 0.01
CD8, NK, NKT, CD4 = ("cd8-positive, alpha-beta t cell", "natural killer cell", "mature nk t cell",
                     "cd4-positive, alpha-beta t cell")


def setup(labels: Path = LABELS) -> dict:
    meta = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    y_all = np.load(bundle.NB1 / "y_all.npy")
    if not np.array_equal(y_all, meta["class_idx"].to_numpy()):
        raise SystemExit("y_all.npy and reference_metadata.csv disagree")
    lab = pd.read_csv(labels)
    if lab["cell"].tolist() != meta["cell"].tolist():
        raise SystemExit(f"{labels} is not in reference_metadata.csv's order")
    genes = reference.load_feature_space_genes()
    nb1d_genes = pd.read_csv(V3_EXPORT / "feature_space_genes.csv")["gene"].astype(str).str.upper().tolist()
    if [g.upper() for g in genes] != nb1d_genes:
        raise SystemExit("the service's feature genes are not NB1d's")
    t = time.time()
    X = bundle.load_rna(bundle.RNA, genes, meta["cell"].astype(str).tolist())
    stats = np.load(bundle.NB1 / "rna_global_stats.npz")
    mu, sd = X.mean(0), X.std(0)
    gap = max(float(np.abs(mu - stats["mu"]).max()), float(np.abs(sd - stats["sd"]).max()))
    if gap > 1e-4:
        raise SystemExit(f"the RNA's statistics are not NB1's (largest difference {gap})")
    device = torch.device("cuda")
    mod = np.load(V3_EXPORT / "module_assignment.npy")
    assign = torch.zeros(len(genes), int(mod.max() + 1))
    assign[torch.arange(len(genes)), torch.from_numpy(mod.astype(np.int64))] = 1.0
    split = np.load(bundle.NB1 / "splits_seed0.npz")
    print(f"RNA {X.shape} in {time.time() - t:.0f}s; statistics match NB1's within {gap:.1e}; "
          f"train {len(split['train']):,} val {len(split['val']):,}", flush=True)
    return {"names": names, "y_all": y_all, "y_clean": lab["class_idx_clean"].to_numpy(), "device": device,
            "XG": torch.from_numpy(X).to(device, dtype=torch.float16), "assign": assign.to(device),
            "mu": torch.from_numpy(stats["mu"].astype(np.float32)).to(device),
            "sd": torch.from_numpy(stats["sd"].astype(np.float32)).to(device),
            "TR": split["train"], "VA": split["val"]}


def load_model(path: Path, s: dict):
    m = core.RefModelV(s["XG"].shape[1], len(s["names"]), ARCH["hidden"], ARCH["dropout"], ARCH["latent"],
                       s["assign"], 1).to(s["device"])
    m.load_state_dict(torch.load(path, map_location=s["device"]), strict=True)
    return m.eval()


@torch.no_grad()
def validation(model, s: dict, y: np.ndarray, seed: int) -> dict:
    """train_variant's validation for this seed: the same mask, loss and accuracy."""
    G = s["XG"].shape[1]
    gen = torch.Generator(device="cpu").manual_seed(seed + 1000)
    VA_t = torch.from_numpy(np.asarray(s["VA"])).to(s["device"])
    vm = (torch.rand(len(s["VA"]), G, generator=gen) < 0.35).float().to(s["device"])
    xsv = core.standardize_t(s["XG"][VA_t].float(), vm, "batch_gene", s["mu"], s["sd"])
    L = torch.cat([model([x[i:i + 4096] for x in xsv], vm[i:i + 4096])[1] for i in range(0, len(s["VA"]), 4096)])
    yv = torch.from_numpy(y[s["VA"]].astype(np.int64)).to(s["device"])
    pv = L.argmax(1).cpu().numpy()
    return {"loss": float(F.cross_entropy(L, yv).item()), "balanced": 100 * float(balanced_accuracy_score(y[s["VA"]], pv))}


def reference_diagnostics(model, s: dict, y: np.ndarray) -> dict:
    names = s["names"]
    Z = core.reference_embedding(model, s["XG"], "batch_gene", s["mu"], s["sd"], s["device"])
    Z /= np.linalg.norm(Z, axis=1, keepdims=True)
    C = core.centroids_from(Z, y, len(names))
    guess = (Z @ C.T).argmax(1)
    i, j = names.index(CD8), names.index(NK)
    return {"centroid_cosine_cd8_nk": round(float(C[i] @ C[j]), 4),
            "nearest_centroid_recall": {c: round(100 * float((guess[y == names.index(c)] == names.index(c)).mean()), 2)
                                        for c in (CD8, NK, NKT, CD4) if (y == names.index(c)).any()}}


def train(s: dict, y: np.ndarray, seed: int):
    prior = np.bincount(y, minlength=len(s["names"])) / len(y)
    return core.train_variant(s["XG"], y, s["TR"], s["VA"], std="batch_gene", sampler="mini", seed=seed,
                              assign=s["assign"], prior=prior, mu_t=s["mu"], sd_t=s["sd"], device=s["device"],
                              n_classes=len(s["names"]), hidden=ARCH["hidden"], dropout=ARCH["dropout"],
                              latent=ARCH["latent"])


def best_epoch(info: dict) -> dict:
    return min(info["history"], key=lambda r: r["val_loss"])


def reproduce(s: dict) -> None:
    t0 = time.time()
    recorded = json.loads((NB1B_CKPT / f"V2_batchgene_aug_seed{REPRO_SEED}.json").read_text())["best_val_loss"]
    served = load_model(config.V31_MEMBERS_DIR / f"V2_batchgene_aug_seed{REPRO_SEED}.pt", s)
    served_val = validation(served, s, s["y_all"], REPRO_SEED)
    served_ref = reference_diagnostics(served, s, s["y_all"])
    data_ok = abs(served_val["loss"] - recorded) <= DATA_TOL
    print(f"data check: served seed {REPRO_SEED} validation loss {served_val['loss']:.5f} against NB1d's {recorded:.5f}: "
          f"{'PASS' if data_ok else 'FAIL'}", flush=True)
    result = {"recorded_best_val_loss": recorded, "served": {**served_val, **served_ref}, "data_check_passed": data_ok}
    if data_ok:
        model, info = train(s, s["y_all"], REPRO_SEED)
        mine = {"best_val_loss": float(info["best_val_loss"]), "balanced": 100 * best_epoch(info)["val_bal"],
                "epochs_run": info["epochs_run"], "seconds": round(info["seconds"]), **reference_diagnostics(model, s, s["y_all"])}
        checks = {
            "best_val_loss": abs(mine["best_val_loss"] - recorded) <= LOSS_TOL,
            "balanced": abs(mine["balanced"] - served_val["balanced"]) <= BAL_TOL,
            "cd8_recall": abs(mine["nearest_centroid_recall"][CD8] - served_ref["nearest_centroid_recall"][CD8]) <= RECALL_TOL,
            "cd8_nk_cosine": abs(mine["centroid_cosine_cd8_nk"] - served_ref["centroid_cosine_cd8_nk"]) <= COS_TOL,
        }
        result.update({"retrained": mine, "checks": checks})
    result["passed"] = bool(data_ok and all(result.get("checks", {}).values()))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reproduce.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"), "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__, "seed": REPRO_SEED,
        "tolerances": {"data": DATA_TOL, "loss": LOSS_TOL, "balanced": BAL_TOL, "recall": RECALL_TOL, "cosine": COS_TOL},
        **result, "seconds": round(time.time() - t0)}, indent=2) + "\n", newline="\n")
    print(json.dumps(result, indent=1))
    print("reproduction " + ("PASSED" if result["passed"] else "FAILED: do not train the cleaned members"))


def clean(s: dict, variant: str = "v5") -> None:
    rep = json.loads((OUT / "reproduce.json").read_text()) if (OUT / "reproduce.json").exists() else {}
    if not rep.get("passed"):
        raise SystemExit("the reproduction has not passed (research/notebook-outputs/v5_train/reproduce.json)")
    v = VARIANTS[variant]
    v["ckpt"].mkdir(parents=True, exist_ok=True)
    t0, members = time.time(), {}
    for seed in SEEDS:
        path = v["ckpt"] / f"V2_batchgene_aug_seed{seed}.pt"
        print(f"[seed {seed}] training on the cleaned labels", flush=True)
        model, info = train(s, s["y_clean"], seed)
        torch.save(model.state_dict(), path)
        (v["ckpt"] / f"V2_batchgene_aug_seed{seed}.json").write_text(json.dumps(
            {k: v for k, v in info.items() if k != "history"}) + "\n", newline="\n")
        members[path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "best_val_loss": float(info["best_val_loss"]), "balanced": round(100 * best_epoch(info)["val_bal"], 2),
                              "epochs_run": info["epochs_run"], "seconds": round(info["seconds"]),
                              **reference_diagnostics(model, s, s["y_clean"])}
        print(f"   {json.dumps(members[path.name])}", flush=True)
        del model
        torch.cuda.empty_cache()
    v["out"].mkdir(parents=True, exist_ok=True)
    (v["out"] / "train_record.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "variant": variant,
        "run": datetime.now().isoformat(timespec="seconds"), "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__, "labels": v["labels"].relative_to(REPO).as_posix(),
        "labels_sha256": hashlib.sha256(v["labels"].read_bytes()).hexdigest(),
        "reproduction": "research/notebook-outputs/v5_train/reproduce.json",
        "checkpoint_dir": v["ckpt_record"], "members": members,
        "seconds": round(time.time() - t0)}, indent=2) + "\n", newline="\n")
    print(f"trained {len(members)} members ({time.time() - t0:.0f}s)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("reproduce", "clean"))
    parser.add_argument("--variant", choices=tuple(VARIANTS), default="v5")
    args = parser.parse_args()
    s = setup(VARIANTS[args.variant]["labels"])
    reproduce(s) if args.stage == "reproduce" else clean(s, args.variant)


if __name__ == "__main__":
    main()
