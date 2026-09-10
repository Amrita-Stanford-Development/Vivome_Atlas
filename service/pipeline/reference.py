"""Loads the reference-side artifacts the pipeline runs against.

`feature_space_genes.csv` and `reference_metadata.csv` are the two
authoritative orderings named in the contract: every input array to the
encoder must match the gene order, and the centroids array / any classifier
head must match the class_idx order. Both files exist today and do not
depend on which encoder architecture is production.

`reference_embedding.npy`, `reference_centroids.npy`, and per-cell property
values are blocked on the full v3 training run (see
service/model/README.md). Loading them before they exist raises
`PendingArtifactError` with the reason, rather than a bare
FileNotFoundError, so a caller can render Stage 4/6/8 as pending instead of
crashing.
"""
from __future__ import annotations

import csv
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
            f"{path} does not exist. reference_embedding.npy is blocked on the "
            "full v3 training run (see service/model/README.md); Stage 6 "
            "abstention scoring cannot run against real data until it lands."
        )
    return np.load(path).astype(np.float32)


def load_reference_centroids(path: Path = config.REFERENCE_CENTROIDS_PATH) -> np.ndarray:
    """(n_classes, 128) float32, L2 normalised, ordered by class_idx.
    Required for Stage 4 (unbalanced OT onto reference centroids)."""
    if not path.exists():
        raise PendingArtifactError(
            f"{path} does not exist. reference_centroids.npy is blocked on the "
            "full v3 training run (see service/model/README.md); Stage 4 label "
            "assignment cannot run against real centroids until it lands."
        )
    return np.load(path).astype(np.float32)


def load_reference_properties(path: Path = config.REFERENCE_PROPERTIES_PATH) -> "tuple[list[str], np.ndarray]":
    """Per-reference-cell continuous property values, computed on RNA's full
    transcriptome (Stage 8). Not part of the six-file contract and not
    produced by any pipeline in this repo yet — see service/model/README.md.
    Returns (property_names, values) with values shape (n_rna_cells, n_properties)."""
    if not path.exists():
        raise PendingArtifactError(
            f"{path} does not exist. Per-cell reference property values have not "
            "been computed for any reference version yet (not part of the "
            "reference_model.pt/embedding/centroids contract). Stage 8 property "
            "transfer cannot run against real data until this artifact exists."
        )
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        names = [c for c in reader.fieldnames if c != "cell"]
        values = np.array([[float(row[n]) for n in names] for row in reader], dtype=np.float32)
    return names, values
