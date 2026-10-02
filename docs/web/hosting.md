# Hosting: Cloudflare Pages

The public site is served by Cloudflare Pages at **https://vivome-atlas.pages.dev**
(project `vivome-atlas`, account of aiamrita.stanford@gmail.com). Deployments
are uploaded from the Windows PC with Wrangler. Nothing is built: `web/`
keeps no build step, and the deploy only copies it.

## What is deployed

`scripts/build_pages_site.py` assembles `dist/` (gitignored):

- `dist/site/`: every file of `web/` except `web/tests/`, `web/README.md`,
  and the RNA parquet no page loads.
- `dist/site/404.html`: without it, Pages answers a missing path with
  `index.html`, so a missing data file would arrive as HTML.
- `dist/large_files.json`: the files over Pages' 25 MiB per-file limit, left
  out of the static copy. These are the two RNA atlas parts (1.4 GB each)
  and `atlas_PROT_lat128.csv` (45 MB).

Until those three files are served from R2 (below), the atlas page's 3D view
has no data. Every other page works.

Pages serves `/home.html` at `/home`. The `.html` addresses redirect with a
308, so the site's own links keep working.

## Publishing

From the repository root, in Git Bash:

```bash
python scripts/build_pages_site.py
cd dist && npx wrangler@4 pages deploy site --project-name vivome-atlas --branch main
```

`--branch main` publishes to the production address. Another branch name
gives a preview address. The first sign-in is `npx wrangler@4 login`.

The project was created with `pages project create ... --force`. Without
`--force`, current Wrangler delegates to Workers, finds `web/` on its own,
and refuses its 45 MB file. Later commands need no `--force`.

## The large files (R2), not yet active

R2 must first be enabled once in the Cloudflare dashboard (R2 Object
Storage). Then:

1. Create the bucket: `npx wrangler@4 r2 bucket create vivome-atlas-data`.
2. Upload the three files under the key `data/<file name>`. The 1.4 GB parts
   are beyond Wrangler's single upload size, so they go through R2's S3 API,
   for example with rclone and an R2 API token.
3. Build with `python scripts/build_pages_site.py --r2 vivome-atlas-data` and
   deploy.

That build adds two things:
- a Pages Function (`functions/data/[[path]].js`) that serves the three
  files from the bucket at their usual `/data/...` URLs, so no page changes;
- `_routes.json`, so the Function runs for those three paths only.

R2's free tier covers 10 GB of storage, and downloads are free. The RNA view
still downloads 2.7 GB per visitor, so a lighter web copy is a separate,
open decision.
