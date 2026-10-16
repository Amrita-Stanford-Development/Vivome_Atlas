"""The internal held-out test's Hao 2021 suite
(research/benchmark/protocol-heldout-hao2021.md): simulated protein-like
uploads of Hao et al. 2021's held-out donors, typed by every frozen candidate
and by the correlation and PCA kNN baselines.

    python -m benchmark.heldout_hao2021 --rehearse     # development donors P1-P4
    python -m benchmark.heldout_hao2021 --unseal       # held-out donors P5-P8, once, at the end

Uploads, per donor: three scenarios ("pbmc": 500 cells at the donor's own
proportions among the included types; "myeloid": 100 CD14 monocytes, 100
CD16 monocytes and 100 dendritic cells at their proportions; "mixed": 60 each
of B cells, CD14 monocytes, NK cells, CD4 T cells and dendritic cells), each
under three real mask profiles (Fulcher, PBMC240, SCoPE2, with per-cell
missingness) and three seeds: 108 uploads. Scored cells are the non-T/NK types
the protocol maps (benchmark scoring: COARSE of the mapped class); T and NK
cells are development data and ride along unscored. A scenario takes every
available cell when a donor has fewer than it asks for.

Writes results/heldout_hao2021{,_rehearsal}/ (gitignored): per_upload.csv
(every model's scores per upload) and summary.json (the primary and secondary
measures); the summary also goes under research/benchmark/heldout/ (as
rehearsals/hao2021.json for the rehearsal, hao2021/summary.json at the
scoring). It refuses to overwrite the unsealed results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

from benchmark import baselines_corrected, baselines_inputs, baselines_run, datasets
from benchmark.evaluate import knn_classifier_predict
from benchmark.fulcher2026_score import COARSE
from benchmark.sorted_cd4cd8_intake import check_frozen, load_bundle
from service.pipeline import alignment, pipeline

REPO = datasets.REPO
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import hao2021  # noqa: E402
import v4_calibration as phase3  # noqa: E402  (raw_upload, NB1)

RESULTS = REPO / "benchmark" / "results"
RECORDS = REPO / "research" / "benchmark" / "heldout"
MODELS = {"v31": "v3.1", "v41": "v4.1", "v42": "v4.2", "v52": "v5.2"}  # candidates frozen by amendment 2; v3.1 for reference
SCENARIOS, MASKS, SEEDS = ("pbmc", "myeloid", "mixed"), ("fulcher", "pbmc240", "scope2"), (0, 1, 2)
DC_L2, B_L2 = ("cDC1", "cDC2", "pDC"), ("B naive", "B intermediate", "B memory")
CD4_L2 = ("CD4 Naive", "CD4 TCM", "CD4 TEM", "CD4 CTL")
MDC, PDC = "myeloid dendritic cell", "plasmacytoid dendritic cell"
N_BOOT, BOOT_SEED = 10_000, 0


def scored_mask(l2: np.ndarray) -> np.ndarray:
    """The cells the suite scores: mapped, and not T or NK."""
    return np.array([x in hao2021.L2_TO_CLASS and x not in hao2021.TNK for x in l2])


def build_uploads(meta: pd.DataFrame) -> list[dict]:
    l2 = meta["celltype.l2"].to_numpy()
    donor = meta["donor"].to_numpy()
    included = np.array([x in hao2021.L2_TO_CLASS for x in l2])
    uploads = []
    for d in sorted(set(donor)):
        mine = donor == d
        pick = lambda types: np.flatnonzero(mine & np.isin(l2, types))  # noqa: E731
        for scenario in SCENARIOS:
            for profile in MASKS:
                for seed in SEEDS:
                    key = f"{d}|{scenario}|{profile}|{seed}".encode()
                    rng = np.random.default_rng(int(hashlib.sha256(key).hexdigest()[:8], 16))
                    take = lambda pool, n: rng.choice(pool, min(n, len(pool)), replace=False)  # noqa: E731
                    if scenario == "pbmc":
                        idx = take(np.flatnonzero(mine & included), 500)
                    elif scenario == "myeloid":
                        idx = np.concatenate([take(pick(["CD14 Mono"]), 100), take(pick(["CD16 Mono"]), 100), take(pick(DC_L2), 100)])
                    else:
                        idx = np.concatenate([take(pick(B_L2), 60), take(pick(["CD14 Mono"]), 60), take(pick(["NK"]), 60),
                                              take(pick(CD4_L2), 60), take(pick(DC_L2), 60)])
                    uploads.append({"upload": f"{d}_{scenario}_{profile}_{seed}", "donor": d, "scenario": scenario,
                                    "profile": profile, "seed": seed, "idx": np.sort(idx)})
    return uploads


def scores(truth_class: np.ndarray, guess_class: np.ndarray, scored: np.ndarray) -> dict:
    t = np.array([COARSE.get(c, "other") for c in truth_class[scored]])
    g = np.array([COARSE.get(c, "other") for c in guess_class[scored]])
    tc, gc = truth_class[scored], guess_class[scored]
    dc = np.isin(tc, (MDC, PDC))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ba = 100 * balanced_accuracy_score(t, g)
    return {"coarse_ba": ba, "scored_cells": int(scored.sum()),
            "dc_cells": int(dc.sum()), "dc_fine_hits": int((gc[dc] == tc[dc]).sum()),
            "b_cells": int((t == "B").sum()), "b_hits": int(((t == "B") & (g == "B")).sum()),
            "mono_cells": int((t == "monocyte").sum()), "mono_hits": int(((t == "monocyte") & (g == "monocyte")).sum())}


class Baselines:
    """Correlation and PCA kNN as benchmark/baselines_corrected.py runs them, per upload."""

    def __init__(self) -> None:
        self.genes = datasets.benchmark_gene_space()
        self.rna = np.load(baselines_inputs.D / "rna_X.npy")
        self.labels = pd.read_csv(baselines_inputs.D / "rna_meta.csv")["class_name"].to_numpy()

    def query(self, raw: np.ndarray, feature_genes: list[str]) -> np.ndarray:
        index = {g: i for i, g in enumerate(feature_genes)}
        cols = [index.get(g) for g in self.genes]
        out = np.full((len(raw), len(self.genes)), np.nan, dtype=np.float32)
        for j, c in enumerate(cols):
            if c is not None:
                out[:, j] = raw[:, c]
        return out

    def run(self, q: np.ndarray) -> dict:
        measured = np.isfinite(q).any(axis=0)
        inp = baselines_inputs.Inputs(dataset="hao", rna_z=baselines_corrected.class_balanced_z(self.rna[:, measured], self.labels),
                                      query_z=baselines_inputs.zscore_cols_observed(q[:, measured]).astype(np.float32),
                                      rna_labels=self.labels, query_ids=[str(i) for i in range(len(q))],
                                      genes=[g for g, m in zip(self.genes, measured) if m], record={})
        corr = np.asarray(baselines_run.run_correlation(inp)["unrestricted"])
        rna_emb, q_emb = baselines_corrected.run_pca(inp, 0)
        knn = np.asarray(knn_classifier_predict(rna_emb, inp.rna_labels, q_emb)["unrestricted"])
        return {"correlation": corr, "pca_knn": knn}


def pooled(df: pd.DataFrame) -> dict:
    s = df.sum(numeric_only=True)
    return {"coarse_ba_mean": float(df["coarse_ba"].mean()),
            "dc_recall": 100 * s["dc_fine_hits"] / max(1, s["dc_cells"]),
            "b_recall": 100 * s["b_hits"] / max(1, s["b_cells"]),
            "mono_recall": 100 * s["mono_hits"] / max(1, s["mono_cells"])}


def donor_blocked_bootstrap(diff: pd.Series, donors: pd.Series) -> dict:
    """The mean per-upload difference, resampling donors, then uploads within each drawn donor."""
    rng = np.random.default_rng(BOOT_SEED)
    by = {d: diff[donors == d].to_numpy() for d in sorted(donors.unique())}
    keys = list(by)
    draws = np.empty(N_BOOT)
    for b in range(N_BOOT):
        picked = [by[k] for k in rng.choice(keys, len(keys))]
        draws[b] = np.mean(np.concatenate([rng.choice(v, len(v)) for v in picked]))
    return {"mean": float(diff.mean()), "lower_95_one_sided": float(np.percentile(draws, 5)),
            "upper_95_one_sided": float(np.percentile(draws, 95))}


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--rehearse", action="store_true", help="development donors P1-P4")
    mode.add_argument("--unseal", action="store_true", help="held-out donors P5-P8, once")
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    t0 = time.time()
    out = RESULTS / ("heldout_hao2021_rehearsal" if args.rehearse else "heldout_hao2021")
    if args.unseal and ((out / "summary.json").exists() or (RECORDS / "hao2021" / "summary.json").exists()):
        sys.exit("the held-out suite's summary exists: it is scored once")
    frozen = check_frozen()
    donors = hao2021.DEVELOPMENT_DONORS if args.rehearse else hao2021.HELD_OUT_DONORS
    X, meta, genes = hao2021.load(donors, "hao_batch1_feature_counts.npz" if args.rehearse else "hao_batch2_feature_counts.npz")
    cols, _ = hao2021._feature_columns(genes)
    present = np.zeros(len(genes), bool)
    present[cols[cols >= 0]] = True
    l2 = meta["celltype.l2"].to_numpy()
    truth = np.array([hao2021.L2_TO_CLASS.get(x, "") for x in l2], dtype=object)
    scored_all = scored_mask(l2)
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    bundles = {name: load_bundle(version) for name, version in MODELS.items()}
    base = Baselines()
    uploads = build_uploads(meta)
    rows = []
    for n, u in enumerate(uploads):
        dense = np.where(present, X[u["idx"]].toarray().astype(np.float32), np.nan)
        spec = {"seed": u["seed"], "cell_idx": list(range(len(dense))), "profile": u["profile"], "stress": False,
                "missingness": "per_cell"}
        raw = phase3.raw_upload(spec, lambda idx: dense[np.asarray(idx)], profiles, len(genes))
        matrix = alignment.RawMatrix(gene_names=genes, cell_ids=[f"c{i}" for i in range(len(raw))], values=raw.T)
        t, sc = truth[u["idx"]], scored_all[u["idx"]]
        guesses = {}
        for name, bundle in bundles.items():
            cells = pipeline.run_projection(bundle, matrix)["cells"]
            guesses[name] = np.array([c.get("best_guess", {}).get("label", "") for c in cells], dtype=object)
        guesses.update(base.run(base.query(raw, genes)))
        for model, g in guesses.items():
            rows.append({"upload": u["upload"], "donor": u["donor"], "scenario": u["scenario"], "profile": u["profile"],
                         "seed": u["seed"], "cells": len(u["idx"]), "model": model, **scores(t, g, sc)})
        if (n + 1) % 12 == 0:
            print(f"  {n + 1}/{len(uploads)} uploads ({time.time() - t0:.0f}s)", flush=True)
    table = pd.DataFrame(rows)
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "per_upload.csv", index=False, lineterminator="\n")
    by_model = {m: pooled(d) for m, d in table.groupby("model")}
    wide = table.pivot(index="upload", columns="model", values="coarse_ba")
    donor_of = table.drop_duplicates("upload").set_index("upload")["donor"].reindex(wide.index)
    stronger = max(("correlation", "pca_knn"), key=lambda m: by_model[m]["coarse_ba_mean"])
    comparisons = {f"{m} - {b}": donor_blocked_bootstrap(wide[m] - wide[b], donor_of)
                   for m in MODELS for b in ("correlation", "pca_knn")}
    comparisons.update({f"{m} - v41": donor_blocked_bootstrap(wide[m] - wide["v41"], donor_of) for m in MODELS if m != "v41"})
    summary = {"protocol": "research/benchmark/protocol-heldout-hao2021.md", "rehearsal": bool(args.rehearse),
               "donors": list(donors), "uploads": len(uploads), "frozen_files": frozen, "by_model": by_model,
               "stronger_baseline_here": stronger, "comparisons": comparisons, "seconds": round(time.time() - t0)}
    text = json.dumps(summary, indent=2) + "\n"
    (out / "summary.json").write_text(text, encoding="utf-8", newline="\n")
    record = RECORDS / ("rehearsals/hao2021.json" if args.rehearse else "hao2021/summary.json")
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({k: summary[k] for k in ("by_model", "stronger_baseline_here")}, indent=1))
    print(json.dumps({k: v for k, v in comparisons.items() if k.startswith("v41")}, indent=1))


if __name__ == "__main__":
    main()
