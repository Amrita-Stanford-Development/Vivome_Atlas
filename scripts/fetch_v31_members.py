"""Put the v3.1 ensemble's five checkpoints in service/model/v3_1/members/.

They are T1 NB1b's V2 checkpoints, ~98 MB each, kept outside git
(service/model/README.md, v3_1/). Their home is the project Drive,
Data/Results/Tier1_v31/NB1b/ckpt/. Download that folder (to
data/incoming/NB1b/ckpt/ by default), then:

    python3 scripts/fetch_v31_members.py                 # from the repository root
    python3 scripts/fetch_v31_members.py --from DIR      # a copy somewhere else

Each file is copied only if its sha256 matches service/model/v3_1/MANIFEST.json;
a file already in place and matching is left alone. Exit 1 on any miss.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
V31_DIR = REPO / "service" / "model" / "v3_1"
DEFAULT_SOURCE = REPO / "data" / "incoming" / "NB1b" / "ckpt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(source: Path) -> list[str]:
    """Copy every checkpoint MANIFEST.json lists; return the problems."""
    manifest = json.loads((V31_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    problems = []
    for rel, entry in manifest["files"].items():
        if not rel.endswith(".pt"):
            continue
        target = V31_DIR / rel
        if target.exists() and sha256(target) == entry["sha256"]:
            print(f"in place  {rel}")
            continue
        candidate = source / Path(rel).name
        if not candidate.exists():
            problems.append(f"{candidate} does not exist")
        elif sha256(candidate) != entry["sha256"]:
            problems.append(f"{candidate} does not match its sha256 in MANIFEST.json")
        else:
            shutil.copyfile(candidate, target)
            print(f"copied    {rel}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="source", type=Path, default=DEFAULT_SOURCE,
                        help=f"folder holding the NB1b checkpoints (default {DEFAULT_SOURCE.relative_to(REPO)})")
    problems = fetch(parser.parse_args().source)
    for problem in problems:
        print(f"MISSING   {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
