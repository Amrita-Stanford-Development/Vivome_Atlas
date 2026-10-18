"""The colon reference's locked test, PXD052341 (Post 2025), steps 2 and 3 of
its unsealing (research/benchmark/protocol-colon-pxd052341.md, rule 10): the
label map, then the intake. Written and rehearsed before any file of the set
was opened.

    python -m benchmark.colon_heldout_intake --rehearse     # RNA pseudobulk in the deposit's format, any time
    python -m benchmark.colon_heldout_intake --labels       # unsealing only: the label map, once
    python -m benchmark.colon_heldout_intake --labels --label-map CSV --reason TEXT
                                                            # a map written by hand by the same rules
    python -m benchmark.colon_heldout_intake                # unsealing only: the intake, once

The label map (rules 3 to 5) is read from the deposit's metadata by meaning,
since its layout was not seen before sealing: a row is native human colon when
some field says so (in vivo, tissue, biopsy, resection, mucosa, native) and none
says organoid, in vitro, transplant, xenograft, mouse, blank, QC or library;
its group comes from the words for the five populations; single contours from a
contour-count column, when there is one. Any doubt stops the automatic reading,
and the map is then written by hand by the same rules, with the reason
recorded (rule 10.2).

The intake checks the two input files against the download record and the
frozen candidate against the protocol's candidate amendment, reads the DIA-NN
matrix with the service's own parser, builds one upload of every included
pooled sample, runs the candidate through the served pipeline, recomputes the
fused best-guess probabilities (their argmax must equal the served best
guess) and writes the baselines' query matrix.

Writes benchmark/results/heldout_pxd052341/ (heldout_pxd052341_rehearsal/ when
rehearsing): label_map.csv, labels.json, intake.json, cell_ids.txt,
li_pred.csv, li_probs.npz, query_benchmark.npz.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import datasets
from benchmark import heldout_formats as formats
from benchmark.baselines_v31 import table
from benchmark.heldout_intake import class_probabilities, facts, write_labels
from benchmark.sorted_cd4cd8_intake import benchmark_matrix, sha256
from service.pipeline import alignment, pipeline

REPO = datasets.REPO
sys.path.insert(0, str(REPO / "scripts"))
from organ_reference import bundle as organ_bundle  # noqa: E402
from organ_reference import data as organ_data  # noqa: E402

RESULTS = REPO / "benchmark" / "results"
PUBLIC = REPO / "data" / "incoming" / "public_sets"
DOWNLOADS = REPO / "research" / "benchmark" / "public-sets-downloads.json"
PROTOCOL = REPO / "research" / "benchmark" / "protocol-colon-pxd052341.md"
SET = "pxd052341"
INPUTS = ("Post2025_PXD052341/DVP_data.pg_matrix.tsv", "Post2025_PXD052341/Post_et_al_organoid_DVP_metadata.tsv")
# rule 5: the five groups and the reference classes each sums over
GROUPS = {
    "crypt bottom": ("intestinal crypt stem cell of colon", "transit amplifying cell of colon"),
    "upper crypt": ("enterocyte of epithelium of large intestine", "best4+ intestinal epithelial cell, human"),
    "goblet": ("large intestine goblet cell",),
    "fibroblast": ("fibroblast", "myofibroblast cell"),
    "immune": "lineage:immune",
}
NATIVE = re.compile(r"in[ _-]?vivo|tissue|biops|resection|mucosa|native", re.I)
EXCLUDE = re.compile(r"organoid|in[ _-]?vitro|transplant|xenograft|mouse|murine|blank|\bqc\b|library|empty", re.I)
GROUP_WORDS = (("goblet", re.compile(r"goblet", re.I)),
               ("fibroblast", re.compile(r"fibro|pdgfr", re.I)),
               ("immune", re.compile(r"immune|cd45|leuko", re.I)),
               ("crypt bottom", re.compile(r"bottom|base", re.I)),
               ("upper crypt", re.compile(r"upper|top", re.I)))


def out_dir(rehearse: bool) -> Path:
    return RESULTS / (f"heldout_{SET}_rehearsal" if rehearse else f"heldout_{SET}")


def group_classes(names: list[str], hierarchy: dict) -> dict:
    """Each group's reference class positions (rule 5)."""
    out = {}
    for g, classes in GROUPS.items():
        if classes == "lineage:immune":
            classes = tuple(c for c in names if hierarchy[c]["lineage"] == "immune")
        missing = [c for c in classes if c not in names]
        if missing:
            raise SystemExit(f"group {g}: the candidate has no class {missing}")
        out[g] = [names.index(c) for c in classes]
    return out


def _group_of(text: str) -> "str | None":
    found = [g for g, rx in GROUP_WORDS if rx.search(text)]
    if "goblet" in found:
        return "goblet"
    found = [g for g in found if g not in ("crypt bottom", "upper crypt")] or found
    return found[0] if len(set(found)) == 1 else None


def read_label_map(metadata: pd.DataFrame, runs: list[str]) -> tuple[pd.DataFrame, dict]:
    """Rules 3 to 5 on the deposit's metadata (module docstring). Stops on any doubt."""
    text = metadata.astype(str)
    run_name = {formats.run_name(r): r for r in runs}
    link = [c for c in text.columns if text[c].map(lambda v: formats.run_name(v) in run_name).mean() > 0.5]
    if len(link) != 1:
        raise SystemExit(f"no single metadata column names the matrix's runs (candidates {link})")
    contour = [c for c in metadata.columns if re.search(r"contour|shape|cells? ?(per|number|count)|n.?cells", str(c), re.I)
               and pd.to_numeric(metadata[c], errors="coerce").notna().all()]
    donor = [c for c in metadata.columns if re.search(r"donor|patient|individual|subject", str(c), re.I)]
    rows, skipped = [], {"not native": 0, "no group": 0, "not in matrix": 0}
    for i, r in text.iterrows():
        fields = " | ".join(r.tolist())
        run = formats.run_name(r[link[0]])
        if run not in run_name:
            skipped["not in matrix"] += 1
            continue
        if EXCLUDE.search(fields) or not NATIVE.search(fields):
            skipped["not native"] += 1
            continue
        g = _group_of(" ".join(v for c, v in r.items() if c != link[0]))
        if g is None:
            skipped["no group"] += 1
            continue
        contours = int(float(metadata.loc[i, contour[0]])) if len(contour) == 1 else None
        rows.append({"cell_id": run_name[run], "group": g, "donor": r[donor[0]] if len(donor) == 1 else "all",
                     "contours": contours, "pooled": contours is None or contours > 1, "scored": True})
    labels = pd.DataFrame(rows)
    if labels.empty:
        raise SystemExit("no native human colon sample was recognised")
    info = {"rules": "protocol rules 3 to 5, read by meaning (automatic)", "link_column": link[0],
            "contour_column": contour[0] if len(contour) == 1 else None, "donor_column": donor[0] if len(donor) == 1 else None,
            "skipped": skipped}
    return labels, info


def candidate_dir(rehearse: bool) -> Path:
    """The frozen candidate (rule 1). The rehearsal uses the colon build's current bundle."""
    work = organ_data.WORK / "large_intestine" / "bundle"
    if rehearse:
        return work
    text = PROTOCOL.read_text(encoding="utf-8")
    m = re.search(r"candidate.*?MANIFEST\.json[^`]*`([0-9a-f]{64})`", text, re.I | re.S)
    if not m:
        raise SystemExit("the protocol has no candidate amendment with the bundle's MANIFEST sha256 (rule 1)")
    if sha256(work / "MANIFEST.json") != m.group(1):
        raise SystemExit("the colon bundle's MANIFEST is not the frozen candidate's")
    return work


def run_candidate(directory: Path, raw: alignment.RawMatrix, out: Path) -> dict:
    b = organ_bundle.load(directory)
    names = list(b.class_names)
    with organ_bundle.gene_map(directory):  # the colon's own identifier map
        response = pipeline.run_projection(b, raw)
        p = class_probabilities(b, raw)
    t = table(response)
    t["reference_similarity"] = [c["reference_similarity"] for c in response["cells"]]
    served, mine = t["best_guess"].to_numpy(), np.array(names)[p.argmax(axis=1)]
    has = served != ""
    if not np.array_equal(served[has], mine[has]):
        raise SystemExit(f"the recomputed probabilities' argmax differs from the served best guess on {int((served[has] != mine[has]).sum())} samples")
    t.to_csv(out / "li_pred.csv", index=False, lineterminator="\n")
    np.savez_compressed(out / "li_probs.npz", probs=p.astype(np.float32), class_names=np.array(names, dtype=object),
                        hierarchy=json.dumps(b.hierarchy))
    return {"pipeline_version": response["pipeline_version"], "reference_version": b.spec.get("reference_version"),
            "manifest_sha256": sha256(directory / "MANIFEST.json"), "n_cells": response["n_cells"],
            "n_features_matched": response["n_features_matched"]}


def intake(labels: pd.DataFrame, matrix: Path, out: Path, candidate: Path, source: dict) -> dict:
    pooled = labels[labels["pooled"]].reset_index(drop=True)
    if len(pooled) < 20:
        raise SystemExit(f"void: {len(pooled)} pooled samples, fewer than the service's 20 (rule 6)")
    tab = formats.read_dia_nn(matrix)
    raw = tab.raw(pooled["cell_id"].tolist())
    (out / "cell_ids.txt").write_text("\n".join(raw.cell_ids) + "\n", encoding="utf-8", newline="\n")
    run = run_candidate(candidate, raw, out)
    np.savez_compressed(out / "query_benchmark.npz", x=benchmark_matrix(raw), cell_ids=np.array(raw.cell_ids, dtype=object))
    single = labels[~labels["pooled"]]
    if len(single):
        tab_s = tab.raw(single["cell_id"].tolist())
        sub = out / "single"
        sub.mkdir(exist_ok=True)
        run["single"] = run_candidate(candidate, tab_s, sub)
    record = {"protocol": "research/benchmark/protocol-colon-pxd052341.md", "set": SET, "rehearsal": "rehearsal" in out.name,
              "source": source, "reader": tab.record, "candidate": run, "label_free_facts": facts(raw),
              "outputs": {p.name: sha256(p) for p in sorted(out.iterdir()) if p.suffix in (".csv", ".txt", ".npz")}}
    (out / "intake.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return record


def _check_download(rel: str) -> str:
    want = json.loads(DOWNLOADS.read_text(encoding="utf-8"))[rel]["sha256"]
    got = sha256(PUBLIC / rel)
    if got != want:
        raise SystemExit(f"{rel}: sha256 {got} differs from the download record {want}")
    return got


# ---- the rehearsal: RNA pseudobulk written in the deposit's format ----

DEV = PUBLIC
DVP_DEV = ("Zheng2025_PXD057118/ColorectalCancer_pg_matrix_Macrophages.txt",
           "Zheng2025_PXD057118/Colorectal_Cancer_pg_matrix_Cytotoxic_T_Cells.txt",
           "Zheng2025_PXD057118/Colorectal_Cancer_pg_matrix_Helper_T_Cells.txt",
           "Kabatnik2024_PXD046999/C3_region1k_DIANN181_MBR_c124.pg_matrix.tsv")
REHEARSAL = {"cells_per_pool": 100, "pools_per_donor_group": 3, "min_cells": 60, "seed": 20261018}


def pool_detection(genes: list[str]) -> np.ndarray:
    """Per gene, the share of development DVP pools (Zheng, Kabatnik) that detect it; 0 where none does."""
    seen: dict[str, list[float]] = {}
    for rel in DVP_DEV:
        t = formats.read_dia_nn(PUBLIC / rel)
        det = np.isfinite(t.values).mean(1)
        for g, d in zip(t.genes, det):
            seen.setdefault(g.upper(), []).append(float(d))
    return np.array([max(seen.get(g.upper(), [0.0])) for g in genes], np.float32)


def rehearsal_files(directory: Path) -> tuple[Path, Path, dict]:
    """A DIA-NN pg_matrix and a metadata table in an assumed layout: pseudobulk
    pools of the colon's test cells by donor and group, detection drawn from the
    development DVP pools, plus organoid and blank decoys the rules must drop."""
    work = organ_data.WORK / "large_intestine"
    lab = pd.read_csv(work / "labels.csv.gz", keep_default_na=False)
    test = np.load(work / "splits_seed0.npz")["test"]
    genes = pd.read_csv(work / "feature_space_genes.csv")["gene"].tolist()
    X = organ_data.load_rna(organ_data.resolve(organ_data.load_organ("large_intestine")["rna"]), genes)[lab["row"].to_numpy()]
    hierarchy = json.loads((work / "classes.json").read_text(encoding="utf-8"))["hierarchy"]
    member = {}
    for g, classes in GROUPS.items():
        classes = [c for c in hierarchy if hierarchy[c]["lineage"] == "immune"] if classes == "lineage:immune" else classes
        member[g] = set(classes)
    p_det = pool_detection(genes)
    rng = np.random.default_rng(REHEARSAL["seed"])
    cols, meta = {}, []
    words = {"crypt bottom": "Crypt bottom epithelium", "upper crypt": "Upper crypt epithelium", "goblet": "Goblet cells",
             "fibroblast": "PDGFRA+ fibroblasts", "immune": "CD45+ immune cells"}
    t_lab = lab.iloc[test]
    for donor, dd in t_lab.groupby("donor"):
        for g, classes in member.items():
            idx = dd.index[dd["class_name"].isin(classes)].to_numpy()
            if len(idx) < REHEARSAL["min_cells"]:
                continue
            for k in range(REHEARSAL["pools_per_donor_group"]):
                pick = rng.choice(idx, min(REHEARSAL["cells_per_pool"], len(idx)), replace=False)
                bulk = np.expm1(X[pick]).mean(0) * 1e4
                seen = rng.random(len(genes)) < p_det
                run = f"D:\\Data\\DVP\\{donor}_{g.replace(' ', '')}_{k + 1}.raw"
                cols[run] = np.where(seen & (bulk > 0), bulk, np.nan)
                meta.append({"Raw file": Path(run.replace("\\", "/")).name, "Sample": "colon mucosa, in vivo", "Population": words[g],
                             "Donor": donor, "Contours": REHEARSAL["cells_per_pool"]})
    decoys = [("organoid in vitro", "LGR5-TdTomato+ stem cells"), ("organoid transplant, mouse", "Goblet cells"), ("blank", "-")]
    for j, (sample, population) in enumerate(decoys):
        run = f"D:\\Data\\DVP\\decoy_{j}.raw"
        cols[run] = next(iter(cols.values()))
        meta.append({"Raw file": Path(run.replace("\\", "/")).name, "Sample": sample, "Population": population,
                     "Donor": "none", "Contours": 500})
    matrix = pd.DataFrame({"Protein.Group": genes, "Protein.Ids": genes, "Protein.Names": genes, "Genes": genes,
                           "First.Protein.Description": "", **cols})
    directory.mkdir(parents=True, exist_ok=True)
    mp, md = directory / "DVP_data.pg_matrix.tsv", directory / "metadata.tsv"
    matrix.to_csv(mp, sep="\t", index=False, lineterminator="\n")
    pd.DataFrame(meta).to_csv(md, sep="\t", index=False, lineterminator="\n")
    return mp, md, {"what": "RNA pseudobulk of the colon reference's test cells, written as a DIA-NN pg_matrix",
                    **REHEARSAL, "pools": len(meta) - len(decoys), "decoys": len(decoys)}


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearse", action="store_true", help="RNA pseudobulk in the deposit's format")
    parser.add_argument("--labels", action="store_true", help="unsealing only: build the label map, once")
    parser.add_argument("--label-map", type=Path, help="a map written by hand by the protocol's rules (with --labels)")
    parser.add_argument("--reason", help="why the map was written by hand (with --label-map)")
    args = parser.parse_args(argv)
    out = out_dir(args.rehearse)
    if args.rehearse:
        if out.exists():
            shutil.rmtree(out)
        matrix, metadata, source = rehearsal_files(out / "files")
        labels, info = read_label_map(pd.read_csv(metadata, sep="\t", dtype=str), formats.read_dia_nn(matrix).samples)
        write_labels(labels, out, {**info, "source": source})
        record = intake(labels, matrix, out, candidate_dir(True), source)
        print(json.dumps({"labels": len(labels), "candidate": record["candidate"]}, indent=1))
        return
    matrix, metadata = PUBLIC / INPUTS[0], PUBLIC / INPUTS[1]
    if args.labels:
        if (out / "label_map.csv").exists():
            raise SystemExit("the label map exists; it is written once")
        source = {rel: _check_download(rel) for rel in INPUTS}
        if args.label_map is not None:
            if not args.reason:
                raise SystemExit("a hand-written map needs --reason")
            labels, info = pd.read_csv(args.label_map), {"rules": "protocol rules 3 to 5, written by hand", "reason": args.reason}
        else:
            labels, info = read_label_map(pd.read_csv(metadata, sep="\t", dtype=str), formats.read_dia_nn(matrix).samples)
        print("label map sha256", write_labels(labels, out, {**info, "inputs": source}))
        return
    if (out / "intake.json").exists():
        raise SystemExit("the intake ran; it runs once")
    labels = pd.read_csv(out / "label_map.csv", keep_default_na=False)
    labels["pooled"] = labels["pooled"].astype(str) == "True"
    source = {rel: _check_download(rel) for rel in INPUTS}
    record = intake(labels, matrix, out, candidate_dir(False), source)
    print(json.dumps(record["candidate"], indent=1))


if __name__ == "__main__":
    main()
