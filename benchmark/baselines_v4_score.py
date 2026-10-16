"""Track G, Phase 4 (v4) and v4.1's Phase E: v4 or v4.1 as served
(baselines_v4.py) against the corrected baselines and against v3.1 (and,
for v4.1, against v4), on the development datasets SCoPE2 (published
matrix), PBMC240, Fulcher 2026 and SCoPE2 reprocessed (its labels from the
experimental design).

Scored exactly as baselines_corrected_score.py scores v3.1: baselines_score's
functions, mapping and bootstrap (evaluate.paired_bootstrap_diff, 2,000
stratified resamples, seed 0), pointed at the corrected runs, with the
model's per-cell tables in v3.1's place. The existing tables are not
rewritten.

A model against v3.1 (or v4) is cell-paired on the same metric as each
dataset's table: balanced accuracy on SCoPE2 (22 classes unrestricted, 2
restricted) and on Fulcher's six types, lymphoid recall on PBMC240's weakly
labelled lymphoid cells.

The checks, from the v4 plan the owner approved on 2026-10-04 (research/
todo.md, Track G): no paired interval favours v3.1 on any development
dataset, and correct-when-committed falls by at most 2 points. For v4.1 the
same checks against v4 are reported too.

Writes research/benchmark/v4_development/ (v4) or v41_development/ (v4.1):
- scope2.csv, pbmc240.csv, fulcher2026.csv: v3.1's rows (and v4's, for
  v4.1) and the model's, with the metrics of the baseline tables in
  research/benchmark/baselines_corrected/;
- scope2_reprocessed.csv: every completed corrected run and the same models,
  both regimes, as scope2.csv's metrics;
- confident.csv: committed share and correct when committed, per model;
- paired_bootstrap_<model>.csv: the model against every corrected baseline
  run and rule;
- paired_bootstrap_<model>_vs_v31.csv (and, for v4.1, _vs_v4.csv);
- checks.json.

    python -m benchmark.baselines_v4_score                    # v4, from the repository root
    python -m benchmark.baselines_v4_score --version v4.1     # v4.1
    python -m benchmark.baselines_v4_score --version v4.2     # v4.2, beside v4.1 (release 0.5.0)
"""
from __future__ import annotations

import argparse
import json
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from benchmark import baselines_corrected_score as corrected
from benchmark import baselines_inputs, datasets
from benchmark import baselines_score as original
from benchmark import fulcher2026_score as protocol
from benchmark.evaluate import paired_bootstrap_diff, score

CORRECT_DROP_MAX = 2.0


@dataclass(frozen=True)
class Model:
    key: str  # its per-cell tables' name (baselines_v4.py)
    name: str  # in the favours columns
    label: str  # its rows' tool name
    out: str  # output folder under research/benchmark/
    beside: tuple = field(default=())  # other models in its tables and bootstraps, besides v3.1


V4 = "v4 (served)"
MODELS = {"v4": Model("v4", "v4", V4, "v4_development"),
          "v4.1": Model("v41", "v4.1", "v4.1 (served)", "v41_development", beside=(("v4", "v4", V4),)),
          "v4.2": Model("v42", "v4.2", "v4.2 (served)", "v42_development", beside=(("v41", "v4.1", "v4.1 (served)"),))}
BUILDERS = (("scope2", lambda paired: original.scope2(paired)), ("pbmc240", lambda paired: original.pbmc240()),
            ("fulcher2026", lambda paired: original.fulcher(paired)))


def run_builders(key: str, label: "str | None" = None) -> tuple[dict, list, list]:
    """baselines_score's builders over the corrected runs, with the tables of
    `key` ("v31", "v4" or "v41") in v3.1's place, under `label`. Returns the
    per-seed tables, the confident answers and the paired bootstraps against
    every baseline."""
    read = original.read_v31
    saved = (original.runs, original.RULES, original.BASELINE_RULES, original.V31, original.read_v31)
    original.runs, original.RULES, original.BASELINE_RULES = corrected.runs, corrected.RULES, corrected.BASELINE_RULES
    if key != "v31":
        original.V31 = label
        original.read_v31 = lambda dataset, name="v31": read(dataset, name.replace("v31", key))
    try:
        per_seed, confident, paired = {}, [], []
        for name, build in BUILDERS:
            table, conf = build(paired)
            per_seed[name] = table
            confident.append({"model": key, **conf})
        return per_seed, confident, paired
    finally:
        original.runs, original.RULES, original.BASELINE_RULES, original.V31, original.read_v31 = saved


def scope2_reprocessed(m: Model, paired: list, against: dict) -> tuple[pd.DataFrame, list[dict]]:
    """baselines_score.scope2's rows and bootstraps on the reprocessed SCoPE2,
    with v3.1, the models beside m, and m; confident answers judged as
    confident_scope2 judges them. against: {other key: rows list}."""
    truth = datasets.load_scope2_reprocessed_labels()["label"].to_numpy()
    rows, preds = [], {}
    order = (("v31", original.V31),) + tuple((k, label) for k, _, label in m.beside) + ((m.key, m.label),)
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
        models = {(key, regime): original.read_v31("scope2_reprocessed", f"{key}{suffix}")
                  for key, _ in order for regime, suffix in (("unrestricted", ""), ("restricted", "_restricted"))}
        for key, label in order:
            for regime in ("unrestricted", "restricted"):
                rows.append({"tool": label, "seed": 0, "rule": corrected.RULES["best_guess"], "regime": regime,
                             **score(truth, models[(key, regime)]["best_guess"].to_numpy(), 22 if regime == "unrestricted" else 2)})
        for (tool, seed, rule, regime), baseline in preds.items():
            paired.append({"dataset": f"SCoPE2 reprocessed {regime}", "baseline": tool, "seed": seed, "baseline_rule": rule,
                           **paired_bootstrap_diff(truth, models[(m.key, regime)]["best_guess"].to_numpy(), baseline)})
        for other, rows_ in against.items():
            for regime in ("unrestricted", "restricted"):
                rows_.append({"dataset": f"SCoPE2 reprocessed {regime}", "metric": "balanced accuracy",
                              **paired_bootstrap_diff(truth, models[(m.key, regime)]["best_guess"].to_numpy(),
                                                      models[(other, regime)]["best_guess"].to_numpy())})
    confident = [{"model": key, **{**original.confident_scope2(models[(key, "unrestricted")], truth),
                                   "dataset": "SCoPE2 reprocessed"}} for key, _ in order]
    return pd.DataFrame(rows), confident


def model_against(key: str, other: str) -> list[dict]:
    """`key`'s best guess against `other`'s, cell-paired, on SCoPE2 (both
    regimes), PBMC240 and Fulcher."""
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # predicted classes absent from the truth
        truth = pd.read_csv(baselines_inputs.D / "prot_meta.csv")["class_name"].to_numpy()
        for regime, suffix in (("unrestricted", ""), ("restricted", "_restricted")):
            a = original.read_v31("scope2", f"{key}{suffix}")["best_guess"].to_numpy()
            b = original.read_v31("scope2", f"{other}{suffix}")["best_guess"].to_numpy()
            rows.append({"dataset": f"SCoPE2 {regime}", "metric": "balanced accuracy", **paired_bootstrap_diff(truth, a, b)})
        meta = pd.read_csv(baselines_inputs.D / "pbmc_meta.csv")
        _, _, lineage = protocol.reference_classes()
        lymphoid = (meta["weak_lineage"] == "lymphoid").to_numpy()
        lin = {m: np.array([lineage.get(c, "none") for c in original.read_v31("pbmc240", m)["best_guess"]])[lymphoid]
               for m in (key, other)}
        rows.append({"dataset": "PBMC240", "metric": "lymphoid recall",
                     **paired_bootstrap_diff(meta["weak_lineage"].to_numpy()[lymphoid], lin[key], lin[other])})
        labels = datasets.load_fulcher2026_labels()
        scored = (labels["label"] != datasets.FULCHER2026["unscored_label"]).to_numpy()
        coarse = {m: np.array([protocol.COARSE.get(c, "other") for c in original.read_v31("fulcher2026", m)["best_guess"].to_numpy()[scored]])
                  for m in (key, other)}
        rows.append({"dataset": "Fulcher 2026", "metric": "balanced accuracy, six types",
                     **paired_bootstrap_diff(labels["label"].to_numpy()[scored], coarse[key], coarse[other])})
    return rows


def interval_table(paired: list[dict], ahead: str, behind: str) -> pd.DataFrame:
    table = pd.DataFrame([{**{k: v for k, v in p.items() if k != "ci_95_pct"}, "ci_lo": p["ci_95_pct"][0],
                           "ci_hi": p["ci_95_pct"][1]} for p in paired])
    table["favours"] = np.where(table["ci_lo"] > 0, ahead, np.where(table["ci_hi"] < 0, behind, "neither"))
    return table


def checks_against(against: pd.DataFrame, confident: pd.DataFrame, m: Model, other: str, other_name: str) -> dict:
    by = confident.set_index(["dataset", "model"])["correct_when_committed_pct"]
    drops = {d: round(float(by[(d, other)] - by[(d, m.key)]), 3) for d in confident["dataset"].unique()}
    out = {f"no_interval_favours_{other}": bool((against["favours"] != other_name).all()),
           "correct_when_committed_drop_at_most_2": bool(all(d <= CORRECT_DROP_MAX for d in drops.values())),
           "correct_when_committed_drop": drops}
    out["passed"] = out[f"no_interval_favours_{other}"] and out["correct_when_committed_drop_at_most_2"]
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=tuple(MODELS), default="v4")
    m = MODELS[parser.parse_args().version]
    out = datasets.REPO / "research" / "benchmark" / m.out
    out.mkdir(parents=True, exist_ok=True)
    tables31, confident31, _ = run_builders("v31")
    beside = [run_builders(k, label) for k, _, label in m.beside]
    tables, confident_m, paired = run_builders(m.key, m.label)
    for name in tables:
        keep = lambda t, tool: t[t["tool"] == tool]  # noqa: E731
        parts = [keep(tables31[name], original.V31)] + [keep(b[0][name], label) for b, (_, _, label) in zip(beside, m.beside)]
        pd.concat(parts + [keep(tables[name], m.label)], ignore_index=True).to_csv(out / f"{name}.csv", index=False, lineterminator="\n")
    against = {"v31": model_against(m.key, "v31"), **{k: model_against(m.key, k) for k, _, _ in m.beside}}
    reprocessed, confident_reprocessed = scope2_reprocessed(m, paired, against)
    reprocessed.to_csv(out / "scope2_reprocessed.csv", index=False, lineterminator="\n")
    confident = pd.DataFrame(confident31 + [c for b in beside for c in b[1]] + confident_m + confident_reprocessed)
    confident.to_csv(out / "confident.csv", index=False, lineterminator="\n")
    baselines = interval_table(paired, m.name, "baseline")
    baselines.to_csv(out / f"paired_bootstrap_{m.key}.csv", index=False, lineterminator="\n")
    vs31 = interval_table(against["v31"], m.name, "v3.1")
    vs31.to_csv(out / f"paired_bootstrap_{m.key}_vs_v31.csv", index=False, lineterminator="\n")
    checks = checks_against(vs31, confident, m, "v31", "v3.1")
    if m.key == "v4":  # the Phase 4 record's own keys, unchanged
        checks = {"no_interval_favours_v31": checks["no_interval_favours_v31"], **{k: v for k, v in checks.items() if k != "no_interval_favours_v31"}}
    for k, name, _ in m.beside:
        table = interval_table(against[k], m.name, name)
        table.to_csv(out / f"paired_bootstrap_{m.key}_vs_{k}.csv", index=False, lineterminator="\n")
        checks = {"against_v31": checks, f"against_{k}": checks_against(table, confident, m, k, name)}
        print(table.round(2).to_string(index=False))
    (out / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", newline="\n")
    print(vs31.round(2).to_string(index=False))
    print(confident.round(2).to_string(index=False))
    print(baselines.groupby(["dataset", "baseline", "baseline_rule"]).favours.value_counts().unstack(fill_value=0))
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
