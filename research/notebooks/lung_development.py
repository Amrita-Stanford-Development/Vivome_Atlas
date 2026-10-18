"""Track I (research/organ-references.md, "Lung"): the lung reference's
development checks, gates G1 and G3, scored once.

The gates were fixed in research/organ-references.md before any lung model
existed: G1 is the colon's, G3 uses the lung's development data. The script
records its own sha256, the gates and the start time in rules.json before
computing anything. No setting is tuned to pass a gate; a miss goes to the
owner.

G1 runs the lung's evaluation suite (240 uploads from the test split) through
the service's code on references without test cells, exactly as the colon's
did (research/notebooks/li_development.py, whose helpers it reuses). Cells
with at least 200 observed genes. Pass when all hold:
- correct when committed ≥ 90%;
- committed ≥ 75%;
- coverage ≥ 85%;
- false abstention ≤ 2%.

G3, through the served form of the bundle, every upload resolved with the
lung's own gene map:
- MSV000094373 (LungMAP BPD and control), sorted pools: FragPipe's
  combined_protein.tsv, MaxLFQ intensities, one upload of all 20 pools. AUROC
  ≥ 0.8 of P(epithelial lineage), epithelial pools ("Epi") over endothelial
  ("Endo").
- The Human Protein Atlas DVP samples: dvp_sample_data.tsv, every pool of
  every tissue as one upload, so the upload is mixed. AUROC ≥ 0.8 of
  P(type II pneumocyte) - P(type I pneumocyte), the AT2 pools over the AT1
  pools. The other cell types' lineages are reported.
- PXD029341 (Herrera 2022), laser-microdissected regions: MaxQuant
  proteinGroups.txt by benchmark/heldout_formats.read_maxquant, every region
  as one upload. AUROC ≥ 0.7 of P(stromal lineage), fibroblastic foci ("FF")
  over alveoli ("NmlAlv", "NmAlv").

Writes research/notebook-outputs/lung_development/: rules.json, g1.json,
g1_cells.csv.gz, g3.json and gates.json.

    python research/notebooks/lung_development.py      # from the repository root (GPU)
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
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import li_development as li  # noqa: E402  (fused, covered, cell_rows, summary, held_out, run_upload, group_sums)
from organ_reference import bundle, calibrate, data  # noqa: E402
from organ_reference import sim_generator as sg  # noqa: E402

from benchmark import heldout_formats  # noqa: E402
from service.pipeline import alignment, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "lung_development"
ORGAN = "lung"
GATES = {"g1_correct_when_committed_min": 90.0, "g1_committed_min": 75.0, "g1_coverage_min": 85.0,
         "g1_false_abstention_max": 2.0, "g3_bpd_auroc_min": 0.8, "g3_hpa_at2_auroc_min": 0.8, "g3_ipf_auroc_min": 0.7}
DEV = REPO / "data" / "incoming" / "public_sets"
AT1, AT2 = "type i pneumocyte", "type ii pneumocyte"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def g1(b_full, build_dir: Path, cfg: dict, t0: float) -> dict:
    """li_development.g1 with this organ's folders."""
    names, hierarchy = b_full.class_names, b_full.hierarchy
    table = pd.read_csv(build_dir / "labels.csv.gz", keep_default_na=False)
    y = table["class_idx"].to_numpy()
    X = data.load_rna(data.resolve(cfg["rna"]), b_full.feature_genes)[table["row"].to_numpy()]
    split = np.load(build_dir / "splits_seed0.npz")
    trainval = np.sort(np.concatenate([split["train"], split["val"]]))
    paths = {m.name: build_dir / "bundle" / "members" / m.name for m in b_full.members}
    b = li.held_out(b_full, X, y, trainval, paths, len(names))
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
        rows += li.cell_rows(response, [names[k] for k in truth_pos], li.covered(b, smoothed, aligned, truth_pos),
                             hierarchy, spec["id"], spec["scenario"])
        if (u + 1) % 40 == 0:
            print(f"G1: {u + 1}/{len(suite)} uploads ({time.time() - t0:.0f}s)", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "g1_cells.csv.gz", index=False, lineterminator="\n")
    return {"overall": li.summary(d), "by_scenario": {k: li.summary(v) for k, v in d.groupby("scenario")},
            "per_class_recall_committed": {c: round(100 * float(v["correct"].mean()), 2) for c, v in d.groupby("true")}}


def read_fragpipe_lfq(path: Path) -> alignment.RawMatrix:
    """FragPipe's combined_protein.tsv: its "Gene" column and each sample's MaxLFQ intensity, 0 as missing."""
    t = pd.read_csv(path, sep="\t", low_memory=False)
    cols = [c for c in t.columns if c.endswith(" MaxLFQ Intensity")]
    v = t[cols].apply(pd.to_numeric, errors="coerce").to_numpy(np.float32)
    v[v <= 0] = np.nan
    genes = t["Gene"].fillna("").astype(str)
    keep = (genes != "").to_numpy()
    return alignment.RawMatrix(gene_names=genes[keep].tolist(), cell_ids=[c[: -len(" MaxLFQ Intensity")] for c in cols],
                               values=v[keep])


def answers(response, truth) -> list[dict]:
    return [{"truth": t, "label": c["label"], "level": c["label_level"], "abstained": c["abstained"],
             "best_guess": c.get("best_guess", {}).get("label")} for t, c in zip(truth, response["cells"])]


def g3(b) -> dict:
    names, hierarchy = b.class_names, b.hierarchy
    out = {}
    # LungMAP BPD and control: sorted epithelial and endothelial pools
    raw = read_fragpipe_lfq(DEV / "LungMAP2025_BPD_MSV000094373" / "combined_protein.tsv")
    truth = ["epithelial" if "_Epi_" in s else "endothelial" if "_Endo_" in s else "other" for s in raw.cell_ids]
    response, G, _ = li.run_upload(b, raw)
    lin = li.group_sums(G, names, hierarchy, "lineage")
    epi = np.array([t == "epithelial" for t in truth])
    out["bpd"] = {"pools": len(truth), "by_population": pd.Series(truth).value_counts().to_dict(),
                  "auroc_epithelial": round(float(roc_auc_score(epi, lin["epithelial"].to_numpy())), 4),
                  "argmax_lineage": pd.crosstab(pd.Series(truth, name="truth"), pd.Series(lin.idxmax(1).to_numpy(), name="called")).to_dict(),
                  "answers": answers(response, truth)}
    # the Human Protein Atlas DVP pools, every tissue in one upload
    d = pd.read_csv(zipfile.ZipFile(DEV / "HPA2026_DVP" / "dvp_sample_data.tsv.zip").open("dvp_sample_data.tsv"), sep="\t")
    wide = d.pivot_table(index="Gene name", columns="Sample name", values="Intensity", aggfunc="first")
    cell_type = d.drop_duplicates("Sample name").set_index("Sample name")["Cell type"]
    raw = alignment.RawMatrix(gene_names=wide.index.astype(str).tolist(), cell_ids=wide.columns.astype(str).tolist(),
                              values=wide.to_numpy(np.float32))
    truth = [cell_type[s] for s in raw.cell_ids]
    response, G, _ = li.run_upload(b, raw)
    lin = li.group_sums(G, names, hierarchy, "lineage")
    at = np.array([t in ("alveolar cells type 1", "alveolar cells type 2") for t in truth])
    is2 = np.array([t == "alveolar cells type 2" for t in truth])[at]
    s = (G[:, names.index(AT2)] - G[:, names.index(AT1)])[at]
    called = pd.DataFrame({"cell_type": truth, "lineage": lin.idxmax(1).to_numpy(),
                           "best_guess": [c.get("best_guess", {}).get("label") for c in response["cells"]]})
    out["hpa"] = {"pools": len(truth), "auroc_at2_over_at1": round(float(roc_auc_score(is2, s)), 4),
                  "at_pools_lineage": called[at]["lineage"].value_counts().to_dict(),
                  "by_cell_type": {k: {"lineage": v["lineage"].value_counts().to_dict(), "best_guess": v["best_guess"].value_counts().head(3).to_dict()}
                                   for k, v in called.groupby("cell_type")}}
    # Herrera 2022: laser-microdissected IPF and control regions
    target = data.WORK / ORGAN / "dev" / "herrera_proteinGroups.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(zipfile.ZipFile(DEV / "Herrera2022_PXD029341" / "results.zip").read("txt/proteinGroups.txt"))
    tab = heldout_formats.read_maxquant(target)
    raw = tab.raw()
    region = ["fibroblastic focus" if "_FF_" in c else "mature scar" if "MtrScr" in c
              else "alveoli" if ("NmlAlv" in c or "NmAlv" in c) else "other" for c in raw.cell_ids]
    response, G, _ = li.run_upload(b, raw)
    lin = li.group_sums(G, names, hierarchy, "lineage")
    keep = np.array([r in ("fibroblastic focus", "alveoli") for r in region])
    ff = np.array([r == "fibroblastic focus" for r in region])[keep]
    out["ipf"] = {"regions": len(region), "by_region": pd.Series(region).value_counts().to_dict(), "reader": tab.record,
                  "auroc_stromal_ff_over_alveoli": round(float(roc_auc_score(ff, lin["stromal"].to_numpy()[keep])), 4),
                  "mean_p_lineage_by_region": {r: lin[np.array(region) == r].mean().round(4).to_dict() for r in set(region)},
                  "answers": answers(response, region)}
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
    with bundle.gene_map(build_dir / "bundle"):
        r1 = g1(b, build_dir, cfg, t0)
        data.save_json(OUT / "g1.json", r1)
        print(json.dumps(r1["overall"], indent=1), flush=True)
        r3 = g3(b)
    data.save_json(OUT / "g3.json", r3)
    o = r1["overall"]
    gates = {
        "G1 correct when committed": (o["correct_when_committed"], o["correct_when_committed"] >= GATES["g1_correct_when_committed_min"]),
        "G1 committed": (o["committed"], o["committed"] >= GATES["g1_committed_min"]),
        "G1 coverage": (o["coverage"], o["coverage"] >= GATES["g1_coverage_min"]),
        "G1 false abstention": (o["false_abstention"], o["false_abstention"] <= GATES["g1_false_abstention_max"]),
        "G3 LungMAP BPD AUROC": (r3["bpd"]["auroc_epithelial"], r3["bpd"]["auroc_epithelial"] >= GATES["g3_bpd_auroc_min"]),
        "G3 HPA AT2 over AT1 AUROC": (r3["hpa"]["auroc_at2_over_at1"], r3["hpa"]["auroc_at2_over_at1"] >= GATES["g3_hpa_at2_auroc_min"]),
        "G3 IPF fibroblastic foci AUROC": (r3["ipf"]["auroc_stromal_ff_over_alveoli"],
                                           r3["ipf"]["auroc_stromal_ff_over_alveoli"] >= GATES["g3_ipf_auroc_min"]),
    }
    data.save_json(OUT / "gates.json", {"finished": datetime.now().isoformat(timespec="seconds"),
                                         "gates": {k: {"value": v, "pass": bool(p)} for k, (v, p) in gates.items()},
                                         "all_pass": all(p for _, p in gates.values()), "seconds": round(time.time() - t0)})
    for k, (v, p) in gates.items():
        print(f"{'PASS' if p else 'MISS'}  {k}: {v}")


if __name__ == "__main__":
    main()
