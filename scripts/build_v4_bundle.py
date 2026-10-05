"""Builds v4's reference files (research/todo.md, Track G, Phase 2).

v4 keeps v3.1's five frozen V2 members and changes the reference side
(research/notebook-run-history.md, entry 20):
- the reference is re-encoded with class-balanced gene statistics (each of
  the 22 classes weighted equally), and the centroids recomputed from it;
- the class-balanced z-scored RNA class means feed the correlation term of
  the fused probability (service/pipeline/fusion.py).

It writes only what v4 changes, into service/model/v4/: the per-member
centroids, the class means, the statistics, the spec and a MANIFEST. The
checkpoints and the reference latents (used for the out-of-distribution
search and the coordinates) stay v3.1's, checked by v3.1's own MANIFEST.

Before writing, it checks itself: re-encoding a sample of reference cells
with NB1's whole-reference statistics must reproduce v3.1's served latents
(median cosine at least 0.999999), so the encoding path is v3.1's exactly.

v4's answers are v3.1's (its spec, calibration and abstention), so the spec
carries no conformal block of its own. The evaluation's verdict comes from
Phase 3c (research/notebook-outputs/v4_phase3c/spec_block.json, when it
exists); until the evaluation has passed, the service refuses to serve v4.

    python scripts/build_v4_bundle.py                    # all reference cells, into service/model/v4/
    python scripts/build_v4_bundle.py --rows trainval --out DIR
    # the calibration bundle: NB1's train and validation cells only (its test
    # split held out), written outside the repository
    python scripts/build_v4_bundle.py --spec-only        # rewrite the spec and MANIFEST only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from service import config  # noqa: E402
from service.pipeline import encoder, ensemble, reference  # noqa: E402
from service.pipeline.fusion import class_balanced_stats, class_means  # noqa: E402

DRIVE = REPO.parent / "drive" / "Data"
RNA = DRIVE / "scRNA-seq" / "Blood_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad"
NB1 = DRIVE / "Results" / "Tier1_v31" / "NB1"
OUT = REPO / "service" / "model" / "v4"
FUSION_WEIGHT, CORRELATION_TEMPERATURE = 0.7, 0.05  # chosen on NB1's calibration suite (entry 20)
# Phase 3c's rule, fixed from its exploration on NB3c's calibration cells and the development data (entry 24)
SMOOTHED_SHARE, AGREEMENT_THRESHOLD = 0.5, 0.4
SELF_CHECK_CELLS, SELF_CHECK_MIN = 5000, 0.999999
PHASE3C = REPO / "research" / "notebook-outputs" / "v4_phase3c" / "spec_block.json"


def load_rna(path: Path, feature_genes: list[str], cell_ids: list[str]) -> np.ndarray:
    """(cells x 9,002) log-normalised RNA in reference_metadata.csv row order."""
    with h5py.File(path, "r") as f:
        sym = f["var"]["gene_symbol"]
        sym = sym["categories"][:].astype(str)[sym["codes"][:]] if isinstance(sym, h5py.Group) else sym[:].astype(str)
        index_key = f["obs"].attrs["_index"]
        obs_ids = f["obs"][index_key][:].astype(str)
        if list(obs_ids) != list(cell_ids):
            raise ValueError("the h5ad's cells are not in reference_metadata.csv's order")
        first: dict[str, int] = {}
        for j, g in enumerate(sym):
            first.setdefault(g.upper(), j)
        missing = [g for g in feature_genes if g.upper() not in first]
        if missing:
            raise ValueError(f"{len(missing)} feature genes are not in the RNA, e.g. {missing[:5]}")
        X = sp.csr_matrix((f["X"]["data"][:], f["X"]["indices"][:], f["X"]["indptr"][:]), shape=tuple(f["X"].attrs["shape"]))
    return X[:, np.array([first[g.upper()] for g in feature_genes])].toarray().astype(np.float32)


def encode(handle, X: np.ndarray, mu: np.ndarray, sd: np.ndarray, chunk: int = 8192) -> np.ndarray:
    out = []
    for i in range(0, len(X), chunk):
        values = (X[i:i + chunk] - mu) / (sd + 1e-8)
        out.append(np.asarray(handle.encode(values, np.ones_like(values)), dtype=np.float32))
    Z = np.concatenate(out)
    return Z / np.linalg.norm(Z, axis=1, keepdims=True)


def self_check(X: np.ndarray, spec: dict) -> float:
    """v3.1's served latents, reproduced from NB1's whole-reference statistics."""
    stats = np.load(NB1 / "rna_global_stats.npz")
    rows = np.random.default_rng(0).choice(len(X), min(SELF_CHECK_CELLS, len(X)), replace=False)
    name = spec["encoder"]["members"][0]
    seed = name.split("seed")[1].split(".")[0]
    served = np.load(config.V31_MEMBERS_DIR / f"V2_seed{seed}_reference_latent_f16.npy")[rows].astype(np.float32)
    served /= np.linalg.norm(served, axis=1, keepdims=True)
    mine = encode(encoder.load_encoder(config.V31_MEMBERS_DIR / name), X[rows], stats["mu"], stats["sd"])
    return float(np.median((mine * served).sum(1)))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_spec(v31: dict, class_names: list[str], rows_name: str, n_cells: int, rna_name: str) -> dict:
    """v4's spec. The served bundle (all rows) takes Phase 3c's verdict when recorded."""
    block = json.loads(PHASE3C.read_text(encoding="utf-8")) if rows_name == "all" and PHASE3C.exists() else {}
    return {
        "version": "v4",
        "created": str(date.today()),
        "source": ("research/notebooks/v4_pretest.py and v4_phase3c.py (research/notebook-run-history.md, "
                   "entries 20, 23 and 24); built by scripts/build_v4_bundle.py"),
        "reference_rows": rows_name,
        "encoder": {"members": v31["encoder"]["members"], "files": "service/model/v3_1 (its MANIFEST)"},
        "preprocessing": {"convention": "service", "smoothing": True,
                          "min_observed_genes": v31["preprocessing"]["min_observed_genes"]},
        "reference": {"statistics": "class_balanced", "rna": rna_name, "n_cells": n_cells,
                      "ood_and_coordinates": "v3.1's reference latents"},
        "answers": {"from": "v3.1", "spec": config.V31_SPEC_PATH.relative_to(REPO).as_posix(),
                    "what": ("conformal sets, abstention, answer levels, coordinates and properties, unchanged; "
                             "the fused best guess joins non-empty sets beside v3.1's")},
        "best_guess": {"rule": "fusion", "temperature": v31["assignment"]["temperature"],
                       "fusion_weight": FUSION_WEIGHT, "correlation_temperature": CORRELATION_TEMPERATURE,
                       "smoothed_share": SMOOTHED_SHARE, "agreement_threshold": AGREEMENT_THRESHOLD,
                       "chosen_on": {"fusion_weight and correlation_temperature": "NB1 sim_suite_calib_v1.json (v4_pretest.py)",
                                     "smoothed_share and agreement_threshold": ("NB3c calibration cells and the development "
                                                                                "data (Phase 3c's exploration, entry 24)")}},
        "label_space": {"method": "none"},
        "evaluation": block.get("evaluation", {"status": "pending", "record": None}),
        "hierarchy": v31["hierarchy"],
        "class_order": class_names,
    }


def write_spec_and_manifest(out: Path, spec: dict, written: dict, check: float) -> None:
    (out / "spec_v4.json").write_text(json.dumps(spec, indent=2) + "\n", newline="\n")
    written["spec_v4.json"] = "v4's settings; its answers are v3.1's"
    manifest = {
        "source": "scripts/build_v4_bundle.py; members and reference latents are v3.1's (service/model/v3_1/MANIFEST.json)",
        "self_check_median_cosine": round(check, 8),
        "files": {rel: {"sha256": sha256(out / rel), "bytes": (out / rel).stat().st_size, "what": what}
                  for rel, what in written.items()},
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", choices=("all", "trainval"), default="all")
    parser.add_argument("--rna", type=Path, default=RNA)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--spec-only", action="store_true", help="rewrite the spec and MANIFEST; keep the data files")
    args = parser.parse_args()
    if args.rows == "trainval" and args.out.resolve() == OUT.resolve():
        raise SystemExit("the calibration bundle is written outside the repository: pass --out")

    ensemble._verify_manifest()  # the members and latents v4 builds on are v3.1's exact files
    v31 = ensemble.load_spec()
    meta = reference.load_reference_metadata()
    class_names = [c.class_name for c in meta.classes]
    if args.spec_only:
        old = json.loads((args.out / "MANIFEST.json").read_text(encoding="utf-8"))
        for rel, entry in old["files"].items():
            if rel != "spec_v4.json" and sha256(args.out / rel) != entry["sha256"]:
                raise SystemExit(f"{rel} changed since it was built: rebuild in full")
        previous = json.loads((args.out / "spec_v4.json").read_text(encoding="utf-8"))
        spec = make_spec(v31, class_names, previous["reference_rows"], previous["reference"]["n_cells"], previous["reference"]["rna"])
        written = {rel: e["what"] for rel, e in old["files"].items() if rel != "spec_v4.json"}
        write_spec_and_manifest(args.out, spec, written, old["self_check_median_cosine"])
        print(f"rewrote {args.out / 'spec_v4.json'} and MANIFEST.json: smoothed_share {spec['best_guess']['smoothed_share']}, "
              f"agreement_threshold {spec['best_guess']['agreement_threshold']}, evaluation {spec['evaluation']['status']}")
        return
    table = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    y = np.array([class_names.index(c) for c in table["class_name"]])
    feature_genes = reference.load_feature_space_genes()
    X = load_rna(args.rna, feature_genes, table["cell"].astype(str).tolist())
    print(f"RNA {X.shape}")

    check = self_check(X, v31)
    print(f"self-check: v3.1's served latents reproduced at median cosine {check:.7f}")
    if check < SELF_CHECK_MIN:
        raise SystemExit(f"self-check failed ({check} < {SELF_CHECK_MIN}): the encoding path is not v3.1's")

    rows = np.arange(len(X))
    if args.rows == "trainval":
        split = np.load(NB1 / "splits_seed0.npz")
        rows = np.sort(np.concatenate([split["train"], split["val"]]))
    Xr, yr = X[rows], y[rows]
    mu, sd = class_balanced_stats(Xr, yr, len(class_names))
    means = class_means(Xr, yr, len(class_names), mu, sd)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "members").mkdir(exist_ok=True)
    written = {}
    np.savez(args.out / "class_balanced_stats.npz", mu=mu, sd=sd)
    np.save(args.out / "class_means_cb.npy", means.astype(np.float32))
    written["class_balanced_stats.npz"] = f"per-gene class-balanced mean and SD over {args.rows} reference cells"
    written["class_means_cb.npy"] = "class-balanced z-scored RNA class means, class position order (22 x 9,002)"
    for name in v31["encoder"]["members"]:
        seed = name.split("seed")[1].split(".")[0]
        Z = encode(encoder.load_encoder(config.V31_MEMBERS_DIR / name), Xr, mu, sd)
        C = np.stack([Z[yr == k].mean(0) for k in range(len(class_names))])
        C /= np.linalg.norm(C, axis=1, keepdims=True)
        np.save(args.out / "members" / f"V2_seed{seed}_centroids_cb.npy", C.astype(np.float32))
        written[f"members/V2_seed{seed}_centroids_cb.npy"] = f"{name} centroids under class-balanced statistics"
        print(f"{name}: centroids written")

    spec = make_spec(v31, class_names, args.rows, int(len(rows)), args.rna.name)
    write_spec_and_manifest(args.out, spec, written, check)
    print(f"wrote {len(written)} files and MANIFEST.json to {args.out}")


if __name__ == "__main__":
    main()
