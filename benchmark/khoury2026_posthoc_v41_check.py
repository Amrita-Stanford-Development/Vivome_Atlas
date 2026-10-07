"""v4.1, Phase B (research/todo.md, Track G): does the weight chosen on
Fulcher carry over to another lab's data? Khoury 2026, POST-HOC, once.

Khoury's labels were read at its one scoring under its protocol
(2026-10-03); its result in research/benchmark/khoury2026/ stays as scored.
The owner decided (2026-10-07) to use it once here as a cross-lab check of
the rule locked in Phase A (research/notebook-outputs/v41_pretest/
locked_rule.json). Khoury chooses nothing: the rule is locked before this
script reads a label, and the verdict below was written before Phase A ran.

Steps, in order:
1. Label-free: check that locked_rule.json is Phase A's choice
   (selection.json) and that research/notebooks/v41_pretest.py is the file
   whose sha256 Phase A recorded; record locked_rule.json's sha256.
2. Label-free: the four per-cell ingredients on Khoury's upload
   (datasets.load_khoury2026_upload) through the served all-cells bundle,
   as research/notebooks/v41_cache.py computes them; v4's rule from them must
   reproduce v4's saved Khoury best guesses (benchmark/results/khoury2026/
   v4_pred.csv) on every cell, or the run stops.
3. Scoring with khoury2026_score.py's metric code, class mapping and paired
   bootstrap (evaluate.paired_bootstrap_diff, 2,000 stratified resamples,
   seed 0): v4.1's best guess against v4's, v3.1's and every completed
   corrected baseline run and rule.

Verdict, fixed before Phase A ran:
- carries over: v4.1's balanced accuracy minus v4's is at least 0;
- does not carry over: it is below 0 (whether or not its CI excludes 0).
  Then v4.1 stops: no pre-registered evaluation, no service change.

Writes research/benchmark/khoury2026_posthoc_v41_check/: summary.json and
paired_bootstrap.csv.

    python -m benchmark.khoury2026_posthoc_v41_check      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
import warnings

import numpy as np
import pandas as pd

from benchmark import datasets
from benchmark import khoury2026_posthoc_score as posthoc
from benchmark import khoury2026_score as protocol
from benchmark.evaluate import paired_bootstrap_diff
from service.pipeline import ensemble, fusion, pipeline

REPO = datasets.REPO
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v41_core as core  # noqa: E402
from v41_cache import ingredients  # noqa: E402

PRETEST = REPO / "research" / "notebook-outputs" / "v41_pretest"
OUT = REPO / "research" / "benchmark" / "khoury2026_posthoc_v41_check"


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    warnings.simplefilter("ignore")
    locked = json.loads((PRETEST / "locked_rule.json").read_text())
    chosen = json.loads((PRETEST / "selection.json").read_text())["chosen"]
    if (locked["w_on"], locked["tau"]) != (chosen["w_on"], chosen["tau"]):
        raise SystemExit("locked_rule.json is not Phase A's choice")
    if json.loads((PRETEST / "rules.json").read_text())["script_sha256"] != sha256(REPO / "research" / "notebooks" / "v41_pretest.py"):
        raise SystemExit("research/notebooks/v41_pretest.py changed after Phase A ran")
    locked_sha = sha256(PRETEST / "locked_rule.json")
    if locked["is_v4"]:
        raise SystemExit("Phase A kept v4: nothing to check")

    src = protocol.sources(False)
    cell_ids = (src.out / "cell_ids.txt").read_text().splitlines()
    v4b = fusion.V4Bundle.load(require_evaluation=False)
    names = np.array(v4b.class_names)
    raw = datasets.load_khoury2026_upload()
    smoothed, aligned, _ = pipeline._prepare_query(v4b.feature_genes, raw)
    A = ingredients(v4b.answers.members, v4b.members, v4b.class_means, smoothed, aligned)
    counted = aligned.per_cell_observed_genes >= core.MIN_GENES
    agree = float((A["R"].argmax(1)[counted] == A["P31"].argmax(1)[counted]).mean()) if counted.any() else 0.0
    agv = np.full(len(cell_ids), agree)
    guess4 = names[core.rule(A, agv, core.V4["w_on"], core.V4["tau"]).argmax(1)]
    saved4 = protocol.read_v31_table(src.out / "v4_pred.csv")
    protocol.same_rows(saved4["cell_id"].tolist(), cell_ids, "v4_pred.csv")
    has_guess = saved4["best_guess"].to_numpy() != ""
    if not (guess4[has_guess] == saved4["best_guess"].to_numpy()[has_guess]).all():
        raise SystemExit("the cached ingredients do not reproduce v4's saved Khoury best guesses")
    guess41 = names[core.rule(A, agv, locked["w_on"], locked["tau"]).argmax(1)]
    v31 = protocol.read_v31_table(src.out / "v31_pred.csv")["best_guess"].to_numpy()
    corrected, excluded = posthoc.corrected_predictions(cell_ids)

    labels = datasets.load_khoury2026_labels(unseal=True)  # read at the 2026-10-03 scoring; post-hoc use
    protocol.same_rows(labels["cell_id"].tolist(), cell_ids, "labels")
    scored = labels["label"].isin(protocol.TYPES).to_numpy()
    true_type = labels["label"].to_numpy()[scored]
    _, _, lineage = protocol.reference_classes()
    scores = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for model, pred in (("v4.1", guess41), ("v4", guess4), ("v3.1", v31)):
            scores[model] = protocol.score(pred[scored], true_type, lineage)[0]
        pairs = [("v4", "v4", "best_guess", guess4), ("v3.1", "v3.1", "best_guess", v31)]
        pairs += [(family, model, rule, pred) for (family, model, _, rule), pred in corrected.items()]
        boot = []
        for family, model, rule, other in pairs:
            d = paired_bootstrap_diff(true_type, protocol.to_type(guess41[scored]), protocol.to_type(other[scored]))
            lo, hi = d["ci_95_pct"]
            boot.append({"comparison": f"v4.1 vs {family}", "model_b": model, "rule_b": rule,
                         "diff_bal_acc_pct": d["point_estimate_pct"], "ci_lo": lo, "ci_hi": hi,
                         "favours": "v4.1" if lo > 0 else model if hi < 0 else "neither"})
    boot = pd.DataFrame(boot)
    against_v4 = boot.iloc[0]
    verdict = "carries over" if against_v4["diff_bal_acc_pct"] >= 0 else "does not carry over"
    OUT.mkdir(parents=True, exist_ok=True)
    boot.to_csv(OUT / "paired_bootstrap.csv", index=False, float_format="%.4f", lineterminator="\n")
    summary = {
        "dataset": "Khoury 2026", "posthoc": True,
        "note": ("Post-hoc cross-lab check of the rule locked on Fulcher 2026 (Phase A). Khoury's labels were read at its "
                 "one scoring (2026-10-03); it chose nothing here. The protocol's result is research/benchmark/khoury2026/."),
        "locked_rule": locked, "locked_rule_sha256": locked_sha, "upload_agreement": round(agree, 4),
        "correlation_term": "used" if agree >= core.V4["agreement_threshold"] else "flat",
        "scores": {m: {k: round(float(v), 2) for k, v in s.items()} for m, s in scores.items()},
        "v41_minus_v4": {"point": round(float(against_v4["diff_bal_acc_pct"]), 2),
                         "ci_95": [round(float(against_v4["ci_lo"]), 2), round(float(against_v4["ci_hi"]), 2)]},
        "verdict": verdict, "excluded_runs": excluded,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", newline="\n")
    print(json.dumps(summary, indent=1))
    print(boot.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
