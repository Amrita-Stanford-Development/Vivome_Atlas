"""Goal 2, Phase 2a: candidate v4.2, v4.1's rule with protein class means for
protein uploads. Development data only; the rule and the gates are fixed here
before the run, and nothing is tuned.

The rule (everything else is v4.1's: its answers, members, weights 0.5 and
0.7, correlation temperature 0.05, smoothed share 0.5, agreement threshold
0.4):
- the correlation term R becomes hybrid: for the 16 classes Rieckmann 2017
  has a sorted population for, each cell's Pearson correlation, over its
  observed proteins, with the protein class means
  (research/notebooks/rieckmann_feasibility.py, protein_means); for the other
  6 (macrophage, the three progenitor classes, mature NK T and the generic
  monocyte class), v4.1's RNA correlation, unchanged;
- the upload's agreement gate is computed on the hybrid R.
It would apply to protein uploads only (RNA uploads keep RNA means).

Scored from v4.1's development cache (research/notebooks/v41_core.py; Drive
Tier1_v31/V41/cache), recombining cached encoder probabilities with the new R:
Fulcher 2026 (six types), PBMC240 (lymphoid recall), SCoPE2 published and
reprocessed (restricted to macrophage or monocyte), and the out-of-reference
AUROC (Fulcher against Furtwangler 2025). Answers: v3.1's sets with the guess
joined (set_includes_best_guess), on Fulcher.

Self-check first: v4.1 recomputed from the cache must reproduce its committed
development figures (research/benchmark/v41_development/: Fulcher 69.05, PBMC240
92.31, SCoPE2 restricted 37.97 and 33.30) to 0.01 point, else stop.

GO for v4.2, all of:
1. Fulcher balanced accuracy at least v4.1 + 2 points;
2. PBMC240 lymphoid recall at least v4.1 - 1;
3. SCoPE2 restricted, both versions, at least v4.1 - 2;
4. Fulcher answers: committed share at least v4.1 - 2, correct when committed
   at least v4.1 - 1;
5. out-of-reference AUROC at least v4.1 - 0.03.
Fulcher also chose v4.1's weight, so a gain there is development evidence
only; the held-out protein sets and the sorted cells are the tests.

Writes research/notebook-outputs/v42_protein_means/summary.json and guesses.csv.gz
(each development cell's best guess under v4.1 and v4.2, for the service's gate).

    python research/notebooks/v42_protein_means.py      # from the repository root
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import rieckmann_feasibility as feas  # noqa: E402
import v41_core as core  # noqa: E402
from benchmark import baselines_v31, datasets  # noqa: E402
from benchmark import fulcher2026_score as fulcher  # noqa: E402
from benchmark.baselines_score import hierarchy  # noqa: E402
from service.pipeline import alignment, ensemble, fusion  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v42_protein_means"
V41 = {"w_on": 0.5, "tau": 0.05}
COMMITTED_V41 = {"fulcher": 69.0488, "pbmc240_lymphoid": 92.3077, "scope2_restricted": 37.9726,
                 "scope2_reprocessed_restricted": 33.3006}


def uploads() -> dict:
    """The development uploads, as v41_cache.build_development built them."""
    return {"fulcher2026": datasets.load_fulcher2026_upload(),
            "pbmc240": alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()),
            "scope2": baselines_v31.scope2_raw(),
            "scope2_reprocessed": datasets.load_scope2_reprocessed_upload(),
            "furtwangler2025": datasets.load_furtwangler2025_upload()}


def hybrid_r(dev: pd.DataFrame, r_rna: np.ndarray, names: list[str]) -> tuple[np.ndarray, list[str]]:
    prot_means, prot_genes, covered = feas.protein_means(names)
    out = r_rna.astype(np.float64).copy()
    for name, raw in uploads().items():
        rows = (dev["dataset"] == name).to_numpy()
        if dev.loc[rows, "cell_id"].tolist() != list(raw.cell_ids):
            raise SystemExit(f"{name}: the cache's cells are not the upload's, in order")
        v, m = feas.query(raw, prot_genes)
        r = fusion.masked_pearson(v, m, prot_means)
        block = out[rows]
        block[:, covered] = r[:, covered]
        out[rows] = block
    return out, [n for n, c in zip(names, covered) if not c]


def fulcher_answers(dev: pd.DataFrame, guess: np.ndarray, names: np.ndarray) -> dict:
    """Committed share and correct when committed on Fulcher's scored cells,
    v3.1's sets with the guess joined, judged at the stated level."""
    hier = hierarchy()
    expected = {}
    for level in ("group", "lineage"):
        found = {}
        for name, t in fulcher.COARSE.items():
            found.setdefault(t, set()).add(hier[name][level])
        expected[level] = {t: v.pop() for t, v in found.items() if len(v) == 1}
    f = (dev["dataset"] == "fulcher2026").to_numpy()
    committed = correct = n = 0
    for i in np.flatnonzero(f):
        t = dev.at[i, "label"]
        if t not in fulcher.TYPES:
            continue
        n += 1
        held = dev.at[i, "abstain_reason"] in ("outside_supported_region", "coverage_too_low")
        s = set(filter(None, str(dev.at[i, "label_set"]).split("|")))
        if s and not held:
            s.add(str(names[guess[i]]))
        r = ensemble.resolve(sorted(s), hier) if s and not held else None
        if r is None:
            continue
        committed += 1
        label, level = r
        correct += (fulcher.COARSE.get(label) == t) if level == "class" else (expected[level].get(t) == label)
    return {"committed": 100 * committed / n, "correct_when_committed": 100 * correct / committed}


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    _, _, dev, d = core.load()
    names = np.array(pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
                     .drop_duplicates("class_idx").sort_values("class_idx")["class_name"])
    P41 = core.rule(d, core.agreement(dev, d, "dataset"), V41["w_on"], V41["tau"])
    fig41 = core.dev_figures(dev, P41, names)
    gaps = {k: abs(fig41[k] - v) for k, v in COMMITTED_V41.items()}
    if max(gaps.values()) > 0.01:
        raise SystemExit(f"STOP: v4.1 from the cache does not reproduce its committed figures: {gaps}")

    R, rna_classes = hybrid_r(dev, d["R"], list(names))
    d42 = {**d, "R": R.astype(np.float32)}
    ag42 = core.agreement(dev, d42, "dataset")
    P42 = core.rule(d42, ag42, V41["w_on"], V41["tau"])
    fig42 = core.dev_figures(dev, P42, names)
    ans41, ans42 = fulcher_answers(dev, P41.argmax(1), names), fulcher_answers(dev, P42.argmax(1), names)
    agreement = {k: {"v4.1": float(core.agreement(dev, d, "dataset")[(dev["dataset"] == k).to_numpy()][0]),
                     "v4.2": float(ag42[(dev["dataset"] == k).to_numpy()][0])} for k in dev["dataset"].unique()}

    checks = {
        "1_fulcher_plus_2": fig42["fulcher"] >= fig41["fulcher"] + 2,
        "2_pbmc240_minus_1": fig42["pbmc240_lymphoid"] >= fig41["pbmc240_lymphoid"] - 1,
        "3_scope2_minus_2": all(fig42[k] >= fig41[k] - 2 for k in ("scope2_restricted", "scope2_reprocessed_restricted")),
        "4_answers": ans42["committed"] >= ans41["committed"] - 2
                     and ans42["correct_when_committed"] >= ans41["correct_when_committed"] - 1,
        "5_auroc_minus_0.03": fig42["auroc"] >= fig41["auroc"] - 0.03,
    }
    summary = {"rule": "v4.1 with hybrid R: protein class means (Rieckmann) for the classes it covers, RNA otherwise",
               "rna_correlation_classes": rna_classes, "self_check_max_gap": max(gaps.values()),
               "figures": {"v4.1": fig41, "v4.2": fig42}, "fulcher_answers": {"v4.1": ans41, "v4.2": ans42},
               "upload_agreement": agreement, "checks": checks, "go": all(checks.values())}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    pd.DataFrame({"dataset": dev["dataset"], "cell_id": dev["cell_id"], "v41": names[P41.argmax(1)],
                  "v42": names[P42.argmax(1)]}).to_csv(OUT / "guesses.csv.gz", index=False, lineterminator="\n")
    keys = ["fulcher", "fulcher_CD4T", "fulcher_CD8T", "fulcher_NK", "fulcher_B", "fulcher_monocyte", "fulcher_DC",
            "pbmc240_lymphoid", "scope2_restricted", "scope2_reprocessed_restricted", "auroc"]
    print(pd.DataFrame({"v4.1": [fig41[k] for k in keys], "v4.2": [fig42[k] for k in keys]}, index=keys).round(2))
    print(json.dumps({"answers": summary["fulcher_answers"], "agreement": agreement, "checks": checks,
                      "go": summary["go"]}, indent=2))


if __name__ == "__main__":
    main()
