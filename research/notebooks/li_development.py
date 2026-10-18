"""Track I, Stage 2 (research/organ-references.md): the large intestine
reference's development checks, gates G1 and G3, scored once.

The gates were fixed in research/organ-references.md before any colon model
existed. The script records its own sha256, the gates and the start time in
rules.json before computing anything. No setting is tuned to pass a gate; a
miss stops the work and goes to the owner.

G1, simulated uploads from the colon's RNA test cells. The organ's
evaluation suite (scripts/build_organ_reference.py, suites stage: 240
uploads from the test split) runs through the service's own code
(fusion.project_prepared) on references without test cells, as v4.1's Phase
C did (research/notebooks/v41_phase3.py): the reference latents and
centroids restricted to the train and validation rows, and the class-
balanced layer rebuilt on those rows. Cells with at least 200 observed genes.
Pass when all hold:
- correct when committed, at the stated level, at least 90%;
- committed at least 75%;
- conformal coverage (the true class in the set before abstention) at least 85%;
- false abstention (refused as outside the supported region) at most 2%.

G3, development protein, through the served form of the bundle (every
reference cell). Probabilities are the fused best-guess probabilities,
recomputed with the service's functions.
- Kabatnik 2024 (PXD046999), its one-search table of CDX2 classes 1, 2 and 4
  (C3_region1k_DIANN181_MBR_c124.pg_matrix.tsv; class from each run's name):
  AUROC at least 0.8 of P(epithelial lineage), classes 1 and 2 (epithelium)
  over class 4 (stroma).
- Zheng 2025 (PXD057118), its three colorectal tables (macrophage, CD8 T, CD4
  T; one protein list) as one upload: at least 80% of pools assigned to their
  group (argmax over groups of the summed probabilities): T cell/ILC for the
  T-cell pools, myeloid for the macrophage pools. CD8 T against CD4 T is
  reported.
- The polyp plate (516 cells, no labels): for each best-guess group with at
  least 20 cells, AUROC at least 0.7 of a marker score, its cells over the
  plate's other cells. The score is the mean of a cell's upload-z-scored
  values over the group's 20 most specific genes in the reference's
  class-balanced class means (group mean minus the highest other group's),
  among genes the plate observes in at least 10% of cells.

Writes research/notebook-outputs/li_development/: rules.json, g1.json (with
per-scenario figures), g3.json, and gates.json (every gate's value and
verdict).

    python research/notebooks/li_development.py      # from the repository root (GPU)
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

import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from organ_reference import bundle, calibrate, data  # noqa: E402
from organ_reference import sim_generator as sg  # noqa: E402

from benchmark import heldout_formats  # noqa: E402
from service.pipeline import abstention, alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "li_development"
ORGAN = "large_intestine"
MIN_GENES = 200
GATES = {"g1_correct_when_committed_min": 90.0, "g1_committed_min": 75.0, "g1_coverage_min": 85.0,
         "g1_false_abstention_max": 2.0, "g3_kabatnik_auroc_min": 0.8, "g3_zheng_group_accuracy_min": 80.0,
         "g3_polyp_auroc_min": 0.7, "g3_polyp_min_cells": 20, "g3_polyp_marker_genes": 20, "g3_polyp_min_observed": 0.10}
DEV = REPO / "data" / "incoming" / "public_sets"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def correct_at_level(label, level, true_name, hierarchy) -> bool:
    if level == "class":
        return label == true_name
    return label == hierarchy[true_name][level]


def fused(b, smoothed, aligned):
    """The answers' ensemble probabilities, the fused best-guess
    probabilities and the label space, as the response builds them
    (research/notebooks/v41_phase3.coverage)."""
    names, answers = b.class_names, b.answers
    Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
    P_all = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature)
                                             for z, m in zip(Z, answers.members)])
    space = b.components.label_space.estimate(None, names, False)
    counted = aligned.per_cell_observed_genes >= MIN_GENES
    G = fusion.best_guess_probabilities(b, Z, aligned.values, aligned.mask, P_all, counted).probabilities
    return P_all, b.components.label_space.probabilities(G, space), space


def covered(b, smoothed, aligned, truth_pos) -> np.ndarray:
    P_all, G, space = fused(b, smoothed, aligned)
    guess = ensemble.best_guess(G, space.positions)[0]
    P = b.components.label_space.probabilities(P_all, space)
    sets = b.components.calibrator.calibrate(P, None, space, guess_positions=guess).label_sets
    return np.array([t in set(s) for t, s in zip(truth_pos, sets)])


def cell_rows(response, truth, cov, hierarchy, upload, scenario) -> list[dict]:
    rows = []
    for i, cell in enumerate(response["cells"]):
        if cell["observed_genes"] < MIN_GENES:
            continue
        committed = not cell["abstained"]
        rows.append({"upload": upload, "scenario": scenario.split(":")[0], "true": truth[i],
                     "ood_abstained": cell.get("abstain_reason") == abstention.AbstainReason.OUT_OF_DISTRIBUTION.value,
                     "committed": committed, "level": cell["label_level"] if committed else "abstain",
                     "correct": committed and correct_at_level(cell["label"], cell["label_level"], truth[i], hierarchy),
                     "best_guess": cell.get("best_guess", {}).get("label"), "covered": bool(cov[i])})
    return rows


def summary(d: pd.DataFrame) -> dict:
    up = d.groupby("upload").apply(lambda u: 100 * (balanced_accuracy_score(u["true"], u["best_guess"])
                                                    if u["true"].nunique() > 1 else float((u["true"] == u["best_guess"]).mean())),
                                   include_groups=False)
    com = d[d["committed"]]
    return {"cells": int(len(d)), "committed": round(100 * d["committed"].mean(), 2),
            "correct_when_committed": round(100 * com["correct"].mean(), 2) if len(com) else None,
            "false_abstention": round(100 * d["ood_abstained"].mean(), 2),
            "levels": {k: round(100 * v, 2) for k, v in d["level"].value_counts(normalize=True).items()},
            "best_guess_per_upload_balanced": round(float(up.mean()), 2),
            "coverage": round(100 * d["covered"].mean(), 2)}


def held_out(full, X, y, trainval, paths, n):
    """The bundle with references from the train and validation rows only."""
    def restrict(members, cents):
        return tuple(dataclasses.replace(m, reference_latents=m.reference_latents[trainval], centroids=c)
                     for m, c in zip(members, cents))
    yt = y[trainval]
    ans_c = [calibrate.core.centroids_from(m.reference_latents[trainval], yt, n) for m in full.answers.members]
    answers = dataclasses.replace(full.answers, members=restrict(full.answers.members, ans_c),
                                  property_values=full.answers.property_values[trainval])
    layer = calibrate.best_guess_layer(paths, yt, X[trainval], n)
    cb = [layer["centroids_cb"][m.name] for m in full.members]
    return dataclasses.replace(full, answers=answers, members=restrict(full.members, cb), class_means=layer["means"])


def g1(b_full, build_dir: Path, cfg: dict, t0: float) -> dict:
    names, hierarchy = b_full.class_names, b_full.hierarchy
    table = pd.read_csv(build_dir / "labels.csv.gz", keep_default_na=False)
    y = table["class_idx"].to_numpy()
    X = data.load_rna(data.resolve(cfg["rna"]), b_full.feature_genes)[table["row"].to_numpy()]
    split = np.load(build_dir / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    paths = {m.name: build_dir / "bundle" / "members" / m.name for m in b_full.members}
    b = held_out(b_full, X, y, trainval, paths, len(names))
    print(f"held-out bundle ready ({time.time() - t0:.0f}s)", flush=True)
    profiles = dict(np.load(build_dir / "mask_profiles.npz"))
    suite = json.loads((build_dir / "sim_suite_eval_v1.json").read_text(encoding="utf-8"))
    if set(i for s in suite for i in s["cell_idx"]) & set(trainval.tolist()):
        raise SystemExit("an evaluation cell is in the reference rows")
    genes = b.feature_genes
    resolution = gene_ids.resolve_identifiers(genes)
    rows = []
    for u, spec in enumerate(suite):
        raw, _ = calibrate.core.raw_upload(spec, X, profiles, len(genes), sg)
        ids = [f"{spec['id']}_{i}" for i in range(len(raw))]
        smoothed, aligned, scale = pipeline._prepare_query(genes, alignment.RawMatrix(gene_names=genes, cell_ids=ids, values=raw.T))
        truth_pos = y[np.asarray(spec["cell_idx"])]
        response = fusion.project_prepared(b, smoothed, aligned, scale, resolution, False, b.components)
        rows += cell_rows(response, [names[k] for k in truth_pos], covered(b, smoothed, aligned, truth_pos),
                          hierarchy, spec["id"], spec["scenario"])
        if (u + 1) % 40 == 0:
            print(f"G1: {u + 1}/{len(suite)} uploads ({time.time() - t0:.0f}s)", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "g1_cells.csv.gz", index=False, lineterminator="\n")
    out = {"overall": summary(d), "by_scenario": {k: summary(v) for k, v in d.groupby("scenario")},
           "per_class_recall_committed": {c: round(100 * float(v["correct"].mean()), 2) for c, v in d.groupby("true")}}
    return out


def table_raw(table: heldout_formats.Table) -> alignment.RawMatrix:
    return table.raw()


def run_upload(b, raw: alignment.RawMatrix):
    smoothed, aligned, scale = pipeline._prepare_query(b.feature_genes, raw)
    response = fusion.project_prepared(b, smoothed, aligned, scale, gene_ids.resolve_identifiers(raw.gene_names), False,
                                       b.components)
    _, G, _ = fused(b, smoothed, aligned)
    return response, G, aligned


def group_sums(G: np.ndarray, names: list[str], hierarchy: dict, level: str) -> pd.DataFrame:
    keys = sorted({hierarchy[c][level] for c in names})
    return pd.DataFrame({k: G[:, [i for i, c in enumerate(names) if hierarchy[c][level] == k]].sum(1) for k in keys})


def g3(b) -> dict:
    names, hierarchy = b.class_names, b.hierarchy
    out = {}
    # Kabatnik: CDX2 classes 1 and 2 (epithelium) over class 4 (stroma)
    kab = heldout_formats.read_dia_nn(DEV / "Kabatnik2024_PXD046999" / "C3_region1k_DIANN181_MBR_c124.pg_matrix.tsv")
    cls = [next((k for k in ("Class1", "Class2", "Class4") if k in s), None) for s in kab.samples]
    response, G, _ = run_upload(b, table_raw(kab))
    lin = group_sums(G, names, hierarchy, "lineage")
    epi = np.array([c in ("Class1", "Class2") for c in cls])
    out["kabatnik"] = {"pools": len(cls), "by_class": pd.Series(cls).value_counts().to_dict(),
                       "auroc_epithelial": round(float(roc_auc_score(epi, lin["epithelial"].to_numpy())), 4),
                       "mean_p_epithelial": {k: round(float(lin["epithelial"][np.array(cls) == k].mean()), 4) for k in ("Class1", "Class2", "Class4")},
                       "answers": [{"class": c, "label": cell["label"], "level": cell["label_level"],
                                    "abstained": cell["abstained"], "best_guess": cell.get("best_guess", {}).get("label")}
                                   for c, cell in zip(cls, response["cells"])]}
    # Zheng: the three colorectal tables as one upload
    files = {"macrophage": "ColorectalCancer_pg_matrix_Macrophages.txt", "cd8": "Colorectal_Cancer_pg_matrix_Cytotoxic_T_Cells.txt",
             "cd4": "Colorectal_Cancer_pg_matrix_Helper_T_Cells.txt"}
    tables = {k: heldout_formats.read_dia_nn(DEV / "Zheng2025_PXD057118" / f) for k, f in files.items()}
    first = tables["macrophage"]
    if any(t.genes != first.genes for t in tables.values()):
        raise SystemExit("Zheng's three tables do not share one protein list")
    raw = alignment.RawMatrix(gene_names=list(first.genes), cell_ids=[s for t in tables.values() for s in t.samples],
                              values=np.hstack([t.values for t in tables.values()]))
    truth = [k for k, t in tables.items() for _ in t.samples]
    response, G, _ = run_upload(b, raw)
    grp = group_sums(G, names, hierarchy, "group")
    called = grp.idxmax(1).to_numpy()
    want = {"macrophage": "myeloid", "cd8": "T cell/ILC", "cd4": "T cell/ILC"}
    right = np.array([called[i] == want[t] for i, t in enumerate(truth)])
    cd8, cd4 = names.index("cd8-positive, alpha-beta t cell"), names.index("cd4-positive, alpha-beta t cell")
    t_pools = np.array([t in ("cd8", "cd4") for t in truth])
    out["zheng"] = {"pools": len(truth), "group_accuracy": round(100 * float(right.mean()), 2),
                    "called_groups": pd.crosstab(pd.Series(truth, name="truth"), pd.Series(called, name="called")).to_dict(),
                    "cd8_over_cd4_auroc": round(float(roc_auc_score(np.array(truth)[t_pools] == "cd8", (G[t_pools, cd8] - G[t_pools, cd4]))), 4),
                    "answers": [{"truth": t, "label": cell["label"], "level": cell["label_level"], "abstained": cell["abstained"],
                                 "best_guess": cell.get("best_guess", {}).get("label")} for t, cell in zip(truth, response["cells"])]}
    # the polyp plate: marker concordance of the best-guess groups
    path = data.resolve("drive:scProteomics/Protein_polyps_p2.h5ad")
    with h5py.File(path, "r") as f:
        genes = [str(g) for g in data._strings(f["var"][f["var"].attrs["_index"]])]
        cells = [str(c) for c in data._strings(f["obs"][f["obs"].attrs["_index"]])]
        Xn = f["X"]
        M = (sp.csr_matrix((Xn["data"][:], Xn["indices"][:], Xn["indptr"][:]), shape=tuple(Xn.attrs["shape"])).toarray()
             if isinstance(Xn, h5py.Group) else Xn[:])
    M = np.where(M > 0, M, np.nan).astype(np.float32)
    raw = alignment.RawMatrix(gene_names=genes, cell_ids=[f"p2_{i}" for i in range(len(cells))], values=M.T)
    response, G, aligned = run_upload(b, raw)
    best = np.array([cell.get("best_guess", {}).get("label") or "" for cell in response["cells"]])
    best_group = np.array([hierarchy[c]["group"] if c in hierarchy else "" for c in best])
    means = b.class_means  # classes x genes, class-balanced z-scored RNA
    groups = sorted({hierarchy[c]["group"] for c in names})
    gmeans = np.stack([means[[i for i, c in enumerate(names) if hierarchy[c]["group"] == g]].mean(0) for g in groups])
    observed = aligned.mask.mean(0) >= GATES["g3_polyp_min_observed"]
    polyp = {"cells": len(best), "best_guess_groups": pd.Series(best_group).value_counts().to_dict(),
             "answers_levels": pd.Series([c["label_level"] if not c["abstained"] else "abstain" for c in response["cells"]]).value_counts().to_dict(),
             "groups": {}}
    for gi, g in enumerate(groups):
        n_g = int((best_group == g).sum())
        if n_g < GATES["g3_polyp_min_cells"]:
            continue
        spec = gmeans[gi] - np.delete(gmeans, gi, axis=0).max(0)
        spec = np.where(observed, spec, -np.inf)
        top = np.argsort(-spec)[:GATES["g3_polyp_marker_genes"]]
        vals, mask = aligned.values[:, top], aligned.mask[:, top]
        score = np.where(mask.sum(1) > 0, (vals * mask).sum(1) / np.maximum(mask.sum(1), 1), np.nan)
        ok = np.isfinite(score)
        auc = roc_auc_score((best_group == g)[ok], score[ok]) if 0 < (best_group == g)[ok].sum() < ok.sum() else None
        polyp["groups"][g] = {"cells": n_g, "auroc": None if auc is None else round(float(auc), 4),
                              "markers": [b.feature_genes[i] for i in top]}
    out["polyp"] = polyp
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    build_dir = data.WORK / ORGAN
    cfg = data.load_organ(ORGAN)
    data.save_json(OUT / "rules.json", {
        "script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"), "gates": GATES,
        "bundle_manifest_sha256": sha256(build_dir / "bundle" / "MANIFEST.json"),
        "organ_file_sha256": sha256(data.ORGANS / f"{ORGAN}.json")})
    t0 = time.time()
    b = bundle.load(build_dir / "bundle")
    print(f"bundle loaded: {len(b.class_names)} classes, {len(b.feature_genes)} genes ({time.time() - t0:.0f}s)", flush=True)
    r1 = g1(b, build_dir, cfg, t0)
    data.save_json(OUT / "g1.json", r1)
    print(json.dumps(r1["overall"], indent=1), flush=True)
    r3 = g3(b)
    data.save_json(OUT / "g3.json", r3)
    o = r1["overall"]
    polyp_aucs = {g: v["auroc"] for g, v in r3["polyp"]["groups"].items()}
    gates = {
        "G1 correct when committed": (o["correct_when_committed"], o["correct_when_committed"] >= GATES["g1_correct_when_committed_min"]),
        "G1 committed": (o["committed"], o["committed"] >= GATES["g1_committed_min"]),
        "G1 coverage": (o["coverage"], o["coverage"] >= GATES["g1_coverage_min"]),
        "G1 false abstention": (o["false_abstention"], o["false_abstention"] <= GATES["g1_false_abstention_max"]),
        "G3 Kabatnik AUROC": (r3["kabatnik"]["auroc_epithelial"], r3["kabatnik"]["auroc_epithelial"] >= GATES["g3_kabatnik_auroc_min"]),
        "G3 Zheng group accuracy": (r3["zheng"]["group_accuracy"], r3["zheng"]["group_accuracy"] >= GATES["g3_zheng_group_accuracy_min"]),
        "G3 polyp marker AUROCs": (polyp_aucs, bool(polyp_aucs) and all(v is not None and v >= GATES["g3_polyp_auroc_min"]
                                                                        for v in polyp_aucs.values())),
    }
    data.save_json(OUT / "gates.json", {"finished": datetime.now().isoformat(timespec="seconds"),
                                         "gates": {k: {"value": v, "pass": bool(p)} for k, (v, p) in gates.items()},
                                         "all_pass": all(p for _, p in gates.values()), "seconds": round(time.time() - t0)})
    for k, (v, p) in gates.items():
        print(f"{'PASS' if p else 'MISS'}  {k}: {v}")


if __name__ == "__main__":
    main()
