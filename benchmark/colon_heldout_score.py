"""The colon reference's locked test, PXD052341, step 5 of its unsealing
(research/benchmark/protocol-colon-pxd052341.md, rules 7 and 8), scored once.

    python -m benchmark.colon_heldout_score --rehearse     # on the intake's rehearsal, any time
    python -m benchmark.colon_heldout_score                # unsealing only, once; refuses a second run

Primary (rule 7): each sample's P(group) is the sum of its fused best-guess
probabilities over the group's reference classes; the predicted group is the
argmax over the five groups; the measure is balanced accuracy over the true
groups, with a one-sided permutation p (10,000 permutations of the true groups
within donor, seed 0). A group with fewer than 3 samples is left out; fewer
than 3 groups left is void. Pass if p < 0.05.

Secondary (rule 8), reported and never deciding: crypt bottom against upper
crypt (AUROC of P(crypt bottom) - P(upper crypt), with its permutation p),
each group's answers and abstention, correct when committed at the stated
level, the confusion table, and single-contour samples when the deposit has
them.

Writes research/benchmark/heldout/pxd052341/ (summary.json, scores.csv), or,
rehearsing, research/benchmark/heldout/rehearsals/pxd052341.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

from benchmark.colon_heldout_intake import GROUPS, REPO, SET, group_classes, out_dir
from benchmark.heldout_score import auroc_with_p

PERMUTATIONS, SEED, MIN_SAMPLES, MIN_GROUPS = 10_000, 0, 3, 3
STATEMENT = ("An internal held-out test of the colon reference on pooled cell-type proteomes (about 500 image-classified "
             "cells per sample), never external validation and never a single-cell accuracy. The set comes from the same lab "
             "and chemistry as the development sets PXD057118 and PXD046999; the reference is Tabula Sapiens normal colon "
             "from other donors.")


def balanced_with_p(truth: np.ndarray, pred: np.ndarray, donors: np.ndarray) -> tuple[float, float]:
    observed = balanced_accuracy_score(truth, pred)
    rng = np.random.default_rng(SEED)
    at_least = 0
    for _ in range(PERMUTATIONS):
        shuffled = truth.copy()
        for d in np.unique(donors):
            idx = np.flatnonzero(donors == d)
            shuffled[idx] = truth[rng.permutation(idx)]
        at_least += balanced_accuracy_score(shuffled, pred) >= observed - 1e-12
    return float(observed), (1 + at_least) / (1 + PERMUTATIONS)


def correct_answer(label: str, level: str, classes: list[str], hierarchy: dict) -> bool:
    if level == "class":
        return label in classes
    return label in {hierarchy[c][level] for c in classes}


def score(directory: Path) -> tuple[dict, pd.DataFrame]:
    labels = pd.read_csv(directory / "label_map.csv", keep_default_na=False)
    labels = labels[labels["pooled"].astype(str) == "True"].reset_index(drop=True)
    pred = pd.read_csv(directory / "li_pred.csv", keep_default_na=False)
    saved = np.load(directory / "li_probs.npz", allow_pickle=True)
    probs, names, hierarchy = saved["probs"], list(saved["class_names"]), json.loads(str(saved["hierarchy"]))
    if pred["cell_id"].astype(str).tolist() != labels["cell_id"].astype(str).tolist():
        raise SystemExit("the predictions are not in label-map order")
    positions = group_classes(names, hierarchy)
    groups = list(GROUPS)
    P = np.stack([probs[:, positions[g]].sum(1) for g in groups], axis=1)
    called = np.array(groups)[P.argmax(1)]
    truth = labels["group"].to_numpy()
    donors = labels["donor"].astype(str).to_numpy()
    counts = pd.Series(truth).value_counts()
    kept = [g for g in groups if counts.get(g, 0) >= MIN_SAMPLES]
    scores = pd.DataFrame({"cell_id": labels["cell_id"], "donor": donors, "group": truth, "called": called,
                           **{f"p_{g}": P[:, i] for i, g in enumerate(groups)},
                           "label": pred["label"], "level": pred["label_level"], "abstained": pred["abstained"].astype(str) == "True",
                           "best_guess": pred["best_guess"]})
    out = {"protocol": "research/benchmark/protocol-colon-pxd052341.md", "set": SET, "statement": STATEMENT,
           "samples_by_group": counts.to_dict(), "groups_scored": kept}
    if len(kept) < MIN_GROUPS:
        out["primary"] = {"void": f"{len(kept)} groups with at least {MIN_SAMPLES} samples (rule 7)"}
        return out, scores
    use = np.isin(truth, kept)
    ba, p = balanced_with_p(truth[use], called[use], donors[use])
    out["primary"] = {"balanced_accuracy": round(100 * ba, 2), "chance": round(100 / len(kept), 2), "p": p,
                      "permutations": PERMUTATIONS, "within_donor": len(set(donors)) > 1, "passed": p < 0.05,
                      "recall": {g: round(100 * float((called[truth == g] == g).mean()), 2) for g in kept}}
    cb, uc = truth == "crypt bottom", truth == "upper crypt"
    if cb.sum() and uc.sum():
        s = P[:, groups.index("crypt bottom")] - P[:, groups.index("upper crypt")]
        both = cb | uc
        auc, p2 = auroc_with_p(s[both], cb[both])
        out["crypt_bottom_over_upper"] = {"auroc": round(auc, 4), "p": p2}
    answers = {}
    for g in kept:
        sub = scores[scores["group"] == g]
        com = sub[~sub["abstained"]]
        classes = [names[i] for i in positions[g]]
        answers[g] = {"samples": int(len(sub)), "abstained": round(100 * float(sub["abstained"].mean()), 2),
                      "levels": com["level"].value_counts().to_dict(),
                      "correct_when_committed": (round(100 * float(np.mean([correct_answer(l, v, classes, hierarchy)
                                                                            for l, v in zip(com["label"], com["level"])])), 2)
                                                 if len(com) else None)}
    out["answers"] = answers
    out["confusion"] = pd.crosstab(pd.Series(truth, name="true"), pd.Series(called, name="called")).to_dict()
    single = directory / "single"
    if (single / "li_probs.npz").exists():
        s_lab = pd.read_csv(directory / "label_map.csv", keep_default_na=False)
        s_lab = s_lab[s_lab["pooled"].astype(str) != "True"].reset_index(drop=True)
        sp_ = np.load(single / "li_probs.npz", allow_pickle=True)["probs"]
        Ps = np.stack([sp_[:, positions[g]].sum(1) for g in groups], axis=1)
        s_called, s_truth = np.array(groups)[Ps.argmax(1)], s_lab["group"].to_numpy()
        ba_s, p_s = balanced_with_p(s_truth, s_called, s_lab["donor"].astype(str).to_numpy())
        out["single_contour"] = {"samples": int(len(s_truth)), "balanced_accuracy": round(100 * ba_s, 2), "p": p_s}
    out["baselines"] = "run before scoring by benchmark/baselines_corrected.py (colon option); see research/organ-references.md, Stage 4"
    return out, scores


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearse", action="store_true")
    args = parser.parse_args(argv)
    directory = out_dir(args.rehearse)
    if args.rehearse:
        target = REPO / "research" / "benchmark" / "heldout" / "rehearsals" / f"{SET}.json"
    else:
        target = REPO / "research" / "benchmark" / "heldout" / SET / "summary.json"
        if target.exists():
            raise SystemExit("the locked test was scored; it is scored once")
    out, scores = score(directory)
    if args.rehearse:
        out["rehearsal"] = json.loads((directory / "labels.json").read_text(encoding="utf-8")).get("source")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((json.dumps(out, indent=2, default=str) + "\n").encode("utf-8"))
    if not args.rehearse:
        scores.to_csv(target.parent / "scores.csv", index=False, lineterminator="\n")
    print(json.dumps(out.get("primary"), indent=1), json.dumps(out.get("crypt_bottom_over_upper")))


if __name__ == "__main__":
    main()
