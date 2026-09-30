"""Loads the reference-side artifacts the pipeline runs against.

`feature_space_genes.csv` and `reference_metadata.csv` are the two
authoritative orderings named in the contract: every input array to the
encoder must match the gene order, and the centroids array / any classifier
head must match the class_idx order. Both files exist today and do not
depend on which encoder architecture is production.

`reference_embedding.npy`, `reference_centroids.npy`, and per-cell property
values are all real now (see service/model/README.md), but the loaders below
still raise `PendingArtifactError` rather than a bare `FileNotFoundError`
when a path doesn't resolve to a file — e.g. an env-var override pointed at
the wrong location — so a caller can render the affected stage as pending
instead of crashing on an unrelated-looking traceback.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from service import config


class PendingArtifactError(RuntimeError):
    """Raised when an artifact is a documented pending item, not a bug."""


def load_feature_space_genes(path: Path = config.FEATURE_SPACE_GENES_PATH) -> list[str]:
    """The authoritative gene order. Every input array to the encoder,
    query or reference, must be reindexed to match this exactly."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [row["gene"] for row in rows]


@dataclass(frozen=True)
class ReferenceClass:
    class_idx: int
    class_name: str
    lineage: str
    n_cells: int


@dataclass(frozen=True)
class ReferenceMetadata:
    """class_idx here is the authoritative class ordering: the centroids
    array and any classifier head must match it (contract, reference_metadata.csv)."""
    cell_ids: list[str]
    class_idx_by_cell: np.ndarray  # (n_cells,) int
    classes: list[ReferenceClass]  # sorted by class_idx

    def class_name(self, class_idx: int) -> str:
        return self._by_idx[class_idx].class_name

    def class_idx_for_name(self, class_name: str) -> int:
        return self._name_to_idx[class_name]

    @property
    def n_classes(self) -> int:
        return len(self.classes)

    def class_positions_by_cell(self) -> np.ndarray:
        """Each cell's class translated from class_idx to its row POSITION
        in self.classes (0..n_classes-1, sorted by class_idx) — the indexing
        reference_centroids and everything in assignment.py actually use.
        The single source for this translation; previously reimplemented
        independently in ReferenceBundle.load() and two test files, which
        risked the tests keeping passing against a stale translation after
        a real fix landed only in production code."""
        position_by_class_idx = {c.class_idx: i for i, c in enumerate(self.classes)}
        return np.array(
            [position_by_class_idx[idx] for idx in self.class_idx_by_cell], dtype=np.int64
        )

    def __post_init__(self):
        object.__setattr__(self, "_by_idx", {c.class_idx: c for c in self.classes})
        object.__setattr__(self, "_name_to_idx", {c.class_name: c.class_idx for c in self.classes})


def load_reference_metadata(path: Path = config.REFERENCE_METADATA_PATH) -> ReferenceMetadata:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    lineage_by_idx: dict[int, str] = {}
    name_by_idx: dict[int, str] = {}
    count_by_idx: dict[int, int] = {}
    cell_ids = []
    class_idx_by_cell = np.empty(len(rows), dtype=np.int64)

    for i, row in enumerate(rows):
        idx = int(row["class_idx"])
        cell_ids.append(row["cell"])
        class_idx_by_cell[i] = idx
        name_by_idx[idx] = row["class_name"]
        lineage_by_idx[idx] = row["lineage"]
        count_by_idx[idx] = count_by_idx.get(idx, 0) + 1

    classes = [
        ReferenceClass(class_idx=idx, class_name=name_by_idx[idx], lineage=lineage_by_idx[idx], n_cells=count_by_idx[idx])
        for idx in sorted(name_by_idx)
    ]
    return ReferenceMetadata(cell_ids=cell_ids, class_idx_by_cell=class_idx_by_cell, classes=classes)


def load_reference_embedding(path: Path = config.REFERENCE_EMBEDDING_PATH) -> np.ndarray:
    """(n_rna_cells, 128) float32, L2 normalised. Required for Stage 6
    (max cosine similarity to any single reference cell)."""
    if not path.exists():
        raise PendingArtifactError(
            f"{path} does not exist. Stage 6 abstention scoring cannot run "
            "against real data without it — check for a stray path override."
        )
    return np.load(path).astype(np.float32)


def load_reference_centroids(path: Path = config.REFERENCE_CENTROIDS_PATH) -> np.ndarray:
    """(n_classes, 128) float32, L2 normalised, ordered by class_idx.
    Required for Stage 4 (unbalanced OT onto reference centroids)."""
    if not path.exists():
        raise PendingArtifactError(
            f"{path} does not exist. Stage 4 label assignment cannot run "
            "against real centroids without it — check for a stray path override."
        )
    return np.load(path).astype(np.float32)


def load_reference_properties(
    path: Path = config.REFERENCE_PROPERTIES_PATH,
    names_path: Path = config.PROPERTY_NAMES_PATH,
) -> "tuple[list[str], np.ndarray]":
    """Per-reference-cell continuous property values, computed on RNA's full
    transcriptome (Stage 8). Not part of the six-file contract — row order
    matches reference_embedding.npy / reference_metadata.csv; column names
    and order come from property_names.json, not a CSV header (this is a raw
    float32 array). Returns (property_names, values), values shape
    (n_rna_cells, n_properties)."""
    if not path.exists():
        raise PendingArtifactError(
            f"{path} does not exist. Stage 8 property transfer cannot run "
            "against real data without it — check for a stray path override."
        )
    if not names_path.exists():
        raise PendingArtifactError(
            f"{names_path} does not exist. {path} exists but cannot be "
            "interpreted without its column names — check for a stray path override."
        )
    with open(names_path, encoding="utf-8") as handle:
        names = json.load(handle)["property_names"]
    values = np.load(path).astype(np.float32)
    if values.shape[1] != len(names):
        raise PendingArtifactError(
            f"{path} has {values.shape[1]} columns but {names_path} names "
            f"{len(names)} properties — they came from different builds."
        )
    return names, values


def load_provenance(path: Path = config.REFERENCE_PROVENANCE_PATH) -> dict:
    """The reference's serving constants and headline measurements — gene list
    hash, class/module counts, the calibrated abstain threshold, seed
    statistics. Recorded for comparison/audit; see abstention.py's module
    docstring for why the live per-request threshold is still what's used."""
    if not path.exists():
        raise PendingArtifactError(f"{path} does not exist.")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def require_v31_artifact(path: Path, produced_by: str) -> Path:
    """The v3.1 components' files (config.V31_DIR) come from T1 NB4's export,
    brought into the service by Track F (research/roadmap.md). Until then
    each is missing, and asking for it raises PendingArtifactError naming the
    notebook that produces it, the same as any other missing artifact."""
    if not path.exists():
        raise PendingArtifactError(
            f"{path} does not exist. It is produced by {produced_by} and lands under "
            "service/model/v3_1/ in Track F (research/roadmap.md, section 8)."
        )
    return path
