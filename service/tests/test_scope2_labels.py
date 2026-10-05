"""Every copy of SCoPE2's cell labels matches the curated source
(research/benchmark/scope2_labels/corrected_labels.csv, from the authors'
SingleCellMultiModal object; benchmark/scope2_labels.py). VivOME's copies
once had macrophage and monocyte the wrong way round
(research/benchmark/bugs-and-fixes.md, 8). Local, gitignored copies are
checked when present."""
import csv
import unittest

import pandas as pd

from benchmark import datasets, scope2_labels


class CorrectedLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = pd.read_csv(scope2_labels.LABELS)

    def test_the_source_has_the_curated_counts(self):
        self.assertEqual(list(self.table["orig_index"]), list(range(1490)))
        self.assertEqual(self.table["label"].value_counts().to_dict(), {"macrophage": 1096, "monocyte": 394})
        self.assertTrue((self.table["label"] == self.table["curated"].str.lower()).all())
        self.assertTrue((self.table["class_idx"] == self.table["label"].map(scope2_labels.CLASS_IDX)).all())

    def test_every_copy_matches_the_source(self):
        expected = {"name": self.table["label"].tolist(), "idx": self.table["class_idx"].tolist()}
        for copy in scope2_labels.COPIES:
            path = datasets.REPO / copy.path
            if not path.exists():
                if copy.tracked:
                    self.fail(f"{copy.path} is missing")
                continue
            with self.subTest(copy=copy.path):
                df = pd.read_csv(path, usecols=[copy.row, *copy.columns])
                self.assertEqual(df[copy.row].tolist(), list(range(1490)))
                for col, kind in copy.columns.items():
                    self.assertEqual(df[col].tolist(), expected[kind], col)

    def test_every_parquet_copy_matches_the_source(self):
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("pyarrow is not installed")
        for rel, tracked in scope2_labels.PARQUETS:
            path = datasets.REPO / rel
            if not path.exists():
                if tracked:
                    self.fail(f"{rel} is missing")
                continue
            with self.subTest(copy=rel):
                df = pd.read_parquet(path, columns=["orig_index", "class_idx", "class_name"])
                self.assertEqual(df["orig_index"].tolist(), list(range(1490)))
                self.assertEqual(df["class_name"].tolist(), self.table["label"].tolist())
                self.assertEqual(df["class_idx"].tolist(), self.table["class_idx"].tolist())

    def test_v3_evidence_counts_the_corrected_cells(self):
        path = scope2_labels.V3_TABLES / "latent_centroid_cosine.csv"
        with open(path, newline="", encoding="utf-8") as handle:
            counts = {row["class_name"]: int(row["n_prot_cells"]) for row in csv.DictReader(handle) if int(row["n_prot_cells"])}
        self.assertEqual(counts, {"macrophage": 1096, "monocyte": 394})


if __name__ == "__main__":
    unittest.main()
