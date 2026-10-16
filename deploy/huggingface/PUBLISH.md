# Publishing the projection service

The live service runs on **Google Cloud Run** (project `vivome-atlas`, region
`us-central1`), built from the same staged folder and `Dockerfile` as a
Hugging Face Space would be. Hugging Face hosts Docker Spaces on its free CPU
tier only with a PRO subscription, so the Space route below is kept for
reference.

## Google Cloud Run (live)

Settings: 2 vCPU, 4 GiB, at most 1 instance, scaled to zero when idle (the
first request after a quiet spell waits while the container starts),
4 requests per instance, a 300 s timeout, port 7860, public. A budget alert
(about $5, in the billing account's currency) watches the project.

Each release, from the repository root, with the `gcloud` CLI logged in to
the project owner's account:

```bash
python deploy/huggingface/build_space.py
gcloud run deploy vivome-atlas --source deploy/huggingface/space --region us-central1   --memory 4Gi --cpu 2 --max-instances 1 --min-instances 0 --concurrency 4 --timeout 300   --port 7860 --allow-unauthenticated --cpu-boost --execution-environment gen2
python deploy/huggingface/check_space.py https://vivome-atlas-577083340913.us-central1.run.app
```

The check must report `0 differ` before the site points at a new revision.

## Hugging Face Space (reference)

The Space runs `service/` in Docker on Hugging Face's free CPU tier (2 cores,
16 GB). It serves v4.1, accepts at most 2,000 cells and 200 MB per upload, and
projects one upload at a time (settings in `Dockerfile`). Its address is
`https://USER-vivome-atlas.hf.space`, where USER is the Hugging Face account.

## Files

- `Dockerfile`: the image (Python 3.11, CPU torch) and the service's settings.
- `space_card.md`: the Space's public page, written to the Space as `README.md`.
- `build_space.py`: stages the Space in the gitignored folder
  `deploy/huggingface/space`: the service package, only the served version's model files
  (found by loading the bundle and projecting the PBMC240 example), the
  Dockerfile, the card, `requirements.txt` pinned to the building
  interpreter's versions, a `.gitattributes` putting files over 10 MB in Git
  LFS, and `space_manifest.json` (every file's sha256 and the commit).
- `check_space.py`: posts the PBMC240 example to a running service, as the
  site does, and compares every cell with this repository's own run.

## Steps

Done once, by the account owner:
1. Create the Space at https://huggingface.co/new-space: name `vivome-atlas`,
   SDK Docker, hardware CPU basic.
2. Create an access token with write access at
   https://huggingface.co/settings/tokens. Keep it out of files and chats.

Each release, from the repository root:

```bash
python deploy/huggingface/build_space.py
python deploy/huggingface/check_space.py http://127.0.0.1:7860   # optional: first run the staged copy (below)
cd deploy/huggingface/space
git init -b main          # the first time only; later builds keep this .git
git lfs install --local
git add -A
git commit -m "VivOME projection service, release 0.4.0"
git remote add space https://huggingface.co/spaces/USER/vivome-atlas   # the first time only
git push --force space main   # user name USER; password: the token
```

To run the staged copy locally first (as the Space does, on this machine only):

```bash
cd deploy/huggingface/space
VIVOME_HOST=127.0.0.1 VIVOME_PORT=7860 OMP_NUM_THREADS=2 python -m service.app
```

The Space then builds the image (several minutes: torch is the largest
download) and starts. After it shows "Running":

```bash
python deploy/huggingface/check_space.py https://USER-vivome-atlas.hf.space
```

It must report `0 differ`. The Space runs Linux, so the numbers may differ
from this PC's at float32 rounding; a label that differs is not expected and
stops the release.

Then point the site at it: set `DEFAULT_SERVICE_URL` in `web/project.html`
to `https://USER-vivome-atlas.hf.space`, update that page's "Connect to a
projection service" text and the status lines of
`docs/service/projection-api.md` and `web/versions.html`, run the three test
suites, and redeploy the site (`docs/web/hosting.md`).

A free Space sleeps after about two days without visits; the next request
wakes it, which takes a minute or two.
