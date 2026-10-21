"""Step 2 of the 2026-10-21 data search (research/reference-data-search.md),
a probe that chooses the route, not a candidate: do the Allen Human Immune
Health Atlas's cells (Gong 2025; side-tests amendment 20), embedded the
reference's way by v4.1's five members, land where Tabula Sapiens's cells of
the same class do?

Hao 2021's dendritic cells did not (run history entry 40): Hao's pDC centre
was nearly orthogonal to Tabula Sapiens's (cosine -0.19 to 0.19), and
adding them to the class centres was NO GO. The Allen atlas has 108 donors,
14,235 cDC2, 943 cDC1, 7,587 pDC and 1,075 CMP cells.

How: up to 2,000 cells per Allen label (seed 0); raw counts to
log1p(counts / total x 10,000), as Tabula Sapiens and Hao; the feature
genes; v4's class-balanced statistics; each member's encoder; its
class-balanced centroids. Platelets and erythrocytes, classes Tabula Sapiens
holds thousands of, are the control.

The reading, fixed before the run:
- **Route A (the Allen cells into the class centres, entry 40's design 1)**
  is worth a candidate only if, in every member, the Allen pDC centre and
  the Allen cDC (cDC1 and cDC2) centre each have cosine at least 0.5 with
  Tabula Sapiens's pDC and myeloid DC centroids, and the controls'
  nearest-centroid recall is at least 50%.
- Otherwise **route B**: the Allen cells go into training (new members), with
  Allen cells of every class beside them so that the atlas cannot stand in
  for the class.

Writes summary.json into its own folder of research/notebook-outputs (OUT).

    python research/notebooks/allen_dc_probe.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import anndata as ad
import numpy as np
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from service.pipeline import pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "allen_dc_probe"
HIHA = REPO / "data" / "incoming" / "public_sets" / "Gong2025_HIHA"
FILES = ("4f925e42-3e42-4e2d-8394-4e88bf9a0ff2.h5ad", "70dd5115-cec8-49ad-a2fb-f985067b193f.h5ad")
V4_STATS = REPO / "service" / "model" / "v4" / "class_balanced_stats.npz"
PER_LABEL, SEED = 2000, 0
MDC, PDC = "myeloid dendritic cell", "plasmacytoid dendritic cell"
# Allen's L3 labels -> the reference class each should land on
TARGET = {"cDC1": MDC, "HLA-DRhi cDC2": MDC, "CD14+ cDC2": MDC, "ISG+ cDC2": MDC, "pDC": PDC,
          "CMP cell": "common myeloid progenitor", "Platelet": "platelet", "Erythrocyte": "erythrocyte"}
CONTROLS = ("Platelet", "Erythrocyte")
COS_MIN, CONTROL_MIN = 0.5, 50.0


def allen_cells(genes: list[str], rng) -> tuple[np.ndarray, np.ndarray]:
    rows, labels = [], []
    for name in FILES:
        a = ad.read_h5ad(HIHA / name, backed="r")
        l3 = a.obs["AIFI_L3"].astype(str).to_numpy()
        symbols = a.var["gene_symbols"].astype(str).str.upper().to_numpy()
        first = {}
        for j, s in enumerate(symbols):
            first.setdefault(s, j)
        cols = np.array([first.get(g.upper(), -1) for g in genes])
        for label in TARGET:
            at = np.flatnonzero(l3 == label)
            if not len(at):
                continue
            pick = np.sort(rng.choice(at, size=min(PER_LABEL, len(at)), replace=False))
            counts = sp.csr_matrix(a.raw.X[pick]).astype(np.float64)
            total = np.asarray(counts.sum(1)).ravel()
            X = (sp.diags(1e4 / total) @ counts).tocsr()
            X.data = np.log1p(X.data)
            dense = np.zeros((len(pick), len(genes)), np.float32)
            dense[:, cols >= 0] = X[:, cols[cols >= 0]].toarray()
            rows.append(dense)
            labels += [label] * len(pick)
    return np.vstack(rows), np.array(labels)


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    bundle = pipeline.load_bundle("v4.1")
    names, genes = list(bundle.class_names), list(bundle.feature_genes)
    X, label = allen_cells(genes, np.random.default_rng(SEED))
    stats = np.load(V4_STATS)
    values = ((X - stats["mu"]) / (stats["sd"] + 1e-8)).astype(np.float32)
    ones = np.ones_like(values)
    unit = lambda M: M / np.linalg.norm(M, axis=-1, keepdims=True)  # noqa: E731
    per_member, votes = [], []
    for k, member in enumerate(bundle.members):
        Z = unit(np.asarray(member.encoder_handle.encode(values, ones), dtype=np.float64))
        C = unit(np.asarray(member.centroids, dtype=np.float64))
        nearest = (Z @ C.T).argmax(1)
        votes.append(nearest)
        cdc = np.isin(label, [k2 for k2, v in TARGET.items() if v == MDC])
        per_member.append({
            "cos_allen_pdc_ts_pdc": round(float(unit(Z[label == "pDC"].mean(0)) @ C[names.index(PDC)]), 4),
            "cos_allen_cdc_ts_mdc": round(float(unit(Z[cdc].mean(0)) @ C[names.index(MDC)]), 4),
        })
    votes = np.array(votes)
    landing = {}
    for lab in TARGET:
        at = label == lab
        if not at.any():
            continue
        first = votes[:, at].reshape(-1)
        counts = np.bincount(first, minlength=len(names)) / first.size
        top = np.argsort(counts)[::-1][:3]
        landing[lab] = {"n": int(at.sum()), "target": TARGET[lab],
                        "recall_pct": round(100 * float(counts[names.index(TARGET[lab])]), 2),
                        "top": {names[i]: round(100 * float(counts[i]), 2) for i in top}}
    cos_ok = all(m["cos_allen_pdc_ts_pdc"] >= COS_MIN and m["cos_allen_cdc_ts_mdc"] >= COS_MIN for m in per_member)
    control_ok = all(landing[c]["recall_pct"] >= CONTROL_MIN for c in CONTROLS if c in landing)
    summary = {"script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "run": datetime.now().isoformat(timespec="seconds"), "cells": int(len(label)),
               "per_member": per_member, "landing": landing,
               "reading": {"cosines_at_least": COS_MIN, "controls_at_least": CONTROL_MIN,
                           "cosines_ok": cos_ok, "controls_ok": control_ok,
                           "route": "A: the Allen cells into the class centres" if cos_ok and control_ok
                           else "B: the Allen cells into training, beside Allen cells of every class"},
               "seconds": round(time.time() - t0)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
