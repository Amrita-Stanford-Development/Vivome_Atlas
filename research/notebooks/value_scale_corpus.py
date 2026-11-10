"""B3, the corpus (research/value-scale-plan.md; protocol
research/benchmark/protocol-value-scale.md): the walk over the frame with
the real network and the service's parser, the hand audit's sample, and the
diagnostics against valuescale/bank/expectations/b3.json. The clean-up of
2026-11-06 (protocol amendment 3): cleanup-selection chooses the records
its fixes touch, revisit --cleanup visits them a third time, and
audit-cleanup lists the tables that visit adds for the audit, against
valuescale/bank/expectations/b3_revisit2.json. The fourth visit (2026-11-07,
protocol amendment 4): fourth-visit-selection chooses the records the fixes
found after the third visit touch, revisit --fourth visits them, against
valuescale/bank/expectations/b3_revisit3.json, and audit-cleanup then lists
the tables either visit added.

    python research/notebooks/value_scale_corpus.py walk [--workers 4]
    python research/notebooks/value_scale_corpus.py revisit [--workers 4]
    python research/notebooks/value_scale_corpus.py cleanup-selection [--workers 4]
    python research/notebooks/value_scale_corpus.py revisit --cleanup [--workers 4]
    python research/notebooks/value_scale_corpus.py fourth-visit-selection [--workers 4]
    python research/notebooks/value_scale_corpus.py revisit --fourth [--workers 4]
    python research/notebooks/value_scale_corpus.py audit-sample
    python research/notebooks/value_scale_corpus.py audit-cleanup
    python research/notebooks/value_scale_corpus.py audit-packets
    python research/notebooks/value_scale_corpus.py report

From the repository root, with the vivome environment. The frame comes
from `python -m valuescale.corpus.frame`. The walk's log is
valuescale/corpus/walk.jsonl (one line per listed deposit, in the frame's
order; a stopped walk resumes). Downloads go to
data/incoming/value-scale-corpus/<accession>/, with the deposit's parsed
table as <accession>/table.npz. No detector statistic, gate or verdict is
computed on any drawn deposit here: the report counts records, quotas and
the audit, from the log alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from service.pipeline import alignment  # noqa: E402
from valuescale.corpus import denylist, draw, frame, remote, tables  # noqa: E402

DATA = REPO / "data" / "incoming" / "value-scale-corpus"
LOG = REPO / "valuescale" / "corpus" / "walk.jsonl"
AUDIT = REPO / "valuescale" / "corpus" / "audit.json"
EXPECTATIONS = REPO / "valuescale" / "bank" / "expectations" / "b3.json"
OUT = REPO / "research" / "notebook-outputs" / "value_scale_b3"
HEADER_BYTES = (64 << 10, 1 << 20, 16 << 20)  # most headers fit the first: PRIDE's FTP gives ~90 KB/s per connection
BIG_PARSE = 50 << 20  # parsed one at a time: the PC runs other jobs too
AUDIT_SHARE = 0.2
_big = threading.Semaphore(1)


def check_patterns() -> None:
    """tables.py copies the parser's quantity patterns; they must still match."""
    pairs = [(tables.MAXQUANT_QUANTITIES, alignment._MAXQUANT_QUANTITIES),
             (tables.FRAGPIPE_LFQ_QUANTITIES, alignment._FRAGPIPE_LFQ_QUANTITIES),
             ((tables.SPECTRONAUT_QUANTITY,), alignment._SPECTRONAUT_QUANTITIES)]
    for mine, theirs in pairs:
        if tuple(mine) != tuple(p.pattern for p in theirs):
            raise SystemExit(f"valuescale/corpus/tables.py's patterns differ from the parser's: {mine}")
    if tables.DIA_NN_ANNOTATION != alignment._DIA_NN_ANNOTATION_COLUMNS:
        raise SystemExit("valuescale/corpus/tables.py's DIA-NN annotation columns differ from the parser's")
    if tables.MAXQUANT_IDS != alignment._MAXQUANT_IDS:
        raise SystemExit("valuescale/corpus/tables.py's MaxQuant column differs from the parser's")
    if tables.COMMA_NUMBER != alignment._COMMA_NUMBER.pattern:
        raise SystemExit("valuescale/corpus/tables.py's comma-number pattern differs from the parser's")

def _safe(path: str) -> Path:
    return Path(*[re.sub(r'[<>:"|?*\\]', "_", part) or "_" for part in path.split("/") if part not in ("", ".", "..")])


def _text_header(read) -> list | None:
    for n in HEADER_BYTES:
        data = read(n)
        fields = remote.first_line_fields(data)
        if fields is not None or len(data) < n:
            return fields
    return None


MASSIVE_FOLDERS = DATA / "massive_folders.json"
_folders_lock = threading.Lock()
_folders: dict = {}


def massive_folders() -> dict:
    """MSV -> its folder on massive-ftp.ucsd.edu, listed once and cached."""
    with _folders_lock:
        if not _folders:
            if MASSIVE_FOLDERS.exists():
                _folders.update(json.loads(MASSIVE_FOLDERS.read_text(encoding="utf-8")))
            else:
                _folders.update(remote.massive_folders())
                MASSIVE_FOLDERS.write_bytes((json.dumps(_folders, sort_keys=True) + "\n").encode("utf-8"))
        return _folders


def make_tools(record: dict) -> draw.Tools:
    massive = record["massive"]

    def list_files(accession, repo):
        if repo == "PRIDE":
            return remote.pride_files(accession)
        msv, ftp = massive[accession]
        denylist.check(msv or "", ftp or "")
        if not ftp:
            raise OSError("the announcement names no MassIVE FTP folder")
        return remote.massive_files(remote.massive_root(ftp, msv, massive_folders()))

    def columns_of(entry):
        f = entry.file
        if entry.member is None:
            if f.name.lower().endswith(".parquet"):
                return remote.parquet_columns(f.url, f.size)
            return _text_header(lambda n: remote.head(f.url, f.size, n))
        if entry.member.lower().endswith(".parquet"):
            return None
        return _text_header(lambda n: remote.member_head(f.url, f.size, entry.member, n))

    def members_of(f):
        return remote.zip_members(f.url, f.size)

    def fetch(entry, folder):
        f = entry.file
        if entry.member is None:
            dest = folder / _safe(f.path)
            remote.download(f, dest)  # remote.STREAMS connections: the walk keeps the host's other slots
            return dest, {"bytes": dest.stat().st_size, "sha256": remote.sha256(dest)}
        # a member alone, by range: the archive itself is never fetched whole
        target = folder / "members" / _safe(entry.member)
        if target.exists():
            rec = {"member_bytes": target.stat().st_size, "member_sha256": remote.sha256(target)}
        else:
            rec = remote.fetch_member(f, entry.member, target)
        return target, {"archive_bytes": f.size, **rec}

    def parse(cand, path):
        big = path.stat().st_size > BIG_PARSE
        if big:
            _big.acquire()
        try:
            if cand.kind == "proteome_discoverer":
                t = tables.read_proteome_discoverer(path)
                parsed = draw.Parsed(t.cells, t.values)
                ids = t.ids
            elif cand.layout in ("long", "spectronaut_long"):
                t = tables.read_long(path, "diann_report" if cand.layout == "long" else cand.layout)
                parsed = draw.Parsed(t.cells, t.values, False, t.quantity)
                ids = t.ids
            else:
                text = tables.read_text(path)  # decoded as the service decodes an upload
                header = remote.first_line_fields(text[:HEADER_BYTES[1]].encode("utf-8")) or []
                raw = alignment.parse_matrix_csv(text)
                parsed = draw.Parsed(list(raw.cell_ids), raw.values, alignment.header_layout(header) == "fragpipe-tmt")
                ids = raw.gene_names
        finally:
            if big:
                _big.release()
        np.savez_compressed(DATA / path.relative_to(DATA).parts[0] / "table.npz",  # the deposit's folder, however deep the file
                            values=np.asarray(parsed.values, dtype=np.float32), cells=np.asarray(parsed.cells, dtype=str),
                            ids=np.asarray(ids, dtype=str))
        return parsed

    def refuse(cand, header):
        """The parser's refusals from the header alone (alignment.refuse_by_header:
        a MaxQuant SILAC or TMT search), so the table need not come down first. The header is the parser's for
        any header without a line break inside quotes."""
        if cand.kind == "proteome_discoverer" or cand.layout in ("long", "spectronaut_long"):
            return None  # read by tables.py, not by the service's parser
        alignment.refuse_by_header(header)
        return None

    return draw.Tools(list_files, columns_of, members_of, fetch, parse, columns_of, refuse)


def cmd_walk(args) -> int:
    check_patterns()
    record = frame.load()
    for acc, *_ in record["order"]:
        denylist.check(acc)
    started = [0]

    def progress(records):
        n = len(records)
        if n - started[0] >= 50:
            started[0] = n
            q = draw.quotas(records)
            outcomes = Counter(r["outcome"] for r in records)
            print(f"{n} listed; kept {outcomes['kept']}; quotas {json.dumps(q)}", flush=True)

    records = draw.walk(record["order"], make_tools(record), LOG, DATA, limit=args.limit, workers=args.workers,
                        progress=progress)
    print(f"done: {len(records)} listed; {Counter(r['outcome'] for r in records)}; {json.dumps(draw.quotas(records))}")
    return 0


def cmd_revisit(args) -> int:
    """The walk's failed reads, visited again once the walk has stopped; with
    --cleanup, the records in CLEANUP instead, each with its reasons as
    revisited_for; with --fourth, the records in FOURTH."""
    check_patterns()
    if getattr(args, "fourth", False):
        chosen = json.loads(FOURTH.read_text(encoding="utf-8"))["records"]
        done = sorted(r["accession"] for r in _records()
                      if r["accession"] in chosen and r.get("revisited_for") == chosen[r["accession"]])
        if done:  # a record the third visit took may be taken again, by its own new reasons
            raise SystemExit(f"the fourth visit is made once: {len(done)} chosen records already hold its reasons "
                             f"({', '.join(done[:5])})")
        return _visit_chosen(chosen, args.workers)
    if not args.cleanup:
        before = Counter(r["outcome"] for r in _records() if r["outcome"] in draw.FAILED_READS)
        records = draw.revisit(LOG, make_tools(frame.load()), DATA, workers=args.workers)
        again = [r for r in records if "revisited_from" in r]
        print(f"revisited {sum(before.values())} ({dict(before)}): now {dict(Counter(r['outcome'] for r in again))}")
        return 0
    chosen = json.loads(CLEANUP.read_text(encoding="utf-8"))["records"]
    done = sorted(r["accession"] for r in _records() if r["accession"] in chosen and "revisited_for" in r)
    if done:  # a second run would nest the third visit inside a fourth
        raise SystemExit(f"the third visit is made once: {len(done)} chosen records already hold revisited_for "
                         f"({', '.join(done[:5])})")
    return _visit_chosen(chosen, args.workers)


def _visit_chosen(chosen: dict, workers: int) -> int:
    """The chosen records visited again in their places, each with its
    reasons as revisited_for."""
    tools = make_tools(frame.load())
    before = Counter(r["outcome"] for r in _records() if r["accession"] in chosen)

    def visit_fn(acc, repo, split, tools, root):
        return {**draw.visit(acc, repo, split, tools, root), "revisited_for": chosen[acc]}
    records = draw.revisit(LOG, tools, DATA, workers=workers, visit_fn=visit_fn,
                           select=lambda r: r["accession"] in chosen)
    now = Counter(r["outcome"] for r in records if r["accession"] in chosen)
    print(f"revisited {sum(before.values())} ({dict(before)}): now {dict(now)}")
    return 0


# The clean-up before B4 (2026-11-06; research/value-scale-plan.md, B3): the
# faults in our own code that B3's walk met, fixed in the parser, the site's
# check and the corpus tool. CLEANUP lists the records they touch; the third
# visit (revisit --cleanup) visits those again.
CLEANUP = REPO / "valuescale" / "corpus" / "cleanup_20261106.json"
_NEWLINE_IN_FIELD = "new-line character seen in unquoted field"  # csv's error on a lone CR before the fix


def _reader_before_cleanup(header: list) -> str:
    """The parser's reader for a header before the clean-up (commit 3c053c9):
    MaxQuant only with both "Majority protein IDs" and "Gene names", spelled
    so; Spectronaut only with "PG.Genes"."""
    if "Majority protein IDs" in header and "Gene names" in header:
        return "maxquant"
    if "PG.Genes" in header and any(alignment._SPECTRONAUT_QUANTITIES[0].match(h) for h in header):
        return "spectronaut"
    if all(m in header for m in alignment._FRAGPIPE_LFQ_MARKERS):
        return "fragpipe-lfq"
    if "Genes" in header:
        return "dia-nn"
    if "Gene" in header:
        return "fragpipe-tmt"
    return "matrix"


def cleanup_reasons(r: dict) -> list:
    """Why the clean-up touches a record, from the log and the local table's
    header and encoding (never its values)."""
    reasons = []
    detail = str(r.get("detail") or "")
    if r["outcome"] in draw.FAILED_READS:
        reasons.append("failed read")
    if _NEWLINE_IN_FIELD in detail:
        reasons.append("line endings")
    if "UnicodeDecodeError" in detail:
        reasons.append("decoding")
    chosen = r.get("member") or r.get("file")
    if chosen and tables.is_mac_companion(chosen):
        reasons.append("macOS file")
    if r.get("file") and r.get("kind") != "proteome_discoverer" and r.get("layout") in ("wide", "spectronaut_pivot"):
        path = _local_table(r)
        if path.exists() and path.suffix.lower() != ".parquet":
            if tables.text_encoding(path) != "utf-8-sig" and "decoding" not in reasons:
                reasons.append("decoding")
            header, _ = _header_lines(path, 0)
            if _reader_before_cleanup(header) != alignment.header_layout(header):
                reasons.append("reader")
    return reasons


def _zero_columns_header_now(r: dict, tools: draw.Tools):
    """A "too few columns" record's quantity columns as the header reader now
    reads its header (a UTF-16 header read as UTF-8 named none); None when
    the header cannot be read."""
    entry = tables.Entry(remote.File(r["file"], r["listed_bytes"], r["url"]), r.get("member"), 0)
    try:
        header = tools.header(entry)
    except denylist.SealedData:
        raise
    except Exception:  # noqa: BLE001 - a read that fails now is the server's, not the fault's
        return None
    return tables.quantity_columns(r["kind"], r["layout"], header) if header else None


def cmd_cleanup_selection(args) -> int:
    """CLEANUP: each record the clean-up touches, with its reasons. The 199
    "too few columns" records whose header named no quantity column have
    their header read again (the header alone); the rest is the log and the
    local tables' headers."""
    check_patterns()
    records = _records()
    chosen = {}
    for r in records:
        reasons = cleanup_reasons(r)
        if reasons:
            chosen[r["accession"]] = reasons
    zero = [r for r in records if r["outcome"] == "too few columns" and r.get("header_columns") == 0]
    tools = make_tools(frame.load())
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        now = list(pool.map(lambda r: _zero_columns_header_now(r, tools), zero))
    probe = {r["accession"]: n for r, n in zip(zero, now)}
    for acc, n in probe.items():
        if n:  # names some now; a header that cannot be read now (None) is the server's, not the fault's
            chosen.setdefault(acc, []).append("header")
    out = {"about": "The records the clean-up of 2026-11-06 touches, each with its reasons "
                    "(research/notebooks/value_scale_corpus.py cleanup-selection; revisit --cleanup visits them).",
           "reasons": dict(Counter(x for v in chosen.values() for x in v).most_common()),
           "probe": {"read": len(probe), "now_nonzero": sum(1 for n in probe.values() if n), "now_unreadable":
                     sum(1 for n in probe.values() if n is None)},
           "records": dict(sorted(chosen.items()))}
    CLEANUP.write_bytes((json.dumps(out, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({k: out[k] for k in ("reasons", "probe")}), len(chosen))
    return 0


# The fourth visit (owner, 2026-11-07): the faults of our own found after the
# third visit (research/notebook-outputs/value_scale_b3/notes.md, "Found after
# the third visit") and the owner's two rulings with them, fixed in the
# parser, the site's check and the corpus tool: a DIA-NN matrix without gene
# names is named by its protein groups; the separator is chosen from the
# header and the line under it; an empty archive member is never the table; a
# number written with a comma is refused in words; MaxQuant's quantity
# columns are known in any case. FOURTH lists the records these touch;
# revisit --fourth visits those again.
FOURTH = REPO / "valuescale" / "corpus" / "cleanup_20261107.json"
_COMMA_IN_DETAIL = re.compile("'" + tables.COMMA_NUMBER + "'")


def _separator_before(r: dict, header_line: str) -> str:
    """The separator before 2026-11-07, from the header line alone: the
    parser's (a tab when there are more tabs than commas), and the long and
    Proteome Discoverer readers' (a tab when there are as many or more)."""
    tabs, commas = header_line.count("\t"), header_line.count(",")
    if r.get("layout") in ("long", "spectronaut_long") or r.get("kind") == "proteome_discoverer":
        return "\t" if tabs >= commas else ","
    return "\t" if tabs > commas else ","


def _first_lines(path: Path) -> tuple[str, str | None]:
    """The header line, and the first line under it that holds anything past
    Perseus's rows: read for their separators alone."""
    with path.open("r", encoding=tables.text_encoding(path), errors="replace", newline="") as fh:
        header = fh.readline().rstrip("\r\n")
        for _ in range(64):
            line = fh.readline()
            if not line:
                break
            if line.strip() and not line.lstrip('"').startswith("#!{"):
                return header, line.rstrip("\r\n")
    return header, None


def fourth_visit_reasons(r: dict) -> list:
    """Why the fixes of 2026-11-07 touch a record, from the log and the local
    table's first lines (their separators and names, never their values)."""
    reasons = []
    detail = str(r.get("detail") or "")
    if r["outcome"] == "unparseable" and "no row has an identifier in 'Genes'" in detail:
        reasons.append("protein groups")
    if r["outcome"] == "unparseable" and _COMMA_IN_DETAIL.search(detail):
        reasons.append("decimal comma")
    if r.get("member") and r.get("member_bytes") == 0:
        reasons.append("empty member")
    if r.get("file") and "empty member" not in reasons:
        path = _local_table(r)
        if path.exists() and path.suffix.lower() != ".parquet":
            header_line, following = _first_lines(path)
            if _separator_before(r, header_line) != remote.delimiter(header_line, following):
                reasons.append("separator")
            header, _ = _header_lines(path, 0)
            exact = [re.compile(p.pattern.replace("(?i)", "")) for p in alignment._MAXQUANT_QUANTITIES]
            if alignment.header_layout(header) == "maxquant" and any(
                    p.match(h) and not e.match(h) for p, e in zip(alignment._MAXQUANT_QUANTITIES, exact) for h in header):
                reasons.append("quantity case")
    return reasons


def _header_decision_now(r: dict, tools: draw.Tools) -> str | None:
    """What the walk decides now from a wide table's header alone (draw.visit,
    step 4): too few columns, unparseable (refused on the header), or fetch.
    None when the header cannot be read now: that is the server's, not the
    fault's."""
    denylist.check(r["accession"])
    entry = tables.Entry(remote.File(r["file"], r["listed_bytes"], r["url"]), r.get("member"), 0)
    try:
        header = tools.header(entry)
    except denylist.SealedData:
        raise
    except Exception:  # noqa: BLE001 - as _zero_columns_header_now
        return None
    if not header:
        return None
    n = tables.quantity_columns(r["kind"], r["layout"], header)
    if n is not None and n < draw.MIN_COLUMNS:
        return "too few columns"
    try:
        tools.refuse(tables.Candidate(r["kind"], r["layout"], entry, ()), header)
    except denylist.SealedData:
        raise
    except Exception:  # noqa: BLE001 - the parser's refusal, in its own words
        return "unparseable"
    return "fetch"


def cmd_fourth_visit_selection(args) -> int:
    """FOURTH: each record the fixes of 2026-11-07 touch, with its reasons,
    from the log and the local tables; and each record the walk decided on a
    wide table's header alone (too few columns, or refused on the header),
    with its header read again (the header alone): the separator rule and
    MaxQuant's names in any case change what the reader makes of a header,
    and those headers were never kept."""
    check_patterns()
    records = _records()
    chosen = {r["accession"]: why for r in records if (why := fourth_visit_reasons(r))}
    judged = [r for r in records if (r["outcome"] == "too few columns" and "header_columns" in r)
              or r.get("refused_on") == "header"]
    tools = make_tools(frame.load())
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        now = list(pool.map(lambda r: _header_decision_now(r, tools), judged))
    for r, decision in zip(judged, now):
        if decision is not None and decision != r["outcome"]:
            chosen.setdefault(r["accession"], []).append("header")
    out = {"about": "The records the fixes of 2026-11-07 touch, each with its reasons "
                    "(research/notebooks/value_scale_corpus.py fourth-visit-selection; revisit --fourth visits them).",
           "reasons": dict(Counter(x for v in chosen.values() for x in v).most_common()),
           "probe": {"read": len(judged),
                     "now_differs": sum(1 for r, d in zip(judged, now) if d is not None and d != r["outcome"]),
                     "now_unreadable": sum(1 for d in now if d is None)},
           "records": dict(sorted(chosen.items()))}
    FOURTH.write_bytes((json.dumps(out, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({k: out[k] for k in ("reasons", "probe")}), len(chosen))
    return 0


def _records() -> list[dict]:
    return [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()]


def audit_sample(records) -> dict:
    """A seeded 20% of each split's labelled deposits, drawn in the frame's
    order by sha256("20261103:audit:" + accession), and every one the walk
    flagged as linear with values that look log (draw.looks_log; R1 of
    protein v2). B3's walk flagged none: the flag came after it."""
    out = {}
    for split in draw.SPLITS:
        kept = [r for r in records if r["outcome"] == "kept" and r["split"] == split]
        labelled = sorted((r["accession"] for r in kept),
                          key=lambda a: hashlib.sha256(f"20261103:audit:{a}".encode()).hexdigest())
        seeded = labelled[:max(1, round(AUDIT_SHARE * len(labelled)))] if labelled else []
        out[split] = sorted(set(seeded) | {r["accession"] for r in kept if r.get("looks_log")})
    return out


def cmd_audit_sample(args) -> int:
    """The sample, drawn once: drawn again after the third visit it would
    shift, as the rank takes in the tables the visit added."""
    sample = audit_sample(_records())
    existing = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else {}
    if existing.get("sample"):
        raise SystemExit(f"{AUDIT} already holds the sample; it is drawn once (b3_revisit2.json's audit)")
    existing["sample"] = sample
    existing.setdefault("verdicts", {})
    AUDIT.write_bytes((json.dumps(existing, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print({k: len(v) for k, v in sample.items()})
    return 0


def newly_kept(records) -> dict:
    """By split, the tables the clean-up's visits (the third and the fourth)
    kept that no visit before the clean-up had kept. An outcome a clean-up
    visit gave carries its reasons (revisited_for), so a table the third
    visit added stays added when the fourth reads it again."""
    def kept_before(prior):
        while prior:
            if prior.get("outcome") == "kept" and "revisited_for" not in prior:
                return True
            prior = prior.get("revisited_from")
        return False
    out = {s: [] for s in draw.SPLITS}
    for r in records:
        if r.get("revisited_for") and r["outcome"] == "kept" and not kept_before(r.get("revisited_from")):
            out[r["split"]].append(r["accession"])
    return {s: sorted(v) for s, v in out.items()}


def cmd_audit_cleanup(args) -> int:
    """audit.json's "cleanup": every table the third visit added, each to be
    judged under b3.json's rubric (b3_revisit2.json's audit)."""
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    audit["cleanup"] = newly_kept(_records())
    AUDIT.write_bytes((json.dumps(audit, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print({k: len(v) for k, v in audit["cleanup"].items()})
    return 0


PRIDE_PROJECT = "https://www.ebi.ac.uk/pride/ws/archive/v2/projects/{}"


def _local_table(r: dict) -> Path:
    folder = DATA / r["accession"]
    return folder / "members" / _safe(r["member"]) if r.get("member") else folder / _safe(r["file"])


def _header_lines(path: Path, most: int = 12) -> tuple[list, list]:
    """The table's header, and the Perseus annotation rows ("#!{...") right
    under it: a table saved from Perseus keeps MaxQuant's column names
    whatever it did to the values. The first row past them is read for its
    separators alone, as the parser reads it (remote.delimiter: a tab-separated
    header whose names hold commas is split on its tabs); no value is
    returned. A parquet table's header is its schema's column names."""
    if path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq
        return list(pq.ParquetFile(path).schema_arrow.names), []
    with path.open("r", encoding=tables.text_encoding(path), errors="replace", newline="") as fh:
        lines = [fh.readline()]
        for _ in range(64):  # up to the first line that holds anything past Perseus's rows
            line = fh.readline()
            lines.append(line)
            if not line or (line.strip() and not line.startswith("#!{")):
                break
    header = remote.first_line_fields("".join(lines).encode("utf-8")) or []
    notes = []
    for line in lines[1:most + 1]:
        line = line.rstrip("\r\n")
        if not line.startswith("#!{"):
            break
        notes.append(line)
    return header, notes


_FAMILIES = {  # kind: the parser's value-column families, in its order of preference
    "maxquant": [("LFQ intensity", tables.MAXQUANT_QUANTITIES[0]), ("Intensity", tables.MAXQUANT_QUANTITIES[1])],
    "fragpipe": [("MaxLFQ Intensity", tables.FRAGPIPE_LFQ_QUANTITIES[0]), ("Intensity", tables.FRAGPIPE_LFQ_QUANTITIES[1])],
    "spectronaut": [("PG.Quantity", tables.SPECTRONAUT_QUANTITY)],
    "proteome_discoverer": [("Abundance", "^" + re.escape(tables.PD_PREFIX))],
}
_RULES = {
    "maxquant": "the parser reads LFQ intensity when any value is above 0, else Intensity",
    "fragpipe": "the parser reads MaxLFQ Intensity when any value is above 0, else Intensity",
    "spectronaut": "the parser reads the PG.Quantity columns",
    "proteome_discoverer": "the reader reads the Abundance columns",
    "diann_matrix": "every column but DIA-NN's annotation columns is a run",
}


def _columns_section(kind: str, layout: str, header: list) -> str:
    """Every column name: the value columns by family first, then the rest,
    none cut off. MaxQuant's value columns came after the first 120 names."""
    if layout in ("long", "spectronaut_long"):
        return (f"## The table's column names ({len(header)})\n\nA long report: its runs are rows; the value column is "
                f"PG.MaxLFQ, else PG.Quantity.\n\n" + ", ".join(header))
    if kind == "diann_matrix":
        families = [("runs", [c for c in header if c.strip() and c not in tables.DIA_NN_ANNOTATION])]
    else:
        families = [(label, [c for c in header if re.match(p, c)]) for label, p in _FAMILIES[kind]]
    used = {c for _, names in families for c in names}
    lines = [f"## Value columns ({_RULES[kind]})", ""]
    lines += [f"{label} ({len(names)}): " + (", ".join(names) or "none") for label, names in families]
    rest = [c for c in header if c not in used]
    lines += ["", f"## The table's other columns ({len(rest)})", "", ", ".join(rest)]
    return "\n".join(lines)


_RAW = re.compile(r"\.(raw|wiff|wiff\.scan|wiff2|mzml|mzxml|mgf|tdf|tdf_bin|baf|d\.zip|raw\.zip|mzml\.gz)$", re.I)


def _files_section(names: list) -> str:
    """Every file but raw instrument data in full; raw files counted by kind."""
    raw = Counter(m.group(1).lower() for n in names if (m := _RAW.search(n)))
    rest = [n for n in names if not _RAW.search(n)]
    counted = ", ".join(f".{k} {v}" for k, v in sorted(raw.items())) or "none"
    return (f"## The deposit's files ({len(names)}: {len(rest)} listed, raw instrument files counted: {counted})\n\n"
            + "\n".join(rest))


def _methods(r: dict, record: dict) -> str:
    """The deposit's own words on how its data were processed: PRIDE's
    project record, or MassIVE's announcement."""
    if r["repo"] == "PRIDE":
        p = remote.get_json(PRIDE_PROJECT.format(r["accession"]))
        refs = "; ".join(x.get("doi") or str(x.get("pubmedID")) for x in p.get("references", []))
        soft = ", ".join(s.get("name", "") for s in p.get("softwares", []))
        return (f"Title: {p.get('title', '')}\n\nReferences: {refs}\n\nSoftware listed: {soft}\n\n"
                f"Data processing protocol:\n{p.get('dataProcessingProtocol', '')}\n\n"
                f"Description:\n{p.get('projectDescription', '')}")
    xml = frame._announcement(r["accession"])
    found = re.findall(r'name="(?:Description|Dataset Description|title|Title)"[^>]*value="([^"]*)"', xml)
    desc = re.findall(r"<Description>(.*?)</Description>", xml, re.S)
    return "\n\n".join([*found, *desc])[:20000]


def _values_section(r: dict) -> str | None:
    """A flagged table's value range (draw.looks_log), for the auditor to
    weigh against its provenance; None for any other table, whose packet
    shows no value."""
    v = r.get("looks_log")
    if not v:
        return None
    return (f"## The values (flagged: 99% of the observed values are under {draw.LOG_CEILING:g})\n\n"
            f"Smallest {v['min']:g}, median {v['median']:g}, 99th percentile {v['p99']:g}, largest {v['max']:g} "
            "(an observed value is finite and not 0).\n\n"
            "Log2 intensities lie in about this range; raw ones mostly far above it, though a small-scale linear "
            "table can lie in it too. Keep the label when the provenance says linear, relabel the table when the "
            "provenance says log, or exclude it when the provenance cannot tell.")


def _packet(r: dict, split: str, header: list, notes: list, names: list, methods: str) -> str:
    """One deposit's packet: its label, the table's place in the deposit, the
    table's column names, its Perseus rows, a flagged table's value range,
    the deposit's file names, and its methods text."""
    text = [f"# {r['accession']} ({split}, {r['repo']})", "",
            f"Label by script: **{r['label']}** ({r['software']}, {r['kind']}, layout {r['layout']}).",
            f"Table: `{r['file']}`" + (f", member `{r['member']}`" if r.get("member") else "")
            + f"; {r['columns']} columns, {r['rows']} rows"
            + (f"; value column {r['quantity']}." if r.get("quantity") else "."), "",
            _columns_section(r["kind"], r["layout"], header), "",
            f"## Annotation rows under the header ({len(notes)})", "",
            "\n".join(n[:300] for n in notes) or "none", ""]
    values = _values_section(r)
    if values:
        text += [values, ""]
    text += [_files_section(names), "", "## Methods", "", methods]
    return "\n".join(text) + "\n"


def cmd_audit_packets(args) -> int:
    """For each sampled deposit, its packet (_packet): the table's column
    names, never its values, but for a table the walk flagged, whose value
    range is shown. Written to data/incoming/value-scale-corpus/audit/."""
    records = {r["accession"]: r for r in _records()}
    record = frame.load()
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    out = DATA / "audit"
    out.mkdir(parents=True, exist_ok=True)
    tools = make_tools(record)
    for split, accs in [*audit["sample"].items(), *audit.get("cleanup", {}).items()]:
        for acc in accs:
            path = out / f"{acc}.md"
            if path.exists():
                continue
            r = records[acc]
            header, notes = _header_lines(_local_table(r))
            names = sorted(f.path for f in tools.list_files(acc, r["repo"]))
            path.write_bytes(_packet(r, split, header, notes, names, _methods(r, record)).encode("utf-8"))
            print(f"  {acc}", flush=True)
    return 0


def report(records, record, audit) -> dict:
    listed = len(records)
    kept = [r for r in records if r["outcome"] == "kept"]
    audit_verdicts = audit.get("verdicts", {})
    disagree = {a for a, v in audit_verdicts.items() if v.get("agrees") is False}
    final = [r for r in kept if r["accession"] not in disagree]
    q = draw.quotas(final)
    sample = [a for s in audit.get("sample", {}).values() for a in s]
    judged = [a for a in sample if a in audit_verdicts]
    agree = sum(1 for a in judged if audit_verdicts[a].get("agrees"))
    def complete(r):  # a member's record carries the member's size and sha256 and the archive's listed size
        size, sha = (r.get("member_bytes"), r.get("member_sha256", "")) if r.get("member") else (r.get("bytes"), r.get("sha256", ""))
        return bool(r.get("url") and isinstance(size, int) and re.fullmatch(r"[0-9a-f]{64}", sha)
                    and r["columns"] >= draw.MIN_COLUMNS and r["rows"] >= draw.MIN_ROWS and r.get("quote"))
    bad_records = [r["accession"] for r in kept if not complete(r)]
    outcomes = Counter(r["outcome"] for r in records)
    software = Counter(r["software"] for r in final if r["label"] == "linear")
    real_log = Counter(r["split"] for r in final if r["label"] == "log")
    sealed_seen = [r["accession"] for r in records if r["accession"] in denylist.SEALED]
    c = record["counts"]
    rows = {
        "B3_frame": {"found": {k: c[k] for k in ("kept", "dropped_sealed", "dropped_tracked", "frame")}
                     | {"calibration_share": round(c["calibration"] / c["frame"], 4)},
                     "pass": c["kept"] == 18859 and c["dropped_sealed"] <= 4 and 20 <= c["dropped_tracked"] <= 101
                     and 0.48 <= c["calibration"] / c["frame"] <= 0.52},
        "B3_records": {"found": f"{len(kept) - len(bad_records)} of {len(kept)} kept records complete",
                       "incomplete": bad_records, "pass": not bad_records},
        "B3_quota_S1": {"found": {s: q[s]["S1"] for s in draw.SPLITS},
                        "pass": all(q[s]["S1"] >= draw.QUOTA for s in draw.SPLITS)},
        "B3_quota_S2": {"found": {s: q[s]["S2"] for s in draw.SPLITS},
                        "pass": all(q[s]["S2"] >= draw.QUOTA for s in draw.SPLITS)},
        "B3_quota_S3": {"found": {s: q[s]["S3"] for s in draw.SPLITS},
                        "pass": any(q[s]["S3"] < draw.QUOTA for s in draw.SPLITS)},
        "B3_stop": {"found": listed, "pass": listed == draw.LIMIT},
        "B3_yield": {"found": round(100 * len(kept) / listed, 2) if listed else None,
                     "pass": bool(listed) and 3 <= 100 * len(kept) / listed <= 15},
        "B3_skips": {"found": dict(outcomes.most_common()),
                     "pass": bool(listed) and outcomes.most_common(1)[0][0] == "no candidate"
                     and outcomes["no candidate"] > listed / 2},
        "B3_real_log": {"found": dict(real_log), "pass": all(real_log[s] < draw.QUOTA for s in draw.SPLITS)},
        "B3_software": {"found": dict(software.most_common()),
                        "pass": bool(software) and software.most_common(1)[0][0] in ("DIA-NN", "MaxQuant")},
        "B3_audit": {"found": {"sampled": len(sample), "judged": len(judged), "agree": agree,
                               "rate": round(agree / len(judged), 4) if judged else None},
                     "pass": bool(judged) and len(judged) == len(sample) and agree / len(judged) >= 0.9},
        "B3_sealed": {"found": sealed_seen, "pass": not sealed_seen},
    }
    if "cleanup" in audit:  # the tables the clean-up's visits added (b3_revisit2.json, b3_revisit3.json)
        added = [a for s in audit["cleanup"].values() for a in s]
        judged_added = [a for a in added if a in audit_verdicts]
        agree_added = sum(1 for a in judged_added if audit_verdicts[a].get("agrees"))
        rows["B3_audit_cleanup"] = {
            "found": {"added": len(added), "judged": len(judged_added), "agree": agree_added,
                      "rate": round(agree_added / len(judged_added), 4) if judged_added else None},
            "pass": len(judged_added) == len(added) and (not added or agree_added / len(judged_added) >= 0.9)}
    return {"step": "b3", "listed": listed, "kept": len(kept), "after_audit": len(final), "quotas": q,
            "rows": rows}


def render(rep: dict) -> str:
    lines = ["# B3 diagnostics: the corpus", "",
             "Generated by `research/notebooks/value_scale_corpus.py report` from `valuescale/corpus/walk.jsonl`,",
             "`frame.json` and `audit.json`, against `valuescale/bank/expectations/b3.json` (B3_audit_cleanup:",
             "`b3_revisit2.json` and `b3_revisit3.json`, the third and fourth visits). No detector statistic was",
             "computed on any drawn deposit.", "",
             f"Listed {rep['listed']}; kept {rep['kept']}; after the audit {rep['after_audit']}.", "",
             "| Row | Pass | Found |", "|---|---|---|"]
    for name, row in rep["rows"].items():
        found = json.dumps(row["found"], sort_keys=True).replace("|", "/")
        lines.append(f"| {name} | {'PASS' if row['pass'] else 'FAIL'} | {found} |")
    return "\n".join(lines) + "\n"


def cmd_report(args) -> int:
    rep = report(_records(), frame.load(), json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else {})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_bytes((json.dumps(rep, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    (OUT / "report.md").write_bytes(render(rep).encode("utf-8"))
    print(render(rep))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("walk")
    w.add_argument("--workers", type=int, default=8)
    w.add_argument("--limit", type=int, default=draw.LIMIT)
    r = sub.add_parser("revisit")
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--cleanup", action="store_true", help="the records cleanup-selection chose")
    r.add_argument("--fourth", action="store_true", help="the records fourth-visit-selection chose")
    c = sub.add_parser("cleanup-selection")
    c.add_argument("--workers", type=int, default=4)
    f = sub.add_parser("fourth-visit-selection")
    f.add_argument("--workers", type=int, default=4)
    sub.add_parser("audit-sample")
    sub.add_parser("audit-cleanup")
    sub.add_parser("audit-packets")
    sub.add_parser("report")
    args = parser.parse_args()
    return {"walk": cmd_walk, "revisit": cmd_revisit, "cleanup-selection": cmd_cleanup_selection,
            "fourth-visit-selection": cmd_fourth_visit_selection,
            "audit-sample": cmd_audit_sample, "audit-cleanup": cmd_audit_cleanup,
            "audit-packets": cmd_audit_packets, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
