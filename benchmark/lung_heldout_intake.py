"""The lung reference's locked test, MSV000094189 (Ushakumary 2025), steps 2 and
3 of its unsealing (research/benchmark/protocol-lung-msv000094189.md): the
label map, then the intake. Written and rehearsed before any file of the set
was opened; the colon's intake (benchmark/colon_heldout_intake.py) is the
pattern, and its candidate runner is reused.

    python -m benchmark.lung_heldout_intake --rehearse     # RNA pseudobulk in the deposit's format, any time
    python -m benchmark.lung_heldout_intake --labels       # unsealing only: the label map, once
    python -m benchmark.lung_heldout_intake --labels --label-map CSV --reason TEXT
    python -m benchmark.lung_heldout_intake                # unsealing only: the intake, once

The label map (rules 3 and 4) is read from the sample names by meaning: a
token starting "epi" is epithelial; "end" or "endo" endothelial; "mes"
stromal (mesenchymal); "mic", "immune" or "cd45" immune. A name with
"pmx", "mix", "unsorted", "presort", "pool", "qc", "blank" or "library" is
excluded. The donor is a token like "D012", "donor12" or "TSP2". A name matching no
population or several stops the automatic reading; the map is then written
by hand by the same rules, with the reason recorded.

Writes benchmark/results/heldout_msv000094189/ (heldout_msv000094189_rehearsal/
when rehearsing): label_map.csv, labels.json, intake.json, cell_ids.txt,
lung_pred.csv, lung_probs.npz, query_benchmark.npz.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import heldout_formats as formats
from benchmark.colon_heldout_intake import DOWNLOADS, PUBLIC, REPO, RESULTS, organ_data, run_candidate
from benchmark.heldout_intake import facts, write_labels
from benchmark.khoury2026_embed import refuse_overrides
from benchmark.sorted_cd4cd8_intake import benchmark_matrix, sha256
from benchmark.organ_baselines import organ_matrix

PROTOCOL = REPO / "research" / "benchmark" / "protocol-lung-msv000094189.md"
SET = "msv000094189"
INPUTS = ("LungMAP2025_MSV000094189/proteinGroups.txt", "LungMAP2025_MSV000094189/Protein_metadata.csv",
          "LungMAP2025_MSV000094189/summary.txt")
LINEAGES = ("epithelial", "endothelial", "stromal", "immune")
# Whole words only: the samples are themselves pools of sorted cells, and the
# paper's own population is "CD45+ mixed immune cells".
EXCLUDE = frozenset({"pmx", "mix", "mixed", "unsorted", "presort", "presorted", "qc", "blank", "library"})
# A gate written with its sign: a positive marker names its lineage, a
# negative one names none, and all three negative is the triple-negative
# mesenchymal sort (rule 4).
MARKERS = {"cd45": "immune", "ptprc": "immune", "epcam": "epithelial", "cd326": "epithelial",
           "cd31": "endothelial", "pecam1": "endothelial", "pecam": "endothelial"}
SIGNED = re.compile(r"(cd45|ptprc|epcam|cd326|cd31|pecam1|pecam)(\+|-|(?:positive|negative|pos|neg)(?![a-z]))")


def out_dir(rehearse: bool) -> Path:
    return RESULTS / (f"heldout_{SET}_rehearsal" if rehearse else f"heldout_{SET}")


def population(name: str) -> "str | None":
    """Rule 4's population, "excluded", or None for doubt."""
    low = name.lower()
    positive, negative = set(), set()
    for m in SIGNED.finditer(low):
        (positive if m.group(2) in ("+", "pos", "positive") else negative).add(MARKERS[m.group(1)])
    tokens = [t for t in re.split(r"[^a-z0-9]+", SIGNED.sub(" ", low)) if t]
    excluded = any(re.sub(r"\d+$", "", t) in EXCLUDE for t in tokens)
    found = set(positive)
    if not positive and negative == {"immune", "endothelial", "epithelial"}:
        found.add("stromal")
    for t in tokens:
        if t.startswith("epi"):
            found.add("epithelial")
        elif t in ("end", "endo") or t.startswith("endoth"):
            found.add("endothelial")
        elif t.startswith("mes"):
            found.add("stromal")
        elif t.startswith(("mic", "immune", "cd45")):
            found.add("immune")
    if excluded:
        return None if found else "excluded"  # a population beside an exclusion word is doubt
    return found.pop() if len(found) == 1 else None


def donor(name: str) -> str:
    m = re.search(r"(?:^|[^a-z0-9])((?:d|donor|tsp)_?\d{1,4})(?:[^0-9]|$)", name.lower())
    return m.group(1).replace("donor", "d").replace("_", "") if m else "all"


def read_label_map(samples: list[str]) -> tuple[pd.DataFrame, dict]:
    rows, doubt, excluded = [], [], 0
    for s in samples:
        p = population(s)
        if p == "excluded":
            excluded += 1
        elif p is None:
            doubt.append(s)
        elif donor(s) == "all":
            doubt.append(s)  # rule 3: a donor is assigned without doubt, or the map is written by hand
        else:
            rows.append({"cell_id": s, "group": p, "donor": donor(s), "scored": True})
    if doubt:
        raise SystemExit(f"{len(doubt)} sample names name no single population or no donor, e.g. {doubt[:3]}: "
                         "write the map by hand (rule 3)")
    return pd.DataFrame(rows), {"rules": "protocol rules 3 and 4, read from the sample names by meaning (automatic)",
                                "excluded": excluded}


# The candidate's build (the protocol's amendment 1, 2026-10-19: "lung v2", built from
# scripts/organs/lung_v2.json); v1 missed its gates.
CANDIDATE = "lung_v2"


def candidate_dir(rehearse: bool) -> Path:
    work = organ_data.WORK / CANDIDATE / "bundle"
    if rehearse:
        return work
    m = re.search(r"candidate.*?MANIFEST\.json[^`]*`([0-9a-f]{64})`", PROTOCOL.read_text(encoding="utf-8"), re.I | re.S)
    if not m:
        raise SystemExit("the protocol has no candidate amendment with the bundle's MANIFEST sha256 (rule 1)")
    if sha256(work / "MANIFEST.json") != m.group(1):
        raise SystemExit("the lung bundle's MANIFEST is not the frozen candidate's")
    return work



def void_record() -> Path:
    """Where a void set is recorded once its labels are read: the summary the
    scorer would write, so the scored-once guard then holds."""
    return REPO / "research" / "benchmark" / "heldout" / SET / "summary.json"


def record_void(out: Path, reason: str) -> None:
    if "rehearsal" not in out.name:
        target = void_record()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"protocol": str(PROTOCOL.relative_to(REPO)).replace("\\", "/"), "set": SET,
                                      "void": reason}, indent=2) + "\n", encoding="utf-8", newline="\n")
    raise SystemExit(f"void: {reason}")


def intake(labels: pd.DataFrame, matrix: Path, out: Path, candidate: Path, source: dict) -> dict:
    if len(labels) < 20:
        record_void(out, f"{len(labels)} samples, fewer than 20 (rule 5)")
    tab = formats.read_maxquant(matrix)
    raw = tab.raw(labels["cell_id"].tolist())
    (out / "cell_ids.txt").write_text("\n".join(raw.cell_ids) + "\n", encoding="utf-8", newline="\n")
    run = run_candidate(candidate, raw, out, prefix="lung")
    np.savez_compressed(out / "query_benchmark.npz", x=benchmark_matrix(raw), cell_ids=np.array(raw.cell_ids, dtype=object))
    # the baselines' input on the organ's own gene space (benchmark/organ_baselines.py)
    np.savez_compressed(out / "query_organ.npz", x=organ_matrix(raw, candidate), cell_ids=np.array(raw.cell_ids, dtype=object))
    record = {"protocol": "research/benchmark/protocol-lung-msv000094189.md", "set": SET, "rehearsal": "rehearsal" in out.name,
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


# ---- the rehearsal: RNA pseudobulk written as a MaxQuant table ----

REHEARSAL = {"cells_per_pool": 200, "pools_per_donor_lineage": 2, "min_cells": 60, "seed": 20261018}
CODE = {"epithelial": "EPI", "endothelial": "END", "stromal": "MES", "immune": "MIC"}


def rehearsal_files(directory: Path) -> tuple[Path, dict]:
    """Pseudobulk pools of the lung's test cells by donor and lineage, detection drawn
    from the development sorted pools (MSV000094373), plus pre-sort-mix and QC decoys."""
    work = organ_data.WORK / CANDIDATE
    lab = pd.read_csv(work / "labels.csv.gz", keep_default_na=False)
    test = np.load(work / "splits_seed0.npz")["test"]
    genes = pd.read_csv(work / "feature_space_genes.csv")["gene"].tolist()
    X = organ_data.load_rna(organ_data.resolve(organ_data.load_organ(CANDIDATE)["rna"]), genes)[lab["row"].to_numpy()]
    dev = pd.read_csv(PUBLIC / "LungMAP2025_BPD_MSV000094373" / "combined_protein.tsv", sep="\t", low_memory=False)
    lfq = dev[[c for c in dev.columns if c.endswith(" MaxLFQ Intensity")]].to_numpy(float)
    seen_share = pd.Series((lfq > 0).mean(1), index=dev["Gene"].fillna("").str.upper()).groupby(level=0).max()
    p_det = np.array([float(seen_share.get(g.upper(), 0.0)) for g in genes])
    rng = np.random.default_rng(REHEARSAL["seed"])
    cols = {}
    t_lab = lab.iloc[test]
    for d, dd in t_lab.groupby("donor"):
        for lineage in LINEAGES:
            idx = dd.index[dd["lineage"] == lineage].to_numpy()
            if len(idx) < REHEARSAL["min_cells"]:
                continue
            for k in range(REHEARSAL["pools_per_donor_lineage"]):
                pick = rng.choice(idx, min(REHEARSAL["cells_per_pool"], len(idx)), replace=False)
                bulk = np.expm1(X[pick]).mean(0) * 1e6
                cols[f"LMAP_{d}_{CODE[lineage]}_{k + 1}"] = np.where((rng.random(len(genes)) < p_det) & (bulk > 0), bulk, 0.0)
    first = next(iter(cols.values()))
    cols["LMAP_TSPX_PMX_1"], cols["QC_HeLa_1"] = first, first
    table = pd.DataFrame({"Protein IDs": genes, "Majority protein IDs": genes, "Gene names": genes,
                          "Only identified by site": "", "Reverse": "", "Potential contaminant": "",
                          **{f"Intensity {s}": v for s, v in cols.items()}, **{f"LFQ intensity {s}": v for s, v in cols.items()}})
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "proteinGroups.txt"
    table.to_csv(path, sep="\t", index=False, lineterminator="\n")
    return path, {"what": "RNA pseudobulk of the lung reference's test cells, written as a MaxQuant proteinGroups table",
                  **REHEARSAL, "pools": len(cols) - 2, "decoys": 2}


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearse", action="store_true")
    parser.add_argument("--labels", action="store_true")
    parser.add_argument("--label-map", type=Path)
    parser.add_argument("--reason")
    args = parser.parse_args(argv)
    refuse_overrides()  # the repository's model files, not an export elsewhere
    out = out_dir(args.rehearse)
    if args.rehearse:
        if out.exists():
            shutil.rmtree(out)
        matrix, source = rehearsal_files(out / "files")
        labels, info = read_label_map(formats.read_maxquant(matrix).samples)
        write_labels(labels, out, {**info, "source": source})
        record = intake(labels, matrix, out, candidate_dir(True), source)
        print(json.dumps({"labels": len(labels), "candidate": record["candidate"]}, indent=1))
        return
    matrix = PUBLIC / INPUTS[0]
    if args.labels:
        if (out / "label_map.csv").exists():
            raise SystemExit("the label map exists; it is written once")
        candidate_dir(False)  # rule 1: no frozen candidate, no unsealing; checked before any sealed file is read
        source = {rel: _check_download(rel) for rel in INPUTS}
        if args.label_map is not None:
            if not args.reason:
                raise SystemExit("a hand-written map needs --reason")
            labels, info = pd.read_csv(args.label_map), {"rules": "protocol rules 3 and 4, written by hand", "reason": args.reason}
        else:
            labels, info = read_label_map(formats.read_maxquant(matrix).samples)
        print("label map sha256", write_labels(labels, out, {**info, "inputs": source}, groups=set(LINEAGES),
                                               required=("donor",), known_ids=formats.read_maxquant(matrix).samples))
        return
    if (out / "intake.json").exists():
        raise SystemExit("the intake ran; it runs once")
    labels = pd.read_csv(out / "label_map.csv", keep_default_na=False)
    source = {rel: _check_download(rel) for rel in INPUTS}
    print(json.dumps(intake(labels, matrix, out, candidate_dir(False), source)["candidate"], indent=1))


if __name__ == "__main__":
    main()
