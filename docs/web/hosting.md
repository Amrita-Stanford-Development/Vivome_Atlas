# Hosting: Cloudflare Pages

The public site is served by Cloudflare Pages at **https://vivome-atlas.pages.dev**
(project `vivome-atlas`, account of aiamrita.stanford@gmail.com). Deployments
are uploaded from the Windows PC with Wrangler. Nothing is built: `web/`
keeps no build step, and the deploy only copies it.

## What is deployed

`scripts/build_pages_site.py` assembles `dist/` (gitignored):

- `dist/site/`: every file of `web/` except `web/tests/`, `web/README.md`,
  and the RNA parquet no page loads.
- `dist/site/data/profiles/`: each RNA reference cell's gene profile, from
  that parquet, as 2,664 shards of 32 cells: float32 values, gzipped, about
  350 MB in all, with `index.json` naming the genes. A click on a cell
  fetches one shard (at most 211 KB). The values are the ones the CSV parts
  print, and the page shows the same four decimals from either. The
  parquet also holds the one cell the CSV parts lack (`orig_index` 42616).
  The shards are byte-identical between builds, so a redeploy uploads none
  of them again. `--no-profiles` leaves them out.
- `dist/site/404.html`: without it, Pages answers a missing path with
  `index.html`, so a missing data file would arrive as HTML.
- `dist/site/_headers`: security headers on every static file, from the
  builder's `HEADERS`. No other site may show the pages in a frame, the
  browser never second-guesses a file's type, and the camera, microphone,
  location, payment and USB features are off. Functions set their own headers.
- `dist/large_files.json`: the files over Pages' 25 MiB per-file limit, left
  out of the static copy. These are the two RNA atlas parts (1.4 GB each)
  and `atlas_PROT_lat128.csv` (45 MB).
- `dist/functions/api/[[path]].js`: the site's door to the labelling service
  (below), copied from `deploy/pages/api-proxy.js`, and `dist/site/_routes.json`,
  so a Function runs for `/api/*` only and every other file is served as it is.
- `dist/functions/_middleware.js`: the beta's sign-in (below), from
  `deploy/pages/beta-gate.js`, with the invited emails written in. With it,
  `_routes.json` sends every path through Functions.
- `dist/wrangler.toml`: the project's settings, with `SERVICE_URL`, the
  hosted service's address, read from `web/js/atlas/service-client.js`.

No page needs the large files: the 3D view's positions come from the small
`metadata_*_lat128.csv` files, and the gene profiles from the shards.

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

## The beta sign-in

The site is a closed beta. Every path, the pages, the data files and the
`/api` door included, first asks for an invited email and the beta's one
password (`deploy/pages/beta-gate.js`, the site's Pages middleware). No
email is verified: the owner's choice for a beta shared only with the
people invited (2026-10-26). The sign-in page and every refusal tell search
engines not to index them.

- **Who is invited:** `~/.vivome-beta/emails.txt` on the PC that builds the
  site (`C:\Users\amarn\.vivome-beta\emails.txt`), outside the repository,
  one email a line. `scripts/build_pages_site.py` writes the list into the
  middleware, and refuses to build without it (`--open` builds a site
  without sign-in). A change reaches the site with the next deploy:

  ```bash
  python scripts/beta_access.py add someone@example.org    # or remove, or list
  python scripts/build_pages_site.py
  cd dist && npx wrangler@4 pages deploy site --project-name vivome-atlas --branch main
  ```

- **The password:** two Pages secrets, `BETA_PASSWORD_HASH` (a salted
  SHA-256; the password itself is stored nowhere on the site) and
  `BETA_SESSION_KEY` (signs the session cookie). `python scripts/beta_access.py
  password` asks for a new one and sets both. `--generate` makes one and saves
  it to `~/.vivome-beta/password.txt`. Then deploy. A new password signs
  everyone out. The site does not limit attempts, so the password needs at
  least 12 characters.
- **A session** lasts 30 days, in an `HttpOnly`, `Secure` cookie. It ends
  early when the email leaves the list or the password changes. The /api
  door drops the cookie, so the service never sees it. Every page's header
  gains a "Beta" mark and a "Sign out" link (`/__beta/signout`), added on the
  way out, so `web/` itself has neither.
- **A deployment without the two secrets** lets nobody in: it answers 503.

Every request now runs the middleware, so it counts toward the Workers free
plan's 100,000 requests a day. A visit loads a few dozen files.

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
- A part is used only when it answers OK at its own length. A missing, cut
  or wrong part makes a ranged answer 502, and breaks a whole-file stream
  rather than send other bytes as the video.

The page links the file at its usual address, so nothing changes for it.

## The labelling service, through the site

The service on Cloud Run answers only through the website. Pages call their
own site's `/api/status` and `/api/project`; the Function forwards each
request to `SERVICE_URL` with the secret `SERVICE_SECRET` in the
`X-VivOME-Proxy-Secret` header, and the service, with the same secret in
`VIVOME_PROXY_SECRET`, answers 403 to anything without it. The Function
keeps the visitor's cookies, any `cf-access-*` headers and the visitor's
address on the site; the service gets none of them. Behind the site's
sign-in (above), only signed-in visitors reach it. Cloudflare takes at most 100 MB in
one request, and Cloud Run at most 32 MiB in an HTTP/1 request, which the
service's server speaks. So the hosted copy's upload limit is 31 MiB
(`VIVOME_MAX_UPLOAD_MB` in `deploy/huggingface/Dockerfile`), and the page
checks a file against it before sending.

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

## The large files (R2), not active

The site does not need them: the gene profiles reach it as shards (above).
To serve the CSVs themselves at their usual URLs, R2 must first be enabled
once in the Cloudflare dashboard (R2 Object Storage). Then:

1. Create the bucket: `npx wrangler@4 r2 bucket create vivome-atlas-data`.
2. Upload the three files under the key `data/<file name>`. The 1.4 GB parts
   are beyond Wrangler's single upload size, so they go through R2's S3 API,
   for example with rclone and an R2 API token.
3. Build with `python scripts/build_pages_site.py --r2 vivome-atlas-data` and
   deploy.

That build adds a Pages Function (`functions/data/[[path]].js`) that serves
the three files from the bucket at their usual `/data/...` URLs, so no page
changes, and adds their three paths to `_routes.json`.

R2's free tier covers 10 GB of storage, and downloads are free.
