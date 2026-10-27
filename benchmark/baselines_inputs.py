"""Track D extension: what every baseline receives, per dataset, after the
gene fairness fix (research/benchmark/results.md, "Baselines beyond scANVI").

Every tool gets the same inputs per dataset, the ones scANVI's headline arm
got there:
- the benchmark's 85,232-cell RNA reference (load.py) and the query, both
  restricted to the benchmark genes the query measures in at least one cell;
- each gene z-scored over its observed values, RNA and query separately;
- unobserved query entries set to 0 after scaling.

Query inputs:
- SCoPE2: the published gene-level matrix as provided (results/prot_X.npy).
  It is complete, so all 2,907 genes are measured.
- PBMC240: the processed file (results/pbmc_X_processed.npy), scANVI's best
  PBMC240 input; it measures 1,111 of the genes.
- Fulcher 2026: log2 of the TMT intensities
  (datasets.load_fulcher2026_benchmark_matrix("log2")); it measures 932.
- SCoPE2 (reprocessed; Track G, Phase 4, with the corrected runner only):
  log2 reporter ratios from its peptide evidence, each cell's median
  subtracted, missing values kept missing
  (datasets.load_scope2_reprocessed_benchmark_matrix).

Nothing here reads a query label.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import datasets

D = Path(__file__).resolve().parent / "results"
DATASETS = ("scope2", "pbmc240", "fulcher2026")
ADDED = ("scope2_reprocessed",)  # development data added in Track G, Phase 4; corrected runs only
SEALED = ("khoury2026",)  # built only at the final v3.1 evaluation (protocol-khoury2026.md)
SORTED = ("sorted_cd4cd8",)  # the sorted CD4/CD8 test: its intake's matrix (protocol-sorted-cd4cd8.md)
# The internal held-out test's protein sets and their rehearsals: each intake's
# matrix (benchmark/heldout_intake.py; protocol-heldout.md), and the sorted
# T-against-B set's (benchmark/pxd064083_intake.py; protocol-pxd064083.md)
HELDOUT = tuple(f"heldout_{s}{suffix}" for s in ("tian", "pxd021882", "pxd043355", "pxd073250", "pxd046211",
                                                 "pxd064083", "pxd064083_log2")
                for suffix in ("", "_rehearsal"))
QUERY_INPUT = {
    "scope2": "SCoPE2 published gene-level matrix, as provided (gene- and cell-centred by its authors, complete)",
    "pbmc240": "PBMC240 processed file: log2(x+1), per-cell median normalised, left-censored imputed, z-scored within its own panel",
    "fulcher2026": "Fulcher 2026: log2 of the TMT-Integrator intensities, missing values kept missing",
    "scope2_reprocessed": "SCoPE2 reprocessed from its peptide evidence (benchmark/scope2_reprocess.py): log2 "
                          "reporter ratios, each cell's median subtracted, missing values kept missing",
    "khoury2026": "Khoury 2026: the column-normalised matrix as provided (log2, ComBat-corrected by its authors), "
                  "missing values kept missing",
    "sorted_cd4cd8": "the sorted CD4/CD8 test: the authors' search output on the service's log scale, a gene's rows "
                     "merged by per-cell median, missing values kept missing (benchmark/sorted_cd4cd8_intake.py)",
    **{name: "an internal held-out set: the upload on the service's log scale, a gene's rows merged by per-cell "
             "median, missing values kept missing (benchmark/heldout_intake.py)" for name in HELDOUT},
}


@dataclass
class Inputs:
    dataset: str
    rna_z: np.ndarray  # (85,232, genes) float32
    query_z: np.ndarray  # (query cells, genes) float32
    rna_labels: np.ndarray  # reference class names
    query_ids: list[str]
    genes: list[str]
    record: dict  # what the tool received, for the gene-fairness table


def zscore_cols(x: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    return (x - x.mean(axis=0, keepdims=True)) / np.clip(x.std(axis=0, keepdims=True), eps, None)


def zscore_cols_observed(x: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Per gene, mean and SD over observed values only; unobserved entries are 0 after scaling."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        z = (x - np.nanmean(x, axis=0, keepdims=True)) / np.clip(np.nanstd(x, axis=0, keepdims=True), eps, None)
    return np.nan_to_num(z, nan=0.0)


def query_matrix(dataset: str) -> tuple[np.ndarray, list[str]]:
    """(cells x benchmark genes, NaN where unobserved) and cell ids."""
    if dataset == "scope2":
        return np.load(D / "prot_X.npy"), pd.read_csv(D / "prot_meta.csv")["orig_index"].astype(str).tolist()
    if dataset == "pbmc240":
        return np.load(D / "pbmc_X_processed.npy"), pd.read_csv(D / "pbmc_meta.csv")["cell_id"].astype(str).tolist()
    if dataset == "fulcher2026":
        x, ids, _ = datasets.load_fulcher2026_benchmark_matrix("log2")
        return x, list(ids)
    if dataset == "scope2_reprocessed":
        x, ids, _ = datasets.load_scope2_reprocessed_benchmark_matrix()
        return x, list(ids)
    if dataset == "khoury2026":
        x, ids, _ = datasets.load_khoury2026_benchmark_matrix()
        return x, list(ids)
    if dataset == "sorted_cd4cd8" or dataset in HELDOUT:  # written by their intakes; label-free
        saved = np.load(D / dataset / "query_benchmark.npz", allow_pickle=True)
        return saved["x"], [str(c) for c in saved["cell_ids"]]
    raise ValueError(f"unknown dataset {dataset!r}; expected one of {DATASETS + ADDED}")


def load(dataset: str) -> Inputs:
    genes = datasets.benchmark_gene_space()
    query_x, ids = query_matrix(dataset)
    measured = np.isfinite(query_x).any(axis=0)
    rna_x = np.load(D / "rna_X.npy")[:, measured]
    query_x = query_x[:, measured]
    record = {
        "dataset": dataset,
        "n_rna_cells": int(rna_x.shape[0]),
        "n_query_cells": int(query_x.shape[0]),
        "n_genes": int(measured.sum()),
        "gene_set": f"benchmark genes measured in at least one query cell ({int(measured.sum())} of {len(genes)})",
        "rna_input": "atlas RNA reference, log normalised (benchmark/load.py)",
        "query_input": QUERY_INPUT[dataset],
        "scaling": "each gene z-scored over its observed values, RNA and query separately",
        "missing_values": f"{100 * (~np.isfinite(query_x)).mean():.1f}% of query entries unobserved; set to 0 after scaling",
    }
    return Inputs(dataset=dataset, rna_z=zscore_cols(rna_x).astype(np.float32),
                  query_z=zscore_cols_observed(query_x).astype(np.float32),
                  rna_labels=pd.read_csv(D / "rna_meta.csv")["class_name"].to_numpy(),
                  query_ids=ids, genes=[g for g, m in zip(genes, measured) if m], record=record)


if __name__ == "__main__":
    for name in DATASETS:
        print(load(name).record)
