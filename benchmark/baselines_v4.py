"""Track G, Phase 4: v4 as served (its evaluation passed in Phase 3c;
service/pipeline/fusion.py) on the development datasets, exactly as
baselines_v31.py runs v3.1: the service's own parser and pipeline
(pipeline.run_projection), the same uploads and the same per-cell table.
- SCoPE2: the published matrix, unrestricted and restricted to
  macrophage/monocyte (restrict_to_supported_classes);
- PBMC240: the raw DIA-NN report, keeping NB1d's 237 cells (results/pbmc_meta.csv);
- Fulcher 2026: the 1,275-cell upload (datasets.load_fulcher2026_upload);
- SCoPE2 (reprocessed; datasets.load_scope2_reprocessed_upload), unrestricted
  and restricted. baselines_v31.py predates this dataset, so v3.1 runs on it
  here too.

Saves results/baselines_ext/<dataset>/<model>[_restricted]_pred.csv (model
v4, or v31 on the reprocessed SCoPE2) and a record with the upload's agreement
and whether the correlation term was used. Never reads a label.

    python -m benchmark.baselines_v4      # from the repository root
"""
from __future__ import annotations

import json

import pandas as pd

from benchmark import baselines_inputs, datasets
from benchmark.baselines_v31 import OUT, PBMC240, scope2_raw, table
from service.pipeline import alignment, pipeline


def main() -> None:
    bundles = {"v4": pipeline.load_bundle("v4"), "v31": pipeline.load_bundle("v3.1")}
    flags = {"set_includes_best_guess": bundles["v4"].components.calibrator.include_best_guess,
             "restricted_renormalise": bundles["v4"].components.label_space.renormalise}
    assert all(flags.values()), f"v4's answers are v3.1's as served, both flags on; got {flags}"
    reprocessed = datasets.load_scope2_reprocessed_upload()
    runs = {
        ("scope2", "v4"): (scope2_raw(), False, None),
        ("scope2", "v4_restricted"): (scope2_raw(), True, None),
        ("pbmc240", "v4"): (alignment.parse_matrix_csv(PBMC240.read_text()), False,
                            pd.read_csv(baselines_inputs.D / "pbmc_meta.csv")["cell_id"].tolist()),
        ("fulcher2026", "v4"): (datasets.load_fulcher2026_upload(), False, None),
    }
    for model in ("v4", "v31"):
        runs[("scope2_reprocessed", model)] = (reprocessed, False, None)
        runs[("scope2_reprocessed", f"{model}_restricted")] = (reprocessed, True, None)
    for (dataset, name), (raw, restrict, keep) in runs.items():
        response = pipeline.run_projection(bundles[name.split("_")[0]], raw, restrict_to_supported_classes=restrict)
        (OUT / dataset).mkdir(parents=True, exist_ok=True)
        table(response, keep).to_csv(OUT / dataset / f"{name}_pred.csv", index=False, lineterminator="\n")
        record = {"model": response["model_version"], "pipeline_version": response["pipeline_version"],
                  "atlas_version": response["atlas_version"], "service_flags": flags,
                  "restrict_to_supported_classes": restrict, "n_cells": len(keep or response["cells"]),
                  **({"best_guess_rule": response["best_guess_rule"]} if "best_guess_rule" in response else {})}
        (OUT / dataset / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n", newline="\n")
        print(dataset, name, record)


if __name__ == "__main__":
    main()
