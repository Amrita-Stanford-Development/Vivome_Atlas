"""SCoPE2 reprocessed from its peptide-level evidence (research/todo.md,
Track G, Phase 1). The published matrix VivOME used so far
(service/model/source/app_export/blood_joint_cells_by_proteins_GENELEVEL.tsv)
is imputed, batch-corrected and centred per protein and per cell, so it
cannot test a real upload. This rebuilds a development dataset from the
evidence, keeping missing values missing.

Rules, fixed before any result was seen (2026-10-04):

- Inputs (data/incoming/SCoPE2_raw/, sha256 in benchmark/datasets.py): MassIVE
  MSV000084660 quant/ev_SCoPE2_runs.csv (MaxQuant evidence with DART-ID's
  dart_PEP) and metadata/annotation.csv (each run's channel design).
- Runs, as SCoPE2's own analysis keeps them (SCoPE2_analysis.R, Zenodo
  4339954): single-cell runs only (not col19-col24, carrier, Ref, Master, SQC
  or blank runs; not FP103, FP95 or FP96); at least 500 PSMs; described in the
  annotation.
- PSMs, as SCoPE2 filters them: 1% FDR on dart_PEP at PSM and protein level
  (its calc_fdr, over single-cell runs); no REV or CON hits; PIF above 0.8;
  mean of reporter channels 4-16 over channel 1 below 0.1.
- Quantification, SCoPE2's normalisation: each channel's reporter intensity
  over the reference channel (channel 2) on the same PSM; log2; several PSMs
  of one peptide (modified sequence and charge) in one run: their median.
- Cells: channels the annotation labels sc_m0 (macrophage) or sc_u
  (monocyte). Labels come from the experimental design, not the protein data.
- Per cell: its median log2 ratio over its peptides is subtracted.
- Peptides to proteins (leading razor protein) by median, proteins to the
  service's feature symbols (gene_ids.resolve_to_feature_symbols), several
  proteins of one symbol by median. Proteins without a feature symbol are
  dropped.
- No imputation, no batch correction, no per-protein centring.
- Cell QC, label-free: at least 200 observed feature genes (the service's
  floor).

These are not SCoPE2's published cells one for one: its cell ids cannot be
mapped back to runs and channels without its lost intermediate files, so
this is its own development dataset, "SCoPE2 (reprocessed)".

Writes data/incoming/SCoPE2_raw/derived/scope2_reprocessed.csv (genes x
cells, empty where unobserved; read by the service's parser) and
scope2_reprocessed_cells.csv (cell_id, label, run, channel, lcbatch).

    python -m benchmark.scope2_reprocess      # from the repository root
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from benchmark import datasets
from service.pipeline import gene_ids

RAW = datasets.REPO / "data" / "incoming" / "SCoPE2_raw"
DERIVED = RAW / "derived"
RI = [f"Reporter.intensity.{c}" for c in range(1, 17)]
LABEL = {"sc_m0": "macrophage", "sc_u": "monocyte"}
MIN_PSMS_SC, PIF_MIN, MRRI_MAX, FDR, MIN_GENES = 500, 0.8, 0.1, 0.01, 200


def calc_fdr(pep: np.ndarray) -> np.ndarray:
    """SCoPE2's calc_fdr: the running mean of the sorted PEPs, in input order."""
    pep = np.asarray(pep, float)
    order = np.argsort(pep, kind="stable")
    out = np.empty_like(pep)
    out[order] = np.cumsum(pep[order]) / np.arange(1, len(pep) + 1)
    return out


def single_cell_runs(runs: list[str]) -> list[str]:
    skip = ("col19", "col20", "col21", "col22", "col23", "col24", "arrier", "Ref", "Master", "SQC", "blank")
    return [r for r in runs if not any(s in r for s in skip) and not any(s in r for s in ("FP103", "FP95", "FP96"))]


def main() -> None:
    entry = datasets.SCOPE2_REPROCESSED
    inputs = ("evidence", "annotation", "batch")
    datasets._check_hashes({"files": {k: entry["files"][k] for k in inputs}, "sha256": {k: entry["sha256"][k] for k in inputs}})
    cols = ["Raw.file", "Modified.sequence", "Charge", "Leading.razor.protein", "dart_PEP", "PIF"] + RI
    ev = pd.read_csv(entry["files"]["evidence"], usecols=lambda c: c in cols, low_memory=False)[cols]
    design = pd.read_csv(entry["files"]["annotation"]).set_index("Set")
    batch = pd.read_csv(entry["files"]["batch"]).set_index("set")
    for c in RI + ["dart_PEP", "PIF"]:
        ev[c] = pd.to_numeric(ev[c], errors="coerce")

    sc = single_cell_runs(list(pd.unique(ev["Raw.file"])))
    ev = ev[ev["Raw.file"].isin(sc)]
    n = ev["Raw.file"].value_counts()
    ev = ev[ev["Raw.file"].isin(n[n >= MIN_PSMS_SC].index) & ev["Raw.file"].isin(design.index)].copy()
    lrp = ev["Leading.razor.protein"].astype(str)
    piped = lrp.str.contains("|", regex=False)
    ev.loc[piped, "Leading.razor.protein"] = lrp[piped].str.split("|").str[1]
    ev["fdr"] = calc_fdr(ev["dart_PEP"].to_numpy())
    prot = ev.groupby("Leading.razor.protein", sort=False)["dart_PEP"].min()
    prot_fdr = pd.Series(calc_fdr(prot.to_numpy()), index=prot.index)
    ev = ev[ev["Leading.razor.protein"].isin(prot_fdr[prot_fdr < FDR].index) & (ev["fdr"] < FDR)]
    lrp = ev["Leading.razor.protein"].astype(str)
    ev = ev[~lrp.str.contains("REV") & ~lrp.str.contains("CON")]
    ev = ev[ev["PIF"].notna() & (ev["PIF"] > PIF_MIN)]
    with np.errstate(divide="ignore", invalid="ignore"):
        mrri = np.nanmean(ev[RI[3:16]].to_numpy(float) / ev[[RI[0]]].to_numpy(float), axis=1)
    ev = ev[mrri < MRRI_MAX]
    print(f"{ev['Raw.file'].nunique()} single-cell runs, {len(ev)} PSMs after SCoPE2's filters")

    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = ev[RI].to_numpy(float) / ev[[RI[1]]].to_numpy(float)
        logr = np.log2(ratios)
    logr[~np.isfinite(logr)] = np.nan
    ev = ev[["Raw.file", "Modified.sequence", "Charge", "Leading.razor.protein"]].assign(
        peptide=ev["Modified.sequence"].astype(str) + ev["Charge"].astype(str))
    long = []
    for c in range(16):
        part = ev[["Raw.file", "peptide", "Leading.razor.protein"]].assign(channel=c + 1, value=logr[:, c])
        long.append(part[part["value"].notna()])
    long = pd.concat(long, ignore_index=True)
    long["design"] = [design.at[r, f"RI{c}"] for r, c in zip(long["Raw.file"], long["channel"])]
    long = long[long["design"].isin(LABEL)]
    long["cell_id"] = long["Raw.file"] + "_RI" + long["channel"].astype(str)
    pep = long.groupby(["cell_id", "peptide", "Leading.razor.protein"], sort=False)["value"].median().reset_index()
    pep["value"] -= pep.groupby("cell_id")["value"].transform("median")
    proteins = pep.groupby(["cell_id", "Leading.razor.protein"], sort=False)["value"].median().reset_index()
    accessions = sorted(proteins["Leading.razor.protein"].astype(str).unique())
    symbol = dict(zip(accessions, gene_ids.resolve_to_feature_symbols(accessions)))
    proteins["gene"] = proteins["Leading.razor.protein"].map(symbol)
    proteins = proteins[proteins["gene"].notna()]
    genes = proteins.groupby(["gene", "cell_id"], sort=False)["value"].median().unstack("cell_id")
    observed = genes.notna().sum(axis=0)
    genes = genes.loc[:, observed >= MIN_GENES]
    cells = pd.DataFrame({"cell_id": genes.columns})
    cells["run"] = cells["cell_id"].str.rsplit("_RI", n=1).str[0]
    cells["channel"] = cells["cell_id"].str.rsplit("_RI", n=1).str[1].astype(int)
    cells["label"] = [LABEL[design.at[r, f"RI{c}"]] for r, c in zip(cells["run"], cells["channel"])]
    cells["lcbatch"] = [batch.at[r, "lcbatch"] if r in batch.index else "" for r in cells["run"]]
    cells = cells.sort_values(["run", "channel"]).reset_index(drop=True)
    genes = genes[cells["cell_id"]].sort_index()

    DERIVED.mkdir(parents=True, exist_ok=True)
    genes.index.name = "Genes"
    genes.to_csv(DERIVED / "scope2_reprocessed.csv", lineterminator="\n", float_format="%.6g")
    cells[["cell_id", "label", "run", "channel", "lcbatch"]].to_csv(DERIVED / "scope2_reprocessed_cells.csv", index=False, lineterminator="\n")
    print(f"{genes.shape[1]} cells x {genes.shape[0]} feature genes; {cells['label'].value_counts().to_dict()}; "
          f"median observed genes per cell {int(genes.notna().sum(axis=0).median())}; {100 * genes.isna().mean().mean():.1f}% missing")


if __name__ == "__main__":
    main()
