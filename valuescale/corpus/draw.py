"""B3's walk over the frame (research/benchmark/protocol-value-scale.md, "Tables").

For each deposit, in the frame's order:
1. list its files (no file list: the listing failed after retries);
2. choose its one table (tables.first_candidate; no candidate);
3. a single file over tables.FILE_MAX is too large;
4. a wide table's header is read first: when no quantity family reaches 20
   columns, the deposit is skipped as too few columns without the full fetch;
5. fetch it, with its size and sha256 (fetch failed);
6. parse it (unparseable), then at least 20 columns and 200 rows;
7. label it (tables.label; unclear label).

Each deposit's outcome is one line of the walk's log, written in the frame's
order whatever finishes first, so a stopped walk resumes where it stopped.
The walk stops when every quota is met in both splits (QUOTA linear
deposits reaching each stratum), or after LIMIT deposits have been listed.

The network and the parser come in as Tools, so the walk is tested without
either; research/notebooks/value_scale_corpus.py supplies the real ones.
No statistic of a table's values is computed here.
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
    lab, quote = tables.label(cand.kind, parsed.cells, parsed.values, parsed.tmt_integrator)
    if lab == "unclear":
        return {**out, "outcome": "unclear label", "detail": quote}
    return {**out, "outcome": "kept", "label": lab, "quote": quote, "strata": strata_reached(columns)}


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
