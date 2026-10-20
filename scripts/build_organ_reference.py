"""Builds an organ's reference from its RNA atlas (research/organ-references.md,
Stage 1), the steps the blood reference took in the Colab notebooks, in order:

  labels     the classes (scripts/organ_reference/labels.py)
  space      the gene space (gene_space.py)
  gene_ids   the gene space's identifier map from HGNC (gene_ids.py), for the service's resolver
  stats      the RNA's whole-reference statistics and the split (scenarios.split)
  profiles   real missingness profiles (profiles.py)
  modules    co-expression modules (modules.py); blood takes its served ones
  suites     the calibration and evaluation uploads (scenarios.suites)
  train      the five members (calibrate.train_member, NB1d's recipe)
  calibrate  temperatures, conformal thresholds, out-of-distribution threshold (NB2's recipe)
  layer      class-balanced statistics, class means and centroids (v4.1's best guess)
  bundle     the reference's files, in v4.1's layout, with a MANIFEST
             (organ_reference/bundle.py), into the work folder's bundle/

Each stage reads the earlier stages' files from the organ's work folder,
drive/Data/Results/Organs/<organ>/, and writes its own there.

Blood is built only to prove the builder, so its calibrate and layer stages
run on the served v3.1 members instead of training its own.

"accept" checks blood's build against the served blood reference, in the
tiers research/organ-references.md fixes (1 and 2 on the data stages, 3 on
the calibration, 2 again on the layer), "accept_loader" tier 4 (the bundle
layout and loader) and "accept_training" tier 5 (seed 1 retrained).
Records: research/notebook-outputs/organ_builder_blood/.

    python scripts/build_organ_reference.py blood labels space stats profiles modules suites
    python scripts/build_organ_reference.py blood calibrate layer bundle accept accept_loader accept_training
    python scripts/build_organ_reference.py large_intestine labels space stats profiles modules suites train calibrate layer
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
import torch  # noqa: E402

from organ_reference import bundle, calibrate, data, gene_ids, gene_space, labels, modules, profiles, scenarios  # noqa: E402

STAGES = ("labels", "space", "gene_ids", "stats", "profiles", "modules", "suites", "train", "calibrate", "layer", "bundle")
CHECKS = ("accept", "accept_loader", "accept_training")
ACCEPT_OUT = REPO / "research" / "notebook-outputs" / "organ_builder_blood"


class Build:
    """One organ's build: its file, its work folder, and what earlier stages wrote."""

    def __init__(self, organ: str):
        self.organ = organ
        self.cfg = data.load_organ(organ)
        self.dir = data.work_dir(organ)
        self._X = None

    def path(self, name: str) -> Path:
        return self.dir / name

    def table(self) -> pd.DataFrame:
        return pd.read_csv(self.path("labels.csv.gz"), keep_default_na=False)

    def names(self) -> list[str]:
        return json.loads(self.path("classes.json").read_text(encoding="utf-8"))["class_order"]

    def space(self) -> list[str]:
        return pd.read_csv(self.path("feature_space_genes.csv"))["gene"].astype(str).str.upper().tolist()

    def X(self) -> np.ndarray:
        """The RNA over the gene space, the reference's cells (labels.csv.gz's rows), cached."""
        if self._X is None:
            t = time.time()
            self._X = data.load_rna(data.resolve(self.cfg["rna"]), self.space())
            rows = self.table()["row"].to_numpy()
            if len(rows) != len(self._X) or not np.array_equal(rows, np.arange(len(rows))):
                self._X = self._X[rows]
            print(f"RNA {self._X.shape} in {time.time() - t:.0f}s", flush=True)
        return self._X


# ---- stages ----

def stage_labels(b: Build) -> None:
    table, names = labels.build(b.cfg)
    table.to_csv(b.path("labels.csv.gz"), index=False, lineterminator="\n")
    data.save_json(b.path("classes.json"), {"class_order": names, "hierarchy": b.cfg["hierarchy"]})
    labels.by_donor(table).to_csv(b.path("classes_by_donor.csv"), lineterminator="\n")
    np.save(b.path("y_all.npy"), table["class_idx"].to_numpy(np.int64))
    np.save(b.path("donors.npy"), table["donor"].to_numpy().astype(str))
    print(f"{len(table):,} cells, {len(names)} classes, {table['donor'].nunique()} donors")


def stage_space(b: Build) -> None:
    space, record = gene_space.build(b.cfg)  # upper case, as NB1 wrote the served list
    pd.DataFrame({"gene": space}).to_csv(b.path("feature_space_genes.csv"), index=False, lineterminator="\n")
    data.save_json(b.path("feature_space_provenance.json"), record)
    print(json.dumps(record))


def stage_gene_ids(b: Build) -> None:
    g = b.cfg["gene_ids"]
    path = data.resolve(g["hgnc"])
    if sha256(path) != g["sha256"]:
        raise SystemExit(f"{path} is not the HGNC file the organ file names")
    table = gene_ids.build(pd.read_csv(b.path("feature_space_genes.csv"))["gene"].astype(str).tolist(), path)
    table.to_csv(b.path("gene_id_map.tsv"), sep="\t", index=False, lineterminator="\n")
    data.save_json(b.path("gene_id_map_provenance.json"), {
        "source": g["source"], "sha256": g["sha256"], "feature_space_genes": len(table),
        "match_counts": table["match_type"].value_counts().to_dict(),
        "resolution_method": "scripts/organ_reference/gene_ids.py (service/model/runtime/gene_id_map_v1_provenance.json's rule)"})
    print(table["match_type"].value_counts().to_dict())


def reused_split(b: Build) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A later version's split (organ references v2): the base organ's own,
    carried over through the atlas rows, so each cell keeps its part and the
    test cells are the base's test cells minus any dropped classes."""
    base = Build(b.cfg["split"]["reuse_from"])
    if base.cfg["rna"] != b.cfg["rna"]:
        raise SystemExit(f"{b.cfg['split']['reuse_from']} reads another RNA file; its rows are not this organ's rows")
    position = {int(r): i for i, r in enumerate(b.table()["row"].to_numpy())}
    rows = base.table()["row"].to_numpy()
    old = np.load(base.path("splits_seed0.npz"))
    part = lambda name: np.sort(np.array([position[int(r)] for r in rows[old[name]] if int(r) in position], dtype=np.int64))  # noqa: E731
    return part("train"), part("val"), part("test")


def stage_stats(b: Build) -> None:
    X = b.X()
    np.savez(b.path("rna_global_stats.npz"), mu=X.mean(0), sd=X.std(0))
    y, donors = np.load(b.path("y_all.npy")), np.load(b.path("donors.npy"))
    TR, VA, TE = reused_split(b) if b.cfg["split"].get("reuse_from") else scenarios.split(b.cfg, y, donors)
    if len(TR) + len(VA) + len(TE) != len(y) or len(np.unique(np.concatenate([TR, VA, TE]))) != len(y):
        raise SystemExit("the split does not partition the reference's cells")
    np.savez(b.path("splits_seed0.npz"), train=TR, val=VA, test=TE)
    print(f"train {len(TR):,} val {len(VA):,} test {len(TE):,}")


def stage_profiles(b: Build) -> None:
    space = b.space()
    members = gene_space.membership(b.cfg, space)
    mu = np.load(b.path("rna_global_stats.npz"))["mu"]

    def other(organ: str):
        o = Build(organ)
        return dict(np.load(o.path("mask_profiles.npz"))), np.load(o.path("rna_global_stats.npz"))["mu"]

    arrays, rows = profiles.build(b.cfg, space, members, mu, other)
    np.savez(b.path("mask_profiles.npz"), **arrays)
    pd.DataFrame(rows).to_csv(b.path("mask_profiles_summary.csv"), index=False, lineterminator="\n")
    print(pd.DataFrame(rows).to_string(index=False))


def stage_modules(b: Build) -> None:
    m = b.cfg["modules"]
    mod = modules.build(b.X(), m["target_size"], m["cells"], m["pca"], m["seed"])
    np.save(b.path("module_assignment_built.npy"), mod)
    sizes = np.bincount(mod)
    print(f"{len(sizes)} modules, median {np.median(sizes):.0f}, min {sizes.min()}, max {sizes.max()}")
    if b.organ == "blood":  # the served blood encoder's modules (Reference_Projection_v3's run); see modules.py
        served = np.load(data.DRIVE / "Results" / "ReferenceProjection_v3" / "export" / "module_assignment.npy")
        np.save(b.path("module_assignment.npy"), served)
    else:
        np.save(b.path("module_assignment.npy"), mod)


def stage_suites(b: Build) -> None:
    y, split = np.load(b.path("y_all.npy")), np.load(b.path("splits_seed0.npz"))
    calib, evals = scenarios.suites(b.cfg, y, b.names(), split["val"], split["test"])
    b.path("sim_suite_calib_v1.json").write_text(json.dumps(calib), encoding="utf-8")
    b.path("sim_suite_eval_v1.json").write_text(json.dumps(evals), encoding="utf-8")
    print(f"suites: {len(calib)} calibration uploads ({sum(len(s['cell_idx']) for s in calib):,} cells), "
          f"{len(evals)} evaluation uploads ({sum(len(s['cell_idx']) for s in evals):,} cells)")


# ---- blood's acceptance ----

def member_paths(b: Build) -> dict:
    """The members to calibrate: the served v3.1 checkpoints for blood, the
    organ's own (train stage) otherwise."""
    if b.organ == "blood":
        spec = json.loads((REPO / "service" / "model" / "v3_1" / "nb2_spec_v31.json").read_text(encoding="utf-8"))
        return {n: REPO / "service" / "model" / "v3_1" / "members" / n for n in spec["encoder"]["members"]}
    return {f"V2_batchgene_aug_seed{k}.pt": b.path("ckpt") / f"V2_batchgene_aug_seed{k}.pt" for k in b.cfg["train"]["seeds"]}


def _setup(b: Build) -> dict:
    stats = np.load(b.path("rna_global_stats.npz"))
    return calibrate.setup(b.X(), stats["mu"], stats["sd"], np.load(b.path("module_assignment.npy")),
                           np.load(b.path("y_all.npy")), np.load(b.path("splits_seed0.npz")))


def stage_train(b: Build) -> None:
    if b.organ == "blood":
        raise SystemExit("blood uses the served members; its training is checked by accept_training")
    s, arch = _setup(b), b.cfg["train"]
    b.path("ckpt").mkdir(exist_ok=True)
    record = {}
    for seed in arch["seeds"]:
        path = b.path("ckpt") / f"V2_batchgene_aug_seed{seed}.pt"
        print(f"[seed {seed}] training", flush=True)
        model, info = calibrate.train_member(s, seed, arch)
        torch.save(model.state_dict(), path)
        best = min(info["history"], key=lambda r: r["val_loss"])
        record[path.name] = {"sha256": sha256(path), "best_val_loss": float(info["best_val_loss"]),
                             "balanced": round(100 * best["val_bal"], 2), "epochs_run": info["epochs_run"],
                             "seconds": round(info["seconds"])}
        print(f"   {json.dumps(record[path.name])}", flush=True)
        del model
        torch.cuda.empty_cache()
    data.save_json(b.path("train_record.json"), {"run": datetime.now().isoformat(timespec="seconds"),
                                                 "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
                                                 "members": record})


def stage_calibrate(b: Build) -> None:
    s, arch = _setup(b), b.cfg["train"]
    paths = member_paths(b)
    models = {n: calibrate.load_model(p, s, arch) for n, p in paths.items()}
    suite = json.loads(b.path("sim_suite_calib_v1.json").read_text(encoding="utf-8"))
    got = calibrate.calibrate(models, s, b.X(), dict(np.load(b.path("mask_profiles.npz"))), suite, b.names(),
                              b.cfg["calibration"], log=lambda m: print(m, flush=True), hierarchy=b.cfg["hierarchy"])
    b.path("members").mkdir(exist_ok=True)
    for name in paths:
        seed = name.split("seed")[1].split(".")[0]
        np.save(b.path("members") / f"V2_seed{seed}_reference_latent_f16.npy", got["latents"][name])
        np.save(b.path("members") / f"V2_seed{seed}_centroids.npy", got["centroids"][name].astype(np.float32))
    np.savez(b.path("calibration_scores.npz"), scores=got["scores"], y=got["y"], upload=got["upload"])
    data.save_json(b.path("calibration.json"), {k: got[k] for k in (
        "temperature", "qhat_by_class", "marginal_qhat", "ood_threshold", "n_uploads", "n_cells", "cells_per_class",
        "suite_top1_accuracy") if k in got} | {k: got[k] for k in ("qhat_options",) if k in got}
        | {"members": {n: sha256(p) for n, p in paths.items()}})
    print(json.dumps({k: got[k] for k in ("temperature", "marginal_qhat", "ood_threshold", "suite_top1_accuracy")}, indent=1))


def stage_layer(b: Build) -> None:
    layer = calibrate.best_guess_layer(member_paths(b), np.load(b.path("y_all.npy")), b.X(), len(b.names()))
    b.path("members").mkdir(exist_ok=True)
    np.savez(b.path("class_balanced_stats.npz"), mu=layer["mu"], sd=layer["sd"])
    np.save(b.path("class_means_cb.npy"), layer["means"])
    for name, C in layer["centroids_cb"].items():
        np.save(b.path("members") / f"V2_seed{name.split('seed')[1].split('.')[0]}_centroids_cb.npy", C)
    print(f"class means {layer['means'].shape}; centroids for {len(layer['centroids_cb'])} members")


def stage_bundle(b: Build) -> None:
    label = b.cfg.get("reference_version", f"{b.organ} v1")
    evaluation = {"status": "pending", "record": None}
    bundle.write(b.dir, b.path("bundle"), b.cfg, label, evaluation, member_paths(b))
    print(f"wrote {b.path('bundle')} ({label}, evaluation pending)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _differences(fresh, frozen, where="response", out=None) -> list:
    """service/tests/test_pipeline_versions.assert_same's rule, as a list:
    exact for keys, labels and every non-float; floats within rel 1e-6, abs 5e-6."""
    import math
    out = [] if out is None else out
    if isinstance(frozen, dict):
        if sorted(fresh) != sorted(frozen):
            out.append(f"{where}: keys differ")
            return out
        for key in frozen:
            _differences(fresh[key], frozen[key], f"{where}.{key}", out)
    elif isinstance(frozen, list):
        if len(fresh) != len(frozen):
            out.append(f"{where}: length differs")
            return out
        for i, (x, z) in enumerate(zip(fresh, frozen)):
            _differences(x, z, f"{where}[{i}]", out)
    elif isinstance(frozen, float):
        if not math.isclose(fresh, frozen, rel_tol=1e-6, abs_tol=5e-6):
            out.append(f"{where}: {fresh} != {frozen}")
    elif fresh != frozen:
        out.append(f"{where}: {fresh!r} != {frozen!r}")
    return out


def accept_loader(b: Build) -> None:
    """Tier 4: blood's served files assembled in the organ layout and loaded by
    bundle.load reproduce v4.1's frozen responses (service/tests/fixtures,
    v41_full_*.json) exactly, under the service tests' float rule. The bundle
    built from the rebuilt files (the bundle stage) is reported: label
    agreement with the same responses."""
    if b.organ != "blood":
        raise SystemExit("accept_loader compares with the served blood responses")
    from unittest import mock

    from service import config
    from service.pipeline import pipeline
    from service.tests.test_golden_fixtures import _load_pbmc240_50, _load_scope2_50
    fixtures = REPO / "service" / "tests" / "fixtures"
    raws = {"scope2": _load_scope2_50(), "pbmc240": _load_pbmc240_50()}
    served_dir = b.path("bundle_served")
    bundle.assemble_served_blood(served_dir)
    results = {}
    for which, directory in (("served_files", served_dir), ("rebuilt_files", b.path("bundle"))):
        if not directory.exists():
            continue
        loaded = bundle.load(directory)
        for name, raw in raws.items():
            for mode, restrict in (("default", False), ("restricted", True)):
                frozen = json.loads((fixtures / f"v41_full_{name}_{mode}.json").read_text(encoding="utf-8"))
                with mock.patch.object(config, "ATLAS_VERSION", frozen["atlas_version"]):
                    fresh = json.loads(json.dumps(pipeline.run_projection(loaded, raw, restrict_to_supported_classes=restrict)))
                diffs = _differences(fresh, frozen)
                same_labels = [c.get("label") == z.get("label") and c.get("label_level") == z.get("label_level")
                               for c, z in zip(fresh["cells"], frozen["cells"])]
                results[f"{which}/{name}_{mode}"] = {"differences": len(diffs), "first": diffs[:5],
                                                     "label_agreement": round(100 * float(np.mean(same_labels)), 2)}
    checks = {k: v["differences"] == 0 for k, v in results.items() if k.startswith("served_files/")}
    out = {"script_sha256": sha256(Path(__file__)), "run": datetime.now().isoformat(timespec="seconds"),
           "tier": "4 (bundle layout and loader)", "checks": checks, "results": results, "passed": all(checks.values())}
    data.save_json(ACCEPT_OUT / "loader.json", out)
    print(json.dumps(out, indent=1))


def accept(b: Build) -> None:
    """research/organ-references.md, Stage 1, "Blood acceptance": tiers 1 and 2
    on the data stages (the training and calibration tiers are added when
    those stages run)."""
    if b.organ != "blood":
        raise SystemExit("accept compares blood's build with the served blood reference")
    nb1 = data.NB1
    record, checks = {}, {}
    # tier 1, exact
    checks["y_all"] = bool(np.array_equal(np.load(b.path("y_all.npy")), np.load(nb1 / "y_all.npy")))
    mine, theirs = np.load(b.path("splits_seed0.npz")), np.load(nb1 / "splits_seed0.npz")
    checks["splits"] = all(np.array_equal(mine[k], theirs[k]) for k in ("train", "val", "test"))
    for s in ("calib", "eval"):
        checks[f"suite_{s}"] = sha256(b.path(f"sim_suite_{s}_v1.json")) == sha256(nb1 / f"sim_suite_{s}_v1.json")
        if not checks[f"suite_{s}"]:
            checks[f"suite_{s}"] = (json.loads(b.path(f"sim_suite_{s}_v1.json").read_text())
                                    == json.loads((nb1 / f"sim_suite_{s}_v1.json").read_text()))
    served_genes = pd.read_csv(REPO / "service" / "model" / "runtime" / "feature_space_genes.csv")["gene"].astype(str)
    built_genes = pd.read_csv(b.path("feature_space_genes.csv"))["gene"].astype(str)
    checks["genes"] = served_genes.tolist() == built_genes.tolist()
    served_map = pd.read_csv(REPO / "service" / "model" / "runtime" / "gene_id_map_v1.tsv", sep="\t", dtype=str, keep_default_na=False)
    built_map = pd.read_csv(b.path("gene_id_map.tsv"), sep="\t", dtype=str, keep_default_na=False)
    checks["gene_id_map"] = served_map.equals(built_map)
    record["genes_upper_equal"] = served_genes.str.upper().tolist() == built_genes.str.upper().tolist()
    spec = json.loads((REPO / "service" / "model" / "v3_1" / "nb2_spec_v31.json").read_text(encoding="utf-8"))
    classes = json.loads(b.path("classes.json").read_text(encoding="utf-8"))
    checks["class_order"] = classes["class_order"] == spec["class_order"]
    checks["hierarchy"] = classes["hierarchy"] == spec["hierarchy"]
    meta = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    t = b.table()
    checks["reference_metadata"] = (t["cell"].astype(str).tolist() == meta["cell"].astype(str).tolist()
                                    and t["class_idx"].tolist() == meta["class_idx"].tolist()
                                    and t["lineage"].tolist() == meta["lineage"].tolist())
    # tier 2, within tolerance
    a, z = np.load(b.path("rna_global_stats.npz")), np.load(nb1 / "rna_global_stats.npz")
    gap = max(float(np.abs(a["mu"] - z["mu"]).max()), float(np.abs(a["sd"] - z["sd"]).max()))
    record["rna_stats_largest_difference"] = gap
    checks["rna_stats"] = gap <= 1e-4
    a, z = dict(np.load(b.path("mask_profiles.npz"))), dict(np.load(nb1 / "mask_profiles.npz"))
    gaps = {}
    for k in sorted(z):
        if k not in a or a[k].shape != z[k].shape:
            gaps[k] = "missing or another shape"
            continue
        if z[k].dtype == bool:
            gaps[k] = int((a[k] != z[k]).sum())
        else:
            same_nan = np.array_equal(np.isnan(a[k]), np.isnan(z[k]))
            gaps[k] = float(np.nanmax(np.abs(a[k] - z[k]))) if same_nan else "NaN pattern differs"
    record["mask_profiles"] = gaps
    checks["mask_profiles"] = all((g == 0 if isinstance(g, int) else isinstance(g, float) and g <= 1e-6) for g in gaps.values())
    built, served = np.load(b.path("module_assignment_built.npy")), np.load(b.path("module_assignment.npy"))
    from sklearn.metrics import adjusted_rand_score
    record["modules_adjusted_rand_built_vs_served"] = round(float(adjusted_rand_score(served, built)), 4)
    ACCEPT_OUT.mkdir(parents=True, exist_ok=True)
    out = {"script_sha256": sha256(Path(__file__)), "run": datetime.now().isoformat(timespec="seconds"),
           "tiers": "1 and 2 (data stages)", "checks": checks, "detail": record, "passed": all(checks.values())}
    data.save_json(ACCEPT_OUT / "data_stages.json", out)
    print(json.dumps(out, indent=1))
    if b.path("calibration.json").exists():
        accept_calibration(b)
    if b.path("class_means_cb.npy").exists():
        accept_layer(b)


RANK_SLACK, TOL_Q, TOL_COS = 3e-4, 1e-3, 0.9999  # research/notebooks/v5_build.py's reproduction rules


def accept_calibration(b: Build) -> None:
    """Tier 3: the calibration of the served members, by v5_build's rules."""
    n2 = calibrate.n2
    spec = json.loads((REPO / "service" / "model" / "v3_1" / "nb2_spec_v31.json").read_text(encoding="utf-8"))
    got = json.loads(b.path("calibration.json").read_text(encoding="utf-8"))
    sc = np.load(b.path("calibration_scores.npz"))
    names, alpha, min_n = b.names(), b.cfg["calibration"]["alpha"], b.cfg["calibration"]["min_n"]
    checks, detail = {}, {}
    detail["temperature"] = {k: (got["temperature"][k], spec["assignment"]["temperature"][k]) for k in got["temperature"]}
    checks["temperature"] = all(abs(x - z) < 1e-12 for x, z in detail["temperature"].values())
    detail["qhat_within_one_rank"] = {}
    for label, scores, nb2 in ([("marginal", sc["scores"], spec["conformal"]["marginal_qhat"])]
                               + [(c, sc["scores"][sc["y"] == names.index(c)], spec["conformal"]["qhat_by_class"][c])
                                  for c in names if (sc["y"] == names.index(c)).sum() >= min_n]):
        ordered = np.sort(scores)
        k = int(np.ceil(n2.conformal_level(len(ordered), alpha) * (len(ordered) - 1)))
        lo, hi = ordered[max(k - 1, 0)] - RANK_SLACK, ordered[min(k + 1, len(ordered) - 1)] + RANK_SLACK
        detail["qhat_within_one_rank"][label] = bool(lo <= nb2 <= hi)
    checks["qhat"] = all(detail["qhat_within_one_rank"].values())
    detail["ood"] = (got["ood_threshold"], spec["ood"]["threshold"])
    checks["ood_threshold"] = abs(got["ood_threshold"] - spec["ood"]["threshold"]) <= TOL_Q
    served_dir = REPO / "service" / "model" / "v3_1" / "members"
    cosines = {}
    for name in got["temperature"]:
        seed = name.split("seed")[1].split(".")[0]
        served = np.load(served_dir / f"V2_seed{seed}_reference_latent_f16.npy").astype(np.float32)
        mine = np.load(b.path("members") / f"V2_seed{seed}_reference_latent_f16.npy").astype(np.float32)
        served_c = np.load(served_dir / f"V2_seed{seed}_centroids.npy")
        mine_c = np.load(b.path("members") / f"V2_seed{seed}_centroids.npy")
        cosines[name] = {"latents_median": float(np.median((mine * served).sum(1) / np.linalg.norm(mine, axis=1)
                                                           / np.linalg.norm(served, axis=1))),
                         "centroids_min": float((mine_c * served_c).sum(1).min())}
    detail["member_files"] = cosines
    checks["member_files"] = all(v["latents_median"] >= TOL_COS and v["centroids_min"] >= TOL_COS for v in cosines.values())
    out = {"script_sha256": sha256(Path(__file__)), "run": datetime.now().isoformat(timespec="seconds"),
           "tier": "3 (calibration of the served members)", "checks": checks, "detail": detail,
           "suite_top1_accuracy": got["suite_top1_accuracy"], "passed": all(checks.values())}
    data.save_json(ACCEPT_OUT / "calibration.json", out)
    print(json.dumps({"checks": checks, "passed": out["passed"]}, indent=1))


def accept_layer(b: Build) -> None:
    """Tier 2, the best-guess layer: v4's served class-balanced statistics,
    class means and centroids."""
    v4 = REPO / "service" / "model" / "v4"
    a, z = np.load(b.path("class_balanced_stats.npz")), np.load(v4 / "class_balanced_stats.npz")
    gaps = {"stats": max(float(np.abs(a["mu"] - z["mu"]).max()), float(np.abs(a["sd"] - z["sd"]).max())),
            "class_means": float(np.abs(np.load(b.path("class_means_cb.npy")) - np.load(v4 / "class_means_cb.npy")).max())}
    cos = {}
    for seed in range(5):
        mine = np.load(b.path("members") / f"V2_seed{seed}_centroids_cb.npy")
        served = np.load(v4 / "members" / f"V2_seed{seed}_centroids_cb.npy")
        cos[f"seed{seed}"] = float((mine * served).sum(1).min())
    checks = {"stats": gaps["stats"] <= 1e-5, "class_means": gaps["class_means"] <= 1e-5,
              "centroids_cb": min(cos.values()) >= 0.999999}
    out = {"script_sha256": sha256(Path(__file__)), "run": datetime.now().isoformat(timespec="seconds"),
           "tier": "2 (the best-guess layer)", "checks": checks, "largest_differences": gaps,
           "centroids_cb_min_cosine": cos, "passed": all(checks.values())}
    data.save_json(ACCEPT_OUT / "layer.json", out)
    print(json.dumps(out, indent=1))


def accept_training(b: Build) -> None:
    """Tier 5: seed 1 retrained by the builder against the served seed-1
    member alone: validation loss, balanced accuracy and each class's recall
    on train_variant's own validation cells, and top-1 on the calibration
    uploads, both computed here in the same run."""
    if b.organ != "blood":
        raise SystemExit("accept_training compares with the served blood member")
    s, arch = _setup(b), b.cfg["train"]
    name = "V2_batchgene_aug_seed1.pt"
    served_path = member_paths(b)[name]
    model, info = calibrate.train_member(s, 1, arch)
    b.path("ckpt").mkdir(exist_ok=True)
    mine_path = b.path("ckpt") / name
    torch.save(model.state_dict(), mine_path)
    served = calibrate.load_model(served_path, s, arch)
    v_mine, v_served = calibrate.validation(model, s, 1), calibrate.validation(served, s, 1)
    suite = json.loads(b.path("sim_suite_calib_v1.json").read_text(encoding="utf-8"))
    profiles_ = dict(np.load(b.path("mask_profiles.npz")))
    top1 = {k: calibrate.calibrate({name: m}, s, b.X(), profiles_, suite, b.names(), b.cfg["calibration"],
                                   log=lambda m_: None)["suite_top1_accuracy"]
            for k, m in (("retrained", model), ("served", served))}
    recall_gap = {b.names()[c]: round(v_mine["recall"][c] - v_served["recall"][c], 2) for c in v_mine["recall"]}
    checks = {"best_val_loss": abs(float(info["best_val_loss"]) - 0.45517) <= 0.02,
              "balanced": abs(v_mine["balanced"] - v_served["balanced"]) <= 2.0,
              "class_recall": max(abs(v) for v in recall_gap.values()) <= 5.0,
              "calibration_top1": abs(top1["retrained"] - top1["served"]) <= 2.0}
    out = {"script_sha256": sha256(Path(__file__)), "run": datetime.now().isoformat(timespec="seconds"),
           "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__, "tier": "5 (training path, seed 1)",
           "retrained": {"best_val_loss": float(info["best_val_loss"]), "epochs_run": info["epochs_run"],
                         "seconds": round(info["seconds"]), "sha256": sha256(mine_path), **v_mine},
           "served": v_served, "recall_differences": recall_gap, "calibration_top1": top1,
           "checks": checks, "passed": all(checks.values())}
    data.save_json(ACCEPT_OUT / "training.json", out)
    print(json.dumps({"checks": checks, "top1": top1, "passed": out["passed"]}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("organ")
    parser.add_argument("stages", nargs="+", choices=STAGES + CHECKS)
    args = parser.parse_args()
    b = Build(args.organ)
    for stage in args.stages:
        t = time.time()
        print(f"== {args.organ}: {stage}", flush=True)
        globals()[stage if stage in CHECKS else f"stage_{stage}"](b)
        print(f"   ({time.time() - t:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
