"""End-to-end product check on Fulcher 2026: post the upload to a running
service exactly as a user would, with default settings, and record what comes
back. Label-free: it reports only the returned composition, never an accuracy.

The upload is the FragPipe TMT-Integrator table as FragPipe writes it:
annotation columns, reference channels, and the original channel names
(including "_rerun"). It is filtered to the 1,275 QC-passed cells. The record
goes to product_check.json in research/benchmark/fulcher2026.

    python3 -m service.app &                       # from the repo root, default settings
    python3 benchmark/fulcher2026_product_check.py [URL]   # default http://127.0.0.1:8001/api/project
"""
import csv
import io
import json
import sys
import urllib.request
import uuid
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datasets  # noqa: E402
from service import config  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001/api/project"
OUT = datasets.REPO / "research" / "benchmark" / "fulcher2026" / "product_check.json"


def user_upload() -> bytes:
    files = datasets.FULCHER2026["files"]
    datasets._check_hashes(datasets.FULCHER2026)
    keep = set(pd.read_csv(files["qc_keep"])["SampleID"])
    rows = list(csv.reader(files["matrix"].read_text().splitlines(), delimiter="\t"))
    header = rows[0]
    columns = [i for i, name in enumerate(header)
               if i < 11 or name.startswith(("RefInt_", "RefDInt_")) or name.replace("_rerun", "") in keep]
    buffer = io.StringIO()
    csv.writer(buffer, delimiter="\t", lineterminator="\n").writerows([[row[i] for i in columns] for row in rows])
    return buffer.getvalue().encode("utf-8")


def post(matrix: bytes) -> dict:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"modality\"\r\n\r\nprot\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"matrix\"; filename=\"fulcher2026.tsv\"\r\n"
            f"Content-Type: text/tab-separated-values\r\n\r\n").encode() + matrix + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(URL, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())


def main() -> None:
    result = post(user_upload())
    cells = result["cells"]
    returned = Counter(f"abstained: {c['abstain_reason']}" if c["abstained"] else c["label"] for c in cells)
    labels = sorted({c["label"] for c in cells if not c["abstained"]})
    record = {
        "what": "Fulcher 2026 upload POSTed to the running service, default settings, as a user would; label-free",
        "service_defaults": {"CROSS_MODAL_SUPPORTED_CLASSES": list(config.CROSS_MODAL_SUPPORTED_CLASSES),
                             "ASSIGNMENT_METHOD": config.ASSIGNMENT_METHOD,
                             "MIN_OBSERVED_GENES": config.MIN_OBSERVED_GENES},
        "response": {k: v for k, v in result.items() if k != "cells"},
        "returned_composition_count": dict(returned.most_common()),
        "returned_composition_pct": {k: round(100 * v / len(cells), 2) for k, v in returned.most_common()},
        "distinct_labels_returned": labels,
        "output_restricted_to_supported_classes": set(labels) <= set(config.CROSS_MODAL_SUPPORTED_CLASSES),
    }
    OUT.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("returned_composition_pct", "output_restricted_to_supported_classes")}, indent=2))


if __name__ == "__main__":
    main()
