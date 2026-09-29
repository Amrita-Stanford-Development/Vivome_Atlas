"""scGLUE, full 85,232-cell RNA reference (user's rule 2).

Produces embeddings only -- scoring (shared kNN rule + native
nearest-centroid + bootstrap CIs) is recompute_v2.py's job, run once after
every method's embeddings exist, so there is exactly one scoring code path
instead of one per method that could drift apart.

At full scale scGLUE's own dataset-size heuristic picks max_epochs/patience
automatically (48/4 here, vs. 207/18 at a much smaller trial) -- this
script does not override that. Training converged smoothly at this scale
(no divergence); see research/benchmark/bugs-and-fixes.md for a smaller-scale
run where it did not.
"""
import time
from pathlib import Path
import numpy as np
import pandas as pd
import anndata as ad
import networkx as nx
import scglue
import warnings

D = Path(__file__).resolve().parent / "results"


def main():
    t0 = time.time()

    rna_X = np.load(D / "rna_X.npy")
    prot_X = np.load(D / "prot_X.npy")
    rna_meta = pd.read_csv(D / "rna_meta.csv")
    prot_meta = pd.read_csv(D / "prot_meta.csv")
    with open(D / "gene_cols.txt") as f:
        gene_cols = f.read().splitlines()
    gene_names = [c[len("gene_"):] for c in gene_cols]
    print(f"RNA cells: {len(rna_meta)} (full reference, no subsample). elapsed {time.time()-t0:.1f}s", flush=True)

    def zscore_cols(X, eps=1e-8):
        mean = X.mean(axis=0, keepdims=True)
        std = X.std(axis=0, keepdims=True)
        return (X - mean) / np.clip(std, eps, None)

    rna_Z = zscore_cols(rna_X).astype(np.float32)
    prot_Z = zscore_cols(prot_X).astype(np.float32)

    adata_rna = ad.AnnData(X=rna_Z)
    adata_rna.var_names = gene_names
    adata_rna.var["highly_variable"] = True

    adata_prot = ad.AnnData(X=prot_Z)
    adata_prot.var_names = gene_names
    adata_prot.var["highly_variable"] = True

    # Trivial guidance graph: both modalities use the EXACT same gene names
    # (identical var_names), so a self-loop per gene is the whole graph --
    # scglue's own node-identity mechanism (shared string in both AnnData
    # var_names) is what actually links the two modalities' copies of a
    # gene; the self-loop just satisfies its structural graph-validity check.
    graph = nx.Graph()
    for g in gene_names:
        graph.add_edge(g, g, weight=1.0, sign=1)

    scglue.graph.check_graph(graph, [adata_rna, adata_prot])
    print(f"Graph OK, {graph.number_of_nodes()} nodes. elapsed {time.time()-t0:.1f}s", flush=True)

    # prob_model="Normal": our data is already z-scored continuous values,
    # not raw counts -- scglue's NB/ZINB defaults assume non-negative counts.
    scglue.models.configure_dataset(adata_rna, prob_model="Normal", use_highly_variable=True)
    scglue.models.configure_dataset(adata_prot, prob_model="Normal", use_highly_variable=True)
    print(f"Datasets configured. elapsed {time.time()-t0:.1f}s", flush=True)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        glue = scglue.models.fit_SCGLUE(
            {"rna": adata_rna, "prot": adata_prot}, graph,
            fit_kws={"directory": str(D / "glue_ckpt_full")},
        )
    print(f"GLUE fit done. elapsed {time.time()-t0:.1f}s", flush=True)

    rna_emb = glue.encode_data("rna", adata_rna)
    prot_emb = glue.encode_data("prot", adata_prot)
    print(f"Embeddings extracted. shapes {rna_emb.shape} {prot_emb.shape}. "
          f"NaN: {np.isnan(rna_emb).sum()} {np.isnan(prot_emb).sum()}. "
          f"elapsed {time.time()-t0:.1f}s", flush=True)

    np.save(D / "rna_scglue.npy", rna_emb)
    np.save(D / "prot_scglue.npy", prot_emb)
    print(f"\nTOTAL elapsed {time.time()-t0:.1f}s -- run recompute_v2.py next to score")


if __name__ == "__main__":
    main()
