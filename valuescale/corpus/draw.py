"""B3's walk over the frame (research/benchmark/protocol-value-scale.md, "Tables").

For each deposit, in the frame's order:
1. list its files (no file list: the listing failed after retries);
2. choose its one table (tables.first_candidate; no candidate);
3. a single file over tables.FILE_MAX is too large;
4. a wide table's header is read first: when no quantity family reaches 20
   columns, the deposit is skipped as too few columns without the full fetch,
   and a table the parser refuses on its header alone (a SILAC or TMT
   MaxQuant search) is unparseable without it, in the parser's own words;
5. fetch it, with its size and sha256 (fetch failed);
6. parse it (unparseable), then at least 20 columns and 200 rows;
7. a table that holds no observed value is empty (R1 of protein v2);
8. label it (tables.label; unclear label);
9. a kept table labelled linear whose observed values look log (99% of
   them under LOG_CEILING) carries looks_log, its value range, and goes to
   the hand audit (R1). Its label stands, and nothing is refused for it.

Each deposit's outcome is one line of the walk's log, written in the frame's
order whatever finishes first, so a stopped walk resumes where it stopped.
The walk stops when every quota is met in both splits (QUOTA linear
deposits reaching each stratum), or after LIMIT deposits have been listed.
Once it has stopped, records can be visited again in their places
(revisit): each whose read failed (fetch failed, no file list), or a chosen
set (B3's third visit, valuescale/corpus/cleanup_20261106.json; its fourth,
valuescale/corpus/cleanup_20261107.json). Each keeps the record it replaces
as revisited_from, an earlier visit and its reasons nested inside.

The network and the parser come in as Tools, so the walk is tested without
either; research/notebooks/value_scale_corpus.py supplies the real ones.
No detector statistic of a table's values is computed here. Three facts of
its values are read, none of them a reading of its scale from its shape:
whether any is observed (empty), the label's refusal of a negative value
(tables.label), and a linear table's value range with its 99th percentile
(looks_log), which sends it to the audit and changes nothing else. An
observed value is finite and not 0: a protein table writes "not detected"
as 0 or leaves it empty (research/value-scale-v2-plan.md, R1).
"""
from __future__ import annotations

import json
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np

from valuescale.corpus import denylist, tables
from valuescale.corpus.strata import STRATA, strata_reached

QUOTA = 59
LIMIT = 10_000
MIN_COLUMNS, MIN_ROWS = 20, 200
SPLITS = ("calibration", "test")
LOOKAHEAD = 64  # deposits in flight per worker: a report that takes 20 minutes must not hold up the rest
LOG_CEILING = 64.0  # 2**6: the 99th percentile of a log2 table's values is well under it, a linear table's far above
LOOK_LOG_QUANTILE = 0.99


class Parsed(NamedTuple):
    cells: list
    values: np.ndarray
    tmt_integrator: bool = False
    quantity: str | None = None


class Tools(NamedTuple):
    list_files: Callable  # (accession, repo) -> [File]
    columns_of: Callable  # (Entry) -> a report's header fields, or None
    members_of: Callable  # (File) -> an archive's members
    fetch: Callable  # (Entry, folder) -> (local path of the table, {bytes, sha256, ...})
    parse: Callable  # (Candidate, local path) -> Parsed
    header: Callable  # (Entry) -> a wide table's header fields, or None
    refuse: Callable | None = None  # (Candidate, header) -> raises where the parser refuses the header itself


def _observed(values: np.ndarray) -> np.ndarray:
    v = np.asarray(values, dtype=np.float64)
    return v[np.isfinite(v) & (v != 0)]


def empty(values: np.ndarray) -> bool:
    """No observed value: every entry missing, infinite or 0. Such a table
    says nothing about its scale (B7's PXD022054 and PXD047898)."""
    return _observed(values).size == 0


def _figure(x) -> float:
    return float(f"{float(x):.6g}")


def looks_log(values: np.ndarray) -> dict | None:
    """The observed values' range (smallest, median, 99th percentile,
    largest) when 99% of them are under LOG_CEILING, else None. Read only of
    a table labelled linear: there it means the label may be wrong (B7's
    PXD066316, log2 values under a linear label), or the table is a
    small-scale linear one, like PXD064083's (median about 7), which the
    audit keeps."""
    observed = _observed(values)
    if not observed.size:
        return None
    p99 = np.quantile(observed, LOOK_LOG_QUANTILE)
    if not p99 < LOG_CEILING:
        return None
    return {"min": _figure(observed.min()), "median": _figure(np.median(observed)), "p99": _figure(p99),
            "max": _figure(observed.max())}


def _short(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:300]


def visit(accession: str, repo: str, split: str, tools: Tools, root: Path) -> dict:
    denylist.check(accession)
    out = {"accession": accession, "repo": repo, "split": split}
    try:
        files = tools.list_files(accession, repo)
    except denylist.SealedData:
        raise
    except Exception as exc:
        return {**out, "outcome": "no file list", "detail": _short(exc)}
    try:
        cand = tables.first_candidate(files, tools.columns_of, tools.members_of)
    except denylist.SealedData:
        raise
    except Exception as exc:
        return {**out, "outcome": "fetch failed", "detail": "reading a header or archive: " + _short(exc)}
    if cand is None:
        return {**out, "outcome": "no candidate", "files": len(files)}
    entry = cand.entry
    out.update(kind=cand.kind, layout=cand.layout, software=tables.SOFTWARE[cand.kind], file=entry.file.path,
               member=entry.member, url=entry.file.url, listed_bytes=entry.file.size)
    size = entry.size or entry.file.size
    if size > tables.FILE_MAX:
        return {**out, "outcome": "too large", "detail": f"{size} bytes"}
    if cand.layout in ("wide", "spectronaut_pivot"):
        try:
            header = list(cand.columns) or tools.header(entry)
        except denylist.SealedData:
            raise
        except Exception as exc:
            return {**out, "outcome": "fetch failed", "detail": "reading the header: " + _short(exc)}
        n = tables.quantity_columns(cand.kind, cand.layout, header) if header else None
        if n is not None and n < MIN_COLUMNS:
            return {**out, "outcome": "too few columns", "header_columns": n}
        if header and tools.refuse is not None:
            try:
                tools.refuse(cand, header)
            except denylist.SealedData:
                raise
            except Exception as exc:
                return {**out, "outcome": "unparseable", "detail": _short(exc), "refused_on": "header"}
    try:
        local, record = tools.fetch(entry, root / accession)
    except denylist.SealedData:
        raise
    except Exception as exc:
        return {**out, "outcome": "fetch failed", "detail": _short(exc)}
    out.update(record)
    try:
        parsed = tools.parse(cand, local)
    except denylist.SealedData:
        raise
    except Exception as exc:
        return {**out, "outcome": "unparseable", "detail": _short(exc)}
    columns, rows = len(parsed.cells), int(parsed.values.shape[0])
    out.update(columns=columns, rows=rows, quantity=parsed.quantity)
    if columns < MIN_COLUMNS:
        return {**out, "outcome": "too few columns"}
    if rows < MIN_ROWS:
        return {**out, "outcome": "too few rows"}
    if empty(parsed.values):
        return {**out, "outcome": "empty"}
    lab, quote = tables.label(cand.kind, parsed.cells, parsed.values, parsed.tmt_integrator)
    if lab == "unclear":
        return {**out, "outcome": "unclear label", "detail": quote}
    flag = looks_log(parsed.values) if lab == "linear" else None
    return {**out, "outcome": "kept", "label": lab, "quote": quote, "strata": strata_reached(columns),
            **({"looks_log": flag} if flag else {})}


def quotas(records) -> dict:
    """Per split and stratum, the kept linear deposits that reach it."""
    q = {s: {k: 0 for k in STRATA} for s in SPLITS}
    for r in records:
        if r.get("outcome") == "kept" and r.get("label") == "linear":
            for k in r["strata"]:
                q[r["split"]][k] += 1
    return q


def met(q: dict, quota: int = QUOTA) -> bool:
    return all(n >= quota for s in SPLITS for n in q[s].values())


def _read_log(log: Path, order) -> list[dict]:
    if not log.exists():
        return []
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected = [row[0] for row in order[:len(records)]]
    if [r.get("accession") for r in records] != expected:
        raise SystemExit(f"{log} does not follow the frame's order; it was not written by this walk")
    return records


def walk(order, tools: Tools, log: Path, root: Path, limit: int = LIMIT, quota: int = QUOTA,
         workers: int = 4, visit_fn=visit, progress: Callable | None = None) -> list[dict]:
    """order: the frame's [accession, repo, split] rows."""
    records = _read_log(log, order)
    if len(records) >= limit or met(quotas(records), quota):
        return records
    todo = iter(order[len(records):limit])
    log.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as pool, log.open("a", encoding="utf-8", newline="\n") as fh:
        pending: deque = deque()

        def top_up():
            while len(pending) < LOOKAHEAD * workers:
                row = next(todo, None)
                if row is None:
                    return
                pending.append(pool.submit(visit_fn, row[0], row[1], row[2], tools, root))
        top_up()
        while pending:
            record = pending.popleft().result()
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            fh.flush()
            records.append(record)
            if progress:
                progress(records)
            if met(quotas(records), quota):
                for f in pending:
                    f.cancel()
                break
            top_up()
    return records


FAILED_READS = ("fetch failed", "no file list")


def revisit(log: Path, tools: Tools, root: Path, workers: int = 4, visit_fn=visit,
            outcomes=FAILED_READS, select: Callable | None = None) -> list[dict]:
    """Each record whose read failed is visited again with the walk's tools as
    they now are, in its place in the log; the outcome it replaces is kept as
    revisited_from, with any earlier revisit's revisited_from and
    revisited_for (its reasons) inside it. B3's
    walk returned a short FTP read as whole until 2026-11-05, so a transfer
    PRIDE ended early was logged as fetch failed. `select(record)`, when
    given, chooses the records instead (B3's third and fourth visits: the
    records the fixes of 2026-11-06 and 2026-11-07 touch). The log is
    rewritten once, at the end: a
    revisit that stops part way leaves it as it was. Not to be run while the
    walk is writing the log."""
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    todo = [i for i, r in enumerate(records) if (select(r) if select is not None else r.get("outcome") in outcomes)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {i: pool.submit(visit_fn, records[i]["accession"], records[i]["repo"], records[i]["split"],
                                  tools, root) for i in todo}
        done = {}
        for i in todo:
            before = {"outcome": records[i]["outcome"], "detail": records[i].get("detail")}
            for key in ("revisited_for", "revisited_from"):  # an earlier visit's reasons and what it replaced
                if key in records[i]:
                    before[key] = records[i][key]
            done[i] = {**futures[i].result(), "revisited_from": before}
    for i, record in done.items():
        records[i] = record
    tmp = log.with_name(log.name + ".tmp")
    tmp.write_bytes("".join(json.dumps(r, sort_keys=True) + "\n" for r in records).encode("utf-8"))
    tmp.replace(log)
    return records
