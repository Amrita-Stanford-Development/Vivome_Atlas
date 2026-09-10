import unittest

import numpy as np

from service.pipeline import alignment


class ParseMatrixCsvTests(unittest.TestCase):
    def test_features_in_rows_cells_in_columns(self):
        text = "gene,cellA,cellB\nGENE1,1.0,2.0\nGENE2,3.0,4.0\n"
        raw = alignment.parse_matrix_csv(text)
        self.assertEqual(raw.gene_names, ["GENE1", "GENE2"])
        self.assertEqual(raw.cell_ids, ["cellA", "cellB"])
        np.testing.assert_array_equal(raw.values, [[1.0, 2.0], [3.0, 4.0]])

    def test_blank_cell_becomes_nan_not_zero(self):
        text = "gene,cellA,cellB\nGENE1,,2.0\n"
        raw = alignment.parse_matrix_csv(text)
        self.assertTrue(np.isnan(raw.values[0, 0]))
        self.assertEqual(raw.values[0, 1], 2.0)


class ZScorePerGeneTests(unittest.TestCase):
    def test_zscores_use_only_this_datasets_own_stats(self):
        raw = np.array([[0.0, 10.0, 20.0]])  # one gene, three cells
        z = alignment.zscore_per_gene(raw)
        self.assertAlmostEqual(z.mean(), 0.0, places=5)
        self.assertAlmostEqual(z.std(), 1.0, places=5)

    def test_zero_variance_gene_scores_to_zero_not_inf(self):
        raw = np.array([[5.0, 5.0, 5.0]])
        z = alignment.zscore_per_gene(raw)
        self.assertTrue(np.all(np.isfinite(z)))
        np.testing.assert_array_equal(z, np.zeros_like(z))

    def test_nan_entries_do_not_poison_the_dataset_statistic(self):
        raw = np.array([[1.0, 2.0, np.nan]])
        z = alignment.zscore_per_gene(raw)
        self.assertTrue(np.isfinite(z[0, 0]) and np.isfinite(z[0, 1]))


class AlignToFeatureSpaceTests(unittest.TestCase):
    feature_genes = ["A1BG", "A2M", "AAAS", "UNMEASURED_GENE"]

    def test_zero_fills_genes_outside_the_uploaded_schema(self):
        raw = alignment.RawMatrix(
            gene_names=["A1BG", "A2M"], cell_ids=["c1", "c2"],
            values=np.array([[1.0, 2.0], [3.0, 4.0]]),
        )
        aligned = alignment.align_to_feature_space(raw, self.feature_genes)
        self.assertEqual(aligned.values.shape, (2, 4))
        np.testing.assert_array_equal(aligned.values[:, 2], [0.0, 0.0])  # AAAS never uploaded
        np.testing.assert_array_equal(aligned.values[:, 3], [0.0, 0.0])  # UNMEASURED_GENE

    def test_mask_is_1_for_observed_0_for_missing(self):
        raw = alignment.RawMatrix(
            gene_names=["A1BG", "A2M"], cell_ids=["c1", "c2"],
            values=np.array([[1.0, 2.0], [3.0, 4.0]]),
        )
        aligned = alignment.align_to_feature_space(raw, self.feature_genes)
        np.testing.assert_array_equal(aligned.mask[:, 0], [1.0, 1.0])  # A1BG
        np.testing.assert_array_equal(aligned.mask[:, 2], [0.0, 0.0])  # AAAS, never uploaded
        np.testing.assert_array_equal(aligned.mask[:, 3], [0.0, 0.0])  # UNMEASURED_GENE

    def test_per_cell_dropout_within_a_matched_gene_is_not_blanket_observed(self):
        """A gene present in the file's schema can still be missing for a
        specific cell; the mask must reflect that cell, not the column."""
        raw = alignment.RawMatrix(
            gene_names=["A1BG"], cell_ids=["c1", "c2"],
            values=np.array([[1.0, np.nan]]),
        )
        aligned = alignment.align_to_feature_space(raw, self.feature_genes)
        np.testing.assert_array_equal(aligned.mask[:, 0], [1.0, 0.0])
        self.assertEqual(aligned.values[1, 0], 0.0)

    def test_unmatched_genes_outside_the_feature_space_are_counted_and_dropped(self):
        raw = alignment.RawMatrix(
            gene_names=["A1BG", "NOT_IN_SPACE"], cell_ids=["c1"],
            values=np.array([[1.0], [2.0]]),
        )
        aligned = alignment.align_to_feature_space(raw, self.feature_genes)
        self.assertEqual(aligned.n_features_matched, 1)
        self.assertEqual(aligned.n_features_unmatched, 1)

    def test_low_coverage_is_reported_not_hidden(self):
        raw = alignment.RawMatrix(gene_names=["A1BG"], cell_ids=["c1"], values=np.array([[1.0]]))
        aligned = alignment.align_to_feature_space(raw, self.feature_genes)
        self.assertAlmostEqual(aligned.coverage, 1 / 4)
        np.testing.assert_array_equal(aligned.per_cell_coverage, [1 / 4])


if __name__ == "__main__":
    unittest.main()
