"""v4.1's gate (research/todo.md, Track G, v4.1, Phase D): the v4 gate
(benchmark/v4_dev_gate.py), run on v4.1 as served (service/model/v4_1/).

- The best guess must equal an independent recomputation, from the member
  encoders and numpy, on at least 99.5% of each development dataset's
  cells. The agreement gate must decide as the service does.
- The answers must be v3.1's, with the guess joined.
- The figures must match Phase A's record for the locked rule
  (research/notebook-outputs/v41_pretest/selection.json, computed from the
  per-cell cache) within the v4 gate's tolerances: Fulcher's six-type
  balanced accuracy, PBMC240's lymphoid recall, SCoPE2's unrestricted
  balanced accuracy and the out-of-reference AUROC.

It loads v4.1 with require_evaluation=False, so it can run before the
evaluation is recorded. Khoury 2026 is not read.

Writes research/benchmark/v41_dev_gate.json.

    python -m benchmark.v41_dev_gate      # from the repository root
"""
from __future__ import annotations

import json

from benchmark import datasets, v4_dev_gate
from service.pipeline import fusion

REPO = datasets.REPO
SELECTION = REPO / "research" / "notebook-outputs" / "v41_pretest" / "selection.json"
RECORD = REPO / "research" / "benchmark" / "v41_dev_gate.json"


def phase_a_figures() -> dict:
    """Phase A's figures for the locked rule, in run_gate's layout."""
    chosen = json.loads(SELECTION.read_text())["chosen_figures"]
    return {"fulcher2026": {"v4.1": {"balanced_accuracy_6_types": round(chosen["fulcher"], 2)}},
            "pbmc240": {"v4.1": {"lymphoid_recall": round(chosen["pbmc240_lymphoid"], 2)}},
            "scope2": {"v4.1": {"balanced_accuracy_unrestricted": round(chosen["scope2_unrestricted"], 2)}},
            "out_of_reference_auroc": {"v4.1": round(chosen["auroc"], 4)}}


def run_gate() -> dict:
    return v4_dev_gate.run_gate(fusion.V4Bundle.load(require_evaluation=False, version="v4.1"), phase_a_figures(), "phase_a")


def main() -> None:
    record = run_gate()
    RECORD.write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    print(json.dumps(record, indent=2))
    if record["misses"]:
        raise SystemExit("v4.1 gate: MISS")


if __name__ == "__main__":
    main()
