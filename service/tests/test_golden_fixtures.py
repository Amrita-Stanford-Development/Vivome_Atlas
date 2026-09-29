"""Golden fixtures: full end-to-end `run_projection()` responses frozen for
a fixed 50-cell slice of real SCoPE2 and real (raw, missing-value-laden)
PBMC240 data, generated once with rng=np.random.default_rng(0). A stronger
regression guard than a single cosine-similarity threshold: catches any
change to the assigned label, abstain reason, confidence, coordinates, or
value_scale detection for these specific real cells, not just an aggregate
similarity number.

Regenerate deliberately (never to make a failing test pass without
understanding why it changed) with the generation snippet in
Documentation-adjacent context, or see git history for this file's
introducing commit for the exact script.
"""
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from service.pipeline import pipeline, alignment

FIXTURES = Path(__file__).resolve().parent / "fixtures"
APP_EXPORT = Path(__file__).resolve().parents[1] / "model" / "source" / "app_export"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _build_raw(df: pd.DataFrame) -> alignment.RawMatrix:
    return alignment.RawMatrix(
        gene_names=df.columns.tolist(), cell_ids=df.index.astype(str).tolist(),
        values=df.to_numpy(dtype=np.float32).T,
    )


def _load_scope2_50() -> alignment.RawMatrix:
    df = pd.read_csv(APP_EXPORT / "blood_joint_cells_by_proteins_GENELEVEL.tsv", sep="\t", index_col=0)
    df.columns = df.columns.astype(str).str.upper()
    if df.columns.duplicated().any():
        df = df.T.groupby(level=0).median().T
    return _build_raw(df.iloc[:50])


def _load_pbmc240_50() -> alignment.RawMatrix:
    raw_df = pd.read_csv(EXAMPLES / "pbmc240_proteins_raw.tsv", sep="\t")
    raw_df = raw_df.dropna(subset=["Genes"])
    raw_df["gene"] = raw_df["Genes"].astype(str).str.split(";").str[0].str.upper()
    sample_cols = raw_df.columns[6:-1].tolist()
    mat = raw_df[sample_cols].copy()
    mat.index = raw_df["gene"].values
    mat = mat.groupby(level=0).median()
    df = mat.T
    df.columns = df.columns.astype(str).str.upper()
    return _build_raw(df.iloc[:50])


class GoldenFixtureTestsBase:
    """Shared assertion logic; subclasses set fixture_name and raw_loader."""

    fixture_name: str
    raw_loader = staticmethod(lambda: None)

    @classmethod
    def setUpClass(cls):
        fixture_path = FIXTURES / cls.fixture_name
        if not fixture_path.exists():
            raise unittest.SkipTest(f"{fixture_path} missing")
        with open(fixture_path) as f:
            cls.golden = json.load(f)
        bundle = pipeline.ReferenceBundle.load()
        raw = cls.raw_loader()
        cls.fresh = pipeline.run_projection(bundle, raw, rng=np.random.default_rng(0))

    def test_dataset_level_fields_match(self):
        for key in ("atlas_version", "model_version", "n_cells", "n_features_matched",
                    "n_features_unmatched", "value_scale"):
            self.assertEqual(self.fresh[key], self.golden[key], f"field {key!r} changed")

    def test_every_cell_label_and_abstain_state_match(self):
        for i, (fresh_cell, golden_cell) in enumerate(zip(self.fresh["cells"], self.golden["cells"])):
            self.assertEqual(fresh_cell["cell_id"], golden_cell["cell_id"], f"cell {i} id changed")
            self.assertEqual(fresh_cell["abstained"], golden_cell["abstained"], f"cell {i} abstained changed")
            self.assertEqual(fresh_cell["label"], golden_cell["label"], f"cell {i} label changed")
            self.assertEqual(fresh_cell.get("abstain_reason"), golden_cell.get("abstain_reason"),
                              f"cell {i} abstain_reason changed")
            self.assertEqual(fresh_cell["observed_genes"], golden_cell["observed_genes"],
                              f"cell {i} observed_genes changed")

    def test_every_cell_confidence_and_coordinates_close(self):
        for i, (fresh_cell, golden_cell) in enumerate(zip(self.fresh["cells"], self.golden["cells"])):
            if golden_cell["confidence"] is not None:
                self.assertAlmostEqual(fresh_cell["confidence"], golden_cell["confidence"], places=4,
                                        msg=f"cell {i} confidence changed")
            np.testing.assert_allclose(fresh_cell["coordinates"], golden_cell["coordinates"], atol=1e-4,
                                        err_msg=f"cell {i} coordinates changed")


class Scope2GoldenFixtureTests(GoldenFixtureTestsBase, unittest.TestCase):
    fixture_name = "golden_scope2_50.json"
    raw_loader = staticmethod(_load_scope2_50)


class Pbmc240GoldenFixtureTests(GoldenFixtureTestsBase, unittest.TestCase):
    fixture_name = "golden_pbmc240_50.json"
    raw_loader = staticmethod(_load_pbmc240_50)


if __name__ == "__main__":
    unittest.main()
