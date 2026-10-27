"""PXD064083, sorted single T and B cells (research/benchmark/protocol-pxd064083.md):
the receipt, the label map and the intake. Written and rehearsed before any
of the deposit's data files was downloaded or read.

    python -m benchmark.pxd064083_intake --rehearse     # Fulcher 2026's B and T cells as two search outputs
    python -m benchmark.pxd064083_intake --receive      # the files fetched by hand: their sha256, once
    python -m benchmark.pxd064083_intake --labels       # the label map, from the run names, once
    python -m benchmark.pxd064083_intake                # the intake, once
    python -m benchmark.pxd064083_intake --log2         # amendment 1's secondary, once (--rehearse to rehearse it)

The deposit holds the authors' two search outputs, SEARCH_T.xlsx (the T-cell
runs) and SEARCH_B.xlsx (the B-cell runs), in data/incoming/public_sets/PXD064083/.
iProX does not answer from the project's network, so they arrive by hand and
--receive records their sha256 in research/benchmark/pxd064083/receipt.json
before anything reads them (protocol, rule 1).

Reading (rule 3): each file's sheets in order; a long report (Spectronaut:
R.FileName, PG.Genes, PG.Quantity; DIA-NN: Run, Genes, PG.MaxLFQ) is pivoted,
one value per run and protein group; any other sheet goes to the service's own
parser (alignment.parse_matrix_csv). The first sheet read is the table.

Labels (rule 4): from each run name, T for "Tcell" and B for "Bcell"
(case, spaces, underscores and hyphens ignored), the donor from its leading
HC<n> or ALS<n>. Each cell comes from its own lineage's table; a table with
at least MIN_CELLS runs of each lineage is a joint search and is the upload
alone.

The uploads (rule 5): every T and B cell in one upload. Each table is put on
the service's log scale and its rows merged to one per gene by per-cell
median (the service's own Stage 0 and Stage 1 rules); each gene is then one
row over every cell, its values from each cell's own table. The primary
upload keeps the genes both searches report (a feature-space symbol, else
the first identifier); union/ holds the secondary upload, every gene either
reports.

Amendment 1 (a secondary, added before any model output was looked at): the
authors' values are linear on a small scale, which the service's Stage 0
reads as log, so --log2 also scores the primary upload built from the tables
as the service treats a linear file: 0 not detected, every other value log2.

Writes benchmark/results/heldout_pxd064083/ (heldout_pxd064083_rehearsal/
when rehearsing): label_map.csv, labels.json, intake.json, cell_ids.txt,
<model>_pred.csv, <model>_probs.npz, query_benchmark.npz, and union/ with the
union upload's <model>_pred.csv and <model>_probs.npz; --log2 writes
heldout_pxd064083_log2/ (intake.json, cell_ids.txt, <model>_pred.csv,
<model>_probs.npz, query_benchmark.npz).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import datasets
from benchmark.heldout_formats import Table, first_symbol
from benchmark.heldout_intake import facts, out_dir, run_models, write_labels
from benchmark.khoury2026_embed import refuse_overrides
from benchmark.sorted_cd4cd8_intake import benchmark_matrix, check_frozen, sha256
from service import config
from service.pipeline import alignment, gene_ids, reference

NAME = "pxd064083"
REPO = datasets.REPO
PROTOCOL = "research/benchmark/protocol-pxd064083.md"
FOLDER = REPO / "data" / "incoming" / "public_sets" / "PXD064083"
FILES = {"T": "SEARCH_T.xlsx", "B": "SEARCH_B.xlsx"}  # each lineage's search output (protocol, "Data")
RECEIPT = REPO / "research" / "benchmark" / "pxd064083" / "receipt.json"
MIN_CELLS = 20  # rule 6: fewer cells of either lineage and the test is void
LONG = {  # rule 3: long reports, (run, gene, value, protein group) columns
    "Spectronaut report": ("R.FileName", "PG.Genes", "PG.Quantity", "PG.ProteinGroups"),
    "DIA-NN report": ("Run", "Genes", "PG.MaxLFQ", "Protein.Group"),
}
LABEL_COLUMNS = ("cell_id", "upload", "sample", "group", "scored", "table", "donor", "status")


# ---- labels ----

def run_lineage(run: str) -> str:
    """T, B, or "" when the run name names neither or both."""
    text = re.sub(r"[\s_\-]+", "", str(run)).lower()
    t, b = "tcell" in text, "bcell" in text
    return "T" if t and not b else "B" if b and not t else ""


def run_donor(run: str) -> str:
    """HC<n> or ALS<n> from the start of the run name (after a "[k]" prefix), else ""."""
    m = re.match(r"^\s*(?:\[\d+\]\s*)?(HC|ALS)[\s_\-]*(\d+)", str(run), flags=re.IGNORECASE)
    return f"{m.group(1).upper()}{int(m.group(2))}" if m else ""


def label_rows(tables: dict) -> tuple[pd.DataFrame, dict]:
    """The label map from the tables' run names (rule 4), and what was left out."""
    lineages = {lin: [run_lineage(s) for s in t.samples] for lin, t in tables.items()}
    joint = [lin for lin, found in lineages.items() if found.count("T") >= MIN_CELLS and found.count("B") >= MIN_CELLS]
    use = {joint[0]: None} if joint else {lin: lin for lin in tables}
    rows, excluded = [], []
    for lin, want in use.items():
        for run, got in zip(tables[lin].samples, lineages[lin]):
            if not got or (want is not None and got != want):
                excluded.append({"table": lin, "run": run, "lineage_from_name": got or "none"})
                continue
            donor = run_donor(run)
            rows.append({"cell_id": run, "upload": "all", "sample": run, "group": got, "scored": True, "table": lin,
                         "donor": donor or "unknown", "status": re.sub(r"\d+$", "", donor) or "unknown"})
    labels = pd.DataFrame(rows, columns=LABEL_COLUMNS)
    if labels["cell_id"].duplicated().any():
        raise SystemExit("a run name appears twice among the included cells; write the map by hand by rule 4")
    info = {"joint_search": joint[0] if joint else None, "excluded_runs": excluded,
            "runs_per_table": {lin: len(t.samples) for lin, t in tables.items()}}
    return labels, info


# ---- reading (rule 3) ----

def _pivot_long(df: pd.DataFrame, layout: str, columns: tuple) -> Table:
    run, gene, value, group = columns
    group = group if group in df.columns else gene
    sub = df[[c for c in dict.fromkeys((run, group, gene, value))]].copy()
    sub[value] = pd.to_numeric(sub[value], errors="coerce")
    sub = sub.dropna(subset=[run, group])
    sub[run] = sub[run].astype(str)
    wide = sub.groupby([group, run], sort=False)[value].first().unstack(run)  # one value per run and protein group
    genes = sub.groupby(group, sort=False)[gene].first().reindex(wide.index)
    keep = genes.notna().to_numpy()
    return Table(genes=[str(g) for g in genes[keep]], samples=[str(c) for c in wide.columns],
                 values=wide.to_numpy(dtype=np.float32)[keep],
                 record={"layout": layout, "rows": int(keep.sum()), "runs": int(wide.shape[1])})


def read_table(path: Path) -> Table:
    """The first sheet of `path` holding per-run protein quantities in a layout
    the readers know (rule 3)."""
    sheets = pd.read_excel(path, sheet_name=None)
    tried = []
    for sheet, df in sheets.items():
        df.columns = [str(c).strip() for c in df.columns]
        for layout, columns in LONG.items():
            if set(columns[:3]) <= set(df.columns):
                table = _pivot_long(df, layout, columns)
                table.record.update({"file": path.name, "sheet": str(sheet)})
                return table
        try:
            raw = alignment.parse_matrix_csv(df.to_csv(sep="\t", index=False, lineterminator="\n"))
        except alignment.UnreadableMatrix as err:
            tried.append({"sheet": str(sheet), "columns": len(df.columns), "error": str(err)[:200]})
            continue
        return Table(genes=list(raw.gene_names), samples=list(raw.cell_ids), values=raw.values,
                     record={"layout": "wide, the service's parser", "file": path.name, "sheet": str(sheet),
                             "rows": len(raw.gene_names), "runs": len(raw.cell_ids)})
    raise SystemExit(f"{path.name}: no sheet holds per-run protein quantities the readers know ({tried}); "
                     "a format fix goes in an amendment before scoring, else the test is void (rules 3 and 6)")


# ---- the uploads (rule 5) ----

def row_key(name: str, symbol: "str | None") -> str:
    """A row's gene: its feature-space symbol, else its first listed identifier."""
    return symbol if symbol is not None else "id:" + first_symbol(name)


def merged_rows(table: Table, samples: list[str]) -> tuple[dict, dict, str]:
    """One table's rows over `samples`, one per gene: on the service's log
    scale (its Stage 0), a gene's rows merged by per-cell median (its Stage 1
    rule, here for every row). Returns {gene: values}, {gene: first
    identifier} and the scale detected."""
    sub = table.raw(samples)
    values, scale = alignment.detect_and_transform_value_scale(np.asarray(sub.values, dtype=np.float32))
    rows: dict[str, list[int]] = {}
    names: dict[str, str] = {}
    for i, (name, symbol) in enumerate(zip(sub.gene_names, gene_ids.resolve_to_feature_symbols(sub.gene_names))):
        key = row_key(name, symbol)
        rows.setdefault(key, []).append(i)
        names.setdefault(key, name)
    merged = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # a cell missing in every row stays NaN
        for key, index in rows.items():
            merged[key] = values[index[0]] if len(index) == 1 else np.nanmedian(values[index], axis=0)
    return merged, names, scale.detected


def build_uploads(tables: dict, labels: pd.DataFrame) -> tuple[dict, dict]:
    """{"intersection": RawMatrix, "union": RawMatrix}, cells in label-map
    order, and what the merge kept. Each gene is one row over every cell, its
    values from each cell's own table, so no row is observed in one lineage
    only because of the search it came from. The intersection keeps the genes
    both tables report; the union every gene either reports."""
    cells = labels["cell_id"].tolist()
    column = {c: i for i, c in enumerate(cells)}
    used = list(dict.fromkeys(labels["table"]))
    per_table, names, scales, where = {}, {}, {}, {}
    for lin in used:
        rows = labels[labels["table"] == lin]
        per_table[lin], found, scales[lin] = merged_rows(tables[lin], rows["sample"].tolist())
        for key, name in found.items():
            names.setdefault(key, name)
        where[lin] = [column[c] for c in rows["cell_id"]]
    if len(set(scales.values()) - {"unknown"}) > 1:
        raise SystemExit(f"the tables are on different scales {scales}: a format fix (amendment) before scoring")
    order = list(dict.fromkeys(k for lin in used for k in per_table[lin]))
    common = set.intersection(*(set(per_table[lin]) for lin in used))
    uploads = {}
    for kind, keep in (("intersection", common), ("union", set(order))):
        chosen = [k for k in order if k in keep]
        values = np.full((len(chosen), len(cells)), np.nan, dtype=np.float32)
        for r, key in enumerate(chosen):
            for lin in used:
                if key in per_table[lin]:
                    values[r, where[lin]] = per_table[lin][key]
        uploads[kind] = alignment.RawMatrix(gene_names=[names[k] for k in chosen], cell_ids=cells, values=values)
    features = {kind: sum(not k.startswith("id:") for k in keys)
                for kind, keys in (("both", common), ("either", order))}
    record = {"tables_used": used, "scales": scales, "genes_reported": {lin: len(per_table[lin]) for lin in used},
              "genes_in_both": len(common), "genes_in_either": len(order),
              "feature_genes_in_both": features["both"], "feature_genes_in_either": features["either"]}
    return uploads, record


def as_linear(table: Table) -> Table:
    """Amendment 1's secondary reading: the table as the service treats a file
    it recognises as linear (its Stage 0): 0 is not detected, every other
    value log2. A table with a negative value is not linear and is refused."""
    values = np.asarray(table.values, dtype=np.float64)
    if (values[np.isfinite(values)] < 0).any():
        raise SystemExit(f"{table.record.get('file', 'a table')} has negative values, so it is not linear (amendment 1)")
    out = np.full(values.shape, np.nan, dtype=np.float32)
    positive = np.isfinite(values) & (values > 0)
    out[positive] = np.log2(values[positive])
    return Table(genes=list(table.genes), samples=list(table.samples), values=out,
                 record={**table.record, "amendment_1": "0 as not detected, other values log2"})


def intake_log2(tables: dict, labels: pd.DataFrame, out: Path, source: dict) -> dict:
    """Amendment 1's secondary: the primary upload (the genes both searches
    report) from the log2 tables, every candidate as served, and the
    baselines' matrix; written to its own folder, once."""
    labels = labels.reset_index(drop=True)
    frozen = check_frozen()
    uploads, merge = build_uploads({lin: as_linear(t) for lin, t in tables.items()}, labels)
    cell_ids = labels["cell_id"].tolist()
    (out / "cell_ids.txt").write_text("\n".join(cell_ids) + "\n", encoding="utf-8", newline="\n")
    runs = run_models({"all": uploads["intersection"]}, out)
    np.savez_compressed(out / "query_benchmark.npz", x=benchmark_matrix(uploads["intersection"]),
                        cell_ids=np.array(cell_ids, dtype=object))
    outputs = {p.name: sha256(p) for p in sorted(out.iterdir()) if p.suffix in (".csv", ".txt", ".npz")}
    raw = uploads["intersection"]
    record = {"protocol": PROTOCOL, "amendment": 1, "set": NAME, "rehearsal": "rehearsal" in out.name, "source": source,
              "merge": merge, "frozen_files": frozen,
              "label_free_facts": {**facts(raw), "cells_at_coverage_floor": floor_facts(raw)}, "runs": runs,
              "outputs": outputs}
    (out / "intake.json").write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    return record


def floor_facts(raw: alignment.RawMatrix) -> int:
    """Cells with at least MIN_OBSERVED_GENES feature-space genes observed,
    the service's coverage floor."""
    aligned = alignment.align_to_feature_space(alignment.collapse_duplicate_genes(raw), reference.load_feature_space_genes())
    return int((aligned.per_cell_observed_genes >= config.MIN_OBSERVED_GENES).sum())


def check_receipt() -> dict:
    if not RECEIPT.exists():
        raise SystemExit(f"no receipt at {RECEIPT.relative_to(REPO)}: run --receive first (protocol, unsealing step 1)")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    for lin, name in FILES.items():
        got, want = sha256(FOLDER / name), receipt["files"][name]["sha256"]
        if got != want:
            raise SystemExit(f"{name}: sha256 {got} differs from the receipt's {want}")
    return {name: receipt["files"][name]["sha256"] for name in FILES.values()}


def intake(tables: dict, labels: pd.DataFrame, out: Path, source: dict) -> dict:
    labels = labels.reset_index(drop=True)
    frozen = check_frozen()
    uploads, merge = build_uploads(tables, labels)
    cell_ids = labels["cell_id"].tolist()
    (out / "cell_ids.txt").write_text("\n".join(cell_ids) + "\n", encoding="utf-8", newline="\n")
    runs = {"intersection": run_models({"all": uploads["intersection"]}, out)}
    (out / "union").mkdir()
    runs["union"] = run_models({"all": uploads["union"]}, out / "union")
    matrix = benchmark_matrix(uploads["intersection"])
    np.savez_compressed(out / "query_benchmark.npz", x=matrix, cell_ids=np.array(cell_ids, dtype=object))
    outputs = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*"))
               if p.is_file() and p.suffix in (".csv", ".txt", ".npz") and p.parent.name != "deposit"}
    record = {"protocol": PROTOCOL, "set": NAME, "rehearsal": "rehearsal" in out.name, "source": source,
              "readers": {lin: t.record for lin, t in tables.items()}, "merge": merge, "frozen_files": frozen,
              "label_free_facts": {kind: {**facts(raw), "cells_at_coverage_floor": floor_facts(raw)}
                                   for kind, raw in uploads.items()},
              "runs": runs, "outputs": outputs}
    (out / "intake.json").write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    return record


# ---- the rehearsal (development data; nothing of PXD064083) ----

def _spectronaut_pivot(raw: alignment.RawMatrix, runs: list[str], path: Path) -> None:
    """A Spectronaut protein-group pivot report in .xlsx: the proteins seen in
    at least one of these cells (a search reports nothing it never found),
    "[k] <run>.PG.Quantity" columns."""
    seen = np.isfinite(raw.values).any(axis=1)
    genes = pd.DataFrame({"PG.ProteinGroups": np.array(raw.gene_names)[seen], "PG.Genes": np.array(raw.gene_names)[seen]})
    quantities = pd.DataFrame(raw.values[seen], columns=[f"[{k}] {run}.d.PG.Quantity" for k, run in enumerate(runs, start=1)])
    pd.concat([genes, quantities], axis=1).to_excel(path, index=False)


def rehearse(out: Path) -> tuple[dict, pd.DataFrame, dict]:
    """Fulcher 2026 (development; its labels from clustering): its B cells and
    its CD4 and CD8 T cells written as two Spectronaut pivot reports, each with
    only its lineage's cells and the proteins seen in them, the runs named in
    the deposit's pattern, two donors split by cell order."""
    raw = datasets.load_fulcher2026_upload()
    truth = datasets.load_fulcher2026_labels().set_index("cell_id")["label"]
    folder = out / "deposit"
    folder.mkdir(parents=True)
    paths = {}
    for lin, types in (("T", ("CD4T", "CD8T")), ("B", ("B",))):
        keep = [i for i, c in enumerate(raw.cell_ids) if truth[c] in types]
        runs = [f"{'HC1' if n % 2 else 'ALS2_T1'}_{lin}cell_{c}" for n, c in enumerate(np.array(raw.cell_ids)[keep])]
        sub = alignment.RawMatrix(gene_names=raw.gene_names, cell_ids=runs, values=raw.values[:, keep])
        paths[lin] = folder / FILES[lin]
        _spectronaut_pivot(sub, runs, paths[lin])
    tables = {lin: read_table(path) for lin, path in paths.items()}
    labels, info = label_rows(tables)
    return tables, labels, {"dataset": "Fulcher 2026 (development): B and T cells as two Spectronaut pivot reports",
                            "files_sha256": {p.name: sha256(p) for p in paths.values()}, **info}


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    step = parser.add_mutually_exclusive_group()
    step.add_argument("--rehearse", action="store_true", help="Fulcher 2026, development data")
    step.add_argument("--receive", action="store_true", help="record the fetched files' sha256, once")
    step.add_argument("--labels", action="store_true", help="build the label map, once")
    parser.add_argument("--log2", action="store_true", help="amendment 1's secondary, after the intake (or its rehearsal)")
    args = parser.parse_args(argv)
    refuse_overrides()
    out = out_dir(NAME, args.rehearse)
    if args.log2:
        if args.receive or args.labels:
            sys.exit("--log2 runs alone, or with --rehearse")
        out2 = out_dir(f"{NAME}_log2", args.rehearse)
        if not (out / "intake.json").exists():
            sys.exit("amendment 1's secondary runs after the intake")
        if (out2 / "intake.json").exists() and not args.rehearse:
            sys.exit(f"{out2 / 'intake.json'} exists: amendment 1's secondary runs once")
        if out2.exists():
            shutil.rmtree(out2)
        out2.mkdir(parents=True)
        labels = pd.read_csv(out / "label_map.csv", dtype={"cell_id": str, "sample": str, "donor": str})
        if args.rehearse:
            paths, source = {lin: out / "deposit" / n for lin, n in FILES.items()}, {"dataset": "the rehearsal's deposit"}
        else:
            paths = {lin: FOLDER / n for lin, n in FILES.items()}
            source = {"inputs_sha256": check_receipt(), "label_map_sha256": sha256(out / "label_map.csv")}
        record = intake_log2({lin: read_table(p) for lin, p in paths.items()}, labels, out2, source)
        print(json.dumps({"facts": record["label_free_facts"], "merge": record["merge"]}, indent=2))
        return
    if args.rehearse:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        tables, labels, source = rehearse(out)
        write_labels(labels, out, {"rehearsal": True, **{k: v for k, v in source.items() if k != "dataset"}},
                     groups={"T", "B"}, required=("table", "donor"))
        record = intake(tables, labels, out, source)
        print(json.dumps({"facts": record["label_free_facts"], "merge": record["merge"]}, indent=2))
        return
    if args.receive:
        if RECEIPT.exists():
            sys.exit(f"{RECEIPT.relative_to(REPO)} exists: the files are received once")
        missing = [n for n in FILES.values() if not (FOLDER / n).exists()]
        if missing:
            sys.exit(f"not in {FOLDER.relative_to(REPO)}: {missing}")
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        files = {n: {"sha256": sha256(FOLDER / n), "bytes": (FOLDER / n).stat().st_size} for n in FILES.values()}
        RECEIPT.write_text(json.dumps({"received": date.today().isoformat(), "source": "iProX IPX0011993000, by hand",
                                       "files": files}, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(files, indent=2))
        return
    if args.labels:
        if (out / "label_map.csv").exists():
            sys.exit(f"{out / 'label_map.csv'} exists: the label map is built once")
        inputs = check_receipt()
        labels, info = label_rows({lin: read_table(FOLDER / n) for lin, n in FILES.items()})
        digest = write_labels(labels, out, {"inputs_sha256": inputs, **info}, groups={"T", "B"},
                              required=("table", "donor"))
        print(f"label map written: {len(labels)} rows, sha256 {digest}")
        return
    if (out / "intake.json").exists():
        sys.exit(f"{out / 'intake.json'} exists: the intake runs once")
    if not (out / "label_map.csv").exists():
        sys.exit("no label map: run --labels first (protocol, unsealing step 2)")
    inputs = check_receipt()
    labels = pd.read_csv(out / "label_map.csv", dtype={"cell_id": str, "sample": str, "donor": str})
    labels["scored"] = labels["scored"].astype(str).eq("True")
    tables = {lin: read_table(FOLDER / n) for lin, n in FILES.items()}
    record = intake(tables, labels, out, {"inputs_sha256": inputs, "label_map_sha256": sha256(out / "label_map.csv")})
    print(json.dumps({"facts": record["label_free_facts"], "merge": record["merge"]}, indent=2))


if __name__ == "__main__":
    main()
