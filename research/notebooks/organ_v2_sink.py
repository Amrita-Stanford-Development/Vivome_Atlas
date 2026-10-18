"""Organ references v2, diagnosis A1b (research/organ-references.md, "Version
2"): what draws protein pools to one class? An explanation only; it decides
nothing by itself.

A1 (research/notebooks/organ_v2_masking.py) showed that removing
immunoglobulin constant chains and serum proteins leaves the sinks as they
were: the lymph node still guesses plasma cell for 44 of Zheng's 48 tonsil
pools, and the lung still calls control epithelial pools immune. Four probes
on the same seen development uploads, each on the organ's v1 bundle:

1. Path. Which path picks the sink class: the answers' encoder
   probabilities, the correlation to RNA class means, or the fused best
   guess? Each one's argmax class is counted per pool.
2. Genes. Remove the sink class's most specific genes from the upload (its
   class-balanced z-scored RNA mean minus the highest other class's), the
   top 25, 50, 100 and 200, against as many random detected genes (5
   draws). Does the sink follow its markers?
3. Depth. Pools observe far more proteins than a single cell. Keep only a
   random 10%, 20% or 40% of each pool's observed proteins (5 draws each),
   so a pool looks like a cell. Does the sink fade?
4. Company. Upload each population's pools on their own, and each pool
   alone with the rest of its population, against the mixed upload. Is the
   sink made by the upload's mix (per-upload scaling)?

Writes research/notebook-outputs/organ_v2_sink/: rules.json (first), probes.json.

    python research/notebooks/organ_v2_sink.py      # from the repository root (GPU)
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import warnings
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import li_development as li  # noqa: E402
import lung_development  # noqa: E402
from organ_reference import bundle, data  # noqa: E402

from benchmark import heldout_formats  # noqa: E402
from service.pipeline import alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_sink"
DEV = REPO / "data" / "incoming" / "public_sets"
SEED = 20261018
TOPS = (25, 50, 100, 200)
DEPTHS = (0.1, 0.2, 0.4)
DRAWS = 5


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def zheng_tonsil() -> tuple[alignment.RawMatrix, list[str]]:
    files = {"B cell": "B_Cells", "CD8 T": "Cytotoxic_T_Cells", "CD4 T": "Helper_T_Cells", "macrophage": "Macrophages",
             "plasma": "Plasma_Cells", "tumour": "Tumor_Cells"}
    frames = {k: pd.read_csv(DEV / "Zheng2025_PXD057118" / f"Tonsil_Cancer_pg_matrix_{v}.txt", sep="\t", na_values=["NA"]).set_index("Protein")
              for k, v in files.items()}
    joined = pd.concat(frames.values(), axis=1, join="outer")
    truth = [k for k, f in frames.items() for _ in f.columns]
    return alignment.RawMatrix(gene_names=joined.index.astype(str).tolist(), cell_ids=joined.columns.astype(str).tolist(),
                               values=joined.to_numpy(np.float32)), truth


def coscia() -> tuple[alignment.RawMatrix, list[str]]:
    raw = alignment.parse_matrix_csv((data.WORK / "lymph_node" / "dev" / "coscia2024_fig3_pg_matrix.tsv").read_text(encoding="utf-8"))
    region = ["B" if "_B" in c.split("_S1")[0][-3:] else "T" if "_T" in c.split("_S1")[0][-3:]
              else "epithelium" if "epi" in c else "other" for c in raw.cell_ids]
    return raw, region


def bpd() -> tuple[alignment.RawMatrix, list[str]]:
    raw = lung_development.read_fragpipe_lfq(DEV / "LungMAP2025_BPD_MSV000094373" / "combined_protein.tsv")
    truth = [("control " if "_C_" in s else "BPD ") + ("epithelial" if "_Epi_" in s else "endothelial" if "_Endo_" in s else "other")
             for s in raw.cell_ids]
    return raw, truth


def zheng_colon() -> tuple[alignment.RawMatrix, list[str]]:
    files = {"macrophage": "ColorectalCancer_pg_matrix_Macrophages.txt", "cd8": "Colorectal_Cancer_pg_matrix_Cytotoxic_T_Cells.txt",
             "cd4": "Colorectal_Cancer_pg_matrix_Helper_T_Cells.txt"}
    tables = {k: heldout_formats.read_dia_nn(DEV / "Zheng2025_PXD057118" / f) for k, f in files.items()}
    first = tables["macrophage"]
    raw = alignment.RawMatrix(gene_names=list(first.genes), cell_ids=[s for t in tables.values() for s in t.samples],
                              values=np.hstack([t.values for t in tables.values()]))
    return raw, [k for k, t in tables.items() for _ in t.samples]


CASES = {"lymph_node": {"zheng_tonsil": (zheng_tonsil, "plasma cell"), "coscia": (coscia, "plasma cell")},
         "lung": {"bpd": (bpd, "macrophage")},
         "large_intestine": {"zheng_colon": (zheng_colon, "mast cell")}}


def paths(b, raw: alignment.RawMatrix) -> dict:
    """Each path's argmax class per pool."""
    smoothed, aligned, _ = pipeline._prepare_query(b.feature_genes, raw)
    names = b.class_names
    Z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in b.answers.members]
    P = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature) for z, m in zip(Z, b.answers.members)])
    r = fusion.masked_pearson(aligned.values, aligned.mask, b.class_means)
    counted = aligned.per_cell_observed_genes >= 200
    bg = fusion.best_guess_probabilities(b, Z, aligned.values, aligned.mask, P, counted)
    return {"encoder": [names[i] for i in P.argmax(1)], "correlation": [names[i] for i in r.argmax(1)],
            "fused": [names[i] for i in bg.probabilities.argmax(1)], "agreement": round(float(bg.agreement), 4),
            "correlation_used": bool(bg.correlation_used), "observed": aligned.per_cell_observed_genes.tolist()}


def subset_rows(raw: alignment.RawMatrix, keep: np.ndarray) -> alignment.RawMatrix:
    return alignment.RawMatrix(gene_names=[g for g, k in zip(raw.gene_names, keep) if k], cell_ids=raw.cell_ids, values=np.asarray(raw.values)[keep])


def subset_cols(raw: alignment.RawMatrix, cols: np.ndarray) -> alignment.RawMatrix:
    return alignment.RawMatrix(gene_names=raw.gene_names, cell_ids=[raw.cell_ids[i] for i in cols], values=np.asarray(raw.values)[:, cols])


def share(called: list[str], sink: str) -> float:
    return round(100 * float(np.mean([c == sink for c in called])), 2)


def probe(b, raw, truth, sink) -> dict:
    names = b.class_names
    symbols = [s.upper() if s else None for s in gene_ids.resolve_identifiers(raw.gene_names).resolved]
    detected = np.isfinite(np.asarray(raw.values, np.float64)).any(1)
    space = {g.upper() for g in b.feature_genes}
    out = {"pools": len(truth), "base": paths(b, raw)}
    out["base_sink_share"] = {k: share(out["base"][k], sink) for k in ("encoder", "correlation", "fused")}
    # 2. the sink class's own markers
    k = names.index(sink)
    others = np.delete(b.class_means, k, axis=0).max(0)
    specificity = b.class_means[k] - others
    order = [b.feature_genes[i].upper() for i in np.argsort(-specificity)]
    out["markers"] = {}
    for top in TOPS:
        markers = set(order[:top])
        drop = np.array([s in markers for s in symbols])
        res = paths(b, subset_rows(raw, ~drop))
        n = int((drop & detected).sum())
        rand = []
        for d in range(DRAWS):
            pool = np.flatnonzero(detected & ~drop & np.array([s in space for s in symbols]))
            rng = np.random.default_rng([SEED, top, d])
            rm = np.zeros(len(symbols), bool)
            rm[rng.choice(pool, size=min(n, len(pool)), replace=False)] = True
            rand.append(share(paths(b, subset_rows(raw, ~rm))["fused"], sink))
        out["markers"][top] = {"removed": n, "fused_sink_share": share(res["fused"], sink),
                               "encoder_sink_share": share(res["encoder"], sink), "random_fused_sink_share": rand,
                               "first_markers": order[:10] if top == TOPS[0] else None}
    # 3. depth: keep a random share of each pool's observed proteins
    out["depth"] = {}
    V = np.asarray(raw.values, np.float32)
    for frac in DEPTHS:
        shares = []
        for d in range(DRAWS):
            rng = np.random.default_rng([SEED, int(frac * 100), d])
            W = V.copy()
            for j in range(W.shape[1]):
                obs = np.flatnonzero(np.isfinite(W[:, j]))
                drop = rng.choice(obs, size=int(round(len(obs) * (1 - frac))), replace=False)
                W[drop, j] = np.nan
            shares.append(share(paths(b, alignment.RawMatrix(gene_names=raw.gene_names, cell_ids=raw.cell_ids, values=W))["fused"], sink))
        out["depth"][frac] = shares
    # 4. company: each population alone
    out["company"] = {}
    t = np.array(truth)
    for pop in sorted(set(truth)):
        cols = np.flatnonzero(t == pop)
        if len(cols) < 2:
            continue
        res = paths(b, subset_cols(raw, cols))
        out["company"][pop] = {"pools": len(cols), "fused_sink_share": share(res["fused"], sink),
                               "fused": pd.Series(res["fused"]).value_counts().head(3).to_dict()}
    out["by_population_base"] = {pop: pd.Series(np.array(out["base"]["fused"])[t == pop]).value_counts().head(3).to_dict()
                                 for pop in sorted(set(truth))}
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    data.save_json(OUT / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "seed": SEED, "tops": TOPS, "depths": DEPTHS, "draws": DRAWS,
                                        "cases": {o: {k: v[1] for k, v in c.items()} for o, c in CASES.items()}})
    t0 = time.time()
    result = {}
    for organ, cases in CASES.items():
        bundle_dir = data.WORK / organ / "bundle"
        b = bundle.load(bundle_dir)
        result[organ] = {}
        with bundle.gene_map(bundle_dir):
            for name, (reader, sink) in cases.items():
                raw, truth = reader()
                result[organ][name] = {"sink": sink, **probe(b, raw, truth, sink)}
                print(f"{organ} {name}: base {result[organ][name]['base_sink_share']} ({time.time() - t0:.0f}s)", flush=True)
        data.save_json(OUT / "probes.json", result)
    print(json.dumps({o: {n: {"base": r["base_sink_share"], "markers": {k: v["fused_sink_share"] for k, v in r["markers"].items()},
                              "depth": r["depth"], "company": {k: v["fused_sink_share"] for k, v in r["company"].items()}}
                          for n, r in c.items()} for o, c in result.items()}, indent=1))


if __name__ == "__main__":
    main()
