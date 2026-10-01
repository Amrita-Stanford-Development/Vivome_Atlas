"""VivOME T1 NB2 core: label space, decision rule, abstention and conformal sets.

Everything here works on per cell class scores that were already computed from the
encoder (cosine to class centroids, kNN votes, max cosine to any reference cell).
No proteomics label is read in this module.
"""
import re

import numpy as np
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

# ------------------------------------------------------------------ hierarchy
GROUP_RULES = [  # checked in order; first match wins
    ("dendritic cell",          ("dendritic",)),
    ("T cell",                  ("nk t", "nkt", "natural killer t", "t cell", "thymus", "regulatory t")),
    ("NK cell",                 ("natural killer", "nk cell")),
    ("B cell",                  ("b cell", "plasma")),
    ("monocyte/macrophage",     ("monocyte", "macrophage")),
    ("granulocyte",             ("neutrophil", "basophil", "eosinophil", "granulocyte", "mast")),
    ("erythroid",               ("erythro",)),
    ("platelet/megakaryocyte",  ("platelet", "megakaryocyte")),
    ("progenitor",              ("progenitor", "stem", "hematopoietic")),
]


def group_of(name):
    lc = name.lower()
    for g, keys in GROUP_RULES:
        if any(k in lc for k in keys):
            return g
    if re.search(r"\bnk\b", lc):
        return "NK cell"
    return "other"


def t_subtype(name):
    lc = name.lower()
    return "CD4" if "cd4" in lc else "CD8" if "cd8" in lc else "other"


# ------------------------------------------------------------ probabilities
def softmax(L, T=1.0):
    Z = L / T
    Z = Z - Z.max(1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(1, keepdims=True)


def logits_for(rule, cos, votes, k):
    if rule == "centroid":
        return cos.astype(np.float64)
    C = votes.shape[1]
    return np.log((votes.astype(np.float64) + 0.5) / (k + 0.5 * C))


def fit_temperature(L, y, grid=None):
    """Grid search of a single temperature minimising NLL of softmax(L / T)."""
    grid = np.exp(np.linspace(np.log(0.003), np.log(3.0), 80)) if grid is None else grid
    best, bestT = np.inf, 1.0
    for T in grid:
        P = softmax(L, T)
        nll = -np.mean(np.log(np.clip(P[np.arange(len(y)), y], 1e-12, None)))
        if nll < best:
            best, bestT = nll, float(T)
    return bestT, float(best)


def ece(P, y, bins=15):
    conf = P.max(1); pred = P.argmax(1); acc = pred == y
    edges = np.linspace(0, 1, bins + 1); e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs(acc[m].mean() - conf[m].mean())
    return float(e)


# ------------------------------------------------------------ label space
def em_prior(P, src, iters=300, tol=1e-7):
    """Saerens et al. EM (maximum likelihood label shift). P: calibrated
    posteriors under the source prior `src`. Returns (target prior, adjusted P)."""
    pi = src.copy()
    for _ in range(iters):
        A = P * (pi / src)[None, :]
        A /= A.sum(1, keepdims=True)
        new = A.mean(0)
        if np.abs(new - pi).max() < tol:
            pi = new
            break
        pi = new
    A = P * (pi / src)[None, :]
    return pi, A / A.sum(1, keepdims=True)


def estimate_label_space(P, method, tau, src):
    """Returns (bool mask of kept classes, final per cell probabilities over all C
    columns, zero outside the mask)."""
    C = P.shape[1]
    if method == "none":
        return np.ones(C, bool), P
    if method == "em_adjust":
        _, A = em_prior(P, src)
        return np.ones(C, bool), A
    if method == "em_restrict":
        pi, A = em_prior(P, src)
        keep = pi >= tau
        base = A
    elif method == "support_restrict":
        share = np.bincount(P.argmax(1), minlength=C) / len(P)
        keep = (share >= tau) & (np.bincount(P.argmax(1), minlength=C) >= 3)
        base = P
    else:
        raise ValueError(method)
    if not keep.any():
        keep[np.argmax(base.mean(0))] = True
    Q = base * keep[None, :]
    return keep, Q / np.clip(Q.sum(1, keepdims=True), 1e-12, None)


# ------------------------------------------------------------ conformal
def conformal_level(n, alpha):
    return min(1.0, np.ceil((n + 1) * (1 - alpha)) / max(n, 1))


def fit_qhat(scores, y, C, alpha, mondrian, min_n=50):
    """Split conformal (LAC score = 1 - p_true). Mondrian: one quantile per true
    class; classes with fewer than min_n calibration cells use the marginal one."""
    marg = float(np.quantile(scores, conformal_level(len(scores), alpha), method="higher"))
    q = np.full(C, marg)
    if mondrian:
        for c in range(C):
            s = scores[y == c]
            if len(s) >= min_n:
                q[c] = float(np.quantile(s, conformal_level(len(s), alpha), method="higher"))
    return q, marg


def prediction_sets(P, q, keep):
    return (P >= (1.0 - q)[None, :]) & keep[None, :]


# ------------------------------------------------------------ outputs
KIND = {0: "fine", 1: "group", 2: "lineage", 3: "abstain_empty", 4: "abstain_ambiguous",
        5: "abstain_ood", 6: "abstain_coverage"}


def resolve(S, grp_idx, lin_idx, ood, low_cov):
    """Per cell output. S: (n, C) bool sets. grp_idx, lin_idx: (C,) int codes.
    Returns kind (n,) and value (n,) where value is a class index (fine), a group
    code (group) or a lineage code (lineage), else -1."""
    n = S.shape[0]
    kind = np.full(n, 4); val = np.full(n, -1)
    size = S.sum(1)
    for i in range(n):
        if low_cov[i]:
            kind[i] = 6; continue
        if ood[i]:
            kind[i] = 5; continue
        if size[i] == 0:
            kind[i] = 3; continue
        cls = np.flatnonzero(S[i])
        if size[i] == 1:
            kind[i], val[i] = 0, cls[0]; continue
        g = np.unique(grp_idx[cls])
        if len(g) == 1:
            kind[i], val[i] = 1, g[0]; continue
        l = np.unique(lin_idx[cls])
        if len(l) == 1:
            kind[i], val[i] = 2, l[0]; continue
    return kind, val


def output_metrics(kind, val, y, grp_idx, lin_idx):
    """Strict fine balanced accuracy (anything but a correct single label counts
    as wrong), rates of each output kind, and correctness of committed outputs at
    the level they were stated."""
    n = len(y)
    pred_fine = np.where(kind == 0, val, -1)
    committed = kind <= 2
    ok = np.zeros(n, bool)
    ok[kind == 0] = val[kind == 0] == y[kind == 0]
    ok[kind == 1] = val[kind == 1] == grp_idx[y[kind == 1]]
    ok[kind == 2] = val[kind == 2] == lin_idx[y[kind == 2]]
    return {"bal_fine_strict": 100 * balanced_accuracy_score(y, pred_fine),
            "fine_rate": 100 * np.mean(kind == 0), "group_rate": 100 * np.mean(kind == 1),
            "lineage_rate": 100 * np.mean(kind == 2), "committed_rate": 100 * np.mean(committed),
            "abstain_rate": 100 * np.mean(~committed),
            "abstain_ood": 100 * np.mean(kind == 5), "abstain_empty": 100 * np.mean(kind == 3),
            "abstain_ambiguous": 100 * np.mean(kind == 4), "abstain_coverage": 100 * np.mean(kind == 6),
            "correct_when_committed": 100 * ok[committed].mean() if committed.any() else np.nan}


def label_space_metrics(keep, present):
    est = set(np.flatnonzero(keep).tolist()); tru = set(present)
    return {"ls_recall": 100 * len(est & tru) / max(len(tru), 1),
            "ls_precision": 100 * len(est & tru) / max(len(est), 1), "ls_size": len(est)}


# ------------------------------------------------------------ service replica
def replica_service(cos, maxcos, nobs, seed, min_obs=200, alpha=0.1, frac=0.2, min_cells=20, q_ood=0.05):
    """The service pipeline as it stands after b023799, Stages 4 to 6 without the
    Stage 7 pair fallback: softmax over raw cosine (temperature 1), conformal
    calibrated on a random 20% slice of the query against the model's own top
    label, and an out of distribution threshold at the 5th percentile of that
    same slice. Returns kind, val like resolve() (no group or lineage outputs)."""
    rng = np.random.default_rng(seed)
    P = softmax(cos, 1.0)
    n = len(P)
    n_cal = min(n, max(min_cells, int(np.ceil(frac * n))))
    cal = rng.choice(n, n_cal, replace=False)
    nc = 1.0 - P[cal].max(1)
    qhat = float(np.quantile(nc, conformal_level(n_cal, alpha), method="higher"))
    S = P >= 1.0 - qhat
    thr = float(np.quantile(maxcos[cal], q_ood))
    kind = np.full(n, 4); val = np.full(n, -1); size = S.sum(1)
    for i in range(n):
        if nobs[i] < min_obs: kind[i] = 6
        elif maxcos[i] < thr: kind[i] = 5
        elif size[i] == 0: kind[i] = 3
        elif size[i] == 1: kind[i], val[i] = 0, int(np.flatnonzero(S[i])[0])
    return kind, val, {"qhat": qhat, "mean_set_size": float(size.mean()), "top_prob_mean": float(P.max(1).mean())}


def auc(pos, neg):
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    return float(roc_auc_score(y, np.r_[pos, neg]))
