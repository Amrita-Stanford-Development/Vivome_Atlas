"""Khoury 2026 final evaluation, step 2: scANVI, one arm and one seed. The
setup is fixed by research/benchmark/protocol-khoury2026.md, section "scANVI":
training exactly as scanvi_run_fulcher2026.py (copied unchanged below),
transductive on all 1,651 upload cells as unlabelled query cells.

Arms (the values are already log2 and are not transformed again):
- "as_provided": the matrix values over load.py's 2,907-gene space
  (datasets.load_khoury2026_benchmark_matrix());
- "cellmedian": the same, minus each cell's median over its observed proteins;
- "measuredgenes": "as_provided", with the RNA reference and the query
  restricted to the benchmark genes Khoury measures.
Each gene is z-scored over its observed values (RNA and query separately) and
unobserved query entries are set to 0.

Saves embeddings and predicted reference classes (scANVI's native classifier
and the shared kNN rule) to <out>/scanvi_<arm>_seed<seed>*. Never reads a label;
khoury2026_score.py scores.

    python -m benchmark.scanvi_run_khoury2026 SEED ARM --unseal       # the final evaluation only
    python -m benchmark.scanvi_run_khoury2026 SEED ARM --rehearse --smoke 3000
    # SEED 0-2; ARM as_provided | cellmedian | measuredgenes

--rehearse runs on Fulcher 2026's log2 and log2_cellmedian matrices instead,
into results/khoury2026_rehearsal/. --smoke N (rehearsal only) subsamples N RNA
cells and caps training at 5 + 3 epochs: plumbing, not results.
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scvi
import torch
from scvi.model import SCANVI, SCVI
from sklearn.neighbors import KNeighborsClassifier

from benchmark import datasets
from benchmark.baselines_run import went_nan
from benchmark.evaluate import KNN_K
from benchmark.khoury2026_embed import out_dir

D = datasets.REPO / "benchmark" / "results"
ARMS = ("as_provided", "cellmedian", "measuredgenes")
FULCHER_VARIANT = {"as_provided": "log2", "cellmedian": "log2_cellmedian", "measuredgenes": "log2"}


def zscore_cols(X, eps=1e-8):
    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    return (X - mean) / np.clip(std, eps, None)


def zscore_cols_nan_aware(X, eps=1e-8):
    mean = np.nanmean(X, axis=0, keepdims=True)
    std = np.nanstd(X, axis=0, keepdims=True)
    return np.nan_to_num((X - mean) / np.clip(std, eps, None), nan=0.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed", type=int, choices=(0, 1, 2))
    parser.add_argument("arm", choices=ARMS)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--unseal", action="store_true", help="the final v3.1 evaluation (protocol-khoury2026.md)")
    mode.add_argument("--rehearse", action="store_true", help="Fulcher 2026 instead, a development dataset")
    parser.add_argument("--smoke", type=int, default=0, help="rehearsal only: subsample N RNA cells, few epochs")
    args = parser.parse_args()
    if args.smoke and not args.rehearse:
        parser.error("--smoke is for rehearsals only: nothing is trained on Khoury except the real runs")

    scvi.settings.seed = args.seed
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    out = out_dir(args.rehearse) / ("smoke" if args.smoke else "")
    out.mkdir(parents=True, exist_ok=True)
    stem = out / f"scanvi_{args.arm}_seed{args.seed}"
    if args.unseal and Path(f"{stem}.json").exists():
        status = json.loads(Path(f"{stem}.json").read_text()).get("status", "completed")
        if status != "failed":  # amendment 4: a diverged run is not rerun; a completed one is final
            raise SystemExit(f"{stem}.json exists ({status}); a sealed run is not rerun or replaced")
    t0 = time.time()
    base = {"method": "scANVI", "dataset": "Fulcher 2026 (rehearsal)" if args.rehearse else "Khoury 2026 (final evaluation)",
            "arm": args.arm, "seed": args.seed, "smoke_rna_cells": args.smoke or None}
    try:
        meta = {**base, **train(args, stem, t0)}
    except Exception as err:  # every exit leaves a record (amendment 7): a failed run is not a missing one
        meta = {**base, "status": "failed", "diverged": False, "error": f"{type(err).__name__}: {err}"[:2000],
                "elapsed_s": round(time.time() - t0, 1)}
        Path(f"{stem}.json").write_text(json.dumps(meta, indent=2) + "\n")
        raise
    Path(f"{stem}.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta), flush=True)


def train(args, stem: Path, t0: float) -> dict:
    rna_X = np.load(D / "rna_X.npy")
    rna_labels = pd.read_csv(D / "rna_meta.csv")["class_name"].to_numpy()
    if args.rehearse:
        query_X, cell_ids, genes = datasets.load_fulcher2026_benchmark_matrix(FULCHER_VARIANT[args.arm])
    else:
        query_X, cell_ids, genes = datasets.load_khoury2026_benchmark_matrix(
            "cellmedian" if args.arm == "cellmedian" else "as_provided")
    if args.arm == "measuredgenes":
        measured = np.isfinite(query_X).any(axis=0)
        rna_X, query_X = rna_X[:, measured], query_X[:, measured]
    if args.smoke:
        keep = np.random.default_rng(0).choice(len(rna_X), args.smoke, replace=False)
        rna_X, rna_labels = rna_X[keep], rna_labels[keep]
    print(f"arm={args.arm} seed={args.seed} RNA cells {len(rna_labels)}, query cells {len(cell_ids)}, "
          f"{query_X.shape[1]} genes, {int(np.isfinite(query_X).any(axis=0).sum())} measured. {time.time()-t0:.1f}s", flush=True)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN gene columns become 0
        query_Z = zscore_cols_nan_aware(query_X).astype(np.float32)
    rna_Z = zscore_cols(rna_X).astype(np.float32)

    adata = ad.AnnData(X=np.vstack([rna_Z, query_Z]).astype(np.float32))
    adata.obs["modality"] = ["RNA"] * len(rna_Z) + ["Protein"] * len(query_Z)
    adata.obs["cell_type"] = pd.Categorical(list(rna_labels) + ["Unknown"] * len(query_Z))
    adata.obs["size_factor"] = 1.0
    epochs = (5, 3) if args.smoke else (200, 100)

    try:  # a NaN during training makes torch raise; the run is then recorded as diverged (amendment 4)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            SCVI.setup_anndata(adata, batch_key="modality", labels_key="cell_type", size_factor_key="size_factor")
            scvi_model = SCVI(adata, n_latent=30, n_layers=2, n_hidden=128, gene_likelihood="normal", log_variational=False)
            scvi_model.train(max_epochs=epochs[0], early_stopping=True, early_stopping_patience=15)
            print(f"SCVI pretrain done. {time.time()-t0:.1f}s", flush=True)
            scanvi_model = SCANVI.from_scvi_model(scvi_model, unlabeled_category="Unknown", labels_key="cell_type")
            scanvi_model.train(max_epochs=epochs[1], early_stopping=True, early_stopping_patience=15)
            print(f"SCANVI train done. {time.time()-t0:.1f}s", flush=True)
        emb = scanvi_model.get_latent_representation()
        native = np.asarray(scanvi_model.predict())[len(rna_Z):]
    except ValueError as err:
        if not went_nan(err):
            raise
        print(f"diverged during training: {str(err)[:200]}", flush=True)
        emb, native = np.full((len(rna_Z) + len(query_Z), 30), np.nan, dtype=np.float32), None

    diverged = not bool(np.isfinite(emb).all())
    rna_emb, query_emb = emb[:len(rna_Z)], emb[len(rna_Z):]
    np.save(f"{stem}_rna_emb.npy", rna_emb)
    np.save(f"{stem}_query_emb.npy", query_emb)

    pred = pd.DataFrame({"cell_id": cell_ids})
    if native is not None:
        pred["native"] = native
    if not diverged:
        clf = KNeighborsClassifier(n_neighbors=KNN_K, metric="cosine", weights="distance").fit(rna_emb, rna_labels)
        pred["shared_knn"] = clf.predict(query_emb)
    pred.to_csv(f"{stem}_pred.csv", index=False)

    return {"status": "diverged" if diverged else "completed", "diverged": diverged, "n_genes": int(query_X.shape[1]),
            "n_rna_cells": int(len(rna_Z)), "n_query_cells": int(len(query_Z)), "elapsed_s": round(time.time() - t0, 1)}


if __name__ == "__main__":
    main()
