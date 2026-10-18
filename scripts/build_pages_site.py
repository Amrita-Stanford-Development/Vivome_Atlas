"""Assembles the public site for Cloudflare Pages in dist/ (gitignored).

web/ has no build step and keeps none: this only copies it. Cloudflare Pages
refuses any file over 25 MiB, so those files (the RNA atlas parts and the
protein atlas CSV) are left out of the static copy and listed in
dist/large_files.json. With --r2 BUCKET they are served from that R2 bucket
at their usual URLs (/data/...) by a small Pages Function, so the pages
need no change; without it they are simply absent and the atlas view shows
its error panel.

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

    python scripts/build_pages_site.py                  # static site only
    python scripts/build_pages_site.py --r2 BUCKET      # plus the R2-backed large files
    cd dist && npx wrangler@4 pages deploy             # publish (see docs/web/hosting.md)
"""
from __future__ import annotations

import argparse
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
SKIP_DIRS, SKIP_FILES = ("tests",), ("README.md",)  # repository material, not the site
UNUSED = ("data/atlas_RNA_lat128.parquet",)  # no page loads it
PROXY = REPO / "deploy" / "pages" / "api-proxy.js"  # the /api/* Pages Function
SERVICE_CLIENT = WEB / "js" / "atlas" / "service-client.js"  # where the service lives
MEDIA_FUNCTION = REPO / "deploy" / "pages" / "media.js"  # byte ranges for MEDIA
# Played with byte ranges (deploy/pages/media.js), by path in web/: each is
# stored as parts of PART bytes beside it, in parts/, and left out of the
# static copy.
MEDIA = {rel.removeprefix("web/"): kind for rel, kind in {"web/motion/film/vivome.mp4": "video/mp4"}.items()}
PART = 1024 * 1024
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


def build(bucket: str | None, dist: Path = DIST) -> None:
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
    print(f"dist/site: {len(static)} files; left out for R2: {', '.join(large) or 'none'}"
          + (f"; served from R2 bucket {bucket}" if bucket else "")
          + "".join(f"; {r} served with byte ranges" for r in routes if r != "/api/*" and not r.startswith("/data/"))
          + "; /api/* forwarded to the service")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--r2", metavar="BUCKET", help="serve the large files from this R2 bucket")
    build(parser.parse_args().r2)
