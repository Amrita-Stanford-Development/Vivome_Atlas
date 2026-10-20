"""Organ references v2: an organ's gates G1 and G3, scored once
(research/organ-references.md, "Version 2"; side-tests.md, amendments 13
and 14).

**G1, split** (the owner's decision of 2026-10-18, fixed before any v2
model). The v2 evaluation suite runs through the service's code, on the
bundle with references from the training and validation cells only
(li_development.held_out).
- An upload is mixed when its classes number at least 3 and span at least
  2 lineages, or when it is a whole tissue; every other upload is narrow.
- Mixed uploads must meet G1's four bars: committed ≥ 75, correct when
  committed ≥ 90, coverage ≥ 85, false abstention ≤ 2.
- Narrow uploads must be safe: correct when committed ≥ 90.
- G1 as v1 wrote it (every upload together) is reported, never gated.

**G3, on the fresh development sets** (amendment 13), through the served
bundle, resolved with the organ's identifier map:
- lung_v2, PXD058626: every run's FragPipe "Intensity" in one upload.
  AUROC ≥ 0.8 of P(airway epithelial group) − P(alveolar epithelial group),
  the non-fibrotic control airways over the non-fibrotic control alveoli.
  The IPF regions are uploaded and reported.
- lymph_node_v2, PXD045043: AUROC ≥ 0.8 of P(B cell group), white pulp over
  red pulp, over the single labelled DIA voxels. Its reader is fixed by the
  dated note on the deposit's layout (research/organ-references.md,
  "Version 2"), before the gate run.
- The organ's seen sets (its v1 g3) are run and reported as diagnostics,
  never gates.

**Refusals.** The script refuses a suite or bundle whose sha256 differs from
the registry (research/notebook-outputs/organ_v2_registry.json), and a
second run (gates.json exists).

Writes research/notebook-outputs/<organ>_development/: rules.json (first),
g1.json, g1_cells.csv.gz, g3.json, seen.json, gates.json.

    python research/notebooks/organ_v2_gates.py lymph_node_v2      # from the repository root (GPU)
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
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import li_development as li  # noqa: E402
import lung_development  # noqa: E402
import lymph_node_development  # noqa: E402
from organ_reference import bundle, calibrate, data  # noqa: E402
from organ_reference import sim_generator as sg  # noqa: E402

from service.pipeline import alignment, fusion, gene_ids, pipeline  # noqa: E402

REGISTRY = REPO / "research" / "notebook-outputs" / "organ_v2_registry.json"
DEV = REPO / "data" / "incoming" / "public_sets"
GATES = {"mixed_committed_min": 75.0, "mixed_correct_when_committed_min": 90.0, "mixed_coverage_min": 85.0,
         "mixed_false_abstention_max": 2.0, "narrow_correct_when_committed_min": 90.0, "g3_auroc_min": 0.8}
SEEN = {"lymph_node_v2": lymph_node_development, "lung_v2": lung_development}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mixed(spec: dict, hierarchy: dict) -> bool:
    lineages = {hierarchy[c]["lineage"] for c in spec["classes"]}
    return (len(spec["classes"]) >= 3 and len(lineages) >= 2) or spec["scenario"] == "tissue"


def g1(b_full, build_dir: Path, cfg: dict, out: Path, t0: float) -> dict:
    names, hierarchy = b_full.class_names, b_full.hierarchy
    table = pd.read_csv(build_dir / "labels.csv.gz", keep_default_na=False)
    y = table["class_idx"].to_numpy()
    X = data.load_rna(data.resolve(cfg["rna"]), b_full.feature_genes)[table["row"].to_numpy()]
    split = np.load(build_dir / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    paths = {m.name: build_dir / "bundle" / "members" / m.name for m in b_full.members}
    b = li.held_out(b_full, X, y, trainval, paths, len(names))
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
        cells = li.cell_rows(response, [names[k] for k in truth_pos], li.covered(b, smoothed, aligned, truth_pos),
                             hierarchy, spec["id"], spec["scenario"])
        band = "mixed" if mixed(spec, hierarchy) else "narrow"
        rows += [{**r, "band": band} for r in cells]
        if (u + 1) % 40 == 0:
            print(f"G1: {u + 1}/{len(suite)} uploads ({time.time() - t0:.0f}s)", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(out / "g1_cells.csv.gz", index=False, lineterminator="\n")
    return {"mixed": li.summary(d[d["band"] == "mixed"]), "narrow": li.summary(d[d["band"] == "narrow"]),
            "as_written_v1": li.summary(d), "by_scenario": {k: li.summary(v) for k, v in d.groupby("scenario")},
            "per_class_recall_committed": {c: round(100 * float(v["correct"].mean()), 2) for c, v in d.groupby("true")}}


def read_fragpipe_intensity(path: Path) -> alignment.RawMatrix:
    """FragPipe's combined_protein.tsv: its "Gene" column and each sample's
    "Intensity" (PXD058626 has no MaxLFQ columns), 0 as missing. FragPipe's
    contaminant and decoy rows (contam_, rev_) are left out, as the service
    leaves them out. The lung v2's gate run (2026-10-20) read them; without
    them its G3 is unchanged (organ_v2_lung_g3_contaminants.py)."""
    t = pd.read_csv(path, sep="\t", low_memory=False)
    t = t[~t["Protein"].astype(str).str.startswith(("contam_", "rev_"))]
    cols = [c for c in t.columns if c.endswith(" Intensity") and not c.endswith("MaxLFQ Intensity")]
    v = t[cols].apply(pd.to_numeric, errors="coerce").to_numpy(np.float32)
    v[v <= 0] = np.nan
    genes = t["Gene"].fillna("").astype(str)
    keep = (genes != "").to_numpy()
    return alignment.RawMatrix(gene_names=genes[keep].tolist(), cell_ids=[c[: -len(" Intensity")] for c in cols], values=v[keep])


def herrera_region(sample: str) -> str:
    if sample.startswith("NonFibroticControlAirway"):
        return "control airway"
    if sample.startswith("Non_fibrotic_Control_Alveoli"):
        return "control alveoli"
    return "IPF " + sample.rsplit("_", 1)[0].removeprefix("IPF").strip("_").replace("_", " ")


def g3_lung(b) -> dict:
    raw = read_fragpipe_intensity(DEV / "Herrera2025_PXD058626" / "combined_protein.tsv")
    region = [herrera_region(s) for s in raw.cell_ids]
    response, G, _ = li.run_upload(b, raw)
    grp = li.group_sums(G, b.class_names, b.hierarchy, "group")
    s = (grp["airway epithelial"] - grp["alveolar epithelial"]).to_numpy()
    keep = np.isin(region, ["control airway", "control alveoli"])
    auc = roc_auc_score(np.array(region)[keep] == "control airway", s[keep])
    lin = li.group_sums(G, b.class_names, b.hierarchy, "lineage")
    return {"set": "PXD058626", "runs": len(region), "by_region": pd.Series(region).value_counts().to_dict(),
            "auroc": round(float(auc), 4), "score": "P(airway epithelial) - P(alveolar epithelial)",
            "mean_score_by_region": pd.Series(s).groupby(np.array(region)).mean().round(4).to_dict(),
            "argmax_lineage": pd.crosstab(pd.Series(region, name="region"), pd.Series(lin.idxmax(1).to_numpy(), name="called")).to_dict(),
            "answers": lung_development.answers(response, region)}


SPLEEN = "Report_DIA-NN_Spleen/ALL_noCarbamy.pg_matrix.tsv"


def spleen_matrix() -> Path:
    """PXD045043's DIA-NN protein groups (the final pass), taken out of the archive once."""
    import zipfile
    target = data.WORK / "lymph_node_v2" / "dev" / "spleen_ALL_noCarbamy.pg_matrix.tsv"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zipfile.ZipFile(DEV / "Kitata2025_PXD045043" / "Report_DIA-NN_Spleen.zip").read(SPLEEN))
    return target


def spleen_region(run: str) -> tuple[str, int]:
    """(red pulp | white pulp, voxel size in µm) from a run name such as wSOP_Spleen_200umDIA_Wh_R2_..."""
    import re
    m = re.search(r"Spleen_(\d+)umDIA_(Red|Wh)_", run)
    if not m:
        raise SystemExit(f"{run}: not a labelled voxel")
    return ("white pulp" if m.group(2) == "Wh" else "red pulp"), int(m.group(1))


def g3_lymph_node(b) -> dict:
    from benchmark import heldout_formats
    table = heldout_formats.read_dia_nn(spleen_matrix())
    raw = table.raw()
    labels = [spleen_region(r) for r in raw.cell_ids]
    region = [r for r, _ in labels]
    size = np.array([s for _, s in labels])
    response, G, _ = li.run_upload(b, raw)
    grp = li.group_sums(G, b.class_names, b.hierarchy, "group")
    s = grp["B cell"].to_numpy()
    white = np.array(region) == "white pulp"
    return {"set": "PXD045043", "voxels": len(region), "by_region": pd.Series(region).value_counts().to_dict(),
            "auroc": round(float(roc_auc_score(white, s)), 4), "score": "P(B cell group)",
            "auroc_by_size": {int(k): round(float(roc_auc_score(white[size == k], s[size == k])), 4) for k in sorted(set(size))
                              if 0 < white[size == k].sum() < (size == k).sum()},
            "mean_score_by_region": pd.Series(s).groupby(np.array(region)).mean().round(4).to_dict(),
            "argmax_group": pd.crosstab(pd.Series(region, name="region"), pd.Series(grp.idxmax(1).to_numpy(), name="called")).to_dict(),
            "answers": lymph_node_development.answers(response, region)}


G3 = {"lung_v2": g3_lung, "lymph_node_v2": g3_lymph_node}


def main() -> None:
    warnings.simplefilter("ignore")
    organ = sys.argv[1]
    if organ not in G3:
        raise SystemExit(f"no v2 gates for {organ}")
    build_dir = data.WORK / organ
    out = REPO / "research" / "notebook-outputs" / f"{organ}_development"
    # Any gate output means a run started: a crash after G1 must not allow a second run.
    if any((out / name).exists() for name in ("gates.json", "g1.json", "g3.json")):
        raise SystemExit(f"{organ}'s v2 gates were run; they are scored once")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))[organ]
    for path, key in ((build_dir / "sim_suite_eval_v1.json", "eval_suite_sha256"),
                      (build_dir / "sim_suite_calib_v1.json", "calib_suite_sha256"),
                      (build_dir / "bundle" / "MANIFEST.json", "bundle_manifest_sha256"),
                      (data.ORGANS / f"{organ}.json", "organ_file_sha256")):
        if sha256(path) != registry.get(key):
            raise SystemExit(f"{path} is not the registered one ({key})")
    out.mkdir(parents=True, exist_ok=True)
    cfg = data.load_organ(organ)
    data.save_json(out / "rules.json", {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
                                        "gates": GATES, "registry": registry, "organ_file_sha256": sha256(data.ORGANS / f"{organ}.json")})
    t0 = time.time()
    b = bundle.load(build_dir / "bundle")
    with bundle.gene_map(build_dir / "bundle"):
        r1 = g1(b, build_dir, cfg, out, t0)
        data.save_json(out / "g1.json", r1)
        print(json.dumps({k: r1[k] for k in ("mixed", "narrow", "as_written_v1")}, indent=1), flush=True)
        r3 = G3[organ](b)
        data.save_json(out / "g3.json", r3)
        seen = SEEN[organ].g3(b)
    data.save_json(out / "seen.json", seen)
    m, n = r1["mixed"], r1["narrow"]
    gates = {
        "G1 mixed committed": (m["committed"], m["committed"] >= GATES["mixed_committed_min"]),
        "G1 mixed correct when committed": (m["correct_when_committed"], m["correct_when_committed"] >= GATES["mixed_correct_when_committed_min"]),
        "G1 mixed coverage": (m["coverage"], m["coverage"] >= GATES["mixed_coverage_min"]),
        "G1 mixed false abstention": (m["false_abstention"], m["false_abstention"] <= GATES["mixed_false_abstention_max"]),
        "G1 narrow correct when committed": (n["correct_when_committed"], (n["correct_when_committed"] or 0) >= GATES["narrow_correct_when_committed_min"]),
        f"G3 {r3['set']} AUROC": (r3["auroc"], r3["auroc"] >= GATES["g3_auroc_min"]),
    }
    data.save_json(out / "gates.json", {"finished": datetime.now().isoformat(timespec="seconds"),
                                         "gates": {k: {"value": v, "pass": bool(p)} for k, (v, p) in gates.items()},
                                         "all_pass": all(p for _, p in gates.values()), "seconds": round(time.time() - t0)})
    for k, (v, p) in gates.items():
        print(f"{'PASS' if p else 'MISS'}  {k}: {v}")


if __name__ == "__main__":
    main()
