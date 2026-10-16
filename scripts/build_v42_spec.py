"""Writes v4.2's files into service/model/v4_2/ (Goal 2, Phase 2a; research/
notebook-run-history.md, entry 32).

v4.2 is v4.1's code and data with one change to the best guess: its
correlation term uses protein class means from sorted cells (Rieckmann 2017,
PXD004352) for the 16 classes with a sorted population, and v4.1's RNA class
means for the rest. Three files:
- protein_class_means.npz: the means (classes x proteins, z-scored per
  protein with every class weighted equally; zero rows for uncovered
  classes), the protein symbols, and which classes are covered, computed by
  research/notebooks/rieckmann_feasibility.py's protein_means from
  Rieckmann's proteinGroups.txt (data/incoming/public_sets/, extracted from
  total.proteomes.single.shot.zip; its sha256 is recorded in the spec);
- spec_v42.json: v4.1's spec with version "v4.2", the protein means named
  under best_guess, and its evaluation pending: the service refuses v4.2
  until it has passed (the held-out milestone and the sorted test);
- MANIFEST.json: both, and every v4 data file v4.1 pins (as ../v4/...).

    python scripts/build_v42_spec.py      # from the repository root
    python scripts/build_v42_spec.py --passed RECORD
    # records the evaluation as passed (RECORD: its evidence), changing only the
    # spec's evaluation block and the MANIFEST's entry for the spec; the protein
    # means are left byte for byte as built
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import rieckmann_feasibility as feas  # noqa: E402
from service import config  # noqa: E402

V42_DIR = REPO / "service" / "model" / "v4_2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


EVALUATION = {
    "status": "passed",
    "date": "2026-10-16",
    "basis": ("the internal held-out test (research/notebook-run-history.md, entry 44): on protein its primaries equal "
              "v4.1's (PXD043355 pass; PXD073250 and PXD046211 fail; Tian and PXD021882 void); RNA uploads take "
              "v4.1's path, so the Hao 2021 suite is v4.1's pass; on development protein data (Fulcher 2026, which also "
              "chose v4.1's weight) six-type balanced accuracy is 6.74 points above v4.1's (95% CI 4.26 to 9.23), with "
              "PBMC240, SCoPE2 and Furtwangler 2025 unchanged (entry 45)"),
    "pending": "the sorted CD4/CD8 test (research/benchmark/protocol-sorted-cd4cd8.md)",
}


def record_passed(record: str) -> None:
    spec_path = V42_DIR / "spec_v42.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["evaluation"] = {**EVALUATION, "record": record}
    spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    manifest_path = V42_DIR / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["spec_v42.json"].update(sha256=sha256(spec_path), bytes=spec_path.stat().st_size)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"v4.2's evaluation recorded as passed ({record}); spec sha256 {sha256(spec_path)}, "
          f"MANIFEST sha256 {sha256(manifest_path)}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--passed", metavar="RECORD", help="record the evaluation as passed, with its evidence")
    args = parser.parse_args()
    if args.passed:
        if not (REPO / args.passed).exists():
            raise SystemExit(f"{args.passed} does not exist")
        record_passed(args.passed)
        return
    meta = pd.read_csv(config.RUNTIME_DIR / "reference_metadata.csv")
    class_names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    means, proteins, covered = feas.protein_means(class_names)
    V42_DIR.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()  # written with fixed contents, so a rebuild is byte for byte
    np.savez(buffer, means=means.astype(np.float32), proteins=np.array(proteins, dtype="U"),
             covered=covered.astype(bool))
    (V42_DIR / "protein_class_means.npz").write_bytes(buffer.getvalue())

    v41 = json.loads(config.V41_SPEC_PATH.read_text(encoding="utf-8"))
    spec = copy.deepcopy(v41)
    spec.pop("based_on", None)
    spec["version"] = "v4.2"
    spec["created"] = str(date.today())
    spec["source"] = ("v4.1's spec (service/model/v4_1/spec_v41.json) with protein class means in the correlation "
                      "term (research/notebooks/v42_protein_means.py); built by scripts/build_v42_spec.py")
    spec["based_on"] = {"spec": "service/model/v4_1/spec_v41.json", "sha256": sha256(config.V41_SPEC_PATH)}
    spec["best_guess"]["protein_class_means"] = {
        "file": "protein_class_means.npz",
        "classes_covered": [c for c, ok in zip(class_names, covered) if ok],
        "proteins": len(proteins),
        "source": "Rieckmann 2017 (PXD004352), steady-state LFQ intensities, mean log2 over donors per population, "
                  "populations mapped to reference classes (research/notebooks/rieckmann_feasibility.py)",
        "source_sha256": sha256(feas.RIECKMANN),
        "query": "each protein's first listed gene symbol, upper case; log scale as the service detects it; a gene's "
                 "rows merged by per-cell median; z-scored per gene over observed values within the upload",
        "chosen_on": "nothing tuned: v4.1's settings; development gates in research/notebooks/v42_protein_means.py",
    }
    spec["evaluation"] = {"status": "pending", "record": None,
                          "tests": "the internal held-out test (research/benchmark/side-tests.md) and the sorted CD4/CD8 "
                                   "test (research/benchmark/protocol-sorted-cd4cd8.md)"}
    (V42_DIR / "spec_v42.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")

    v41_manifest = json.loads(config.V41_MANIFEST_PATH.read_text(encoding="utf-8"))
    files = {
        "spec_v42.json": {"sha256": sha256(V42_DIR / "spec_v42.json"), "bytes": (V42_DIR / "spec_v42.json").stat().st_size,
                          "what": "v4.2's settings: v4.1's with protein class means in the correlation term"},
        "protein_class_means.npz": {"sha256": sha256(V42_DIR / "protein_class_means.npz"),
                                    "bytes": (V42_DIR / "protein_class_means.npz").stat().st_size,
                                    "what": "Rieckmann's protein class means (classes x proteins), symbols, classes covered"},
    }
    for rel, entry in v41_manifest["files"].items():
        if not rel.startswith("../v4/"):
            continue
        if sha256(config.V41_DIR / rel) != entry["sha256"]:
            raise SystemExit(f"{rel} does not match v4.1's MANIFEST: rebuild v4 first")
        files[rel] = entry
    (V42_DIR / "MANIFEST.json").write_text(json.dumps({
        "source": "scripts/build_v42_spec.py; v4's data files pinned as v4.1 pins them", "files": files},
        indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {V42_DIR}: {len(proteins)} proteins, {int(covered.sum())} classes covered, evaluation pending")


if __name__ == "__main__":
    main()
