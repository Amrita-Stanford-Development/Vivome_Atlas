"""Goal 2, Phase 1.1: the marker audit. A diagnosis; it changes no model.

Why: the model's 9,002-gene input space is the union of proteins six early
proteomics datasets detected, and it lacks most canonical markers (CD8B, CCR7,
SELL; GNLY, NKG7, KLRD1, KLRF1; CD79A; CD1C, CLEC4C, LILRA4, IL3RA, CLEC9A,
FCER1A; CD68, CD163). Adding a marker to the best guess's correlation term
(plan, Phase 2a) only helps if real single-cell proteomics measures it and it
separates the populations the model confuses.

Data: development data only (research/benchmark/side-tests.md, amendment 1):
Fulcher 2026 (TMT, with the authors' six types), PBMC240, PXD070599 DS18 (three
searches of one run set) and DS19 (Olsen lab, Astral), Furtwängler 2025
(CD34+ progenitors), Rieckmann 2017 (sorted bulk populations, steady state),
and the reference RNA (Tabula Sapiens blood) under v5.2's labels. No Khoury, no
held-out set.

Parts, every rule fixed here before the run:
A. Detection: per dataset, whether each marker's protein is measured and the
   share of cells with a value. Gene symbols are each row's first listed
   gene, upper case. A dataset counts once per lab (DS18's three searches
   are one lab with DS19).
B. Fulcher by type: the share of each author type's cells with a value.
C. Rieckmann: per donor (_01 to _04), log2 LFQ intensity; for each confused
   pair, the donors whose log2 fold change is at least 1 in the expected
   direction, a missing value counting as not shown.
D. Reference RNA: AUROC of each marker's log-normalised expression for the
   pair, under v5.2's labels (class sizes reported).

A marker "qualifies" for Phase 2a's panel when all three hold:
1. measured with a value in at least 30% of cells in datasets from at least
   two labs (Part A), or, for a marker of a rare population, in at least 30%
   of Fulcher's cells of that type (Part B) and measured in a second lab;
2. Rieckmann shows the expected two-fold difference in at least 3 of 4 donors
   (Part C);
3. reference AUROC at least 0.75 for the pair (Part D).
Phase 1.1's last step, the probe on RNA calibration cells, runs only on the
markers that qualify, in a later script.

Writes research/notebook-outputs/marker_audit/audit.json and
detection.csv, fulcher_by_type.csv, rieckmann_pairs.csv, reference_auroc.csv.

    python research/notebooks/marker_audit.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from benchmark import datasets  # noqa: E402
from service.pipeline import alignment  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "marker_audit"
PUBLIC = REPO / "data" / "incoming" / "public_sets"
H5 = REPO.parent / "drive" / "Data" / "scRNA-seq" / "Blood_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad"
LABELS = REPO / "research" / "notebook-outputs" / "v52_labels" / "reference_labels_v52.csv.gz"
FEATURES = REPO / "service" / "model" / "runtime" / "feature_space_genes.csv"

# The confused pairs: (name, Rieckmann populations high, low, reference classes high, low, markers)
PAIRS = [
    ("CD8 T vs CD4 T", ["T8.naive", "T8.CM", "T8.EM", "T8.EMRA"], ["T4.naive", "T4.CM", "T4.EM", "T4.EMRA"],
     ["cd8-positive, alpha-beta t cell"],
     ["cd4-positive, alpha-beta t cell", "naive thymus-derived cd4-positive, alpha-beta t cell", "regulatory t cell"],
     ["CD8A", "CD8B", "CD4", "CD40LG", "GZMK", "GZMH", "CCL5", "KLRG1"]),
    ("naive vs memory T", ["T4.naive", "T8.naive"], ["T4.EM", "T8.EM", "T4.EMRA", "T8.EMRA"],
     ["naive thymus-derived cd4-positive, alpha-beta t cell"], ["cd4-positive, alpha-beta t cell"],
     ["CCR7", "SELL", "LEF1", "TCF7", "S100A4", "ANXA1", "IL7R", "CD27", "CD28"]),
    ("NK vs CD8 T", ["NK.dim", "NK.bright"], ["T8.EM", "T8.EMRA", "T8.CM"],
     ["natural killer cell"], ["cd8-positive, alpha-beta t cell"],
     ["GNLY", "NKG7", "KLRD1", "KLRF1", "NCAM1", "FCGR3A", "PRF1", "GZMB", "CD3D", "CD3E", "CD247"]),
    ("myeloid DC vs monocyte", ["mDC"], ["MO.classical", "MO.intermediate"],
     ["myeloid dendritic cell"], ["classical monocyte", "monocyte", "intermediate monocyte"],
     ["CD1C", "CLEC10A", "FCER1A", "CLEC9A", "IRF8", "HLA-DQA1", "CD74", "CD14", "LYZ", "S100A8", "FCN1"]),
    ("plasmacytoid DC vs others", ["pDC"], ["mDC", "MO.classical", "B.naive"],
     ["plasmacytoid dendritic cell"], ["classical monocyte", "monocyte", "b cell"],
     ["LILRA4", "CLEC4C", "IL3RA", "TCF4", "PLD4", "IRF7", "IRF8"]),
    ("B vs T", ["B.naive", "B.memory"], ["T4.naive", "T8.naive"],
     ["b cell"], ["cd4-positive, alpha-beta t cell", "cd8-positive, alpha-beta t cell"],
     ["CD79A", "CD79B", "MS4A1", "CD19", "PAX5", "CD22", "BLK"]),
    ("macrophage vs monocyte", [], [],
     ["macrophage"], ["classical monocyte", "monocyte"],
     ["CD68", "CD163", "MRC1", "APOE", "C1QA", "MARCO", "CD14", "VCAN", "FCN1"]),
]
MARKERS = sorted({m for p in PAIRS for m in p[5]})
LAB_OF = {"Fulcher 2026": "Fulcher", "PBMC240": "PBMC240", "DS18 FAIMS Astral-Zoom": "Olsen", "DS18 FAIMS Astral": "Olsen",
          "DS18 Standard Astral": "Olsen", "DS19": "Olsen", "Furtwangler 2025": "Furtwangler"}
MIN_DETECTED, MIN_DONORS, MIN_AUROC = 30.0, 3, 0.75


def first_symbol(name: str) -> str:
    return str(name).split(";")[0].strip().upper()


def detection(raw: alignment.RawMatrix) -> dict:
    """marker -> share of cells (percent) with a value; None if not measured."""
    symbols = [first_symbol(g) for g in raw.gene_names]
    out = {}
    for m in MARKERS:
        rows = [i for i, s in enumerate(symbols) if s == m]
        out[m] = None if not rows else round(100 * float(np.isfinite(raw.values[rows]).any(axis=0).mean()), 1)
    return out


def proteomics() -> dict:
    sets = {"Fulcher 2026": datasets.load_fulcher2026_upload(),
            "PBMC240": alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()),
            "Furtwangler 2025": datasets.load_furtwangler2025_upload()}
    ext = PUBLIC / "PXD070599_PBMC" / "extracted"
    for name, path in (("DS18 FAIMS Astral-Zoom", ext / "DS18" / "FAIMS_Astral-Zoom_MBR"),
                       ("DS18 FAIMS Astral", ext / "DS18" / "FAIMS_Astral_MBR"),
                       ("DS18 Standard Astral", ext / "DS18" / "Standard_Astral_MBR"), ("DS19", ext / "DS19" / "MBR")):
        sets[name] = alignment.parse_matrix_csv((path / "report.pg_matrix.tsv").read_text(encoding="utf-8"))
    return sets


def fulcher_by_type(raw: alignment.RawMatrix) -> pd.DataFrame:
    labels = datasets.load_fulcher2026_labels().set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
    symbols = [first_symbol(g) for g in raw.gene_names]
    rows = []
    for m in MARKERS:
        idx = [i for i, s in enumerate(symbols) if s == m]
        for t in ("CD4T", "CD8T", "NK", "B", "monocyte", "DC"):
            cells = labels == t
            share = None if not idx else round(100 * float(np.isfinite(raw.values[idx][:, cells]).any(axis=0).mean()), 1)
            rows.append({"marker": m, "type": t, "n_cells": int(cells.sum()), "detected_pct": share})
    return pd.DataFrame(rows)


def rieckmann() -> pd.DataFrame:
    path = PUBLIC / "Rieckmann2017_PXD004352" / "extracted" / "proteinGroups.txt"
    header = [c.strip('"') for c in path.open(encoding="utf-8").readline().rstrip("\n").split("\t")]
    lfq = {c: re.match(r"LFQ\.intensity\.(.+)_(\d\d) \(steady-state\)$", c) for c in header}
    lfq = {c: (m.group(1), m.group(2)) for c, m in lfq.items() if m}
    table = pd.read_csv(path, sep="\t", usecols=["Gene.names"] + list(lfq), dtype={"Gene.names": str})
    table["symbol"] = table["Gene.names"].fillna("").map(first_symbol)
    table = table[table["symbol"].isin(MARKERS)].groupby("symbol").max(numeric_only=True)  # one row per marker
    rows = []
    for name, high, low, _, _, markers in PAIRS:
        if not high:
            continue
        for m in markers:
            ok_donors, fcs = 0, []
            for donor in ("01", "02", "03", "04"):
                def mean_log(pops):
                    vals = [table.at[m, c] for c, (p, d) in lfq.items() if p in pops and d == donor and m in table.index]
                    vals = [np.log2(v) for v in vals if v and v > 0]
                    return np.mean(vals) if vals else np.nan
                fc = mean_log(high) - mean_log(low)
                fcs.append(None if np.isnan(fc) else round(float(fc), 2))
                ok_donors += bool(np.isfinite(fc) and fc >= 1)
            rows.append({"pair": name, "marker": m, "measured": m in table.index,
                         "log2fc_by_donor": json.dumps(fcs), "donors_2fold": ok_donors})
    return pd.DataFrame(rows)


def obs_column(f, key):
    v = f["obs"][key]
    return v["categories"][:].astype(str)[v["codes"][:]] if isinstance(v, h5py.Group) else v[:].astype(str)


def reference_auroc() -> pd.DataFrame:
    labels = pd.read_csv(LABELS)
    with h5py.File(H5, "r") as f:
        sym = f["var"]["gene_symbol"]
        sym = sym["categories"][:].astype(str)[sym["codes"][:]] if isinstance(sym, h5py.Group) else sym[:].astype(str)
        cells = f["obs"][f["obs"].attrs["_index"]][:].astype(str)
        X = sp.csr_matrix((f["X"]["data"][:], f["X"]["indices"][:], f["X"]["indptr"][:]), shape=tuple(f["X"].attrs["shape"]))
    if list(cells) != labels["cell"].tolist():
        raise SystemExit("the h5ad's cells are not the label table's")
    first = {}
    for i, s in enumerate(sym):
        first.setdefault(s.upper(), i)
    cls = labels["class_clean"].to_numpy()
    rows = []
    for name, _, _, hi, lo, markers in PAIRS:
        a, b = np.isin(cls, hi), np.isin(cls, lo)
        for m in markers:
            if m not in first:
                rows.append({"pair": name, "marker": m, "in_reference": False})
                continue
            e = X[:, first[m]].toarray().ravel()
            y = np.r_[np.ones(a.sum()), np.zeros(b.sum())]
            w = np.r_[np.full(a.sum(), 0.5 / a.sum()), np.full(b.sum(), 0.5 / b.sum())] if a.sum() and b.sum() else None
            auc = roc_auc_score(y, np.r_[e[a], e[b]], sample_weight=w) if w is not None else np.nan
            rows.append({"pair": name, "marker": m, "in_reference": True, "n_high": int(a.sum()), "n_low": int(b.sum()),
                         "auroc": round(float(auc), 3), "detected_high_pct": round(100 * float((e[a] > 0).mean()), 1),
                         "detected_low_pct": round(100 * float((e[b] > 0).mean()), 1)})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    feature_space = set(pd.read_csv(FEATURES)["gene"].str.upper())
    sets = proteomics()
    det = pd.DataFrame({name: detection(raw) for name, raw in sets.items()}).rename_axis("marker").reset_index()
    det.insert(1, "in_feature_space", det["marker"].isin(feature_space))
    by_type = fulcher_by_type(sets["Fulcher 2026"])
    riek = rieckmann()
    auroc = reference_auroc()

    verdicts = []
    for name, _, _, _, _, markers in PAIRS:
        for m in markers:
            d = det.set_index("marker").loc[m]
            labs = {LAB_OF[s] for s in sets if pd.notna(d[s]) and d[s] >= MIN_DETECTED}
            labs_measured = {LAB_OF[s] for s in sets if pd.notna(d[s])}
            fulcher_types = by_type[(by_type["marker"] == m) & by_type["detected_pct"].notna()]
            rare_ok = bool(len(fulcher_types) and fulcher_types["detected_pct"].max() >= MIN_DETECTED and len(labs_measured) >= 2)
            r = riek[(riek["pair"] == name) & (riek["marker"] == m)]
            a = auroc[(auroc["pair"] == name) & (auroc["marker"] == m)]
            c1 = len(labs) >= 2 or rare_ok
            c2 = (int(r["donors_2fold"].iloc[0]) >= MIN_DONORS) if len(r) else None  # None: no sorted pair (macrophage)
            c3 = bool(len(a) and a["in_reference"].iloc[0] and a["auroc"].iloc[0] >= MIN_AUROC)
            verdicts.append({"pair": name, "marker": m, "in_feature_space": m in feature_space,
                             "measured_labs": sorted(labs_measured), "labs_at_30pct": sorted(labs),
                             "1_measured": c1, "2_rieckmann": c2, "3_reference_auroc": c3,
                             "qualifies": bool(c1 and c3 and (c2 is None or c2))})
    verdict = pd.DataFrame(verdicts)
    for frame, name in ((det, "detection"), (by_type, "fulcher_by_type"), (riek, "rieckmann_pairs"),
                        (auroc, "reference_auroc"), (verdict, "verdicts")):
        frame.to_csv(OUT / f"{name}.csv", index=False, lineterminator="\n")
    summary = {"run": datetime.now().isoformat(timespec="seconds"), "rules": {"min_detected_pct": MIN_DETECTED,
               "min_donors_2fold": MIN_DONORS, "min_auroc": MIN_AUROC},
               "datasets": {n: {"cells": len(r.cell_ids), "proteins": len(r.gene_names)} for n, r in sets.items()},
               "reference_labels": {"file": LABELS.relative_to(REPO).as_posix(),
                                    "sha256": hashlib.sha256(LABELS.read_bytes()).hexdigest()},
               "qualifying": verdict[verdict["qualifies"]][["pair", "marker", "in_feature_space"]].to_dict("records")}
    (OUT / "audit.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(det.to_string(index=False))
    print(verdict.to_string(index=False))


if __name__ == "__main__":
    main()
