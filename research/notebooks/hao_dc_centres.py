"""Goal 2, Phases 1.2 and 2b: dendritic cells from Hao et al. 2021 in the class
centres, without retraining. The reference has one myeloid DC cell and 29
pDCs, so the best guess's DC centroids and class means rest on almost
nothing. Development data only (Hao's Batch1 donors P1-P4, Tabula Sapiens,
the development protein sets); rules, checks and gates fixed here before the
run.

Candidates, each against its own base (everything else unchanged: answers,
weights, OOD, coordinates):
- "v4.1+DC": v4.1 with every member's myeloid DC and pDC centroids, and those
  two RNA class means, recomputed over the Tabula Sapiens cells of the class
  plus Hao's Batch1 cells mapped to it (cDC1 and cDC2 to myeloid DC; pDC),
  embedded the reference's way (class-balanced statistics, every gene
  observed, scripts/build_v4_bundle.py; Hao genes absent from the input space
  masked). Cell-weighted.
- "v4.2+DC": the same on v4.2 (its protein class means unchanged).

Hao cells: research/notebooks/hao2021.py (Batch1 only). The Hao suite holds
out donors: fold A builds the centroids from P1 and P2 and scores uploads of
P3 and P4; fold B the reverse. The frozen candidate uses all four donors.

Checks (Batch1 and Tabula Sapiens only); any failure is NO GO for both:
- C1, atlas probe: within B cells, classical monocytes (Hao CD14 Mono), NK
  cells and pDCs, a logistic regression (5-fold CV) tells Tabula Sapiens from
  Hao on member 0's reference-side embedding under a real mask (Fulcher's and
  PBMC240's gene sets with per-cell missingness), 300 cells per side and
  class or all there are. Pass: under each mask the mean AUC over the four
  classes is at most 0.9.
- C2, swap: the pDC centroids and class mean from Hao's pDCs alone (no Tabula
  Sapiens pDC); Tabula Sapiens's 29 pDCs, each upload holding them among 271
  other calibration cells (te_cal), 10 uploads per mask (Fulcher, PBMC240),
  through v4.1's served code. Pass: pDC recall of the best guess at least 70%.
- C3, leakage: (a) in the Hao suite, B cells and monocytes guessed as either
  DC class rise by at most 1 point over the base; (b) on Fulcher 2026, DC
  precision (cells guessed DC whose label is DC) at least base - 5 points; on
  PBMC240 and PXD070599's four Astral searches, the share of cells guessed DC
  rises by at most 2 points.

Gates, each candidate against its base:
- G1: Hao suite DC recall (the fine class: myeloid DC for cDC1 and cDC2,
  pDC for pDC; pooled over cells) at least base + 20 points;
- G2: Hao suite mean per-upload coarse balanced accuracy at least base;
- G3: Fulcher six-type balanced accuracy at least base, DC recall at least base;
- G4: PBMC240 lymphoid recall at least base - 1;
- G5: SCoPE2 restricted, both versions, at least base - 2;
- G6: NB3c's calibration suite (te_cal, 240 uploads), mean per-upload
  balanced accuracy of the best guess at least base - 1, with the
  train-plus-validation references and the candidate's DC centroids built
  from those rows plus Hao.
GO: C1-C3 and G1-G6 all hold.

The Hao suite (Batch1, per fold): scenarios "pbmc" (500 cells at Hao's
proportions among mapped types), "myeloid" (100 CD14 monocytes, 100 CD16
monocytes, 100 DCs at their proportions) and "mixed" (60 each of B, CD14
monocyte, NK, CD4 T and DC), masks Fulcher, PBMC240 and SCoPE2 with per-cell
missingness, 5 seeds: 45 uploads per fold.

Self-checks before any gate: each base's development figures recomputed here
equal the committed ones (research/notebook-outputs/v42_protein_means/
summary.json) within 0.01 point, and the recombined best guess equals
fusion.best_guess_probabilities on one upload.

Writes research/notebook-outputs/hao_dc_centres/summary.json and, for a GO,
the candidate's centroids and class means to Drive Data/Results/HaoDC/.

    python research/notebooks/hao_dc_centres.py      # from the repository root
"""
from __future__ import annotations

import collections
import dataclasses
import hashlib
import json
import sys
import time
import warnings
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import cross_val_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import hao2021  # noqa: E402
import v4_calibration as phase3  # noqa: E402
import v41_core as core  # noqa: E402
import v42_protein_means as v42  # noqa: E402

from benchmark.fulcher2026_score import COARSE  # noqa: E402
from service.pipeline import alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "hao_dc_centres"
DRIVE_OUT = REPO.parent / "drive" / "Data" / "Results" / "HaoDC"
RNA_H5 = REPO.parent / "drive" / "Data" / "scRNA-seq" / "Blood_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad"
V4_STATS = REPO / "service" / "model" / "v4" / "class_balanced_stats.npz"
PUBLIC = REPO / "data" / "incoming" / "public_sets" / "PXD070599_PBMC" / "extracted"
MDC, PDC = "myeloid dendritic cell", "plasmacytoid dendritic cell"
DC = (MDC, PDC)
FOLDS = {"A": (("P1", "P2"), ("P3", "P4")), "B": (("P3", "P4"), ("P1", "P2"))}
MASKS, SEEDS = ("fulcher", "pbmc240", "scope2"), range(5)
PROBE_CLASSES = {"b cell": "b cell", "classical monocyte": "classical monocyte", "natural killer cell": "natural killer cell",
                 PDC: PDC}  # Tabula Sapiens class -> Hao class


# ---- data ----
def ts_rows(rows: np.ndarray, feature_genes: list[str]) -> np.ndarray:
    """Tabula Sapiens log-normalised RNA for the given reference rows (reference_metadata.csv order)."""
    with h5py.File(RNA_H5, "r") as f:
        sym = f["var"]["gene_symbol"]
        sym = sym["categories"][:].astype(str)[sym["codes"][:]] if isinstance(sym, h5py.Group) else sym[:].astype(str)
        first: dict[str, int] = {}
        for j, g in enumerate(sym):
            first.setdefault(g.upper(), j)
        indptr = f["X"]["indptr"][:]
        out = np.zeros((len(rows), len(feature_genes)), np.float32)
        cols = np.array([first[g.upper()] for g in feature_genes])
        where = np.full(len(sym), -1, np.int64)
        where[cols] = np.arange(len(cols))
        for i, r in enumerate(rows):
            a, b = indptr[r], indptr[r + 1]
            idx, val = f["X"]["indices"][a:b], f["X"]["data"][a:b]
            keep = where[idx] >= 0
            out[i, where[idx[keep]]] = val[keep]
    return out


class Lab:
    def __init__(self) -> None:
        self.v41 = pipeline.load_bundle("v4.1")
        self.v42 = fusion.V4Bundle.load(require_evaluation=False, version="v4.2")
        self.names = list(self.v41.class_names)
        self.genes = list(self.v41.feature_genes)
        self.meta = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
        self.y = np.array([self.names.index(c) for c in self.meta["class_name"]])
        stats = np.load(V4_STATS)
        self.mu, self.sd = stats["mu"].astype(np.float32), stats["sd"].astype(np.float32)
        X, self.hao_meta, genes = hao2021.load(hao2021.DEVELOPMENT_DONORS, "hao_batch1_feature_counts.npz")
        if genes != self.genes:
            raise SystemExit("Hao's feature genes are not the bundle's")
        self.hao = X
        cols, _ = hao2021._feature_columns(self.genes)
        self.present = np.zeros(len(self.genes), bool)
        self.present[cols[cols >= 0]] = True
        self.hao_class = self.hao_meta["class_name"].to_numpy()
        self.donor = self.hao_meta["donor"].to_numpy()
        self.coarse = np.array([COARSE.get(c, "other") for c in self.names])
        self.resolution = gene_ids.resolve_identifiers(self.genes)
        self.profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
        dc_rows = np.flatnonzero(np.isin(self.meta["class_name"].to_numpy(), DC))
        self.ts_dc_rows = dc_rows
        self.ts_dc = ts_rows(dc_rows, self.genes)

    # ---- the reference side ----
    def embed_reference(self, X: np.ndarray, mask: "np.ndarray | None" = None) -> list[np.ndarray]:
        """Every member's normalised embedding, the reference's way (class-balanced statistics)."""
        values = (X - self.mu) / (self.sd + 1e-8)
        m = np.ones_like(values) if mask is None else mask.astype(np.float32)
        values = np.where(m > 0, values, 0.0).astype(np.float32)
        out = []
        for member in self.v41.members:
            Z = np.asarray(member.encoder_handle.encode(values, m), dtype=np.float32)
            out.append(Z / np.linalg.norm(Z, axis=1, keepdims=True))
        return out

    def hao_dense(self, idx: np.ndarray) -> np.ndarray:
        return self.hao[idx].toarray().astype(np.float32)

    def with_dc(self, base, hao_idx: dict, ts_dc: bool = True, rows_ok: "np.ndarray | None" = None,
                members_base=None, means_base=None):
        """base with the DC centroids and class means recomputed over Tabula Sapiens's cells of the class (those
        in rows_ok, if given; none with ts_dc False) and the Hao cells hao_idx[class]."""
        members = list(members_base or base.members)
        means = np.array(means_base if means_base is not None else base.class_means, dtype=np.float32).copy()
        hao_mask = np.broadcast_to(self.present, (1, len(self.genes)))
        for cls in DC:
            k = self.names.index(cls)
            ts_sel = (self.y[self.ts_dc_rows] == k)
            if rows_ok is not None:
                ts_sel &= np.isin(self.ts_dc_rows, rows_ok)
            if not ts_dc:
                ts_sel[:] = False
            Xt = self.ts_dc[ts_sel]
            Xh = self.hao_dense(hao_idx[cls])
            Zt = self.embed_reference(Xt) if len(Xt) else [np.zeros((0, 1))] * len(members)
            Zh = self.embed_reference(Xh, np.broadcast_to(hao_mask, Xh.shape))
            for i, member in enumerate(members):
                Z = np.vstack([Zt[i], Zh[i]]) if len(Xt) else Zh[i]
                c = Z.mean(0)
                C = member.centroids.copy()
                C[k] = c / np.linalg.norm(c)
                members[i] = dataclasses.replace(member, centroids=C.astype(np.float32))
            zt = (Xt - self.mu) / (self.sd + 1e-8)
            zh = np.where(self.present, (Xh - self.mu) / (self.sd + 1e-8), np.nan)
            means[k] = np.nanmean(np.vstack([zt, zh]) if len(Xt) else zh, axis=0)
        return dataclasses.replace(base, members=tuple(members), class_means=means.astype(np.float32))

    # ---- the query side ----
    def embed_query(self, bundle, raw: alignment.RawMatrix) -> dict:
        """Everything the best guess needs that does not depend on centroids or class means."""
        smoothed, aligned, scale = pipeline._prepare_query(self.genes, raw)
        Zs = [m.encoder_handle.encode(smoothed, aligned.mask) for m in bundle.answers.members]
        Zu = [m.encoder_handle.encode(aligned.values, aligned.mask) for m in bundle.answers.members]
        all_probs = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature)
                                                     for z, m in zip(Zs, bundle.answers.members)])
        counted = aligned.per_cell_observed_genes >= int(bundle.spec["preprocessing"]["min_observed_genes"])
        return {"Zs": Zs, "Zu": Zu, "values": aligned.values, "mask": aligned.mask, "all": all_probs,
                "counted": counted, "raw": raw, "observed": aligned.per_cell_observed_genes}

    def guess(self, bundle, e: dict) -> np.ndarray:
        """fusion.best_guess_probabilities from precomputed embeddings, then the label space."""
        probs = lambda Z: ensemble.ensemble_probabilities([  # noqa: E731
            ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, bundle.members)])
        on = probs(e["Zs"])
        r = fusion.masked_pearson(e["values"], e["mask"], bundle.class_means)
        if getattr(bundle, "protein_means", None) is not None:
            if "protein" not in e:
                e["protein"] = fusion.protein_query(e["raw"], bundle.protein_genes)
            covered = bundle.protein_covered
            r[:, covered] = fusion.masked_pearson(e["protein"][0], e["protein"][1], bundle.protein_means)[:, covered]
        agreement = fusion.upload_agreement(r, e["all"], e["counted"])
        if agreement < bundle.agreement_threshold:
            p = fusion.fused_probabilities(on, np.full_like(on, 1.0 / on.shape[1]), bundle.fusion_weight)
        else:
            enc = fusion.mixed_encoder_probabilities(on, probs(e["Zu"]), bundle.smoothed_share) if bundle.smoothed_share < 1 else on
            p = fusion.fused_probabilities(enc, fusion.correlation_probabilities(r, bundle.correlation_temperature),
                                           fusion.encoder_weight_where_used(bundle))
        space = bundle.components.label_space.estimate(None, self.names, False)
        return bundle.components.label_space.probabilities(p, space)

    def served_guess(self, bundle, e: dict) -> np.ndarray:
        protein = fusion.protein_query(e["raw"], bundle.protein_genes) if getattr(bundle, "protein_means", None) is not None else None
        g = fusion.best_guess_probabilities(bundle, e["Zs"], e["values"], e["mask"], e["all"], e["counted"], protein)
        space = bundle.components.label_space.estimate(None, self.names, False)
        return bundle.components.label_space.probabilities(g.probabilities, space)

    def masked(self, X: np.ndarray, profile: str, seed: int) -> np.ndarray:
        spec = {"seed": seed, "cell_idx": list(range(len(X))), "profile": profile, "stress": False, "missingness": "per_cell"}
        return phase3.raw_upload(spec, lambda idx: X[np.asarray(idx)], self.profiles, len(self.genes))

    def upload(self, X: np.ndarray, profile: str, seed: int) -> alignment.RawMatrix:
        """Hao cells as a protein-like upload: genes Hao lacks unobserved, then the mask profile."""
        raw = self.masked(np.where(self.present, X, np.nan), profile, seed)
        return alignment.RawMatrix(gene_names=self.genes, cell_ids=[f"c{i}" for i in range(len(raw))], values=raw.T)


# ---- the Hao suite ----
def hao_suite(lab: Lab, donors: tuple[str, ...]) -> list[dict]:
    """Uploads of the given donors' cells (indices into lab.hao, true classes)."""
    ok = np.isin(lab.donor, donors) & pd.notna(lab.hao_class)
    by = {c: np.flatnonzero(ok & (lab.hao_class == c)) for c in set(lab.hao_class[ok])}
    l2 = lab.hao_meta["celltype.l2"].to_numpy()
    cd4 = np.flatnonzero(ok & np.isin(l2, ("CD4 Naive", "CD4 TCM", "CD4 TEM", "CD4 CTL")))
    dcs = np.flatnonzero(ok & np.isin(lab.hao_class, DC))
    uploads = []
    for scenario in ("pbmc", "myeloid", "mixed"):
        for profile in MASKS:
            for seed in SEEDS:
                key = f"{scenario}|{profile}|{seed}|{','.join(donors)}".encode()
                rng = np.random.default_rng(int(hashlib.sha256(key).hexdigest()[:8], 16))
                if scenario == "pbmc":
                    idx = rng.choice(np.flatnonzero(ok), 500, replace=False)
                elif scenario == "myeloid":
                    idx = np.concatenate([rng.choice(by["classical monocyte"], 100, replace=False),
                                          rng.choice(by["non-classical monocyte"], 100, replace=False),
                                          rng.choice(dcs, 100, replace=False)])
                else:
                    idx = np.concatenate([rng.choice(by["b cell"], 60, replace=False),
                                          rng.choice(by["classical monocyte"], 60, replace=False),
                                          rng.choice(by["natural killer cell"], 60, replace=False),
                                          rng.choice(cd4, 60, replace=False), rng.choice(dcs, 60, replace=False)])
                uploads.append({"scenario": scenario, "profile": profile, "seed": seed, "idx": idx})
    return uploads


def hao_scores(lab: Lab, truth: np.ndarray, guesses: list[np.ndarray], uploads: list[dict]) -> dict:
    names = np.array(lab.names)
    t_all, g_all, ba = [], [], []
    for u, P in zip(uploads, guesses):
        t = lab.hao_class[u["idx"]]
        g = names[P.argmax(1)]
        t_all.append(t)
        g_all.append(g)
        tc, gc = lab.coarse[[lab.names.index(c) for c in t]], lab.coarse[P.argmax(1)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ba.append(100 * balanced_accuracy_score(tc, gc))
    t, g = np.concatenate(t_all), np.concatenate(g_all)
    dc = np.isin(t, DC)
    bm = np.isin(t, ("b cell", "classical monocyte", "non-classical monocyte"))
    return {"dc_recall": 100 * float((g[dc] == t[dc]).mean()),
            "mdc_recall": 100 * float((g[t == MDC] == MDC).mean()), "pdc_recall": 100 * float((g[t == PDC] == PDC).mean()),
            "coarse_ba": float(np.mean(ba)), "b_mono_called_dc_pct": 100 * float(np.isin(g[bm], DC).mean()),
            "cells": int(len(t)), "uploads": len(uploads)}


# ---- the checks ----
def atlas_probe(lab: Lab) -> dict:
    rng = np.random.default_rng(0)
    out = {}
    for profile in ("fulcher", "pbmc240"):
        aucs = {}
        for ts_cls, hao_cls in PROBE_CLASSES.items():
            ts = np.flatnonzero(lab.y == lab.names.index(ts_cls))
            ts = rng.choice(ts, min(300, len(ts)), replace=False)
            hao = np.flatnonzero(lab.hao_class == hao_cls)
            hao = rng.choice(hao, min(300, len(hao)), replace=False)
            Xt, Xh = ts_rows(np.sort(ts), lab.genes), lab.hao_dense(hao)
            masked = lab.masked(np.vstack([Xt, np.where(lab.present, Xh, np.nan)]), profile, 0)
            mask = np.isfinite(masked)
            Z = lab.embed_reference(np.nan_to_num(masked), mask)[0]
            ylab = np.r_[np.zeros(len(Xt)), np.ones(len(Xh))]
            aucs[ts_cls] = float(cross_val_score(LogisticRegression(max_iter=2000, C=1.0), Z, ylab, cv=5, scoring="roc_auc").mean())
        out[profile] = {"auc": aucs, "mean": float(np.mean(list(aucs.values())))}
    return out


def swap_test(lab: Lab) -> dict:
    hao_pdc = np.flatnonzero(lab.hao_class == PDC)
    hao_mdc = np.flatnonzero(lab.hao_class == MDC)
    swapped = lab.with_dc(lab.v41, {MDC: hao_mdc, PDC: hao_pdc}, ts_dc=False)
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    te_cal = np.asarray(suites["te_cal"])
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_x = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    y_all = np.load(phase3.NB1 / "y_all.npy")
    others = te_cal[~np.isin(y_all[te_cal], [lab.names.index(c) for c in DC])]
    ts_pdc = lab.ts_dc[lab.y[lab.ts_dc_rows] == lab.names.index(PDC)]
    rng = np.random.default_rng(0)
    hits, base_hits = [], []
    for profile in ("fulcher", "pbmc240"):
        for seed in range(10):
            idx = rng.choice(others, 271, replace=False)
            X = np.vstack([ts_pdc, np.asarray(pool_x[[pos[i] for i in idx]], dtype=np.float32)])
            raw = lab.masked(X, profile, seed)
            e = lab.embed_query(lab.v41, alignment.RawMatrix(gene_names=lab.genes, cell_ids=[f"c{i}" for i in range(len(raw))],
                                                             values=raw.T))
            for bundle, sink in ((swapped, hits), (lab.v41, base_hits)):
                P = lab.guess(bundle, e)
                sink.append(np.array(lab.names)[P[:len(ts_pdc)].argmax(1)] == PDC)
    return {"pdc_recall_swapped": 100 * float(np.concatenate(hits).mean()),
            "pdc_recall_served_in_sample": 100 * float(np.concatenate(base_hits).mean()), "ts_pdc_cells": int(len(ts_pdc))}


# ---- development protein data ----
def protein_uploads() -> dict:
    up = v42.uploads()
    for name, sub in (("ds18_standard", "DS18/Standard_Astral_MBR"), ("ds18_faims", "DS18/FAIMS_Astral_MBR"),
                      ("ds18_zoom", "DS18/FAIMS_Astral-Zoom_MBR"), ("ds19", "DS19/MBR")):
        up[name] = alignment.parse_matrix_csv((PUBLIC / sub / "report.pg_matrix.tsv").read_text(encoding="utf-8"))
    return up


def dev_block(lab: Lab, dev: pd.DataFrame, P: dict) -> dict:
    """dev_figures plus DC precision on Fulcher and the DC-guess share elsewhere."""
    stacked = np.vstack([P[n] for n in dict.fromkeys(dev["dataset"])])  # the cache's own row order
    figs = core.dev_figures(dev, stacked, np.array(lab.names))
    names = np.array(lab.names)
    f = (dev["dataset"] == "fulcher2026").to_numpy()
    g = names[P["fulcher2026"].argmax(1)]
    called = np.isin(g, DC)
    figs["fulcher_dc_precision"] = 100 * float((dev.loc[f, "label"].to_numpy()[called] == "DC").mean()) if called.any() else float("nan")
    for n in ("pbmc240", "ds18_standard", "ds18_faims", "ds18_zoom", "ds19"):
        figs[f"{n}_dc_share"] = 100 * float(np.isin(names[P[n].argmax(1)], DC).mean())
    return figs


def calibration_suite(lab: Lab, candidates: dict) -> dict:
    """G6: NB3c's 240 calibration uploads with the train-plus-validation references."""
    split = np.load(phase3.NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    v31 = lab.v41.answers
    cents = [phase3.centroids_from(m.reference_latents[trainval], lab.y[trainval], len(lab.names)) for m in v31.members]
    answers = dataclasses.replace(v31, members=phase3.restricted(v31.members, trainval, cents),
                                  property_values=v31.property_values[trainval])
    cb = [np.load(phase3.CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy")
          for m in lab.v41.members]
    means = np.load(phase3.CALIB_BUNDLE / "class_means_cb.npy").astype(np.float32)
    bundles = {}
    for name, (base, hao_idx) in candidates.items():
        b = dataclasses.replace(base, answers=answers, members=phase3.restricted(base.members, trainval, cb), class_means=means)
        bundles[name] = b if hao_idx is None else lab.with_dc(b, hao_idx, rows_ok=trainval)
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_x = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_x[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    y_all = np.load(phase3.NB1 / "y_all.npy")
    rows, guesses = [], {n: [] for n in bundles}
    first = next(iter(bundles.values()))
    for s in suites["calib"]:
        raw = phase3.raw_upload(s, get_raw, lab.profiles, len(lab.genes))
        e = lab.embed_query(first, alignment.RawMatrix(gene_names=lab.genes, cell_ids=[f"c{i}" for i in range(len(raw))], values=raw.T))
        keep = e["observed"] >= core.MIN_GENES
        for n, b in bundles.items():
            guesses[n].append(lab.guess(b, e).argmax(1)[keep])
        rows.append(pd.DataFrame({"upload": s["id"], "group": phase3.GROUP[s["scenario"]], "source": "calib",
                                  "true": y_all[np.asarray(s["cell_idx"])][keep]}))
    cells = pd.concat(rows, ignore_index=True)
    return {n: core.suite_scores(cells, np.concatenate(g)) for n, g in guesses.items()}


def main() -> None:
    warnings.simplefilter("ignore")
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    lab = Lab()
    print(f"loaded ({time.time() - t0:.0f}s); Hao Batch1 DCs: "
          f"{collections.Counter(lab.hao_class[np.isin(lab.hao_class, DC)])}", flush=True)
    bases = {"v4.1": lab.v41, "v4.2": lab.v42}
    dc_all = {c: np.flatnonzero(lab.hao_class == c) for c in DC}

    # self-checks: committed development figures, and the recombination against the served function
    _, _, dev, _ = core.load()
    up = protein_uploads()
    committed = json.loads((REPO / "research" / "notebook-outputs" / "v42_protein_means" / "summary.json").read_text())["figures"]
    for name in dict.fromkeys(dev["dataset"]):
        if dev.loc[dev["dataset"] == name, "cell_id"].tolist() != list(up[name].cell_ids):
            raise SystemExit(f"STOP: {name}'s cache cells are not its upload's, in order")
    emb = {n: lab.embed_query(lab.v41, raw) for n, raw in up.items()}
    gap = float(np.abs(lab.guess(lab.v42, emb["fulcher2026"]) - lab.served_guess(lab.v42, emb["fulcher2026"])).max())
    if gap > 1e-5:
        raise SystemExit(f"STOP: the recombined best guess differs from the served one by {gap}")
    dev_figs = {}
    for name, base in bases.items():
        figs = dev_block(lab, dev, {n: lab.guess(base, e) for n, e in emb.items()})
        worst = max(abs(figs[k] - v) for k, v in committed[name].items() if k != "auroc")
        if worst > 0.01:
            raise SystemExit(f"STOP: {name}'s development figures differ from the committed ones by {worst:.4f}")
        dev_figs[name] = figs
    print(f"self-checks passed ({time.time() - t0:.0f}s)", flush=True)

    checks = {"atlas_probe": atlas_probe(lab)}
    print("C1", json.dumps(checks["atlas_probe"]), flush=True)
    checks["swap"] = swap_test(lab)
    print("C2", json.dumps(checks["swap"]), flush=True)

    hao = {}
    for fold, (build, score) in FOLDS.items():
        idx = {c: np.flatnonzero((lab.hao_class == c) & np.isin(lab.donor, build)) for c in DC}
        uploads = hao_suite(lab, score)
        es = [lab.embed_query(lab.v41, lab.upload(lab.hao_dense(u["idx"]), u["profile"], u["seed"])) for u in uploads]
        for name, base in bases.items():
            for variant, bundle in ((name, base), (f"{name}+DC", lab.with_dc(base, idx))):
                hao.setdefault(variant, {})[fold] = hao_scores(lab, None, [lab.guess(bundle, e) for e in es], uploads)
        print(f"Hao fold {fold}: {json.dumps({k: v[fold] for k, v in hao.items()})} ({time.time() - t0:.0f}s)", flush=True)
    hao_mean = {k: {m: float(np.mean([v[f][m] for f in v])) for m in v["A"]} for k, v in hao.items()}

    full = {name: lab.with_dc(base, dc_all) for name, base in bases.items()}
    for name, bundle in full.items():
        dev_figs[f"{name}+DC"] = dev_block(lab, dev, {n: lab.guess(bundle, e) for n, e in emb.items()})
    print("development", json.dumps(dev_figs), flush=True)
    calib = calibration_suite(lab, {"v4.1": (lab.v41, None), "v4.1+DC": (lab.v41, dc_all),
                                    "v4.2": (lab.v42, None), "v4.2+DC": (lab.v42, dc_all)})
    print("calibration suite", json.dumps(calib), flush=True)

    c1 = all(checks["atlas_probe"][p]["mean"] <= 0.9 for p in checks["atlas_probe"])
    c2 = checks["swap"]["pdc_recall_swapped"] >= 70
    verdicts = {}
    for name in bases:
        cand, b = f"{name}+DC", name
        d, db, h, hb = dev_figs[cand], dev_figs[b], hao_mean[cand], hao_mean[b]
        c3 = (h["b_mono_called_dc_pct"] - hb["b_mono_called_dc_pct"] <= 1
              and d["fulcher_dc_precision"] >= db["fulcher_dc_precision"] - 5
              and all(d[f"{n}_dc_share"] - db[f"{n}_dc_share"] <= 2 for n in ("pbmc240", "ds18_standard", "ds18_faims", "ds18_zoom", "ds19")))
        gates = {"G1": h["dc_recall"] >= hb["dc_recall"] + 20, "G2": h["coarse_ba"] >= hb["coarse_ba"],
                 "G3": d["fulcher"] >= db["fulcher"] and d["fulcher_DC"] >= db["fulcher_DC"],
                 "G4": d["pbmc240_lymphoid"] >= db["pbmc240_lymphoid"] - 1,
                 "G5": d["scope2_restricted"] >= db["scope2_restricted"] - 2
                 and d["scope2_reprocessed_restricted"] >= db["scope2_reprocessed_restricted"] - 2,
                 "G6": calib[cand]["overall"] >= calib[b]["overall"] - 1}
        verdicts[cand] = {"C1": c1, "C2": c2, "C3": bool(c3), **{k: bool(v) for k, v in gates.items()},
                          "GO": bool(c1 and c2 and c3 and all(gates.values()))}
    summary = {"checks": checks, "hao_suite": hao, "hao_suite_mean": hao_mean, "development": dev_figs,
               "calibration_suite": calib, "verdicts": verdicts, "seconds": round(time.time() - t0)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(verdicts, indent=1), flush=True)
    if any(v["GO"] for v in verdicts.values()):
        DRIVE_OUT.mkdir(parents=True, exist_ok=True)
        for name, bundle in full.items():
            if verdicts[f"{name}+DC"]["GO"]:
                tag = name.replace(".", "") + "_dc"
                np.save(DRIVE_OUT / f"{tag}_class_means_cb.npy", bundle.class_means)
                for m in bundle.members:
                    seed = m.name.split("seed")[1].split(".")[0]
                    np.save(DRIVE_OUT / f"{tag}_V2_seed{seed}_centroids_cb.npy", m.centroids)
        print(f"centroids written to {DRIVE_OUT}")


if __name__ == "__main__":
    main()
