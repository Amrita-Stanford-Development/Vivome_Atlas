"""Track G, Phase 4: v4 as served (baselines_v4.py) against the corrected
baselines and against v3.1, on the development datasets SCoPE2 (published
matrix), PBMC240, Fulcher 2026 and SCoPE2 reprocessed (its labels from the
experimental design; the corrected baselines' rows once their runs exist,
benchmark/baselines_corrected_queue.sh scope2_reprocessed).

Scored exactly as baselines_corrected_score.py scores v3.1: baselines_score's
functions, mapping and bootstrap (evaluate.paired_bootstrap_diff, 2,000
stratified resamples, seed 0), pointed at the corrected runs, with v4's
per-cell tables in v3.1's place. The existing tables are not rewritten.

v4 against v3.1 is cell-paired on the same metric as each dataset's table:
balanced accuracy on SCoPE2 (22 classes unrestricted, 2 restricted) and on
Fulcher's six types, lymphoid recall on PBMC240's weakly labelled lymphoid
cells.

The Phase 4 checks, from the v4 plan the owner approved on 2026-10-04
(research/todo.md, Track G) and fixed before this scorer ran: no paired
interval favours v3.1 on any development dataset, and correct-when-committed
falls by at most 2 points.

Writes research/benchmark/v4_development/:
- scope2.csv, pbmc240.csv, fulcher2026.csv: v3.1's and v4's rows, with the
  metrics of the baseline tables in research/benchmark/baselines_corrected/;
- scope2_reprocessed.csv: every completed corrected run, v3.1 and v4, both
  regimes, as scope2.csv's metrics;
- confident.csv: committed share and correct when committed, v3.1 and v4;
- paired_bootstrap_v4.csv: v4 against every corrected baseline run and rule;
- paired_bootstrap_v4_vs_v31.csv: v4 against v3.1;
- checks.json: the Phase 4 checks.

    python -m benchmark.baselines_v4_score      # from the repository root
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from benchmark import baselines_corrected_score as corrected
from benchmark import baselines_inputs, datasets
from benchmark import baselines_score as original
from benchmark import fulcher2026_score as protocol
from benchmark.evaluate import paired_bootstrap_diff, score

OUT = datasets.REPO / "research" / "benchmark" / "v4_development"
V4 = "v4 (served)"
CORRECT_DROP_MAX = 2.0
BUILDERS = (("scope2", lambda paired: original.scope2(paired)), ("pbmc240", lambda paired: original.pbmc240()),
            ("fulcher2026", lambda paired: original.fulcher(paired)))


def run_builders(model: str) -> tuple[dict, list, list]:
    """baselines_score's builders over the corrected runs, with `model`'s
    tables ("v31" or "v4") in v3.1's place. Returns the per-seed tables, the
    confident answers and the paired bootstraps against every baseline."""
    read = original.read_v31
    saved = (original.runs, original.RULES, original.BASELINE_RULES, original.V31, original.read_v31)
    original.runs, original.RULES, original.BASELINE_RULES = corrected.runs, corrected.RULES, corrected.BASELINE_RULES
    if model == "v4":
        original.V31 = V4
        original.read_v31 = lambda dataset, name="v31": read(dataset, name.replace("v31", "v4"))
    try:
        per_seed, confident, paired = {}, [], []
        for name, build in BUILDERS:
            table, conf = build(paired)
            per_seed[name] = table
            confident.append({"model": model, **conf})
        return per_seed, confident, paired
    finally:
        original.runs, original.RULES, original.BASELINE_RULES, original.V31, original.read_v31 = saved


def scope2_reprocessed(paired: list, against: list) -> tuple[pd.DataFrame, list[dict]]:
    """baselines_score.scope2's rows and bootstraps on the reprocessed SCoPE2,
    with v3.1 and v4; confident answers judged as confident_scope2 judges them."""
    truth = datasets.load_scope2_reprocessed_labels()["label"].to_numpy()
    rows, preds = [], {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for tool, seed, pred in corrected.runs("scope2_reprocessed"):
            for rule in corrected.BASELINE_RULES:
                for regime in ("unrestricted", "restricted"):
                    column = f"{rule}_{regime}"
                    if column in pred:
                        rows.append({"tool": tool, "seed": seed, "rule": corrected.RULES[rule], "regime": regime,
                                     **score(truth, pred[column].to_numpy(), 22 if regime == "unrestricted" else 2)})
                        preds[(tool, seed, corrected.RULES[rule], regime)] = pred[column].to_numpy()
        models = {(label, regime): original.read_v31("scope2_reprocessed", f"{m}{suffix}")
                  for m, label in (("v31", original.V31), ("v4", V4))
                  for regime, suffix in (("unrestricted", ""), ("restricted", "_restricted"))}
        for (label, regime), table in models.items():
            rows.append({"tool": label, "seed": 0, "rule": corrected.RULES["best_guess"], "regime": regime,
                         **score(truth, table["best_guess"].to_numpy(), 22 if regime == "unrestricted" else 2)})
        for (tool, seed, rule, regime), baseline in preds.items():
            paired.append({"dataset": f"SCoPE2 reprocessed {regime}", "baseline": tool, "seed": seed, "baseline_rule": rule,
                           **paired_bootstrap_diff(truth, models[(V4, regime)]["best_guess"].to_numpy(), baseline)})
        for regime in ("unrestricted", "restricted"):
            against.append({"dataset": f"SCoPE2 reprocessed {regime}", "metric": "balanced accuracy",
                            **paired_bootstrap_diff(truth, models[(V4, regime)]["best_guess"].to_numpy(),
                                                    models[(original.V31, regime)]["best_guess"].to_numpy())})
    confident = [{"model": m, **{**original.confident_scope2(models[(label, "unrestricted")], truth),
                                 "dataset": "SCoPE2 reprocessed"}}
                 for m, label in (("v31", original.V31), ("v4", V4))]
    return pd.DataFrame(rows), confident


def v4_against_v31() -> list[dict]:
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # predicted classes absent from the truth
        truth = pd.read_csv(baselines_inputs.D / "prot_meta.csv")["class_name"].to_numpy()
        for regime, suffix in (("unrestricted", ""), ("restricted", "_restricted")):
            a = original.read_v31("scope2", f"v4{suffix}")["best_guess"].to_numpy()
            b = original.read_v31("scope2", f"v31{suffix}")["best_guess"].to_numpy()
            rows.append({"dataset": f"SCoPE2 {regime}", "metric": "balanced accuracy", **paired_bootstrap_diff(truth, a, b)})
        meta = pd.read_csv(baselines_inputs.D / "pbmc_meta.csv")
        _, _, lineage = protocol.reference_classes()
        lymphoid = (meta["weak_lineage"] == "lymphoid").to_numpy()
        lin = {m: np.array([lineage.get(c, "none") for c in original.read_v31("pbmc240", m)["best_guess"]])[lymphoid]
               for m in ("v4", "v31")}
        rows.append({"dataset": "PBMC240", "metric": "lymphoid recall",
                     **paired_bootstrap_diff(meta["weak_lineage"].to_numpy()[lymphoid], lin["v4"], lin["v31"])})
        labels = datasets.load_fulcher2026_labels()
        scored = (labels["label"] != datasets.FULCHER2026["unscored_label"]).to_numpy()
        coarse = {m: np.array([protocol.COARSE.get(c, "other") for c in original.read_v31("fulcher2026", m)["best_guess"].to_numpy()[scored]])
                  for m in ("v4", "v31")}
        rows.append({"dataset": "Fulcher 2026", "metric": "balanced accuracy, six types",
                     **paired_bootstrap_diff(labels["label"].to_numpy()[scored], coarse["v4"], coarse["v31"])})
    return rows


def interval_table(paired: list[dict], ahead: str, behind: str) -> pd.DataFrame:
    table = pd.DataFrame([{**{k: v for k, v in p.items() if k != "ci_95_pct"}, "ci_lo": p["ci_95_pct"][0],
                           "ci_hi": p["ci_95_pct"][1]} for p in paired])
    table["favours"] = np.where(table["ci_lo"] > 0, ahead, np.where(table["ci_hi"] < 0, behind, "neither"))
    return table


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tables31, confident31, _ = run_builders("v31")
    tables4, confident4, paired4 = run_builders("v4")
    for name in tables4:
        keep = lambda t, tool: t[t["tool"] == tool]  # noqa: E731
        both = pd.concat([keep(tables31[name], original.V31), keep(tables4[name], V4)], ignore_index=True)
        both.to_csv(OUT / f"{name}.csv", index=False, lineterminator="\n")
    against_rows = v4_against_v31()
    reprocessed, confident_reprocessed = scope2_reprocessed(paired4, against_rows)
    reprocessed.to_csv(OUT / "scope2_reprocessed.csv", index=False, lineterminator="\n")
    confident = pd.DataFrame(confident31 + confident4 + confident_reprocessed)
    confident.to_csv(OUT / "confident.csv", index=False, lineterminator="\n")
    baselines = interval_table(paired4, "v4", "baseline")
    baselines.to_csv(OUT / "paired_bootstrap_v4.csv", index=False, lineterminator="\n")
    against = interval_table(against_rows, "v4", "v3.1")
    against.to_csv(OUT / "paired_bootstrap_v4_vs_v31.csv", index=False, lineterminator="\n")
    by = confident.set_index(["dataset", "model"])["correct_when_committed_pct"]
    drops = {d: round(float(by[(d, "v31")] - by[(d, "v4")]), 3) for d in confident["dataset"].unique()}
    checks = {"no_interval_favours_v31": bool((against["favours"] != "v3.1").all()),
              "correct_when_committed_drop_at_most_2": bool(all(d <= CORRECT_DROP_MAX for d in drops.values())),
              "correct_when_committed_drop": drops}
    checks["passed"] = checks["no_interval_favours_v31"] and checks["correct_when_committed_drop_at_most_2"]
    (OUT / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", newline="\n")
    print(against.round(2).to_string(index=False))
    print(confident.round(2).to_string(index=False))
    print(baselines.groupby(["dataset", "baseline", "baseline_rule"]).favours.value_counts().unstack(fill_value=0))
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
