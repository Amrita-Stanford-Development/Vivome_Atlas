"""The sorted CD4/CD8 test, step 3: the scoring, the only step that reads the
sorting labels (research/benchmark/protocol-sorted-cd4cd8.md: rules 1 and 4 to
7, the decision rules, amendment 1). Written and rehearsed on Fulcher 2026
before any sorted data exists; it reuses benchmark/evaluate.py unchanged.

Inputs:
- benchmark/sorted_cd4cd8_intake.py's outputs: intake.json, cell_ids.txt,
  v31_pred.csv, v41_pred.csv, v42_pred.csv, v52_pred.csv;
- the corrected baselines on this dataset (benchmark/baselines_corrected.py),
  with the original reference labels and with v5.2's (--labels v52), the arms
  scored on Khoury post-hoc: correlation; PCA, Harmony, scANVI, MaxFuse and
  scGLUE with the shared kNN rule; scANVI's classifier, MaxFuse's matching and
  Seurat's transfer; three seeds where the tool has them;
- the labels, stored apart on receipt: a CSV with cell_id, type (CD4T, CD8T,
  NK, B, monocyte, DC, or empty) and unit (single, bulk or unsorted), and its
  sha256 as recorded then.

Scored, from each model's best guess (rule 6), on the single cells of the
sorted types only (amendment 1); bulk units apart; unsorted cells never:
- primary: balanced accuracy over the sorted types, predictions mapped by
  rule 5 (fulcher2026_score.COARSE; anything else, or a type not sorted, is
  "other" and wrong);
- secondary: per-type recall, and the CD4/CD8 confusion among sorted T cells;
- answers, for v3.1, v4.1, v4.2 and v5.2: coverage (the set holds a class of the
  cell's type), committed share, and correct when committed at the stated
  level (NB2's hierarchy, as Khoury's scorer judges it);
- paired bootstraps (rule 7): each model against every baseline run on its own
  reference labels, and v5.2 and v4.2 against v4.1 (balanced accuracy, and CD8 T
  recall on the CD8 T cells; v4.2's are reported, with no decision rule).

Decision rules, read here as written, with every run of every arm:
- "beats the corrected baselines": a lead of at least 3 points and a 95% CI
  above zero against every run;
- "v5.2 improves CD4/CD8 over v4.1": CD8 T recall above v4.1's with its CI
  above zero, and balanced accuracy at most 1 point below v4.1's.
If v5.2-label baselines are missing at unsealing, v5.2 is compared with v4.1
only (rule 4).

    python -m benchmark.sorted_cd4cd8_score --unseal LABELS.csv --sha256 HEX   # once
    python -m benchmark.sorted_cd4cd8_score --rehearse                          # Fulcher 2026

Writes research/benchmark/sorted_cd4cd8/ (results/sorted_cd4cd8_rehearsal/tables/
when rehearsing): per_run_scores.csv, cd4_cd8_confusion.csv, answers.json,
paired_bootstrap.csv, summary.json (with the verdicts). The real scoring
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
from sklearn.metrics import balanced_accuracy_score

from benchmark import baselines_corrected, datasets
from benchmark import fulcher2026_score as fulcher
from benchmark.baselines_score import hierarchy
from benchmark.evaluate import paired_bootstrap_diff
from benchmark.khoury2026_embed import refuse_overrides
from benchmark.sorted_cd4cd8_intake import MODELS, out_dir, sha256

REPO = datasets.REPO
COARSE = fulcher.COARSE  # rule 5
ALL_TYPES = ("CD4T", "CD8T", "NK", "B", "monocyte", "DC")
OURS = {"v31": "v3.1", "v41": "v4.1", "v42": "v4.2", "v52": "v5.2"}
OWN_LABELS = {"v4.1": "original", "v4.2": "original", "v5.2": "v52"}  # rule 4: baselines on each model's own labels
# (tool, rule) -> (prediction column, seeds): Khoury's post-hoc arms
ARMS = {("correlation", "correlation"): ("corr", (0,)), ("pca", "shared_knn"): ("knn", (0,)),
        ("harmony", "shared_knn"): ("knn", (0, 1, 2)), ("scanvi", "native"): ("clf", (0, 1, 2)),
        ("scanvi", "shared_knn"): ("knn", (0, 1, 2)), ("maxfuse", "shared_knn"): ("knn", (0, 1, 2)),
        ("maxfuse", "matching"): ("match", (0, 1, 2)), ("scglue", "shared_knn"): ("knn", (0, 1, 2)),
        ("seurat", "native"): ("native", (0,))}
LEAD_POINTS, BA_SLACK_POINTS = 3.0, 1.0
MIN_SORTED_CELLS = 50  # "A qualifying dataset": CD4 T and CD8 T, at least 50 single cells each after QC
# "Caveats, stated alongside every result" (the protocol's three, in its words)
CAVEATS = (
    "Batch can stand in for the label: sorted populations are often prepared or run separately, and the amendment "
    "at intake records how this dataset did it.",
    "The panel decides what is possible: whether CD8A, CD8B and CD4 are measured, and in what share of cells, is "
    "recorded at intake.",
    "Donors are few: the donor count is reported beside every figure.",
)


def qualifies(true_type: np.ndarray) -> tuple[bool, dict]:
    """Whether the scored single cells hold at least MIN_SORTED_CELLS each of
    CD4 T and CD8 T (the protocol's "A qualifying dataset"; amendment 1: only
    single cells count), and the two counts."""
    counts = {t: int((np.asarray(true_type) == t).sum()) for t in ("CD4T", "CD8T")}
    return all(n >= MIN_SORTED_CELLS for n in counts.values()), counts


def donor_counts(labels: pd.DataFrame, single: np.ndarray) -> "dict | str":
    """Donors among the scored single cells, overall and per type, from the
    labels file's donor column when it has one (amendment 5)."""
    if "donor" not in labels.columns:
        return "not given in the labels file"
    sub = labels[np.asarray(single)]
    out = {"all": int(sub["donor"].nunique())}
    out.update({t: int(g["donor"].nunique()) for t, g in sub.groupby("type") if t in ("CD4T", "CD8T")})
    return out


def tables_dir(rehearse: bool) -> Path:
    return out_dir(True) / "tables" if rehearse else REPO / "research" / "benchmark" / "sorted_cd4cd8"


def baseline_dataset(rehearse: bool) -> str:
    return "fulcher2026" if rehearse else "sorted_cd4cd8"


def read_pred(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, keep_default_na=False, dtype={"cell_id": str})
    if "abstained" in df:
        df["abstained"] = df["abstained"].astype(str).eq("True")
    return df


def same_rows(ids: list[str], cell_ids: list[str], what: str) -> None:
    if list(ids) != list(cell_ids):
        raise ValueError(f"{what}: rows are not in cell_ids.txt order")


def collect(rehearse: bool, cell_ids: list[str]) -> tuple[dict, dict, dict]:
    """Label-free. (name, labels set, seed, rule) -> predicted class per cell for
    every completed run; our per-cell answer tables; and, per label set, the runs
    never made ("missing") and the runs that failed or diverged ("excluded",
    listed and not scored, as on Khoury)."""
    src = out_dir(rehearse)
    predictions, answers = {}, {}
    gaps = {labels: {"missing": set(), "excluded": set()} for labels in ("original", "v52")}
    for key, version in OURS.items():
        table = read_pred(src / f"{key}_pred.csv")
        same_rows(table["cell_id"].tolist(), cell_ids, f"{key}_pred.csv")
        predictions[(version, "own", 0, "best_guess")] = table["best_guess"].to_numpy()
        answers[version] = table
    for labels in ("original", "v52"):
        runs = baselines_corrected.out_dir(labels) / baseline_dataset(rehearse)
        for (tool, rule), (column, seeds) in ARMS.items():
            for seed in seeds:
                stem = runs / f"{tool}_seed{seed}"
                record = Path(f"{stem}.json")
                if not record.exists():
                    gaps[labels]["missing"].add(f"{tool} seed {seed}")
                    continue
                status = json.loads(record.read_text()).get("status")
                if status != "completed":
                    gaps[labels]["excluded"].add(f"{tool} seed {seed} ({status})")
                    continue
                pred = pd.read_csv(f"{stem}_pred.csv", dtype={"cell_id": str}, keep_default_na=False)
                same_rows(pred["cell_id"].tolist(), cell_ids, f"{stem}_pred.csv")
                predictions[(tool, labels, seed, rule)] = pred[f"{column}_unrestricted"].to_numpy()
    return predictions, answers, {k: {kind: sorted(v) for kind, v in g.items()} for k, g in gaps.items()}


def to_type(pred_fine: np.ndarray, sorted_types: tuple) -> np.ndarray:
    return np.array([t if (t := COARSE.get(c, "other")) in sorted_types else "other" for c in pred_fine])


def scores(pred_fine: np.ndarray, true_type: np.ndarray, sorted_types: tuple) -> dict:
    pred = to_type(pred_fine, sorted_types)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # "other" is never a true type
        row = {"balanced_accuracy_pct": 100 * balanced_accuracy_score(true_type, pred)}
    for t in sorted_types:
        row[f"recall_{t}_pct"] = 100 * float((pred[true_type == t] == t).mean())
    return row


def answers_scored(table: pd.DataFrame, scored: np.ndarray, true_type: np.ndarray) -> dict:
    """Coverage, committed share and correct when committed (rule 6), judged at
    the stated level against NB2's hierarchy, as Khoury's scorer does."""
    hier = hierarchy()
    expected = {}
    for level in ("group", "lineage"):
        found = {}
        for name, t in COARSE.items():
            found.setdefault(t, set()).add(hier[name][level])
        expected[level] = {t: v.pop() for t, v in found.items() if len(v) == 1}
    rows = table[scored]
    covered = committed = correct = 0
    for (_, cell), t in zip(rows.iterrows(), true_type):
        label_set = json.loads(cell["label_set"])
        covered += any(COARSE.get(c) == t for c in label_set)
        if not cell["abstained"]:
            committed += 1
            level = cell["label_level"]
            correct += (COARSE.get(cell["label"]) == t) if level == "class" else (expected[level].get(t) == cell["label"])
    n = len(true_type)
    return {"n": n, "coverage_pct": round(100 * covered / n, 2), "committed_pct": round(100 * committed / n, 2),
            "correct_when_committed_pct": round(100 * correct / committed, 2) if committed else None}


def bootstrap(a: np.ndarray, b: np.ndarray, true_type: np.ndarray, sorted_types: tuple) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        d = paired_bootstrap_diff(true_type, to_type(a, sorted_types), to_type(b, sorted_types))
    lo, hi = d["ci_95_pct"]
    return {"diff_pct": d["point_estimate_pct"], "ci_lo": lo, "ci_hi": hi}


def load_labels(rehearse: bool, labels_path: Path | None, want_sha: str | None) -> pd.DataFrame:
    if rehearse:
        labels = datasets.load_fulcher2026_labels()
        return pd.DataFrame({"cell_id": labels["cell_id"].astype(str),
                             "type": labels["label"].where(labels["label"].isin(ALL_TYPES), ""), "unit": "single"})
    got = sha256(labels_path)
    if got != want_sha:
        sys.exit(f"the labels file's sha256 is {got}, not the {want_sha} recorded on receipt")
    labels = pd.read_csv(labels_path, dtype={"cell_id": str}, keep_default_na=False)
    if not set(labels["type"]) <= set(ALL_TYPES) | {""} or not set(labels["unit"]) <= {"single", "bulk", "unsorted"}:
        raise ValueError("labels must have type in the six types (or empty) and unit single, bulk or unsorted")
    return labels


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--unseal", type=Path, metavar="LABELS_CSV", help="read the sorting labels: once")
    mode.add_argument("--rehearse", action="store_true", help="the same code on Fulcher 2026")
    parser.add_argument("--sha256", help="the labels file's sha256, as recorded on receipt (with --unseal)")
    args = parser.parse_args(argv)
    rehearse = args.rehearse
    refuse_overrides()
    tables = tables_dir(rehearse)
    if not rehearse and (tables / "summary.json").exists():
        sys.exit(f"{tables / 'summary.json'} exists: the sorted test is scored once")
    if not rehearse and not args.sha256:
        sys.exit("--unseal needs --sha256, the labels file's hash recorded on receipt")
    src = out_dir(rehearse)
    intake = json.loads((src / "intake.json").read_text())
    if intake["rehearsal"] != rehearse:
        sys.exit("the intake's outputs are from the other mode")
    cell_ids = (src / "cell_ids.txt").read_text(encoding="utf-8").splitlines()
    predictions, answers, gaps = collect(rehearse, cell_ids)  # every label-free check, done
    for labels, gap in gaps.items():
        for kind, runs in gap.items():
            if runs:
                print(f"{labels} labels, {kind}: {', '.join(runs)}")

    labels = load_labels(rehearse, args.unseal, args.sha256).set_index("cell_id").reindex(cell_ids)
    if labels["type"].isna().any():
        raise ValueError("an uploaded cell has no row in the labels file")
    single = (labels["unit"] == "single").to_numpy() & labels["type"].isin(ALL_TYPES).to_numpy()
    bulk = (labels["unit"] == "bulk").to_numpy() & labels["type"].isin(ALL_TYPES).to_numpy()
    sorted_types = tuple(t for t in ALL_TYPES if (labels["type"].to_numpy()[single] == t).any())
    true_type = labels["type"].to_numpy()[single]
    ok, counts = qualifies(true_type)
    if not ok:
        # Not a qualifying dataset: no scores and no verdicts. The labels have been read, so a record of why is
        # written, and the scored-once guard then holds.
        tables.mkdir(parents=True, exist_ok=True)
        (tables / "summary.json").write_text(json.dumps({
            "protocol": "research/benchmark/protocol-sorted-cd4cd8.md", "rehearsal": rehearse, "qualifies": False,
            "reason": f"single cells after QC: CD4 T {counts['CD4T']}, CD8 T {counts['CD8T']}; at least "
                      f"{MIN_SORTED_CELLS} each are needed", "labels_sha256": None if rehearse else args.sha256},
            indent=2) + "\n", encoding="utf-8", newline="\n")
        sys.exit("not a qualifying dataset: " + json.dumps(counts))

    rows = []
    for (name, label_set, seed, rule), pred in predictions.items():
        row = {"model": name, "reference_labels": label_set, "seed": seed, "rule": rule, "unit": "single",
               "n": int(single.sum()), **scores(pred[single], true_type, sorted_types)}
        rows.append(row)
        if bulk.any():
            rows.append({**row, "unit": "bulk", "n": int(bulk.sum()),
                         **scores(pred[bulk], labels["type"].to_numpy()[bulk], sorted_types)})
    per_run = pd.DataFrame(rows)

    t_cells = np.isin(true_type, ("CD4T", "CD8T"))
    confusion = []
    for version in OURS.values():
        pred = to_type(predictions[(version, "own", 0, "best_guess")][single][t_cells], sorted_types)
        truth = true_type[t_cells]
        confusion += [{"model": version, "true": t, "predicted": p, "count": int(((truth == t) & (pred == p)).sum())}
                      for t in ("CD4T", "CD8T") if t in sorted_types for p in sorted_types + ("other",)]
    answer_table = {version: answers_scored(answers[version], single, true_type) for version in OURS.values()}

    boot, verdicts = [], {}
    for version, own in OWN_LABELS.items():
        ours = predictions[(version, "own", 0, "best_guess")][single]
        runs = [(k, p) for k, p in predictions.items() if k[1] == own]
        for (tool, _, seed, rule), pred in runs:
            boot.append({"comparison": f"{version} vs {tool}", "rule_b": rule, "seed_b": seed, "reference_labels": own,
                         **bootstrap(ours, pred[single], true_type, sorted_types)})
        mine = [b for b in boot if b["comparison"].startswith(f"{version} vs ") and b["reference_labels"] == own]
        # Judged only on a complete set: a run never made leaves the verdict open
        # (rule 4: without v5.2-label baselines, v5.2 is compared with v4.1 only);
        # a failed or diverged run is listed and not scored, as on Khoury.
        verdicts[f"{version} beats the corrected baselines"] = (
            None if gaps[own]["missing"] or not mine
            else all(b["diff_pct"] >= LEAD_POINTS and b["ci_lo"] > 0 for b in mine))
    v41 = predictions[("v4.1", "own", 0, "best_guess")][single]
    for version in ("v5.2", "v4.2"):
        ours = predictions[(version, "own", 0, "best_guess")][single]
        ba = bootstrap(ours, v41, true_type, sorted_types)
        boot.append({"comparison": f"{version} vs v4.1", "rule_b": "best_guess", "seed_b": 0, "reference_labels": "own",
                     **ba})
        if "CD8T" in sorted_types:
            cd8 = true_type == "CD8T"
            recall = bootstrap(ours[cd8], v41[cd8], true_type[cd8], ("CD8T",))  # balanced accuracy on one class = recall
            boot.append({"comparison": f"{version} vs v4.1, CD8 T recall", "rule_b": "best_guess", "seed_b": 0,
                         "reference_labels": "own", **recall})
            if version == "v5.2":  # the protocol's one rule between our models
                verdicts["v5.2 improves CD4/CD8 over v4.1"] = bool(recall["ci_lo"] > 0
                                                                   and ba["diff_pct"] >= -BA_SLACK_POINTS)

    tables.mkdir(parents=True, exist_ok=True)
    fmt = {"index": False, "float_format": "%.4f", "lineterminator": "\n"}
    per_run.to_csv(tables / "per_run_scores.csv", **fmt)
    pd.DataFrame(confusion).to_csv(tables / "cd4_cd8_confusion.csv", **fmt)
    pd.DataFrame(boot).to_csv(tables / "paired_bootstrap.csv", **fmt)
    (tables / "answers.json").write_text(json.dumps(answer_table, indent=2) + "\n", encoding="utf-8", newline="\n")
    summary = {"protocol": "research/benchmark/protocol-sorted-cd4cd8.md", "rehearsal": rehearse,
               "sorted_types": list(sorted_types), "n_single_scored": int(single.sum()), "n_bulk_scored": int(bulk.sum()),
               "baseline_runs_not_scored": gaps, "verdicts": verdicts, "qualifies": True,
               "single_cells_by_type": counts, "donors": donor_counts(labels.reset_index(), single), "caveats": list(CAVEATS),
               "labels_sha256": None if rehearse else args.sha256}
    (tables / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    ours_rows = per_run[(per_run["reference_labels"] == "own") & (per_run["unit"] == "single")]
    print(ours_rows[["model", "balanced_accuracy_pct"] + [f"recall_{t}_pct" for t in sorted_types]].round(2).to_string(index=False))
    print(json.dumps({"verdicts": verdicts, "answers": answer_table}, indent=2))
    if rehearse:
        check_rehearsal(per_run)


def check_rehearsal(per_run: pd.DataFrame) -> None:
    """The scorer must reproduce Fulcher's committed six-type figures: v3.1 and
    v4.1 as served (research/benchmark/v41_development/fulcher2026.csv) and every
    original-label baseline run (research/benchmark/baselines_corrected/
    fulcher2026_per_seed.csv)."""
    rule_names = {"shared_knn": "shared kNN", "native": {"scanvi": "scANVI classifier", "seurat": "Seurat native transfer"},
                  "matching": "MaxFuse matching", "correlation": "correlation to class mean"}
    worst, compared = 0.0, 0
    ours = pd.read_csv(REPO / "research" / "benchmark" / "v41_development" / "fulcher2026.csv")
    for version, tool in (("v3.1", "v3.1 (served)"), ("v4.1", "v4.1 (served)")):
        mine = per_run.query("model == @version and unit == 'single'")["balanced_accuracy_pct"].iloc[0]
        theirs = ours.query("tool == @tool")["balanced_accuracy_pct"].iloc[0]
        worst, compared = max(worst, abs(mine - theirs)), compared + 1
    v42 = json.loads((REPO / "research" / "notebook-outputs" / "v42_protein_means" / "summary.json").read_text())
    mine = per_run.query("model == 'v4.2' and unit == 'single'")["balanced_accuracy_pct"].iloc[0]
    worst, compared = max(worst, abs(mine - v42["figures"]["v4.2"]["fulcher"])), compared + 1
    committed = pd.read_csv(REPO / "research" / "benchmark" / "baselines_corrected" / "fulcher2026_per_seed.csv")
    for _, r in per_run.query("reference_labels == 'original' and unit == 'single'").iterrows():
        name = rule_names[r["rule"]]
        name = name[r["model"]] if isinstance(name, dict) else name
        match = committed.query("tool == @r.model and seed == @r.seed and rule == @name")
        if match.empty:
            print(f"  no committed row for {r['model']} seed {r['seed']} {name}")
            continue
        worst = max(worst, abs(r["balanced_accuracy_pct"] - match["balanced_accuracy_pct"].iloc[0]))
        compared += 1
    print(f"rehearsal check: {compared} runs compared with Fulcher's committed tables; "
          f"largest balanced-accuracy difference {worst:.6f} points")
    if worst > 1e-6:
        sys.exit("the rehearsal does not reproduce Fulcher's committed figures")


if __name__ == "__main__":
    main()
