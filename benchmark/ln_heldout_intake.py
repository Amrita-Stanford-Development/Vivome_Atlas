"""The lymph node reference's locked test, PXD042367's tonsil niches (Makhmut
2023), steps 2 and 3 of its unsealing (research/benchmark/protocol-ln-pxd042367.md):
the label map, then the intake. Written and rehearsed before any file of the
set was opened, on the colon's and the lung's pattern.

    python -m benchmark.ln_heldout_intake --rehearse     # RNA pseudobulk regions in DIA-NN's layout, any time
    python -m benchmark.ln_heldout_intake --labels       # unsealing only: the label map, once
    python -m benchmark.ln_heldout_intake --labels --label-map CSV --reason TEXT
    python -m benchmark.ln_heldout_intake                # unsealing only: the intake, once

The archive (DIANN_results_Fig4.rar) is unpacked with Windows' tar
(libarchive reads RAR). The protein-group matrix is the file whose name has
"pg" and "matrix" in it: a tab-separated file is read by the service's own
parser; an Excel file (the lab's other deposit used one) is written out as
tab-separated text first, unchanged.

Each run's region is read from its name by meaning (rule 3), on name tokens
with trailing digits removed:
- germinal centre: "dz", "lz", "gz", "gc", "dark", "light", "grey", "gray";
- mantle zone: "mz", "mantle";
- a B-cell region named without its zone: "b", "bcell", "bzone", "follicle";
- T zone: "tz", "tzone", "interfollicular", "if", or a bare "t";
- epithelium: "epi", "epithelium", "squamous";
- excluded: "blank", "qc", "library", "hela", "empty".
Germinal centre and mantle zone make the B zone. A name with no region, or
regions of two zones, stops the automatic reading; the map is then written by
hand by the same rules, with the reason.

Writes benchmark/results/heldout_pxd042367/ (heldout_pxd042367_rehearsal/ when
rehearsing): label_map.csv, labels.json, intake.json, cell_ids.txt,
ln_pred.csv, ln_probs.npz, query_benchmark.npz.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark.colon_heldout_intake import DOWNLOADS, PUBLIC, REPO, RESULTS, organ_data, run_candidate
from benchmark.heldout_intake import facts, write_labels
from benchmark.khoury2026_embed import refuse_overrides
from benchmark.sorted_cd4cd8_intake import benchmark_matrix, sha256
from benchmark.organ_baselines import organ_matrix
from service.pipeline import alignment

PROTOCOL = REPO / "research" / "benchmark" / "protocol-ln-pxd042367.md"
SET = "pxd042367"
INPUTS = ("Coscia2023_PXD042367/DIANN_results_Fig4.rar",)
TAR = Path(r"C:\Windows\System32\tar.exe")
WORDS = {"germinal centre": ("dz", "lz", "gz", "gc", "dark", "light", "grey", "gray"),
         "mantle zone": ("mz", "mantle"),
         "B-cell region": ("b", "bcell", "bzone", "follicle"),
         "T zone": ("tz", "tzone", "interfollicular", "if", "t"),
         "epithelium": ("epi", "epithelium", "squamous")}
EXCLUDE = ("blank", "qc", "library", "hela", "empty")
ZONE = {"germinal centre": "B zone", "mantle zone": "B zone", "B-cell region": "B zone", "T zone": "T zone",
        "epithelium": "epithelium"}


def out_dir(rehearse: bool) -> Path:
    return RESULTS / (f"heldout_{SET}_rehearsal" if rehearse else f"heldout_{SET}")


# A plate slot and well, as in "S2-B1", names no region (its letter is a row).
SLOT_WELL = re.compile(r"(?<![a-z0-9])s\d+-[a-p]\d+(?![0-9])")


def region(name: str) -> "str | None":
    """Rule 3's region, or None for doubt (no region, or more than one)."""
    tokens = [re.sub(r"\d+$", "", t) for t in re.split(r"[^a-z0-9]+", SLOT_WELL.sub(" ", name.lower())) if t]
    if any(t in EXCLUDE for t in tokens):
        return "excluded"
    found = {r for r, words in WORDS.items() for t in tokens if t in words}
    return found.pop() if len(found) == 1 else None


def read_label_map(runs: list[str]) -> tuple[pd.DataFrame, dict]:
    rows, doubt, excluded = [], [], 0
    for r in runs:
        reg = region(r)
        if reg == "excluded":
            excluded += 1
        elif reg is None:
            doubt.append(r)
        else:
            rows.append({"cell_id": r, "region": reg, "group": ZONE[reg], "scored": ZONE[reg] != "epithelium"})
    if doubt:
        raise SystemExit(f"{len(doubt)} run names name no single region, e.g. {doubt[:3]}: write the map by hand (rule 3)")
    return pd.DataFrame(rows), {"rules": "protocol rule 3, read from the run names by meaning (automatic)", "excluded": excluded}


def matrix_from_archive(archive: Path, target: Path) -> Path:
    """The protein-group matrix as tab-separated text (module docstring)."""
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(TAR), "-xf", str(archive), "-C", str(target)], check=True)
    found = [p for p in target.rglob("*") if p.is_file() and "pg" in p.name.lower() and "matrix" in p.name.lower()]
    if len(found) != 1:
        raise SystemExit(f"not one protein-group matrix in {archive.name}: {[p.name for p in found]}")
    p = found[0]
    if p.suffix.lower() in (".xlsx", ".xls"):
        tsv = p.with_suffix(".tsv")
        pd.read_excel(p).to_csv(tsv, sep="\t", index=False, lineterminator="\n")
        return tsv
    return p


def read_matrix(path: Path) -> alignment.RawMatrix:
    return alignment.parse_matrix_csv(path.read_text(encoding="utf-8"))


# The candidate's build (the protocol's amendment 6, 2026-10-21: "lymph_node v3", built
# from scripts/organs/lymph_node_v3.json); v1 and v2 missed their gates.
CANDIDATE = "lymph_node_v3"


def candidate_dir(rehearse: bool) -> Path:
    work = organ_data.WORK / CANDIDATE / "bundle"
    if rehearse:
        return work
    m = re.search(r"candidate.*?MANIFEST\.json[^`]*`([0-9a-f]{64})`", PROTOCOL.read_text(encoding="utf-8"), re.I | re.S)
    if not m:
        raise SystemExit("the protocol has no candidate amendment with the bundle's MANIFEST sha256 (rule 1)")
    if sha256(work / "MANIFEST.json") != m.group(1):
        raise SystemExit("the lymph node bundle's MANIFEST is not the frozen candidate's")
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
    scored = labels[labels["scored"].astype(str) == "True"]
    if (scored["group"] == "B zone").sum() < 3 or (scored["group"] == "T zone").sum() < 3 or len(scored) < 20:
        record_void(out, "too few B-zone or T-zone regions (rule 7)")
    full = read_matrix(matrix)
    position = {c: i for i, c in enumerate(full.cell_ids)}
    keep = labels["cell_id"].tolist()
    raw = alignment.RawMatrix(gene_names=full.gene_names, cell_ids=keep, values=full.values[:, [position[c] for c in keep]])
    (out / "cell_ids.txt").write_text("\n".join(raw.cell_ids) + "\n", encoding="utf-8", newline="\n")
    run = run_candidate(candidate, raw, out, prefix="ln")
    np.savez_compressed(out / "query_benchmark.npz", x=benchmark_matrix(raw), cell_ids=np.array(raw.cell_ids, dtype=object))
    # the baselines' input on the organ's own gene space (benchmark/organ_baselines.py)
    np.savez_compressed(out / "query_organ.npz", x=organ_matrix(raw, candidate), cell_ids=np.array(raw.cell_ids, dtype=object))
    record = {"protocol": "research/benchmark/protocol-ln-pxd042367.md", "set": SET, "rehearsal": "rehearsal" in out.name,
              "source": source, "matrix": matrix.name, "candidate": run, "label_free_facts": facts(raw),
              "outputs": {p.name: sha256(p) for p in sorted(out.iterdir()) if p.suffix in (".csv", ".txt", ".npz")}}
    (out / "intake.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return record


def _check_download(rel: str) -> str:
    want = json.loads(DOWNLOADS.read_text(encoding="utf-8"))[rel]["sha256"]
    got = sha256(PUBLIC / rel)
    if got != want:
        raise SystemExit(f"{rel}: sha256 {got} differs from the download record {want}")
    return got


# ---- the rehearsal: pseudobulk regions written as a DIA-NN pg_matrix in Excel ----

REHEARSAL = {"cells_per_region": 100, "regions_per_kind": 12, "seed": 20261018}
MIX = {"DZ": {"B cell": 0.85, "T cell": 0.15}, "MZ": {"B cell": 0.9, "T cell": 0.1},
       "TZ": {"T cell": 0.8, "B cell": 0.1, "monocyte/macrophage": 0.1}}


def rehearsal_files(directory: Path) -> tuple[Path, dict]:
    """Regions as mixtures of the reference's test cells (germinal-centre-like,
    mantle-like, T-zone-like), detection from PXD047762's development regions,
    plus epithelium decoys (values shuffled across proteins) and a blank."""
    work = organ_data.WORK / CANDIDATE
    lab = pd.read_csv(work / "labels.csv.gz", keep_default_na=False)
    test = np.load(work / "splits_seed0.npz")["test"]
    genes = pd.read_csv(work / "feature_space_genes.csv")["gene"].tolist()
    X = organ_data.load_rna(organ_data.resolve(organ_data.load_organ(CANDIDATE)["rna"]), genes)[lab["row"].to_numpy()]
    dev = pd.read_csv(organ_data.WORK / "lymph_node" / "dev" / "coscia2024_fig3_pg_matrix.tsv", sep="\t")
    runs = [c for c in dev.columns if c.endswith(".d")]
    seen_share = pd.Series(np.isfinite(dev[runs].to_numpy(float)).mean(1), index=dev["Genes"].fillna("").str.upper()).groupby(level=0).max()
    p_det = np.array([float(seen_share.get(g.upper(), 0.0)) for g in genes])
    rng = np.random.default_rng(REHEARSAL["seed"])
    t_lab = lab.iloc[test]
    by_group = {g: t_lab.index[t_lab["group"] == g].to_numpy() for g in ("B cell", "T cell", "monocyte/macrophage")}
    cols = {}
    for kind, mix in MIX.items():
        for k in range(REHEARSAL["regions_per_kind"]):
            pick = np.concatenate([rng.choice(by_group[g], int(round(f * REHEARSAL["cells_per_region"])), replace=False) for g, f in mix.items()])
            bulk = np.expm1(X[pick]).mean(0) * 1e6
            cols[f"tonsil_Whisper_{kind}{k + 1}_S2-A{k + 1}_1_{1000 + len(cols)}.d"] = np.where((rng.random(len(genes)) < p_det) & (bulk > 0), bulk, np.nan)
    first = next(iter(cols.values()))
    for k in range(4):
        cols[f"tonsil_Whisper_Epi{k + 1}_S2-C{k + 1}_1_{2000 + k}.d"] = rng.permutation(first)
    cols["tonsil_Whisper_blank_S2-D1_1_3000.d"] = first
    table = pd.DataFrame({"Protein.Group": genes, "Protein.Ids": genes, "Protein.Names": genes, "Genes": genes,
                          "First.Protein.Description": "", **cols})
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "Fig4_pg.matrix.xlsx"
    table.to_excel(path, index=False)
    return path, {"what": "RNA pseudobulk regions of the lymph node reference's test cells, written as a DIA-NN pg_matrix in Excel",
                  **REHEARSAL, "regions": 3 * REHEARSAL["regions_per_kind"], "epithelium_decoys": 4, "blanks": 1}


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
        xlsx, source = rehearsal_files(out / "files")
        tsv = xlsx.with_suffix(".tsv")
        pd.read_excel(xlsx).to_csv(tsv, sep="\t", index=False, lineterminator="\n")
        labels, info = read_label_map(read_matrix(tsv).cell_ids)
        write_labels(labels, out, {**info, "source": source})
        record = intake(labels, tsv, out, candidate_dir(True), source)
        print(json.dumps({"labels": len(labels), "candidate": record["candidate"]}, indent=1))
        return
    if args.labels:
        if (out / "label_map.csv").exists():
            raise SystemExit("the label map exists; it is written once")
        candidate_dir(False)  # rule 1: no frozen candidate, no unsealing; checked before any sealed file is read
        source = {rel: _check_download(rel) for rel in INPUTS}
        matrix = matrix_from_archive(PUBLIC / INPUTS[0], out / "archive")
        if args.label_map is not None:
            if not args.reason:
                raise SystemExit("a hand-written map needs --reason")
            labels, info = pd.read_csv(args.label_map), {"rules": "protocol rule 3, written by hand", "reason": args.reason}
        else:
            labels, info = read_label_map(read_matrix(matrix).cell_ids)
        print("label map sha256", write_labels(labels, out, {**info, "inputs": source, "matrix": matrix.name},
                                               groups=set(ZONE.values()), known_ids=read_matrix(matrix).cell_ids))
        return
    if (out / "intake.json").exists():
        raise SystemExit("the intake ran; it runs once")
    labels = pd.read_csv(out / "label_map.csv", keep_default_na=False)
    source = {rel: _check_download(rel) for rel in INPUTS}
    matrix = [p for p in (out / "archive").rglob("*.tsv") if "pg" in p.name.lower() and "matrix" in p.name.lower()][0]
    print(json.dumps(intake(labels, matrix, out, candidate_dir(False), source)["candidate"], indent=1))


if __name__ == "__main__":
    main()
