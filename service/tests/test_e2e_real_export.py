"""End-to-end regression guard against the real v3 export bundle.

service/model/source/app_export/ carries the export notebook's own real, saved
protein embedding (prot_embedding_scope2.npy) and the real raw input that
produced it (blood_joint_cells_by_proteins_GENELEVEL.tsv). Running that raw
file through the ACTUAL production pipeline code (service/pipeline/pipeline.py's
Stage 1-3 sequence, replicated call-for-call here since run_projection()
doesn't expose the raw 128-d embedding in its response) should reproduce
the notebook's embedding closely -- this is the check that caught two real
bugs during the fair-baseline-comparison work
(research/benchmark/bugs-and-fixes.md): smoothing.py's inverted alpha convention
and wrong neighbour graph, and encoder.py's ReLU-instead-of-GELU activation.
Both are fixed; this test is what would have caught either one before it
shipped, and is here so neither can silently regress.

Note what this test does NOT check: pipeline.py computes Stage 2's
full_query_values as np.nan_to_num(raw.values.T, nan=0.0) -- the query's
raw, un-z-scored values with missing entries zeroed. The export notebook
instead z-scores its own full panel (dataset-level median fill, then
per-gene z-score) before smoothing. On this specific input (SCoPE2's real
GENELEVEL TSV, which happens to have zero missing values and values already
in a small, roughly-normalized range) the two conventions land close
together -- median cosine ~0.9985, not the notebook-exact ~1.0 a fully
matching convention would give. On a real dataset with substantial
missingness (PBMC240's raw DIA-NN search output, ~63% NaN) the two
conventions diverge sharply -- median cosine ~0.78, 5th percentile ~0.23,
some cells anti-correlated. This is a real, measured, currently-UNFIXED gap
between the shipped pipeline and the methodology that produced the
project's headline numbers; see research/benchmark/known-limitations.md. This
test intentionally uses the real pipeline.py convention (not the
notebook's) so it tests what a live user's upload actually gets, and its
threshold is set to what that real, imperfect convention actually achieves
on this input -- not to the notebook-exact 1.0 a convention change might
someday reach.
"""
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from service.pipeline import alignment, smoothing, encoder, reference

APP_EXPORT = Path(__file__).resolve().parents[1] / "model" / "source" / "app_export"


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

        # Exactly pipeline.py's Stage 2 line -- the real production
        # convention, not the notebook's. See module docstring above.
        full_query_values = np.nan_to_num(raw.values.T, nan=0.0)

        smoothed = smoothing.fuzzy_smooth(aligned.values, full_query_values)
        cls.service_embedding = encoder.load_encoder().encode(smoothed, aligned.mask)
        cls.notebook_embedding = np.load(APP_EXPORT / "prot_embedding_scope2.npy")

    def test_reproduces_the_notebooks_embedding_closely(self):
        service_unit = self.service_embedding / np.clip(
            np.linalg.norm(self.service_embedding, axis=1, keepdims=True), 1e-8, None
        )
        notebook_unit = self.notebook_embedding / np.clip(
            np.linalg.norm(self.notebook_embedding, axis=1, keepdims=True), 1e-8, None
        )
        per_cell_cosine = np.sum(service_unit * notebook_unit, axis=1)

        # The GELU/ReLU bug pulled the median to ~0.75; the real production
        # full_query_values convention (see module docstring) caps the best
        # achievable median on this input at ~0.9985, not 1.0 -- these
        # thresholds catch a real architecture/smoothing regression while
        # tolerating the known, disclosed, un-fixed convention gap.
        self.assertGreater(np.median(per_cell_cosine), 0.99)
        self.assertGreater(np.percentile(per_cell_cosine, 5), 0.95)


if __name__ == "__main__":
    unittest.main()
