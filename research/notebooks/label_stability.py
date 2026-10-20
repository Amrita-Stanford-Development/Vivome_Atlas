"""Label stability between releases (docs/web/manifest.md, release protocol
step 5): how much the served answers change from one release to the next, on
the same uploads. No release has measured it so far.

**Releases and the model each served** (scripts/build_manifest.py):
0.2.0 v3; 0.3.0 v3.1; 0.4.0 v4.1; 0.5.0 v4.2; 0.6.0 v4.1 again.

**The definition, fixed here.** Each cell's answer is either an abstention
or a label at the class, group or lineage level. A label stands for the set
of classes it covers, read from v3.1's hierarchy (service/model/v3_1/
nb2_spec_v31.json); v3 answers at class level. For a pair of releases, old
then new, each cell is one of:
- same: both abstain, or the same label at the same level;
- refined: both answer, and the new answer lies inside the old (a group
  became one of its classes);
- coarsened: both answer, and the old answer lies inside the new;
- contradicted: both answer, and neither contains the other;
- newly answered, or newly abstained.

**Label stability** is the share of cells that are same, refined or
coarsened: their new answer does not contradict the last release's and
does not appear or vanish. The contradicted share is the headline
instability. The best guess's agreement is reported beside it (v3 has
none).

**Uploads:** development data only, each sent whole, as a user would,
through the service's own run_projection (protein modality):
- Fulcher 2026 (1,275 cells);
- PBMC240 (238);
- SCoPE2 as published (1,490);
- Furtwangler 2025.
v4.2 differs from v4.1 on protein uploads only, so RNA uploads are not
needed.

**Check, first:** 0.4.0 and 0.6.0 serve the same v4.1. Each upload is
answered twice by it, and the two must be 100% same, or the run stops.
Identical uploads must give identical answers.

A version that cannot load (a missing artifact) is recorded, and its pairs
are skipped.

Writes research/notebook-outputs/label_stability/: rules.json (first),
per_cell.csv.gz, summary.json.

    python research/notebooks/label_stability.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from benchmark import baselines_v31, datasets  # noqa: E402
from service.pipeline import alignment, pipeline, reference  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "label_stability"
SPEC = REPO / "service" / "model" / "v3_1" / "nb2_spec_v31.json"
RELEASES = {"0.2.0": "v3", "0.3.0": "v3.1", "0.4.0": "v4.1", "0.5.0": "v4.2", "0.6.0": "v4.1"}
PAIRS = (("0.2.0", "0.3.0"), ("0.3.0", "0.4.0"), ("0.4.0", "0.5.0"), ("0.5.0", "0.6.0"))
STABLE = ("same", "refined", "coarsened")
KINDS = ("same", "refined", "coarsened", "contradicted", "newly answered", "newly abstained")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def covers(label: "str | None", level: "str | None", hierarchy: dict) -> frozenset:
    if label is None:
        return frozenset()
    if level in (None, "class"):
        return frozenset([label])
    return frozenset(c for c, h in hierarchy.items() if h[level] == label)


def kind(old: tuple, new: tuple, hierarchy: dict) -> str:
    """old and new are (label, level) or (None, None) for an abstention."""
    if old[0] is None and new[0] is None:
        return "same"
    if old[0] is None:
        return "newly answered"
    if new[0] is None:
        return "newly abstained"
    if old == new or (old[0] == new[0] and {old[1], new[1]} <= {None, "class"}):
        return "same"
    a, b = covers(*old, hierarchy), covers(*new, hierarchy)
    if b < a:
        return "refined"
    if a < b:
        return "coarsened"
    return "same" if a == b else "contradicted"


def uploads() -> list[tuple[str, alignment.RawMatrix]]:
    pbmc = alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text())
    return [("Fulcher 2026", datasets.load_fulcher2026_upload()), ("PBMC240", pbmc),
            ("SCoPE2, published", baselines_v31.scope2_raw()), ("Furtwangler 2025", datasets.load_furtwangler2025_upload())]


def answers(bundle, raw) -> pd.DataFrame:
    cells = pipeline.run_projection(bundle, raw)["cells"]
    return pd.DataFrame({
        "label": [None if c.get("abstained") else c.get("label") for c in cells],
        "level": [None if c.get("abstained") else c.get("label_level", "class") for c in cells],
        "best_guess": [(c.get("best_guess") or {}).get("label") for c in cells],
    })


def summarise(kinds: pd.Series, guess_old: pd.Series, guess_new: pd.Series) -> dict:
    share = {k: round(100 * float((kinds == k).mean()), 2) for k in KINDS}
    both = guess_old.notna() & guess_new.notna()
    return {"cells": int(len(kinds)), "label_stability": round(sum(share[k] for k in STABLE), 2), **share,
            "best_guess_agreement": round(100 * float((guess_old[both] == guess_new[both]).mean()), 2) if both.any() else None}


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    rules = {"script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
             "releases": RELEASES, "pairs": PAIRS, "hierarchy_from": str(SPEC.relative_to(REPO)), "spec_sha256": sha256(SPEC)}
    (OUT / "rules.json").write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8", newline="\n")
    t0 = time.time()
    hierarchy = json.loads(SPEC.read_text(encoding="utf-8"))["hierarchy"]
    bundles, missing = {}, {}
    for version in sorted(set(RELEASES.values())):
        try:
            bundles[version] = pipeline.load_bundle(version)
        except reference.PendingArtifactError as exc:
            missing[version] = str(exc)
    print(f"loaded {sorted(bundles)}, missing {sorted(missing)} ({time.time() - t0:.0f}s)", flush=True)
    frames = []
    for name, raw in uploads():
        per = {v: answers(b, raw) for v, b in bundles.items()}
        again = answers(bundles["v4.1"], raw)
        if not again.equals(per["v4.1"]):
            raise SystemExit(f"{name}: v4.1 answered the same upload differently twice; the measure would be wrong")
        frame = pd.DataFrame({"upload": name, "cell_id": list(raw.cell_ids)})
        for v, a in per.items():
            frame[[f"{v}_label", f"{v}_level", f"{v}_best_guess"]] = a[["label", "level", "best_guess"]].to_numpy()
        frames.append(frame)
        print(f"{name}: {len(frame)} cells ({time.time() - t0:.0f}s)", flush=True)
    cells = pd.concat(frames, ignore_index=True)
    summary = {"definition": __doc__.split("**The definition, fixed here.**")[1].split("**Uploads:**")[0].strip(),
               "missing_versions": missing, "determinism_check": "v4.1 answered every upload identically twice", "pairs": {}}
    for old_r, new_r in PAIRS:
        old_v, new_v = RELEASES[old_r], RELEASES[new_r]
        key = f"{old_r} ({old_v}) to {new_r} ({new_v})"
        if old_v not in bundles or new_v not in bundles:
            summary["pairs"][key] = {"skipped": "a version could not load"}
            continue
        k = pd.Series([kind((a, b), (c, d), hierarchy) for a, b, c, d in
                       zip(cells[f"{old_v}_label"], cells[f"{old_v}_level"], cells[f"{new_v}_label"], cells[f"{new_v}_level"])])
        cells[f"kind {old_r} to {new_r}"] = k.to_numpy()
        go, gn = cells[f"{old_v}_best_guess"], cells[f"{new_v}_best_guess"]
        summary["pairs"][key] = {"all": summarise(k, go, gn),
                                 "by_upload": {u: summarise(k[m.to_numpy()], go[m], gn[m])
                                               for u in cells["upload"].unique() for m in [cells["upload"] == u]}}
    cells.to_csv(OUT / "per_cell.csv.gz", index=False, lineterminator="\n")
    summary["seconds"] = round(time.time() - t0)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({p: v.get("all", v) for p, v in summary["pairs"].items()}, indent=1))


if __name__ == "__main__":
    main()
