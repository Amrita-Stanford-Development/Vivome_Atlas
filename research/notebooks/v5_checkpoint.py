"""v5, Phase 1 (research/todo.md, Track H): the checkpoint with the current
encoder.

The question: how far do the cleaned reference labels
(research/notebooks/v5_labels.py) go without retraining? It compares two
best guesses:
- v4.1, as served;
- v4.1 with its class-balanced centroids and RNA class means rebuilt from
  the cleaned labels. They are built by scripts/build_v4_bundle.py --labels,
  outside the repository: Drive Tier1_v31/V5/clean_all for the development
  data, clean_calib for the calibration cells (NB1's train and validation
  rows).

The answers (v3.1's conformal sets) are unchanged, and the guess joins them,
as in v4.1. v4.1's settings are fixed: gate-on encoder weight 0.5,
correlation temperature 0.05, smoothed share 0.5, agreement gate 0.4,
gate-off weight 0.7. Nothing is chosen here; the script only reports. Its
figures set what retraining (Phase 2) has to add, and are the fallback if
retraining fails.

Cells: those of research/notebooks/v41_cache.py, which are
- NB3c's calibration suite (240 uploads) and the 60 extra single-type
  uploads, all from te_cal;
- the development datasets.
Khoury 2026 and te_eval are not read.

Truth is the cleaned labels at each cell's reference row; the original
labels are reported beside them.

Self-check: computed in the same pass, the ingredients with v4.1's own
centroids and class means must match the v4.1 cache
(research/notebook-outputs/v41_pretest/cache_record.json) within 1e-5.

Reports, in research/notebook-outputs/v5_checkpoint/checkpoint.json:
- calibration cells (at least 200 genes), for v3.1's guess, v4.1 and v4.1
  with cleaned centroids:
  - per-upload balanced accuracy, overall and by scenario group;
  - per-class recall over the cells of multi-type uploads (every group but
    single), CD8 T, NK and NK T first;
  - coverage, committed share and correct-when-committed, with the guess
    joined to v3.1's sets;
  - single-type robustness against v4.1;
- development: research/notebooks/v41_core.dev_figures, which covers
  - Fulcher's six-type balanced accuracy and per-type recall;
  - PBMC240;
  - both SCoPE2 versions;
  - the out-of-reference AUROC.

The arrays go to Drive Tier1_v31/V5/checkpoint_cache/.

    python research/notebooks/v5_checkpoint.py      # from the repository root
    python research/notebooks/v5_checkpoint.py --smoke      # 4 + 2 uploads, nothing written
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

from benchmark import baselines_v31, datasets  # noqa: E402
from service.pipeline import alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

V5 = phase3.T1 / "V5"
CLEAN_ALL, CLEAN_CALIB, CACHE = V5 / "clean_all", V5 / "clean_calib", V5 / "checkpoint_cache"
LABELS = REPO / "research" / "notebook-outputs" / "v5_labels" / "reference_labels_clean.csv.gz"
OUT = REPO / "research" / "notebook-outputs" / "v5_checkpoint"
V41 = {"w_on": 0.5, "tau": 0.05}
FIRST = ("cd8-positive, alpha-beta t cell", "natural killer cell", "mature nk t cell")
TOLERANCE = 1e-5


def clean_files(bundle: Path, members, labels_sha: str) -> tuple[list, np.ndarray]:
    spec = json.loads((bundle / "spec_v4.json").read_text())
    if labels_sha not in spec["reference"].get("labels", ""):
        raise SystemExit(f"{bundle} was not built from {LABELS.name} as it is now")
    cb = [np.load(bundle / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy") for m in members]
    return cb, np.load(bundle / "class_means_cb.npy")


def two_ingredients(members31, members4, clean4, means, clean_means, smoothed, aligned) -> tuple[dict, dict]:
    """v41_cache.ingredients for two reference sides, encoding the cells once."""
    Zs = [m.encoder_handle.encode(smoothed, aligned.mask) for m in members4]
    Zu = [m.encoder_handle.encode(aligned.values, aligned.mask) for m in members4]
    probs = lambda Z, members: ensemble.ensemble_probabilities(  # noqa: E731
        [ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, members)]).astype(np.float32)
    p31 = probs(Zs, members31)
    pearson = lambda m: fusion.masked_pearson(aligned.values, aligned.mask, m).astype(np.float32)  # noqa: E731
    return ({"Ps": probs(Zs, members4), "Pu": probs(Zu, members4), "P31": p31, "R": pearson(means)},
            {"Ps": probs(Zs, clean4), "Pu": probs(Zu, clean4), "P31": p31, "R": pearson(clean_means)})


def build(v4, y, labels_sha, t0, smoke):
    v31, names, n = v4.answers, v4.class_names, len(v4.class_names)
    split = np.load(phase3.NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    extra = json.loads(v41_cache.EXTRA.read_text())
    if smoke:
        suites["calib"], extra = suites["calib"][:4], extra[:2]
    te_cal = set(np.asarray(suites["te_cal"]).tolist())
    for s in suites["calib"] + extra:
        if not set(s["cell_idx"]) <= te_cal:
            raise SystemExit(f"{s['id']} draws outside te_cal")
    v31_centroids = [phase3.centroids_from(m.reference_latents[trainval], y[trainval], n) for m in v31.members]
    v31c = dataclasses.replace(v31, members=phase3.restricted(v31.members, trainval, v31_centroids),
                               property_values=v31.property_values[trainval])
    cb = [np.load(phase3.CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy")
          for m in v4.members]
    members4 = phase3.restricted(v4.members, trainval, cb)
    clean_cb, clean_means = clean_files(CLEAN_CALIB, v4.members, labels_sha)
    clean4 = phase3.restricted(v4.members, trainval, clean_cb)
    means = np.load(phase3.CALIB_BUNDLE / "class_means_cb.npy")
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_X = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_X[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    genes = v4.feature_genes
    resolution = gene_ids.resolve_identifiers(genes)
    orig, clean, rows = {k: [] for k in ("Ps", "Pu", "P31", "R")}, {k: [] for k in ("Ps", "Pu", "R")}, []
    for s, source in [(s, "calib") for s in suites["calib"]] + [(s, "single_extra") for s in extra]:
        raw = phase3.raw_upload(s, get_raw, profiles, len(genes))
        ids = [f"{s['id']}_{i}" for i in range(len(raw))]
        smoothed, aligned, scale = pipeline._prepare_query(genes, alignment.RawMatrix(gene_names=genes, cell_ids=ids, values=raw.T))
        a, b = two_ingredients(v31c.members, members4, clean4, means, clean_means, smoothed, aligned)
        for k in orig:
            orig[k].append(a[k])
        for k in clean:
            clean[k].append(b[k])
        response = ensemble.project_prepared(v31c, smoothed, aligned, scale, resolution, False, v31c.components)
        for i, cell in enumerate(response["cells"]):
            rows.append({"upload": s["id"], "source": source, "scenario": s["scenario"], "group": phase3.GROUP[s["scenario"]],
                         "row": int(s["cell_idx"][i]), "true": int(y[s["cell_idx"][i]]), **v41_cache.answer_fields(cell)})
        if len({r["upload"] for r in rows}) % 50 == 0:
            print(f"calibration: {len({r['upload'] for r in rows})} uploads ({time.time() - t0:.0f}s)", flush=True)
    calib = (pd.DataFrame(rows), {k: np.concatenate(v) for k, v in orig.items()}, {k: np.concatenate(v) for k, v in clean.items()})

    pbmc_meta = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    weak = dict(zip(pbmc_meta["cell_id"].astype(str), pbmc_meta["weak_lineage"].astype(str)))
    uploads = [
        ("fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels()["label"].astype(str).tolist()),
        ("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), None),
        ("scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")["class_name"].astype(str).tolist()),
        ("scope2_reprocessed", datasets.load_scope2_reprocessed_upload(), datasets.load_scope2_reprocessed_labels()["label"].astype(str).tolist()),
        ("furtwangler2025", datasets.load_furtwangler2025_upload(), None),
    ]
    dev_clean_cb, dev_clean_means = clean_files(CLEAN_ALL, v4.members, labels_sha)
    dev_clean4 = tuple(dataclasses.replace(m, centroids=c) for m, c in zip(v4.members, dev_clean_cb))
    orig, clean, rows = {k: [] for k in ("Ps", "Pu", "P31", "R")}, {k: [] for k in ("Ps", "Pu", "R")}, []
    for name, raw, labels in uploads:
        smoothed, aligned, scale = pipeline._prepare_query(v4.feature_genes, raw)
        a, b = two_ingredients(v31.members, v4.members, dev_clean4, v4.class_means, dev_clean_means, smoothed, aligned)
        for k in orig:
            orig[k].append(a[k])
        for k in clean:
            clean[k].append(b[k])
        response = ensemble.project_prepared(v31, smoothed, aligned, scale, gene_ids.resolve_identifiers(raw.gene_names),
                                             False, v31.components)
        for i, cell in enumerate(response["cells"]):
            label = labels[i] if labels else weak.get(cell["cell_id"], "")
            rows.append({"dataset": name, "cell_id": cell["cell_id"], "label": label, **v41_cache.answer_fields(cell)})
        print(f"{name}: {len(response['cells'])} cells ({time.time() - t0:.0f}s)", flush=True)
    dev = (pd.DataFrame(rows), {k: np.concatenate(v) for k, v in orig.items()}, {k: np.concatenate(v) for k, v in clean.items()})
    return calib, dev


def self_check(a: dict, d: dict, smoke: bool) -> dict:
    """The v4.1-side ingredients against the v4.1 cache, file by file."""
    record = json.loads(core.RECORD.read_text())
    out = {}
    for tag, mine, name in (("calibration", a, "calib_arrays.npz"), ("development", d, "dev_arrays.npz")):
        if hashlib.sha256((core.CACHE / name).read_bytes()).hexdigest() != record["sha256"][name]:
            raise SystemExit(f"{core.CACHE / name} does not match {core.RECORD}")
        cached = np.load(core.CACHE / name)
        out[tag] = {k: float(np.abs(mine[k] - cached[k][:len(mine[k])]).max()) for k in mine}
    out["passed"] = all(v <= TOLERANCE for r in out.values() if isinstance(r, dict) for v in r.values())
    if smoke:
        out["note"] = "smoke: not enforced; the calibration rows past the first uploads are not the cache's"
    return out


def calibration_report(calib: pd.DataFrame, a: dict, b: dict, v4, y_clean: np.ndarray) -> dict:
    names = np.array(v4.class_names)
    keep = (calib["observed_genes"] >= core.MIN_GENES).to_numpy()
    c = calib[keep].reset_index(drop=True)
    a, b = {k: v[keep] for k, v in a.items()}, {k: v[keep] for k, v in b.items()}
    cal = (c["source"] == "calib").to_numpy()
    space = v4.answers.components.label_space.estimate(None, list(names), False)
    sets = v4.answers.components.calibrator.calibrate(a["P31"].astype(np.float64), None, space).label_sets
    guesses = {"v3.1": a["P31"].argmax(1),
               "v4.1": core.rule(a, core.agreement(c, a, "upload"), V41["w_on"], V41["tau"]).argmax(1),
               "v4.1_clean_centroids": core.rule(b, core.agreement(c, b, "upload"), V41["w_on"], V41["tau"]).argmax(1)}
    multi = (c["group"] != "single").to_numpy() & cal
    order = [names.tolist().index(x) for x in FIRST] + [k for k in range(len(names)) if names[k] not in FIRST]
    report = {}
    for truth_name, truth in (("cleaned", y_clean[c["row"].to_numpy()]), ("original", c["true"].to_numpy())):
        ct = c.assign(true=truth)
        r = {}
        for g, guess in guesses.items():
            recall = {names[k]: round(100 * float((guess[multi & (truth == k)] == k).mean()), 2)
                      for k in order if (multi & (truth == k)).sum() >= 20}
            r[g] = {"per_upload_balanced": {k: round(v, 2) for k, v in core.suite_scores(ct, guess).items()},
                    "recall_multi_type": recall,
                    **{k: round(v, 2) for k, v in core.answers(ct, sets, names, v4.answers.hierarchy,
                                                               None if g == "v3.1" else guess, cal).items()}}
        r["robustness_clean_vs_v41"] = {k: round(v, 3) for k, v in
                                        core.robustness(ct, guesses["v4.1_clean_centroids"], guesses["v4.1"]).items()}
        report[truth_name] = r
    report["cells"] = {"all": int(len(c)), "multi_type": int(multi.sum()),
                       "multi_type_by_cleaned_class": {names[k]: int((multi & (y_clean[c["row"].to_numpy()] == k)).sum()) for k in order[:3]}}
    return report


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
    y = np.array([names.index(x) for x in table["class_name"]])
    lab = pd.read_csv(LABELS)
    if lab["cell"].tolist() != table["cell"].tolist():
        raise SystemExit(f"{LABELS} is not in reference_metadata.csv's order")
    y_clean = lab["class_idx_clean"].to_numpy()
    labels_sha = hashlib.sha256(LABELS.read_bytes()).hexdigest()
    (calib, a, b), (dev, d, e) = build(v4, y, labels_sha, t0, smoke)
    b["P31"], e["P31"] = a["P31"], d["P31"]  # the answers are v3.1's on both sides
    check = self_check(a, d, smoke)
    print(json.dumps(check, indent=1), flush=True)
    if not check["passed"] and not smoke:
        raise SystemExit("STOP: the v4.1 side does not reproduce the v4.1 cache")
    report = {"calibration": calibration_report(calib, a, b, v4, y_clean)}
    nm = np.array(names)
    report["development"] = {
        "v4.1": {k: round(v, 4) for k, v in core.dev_figures(dev, core.rule(d, core.agreement(dev, d, "dataset"), V41["w_on"], V41["tau"]), nm).items()},
        "v4.1_clean_centroids": {k: round(v, 4) for k, v in core.dev_figures(dev, core.rule(e, core.agreement(dev, e, "dataset"), V41["w_on"], V41["tau"]), nm).items()}}
    print(json.dumps(report, indent=1), flush=True)
    if smoke:
        print(f"smoke: nothing written ({time.time() - t0:.0f}s)")
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE / "calib_clean_arrays.npz", **b)
    np.savez_compressed(CACHE / "dev_clean_arrays.npz", **e)
    calib.to_csv(CACHE / "calib_cells.csv.gz", index=False, lineterminator="\n")
    files = ("calib_clean_arrays.npz", "dev_clean_arrays.npz", "calib_cells.csv.gz")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "checkpoint.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"),
        "labels_sha256": labels_sha,
        "clean_bundles": {p.name: hashlib.sha256((p / "MANIFEST.json").read_bytes()).hexdigest() for p in (CLEAN_ALL, CLEAN_CALIB)},
        "cache_dir": "Drive Data/Results/Tier1_v31/V5/checkpoint_cache",
        "sha256": {f: hashlib.sha256((CACHE / f).read_bytes()).hexdigest() for f in files},
        "self_check": check, **report, "seconds": round(time.time() - t0),
    }, indent=2) + "\n", newline="\n")
    print(f"written ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
