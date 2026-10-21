"""Candidate v4.3 (owner, 2026-10-21; research/reference-data-search.md, step 1):
v4.1 with each gene of its correlation term weighted by how well that gene's
pattern across the reference classes in RNA holds on protein. Protein
uploads only; RNA uploads stay v4.1's. Development data only; the rule and
the gates are fixed here, before any upload is scored, and nothing is tuned.

Why: v4.1's correlation term r compares each protein cell with Tabula
Sapiens's RNA class means, over the genes the cell measured, and every gene
counts the same. A gene whose RNA contrast between classes does not survive
on protein (CD8 T against NK, B against T are the known casualties) still
pulls r. v4.2 replaced the RNA class means with sorted-cell protein means and
gained on Fulcher 2026 but lost on Khoury 2026 (run history entry 48); this
candidate keeps the RNA class means and only weights the genes.

The rule:
- for each feature gene g with a protein in Rieckmann 2017's class means
  (service/model/v4_2/protein_class_means.npz, v4.2's 16 covered classes):
  rho_g = Pearson, across those classes, between v4.1's z-scored
  class-balanced RNA class means and the protein class means;
- w_g = max(0, rho_g);
- a gene without a protein keeps the median weight of the genes with one;
- r becomes the weighted Pearson correlation over the cell's observed genes
  (weight w_g for an observed gene, 0 otherwise). With every weight 1 it is
  v4.1's masked_pearson exactly (self-check 1).
Monaco 2019's sorted RNA (GSE107011) gives a second RNA source for the same
weights; their agreement with the rule's weights is reported only.

Development uploads, each through pipeline.run_projection as served, for
v4.1 and v4.3: Fulcher 2026; PBMC240; both SCoPE2 versions and Furtwängler
2025 (reported, and the out-of-reference AUROC); and PXD056050 (another
lab's FACS-sorted B, naive B, T, CD8 T, monocyte and activated NK pools, a
mix and PBMC, as one upload; side-tests amendment 20), read here for the
first time.

Self-checks first, else stop: (1) unit weights reproduce masked_pearson;
(2) v4.1 reproduces Fulcher 69.05 and PBMC240 92.31 within 0.01.

GO for v4.3 (development evidence), all of:
1. Fulcher balanced accuracy at least v4.1 + 2;
2. PXD056050, balanced accuracy over its five sorted groups at least v4.1's
   (no loss on a second lab's data);
3. PBMC240 lymphoid recall at least v4.1 - 2;
4. Fulcher committed share at least v4.1 - 2, and correct when committed at
   least v4.1 - 1;
5. out-of-reference AUROC at least v4.1 - 0.03.
Reported: Fulcher's CD8 T recall, PXD056050's call per pool, SCoPE2, the
weights. A GO makes v4.3 a frozen candidate (a service spec and the sorted
CD4/CD8 test's next amendment); it is not served before then.

Writes rules.json (first), weights.json, development.json and decision.json
into its own folder of research/notebook-outputs (OUT).

    python research/notebooks/gene_weights.py      # from the repository root
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import sys
import time
import warnings
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v53_gates  # noqa: E402  (the uploads and figures, as v5.3's gates read them)
from benchmark import fulcher2026_score as fulcher  # noqa: E402
from service import config  # noqa: E402
from service.pipeline import alignment, fusion, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "gene_weights"
SETS = REPO / "data" / "incoming" / "public_sets"
PROTEIN_MEANS = REPO / "service" / "model" / "v4_2" / "protein_class_means.npz"
VERSION = "v4.3"
V41_EXPECTED = {"fulcher2026": 69.05, "pbmc240": 92.31}
TOL = 0.01
GO = {"fulcher_gain_min": 2.0, "pxd056050_drop_max": 0.0, "pbmc240_drop_max": 2.0, "committed_drop_max": 2.0,
      "correct_drop_max": 1.0, "auroc_drop_max": 0.03}

# PXD056050's pools, by the cell type in each run's name; the mix and PBMC are context, not scored.
POOL_GROUP = {"Bcell": "B", "Bnaive": "B", "CD8T": "CD8T", "Tcell": "T", "NKactive": "NK", "Mono": "monocyte"}
GROUP_CORRECT = {"B": {"B"}, "CD8T": {"CD8T"}, "T": {"CD4T", "CD8T"}, "NK": {"NK"}, "monocyte": {"monocyte"}}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


# ---- the weights ----

def zscore_rows(M: np.ndarray) -> np.ndarray:
    """Each gene (column) z-scored across the classes (rows)."""
    return (M - M.mean(0)) / (M.std(0) + 1e-12)


def gene_weights(class_means: np.ndarray, genes: list[str], protein: dict) -> tuple[np.ndarray, dict]:
    covered = protein["covered"]
    at = {p: i for i, p in enumerate(protein["proteins"])}
    has = np.array([g in at for g in genes])
    rna = zscore_rows(class_means[covered][:, has])
    prot = zscore_rows(protein["means"][covered][:, [at[g] for g in np.array(genes)[has]]])
    rho = (rna * prot).mean(0)
    w = np.full(len(genes), np.nan)
    w[has] = np.maximum(0.0, rho)
    w[~has] = float(np.median(w[has]))
    summary = {"genes": len(genes), "with_protein": int(has.sum()), "classes": int(covered.sum()),
               "rho_median": round(float(np.median(rho)), 4), "share_weight_zero": round(float(np.mean(rho <= 0)), 4),
               "fill_weight": round(float(np.median(w[has])), 4)}
    return w, summary


def weighted_pearson(values: np.ndarray, mask: np.ndarray, means: np.ndarray, w: np.ndarray) -> np.ndarray:
    """masked_pearson with a weight per gene: a weighted Pearson r over each
    cell's observed genes. A cell with fewer than two observed genes of
    positive weight, or no variance, gets r = 0."""
    W = (mask > 0).astype(np.float64) * w[None, :]
    V = values.astype(np.float64)
    X = V * W
    M = means.astype(np.float64)
    n = W.sum(1, keepdims=True)
    k = (W > 0).sum(1, keepdims=True)
    sx, sxx = X.sum(1, keepdims=True), (X * V).sum(1, keepdims=True)
    sm, smm, sxm = W @ M.T, W @ (M * M).T, X @ M.T
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxm - sx * sm / n
        var = (sxx - sx ** 2 / n) * (smm - sm ** 2 / n)
        r = cov / np.sqrt(var)
    r = np.where((k >= 2) & (var > 1e-12), r, 0.0)
    return np.nan_to_num(r, nan=0.0)


class Weighted:
    """Within this block, v4.1's correlation term uses the weights."""

    def __init__(self, w: np.ndarray):
        self.w = w

    def __enter__(self):
        self.saved = fusion.masked_pearson
        fusion.masked_pearson = lambda values, mask, means: weighted_pearson(values, mask, means, self.w)

    def __exit__(self, *exc):
        fusion.masked_pearson = self.saved


# ---- the data read here for the first time ----

CD4, CD8 = "cd4-positive, alpha-beta t cell", "cd8-positive, alpha-beta t cell"
# Monaco 2019's sorted types (sample names DONOR_TYPE), mapped to the protein means' covered classes.
MONACO_CLASS = {
    "B_naive": "b cell", "B_NSM": "b cell", "B_SM": "b cell", "B_Ex": "b cell", "Plasmablasts": "plasma cell",
    "Basophils": "basophil", "CD4_naive": "naive thymus-derived cd4-positive, alpha-beta t cell",
    "Th1": CD4, "Th1/Th17": CD4, "Th17": CD4, "Th2": CD4, "TFH": CD4, "CD4_TE": CD4, "Treg": "regulatory t cell",
    "CD8_naive": CD8, "CD8_CM": CD8, "CD8_EM": CD8, "CD8_TE": CD8, "NK": "natural killer cell",
    "C_mono": "classical monocyte", "I_mono": "intermediate monocyte", "NC_mono": "non-classical monocyte",
    "mDC": "myeloid dendritic cell", "pDC": "plasmacytoid dendritic cell", "Neutrophils": "neutrophil"}


def monaco_weights(class_means, genes, protein, names) -> dict:
    """The same weights with Monaco's sorted RNA in place of the reference's
    class means, over the classes both cover; reported only."""
    from scipy.stats import spearmanr
    from service.pipeline import gene_ids
    with gzip.open(SETS / "Monaco2019_GSE107011" / "GSE107011_Processed_data_TPM.txt.gz", "rt") as fh:
        tpm = pd.read_csv(fh, sep="\t", index_col=0)
    tpm.index = gene_ids.resolve_to_feature_symbols([i.split(".")[0] for i in tpm.index])
    tpm = np.log2(tpm[tpm.index.notna()] + 1).groupby(level=0).mean()
    kind = pd.Series({c: MONACO_CLASS.get(c.split("_", 1)[1]) for c in tpm.columns}).dropna()
    by_class = tpm[kind.index].T.groupby(kind.to_numpy()).mean()
    classes = [n for n, c in zip(names, protein["covered"]) if c and n in by_class.index]
    at = {p: i for i, p in enumerate(protein["proteins"])}
    use = [g for g in genes if g in at and g in by_class.columns]
    gi, ci = [genes.index(g) for g in use], [names.index(c) for c in classes]
    prot = zscore_rows(protein["means"][ci][:, [at[g] for g in use]])
    rho_m = (zscore_rows(by_class.loc[classes, use].to_numpy()) * prot).mean(0)
    rho_t = (zscore_rows(class_means[ci][:, gi]) * prot).mean(0)
    ok = np.isfinite(rho_m) & np.isfinite(rho_t)
    return {"classes": classes, "genes": int(ok.sum()),
            "spearman_rho_reference_vs_monaco": round(float(spearmanr(rho_t[ok], rho_m[ok])[0]), 4),
            "spearman_weight_reference_vs_monaco": round(float(spearmanr(np.maximum(0, rho_t[ok]),
                                                                           np.maximum(0, rho_m[ok]))[0]), 4),
            "rho_median_monaco": round(float(np.median(rho_m[ok])), 4)}


def pxd056050_upload():
    """PXD056050's DIA-NN protein-group matrix as one upload of its 30 runs,
    read as the service reads a DIA-NN table; each run's group from the cell
    type in its name ("context" for the mix and PBMC, which are not scored)."""
    with zipfile.ZipFile(SETS / "Zamore2025_PXD056050" / "DIA-NN_immune_cells.zip") as z:
        text = z.read("report.pg_matrix.tsv").decode("utf-8")
    raw = alignment.parse_matrix_csv(text)
    kinds = [re.search(r"230516_([A-Za-z0-9]+)-\d", c).group(1) for c in raw.cell_ids]
    return raw, np.array([POOL_GROUP.get(k, "context") for k in kinds])


def pool_figures(response: dict, groups: np.ndarray, names: list) -> dict:
    calls = [c.get("best_guess", {}).get("label") or "" for c in response["cells"]]
    coarse = [fulcher.COARSE.get(c, "other") for c in calls]
    per = {}
    for g in GROUP_CORRECT:
        at = np.flatnonzero(groups == g)
        per[g] = {"n": int(len(at)), "recall": round(100 * float(np.mean([coarse[i] in GROUP_CORRECT[g] for i in at])), 2)}
    return {"balanced_accuracy": round(float(np.mean([v["recall"] for v in per.values()])), 2), "per_group": per,
            "calls": [{"group": str(g), "best_guess": c} for g, c in zip(groups, calls)]}


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "decision.json").exists():
        raise SystemExit("v4.3's gates were run; they are read once")
    write(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                               "go": GO, "v41_expected": V41_EXPECTED, "tolerance": TOL})
    t0 = time.time()
    bundle = pipeline.load_bundle("v4.1")
    names, genes = bundle.class_names, list(bundle.feature_genes)
    protein = dict(np.load(PROTEIN_MEANS, allow_pickle=False))
    w, summary = gene_weights(bundle.class_means, genes, protein)

    rng = np.random.default_rng(0)
    vals, mask = rng.normal(size=(50, len(genes))), (rng.random((50, len(genes))) < 0.3).astype(float)
    unit_gap = float(np.abs(weighted_pearson(vals, mask, bundle.class_means, np.ones(len(genes)))
                            - fusion.masked_pearson(vals, mask, bundle.class_means)).max())
    summary["self_check_unit_weights_max_gap"] = unit_gap
    summary["monaco"] = monaco_weights(bundle.class_means, genes, protein, names) | {"note": "reported only"}
    write(OUT / "weights.json", summary)
    if unit_gap > 1e-9:
        raise SystemExit(f"STOP: unit weights do not reproduce masked_pearson ({unit_gap})")

    table = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    lineage = table.groupby("class_name")["lineage"].first().to_dict()
    expected = v53_gates.expected_levels()
    dev, prob = {}, {}
    for name, raw, info in v53_gates.uploads():
        for version in ("v4.1", VERSION):
            if version == VERSION:
                with Weighted(w):
                    response = pipeline.run_projection(bundle, raw)
            else:
                response = pipeline.run_projection(bundle, raw)
            fig, p = v53_gates.figures(name, response, info, raw, names, lineage, expected)
            dev.setdefault(name, {})[version] = fig
            prob[(name, version)] = p
        print(name, json.dumps(dev[name]), f"({time.time() - t0:.0f}s)", flush=True)
    raw, groups = pxd056050_upload()
    for version in ("v4.1", VERSION):
        if version == VERSION:
            with Weighted(w):
                response = pipeline.run_projection(bundle, raw)
        else:
            response = pipeline.run_projection(bundle, raw)
        dev.setdefault("pxd056050", {})[version] = pool_figures(response, groups, names)
    print("pxd056050", {v: dev["pxd056050"][v]["balanced_accuracy"] for v in dev["pxd056050"]}, flush=True)
    for version in ("v4.1", VERSION):
        a, b = prob[("fulcher2026", version)], prob[("furtwangler2025", version)]
        dev.setdefault("out_of_reference_auroc", {})[version] = round(
            float(roc_auc_score(np.r_[np.ones(len(a)), np.zeros(len(b))], np.nan_to_num(np.r_[a, b]))), 4)
    write(OUT / "development.json", dev)

    got = {"fulcher2026": dev["fulcher2026"]["v4.1"]["balanced_accuracy_6_types"],
           "pbmc240": dev["pbmc240"]["v4.1"]["lymphoid_recall"]}
    self_check = {k: {"expected": V41_EXPECTED[k], "got": got[k], "passed": abs(got[k] - V41_EXPECTED[k]) <= TOL}
                  for k in V41_EXPECTED}
    if not all(v["passed"] for v in self_check.values()):
        write(OUT / "decision.json", {"self_check": self_check, "go": None,
                                      "reason": "v4.1 did not reproduce its development figures"})
        raise SystemExit(f"STOP: v4.1 did not reproduce its figures: {self_check}")

    f, p, x, oor = dev["fulcher2026"], dev["pbmc240"], dev["pxd056050"], dev["out_of_reference_auroc"]
    checks = {
        "fulcher_gain": f[VERSION]["balanced_accuracy_6_types"] >= f["v4.1"]["balanced_accuracy_6_types"] + GO["fulcher_gain_min"],
        "pxd056050_no_loss": x[VERSION]["balanced_accuracy"] >= x["v4.1"]["balanced_accuracy"] - GO["pxd056050_drop_max"],
        "pbmc240_guardrail": p[VERSION]["lymphoid_recall"] >= p["v4.1"]["lymphoid_recall"] - GO["pbmc240_drop_max"],
        "fulcher_committed": f[VERSION]["answers_committed"] >= f["v4.1"]["answers_committed"] - GO["committed_drop_max"],
        "fulcher_correct_when_committed": (f[VERSION]["answers_correct_when_committed"]
                                           >= f["v4.1"]["answers_correct_when_committed"] - GO["correct_drop_max"]),
        "out_of_reference_auroc": oor[VERSION] >= oor["v4.1"] - GO["auroc_drop_max"],
    }
    go = all(checks.values())
    decision = {"finished": datetime.now().isoformat(timespec="seconds"), "self_check": self_check,
                "checks": checks, "go": go, "seconds": round(time.time() - t0)}
    write(OUT / "decision.json", decision)
    print(json.dumps(decision, indent=1))


if __name__ == "__main__":
    main()
