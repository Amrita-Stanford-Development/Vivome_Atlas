"""v4 pre-test: the inference-only design chosen for v4.0, reproduced and its
fusion setting chosen properly (research/notebook-run-history.md, entry 20).

The 2026-10-04 pre-tests ran in memory. This script fixes the adopted design
and makes the one choice that was not yet clean: the fusion weight and
temperature had been picked on NB1's evaluation suite. Here they are picked
on NB1's calibration suite, and the evaluation suite is then scored once.

The design (frozen V2 members, no retraining):
- query smoothing off: the members encode the aligned, per-upload z-scored
  values (pipeline._prepare_query's `aligned.values`), not the smoothed ones;
- the reference is re-encoded with class-balanced gene statistics (each of the
  22 classes weighted equally), and the centroids recomputed;
- fusion: p = w * ensemble probabilities + (1 - w) * softmax(r / tau), where r
  is the Pearson correlation, over each cell's observed genes, between its
  values and the class-balanced z-scored RNA class means (9,002 genes).

Rules fixed before the run:
- Grid: w in {0.3, 0.5, 0.7}, tau in {0.03, 0.05, 0.10}. Chosen on the
  calibration suite (sim_suite_calib_v1.json) by the highest mean per-upload
  balanced accuracy over all 240 uploads; ties within 0.1 point go to the
  higher w (closer to v3.1), then the higher tau (smoother).
- The evaluation suite (sim_suite_eval_v1.json) is then scored once: the
  chosen fusion, the encoder alone (smoothing off, class-balanced) and v3.1
  as served (smoothing on, whole-blood statistics).
- Simulation references use only cells outside NB1's held-out pool.
- Development data (SCoPE2, PBMC240, Fulcher 2026, Furtwangler 2025) are
  reported for the chosen setting, never used to choose. They are reported
  with two references: the pool-free one the in-memory pre-tests used, and all
  85,233 cells, which is what v4 will serve (Phase 2's gate compares with this).
- Khoury 2026 is not read.

Inputs outside the repository (D:/Project/Vivome/drive): the Tabula Sapiens
blood h5ad and NB1's folder (pool, splits, global statistics, mask profiles,
suites, sim_generator.py). Writes research/notebook-outputs/v4_pretest/.

    python research/notebooks/v4_pretest.py      # from the repository root, vivome env (about 10 minutes)
"""
from __future__ import annotations

import glob
import json
import sys
import time
import warnings
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

REPO = Path(__file__).resolve().parents[2]
DRIVE = REPO.parent / "drive" / "Data"
NB1 = DRIVE / "Results" / "Tier1_v31" / "NB1"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(NB1))
import sim_generator as sg  # noqa: E402

from benchmark import baselines_v31, datasets  # noqa: E402
from benchmark import fulcher2026_score as fulcher  # noqa: E402
from service.pipeline import alignment, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v4_pretest"
GRID = [(w, tau) for w in (0.3, 0.5, 0.7) for tau in (0.03, 0.05, 0.10)]
GROUP = {"random_1": "single", "random_2": "narrow", "random_3": "narrow", "random_5": "mixed",
         "random_8": "mixed", "myeloid": "lineage", "lymphoid": "lineage", "pbmc_like": "pbmc",
         "scope2_like": "scope2"}
PROGENITORS = ("hematopoietic stem cell", "hematopoietic precursor cell", "common myeloid progenitor")


def softmax(logits):
    logits = logits - logits.max(axis=1, keepdims=True)
    p = np.exp(logits)
    return p / p.sum(axis=1, keepdims=True)


def masked_pearson(values, mask, means):
    """Pearson r between each cell and each class mean over that cell's observed
    genes only. values: (n, G), 0 where unobserved; mask: (n, G); means: (K, G)."""
    W = (mask > 0).astype(np.float64)
    X = values.astype(np.float64) * W
    M = means.astype(np.float64)
    n = W.sum(1, keepdims=True)
    sx, sxx = X.sum(1, keepdims=True), (X * X).sum(1, keepdims=True)
    sm, smm, sxm = W @ M.T, W @ (M * M).T, X @ M.T
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxm - sx * sm / n
        var = (sxx - sx ** 2 / n) * (smm - sm ** 2 / n)
        r = cov / np.sqrt(var)
    return np.nan_to_num(r, nan=0.0)


def load_blood(feature_genes):
    f = h5py.File(glob.glob(str(DRIVE / "scRNA-seq" / "Blood_TSP1_30*.h5ad"))[0], "r")
    sym = f["var"]["gene_symbol"]
    sym = sym["categories"][:].astype(str)[sym["codes"][:]] if isinstance(sym, h5py.Group) else sym[:].astype(str)
    first = {}
    for j, g in enumerate(sym):
        first.setdefault(g.upper(), j)
    X = sp.csr_matrix((f["X"]["data"][:], f["X"]["indices"][:], f["X"]["indptr"][:]), shape=tuple(f["X"].attrs["shape"]))
    return X[:, np.array([first[g.upper()] for g in feature_genes])].toarray().astype(np.float32)


class Reference:
    """Centroids per member and class means, from a set of reference cells under
    given gene statistics (class-balanced unless mu/sd are passed)."""

    def __init__(self, bundle, X, y, n_classes, mu=None, sd=None):
        if mu is None:
            counts = np.bincount(y, minlength=n_classes).astype(np.float64)
            w = 1.0 / counts[y]
            w /= w.sum()
            mu = (w @ X).astype(np.float32)
            sd = np.sqrt(w @ (X - mu) ** 2).astype(np.float32)
        self.centroids = []
        for m in bundle.members:
            Z = np.concatenate([np.asarray(m.encoder_handle.encode((X[i:i + 8192] - mu) / (sd + 1e-8),
                                                                    np.ones((len(X[i:i + 8192]), X.shape[1]), np.float32)),
                                           dtype=np.float32) for i in range(0, len(X), 8192)])
            Z /= np.linalg.norm(Z, axis=1, keepdims=True)
            c = np.stack([Z[y == k].mean(0) for k in range(n_classes)])
            self.centroids.append(c / np.linalg.norm(c, axis=1, keepdims=True))
        self.means = np.stack([((X[y == k] - mu) / (sd + 1e-8)).mean(0) for k in range(n_classes)])

    def encoder_probs(self, bundle, values, mask):
        out = []
        for m, c in zip(bundle.members, self.centroids):
            z = np.asarray(m.encoder_handle.encode(values, mask), dtype=np.float32)
            out.append(softmax((z / np.linalg.norm(z, axis=1, keepdims=True)) @ c.T / m.temperature))
        return np.mean(out, axis=0)


def per_upload_balanced(truth, pred):
    return 100 * (balanced_accuracy_score(truth, pred) if len(set(truth)) > 1 else float((pred == truth).mean()))


def simulate(suite, y, get_raw, profiles, n_genes):
    rows = []
    for s in suite:
        Xs, Ms, _ = sg.materialize(s, get_raw, profiles, n_genes, convention="service", smooth=True)
        Xn, Mn, _ = sg.materialize(s, get_raw, profiles, n_genes, convention="service", smooth=False)
        rows.append((GROUP[s["scenario"]], y[np.asarray(s["cell_idx"])], Xs, Ms, Xn, Mn))
    return rows


def suite_table(scores):
    df = pd.DataFrame(scores)
    table = df.pivot_table(index="method", columns="group", values="bal", aggfunc="mean")
    table["ALL"] = df.groupby("method")["bal"].mean()
    return table.round(2)


def main() -> None:
    warnings.simplefilter("ignore")
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    bundle = pipeline.load_bundle("v3.1")
    classes = list(bundle.class_names)
    cidx = {c: i for i, c in enumerate(classes)}
    meta = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    lineage = meta.groupby("class_name")["lineage"].first().to_dict()
    y = np.array([cidx[c] for c in meta["class_name"]])
    X = load_blood(bundle.feature_genes)
    pool = np.load(NB1 / "pool_idx.npy")
    keep = np.ones(len(X), bool)
    keep[pool] = False
    gs = np.load(NB1 / "rna_global_stats.npz")
    refs = {"pool-free, class-balanced": Reference(bundle, X[keep], y[keep], len(classes)),
            "pool-free, whole-blood stats": Reference(bundle, X[keep], y[keep], len(classes), gs["mu"], gs["sd"]),
            "all cells, class-balanced": Reference(bundle, X, y, len(classes))}
    print(f"references built ({time.time() - t0:.0f}s)", flush=True)

    profiles = dict(np.load(NB1 / "mask_profiles.npz"))
    pos = {g: i for i, g in enumerate(pool)}
    pool_X = np.load(NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_X[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731

    def load_suite(name):
        d = json.loads((NB1 / name).read_text())
        return d["specs"] if isinstance(d, dict) else d

    cb, gl = refs["pool-free, class-balanced"], refs["pool-free, whole-blood stats"]

    # 1. the grid, on the calibration suite
    calib = simulate(load_suite("sim_suite_calib_v1.json"), y, get_raw, profiles, len(bundle.feature_genes))
    scores = []
    for group, truth, _, _, Xn, Mn in calib:
        pe, r = cb.encoder_probs(bundle, Xn, Mn), masked_pearson(Xn, Mn, cb.means)
        for w, tau in GRID:
            pred = (w * pe + (1 - w) * softmax(r / tau)).argmax(1)
            scores.append({"method": f"w={w} tau={tau}", "group": group, "bal": per_upload_balanced(truth, pred)})
    grid = suite_table(scores)
    grid.to_csv(OUT / "selection_calibration_suite.csv", lineterminator="\n")
    best = grid["ALL"].max()
    tied = [(w, tau) for w, tau in GRID if grid.loc[f"w={w} tau={tau}", "ALL"] >= best - 0.1]
    w_star, tau_star = sorted(tied, key=lambda t: (-t[0], -t[1]))[0]
    print(grid.sort_values("ALL", ascending=False).to_string(), flush=True)
    print(f"chosen on the calibration suite: w={w_star}, tau={tau_star} ({time.time() - t0:.0f}s)", flush=True)

    # 2. the evaluation suite, scored once
    evaluation = simulate(load_suite("sim_suite_eval_v1.json"), y, get_raw, profiles, len(bundle.feature_genes))
    scores = []
    for group, truth, Xs, Ms, Xn, Mn in evaluation:
        pe = cb.encoder_probs(bundle, Xn, Mn)
        fused = w_star * pe + (1 - w_star) * softmax(masked_pearson(Xn, Mn, cb.means) / tau_star)
        for method, P in (("v3.1 as served (smoothing on, whole-blood stats)", gl.encoder_probs(bundle, Xs, Ms)),
                          ("encoder (smoothing off, class-balanced)", pe), ("v4 candidate (fusion)", fused)):
            scores.append({"method": method, "group": group, "bal": per_upload_balanced(truth, P.argmax(1))})
    ev = suite_table(scores)
    ev.to_csv(OUT / "evaluation_suite.csv", lineterminator="\n")
    print(ev.to_string(), f"({time.time() - t0:.0f}s)", flush=True)

    # 3. development data, reported only
    pbmc_meta = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    uploads = [("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), pbmc_meta),
               ("scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")),
               ("fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels()),
               ("furtwangler2025", datasets.load_furtwangler2025_upload(), datasets.load_furtwangler2025_labels())]
    dev, max_prob, predictions = {}, {}, []
    for name, raw, info in uploads:
        smoothed, aligned, _ = pipeline._prepare_query(bundle.feature_genes, raw)
        rows = np.arange(len(aligned.values))
        if name == "pbmc240":
            at = {c: i for i, c in enumerate(raw.cell_ids)}
            rows = np.array([at[c] for c in info["cell_id"].astype(str)])
        V, M, S = aligned.values[rows], aligned.mask[rows], smoothed[rows]
        ids = np.asarray(raw.cell_ids)[rows]
        for rname, ref in (("pool-free", cb), ("all cells", refs["all cells, class-balanced"])):
            pe = ref.encoder_probs(bundle, V, M)
            variants = {"v3.1 as served": gl.encoder_probs(bundle, S, M) if rname == "pool-free" else None,
                        "encoder, smoothing off, class-balanced": pe,
                        "v4 candidate (fusion)": w_star * pe + (1 - w_star) * softmax(masked_pearson(V, M, ref.means) / tau_star)}
            for vname, P in variants.items():
                if P is None:
                    continue
                pred = np.array(classes)[P.argmax(1)]
                dev.setdefault(name, {}).setdefault(rname, {})[vname] = metrics(name, pred, info, P, cidx, lineage)
                max_prob[(name, rname, vname)] = P.max(1)
                if vname == "v4 candidate (fusion)" and rname == "all cells":
                    predictions += [{"dataset": name, "cell_id": c, "best_guess": p} for c, p in zip(ids, pred)]
    for rname in ("pool-free", "all cells"):
        for vname in ("v3.1 as served", "encoder, smoothing off, class-balanced", "v4 candidate (fusion)"):
            a, b = max_prob.get(("fulcher2026", rname, vname)), max_prob.get(("furtwangler2025", rname, vname))
            if a is not None:
                auc = roc_auc_score(np.r_[np.ones(len(a)), np.zeros(len(b))], np.r_[a, b])
                dev.setdefault("out_of_reference_auroc", {}).setdefault(rname, {})[vname] = round(float(auc), 4)
    pd.DataFrame(predictions).to_csv(OUT / "development_predictions_v4_candidate.csv", index=False, lineterminator="\n")
    record = {"chosen": {"w": w_star, "tau": tau_star, "on": "sim_suite_calib_v1.json (NB1 calibration suite)"},
              "grid": GRID, "evaluation_suite": json.loads(ev.to_json(orient="index")), "development": dev,
              "khoury2026": "not read", "seconds": round(time.time() - t0)}
    (OUT / "summary.json").write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    print(json.dumps(dev, indent=1), flush=True)


def metrics(name, pred, info, P, cidx, lineage):
    if name == "fulcher2026":
        truth = info["label"].to_numpy()
        scored = truth != datasets.FULCHER2026["unscored_label"]
        types = np.array([fulcher.COARSE.get(c, "other") for c in pred])
        out = {"balanced_accuracy_6_types": 100 * balanced_accuracy_score(truth[scored], types[scored])}
        for t in datasets.FULCHER2026["types"]:
            out[f"recall_{t}"] = 100 * float((types[truth == t] == t).mean())
        return {k: round(v, 2) for k, v in out.items()}
    if name == "pbmc240":
        truth = info["weak_lineage"].to_numpy()
        lin = np.array([lineage[c] for c in pred])
        return {"lymphoid_recall": round(100 * float((lin[truth == "lymphoid"] == "lymphoid").mean()), 2),
                "myeloid_recall": round(100 * float((lin[truth == "myeloid"] == "myeloid").mean()), 2)}
    if name == "scope2":
        truth = info["class_name"].to_numpy()
        two = [cidx["macrophage"], cidx["monocyte"]]
        restricted = np.array(["macrophage", "monocyte"])[P[:, two].argmax(1)]
        return {"balanced_accuracy_unrestricted": round(100 * balanced_accuracy_score(truth, pred), 2),
                "balanced_accuracy_restricted": round(100 * balanced_accuracy_score(truth, restricted), 2)}
    return {"progenitor_share": round(100 * float(np.isin(pred, PROGENITORS).mean()), 2),
            "t_cell_share": round(100 * float(np.char.find(pred.astype(str), " t cell").__ge__(0).mean()), 2),
            "median_max_probability": round(float(np.median(P.max(1))), 4)}


if __name__ == "__main__":
    main()
