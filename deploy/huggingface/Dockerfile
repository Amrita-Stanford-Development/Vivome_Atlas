# The VivOME projection service as a Hugging Face Space (Docker SDK, CPU).
# deploy/huggingface/build_space.py copies this file to the Space's root with
# the service package, the served version's model files and requirements.txt.
FROM python:3.11-slim

# libgomp: the OpenMP runtime torch's and faiss's CPU builds use.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# The settings the service reads (service/config.py). A container sees the
# host's cores but gets 2 on the free tier, so the thread pools are capped to
# match, or they oversubscribe and every projection slows down. The upload
# limit is 31 MiB: Cloud Run takes at most 32 MiB in an HTTP/1 request, which
# this server speaks, and the form around the file needs a little room.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    VIVOME_HOST=0.0.0.0 \
    VIVOME_PORT=7860 \
    VIVOME_PIPELINE_VERSION=v4.1 \
    VIVOME_ALLOWED_ORIGINS=https://vivome-atlas.pages.dev \
    VIVOME_MAX_UPLOAD_CELLS=2000 \
    VIVOME_MAX_UPLOAD_MB=31 \
    VIVOME_MAX_CONCURRENT_PROJECTIONS=1

# Hugging Face runs the container as user 1000.
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user service ./service
COPY --chown=user space_manifest.json .
USER user
EXPOSE 7860
CMD ["python", "-m", "service.app"]
