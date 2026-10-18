"""Co-expression modules for the encoder's module pooling (Reference_Projection_v3,
cell 5): genes clustered on a PCA of z-scored RNA, about 18 genes per
module, then oversized modules give genes to undersized ones.

Blood's served modules came from that notebook's run; this port may not
reproduce them exactly (another sklearn), so blood's build takes the served
assignment and this one is only compared with it.
"""
from __future__ import annotations

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA


def build(X: np.ndarray, target_size: int = 18, cells: int = 15000, pca: int = 64, seed: int = 0) -> np.ndarray:
    """X: (cells, genes) log-normalised RNA. Returns each gene's module index."""
    G = X.shape[1]
    K = int(np.ceil(G / target_size))
    Xz = (X - X.mean(0)) / (X.std(0) + 1e-8)  # the notebook z-scored the whole reference first
    sub = np.random.default_rng(seed).choice(len(Xz), min(cells, len(Xz)), replace=False)
    Xs = Xz[sub]
    Xs = (Xs - Xs.mean(0)) / (Xs.std(0) + 1e-8)
    P = PCA(n_components=pca, random_state=seed).fit_transform(Xs.T.astype(np.float32))
    P /= (np.linalg.norm(P, axis=1, keepdims=True) + 1e-8)
    km = MiniBatchKMeans(n_clusters=K, random_state=seed, n_init=10, batch_size=2048, max_iter=300).fit(P)
    mod, cent = km.labels_.copy(), km.cluster_centers_
    for _ in range(6):
        sizes = np.bincount(mod, minlength=K)
        big = np.where(sizes > 3 * target_size)[0]
        small = np.where(sizes < target_size // 2)[0]
        if len(big) == 0 or len(small) == 0:
            break
        for b in big:
            members = np.where(mod == b)[0]
            d = P[members] @ cent[small].T
            n_move = sizes[b] - 2 * target_size
            if n_move <= 0:
                continue
            take = members[np.argsort(-d.max(1))][:n_move]
            mod[take] = small[d[np.isin(members, take)].argmax(1)]
    return mod.astype(np.int64)
