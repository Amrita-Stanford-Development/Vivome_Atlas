"""v4.2 (research/todo.md, release 0.5.0): does the served model hold on
another lab's data? Khoury 2026, POST-HOC, once.

Khoury's labels were read at its one scoring under its protocol
(2026-10-03); its result in research/benchmark/khoury2026/ stays as scored.
The owner decided (2026-10-17, "go ahead and finish whatever is remaining",
on a list naming this check) to use it once more here, for v4.2: v4.1 with
protein class means from sorted immune cells (Rieckmann et al. 2017) in the
correlation term of the best guess, for the types they cover. v4.2 is
already served (release 0.5.0); its release rule rested on development data
and the internal held-out test. This check cannot change that release. It
reports whether the served best guess loses anything on a second lab's
single-cell proteomics, which v4.2's protein means were not chosen on.
Khoury chooses nothing.

Verdict, fixed here before the labels are read:
- holds: v4.2's balanced accuracy minus v4.1's has a 95% interval that
  reaches 0 or above (no clear loss);
- falls short: the interval lies wholly below 0. Then the model card and
  the site say so beside v4.2's development gain.

Steps, in order:
1. Label-free. v4 and v4.1's best guesses from their per-cell ingredients on
   Khoury's upload, through the served all-cells bundles, as
   research/notebooks/v41_cache.py computes them, each rule taking the
   upload's agreement. v4's must reproduce v4's saved Khoury best guesses
   (benchmark/results/khoury2026/v4_pred.csv) on every cell that has one,
   or the run stops. v4.2's best guesses are the service's own response
   (fusion.project, a protein upload), as served.
2. Scoring with khoury2026_score.py's metric code and class mapping. v4.1's
   scores must equal the v4.1 check's
   (research/benchmark/khoury2026_posthoc_v41_check/summary.json) within
   0.01, or the run stops.
3. The paired bootstrap (evaluate.paired_bootstrap_diff, 2,000 stratified
   resamples, seed 0): v4.2's best guess against v4.1's, v4's, v3.1's and
   every completed corrected baseline run and rule.

Writes research/benchmark/khoury2026_posthoc_v42_check/: summary.json and
paired_bootstrap.csv.

    python -m benchmark.khoury2026_posthoc_v42_check      # from the repository root
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
from service import config
from service.pipeline import fusion, pipeline

REPO = datasets.REPO
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v41_core as core  # noqa: E402
from v41_cache import ingredients  # noqa: E402

OUT = REPO / "research" / "benchmark" / "khoury2026_posthoc_v42_check"
V41_CHECK = REPO / "research" / "benchmark" / "khoury2026_posthoc_v41_check" / "summary.json"


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guesses(bundle, smoothed, aligned, names, n_cells) -> tuple[np.ndarray, float]:
    """The bundle's rule on every cell from its ingredients, with the upload's agreement."""
    A = ingredients(bundle.answers.members, bundle.members, bundle.class_means, smoothed, aligned)
    counted = aligned.per_cell_observed_genes >= core.MIN_GENES
    agree = float((A["R"].argmax(1)[counted] == A["P31"].argmax(1)[counted]).mean()) if counted.any() else 0.0
    w_on = fusion.encoder_weight_where_used(bundle)
    P = core.rule(A, np.full(n_cells, agree), w_on, bundle.correlation_temperature, bundle.smoothed_share,
                  bundle.agreement_threshold, bundle.fusion_weight)
    return names[P.argmax(1)], agree


def main() -> None:
    warnings.simplefilter("ignore")
    src = protocol.sources(False)
    cell_ids = (src.out / "cell_ids.txt").read_text().splitlines()
    bundles = {"v4": fusion.V4Bundle.load(require_evaluation=False, version="v4"),
               "v4.1": fusion.V4Bundle.load(require_evaluation=False, version="v4.1")}
    v42 = fusion.V4Bundle.load(require_evaluation=True, version="v4.2")
    names = np.array(bundles["v4"].class_names)
    raw = datasets.load_khoury2026_upload()
    smoothed, aligned, _ = pipeline._prepare_query(bundles["v4"].feature_genes, raw)
    guess, agreement = {}, {}
    for m, b in bundles.items():
        guess[m], agreement[m] = guesses(b, smoothed, aligned, names, len(cell_ids))

    # 1. label-free: v4 reproduced; v4.2 as served
    saved4 = protocol.read_v31_table(src.out / "v4_pred.csv")
    protocol.same_rows(saved4["cell_id"].tolist(), cell_ids, "v4_pred.csv")
    has = saved4["best_guess"].to_numpy() != ""
    if not (guess["v4"][has] == saved4["best_guess"].to_numpy()[has]).all():
        raise SystemExit("STOP: the ingredients do not reproduce v4's saved Khoury best guesses")
    response = fusion.project(v42, raw, False, None, modality="prot")
    protocol.same_rows([c["cell_id"] for c in response["cells"]], cell_ids, "v4.2's response")
    guess["v4.2"] = np.array([(c.get("best_guess") or {}).get("label") or "" for c in response["cells"]])
    rule42 = response["best_guess_rule"]
    agreement["v4.2"] = float(rule42["agreement"])
    v31 = protocol.read_v31_table(src.out / "v31_pred.csv")["best_guess"].to_numpy()
    corrected, excluded = posthoc.corrected_predictions(cell_ids)

    # 2. scoring
    labels = datasets.load_khoury2026_labels(unseal=True)  # read at the 2026-10-03 scoring; post-hoc use
    protocol.same_rows(labels["cell_id"].tolist(), cell_ids, "labels")
    scored = labels["label"].isin(protocol.TYPES).to_numpy()
    true_type = labels["label"].to_numpy()[scored]
    _, _, lineage = protocol.reference_classes()
    scores, confusion = {}, {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for m, pred in (("v4.2", guess["v4.2"]), ("v4.1", guess["v4.1"]), ("v4", guess["v4"]), ("v3.1", v31)):
            row, _, conf = protocol.score(pred[scored], true_type, lineage)
            scores[m] = {k: round(float(v), 2) for k, v in row.items()}
            confusion[m] = {t: {p: int(conf.loc[t, p]) for p in conf.columns} for t in conf.index}
    recorded = json.loads(V41_CHECK.read_text())["scores"]["v4.1"]
    gaps = {k: round(scores["v4.1"][k] - v, 4) for k, v in recorded.items()}
    if any(abs(g) > 0.01 for g in gaps.values()):
        raise SystemExit(f"STOP: v4.1's Khoury scores differ from the v4.1 check's: {gaps}")

    # 3. paired bootstrap
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        pairs = [("v4.1", "v4.1", "best_guess", guess["v4.1"]), ("v4", "v4", "best_guess", guess["v4"]),
                 ("v3.1", "v3.1", "best_guess", v31)]
        pairs += [(family, model, rule, pred) for (family, model, _, rule), pred in corrected.items()]
        boot = []
        for family, model, rule, other in pairs:
            d = paired_bootstrap_diff(true_type, protocol.to_type(guess["v4.2"][scored]), protocol.to_type(other[scored]))
            lo, hi = d["ci_95_pct"]
            boot.append({"comparison": f"v4.2 vs {family}", "model_b": model, "rule_b": rule,
                         "diff_bal_acc_pct": d["point_estimate_pct"], "ci_lo": lo, "ci_hi": hi,
                         "favours": "v4.2" if lo > 0 else model if hi < 0 else "neither"})
    boot = pd.DataFrame(boot)
    against = boot.iloc[0]
    verdict = "holds" if against["ci_hi"] >= 0 else "falls short"
    OUT.mkdir(parents=True, exist_ok=True)
    boot.to_csv(OUT / "paired_bootstrap.csv", index=False, float_format="%.4f", lineterminator="\n")
    summary = {
        "dataset": "Khoury 2026", "posthoc": True,
        "note": ("Post-hoc check of v4.2, the served model (protein class means in the best guess's correlation term). "
                 "Khoury's labels were read at its one scoring (2026-10-03); it chose nothing here, and this check "
                 "does not change release 0.5.0."),
        "script_sha256": sha256(REPO / "benchmark" / "khoury2026_posthoc_v42_check.py"),
        "spec_v42_sha256": sha256(config.V42_SPEC_PATH),
        "upload_agreement": {m: round(a, 4) for m, a in agreement.items()},
        "correlation_term": {**{m: "used" if agreement[m] >= b.agreement_threshold else "flat" for m, b in bundles.items()},
                             "v4.2": rule42["correlation_term"]},
        "scores": scores, "confusion_type_by_predicted": confusion, "v41_reproduced": gaps,
        "v42_minus_v41": {"point": round(float(against["diff_bal_acc_pct"]), 2),
                          "ci_95": [round(float(against["ci_lo"]), 2), round(float(against["ci_hi"]), 2)]},
        "verdict": verdict, "excluded_runs": excluded,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", newline="\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "confusion_type_by_predicted"}, indent=1))
    print(json.dumps(summary["confusion_type_by_predicted"]["v4.2"], indent=0))
    print(boot.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
