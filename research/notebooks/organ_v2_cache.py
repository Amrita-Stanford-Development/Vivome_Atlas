"""Organ references v2, diagnostic A0 (research/organ-references.md,
"Version 2"; the plan of 2026-10-18): every calibration answer of the v1
bundles, cached, so A2 and A3 can try other calibrations offline.

For each organ, on a bundle whose references are the training rows only
(li_development.held_out; so calibration cells never meet themselves, as in
calibrate.calibrate), every upload of two suites goes through the service's
own steps (pipeline._prepare_query, then the fused best guess and the
answers' parts of fusion.project_prepared):
- "calib": v1's calibration suite (sim_suite_calib_v1.json, validation cells);
- "rare": a diagnostic suite from the validation cells only (seed 33,
  min_cells 5, scenarios.make_suite with cap_per_class), so every class with
  at least 5 validation cells has calibration cells.

Cached per cell: each member's cosine to every centroid (so temperatures can
be refitted), the answers' probabilities, the fused best guess, the
out-of-distribution score, observed genes and the true class. Per upload:
scenario, classes, lineages and the best guess's agreement.

The replay check:
- the answers rebuilt from the cache with v1's calibrator and abstention
  must equal fusion.project_prepared's labels and levels on the first five
  uploads;
- qhat refitted from the cache with v1's temperatures must be within
  QHAT_TOLERANCE of calibration.json's, class by class and marginal.

  Amended 2026-10-18 after the first run. That run passed the replay
  exactly (0 of 1,306 cells differ) but failed the original rule, "within
  one rank", by 14 ranks (CD8 T, 12,862 cells). The cause: v1's
  calibration read uploads through core.query_inputs; this cache reads
  them through the service's own pipeline._prepare_query. The two differ
  slightly on 19 of 240 uploads, mostly with per-cell missingness, and
  every qhat moves by at most 0.0007. The cache follows the service, which
  is what G1 measures, so the check bounds the qhat shift instead.

A failed check stops the script. The evaluation suites are not touched.

The caches (large) go to each organ's work folder,
drive/Data/Results/Organs/<organ>/v2_diagnostics/; the records to
research/notebook-outputs/organ_v2_cache/.

    python research/notebooks/organ_v2_cache.py      # from the repository root (GPU)
"""
from __future__ import annotations

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
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
sys.path.insert(0, str(REPO / "research" / "notebook-outputs" / "nb2"))
import li_development as li  # noqa: E402
import nb2_core as n2  # noqa: E402
from organ_reference import bundle, calibrate, data, scenarios  # noqa: E402
from organ_reference import sim_generator as sg  # noqa: E402

from service.pipeline import abstention, alignment, ensemble, fusion, gene_ids, pipeline, search  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_cache"
ORGANS = ("lymph_node", "lung", "large_intestine")
RARE = {"seed": 33, "min_cells": 5, "n_uploads": 240}
REPLAY_UPLOADS = 5
QHAT_TOLERANCE = 0.005


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepared(b, spec, X, profiles):
    raw, _ = calibrate.core.raw_upload(spec, X, profiles, len(b.feature_genes), sg)
    ids = [f"{spec['id']}_{i}" for i in range(len(raw))]
    return pipeline._prepare_query(b.feature_genes, alignment.RawMatrix(gene_names=b.feature_genes, cell_ids=ids, values=raw.T))


def cache_suite(b, suite, X, y, profiles, hierarchy, names, log) -> tuple[dict, list[dict]]:
    answers = b.answers
    min_genes = int(b.spec["preprocessing"]["min_observed_genes"])
    cos, P, guess, ood, observed, truth, upload = [], [], [], [], [], [], []
    uploads, t0 = [], time.time()
    for u, spec in enumerate(suite):
        smoothed, aligned, _ = prepared(b, spec, X, profiles)
        Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
        cos.append(np.stack([z.astype(np.float64) @ m.centroids.astype(np.float64).T for z, m in zip(Z, answers.members)], 1).astype(np.float16))
        p = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, answers.members)])
        counted = aligned.per_cell_observed_genes >= min_genes
        bg = fusion.best_guess_probabilities(b, Z, aligned.values, aligned.mask, p, counted)
        P.append(p.astype(np.float32))
        guess.append(ensemble.best_guess(bg.probabilities, None)[0].astype(np.int16))
        ood.append(np.mean([search.faiss_max_cosine_to_reference(z, m.reference_latents) for z, m in zip(Z, answers.members)], 0).astype(np.float32))
        observed.append(aligned.per_cell_observed_genes.astype(np.int32))
        truth.append(y[np.asarray(spec["cell_idx"])].astype(np.int16))
        upload.append(np.full(len(spec["cell_idx"]), u, np.int32))
        classes = spec["classes"]
        uploads.append({"id": spec["id"], "scenario": spec["scenario"], "classes": len(classes),
                        "lineages": len({hierarchy[c]["lineage"] for c in classes}), "cells": len(spec["cell_idx"]),
                        "profile": spec["profile"], "agreement": round(float(bg.agreement), 6),
                        "correlation_used": bool(bg.correlation_used)})
        if (u + 1) % 40 == 0:
            log(f"  {u + 1}/{len(suite)} uploads ({time.time() - t0:.0f}s)")
    arrays = {"cos": np.concatenate(cos), "P": np.concatenate(P), "guess": np.concatenate(guess), "ood": np.concatenate(ood),
              "observed": np.concatenate(observed), "y": np.concatenate(truth), "upload": np.concatenate(upload)}
    return arrays, uploads


def offline_answers(b, P, guess, ood, observed, calibrator=None):
    """fusion.project_prepared's labels and levels from cached arrays."""
    names, comp = b.answers.class_names, b.components
    space = comp.label_space.estimate(None, names, False)
    cal = (calibrator or comp.calibrator).calibrate(comp.label_space.probabilities(P.astype(np.float64), space), None, space,
                                                    guess_positions=guess.astype(np.int64))
    verdict = comp.abstention.score(max_similarity=ood.astype(np.float64), hidden_features=None, per_cell_observed_genes=observed,
                                    label_sets=cal.label_sets, calibration_indices=cal.calibration_indices)
    out = []
    for i, reason in enumerate(verdict.reason):
        resolved = None
        if reason in (abstention.AbstainReason.NONE, abstention.AbstainReason.AMBIGUOUS):
            resolved = ensemble.resolve([names[c] for c in cal.label_sets[i]], b.answers.hierarchy)
        out.append(resolved)
    return out


def replay(b, suite, X, profiles, arrays) -> dict:
    """The service's own response against the cache, on the first uploads."""
    resolution = gene_ids.resolve_identifiers(b.feature_genes)
    mismatches, cells = 0, 0
    for u, spec in enumerate(suite[:REPLAY_UPLOADS]):
        smoothed, aligned, scale = prepared(b, spec, X, profiles)
        response = fusion.project_prepared(b, smoothed, aligned, scale, resolution, False, b.components)
        rows = arrays["upload"] == u
        mine = offline_answers(b, arrays["P"][rows], arrays["guess"][rows], arrays["ood"][rows], arrays["observed"][rows])
        for cell, m in zip(response["cells"], mine):
            theirs = None if cell["abstained"] else (cell["label"], cell["label_level"])
            mismatches += int(theirs != m)
            cells += 1
    return {"uploads": REPLAY_UPLOADS, "cells": cells, "mismatches": mismatches}


def refit_check(b, arrays, calibration: dict, names) -> dict:
    """qhat from the cache with v1's temperatures, against calibration.json, by rank."""
    temps = calibration["temperature"]
    members = [m.name for m in b.answers.members]
    P = np.mean([n2.softmax(arrays["cos"][:, k, :].astype(np.float64), temps[name]) for k, name in enumerate(members)], 0)
    y = arrays["y"].astype(np.int64)
    scores = 1.0 - P[np.arange(len(y)), y]
    q, marg = n2.fit_qhat(scores, y, len(names), 0.1, True, 50)
    worst = max(abs(float(q[c]) - calibration["qhat_by_class"][name]) for c, name in enumerate(names))
    worst = max(worst, abs(float(marg) - calibration["marginal_qhat"]))
    return {"marginal_qhat": round(float(marg), 6), "v1_marginal_qhat": calibration["marginal_qhat"],
            "worst_qhat_difference": round(worst, 6), "ok": worst <= QHAT_TOLERANCE}


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "organs": list(ORGANS), "rare_suite": RARE, "replay_uploads": REPLAY_UPLOADS,
                                        "qhat_tolerance": QHAT_TOLERANCE})
    log = lambda m: print(m, flush=True)  # noqa: E731
    record = {}
    for organ in ORGANS:
        t0 = time.time()
        build_dir = data.WORK / organ
        cfg = data.load_organ(organ)
        b_full = bundle.load(build_dir / "bundle")
        names, hierarchy = b_full.class_names, b_full.hierarchy
        table = pd.read_csv(build_dir / "labels.csv.gz", keep_default_na=False)
        y = table["class_idx"].to_numpy()
        X = data.load_rna(data.resolve(cfg["rna"]), b_full.feature_genes)[table["row"].to_numpy()]
        split = np.load(build_dir / "splits_seed0.npz")
        TR, VA = np.sort(split["train"]), np.sort(split["val"])
        paths = {m.name: build_dir / "bundle" / "members" / m.name for m in b_full.members}
        b = li.held_out(b_full, X, y, TR, paths, len(names))
        profiles = dict(np.load(build_dir / "mask_profiles.npz"))
        calib = json.loads((build_dir / "sim_suite_calib_v1.json").read_text(encoding="utf-8"))
        rare = scenarios.make_suite("rare", VA, y[VA], names, hierarchy, tuple(cfg["suites"]["profiles"]), RARE["n_uploads"],
                                    RARE["seed"], min_cells=RARE["min_cells"], cap_per_class=True)
        target = build_dir / "v2_diagnostics"
        target.mkdir(exist_ok=True)
        record[organ] = {"bundle_manifest_sha256": sha256(build_dir / "bundle" / "MANIFEST.json")}
        with bundle.gene_map(build_dir / "bundle"):
            for suite_name, suite in (("calib", calib), ("rare", rare)):
                log(f"{organ} {suite_name}: {len(suite)} uploads")
                arrays, uploads = cache_suite(b, suite, X, y, profiles, hierarchy, names, log)
                np.savez_compressed(target / f"cache_{suite_name}.npz", **arrays)
                data.save_json(target / f"uploads_{suite_name}.json", uploads)
                if suite_name == "rare":
                    data.save_json(target / "sim_suite_rare_v2diag.json", suite)
                info = {"cells": int(len(arrays["y"])), "uploads": len(uploads),
                        "cells_per_class": {names[c]: int((arrays["y"] == c).sum()) for c in range(len(names))},
                        "cache_sha256": sha256(target / f"cache_{suite_name}.npz")}
                if suite_name == "calib":
                    info["replay"] = replay(b, suite, X, profiles, arrays)
                    info["refit"] = refit_check(b, arrays, json.loads((build_dir / "calibration.json").read_text(encoding="utf-8")), names)
                    log(f"  replay {info['replay']}, refit {info['refit']}")
                    if info["replay"]["mismatches"] or not info["refit"]["ok"]:
                        record[organ][suite_name] = info
                        data.save_json(OUT / "record.json", record)
                        raise SystemExit(f"{organ}: the cache does not replay the service; stopping")
                record[organ][suite_name] = info
        record[organ]["seconds"] = round(time.time() - t0)
        data.save_json(OUT / "record.json", record)
    log(json.dumps({o: {s: {k: v for k, v in r[s].items() if k != "cells_per_class"} for s in ("calib", "rare")} for o, r in record.items()}, indent=1))


if __name__ == "__main__":
    main()
