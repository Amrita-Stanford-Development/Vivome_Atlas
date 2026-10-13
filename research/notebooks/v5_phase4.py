"""v5, Phase 4 (research/todo.md, Track H): v5's pre-registered evaluation,
scored once. Modelled on research/notebooks/v41_phase3.py.

v5 is v4.1's rule (service/pipeline/fusion.py) on five V2 members retrained
on the cleaned reference labels (research/notebooks/v5_labels.py,
v5_train.py), with its own calibration by NB2's recipe (v5_build.py).

Rules, fixed before the run. The script records its sha256, the specs' and
the cleaned labels' sha256s and the start time in rules.json before
computing anything.

- Truth is the cleaned labels. The original labels are reported beside
  them and decide nothing.
- References hold no test cells, as in Phases 3 to 3c and v4.1's Phase C.
  NB1's train and validation rows only:
  - v4.1: v3.1's centroids recomputed on those rows (original labels) and
    v4's train-plus-validation bundle;
  - v5: its members' centroids recomputed on those rows (cleaned labels),
    and its class-balanced layer rebuilt on them (v5_build.best_guess_layer).
  Every upload goes through the service's own code.
- 1. Implementation check, first. On T1 NB3c's calibration suite
  (original truth), v4.1's best guess, coverage, committed share and
  correct-when-committed must equal Phase C's
  (research/notebook-outputs/v41_phase3/calibration_check.json, "found")
  within 0.01. Also, v5's spec must carry v4.1's fusion settings. Otherwise
  the run stops.
- 2. Sanity stop. On the same suite with cleaned truth, v5's coverage must be
  at least 85%. Otherwise the run stops before the evaluation suite is
  drawn. v5's figures there are reported.
- 3. Development figures, the served all-cells bundles. v3.1, v4.1 and v5
  on Fulcher 2026, PBMC240, SCoPE2 (published and reprocessed) and
  Furtwangler 2025. Two of them are guardrails, below.
- 4. A fresh evaluation suite. 240 new uploads from NB3c's te_eval cells,
  composed by the cleaned labels: sim_generator.make_suite("eval_v5", ...,
  seed 20261012). It is written before it is scored. Declared: this is the
  fifth use of these cells, so the suite is a safety check on simulated RNA
  uploads; only a sealed protein test can show a protein gain.
- 5. Evaluation, scored once: v3.1, v4.1 and v5 on the same uploads, cells
  with at least 200 observed genes.
- GO only if every check holds, all on cleaned truth.
  - The target, over the cells of multi-type uploads (every scenario group
    but single):
    - CD8 T recall of v5's best guess at least v4.1's + 10 points;
    - NK recall at least v4.1's - 2.
  - The best guess:
    - mean per-upload balanced accuracy at least v4.1's - 1;
    - no scenario group more than 2 points below v4.1.
  - v5's answers:
    - coverage not below v3.1's;
    - false abstention at most 3%;
    - correct when committed at least 94%;
    - committed share at least v3.1's - 2 points.
  - The development guardrails: Fulcher's six-type balanced accuracy and
    PBMC240's lymphoid recall each at least v4.1's - 2. Fulcher is a
    guardrail, not an objective.
- Khoury 2026 is not read.

Writes research/notebook-outputs/v5_phase4/:
- rules.json and the calibration check;
- the development figures;
- the evaluation suite and the evaluation;
- spec_block.json, for research/notebooks/v5_build.py spec.

--version v5.1 (added 2026-10-12, before any v5.1 evaluation) runs the same
evaluation for v5.1: v5 with NK T folded into NK in training
(research/notebooks/v51_labels.py). The rules are unchanged except as
follows.
- Truth is v5.1's labels, which are v5's with NK T cells counted as NK, as
  their markers say.
- The suite is eval_v51 (sim_generator.make_suite, seed 20261013), composed
  by those labels. v5's Phase 4 never ran, so this is te_eval's fifth use.
- The outputs go to research/notebook-outputs/v51_phase4/.
Declared before the run: on NB3c's calibration suite (v5_diagnose.py
--version v5.1) v5.1 was 3.6 points below v4.1 in the scope2-like scenario
and +11.5 on CD8 T recall, against bounds of 2 and +10.

    python research/notebooks/v5_phase4.py      # from the repository root
    python research/notebooks/v5_phase4.py --version v5.1
    python research/notebooks/v5_phase4.py --smoke DIR [--version v5.1]
    # plumbing: 4 uploads per stage, test uploads drawn from the calibration
    # cells (never the evaluation pool), written to DIR; checks printed only
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
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v4_calibration as phase3  # noqa: E402  (raw_upload, restricted, centroids_from, GROUP, correct_at_level)
import v4_phase3c  # noqa: E402  (summary)
import v4_pretest  # noqa: E402  (the development metrics)
import sim_generator as sg  # noqa: E402  (on NB1's path, added by v4_calibration)
import v5_build  # noqa: E402  (best_guess_layer)

from benchmark import baselines_v31, datasets  # noqa: E402
from service import config  # noqa: E402
from service.pipeline import abstention, alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "v5_phase4"
PHASE_C = REPO / "research" / "notebook-outputs" / "v41_phase3" / "calibration_check.json"
LABELS = REPO / "research" / "notebook-outputs" / "v5_labels" / "reference_labels_clean.csv.gz"
VERSIONS = {
    "v5": {"labels": LABELS, "out": OUT, "suite": "eval_v5", "seed": 20261012, "fifth": "eval_v5: 240 new uploads from "
           "T1 NB3c's te_eval cells by the cleaned labels, seed 20261012 (their fifth use)"},
    "v5.1": {"labels": REPO / "research" / "notebook-outputs" / "v51_labels" / "reference_labels_v51.csv.gz",
             "out": REPO / "research" / "notebook-outputs" / "v51_phase4", "suite": "eval_v51", "seed": 20261013,
             "fifth": "eval_v51: 240 new uploads from T1 NB3c's te_eval cells by v5.1's labels, seed 20261013 (their fifth use)"},
}
MIN_GENES, N_UPLOADS, EVAL_SEED, CHECK_TOLERANCE, SANITY_COVERAGE = 200, 240, 20261012, 0.01, 85.0
GO = {"cd8_recall_gain": 10.0, "nk_recall_drop_max": 2.0, "best_guess_drop_max": 1.0, "scenario_drop_max": 2.0,
      "coverage": "not below v3.1", "false_abstention_max": 3.0, "correct_min": 94.0, "committed_drop_max": 2.0,
      "development_drop_max": 2.0}
CD8, NK = "cd8-positive, alpha-beta t cell", "natural killer cell"
FUSED = ("v4.1", "v5", "v5.1")
SETTINGS = ("fusion_weight", "gate_on_fusion_weight", "correlation_temperature", "smoothed_share", "agreement_threshold")


def centroids_from(latents, y, n):
    """v4_calibration.centroids_from, with a class without cells at zero (v5.1's NK T)."""
    Z = latents / np.linalg.norm(latents, axis=1, keepdims=True)
    C = np.stack([Z[y == k].mean(0) if (y == k).any() else np.zeros(Z.shape[1]) for k in range(n)])
    return C / np.maximum(np.linalg.norm(C, axis=1, keepdims=True), 1e-12)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def answer_sets(bundle, smoothed, aligned, components) -> list:
    """Each cell's set before abstention, built as the response builds it
    (v41_phase3.coverage, returning the sets so any truth can be scored)."""
    names = bundle.class_names
    answers = bundle.answers if bundle.pipeline_version in FUSED else bundle
    Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
    P_all = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature)
                                             for z, m in zip(Z, answers.members)])
    space = components.label_space.estimate(None, names, False)
    P = components.label_space.probabilities(P_all, space)
    guess = None
    if bundle.pipeline_version in FUSED:
        counted = aligned.per_cell_observed_genes >= MIN_GENES
        G = fusion.best_guess_probabilities(bundle, Z, aligned.values, aligned.mask, P_all, counted).probabilities
        guess = ensemble.best_guess(components.label_space.probabilities(G, space), space.positions)[0]
    return [set(s) for s in components.calibrator.calibrate(P, None, space, guess_positions=guess).label_sets]


def project(bundle, smoothed, aligned, scale, resolution):
    if bundle.pipeline_version in FUSED:
        return fusion.project_prepared(bundle, smoothed, aligned, scale, resolution, False, bundle.components)
    return ensemble.project_prepared(bundle, smoothed, aligned, scale, resolution, False, bundle.components)


def cell_rows(response, sets, clean_pos, orig_pos, names, hierarchy, upload, group, method) -> list[dict]:
    """v4_phase3c.cell_rows under both truths: "true", "correct" and
    "covered" are the cleaned labels'; the *_original columns the original's."""
    rows = []
    for i, cell in enumerate(response["cells"]):
        if cell["observed_genes"] < MIN_GENES:
            continue
        committed = not cell["abstained"]
        row = {"method": method, "upload": upload, "group": group,
               "ood_abstained": cell.get("abstain_reason") == abstention.AbstainReason.OUT_OF_DISTRIBUTION.value,
               "committed": committed, "level": cell["label_level"] if committed else "abstain",
               "best_guess": cell.get("best_guess", {}).get("label")}
        for suffix, pos in (("", clean_pos[i]), ("_original", orig_pos[i])):
            t = names[pos]
            row["true" + suffix] = t
            row["correct" + suffix] = committed and phase3.correct_at_level(cell["label"], cell["label_level"], t, hierarchy)
            row["covered" + suffix] = pos in sets[i]
        rows.append(row)
    return rows


def as_original(d: pd.DataFrame) -> pd.DataFrame:
    return d.assign(true=d["true_original"], correct=d["correct_original"], covered=d["covered_original"])


def multi_type_recall(d: pd.DataFrame, cls: str) -> float:
    m = d[(d["group"] != "single") & (d["true"] == cls)]
    return round(100 * float((m["best_guess"] == cls).mean()), 2) if len(m) else float("nan")


def main() -> None:
    global OUT
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", type=Path, help="plumbing check into this directory (no evaluation-pool cell is read)")
    parser.add_argument("--version", choices=tuple(VERSIONS), default="v5")
    args = parser.parse_args()
    smoke, version = args.smoke, args.version
    V = VERSIONS[version]
    OUT = smoke if smoke else V["out"]
    spec_path, answers_path = fusion.version_files(version)[0], fusion.version_files(version)[2] / (
        "nb2_spec_v5.json" if version == "v5" else "nb2_spec_v51.json")
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rules.json").write_text(json.dumps({
        "script_sha256": sha256(Path(__file__)), "version": version, "spec_sha256": sha256(spec_path),
        "answers_spec_sha256": sha256(answers_path), "spec_v41_sha256": sha256(config.V41_SPEC_PATH),
        "labels": V["labels"].relative_to(REPO).as_posix(), "labels_sha256": sha256(V["labels"]),
        "started": datetime.now().isoformat(timespec="seconds"), "suite": V["suite"],
        "check_tolerance": CHECK_TOLERANCE, "sanity_coverage": SANITY_COVERAGE, "go": GO, "eval_seed": V["seed"]},
        indent=2) + "\n", newline="\n")
    t0 = time.time()
    v41 = fusion.V4Bundle.load(require_evaluation=False, version="v4.1")
    v5 = fusion.V4Bundle.load(require_evaluation=False, version=version)
    settings = {k: (v5.spec["best_guess"].get(k), v41.spec["best_guess"].get(k)) for k in SETTINGS}
    if any(a != b for a, b in settings.values()):
        raise SystemExit(f"STOP: {version}'s spec does not carry v4.1's fusion settings: {settings}")
    v31 = v41.answers
    names, n = v41.class_names, len(v41.class_names)
    table = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    y = np.array([names.index(c) for c in table["class_name"]])
    lab = pd.read_csv(V["labels"])
    if lab["cell"].tolist() != table["cell"].tolist():
        raise SystemExit(f"{V['labels']} is not in reference_metadata.csv's order")
    y_clean = lab["class_idx_clean"].to_numpy()
    split = np.load(phase3.NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    if smoke:
        suites["calib"] = suites["calib"][:4]

    # references without test cells
    if json.loads((phase3.CALIB_BUNDLE / "spec_v4.json").read_text()).get("reference_rows") != "trainval":
        raise SystemExit(f"{phase3.CALIB_BUNDLE} is not the train-plus-validation bundle")
    v31c = dataclasses.replace(v31, members=phase3.restricted(
        v31.members, trainval, [centroids_from(m.reference_latents[trainval], y[trainval], n) for m in v31.members]),
        property_values=v31.property_values[trainval])
    cb41 = [np.load(phase3.CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy")
            for m in v41.members]
    held_out = {"v3.1": v31c,
                "v4.1": dataclasses.replace(v41, answers=v31c, members=phase3.restricted(v41.members, trainval, cb41),
                                            class_means=np.load(phase3.CALIB_BUNDLE / "class_means_cb.npy"))}
    a5 = v5.answers
    v5c = dataclasses.replace(a5, members=phase3.restricted(
        a5.members, trainval, [centroids_from(m.reference_latents[trainval], y_clean[trainval], n) for m in a5.members]),
        property_values=a5.property_values[trainval])
    X = v5_build.bundle.load_rna(v5_build.bundle.RNA, v5.feature_genes, table["cell"].astype(str).tolist())[trainval]
    members_dir = config.V51_MEMBERS_DIR if version == "v5.1" else config.V5_MEMBERS_DIR
    layer = v5_build.best_guess_layer({m.name: members_dir / m.name for m in a5.members}, y_clean[trainval], X, n)
    del X
    held_out[version] = dataclasses.replace(v5, answers=v5c, class_means=layer["means"], members=phase3.restricted(
        v5.members, trainval, [layer["centroids_cb"][m.name] for m in v5.members]))
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_X = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_X[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    genes = v41.feature_genes
    resolution = gene_ids.resolve_identifiers(genes)
    print(f"ready ({time.time() - t0:.0f}s)", flush=True)

    def score(specs, models) -> tuple[pd.DataFrame, list[dict]]:
        rows, uploads = [], []
        for s in specs:
            raw = phase3.raw_upload(s, get_raw, profiles, len(genes))
            ids = [f"{s['id']}_{i}" for i in range(len(raw))]
            smoothed, aligned, scale = pipeline._prepare_query(genes, alignment.RawMatrix(gene_names=genes, cell_ids=ids, values=raw.T))
            idx = np.asarray(s["cell_idx"])
            group = phase3.GROUP[s["scenario"]]
            for m in models:
                b = held_out[m]
                response = project(b, smoothed, aligned, scale, resolution)
                rows += cell_rows(response, answer_sets(b, smoothed, aligned, b.components), y_clean[idx], y[idx], names,
                                  v41.hierarchy, s["id"], group, m)
                if m == version:
                    uploads.append({"upload": s["id"], "group": group, "scenario": s["scenario"], "cells": len(idx),
                                    **{k: v for k, v in response["best_guess_rule"].items() if k != "rule"}})
        return pd.DataFrame(rows), uploads

    # 1 and 2. the implementation check and the sanity stop, on NB3c's calibration suite
    calib, _ = score(suites["calib"], ("v4.1", version))
    found = {k: v4_phase3c.summary(as_original(calib[calib["method"] == "v4.1"]))[k]
             for k in ("best_guess_per_upload_balanced", "coverage", "committed", "correct_when_committed")}
    expected = json.loads(PHASE_C.read_text())["found"]
    differences = {k: round(found[k] - expected[k], 4) for k in found}
    implementation = all(abs(d) <= CHECK_TOLERANCE for d in differences.values())
    v5_calib = {k: v for k, v in v4_phase3c.summary(calib[calib["method"] == version]).items() if k != "levels"}
    v41_calib = {k: v for k, v in v4_phase3c.summary(calib[calib["method"] == "v4.1"]).items() if k != "levels"}
    for d, label in ((v5_calib, version), (v41_calib, "v4.1")):
        sub = calib[calib["method"] == label]
        d.update(cd8_recall_multi_type=multi_type_recall(sub, CD8), nk_recall_multi_type=multi_type_recall(sub, NK))
    sane = bool(v5_calib["coverage"] >= SANITY_COVERAGE)
    check = {"v41_found": found, "v41_expected_phase_c": expected, "differences": differences, "tolerance": CHECK_TOLERANCE,
             "implementation_passed": implementation, "v5_settings": settings,
             "calibration_suite_cleaned_truth": {version: v5_calib, "v4.1": v41_calib},
             "sanity_coverage": SANITY_COVERAGE, "sanity_passed": sane, "enforced": not smoke}
    (OUT / "calibration_check.json").write_text(json.dumps(check, indent=2) + "\n", newline="\n")
    print(json.dumps(check, indent=1), f"({time.time() - t0:.0f}s)", flush=True)
    if not (implementation and sane) and not smoke:
        (OUT / "spec_block.json").write_text(json.dumps({"evaluation": {
            "status": "not run", "record": (OUT / "calibration_check.json").relative_to(REPO).as_posix() if not smoke else None,
            "reason": "the implementation check or the sanity stop failed"}}, indent=2) + "\n", newline="\n")
        raise SystemExit("STOP: the implementation check or the sanity stop failed; nothing evaluated")

    # 3. development figures, the served all-cells bundles
    lineage = table.groupby("class_name")["lineage"].first().to_dict()
    cidx = {c: i for i, c in enumerate(names)}
    pbmc_meta = pd.read_csv(REPO / "benchmark" / "results" / "pbmc_meta.csv")
    dev_uploads = [("fulcher2026", datasets.load_fulcher2026_upload(), datasets.load_fulcher2026_labels()),
                   ("pbmc240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), pbmc_meta),
                   ("scope2", baselines_v31.scope2_raw(), pd.read_csv(REPO / "benchmark" / "results" / "prot_meta.csv")),
                   ("scope2_reprocessed", datasets.load_scope2_reprocessed_upload(),
                    datasets.load_scope2_reprocessed_labels().rename(columns={"label": "class_name"})),
                   ("furtwangler2025", datasets.load_furtwangler2025_upload(), datasets.load_furtwangler2025_labels())]
    served = {"v3.1": v31, "v4.1": v41, version: v5}
    dev, maxp = {}, {}
    for name, raw, info in dev_uploads:
        smoothed, aligned, scale = pipeline._prepare_query(genes, raw)
        rows_ = np.arange(len(aligned.values))
        if name == "pbmc240":
            at = {c: i for i, c in enumerate(raw.cell_ids)}
            rows_ = np.array([at[c] for c in info["cell_id"].astype(str)])
        res = gene_ids.resolve_identifiers(raw.gene_names)
        for m, b in served.items():
            resp = project(b, smoothed, aligned, scale, res)
            cells = [resp["cells"][i] for i in rows_]
            pred = np.array([c.get("best_guess", {}).get("label") or "" for c in cells])
            prob = np.array([c.get("best_guess", {}).get("probability", np.nan) for c in cells])
            P = np.zeros((len(pred), n))
            P[np.arange(len(pred)), [cidx.get(p, 0) for p in pred]] = prob
            if name.startswith("scope2"):
                fig = {"balanced_accuracy_unrestricted": round(100 * balanced_accuracy_score(info["class_name"].to_numpy(), pred), 2)}
            else:
                fig = v4_pretest.metrics(name, pred, info, P, cidx, lineage)
            fig["committed"] = round(100 * float(np.mean([not c["abstained"] for c in cells])), 2)
            if "best_guess_rule" in resp:
                fig.update({k: v for k, v in resp["best_guess_rule"].items() if k != "rule"})
            dev.setdefault(name, {})[m] = fig
            maxp[(name, m)] = prob
    for m in served:
        a_, b_ = maxp[("fulcher2026", m)], maxp[("furtwangler2025", m)]
        dev.setdefault("out_of_reference_auroc", {})[m] = round(float(roc_auc_score(np.r_[np.ones(len(a_)), np.zeros(len(b_))], np.r_[a_, b_])), 4)
    (OUT / "development.json").write_text(json.dumps(dev, indent=2) + "\n", newline="\n")
    print(json.dumps(dev, indent=1), f"({time.time() - t0:.0f}s)", flush=True)

    # 4. the fresh evaluation suite, composed by the cleaned labels, written before it is scored
    te_eval = np.asarray(suites["te_cal" if smoke else "te_eval"])
    if set(te_eval.tolist()) & set(trainval.tolist()):
        raise SystemExit("an evaluation cell is in the reference rows")
    fresh = sg.make_suite(V["suite"], te_eval, y_clean[te_eval], names, N_UPLOADS, V["seed"])
    if smoke:
        fresh = fresh[:4]
    (OUT / "eval_suite.json").write_text(json.dumps(fresh) + "\n", newline="\n")
    print(f"fresh suite written: {len(fresh)} uploads, {sum(len(s['cell_idx']) for s in fresh)} cells", flush=True)

    # 5. evaluate once
    df, eval_uploads = score(fresh, ("v3.1", "v4.1", version))
    df.to_csv(OUT / "eval_cells.csv.gz", index=False, lineterminator="\n")
    pd.DataFrame(eval_uploads).to_csv(OUT / "eval_uploads.csv", index=False, lineterminator="\n")
    models = (version, "v4.1", "v3.1")
    result, original = {}, {}
    for m in models:
        d = df[df["method"] == m]
        result[m] = {**v4_phase3c.summary(d), "cd8_recall_multi_type": multi_type_recall(d, CD8),
                     "nk_recall_multi_type": multi_type_recall(d, NK)}
        o = as_original(d)
        original[m] = {**v4_phase3c.summary(o), "cd8_recall_multi_type": multi_type_recall(o, CD8),
                       "nk_recall_multi_type": multi_type_recall(o, NK)}
    by_group = {m: {g: v4_phase3c.summary(df[(df["method"] == m) & (df["group"] == g)]) for g in sorted(df["group"].unique())}
                for m in models}
    pd.DataFrame([{"method": m, "group": g, **{k: v for k, v in r.items() if k != "levels"}} for m, gs in by_group.items()
                  for g, r in gs.items()]).to_csv(OUT / "eval_by_scenario.csv", index=False, lineterminator="\n")
    a, b41, b31 = result[version], result["v4.1"], result["v3.1"]
    bg = lambda m, g: by_group[m][g]["best_guess_per_upload_balanced"]  # noqa: E731
    drops = {g: round(bg("v4.1", g) - bg(version, g), 2) for g in by_group[version]}
    fd, pd_ = dev["fulcher2026"], dev["pbmc240"]
    checks = {k: bool(v) for k, v in {
        "cd8_recall_gain": a["cd8_recall_multi_type"] >= b41["cd8_recall_multi_type"] + GO["cd8_recall_gain"],
        "nk_recall": a["nk_recall_multi_type"] >= b41["nk_recall_multi_type"] - GO["nk_recall_drop_max"],
        "best_guess_vs_v41": a["best_guess_per_upload_balanced"] >= b41["best_guess_per_upload_balanced"] - GO["best_guess_drop_max"],
        "no_scenario_drop_vs_v41": all(d <= GO["scenario_drop_max"] for d in drops.values()),
        "coverage": a["coverage"] >= b31["coverage"],
        "false_abstention": a["false_abstention"] <= GO["false_abstention_max"],
        "correct_when_committed": a["correct_when_committed"] >= GO["correct_min"],
        "committed": a["committed"] >= b31["committed"] - GO["committed_drop_max"],
        "fulcher_guardrail": fd[version]["balanced_accuracy_6_types"] >= fd["v4.1"]["balanced_accuracy_6_types"] - GO["development_drop_max"],
        "pbmc240_guardrail": pd_[version]["lymphoid_recall"] >= pd_["v4.1"]["lymphoid_recall"] - GO["development_drop_max"],
    }.items()}
    go = all(checks.values())
    record = {"result_cleaned_truth": result, "result_original_truth": original, "by_scenario": by_group,
              "scenario_drop_vs_v41": drops, "checks": checks, "go": go, "seconds": round(time.time() - t0)}
    (OUT / "summary.json").write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    (OUT / "spec_block.json").write_text(json.dumps({"evaluation": {
        "status": "passed" if go else "failed",
        "record": (OUT / "summary.json").relative_to(REPO).as_posix() if not smoke else None, "suite": V["fifth"],
        "date": datetime.now().date().isoformat()}}, indent=2) + "\n", newline="\n")
    print(json.dumps({k: record[k] for k in ("result_cleaned_truth", "scenario_drop_vs_v41", "checks", "go")}, indent=1), flush=True)


if __name__ == "__main__":
    main()
