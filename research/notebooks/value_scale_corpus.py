"""B3, the corpus (research/value-scale-plan.md; protocol
research/benchmark/protocol-value-scale.md): the walk over the frame with
the real network and the service's parser, the hand audit's sample, and the
diagnostics against valuescale/bank/expectations/b3.json.

    python research/notebooks/value_scale_corpus.py walk [--workers 4]
    python research/notebooks/value_scale_corpus.py audit-sample
    python research/notebooks/value_scale_corpus.py audit-packets
    python research/notebooks/value_scale_corpus.py report

From the repository root, with the vivome environment. The frame comes
from `python -m valuescale.corpus.frame`. The walk's log is
valuescale/corpus/walk.jsonl (one line per listed deposit, in the frame's
order; a stopped walk resumes). Downloads go to
data/incoming/value-scale-corpus/<accession>/, with each parsed table as
table.npz beside its file. No detector statistic, gate or verdict is
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
import zipfile
from collections import Counter
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
HEADER_BYTES = (1 << 20, 16 << 20)
BIG_PARSE = 200 << 20
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
        dest = folder / _safe(f.path)
        remote.download(f, dest, workers=8)  # the host's slots cap the connections
        rec = {"bytes": dest.stat().st_size, "sha256": remote.sha256(dest)}
        if entry.member is None:
            return dest, rec
        target = folder / "members" / _safe(entry.member)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_name(target.name + ".part")
            with zipfile.ZipFile(dest) as zf, zf.open(entry.member) as src, part.open("wb") as out:
                while block := src.read(4 << 20):
                    out.write(block)
            part.replace(target)
        rec.update(member_bytes=target.stat().st_size, member_sha256=remote.sha256(target))
        return target, rec

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
                text = path.read_bytes().decode("utf-8", errors="replace")
                header = remote.first_line_fields(text[:HEADER_BYTES[1]].encode("utf-8")) or []
                raw = alignment.parse_matrix_csv(text)
                parsed = draw.Parsed(list(raw.cell_ids), raw.values, tables.is_tmt_integrator(header))
                ids = raw.gene_names
        finally:
            if big:
                _big.release()
        np.savez_compressed(path.parent / "table.npz" if path.parent.name != "members" else path.parent.parent / "table.npz",
                            values=np.asarray(parsed.values, dtype=np.float32), cells=np.asarray(parsed.cells, dtype=str),
                            ids=np.asarray(ids, dtype=str))
        return parsed

    return draw.Tools(list_files, columns_of, members_of, fetch, parse, columns_of)


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


def _records() -> list[dict]:
    return [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()]


def audit_sample(records) -> dict:
    """A seeded 20% of each split's labelled deposits, drawn in the frame's
    order by sha256("20261103:audit:" + accession)."""
    out = {}
    for split in draw.SPLITS:
        labelled = sorted((r["accession"] for r in records if r["outcome"] == "kept" and r["split"] == split),
                          key=lambda a: hashlib.sha256(f"20261103:audit:{a}".encode()).hexdigest())
        out[split] = sorted(labelled[:max(1, round(AUDIT_SHARE * len(labelled)))]) if labelled else []
    return out


def cmd_audit_sample(args) -> int:
    sample = audit_sample(_records())
    existing = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else {}
    existing["sample"] = sample
    existing.setdefault("verdicts", {})
    AUDIT.write_bytes((json.dumps(existing, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    print({k: len(v) for k, v in sample.items()})
    return 0


PRIDE_PROJECT = "https://www.ebi.ac.uk/pride/ws/archive/v2/projects/{}"


def _local_table(r: dict) -> Path:
    folder = DATA / r["accession"]
    return folder / "members" / _safe(r["member"]) if r.get("member") else folder / _safe(r["file"])


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


def cmd_audit_packets(args) -> int:
    """For each sampled deposit: its label, the table's place in the deposit,
    the table's column names (never its values), the deposit's file names,
    and its methods text. Written to data/incoming/value-scale-corpus/audit/."""
    records = {r["accession"]: r for r in _records()}
    record = frame.load()
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    out = DATA / "audit"
    out.mkdir(parents=True, exist_ok=True)
    tools = make_tools(record)
    for split, accs in audit["sample"].items():
        for acc in accs:
            path = out / f"{acc}.md"
            if path.exists():
                continue
            r = records[acc]
            with _local_table(r).open("r", encoding="utf-8-sig", errors="replace") as fh:
                header = remote.first_line_fields((fh.readline()).encode("utf-8")) or []
            names = sorted(f.path for f in tools.list_files(acc, r["repo"]))
            text = [f"# {acc} ({split}, {r['repo']})", "",
                    f"Label by script: **{r['label']}** ({r['software']}, {r['kind']}, layout {r['layout']}).",
                    f"Table: `{r['file']}`" + (f", member `{r['member']}`" if r.get("member") else "")
                    + f"; {r['columns']} columns, {r['rows']} rows; quantity {r.get('quantity')}.", "",
                    f"## The table's column names ({len(header)})", "", ", ".join(header[:120])
                    + (" ..." if len(header) > 120 else ""), "",
                    f"## The deposit's files ({len(names)})", "", "\n".join(names[:300])
                    + ("\n..." if len(names) > 300 else ""), "",
                    "## Methods", "", _methods(r, record)]
            path.write_bytes(("\n".join(text) + "\n").encode("utf-8"))
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
    bad_records = [r["accession"] for r in kept if not (
        r.get("url") and isinstance(r.get("bytes"), int) and re.fullmatch(r"[0-9a-f]{64}", r.get("sha256", ""))
        and r["columns"] >= draw.MIN_COLUMNS and r["rows"] >= draw.MIN_ROWS and r.get("quote"))]
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
    return {"step": "b3", "listed": listed, "kept": len(kept), "after_audit": len(final), "quotas": q,
            "rows": rows}


def render(rep: dict) -> str:
    lines = ["# B3 diagnostics: the corpus", "",
             "Generated by `research/notebooks/value_scale_corpus.py report` from `valuescale/corpus/walk.jsonl`,",
             "`frame.json` and `audit.json`, against `valuescale/bank/expectations/b3.json`. No detector statistic",
             "was computed on any drawn deposit.", "",
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
    sub.add_parser("audit-sample")
    sub.add_parser("audit-packets")
    sub.add_parser("report")
    args = parser.parse_args()
    return {"walk": cmd_walk, "audit-sample": cmd_audit_sample, "audit-packets": cmd_audit_packets,
            "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
