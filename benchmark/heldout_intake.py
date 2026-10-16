"""The internal held-out test, steps 2 and 3 of the unsealing
(research/benchmark/protocol-heldout.md): the label map, then the intake. For
the five protein sets; the Hao 2021 suite has its own. Written and rehearsed
before any held-out file was opened.

    python -m benchmark.heldout_intake SET --rehearse      # development data or a synthetic file, any time
    python -m benchmark.heldout_intake SET --labels         # Phase 3 only: the label map, once
    python -m benchmark.heldout_intake SET --labels --label-map CSV --reason TEXT
                                                            # a map written by hand by the same rules
    python -m benchmark.heldout_intake SET                  # Phase 3 only: the intake, once

SET is tian, pxd021882, pxd043355, pxd073250 or pxd046211.

The label map lists the included samples only: cell_id, upload, sample, group,
scored, and the set's keys (patient and state, line, gate, file and channel).
The intake builds each upload from the map (protocol, per set), checks every
input file against its download record and the frozen models against the
protocol, records label-free facts, runs every candidate as served
(pipeline.run_projection), recomputes the per-class best-guess probabilities
with the service's own functions (class_probabilities; the argmax must equal
the served best guess), and writes the baselines' query matrix.

Writes benchmark/results/heldout_<set>/ (heldout_<set>_rehearsal/ when
rehearsing): label_map.csv, labels.json, intake.json, cell_ids.txt,
<model>_pred.csv, <model>_probs.npz, query_benchmark.npz.
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
from benchmark.khoury2026_embed import refuse_overrides
from benchmark.sorted_cd4cd8_intake import benchmark_matrix, check_frozen, load_bundle, sha256
from service.pipeline import alignment, ensemble, fusion, pipeline

REPO = datasets.REPO
RESULTS = REPO / "benchmark" / "results"
PUBLIC = REPO / "data" / "incoming" / "public_sets"
DOWNLOADS = REPO / "research" / "benchmark" / "public-sets-downloads.json"
SETS = ("tian", "pxd021882", "pxd043355", "pxd073250", "pxd046211")
# The candidates (protocol, "Candidates"): v4.1 the headline, v4.2 and v5.2 frozen
# by protocol-sorted-cd4cd8.md amendment 3 (check_frozen), v3.1 for reference.
# A Phase 2 candidate joins only by amendment, with its files' sha256s.
MODELS = {"v31": "v3.1", "v41": "v4.1", "v42": "v4.2", "v52": "v5.2"}
INPUTS = {  # the deposit's files each set reads at unsealing, relative to PUBLIC
    "tian": ("Tian_MSV000087462/proteinGroupsCD3CD4CD8.xlsx", "Tian_MSV000087462/proteinGroupsMMsample.xlsx"),
    "pxd021882": ("PXD021882/proteinGroups.txt",),
    "pxd043355": ("PXD043355/HeLa_VS_Jurkat_Proteins.txt", "PXD043355/HeLa_VS_Jurkat_InputFiles.txt"),
    "pxd073250": ("PXD073250/report.pg_matrix.tsv", "PXD073250/LSA-2026-03759_Supplemental_Data_1.xlsx"),
    "pxd046211": ("PXD046211/quant.cbio.tsv", "PXD046211/sampleAnnotations.csv"),
}
SEALED_DIRS = ("Tian_MSV000087462", "PXD046211", "PXD043355", "PXD073250", "PXD021882")
RIECKMANN = PUBLIC / "Rieckmann2017_PXD004352" / "extracted" / "proteinGroups.txt"
DS18_ZOOM = PUBLIC / "PXD070599_PBMC" / "extracted" / "DS18" / "FAIMS_Astral-Zoom_MBR" / "report.pg_matrix.tsv"
LABEL_COLUMNS = ("cell_id", "upload", "sample", "group", "scored")


def out_dir(name: str, rehearse: bool) -> Path:
    return RESULTS / (f"heldout_{name}_rehearsal" if rehearse else f"heldout_{name}")


# ---- label rules (protocol, per set); pure functions of names and annotation tables ----

def tian_parse(sample: str) -> dict:
    """Lineage, state and patient from a sample name; "" where absent."""
    found = set(re.findall(r"(?<![0-9A-Za-z])CD\s*([348])(?![0-9])", sample, flags=re.IGNORECASE))
    lineage = "CD8" if found == {"8"} or found == {"3", "8"} else "CD4" if found == {"4"} or found == {"3", "4"} \
        else "CD3" if found == {"3"} else ""
    s = sample.lower()
    state = ("EMRA" if re.search(r"(?<![a-z])t?emra(?![a-z])", s) else
             "EM" if re.search(r"(?<![a-z])t?em(?![a-z])", s) else
             "CM" if re.search(r"(?<![a-z])t?cm(?![a-z])", s) else
             "naive" if re.search(r"naive|(?<![a-z])t?n(?![a-z])", s) else
             "memory" if "memory" in s else "none")
    m = re.search(r"(?:patient|pt|mm|p)[ _#-]?(\d+)", s)
    return {"lineage": lineage, "state": state, "patient": f"P{int(m.group(1))}" if m else ""}


def tian_label_rows(upload: str, samples: list[str]) -> tuple[list[dict], list[str]]:
    """(rows, unparsed): every sample with a lineage is included (CD3 too); CD4
    and CD8 samples with a patient are scored."""
    rows, unparsed = [], []
    for s in samples:
        p = tian_parse(s)
        if not p["lineage"]:
            unparsed.append(s)
            continue
        rows.append({"cell_id": f"{upload}:{s}", "upload": upload, "sample": s, "group": p["lineage"],
                     "scored": p["lineage"] in ("CD4", "CD8") and bool(p["patient"]),
                     "patient": p["patient"], "state": p["state"]})
    return rows, unparsed


def b_or_t(sample: str) -> str:
    s = sample.lower()
    b = bool(re.search(r"cd19|(?<![a-z])b[ _-]?cells?(?![a-z])|(?<![a-z0-9])b(?![a-z])", s))
    t = bool(re.search(r"cd3(?![0-9])|(?<![a-z])t[ _-]?cells?(?![a-z])|(?<![a-z0-9])t(?![a-z])", s))
    hela = "hela" in s
    return "" if hela or b == t else "B" if b else "T"


def cell_line(name: str) -> str:
    s = name.lower()
    jurkat, hela = "jurkat" in s, "hela" in s
    return "" if jurkat == hela else "Jurkat" if jurkat else "HeLa"


def gate(text: str) -> str:
    """immune (CD45+ CD74+), keratinocyte (CD45- CD200+), double (CD45+ CD200+); "" otherwise."""
    marks = {m.group(1): m.group(2) for m in re.finditer(r"CD(45|74|200)\s*([+-])", str(text), flags=re.IGNORECASE)}
    if marks.get("45") == "+" and marks.get("200") == "+":
        return "double"
    if marks.get("45") == "+" and marks.get("74") == "+":
        return "immune"
    if marks.get("45") == "-" and marks.get("200") == "+":
        return "keratinocyte"
    return ""


TMTPRO = ("126", "127N", "127C", "128N", "128C", "129N", "129C", "130N", "130C", "131N", "131C", "132N", "132C",
          "133N", "133C", "134N")


def tmt_channel(value) -> int:
    """sage's 1-based tmt_<n> for a TMTpro channel written as 126..134N, TMT<n>, tmt_<n> or RI<n>."""
    text = str(value).strip()
    tag = re.sub(r"^(tmtpro|tmt|ri|reporter[ ._]intensity)[ _.-]?", "", text, flags=re.IGNORECASE).upper()
    if tag in TMTPRO:
        return TMTPRO.index(tag) + 1
    if tag.isdigit() and 1 <= int(tag) <= 16:
        return int(tag)
    raise ValueError(f"channel {value!r} is not a TMTpro 16-plex channel")


def tmt_sample(sample_type: str, treatment: str) -> tuple[str, str]:
    """(line, group): line THP-1 or U-937 for a single cell of one line, "" for
    mixes, carriers, references, empty and blank wells; group PMA or untreated."""
    s = str(sample_type).lower()
    if re.search(r"mix|carrier|booster|ref|empty|blank|neg|control", s):
        return "", ""
    thp, u937 = bool(re.search(r"thp", s)), bool(re.search(r"u[ -]?937", s))
    if thp == u937:
        return "", ""
    t = f"{sample_type} {treatment}".lower()
    pma = bool(re.search(r"pma|macro|differentiat|(?<![a-z])m0(?![a-z])|treated", t)) and not re.search(r"untreated|no[ _-]?pma", t)
    return ("THP-1" if thp else "U-937"), ("PMA" if pma else "untreated")


def annotation_columns(df: pd.DataFrame) -> dict:
    """The annotation's file, channel, sample-type and treatment columns, by name."""
    def find(*patterns):
        for c in df.columns:
            if any(re.search(p, str(c), flags=re.IGNORECASE) for p in patterns):
                return c
        return None
    return {"file": find(r"file", r"raw", r"run"), "channel": find(r"channel", r"label", r"tmt"),
            "type": find(r"sampletype", r"sample[ ._]?type", r"cell[ ._]?(type|line)", r"^sample$"),
            "treatment": find(r"treat", r"condition", r"pma")}


def tmt_label_rows(annotation: pd.DataFrame) -> tuple[list[dict], dict]:
    cols = annotation_columns(annotation)
    if not cols["file"] or not cols["channel"] or not cols["type"]:
        raise ValueError(f"annotation columns not found: {cols}; columns {list(annotation.columns)}")
    rows, excluded = [], {}
    for _, r in annotation.iterrows():
        line, group = tmt_sample(r[cols["type"]], r[cols["treatment"]] if cols["treatment"] else "")
        if not line:
            key = str(r[cols["type"]])
            excluded[key] = excluded.get(key, 0) + 1
            continue
        file = formats.run_name(r[cols["file"]])
        channel = tmt_channel(r[cols["channel"]])
        rows.append({"cell_id": f"{file}_tmt{channel}", "upload": "all", "sample": f"{file}_tmt{channel}",
                     "group": group, "scored": True, "line": line, "file": file, "channel": channel})
    return rows, {"columns": cols, "excluded_by_type": excluded}


# ---- the real label maps (Phase 3 only) ----

def _check_download(rel: str) -> str:
    record = json.loads(DOWNLOADS.read_text(encoding="utf-8"))
    want = record[rel]["sha256"]
    got = sha256(PUBLIC / rel)
    if got != want:
        raise SystemExit(f"{rel}: sha256 {got} differs from the download record {want}")
    return got


def real_label_map(name: str) -> tuple[pd.DataFrame, dict]:
    files = {rel: _check_download(rel) for rel in INPUTS[name]}
    paths = [PUBLIC / rel for rel in INPUTS[name]]
    info: dict = {"inputs_sha256": files}
    if name == "tian":
        rows = []
        for path in paths:
            samples = formats.read_maxquant(path).samples
            got, unparsed = tian_label_rows(path.stem, samples)
            lineages = {r["group"] for r in got}
            info[path.name] = {"samples": len(samples), "unparsed": unparsed, "lineages": sorted(lineages)}
            if unparsed:
                raise SystemExit(f"{path.name}: samples without a lineage {unparsed}; write the map by hand "
                                 "(--label-map, --reason) by the protocol's rules")
            if {"CD4", "CD8"} <= lineages:
                rows += got
            else:
                info[path.name]["used"] = False
        return pd.DataFrame(rows), info
    if name == "pxd021882":
        samples = formats.read_maxquant(paths[0]).samples
        rows = [{"cell_id": s, "upload": "all", "sample": s, "group": g, "scored": True}
                for s in samples if (g := b_or_t(s))]
        info["excluded_samples"] = [s for s in samples if not b_or_t(s)]
        return pd.DataFrame(rows, columns=LABEL_COLUMNS), info
    if name == "pxd043355":
        files = pd.read_csv(paths[1], sep="\t", dtype=str)
        files.columns = [str(c).strip().strip('"') for c in files.columns]
        names = files[formats.PD["file_name"]].map(formats._sample_name).tolist()
        rows = [{"cell_id": n, "upload": "all", "sample": n, "group": g, "scored": True} for n in names if (g := cell_line(n))]
        info["excluded_files"] = [n for n in names if not cell_line(n)]
        return pd.DataFrame(rows, columns=LABEL_COLUMNS), info
    if name == "pxd073250":
        cells = formats.read_dia_nn(paths[0]).samples
        return gate_label_rows(cells, pd.read_excel(paths[1], sheet_name=None), info)
    if name == "pxd046211":
        rows, found = tmt_label_rows(pd.read_csv(paths[1], dtype=str))
        info.update(found)
        return pd.DataFrame(rows), info
    raise ValueError(name)


def gate_label_rows(cells: list[str], sheets: dict, info: dict) -> tuple[pd.DataFrame, dict]:
    """The sheet whose column names the most matrix runs, and its gate column
    (a column naming CD45/CD74/CD200 with + or -, or one text column holding
    them). Runs without a gate are left out of the upload."""
    key = {c.lower(): c for c in cells}
    best = None
    for sheet, df in sheets.items():
        for col in df.columns:
            names = df[col].astype(str).map(lambda v: formats._sample_name(v).lower())
            hits = int(names.isin(key).sum())
            if hits and (best is None or hits > best[0]):
                best = (hits, sheet, col)
    if best is None:
        raise SystemExit("no sheet names the matrix's runs; write the map by hand (--label-map, --reason)")
    _, sheet, col = best
    df = sheets[sheet]
    marker_cols = [c for c in df.columns if re.search(r"CD(45|74|200)", str(c), flags=re.IGNORECASE)]
    if marker_cols:
        text = df[marker_cols].astype(str).apply(lambda r: " ".join(f"{c}{v}" if v.strip() in "+-" else v for c, v in r.items()), axis=1)
    else:
        text = df.astype(str).apply(lambda r: " ".join(r.values), axis=1)
    rows, ungated = [], []
    for run, t in zip(df[col].astype(str), text):
        cell = key.get(formats._sample_name(run).lower())
        if cell is None:
            continue
        g = gate(t)
        if not g:
            ungated.append(cell)
            continue
        rows.append({"cell_id": cell, "upload": "all", "sample": cell, "group": g, "scored": g != "double"})
    mapped = {r["cell_id"] for r in rows}
    info.update({"sheet": str(sheet), "run_column": str(col), "gate_columns": [str(c) for c in marker_cols],
                 "runs_without_gate": sorted(set(cells) - mapped)})
    return pd.DataFrame(rows, columns=LABEL_COLUMNS), info


# ---- the uploads ----

def build_uploads(name: str, labels: pd.DataFrame, sources: dict) -> tuple[dict, dict]:
    """{upload: RawMatrix} in label-map order, and the readers' records."""
    uploads, records = {}, {}
    if name == "pxd046211":
        channels = {(formats.run_name(r.file), int(r.channel)): r.cell_id for r in labels.itertuples()}
        table_ = formats.read_sage_tmt(sources["quant"], channels)
        records["all"] = table_.record
        uploads["all"] = table_.raw(labels["cell_id"].tolist())
        return uploads, records
    for upload, rows in labels.groupby("upload", sort=False):
        table_ = sources["tables"][upload]
        raw = table_.raw(rows["sample"].tolist())
        uploads[upload] = alignment.RawMatrix(gene_names=raw.gene_names, cell_ids=rows["cell_id"].tolist(),
                                              values=raw.values)
        records[upload] = table_.record
    return uploads, records


def real_sources(name: str, labels: pd.DataFrame) -> dict:
    paths = [PUBLIC / rel for rel in INPUTS[name]]
    if name == "tian":
        return {"tables": {p.stem: formats.read_maxquant(p) for p in paths if p.stem in set(labels["upload"])}}
    if name == "pxd021882":
        return {"tables": {"all": formats.read_maxquant(paths[0])}}
    if name == "pxd043355":
        return {"tables": {"all": formats.read_proteome_discoverer(paths[0], paths[1])}}
    if name == "pxd073250":
        return {"tables": {"all": formats.read_dia_nn(paths[0])}}
    if name == "pxd046211":
        return {"quant": paths[0]}
    raise ValueError(name)


# ---- the models ----

def class_probabilities(bundle, raw: alignment.RawMatrix) -> np.ndarray:
    """The per-class probabilities the served best guess ranks (cells x
    classes): v3.1's ensemble probabilities, or v4.x's and v5.2's fused
    best-guess probabilities (with v4.2's protein term), each over the label
    space as served."""
    smoothed, aligned, _ = pipeline._prepare_query(bundle.feature_genes, raw)
    components = bundle.components
    if bundle.pipeline_version == "v3.1":
        members, names = bundle.members, bundle.class_names
        embeddings = [m.encoder_handle.encode(smoothed, aligned.mask) for m in members]
        probs = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature)
                                                 for z, m in zip(embeddings, members)])
    else:
        answers, names = bundle.answers, bundle.answers.class_names
        embeddings = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
        all_probs = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature)
                                                     for z, m in zip(embeddings, answers.members)])
        counted = aligned.per_cell_observed_genes >= int(bundle.spec["preprocessing"]["min_observed_genes"])
        protein = fusion.protein_query(raw, bundle.protein_genes) if getattr(bundle, "protein_means", None) is not None else None
        probs = fusion.best_guess_probabilities(bundle, embeddings, aligned.values, aligned.mask, all_probs, counted,
                                                protein).probabilities
    space = components.label_space.estimate(None, list(names), False)
    return components.label_space.probabilities(probs, space)


def run_models(uploads: dict, out: Path) -> dict:
    runs = {}
    for key, version in MODELS.items():
        bundle = load_bundle(version)
        names = list(bundle.class_names)
        tables, probs = [], []
        for upload, raw in uploads.items():
            response = pipeline.run_projection(bundle, raw)
            p = class_probabilities(bundle, raw)
            t = table(response)
            t.insert(1, "upload", upload)
            t["reference_similarity"] = [c["reference_similarity"] for c in response["cells"]]
            served = t["best_guess"].to_numpy()
            mine = np.array(names)[p.argmax(axis=1)]
            has = served != ""
            if not np.array_equal(served[has], mine[has]):
                raise SystemExit(f"{version}: the recomputed probabilities' argmax differs from the served best guess "
                                 f"on {int((served[has] != mine[has]).sum())} cells")
            tables.append(t)
            probs.append(p)
            runs.setdefault(key, {"pipeline_version": response["pipeline_version"],
                                  "model_version": response["model_version"], "uploads": {}})
            runs[key]["uploads"][upload] = {"n_cells": response["n_cells"],
                                            "n_features_matched": response["n_features_matched"]}
        pd.concat(tables).to_csv(out / f"{key}_pred.csv", index=False, lineterminator="\n")
        np.savez_compressed(out / f"{key}_probs.npz", probs=np.vstack(probs).astype(np.float32),
                            class_names=np.array(names, dtype=object))
    return runs


def facts(raw: alignment.RawMatrix) -> dict:
    observed = np.isfinite(raw.values)
    return {"cells": len(raw.cell_ids), "proteins": len(raw.gene_names),
            "missing_pct": round(100 * float(1 - observed.mean()), 2),
            "proteins_per_cell_median": int(np.median(observed.sum(axis=0)))}


def intake(name: str, labels: pd.DataFrame, sources: dict, out: Path, source_record: dict) -> dict:
    labels = labels.reset_index(drop=True)
    frozen = check_frozen()
    uploads, readers = build_uploads(name, labels, sources)
    cell_ids = [c for raw in uploads.values() for c in raw.cell_ids]
    if cell_ids != labels["cell_id"].tolist():
        raise SystemExit("the uploads' cells are not in label-map order")
    (out / "cell_ids.txt").write_text("\n".join(cell_ids) + "\n", encoding="utf-8")
    runs = run_models(uploads, out)
    matrix = np.vstack([benchmark_matrix(raw) for raw in uploads.values()])
    np.savez_compressed(out / "query_benchmark.npz", x=matrix, cell_ids=np.array(cell_ids, dtype=object))
    record = {"protocol": "research/benchmark/protocol-heldout.md", "set": name, "rehearsal": "rehearsal" in out.name,
              "source": source_record, "readers": readers, "frozen_files": frozen,
              "label_free_facts": {u: facts(raw) for u, raw in uploads.items()}, "runs": runs,
              "outputs": {p.name: sha256(p) for p in sorted(out.iterdir()) if p.suffix in (".csv", ".txt", ".npz")}}
    (out / "intake.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return record


def write_labels(labels: pd.DataFrame, out: Path, info: dict) -> str:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "label_map.csv"
    labels.to_csv(path, index=False, lineterminator="\n")
    digest = sha256(path)
    counts = labels.groupby("group")["scored"].agg(["size", "sum"]).astype(int)
    (out / "labels.json").write_text(json.dumps({
        "label_map_sha256": digest, "rows": len(labels),
        "groups": {g: {"included": int(r["size"]), "scored": int(r["sum"])} for g, r in counts.iterrows()},
        **info}, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    return digest


# ---- rehearsals (development data or synthetic files; nothing held out) ----

def _rieckmann_samples(pattern: str) -> list[str]:
    header = formats._header(RIECKMANN)
    return sorted({m.group(1) for c in header if (m := re.match(r"^LFQ\.intensity\.(.+ \(steady-state\))$", c))
                   and re.match(pattern, m.group(1))})


def rehearse_tian(out: Path) -> tuple[pd.DataFrame, dict, dict]:
    samples = _rieckmann_samples(r"^(T4|T8)\.(naive|CM|EM|EMRA)_\d\d|^(Th1|Th2|Th17|nTregs|mTregs)_\d\d")
    rows = []
    for s in samples:
        m = re.match(r"^(T4|T8)\.(naive|CM|EM|EMRA)_(\d\d)", s)
        donor = re.search(r"_(\d\d) ", s).group(1)
        if m:
            rows.append({"cell_id": f"rieckmann:{s}", "upload": "rieckmann", "sample": s,
                         "group": "CD4" if m.group(1) == "T4" else "CD8", "scored": True,
                         "patient": f"D{donor}", "state": m.group(2)})
        else:
            rows.append({"cell_id": f"rieckmann:{s}", "upload": "rieckmann", "sample": s, "group": "CD4",
                         "scored": False, "patient": f"D{donor}", "state": "none"})
    table_ = formats.read_maxquant(RIECKMANN, samples=set(samples))
    return pd.DataFrame(rows), {"tables": {"rieckmann": table_}}, {"dataset": "Rieckmann 2017 (development)",
                                                                       "file": RIECKMANN.name}


def rehearse_pxd021882(out: Path) -> tuple[pd.DataFrame, dict, dict]:
    samples = _rieckmann_samples(r"^B\.(naive|memory)_\d\d|^(T4|T8)\.(naive|CM|EM|EMRA)_\d\d")
    rows = [{"cell_id": s, "upload": "all", "sample": s, "group": "B" if s.startswith("B.") else "T", "scored": True}
            for s in samples]
    table_ = formats.read_maxquant(RIECKMANN, samples=set(samples))
    return pd.DataFrame(rows, columns=LABEL_COLUMNS), {"tables": {"all": table_}}, \
        {"dataset": "Rieckmann 2017 (development): B and conventional T populations as pools", "file": RIECKMANN.name}


def _scramble(values: np.ndarray, rng) -> np.ndarray:
    out = values.copy()
    for j in range(out.shape[1]):
        seen = np.flatnonzero(np.isfinite(out[:, j]))
        out[seen, j] = out[rng.permutation(seen), j]
    return out


def write_pd(raw: alignment.RawMatrix, names: list[str], directory: Path) -> tuple[Path, Path]:
    """A Proteome Discoverer 3.0-style protein table and input-file table holding `raw` (linear values)."""
    n = len(raw.cell_ids)
    df = pd.DataFrame({"Checked": False, "Protein FDR Confidence: Combined": "High", "Master": "IsMasterProtein",
                       "Accession": [f"ACC{i:05d}" for i in range(len(raw.gene_names))],
                       "Description": [f"protein {g} OS=Homo sapiens OX=9606 GN={g} PE=1 SV=1" for g in raw.gene_names],
                       "Contaminant": False})
    for k in range(n):
        df[f"Abundance: F{k + 1}: Sample"] = raw.values[:, k]
    for k in range(n):
        df[f"Abundances (Normalized): F{k + 1}: Sample"] = raw.values[:, k]
    decoy = df.iloc[:3].copy()
    decoy["Master"] = "IsMasterProteinCandidate"
    proteins = directory / "synthetic_Proteins.txt"
    pd.concat([df, decoy]).to_csv(proteins, sep="\t", index=False, lineterminator="\n")
    files = directory / "synthetic_InputFiles.txt"
    pd.DataFrame({"File ID": [f"F{k + 1}" for k in range(n)],
                  "File Name": [f"D:\\data\\{nm}.raw" for nm in names]}).to_csv(files, sep="\t", index=False,
                                                                                lineterminator="\n")
    return proteins, files


def rehearse_pxd043355(out: Path) -> tuple[pd.DataFrame, dict, dict]:
    pbmc = alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text())
    meta = pd.read_csv(RESULTS / "pbmc_meta.csv")
    lineage = dict(zip(meta["cell_id"], meta["weak_lineage"]))
    rng = np.random.default_rng(0)
    lymphoid = [i for i, c in enumerate(pbmc.cell_ids) if lineage.get(c) == "lymphoid"]
    other = [i for i in range(len(pbmc.cell_ids)) if i not in set(lymphoid)]
    pick_t = rng.choice(lymphoid, 30, replace=False)
    pick_f = rng.choice(other, 24, replace=False)
    values = np.hstack([pbmc.values[:, pick_t], _scramble(pbmc.values[:, pick_f], rng)])
    names = [f"20230101_SC_Jurkat_{k + 1:02d}" for k in range(30)] + [f"20230101_SC_HeLa_{k + 1:02d}" for k in range(24)]
    written = alignment.RawMatrix(gene_names=[formats.first_symbol(g) for g in pbmc.gene_names], cell_ids=names,
                                  values=values)
    keep = np.array([g != "" for g in written.gene_names])
    written = alignment.RawMatrix(gene_names=[g for g, k in zip(written.gene_names, keep) if k], cell_ids=names,
                                  values=written.values[keep])
    proteins, files = write_pd(written, names, out)
    table_ = formats.read_proteome_discoverer(proteins, files)
    same = table_.samples == names and table_.genes == written.gene_names and \
        np.array_equal(np.isnan(table_.values), np.isnan(np.where(written.values > 0, written.values, np.nan))) and \
        np.allclose(np.nan_to_num(table_.values), np.nan_to_num(np.where(written.values > 0, written.values, np.nan)))
    if not same:
        raise SystemExit("the Proteome Discoverer reader does not reproduce the matrix it was given")
    rows = [{"cell_id": n, "upload": "all", "sample": n, "group": g, "scored": True} for n in table_.samples
            if (g := cell_line(n))]
    return pd.DataFrame(rows, columns=LABEL_COLUMNS), {"tables": {"all": table_}}, {
        "dataset": "synthetic Proteome Discoverer files from PBMC240 (development): 30 lymphoid cells as 'Jurkat', "
                   "24 other cells with values shuffled among their proteins as 'HeLa'",
        "reader_reproduces_matrix": True}


def rehearse_pxd073250(out: Path) -> tuple[pd.DataFrame, dict, dict]:
    df = pd.read_csv(DS18_ZOOM, sep="\t", low_memory=False)
    runs = [c for c in df.columns if c.lower().endswith(".raw") or ".raw" in c.lower()]
    rng = np.random.default_rng(0)
    scrambled_from = rng.choice(len(runs), 40, replace=False)
    values = df[runs].to_numpy(dtype=np.float64)
    extra = _scramble(values[:, scrambled_from], rng)
    new_runs = [f"E:\\rehearsal\\SC_keratinocyte_{k + 1:02d}.raw" for k in range(40)]
    df2 = pd.concat([df, pd.DataFrame(extra, columns=new_runs, index=df.index)], axis=1)
    matrix = out / "synthetic_report.pg_matrix.tsv"
    df2.to_csv(matrix, sep="\t", index=False, lineterminator="\n", na_rep="")
    cells = [alignment._clean_dia_nn_cell_id(r) for r in runs + new_runs]
    gates = (["CD45+ CD74+"] * 76 + ["CD45+ CD200+"] * 10 + [None] * 5)[:len(runs)] + ["CD45- CD200+"] * 40
    sheet = pd.DataFrame({"Run": [c + ".raw" for c in cells], "Population": gates})
    table_ = formats.read_dia_nn(matrix)
    labels, info = gate_label_rows(table_.samples, {"cells": sheet.dropna()}, {})
    return labels, {"tables": {"all": table_}}, {
        "dataset": "PXD070599 DS18 FAIMS Astral-Zoom (development) as 'immune' or 'double' cells, 40 of them with "
                   "values shuffled among their proteins as 'keratinocyte'; a stand-in gate table",
        "gate_table": info}


def write_sage(upload: alignment.RawMatrix, labels: pd.DataFrame, directory: Path, rng) -> Path:
    """sage-style PSM rows: per run and gene, two PSMs whose single-cell channels
    are 2^(cell value + peptide offset); carrier 50x the mean; a decoy-level PSM
    per run that the q-value filter must drop."""
    gene_pos = {g: i for i, g in enumerate(upload.gene_names)}
    cell_pos = {c: i for i, c in enumerate(upload.cell_ids)}
    rows = []
    for file, members in labels.groupby("file", sort=False):
        cols = [cell_pos[c] for c in members["cell_id"]]
        block = upload.values[:, cols]
        seen = np.isfinite(block).any(axis=1)
        for g in np.flatnonzero(seen):
            for psm in range(2):
                offset = rng.normal(14, 1)
                row = {"filename": f"{file}.mzML", "scannr": f"scan={len(rows)}",
                       "proteins": f"sp|{upload.gene_names[g]}|{upload.gene_names[g]}_HUMAN",
                       "spectrum_q": 0.001, "peptide_q": 0.001, "protein_q": 0.001}
                vals = np.full(16, 0.0)
                for ch, k in zip(members["channel"], range(len(cols))):
                    v = block[g, k]
                    vals[int(ch) - 1] = 2 ** (v + offset) if np.isfinite(v) else 0.0
                vals[0] = 50 * np.nanmean(np.where(vals > 0, vals, np.nan))  # carrier, channel 126
                for ch in range(16):
                    row[f"tmt_{ch + 1}"] = vals[ch]
                rows.append(row)
        rows.append({**rows[-1], "scannr": "decoy", "spectrum_q": 0.4, "peptide_q": 0.4, "protein_q": 0.4,
                     **{f"tmt_{ch + 1}": 1e9 for ch in range(16)}})
    path = directory / "synthetic_quant.tsv"
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False, lineterminator="\n")
    return path


def rehearse_pxd046211(out: Path) -> tuple[pd.DataFrame, dict, dict]:
    upload = datasets.load_scope2_reprocessed_upload()
    cells = datasets.load_scope2_reprocessed_labels().set_index("cell_id").reindex(upload.cell_ids)["label"].to_numpy()
    rng = np.random.default_rng(0)
    order = rng.permutation(len(upload.cell_ids))
    annotation = []
    for run, start in enumerate(range(0, len(order), 12)):
        chunk = order[start:start + 12]
        file = f"20230101_rehearsal_run{run + 1:03d}"
        annotation += [{"File.Name": f"{file}.raw", "Channel": "126", "SampleType": "Carrier", "Treatment": ""},
                       {"File.Name": f"{file}.raw", "Channel": "127N", "SampleType": "Reference", "Treatment": ""},
                       {"File.Name": f"{file}.raw", "Channel": "127C", "SampleType": "Empty", "Treatment": ""},
                       {"File.Name": f"{file}.raw", "Channel": "128N", "SampleType": "Mix", "Treatment": ""}]
        for k, i in enumerate(chunk):
            line = "THP1" if run % 2 == 0 else "U937"
            annotation.append({"File.Name": f"{file}.raw", "Channel": TMTPRO[4 + k], "SampleType": line,
                               "Treatment": "PMA" if cells[i] == "macrophage" else "none", "_cell": upload.cell_ids[i]})
    ann = pd.DataFrame(annotation)
    ann.drop(columns="_cell").to_csv(out / "synthetic_annotation.csv", index=False, lineterminator="\n")
    rows, info = tmt_label_rows(pd.read_csv(out / "synthetic_annotation.csv", dtype=str))
    labels = pd.DataFrame(rows)
    source_cells = ann.dropna(subset=["_cell"])["_cell"].tolist()
    if len(source_cells) != len(labels):
        raise SystemExit("the stand-in annotation's single cells do not match the label rule's")
    values = upload.values[:, [upload.cell_ids.index(c) for c in source_cells]]
    staged = alignment.RawMatrix(gene_names=[formats.first_symbol(g) for g in upload.gene_names],
                                 cell_ids=labels["cell_id"].tolist(), values=values)
    quant = write_sage(staged, labels, out, rng)
    return labels, {"quant": quant}, {
        "dataset": "synthetic sage PSMs from SCoPE2 reprocessed (development): macrophages as 'PMA', monocytes as "
                   "'untreated', runs of 12 cells alternating 'THP1' and 'U937'; carrier, reference, empty and mix "
                   "channels and one decoy-level PSM per run", "annotation": info}


REHEARSALS = {"tian": rehearse_tian, "pxd021882": rehearse_pxd021882, "pxd043355": rehearse_pxd043355,
              "pxd073250": rehearse_pxd073250, "pxd046211": rehearse_pxd046211}


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("set", choices=SETS)
    parser.add_argument("--rehearse", action="store_true", help="development data or a synthetic file")
    parser.add_argument("--labels", action="store_true", help="Phase 3 only: build the label map, once")
    parser.add_argument("--label-map", type=Path, help="a map written by hand by the protocol's rules (with --labels)")
    parser.add_argument("--reason", help="why the map was written by hand (with --label-map)")
    args = parser.parse_args(argv)
    refuse_overrides()
    out = out_dir(args.set, args.rehearse)
    if args.rehearse:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        labels, sources, source_record = REHEARSALS[args.set](out)
        write_labels(labels, out, {"rehearsal": True})
        record = intake(args.set, labels, sources, out, source_record)
        print(json.dumps({"facts": record["label_free_facts"], "runs": record["runs"]}, indent=2))
        return
    if args.labels:
        if (out / "label_map.csv").exists():
            sys.exit(f"{out / 'label_map.csv'} exists: the label map is built once")
        if args.label_map:
            if not args.reason:
                sys.exit("a map written by hand needs --reason")
            labels = pd.read_csv(args.label_map, dtype={"cell_id": str, "sample": str})
            info = {"written_by_hand": str(args.label_map), "reason": args.reason,
                    "inputs_sha256": {rel: _check_download(rel) for rel in INPUTS[args.set]}}
        else:
            labels, info = real_label_map(args.set)
        digest = write_labels(labels, out, info)
        print(f"label map written: {len(labels)} rows, sha256 {digest}")
        return
    if (out / "intake.json").exists():
        sys.exit(f"{out / 'intake.json'} exists: the intake runs once")
    if not (out / "label_map.csv").exists():
        sys.exit("no label map: run --labels first (protocol, unsealing step 2)")
    labels = pd.read_csv(out / "label_map.csv", dtype={"cell_id": str, "sample": str, "file": str})
    labels["scored"] = labels["scored"].astype(str).eq("True")
    record = intake(args.set, labels, real_sources(args.set, labels), out,
                    {"inputs_sha256": {rel: _check_download(rel) for rel in INPUTS[args.set]},
                     "label_map_sha256": sha256(out / "label_map.csv")})
    print(json.dumps({"facts": record["label_free_facts"], "runs": record["runs"]}, indent=2))


if __name__ == "__main__":
    main()
