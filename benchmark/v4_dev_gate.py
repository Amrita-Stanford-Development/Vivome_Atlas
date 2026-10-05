"""Track G's gate for v4 as served (service/pipeline/fusion.py), on the
development datasets (SCoPE2's published matrix, PBMC240, Fulcher 2026 and
Furtwangler 2025):

- the best guess: the service's, for every cell, must equal an independent
  recomputation from the member encoders on at least 99.5% of each dataset's
  cells. The recomputation applies the agreement gate (the mixed smoothed and
  unsmoothed encoder probability fused with the correlation term, or the
  smoothed encoder with a flat correlation term), and the gate's decision
  must match the response's;
- the answers are v3.1's: every committed cell's set equals v3.1's
  conformal set with v3.1's best guess and the fused one joined, and every
  out-of-distribution or low-coverage abstention is v3.1's;
- each figure within 0.5 points of Phase 3c's record
  (research/notebook-outputs/v4_phase3c/development.json), and the
  out-of-distribution AUROC within 0.01.

A miss means stop and diagnose; nothing is tuned to pass. Khoury 2026 is not
read. It loads the bundle with require_evaluation=False, so it can run before
the evaluation is recorded.

Writes research/benchmark/v4_dev_gate.json.

    python -m benchmark.v4_dev_gate      # from the repository root
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from benchmark import baselines_v31, datasets
from benchmark import fulcher2026_score as fulcher
from service.pipeline import abstention, alignment, ensemble, fusion, gene_ids, pipeline

REPO = datasets.REPO
PHASE3C = REPO / "research" / "notebook-outputs" / "v4_phase3c"
RECORD = REPO / "research" / "benchmark" / "v4_dev_gate.json"
TOLERANCE, AUROC_TOLERANCE, MIN_AGREEMENT = 0.5, 0.01, 99.5
V31_ONLY = {abstention.AbstainReason.OUT_OF_DISTRIBUTION.value, abstention.AbstainReason.LOW_COVERAGE.value}


def uploads():
    pbmc = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    yield ("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()),
           pbmc, pbmc["cell_id"].astype(str).tolist())
    yield "scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv"), None
    yield "fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels(), None
    yield "furtwangler2025", datasets.load_furtwangler2025_upload(), None, None


def independent_guess(bundle: "fusion.V4Bundle", smoothed: np.ndarray, values: np.ndarray, mask: np.ndarray,
                      counted: np.ndarray) -> tuple[np.ndarray, bool]:
    """The best-guess probability and whether the correlation term was used,
    recomputed here from the encoders and numpy rather than through
    fusion.best_guess_probabilities."""
    def mean_softmax(members, query):
        out = []
        for m in members:
            z = np.asarray(m.encoder_handle.encode(query, mask), dtype=np.float64)
            z /= np.linalg.norm(z, axis=1, keepdims=True)
            c = m.centroids / np.linalg.norm(m.centroids, axis=1, keepdims=True)
            logits = z @ c.T / m.temperature
            e = np.exp(logits - logits.max(1, keepdims=True))
            out.append(e / e.sum(1, keepdims=True))
        return np.mean(out, axis=0)
    s, w = bundle.smoothed_share, bundle.fusion_weight
    on = mean_softmax(bundle.members, smoothed)
    v31_top = mean_softmax(bundle.answers.members, smoothed).argmax(1)
    pearson = np.array([[np.corrcoef(values[i, mask[i] > 0], bundle.class_means[k, mask[i] > 0])[0, 1]
                         for k in range(len(bundle.class_means))] for i in range(len(values))])
    pearson = np.nan_to_num(pearson, nan=0.0)
    used = bool(counted.any() and (pearson.argmax(1)[counted] == v31_top[counted]).mean() >= bundle.agreement_threshold)
    if not used:
        return w * on + (1 - w) / on.shape[1], False
    r = pearson / bundle.correlation_temperature
    e = np.exp(r - r.max(1, keepdims=True))
    return w * (s * on + (1 - s) * mean_softmax(bundle.members, values)) + (1 - w) * e / e.sum(1, keepdims=True), True


def figures(name: str, pred: np.ndarray, info, lineage) -> dict:
    if name == "fulcher2026":
        truth = info["label"].to_numpy()
        scored = truth != datasets.FULCHER2026["unscored_label"]
        types = np.array([fulcher.COARSE.get(c, "other") for c in pred])
        return {"balanced_accuracy_6_types": 100 * balanced_accuracy_score(truth[scored], types[scored])}
    if name == "pbmc240":
        truth = info["weak_lineage"].to_numpy()
        lin = np.array([lineage[c] for c in pred])
        return {"lymphoid_recall": 100 * float((lin[truth == "lymphoid"] == "lymphoid").mean())}
    if name == "scope2":
        return {"balanced_accuracy_unrestricted": 100 * balanced_accuracy_score(info["class_name"].to_numpy(), pred)}
    return {}


def run_gate(bundle: "fusion.V4Bundle") -> dict:
    development = json.loads((PHASE3C / "development.json").read_text())
    meta = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    lineage = meta.groupby("class_name")["lineage"].first().to_dict()
    names = bundle.class_names
    v31 = bundle.answers
    floor = int(bundle.spec["preprocessing"]["min_observed_genes"])
    record = {"smoothed_share": bundle.smoothed_share, "agreement_threshold": bundle.agreement_threshold, "datasets": {}}
    misses, max_prob = [], {}
    for name, raw, info, keep in uploads():
        smoothed, aligned, scale = pipeline._prepare_query(bundle.feature_genes, raw)
        resolution = gene_ids.resolve_identifiers(raw.gene_names)
        served = fusion.project_prepared(bundle, smoothed, aligned, scale, resolution, False, bundle.components)
        answers = ensemble.project_prepared(v31, smoothed, aligned, scale, resolution, False, v31.components)
        G, used = independent_guess(bundle, smoothed, aligned.values, aligned.mask, aligned.per_cell_observed_genes >= floor)
        guess = G.argmax(1)
        if used != (served["best_guess_rule"]["correlation_term"] == "used"):
            misses.append(f"{name}: the agreement gate decided differently ({served['best_guess_rule']})")
        # v3.1's sets with v3.1's best guess and the recomputed one joined, built by v3.1's calibrator
        Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in v31.members]
        P = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, v31.members)])
        space = v31.components.label_space.estimate(None, names, False)
        sets = v31.components.calibrator.calibrate(P, None, space, guess_positions=guess).label_sets
        rows = np.arange(len(served["cells"]))
        if keep is not None:
            at = {c["cell_id"]: i for i, c in enumerate(served["cells"])}
            rows = np.array([at[c] for c in keep])
        cells = [served["cells"][i] for i in rows]
        pred = np.array([c.get("best_guess", {}).get("label", "") for c in cells])
        mine = np.array(names)[guess[rows]]
        has_guess = np.array(["best_guess" in c for c in cells])
        agreement = 100 * float((pred[has_guess] == mine[has_guess]).mean())
        set_mismatch = sum(1 for i in rows if not served["cells"][i]["abstained"]
                           and sorted(served["cells"][i]["label_set"]) != sorted(names[k] for k in sets[i]))
        reason_mismatch = sum(1 for a, b in zip(served["cells"], answers["cells"])
                              if (a.get("abstain_reason") in V31_ONLY or b.get("abstain_reason") in V31_ONLY)
                              and a.get("abstain_reason") != b.get("abstain_reason"))
        entry = {"cells": len(rows), "upload_agreement": served["best_guess_rule"]["agreement"],
                 "correlation_term": served["best_guess_rule"]["correlation_term"],
                 "best_guess_agreement_pct": round(agreement, 3),
                 "committed_sets_not_v31_with_the_guess": set_mismatch, "v31_abstentions_differing": reason_mismatch, "figures": []}
        if agreement < MIN_AGREEMENT:
            misses.append(f"{name}: best guesses agree on {agreement:.2f}% of cells (at least {MIN_AGREEMENT})")
        if set_mismatch or reason_mismatch:
            misses.append(f"{name}: {set_mismatch} committed sets and {reason_mismatch} abstentions are not v3.1's")
        max_prob[name] = np.array([c.get("best_guess", {}).get("probability", np.nan) for c in cells])
        target = development[name]["v4"]
        for figure, value in figures(name, pred, info, lineage).items():
            ok = abs(value - target[figure]) <= TOLERANCE
            entry["figures"].append({"figure": figure, "v4": round(value, 2), "phase3c": target[figure], "ok": ok})
            if not ok:
                misses.append(f"{name} {figure}: {value:.2f} vs {target[figure]} (tolerance {TOLERANCE})")
        record["datasets"][name] = entry
    a, b = max_prob["fulcher2026"], max_prob["furtwangler2025"]
    auroc = float(roc_auc_score(np.r_[np.ones(len(a)), np.zeros(len(b))], np.r_[a, b]))
    target = development["out_of_reference_auroc"]["v4"]
    record["out_of_reference_auroc"] = {"v4": round(auroc, 4), "phase3c": target, "ok": abs(auroc - target) <= AUROC_TOLERANCE}
    if not record["out_of_reference_auroc"]["ok"]:
        misses.append(f"AUROC {auroc:.4f} vs {target} (tolerance {AUROC_TOLERANCE})")
    record.update(misses=misses, passed=not misses, tolerance=TOLERANCE, auroc_tolerance=AUROC_TOLERANCE,
                  min_agreement_pct=MIN_AGREEMENT, khoury2026="not read")
    return record


def main() -> None:
    record = run_gate(fusion.V4Bundle.load(require_evaluation=False))
    RECORD.write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    print(json.dumps(record, indent=2))
    if record["misses"]:
        raise SystemExit("v4 gate: MISS")


if __name__ == "__main__":
    main()
