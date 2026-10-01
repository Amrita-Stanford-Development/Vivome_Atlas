"""Track D extension: "ours" is v3.1 as served (release 0.3.0, both service
flags on), on the same three development datasets as the baselines, through
the service's own parser and pipeline (pipeline.run_projection):
- SCoPE2: the published matrix, unrestricted and restricted to
  macrophage/monocyte (restrict_to_supported_classes);
- PBMC240: the raw DIA-NN report, keeping NB1d's 237 cells (results/pbmc_meta.csv);
- Fulcher 2026: the 1,275-cell upload (datasets.load_fulcher2026_upload).

Saves, per cell, the best guess (what balanced accuracy is scored on, since
the baselines give fine labels only) and the confident answer (label,
label_level, label_set, abstained, abstain_reason) to
results/baselines_ext/<dataset>/v31[_restricted]_pred.csv. Never reads a label.

    python3 -m benchmark.baselines_v31      # from the repository root
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import baselines_inputs, datasets
from service.pipeline import alignment, pipeline

OUT = baselines_inputs.D / "baselines_ext"
SCOPE2 = datasets.REPO / "service" / "model" / "source" / "app_export" / "blood_joint_cells_by_proteins_GENELEVEL.tsv"
PBMC240 = datasets.REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv"


def scope2_raw() -> alignment.RawMatrix:
    df = pd.read_csv(SCOPE2, sep="\t", index_col=0)
    return alignment.RawMatrix(gene_names=df.columns.astype(str).tolist(), cell_ids=df.index.astype(str).tolist(),
                               values=df.to_numpy(dtype=np.float32).T)


def table(response: dict, keep: list[str] | None = None) -> pd.DataFrame:
    rows = [{
        "cell_id": c["cell_id"],
        "best_guess": c.get("best_guess", {}).get("label", ""),
        "best_guess_probability": c.get("best_guess", {}).get("probability", np.nan),
        "label": c["label"] or "", "label_level": c["label_level"] or "",
        "label_set": json.dumps(c["label_set"]), "abstained": c["abstained"],
        "abstain_reason": c.get("abstain_reason", ""),
    } for c in response["cells"]]
    df = pd.DataFrame(rows)
    if keep is not None:
        df = df.set_index("cell_id").loc[keep].reset_index()
    return df


def main() -> None:
    bundle = pipeline.load_bundle("v3.1")
    flags = {"set_includes_best_guess": bundle.components.calibrator.include_best_guess,
             "restricted_renormalise": bundle.components.label_space.renormalise}
    assert all(flags.values()), f"v3.1 as served has both flags on, got {flags}"
    runs = {
        ("scope2", "v31"): (scope2_raw(), False, None),
        ("scope2", "v31_restricted"): (scope2_raw(), True, None),
        ("pbmc240", "v31"): (alignment.parse_matrix_csv(PBMC240.read_text()), False,
                             pd.read_csv(baselines_inputs.D / "pbmc_meta.csv")["cell_id"].tolist()),
        ("fulcher2026", "v31"): (datasets.load_fulcher2026_upload(), False, None),
    }
    for (dataset, name), (raw, restrict, keep) in runs.items():
        response = pipeline.run_projection(bundle, raw, restrict_to_supported_classes=restrict)
        (OUT / dataset).mkdir(parents=True, exist_ok=True)
        table(response, keep).to_csv(OUT / dataset / f"{name}_pred.csv", index=False)
        record = {"model": response["model_version"], "pipeline_version": response["pipeline_version"],
                  "atlas_version": response["atlas_version"], "service_flags": flags,
                  "restrict_to_supported_classes": restrict, "n_cells": len(keep or response["cells"])}
        (OUT / dataset / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n")
        print(dataset, name, record)


if __name__ == "__main__":
    main()
