"""v4.1, Phase A (research/todo.md, Track G): the per-cell cache of the
pre-test. Every candidate rule of research/notebooks/v41_pretest.py is a
recombination of four per-cell ingredients (research/notebooks/v41_core.py),
so they are computed once here, through the service's own code, and never
re-encoded.

Cells:
- calibration: T1 NB3c's calibration suite (Drive NB3c/suites.json, 240
  uploads from te_cal) and the 60 extra single-type uploads of Phase 3c's
  exploration (research/notebook-outputs/v4_phase3c/
  exploration_single_type_suite.json, also from te_cal); references without
  test cells, as in Phases 3 to 3c (v4's train-plus-validation bundle,
  v3.1's centroids recomputed on those rows). te_eval is never read.
- development: Fulcher 2026, PBMC240, SCoPE2 (published matrix and
  reprocessed), Furtwangler 2025, through the served all-cells bundle.
  Khoury 2026 is not read.

Self-check, before the record is written: from the cache, v4's rule must
reproduce Phase 3c's implementation check on the calibration suite
(research/notebook-outputs/v4_phase3c/calibration_check.json) and v4's
development figures (development.json) to their recorded precision.

Writes the arrays and cell tables to Drive Data/Results/Tier1_v31/V41/cache/
(outside the repository) and their sha256s, counts and the self-check to
research/notebook-outputs/v41_pretest/cache_record.json.

    python research/notebooks/v41_cache.py      # from the repository root
    python research/notebooks/v41_cache.py --smoke
    # a plumbing check: 4 calibration and 2 extra uploads, the self-check
    # printed (not enforced, since it needs the whole suite), nothing written
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v4_calibration as phase3  # noqa: E402  (raw_upload, restricted, centroids_from, GROUP)
import v41_core as core  # noqa: E402

from benchmark import baselines_v31, datasets  # noqa: E402
from service.pipeline import alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

PHASE3C = REPO / "research" / "notebook-outputs" / "v4_phase3c"
EXTRA = PHASE3C / "exploration_single_type_suite.json"


def ingredients(members31, members4, class_means, smoothed, aligned) -> dict:
    Zs = [m.encoder_handle.encode(smoothed, aligned.mask) for m in members4]
    Zu = [m.encoder_handle.encode(aligned.values, aligned.mask) for m in members4]
    probs = lambda Z, members: ensemble.ensemble_probabilities(  # noqa: E731
        [ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, members)])
    return {"Ps": probs(Zs, members4).astype(np.float32), "Pu": probs(Zu, members4).astype(np.float32),
            "P31": probs(Zs, members31).astype(np.float32),
            "R": fusion.masked_pearson(aligned.values, aligned.mask, class_means).astype(np.float32)}


def answer_fields(cell: dict) -> dict:
    return {"observed_genes": int(cell["observed_genes"]), "abstained": bool(cell["abstained"]),
            "abstain_reason": cell.get("abstain_reason") or "", "level": cell.get("label_level") or "",
            "answer": cell.get("label") or "", "label_set": "|".join(cell.get("label_set") or []),
            "v31_best_guess": cell.get("best_guess", {}).get("label") or ""}


def build_calibration(v4, y, t0, smoke: bool) -> tuple[pd.DataFrame, dict]:
    v31 = v4.answers
    names, n = v4.class_names, len(v4.class_names)
    split = np.load(phase3.NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    extra = json.loads(EXTRA.read_text())
    if smoke:
        suites["calib"], extra = suites["calib"][:4], extra[:2]
    te_cal = set(np.asarray(suites["te_cal"]).tolist())
    if te_cal & set(np.asarray(suites["te_eval"]).tolist()):
        raise SystemExit("te_cal overlaps te_eval")
    for s in suites["calib"] + extra:
        if not set(s["cell_idx"]) <= te_cal:
            raise SystemExit(f"{s['id']} draws outside te_cal")
    if json.loads((phase3.CALIB_BUNDLE / "spec_v4.json").read_text()).get("reference_rows") != "trainval":
        raise SystemExit(f"{phase3.CALIB_BUNDLE} is not the train-plus-validation bundle")
    v31_centroids = [phase3.centroids_from(m.reference_latents[trainval], y[trainval], n) for m in v31.members]
    v31c = dataclasses.replace(v31, members=phase3.restricted(v31.members, trainval, v31_centroids),
                               property_values=v31.property_values[trainval])
    cb = [np.load(phase3.CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy")
          for m in v4.members]
    members4 = phase3.restricted(v4.members, trainval, cb)
    class_means = np.load(phase3.CALIB_BUNDLE / "class_means_cb.npy")
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_X = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_X[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    genes = v4.feature_genes
    resolution = gene_ids.resolve_identifiers(genes)
    arrays = {k: [] for k in ("Ps", "Pu", "P31", "R")}
    rows = []
    for s, source in [(s, "calib") for s in suites["calib"]] + [(s, "single_extra") for s in extra]:
        raw = phase3.raw_upload(s, get_raw, profiles, len(genes))
        ids = [f"{s['id']}_{i}" for i in range(len(raw))]
        smoothed, aligned, scale = pipeline._prepare_query(genes, alignment.RawMatrix(gene_names=genes, cell_ids=ids, values=raw.T))
        for k, v in ingredients(v31c.members, members4, class_means, smoothed, aligned).items():
            arrays[k].append(v)
        response = ensemble.project_prepared(v31c, smoothed, aligned, scale, resolution, False, v31c.components)
        for i, cell in enumerate(response["cells"]):
            rows.append({"upload": s["id"], "source": source, "scenario": s["scenario"], "group": phase3.GROUP[s["scenario"]],
                         "true": int(y[s["cell_idx"][i]]), **answer_fields(cell)})
        if len({r["upload"] for r in rows}) % 50 == 0:
            print(f"calibration: {len({r['upload'] for r in rows})} uploads ({time.time() - t0:.0f}s)", flush=True)
    return pd.DataFrame(rows), {k: np.concatenate(v) for k, v in arrays.items()}


def build_development(v4, t0) -> tuple[pd.DataFrame, dict]:
    v31 = v4.answers
    pbmc_meta = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    weak = dict(zip(pbmc_meta["cell_id"].astype(str), pbmc_meta["weak_lineage"].astype(str)))
    uploads = [
        ("fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels()["label"].astype(str).tolist()),
        ("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), None),
        ("scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")["class_name"].astype(str).tolist()),
        ("scope2_reprocessed", datasets.load_scope2_reprocessed_upload(), datasets.load_scope2_reprocessed_labels()["label"].astype(str).tolist()),
        ("furtwangler2025", datasets.load_furtwangler2025_upload(), None),
    ]
    arrays = {k: [] for k in ("Ps", "Pu", "P31", "R")}
    rows = []
    for name, raw, labels in uploads:
        smoothed, aligned, scale = pipeline._prepare_query(v4.feature_genes, raw)
        for k, v in ingredients(v31.members, v4.members, v4.class_means, smoothed, aligned).items():
            arrays[k].append(v)
        response = ensemble.project_prepared(v31, smoothed, aligned, scale, gene_ids.resolve_identifiers(raw.gene_names),
                                             False, v31.components)
        for i, cell in enumerate(response["cells"]):
            label = labels[i] if labels else weak.get(cell["cell_id"], "")
            rows.append({"dataset": name, "cell_id": cell["cell_id"], "label": label, **answer_fields(cell)})
        print(f"{name}: {len(response['cells'])} cells ({time.time() - t0:.0f}s)", flush=True)
    return pd.DataFrame(rows), {k: np.concatenate(v) for k, v in arrays.items()}


def self_check(calib: pd.DataFrame, a: dict, dev: pd.DataFrame, d: dict, v4) -> dict:
    """v4's rule from the cache against Phase 3c's records."""
    names = np.array(v4.class_names)
    keep = (calib["observed_genes"] >= core.MIN_GENES).to_numpy()
    c, ak = calib[keep].reset_index(drop=True), {k: v[keep] for k, v in a.items()}
    cal = (c["source"] == "calib").to_numpy()
    space = v4.answers.components.label_space.estimate(None, list(names), False)
    sets = v4.answers.components.calibrator.calibrate(ak["P31"].astype(np.float64), None, space).label_sets
    guess4 = core.rule(ak, core.agreement(c, ak, "upload"), core.V4["w_on"], core.V4["tau"]).argmax(1)
    guess31 = ak["P31"].argmax(1)
    found = {"v3.1": {"best_guess_per_upload_balanced": core.suite_scores(c, guess31)["overall"],
                      **core.answers(c, sets, names, v4.answers.hierarchy, None, cal)},
             "v4": {"best_guess_per_upload_balanced": core.suite_scores(c, guess4)["overall"],
                    **core.answers(c, sets, names, v4.answers.hierarchy, guess4, cal)}}
    expected = json.loads((PHASE3C / "calibration_check.json").read_text())["found"]
    misses = [f"calibration {m} {k}: {found[m][k]:.4f} vs {expected[m][k]}" for m in found for k in expected[m]
              if abs(round(found[m][k], 2) - expected[m][k]) > 1e-9]
    P4 = core.rule(d, core.agreement(dev, d, "dataset"), core.V4["w_on"], core.V4["tau"])
    figures = core.dev_figures(dev, P4, names)
    recorded = json.loads((PHASE3C / "development.json").read_text())
    pairs = {"fulcher": (recorded["fulcher2026"]["v4"]["balanced_accuracy_6_types"], 2),
             "pbmc240_lymphoid": (recorded["pbmc240"]["v4"]["lymphoid_recall"], 2),
             "scope2_unrestricted": (recorded["scope2"]["v4"]["balanced_accuracy_unrestricted"], 2),
             "auroc": (recorded["out_of_reference_auroc"]["v4"], 4)}
    misses += [f"development {k}: {figures[k]:.6f} vs {v}" for k, (v, places) in pairs.items()
               if abs(round(figures[k], places) - v) > 1e-9]
    return {"calibration_found": {m: {k: round(v, 4) for k, v in r.items()} for m, r in found.items()},
            "calibration_expected": expected, "development_found": {k: round(figures[k], 4) for k in pairs},
            "development_expected": {k: v for k, (v, _) in pairs.items()}, "misses": misses, "passed": not misses}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="plumbing check: a few uploads, nothing written")
    smoke = parser.parse_args().smoke
    warnings.simplefilter("ignore")
    t0 = time.time()
    v4 = fusion.V4Bundle.load(require_evaluation=False)
    names = v4.class_names
    table = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    y = np.array([names.index(c) for c in table["class_name"]])
    calib, a = build_calibration(v4, y, t0, smoke)
    dev, d = build_development(v4, t0)
    check = self_check(calib, a, dev, d, v4)
    print(json.dumps(check, indent=1), flush=True)
    if smoke:
        print(f"smoke: {calib['upload'].nunique()} calibration uploads, {len(dev)} development cells; nothing written "
              f"({time.time() - t0:.0f}s)")
        return
    if not check["passed"]:
        raise SystemExit("STOP: the cache does not reproduce Phase 3c's records; nothing written")
    core.CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(core.CACHE / "calib_arrays.npz", **a)
    np.savez_compressed(core.CACHE / "dev_arrays.npz", **d)
    calib.to_csv(core.CACHE / "calib_cells.csv.gz", index=False, lineterminator="\n")
    dev.to_csv(core.CACHE / "dev_cells.csv.gz", index=False, lineterminator="\n")
    files = ("calib_arrays.npz", "dev_arrays.npz", "calib_cells.csv.gz", "dev_cells.csv.gz")
    core.RECORD.parent.mkdir(parents=True, exist_ok=True)
    core.RECORD.write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "core_sha256": hashlib.sha256((REPO / "research" / "notebooks" / "v41_core.py").read_bytes()).hexdigest(),
        "cache_dir": "Drive Data/Results/Tier1_v31/V41/cache",
        "sha256": {f: hashlib.sha256((core.CACHE / f).read_bytes()).hexdigest() for f in files},
        "calibration": {"uploads": int(calib["upload"].nunique()), "cells": int(len(calib)),
                        "cells_with_200_genes": int((calib["observed_genes"] >= core.MIN_GENES).sum())},
        "development": {k: int(v) for k, v in dev["dataset"].value_counts().items()},
        "self_check": check, "seconds": round(time.time() - t0),
    }, indent=2) + "\n", newline="\n")
    print(f"cache written ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
