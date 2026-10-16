"""Goal 2, Phase 1.2, second design: Hao's dendritic cells with a per-gene
offset removed. The first design (research/notebooks/hao_dc_centres.py; run
history, entry 40) failed both batch checks: the model tells Tabula Sapiens
from Hao within a class at AUC 0.92-0.93, and a pDC centre built from Hao
cells alone recalls 0% of Tabula Sapiens's pDCs. The plan's fallback is a
per-gene offset learned from the classes both atlases share. Development data
only; rules fixed here before the run; a second look at the same data,
recorded as such.

The offset: for each gene, on the reference's class-balanced z-scale, the
mean over fitting classes of (Hao's class mean - Tabula Sapiens's class
mean), each class weighted equally; Hao cells are corrected by subtracting
it (z-scale, genes Hao lacks stay unobserved). Fitting classes: B cells, NK
cells, CD4 T, naive CD4 T and CD8 T (Hao Batch1 against all Tabula Sapiens
cells of the class). No myeloid class is used to fit, so the checks below are
scored on classes the offset never saw.

Checks, both required before any gate is scored:
- C1': the atlas probe of the first design, on corrected Hao cells, within
  classical monocytes, non-classical monocytes and pDCs (not fitting classes),
  Fulcher's and PBMC240's masks. Pass: under each mask the mean AUC is at
  most 0.9.
- C2': the swap test with the pDC centre and class mean from corrected Hao
  pDCs alone. Pass: Tabula Sapiens pDC recall at least 70%.
If both pass, the first design's leakage check C3 and gates G1-G6 are scored
with corrected Hao DCs in the centres (hao_dc_centres.py's rules, unchanged).
If either fails, there is no Hao DC candidate.

Writes research/notebook-outputs/hao_dc_centres/offset.json.

    python research/notebooks/hao_dc_offset.py      # from the repository root
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import hao_dc_centres as first  # noqa: E402

FIT = ("b cell", "natural killer cell", "cd4-positive, alpha-beta t cell",
       "naive thymus-derived cd4-positive, alpha-beta t cell", "cd8-positive, alpha-beta t cell")
PROBE = ("classical monocyte", "non-classical monocyte", first.PDC)
OUT = first.OUT / "offset.json"


class OffsetLab(first.Lab):
    """The first design's lab, with Hao's cells corrected by a per-gene offset on the z-scale."""

    def fit_offset(self) -> np.ndarray:
        rng = np.random.default_rng(0)
        diffs = []
        for cls in FIT:
            ts = np.flatnonzero(self.y == self.names.index(cls))
            ts = np.sort(rng.choice(ts, min(2000, len(ts)), replace=False))
            hao = np.flatnonzero(self.hao_class == cls)
            hao = rng.choice(hao, min(2000, len(hao)), replace=False)
            zt = (first.ts_rows(ts, self.genes) - self.mu) / (self.sd + 1e-8)
            zh = (self.hao_dense(hao) - self.mu) / (self.sd + 1e-8)
            diffs.append(zh.mean(0) - zt.mean(0))
        offset = np.mean(diffs, axis=0)
        return np.where(self.present, offset, 0.0).astype(np.float32)

    def hao_dense(self, idx: np.ndarray) -> np.ndarray:
        X = super().hao_dense(idx)
        if getattr(self, "offset", None) is None:
            return X
        return X - self.offset * (self.sd + 1e-8)  # subtracting the offset on the z-scale, in log units


def probe(lab: OffsetLab) -> dict:
    rng = np.random.default_rng(0)
    out = {}
    for profile in ("fulcher", "pbmc240"):
        aucs = {}
        for cls in PROBE:
            ts = np.flatnonzero(lab.y == lab.names.index(cls))
            ts = rng.choice(ts, min(300, len(ts)), replace=False)
            hao = np.flatnonzero(lab.hao_class == cls)
            hao = rng.choice(hao, min(300, len(hao)), replace=False)
            Xt, Xh = first.ts_rows(np.sort(ts), lab.genes), lab.hao_dense(hao)
            masked = lab.masked(np.vstack([Xt, np.where(lab.present, Xh, np.nan)]), profile, 0)
            Z = lab.embed_reference(np.nan_to_num(masked), np.isfinite(masked))[0]
            ylab = np.r_[np.zeros(len(Xt)), np.ones(len(Xh))]
            aucs[cls] = float(cross_val_score(LogisticRegression(max_iter=2000), Z, ylab, cv=5, scoring="roc_auc").mean())
        out[profile] = {"auc": aucs, "mean": float(np.mean(list(aucs.values())))}
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    lab = OffsetLab()
    lab.offset = None
    lab.offset = lab.fit_offset()
    record = {"offset_abs_median": float(np.median(np.abs(lab.offset[lab.present]))),
              "offset_abs_p95": float(np.percentile(np.abs(lab.offset[lab.present]), 95))}
    record["C1_probe"] = probe(lab)
    print("C1'", json.dumps(record["C1_probe"]), flush=True)
    record["C2_swap"] = first.swap_test(lab)
    print("C2'", json.dumps(record["C2_swap"]), flush=True)
    c1 = all(v["mean"] <= 0.9 for v in record["C1_probe"].values())
    c2 = record["C2_swap"]["pdc_recall_swapped"] >= 70
    record["checks_pass"] = bool(c1 and c2)
    record["second_look"] = True
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in record.items() if k not in ("C1_probe",)}, indent=1))


if __name__ == "__main__":
    main()
