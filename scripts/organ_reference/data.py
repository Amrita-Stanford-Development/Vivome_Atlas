"""Paths, organ files and the RNA atlas.

An organ file (scripts/organs/<organ>.json) names its inputs with a prefix:
"drive:" for the project Drive's Data folder (D:/Project/Vivome/drive/Data on
this PC), "repo:" for the repository. Every stage of the builder writes into
the organ's work folder on the Drive, outside the repository.
"""
from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[2]
DRIVE = REPO.parent / "drive" / "Data"
ORGANS = REPO / "scripts" / "organs"
WORK = DRIVE / "Results" / "Organs"
NB1 = DRIVE / "Results" / "Tier1_v31" / "NB1"  # blood's T1 NB1 outputs, the acceptance's reference


def resolve(name: str) -> Path:
    prefix, _, rest = name.partition(":")
    if prefix == "drive":
        return DRIVE / rest
    if prefix == "repo":
        return REPO / rest
    raise ValueError(f"{name}: a path starts with drive: or repo:")


def load_organ(organ: str) -> dict:
    cfg = json.loads((ORGANS / f"{organ}.json").read_text(encoding="utf-8"))
    if cfg["organ"] != organ:
        raise ValueError(f"scripts/organs/{organ}.json names organ {cfg['organ']!r}")
    return cfg


def work_dir(organ: str) -> Path:
    path = WORK / organ
    path.mkdir(parents=True, exist_ok=True)
    return path


def _strings(node) -> np.ndarray:
    """An h5ad obs or var column: categorical (codes and categories) or plain."""
    if isinstance(node, h5py.Group):
        return np.asarray(node["categories"][:]).astype(str)[np.asarray(node["codes"][:])]
    return np.asarray(node[:]).astype(str)


def read_obs(path: Path, columns: list[str]) -> pd.DataFrame:
    """The cells' ids and the named obs columns, in the h5ad's row order."""
    with h5py.File(path, "r") as f:
        obs = f["obs"]
        table = pd.DataFrame({"cell": _strings(obs[obs.attrs["_index"]])})
        for c in columns:
            table[c] = _strings(obs[c])
    return table


def rna_genes(path: Path) -> list[str]:
    """The atlas's gene symbols, upper case, in column order (the var index,
    as Build_Feature_Space and NB1 read it)."""
    with h5py.File(path, "r") as f:
        var = f["var"]
        return [g.upper() for g in _strings(var[var.attrs["_index"]])]


def load_rna(path: Path, genes: list[str]) -> np.ndarray:
    """(cells x genes) log-normalised RNA (the h5ad's X), in its row order,
    one column per requested gene (first column of a repeated symbol)."""
    with h5py.File(path, "r") as f:
        var = f["var"]
        sym = [g.upper() for g in _strings(var["gene_symbol"])]
        first: dict[str, int] = {}
        for j, g in enumerate(sym):
            first.setdefault(g, j)
        missing = [g for g in genes if g.upper() not in first]
        if missing:
            raise ValueError(f"{len(missing)} genes are not in {path.name}, e.g. {missing[:5]}")
        X = f["X"]
        M = sp.csr_matrix((X["data"][:], X["indices"][:], X["indptr"][:]), shape=tuple(X.attrs["shape"]))
    return M[:, np.array([first[g.upper()] for g in genes])].toarray().astype(np.float32)


def save_json(path: Path, obj) -> None:
    path.write_bytes((json.dumps(obj, indent=2) + "\n").encode("utf-8"))
