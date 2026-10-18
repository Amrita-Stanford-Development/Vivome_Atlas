"""Track I (research/organ-references.md, "Lymph node"): the lymph node
reference's development checks, gates G1 and G3, scored once.

The gates were fixed in research/organ-references.md before any lymph node
model existed, with the dated note on the deposits' layouts. G1 is the
colon's and the lung's. The script records its own sha256, the gates and the
start time in rules.json before computing anything. Nothing is tuned to pass
a gate; a miss goes to the owner.

G1: the organ's evaluation suite through the service's code on references
without test cells (research/notebooks/lung_development.py's g1, written
here for this organ's folders). Pass when committed ≥ 75%, correct when
committed ≥ 90%, coverage ≥ 85% and false abstention ≤ 2%.

G3, through the served bundle, resolved with the lymph node's gene map:
- PXD047762, its Fig. 3 tonsil regions, one upload: AUROC ≥ 0.8 of
  P(B cell group) - P(T cell group), the 5 B-cell regions over the 5 T-cell
  regions. The epithelium regions are uploaded too, and reported.
- Zheng's six tonsil tables (PXD057118) as one upload: at least 80% of the B,
  plasma, CD8 T, CD4 T and macrophage pools with their group as the argmax.
  B and plasma count as B cell, CD8 T and CD4 T as T cell, macrophage as
  monocyte/macrophage. Tumour pools are uploaded, not scored.
- The Protein Atlas DVP samples, all in one upload: at least 80% of the
  lymph-node macrophage, CD4 T, CD8 T and B-cell pools with their group as
  the argmax.
- PXD011683, all 45 CD19+ samples: at least 80% with B cell as the argmax
  group.

Writes research/notebook-outputs/lymph_node_development/: rules.json,
g1.json, g1_cells.csv.gz, g3.json and gates.json.

    python research/notebooks/lymph_node_development.py      # from the repository root (GPU)
"""
from __future__ import annotations

import glob
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

OUT = REPO / "research" / "notebook-outputs" / "lymph_node_development"
ORGAN = "lymph_node"
GATES = {"g1_correct_when_committed_min": 90.0, "g1_committed_min": 75.0, "g1_coverage_min": 85.0,
         "g1_false_abstention_max": 2.0, "g3_coscia_auroc_min": 0.8, "g3_zheng_group_accuracy_min": 80.0,
         "g3_hpa_group_accuracy_min": 80.0, "g3_b_share_min": 80.0}
DEV = REPO / "data" / "incoming" / "public_sets"
WORK_DEV = data.WORK / ORGAN / "dev"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def g1(b_full, build_dir: Path, cfg: dict, t0: float) -> dict:
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


def answers(response, truth) -> list[dict]:
    return [{"truth": t, "label": c["label"], "level": c["label_level"], "abstained": c["abstained"],
             "best_guess": c.get("best_guess", {}).get("label")} for t, c in zip(truth, response["cells"])]


def group_accuracy(G, names, hierarchy, truth, want) -> tuple[float, dict]:
    grp = li.group_sums(G, names, hierarchy, "group")
    called = grp.idxmax(1).to_numpy()
    scored = np.array([t in want for t in truth])
    right = np.array([want.get(t) == c for t, c in zip(truth, called)])
    table = pd.crosstab(pd.Series(truth, name="truth"), pd.Series(called, name="called")).to_dict()
    return round(100 * float(right[scored].mean()), 2), table


def g3(b) -> dict:
    names, hierarchy = b.class_names, b.hierarchy
    out = {}
    # PXD047762, the Fig. 3 tonsil regions
    raw = alignment.parse_matrix_csv((WORK_DEV / "coscia2024_fig3_pg_matrix.tsv").read_text(encoding="utf-8"))
    region = ["B" if "_B" in c.split("_S1")[0][-3:] else "T" if "_T" in c.split("_S1")[0][-3:]
              else "epithelium" if "epi" in c else "other" for c in raw.cell_ids]
    response, G, _ = li.run_upload(b, raw)
    grp = li.group_sums(G, names, hierarchy, "group")
    bt = np.array([r in ("B", "T") for r in region])
    s = (grp["B cell"] - grp["T cell"]).to_numpy()
    out["coscia2024"] = {"regions": len(region), "by_region": pd.Series(region).value_counts().to_dict(),
                         "auroc_b_over_t": round(float(roc_auc_score(np.array(region)[bt] == "B", s[bt])), 4),
                         "argmax_group": pd.crosstab(pd.Series(region, name="region"), pd.Series(grp.idxmax(1).to_numpy(), name="called")).to_dict(),
                         "answers": answers(response, region)}
    # Zheng's tonsil tables, one upload
    files = {"B cell": "B_Cells", "CD8 T": "Cytotoxic_T_Cells", "CD4 T": "Helper_T_Cells", "macrophage": "Macrophages",
             "plasma": "Plasma_Cells", "tumour": "Tumor_Cells"}
    frames = {k: pd.read_csv(DEV / "Zheng2025_PXD057118" / f"Tonsil_Cancer_pg_matrix_{v}.txt", sep="\t", na_values=["NA"]).set_index("Protein")
              for k, v in files.items()}
    joined = pd.concat(frames.values(), axis=1, join="outer")
    truth = [k for k, f in frames.items() for _ in f.columns]
    raw = alignment.RawMatrix(gene_names=joined.index.astype(str).tolist(), cell_ids=joined.columns.astype(str).tolist(),
                              values=joined.to_numpy(np.float32))
    response, G, _ = li.run_upload(b, raw)
    want = {"B cell": "B cell", "plasma": "B cell", "CD8 T": "T cell", "CD4 T": "T cell", "macrophage": "monocyte/macrophage"}
    acc, table = group_accuracy(G, names, hierarchy, truth, want)
    out["zheng_tonsil"] = {"pools": len(truth), "by_population": pd.Series(truth).value_counts().to_dict(),
                           "group_accuracy": acc, "called_groups": table, "answers": answers(response, truth)}
    # the Protein Atlas DVP samples, all in one upload
    d = pd.read_csv(zipfile.ZipFile(DEV / "HPA2026_DVP" / "dvp_sample_data.tsv.zip").open("dvp_sample_data.tsv"), sep="\t")
    wide = d.pivot_table(index="Gene name", columns="Sample name", values="Intensity", aggfunc="first")
    cell_type = d.drop_duplicates("Sample name").set_index("Sample name")["Cell type"]
    raw = alignment.RawMatrix(gene_names=wide.index.astype(str).tolist(), cell_ids=wide.columns.astype(str).tolist(),
                              values=wide.to_numpy(np.float32))
    truth = [cell_type[s_] for s_ in raw.cell_ids]
    response, G, _ = li.run_upload(b, raw)
    want = {"macrophages": "monocyte/macrophage", "cd4 t-cells": "T cell", "cd8 t-cells": "T cell", "b-cells": "B cell"}
    acc, table = group_accuracy(G, names, hierarchy, truth, want)
    out["hpa"] = {"pools": len(truth), "group_accuracy_lymph_node_pools": acc,
                  "called_groups": {k: v for k, v in table.items()}}
    # PXD011683: CD19+ B-cell samples
    tab = heldout_formats.read_maxquant(WORK_DEV / "proteinGroups.txt")
    raw = tab.raw()
    response, G, _ = li.run_upload(b, raw)
    grp = li.group_sums(G, names, hierarchy, "group")
    called = grp.idxmax(1).to_numpy()
    out["pxd011683"] = {"samples": len(called), "reader": tab.record,
                        "b_share": round(100 * float((called == "B cell").mean()), 2),
                        "called_by_sample_group": pd.crosstab(pd.Series([c[0] for c in raw.cell_ids], name="group"),
                                                              pd.Series(called, name="called")).to_dict()}
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
        "G3 Coscia B over T AUROC": (r3["coscia2024"]["auroc_b_over_t"], r3["coscia2024"]["auroc_b_over_t"] >= GATES["g3_coscia_auroc_min"]),
        "G3 Zheng tonsil group accuracy": (r3["zheng_tonsil"]["group_accuracy"],
                                           r3["zheng_tonsil"]["group_accuracy"] >= GATES["g3_zheng_group_accuracy_min"]),
        "G3 HPA lymph-node pools group accuracy": (r3["hpa"]["group_accuracy_lymph_node_pools"],
                                                   r3["hpa"]["group_accuracy_lymph_node_pools"] >= GATES["g3_hpa_group_accuracy_min"]),
        "G3 PXD011683 B share": (r3["pxd011683"]["b_share"], r3["pxd011683"]["b_share"] >= GATES["g3_b_share_min"]),
    }
    data.save_json(OUT / "gates.json", {"finished": datetime.now().isoformat(timespec="seconds"),
                                         "gates": {k: {"value": v, "pass": bool(p)} for k, (v, p) in gates.items()},
                                         "all_pass": all(p for _, p in gates.values()), "seconds": round(time.time() - t0)})
    for k, (v, p) in gates.items():
        print(f"{'PASS' if p else 'MISS'}  {k}: {v}")


if __name__ == "__main__":
    main()
