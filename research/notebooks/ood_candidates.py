"""Goal 2, Phase 2c: out-of-distribution scores beyond the served one. Does a
cell's distance to the reference say "not a blood cell" better than the
served score? Development data only; rules fixed here before the run.

Scores, higher meaning closer to the reference, each computed by the
service's own functions on the upload as served:
- S0, served: the members' mean maximum cosine to the reference latents (the
  response's reference_similarity);
- S1, nearest RNA class mean: the largest masked Pearson correlation with
  v4.1's class-balanced RNA class means;
- S2, protein space: the largest masked Pearson correlation with v4.2's
  protein class means (Rieckmann 2017), over the classes they cover;
- S3, nearest class centre: the members' mean maximum cosine to v4.1's
  class-balanced centroids.

Choosing (tuning data, as the plan fixed: Furtwangler 2025 and scrambled cells):
- scrambled: in Fulcher 2026's and in PBMC240's upload, 20% of the cells are
  replaced by scrambled cells (another cell of the same upload, its observed
  values shuffled among its observed genes; seed 0); AUROC real over
  scrambled, within the upload;
- Furtwangler 2025's CD34+ cells (their own upload) against PBMC240's cells:
  AUROC PBMC240 over Furtwangler.
The best of S1-S3 by the mean of these three AUROCs is chosen. It replaces S0
only if all hold:
1. its mean AUROC is at least S0's + 0.05, and none of its three is below
   S0's by more than 0.02;
2. at a threshold set as NB2 set S0's (the 1st percentile over NB3c's
   calibration cells, te_cal with real masks, at least 200 observed genes,
   train-plus-validation references), the share of Fulcher's and PBMC240's
   cells below it is at most S0's share + 2 points;
3. on the real foreign cells of the development data, reported beside it
   (PXD077946's HEK293T and HCT116, MSV000099294's HMC3), the share below
   the threshold is not lower than S0's on any set.
Also reported, never deciding: PXD077946's K562 (a leukaemia line) and
MSV000099294's microglia (tissue macrophages), and each set's AUROC against
PBMC240's cells. Added after the first run, reported only: v4.1's served
answers for each foreign set (abstention reasons and committed answers).

Writes research/notebook-outputs/ood_candidates/summary.json.

    python research/notebooks/ood_candidates.py      # from the repository root
"""
from __future__ import annotations

import collections
import dataclasses
import json
import re
import sys
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v4_calibration as phase3  # noqa: E402
import v41_core as core  # noqa: E402
import v42_protein_means as v42  # noqa: E402

from service.pipeline import alignment, fusion, gene_ids, pipeline, search  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "ood_candidates"
PUBLIC = REPO / "data" / "incoming" / "public_sets"
SCRAMBLED_SHARE = 0.2
SCORES = ("S0", "S1", "S2", "S3")


def scramble(raw: alignment.RawMatrix, rng) -> tuple[alignment.RawMatrix, np.ndarray]:
    """raw with SCRAMBLED_SHARE of its cells replaced by scrambled copies of other cells; the scrambled mask."""
    n = len(raw.cell_ids)
    k = int(round(SCRAMBLED_SHARE * n))
    targets = rng.choice(n, k, replace=False)
    values = raw.values.copy()
    for t in targets:
        src = values[:, rng.integers(n)].copy()
        seen = np.flatnonzero(np.isfinite(src))
        src[seen] = src[rng.permutation(seen)]
        values[:, t] = src
    flag = np.zeros(n, bool)
    flag[targets] = True
    return dataclasses.replace(raw, values=values), flag


def pxd077946() -> dict:
    with zipfile.ZipFile(PUBLIC / "PXD077946" / "diann_singlecell.zip") as z:
        raw = alignment.parse_matrix_csv(z.read("report.unique_genes_matrix.tsv").decode("utf-8"))
    out = {}
    for line in ("293T", "HCT116", "K562"):
        keep = [i for i, c in enumerate(raw.cell_ids) if re.search(line, c, re.I)]
        if keep:
            out[line] = alignment.RawMatrix(gene_names=raw.gene_names, cell_ids=[raw.cell_ids[i] for i in keep],
                                            values=raw.values[:, keep])
    return out


def msv000099294() -> dict:
    base = PUBLIC / "MSV000099294"
    return {name: alignment.parse_matrix_csv((base / f"DirectDIA_{name}_1cell_Protein_Quant_Pivot_Report.tsv").read_text(encoding="utf-8"))
            for name in ("HMC3", "Microglia")}


class Scorer:
    def __init__(self, bundle, protein_bundle) -> None:
        self.b, self.p = bundle, protein_bundle
        self.names = list(bundle.class_names)

    def score(self, raw: alignment.RawMatrix) -> dict:
        b = self.b
        smoothed, aligned, _ = pipeline._prepare_query(b.feature_genes, raw)
        Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in b.answers.members]
        s0 = np.mean([search.faiss_max_cosine_to_reference(z, m.reference_latents) for z, m in zip(Z, b.answers.members)], axis=0)
        s1 = fusion.masked_pearson(aligned.values, aligned.mask, b.class_means).max(axis=1)
        pv, pm = fusion.protein_query(raw, self.p.protein_genes)
        s2 = fusion.masked_pearson(pv, pm, self.p.protein_means)[:, self.p.protein_covered].max(axis=1)
        s3 = np.mean([(z / np.linalg.norm(z, axis=1, keepdims=True)) @ m.centroids.T for z, m in zip(Z, b.members)], axis=0).max(axis=1)
        counted = aligned.per_cell_observed_genes >= core.MIN_GENES
        return {"S0": s0, "S1": s1, "S2": s2, "S3": s3, "counted": counted}


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    return float(roc_auc_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))], np.r_[pos, neg]))


def calibration_thresholds(v41, v42b) -> dict:
    """Each score's 1st percentile over NB3c's calibration cells, train-plus-validation references."""
    names = list(v41.class_names)
    table = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    y = np.array([names.index(c) for c in table["class_name"]])
    split = np.load(phase3.NB1 / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    v31 = v41.answers
    cents = [phase3.centroids_from(m.reference_latents[trainval], y[trainval], len(names)) for m in v31.members]
    answers = dataclasses.replace(v31, members=phase3.restricted(v31.members, trainval, cents),
                                  property_values=v31.property_values[trainval])
    cb = [np.load(phase3.CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy")
          for m in v41.members]
    calib = dataclasses.replace(v41, answers=answers, members=phase3.restricted(v41.members, trainval, cb),
                                class_means=np.load(phase3.CALIB_BUNDLE / "class_means_cb.npy").astype(np.float32))
    scorer = Scorer(calib, v42b)
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_x = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_x[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    genes = list(v41.feature_genes)
    collected = {k: [] for k in SCORES}
    for s in suites["calib"]:
        raw = phase3.raw_upload(s, get_raw, profiles, len(genes))
        sc = scorer.score(alignment.RawMatrix(gene_names=genes, cell_ids=[f"c{i}" for i in range(len(raw))], values=raw.T))
        for k in SCORES:
            collected[k].append(sc[k][sc["counted"]])
    return {k: float(np.percentile(np.concatenate(v), 1.0)) for k, v in collected.items()}


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    v41 = pipeline.load_bundle("v4.1")
    v42b = fusion.V4Bundle.load(require_evaluation=False, version="v4.2")
    scorer = Scorer(v41, v42b)
    up = v42.uploads()
    # S0 as served must equal the response's reference_similarity
    cells = pipeline.run_projection(v41, up["pbmc240"])["cells"]
    served = np.array([c["reference_similarity"] for c in cells])
    pbmc = scorer.score(up["pbmc240"])
    if np.abs(served - pbmc["S0"]).max() > 1e-5:
        raise SystemExit("STOP: S0 is not the served reference similarity")

    rng = np.random.default_rng(0)
    tuning = {}
    for name in ("fulcher2026", "pbmc240"):
        raw, flag = scramble(up[name], rng)
        sc = scorer.score(raw)
        tuning[f"scrambled in {name}"] = {k: auroc(sc[k][~flag], sc[k][flag]) for k in SCORES}
    furt = scorer.score(up["furtwangler2025"])
    tuning["PBMC240 over Furtwangler"] = {k: auroc(pbmc[k], furt[k]) for k in SCORES}
    mean = {k: float(np.mean([t[k] for t in tuning.values()])) for k in SCORES}
    best = max(("S1", "S2", "S3"), key=lambda k: mean[k])
    print(json.dumps({"tuning": tuning, "mean": mean, "best": best}, indent=1), flush=True)

    thresholds = calibration_thresholds(v41, v42b)
    fulcher = scorer.score(up["fulcher2026"])
    in_ref = {k: np.r_[fulcher[k], pbmc[k]] for k in SCORES}
    false_abstention = {k: 100 * float((in_ref[k] < thresholds[k]).mean()) for k in SCORES}
    foreign = {**{f"PXD077946 {k}": v for k, v in pxd077946().items()},
               **{f"MSV000099294 {k}": v for k, v in msv000099294().items()}}
    reported = {}
    for name, raw in foreign.items():
        sc = scorer.score(raw)
        served_cells = pipeline.run_projection(v41, raw)["cells"]
        reported[name] = {"cells": len(raw.cell_ids),
                          "below_threshold_pct": {k: 100 * float((sc[k] < thresholds[k]).mean()) for k in SCORES},
                          "auroc_pbmc240_over_set": {k: auroc(pbmc[k], sc[k]) for k in SCORES},
                          "v41_served": dict(collections.Counter(
                              c.get("abstain_reason") or f"answer: {c['label']}" for c in served_cells).most_common())}
    deciding = [n for n in reported if n.endswith(("293T", "HCT116", "HMC3"))]
    rule1 = mean[best] >= mean["S0"] + 0.05 and all(t[best] >= t["S0"] - 0.02 for t in tuning.values())
    rule2 = false_abstention[best] <= false_abstention["S0"] + 2
    rule3 = all(reported[n]["below_threshold_pct"][best] >= reported[n]["below_threshold_pct"]["S0"] for n in deciding)
    summary = {"tuning_auroc": tuning, "tuning_mean": mean, "chosen": best, "thresholds": thresholds,
               "false_abstention_pct_fulcher_pbmc240": false_abstention, "foreign_development": reported,
               "rules": {"1_auroc": bool(rule1), "2_false_abstention": bool(rule2), "3_foreign": bool(rule3)},
               "GO": bool(rule1 and rule2 and rule3)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "tuning_auroc"}, indent=1))


if __name__ == "__main__":
    main()
