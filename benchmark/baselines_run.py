"""Track D extension: one baseline, one dataset, one seed.

    python -m benchmark.baselines_run TOOL DATASET SEED     # from the repository root
    # TOOL maxfuse | scglue | harmony | seurat | correlation; DATASET scope2 | pbmc240 | fulcher2026; SEED 0-2
    # khoury2026 is sealed: it runs only at the final v3.1 evaluation, with --unseal
    # --out DIR writes somewhere else (a reproduction check), leaving the recorded runs alone

Inputs come from baselines_inputs.load (the same for every tool). Settings are
the original Track D runners' (maxfuse_run.py, scglue_run.py, the Harmony arm
of paired_and_pool_first.py), with the seed passed through; Seurat CCA label
transfer runs in R (seurat_cca_transfer.R). The correlation baseline is the
deliberately simple one: each query cell takes the RNA class whose mean
profile it correlates with best (Pearson, over the same genes and values every
tool gets). It is deterministic, so it runs once, seed 0. Nothing is tuned.

Writes results/baselines_ext/<dataset>/<tool>_seed<seed>_pred.csv: per query
cell, the predicted reference class under each rule:
- knn_unrestricted, knn_restricted: the shared kNN rule (evaluate.py; k = 30,
  cosine, distance weighted; restricted masks to macrophage/monocyte);
- nc_unrestricted, nc_restricted: nearest centroid in the tool's embedding;
- native_unrestricted, native_restricted (Seurat only): TransferData's
  prediction, and its best score among macrophage/monocyte;
- corr_unrestricted, corr_restricted (correlation only): the best-correlated
  class mean, over all classes and over macrophage/monocyte.
plus the embeddings (embedding tools) and a JSON record. Never reads a query label.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import baselines_inputs
from benchmark.evaluate import SUPPORTED, knn_classifier_predict, nearest_centroid_predict

OUT = baselines_inputs.D / "baselines_ext"
TOOLS = ("maxfuse", "scglue", "harmony", "seurat", "correlation")
DETERMINISTIC = ("correlation",)
R_SCRIPT = Path(__file__).resolve().parent / "seurat_cca_transfer.R"
SETTINGS = {
    "maxfuse": "Fusor on z-scored shared = active arrays; split_into_batches(max_outward_size=8000, matching_ratio=3, "
               "metacell_size=2, method='random', seed=SEED); construct_graphs(15, 15); refine_pivots(n_iters=1, "
               "cca_components=10); filter_bad_matches(pivot, 0.3); propagate; get_embedding",
    "scglue": "fit_SCGLUE, Normal likelihood on z-scored values, one self-loop per gene as the guidance graph, "
              "scGLUE's own epoch heuristic, random_seed=SEED",
    "harmony": "PCA(50, random_state=SEED) on RNA and query stacked; harmonypy.run_harmony on modality, "
               "max_iter_harmony=30, random_state=SEED",
    "seurat": "Seurat FindTransferAnchors(reduction='cca', dims=1:30, features=all genes, z-scored values as data "
              "and scale.data), then TransferData(dims=1:30); set.seed(SEED)",
    "correlation": "per RNA class, the mean of its cells' z-scored profiles; each query cell takes the class "
                   "with the highest Pearson correlation over all genes (unobserved entries 0, as for every "
                   "tool); restricted: the best of macrophage/monocyte. Deterministic: seed 0 only",
}


def run_maxfuse(inp, seed):
    import maxfuse as mf
    rna, query = inp.rna_z.astype(np.float64), inp.query_z.astype(np.float64)
    fusor = mf.model.Fusor(shared_arr1=rna, shared_arr2=query, active_arr1=rna, active_arr2=query,
                           labels1=None, labels2=None)
    fusor.split_into_batches(max_outward_size=8000, matching_ratio=3, metacell_size=2, method="random",
                             seed=seed, verbose=False)
    fusor.construct_graphs(n_neighbors1=15, n_neighbors2=15, verbose=False)
    fusor.find_initial_pivots(verbose=False)
    fusor.refine_pivots(n_iters=1, cca_components=10, verbose=False)
    fusor.filter_bad_matches(target="pivot", filter_prop=0.3, verbose=False)
    fusor.propagate(verbose=False)
    return fusor.get_embedding(active_arr1=rna, active_arr2=query)


def run_scglue(inp, seed, workdir):
    import anndata as ad
    import networkx as nx
    import scglue
    import torch
    torch.manual_seed(seed)
    np.random.seed(seed)
    adatas = {}
    for name, x in (("rna", inp.rna_z), ("query", inp.query_z)):
        a = ad.AnnData(X=x)
        a.var_names = inp.genes
        a.var["highly_variable"] = True
        scglue.models.configure_dataset(a, prob_model="Normal", use_highly_variable=True)
        adatas[name] = a
    graph = nx.Graph()
    for g in inp.genes:
        graph.add_edge(g, g, weight=1.0, sign=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        glue = scglue.models.fit_SCGLUE(adatas, graph, init_kws={"random_seed": seed},
                                        fit_kws={"directory": str(workdir)})
    return glue.encode_data("rna", adatas["rna"]), glue.encode_data("query", adatas["query"])


def run_harmony(inp, seed):
    import harmonypy
    from sklearn.decomposition import PCA
    stacked = np.vstack([inp.rna_z, inp.query_z])
    pcs = PCA(n_components=50, random_state=seed).fit_transform(stacked)
    meta = pd.DataFrame({"modality": ["RNA"] * len(inp.rna_z) + ["Protein"] * len(inp.query_z)})
    z = np.asarray(harmonypy.run_harmony(pcs, meta, ["modality"], max_iter_harmony=30, random_state=seed,
                                         verbose=False).Z_corr)
    if z.shape[0] == 50:
        z = z.T
    return z[:len(inp.rna_z)], z[len(inp.rna_z):]


def run_seurat(inp, seed, workdir):
    """Writes the inputs as raw float32 (genes x cells, column-major) for R,
    runs seurat_cca_transfer.R, and reads its predictions back."""
    workdir.mkdir(parents=True, exist_ok=True)
    np.asfortranarray(inp.rna_z.T).tofile(workdir / "rna.f32")
    np.asfortranarray(inp.query_z.T).tofile(workdir / "query.f32")
    (workdir / "genes.txt").write_text("\n".join(inp.genes) + "\n")
    pd.Series(inp.rna_labels).to_csv(workdir / "rna_labels.csv", index=False, header=["label"])
    pd.Series(inp.query_ids).to_csv(workdir / "query_ids.csv", index=False, header=["cell_id"])
    subprocess.run(["Rscript", str(R_SCRIPT), str(workdir), str(len(inp.rna_z)), str(len(inp.query_z)),
                    str(len(inp.genes)), str(seed)], check=True)
    pred = pd.read_csv(workdir / "predictions.csv")
    scores = pred[[c for c in pred.columns if c.startswith("score.")]]
    scores.columns = [c[len("score."):] for c in scores.columns]
    restricted = scores[[c for c in SUPPORTED if c in scores.columns]].idxmax(axis=1)
    return pred["predicted"].to_numpy(), restricted.to_numpy()


def environment(tool: str) -> dict:
    """Where a run ran and with what, for the record (the Mac's runs predate this)."""
    import platform
    from importlib.metadata import version
    env = {"platform": platform.platform(), "python": platform.python_version(), "numpy": version("numpy")}
    for package in {"maxfuse": ("maxfuse",), "scglue": ("scglue", "torch"), "harmony": ("harmonypy", "scikit-learn")}.get(tool, ()):
        env[package] = version(package)
    if tool == "seurat":
        env["R"] = subprocess.run(["Rscript", "-e", "cat(R.version$version.string, '| Seurat', "
                                   "as.character(packageVersion('Seurat')))"],
                                  capture_output=True, text=True, check=True).stdout.strip()
    return env


def run_correlation(inp):
    """Pearson correlation is the cosine of profiles centred across genes, and
    centring commutes with the class mean, so this is nearest centroid on
    row-centred profiles."""
    rna = inp.rna_z - inp.rna_z.mean(axis=1, keepdims=True)
    query = inp.query_z - inp.query_z.mean(axis=1, keepdims=True)
    return nearest_centroid_predict(rna, inp.rna_labels, query)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool", choices=TOOLS)
    parser.add_argument("dataset", choices=baselines_inputs.DATASETS + baselines_inputs.SEALED)
    parser.add_argument("seed", type=int)
    parser.add_argument("--smoke", type=int, default=0, help="subsample this many RNA cells, to test the plumbing only")
    parser.add_argument("--unseal", action="store_true", help="required for a sealed dataset, at its final evaluation only")
    parser.add_argument("--out", type=Path, help="write here instead of results/baselines_ext/<dataset>/")
    args = parser.parse_args()
    if args.dataset in baselines_inputs.SEALED and not args.unseal:
        raise SystemExit(f"{args.dataset} is sealed; it runs only at the final v3.1 evaluation, with --unseal "
                         "(research/benchmark/protocol-khoury2026.md)")
    if args.tool in DETERMINISTIC and args.seed != 0:
        raise SystemExit(f"{args.tool} is deterministic; it runs once, as seed 0")
    t0 = time.time()
    inp = baselines_inputs.load(args.dataset)
    out_dir = args.out or (OUT / ("smoke" if args.smoke else args.dataset))
    if args.smoke:
        keep = np.random.default_rng(0).choice(len(inp.rna_z), args.smoke, replace=False)
        inp.rna_z, inp.rna_labels = inp.rna_z[keep], inp.rna_labels[keep]
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"{args.tool}_seed{args.seed}"

    pred = pd.DataFrame({"cell_id": inp.query_ids})
    diverged = False
    if args.tool == "seurat":
        pred["native_unrestricted"], pred["native_restricted"] = run_seurat(inp, args.seed, Path(f"{stem}_work"))
    elif args.tool == "correlation":
        corr = run_correlation(inp)
        pred["corr_unrestricted"], pred["corr_restricted"] = corr["unrestricted"], corr["restricted"]
    else:
        runner = {"maxfuse": run_maxfuse, "harmony": run_harmony}.get(args.tool)
        rna_emb, query_emb = (runner(inp, args.seed) if runner
                              else run_scglue(inp, args.seed, Path(f"{stem}_work")))
        diverged = not (np.isfinite(rna_emb).all() and np.isfinite(query_emb).all())
        np.save(f"{stem}_rna_emb.npy", rna_emb)
        np.save(f"{stem}_query_emb.npy", query_emb)
        if not diverged:
            knn = knn_classifier_predict(rna_emb, inp.rna_labels, query_emb)
            nc = nearest_centroid_predict(rna_emb, inp.rna_labels, query_emb)
            pred["knn_unrestricted"], pred["knn_restricted"] = knn["unrestricted"], knn["restricted"]
            pred["nc_unrestricted"], pred["nc_restricted"] = nc["unrestricted"], nc["restricted"]
    pred.to_csv(f"{stem}_pred.csv", index=False)
    record = {"tool": args.tool, "seed": args.seed, "deterministic": args.tool in DETERMINISTIC,
              "settings": SETTINGS[args.tool], "diverged": diverged,
              "smoke_rna_cells": args.smoke or None, **inp.record, "environment": environment(args.tool),
              "elapsed_s": round(time.time() - t0, 1)}
    Path(f"{stem}.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
