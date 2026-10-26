"""Assembles the public site for Cloudflare Pages in dist/ (gitignored).

web/ has no build step and keeps none: this only copies it. Cloudflare Pages
refuses any file over 25 MiB, so those files (the RNA atlas parts and the
protein atlas CSV) are left out of the static copy and listed in
dist/large_files.json. With --r2 BUCKET they are served from that R2 bucket
at their usual URLs (/data/...) by a small Pages Function, so the pages
need no change; without it they are simply absent and the atlas view shows
its error panel.

The Atlas page's gene profiles (PROFILES: one row of gene values per RNA
reference cell) reach the site as shards instead: every PROFILE_CELLS cells
as float32 values, gzipped, in data/profiles/, with data/profiles/index.json
naming the genes. A click then fetches one shard of about 120 KB, where the
CSV parts would need up to 2.9 GB read (web/js/atlas/gene-profile.js).
Without the source (a clone without `git lfs pull`), no shards are written
and a click says the profiles are not on this copy.

Media files the site plays (MEDIA: the Motion page's film) are stored as
parts and served by deploy/pages/media.js, a Pages Function at the file's
own URL that answers byte-range requests. Pages answers a Range request for
a static file with the whole file, and Safari and every iPhone browser will
not play a video without ranged answers.

Every build also carries the site's door to the labelling service:
deploy/pages/api-proxy.js as the Pages Function for /api/*, which forwards
to the service at SERVICE_URL (wrangler.toml, from web/js/atlas/
service-client.js) with the secret SERVICE_SECRET (a Pages secret, set
once with wrangler; docs/web/hosting.md).

    python scripts/build_pages_site.py                  # static site, with the profile shards
    python scripts/build_pages_site.py --no-profiles    # without them (faster)
    python scripts/build_pages_site.py --r2 BUCKET      # plus the R2-backed large files
    cd dist && npx wrangler@4 pages deploy             # publish (see docs/web/hosting.md)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "web"
DIST = REPO / "dist"
PROJECT = "vivome-atlas"
MAX_BYTES = 25 * 1024 * 1024  # Cloudflare Pages' per-file limit
MAX_FILES = 20_000  # Cloudflare Pages' file limit on the free plan
SKIP_DIRS, SKIP_FILES = ("tests",), ("README.md",)  # repository material, not the site
UNUSED = ("data/atlas_RNA_lat128.parquet",)  # no page loads it; the profile shards are built from it
# The gene profiles' sources, by modality, in web/ (the same float32 values the
# CSV parts print), and the cells per shard.
PROFILES = {"rna": "data/atlas_RNA_lat128.parquet"}
PROFILE_CELLS = 32
PROFILE_DIGITS = 5  # a shard's number in its file name, zero-padded
PROXY = REPO / "deploy" / "pages" / "api-proxy.js"  # the /api/* Pages Function
SERVICE_CLIENT = WEB / "js" / "atlas" / "service-client.js"  # where the service lives
MEDIA_FUNCTION = REPO / "deploy" / "pages" / "media.js"  # byte ranges for MEDIA
# Played with byte ranges (deploy/pages/media.js), by path in web/: each is
# stored as parts of PART bytes beside it, in parts/, and left out of the
# static copy.
MEDIA = {rel.removeprefix("web/"): kind for rel, kind in {"web/motion/film/vivome.mp4": "video/mp4"}.items()}
PART = 1024 * 1024
# Sent with every static file (Pages' _headers file): no other site may show
# these pages in a frame, the browser never second-guesses a file's type, and
# browser features the site never uses are off. Functions (the /api door, the
# film) answer with their own headers.
HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Content-Security-Policy", "frame-ancestors 'none'"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
)
# Pages that were renamed, so old links keep working (Pages' _redirects file).
REDIRECTS = (
    ("/benchmark", "/manuscript"),  # the Benchmark page became the Manuscript page (2026-10-17)
    ("/benchmark.html", "/manuscript"),
    ("/home", "/"),  # the Dashboard was removed (2026-10-17); its links go to the landing page
    ("/home.html", "/"),
    ("/project", "/atlas"),  # the Project page became the Atlas page's Your data tab (2026-10-17)
    ("/project.html", "/atlas"),
    ("/versions", "/manuscript"),  # the Versions page was removed for the beta (2026-10-17)
    ("/versions.html", "/manuscript"),
)

NOT_FOUND = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Not found · VivOME Atlas</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family: system-ui, sans-serif; padding: 3rem;">
<h1>Not found</h1><p>This page or file does not exist. <a href="/">Back to the VivOME Atlas</a></p>
</body></html>
"""

FUNCTION = """// Serves the atlas files too large for Pages from R2, at their usual /data/ URLs.
export async function onRequestGet({ params, env }) {
  const key = `data/${[].concat(params.path).join("/")}`;
  const object = await env.DATA.get(key);
  if (object === null) return new Response("Not found", { status: 404 });
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("cache-control", "public, max-age=86400");
  return new Response(object.body, { headers });
}
"""


def plan(web: Path = WEB) -> tuple[list[str], list[str]]:
    """(static files, large files), as paths relative to web/."""
    static, large = [], []
    for path in sorted(p for p in web.rglob("*") if p.is_file()):
        rel = path.relative_to(web).as_posix()
        if rel.split("/")[0] in SKIP_DIRS or rel in SKIP_FILES or rel in UNUSED or rel in MEDIA:
            continue
        (large if path.stat().st_size > MAX_BYTES else static).append(rel)
    return static, large


def service_url() -> str:
    """The hosted service's address, from the one line the site keeps it on."""
    return re.search(r"DEFAULT_SERVICE_URL = '([^']+)'", SERVICE_CLIENT.read_text(encoding="utf-8")).group(1)


def write_media(site: Path, functions: Path, web: Path = WEB) -> list[str]:
    """Each MEDIA file as parts, and the Function that serves it; returns its routes."""
    table = {}
    for rel, kind in MEDIA.items():
        source = web / rel
        if not source.exists():
            continue
        data = source.read_bytes()
        folder, name = rel.rsplit("/", 1)
        (site / folder / "parts").mkdir(parents=True, exist_ok=True)
        for i in range(0, len(data), PART):
            (site / folder / "parts" / f"{name}.{i // PART:04d}").write_bytes(data[i:i + PART])
        table[f"/{rel}"] = {"size": len(data), "part": PART, "parts": f"/{folder}/parts/{name}.",
                            "type": kind, "sha256": hashlib.sha256(data).hexdigest()}
    if not table:
        return []
    source = MEDIA_FUNCTION.read_text(encoding="utf-8")
    assert source.count("export const MEDIA = {};") == 1
    code = source.replace("export const MEDIA = {};", f"export const MEDIA = {json.dumps(table)};")
    # One Function per folder holding media, matching any file name there; the
    # routes below send it only the media files themselves.
    for folder in sorted({route.rsplit("/", 1)[0] for route in table}):
        target = functions / folder.strip("/") / "[name].js"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(code.encode("utf-8"))
    return sorted(table)


def is_lfs_pointer(path: Path) -> bool:
    """True for a Git LFS object that has not been fetched (git lfs pull)."""
    with open(path, "rb") as handle:
        return handle.read(64).startswith(b"version https://git-lfs")


def write_profiles(site: Path, web: Path = WEB, cells: int = PROFILE_CELLS) -> dict:
    """The gene profiles as gzipped float32 shards in site/data/profiles/, with
    their index.json; returns the index, or {} when no source is on this copy."""
    index = {}
    for modality, rel in PROFILES.items():
        source = web / rel
        if not source.exists() or is_lfs_pointer(source):
            continue
        import numpy as np  # only here: the rest of the build needs neither
        import pyarrow.parquet as pq
        table = pq.read_table(source)
        genes = [name for name in table.column_names if name.startswith("gene_")]
        # A cell's shard and row follow from its orig_index alone.
        order = table.column("orig_index").to_numpy()
        if not (order == np.arange(len(order))).all():
            raise ValueError(f"{rel}: orig_index is not 0 to n-1 in order")
        values = np.column_stack([table.column(g).to_numpy() for g in genes])
        # float32, as the CSV parts print it: the page reads each value back
        # through its shortest float32 text, so both copies show the same digits.
        if values.dtype != np.float32:
            raise ValueError(f"{rel}: gene values are {values.dtype}, not float32")
        values = values.astype("<f4", copy=False)
        folder = site / "data" / "profiles" / modality
        folder.mkdir(parents=True, exist_ok=True)
        for start in range(0, len(values), cells):
            # mtime=0: the same values give the same bytes, so a redeploy
            # uploads no shard again.
            (folder / f"{start // cells:0{PROFILE_DIGITS}d}.f32.gz").write_bytes(
                gzip.compress(values[start:start + cells].tobytes(), compresslevel=6, mtime=0))
        index[modality] = {
            "cells": len(values), "shards": -(-len(values) // cells), "file": f"{modality}/{{shard}}.f32.gz",
            "genes": [g.removeprefix("gene_") for g in genes],
            "source": rel, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    if not index:
        return {}
    index = {"cells_per_shard": cells, "digits": PROFILE_DIGITS,
             "values": "float32, little-endian; one row of genes per cell, in orig_index order; each file gzipped",
             **index}
    (site / "data" / "profiles" / "index.json").write_bytes((json.dumps(index) + "\n").encode())
    return index


def build(bucket: str | None, dist: Path = DIST, profiles: bool = True) -> None:
    if dist.exists():
        shutil.rmtree(dist)
    static, large = plan()
    site = dist / "site"
    for rel in static:
        (site / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WEB / rel, site / rel)
    # Without a 404.html, Pages answers any missing path with index.html (a
    # single-page-app fallback), so a missing data file would arrive as HTML.
    (site / "404.html").write_text(NOT_FOUND)
    (site / "_redirects").write_bytes("".join(f"{old} {new} 301\n" for old, new in REDIRECTS).encode())
    (site / "_headers").write_bytes(("/*\n" + "".join(f"  {name}: {value}\n" for name, value in HEADERS)).encode())
    shards = write_profiles(site) if profiles else {}
    (dist / "large_files.json").write_text(json.dumps(
        [{"path": rel, "bytes": (WEB / rel).stat().st_size} for rel in large], indent=2) + "\n")
    # The labelling service, reached through the site (deploy/pages/api-proxy.js).
    (dist / "functions" / "api").mkdir(parents=True)
    (dist / "functions" / "api" / "[[path]].js").write_bytes(PROXY.read_bytes())
    routes = ["/api/*"] + write_media(site, dist / "functions")
    toml = [f'name = "{PROJECT}"', 'pages_build_output_dir = "./site"', 'compatibility_date = "2026-10-01"',
            "", "[vars]", f'SERVICE_URL = "{service_url()}"']
    if bucket:
        (dist / "functions" / "data").mkdir(parents=True)
        (dist / "functions" / "data" / "[[path]].js").write_text(FUNCTION)
        routes += [f"/{rel}" for rel in large]
        toml += ["", "[[r2_buckets]]", 'binding = "DATA"', f'bucket_name = "{bucket}"']
    # Only these paths wake a Function; every other file is served as it is.
    (site / "_routes.json").write_text(json.dumps({"version": 1, "include": routes, "exclude": []}, indent=2) + "\n")
    (dist / "wrangler.toml").write_text("\n".join(toml) + "\n")
    files = sum(1 for p in site.rglob("*") if p.is_file())
    if files >= MAX_FILES:
        raise SystemExit(f"dist/site holds {files} files; Cloudflare Pages takes fewer than {MAX_FILES}")
    print(f"dist/site: {files} files; left out for R2: {', '.join(large) or 'none'}"
          + (f"; served from R2 bucket {bucket}" if bucket else "")
          + "".join(f"; {m} gene profiles as {shards[m]['shards']} shards" for m in PROFILES if m in shards)
          + "".join(f"; {r} served with byte ranges" for r in routes if r != "/api/*" and not r.startswith("/data/"))
          + "; /api/* forwarded to the service")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--r2", metavar="BUCKET", help="serve the large files from this R2 bucket")
    parser.add_argument("--no-profiles", action="store_true", help="leave out the gene profile shards")
    args = parser.parse_args()
    build(args.r2, profiles=not args.no_profiles)
