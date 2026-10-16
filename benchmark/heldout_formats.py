"""Readers for the internal held-out test's search outputs
(research/benchmark/protocol-heldout.md, "Intake"). Written from each deposit's
documentation before any held-out file was opened, and checked on development
data of the same format or on synthetic files in the documented layout
(service/tests/test_heldout.py; benchmark/heldout_intake.py --rehearse).

Each reader returns a Table: one row per protein group, its gene identifier
(the first listed gene symbol, upper case, or for TMT the first protein's
symbol), the sample ids, the values (rows x samples, NaN missing) and a record
of the choices it made. The column names each format is read by sit in one
dictionary per format, so a format fix at unsealing (protocol, "Unsealing") is
one edit, recorded with its reason.

- MaxQuant proteinGroups (.txt, or exported to .xlsx): rows flagged "+" as
  only identified by site, reverse or potential contaminant are dropped; the
  "LFQ intensity <sample>" columns if any holds a non-zero value, else the
  "Intensity <sample>" columns; 0 is missing. Both MaxQuant's own spelling and
  R's (dots for spaces) are read.
- Proteome Discoverer protein table with its input-file table: master
  proteins at high FDR confidence, contaminants dropped, where those columns
  exist; "Abundances (Normalized): F<n>: Sample" if present, else
  "Abundance: F<n>: Sample"; F<n> named by its raw file; the gene symbol from
  a "Gene Symbol" column, else GN= in the description.
- sage TMT (PSM rows with reporter channels): PSMs at spectrum, peptide and
  protein q-values <= 0.01 where those columns exist; per PSM, each included
  single-cell channel divided by the mean over that run's included channels,
  log2; per cell and gene, the median over PSMs.
- DIA-NN: the service's own parser (service/pipeline/alignment.py).
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd

from service.pipeline import alignment, gene_ids


@dataclass
class Table:
    genes: list[str]
    samples: list[str]
    values: np.ndarray  # (rows, samples), NaN missing
    record: dict = field(default_factory=dict)

    def raw(self, keep: "list[str] | None" = None) -> alignment.RawMatrix:
        """The upload: the samples in `keep` (that order), or all."""
        if keep is None:
            return alignment.RawMatrix(gene_names=list(self.genes), cell_ids=list(self.samples), values=self.values)
        position = {s: i for i, s in enumerate(self.samples)}
        missing = [s for s in keep if s not in position]
        if missing:
            raise ValueError(f"{len(missing)} samples are not in the table, e.g. {missing[:3]}")
        return alignment.RawMatrix(gene_names=list(self.genes), cell_ids=list(keep),
                                   values=self.values[:, [position[s] for s in keep]])


def first_symbol(name) -> str:
    return str(name).split(";")[0].strip().upper() if isinstance(name, str) or pd.notna(name) else ""


def _read(path: Path, usecols=None) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
        df.columns = [str(c).strip().strip('"') for c in df.columns]
        return df[[c for c in df.columns if usecols is None or c in usecols]]
    return pd.read_csv(path, sep="\t", low_memory=False, usecols=usecols)


def _header(path: Path) -> list[str]:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return [str(c).strip().strip('"') for c in pd.read_excel(path, nrows=0).columns]
    with path.open(encoding="utf-8", errors="replace") as handle:
        return [c.strip().strip('"') for c in handle.readline().rstrip("\r\n").split("\t")]


# ---- MaxQuant ----

MAXQUANT = {
    "gene": ("gene names",),
    "flags": ("only identified by site", "reverse", "potential contaminant", "contaminant"),
    "lfq": re.compile(r"^LFQ[ .]intensity[ .](.+)$", re.IGNORECASE),
    "intensity": re.compile(r"^Intensity[ .](.+)$", re.IGNORECASE),
}


def _canon(name: str) -> str:
    return re.sub(r"[ ._]+", " ", str(name).strip().strip('"')).strip().lower()


def read_maxquant(path: Path, samples: "set[str] | None" = None) -> Table:
    """A MaxQuant protein-group table. `samples`, if given, limits the
    quantity columns read to those sample names (a memory bound for large
    files; it changes no value)."""
    header = _header(path)
    canon = {c: _canon(c) for c in header}
    genes_col = [c for c in header if canon[c] in MAXQUANT["gene"]]
    if not genes_col:
        raise ValueError(f"{path.name}: no gene-names column; columns start {header[:12]}")
    flags = [c for c in header if canon[c] in MAXQUANT["flags"]]
    quant = {}
    for kind in ("lfq", "intensity"):
        cols = {c: m.group(1).strip() for c in header if (m := MAXQUANT[kind].match(c))}
        if samples is not None:
            cols = {c: s for c, s in cols.items() if s in samples}
        quant[kind] = cols
    df = _read(path, usecols=genes_col[:1] + flags + list(quant["lfq"]) + list(quant["intensity"]))
    drop = np.zeros(len(df), dtype=bool)
    for c in flags:
        drop |= df[c].astype(str).str.strip().eq("+").to_numpy()
    genes = df[genes_col[0]].map(first_symbol)
    keep = ~drop & genes.ne("").to_numpy()
    lfq = df.loc[keep, list(quant["lfq"])].apply(pd.to_numeric, errors="coerce")
    use = "lfq" if len(quant["lfq"]) and bool((lfq.fillna(0) > 0).to_numpy().any()) else "intensity"
    if not quant[use]:
        raise ValueError(f"{path.name}: no LFQ intensity or Intensity columns")
    values = df.loc[keep, list(quant[use])].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
    values = np.where(values > 0, values, np.nan)
    record = {"format": "MaxQuant proteinGroups", "file": path.name, "rows_read": int(len(df)),
              "rows_dropped_flagged": int(drop.sum()), "rows_without_gene": int((~drop & genes.eq("").to_numpy()).sum()),
              "rows_kept": int(keep.sum()), "quantity": "LFQ intensity" if use == "lfq" else "Intensity",
              "flags_read": flags}
    return Table(genes=genes[keep].tolist(), samples=list(quant[use].values()), values=values, record=record)


# ---- Proteome Discoverer ----

PD = {
    "normalized": re.compile(r"^Abundances? \(Normali[sz]ed\):\s*(F\d+)\b"),
    "abundance": re.compile(r"^Abundance:\s*(F\d+)\b"),
    "gene": "Gene Symbol",
    "description": "Description",
    "master": ("Master", "IsMasterProtein"),
    "confidence": ("Protein FDR Confidence: Combined", "High"),
    "contaminant": "Contaminant",
    "file_id": "File ID",
    "file_name": "File Name",
}


def _sample_name(path_text: str) -> str:
    name = PureWindowsPath(str(path_text)).name
    return re.sub(r"\.raw$", "", name, flags=re.IGNORECASE)


def read_proteome_discoverer(proteins: Path, input_files: Path) -> Table:
    df = pd.read_csv(proteins, sep="\t", low_memory=False)
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    files = pd.read_csv(input_files, sep="\t", dtype=str)
    files.columns = [str(c).strip().strip('"') for c in files.columns]
    name_of = dict(zip(files[PD["file_id"]].str.strip(), files[PD["file_name"]].map(_sample_name)))
    keep = np.ones(len(df), dtype=bool)
    applied = []
    master_col, master_val = PD["master"]
    if master_col in df:
        keep &= df[master_col].astype(str).eq(master_val).to_numpy()
        applied.append("master proteins")
    conf_col, conf_val = PD["confidence"]
    if conf_col in df:
        keep &= df[conf_col].astype(str).eq(conf_val).to_numpy()
        applied.append("high FDR confidence")
    if PD["contaminant"] in df:
        keep &= ~df[PD["contaminant"]].astype(str).str.lower().isin(("true", "1", "+")).to_numpy()
        applied.append("contaminants dropped")
    if PD["gene"] in df:
        genes = df[PD["gene"]].map(first_symbol)
        gene_source = PD["gene"]
    else:
        genes = df[PD["description"]].astype(str).str.extract(r"GN=(\S+)")[0].fillna("").map(first_symbol)
        gene_source = "GN= in Description"
    keep &= genes.ne("").to_numpy()
    for kind in ("normalized", "abundance"):
        cols = {c: m.group(1) for c in df.columns if (m := PD[kind].match(c))}
        if cols:
            break
    else:
        raise ValueError(f"{proteins.name}: no abundance columns; columns start {list(df.columns)[:12]}")
    unknown = [f for f in cols.values() if f not in name_of]
    if unknown:
        raise ValueError(f"{input_files.name} does not name {unknown[:5]}")
    values = df.loc[keep, list(cols)].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
    values = np.where(values > 0, values, np.nan)
    record = {"format": "Proteome Discoverer proteins", "file": proteins.name, "rows_read": int(len(df)),
              "rows_kept": int(keep.sum()), "filters": applied, "gene_from": gene_source,
              "quantity": "Abundances (Normalized)" if kind == "normalized" else "Abundance"}
    return Table(genes=genes[keep].tolist(), samples=[name_of[f] for f in cols.values()], values=values, record=record)


# ---- sage TMT ----

SAGE = {
    "file": "filename",
    "proteins": "proteins",
    "q_values": ("spectrum_q", "peptide_q", "protein_q"),
    "channel": re.compile(r"^tmt_(\d+)$"),
    "max_q": 0.01,
}


def _accession(protein: str) -> str:
    first = str(protein).split(";")[0].strip()
    parts = first.split("|")
    return parts[1] if len(parts) >= 3 else first


def _entry_symbol(protein: str) -> str:
    first = str(protein).split(";")[0].strip()
    parts = first.split("|")
    return re.sub(r"_HUMAN$", "", parts[2]).upper() if len(parts) >= 3 else first.upper()


def protein_symbols(proteins: pd.Series) -> list[str]:
    """The first protein's gene symbol: the service map's symbol for its
    UniProt accession, else its UniProt entry name without "_HUMAN"."""
    unique = proteins.astype(str).unique().tolist()
    mapped = gene_ids.resolve_to_feature_symbols([_accession(p) for p in unique])
    symbol = {p: (m if m else _entry_symbol(p)) for p, m in zip(unique, mapped)}
    return [symbol[p] for p in proteins.astype(str)]


def run_name(path_text: str) -> str:
    """A run's file name without folder or extension (.raw, .mzML, .d)."""
    return re.sub(r"\.(raw|mzml|d)$", "", PureWindowsPath(str(path_text)).name, flags=re.IGNORECASE)


def read_sage_tmt(path: Path, channels: dict) -> Table:
    """channels: {(run name, channel number): cell id} for the included
    single-cell channels only (carrier, reference, empty, blank and mixed
    channels are left out by the label map)."""
    df = pd.read_csv(path, sep="\t", low_memory=False)
    channel_cols = {int(m.group(1)): c for c in df.columns if (m := SAGE["channel"].match(str(c)))}
    needed = [SAGE["file"], SAGE["proteins"]]
    missing = [c for c in needed if c not in df] + ([] if channel_cols else ["tmt_<n>"])
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}; columns start {list(df.columns)[:15]}")
    keep = np.ones(len(df), dtype=bool)
    q_used = [q for q in SAGE["q_values"] if q in df]
    for q in q_used:
        keep &= pd.to_numeric(df[q], errors="coerce").le(SAGE["max_q"]).to_numpy()
    df = df.loc[keep].reset_index(drop=True)
    df["_gene"] = protein_symbols(df[SAGE["proteins"]])
    files = df[SAGE["file"]].astype(str).map(run_name)
    cells = sorted(set(channels.values()), key=list(channels.values()).index)
    genes = sorted(df["_gene"].unique())
    gene_pos = {g: i for i, g in enumerate(genes)}
    cell_pos = {c: i for i, c in enumerate(cells)}
    out = np.full((len(genes), len(cells)), np.nan)
    by_file: dict[str, list[tuple[int, str]]] = {}
    for (file, channel), cell in channels.items():
        by_file.setdefault(file, []).append((channel, cell))
    for file, members in by_file.items():
        rows = files.eq(file).to_numpy()
        if not rows.any():
            continue
        cols = [channel_cols[ch] for ch, _ in members if ch in channel_cols]
        if len(cols) != len(members):
            raise ValueError(f"{file}: channels {sorted(ch for ch, _ in members)} not all in {sorted(channel_cols)}")
        x = df.loc[rows, cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
        x = np.where(x > 0, x, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ratio = np.log2(x / np.nanmean(x, axis=1, keepdims=True))
        frame = pd.DataFrame(ratio, columns=[cell for _, cell in members])
        frame["_gene"] = df.loc[rows, "_gene"].to_numpy()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = frame.groupby("_gene").median()
        for cell in med.columns:
            out[[gene_pos[g] for g in med.index], cell_pos[cell]] = med[cell].to_numpy()
    record = {"format": "sage TMT PSMs", "file": path.name, "psms_read": int(len(keep)), "psms_kept": int(keep.sum()),
              "q_values_filtered": q_used, "max_q": SAGE["max_q"], "runs": len(by_file),
              "quantity": "log2 reporter intensity over the run's included single-cell channels, median over PSMs"}
    return Table(genes=genes, samples=cells, values=out, record=record)


# ---- DIA-NN ----

def read_dia_nn(path: Path) -> Table:
    raw = alignment.parse_matrix_csv(path.read_text(encoding="utf-8"))
    return Table(genes=list(raw.gene_names), samples=list(raw.cell_ids), values=raw.values,
                 record={"format": "DIA-NN pg_matrix", "file": path.name, "rows": len(raw.gene_names),
                         "parser": "service parse_matrix_csv"})
