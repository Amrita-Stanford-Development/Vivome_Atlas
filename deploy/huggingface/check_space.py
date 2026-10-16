"""Checks a running projection service against this repository's own run of
the same version: posts the PBMC240 example
(service/examples/pbmc240_proteins_raw.tsv) to URL/api/project, as the site
does (Origin https://vivome-atlas.pages.dev), and compares every cell's label,
level, abstention, reason and best guess with service.pipeline's run on the
same file. Also checks that the site's origin may read the answer (CORS).
Prints the differences and the largest gaps in the numbers; exit status 1 if
any label, abstention or best guess differs.

    python deploy/huggingface/check_space.py http://127.0.0.1:7860
    python deploy/huggingface/check_space.py https://USER-vivome-atlas.hf.space
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv"
ORIGIN = "https://vivome-atlas.pages.dev"
FIELDS = ("label", "label_level", "abstained", "abstain_reason")


def request(url: str, body: bytes | None = None, content_type: str | None = None) -> tuple[int, dict, dict]:
    headers = {"Origin": ORIGIN}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, method="POST" if body is not None else "GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=900) as response:
            return response.status, dict(response.headers), json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), json.loads(exc.read())


def post_example(base: str) -> tuple[int, dict, dict, float]:
    boundary = "VIVOMECHECK"
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="modality"\r\n\r\nprot'
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="matrix"; filename="pbmc240.tsv"\r\n\r\n'
            ).encode() + EXAMPLE.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    start = time.time()
    status, headers, payload = request(f"{base}/api/project", body, f"multipart/form-data; boundary={boundary}")
    return status, headers, payload, time.time() - start


def main() -> None:
    base = sys.argv[1].rstrip("/")
    status, headers, info = request(f"{base}/api/status")
    print(f"status {status}: {json.dumps(info)}")
    if status != 200:
        raise SystemExit(1)
    if headers.get("Access-Control-Allow-Origin") != ORIGIN:
        print(f"CORS: {ORIGIN} may not read the answers (Access-Control-Allow-Origin "
              f"{headers.get('Access-Control-Allow-Origin')!r})")
    status, headers, remote, seconds = post_example(base)
    print(f"project {status} in {seconds:.1f} s; {remote.get('n_cells')} cells; CORS "
          f"{headers.get('Access-Control-Allow-Origin') == ORIGIN}")
    if status != 200:
        print(json.dumps(remote))
        raise SystemExit(1)

    sys.path.insert(0, str(REPO))
    warnings.simplefilter("ignore")
    from service.pipeline import alignment, pipeline
    version = info["pipeline_version"]
    local = pipeline.run_projection(pipeline.load_bundle(version),
                                    alignment.parse_matrix_csv(EXAMPLE.read_text(encoding="utf-8")))
    if remote["model_version"] != local["model_version"]:
        print(f"model differs: {remote['model_version']!r} against {local['model_version']!r}")
    differences = 0
    gaps = {"best_guess_probability": 0.0, "reference_similarity": 0.0, "confidence": 0.0, "coordinates": 0.0}
    for r, l in zip(remote["cells"], local["cells"]):
        changed = [f for f in FIELDS if r.get(f) != l.get(f)]
        if r.get("best_guess", {}).get("label") != l.get("best_guess", {}).get("label"):
            changed.append("best_guess")
        if r["cell_id"] != l["cell_id"] or changed:
            differences += 1
            print(f"  {l['cell_id']}: {', '.join(changed) or 'cell order'}")
        if "best_guess" in r and "best_guess" in l:
            gaps["best_guess_probability"] = max(gaps["best_guess_probability"],
                                                 abs(r["best_guess"]["probability"] - l["best_guess"]["probability"]))
        gaps["reference_similarity"] = max(gaps["reference_similarity"],
                                           abs(r["reference_similarity"] - l["reference_similarity"]))
        if r.get("confidence") is not None and l.get("confidence") is not None:
            gaps["confidence"] = max(gaps["confidence"], abs(r["confidence"] - l["confidence"]))
        gaps["coordinates"] = max(gaps["coordinates"], float(np.max(np.abs(np.subtract(r["coordinates"], l["coordinates"])))))
    if len(remote["cells"]) != len(local["cells"]):
        differences += 1
        print(f"  cell count {len(remote['cells'])} against {len(local['cells'])}")
    print(f"{len(local['cells'])} cells compared, {differences} differ; largest gaps "
          + ", ".join(f"{k} {v:.2e}" for k, v in gaps.items()))
    raise SystemExit(1 if differences else 0)


if __name__ == "__main__":
    main()
