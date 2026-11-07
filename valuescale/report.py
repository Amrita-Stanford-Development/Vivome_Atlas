"""The scale report: what `valuescale.detect` says about a table, as a small
plain-JSON record.

- `verdict`: "linear" (take the log), "log" (use as given), "cant_tell"
  (both readings fit) or "unlike_either" (neither does);
- `reading`: the reading to use. The verdict's own for "linear" and "log";
  UNDECIDED_READING otherwise, the cheaper mistake by B1's cost study
  (research/notebook-outputs/value_scale_b1/notes.md);
- `set`: the readings the calibrated answer contains;
- `stratum`: the calibrated stratum whose thresholds were used (None below
  20 columns), with `columns` and `rows` (proteins);
- `gate`, `reason`, `warning`: what decided the table, why it is "can't
  tell" or "unlike either", and the typicality warning
  (valuescale/method.py);
- `probabilities`, `thresholds`, `typicality`, `statistics`: the class
  probabilities, the stratum's thresholds, the typicality ranks and the
  table's statistics (None where a gate or rule decided first);
- `calibration`, `guarantee`: the calibration's id, and the guarantee in
  words when the table lies in a calibrated stratum;
- `notes`: anything else the reader should know.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

UNDECIDED_READING = "linear"
GUARANTEE = ("For tables like the {n} calibration deposits of this stratum (public processed protein tables, "
             "linear as deposited, and constructed logs of them), the right reading is missing from the answer "
             "at most {alpha:.0%} of the time, with {confidence:.0%} confidence ({calibration}).")


def _clean(v):
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if hasattr(v, "item"):  # a numpy scalar
        return _clean(v.item())
    return v


@dataclass(frozen=True)
class ScaleReport:
    verdict: str
    reading: str
    set: tuple[str, ...]
    stratum: str | None
    columns: int
    rows: int
    gate: str | None
    reason: str | None
    warning: str | None
    probabilities: dict | None
    thresholds: dict | None
    typicality: dict | None
    statistics: dict | None
    calibration: str | None
    guarantee: str | None
    notes: tuple[str, ...] = field(default=())

    def to_json(self) -> dict:
        return {k: _clean(getattr(self, k)) for k in self.__dataclass_fields__}
