"""Write the list of Tabula Sapiens v2's organs, the atlas VivOME builds its
references from, to web/data/organs/tabula_sapiens.json.

It reads the Figshare record's public file list (article 27921984, "Tabula
Sapiens v2"): one h5ad per organ. The manifest (scripts/build_manifest.py,
"organs") marks each organ by what VivOME has of it: blood labels files,
the organs in web/data/organs/index.json are maps, the rest are to build.

    python scripts/tabula_sapiens_organs.py      # from the repository root; needs the network
    python scripts/build_manifest.py
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TARGET = REPO / "web" / "data" / "organs" / "tabula_sapiens.json"
ARTICLE = 27921984
API = f"https://api.figshare.com/v2/articles/{ARTICLE}"
PAGE = f"https://figshare.com/articles/dataset/Tabula_Sapiens_v2/{ARTICLE}"
# One organ's file: <Organ>_TSP1_30_version2d_10X_smartseq_scvi_<date>[_updated].h5ad
FILE = re.compile(r"^([A-Za-z_]+?)_TSP1_30_version2d_.*\.h5ad$")


def organs_from(record: dict) -> list[dict]:
    out = []
    for f in record["files"]:
        m = FILE.match(f["name"])
        if not m:
            continue
        name = m.group(1).replace("_", " ")
        out.append({"name": name[0].upper() + name[1:].lower(), "file": f["name"], "bytes": int(f["size"])})
    if not out:
        raise ValueError(f"no organ files in Figshare article {ARTICLE}")
    return sorted(out, key=lambda o: o["name"])


def main() -> None:
    with urllib.request.urlopen(API, timeout=60) as response:
        record = json.load(response)
    data = {
        "source": {"atlas": record["title"], "figshare_article": ARTICLE, "url": PAGE, "retrieved": date.today().isoformat()},
        "organs": organs_from(record),
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes((json.dumps(data, indent=1) + "\n").encode("utf-8"))
    print(f"Wrote {len(data['organs'])} organs to {TARGET.relative_to(REPO)}")


if __name__ == "__main__":
    main()
