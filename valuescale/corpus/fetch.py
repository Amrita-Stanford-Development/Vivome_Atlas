"""Fetches the diagnostic bank's downloads and records every source file's
size and sha256 (bank-files.json), local files included.

    python -m valuescale.corpus.fetch            # from the repository root
    python -m valuescale.corpus.fetch --only pxd049412_hela250pg,cptac_ccrcc_tumor

Downloads go to data/incoming/value-scale-bank/<accession>/ (gitignored).
PRIDE throttles each connection, so a file whose server answers range
requests is fetched in 8 MiB ranges on several connections at once, as
scripts/fetch_public_sets.py does; a server that ignores ranges (Google
Drive, GitHub raw) is read in one stream. A download resumes from its
.part file. Every path and URL passes denylist.check first. A file already
recorded must still match its sha256, or the run stops: the bank does not
change under the diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import shutil
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from valuescale.corpus import denylist

REPO = Path(__file__).resolve().parents[2]
BANK = Path(__file__).with_name("bank.json")
RECORD = Path(__file__).with_name("bank-files.json")
ROOT = REPO / "data" / "incoming" / "value-scale-bank"
CHUNK = 8 << 20
AGENT = {"User-Agent": "valuescale-fetch/1"}


def load_bank(path: Path = BANK) -> dict:
    bank = json.loads(path.read_text(encoding="utf-8"))
    for entry in bank["entries"]:
        denylist.check(entry["id"], entry["accession"], entry.get("path", ""), entry.get("url", ""))
    return bank


def source_path(entry: dict, root: Path = ROOT) -> Path:
    """Where an entry's source file lives: its repository path, or its download."""
    if "path" in entry:
        return REPO / entry["path"]
    name = entry.get("file") or entry["url"].split("?")[0].rsplit("/", 1)[1]
    return root / entry["accession"] / name


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _ranged_size(url: str) -> int | None:
    """The file's size when the server honours a one-byte range request, else None."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0", **AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        crange = r.headers.get("Content-Range", "")
        if r.status == 206 and "/" in crange:
            return int(crange.rsplit("/", 1)[1])
    return None


def _range(url: str, start: int, end: int, tries: int = 6) -> bytes:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}", **AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if r.status != 206 or len(data) != end - start + 1:
                raise OSError(f"HTTP {r.status}, {len(data)} of {end - start + 1} bytes")
            return data
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            last = exc
            time.sleep(min(2 ** attempt, 30))
    raise OSError(f"{url} bytes {start}-{end}: {last}")


def _download(url: str, dest: Path, workers: int) -> None:
    part = dest.with_name(dest.name + ".part")
    size = _ranged_size(url)
    if size is None:  # one stream
        with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=300) as r, part.open("wb") as fh:
            shutil.copyfileobj(r, fh, 4 << 20)
        part.replace(dest)
        return
    state = dest.with_name(dest.name + ".part.json")
    done: set[int] = set()
    if part.exists() and state.exists():
        saved = json.loads(state.read_text())
        if saved.get("size") == size:
            done = set(saved["done"])
    if not done:
        with part.open("wb") as fh:
            fh.truncate(size)
    n, lock = -(-size // CHUNK), threading.Lock()

    def one(i: int) -> None:
        start = i * CHUNK
        data = _range(url, start, min(start + CHUNK, size) - 1)
        with lock:
            with part.open("r+b") as fh:
                fh.seek(start)
                fh.write(data)
            done.add(i)
            state.write_text(json.dumps({"size": size, "done": sorted(done)}), newline="\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(one, i) for i in range(n) if i not in done]:
            future.result()
    part.replace(dest)
    state.unlink(missing_ok=True)


def fetch(entry: dict, workers: int = 16, root: Path = ROOT) -> Path:
    """Downloads one entry's source unless it is there already; returns its path."""
    dest = source_path(entry, root)
    denylist.check(dest)
    if dest.exists() or "url" not in entry:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  {entry['id']}: {entry['url']}", flush=True)
    _download(entry["url"], dest, workers)
    if entry.get("bytes") is not None and dest.stat().st_size != entry["bytes"]:
        raise OSError(f"{dest}: {dest.stat().st_size} bytes, the bank says {entry['bytes']}")
    return dest


def record_file(record: dict, entry: dict, path: Path) -> None:
    """Adds a source file to the record, or checks it against the record."""
    key = path.relative_to(REPO).as_posix()
    digest = sha256(path)
    if key in record and record[key]["sha256"] != digest:
        raise SystemExit(f"{key} changed since it was recorded ({record[key]['sha256']} -> {digest})")
    record.setdefault(key, {"bytes": path.stat().st_size, "sha256": digest, "url": entry.get("url"),
                            "recorded": str(date.today())})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma-separated entry ids")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    bank = load_bank()
    wanted = set(args.only.split(",")) if args.only else None
    record = json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.exists() else {}
    for entry in bank["entries"]:
        if wanted and entry["id"] not in wanted:
            continue
        path = fetch(entry, args.workers)
        if not path.exists():
            raise SystemExit(f"{entry['id']}: {path} is missing")
        record_file(record, entry, path)
        RECORD.write_bytes((json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(f"{len(record)} source files recorded in {RECORD.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
