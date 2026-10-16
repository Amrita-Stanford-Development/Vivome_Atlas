"""Corrected baselines, after the review of 2026-10-03: one tool, one dataset,
one seed. The corrections were fixed in research/benchmark/baseline-corrections.md
before any corrected run; nothing here is tuned on a query label.

    python -m benchmark.baselines_corrected TOOL DATASET SEED              # from the repository root
    # TOOL correlation | pca | harmony | seurat | maxfuse | scglue | scanvi
    # DATASET scope2 | pbmc240 | fulcher2026 | scope2_reprocessed (Track G, Phase 4); SEED 0-2
    # benchmark/baselines_corrected_queue.sh DATASET runs every tool and seed on one dataset
    python -m benchmark.baselines_corrected TOOL khoury2026 SEED --posthoc
    # Khoury 2026's labels were read at its one scoring; runs on it are post-hoc
    # --smoke N (development datasets only) subsamples N RNA cells, few epochs: plumbing only
    python -m benchmark.baselines_corrected TOOL DATASET SEED --labels v52
    # the reference cells relabelled as a candidate model's were (clean | v51 | v52), so
    # each candidate is compared with baselines that used its own reference labels
    # (protocol-sorted-cd4cd8.md, rule 4); written beside the original runs, never over them

What changed from baselines_run.py (which stays as it was, the reference for
the earlier tables and for Khoury's sealed result):
1. The RNA side is z-scored class-balanced (every reference class weighted
   equally); the query side is unchanged. Seurat CCA and MaxFuse re-centre each
   gene within each modality themselves, so for them this changes nothing.
2. MaxFuse uses the settings of its own PBMC CITE-seq tutorial, and adds its
   native transfer through the matching (column match_unrestricted).
3. scANVI gets the inputs every tool gets, shifted by one constant so that no
   value is negative (its likelihood's mean cannot be); it also writes its
   native classifier (clf_unrestricted, clf_restricted).
4. A plain PCA arm: Harmony's input, uncorrected.
5. Every embedding run records two setup checks that use RNA labels only:
   held-out RNA kNN balanced accuracy, and how much query cells mix with RNA.

Writes results/baselines_corrected/<dataset>/<tool>_seed<seed>{.json,_pred.csv,
_rna_emb.npy,_query_emb.npy}, with the columns baselines_run.py writes. Never
reads a query label.
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score
from sklearn.neighbors import NearestNeighbors

from benchmark import baselines_inputs, baselines_run, datasets
from benchmark.evaluate import KNN_K, SUPPORTED, knn_classifier_predict, nearest_centroid_predict

OUT = baselines_inputs.D / "baselines_corrected"
# Reference label sets a run can use instead of the atlas's own: each table has
# one row per reference cell, in service/model/runtime/reference_metadata.csv's
# order, with the original and the new class.
LABEL_SETS = {
    "original": None,
    "clean": datasets.REPO / "research" / "notebook-outputs" / "v5_labels" / "reference_labels_clean.csv.gz",
    "v51": datasets.REPO / "research" / "notebook-outputs" / "v51_labels" / "reference_labels_v51.csv.gz",
    "v52": datasets.REPO / "research" / "notebook-outputs" / "v52_labels" / "reference_labels_v52.csv.gz",
}


def out_dir(labels: str = "original") -> Path:
    """Where a label set's runs go: the original runs stay where they were."""
    return OUT if labels == "original" else baselines_inputs.D / f"baselines_corrected_labels_{labels}"


def relabel(rna_meta: pd.DataFrame, table: pd.DataFrame) -> np.ndarray:
    """The benchmark's RNA cells (rna_meta.csv: orig_index, class_name) with
    another label set's class (columns class_original, class_clean). orig_index
    is the cell's row in the label table; every cell's original class must
    match, so a misaligned join cannot pass."""
    index = rna_meta["orig_index"].to_numpy()
    if index.min() < 0 or index.max() >= len(table):
        raise ValueError(f"orig_index runs to {index.max()}, but the label table has {len(table)} rows")
    mismatched = table["class_original"].to_numpy()[index] != rna_meta["class_name"].to_numpy()
    if mismatched.any():
        raise ValueError(f"{int(mismatched.sum())} cells' original class differs: not the reference's cell order")
    return table["class_clean"].to_numpy()[index]
TOOLS = ("correlation", "pca", "harmony", "seurat", "maxfuse", "scglue", "scanvi")
SINGLE_RUN = ("correlation", "pca", "seurat")  # deterministic, or deterministic given its inputs: seed 0 only
POSTHOC = ("khoury2026",)
SCALING = ("RNA: each gene z-scored class-balanced (each of the 22 reference classes weighted equally, RNA labels "
           "only); query: each gene z-scored over its observed values, unobserved entries 0")
RNA_INPUT = "atlas RNA reference as stored: per-gene z-scores over all 85,232 cells (benchmark/load.py)"
SETTINGS = {
    "correlation": baselines_run.SETTINGS["correlation"],
    "pca": "PCA(50, random_state=SEED) on RNA and query stacked (Harmony's input), no correction",
    "harmony": baselines_run.SETTINGS["harmony"],
    "seurat": "Seurat FindTransferAnchors(reduction='cca', dims=1:30, features=all genes), our values as 'data'; "
              "Seurat runs ScaleData itself, re-centring and re-scaling every gene within each object; then "
              "TransferData(dims=1:30); set.seed(SEED)",
    "maxfuse": "MaxFuse's PBMC CITE-seq tutorial settings: split_into_batches(5000, 3, 2, seed=SEED); "
               "construct_graphs(15, 15, svd 30/30, resolution 2/2, tol 0.1, leiden_seed=SEED); "
               "find_initial_pivots(wt 0.7/0.7, svd 25/20); refine_pivots(wt 0.7/0.7, svd 30/30, cca 20, n_iters=3); "
               "filter_bad_matches(pivot, 0.3); get_embedding; propagate(svd 30/30, wt 0.7/0.7); "
               "filter_bad_matches(propagated, 0); native rule: the matched RNA cell's label, "
               "get_matching(order=(2, 1), target='full_data'), ties by matching score",
    "scglue": baselines_run.SETTINGS["scglue"],
    "scanvi": "scVI then scANVI (scvi-tools), n_latent=30, 2 layers of 128, gene_likelihood='normal', "
              "log_variational=False, batch_key=modality, size factor 1, 200 + 100 epochs, early stopping "
              "(patience 15); inputs as every tool's plus one constant so the minimum is 0; seed SEED",
}


def class_balanced_z(x: np.ndarray, labels: np.ndarray, eps: float = 1e-8, block: int = 256) -> np.ndarray:
    """Per gene, (x - mean) / SD with each class weighted equally: every class
    contributes 1/n_classes, split evenly over its cells."""
    _, index, counts = np.unique(labels, return_inverse=True, return_counts=True)
    w = 1.0 / (len(counts) * counts[index])
    out = np.empty(x.shape, dtype=np.float32)
    for start in range(0, x.shape[1], block):  # in blocks of genes, to bound memory
        cols = x[:, start:start + block].astype(np.float64)
        mean = w @ cols
        sd = np.sqrt(w @ (cols - mean) ** 2)
        out[:, start:start + block] = (cols - mean) / np.clip(sd, eps, None)
    return out


def load(dataset: str, labels: str = "original"):
    """The tool's inputs; with another label set, the RNA side is relabelled
    before its class-balanced scaling, which the labels also decide."""
    inp = baselines_inputs.load(dataset)
    reference_labels = {"set": "original", "file": "benchmark/results/rna_meta.csv"}
    if labels != "original":
        path = LABEL_SETS[labels]
        new = relabel(pd.read_csv(baselines_inputs.D / "rna_meta.csv"), pd.read_csv(path))
        reference_labels = {"set": labels, "file": path.relative_to(datasets.REPO).as_posix(),
                            "sha256": _sha256(path), "cells_relabelled": int((new != inp.rna_labels).sum())}
        inp.rna_labels = new
    inp.rna_z = class_balanced_z(inp.rna_z, inp.rna_labels)
    inp.record = {**inp.record, "rna_input": RNA_INPUT, "scaling": SCALING, "reference_labels": reference_labels}
    return inp


def _sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_pca(inp, seed):
    from sklearn.decomposition import PCA
    pcs = PCA(n_components=50, random_state=seed).fit_transform(np.vstack([inp.rna_z, inp.query_z]))
    return pcs[:len(inp.rna_z)], pcs[len(inp.rna_z):]


def run_maxfuse(inp, seed):
    """MaxFuse's PBMC CITE-seq tutorial, verbatim apart from the seed
    (https://github.com/shuxiaoc/maxfuse/blob/main/docs/citeseq_pbmc_evaluate.ipynb)."""
    import maxfuse as mf
    rna, query = inp.rna_z.astype(np.float64), inp.query_z.astype(np.float64)
    fusor = mf.model.Fusor(shared_arr1=rna, shared_arr2=query, active_arr1=rna, active_arr2=query,
                           labels1=None, labels2=None)
    fusor.split_into_batches(max_outward_size=5000, matching_ratio=3, metacell_size=2, seed=seed, verbose=False)
    fusor.construct_graphs(n_neighbors1=15, n_neighbors2=15, svd_components1=30, svd_components2=30,
                           resolution1=2, resolution2=2, resolution_tol=0.1, leiden_seed=seed, verbose=False)
    fusor.find_initial_pivots(wt1=0.7, wt2=0.7, svd_components1=25, svd_components2=20, verbose=False)
    fusor.refine_pivots(wt1=0.7, wt2=0.7, svd_components1=30, svd_components2=30, cca_components=20,
                        n_iters=3, randomized_svd=False, svd_runs=1, verbose=False)
    fusor.filter_bad_matches(target="pivot", filter_prop=0.3, verbose=False)
    rna_emb, query_emb = fusor.get_embedding(active_arr1=fusor.active_arr1, active_arr2=fusor.active_arr2)
    fusor.propagate(svd_components1=30, svd_components2=30, wt1=0.7, wt2=0.7, verbose=False)
    fusor.filter_bad_matches(target="propagated", filter_prop=0, verbose=False)
    rna_idx, query_idx, score = fusor.get_matching(order=(2, 1), target="full_data")
    return rna_emb, query_emb, matched_labels(inp.rna_labels, np.asarray(rna_idx), np.asarray(query_idx),
                                              np.asarray(score, dtype=float), len(query))


def matched_labels(rna_labels, rna_idx, query_idx, score, n_query) -> np.ndarray:
    """Each query cell takes its matched RNA cell's label; several matches vote by
    matching score. An unmatched cell gets "" (no answer, scored as wrong)."""
    votes = pd.DataFrame({"query": query_idx, "label": rna_labels[rna_idx], "score": score})
    best = votes.groupby(["query", "label"])["score"].sum().reset_index().sort_values(
        ["query", "score", "label"], ascending=[True, False, True]).drop_duplicates("query")
    out = np.full(n_query, "", dtype=object)
    out[best["query"].to_numpy()] = best["label"].to_numpy()
    return out


def run_scanvi(inp, seed, smoke=False):
    import anndata as ad
    import scvi
    import torch
    from scvi.model import SCANVI, SCVI
    scvi.settings.seed = seed
    torch.manual_seed(seed)
    np.random.seed(seed)
    shift = float(-min(inp.rna_z.min(), inp.query_z.min(), 0.0))
    adata = ad.AnnData(X=np.vstack([inp.rna_z, inp.query_z]).astype(np.float32) + np.float32(shift))
    adata.obs["modality"] = ["RNA"] * len(inp.rna_z) + ["Protein"] * len(inp.query_z)
    adata.obs["cell_type"] = pd.Categorical(list(inp.rna_labels) + ["Unknown"] * len(inp.query_z))
    adata.obs["size_factor"] = 1.0
    epochs = (5, 3) if smoke else (200, 100)
    n = len(inp.rna_z)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # its "not count data" warning: known, see the record
        SCVI.setup_anndata(adata, batch_key="modality", labels_key="cell_type", size_factor_key="size_factor")
        model = SCVI(adata, n_latent=30, n_layers=2, n_hidden=128, gene_likelihood="normal", log_variational=False)
        model.train(max_epochs=epochs[0], early_stopping=True, early_stopping_patience=15)
        scvi_epochs = len(model.history.get("elbo_train", []))
        model = SCANVI.from_scvi_model(model, unlabeled_category="Unknown", labels_key="cell_type")
        model.train(max_epochs=epochs[1], early_stopping=True, early_stopping_patience=15)
        scanvi_epochs = len(model.history.get("elbo_train", []))
    emb = model.get_latent_representation()
    soft = model.predict(soft=True).iloc[n:]
    restricted = soft[[c for c in SUPPORTED if c in soft.columns]].idxmax(axis=1).to_numpy()
    info = {"input_shift": shift, "epochs_trained": {"scvi": scvi_epochs, "scanvi": scanvi_epochs}}
    return emb[:n], emb[n:], soft.idxmax(axis=1).to_numpy(), restricted, info


def setup_checks(rna_emb, rna_labels, query_emb) -> dict:
    """RNA labels only. Held-out RNA kNN: does the embedding carry cell types at
    all? Mixing: are query cells among RNA cells, or apart from them?"""
    rng = np.random.default_rng(0)
    n = len(rna_emb)
    test = rng.choice(n, min(10_000, n // 5), replace=False)
    train = np.setdiff1d(np.arange(n), test)
    pred = knn_classifier_predict(rna_emb[train], rna_labels[train], rna_emb[test])["unrestricted"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        bal = balanced_accuracy_score(rna_labels[test], np.asarray(pred))
    joint = np.vstack([rna_emb, query_emb])
    _, idx = NearestNeighbors(n_neighbors=KNN_K + 1, metric="cosine").fit(joint).kneighbors(query_emb)
    share = (idx[:, 1:] >= n).mean(axis=1)
    return {"rna_holdout_knn_balanced_accuracy_pct": round(100 * bal, 2),
            "rna_holdout_knn_chance_pct": round(100 / len(set(rna_labels)), 2),
            "query_neighbour_share_median_pct": round(100 * float(np.median(share)), 2),
            "query_neighbour_share_if_mixed_pct": round(100 * len(query_emb) / len(joint), 2)}


def correlation_check(inp) -> dict:
    """The correlation rule's own RNA-side check: held-out RNA cells against the
    class means of the rest."""
    rng = np.random.default_rng(0)
    n = len(inp.rna_z)
    test = rng.choice(n, min(10_000, n // 5), replace=False)
    train = np.setdiff1d(np.arange(n), test)
    center = lambda x: x - x.mean(axis=1, keepdims=True)  # noqa: E731
    pred = nearest_centroid_predict(center(inp.rna_z[train]), inp.rna_labels[train], center(inp.rna_z[test]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        bal = balanced_accuracy_score(inp.rna_labels[test], np.asarray(pred["unrestricted"]))
    return {"rna_holdout_balanced_accuracy_pct": round(100 * bal, 2),
            "rna_holdout_chance_pct": round(100 / len(set(inp.rna_labels)), 2)}


def run(args, inp, stem: Path) -> dict:
    pred = pd.DataFrame({"cell_id": inp.query_ids})
    extra, diverged = {}, False
    if args.tool == "seurat":
        pred["native_unrestricted"], pred["native_restricted"] = baselines_run.run_seurat(inp, args.seed, Path(f"{stem}_work"))
    elif args.tool == "correlation":
        corr = baselines_run.run_correlation(inp)
        pred["corr_unrestricted"], pred["corr_restricted"] = corr["unrestricted"], corr["restricted"]
        extra["setup_checks"] = correlation_check(inp)
    else:
        if args.tool == "maxfuse":
            rna_emb, query_emb, pred["match_unrestricted"] = run_maxfuse(inp, args.seed)
            extra["matched_query_cells_pct"] = round(100 * float((pred["match_unrestricted"] != "").mean()), 2)
        elif args.tool == "scanvi":
            try:
                rna_emb, query_emb, clf, clf_restricted, extra = run_scanvi(inp, args.seed, bool(args.smoke))
                pred["clf_unrestricted"], pred["clf_restricted"] = clf, clf_restricted
            except ValueError as err:  # a NaN during training makes torch raise (amendment 4's rule)
                if not baselines_run.went_nan(err):
                    raise
                rna_emb = np.full((len(inp.rna_z), 30), np.nan, dtype=np.float32)
                query_emb = np.full((len(inp.query_z), 30), np.nan, dtype=np.float32)
        elif args.tool == "scglue":
            rna_emb, query_emb = baselines_run.run_scglue(inp, args.seed, Path(f"{stem}_work"))
        else:
            rna_emb, query_emb = {"pca": run_pca, "harmony": baselines_run.run_harmony}[args.tool](inp, args.seed)
        diverged = not (np.isfinite(rna_emb).all() and np.isfinite(query_emb).all())
        np.save(f"{stem}_rna_emb.npy", rna_emb)
        np.save(f"{stem}_query_emb.npy", query_emb)
        if not diverged:
            knn = knn_classifier_predict(rna_emb, inp.rna_labels, query_emb)
            nc = nearest_centroid_predict(rna_emb, inp.rna_labels, query_emb)
            pred["knn_unrestricted"], pred["knn_restricted"] = knn["unrestricted"], knn["restricted"]
            pred["nc_unrestricted"], pred["nc_restricted"] = nc["unrestricted"], nc["restricted"]
            extra["setup_checks"] = setup_checks(rna_emb, inp.rna_labels, query_emb)
    pred.to_csv(f"{stem}_pred.csv", index=False)
    env = baselines_run.environment(args.tool)
    if args.tool == "scanvi":
        from importlib.metadata import version
        env.update({"scvi-tools": version("scvi-tools"), "torch": version("torch")})
    return {"status": "diverged" if diverged else "completed", "diverged": diverged, **extra, "environment": env}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool", choices=TOOLS)
    parser.add_argument("dataset", choices=baselines_inputs.DATASETS + baselines_inputs.ADDED + POSTHOC
                        + baselines_inputs.SORTED + baselines_inputs.HELDOUT)
    parser.add_argument("seed", type=int, choices=(0, 1, 2))
    parser.add_argument("--smoke", type=int, default=0, help="development datasets only: subsample N RNA cells")
    parser.add_argument("--posthoc", action="store_true", help="required for Khoury 2026: its runs are post-hoc")
    parser.add_argument("--labels", choices=tuple(LABEL_SETS), default="original",
                        help="the reference label set (a candidate model's own); runs go to their own directory")
    args = parser.parse_args()
    posthoc = args.dataset in POSTHOC
    if posthoc and not args.posthoc:
        raise SystemExit("Khoury 2026's labels were read at its one scoring: corrected runs on it are post-hoc. "
                         "Pass --posthoc (research/benchmark/baseline-corrections.md)")
    if posthoc and args.smoke:
        raise SystemExit("--smoke is for the development datasets only")
    if args.tool in SINGLE_RUN and args.seed != 0:
        raise SystemExit(f"{args.tool} runs once, as seed 0")
    run_dir = out_dir(args.labels) / ("smoke" if args.smoke else args.dataset)
    stem = run_dir / f"{args.tool}_seed{args.seed}"
    if not args.smoke and Path(f"{stem}.json").exists():
        status = json.loads(Path(f"{stem}.json").read_text()).get("status")
        if status != "failed":  # a completed or diverged run is final; a failed one may run again
            raise SystemExit(f"{stem}.json exists ({status}); not rerun")
    t0 = time.time()
    inp = load(args.dataset, args.labels)
    if args.smoke:
        keep = np.random.default_rng(0).choice(len(inp.rna_z), args.smoke, replace=False)
        inp.rna_z, inp.rna_labels = inp.rna_z[keep], inp.rna_labels[keep]
    run_dir.mkdir(parents=True, exist_ok=True)
    base = {"tool": args.tool, "seed": args.seed, "settings": SETTINGS[args.tool], "posthoc": posthoc,
            "corrections": "research/benchmark/baseline-corrections.md", "smoke_rna_cells": args.smoke or None,
            **inp.record}
    try:
        record = {**base, **run(args, inp, stem)}
    except Exception as err:  # every exit leaves a record: a failed run is not a missing one
        record = {**base, "status": "failed", "diverged": False, "error": f"{type(err).__name__}: {err}"[:2000],
                  "elapsed_s": round(time.time() - t0, 1)}
        Path(f"{stem}.json").write_text(json.dumps(record, indent=2) + "\n")
        raise
    record["elapsed_s"] = round(time.time() - t0, 1)
    Path(f"{stem}.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
