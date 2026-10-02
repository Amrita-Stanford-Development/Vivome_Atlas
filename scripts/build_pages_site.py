"""Assembles the public site for Cloudflare Pages in dist/ (gitignored).

web/ has no build step and keeps none: this only copies it. Cloudflare Pages
refuses any file over 25 MiB, so those files (the RNA atlas parts and the
protein atlas CSV) are left out of the static copy and listed in
dist/large_files.json. With --r2 BUCKET they are served from that R2 bucket
at their usual URLs (/data/...) by a small Pages Function, so the pages
need no change; without it they are simply absent and the atlas view shows
its error panel.

    python scripts/build_pages_site.py                  # static site only
    python scripts/build_pages_site.py --r2 BUCKET      # plus the R2-backed large files
    cd dist && npx wrangler@4 pages deploy             # publish (see docs/web/hosting.md)
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "web"
DIST = REPO / "dist"
PROJECT = "vivome-atlas"
MAX_BYTES = 25 * 1024 * 1024  # Cloudflare Pages' per-file limit
SKIP_DIRS, SKIP_FILES = ("tests",), ("README.md",)  # repository material, not the site
UNUSED = ("data/atlas_RNA_lat128.parquet",)  # no page loads it

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
        if rel.split("/")[0] in SKIP_DIRS or rel in SKIP_FILES or rel in UNUSED:
            continue
        (large if path.stat().st_size > MAX_BYTES else static).append(rel)
    return static, large


def build(bucket: str | None) -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    static, large = plan()
    site = DIST / "site"
    for rel in static:
        (site / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WEB / rel, site / rel)
    # Without a 404.html, Pages answers any missing path with index.html (a
    # single-page-app fallback), so a missing data file would arrive as HTML.
    (site / "404.html").write_text(NOT_FOUND)
    (DIST / "large_files.json").write_text(json.dumps(
        [{"path": rel, "bytes": (WEB / rel).stat().st_size} for rel in large], indent=2) + "\n")
    toml = [f'name = "{PROJECT}"', 'pages_build_output_dir = "./site"', 'compatibility_date = "2026-10-01"']
    if bucket:
        (DIST / "functions" / "data").mkdir(parents=True)
        (DIST / "functions" / "data" / "[[path]].js").write_text(FUNCTION)
        (site / "_routes.json").write_text(json.dumps({"version": 1, "include": [f"/{rel}" for rel in large],
                                                       "exclude": []}, indent=2) + "\n")
        toml += ["", "[[r2_buckets]]", 'binding = "DATA"', f'bucket_name = "{bucket}"']
    (DIST / "wrangler.toml").write_text("\n".join(toml) + "\n")
    print(f"dist/site: {len(static)} files; left out for R2: {', '.join(large) or 'none'}"
          + (f"; served from R2 bucket {bucket}" if bucket else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--r2", metavar="BUCKET", help="serve the large files from this R2 bucket")
    build(parser.parse_args().r2)
