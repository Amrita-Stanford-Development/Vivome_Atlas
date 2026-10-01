"""The "notebook convention" query parse: how T1 NB2 (Section 9) read its
development datasets, kept here so its numbers can be reproduced through the
served v3.1 pipeline. It is a benchmark parser, not the product's: the
service parses uploads with service/pipeline/alignment.py (HGNC identifier
resolution), and the two differ on PBMC240 (research/benchmark/results.md).

PBMC240 raw DIA-NN, exactly as NB2 read it:
  a. read the TSV; annotation columns are whichever of ANNOTATION_COLUMNS are
     present; every other column is a cell;
  b. cell id: the column name with "\\\\" replaced by "\\", the last part after
     "\\", ".raw" removed;
  c. values to numeric; anything <= 0 or missing is NaN; then log2;
  d. gene: Genes split on ";", first entry, as string, upper-cased; genes
     "NAN" and "" dropped;
  e. duplicate genes: per cell median across duplicates, skipping NaN;
  f. every cell kept; the 200-gene floor applies only at output
     (abstain coverage_too_low), not before z-scoring;
  g. aligned matrix: feature-space genes present (by name) get their values,
     the others NaN;
  h. smoothing graph input: ALL collapsed genes, z-scored per gene with
     nanmean and nanstd (ddof 0, sd clipped at 1e-8), NaN -> 0;
  i. then the service path: per-upload gene z over observed values, NaN -> 0,
     a per-cell mask, smoothing with that graph.
SCoPE2's published matrix goes through d to i the same way (its values are
already log scale and complete).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from service import config
from service.pipeline import alignment, smoothing

ANNOTATION_COLUMNS = ("Protein.Group", "Protein.Names", "Genes", "First.Protein.Description",
                      "N.Sequences", "N.Proteotypic.Sequences")


def read_dia_nn(path) -> pd.DataFrame:
    """Steps a to c: cells x proteins, log2, NaN for not observed; columns
    are still the raw Genes entries."""
    report = pd.read_csv(path, sep="\t")
    annotation = [c for c in ANNOTATION_COLUMNS if c in report.columns]
    cells = [c for c in report.columns if c not in annotation]
    ids = [c.replace("\\\\", "\\").split("\\")[-1].replace(".raw", "") for c in cells]
    values = report[cells].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
    values[~(values > 0)] = np.nan
    with np.errstate(divide="ignore", invalid="ignore"):
        logged = np.log2(values)
    out = pd.DataFrame(logged.T, index=ids)
    out.columns = report["Genes"].astype(str).str.split(";").str[0].to_numpy()
    return out


def collapse_genes(cells_by_genes: pd.DataFrame) -> pd.DataFrame:
    """Steps d and e: upper-case gene names, drop "NAN" and "", and take the
    per-cell median (NaN skipped) across duplicate genes."""
    df = cells_by_genes.copy()
    df.columns = df.columns.astype(str).str.upper()
    df = df.loc[:, (df.columns != "NAN") & (df.columns != "")]
    if df.columns.duplicated().any():
        df = df.T.groupby(level=0).median().T
    return df


def prepare(cells_by_genes: pd.DataFrame, feature_genes: list[str]):
    """Steps f to i on a collapsed cells x genes frame. Returns
    (smoothed_values, AlignedQuery), ready for ensemble.project_prepared."""
    df = collapse_genes(cells_by_genes)
    index = {g: i for i, g in enumerate(feature_genes)}
    present = [g for g in feature_genes if g in set(df.columns)]

    raw = np.full((len(df), len(feature_genes)), np.nan, dtype=np.float32)
    raw[:, [index[g] for g in present]] = df[present].to_numpy(dtype=np.float32)

    # h: the graph's input, every collapsed gene.
    full = df.to_numpy(dtype=np.float64)
    with np.errstate(all="ignore"):
        graph = np.nan_to_num((full - np.nanmean(full, 0)) / np.clip(np.nanstd(full, 0), 1e-8, None), nan=0.0)

    # i: the service's per-upload gene z over observed values, NaN -> 0, and a mask.
    observed = ~np.isnan(raw)
    values = alignment.zscore_per_gene(raw.T.astype(np.float64)).T.astype(np.float32)
    mask = np.where(observed, config.MASK_OBSERVED, config.MASK_MISSING).astype(np.float32)
    aligned = alignment.AlignedQuery(
        values=values, mask=mask, cell_ids=[str(i) for i in df.index],
        n_features_matched=len(present), n_features_unmatched=df.shape[1] - len(present),
    )
    smoothed = smoothing.fuzzy_smooth(values, graph.astype(np.float32))
    return smoothed, aligned
