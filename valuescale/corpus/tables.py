"""Which file of a deposit is its table, how it is read when the service's
parser does not read it, and its label (research/benchmark/protocol-value-scale.md,
"Tables" and "Labels"). Nothing here computes a statistic of the values;
the one look at them is the protocol's check for a negative value in a
table labelled linear.

**Candidates**, by name without regard to case: `*pg_matrix.tsv` (DIA-NN
matrix), `*combined_protein.tsv` (FragPipe), `proteinGroups*.txt` (MaxQuant),
`*_Proteins.txt` (Proteome Discoverer). A text or parquet file with "report"
in its name (not a DIA-NN precursor or gene matrix, stats or log) is read at
its header: PG.Quantity with PG.ProteinGroups and R.FileName (or R.Label) is a
Spectronaut long report, `<run>.PG.Quantity` columns a Spectronaut pivot;
Protein.Group and Run with PG.MaxLFQ or PG.Quantity a DIA-NN long report.

**One table per deposit:** the first candidate in the order DIA-NN matrix,
FragPipe, MaxQuant, Spectronaut, Proteome Discoverer, DIA-NN long report,
then the members of zip archives of 500 MB or less in the same order. Ties go
by file name, then path (archive members: member name, then archive). Zipped
raw instrument data (`*.d.zip`, `*.raw.zip`, `*.wiff.zip`, `*.mzML.zip` and
the like) is never a protein table and is not listed. Nor is a Mac's
companion file: a name starting "._", or anything under `__MACOSX/`.

**Labels**, on the names of the chosen value columns only (a Spectronaut
pivot's PG.AvgLog2Quantity is not a value column):
- unclear, so excluded: a ratio, z-score, imputation or scale-changing
  normalisation named; a TMT-Integrator table; a negative value in a table
  that would be labelled linear;
- log: a log named (log2, log10, "log(" or "ln(");
- linear: a native output, quoted from bank.json's quotes for its software.

The quantity patterns copy the service's parser's
(service/pipeline/alignment.py); the draw's runner checks they still match.
"""
from __future__ import annotations

import codecs
import fnmatch
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from valuescale.corpus.remote import File

KINDS = ("diann_matrix", "fragpipe", "maxquant", "spectronaut", "proteome_discoverer", "diann_report")
SOFTWARE = {"diann_matrix": "DIA-NN", "diann_report": "DIA-NN", "fragpipe": "FragPipe", "maxquant": "MaxQuant",
            "spectronaut": "Spectronaut", "proteome_discoverer": "Proteome Discoverer"}
QUOTE_KEYS = {"DIA-NN": "diann", "FragPipe": "fragpipe", "MaxQuant": "maxquant", "Spectronaut": "spectronaut",
              "Proteome Discoverer": "proteome_discoverer"}
ARCHIVE_MAX = 500_000_000
FILE_MAX = ARCHIVE_MAX  # the archive bar for single files too (b3.json, changed before the run)
REPORT_EXTENSIONS = (".tsv", ".txt", ".csv", ".xls", ".parquet")
# Raw instrument data zipped (a Bruker .d folder, a Thermo .raw, SCIEX .wiff,
# peak lists): never a protein table, so not listed. B3's walk met a MassIVE
# deposit with 421 of them beside 421 search zips.
RAW_ARCHIVE = re.compile(r"\.(?:d|raw|wiff|wiff2|mzml|mzxml|mgf|tdf|baf)\.zip$")
ARCHIVE_WORKERS = 4
BANK = Path(__file__).with_name("bank.json")

DIA_NN_ANNOTATION = frozenset({"Protein.Group", "Protein.Ids", "Protein.Names", "Genes",
                               "First.Protein.Description", "N.Sequences", "N.Proteotypic.Sequences"})
MAXQUANT_IDS = "majority protein ids"  # MaxQuant's protein-group column, in any case
MAXQUANT_QUANTITIES = (r"^LFQ intensity (.+)$", r"^Intensity (.+)$")
FRAGPIPE_LFQ_MARKERS = ("Gene", "Combined Total Peptides")
FRAGPIPE_LFQ_QUANTITIES = (r"^(?!Combined )(.+) MaxLFQ Intensity$",
                           r"^(?!Combined )(.+?)(?<! MaxLFQ)(?<! Unique)(?<! Total)(?<! Razor) Intensity$")
SPECTRONAUT_QUANTITY = r"^(?:\[\d+\]\s*)?(.+?)\.PG\.Quantity$"
PD_PREFIX = "Abundance: "
MISSING = frozenset({"", "NA", "Filtered", "NaN", "nan"})

UNCLEAR = re.compile(r"ratio|z-?score|imput|scaled|cent(?:ered|red)|quantile|(?<![a-z])vsn(?![a-z])|combat", re.I)
LOGGED = re.compile(r"log\s*2|log\s*10|log\s*\(|(?<![a-z])ln\s*\(", re.I)


@dataclass(frozen=True)
class Entry:
    file: File
    member: str | None = None
    size: int = 0  # the member's uncompressed size, or the file's

    @property
    def name(self) -> str:
        return (self.member or self.file.path).rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Candidate:
    kind: str
    layout: str  # "wide", "spectronaut_pivot", "spectronaut_long" or "long"
    entry: Entry
    columns: tuple = ()


@dataclass(frozen=True)
class Table:
    ids: list
    cells: list
    values: np.ndarray
    quantity: str | None = None


def is_mac_companion(name: str) -> bool:
    """A Mac's companion file (its resource fork, "._name", or anything under
    __MACOSX/), written beside the real file: never a table."""
    return name.rsplit("/", 1)[-1].startswith("._") or "__macosx/" in name.lower()


def name_kind(name: str) -> str | None:
    n = name.rsplit("/", 1)[-1].lower()
    if is_mac_companion(name):
        return None
    if fnmatch.fnmatch(n, "*pg_matrix.tsv"):
        return "diann_matrix"
    if fnmatch.fnmatch(n, "*combined_protein.tsv"):
        return "fragpipe"
    if fnmatch.fnmatch(n, "proteingroups*.txt"):
        return "maxquant"
    if fnmatch.fnmatch(n, "*_proteins.txt"):
        return "proteome_discoverer"
    if "report" in n and n.endswith(REPORT_EXTENSIONS) and not ("matrix" in n or "stats" in n or n.endswith(".log.txt")):
        return "report"
    if RAW_ARCHIVE.search(n):
        return "raw_archive"
    if n.endswith(".zip"):
        return "archive"
    return None


def classify_report(columns) -> str | None:
    cols = set(columns)
    if {"PG.ProteinGroups", "PG.Quantity"} <= cols and ("R.FileName" in cols or "R.Label" in cols):
        return "spectronaut_long"
    if any(re.match(SPECTRONAUT_QUANTITY, c) for c in columns):
        return "spectronaut_pivot"
    if {"Protein.Group", "Run"} <= cols and ("PG.MaxLFQ" in cols or "PG.Quantity" in cols):
        return "diann_report"
    return None


def _first(entries: list[Entry], columns_of) -> Candidate | None:
    ordered = sorted(entries, key=lambda e: (e.name.lower(), e.member or e.file.path, e.file.path))
    by_kind: dict[str, list[Entry]] = {}
    for e in ordered:
        by_kind.setdefault(name_kind(e.name), []).append(e)
    for kind in ("diann_matrix", "fragpipe", "maxquant"):
        if by_kind.get(kind):
            return Candidate(kind, "wide", by_kind[kind][0])
    reports = []
    for e in by_kind.get("report", []):
        cols = columns_of(e)
        layout = classify_report(cols) if cols else None
        if layout in ("spectronaut_long", "spectronaut_pivot"):
            return Candidate("spectronaut", layout, e, tuple(cols))
        reports.append((e, layout, cols))
    if by_kind.get("proteome_discoverer"):
        return Candidate("proteome_discoverer", "wide", by_kind["proteome_discoverer"][0])
    for e, layout, cols in reports:
        if layout == "diann_report":
            return Candidate("diann_report", "long", e, tuple(cols))
    return None


def first_candidate(files: list[File], columns_of, members_of) -> Candidate | None:
    """columns_of(entry) gives a report's header (or None); members_of(file)
    gives an archive's member names, read only when no file is a candidate."""
    found = _first([Entry(f, None, f.size) for f in files if name_kind(f.name) != "archive"], columns_of)
    if found is not None:
        return found
    archives = sorted((f for f in files if name_kind(f.name) == "archive" and f.size <= ARCHIVE_MAX),
                      key=lambda f: (f.name.lower(), f.path))
    members = []
    with ThreadPoolExecutor(max_workers=ARCHIVE_WORKERS) as pool:
        listed = list(pool.map(members_of, archives))  # in the archives' order
    for f, found in zip(archives, listed):
        for m in found:
            name, size = (m, 0) if isinstance(m, str) else (m.name, m.size)
            if not name.endswith("/") and name_kind(name) not in (None, "archive"):
                members.append(Entry(f, name, size))
    return _first(members, columns_of)


def quantity_columns(kind: str, layout: str, columns) -> int | None:
    """The most columns any quantity family could give, from the header
    alone; None for a long report, whose runs are rows."""
    if layout in ("long", "spectronaut_long"):
        return None
    if kind == "diann_matrix":
        return sum(1 for c in columns if c.strip() and c not in DIA_NN_ANNOTATION)
    if kind == "maxquant":
        return max(sum(1 for c in columns if re.match(p, c)) for p in MAXQUANT_QUANTITIES)
    if kind == "fragpipe":
        return max(sum(1 for c in columns if re.match(p, c)) for p in FRAGPIPE_LFQ_QUANTITIES)
    if kind == "spectronaut":
        return sum(1 for c in columns if re.match(SPECTRONAUT_QUANTITY, c))
    if kind == "proteome_discoverer":
        return sum(1 for c in columns if c.startswith(PD_PREFIX))
    raise ValueError(kind)


def _numbers(frame: pd.DataFrame) -> np.ndarray:
    """Text to float: the missing spellings become NaN; any other text raises."""
    cleaned = frame.apply(lambda s: s.str.strip()).where(lambda d: ~d.isin(MISSING))
    try:
        return cleaned.astype(np.float64).to_numpy()
    except ValueError as exc:
        raise ValueError(f"text where a number belongs: {exc}") from None


def text_encoding(path: Path) -> str:
    """The encoding the service reads an uploaded matrix in (service/app.py
    `_decode_matrix`): UTF-16 by its byte order mark, else UTF-8 (a byte
    order mark skipped) when the whole file is UTF-8, else Windows-1252
    (Excel's plain "CSV" on Windows)."""
    with path.open("rb") as fh:
        if fh.read(2) in (b"\xff\xfe", b"\xfe\xff"):
            return "utf-16"
        fh.seek(0)
        decoder = codecs.getincrementaldecoder("utf-8")()
        try:
            for block in iter(lambda: fh.read(1 << 20), b""):
                decoder.decode(block)
            decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            return "cp1252"
    return "utf-8-sig"


def read_text(path: Path) -> str:
    """The file's text as the service decodes an upload: a byte Windows-1252
    leaves undefined is replaced, and UTF-16 cut mid-character is refused."""
    encoding, data = text_encoding(path), path.read_bytes()
    if encoding == "utf-16" and len(data) % 2:
        raise ValueError("the file ends in half a character, so it looks cut off")
    return data.decode(encoding, errors="replace")


def _sep(path: Path, encoding: str) -> str:
    with path.open("r", encoding=encoding, errors="replace") as fh:
        line = fh.readline()
    return "\t" if line.count("\t") >= line.count(",") else ","


def read_proteome_discoverer(path: Path) -> Table:
    """'Abundance: ' columns; Gene Symbol as the identifier, else Accession;
    rows with neither dropped."""
    encoding = text_encoding(path)
    df = pd.read_csv(path, sep=_sep(path, encoding), dtype=str, keep_default_na=False, encoding=encoding,
                     encoding_errors="replace")
    cells = [c for c in df.columns if c.startswith(PD_PREFIX)]
    if not cells:
        raise ValueError(f"no column starts with {PD_PREFIX!r}")
    gene = df["Gene Symbol"].str.strip() if "Gene Symbol" in df.columns else pd.Series([""] * len(df))
    acc = df["Accession"].str.strip() if "Accession" in df.columns else pd.Series([""] * len(df))
    ids = gene.where(gene != "", acc)
    keep = (ids != "").to_numpy()
    return Table(ids[keep].tolist(), [c[len(PD_PREFIX):].strip() for c in cells], _numbers(df.loc[keep, cells]))


def read_long(path: Path, layout: str) -> Table:
    """A long report pivoted to proteins x runs, the first value per pair.
    DIA-NN: Protein.Group x Run on PG.MaxLFQ when any is above 0, else
    PG.Quantity. Spectronaut: PG.ProteinGroups x R.FileName (else R.Label) on
    PG.Quantity."""
    parquet = path.suffix.lower() == ".parquet"
    if parquet:
        import pyarrow.parquet as pq
        names = pq.ParquetFile(path).schema_arrow.names
    else:
        encoding = text_encoding(path)
        sep = _sep(path, encoding)
        names = pd.read_csv(path, sep=sep, nrows=0, encoding=encoding, encoding_errors="replace").columns.tolist()
    if layout == "diann_report":
        row, column = "Protein.Group", "Run"
        quantities = [q for q in ("PG.MaxLFQ", "PG.Quantity") if q in names]
    elif layout == "spectronaut_long":
        row, column = "PG.ProteinGroups", ("R.FileName" if "R.FileName" in names else "R.Label")
        quantities = ["PG.Quantity"]
    else:
        raise ValueError(layout)
    usecols = [row, column, *quantities]
    if parquet:
        df = pd.read_parquet(path, columns=usecols).astype(str)
    else:
        df = pd.read_csv(path, sep=sep, usecols=usecols, dtype=str, keep_default_na=False,
                         encoding=encoding, encoding_errors="replace")
    df = df[df[row].str.strip() != ""]
    if not quantities:
        raise ValueError("no quantity column")
    numbers = {q: _numbers(df[[q]])[:, 0] for q in quantities}
    q = "PG.MaxLFQ" if "PG.MaxLFQ" in numbers and np.any(numbers["PG.MaxLFQ"] > 0) else quantities[-1]
    v = numbers[q]
    long =pd.DataFrame({"row": df[row].to_numpy(), "column": df[column].to_numpy(), "value": v})
    wide = long.groupby(["row", "column"], sort=False)["value"].first().unstack("column")
    rows = list(dict.fromkeys(long["row"]))
    cols = list(dict.fromkeys(long["column"]))
    wide = wide.reindex(index=rows, columns=cols)
    return Table(rows, cols, wide.to_numpy(dtype=np.float64), q)


def is_tmt_integrator(columns) -> bool:
    """The service's parser reads a 'Gene' table without 'Genes' or FragPipe's
    LFQ markers as a TMT-Integrator table."""
    cols = set(columns)
    return ("Gene" in cols and "Genes" not in cols and not all(m in cols for m in FRAGPIPE_LFQ_MARKERS)
            and not any(c.lower() == MAXQUANT_IDS for c in cols))


def quotes() -> dict:
    return json.loads(BANK.read_text(encoding="utf-8"))["quotes"]


def label(kind: str, value_names, values: np.ndarray, tmt_integrator: bool = False) -> tuple[str, str]:
    """(label, quote or reason): linear, log or unclear."""
    if tmt_integrator:
        return "unclear", "a TMT-Integrator table (its documentation disagrees on the scale)"
    for name in value_names:
        if m := UNCLEAR.search(str(name)):
            return "unclear", f"the value column {name!r} names {m.group(0)!r}"
    for name in value_names:
        if LOGGED.search(str(name)):
            return "log", str(name)
    v = np.asarray(values, dtype=np.float64)
    if np.any(v[np.isfinite(v)] < 0):
        return "unclear", "a negative value in a table that would be labelled linear"
    q = quotes()[QUOTE_KEYS[SOFTWARE[kind]]]
    return "linear", f"{q['quote']} ({q['source']})"
