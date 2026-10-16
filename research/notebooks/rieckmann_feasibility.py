"""Goal 2, Phase 2a feasibility: do protein class means from sorted cells
(Rieckmann 2017) tell single cells apart better than the reference's RNA class
means? A diagnosis on development data; it changes no model.

v4.1's best guess correlates each cell, over its observed genes, with the
reference's class-balanced RNA class means (service/pipeline/fusion.py,
masked_pearson). The marker audit (run history, entry 30) found that single
cells yield abundant proteins only, so any gain must come from patterns across
those. This compares the correlation term alone under three sets of means:
- RNA: v4.1's own class means (service/model/v4/class_means_cb.npy), 9,002 genes;
- RNA, shared genes: the same, over the genes Rieckmann also quantifies;
- protein: Rieckmann's steady-state populations mapped to the reference's
  classes, log2 LFQ averaged over donors, z-scored per protein with every
  class weighted equally; a protein a class never shows takes that protein's
  lowest class mean (left-censored), so absence counts as low.
Classes Rieckmann has no population for (macrophage, the progenitors, the
generic "monocyte", mature NK T) cannot be chosen under the protein means;
the two RNA variants are scored with the same classes removed, so all three
choose from one set.

Queries, as the service prepares them: values on the log scale, a gene's rows
merged by per-cell median, each gene z-scored over its observed values within
the upload, unobserved entries masked.

Scored (development data; research/benchmark/side-tests.md, amendment 1):
- Fulcher 2026: balanced accuracy over its six author types, predictions
  mapped by COARSE in benchmark/fulcher2026_score.py (in-sample for v4.1's weight,
  which this does not use);
- PBMC240: lymphoid recall over its weakly labelled lymphoid cells.

Decision, fixed before the run: build a Phase 2a candidate only if the protein
means beat both RNA variants by at least 3 points of Fulcher balanced
accuracy and lose no more than 2 points of PBMC240 lymphoid recall.

Writes research/notebook-outputs/rieckmann_feasibility/summary.json and
per_type.csv.

    python research/notebooks/rieckmann_feasibility.py      # from the repository root
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from benchmark import baselines_inputs, datasets  # noqa: E402
from benchmark import fulcher2026_score as fulcher  # noqa: E402
from service.pipeline import alignment, fusion  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "rieckmann_feasibility"
RIECKMANN = REPO / "data" / "incoming" / "public_sets" / "Rieckmann2017_PXD004352" / "extracted" / "proteinGroups.txt"
RUNTIME = REPO / "service" / "model" / "runtime"
POPULATIONS = {  # Rieckmann steady-state population -> reference class
    "T4.naive": "naive thymus-derived cd4-positive, alpha-beta t cell",
    "T4.CM": "cd4-positive, alpha-beta t cell", "T4.EM": "cd4-positive, alpha-beta t cell",
    "T4.EMRA": "cd4-positive, alpha-beta t cell", "Th1": "cd4-positive, alpha-beta t cell",
    "Th2": "cd4-positive, alpha-beta t cell", "Th17": "cd4-positive, alpha-beta t cell",
    "nTregs": "regulatory t cell", "mTregs": "regulatory t cell",
    "T8.naive": "cd8-positive, alpha-beta t cell", "T8.CM": "cd8-positive, alpha-beta t cell",
    "T8.EM": "cd8-positive, alpha-beta t cell", "T8.EMRA": "cd8-positive, alpha-beta t cell",
    "NK.dim": "natural killer cell", "NK.bright": "natural killer cell",
    "B.naive": "b cell", "B.memory": "b cell", "B.plasma": "plasma cell",
    "MO.classical": "classical monocyte", "MO.intermediate": "intermediate monocyte",
    "MO.nonclassical": "non-classical monocyte", "mDC": "myeloid dendritic cell", "pDC": "plasmacytoid dendritic cell",
    "Neutrophil": "neutrophil", "Basophil": "basophil", "Erythrocyte": "erythrocyte", "Thrombocyte": "platelet",
}
MIN_GAIN_FULCHER, MAX_LOSS_PBMC = 3.0, 2.0


def first_symbol(name) -> str:
    return str(name).split(";")[0].strip().upper()


def protein_means(class_names: list[str]) -> tuple[np.ndarray, list[str], np.ndarray]:
    """(classes x proteins) z-scored class means, the protein symbols, and which
    classes have a population."""
    header = [c.strip('"') for c in RIECKMANN.open(encoding="utf-8").readline().rstrip("\n").split("\t")]
    cols = {}
    for c in header:
        m = re.match(r"LFQ\.intensity\.(.+)_(\d\d) \(steady-state\)$", c)
        if m and m.group(1) in POPULATIONS:
            cols[c] = POPULATIONS[m.group(1)]
    table = pd.read_csv(RIECKMANN, sep="\t", usecols=["Gene.names"] + list(cols), dtype={"Gene.names": str})
    table["symbol"] = table["Gene.names"].fillna("").map(first_symbol)
    table = table[table["symbol"] != ""].groupby("symbol").max(numeric_only=True)
    logged = np.log2(table.where(table > 0))
    by_class = {}
    for cls in sorted(set(cols.values())):
        by_class[cls] = logged[[c for c, k in cols.items() if k == cls]].mean(axis=1)  # over donors and populations
    means = pd.DataFrame(by_class)
    means = means[means.notna().any(axis=1)]
    floor = means.min(axis=1)
    means = means.apply(lambda col: col.fillna(floor))  # never shown in a class: that protein's lowest class mean
    z = means.sub(means.mean(axis=1), axis=0).div(means.std(axis=1, ddof=0) + 1e-8, axis=0)  # classes weighted equally
    covered = np.array([c in z.columns for c in class_names])
    full = np.zeros((len(class_names), len(z)), np.float32)
    for k, c in enumerate(class_names):
        if c in z.columns:
            full[k] = z[c].to_numpy(np.float32)
    return full, z.index.tolist(), covered


def query(raw: alignment.RawMatrix, genes: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Values and mask over `genes`, as the service prepares a query."""
    values, _ = alignment.detect_and_transform_value_scale(raw.values)
    symbols = [first_symbol(g) for g in raw.gene_names]
    index = {g: i for i, g in enumerate(genes)}
    x = np.full((len(raw.cell_ids), len(genes)), np.nan, np.float64)
    rows: dict[int, list[int]] = {}
    for r, s in enumerate(symbols):
        if s in index:
            rows.setdefault(index[s], []).append(r)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for col, rs in rows.items():
            x[:, col] = np.nanmedian(values[rs], axis=0) if len(rs) > 1 else values[rs[0]]
        z = (x - np.nanmean(x, axis=0)) / (np.nanstd(x, axis=0) + 1e-8)
    mask = np.isfinite(z)
    return np.where(mask, z, 0.0), mask.astype(np.float32)


def predict(values, mask, means, allowed, class_names) -> np.ndarray:
    r = fusion.masked_pearson(values, mask, means)
    r[:, ~allowed] = -np.inf
    return np.array(class_names)[r.argmax(axis=1)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(RUNTIME / "reference_metadata.csv")
    class_names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    feature_genes = pd.read_csv(RUNTIME / "feature_space_genes.csv")["gene"].str.upper().tolist()
    rna_means = np.load(REPO / "service" / "model" / "v4" / "class_means_cb.npy").astype(np.float32)
    prot_means, prot_genes, covered = protein_means(class_names)
    shared = [g for g in feature_genes if g in set(prot_genes)]
    shared_idx = [feature_genes.index(g) for g in shared]

    uploads = {"Fulcher 2026": datasets.load_fulcher2026_upload(),
               "PBMC240": alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text())}
    lineage = meta.groupby("class_name")["lineage"].first().to_dict()
    results, per_type = {}, []
    for name, raw in uploads.items():
        arms = {}
        v, m = query(raw, feature_genes)
        arms["RNA"] = predict(v, m, rna_means, covered, class_names)
        vs, ms = query(raw, shared)
        arms["RNA, shared genes"] = predict(vs, ms, rna_means[:, shared_idx], covered, class_names)
        vp, mp = query(raw, prot_genes)
        arms["protein"] = predict(vp, mp, prot_means, covered, class_names)
        observed = {"RNA": int(np.median(m.sum(1))), "RNA, shared genes": int(np.median(ms.sum(1))),
                    "protein": int(np.median(mp.sum(1)))}
        if name == "Fulcher 2026":
            labels = datasets.load_fulcher2026_labels().set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
            scored = np.isin(labels, fulcher.TYPES)
            out = {}
            for arm, pred in arms.items():
                pt = np.array([fulcher.COARSE.get(c, "other") for c in pred[scored]])
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    out[arm] = round(100 * balanced_accuracy_score(labels[scored], pt), 2)
                for t in fulcher.TYPES:
                    per_type.append({"dataset": name, "arm": arm, "type": t,
                                     "recall_pct": round(100 * float((pt[labels[scored] == t] == t).mean()), 2)})
            results[name] = {"metric": "balanced accuracy, six types", "scores": out, "median_genes_observed": observed}
        else:
            pbmc = pd.read_csv(baselines_inputs.D / "pbmc_meta.csv", dtype={"cell_id": str}).set_index("cell_id")
            truth = pbmc.reindex(raw.cell_ids)["weak_lineage"].to_numpy()
            lymph = truth == "lymphoid"
            out = {arm: round(100 * float(np.mean([lineage.get(c) == "lymphoid" for c in pred[lymph]])), 2)
                   for arm, pred in arms.items()}
            results[name] = {"metric": "lymphoid recall", "n": int(lymph.sum()), "scores": out,
                             "median_genes_observed": observed}
    f, p = results["Fulcher 2026"]["scores"], results["PBMC240"]["scores"]
    go = (f["protein"] >= max(f["RNA"], f["RNA, shared genes"]) + MIN_GAIN_FULCHER
          and p["protein"] >= p["RNA"] - MAX_LOSS_PBMC)
    summary = {"classes_with_a_population": [c for c, ok in zip(class_names, covered) if ok],
               "proteins": len(prot_genes), "shared_with_feature_space": len(shared), "results": results,
               "decision": {"rule": f"protein beats both RNA variants by >= {MIN_GAIN_FULCHER} points on Fulcher and "
                                    f"loses <= {MAX_LOSS_PBMC} on PBMC240", "build_candidate": bool(go)}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    pd.DataFrame(per_type).to_csv(OUT / "per_type.csv", index=False, lineterminator="\n")
    print(json.dumps(summary["results"], indent=2), "\nbuild candidate:", go)


if __name__ == "__main__":
    main()
