"""Listing and reading a deposit's files remotely, for B3's draw
(research/benchmark/protocol-value-scale.md, "Tables").

- PRIDE: the Archive API's file list (`/pride/ws/archive/v2/projects/<PXD>/files`),
  each file read over FTP from ftp.pride.ebi.ac.uk. B3's smoke test found
  its HTTPS took 15 to 30 s to a first byte where FTP took 2 to 10, and
  that PRIDE refuses 16 connections at once: at most 8 are open.
- MassIVE: the dataset's FTP folder, listed with ftplib over explicit TLS
  (what `curl --ssl-reqd` does) down to three folder levels below the root;
  at most 4 connections.
- Every FTP read opens a connection in one of its host's slots and closes
  it after; a large file comes in 8 MiB ranges on several connections,
  resumable.
- A zip archive is listed, and a member's first bytes read, through range
  requests: zipfile reads a RangeFile, which fetches the blocks it touches.

Every URL passes denylist.check before it is opened.
"""
from __future__ import annotations

import csv
import ftplib
import hashlib
import io
import json
import re
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from valuescale.corpus import denylist
from valuescale.corpus import fetch as bank_fetch

PRIDE_FILES = "https://www.ebi.ac.uk/pride/ws/archive/v2/projects/{}/files?pageSize={}&page={}"
MASSIVE_HOST = "massive-ftp.ucsd.edu"
MASSIVE_DEPTH = 3
BLOCK = 256 << 10
AGENT = {"User-Agent": "valuescale-draw/1"}


@dataclass(frozen=True)
class File:
    path: str  # relative to the deposit's root
    size: int
    url: str

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Member:
    name: str
    size: int  # uncompressed


def _retry(fn, tries: int = 5):
    last = None
    for attempt in range(tries):
        try:
            return fn()
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                raise
            last = exc
        except ftplib.error_perm:
            raise  # 5xx: no such file or folder
        except (OSError, EOFError, ftplib.Error) as exc:
            last = exc
        time.sleep(min(2 ** attempt, 30))
    raise OSError(f"after {tries} tries: {last}")


def get_json(url: str):
    denylist.check(url)

    def one():
        req = urllib.request.Request(url, headers={**AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    return _retry(one)


def pride_files(accession: str, get_json=get_json, page_size: int = 500) -> list[File]:
    files, page = [], 0
    marker = f"/{accession}/"
    while True:
        items = get_json(PRIDE_FILES.format(accession, page_size, page))
        for item in items:
            ftp = next((loc.get("value") for loc in item.get("publicFileLocations", [])
                        if loc.get("name") == "FTP Protocol"), None)
            if not ftp:
                continue
            url = ftp
            path = url.split(marker, 1)[1] if marker in url else item.get("fileName", url.rsplit("/", 1)[-1])
            files.append(File(path, int(item.get("fileSizeBytes") or 0), url))
        if len(items) < page_size:
            return files
        page += 1


FTP_SITES = {"ftp.pride.ebi.ac.uk": (False, 8), MASSIVE_HOST: (True, 4)}  # host: (TLS, connections at once)
CHUNK = 8 << 20
_slots = {host: threading.BoundedSemaphore(n) for host, (_, n) in FTP_SITES.items()}


def ftp_site(url: str) -> tuple[str, bool]:
    host = urlparse(url).hostname
    if host not in FTP_SITES:
        raise ValueError(f"no FTP site known for {url}")
    return host, FTP_SITES[host][0]


@contextmanager
def ftp_connection(url: str):
    """A logged-in connection, one of the host's capped slots, closed after use."""
    host, tls = ftp_site(url)
    with _slots[host]:
        conn = (ftplib.FTP_TLS if tls else ftplib.FTP)(host, timeout=120)
        try:
            conn.login()
            if tls:
                conn.prot_p()
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass


def massive_files(ftp_url: str, ftp=None, depth: int = MASSIVE_DEPTH) -> list[File]:
    denylist.check(ftp_url)
    u = urlparse(ftp_url)
    root = u.path.rstrip("/")

    def listing(conn) -> list[File]:
        files: list[File] = []

        def walk(path: str, rel: str, level: int) -> None:
            for name, facts in sorted(conn.mlsd(path)):
                if name in (".", ".."):
                    continue
                here = f"{rel}{name}"
                if facts.get("type") == "dir":
                    if level < depth:
                        walk(f"{path}/{name}", here + "/", level + 1)
                elif facts.get("type") == "file":
                    files.append(File(here, int(facts.get("size") or 0), f"ftp://{u.netloc}{root}/{here}"))
        walk(root, "", 0)
        return files

    if ftp is not None:
        return listing(ftp)

    def one():
        with ftp_connection(ftp_url) as conn:
            return listing(conn)
    return _retry(one)


def massive_folders(ftp=None) -> dict[str, str]:
    """Every MassIVE dataset's folder on massive-ftp.ucsd.edu (MSV -> /vNN/MSV),
    from one listing of each top folder; the v folders are read first."""

    def listing(conn) -> dict[str, str]:
        tops = [n for n, f in conn.mlsd("/") if f.get("type") == "dir"]
        out: dict[str, str] = {}
        for top in sorted(tops, key=lambda n: (not n.startswith("v"), n)):
            for name, facts in conn.mlsd(f"/{top}"):
                if facts.get("type") == "dir" and re.fullmatch(r"MSV\d{9}", name):
                    out.setdefault(name, f"/{top}/{name}")
        return out

    if ftp is not None:
        return listing(ftp)

    def one():
        with ftp_connection(f"ftp://{MASSIVE_HOST}/") as conn:
            return listing(conn)
    return _retry(one)


def massive_root(ftp_url: str, msv: str, folders: dict[str, str]) -> str:
    """The dataset's folder on the current host. Older announcements name
    ftp://massive.ucsd.edu/MSV.../, which no longer answers."""
    if urlparse(ftp_url).hostname == MASSIVE_HOST:
        return ftp_url
    if msv in folders:
        return f"ftp://{MASSIVE_HOST}{folders[msv]}/"
    raise OSError(f"{msv} is not on {MASSIVE_HOST}")


def ftp_read(url: str, start: int, length: int) -> bytes:
    path = urlparse(url).path

    def one():
        with ftp_connection(url) as conn:
            conn.voidcmd("TYPE I")
            sock = conn.transfercmd(f"RETR {path}", rest=start or None)
            got = bytearray()
            while len(got) < length:
                b = sock.recv(min(1 << 16, length - len(got)))
                if not b:
                    break
                got += b
            sock.close()
            return bytes(got)
    return _retry(one)


def chunks(size: int, chunk: int = CHUNK) -> list[tuple[int, int]]:
    return [(s, min(s + chunk, size) - 1) for s in range(0, size, chunk)]


def ftp_download(url: str, dest: Path, size: int, streams: int = 4) -> None:
    """In CHUNK ranges on up to `streams` connections, resumable from the
    .part file and its record of finished ranges."""
    part = dest.with_name(dest.name + ".part")
    state = dest.with_name(dest.name + ".part.json")
    pieces = chunks(size)
    done: set[int] = set()
    if part.exists() and state.exists():
        saved = json.loads(state.read_text())
        if saved.get("size") == size:
            done = set(saved["done"])
    if not done:
        with part.open("wb") as fh:
            fh.truncate(size)
    lock = threading.Lock()

    def one(i: int) -> None:
        start, end = pieces[i]
        data = ftp_read(url, start, end - start + 1)
        if len(data) != end - start + 1:
            raise OSError(f"{url} bytes {start}-{end}: got {len(data)}")
        with lock:
            with part.open("r+b") as fh:
                fh.seek(start)
                fh.write(data)
            done.add(i)
            state.write_text(json.dumps({"size": size, "done": sorted(done)}), newline="\n")

    with ThreadPoolExecutor(max_workers=streams) as pool:
        for future in [pool.submit(one, i) for i in range(len(pieces)) if i not in done]:
            future.result()
    part.replace(dest)
    state.unlink(missing_ok=True)


def fetch_range(url: str, start: int, end: int) -> bytes:
    """Bytes start to end, inclusive."""
    denylist.check(url)
    if url.startswith("ftp://"):
        return ftp_read(url, start, end - start + 1)
    return bank_fetch._range(url, start, end)


class RangeFile(io.RawIOBase):
    """A remote file read in cached blocks, for zipfile and pyarrow."""

    def __init__(self, url: str, size: int, fetch=fetch_range, block: int = BLOCK):
        self.url, self.size, self.fetch, self.block = url, size, fetch, block
        self.pos, self.cache = 0, {}

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        self.pos = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence] + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def _block(self, i: int) -> bytes:
        if i not in self.cache:
            start = i * self.block
            self.cache[i] = self.fetch(self.url, start, min(start + self.block, self.size) - 1)
        return self.cache[i]

    def readinto(self, b) -> int:
        n = max(0, min(len(b), self.size - self.pos))
        out = bytearray()
        while len(out) < n:
            i, off = divmod(self.pos + len(out), self.block)
            chunk = self._block(i)[off:off + n - len(out)]
            if not chunk:
                break
            out += chunk
        b[:len(out)] = out
        self.pos += len(out)
        return len(out)


def head(url: str, size: int, nbytes: int, fetch=fetch_range) -> bytes:
    return fetch(url, 0, min(nbytes, size) - 1) if size > 0 else b""


def zip_members(url: str, size: int, fetch=fetch_range, block: int = BLOCK) -> list[Member]:
    with zipfile.ZipFile(RangeFile(url, size, fetch, block)) as zf:
        return [Member(i.filename, i.file_size) for i in zf.infolist() if not i.is_dir()]


def member_head(url: str, size: int, member: str, nbytes: int, fetch=fetch_range, block: int = BLOCK) -> bytes:
    with zipfile.ZipFile(RangeFile(url, size, fetch, block)) as zf, zf.open(member) as fh:
        return fh.read(nbytes)


def parquet_columns(url: str, size: int, fetch=fetch_range) -> list[str]:
    import pyarrow.parquet as pq
    return list(pq.ParquetFile(RangeFile(url, size, fetch)).schema_arrow.names)


def first_line_fields(data: bytes) -> list[str] | None:
    """The header's fields, or None when the bytes end before the first line does."""
    text = data.decode("utf-8-sig", errors="replace")
    if "\n" not in text:
        return None
    line = text.split("\n", 1)[0].rstrip("\r")
    delimiter = "\t" if line.count("\t") > line.count(",") else ","
    return next(csv.reader([line], delimiter=delimiter))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(file: File, dest: Path, workers: int = 4) -> None:
    """The whole file to dest (resumable), checked against the listed size."""
    denylist.check(file.url, dest)
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if file.url.startswith("ftp://"):
        if not file.size:
            raise OSError(f"{file.url}: the listing gives no size")
        ftp_download(file.url, dest, file.size, workers)
    else:
        bank_fetch._download(file.url, dest, workers)
    if file.size and dest.stat().st_size != file.size:
        got = dest.stat().st_size
        dest.unlink()
        raise OSError(f"{file.url}: {got} bytes, the listing says {file.size}")
