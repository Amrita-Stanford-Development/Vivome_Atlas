"""Turns each bank entry into a file the projection service's parser reads,
as a user would upload it: the native table when the service reads its
layout, else a plain matrix (identifiers in the first column, one column
per cell, missing values left empty).

    python -m valuescale.corpus.extract                 # from the repository root

Extracted files go to data/incoming/value-scale-bank/extracted/<entry id>/.
Each kind of extraction is one function below; none of them looks at a
value beyond moving it, so a table's numbers reach the diagnostics as its
source wrote them (float32 text keeps 9 significant digits).
"""
from __future__ import annotations

import fnmatch
import functools
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from valuescale.corpus import denylist
from valuescale.corpus.fetch import ROOT, load_bank, source_path

OUT = ROOT / "extracted"


def _write_matrix(path: Path, genes, cells, values: np.ndarray, corner: str = "gene") -> Path:
    """A plain genes x cells matrix: tab separated, NaN as an empty field."""
    path.parent.mkdir(parents=True, exist_ok=True)
    values = np.asarray(values, dtype=np.float64)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join([corner, *map(str, cells)]) + "\n")
        for gene, row in zip(genes, values):
            fh.write("\t".join([str(gene), *("" if np.isnan(v) else f"{v:.9g}" for v in row)]) + "\n")
    return path


def _member(entry: dict, archive: Path, out: Path) -> Path:
    """One file out of a zip, named exactly or by a single glob match."""
    with zipfile.ZipFile(archive) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        hits = [n for n in names if n == entry["member"] or fnmatch.fnmatch(n, entry["member"])]
        if len(hits) != 1:
            raise SystemExit(f"{entry['id']}: member {entry['member']!r} matches {len(hits)} files in "
                             f"{archive.name}: {hits[:10]}")
        target = out / Path(hits[0]).name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(hits[0]) as src, target.open("wb") as dst:
                while block := src.read(4 << 20):
                    dst.write(block)
        return target


def _xlsx(entry: dict, source: Path, out: Path) -> Path:
    """The first sheet, as benchmark/pxd064083_intake.read_table hands it to the parser."""
    df = next(iter(pd.read_excel(source, sheet_name=None).values()))
    df.columns = [str(c).strip() for c in df.columns]
    target = out / (source.stem + ".tsv")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(df.to_csv(sep="\t", index=False, lineterminator="\n"), encoding="utf-8", newline="\n")
    return target


def _pd_abundance(entry: dict, source: Path, out: Path) -> Path:
    """Proteome Discoverer's protein export: the gene (or accession) column and
    every 'Abundance: <file>: <sample>' column; rows without an identifier dropped."""
    sep = "\t" if source.suffix.lower() == ".txt" else ","
    df = pd.read_csv(source, sep=sep, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    gene, prefix = entry["extract"]["gene_column"], entry["extract"]["prefix"]
    cells = [c for c in df.columns if c.startswith(prefix)]
    if not cells:
        raise SystemExit(f"{entry['id']}: no column starts with {prefix!r}")
    keep = df[gene].str.strip() != ""
    values = df.loc[keep, cells].replace("", np.nan).astype(np.float64).to_numpy()
    names = [c[len(prefix):].strip() for c in cells]
    return _write_matrix(out / "matrix.tsv", df.loc[keep, gene].str.strip(), names, values)


def _cells_by_genes(entry: dict, source: Path, out: Path) -> Path:
    """A cells x genes table (cell ids as the index), turned to genes x cells."""
    df = pd.read_csv(source, sep="\t", index_col=0)
    return _write_matrix(out / "matrix.tsv", df.columns.astype(str), df.index.astype(str), df.to_numpy().T)


@functools.lru_cache(maxsize=1)
def _adata(path: str):
    import anndata as ad
    return ad.read_h5ad(path)


def _h5ad_layer(entry: dict, source: Path, out: Path) -> Path:
    adata = _adata(str(source))
    layer = entry["extract"]["layer"]
    values = np.asarray(adata.layers[layer], dtype=np.float32).T
    genes = adata.var[entry["extract"]["gene_column"]].astype(str).tolist()
    return _write_matrix(out / f"{layer}.tsv", genes, adata.obs_names.astype(str).tolist(), values)


def _long(entry: dict, source: Path, out: Path, row: str, column: str, value: str, label=None) -> Path:
    """A long table (one row per protein and sample) pivoted to a matrix: the
    first value per protein and sample."""
    df = pd.read_csv(source, sep="\t", comment="#", usecols=lambda c: c in {row, column, value, label})
    wide = df.groupby([row, column], sort=False)[value].first().unstack(column)
    names = wide.index.astype(str)
    if label is not None:
        names = df.groupby(row, sort=False)[label].first().reindex(wide.index).fillna("").astype(str)
    keep = np.asarray([bool(n) for n in names])
    return _write_matrix(out / f"{value}.tsv", np.asarray(names)[keep], wide.columns.astype(str),
                         wide.to_numpy(dtype=np.float64)[keep])


def extract(entry: dict) -> Path:
    """The upload-ready file for one entry (written once, then reused)."""
    denylist.check(entry["id"], entry["accession"])
    source = source_path(entry)
    out = OUT / entry["id"]
    kind = entry["extract"]["kind"]
    if "member" in entry:
        source = _member(entry, source, out)
    if kind == "native":
        return source
    done = out / ".done"
    if done.exists():
        return out / done.read_text(encoding="utf-8").strip()
    if kind == "xlsx":
        target = _xlsx(entry, source, out)
    elif kind == "pd_abundance":
        target = _pd_abundance(entry, source, out)
    elif kind == "cells_by_genes":
        target = _cells_by_genes(entry, source, out)
    elif kind == "h5ad_layer":
        target = _h5ad_layer(entry, source, out)
    elif kind == "diann_long":
        target = _long(entry, source, out, "Protein.Group", "Run", entry["extract"]["quantity"], label="Genes")
    elif kind == "long":
        x = entry["extract"]
        target = _long(entry, source, out, x["row"], x["column"], x["value"])
    elif kind == "scope2_processed":
        df = pd.read_csv(source, index_col=0)
        target = _write_matrix(out / "matrix.tsv", df.index.astype(str), df.columns.astype(str), df.to_numpy())
    else:
        raise SystemExit(f"{entry['id']}: unknown extraction {kind!r}")
    done.write_text(target.name, encoding="utf-8", newline="\n")
    return target


def main() -> int:
    for entry in load_bank()["entries"]:
        path = extract(entry)
        print(f"{entry['id']}: {path.relative_to(ROOT.parents[2]).as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
