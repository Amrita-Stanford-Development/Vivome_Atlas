"""SCoPE2's cell labels, corrected (research/benchmark/bugs-and-fixes.md, 8).

VivOME's copy of SCoPE2 (the Drive file blood_joint_cells_by_proteins.tsv,
and every file derived from it) labelled all 1,490 cells the wrong way round:
each "monocyte" is a macrophage and each "macrophage" a monocyte. Every
local copy is now corrected; the original is kept, by its sha256, as
data/incoming/SCoPE2_raw/blood_joint_cells_by_proteins.swapped_labels_original.tsv.
This script derives the correct labels and records the evidence:

1. The authors' curated object, Bioconductor SingleCellMultiModal's
   macrophage_protein (ExperimentHub EH4694), names each cell by SCoPE2's own
   id (i1, i2, ...) with its cell type. VivOME's id map
   (blood_cellid_mapping.tsv) links those ids to Prot_Blood_N, row N - 1 of
   every VivOME copy.
2. The cell counts: the curated object has 1,096 macrophages and 394
   monocytes; VivOME's copy had the reverse.
3. Biology, on VivOME's own matrix and on the reprocessed evidence
   (benchmark/scope2_reprocess.py, whose labels come from the experimental
   design): U-937 monocytes divide, so replication proteins are higher;
   PMA-differentiated macrophages carry more lysosomal and adhesion proteins.

The curated object is read with base R (its slots are plain attributes),
so no Bioconductor package is needed.

Writes research/benchmark/scope2_labels/corrected_labels.csv (orig_index,
vivome_id, scope2_id, curated, previous, label, class_idx) and check.json.

With --apply, puts the corrected labels into every copy (COPIES), changing
only the label fields so every other byte stays as it was, and into the
Parquet copies (PARQUETS; needs pyarrow), and updates what
records those files: the v3 export's sha256s, and v3's SCoPE2 evidence
tables (EVIDENCE), recomputed from v3's own saved latents. Each value it
replaces must be the previous labels' value, reproduced first, or the
corrected one already; anything else stops it. Running it twice changes
nothing. service/tests/test_scope2_labels.py pins every copy.

    python -m benchmark.scope2_labels            # from the repository root
    python -m benchmark.scope2_labels --apply
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from benchmark import datasets

RAW = datasets.REPO / "data" / "incoming" / "SCoPE2_raw"
OUT = datasets.REPO / "research" / "benchmark" / "scope2_labels"
FILES = {
    "curated": (RAW / "macrophage_protein.Rda", "0b445058e0e429bd26efd1d4e11dc1cbea9afc4c2f5f9abc0f04658d7059dd19"),
    "id_map": (RAW / "blood_cellid_mapping.tsv", "c4f4ffa2497ae1d7e51111748aa7789d4a3c718b07c23213837ae2503e3d14bd"),
    # VivOME's copy as it was, kept as the evidence; every working copy now has the corrected labels.
    "previous": (RAW / "blood_joint_cells_by_proteins.swapped_labels_original.tsv",
                 "59e00cbddaf9824c7e24f24ad573331984906fe07932b6ede04cf93ce8aa39b3"),
}
CLASS_IDX = {"macrophage": 10, "monocyte": 12}
PROLIFERATION = ["MCM2", "MCM3", "MCM4", "MCM5", "MCM6", "MCM7", "PCNA", "TOP2A", "MKI67", "SMC4", "RRM1", "RRM2", "TYMS", "LMNB1", "HMGB2"]
MACROPHAGE = ["CTSB", "CTSD", "LAMP1", "LAMP2", "LGALS3", "FN1", "ITGAM", "VIM", "SQSTM1", "CAPG", "PLAUR", "ICAM1",
              "MMP9", "ANPEP", "CD68", "TGM2", "SPP1", "APOE", "CYBB", "S100A4"]
RSCRIPT = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "R" / "R-4.6.1" / "bin" / "Rscript.exe"
LABELS = OUT / "corrected_labels.csv"


class Copy(NamedTuple):
    path: str            # from the repository root
    row: str             # the column numbering the cells 0..1489, orig_index order
    columns: dict        # label column -> "name" or "idx"
    tracked: bool        # False: a local, gitignored copy that may be absent


COPIES = [
    Copy("web/data/metadata_PROT_lat128.csv", "orig_index", {"class_idx": "idx", "class_name": "name"}, True),
    Copy("web/data/atlas_PROT_lat128.csv", "orig_index", {"class_idx": "idx", "class_name": "name"}, True),
    Copy("service/model/source/app_export/atlas_PROT_v3_meta.csv", "cell", {"true_class_name": "name"}, True),
    Copy("research/notebook-outputs/nb1d/scope2_cell_ids.csv", "cell_id", {"cell_type": "name"}, True),
    Copy("benchmark/results/prot_meta.csv", "orig_index", {"class_idx": "idx", "class_name": "name"}, False),
    Copy("data/incoming/NB1d/embeddings/scope2_cell_ids.csv", "cell_id", {"cell_type": "name"}, False),
]
# Parquet copies of web/data/atlas_PROT_lat128.csv: (path, tracked). Needs pyarrow.
PARQUETS = [("web/data/atlas_PROT_lat128.parquet", True), ("dist/site/data/atlas_PROT_lat128.parquet", False)]
# atlas_PROT_v3_meta.csv's size and sha256 are recorded in the app_export README. The
# export's own manifests (BUNDLE_MANIFEST.json, v3_export_manifest.json) keep the
# export's original file, as produced.
V3_META = "service/model/source/app_export/atlas_PROT_v3_meta.csv"
V3_META_README = "service/model/source/app_export/README.md"
V3_TABLES = datasets.REPO / "service" / "model" / "evidence" / "v3_tables"
# v3's SCoPE2 evidence that depends on the labels: (file, row key column, row key, column) -> metric name.
EVIDENCE = {
    ("latent_centroid_cosine.csv", "class_idx", "10", "n_prot_cells"): "n_macrophage",
    ("latent_centroid_cosine.csv", "class_idx", "10", "latent_centroid_cosine"): "cosine_macrophage",
    ("latent_centroid_cosine.csv", "class_idx", "12", "n_prot_cells"): "n_monocyte",
    ("latent_centroid_cosine.csv", "class_idx", "12", "latent_centroid_cosine"): "cosine_monocyte",
    ("support_restricted_assignment.csv", "regime", "unrestricted, all 22 classes", "accuracy_pct"): "unrestricted_acc",
    ("support_restricted_assignment.csv", "regime", "unrestricted, all 22 classes", "balanced_acc_pct"): "unrestricted_bal",
    ("support_restricted_assignment.csv", "regime", "restricted to cross modal supported classes", "accuracy_pct"): "restricted_acc",
    ("support_restricted_assignment.csv", "regime", "restricted to cross modal supported classes", "balanced_acc_pct"): "restricted_bal",
    ("support_restricted_assignment.csv", "regime", "restricted, threshold tuned on the margin", "balanced_acc_pct"): "tuned_bal",
    ("zero_shot_all_datasets.csv", "dataset", "SCoPE2", "acc"): "unrestricted_acc",
    ("zero_shot_all_datasets.csv", "dataset", "SCoPE2", "auc"): "auc",
}


def check_hashes() -> None:
    for name, (path, digest) in FILES.items():
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != digest:
            raise ValueError(f"{path} changed: sha256 {got}, registered {digest}")


def curated_labels() -> pd.DataFrame:
    """SCoPE2 id and cell type from the curated object, via base R."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "celltype.csv"
        code = (f"e <- new.env(); nm <- load('{FILES['curated'][0].as_posix()}', envir = e); x <- get(nm[1], envir = e); "
                "cd <- attr(x, 'colData'); ld <- attr(cd, 'listData'); "
                f"write.csv(data.frame(scope2_id = attr(cd, 'rownames'), curated = ld[['celltype']]), '{out.as_posix()}', row.names = FALSE)")
        subprocess.run([str(RSCRIPT), "-e", code], check=True, capture_output=True)
        return pd.read_csv(out)


def marker_shift(matrix: pd.DataFrame, labels: np.ndarray, genes: list[str]) -> dict:
    present = [g for g in genes if g in matrix.columns]
    d = matrix.loc[labels == "macrophage", present].mean() - matrix.loc[labels == "monocyte", present].mean()
    d = d.dropna()
    return {"genes": len(d), "mean_macrophage_minus_monocyte": round(float(d.mean()), 4),
            "higher_in_macrophages": int((d > 0).sum())}


def main() -> None:
    check_hashes()
    cur = curated_labels()
    ids = pd.read_csv(FILES["id_map"][0], sep="\t")
    previous = pd.read_csv(FILES["previous"][0], sep="\t", usecols=["Cell_ID", "cell_type"])
    if list(previous["Cell_ID"]) != [f"Prot_Blood_{i + 1}" for i in range(len(previous))]:
        raise ValueError("the previous copy's rows are not Prot_Blood_1..N in order")
    table = (previous.rename(columns={"Cell_ID": "vivome_id", "cell_type": "previous"})
             .merge(ids.rename(columns={"old_Cell_ID": "scope2_id", "new_Cell_ID": "vivome_id"}), on="vivome_id", how="left")
             .merge(cur, on="scope2_id", how="left"))
    if table["curated"].isna().any():
        raise ValueError(f"{int(table['curated'].isna().sum())} cells have no curated label")
    table.insert(0, "orig_index", np.arange(len(table)))
    table["label"] = table["curated"].str.lower()
    table["class_idx"] = table["label"].map(CLASS_IDX)
    agree = int((table["label"] == table["previous"]).sum())

    from benchmark import baselines_v31
    pub = baselines_v31.scope2_raw()
    published = pd.DataFrame(pub.values.T, columns=[g.upper() for g in pub.gene_names])
    reprocessed = datasets.load_scope2_reprocessed_upload()
    rep = pd.DataFrame(reprocessed.values.T, columns=[g.upper() for g in reprocessed.gene_names])
    rep_labels = datasets.load_scope2_reprocessed_labels()["label"].to_numpy()
    record = {
        "cells": len(table),
        "curated_counts": table["curated"].value_counts().to_dict(),
        "previous_counts": table["previous"].value_counts().to_dict(),
        "previous_agrees_with_curated": agree,
        "markers": {
            "published matrix, previous labels": {"proliferation": marker_shift(published, table["previous"].to_numpy(), PROLIFERATION),
                                                  "macrophage": marker_shift(published, table["previous"].to_numpy(), MACROPHAGE)},
            "published matrix, corrected labels": {"proliferation": marker_shift(published, table["label"].to_numpy(), PROLIFERATION),
                                                   "macrophage": marker_shift(published, table["label"].to_numpy(), MACROPHAGE)},
            "reprocessed evidence, design labels": {"proliferation": marker_shift(rep, rep_labels, PROLIFERATION),
                                                    "macrophage": marker_shift(rep, rep_labels, MACROPHAGE)},
        },
        "sources": {name: {"file": path.name, "sha256": digest} for name, (path, digest) in FILES.items()},
        "curated_source": "Bioconductor SingleCellMultiModal, macrophage_protein (ExperimentHub EH4694)",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    table[["orig_index", "vivome_id", "scope2_id", "curated", "previous", "label", "class_idx"]].to_csv(
        OUT / "corrected_labels.csv", index=False, lineterminator="\n")
    (OUT / "check.json").write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    print(json.dumps(record, indent=1))


def field_spans(line: str) -> list[tuple[int, int]]:
    """(start, end) of each field of one CSV line, quotes included."""
    spans, start, quoted = [], 0, False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == "," and not quoted:
            spans.append((start, i))
            start = i + 1
    spans.append((start, len(line)))
    return spans


def unquote(field: str) -> str:
    return field[1:-1].replace('""', '"') if field.startswith('"') else field


def edit_csv(path: Path, edit) -> tuple[bytes, int]:
    """A CSV with some fields replaced, every other byte (line endings, quoting,
    number formats) unchanged. edit(row) gets {column: unquoted value} and
    returns {column: new value}; new values need no quoting. Returns the new
    bytes and the number of rows changed."""
    text = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    header = next(csv.reader([lines[0]]))
    changed = 0
    for n in range(1, len(lines)):
        line = lines[n]
        if not line:
            continue
        if "\r" in line or '"' in line and line.count('"') % 2:
            raise ValueError(f"{path}: line {n + 1} is not one plain CSV record")
        spans = field_spans(line)
        if len(spans) != len(header):
            raise ValueError(f"{path}: line {n + 1} has {len(spans)} fields, the header {len(header)}")
        new = edit({h: unquote(line[a:b]) for h, (a, b) in zip(header, spans)})
        for col in sorted(new, key=header.index, reverse=True):
            if any(ch in new[col] for ch in ',"\r\n'):
                raise ValueError(f"{new[col]!r} would need quoting")
            a, b = spans[header.index(col)]
            line = line[:a] + new[col] + line[b:]
        if line != lines[n]:
            lines[n] = line
            changed += 1
    return eol.join(lines).encode("utf-8"), changed


def apply_copy(copy: Copy, table: pd.DataFrame) -> int:
    """Puts the corrected labels into one copy; returns the rows changed."""
    as_text = {"name": str, "idx": lambda label: str(CLASS_IDX[label])}
    seen = []

    def edit(row: dict) -> dict:
        i = int(row[copy.row])
        seen.append(i)
        out = {}
        for col, kind in copy.columns.items():
            want, old = as_text[kind](table.at[i, "label"]), as_text[kind](table.at[i, "previous"])
            if row[col] not in (want, old):
                raise ValueError(f"{copy.path}: cell {i} has {col} {row[col]!r}, neither the previous {old!r} nor the corrected {want!r}")
            out[col] = want
        return out

    path = datasets.REPO / copy.path
    new, changed = edit_csv(path, edit)
    if seen != list(range(len(table))):
        raise ValueError(f"{copy.path}: its rows are not cells 0..{len(table) - 1} in order")
    if changed:
        path.write_bytes(new)
    return changed


def apply_parquet(rel: str, table: pd.DataFrame) -> int:
    """Puts the corrected class_idx and class_name into a Parquet copy of the
    atlas. Every other column must read back identical, or nothing is written.
    Returns the rows changed."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = datasets.REPO / rel
    before = pq.read_table(path)
    if before.column("orig_index").to_pylist() != list(range(len(table))):
        raise ValueError(f"{rel}: its rows are not cells 0..{len(table) - 1} in order")
    want = {"class_name": table["label"].tolist(), "class_idx": [int(v) for v in table["class_idx"]]}
    old = {"class_name": table["previous"].tolist(), "class_idx": [CLASS_IDX[v] for v in table["previous"]]}
    now = {c: before.column(c).to_pylist() for c in want}
    for i in range(len(table)):
        if (now["class_name"][i], now["class_idx"][i]) not in ((want["class_name"][i], want["class_idx"][i]),
                                                              (old["class_name"][i], old["class_idx"][i])):
            raise ValueError(f"{rel}: cell {i} has {now['class_name'][i]!r} / {now['class_idx'][i]}")
    changed = sum(now["class_name"][i] != want["class_name"][i] for i in range(len(table)))
    if not changed:
        return 0
    after = before
    for c, values in want.items():
        field = before.schema.field(c)
        after = after.set_column(before.schema.get_field_index(c), field, pa.array(values, type=field.type))
    tmp = path.with_suffix(".tmp.parquet")
    pq.write_table(after, tmp, compression="snappy", row_group_size=len(table), version="2.6")
    back = pq.read_table(tmp)
    others = [c for c in before.column_names if c not in want]
    if not (back.select(others).equals(before.select(others)) and back.schema.metadata == before.schema.metadata
            and all(back.column(c).to_pylist() == v for c, v in want.items())):
        tmp.unlink()
        raise ValueError(f"{rel}: the rewritten file does not read back as intended")
    os.replace(tmp, path)
    return changed


def v3_metrics(y: np.ndarray) -> dict:
    """v3's SCoPE2 evidence for labels y (class positions), from v3's saved
    latents, as the export notebook computed it
    (service/model/source/VivOME_Prototype_Export.ipynb, sections C and E)."""
    import warnings
    model = datasets.REPO / "service" / "model"
    z = np.load(model / "source" / "app_export" / "prot_embedding_scope2.npy")
    centroids = np.load(model / "runtime" / "reference_centroids.npy")
    s = (z / np.linalg.norm(z, axis=1, keepdims=True)) @ centroids.T
    mac, mon = CLASS_IDX["macrophage"], CLASS_IDX["monocyte"]
    pred = s.argmax(1)
    pred_r = np.array([mac, mon])[s[:, [mac, mon]].argmax(1)]
    margin = s[:, mac] - s[:, mon]
    is_mac = (y == mac).astype(int)
    grid = np.quantile(margin, np.linspace(0.01, 0.99, 199))
    out = {}
    for name, ci in (("macrophage", mac), ("monocyte", mon)):
        c = z[y == ci].mean(0)
        out[f"n_{name}"] = int((y == ci).sum())
        out[f"cosine_{name}"] = float(c / (np.linalg.norm(c) + 1e-12) @ centroids[ci])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # y_pred has classes y_true lacks; sklearn warns and averages over y_true's
        out.update(
            unrestricted_acc=100 * float((pred == y).mean()), unrestricted_bal=100 * float(balanced_accuracy_score(y, pred)),
            restricted_acc=100 * float((pred_r == y).mean()), restricted_bal=100 * float(balanced_accuracy_score(y, pred_r)),
            tuned_bal=max(100 * float(balanced_accuracy_score(is_mac, (margin > t).astype(int))) for t in grid),
            auc=float(roc_auc_score(is_mac, margin)))
    return out


def apply_evidence(table: pd.DataFrame) -> dict:
    """Rewrites v3's label-dependent SCoPE2 evidence (EVIDENCE) with the
    corrected labels. Each value must first match the previous labels' value
    recomputed from v3's latents (1e-6), or already be the corrected one."""
    previous = v3_metrics(table["previous"].map(CLASS_IDX).to_numpy())
    corrected = v3_metrics(table["class_idx"].to_numpy())
    done = {}
    for name in sorted({k[0] for k in EVIDENCE}):
        wanted = {(key_col, key, col): metric for (file, key_col, key, col), metric in EVIDENCE.items() if file == name}
        hits = []

        def edit(row: dict) -> dict:
            out = {}
            for (key_col, key, col), metric in wanted.items():
                if row[key_col] != key:
                    continue
                now = float(row[col])
                if not (abs(now - previous[metric]) <= 1e-6 or abs(now - corrected[metric]) <= 1e-6):
                    raise ValueError(f"{name}: {key} {col} is {now}, neither v3's previous {previous[metric]} nor corrected {corrected[metric]}")
                out[col] = str(corrected[metric]) if isinstance(corrected[metric], int) else repr(corrected[metric])
                if abs(now - corrected[metric]) <= 1e-6 and abs(corrected[metric] - previous[metric]) > 1e-6:
                    out[col] = row[col]  # already corrected: keep its bytes
                hits.append((key_col, key, col))
            return out

        new, changed = edit_csv(V3_TABLES / name, edit)
        if sorted(hits) != sorted(wanted):
            raise ValueError(f"{name}: expected each of {sorted(wanted)} once, found {sorted(hits)}")
        if changed:
            (V3_TABLES / name).write_bytes(new)
        done[name] = changed
    return {"rows_changed": done, "previous": previous, "corrected": corrected}


def record_v3_meta() -> str:
    """The app_export README's size and sha256 for atlas_PROT_v3_meta.csv."""
    import re
    data = (datasets.REPO / V3_META).read_bytes()
    readme = datasets.REPO / V3_META_README
    text = readme.read_bytes().decode("utf-8")
    pattern = r"(\| `atlas_PROT_v3_meta\.csv` \| )[\d,]+( \| `)[0-9a-f]{64}(`)"
    if len(re.findall(pattern, text)) != 1:
        raise ValueError(f"{V3_META_README}: no single atlas_PROT_v3_meta.csv row")
    digest = hashlib.sha256(data).hexdigest()
    readme.write_bytes(re.sub(pattern, lambda m: f"{m[1]}{len(data):,}{m[2]}{digest}{m[3]}", text).encode("utf-8"))
    return digest


def apply() -> None:
    table = pd.read_csv(LABELS)
    if list(table["orig_index"]) != list(range(len(table))):
        raise ValueError(f"{LABELS} is not in orig_index order")
    report = {}
    for copy in COPIES:
        if not (datasets.REPO / copy.path).exists():
            if copy.tracked:
                raise FileNotFoundError(copy.path)
            report[copy.path] = "absent (local copy)"
            continue
        report[copy.path] = f"{apply_copy(copy, table)} rows changed"
    for rel, tracked in PARQUETS:
        if not (datasets.REPO / rel).exists():
            if tracked:
                raise FileNotFoundError(rel)
            report[rel] = "absent (local copy)"
            continue
        report[rel] = f"{apply_parquet(rel, table)} rows changed"
    report[V3_META_README] = f"sha256 {record_v3_meta()}"
    evidence = apply_evidence(table)
    report.update({f"evidence/v3_tables/{k}": f"{v} rows changed" for k, v in evidence["rows_changed"].items()})
    print(json.dumps(report, indent=1))
    print(json.dumps({"v3 previous": evidence["previous"], "v3 corrected": evidence["corrected"]}, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="put the corrected labels into every copy")
    if parser.parse_args().apply:
        apply()
    else:
        main()
