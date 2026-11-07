"""The frozen calibration: each stratum's thresholds and the design model
they were set on (research/benchmark/protocol-value-scale.md, amendment 5).

The file is `calibration/<id>.json` beside this module, written once by
B4's calibration (valuescale/corpus/calibrate.py) and never edited:
- `strata`: each calibrated stratum's name, its column range, the protocol
  strata pooled into it, and per class its threshold (the umbrella k-th
  smallest calibration score), n and k;
- `model`: the design model (valuescale/score.py) the scores come from;
- `alpha`, `delta`: the guarantee's 5% and 95%;
- `corpus`: the calibration deposits (accession, file sha256, columns,
  rows) and the sha256 of that list.

A table finds its stratum by its number of columns. Fewer than the first
stratum's lowest bound has none; more than the last one's highest bound
also has none, and `valuescale.detect` then uses the widest stratum's
thresholds without the guarantee.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from valuescale import score

CALIBRATION_DIR = Path(__file__).resolve().with_name("calibration")
DEFAULT = "protein-v1"


@dataclass(frozen=True)
class Stratum:
    name: str  # "S1", "S2+S3"
    columns: tuple[int, int]  # inclusive
    members: tuple[str, ...]  # the protocol's strata pooled into it
    thresholds: Mapping[str, float | None]  # None: too few calibration deposits for any k
    n: Mapping[str, int]
    k: Mapping[str, int | None]

    def to_json(self) -> dict:
        return {"name": self.name, "columns": list(self.columns), "members": list(self.members),
                "thresholds": dict(self.thresholds), "n": dict(self.n), "k": dict(self.k)}


@dataclass(frozen=True)
class Calibration:
    id: str
    alpha: float
    delta: float
    model: score.Model
    strata: tuple[Stratum, ...]
    corpus_sha256: str
    extra: tuple = ()  # (key, value) pairs kept from the file (written, about, corpus), for to_json

    def stratum_for(self, columns: int) -> Stratum | None:
        return next((s for s in self.strata if s.columns[0] <= columns <= s.columns[1]), None)

    def widest(self) -> Stratum:
        return max(self.strata, key=lambda s: s.columns[1])

    def to_json(self) -> dict:
        out = dict(self.extra)
        out.update({"id": self.id, "alpha": self.alpha, "delta": self.delta,
                    "strata": [s.to_json() for s in self.strata], "corpus_sha256": self.corpus_sha256,
                    "model": self.model.to_json()})
        return out


def from_json(data: Mapping) -> Calibration:
    strata = tuple(Stratum(s["name"], (int(s["columns"][0]), int(s["columns"][1])), tuple(s["members"]),
                           {y: None if t is None else float(t) for y, t in s["thresholds"].items()},
                           {y: int(v) for y, v in s["n"].items()},
                           {y: None if v is None else int(v) for y, v in s["k"].items()})
                   for s in data["strata"])
    extra = tuple((k, v) for k, v in data.items()
                  if k not in ("id", "alpha", "delta", "strata", "corpus_sha256", "model"))
    return Calibration(str(data["id"]), float(data["alpha"]), float(data["delta"]), score.Model.from_json(data["model"]),
                       strata, str(data["corpus_sha256"]), extra)


@lru_cache(maxsize=None)
def load(name: str = DEFAULT) -> Calibration:
    path = CALIBRATION_DIR / f"{name}.json"
    return from_json(json.loads(path.read_text(encoding="utf-8")))
