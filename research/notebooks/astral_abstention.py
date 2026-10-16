"""Goal 2: why v4.1 commits on only 27-41% of the Astral PBMC cells
(PXD070599 DS18 and DS19; research/notebook-run-history.md, entry 37). A
diagnosis on development data; label-free; it changes nothing.

The deposit's runs are frozen PBMCs sorted one per well (file names "_SC";
the empty-well controls are listed in the deposit's raw-file mapping but
searched into none of its matrices): DS18 is three run sets (Standard Astral,
FAIMS, and FAIMS 20-40 on a second instrument, "Astral-Zoom") of 88-91 cells;
DS19, 81 cells from a second plate on that instrument. Every search used
match-between-runs. For each, beside Fulcher 2026 and PBMC240, v4.1 as served:
1. why cells abstain: the four reasons' shares;
2. coverage: proteins observed per cell, and how many fall in the 9,002-gene
   input space;
3. the out-of-distribution score (mean max cosine to any reference cell)
   against its threshold;
4. what the answers and best guesses say: lineage shares of the committed
   answers and of the best guesses (PBMCs should be mostly lymphoid);
5. upload size: Fulcher's mixed upload subsampled to 90 cells, 20 seeds, as
   a control for the small Astral uploads (fewer than 100 cells draw the
   service's own warning);
6. depth: each Astral upload restricted to the proteins observed in at least
   half its cells, and to the proteins Fulcher 2026 measures, re-run;
7. match-between-runs: DIA-NN's first-pass precursor matrix beside the final
   one. The share of each cell's final values its first pass did not
   identify, and four uploads re-run: the served protein matrix, the final
   precursors rolled up to genes, the final precursors kept only where the
   first pass identified them, and the first-pass precursors;
8. lineage markers: the share of cells observing each of a few T, NK, B,
   monocyte, platelet and red-cell markers, and its median rank among the
   cell's own observed proteins;
9. a shared contaminant: the reference's 100 most platelet-specific and 100
   most erythrocyte-specific genes (class mean minus the largest other class
   mean, v4.1's class means) dropped from each upload, against ten drops of
   as many random input-space genes.

Needs the four searches' report.pg_matrix.tsv, report.pr_matrix.tsv and
report-first-pass.pr_matrix.tsv extracted from DS18_DIANN.tar.gz and
DS19_DIANN.tar.gz into data/incoming/public_sets/PXD070599_PBMC/extracted/DS18
and .../DS19 (each archive's own folder names).

Writes research/notebook-outputs/astral_abstention/summary.json.

    python research/notebooks/astral_abstention.py      # from the repository root
"""
from __future__ import annotations

import collections
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from benchmark import datasets  # noqa: E402
from service.pipeline import alignment, fusion, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "astral_abstention"
PUBLIC = REPO / "data" / "incoming" / "public_sets" / "PXD070599_PBMC" / "extracted"
RUNTIME = REPO / "service" / "model" / "runtime"
ASTRAL = {"DS18 Standard Astral": PUBLIC / "DS18" / "Standard_Astral_MBR",
          "DS18 FAIMS Astral": PUBLIC / "DS18" / "FAIMS_Astral_MBR",
          "DS18 FAIMS Astral-Zoom": PUBLIC / "DS18" / "FAIMS_Astral-Zoom_MBR",
          "DS19": PUBLIC / "DS19" / "MBR"}
PRECURSOR_COLUMNS = {"Protein.Group", "Protein.Ids", "Protein.Names", "Genes", "First.Protein.Description",
                     "Proteotypic", "Stripped.Sequence", "Modified.Sequence", "Precursor.Charge", "Precursor.Id"}
MARKERS = {"T": ["CD3E", "CD3D", "CD2", "LCK", "CD247", "ZAP70"], "NK": ["NKG7", "GNLY", "PRF1", "GZMB"],
           "B": ["CD79A", "CD79B", "MS4A1", "CD19"], "monocyte": ["LYZ", "S100A8", "S100A9", "CSTA", "MNDA", "CD14"],
           "platelet": ["PPBP", "PF4", "ITGA2B", "TUBB1"], "red cell": ["HBB", "HBA1", "CA1"]}
SIGNATURE_CLASSES, SIGNATURE_TOP = ("platelet", "erythrocyte"), 100


def describe(response: dict, raw: alignment.RawMatrix, lineage: dict, threshold: float) -> dict:
    cells = response["cells"]
    n = len(cells)
    reasons = collections.Counter(c.get("abstain_reason") or "committed" for c in cells)
    observed = np.isfinite(raw.values).sum(axis=0)
    sim = np.array([c.get("reference_similarity", np.nan) for c in cells], dtype=float)
    committed = [c for c in cells if not c["abstained"]]
    answer_lineage = collections.Counter(
        (lineage.get(c["label"]) if c["label_level"] == "class" else c["label"]) for c in committed)
    guess_lineage = collections.Counter(lineage.get(c.get("best_guess", {}).get("label"), "none") for c in cells)
    guess_class = collections.Counter(c.get("best_guess", {}).get("label") or "none" for c in cells)
    pct = lambda counter: {k: round(100 * v / max(1, sum(counter.values())), 1) for k, v in counter.most_common()}  # noqa: E731
    return {
        "cells": n, "features_matched": response["n_features_matched"],
        "features_unmatched": response["n_features_unmatched"],
        "proteins_per_cell_median": int(np.median(observed)),
        "observed_in_space_per_cell_median": int(np.median([c["observed_genes"] for c in cells])),
        "reasons_pct": pct(reasons),
        "reference_similarity": {"median": round(float(np.nanmedian(sim)), 4), "threshold": threshold,
                                 "below_threshold_pct": round(100 * float(np.nanmean(sim < threshold)), 1)},
        "committed_answers": pct(answer_lineage), "best_guess_lineage": pct(guess_lineage),
        "best_guess_classes": dict(list(pct(guess_class).items())[:6]),
    }


def subset(raw: alignment.RawMatrix, keep: np.ndarray) -> alignment.RawMatrix:
    return alignment.RawMatrix(gene_names=[g for g, k in zip(raw.gene_names, keep) if k], cell_ids=raw.cell_ids,
                               values=raw.values[keep])


def precursors(path: Path) -> tuple[pd.Series, np.ndarray, list[str]]:
    """Proteotypic precursors of a DIA-NN pr_matrix: first gene per precursor (indexed by Precursor.Id),
    log2 values (NaN unobserved), cell ids as the service cleans them."""
    table = pd.read_csv(path, sep="\t", low_memory=False)
    runs = [c for c in table.columns if c not in PRECURSOR_COLUMNS]
    table = table[(table["Proteotypic"] == 1) & table["Genes"].notna()].set_index("Precursor.Id")
    values = table[runs].to_numpy(dtype=float)
    return (table["Genes"].astype(str).str.split(";").str[0], np.where(values > 0, np.log2(values), np.nan),
            [alignment._clean_dia_nn_cell_id(c) for c in runs])


def roll_up(genes: pd.Series, log_values: np.ndarray, cell_ids: list[str]) -> alignment.RawMatrix:
    """One row per gene: each precursor centred on its own median, the per-cell median of those, plus the
    median of the precursors' medians; linear units, as a protein matrix arrives."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        offset = np.nanmedian(log_values, axis=1)
        names, rows = [], []
        for gene, idx in genes.groupby(genes.to_numpy()).indices.items():
            rows.append(np.nanmedian(offset[idx]) + np.nanmedian(log_values[idx] - offset[idx, None], axis=0))
            names.append(gene)
    return alignment.RawMatrix(gene_names=names, cell_ids=cell_ids, values=np.exp2(np.array(rows)))


def match_between_runs(bundle, path: Path, served: alignment.RawMatrix, lineage: dict, threshold: float) -> dict:
    genes, final, cells = precursors(path / "report.pr_matrix.tsv")
    fp_genes, first, fp_cells = precursors(path / "report-first-pass.pr_matrix.tsv")
    if cells != fp_cells:
        raise SystemExit(f"{path.name}: the two passes list different runs")
    first_aligned = pd.DataFrame(first, index=fp_genes.index).reindex(genes.index).to_numpy()
    identified = np.isfinite(first_aligned)
    observed = np.isfinite(final)
    transferred = (observed & ~identified).sum(axis=0) / np.maximum(observed.sum(axis=0), 1)
    both = observed & identified
    arms = {"served protein matrix": served,
            "final precursors, rolled up": roll_up(genes, final, cells),
            "final precursors, first-pass identifications only": roll_up(genes, np.where(identified, final, np.nan), cells),
            "first-pass precursors": roll_up(fp_genes, first, cells)}
    out = {"precursors_per_cell_median": {"final": int(np.median(observed.sum(axis=0))),
                                          "first_pass": int(np.median(np.isfinite(first).sum(axis=0)))},
           "final_values_not_identified_in_first_pass_pct": {
               "median": round(100 * float(np.median(transferred)), 1),
               "p10": round(100 * float(np.percentile(transferred, 10)), 1),
               "p90": round(100 * float(np.percentile(transferred, 90)), 1)},
           "both_passes_median_abs_log2_difference": round(float(np.median(np.abs(final[both] - first_aligned[both]))), 3)}
    for arm, raw in arms.items():
        d = describe(pipeline.run_projection(bundle, raw), raw, lineage, threshold)
        out[arm] = {"genes_per_cell_median": d["proteins_per_cell_median"], "committed_pct": d["reasons_pct"].get("committed", 0.0),
                    "reference_similarity_median": d["reference_similarity"]["median"],
                    "best_guess_lineage": d["best_guess_lineage"]}
    return out


def lineage_markers(raw: alignment.RawMatrix) -> dict:
    """Per marker: percent of cells observing it, and its median rank (0 lowest, 1 highest) among each
    observing cell's own observed proteins."""
    values, _ = alignment.detect_and_transform_value_scale(raw.values)
    rows: dict[str, int] = {}
    for i, name in enumerate(raw.gene_names):
        rows.setdefault(name.split(";")[0].upper(), i)
    n_obs = np.isfinite(values).sum(axis=0)
    order = np.argsort(np.argsort(np.where(np.isfinite(values), values, -np.inf), axis=0), axis=0)
    rank = np.where(np.isfinite(values), (order - (values.shape[0] - n_obs)) / np.maximum(n_obs - 1, 1), np.nan)
    out = {}
    for group, genes in MARKERS.items():
        out[group] = {g: {"cells_pct": round(100 * float(np.isfinite(values[rows[g]]).mean()), 1),
                          "median_rank": round(float(np.nanmedian(rank[rows[g]])), 2)}
                      for g in genes if g in rows and np.isfinite(values[rows[g]]).any()}
    return out


def signature_genes() -> set[str]:
    meta = pd.read_csv(RUNTIME / "reference_metadata.csv")
    names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    genes = pd.read_csv(RUNTIME / "feature_space_genes.csv")["gene"].str.upper().tolist()
    means = np.load(fusion.data_dir("v4.1") / "class_means_cb.npy")
    targets = [names.index(c) for c in SIGNATURE_CLASSES]
    others = [k for k in range(len(names)) if k not in targets]
    return {genes[g] for k in targets for g in np.argsort(-(means[k] - means[others].max(axis=0)))[:SIGNATURE_TOP]}


def drop_signature(bundle, raw: alignment.RawMatrix, signature: set[str], space: set[str]) -> dict:
    symbols = np.array([g.split(";")[0].upper() for g in raw.gene_names])
    drop = np.isin(symbols, list(signature))
    committed = lambda keep: round(100 * float(np.mean(  # noqa: E731
        [not c["abstained"] for c in pipeline.run_projection(bundle, subset(raw, keep))["cells"]])), 1)
    pool = np.flatnonzero(np.isin(symbols, list(space)) & ~drop)
    rng = np.random.default_rng(0)
    controls = []
    for _ in range(10):
        keep = np.ones(len(symbols), dtype=bool)
        keep[rng.choice(pool, int(drop.sum()), replace=False)] = False
        controls.append(committed(keep))
    return {"rows_dropped": int(drop.sum()), "committed_pct": committed(np.ones(len(symbols), dtype=bool)),
            "committed_pct_signature_dropped": committed(~drop),
            "committed_pct_random_drops": {"median": float(np.median(controls)), "min": min(controls), "max": max(controls)}}


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    bundle = pipeline.load_bundle("v4.1")
    threshold = float(bundle.answers.spec["ood"]["threshold"])
    meta = pd.read_csv(RUNTIME / "reference_metadata.csv")
    lineage = meta.groupby("class_name")["lineage"].first().to_dict()
    uploads = {"Fulcher 2026": datasets.load_fulcher2026_upload(),
               "PBMC240": alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text())}
    for name, path in ASTRAL.items():
        uploads[name] = alignment.parse_matrix_csv((path / "report.pg_matrix.tsv").read_text(encoding="utf-8"))
    summary = {name: describe(pipeline.run_projection(bundle, raw), raw, lineage, threshold) for name, raw in uploads.items()}

    full = uploads["Fulcher 2026"]
    shares = []
    for seed in range(20):
        keep = np.sort(np.random.default_rng(seed).choice(len(full.cell_ids), 90, replace=False))
        sub = alignment.RawMatrix(gene_names=full.gene_names, cell_ids=[full.cell_ids[i] for i in keep],
                                  values=full.values[:, keep])
        cells = pipeline.run_projection(bundle, sub)["cells"]
        shares.append(100 * float(np.mean([not c["abstained"] for c in cells])))
    summary["Fulcher 2026, 90-cell subsamples"] = {
        "seeds": 20, "committed_pct": {"median": round(float(np.median(shares)), 1),
                                       "min": round(min(shares), 1), "max": round(max(shares), 1)}}
    fulcher_genes = {g.split(";")[0].upper() for g in full.gene_names}
    for name in ASTRAL:
        raw = uploads[name]
        for variant, keep in (("observed in half its cells", np.isfinite(raw.values).mean(axis=1) >= 0.5),
                              ("Fulcher's proteins", np.array([g.split(";")[0].upper() in fulcher_genes for g in raw.gene_names]))):
            d = describe(pipeline.run_projection(bundle, subset(raw, keep)), subset(raw, keep), lineage, threshold)
            summary[f"{name}, {variant}"] = {k: d[k] for k in ("proteins_per_cell_median", "reasons_pct",
                                                               "reference_similarity", "best_guess_lineage")}
    summary["match-between-runs"] = {name: match_between_runs(bundle, path, uploads[name], lineage, threshold)
                                     for name, path in ASTRAL.items()}
    summary["lineage markers"] = {name: lineage_markers(raw) for name, raw in uploads.items()}
    signature = signature_genes()
    space = set(pd.read_csv(RUNTIME / "feature_space_genes.csv")["gene"].str.upper())
    summary["platelet and red-cell signature dropped"] = {
        "classes": list(SIGNATURE_CLASSES), "genes_per_class": SIGNATURE_TOP, "signature_genes": len(signature),
        **{name: drop_signature(bundle, raw, signature, space) for name, raw in uploads.items()}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    for name, d in summary.items():
        if "cells" in d:
            print(f"{name:24} n {d['cells']:5} proteins/cell {d['proteins_per_cell_median']:5} in-space {d['observed_in_space_per_cell_median']:5} "
                  f"| {d['reasons_pct']} | sim median {d['reference_similarity']['median']} below thr {d['reference_similarity']['below_threshold_pct']}%")
            print(f"{'':24} answers {d['committed_answers']} | guesses {d['best_guess_lineage']}")
        elif "proteins_per_cell_median" in d:
            print(f"{name:52} proteins/cell {d['proteins_per_cell_median']:5} committed {d['reasons_pct'].get('committed')} "
                  f"sim {d['reference_similarity']['median']} | guesses {d['best_guess_lineage']}")
        else:
            print(name, json.dumps(d, indent=1))


if __name__ == "__main__":
    main()
