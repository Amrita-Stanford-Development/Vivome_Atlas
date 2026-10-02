"""Khoury 2026 final evaluation, step 1: gates, then embeddings and v3.1's
served answers. Fixed by research/benchmark/protocol-khoury2026.md (sections
"Gate", "Our query path", "Decision rules"; amendments 2 and 5).

Gates, before any Khoury embedding (amendment 2):
- each v3.1 member (service/model/v3_1/members/V2_batchgene_aug_seed{0..4}.pt)
  reproduces its own NB1d latents on PBMC240 raw (NB1d's 237 cells and
  first-symbol gene convention) through pipeline.embed_query, median cosine
  at least 0.999;
- the served pipeline passes benchmark/v31_dev_gate.py (NB2's development table);
- the v3.1 bundle loads (its MANIFEST sha256s are checked on load) with both
  service flags on.
If any gate fails, nothing is embedded.

Then, on the full upload (datasets.load_khoury2026_upload, which cannot
return labels):
- each member's latents and v3 as served's latents (embed_query, unchanged),
  to <out>/<model>_latent.npy, rows in cell_ids.txt order;
- v3.1 as served (pipeline.run_projection, unrestricted, default settings):
  the per-cell best guess and confident answer, to <out>/v31_pred.csv
  (baselines_v31.table's columns) and v31.json.
This script never reads a label.

    python -m benchmark.khoury2026_embed --unseal       # the final evaluation only
    python -m benchmark.khoury2026_embed --rehearse     # the same code on Fulcher 2026 (development data)

--rehearse writes to results/khoury2026_rehearsal/ and checks the latents
against fulcher2026_embed.py's.
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from benchmark import baselines_v31, datasets, v31_dev_gate
from benchmark.fulcher2026_embed import cosine_stats, pbmc240_upload, sha256
from service.pipeline import encoder, pipeline, reference

RESULTS = datasets.REPO / "benchmark" / "results"
MEMBERS_DIR = datasets.REPO / "service" / "model" / "v3_1" / "members"
NB1D = datasets.REPO / "data" / "incoming" / "NB1d" / "embeddings"
MEMBERS = {f"V2_seed{s}": MEMBERS_DIR / f"V2_batchgene_aug_seed{s}.pt" for s in range(5)}
V3_SERVED = datasets.REPO / "service" / "model" / "runtime" / "reference_model.pt"
GATE_MIN_MEDIAN_COSINE = 0.999


def out_dir(rehearse: bool):
    return RESULTS / ("khoury2026_rehearsal" if rehearse else "khoury2026")


def tables_dir(rehearse: bool):
    return out_dir(True) / "tables" if rehearse else datasets.REPO / "research" / "benchmark" / "khoury2026"


def member_gate(genes: list[str]) -> dict:
    upload = pbmc240_upload(first_symbol=True)
    record = {}
    for name, path in MEMBERS.items():
        z = pipeline.embed_query(encoder.load_encoder(path), genes, upload)[0]
        stats = cosine_stats(z, np.load(NB1D / name / "pbmc240_raw_latent.npy"))
        record[name] = {**stats, "passed": stats["median"] >= GATE_MIN_MEDIAN_COSINE}
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--unseal", action="store_true", help="the final v3.1 evaluation (protocol-khoury2026.md)")
    mode.add_argument("--rehearse", action="store_true", help="the same steps on Fulcher 2026, a development dataset")
    args = parser.parse_args()
    out, tables = out_dir(args.rehearse), tables_dir(args.rehearse)
    out.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    genes = reference.load_feature_space_genes()
    bundle = pipeline.load_bundle("v3.1")  # checks MANIFEST.json's sha256s
    flags = {"set_includes_best_guess": bundle.components.calibrator.include_best_guess,
             "restricted_renormalise": bundle.components.label_space.renormalise}
    gate = {
        "criterion": f"every v3.1 member's median cosine >= {GATE_MIN_MEDIAN_COSINE} against its NB1d PBMC240 raw "
                     "latents (NB1d's cells and first-symbol genes); v31_dev_gate passes; both service flags on",
        "members": member_gate(genes),
        "dev_gate_passed": bool(v31_dev_gate.run_gate(bundle)["passed"]),
        "service_flags": flags,
        "checkpoints": {name: {"file": path.name, "sha256": sha256(path)}
                        for name, path in {**MEMBERS, "v3_served": V3_SERVED}.items()},
    }
    gate["passed"] = (all(m["passed"] for m in gate["members"].values()) and gate["dev_gate_passed"]
                      and all(flags.values()))
    (tables / "gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    print(json.dumps({k: gate[k] for k in ("members", "dev_gate_passed", "service_flags", "passed")}, indent=2))
    if not gate["passed"]:
        sys.exit("GATE FAILED. Nothing embedded.")

    upload = datasets.load_fulcher2026_upload() if args.rehearse else datasets.load_khoury2026_upload()
    (out / "cell_ids.txt").write_text("\n".join(upload.cell_ids) + "\n")
    for name, path in {**MEMBERS, "v3_served": V3_SERVED}.items():
        z, aligned, value_scale = pipeline.embed_query(encoder.load_encoder(path), genes, upload)
        np.save(out / f"{name}_latent.npy", z)
        print(f"{name}: {z.shape}, value scale {value_scale.detected}, {aligned.n_features_matched} genes matched, "
              f"observed per cell min {aligned.per_cell_observed_genes.min()}")

    response = pipeline.run_projection(bundle, upload)
    baselines_v31.table(response).to_csv(out / "v31_pred.csv", index=False)
    (out / "v31.json").write_text(json.dumps({
        "model": response["model_version"], "pipeline_version": response["pipeline_version"],
        "atlas_version": response["atlas_version"], "service_flags": flags,
        "restrict_to_supported_classes": False, "n_cells": len(response["cells"])}, indent=2) + "\n")

    if args.rehearse:  # the same checkpoints embedded the same upload for fulcher2026_embed.py
        fulcher = RESULTS / "fulcher2026"
        for name, earlier in {**{m: m for m in MEMBERS}, "v3_served": "v3_seed0"}.items():
            a, b = np.load(out / f"{name}_latent.npy"), np.load(fulcher / f"{earlier}_latent.npy")
            print(f"rehearsal check {name} vs fulcher2026/{earlier}: max abs diff {np.abs(a - b).max():.2e}")


if __name__ == "__main__":
    main()
