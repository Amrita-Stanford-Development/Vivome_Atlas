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

    def test_tab_separated_file_is_auto_detected(self):
        text = "gene\tcellA\tcellB\nGENE1\t1.0\t2.0\nGENE2\t3.0\t4.0\n"
        raw = alignment.parse_matrix_csv(text)
        self.assertEqual(raw.gene_names, ["GENE1", "GENE2"])
        self.assertEqual(raw.cell_ids, ["cellA", "cellB"])
        np.testing.assert_array_equal(raw.values, [[1.0, 2.0], [3.0, 4.0]])

    def test_dia_nn_report_uses_genes_column_and_drops_annotation_columns(self):
        header = "Protein.Group\tProtein.Names\tGenes\tFirst.Protein.Description\t" \
                 "N.Sequences\tN.Proteotypic.Sequences\t" \
                 r"E:\raw\Astral_SP_1.raw" + "\t" + r"E:\raw\Astral_SP_2.raw"
        row1 = "P1\tNAME1\tGENE1\tdesc\t3\t2\t1.0\t2.0"
        row2 = "P2;P3\tNAME2;NAME3\tGENE2;GENE3\tdesc2\t1\t1\t\t4.0"
        text = "\n".join([header, row1, row2])

        raw = alignment.parse_matrix_csv(text)

        self.assertEqual(raw.gene_names, ["GENE1", "GENE2;GENE3"])
        self.assertEqual(raw.cell_ids, ["Astral_SP_1", "Astral_SP_2"])
        self.assertTrue(np.isnan(raw.values[1, 0]))
        np.testing.assert_array_equal(raw.values, [[1.0, 2.0], [raw.values[1, 0], 4.0]])

    def test_fragpipe_tmt_table_uses_gene_column_and_drops_annotation_and_reference_columns(self):
        header = "\t".join([
            "Index", "NumberPSM", "Gene", "MaxPepProb", "Protein", "Protein ID", "Entry Name",
            "Protein Description", "Organism", "Indistinguishable Proteins", "ReferenceIntensity",
            "run1_127N", "RefInt_run1_126", "run1_rerun_127C", "RefDInt_run1_135ND",
        ])
        row1 = "\t".join(["sp|P1|A_HUMAN", "12", "GENE1", "1", "P1", "P1", "A_HUMAN", "desc",
                          "Homo sapiens", "", "1000", "100.5", "999", "NA", "998"])
        row2 = "\t".join(["sp|P2|B_HUMAN", "3", "GENE2", "0.99", "P2", "P2", "B_HUMAN", "desc2",
                          "Homo sapiens", "P3", "2000", "NA", "999", "300.25", "998"])
        raw = alignment.parse_matrix_csv("\n".join([header, row1, row2]))

        self.assertEqual(raw.gene_names, ["GENE1", "GENE2"])
        self.assertEqual(raw.cell_ids, ["run1_127N", "run1_rerun_127C"])
        self.assertEqual(raw.values[0, 0], np.float32(100.5))
        self.assertEqual(raw.values[1, 1], np.float32(300.25))
        self.assertTrue(np.isnan(raw.values[0, 1]))
        self.assertTrue(np.isnan(raw.values[1, 0]))

    def test_na_is_missing_in_the_plain_contract_too(self):
        raw = alignment.parse_matrix_csv("gene,cellA,cellB\nGENE1,NA,2.0\n")
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

    def test_per_cell_observed_genes_is_an_absolute_count_not_a_fraction(self):
        # values is (n_genes, n_cells): A1BG = [1.0, NaN], A2M = [3.0, 4.0]
        # -- c1 observes both genes (A1BG=1.0, A2M=3.0), c2 only A2M.
        raw = alignment.RawMatrix(
            gene_names=["A1BG", "A2M"], cell_ids=["c1", "c2"],
            values=np.array([[1.0, np.nan], [3.0, 4.0]]),
        )
        aligned = alignment.align_to_feature_space(raw, self.feature_genes)
        np.testing.assert_array_equal(aligned.per_cell_observed_genes, [2, 1])


class DetectAndTransformValueScaleTests(unittest.TestCase):
    def test_linear_scale_is_detected_and_log2_transformed(self):
        raw = np.array([[100.0, 4000.0, 20000.0]])
        transformed, scale = alignment.detect_and_transform_value_scale(raw)
        self.assertEqual(scale.detected, "linear")
        self.assertTrue(scale.transformed)
        np.testing.assert_allclose(transformed, np.log2(raw))

    def test_already_log_scale_is_not_transformed(self):
        raw = np.array([[1.0, 2.0, 3.0]])
        transformed, scale = alignment.detect_and_transform_value_scale(raw)
        self.assertEqual(scale.detected, "log")
        self.assertFalse(scale.transformed)
        np.testing.assert_array_equal(transformed, raw)

    def test_any_negative_value_prevents_the_transform_even_with_a_high_median(self):
        raw = np.array([[-5.0, 4000.0, 20000.0]])
        transformed, scale = alignment.detect_and_transform_value_scale(raw)
        self.assertEqual(scale.detected, "log")
        self.assertFalse(scale.transformed)
        np.testing.assert_array_equal(transformed, raw)

    def test_zero_is_treated_as_not_detected_not_log2_of_zero(self):
        raw = np.array([[0.0, 4000.0, 20000.0]])
        transformed, scale = alignment.detect_and_transform_value_scale(raw)
        self.assertTrue(scale.transformed)
        self.assertTrue(np.isnan(transformed[0, 0]))
        self.assertFalse(np.isnan(transformed[0, 1]))

    def test_nan_entries_are_ignored_by_detection_and_left_nan(self):
        raw = np.array([[np.nan, 4000.0, 20000.0]])
        transformed, scale = alignment.detect_and_transform_value_scale(raw)
        self.assertEqual(scale.detected, "linear")
        self.assertTrue(np.isnan(transformed[0, 0]))

    def test_no_observed_values_at_all_is_unknown_not_a_crash(self):
        raw = np.array([[np.nan, np.nan]])
        transformed, scale = alignment.detect_and_transform_value_scale(raw)
        self.assertEqual(scale.detected, "unknown")
        self.assertFalse(scale.transformed)

    def test_a_log_matrix_and_its_linear_equivalent_transform_to_the_same_values(self):
        """The end-to-end acceptance test from the roadmap: log2(x) and its
        2**x version must be recoverable to the same (transformed) values.
        Magnitudes chosen so 2**x lands in a realistic linear-intensity
        range (hundreds to low thousands, median > 50) -- log2 of small
        values (e.g. 1.5) round-trips to a linear value the detector
        wouldn't flag as linear-scale at all, which would defeat the test."""
        log_values = np.array([[7.0, 8.5, 6.0, 10.0]])
        linear_values = 2 ** log_values
        transformed_linear, scale = alignment.detect_and_transform_value_scale(linear_values)
        self.assertTrue(scale.transformed)
        np.testing.assert_allclose(transformed_linear, log_values, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
