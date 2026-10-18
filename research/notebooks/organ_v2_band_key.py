"""Organ references v2, diagnostic A4 (research/organ-references.md, "Version
2"): can the service tell, without labels, whether a colon upload is mixed or
narrow?

A2 (research/notebooks/organ_v2_calibration.py) found that calibrating
mixed and narrow uploads separately lets the colon commit 97% of mixed-upload
cells, with narrow uploads kept safe. But that needs each upload's band,
read without labels. A wrong "mixed" on a narrow upload gives it the
permissive threshold. Calibrating every upload as mixed made narrow uploads
65% correct when committed, so a key must almost never call a narrow upload
mixed. Earlier keys on blood all failed (run history, entry 37; NB3c).

Only the colon needs a key: the lung and the lymph node pass the split G1 on
v1's own rule in A2.

**Candidate keys**, per upload, where higher means "more mixed":
- K1, agreement: fusion.upload_agreement, the best guess's own.
- K2, predicted lineages: exp(entropy) of the lineages of the cells' answer
  argmaxes.
- K3, structure: entry 37's structure ratio of the upload's leading
  components over a per-protein permutation null (narrow_upload_calibration's
  settings).

**How each key is set and checked**
- On simulated uploads (v1's calibration suite, A0's cache, plus its raw
  uploads for K3): the threshold is the 98th percentile of narrow uploads
  on a random half, so at most about 2% of narrow uploads read as mixed.
- It is checked on the other half, over 5 seeds.
- A key that cannot be computed (K3 on fewer than 20 cells) reads narrow,
  the safe side.

**Real uploads through the colon's v1 bundle**
- Narrow (one lineage for the colon), each must read narrow:
  - Kabatnik's class 1, class 2 and class 4 pools, each alone;
  - Zheng's macrophage, CD8 T and CD4 T pools, each alone and all three
    together (all immune);
  - Fulcher 2026 full and each of its six types alone, PBMC240, and SCoPE2
    published (blood, all immune).
- Mixed, reported, and at least one must read mixed: Kabatnik's three
  classes together; the polyp plate.

**Pass rule, fixed here.** A key passes if:
1. on held halves, at most 3% of simulated narrow uploads read mixed and at
   least 50% of mixed uploads read mixed, in at least 4 of 5 seeds;
2. no real narrow upload reads mixed;
3. at least one real mixed upload reads mixed;
4. on Kabatnik's and Zheng's labelled narrow pools, committed-and-wrong
   under the banded rule is at most 5 points above v1's pooled rule.

Of the keys that pass, the one with the highest mixed share is chosen. If
none passes: NO GO, and by A2's rule the colon v2 is not built.

Writes research/notebook-outputs/organ_v2_band_key/: rules.json (first),
simulated.json, real.json, decision.json.

    python research/notebooks/organ_v2_band_key.py      # from the repository root (GPU)
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
import h5py  # noqa: E402
import li_development as li  # noqa: E402
import narrow_upload_calibration as entry37  # noqa: E402
import nb2_core as n2  # noqa: E402
import scipy.sparse as sp  # noqa: E402
from organ_reference import bundle, calibrate, data  # noqa: E402
from organ_reference import sim_generator as sg  # noqa: E402

from benchmark import baselines_v31, datasets, heldout_formats  # noqa: E402
from service.pipeline import abstention, alignment, calibration, ensemble, fusion, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_band_key"
ORGAN = "large_intestine"
DEV = REPO / "data" / "incoming" / "public_sets"
SEEDS = 5
NARROW_QUANTILE = 98.0
BARS = {"sim_narrow_as_mixed_max": 3.0, "sim_mixed_as_mixed_min": 50.0, "seeds_needed": 4, "wrong_increase_max": 5.0}
ALPHA, MIN_N = 0.1, 50


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def k2(P: np.ndarray, lineage_of: np.ndarray, n_lineages: int) -> float:
    counts = np.bincount(lineage_of[P.argmax(1)], minlength=n_lineages).astype(float)
    p = counts / counts.sum()
    p = p[p > 0]
    return float(np.exp(-(p * np.log(p)).sum()))


def k3(values_genes_by_cells: np.ndarray) -> float | None:
    return entry37.score(values_genes_by_cells)


def band_qhats(cache: dict, uploads: list, C: int) -> dict:
    y = cache["y"].astype(np.int64)
    P = cache["P"].astype(np.float64)
    scores = 1.0 - P[np.arange(len(y)), y]
    mixed = np.array([(u["classes"] >= 3 and u["lineages"] >= 2) or u["scenario"] == "tissue" for u in uploads])[cache["upload"]]
    return {"mixed": n2.fit_qhat(scores[mixed], y[mixed], C, ALPHA, True, MIN_N)[0],
            "narrow": n2.fit_qhat(scores[~mixed], y[~mixed], C, ALPHA, True, MIN_N)[0],
            "pooled": n2.fit_qhat(scores, y, C, ALPHA, True, MIN_N)[0]}


def run(b, raw: alignment.RawMatrix) -> dict:
    """The answers' parts of fusion.project_prepared, kept for re-answering."""
    smoothed, aligned, _ = pipeline._prepare_query(b.feature_genes, raw)
    answers = b.answers
    Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
    P = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, answers.members)])
    counted = aligned.per_cell_observed_genes >= 200
    bg = fusion.best_guess_probabilities(b, Z, aligned.values, aligned.mask, P, counted)
    from service.pipeline import search
    ood = np.mean([search.faiss_max_cosine_to_reference(z, m.reference_latents) for z, m in zip(Z, answers.members)], 0)
    return {"P": P, "guess": ensemble.best_guess(bg.probabilities, None)[0], "ood": ood,
            "observed": aligned.per_cell_observed_genes, "agreement": float(bg.agreement)}


def answers_with(b, r: dict, qhat: np.ndarray) -> list:
    spec = b.answers.spec
    cal = calibration.MondrianCalibrator(qhat, float(np.max(qhat)), ALPHA, "diagnostic", include_best_guess=True)
    space = b.components.label_space.estimate(None, b.class_names, False)
    sets = cal.calibrate(r["P"], None, space, guess_positions=r["guess"]).label_sets
    verdict = abstention.score_abstention(r["ood"], r["observed"], sets, np.zeros(0, np.int64),
                                          min_observed_genes=int(spec["preprocessing"]["min_observed_genes"]),
                                          threshold=float(spec["ood"]["threshold"]))
    out = []
    for i, reason in enumerate(verdict.reason):
        res = None
        if reason in (abstention.AbstainReason.NONE, abstention.AbstainReason.AMBIGUOUS):
            res = ensemble.resolve([b.class_names[c] for c in sets[i]], b.hierarchy)
        out.append(res)
    return out


def committed_wrong(b, answers: list, truth_lineage: str, truth_group: "str | None") -> float:
    h = b.hierarchy
    wrong = 0
    for a in answers:
        if a is None:
            continue
        label, level = a
        lineage = label if level == "lineage" else h[label]["lineage"] if level == "class" else next(
            v["lineage"] for v in h.values() if v["group"] == label)
        group = None if level == "lineage" else (h[label]["group"] if level == "class" else label)
        wrong += int(lineage != truth_lineage or (truth_group is not None and group is not None and group != truth_group))
    return 100.0 * wrong / max(len(answers), 1)


def real_uploads(b) -> list[tuple]:
    """(name, RawMatrix, expected band, truth lineage, truth group) for the colon."""
    out = []
    kab = heldout_formats.read_dia_nn(DEV / "Kabatnik2024_PXD046999" / "C3_region1k_DIANN181_MBR_c124.pg_matrix.tsv")
    kraw = li.table_raw(kab)
    cls = np.array([next((k for k in ("Class1", "Class2", "Class4") if k in s), "") for s in kab.samples])
    cols = lambda m: alignment.RawMatrix(gene_names=kraw.gene_names, cell_ids=[c for c, k in zip(kraw.cell_ids, m) if k],  # noqa: E731
                                         values=np.asarray(kraw.values)[:, m])
    for c, lin in (("Class1", "epithelial"), ("Class2", "epithelial"), ("Class4", "stromal")):
        out.append((f"Kabatnik {c} alone", cols(cls == c), "narrow", lin, None))
    out.append(("Kabatnik classes 1, 2 and 4", kraw, "mixed", None, None))
    files = {"macrophage": ("ColorectalCancer_pg_matrix_Macrophages.txt", "myeloid"),
             "cd8": ("Colorectal_Cancer_pg_matrix_Cytotoxic_T_Cells.txt", "T cell/ILC"),
             "cd4": ("Colorectal_Cancer_pg_matrix_Helper_T_Cells.txt", "T cell/ILC")}
    tables = {k: heldout_formats.read_dia_nn(DEV / "Zheng2025_PXD057118" / f) for k, (f, _) in files.items()}
    for k, t in tables.items():
        out.append((f"Zheng {k} alone", t.raw(), "narrow", "immune", files[k][1]))
    first = tables["macrophage"]
    out.append(("Zheng all three", alignment.RawMatrix(gene_names=list(first.genes), cell_ids=[s for t in tables.values() for s in t.samples],
                                                       values=np.hstack([t.values for t in tables.values()])), "narrow", "immune", None))
    raw = datasets.load_fulcher2026_upload()
    labels = datasets.load_fulcher2026_labels().set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
    out.append(("Fulcher 2026, full", raw, "narrow", None, None))
    for t in ("CD4T", "CD8T", "NK", "B", "monocyte", "DC"):
        m = labels == t
        out.append((f"Fulcher 2026, {t} alone", alignment.RawMatrix(gene_names=raw.gene_names, cell_ids=[c for c, k in zip(raw.cell_ids, m) if k],
                                                                   values=np.asarray(raw.values)[:, m]), "narrow", None, None))
    out.append(("PBMC240", alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()), "narrow", None, None))
    out.append(("SCoPE2, published", baselines_v31.scope2_raw(), "narrow", None, None))
    path = data.resolve("drive:scProteomics/Protein_polyps_p2.h5ad")
    with h5py.File(path, "r") as f:
        genes = [str(g) for g in data._strings(f["var"][f["var"].attrs["_index"]])]
        cells = [str(c) for c in data._strings(f["obs"][f["obs"].attrs["_index"]])]
        Xn = f["X"]
        M = (sp.csr_matrix((Xn["data"][:], Xn["indices"][:], Xn["indptr"][:]), shape=tuple(Xn.attrs["shape"])).toarray()
             if isinstance(Xn, h5py.Group) else Xn[:])
    M = np.where(M > 0, M, np.nan).astype(np.float32)
    out.append(("Polyp plate", alignment.RawMatrix(gene_names=genes, cell_ids=[f"p2_{i}" for i in range(len(cells))], values=M.T), "mixed", None, None))
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    work = data.WORK / ORGAN
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "organ": ORGAN, "seeds": SEEDS, "narrow_quantile": NARROW_QUANTILE, "bars": BARS,
                                        "k3_settings": entry37.SETTINGS,
                                        "cache_sha256": sha256(work / "v2_diagnostics" / "cache_calib.npz")})
    t0 = time.time()
    b = bundle.load(work / "bundle")
    names, hierarchy = b.class_names, b.hierarchy
    lineages = sorted({hierarchy[c]["lineage"] for c in names})
    lineage_of = np.array([lineages.index(hierarchy[c]["lineage"]) for c in names])
    cache = dict(np.load(work / "v2_diagnostics" / "cache_calib.npz"))
    uploads = json.loads((work / "v2_diagnostics" / "uploads_calib.json").read_text(encoding="utf-8"))
    suite = json.loads((work / "sim_suite_calib_v1.json").read_text(encoding="utf-8"))
    cfg = data.load_organ(ORGAN)
    table = pd.read_csv(work / "labels.csv.gz", keep_default_na=False)
    X = data.load_rna(data.resolve(cfg["rna"]), b.feature_genes)[table["row"].to_numpy()]
    profiles = dict(np.load(work / "mask_profiles.npz"))
    # simulated keys
    sim = []
    for u, (spec, up) in enumerate(zip(suite, uploads)):
        rows = cache["upload"] == u
        raw, _ = calibrate.core.raw_upload(spec, X, profiles, len(b.feature_genes), sg)
        logged = alignment.detect_and_transform_value_scale(raw.T)[0]
        sim.append({"upload": up["id"], "mixed": bool((up["classes"] >= 3 and up["lineages"] >= 2) or up["scenario"] == "tissue"),
                    "scenario": up["scenario"], "K1": up["agreement"],
                    "K2": k2(cache["P"][rows].astype(np.float64), lineage_of, len(lineages)), "K3": k3(logged)})
    del X
    sim = pd.DataFrame(sim)
    print(f"simulated keys ({time.time() - t0:.0f}s)", flush=True)
    keys = ("K1", "K2", "K3")
    held = {k: [] for k in keys}
    rng_scen = sim["scenario"].str.split(":").str[0].to_numpy()
    for seed in range(SEEDS):
        rng = np.random.default_rng(seed)
        A = np.zeros(len(sim), bool)
        for s in np.unique(rng_scen):
            idx = np.flatnonzero(rng_scen == s)
            rng.shuffle(idx)
            A[idx[: len(idx) // 2]] = True
        for k in keys:
            v = sim[k].astype(float).fillna(-np.inf).to_numpy()
            t = float(np.percentile(v[A & ~sim["mixed"].to_numpy() & np.isfinite(v)], NARROW_QUANTILE))
            B = ~A
            held[k].append({"threshold": t, "narrow_as_mixed": round(100 * float((v[B & ~sim["mixed"].to_numpy()] > t).mean()), 2),
                            "mixed_as_mixed": round(100 * float((v[B & sim["mixed"].to_numpy()] > t).mean()), 2)})
    final = {}
    for k in keys:
        v = sim[k].astype(float).fillna(-np.inf).to_numpy()
        final[k] = float(np.percentile(v[~sim["mixed"].to_numpy() & np.isfinite(v)], NARROW_QUANTILE))
    data.save_json(OUT / "simulated.json", {"held": held, "final_thresholds": final,
                                            "medians": {k: {"mixed": float(sim.loc[sim["mixed"], k].astype(float).median()),
                                                            "narrow": float(sim.loc[~sim["mixed"], k].astype(float).median())} for k in keys}})
    # real uploads
    q = band_qhats(cache, uploads, len(names))
    real = []
    with bundle.gene_map(work / "bundle"):
        for name, raw, expected, lin, grp in real_uploads(b):
            r = run(b, raw)
            logged = alignment.detect_and_transform_value_scale(np.asarray(raw.values, np.float32))[0]
            values = {"K1": r["agreement"], "K2": k2(r["P"], lineage_of, len(lineages)), "K3": k3(logged)}
            entry = {"upload": name, "cells": int(len(r["P"])), "expected": expected, "keys": values,
                     "reads_mixed": {k: bool(values[k] is not None and values[k] > final[k]) for k in keys}}
            if lin is not None:
                pooled = answers_with(b, r, q["pooled"])
                entry["committed_wrong_pooled"] = round(committed_wrong(b, pooled, lin, grp), 2)
                entry["committed_wrong_banded"] = {k: round(committed_wrong(b, answers_with(b, r, q["mixed"] if entry["reads_mixed"][k] else q["narrow"]),
                                                                            lin, grp), 2) for k in keys}
            real.append(entry)
            print(f"{name}: {values} mixed {entry['reads_mixed']} ({time.time() - t0:.0f}s)", flush=True)
    data.save_json(OUT / "real.json", real)
    decision = {}
    for k in keys:
        sim_ok = sum(h["narrow_as_mixed"] <= BARS["sim_narrow_as_mixed_max"] and h["mixed_as_mixed"] >= BARS["sim_mixed_as_mixed_min"]
                     for h in held[k]) >= BARS["seeds_needed"]
        narrow_ok = all(not e["reads_mixed"][k] for e in real if e["expected"] == "narrow")
        mixed_ok = any(e["reads_mixed"][k] for e in real if e["expected"] == "mixed")
        wrong_ok = all(e["committed_wrong_banded"][k] - e["committed_wrong_pooled"] <= BARS["wrong_increase_max"]
                       for e in real if "committed_wrong_pooled" in e)
        decision[k] = {"simulated": bool(sim_ok), "real_narrow_read_narrow": bool(narrow_ok), "a_real_mixed_read_mixed": bool(mixed_ok),
                       "wrong_within": bool(wrong_ok), "passes": bool(sim_ok and narrow_ok and mixed_ok and wrong_ok),
                       "mixed_share_median": float(np.median([h["mixed_as_mixed"] for h in held[k]]))}
    passing = [k for k in keys if decision[k]["passes"]]
    chosen = max(passing, key=lambda k: decision[k]["mixed_share_median"]) if passing else None
    data.save_json(OUT / "decision.json", {"finished": datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - t0),
                                           "keys": decision, "chosen": chosen, "threshold": final.get(chosen) if chosen else None,
                                           "colon_v2_built": chosen is not None})
    print(json.dumps({"keys": decision, "chosen": chosen}, indent=1))


if __name__ == "__main__":
    main()
