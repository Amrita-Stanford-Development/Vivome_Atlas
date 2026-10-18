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
- `dist/functions/api/[[path]].js`: the site's door to the labelling service
  (below), copied from `deploy/pages/api-proxy.js`, and `dist/site/_routes.json`,
  so a Function runs for `/api/*` only and every other file is served as it is.
- `dist/wrangler.toml`: the project's settings, with `SERVICE_URL`, the
  hosted service's address, read from `web/js/atlas/service-client.js`.

The 3D view does not need them: its positions come from the small
`metadata_*_lat128.csv` files, which are deployed. The three large files hold
each cell's gene profile, so until they are served from R2 (below), clicking
a cell cannot show its profile. Every other page works.

Pages serves `/atlas.html` at `/atlas`. The `.html` addresses redirect with
a 308, so the site's own links keep working. Pages that were removed or
renamed redirect through `_redirects`, which `scripts/build_pages_site.py`
writes from its `REDIRECTS`: `/benchmark` and `/versions` to `/manuscript`,
the removed Dashboard, `/home`, to the landing page, and `/project` to
`/atlas`, whose Your data tab sends a file to the service.

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

## Media with byte ranges

Pages answers a Range request for a static file with the whole file (200).
Safari and every iPhone browser will not play a video without ranged (206)
answers, so the media files the site plays (`MEDIA` in
`scripts/build_pages_site.py`: the Motion page's film) are not uploaded as
they are:

- the build stores each as 1 MiB parts beside it, in `parts/`
  (`parts/vivome.mp4.0000` and on, beside the film);
- `deploy/pages/media.js` becomes the Pages Function for the file's own URL
  (`functions/motion/film/[name].js`), and `_routes.json` sends it that URL
  only. It answers a range from the parts (at most 4 MiB per answer, which
  an open-ended `bytes=N-` allows), streams the parts in order for a
  whole-file request, and answers HEAD and ranges past the end (416).

The page links the file at its usual address, so nothing changes for it.

## The labelling service, through the site

The service on Cloud Run answers only through the website. Pages call their
own site's `/api/status` and `/api/project`; the Function forwards each
request to `SERVICE_URL` with the secret `SERVICE_SECRET` in the
`X-VivOME-Proxy-Secret` header, and the service, with the same secret in
`VIVOME_PROXY_SECRET`, answers 403 to anything without it. Behind the site's
sign-in, only signed-in visitors reach it. Cloudflare takes at most 100 MB in
one request, so that is the upload limit.

The secret is set once, never in a file. Make a long random value, then:

```bash
npx wrangler@4 pages secret put SERVICE_SECRET --project-name vivome-atlas   # paste it when asked
gcloud run services update vivome-atlas --region us-central1 --update-env-vars VIVOME_PROXY_SECRET=THE_SAME_VALUE
```

Set the site's secret and deploy the site first, then the service's: the
other way round, the live site is refused until its new Function is out. A
Cloud Run deploy keeps the variable. To change the secret, set both again in
the same order. `deploy/huggingface/check_space.py` reads it from the
`VIVOME_PROXY_SECRET` in its own environment and first checks that a request
without it is refused.

## The large files (R2), not yet active

R2 must first be enabled once in the Cloudflare dashboard (R2 Object
Storage). Then:

1. Create the bucket: `npx wrangler@4 r2 bucket create vivome-atlas-data`.
2. Upload the three files under the key `data/<file name>`. The 1.4 GB parts
   are beyond Wrangler's single upload size, so they go through R2's S3 API,
   for example with rclone and an R2 API token.
3. Build with `python scripts/build_pages_site.py --r2 vivome-atlas-data` and
   deploy.

That build adds a Pages Function (`functions/data/[[path]].js`) that serves
the three files from the bucket at their usual `/data/...` URLs, so no page
changes, and adds their three paths to `_routes.json`.

R2's free tier covers 10 GB of storage, and downloads are free. The RNA view
still downloads 2.7 GB per visitor, so a lighter web copy is a separate,
open decision.
