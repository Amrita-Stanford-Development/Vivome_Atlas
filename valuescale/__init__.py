"""valuescale: is a quantification table still on a linear scale (it needs a
log), or already log-transformed?

    import valuescale
    report = valuescale.detect(values)        # genes x cells, NaN for missing
    logged = valuescale.apply(values, report.reading)

`detect` returns a ScaleReport (valuescale/report.py): the verdict, the set
of readings the calibrated answer contains, the reading to use, the
stratum, the probabilities and thresholds, and the guarantee. For a protein
table like the calibration's, the right reading is missing from the set at
most 5% of the time, with 95% confidence
(research/benchmark/protocol-value-scale.md). `apply` reads the values as
the projection service reads a protein table.

The plan is research/value-scale-plan.md. The package:
- the method: gates.py, statistics.py, score.py, conformal.py and
  method.assess, from a table to a verdict with its reason (B2; the score
  as amended before calibration, protocol amendment 5);
- the calibration: calibrated.py and calibration/protein-v1.json (B4);
- the baselines other tools use, for comparison: baselines.py (B4);
- not shipped: the diagnostic bank and the calibration and test corpus
  (corpus/, Step 1 and B3), with B4's calibration and the one-time scorer.
Nothing here imports the projection service, so the package can leave this
repository unchanged.
"""
from __future__ import annotations

import numpy as np

from valuescale import calibrated, conformal, method
from valuescale.report import GUARANTEE, UNDECIDED_READING, ScaleReport

__version__ = "0.1.0"
__all__ = ["detect", "apply", "ScaleReport"]


def detect(matrix, calibration: "calibrated.Calibration | None" = None) -> ScaleReport:
    """The scale report of `matrix` (genes x cells, NaN for missing), with
    the shipped calibration unless another is given."""
    x = np.asarray(matrix, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError(f"a table has two dimensions (genes x cells), not {x.ndim}")
    cal = calibration or calibrated.load()
    columns = int(x.shape[1])
    stratum = cal.stratum_for(columns)
    notes = []
    used = stratum
    if stratum is None and columns > cal.widest().columns[1]:
        used = cal.widest()
        notes.append(f"{columns:,} columns, more than the {used.columns[1]:,} calibrated: the {used.name} thresholds "
                     "are used, without the guarantee")
    thresholds = dict(used.thresholds) if used else dict(cal.strata[0].thresholds)
    if any(t is None for t in thresholds.values()):
        raise ValueError(f"calibration {cal.id} has too few deposits for a threshold in "
                         f"{(used or cal.strata[0]).name}")
    a = method.assess(x, cal.model, thresholds)
    in_stratum = stratum is not None and columns >= conformal.MIN_COLUMNS
    guarantee = (GUARANTEE.format(n=min(stratum.n.values()), alpha=cal.alpha, confidence=1 - cal.delta,
                                  calibration=cal.id) if in_stratum else None)
    verdict = a["verdict"]
    parts = a["parts"]
    return ScaleReport(
        verdict=verdict,
        reading=verdict if verdict in conformal.CLASSES else UNDECIDED_READING,
        set=tuple(a["set"]),
        stratum=used.name if used and columns >= conformal.MIN_COLUMNS else None,
        columns=columns,
        rows=int(x.shape[0]),
        gate=a["gate"],
        reason=a["reason"],
        warning=a["warning"],
        probabilities=dict(a["scores"]) if a["scores"] else None,
        thresholds=thresholds if used and columns >= conformal.MIN_COLUMNS else None,
        typicality={y: p["typicality"] for y, p in parts.items()} if parts else None,
        statistics=dict(a["features"]) if a["features"] else None,
        calibration=cal.id,
        guarantee=guarantee,
        notes=tuple(notes),
    )


def apply(matrix, reading: str, zeros: str | None = None) -> np.ndarray:
    """`matrix` (NaN for missing) read as `reading`, as the projection
    service reads a protein table (service/pipeline/alignment.py
    apply_reading): "linear" makes each 0 missing ("not detected") and takes
    log2 of the rest, and refuses a negative value (no intensity is
    negative); "log" leaves the values as they are, or makes each 0 missing
    when `zeros` is "missing". The input is not changed."""
    if reading not in ("linear", "log"):
        raise ValueError(f"no such reading of the values: {reading!r} (linear or log)")
    x = np.array(matrix, dtype=np.float64)
    if reading == "log":
        if zeros == "missing":
            x[x == 0] = np.nan
        return x
    observed = ~np.isnan(x)
    negative = int((x[observed] < 0).sum())
    if negative:
        raise ValueError(f"{negative:,} {'value is' if negative == 1 else 'values are'} negative, so they are not raw "
                         "intensities: the table is already on a log scale, or centred")
    zero = observed & (x == 0)
    x[zero] = np.nan
    keep = observed & ~zero
    x[keep] = np.log2(x[keep])
    return x
