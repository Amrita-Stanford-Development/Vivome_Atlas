"""End-to-end regression guard against the real v3 export bundle.

service/model/app_export/ carries the export notebook's own real, saved
protein embedding (prot_embedding_scope2.npy) and the real raw input that
produced it (blood_joint_cells_by_proteins_GENELEVEL.tsv). Running that raw
file through the full production pipeline (alignment -> smoothing ->
encoder) must reproduce the notebook's embedding almost exactly -- this is
the check that caught two real bugs during the fair-baseline-comparison
work (Documentation/bugs-and-fixes.md): smoothing.py's inverted alpha
convention and wrong neighbour graph, and encoder.py's ReLU-instead-of-GELU
activation. Both are fixed; this test is what would have caught either one
before it shipped, and is here so neither can silently regress.
"""
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from service.pipeline import alignment, smoothing, encoder, reference

APP_EXPORT = Path(__file__).resolve().parents[1] / "model" / "app_export"


@unittest.skipUnless(
    (APP_EXPORT / "blood_joint_cells_by_proteins_GENELEVEL.tsv").exists(),
    "app_export/blood_joint_cells_by_proteins_GENELEVEL.tsv is Git-LFS content; "
    "run `git lfs pull` to fetch it before this test can run.",
)
class ProductionPipelineReproducesTheRealExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        df = pd.read_csv(
            APP_EXPORT / "blood_joint_cells_by_proteins_GENELEVEL.tsv", sep="\t", index_col=0
        )
        df.columns = df.columns.astype(str).str.upper()
        if df.columns.duplicated().any():
            df = df.T.groupby(level=0).median().T

        raw = alignment.RawMatrix(
            gene_names=df.columns.tolist(),
            cell_ids=df.index.astype(str).tolist(),
            values=df.to_numpy(dtype=np.float32).T,
        )
        feature_genes = reference.load_feature_space_genes()
        aligned = alignment.align_to_feature_space(raw, feature_genes)

        # full_query_values: the query's own complete feature set, z-scored
        # per gene against its own cells (matches VivOME_Prototype_Export.ipynb's
        # clean_numeric + zscore_cols exactly).
        clean = df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        clean = clean.apply(lambda c: c.fillna(c.median()), axis=0).fillna(0.0)
        full_query_values = (
            (clean - clean.mean(axis=0)) / (clean.std(axis=0, ddof=0) + 1e-8)
        ).to_numpy(dtype=np.float32)

        smoothed = smoothing.fuzzy_smooth(aligned.values, full_query_values)
        cls.service_embedding = encoder.load_encoder().encode(smoothed, aligned.mask)
        cls.notebook_embedding = np.load(APP_EXPORT / "prot_embedding_scope2.npy")

    def test_reproduces_the_notebooks_embedding_almost_exactly(self):
        service_unit = self.service_embedding / np.clip(
            np.linalg.norm(self.service_embedding, axis=1, keepdims=True), 1e-8, None
        )
        notebook_unit = self.notebook_embedding / np.clip(
            np.linalg.norm(self.notebook_embedding, axis=1, keepdims=True), 1e-8, None
        )
        per_cell_cosine = np.sum(service_unit * notebook_unit, axis=1)

        # Both real bugs found this session pulled the median well below
        # 0.99 (down to ~0.75); a correct pipeline reproduces every cell at
        # essentially 1.0. 0.999 leaves floating-point headroom without
        # being loose enough to let a real regression slip through.
        self.assertGreater(np.median(per_cell_cosine), 0.999)
        self.assertGreater(np.percentile(per_cell_cosine, 5), 0.999)


if __name__ == "__main__":
    unittest.main()
