"""The draw's frame (research/benchmark/protocol-value-scale.md, "The frame").

ProteomeXchange's index, downloaded on 2026-11-03, cut to human PRIDE and
MassIVE deposits announced 2020-01-01 to 2026-10-31. Dropped before the
draw: the sealed sets, and every PXD, MSV or IPX identifier in any text file
tracked by git at the protocol's commit (MassIVE rows are checked under
their PXD and MSV identifiers). The rest are sorted, then shuffled with
random.Random(20261103). A deposit goes to calibration when
int(sha256("20261103:" + accession), 16) is even, and to test otherwise.

The index is ProteomeCentral's HTML-flavoured TSV. Each record starts with
a link to GetDataset; a title may hold a line break or a tab; a few bytes
are not UTF-8 (the accessions are ASCII). Records are joined at their
links, and the repository is the first field after the title that names one.

    python -m valuescale.corpus.frame      # from the repository root; writes frame.json

A MassIVE row's MSV identifier and FTP folder come from its ProteomeCentral
announcement, cached in data/incoming/value-scale-corpus/massive_ids.json.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from valuescale.corpus import denylist

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "incoming" / "value-scale-corpus"
INDEX = DATA / "px_index_2026-11-03.tsv"
INDEX_SHA256 = "4002a4fcb830099561c49daf67d04a1a9e109338850a58c8f56817c5ab1ef0ea"
MASSIVE_CACHE = DATA / "massive_ids.json"
OUT = Path(__file__).with_name("frame.json")
PROTOCOL_COMMIT = "26519a8"
SEED = 20261103
FIRST, LAST = "2020-01-01", "2026-10-31"
KEPT_REPOS = ("PRIDE", "MassIVE")
REPOSITORIES = frozenset({"PRIDE", "MassIVE", "iProX", "jPOST", "PanoramaPublic", "PeptideAtlas"})
RECORD_START = '<a href="http://proteomecentral.proteomexchange.org/cgi/GetDataset?ID='
IDENTIFIER = re.compile(r"PXD\d{6}|MSV\d{9}|IPX\d{10}", re.IGNORECASE)
ANNOUNCEMENT = "https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={}&outputMode=XML"
AGENT = {"User-Agent": "valuescale-frame/1"}


@dataclass(frozen=True)
class Row:
    accession: str
    title: str
    repo: str
    species: str
    date: str


def parse_index(raw: bytes) -> list[Row]:
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
    records: list[str] = []
    for line in text.split("\n")[1:]:
        if line.startswith(RECORD_START):
            records.append(line)
        elif line.strip() and records:
            records[-1] += " " + line
    rows = []
    for record in records:
        fields = record.split("\t")
        i = next((k for k in range(2, len(fields)) if fields[k].strip() in REPOSITORIES), None)
        if i is None or len(fields) < i + 6:
            raise ValueError(f"unreadable index record: {record[:160]!r}")
        accession = re.sub(r"<[^>]+>", "", fields[0]).strip()
        rows.append(Row(accession, " ".join(f.strip() for f in fields[1:i]).strip(), fields[i].strip(),
                        fields[i + 1].strip(), fields[i + 5].strip()))
    return rows


def kept(rows: list[Row]) -> list[Row]:
    return [r for r in rows if r.repo in KEPT_REPOS and FIRST <= r.date <= LAST
            and "homo sapiens" in r.species.lower()]


def identifiers(text: str) -> set[str]:
    return {m.upper() for m in IDENTIFIER.findall(text)}


def tracked_identifiers(commit: str = PROTOCOL_COMMIT) -> set[str]:
    """Every identifier in a text file tracked at the commit (git grep -I
    skips binary files)."""
    out = subprocess.run(["git", "grep", "-I", "-i", "-o", "-h", "-E", IDENTIFIER.pattern.replace(r"\d", "[0-9]"),
                          commit], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode not in (0, 1):
        raise RuntimeError(out.stderr)
    return identifiers(out.stdout)


def massive_from_xml(xml: str) -> tuple[str | None, str | None]:
    msv = re.search(r'name="MassIVE dataset identifier" value="(MSV\d{9})"', xml)
    ftp = re.search(r'name="Dataset FTP location" value="(ftp://massive[^"]+)"', xml)
    return (msv.group(1) if msv else None, ftp.group(1) if ftp else None)


def _announcement(accession: str, tries: int = 6) -> str:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(ANNOUNCEMENT.format(accession), headers=AGENT)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except OSError as exc:
            last = exc
            time.sleep(min(2 ** attempt, 30))
    raise OSError(f"{accession}: {last}")


def massive_ids(rows: list[Row], cache: Path = MASSIVE_CACHE, workers: int = 4) -> dict[str, tuple]:
    """PXD -> (MSV, FTP folder) for every MassIVE row, cached."""
    known = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    todo = sorted({r.accession for r in rows if r.repo == "MassIVE"} - set(known))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, (acc, xml) in enumerate(zip(todo, pool.map(_announcement, todo)), 1):
            known[acc] = list(massive_from_xml(xml))
            if n % 100 == 0 or n == len(todo):
                cache.write_bytes((json.dumps(known, indent=0, sort_keys=True) + "\n").encode("utf-8"))
                print(f"  MassIVE announcements: {n} of {len(todo)}", flush=True)
    return {acc: tuple(v) for acc, v in known.items()}


def deny(rows: list[Row], tracked: set[str], massive: dict[str, tuple]) -> tuple[list[Row], dict]:
    keep, dropped = [], {"sealed": [], "tracked": []}
    for r in rows:
        names = {r.accession.upper()}
        if r.repo == "MassIVE":
            msv = massive[r.accession][0]  # a KeyError means the lookup was skipped
            names |= {msv} if msv else set()
        if names & denylist.SEALED:
            dropped["sealed"].append(r.accession)
        elif names & tracked:
            dropped["tracked"].append(r.accession)
        else:
            keep.append(r)
    return keep, {k: sorted(v) for k, v in dropped.items()}


def order(accessions) -> list[str]:
    accs = sorted(set(accessions))
    random.Random(SEED).shuffle(accs)
    return accs


def split_of(accession: str) -> str:
    return "calibration" if int(hashlib.sha256(f"{SEED}:{accession}".encode()).hexdigest(), 16) % 2 == 0 else "test"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    if _sha256(INDEX) != INDEX_SHA256:
        raise SystemExit(f"{INDEX} does not match the protocol's sha256")
    rows = parse_index(INDEX.read_bytes())
    cut = kept(rows)
    massive = massive_ids(cut)
    keep, dropped = deny(cut, tracked_identifiers(), massive)
    repo = {r.accession: r.repo for r in keep}
    walk = order(repo)
    return {
        "about": "The draw's frame (research/benchmark/protocol-value-scale.md); valuescale/corpus/frame.py writes it.",
        "index": {"path": INDEX.relative_to(REPO).as_posix(), "sha256": INDEX_SHA256},
        "protocol_commit": PROTOCOL_COMMIT, "seed": SEED,
        "counts": {"index_records": len(rows), "kept": len(cut), "dropped_sealed": len(dropped["sealed"]),
                   "dropped_tracked": len(dropped["tracked"]), "frame": len(walk),
                   "calibration": sum(split_of(a) == "calibration" for a in walk)},
        "dropped": dropped,
        "massive": {a: list(massive[a]) for a in walk if repo[a] == "MassIVE"},
        "order": [[a, repo[a], split_of(a)] for a in walk],
    }


def write(record: dict, path: Path = OUT) -> None:
    """JSON with one frame row per line, so a diff shows what moved."""
    head = {k: v for k, v in record.items() if k not in ("order", "massive")}
    lines = json.dumps(head, indent=1)[:-2].rstrip() + ",\n"
    lines += ' "massive": {\n' + ",\n".join(f"  {json.dumps(a)}: {json.dumps(v)}"
                                           for a, v in record["massive"].items()) + "\n },\n"
    lines += ' "order": [\n' + ",\n".join(f"  {json.dumps(r)}" for r in record["order"]) + "\n ]\n}\n"
    json.loads(lines)
    path.write_bytes(lines.encode("utf-8"))


def load(path: Path = OUT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    record = build()
    write(record)
    print(json.dumps(record["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
