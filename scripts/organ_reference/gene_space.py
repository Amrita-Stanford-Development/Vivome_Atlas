"""The gene space: every gene symbol a proteomics source detected, minus
immunoglobulin and T-cell receptor segments, that the RNA atlas measures,
sorted (Build_Feature_Space's rule; service/model/evidence/
feature_space_provenance.json records blood's counts).

A source is read one of three ways: a column of gene symbols (split on ";";
"member" names the table inside a zip archive; "detected" keeps, from a long
table listing every gene, only those with a positive value in rows of the
named samples), a header of gene symbols (cells in rows), or an h5ad's var
names.
"""
from __future__ import annotations

import zipfile

import h5py
import pandas as pd

from . import data

IG_PREFIX = ("IGKV", "IGLV", "IGHV", "IGKJ", "IGLJ", "IGHJ",
             "TRAV", "TRBV", "TRGV", "TRDV", "TRAJ", "TRBJ")


def split_symbols(values) -> set[str]:
    out = set()
    for v in pd.Series(values).dropna().astype(str):
        for s in v.split(";"):
            s = s.strip().upper()
            if s and s not in ("NAN", "NONE", "-"):
                out.add(s)
    return out


def source_symbols(source: dict) -> set[str]:
    path = data.resolve(source["path"])
    if source["read"] == "column":
        handle = zipfile.ZipFile(path).open(source["member"]) if "member" in source else path  # a table inside a zip
        det = source.get("detected")  # a long table: keep genes with a positive value in the listed samples' rows
        cols = [source["column"]] + ([det["value"], det["column"]] if det else [])
        t = pd.read_csv(handle, sep="\t", low_memory=False, usecols=cols)
        if det:
            t = t[(t[det["value"]] > 0) & t[det["column"]].isin(det["keep"])]
        return split_symbols(t[source["column"]])
    if source["read"] == "header":
        return split_symbols(pd.read_csv(path, sep="\t", nrows=0, index_col=0).columns.astype(str))
    if source["read"] == "h5ad_var":
        with h5py.File(path, "r") as f:
            return split_symbols(data._strings(f["var"][f["var"].attrs["_index"]]))
    raise ValueError(f"{source['name']}: unknown read {source['read']!r}")


def build(cfg: dict) -> tuple[list[str], dict]:
    """(the sorted gene space, a record of each source's count)."""
    by_name: dict[str, set[str]] = {}
    for source in cfg["gene_space"]["sources"]:
        by_name.setdefault(source["name"], set()).update(source_symbols(source))
    union_raw = set().union(*by_name.values())
    union = {s for s in union_raw if not s.startswith(IG_PREFIX)}
    rna = set(data.rna_genes(data.resolve(cfg["rna"])))
    space = sorted(union & rna)
    record = {"sources": {k: len(v) for k, v in by_name.items()}, "union_raw": len(union_raw),
              "union_no_ig": len(union), "ig_tcr_excluded": len(union_raw) - len(union),
              "rna_genes": len(rna), "feature_space": len(space),
              "per_source_in_space": {k: len(v & set(space)) for k, v in by_name.items()}}
    return space, record


def membership(cfg: dict, space: list[str]) -> dict[str, set[str]]:
    """Each named source's genes inside the space (feature_space_detail.csv's columns)."""
    keep = set(space)
    out: dict[str, set[str]] = {}
    for source in cfg["gene_space"]["sources"]:
        out.setdefault(source["name"], set()).update(
            {s for s in source_symbols(source) if not s.startswith(IG_PREFIX)} & keep)
    return out
