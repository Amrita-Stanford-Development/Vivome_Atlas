"""The lymph node reference's locked test, PXD042367's tonsil niches, its scoring
(research/benchmark/protocol-ln-pxd042367.md, rules 7 and 8), once.

    python -m benchmark.ln_heldout_score --rehearse     # on the intake's rehearsal, any time
    python -m benchmark.ln_heldout_score                # unsealing only, once; refuses a second run

Primary (rule 7): S = P(B cell group) - P(T cell group) from the fused
best-guess probabilities; AUROC of S, B-zone regions over T-zone regions, with
a one-sided permutation p (10,000 permutations, seed 0, not blocked: one
section). Pass if p < 0.05.

Secondary (rule 8): each region's argmax group, answers and abstention per
zone, germinal centre against mantle zone, and the epithelium regions'
reference similarity (AUROC, lymphoid regions over epithelium) and abstention.

Writes research/benchmark/heldout/pxd042367/ (summary.json, scores.csv), or,
rehearsing, research/benchmark/heldout/rehearsals/pxd042367.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from benchmark.heldout_score import auroc_with_p
from benchmark.ln_heldout_intake import REPO, SET, out_dir

STATEMENT = ("An internal held-out test of the lymph node reference on laser-microdissected tonsil micro-regions (mixtures "
             "of the cells in 4,000 square micrometres), never external validation and never a single-cell accuracy. Tonsil "
             "is a secondary lymphoid organ but not a lymph node; every region comes from one section of one donor; the "
             "development set PXD047762 comes from the same lab and may share tonsils.")


def score(directory: Path) -> tuple[dict, pd.DataFrame]:
    labels = pd.read_csv(directory / "label_map.csv", keep_default_na=False)
    pred = pd.read_csv(directory / "ln_pred.csv", keep_default_na=False)
    saved = np.load(directory / "ln_probs.npz", allow_pickle=True)
    probs, names, hierarchy = saved["probs"], list(saved["class_names"]), json.loads(str(saved["hierarchy"]))
    if pred["cell_id"].astype(str).tolist() != labels["cell_id"].astype(str).tolist():
        raise SystemExit("the predictions are not in label-map order")
    groups = sorted({hierarchy[c]["group"] for c in names})
    G = np.stack([probs[:, [i for i, c in enumerate(names) if hierarchy[c]["group"] == g]].sum(1) for g in groups], axis=1)
    called = np.array(groups)[G.argmax(1)]
    s = G[:, groups.index("B cell")] - G[:, groups.index("T cell")]
    zone, reg = labels["group"].to_numpy(), labels["region"].to_numpy()
    scores = pd.DataFrame({"cell_id": labels["cell_id"], "region": reg, "zone": zone, "called": called, "s": s,
                           "reference_similarity": pred["reference_similarity"], "label": pred["label"],
                           "level": pred["label_level"], "abstained": pred["abstained"].astype(str) == "True",
                           "best_guess": pred["best_guess"]})
    out = {"protocol": "research/benchmark/protocol-ln-pxd042367.md", "set": SET, "statement": STATEMENT,
           "regions_by_zone": pd.Series(zone).value_counts().to_dict()}
    bt = np.isin(zone, ["B zone", "T zone"])
    if (zone == "B zone").sum() < 3 or (zone == "T zone").sum() < 3 or bt.sum() < 20:
        out["primary"] = {"void": "too few B-zone or T-zone regions (rule 7)"}
        return out, scores
    auc, p = auroc_with_p(s[bt], zone[bt] == "B zone")
    out["primary"] = {"auroc_b_over_t": round(auc, 4), "p": p, "passed": bool(p < 0.05),
                      "b_zone": int((zone == "B zone").sum()), "t_zone": int((zone == "T zone").sum())}
    out["argmax_group"] = pd.crosstab(pd.Series(reg, name="region"), pd.Series(called, name="called")).to_dict()
    out["answers"] = {z: {"regions": int((zone == z).sum()), "abstained": round(100 * float(scores[zone == z]["abstained"].mean()), 2),
                          "levels": scores[(zone == z) & ~scores["abstained"]]["level"].value_counts().to_dict()}
                      for z in sorted(set(zone))}
    gc, mz = reg == "germinal centre", reg == "mantle zone"
    if gc.sum() and mz.sum():
        out["germinal_centre_vs_mantle"] = {"mean_p_b_gc": round(float(G[gc, groups.index("B cell")].mean()), 4),
                                            "mean_p_b_mantle": round(float(G[mz, groups.index("B cell")].mean()), 4)}
    epi = zone == "epithelium"
    if epi.sum():
        sim = scores["reference_similarity"].astype(float).to_numpy()
        out["epithelium"] = {"regions": int(epi.sum()), "abstained": round(100 * float(scores[epi]["abstained"].mean()), 2),
                             "auroc_similarity_lymphoid_over_epithelium": round(float(roc_auc_score(bt[bt | epi], sim[bt | epi])), 4)}
    path = directory / "baselines.json"  # benchmark/organ_baselines.py, run after the intake (rule 9)
    out["baselines"] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
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
    if not args.rehearse and not (directory / "baselines.json").exists():
        raise SystemExit("run the baselines first: python -m benchmark.organ_baselines ln (rule 9)")
    out, scores = score(directory)
    if args.rehearse:
        out["rehearsal"] = json.loads((directory / "labels.json").read_text(encoding="utf-8")).get("source")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((json.dumps(out, indent=2, default=str) + "\n").encode("utf-8"))
    if not args.rehearse:
        scores.to_csv(target.parent / "scores.csv", index=False, lineterminator="\n")
    print(json.dumps(out.get("primary"), indent=1, default=str), json.dumps(out.get("epithelium"), default=str))


if __name__ == "__main__":
    main()
