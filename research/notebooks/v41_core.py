"""v4.1 (Track G): the shared helpers of the pre-test (research/notebooks/
v41_cache.py, v41_pretest.py). Promoted from Phase 3c's exploration
(research/notebook-outputs/v4_phase3c/exploration.json), unchanged in what
they compute.

The cache holds, per cell, the four ingredients of v4's best guess, each
over the 22 reference classes:
- Ps: the class-balanced encoder on the smoothed query (v4's members);
- Pu: the same on the unsmoothed query;
- P31: v3.1's encoder probability (its own centroids), behind its answers;
- R: the masked Pearson correlation with the class-balanced RNA class means.
Every rule here recombines them in memory; nothing re-encodes a cell.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
CACHE = REPO.parent / "drive" / "Data" / "Results" / "Tier1_v31" / "V41" / "cache"
RECORD = REPO / "research" / "notebook-outputs" / "v41_pretest" / "cache_record.json"
MIN_GENES = 200
V4 = {"w_on": 0.7, "tau": 0.05, "smoothed_share": 0.5, "agreement_threshold": 0.4, "w_off": 0.7}
SCOPE2_PAIR = ("macrophage", "monocyte")


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(1, keepdims=True))
    return e / e.sum(1, keepdims=True)


def agreement(cells: pd.DataFrame, A: dict, key: str) -> np.ndarray:
    """Per cell, its upload's agreement (fusion.upload_agreement): the share of
    the upload's cells with at least MIN_GENES observed genes whose top class
    under R is v3.1's top class."""
    counted = (cells["observed_genes"] >= MIN_GENES).to_numpy()
    hit = (A["R"].argmax(1) == A["P31"].argmax(1)).astype(float)
    frame = pd.DataFrame({"g": cells[key].to_numpy(), "hit": np.where(counted, hit, np.nan)})
    return frame.groupby("g")["hit"].transform("mean").fillna(0.0).to_numpy()


def rule(A: dict, agv: np.ndarray, w_on: float, tau: float, smoothed_share: float = 0.5,
         agreement_threshold: float = 0.4, w_off: float = 0.7) -> np.ndarray:
    """v4's best-guess probability with the gate-on encoder weight and
    correlation temperature as parameters. The gate-off branch is v4's:
    w_off x the smoothed encoder + (1 - w_off) x a flat correlation term."""
    n = A["Ps"].shape[1]
    on = w_on * (smoothed_share * A["Ps"] + (1 - smoothed_share) * A["Pu"]) + (1 - w_on) * softmax(A["R"] / tau)
    off = w_off * A["Ps"] + (1 - w_off) / n
    return np.where((agv >= agreement_threshold)[:, None], on, off)


def per_upload(cells: pd.DataFrame, guess: np.ndarray) -> pd.DataFrame:
    """Each upload's best-guess balanced accuracy (accuracy when one class), as
    v4_phase3c.per_upload_balanced computes it."""
    d = pd.DataFrame({"upload": cells["upload"], "group": cells["group"], "source": cells["source"],
                      "true": cells["true"], "g": guess})

    def one(u):
        if u["true"].nunique() > 1:
            return 100 * balanced_accuracy_score(u["true"], u["g"])
        return 100 * float((u["true"] == u["g"]).mean())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        acc = d.groupby("upload").apply(one, include_groups=False)
    return pd.concat([acc.rename("acc"), d.groupby("upload")[["group", "source"]].first()], axis=1)


def suite_scores(cells: pd.DataFrame, guess: np.ndarray) -> dict:
    """The calibration suite's mean per-upload balanced accuracy, overall and
    per scenario group (absolute)."""
    p = per_upload(cells, guess)
    cal = p[p["source"] == "calib"]
    return {"overall": float(cal["acc"].mean()), **{g: float(v) for g, v in cal.groupby("group")["acc"].mean().items()}}


def robustness(cells: pd.DataFrame, guess: np.ndarray, base_guess: np.ndarray, n_uploads: int = 35,
               draws: int = 4000, seed: int = 0) -> dict:
    """Over every single-type calibration upload (the suite's and the extra
    ones): the mean and worst per-class difference from base_guess, and p_fail,
    the share of resampled n_uploads-upload single-type suites more than 3
    points below it."""
    rng = np.random.default_rng(seed)
    pa, pb = per_upload(cells, guess), per_upload(cells, base_guess)
    d = (pa["acc"] - pb["acc"])[pa["group"] == "single"]
    cls = cells[cells["group"] == "single"].groupby("upload")["true"].first().reindex(d.index)
    by = {k: v.to_numpy() for k, v in d.groupby(cls)}
    ks = list(by)
    sims = np.array([np.mean([rng.choice(by[k]) for k in rng.choice(ks, n_uploads)]) for _ in range(draws)])
    per_class = pd.Series({k: v.mean() for k, v in by.items()})
    return {"single_class_mean": float(per_class.mean()), "single_worst_class": float(per_class.min()),
            "single_p_fail": float((sims < -3).mean())}


def answers(cells: pd.DataFrame, sets: list, names: np.ndarray, hier: dict, guess: "np.ndarray | None",
            only: np.ndarray) -> dict:
    """Coverage, committed share and correct-when-committed, with the guess
    joined beside v3.1's in v3.1's non-empty sets (guess None: v3.1's own)."""
    sys.path.insert(0, str(REPO / "research" / "notebooks"))
    import v4_calibration as phase3
    from service.pipeline import ensemble
    hold = cells["abstain_reason"].fillna("").to_numpy() == "outside_supported_region"
    truth = cells["true"].to_numpy()
    cov, com, cor = [], [], []
    for i in np.flatnonzero(only):
        s = set(sets[i])
        if s and guess is not None:
            s.add(int(guess[i]))
        cov.append(truth[i] in s)
        r = ensemble.resolve(sorted(names[list(s)]), hier) if s and not hold[i] else None
        com.append(r is not None)
        cor.append(r is not None and phase3.correct_at_level(r[0], r[1], names[truth[i]], hier))
    cov, com, cor = map(np.array, (cov, com, cor))
    return {"coverage": 100 * cov.mean(), "committed": 100 * com.mean(), "correct_when_committed": 100 * cor[com].mean()}


def dev_figures(dev: pd.DataFrame, P: np.ndarray, names: np.ndarray) -> dict:
    """The development figures of a best-guess probability P (rows = dev cache
    rows): Fulcher's six-type balanced accuracy and per-type recall, PBMC240's
    lymphoid recall, both SCoPE2 versions unrestricted and restricted to
    macrophage/monocyte, and the out-of-reference AUROC (Fulcher's maximum
    probability against Furtwangler's)."""
    from benchmark import datasets
    from benchmark import fulcher2026_score as fulcher
    meta = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    lineage = meta.groupby("class_name")["lineage"].first().to_dict()
    guess = names[P.argmax(1)]
    pair = [int(np.flatnonzero(names == c)[0]) for c in SCOPE2_PAIR]
    restricted = np.array(SCOPE2_PAIR)[P[:, pair].argmax(1)]
    out = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = (dev["dataset"] == "fulcher2026").to_numpy()
        truth = dev.loc[f, "label"].to_numpy()
        scored = truth != datasets.FULCHER2026["unscored_label"]
        types = np.array([fulcher.COARSE.get(c, "other") for c in guess[f]])
        out["fulcher"] = 100 * balanced_accuracy_score(truth[scored], types[scored])
        for t in datasets.FULCHER2026["types"]:
            out[f"fulcher_{t}"] = 100 * float((types[scored][truth[scored] == t] == t).mean())
        p = ((dev["dataset"] == "pbmc240") & (dev["label"] == "lymphoid")).to_numpy()
        out["pbmc240_lymphoid"] = 100 * float(np.mean([lineage[c] == "lymphoid" for c in guess[p]]))
        for name in ("scope2", "scope2_reprocessed"):
            s = (dev["dataset"] == name).to_numpy()
            out[f"{name}_unrestricted"] = 100 * balanced_accuracy_score(dev.loc[s, "label"], guess[s])
            out[f"{name}_restricted"] = 100 * balanced_accuracy_score(dev.loc[s, "label"], restricted[s])
        fu = (dev["dataset"] == "furtwangler2025").to_numpy()
        out["auroc"] = roc_auc_score(np.r_[np.ones(f.sum()), np.zeros(fu.sum())], np.r_[P[f].max(1), P[fu].max(1)])
    return {k: float(v) for k, v in out.items()}


def load() -> tuple:
    """(calibration cells, their arrays, development cells, their arrays),
    calibration cells limited to those with at least MIN_GENES observed
    genes, after checking every cache file against the cache record."""
    import hashlib
    record = json.loads(RECORD.read_text())
    for name, digest in record["sha256"].items():
        if hashlib.sha256((CACHE / name).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{CACHE / name} does not match {RECORD}")
    calib = pd.read_csv(CACHE / "calib_cells.csv.gz", keep_default_na=False)
    a = dict(np.load(CACHE / "calib_arrays.npz"))
    keep = (calib["observed_genes"] >= MIN_GENES).to_numpy()
    dev = pd.read_csv(CACHE / "dev_cells.csv.gz", keep_default_na=False, dtype={"cell_id": str})
    d = dict(np.load(CACHE / "dev_arrays.npz"))
    return calib[keep].reset_index(drop=True), {k: v[keep] for k, v in a.items()}, dev, d
