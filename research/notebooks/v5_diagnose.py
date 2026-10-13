"""v5 (research/todo.md, Track H): why v5 falls behind v4.1 on Fulcher, and
what it does to CD8 T and NK. A diagnosis only: it chooses nothing, and it
reads no te_eval cell and no Khoury cell.

The cells are those of the v4.1 cache (research/notebooks/v41_cache.py,
whose arrays are v4.1's ingredients):
- calibration: NB3c's calibration suite and the 60 extra single-type
  uploads, all from te_cal, with references holding no test cells (NB1's
  train and validation rows);
- development: Fulcher 2026, PBMC240, both SCoPE2 versions and Furtwangler
  2025, against the served all-cells references.

v5's ingredients are computed here through the service's code:
- Ps and Pu: the class-balanced encoder on the smoothed and unsmoothed
  query (v5's members);
- P: v5's answers' probability (its own centroids and temperatures);
- R: the masked Pearson with the class-balanced class means under the
  cleaned labels;
- v5's answers per cell (sets and abstentions).
On calibration cells, v5's references are rebuilt on the train and
validation rows (v5_build.best_guess_layer).

Calibration cells are scored on cleaned truth (v5_checkpoint's cell table,
whose row column indexes the reference). The report has, for v3.1's and
v5's own guesses and for the v4.1 and v5 rules:
- multi-type recall per class, CD8 T, NK and NK T first;
- the T and NK confusion;
- per-upload balanced accuracy;
- the answers' coverage, committed share and correct-when-committed.
Development, in-sample and report-only:
- v5 as served;
- with its correlation term forced on, and forced flat;
- its encoder alone and its correlation term alone;
- v4.1's equivalents, for comparison;
- each upload's agreement.

Writes research/notebook-outputs/v5_diagnose/diagnosis.json, and the arrays
to Drive Tier1_v31/V5/diagnose_cache/.

--version v5.1 diagnoses v5.1 (NK T folded into NK; research/notebooks/
v51_labels.py) the same way. Its held-out references use v5.1's labels.
It is compared with v4.1 (the v4.1 cache) and with v5 (v5's diagnosis
cache, checked against v5's diagnosis.json), under both truths:
- v5's cleaned labels;
- v5.1's, where NK T is NK.
Writes research/notebook-outputs/v51_diagnose/diagnosis.json; arrays go to
Drive Tier1_v31/V5/diagnose_cache_v51/. v5's diagnosis.json was written by
this script before the option existed (its sha256 is recorded in it).

    python research/notebooks/v5_diagnose.py      # from the repository root
    python research/notebooks/v5_diagnose.py --version v5.1
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v4_calibration as phase3  # noqa: E402
import v41_cache  # noqa: E402
import v41_core as core  # noqa: E402
import v5_build  # noqa: E402
import v5_checkpoint  # noqa: E402

from benchmark import baselines_v31, datasets  # noqa: E402
from service import config  # noqa: E402
from service.pipeline import alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v5_diagnose"
CACHE = phase3.T1 / "V5" / "diagnose_cache"
LABELS = v5_checkpoint.LABELS
VERSIONS = {
    "v5": {"labels": LABELS, "out": OUT, "cache": CACHE, "members": config.V5_MEMBERS_DIR},
    "v5.1": {"labels": REPO / "research" / "notebook-outputs" / "v51_labels" / "reference_labels_v51.csv.gz",
             "out": REPO / "research" / "notebook-outputs" / "v51_diagnose", "cache": phase3.T1 / "V5" / "diagnose_cache_v51",
             "members": config.V51_MEMBERS_DIR},
}
CACHE_FILES = ("calib_v5_arrays.npz", "dev_v5_arrays.npz", "calib_v5_cells.csv.gz", "dev_v5_cells.csv.gz")
V41 = {"w_on": 0.5, "tau": 0.05}
TNK = ("cd8-positive, alpha-beta t cell", "natural killer cell", "mature nk t cell", "cd4-positive, alpha-beta t cell",
       "naive thymus-derived cd4-positive, alpha-beta t cell", "regulatory t cell")


def centroids_from(latents, y, n):
    """v4_calibration.centroids_from, with a class without cells at zero (v5.1's NK T)."""
    Z = latents / np.linalg.norm(latents, axis=1, keepdims=True)
    C = np.stack([Z[y == k].mean(0) if (y == k).any() else np.zeros(Z.shape[1]) for k in range(n)])
    return C / np.maximum(np.linalg.norm(C, axis=1, keepdims=True), 1e-12)


def ingredients(bundle, smoothed, aligned) -> dict:
    """Ps, Pu (class-balanced members), P (the answers' members), R."""
    a = bundle.answers
    Zs = [m.encoder_handle.encode(smoothed, aligned.mask) for m in a.members]
    Zu = [m.encoder_handle.encode(aligned.values, aligned.mask) for m in a.members]
    probs = lambda Z, members: ensemble.ensemble_probabilities(  # noqa: E731
        [ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, members)]).astype(np.float32)
    return {"Ps": probs(Zs, bundle.members), "Pu": probs(Zu, bundle.members), "P31": probs(Zs, a.members),
            "R": fusion.masked_pearson(aligned.values, aligned.mask, bundle.class_means).astype(np.float32)}


def build(v5, y_clean, t0, members_dir):
    names, n = v5.class_names, len(v5.class_names)
    split = np.load(phase3.NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    table = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    a5 = v5.answers
    v5c = dataclasses.replace(a5, members=phase3.restricted(
        a5.members, trainval, [centroids_from(m.reference_latents[trainval], y_clean[trainval], n) for m in a5.members]),
        property_values=a5.property_values[trainval])
    X = v5_build.bundle.load_rna(v5_build.bundle.RNA, v5.feature_genes, table["cell"].astype(str).tolist())[trainval]
    layer = v5_build.best_guess_layer({m.name: members_dir / m.name for m in a5.members}, y_clean[trainval], X, n)
    del X
    held = dataclasses.replace(v5, answers=v5c, class_means=layer["means"], members=phase3.restricted(
        v5.members, trainval, [layer["centroids_cb"][m.name] for m in v5.members]))
    print(f"held-out references ready ({time.time() - t0:.0f}s)", flush=True)
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    extra = json.loads(v41_cache.EXTRA.read_text())
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_X = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_X[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    genes = v5.feature_genes
    resolution = gene_ids.resolve_identifiers(genes)
    arrays, rows = {k: [] for k in ("Ps", "Pu", "P31", "R")}, []
    for s, source in [(s, "calib") for s in suites["calib"]] + [(s, "single_extra") for s in extra]:
        raw = phase3.raw_upload(s, get_raw, profiles, len(genes))
        ids = [f"{s['id']}_{i}" for i in range(len(raw))]
        smoothed, aligned, scale = pipeline._prepare_query(genes, alignment.RawMatrix(gene_names=genes, cell_ids=ids, values=raw.T))
        for k, v in ingredients(held, smoothed, aligned).items():
            arrays[k].append(v)
        response = ensemble.project_prepared(v5c, smoothed, aligned, scale, resolution, False, v5c.components)
        for i, cell in enumerate(response["cells"]):
            rows.append({"upload": s["id"], "source": source, "scenario": s["scenario"], "group": phase3.GROUP[s["scenario"]],
                         "row": int(s["cell_idx"][i]), "true": int(y_clean[s["cell_idx"][i]]), **v41_cache.answer_fields(cell)})
        if len({r["upload"] for r in rows}) % 50 == 0:
            print(f"calibration: {len({r['upload'] for r in rows})} uploads ({time.time() - t0:.0f}s)", flush=True)
    calib = (pd.DataFrame(rows), {k: np.concatenate(v) for k, v in arrays.items()}, v5c)

    pbmc_meta = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    weak = dict(zip(pbmc_meta["cell_id"].astype(str), pbmc_meta["weak_lineage"].astype(str)))
    uploads = [
        ("fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels()["label"].astype(str).tolist()),
        ("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), None),
        ("scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")["class_name"].astype(str).tolist()),
        ("scope2_reprocessed", datasets.load_scope2_reprocessed_upload(), datasets.load_scope2_reprocessed_labels()["label"].astype(str).tolist()),
        ("furtwangler2025", datasets.load_furtwangler2025_upload(), None),
    ]
    arrays, rows = {k: [] for k in ("Ps", "Pu", "P31", "R")}, []
    for name, raw, labels in uploads:
        smoothed, aligned, scale = pipeline._prepare_query(genes, raw)
        for k, v in ingredients(v5, smoothed, aligned).items():
            arrays[k].append(v)
        response = ensemble.project_prepared(v5.answers, smoothed, aligned, scale, gene_ids.resolve_identifiers(raw.gene_names),
                                             False, v5.answers.components)
        for i, cell in enumerate(response["cells"]):
            label = labels[i] if labels else weak.get(cell["cell_id"], "")
            rows.append({"dataset": name, "cell_id": cell["cell_id"], "label": label, **v41_cache.answer_fields(cell)})
        print(f"{name}: {len(response['cells'])} cells ({time.time() - t0:.0f}s)", flush=True)
    dev = (pd.DataFrame(rows), {k: np.concatenate(v) for k, v in arrays.items()})
    return calib, dev


def recall_table(truth, guess, multi, names) -> dict:
    order = [names.index(c) for c in TNK] + [k for k in range(len(names)) if names[k] not in TNK]
    return {names[k]: round(100 * float((guess[multi & (truth == k)] == k).mean()), 2)
            for k in order if (multi & (truth == k)).sum() >= 20}


def tnk_confusion(truth, guess, multi, names) -> dict:
    idx = [names.index(c) for c in TNK[:4]]
    out = {}
    for t in idx:
        m = multi & (truth == t)
        out[names[t]] = {**{names[g]: round(100 * float((guess[m] == g).mean()), 1) for g in idx},
                         "other": round(100 * float((~np.isin(guess[m], idx)).mean()), 1)}
    return out


def calibration_report(frames: dict, guesses: dict, sets: dict, truths: dict, rows: np.ndarray, multi: np.ndarray,
                       cal: np.ndarray, names: list, hierarchy: dict) -> dict:
    """Every guess under every truth. frames[g] carries the answers' abstentions
    behind guess g; sets[g] its conformal sets (None: no answers metrics)."""
    nm = np.array(names)
    out = {}
    for tag, y in truths.items():
        truth = y[rows]
        out[tag] = {}
        for g, guess in guesses.items():
            frame = frames[g].assign(true=truth)
            r = {"per_upload_balanced": {k: round(v, 2) for k, v in core.suite_scores(frame, guess).items()},
                 "recall_multi_type": recall_table(truth, guess, multi, names),
                 "tnk_confusion_multi_type": tnk_confusion(truth, guess, multi, names)}
            if sets.get(g) is not None:
                joined = None if g.endswith("_own") else guess
                r.update({k: round(v, 2) for k, v in core.answers(frame, sets[g], nm, hierarchy, joined, cal).items()})
            out[tag][g] = r
    return out


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=tuple(VERSIONS), default="v5")
    version = parser.parse_args().version
    V = VERSIONS[version]
    warnings.simplefilter("ignore")
    t0 = time.time()
    bundle = fusion.V4Bundle.load(require_evaluation=False, version=version)
    v41 = fusion.V4Bundle.load(require_evaluation=False, version="v4.1")
    names = bundle.class_names
    nm = np.array(names)
    table = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    truths = {}
    for tag, path in (("v5_truth", VERSIONS["v5"]["labels"]), ("v51_truth", VERSIONS["v5.1"]["labels"])):
        lab = pd.read_csv(path)
        if lab["cell"].tolist() != table["cell"].tolist():
            raise SystemExit(f"{path} is not in reference_metadata.csv's order")
        truths[tag] = lab["class_idx_clean"].to_numpy()
    own = truths["v5_truth" if version == "v5" else "v51_truth"]
    (calib, a_new, held_answers), (dev, d_new) = build(bundle, own, t0, V["members"])
    V["cache"].mkdir(parents=True, exist_ok=True)
    np.savez_compressed(V["cache"] / CACHE_FILES[0], **a_new)
    np.savez_compressed(V["cache"] / CACHE_FILES[1], **d_new)
    calib.to_csv(V["cache"] / CACHE_FILES[2], index=False, lineterminator="\n")
    dev.to_csv(V["cache"] / CACHE_FILES[3], index=False, lineterminator="\n")

    # v4.1's ingredients on the same cells: the v4.1 cache, rows aligned by construction
    v41_calib = pd.read_csv(core.CACHE / "calib_cells.csv.gz", keep_default_na=False)
    a41 = dict(np.load(core.CACHE / "calib_arrays.npz"))
    if not (v41_calib["upload"].tolist() == calib["upload"].tolist()
            and v41_calib["observed_genes"].tolist() == calib["observed_genes"].tolist()):
        raise SystemExit("the v4.1 cache's cells are not these cells")
    dev41 = pd.read_csv(core.CACHE / "dev_cells.csv.gz", keep_default_na=False, dtype={"cell_id": str})
    d41 = dict(np.load(core.CACHE / "dev_arrays.npz"))
    keep = (calib["observed_genes"] >= core.MIN_GENES).to_numpy()
    c = calib[keep].reset_index(drop=True)
    rows = c["row"].to_numpy()
    cal = (c["source"] == "calib").to_numpy()
    multi = (c["group"] != "single").to_numpy() & cal
    c41 = v41_calib[keep].reset_index(drop=True)
    A41, A = {k: v[keep] for k, v in a41.items()}, {k: v[keep] for k, v in a_new.items()}
    space = held_answers.components.label_space.estimate(None, names, False)
    frames = {"v3.1_own": c41, "v4.1_rule": c41, f"{version}_own": c, f"{version}_rule": c}
    guesses = {"v3.1_own": A41["P31"].argmax(1),
               "v4.1_rule": core.rule(A41, core.agreement(c41, A41, "upload"), V41["w_on"], V41["tau"]).argmax(1),
               f"{version}_own": A["P31"].argmax(1),
               f"{version}_rule": core.rule(A, core.agreement(c, A, "upload"), V41["w_on"], V41["tau"]).argmax(1)}
    s31 = v41.answers.components.calibrator.calibrate(A41["P31"].astype(np.float64), None, space).label_sets
    s_new = held_answers.components.calibrator.calibrate(A["P31"].astype(np.float64), None, space).label_sets
    sets = {"v3.1_own": s31, "v4.1_rule": s31, f"{version}_own": s_new, f"{version}_rule": s_new}
    dev_sets = {"v4.1": (d41, dev41), version: (d_new, dev)}
    if version != "v5":
        record = json.loads((OUT / "diagnosis.json").read_text())
        for f in CACHE_FILES:
            if hashlib.sha256((CACHE / f).read_bytes()).hexdigest() != record["sha256"][f]:
                raise SystemExit(f"{CACHE / f} does not match {OUT / 'diagnosis.json'}")
        c5 = pd.read_csv(CACHE / CACHE_FILES[2], keep_default_na=False)[keep].reset_index(drop=True)
        A5 = {k: v[keep] for k, v in dict(np.load(CACHE / CACHE_FILES[0])).items()}
        frames.update({"v5_own": c5, "v5_rule": c5})
        guesses.update({"v5_own": A5["P31"].argmax(1),
                        "v5_rule": core.rule(A5, core.agreement(c5, A5, "upload"), V41["w_on"], V41["tau"]).argmax(1)})
        v5_components = fusion.V4Bundle.load(require_evaluation=False, version="v5").answers.components
        s5 = v5_components.calibrator.calibrate(A5["P31"].astype(np.float64), None, space).label_sets
        sets.update({"v5_own": s5, "v5_rule": s5})
        dev_sets["v5"] = (dict(np.load(CACHE / CACHE_FILES[1])),
                          pd.read_csv(CACHE / CACHE_FILES[3], keep_default_na=False, dtype={"cell_id": str}))
    report = {"version": version,
              "calibration": calibration_report(frames, guesses, sets, truths, rows, multi, cal, names, bundle.hierarchy),
              "calibration_cells": {"all": int(len(c)), "multi_type": int(multi.sum())}}

    # development, in-sample and report-only
    def variants(A, frame):
        agv = core.agreement(frame, A, "dataset")
        n = A["Ps"].shape[1]
        on = V41["w_on"] * (0.5 * A["Ps"] + 0.5 * A["Pu"]) + (1 - V41["w_on"]) * core.softmax(A["R"] / V41["tau"])
        off = 0.7 * A["Ps"] + 0.3 / n
        return {"as_served": core.rule(A, agv, V41["w_on"], V41["tau"]), "correlation_forced_on": on,
                "correlation_forced_flat": off, "encoder_alone": 0.5 * A["Ps"] + 0.5 * A["Pu"],
                "correlation_alone": core.softmax(A["R"] / V41["tau"]), "answers_own": A["P31"]}, agv
    report["development"] = {}
    for label, (Ad, frame) in dev_sets.items():
        vs, agv = variants(Ad, frame)
        report["development"][label] = {k: {f: round(v, 3) for f, v in core.dev_figures(frame, P, nm).items()}
                                        for k, P in vs.items()}
        report["development"][label]["agreement"] = {ds: round(float(agv[(frame["dataset"] == ds).to_numpy()][0]), 4)
                                                     for ds in frame["dataset"].unique()}
    V["out"].mkdir(parents=True, exist_ok=True)
    (V["out"] / "diagnosis.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"),
        "spec_sha256": hashlib.sha256(fusion.version_files(version)[0].read_bytes()).hexdigest(),
        "cache_dir": "Drive Data/Results/Tier1_v31/V5/" + V["cache"].name,
        "sha256": {f: hashlib.sha256((V["cache"] / f).read_bytes()).hexdigest() for f in CACHE_FILES},
        **report, "seconds": round(time.time() - t0)}, indent=2) + "\n", newline="\n")
    print(json.dumps(report, indent=1), flush=True)


if __name__ == "__main__":
    main()
