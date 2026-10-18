"""The lung reference's locked test, MSV000094189, its scoring
(research/benchmark/protocol-lung-msv000094189.md, rules 7 and 8), once.

    python -m benchmark.lung_heldout_score --rehearse     # on the intake's rehearsal, any time
    python -m benchmark.lung_heldout_score                # unsealing only, once; refuses a second run

Primary (rule 7): each sample's P(lineage) is the sum of its fused best-guess
probabilities over the lineage's classes; the predicted lineage is the
argmax over the four; balanced accuracy over the true lineages with a
one-sided permutation p (10,000 permutations within donor, seed 0; the
colon scorer's balanced_with_p). A lineage with fewer than 3 samples is left
out; fewer than 3 lineages left is void. Pass if p < 0.05.

Secondary (rule 8): recall per lineage, the confusion table, answers and
abstention per lineage, correct when committed, balanced accuracy per donor.

Writes research/benchmark/heldout/msv000094189/ (summary.json, scores.csv), or,
rehearsing, research/benchmark/heldout/rehearsals/msv000094189.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

from benchmark.colon_heldout_score import PERMUTATIONS, balanced_with_p, correct_answer
from benchmark.lung_heldout_intake import LINEAGES, REPO, SET, out_dir

MIN_SAMPLES, MIN_LINEAGES = 3, 3
STATEMENT = ("An internal held-out test of the lung reference on pooled, FACS-sorted lineage proteomes, never external "
             "validation and never a single-cell accuracy. The donors are children (0 to 8 years) and the reference is "
             "adult; the development set MSV000094373 comes from the same lab and may share donors; the sorting antigens "
             "are measured in the proteomes.")


def score(directory: Path) -> tuple[dict, pd.DataFrame]:
    labels = pd.read_csv(directory / "label_map.csv", keep_default_na=False)
    pred = pd.read_csv(directory / "lung_pred.csv", keep_default_na=False)
    saved = np.load(directory / "lung_probs.npz", allow_pickle=True)
    probs, names, hierarchy = saved["probs"], list(saved["class_names"]), json.loads(str(saved["hierarchy"]))
    if pred["cell_id"].astype(str).tolist() != labels["cell_id"].astype(str).tolist():
        raise SystemExit("the predictions are not in label-map order")
    P = np.stack([probs[:, [i for i, c in enumerate(names) if hierarchy[c]["lineage"] == g]].sum(1) for g in LINEAGES], axis=1)
    called = np.array(LINEAGES)[P.argmax(1)]
    truth, donors = labels["group"].to_numpy(), labels["donor"].astype(str).to_numpy()
    counts = pd.Series(truth).value_counts()
    kept = [g for g in LINEAGES if counts.get(g, 0) >= MIN_SAMPLES]
    scores = pd.DataFrame({"cell_id": labels["cell_id"], "donor": donors, "lineage": truth, "called": called,
                           **{f"p_{g}": P[:, i] for i, g in enumerate(LINEAGES)}, "label": pred["label"],
                           "level": pred["label_level"], "abstained": pred["abstained"].astype(str) == "True",
                           "best_guess": pred["best_guess"]})
    out = {"protocol": "research/benchmark/protocol-lung-msv000094189.md", "set": SET, "statement": STATEMENT,
           "samples_by_lineage": counts.to_dict(), "lineages_scored": kept}
    if len(kept) < MIN_LINEAGES:
        out["primary"] = {"void": f"{len(kept)} lineages with at least {MIN_SAMPLES} samples (rule 7)"}
        return out, scores
    use = np.isin(truth, kept)
    ba, p = balanced_with_p(truth[use], called[use], donors[use])
    out["primary"] = {"balanced_accuracy": round(100 * ba, 2), "chance": round(100 / len(kept), 2), "p": p,
                      "permutations": PERMUTATIONS, "within_donor": len(set(donors)) > 1, "passed": p < 0.05,
                      "recall": {g: round(100 * float((called[truth == g] == g).mean()), 2) for g in kept}}
    out["confusion"] = pd.crosstab(pd.Series(truth, name="true"), pd.Series(called, name="called")).to_dict()
    out["by_donor"] = {d: round(100 * float(balanced_accuracy_score(truth[use & (donors == d)], called[use & (donors == d)])), 2)
                       for d in sorted(set(donors[use]))}
    answers = {}
    for g in kept:
        sub = scores[scores["lineage"] == g]
        com = sub[~sub["abstained"]]
        classes = [c for c in names if hierarchy[c]["lineage"] == g]
        answers[g] = {"samples": int(len(sub)), "abstained": round(100 * float(sub["abstained"].mean()), 2),
                      "levels": com["level"].value_counts().to_dict(),
                      "correct_when_committed": (round(100 * float(np.mean([correct_answer(lbl, lvl, classes, hierarchy)
                                                                            for lbl, lvl in zip(com["label"], com["level"])])), 2)
                                                 if len(com) else None)}
    out["answers"] = answers
    out["baselines"] = "run before scoring by benchmark/baselines_corrected.py (lung option); see research/organ-references.md, Lung"
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
    print(json.dumps(out.get("primary"), indent=1))


if __name__ == "__main__":
    main()
