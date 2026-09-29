"""MaxFuse, full 85,232-cell RNA reference (user's rule 2: try full scale
first; only subsample if compute genuinely forces it, and if so, apply the
identical subsample to every arm and disclose it).

Produces embeddings only -- scoring (shared kNN rule + native
nearest-centroid + bootstrap CIs) is recompute_v2.py's job, run once after
every method's embeddings exist, so there is exactly one scoring code path
instead of one per method that could drift apart.

Needed cca_components=10 (down from an initial 20) to avoid a real
`numpy.linalg.LinAlgError: SVD did not converge` that a batch hit at full
85,232-cell scale -- see research/benchmark/bugs-and-fixes.md.
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import maxfuse as mf

D = Path(__file__).resolve().parent / "results"

t0 = time.time()
rna_X = np.load(D / "rna_X.npy")
prot_X = np.load(D / "prot_X.npy")
rna_meta = pd.read_csv(D / "rna_meta.csv")
prot_meta = pd.read_csv(D / "prot_meta.csv")
print(f"RNA cells: {len(rna_meta)} (full reference, no subsample). elapsed {time.time()-t0:.1f}s", flush=True)


def zscore_cols(X, eps=1e-8):
    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    return (X - mean) / np.clip(std, eps, None)


rna_Z = zscore_cols(rna_X).astype(np.float64)
prot_Z = zscore_cols(prot_X).astype(np.float64)

fusor = mf.model.Fusor(
    shared_arr1=rna_Z, shared_arr2=prot_Z,
    active_arr1=rna_Z, active_arr2=prot_Z,
    labels1=None, labels2=None,
)
print(f"Fusor created. elapsed {time.time()-t0:.1f}s", flush=True)

fusor.split_into_batches(max_outward_size=8000, matching_ratio=3, metacell_size=2, method='random', seed=0, verbose=True)
print(f"split_into_batches done. elapsed {time.time()-t0:.1f}s", flush=True)

fusor.construct_graphs(n_neighbors1=15, n_neighbors2=15, verbose=True)
print(f"construct_graphs done. elapsed {time.time()-t0:.1f}s", flush=True)

fusor.find_initial_pivots(verbose=True)
print(f"find_initial_pivots done. elapsed {time.time()-t0:.1f}s", flush=True)

fusor.refine_pivots(n_iters=1, cca_components=10, verbose=True)
print(f"refine_pivots done. elapsed {time.time()-t0:.1f}s", flush=True)

fusor.filter_bad_matches(target='pivot', filter_prop=0.3, verbose=True)
print(f"filter_bad_matches done. elapsed {time.time()-t0:.1f}s", flush=True)

fusor.propagate(verbose=True)
print(f"propagate done. elapsed {time.time()-t0:.1f}s", flush=True)

rna_emb, prot_emb = fusor.get_embedding(active_arr1=rna_Z, active_arr2=prot_Z)
print(f"get_embedding done. shapes {rna_emb.shape} {prot_emb.shape} elapsed {time.time()-t0:.1f}s", flush=True)
print(f"NaN check: {np.isnan(rna_emb).sum()} {np.isnan(prot_emb).sum()}", flush=True)

np.save(D / "rna_maxfuse.npy", rna_emb)
np.save(D / "prot_maxfuse.npy", prot_emb)
print(f"\nTOTAL elapsed {time.time()-t0:.1f}s -- run recompute_v2.py next to score")
