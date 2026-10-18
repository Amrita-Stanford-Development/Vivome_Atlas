"""Real missingness profiles for the simulated uploads (T1 NB1, section 3).

Each profile gives, over the gene space: the genes the dataset measures at
all (gene_set), how often each is detected across cells (det_prob), and the
distribution of each cell's observed fraction (cell_frac). They shape which
values a simulated upload keeps; no proteomics label is read.

Readers, by the profile's "read":
- cells_by_genes: cells in rows, gene symbols as columns (SCoPE2's gene-level file);
- diann_pg: a DIA-NN protein-group report, proteins in rows (PBMC240);
- fulcher: Fulcher 2026's abundance table, cells in columns starting 60708,
  cells with more than 200 values kept (NB1's filter);
- h5ad_cells: an h5ad of cells by gene symbols, 0 meaning not detected (the
  polyp plate); its gene set is the genes detected in any cell;
- rank_transfer: another organ's profile carried over by RNA abundance. Each
  gene here takes the gene_set and det_prob of the other organ's gene at the
  same quantile of mean RNA expression, so detection follows how abundant a
  gene is in this tissue rather than which genes blood cells express.
"""
from __future__ import annotations

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import data


def _explode(series: pd.Series) -> list[list[str]]:
    return series.astype(str).str.upper().str.split(";").tolist()


def profile_from_obs(obs: np.ndarray, gene_names: list[str], space: list[str]):
    """NB1's profile_from_obs: obs is (cells, columns) bool, one column per gene
    symbol (repeats allowed). Returns per-gene detection probability over the
    space (NaN where never measured) and each cell's observed fraction."""
    df = pd.DataFrame(obs, columns=gene_names)
    df = df.T.groupby(level=0).max().T  # a gene seen in any of its protein groups
    det = df.mean(0).reindex(space).values.astype(np.float32)
    frac = df.reindex(columns=[g for g in space if g in df.columns]).mean(1).values.astype(np.float32)
    return det, frac


def _columns_by_gene(genes: pd.Series) -> tuple[list[int], list[str]]:
    cols_i, cols_g = [], []
    for i, gs in enumerate(_explode(genes)):
        for g in gs:
            if g and g != "NAN":
                cols_i.append(i); cols_g.append(g)
    return cols_i, cols_g


def observed(profile: dict) -> tuple[np.ndarray, list[str]]:
    """(cells x columns observed, the columns' gene symbols)."""
    path = data.resolve(profile["path"])
    read = profile["read"]
    if read == "cells_by_genes":
        t = pd.read_csv(path, sep="\t", index_col=0)
        t.columns = t.columns.astype(str).str.upper()
        return t.apply(pd.to_numeric, errors="coerce").notna().values, list(t.columns)
    if read == "diann_pg":
        t = pd.read_csv(path, sep="\t")
        ann = [c for c in ["Protein.Group", "Protein.Names", "Genes", "First.Protein.Description",
                           "N.Sequences", "N.Proteotypic.Sequences"] if c in t.columns]
        vals = t[[c for c in t.columns if c not in ann]].apply(pd.to_numeric, errors="coerce")
        obs = (vals.notna() & (vals > 0)).values.T
        cols_i, cols_g = _columns_by_gene(t["Genes"].fillna(""))
        return obs[:, cols_i], cols_g
    if read == "fulcher":
        t = pd.read_csv(path, sep="\t", low_memory=False)
        t = t[t["Gene"].notna()]
        cc = [c for c in t.columns if c.startswith("60708") and not c.startswith(("RefInt", "RefDInt"))]
        vals = t[cc].apply(pd.to_numeric, errors="coerce")
        obs = vals.loc[:, vals.notna().sum(0) > 200].notna().values.T
        cols_i, cols_g = _columns_by_gene(t["Gene"])
        return obs[:, cols_i], cols_g
    if read == "h5ad_cells":
        with h5py.File(path, "r") as f:
            names = [g.upper() for g in data._strings(f["var"][f["var"].attrs["_index"]])]
            X = f["X"]
            M = (sp.csr_matrix((X["data"][:], X["indices"][:], X["indptr"][:]), shape=tuple(X.attrs["shape"])).toarray()
                 if isinstance(X, h5py.Group) else X[:])
        return np.isfinite(M) & (M > 0), names
    raise ValueError(f"{profile['name']}: unknown read {read!r}")


def finish(gene_set: np.ndarray, det: np.ndarray, frac: np.ndarray) -> dict:
    """NB1's last step: detection outside the set is NaN; a gene in the set the
    file never shows takes the set's median detection."""
    det = np.where(gene_set, det, np.nan).astype(np.float32)
    med = np.nanmedian(det) if np.isfinite(det).any() else 1.0
    det = np.where(gene_set & ~np.isfinite(det), med, det).astype(np.float32)
    return {"gene_set": gene_set.astype(bool), "det_prob": det, "cell_frac": frac.astype(np.float32)}


def rank_transfer(source: dict, source_mu: np.ndarray, target_mu: np.ndarray) -> dict:
    """source's profile carried to a gene space whose mean RNA is target_mu (module docstring)."""
    q_src = np.empty(len(source_mu)); q_src[np.argsort(-source_mu, kind="stable")] = np.linspace(0, 1, len(source_mu))
    q_tgt = np.empty(len(target_mu)); q_tgt[np.argsort(-target_mu, kind="stable")] = np.linspace(0, 1, len(target_mu))
    order = np.argsort(q_src)
    nearest = order[np.clip(np.searchsorted(q_src[order], q_tgt), 0, len(order) - 1)]
    gs = source["gene_set"][nearest]
    return finish(gs, np.where(gs, source["det_prob"][nearest], np.nan), source["cell_frac"])


def build(cfg: dict, space: list[str], members: dict, mu: np.ndarray, other) -> tuple[dict, list[dict]]:
    """(the npz arrays, a summary row per profile). members: gene_space.membership;
    mu: this organ's mean RNA per gene; other(organ) -> (its profiles npz, its mu)."""
    arrays, rows = {}, []
    index = {g: i for i, g in enumerate(space)}
    for p in cfg["mask_profiles"]:
        if p["read"] == "rank_transfer":
            prof_npz, src_mu = other(p["from_organ"])
            src = {k: prof_npz[f"{k}_{p['from_profile']}"] for k in ("gene_set", "det_prob", "cell_frac")}
            out = rank_transfer(src, src_mu, mu)
        else:
            obs, names = observed(p)
            det, frac = profile_from_obs(obs, names, space)
            if p["gene_set"] == "detected":
                gs = np.isfinite(det) & (det > 0)
            else:
                gs = np.zeros(len(space), bool)
                gs[[index[g] for g in members[p["gene_set"]]]] = True
            out = finish(gs, det, frac)
        for k, v in out.items():
            arrays[f"{k}_{p['name']}"] = v
        gm = out["gene_set"]
        rows.append({"profile": p["name"], "genes_in_set": int(gm.sum()), "coverage_pct": 100 * float(gm.mean()),
                     "median_gene_detection": float(np.nanmedian(out["det_prob"][gm])),
                     "median_cell_observed_frac": float(np.median(out["cell_frac"]))})
    return arrays, rows
