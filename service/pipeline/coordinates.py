"""3-component PCA projection of the 128-d latent space, for the
`coordinates` field in the response contract.

Every other view in this app plots a 3-component PCA projection of the
latent space, never the raw 128-d vectors (see CLAUDE.md). The projection
service has to land query cells in that same 3D space, but no PCA transform
artifact is part of the six-file contract — so this fits one directly from
`reference_embedding.npy` once, at load time, and reuses it for every query.
Because both sides come from the same reference, this needs no additional
artifact and stays self-consistent by construction.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PcaTransform:
    mean: np.ndarray  # (dim,)
    components: np.ndarray  # (3, dim)

    def project(self, embeddings: np.ndarray) -> np.ndarray:
        return (embeddings - self.mean) @ self.components.T


def fit_pca_3d(reference_embeddings: np.ndarray) -> PcaTransform:
    mean = reference_embeddings.mean(axis=0)
    centered = reference_embeddings - mean
    covariance = (centered.T @ centered) / max(len(centered) - 1, 1)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(-eigenvalues)[:3]
    components = eigenvectors[:, order].T.astype(np.float32)
    return PcaTransform(mean=mean.astype(np.float32), components=components)
