"""Goal 2: calibrating a narrow-upload check, first design. Rules fixed here
before the run; development and calibration data only. Result: NO GO (run
history, entry 37), so the check was not served.

The score is an upload's leading-component variance over a per-protein
permutation null: on the service's log scale, over the proteins measured in at
least half the cells, each z-scored over its observed values (unobserved 0),
the variance share of the top principal components divided by its mean over a
few seeded permutations of each protein across cells. This script:

1. Scores the simulated RNA uploads of NB3c's calibration suite (240 uploads
   from te_cal cells: single-type, two or three types, five or eight types,
   one lineage, PBMC-like and SCoPE2-like) and the 60 extra single-type
   uploads, materialised with real mass-spectrometry mask profiles
   (research/notebooks/v4_calibration.py, raw_upload). te_eval is not used.
2. Sets the threshold: the 5th percentile of the score among uploads of five
   or more types (the mixed and PBMC-like groups), so at most about 5% of
   broad uploads are flagged. It reports the share flagged in every group.
3. Checks the protein development data, with a pass rule fixed now:
   - not flagged: Fulcher 2026's full upload, PBMC240, PXD070599 DS18 (three
     searches) and DS19 (all mixed PBMCs);
   - flagged: at least 5 of Fulcher's 6 single-type uploads.
   Reported without a rule: Fulcher's two pairs (CD4 T with CD8 T, B with
   monocytes), both SCoPE2 versions (two states of one cell line) and
   Furtwangler 2025 (CD34+ progenitors).
If the pass rule fails, the check is not served.

Writes research/notebook-outputs/narrow_upload/calibration.json and scores.csv.

    python research/notebooks/narrow_upload_calibration.py      # from the repository root
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v4_calibration as phase3  # noqa: E402
from benchmark import baselines_v31, datasets  # noqa: E402
from service.pipeline import alignment  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "narrow_upload"
SETTINGS = {"components": 5, "min_observed": 0.5, "permutations": 3, "min_cells": 20, "min_proteins": 50}
BROAD = ("mixed", "pbmc")
EXTRA = REPO / "research" / "notebook-outputs" / "v4_phase3c" / "exploration_single_type_suite.json"
PUBLIC = REPO / "data" / "incoming" / "public_sets" / "PXD070599_PBMC" / "extracted"


def _leading_share(z: np.ndarray, k: int) -> float:
    s = np.linalg.svd(z, compute_uv=False) ** 2
    return float(s[:k].sum() / s.sum()) if s.sum() > 0 else 0.0


def structure_ratio(values: np.ndarray, components: int, min_observed: float, permutations: int,
                    min_cells: int, min_proteins: int, seed: int = 0) -> "float | None":
    """values: proteins x cells on the log scale, NaN unobserved; None when too small."""
    keep = np.isfinite(values).mean(axis=1) >= min_observed
    if values.shape[1] < min_cells or keep.sum() < min_proteins:
        return None
    x = values[keep].T.astype(np.float64)
    with np.errstate(all="ignore"):
        mean, sd = np.nanmean(x, axis=0), np.nanstd(x, axis=0)
    z = np.nan_to_num((x - mean) / np.where(sd > 1e-8, sd, 1.0), nan=0.0)
    k = min(components, min(z.shape) - 1)
    rng = np.random.default_rng(seed)
    null = np.mean([_leading_share(rng.permuted(z, axis=0), k) for _ in range(permutations)])
    return _leading_share(z, k) / null


def score(values: np.ndarray) -> "float | None":
    return structure_ratio(values, **SETTINGS)


def simulated() -> pd.DataFrame:
    suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
    extra = json.loads(EXTRA.read_text())
    te_cal = set(np.asarray(suites["te_cal"]).tolist())
    profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
    pool = np.load(phase3.NB1 / "pool_idx.npy")
    pos = {g: i for i, g in enumerate(pool)}
    pool_x = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
    get_raw = lambda idx: np.asarray(pool_x[[pos[i] for i in idx]], dtype=np.float32)  # noqa: E731
    n_genes = pool_x.shape[1]
    rows = []
    for s in suites["calib"] + extra:
        if not set(s["cell_idx"]) <= te_cal:
            raise SystemExit(f"{s['id']} draws outside te_cal")
        raw = phase3.raw_upload(s, get_raw, profiles, n_genes)  # cells x genes, NaN unobserved
        rows.append({"upload": s["id"], "group": phase3.GROUP[s["scenario"]], "scenario": s["scenario"],
                     "cells": len(raw), "types": len(s["classes"]), "profile": s["profile"], "score": score(raw.T)})
    return pd.DataFrame(rows)


def protein() -> list[dict]:
    raw = datasets.load_fulcher2026_upload()
    labels = datasets.load_fulcher2026_labels().set_index("cell_id").reindex(raw.cell_ids)["label"].to_numpy()
    log = lambda r: alignment.detect_and_transform_value_scale(r.values)[0]  # noqa: E731
    uploads = [("Fulcher 2026, full", log(raw), "not flagged")]
    for t in ("CD4T", "CD8T", "NK", "B", "monocyte", "DC"):
        uploads.append((f"Fulcher 2026, {t} alone", log(raw)[:, labels == t], "flagged"))
    for pair in (("CD4T", "CD8T"), ("B", "monocyte")):
        uploads.append((f"Fulcher 2026, {' with '.join(pair)}", log(raw)[:, np.isin(labels, pair)], None))
    uploads.append(("PBMC240", log(alignment.parse_matrix_csv(
        (REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text())), "not flagged"))
    for name, path in (("DS18 FAIMS Astral-Zoom", PUBLIC / "DS18" / "FAIMS_Astral-Zoom_MBR"),
                       ("DS18 FAIMS Astral", PUBLIC / "DS18" / "FAIMS_Astral_MBR"),
                       ("DS18 Standard Astral", PUBLIC / "DS18" / "Standard_Astral_MBR"), ("DS19", PUBLIC / "DS19" / "MBR")):
        uploads.append((name, log(alignment.parse_matrix_csv((path / "report.pg_matrix.tsv").read_text(encoding="utf-8"))),
                        "not flagged"))
    uploads.append(("SCoPE2, published", log(baselines_v31.scope2_raw()), None))
    uploads.append(("SCoPE2, reprocessed", log(datasets.load_scope2_reprocessed_upload()), None))
    uploads.append(("Furtwangler 2025", log(datasets.load_furtwangler2025_upload()), None))
    return [{"upload": name, "cells": int(v.shape[1]), "score": score(v), "expected": exp} for name, v, exp in uploads]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sim = simulated()
    threshold = round(float(np.percentile(sim.loc[sim["group"].isin(BROAD), "score"].dropna(), 5)), 4)
    flagged = {g: round(100 * float((d["score"] < threshold).mean()), 1) for g, d in sim.groupby("group")}
    prot = protein()
    for p in prot:
        p["flagged"] = bool(p["score"] is not None and p["score"] < threshold)
    must_pass = [p for p in prot if p["expected"] == "not flagged"]
    must_flag = [p for p in prot if p["expected"] == "flagged"]
    passed = all(not p["flagged"] for p in must_pass) and sum(p["flagged"] for p in must_flag) >= 5
    summary = {"settings": {**SETTINGS, "threshold": threshold}, "threshold_rule": "5th percentile of broad uploads",
               "simulated_flagged_pct_by_group": flagged,
               "simulated_median_score_by_group": {g: round(float(d["score"].median()), 3) for g, d in sim.groupby("group")},
               "protein": prot, "pass_rule_met": bool(passed)}
    (OUT / "calibration.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    sim.round(4).to_csv(OUT / "scores.csv", index=False, lineterminator="\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "protein"}, indent=1))
    for p in prot:
        print(f"  {p['upload']:32} cells {p['cells']:5}  score {p['score'] if p['score'] is None else round(p['score'], 3)}"
              f"  flagged {p['flagged']}  expected {p['expected']}")


if __name__ == "__main__":
    main()
