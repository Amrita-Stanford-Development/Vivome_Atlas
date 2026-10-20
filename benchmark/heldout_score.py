"""The internal held-out test, step 4: the scoring, once per set
(research/benchmark/protocol-heldout.md, "Statistics" and each set's section).
Written and rehearsed before any held-out file was opened.

Inputs: benchmark/heldout_intake.py's outputs (label_map.csv, cell_ids.txt,
<model>_pred.csv, <model>_probs.npz) and, as secondary measures, the corrected
baselines' correlation and PCA kNN runs on the intake's matrix
(benchmark/baselines_corrected.py, dataset heldout_<set>, original labels).

Primary, per candidate (v4.1 the headline; every candidate reported):
- tian: S = P(CD8T) - P(CD4T) over the coarse types; for each (upload,
  patient, state) with a CD4 and a CD8 sample (replicates averaged), the pair
  is won when the CD8 sample's S is higher; exact one-sided sign test over
  the pairs; void with fewer than 5 pairs.
- pxd021882: S = P(B) - P(CD4T or CD8T); AUROC, B pools over T pools; void
  without a B or a T pool.
- pxd043355: reference similarity; AUROC, Jurkat over HeLa.
- pxd073250: reference similarity; AUROC, immune over keratinocyte.
- pxd046211: S = P(macrophage) - P(classical, intermediate, non-classical
  monocyte, monocyte); AUROC, PMA over untreated, both lines pooled.
AUROC p: one-sided, 10,000 label permutations, seed 0. Pass: p < 0.05.

    python -m benchmark.heldout_score SET --rehearse
    python -m benchmark.heldout_score SET            # Phase 3 only, once

Writes research/benchmark/heldout/<set>/ (summary.json, scores.csv); a
rehearsal writes benchmark/results/heldout_<set>_rehearsal/tables/ and its
summary to research/benchmark/heldout/rehearsals/<set>.json. The real scoring
refuses to run twice.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, rankdata

from benchmark import baselines_corrected, datasets
from benchmark.baselines_score import hierarchy
from benchmark.fulcher2026_score import COARSE
from benchmark.heldout_intake import MODELS, SETS, out_dir
from benchmark.khoury2026_embed import refuse_overrides
from benchmark.sorted_cd4cd8_intake import sha256

REPO = datasets.REPO
HEADLINE = "v41"
PERMUTATIONS, SEED, ALPHA, MIN_PAIRS = 10_000, 0, 0.05, 5
MONO_GROUP = ("classical monocyte", "intermediate monocyte", "non-classical monocyte", "monocyte")
CONTRASTS = {  # set -> (positive group, negative group, statistic)
    "pxd021882": ("B", "T", "score"),
    "pxd043355": ("Jurkat", "HeLa", "reference_similarity"),
    "pxd073250": ("immune", "keratinocyte", "reference_similarity"),
    "pxd046211": ("PMA", "untreated", "score"),
}
BASELINE_ARMS = {"correlation": "corr_unrestricted", "pca": "knn_unrestricted"}
STATEMENT = ("An internal held-out test, never external validation. Cell lines and tissue cells are outside the "
             "blood reference, and the acquisition differs from the reference's protein data.")


def tables_dir(name: str, rehearse: bool) -> Path:
    return out_dir(name, True) / "tables" if rehearse else REPO / "research" / "benchmark" / "heldout" / name


def rehearsal_record(name: str) -> Path:
    return REPO / "research" / "benchmark" / "heldout" / "rehearsals" / f"{name}.json"


# ---- statistics ----

def auroc_with_p(scores: np.ndarray, positive: np.ndarray, permutations: int = PERMUTATIONS,
                 seed: int = SEED) -> tuple[float, float]:
    """AUROC of `scores` for positive over negative (ties count half), and
    the one-sided permutation p: (1 + permutations at least as high) / (1 + permutations).
    A score that is not a finite number is refused: NaN fails every comparison,
    so p would come out at its smallest and the test would pass."""
    if not np.isfinite(np.asarray(scores, dtype=float)).all():
        raise ValueError("a score is not a finite number; the AUROC and its p are not computed")
    ranks = rankdata(scores)
    n1, n0 = int(positive.sum()), int((~positive).sum())
    scale = n1 * n0
    observed = (ranks[positive].sum() - n1 * (n1 + 1) / 2) / scale
    rng = np.random.default_rng(seed)
    at_least = 0
    for _ in range(permutations):
        pick = rng.permutation(len(ranks))[:n1]
        at_least += (ranks[pick].sum() - n1 * (n1 + 1) / 2) / scale >= observed - 1e-12
    return float(observed), (1 + at_least) / (1 + permutations)


def sign_test(won: int, n: int) -> float:
    return float(binomtest(won, n, 0.5, alternative="greater").pvalue)


def contrast_score(probs: np.ndarray, names: list[str], name: str) -> np.ndarray:
    coarse = np.array([COARSE.get(c, "other") for c in names])
    classes = np.array(names)
    if name == "tian":
        return probs[:, coarse == "CD8T"].sum(1) - probs[:, coarse == "CD4T"].sum(1)
    if name == "pxd021882":
        return probs[:, coarse == "B"].sum(1) - probs[:, np.isin(coarse, ("CD4T", "CD8T"))].sum(1)
    if name == "pxd046211":
        return probs[:, classes == "macrophage"].sum(1) - probs[:, np.isin(classes, MONO_GROUP)].sum(1)
    return np.full(len(probs), np.nan)


def tian_pairs(labels: pd.DataFrame, score: np.ndarray) -> tuple[list[dict], int]:
    frame = labels.assign(score=score)
    frame = frame[frame["scored"] & frame["group"].isin(("CD4", "CD8"))]
    means = frame.groupby(["upload", "patient", "state", "group"])["score"].mean().unstack("group")
    pairs = []
    for (upload, patient, state), row in means.iterrows():
        if pd.notna(row.get("CD4")) and pd.notna(row.get("CD8")):
            pairs.append({"upload": upload, "patient": patient, "state": state, "cd8_score": round(float(row["CD8"]), 6),
                          "cd4_score": round(float(row["CD4"]), 6), "won": bool(row["CD8"] > row["CD4"])})
    return pairs, sum(p["won"] for p in pairs)


def primary(name: str, labels: pd.DataFrame, pred: pd.DataFrame, score: np.ndarray) -> dict:
    if name == "tian":
        pairs, won = tian_pairs(labels, score)
        if len(pairs) < MIN_PAIRS:
            return {"statistic": "pairs won", "pairs": len(pairs), "won": won, "void": True,
                    "reason": f"fewer than {MIN_PAIRS} pairs", "pass": False, "pair_table": pairs}
        p = sign_test(won, len(pairs))
        return {"statistic": "pairs won", "pairs": len(pairs), "won": won, "p": round(p, 6), "void": False,
                "pass": bool(p < ALPHA), "pair_table": pairs}
    pos, neg, kind = CONTRASTS[name]
    scored = labels["scored"].to_numpy() & labels["group"].isin((pos, neg)).to_numpy()
    values = (score if kind == "score" else pred["reference_similarity"].to_numpy(dtype=float))[scored]
    positive = labels["group"].to_numpy()[scored] == pos
    if positive.all() or not positive.any():
        return {"statistic": f"AUROC, {pos} over {neg}", "void": True, "pass": False,
                "reason": f"no {neg if positive.all() else pos} samples", "n_positive": int(positive.sum()),
                "n_negative": int((~positive).sum())}
    auc, p = auroc_with_p(values, positive)
    return {"statistic": f"AUROC of {'S' if kind == 'score' else 'reference similarity'}, {pos} over {neg}",
            "auroc": round(auc, 4), "p": round(p, 6), "n_positive": int(positive.sum()),
            "n_negative": int((~positive).sum()), "void": False, "pass": bool(p < ALPHA)}


# ---- secondary ----

def answer_lineage(label: str, level: str, h: dict) -> str:
    if not label:
        return ""
    if level == "class":
        return h[label]["lineage"]
    if level == "group":
        return next((v["lineage"] for v in h.values() if v["group"] == label), "")
    return label


def names_t_lineage(label: str, level: str, h: dict) -> bool:
    if level == "class":
        return h[label]["group"] == "T cell"
    return (level == "group" and label == "T cell") or (level == "lineage" and label == "lymphoid")


def shares(values: pd.Series) -> dict:
    counts = values.value_counts()
    return {str(k): round(100 * v / counts.sum(), 1) for k, v in counts.items()}


def secondary(name: str, labels: pd.DataFrame, pred: pd.DataFrame, score: np.ndarray) -> dict:
    h = hierarchy()
    coarse = pred["best_guess"].map(lambda c: COARSE.get(c, "other") if c else "none")
    out = {"best_guess_coarse_pct_by_group": {g: shares(coarse[labels["group"].eq(g).to_numpy()])
                                              for g in labels["group"].unique()},
           "abstained_pct_by_group": {g: round(100 * float(pred.loc[labels["group"].eq(g).to_numpy(), "abstained"].mean()), 1)
                                      for g in labels["group"].unique()}}
    if name == "pxd043355":
        right = []
        for (_, row), group in zip(pred.iterrows(), labels["group"]):
            if group == "HeLa":
                right.append(bool(row["abstained"]))
            else:
                right.append(bool(row["abstained"]) or names_t_lineage(row["label"], row["label_level"], h))
        right = pd.Series(right)
        out["cell_line_rule_right_pct"] = {g: round(100 * float(right[labels["group"].eq(g).to_numpy()].mean()), 1)
                                           for g in ("Jurkat", "HeLa") if labels["group"].eq(g).any()}
    if name == "pxd073250":
        immune = labels["group"].eq("immune").to_numpy()
        guess_lineage = pred["best_guess"].map(lambda c: h[c]["lineage"] if c else "none")
        out["immune_best_guess_lineage_pct"] = shares(guess_lineage[immune])
    if name == "pxd046211":
        for line in sorted(labels["line"].unique()):
            keep = labels["line"].eq(line).to_numpy() & labels["group"].isin(("PMA", "untreated")).to_numpy()
            positive = labels["group"].to_numpy()[keep] == "PMA"
            if positive.any() and not positive.all():
                auc, p = auroc_with_p(score[keep], positive)
                out.setdefault("auroc_by_line", {})[line] = {"auroc": round(auc, 4), "p": round(p, 6)}
    return out


def baselines(name: str, rehearse: bool, labels: pd.DataFrame) -> dict:
    """Secondary: each available baseline run's coarse predictions per group."""
    dataset = f"heldout_{name}_rehearsal" if rehearse else f"heldout_{name}"
    found = {}
    for tool, column in BASELINE_ARMS.items():
        path = baselines_corrected.out_dir("original") / dataset / f"{tool}_seed0_pred.csv"
        if not path.exists():
            found[tool] = "missing"
            continue
        pred = pd.read_csv(path, keep_default_na=False, dtype={"cell_id": str}).set_index("cell_id")
        coarse = pred.reindex(labels["cell_id"])[column].map(lambda c: COARSE.get(c, "other"))
        found[tool] = {g: shares(coarse[labels["group"].eq(g).to_numpy()]) for g in labels["group"].unique()}
    return found


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("set", choices=SETS)
    parser.add_argument("--rehearse", action="store_true")
    args = parser.parse_args(argv)
    refuse_overrides()
    name, src = args.set, out_dir(args.set, args.rehearse)
    tables = tables_dir(name, args.rehearse)
    if not args.rehearse and (tables / "summary.json").exists():
        sys.exit(f"{tables / 'summary.json'} exists: each held-out set is scored once")
    intake = json.loads((src / "intake.json").read_text(encoding="utf-8"))
    labels = pd.read_csv(src / "label_map.csv", dtype={"cell_id": str, "sample": str, "patient": str, "state": str})
    labels["scored"] = labels["scored"].astype(str).eq("True")
    cell_ids = [c for c in (src / "cell_ids.txt").read_text(encoding="utf-8").splitlines() if c]
    if labels["cell_id"].tolist() != cell_ids:
        raise SystemExit("label_map.csv and cell_ids.txt disagree")
    summary = {"set": name, "protocol": "research/benchmark/protocol-heldout.md", "rehearsal": args.rehearse,
               "statement": STATEMENT, "headline": MODELS[HEADLINE],
               "label_map_sha256": sha256(src / "label_map.csv"), "intake_source": intake["source"],
               "groups": {g: int(n) for g, n in labels["group"].value_counts().items()}, "candidates": {}}
    per_cell = labels.copy()
    for key, version in MODELS.items():
        pred = pd.read_csv(src / f"{key}_pred.csv", keep_default_na=False, dtype={"cell_id": str})
        pred["abstained"] = pred["abstained"].astype(str).eq("True")
        if pred["cell_id"].tolist() != cell_ids:
            raise SystemExit(f"{key}_pred.csv rows are not in cell_ids.txt order")
        saved = np.load(src / f"{key}_probs.npz", allow_pickle=True)
        score = contrast_score(saved["probs"], [str(c) for c in saved["class_names"]], name)
        per_cell[f"{key}_score"] = np.round(score, 6)
        per_cell[f"{key}_similarity"] = pred["reference_similarity"].astype(float).round(6)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            summary["candidates"][version] = {"primary": primary(name, labels, pred, score),
                                              "secondary": secondary(name, labels, pred, score)}
    summary["baselines_secondary"] = baselines(name, args.rehearse, labels)
    tables.mkdir(parents=True, exist_ok=True)
    per_cell.to_csv(tables / "scores.csv", index=False, lineterminator="\n")
    (tables / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.rehearse:
        record = rehearsal_record(name)
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({v: c["primary"] if name != "tian" else {k: x for k, x in c["primary"].items() if k != "pair_table"}
                      for v, c in summary["candidates"].items()}, indent=1))


if __name__ == "__main__":
    main()
