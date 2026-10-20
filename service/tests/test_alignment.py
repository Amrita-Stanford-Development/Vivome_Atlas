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

    def test_dia_nn_18_report_with_protein_ids_is_read(self):
        # DIA-NN 1.8's pg_matrix adds Protein.Ids (found on PXD057118 and PXD046999, Track I)
        header = "Protein.Group\tProtein.Ids\tProtein.Names\tGenes\tFirst.Protein.Description\t" \
                 r"D:\raw\Pool_1.raw" + "\t" + r"D:\raw\Pool_2.raw"
        row1 = "P1\tP1;A0A075B6H7\tNAME1\tGENE1\tdesc\t1.0\t2.0"
        raw = alignment.parse_matrix_csv("\n".join([header, row1]))
        self.assertEqual(raw.gene_names, ["GENE1"])
        self.assertEqual(raw.cell_ids, ["Pool_1", "Pool_2"])
        np.testing.assert_array_equal(raw.values, [[1.0, 2.0]])

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

    # MaxQuant's proteinGroups.txt, in its own column layout (read from
    # PXD011683's and PXD029341's files): per-sample peptides, intensity, LFQ
    # intensity and iBAQ columns, flag columns marked "+", 0 for "not quantified".
    MAXQUANT_HEADER = [
        "Protein IDs", "Majority protein IDs", "Peptide counts (all)", "Protein names", "Gene names",
        "Fasta headers", "Number of proteins", "Peptides", "Peptides S1", "Peptides S2", "Sequence coverage [%]",
        "Intensity", "Intensity S1", "Intensity S2", "iBAQ S1", "iBAQ S2", "LFQ intensity S1", "LFQ intensity S2",
        "Only identified by site", "Reverse", "Potential contaminant", "id",
    ]

    def maxquant(self, rows):
        return "\n".join(["\t".join(self.MAXQUANT_HEADER)] + ["\t".join(r) for r in rows])

    def test_maxquant_protein_groups_read_lfq_per_sample_and_drop_flagged_rows(self):
        text = self.maxquant([
            ["P1", "P1", "3", "Name 1", "GENE1", ">sp|P1", "1", "3", "2", "1", "12.5", "1900", "1000", "900", "5", "4",
             "950", "0", "", "", "", "0"],
            ["REV__P9", "REV__P9", "1", "", "", "", "1", "1", "1", "0", "3", "10", "10", "0", "1", "0", "10", "0",
             "", "+", "", "1"],
            ["CON__P8", "CON__P8", "2", "Keratin", "KRT1", "", "1", "2", "1", "1", "8", "700", "300", "400", "2", "2",
             "300", "400", "", "", "+", "2"],
            ["P5", "P5", "1", "Name 5", "GENE5", "", "1", "1", "1", "0", "2", "20", "20", "0", "1", "0", "20", "0",
             "+", "", "", "3"],
            ["P2;P3", "P2;P3", "4;2", "Name 2;Name 3", "GENE2;GENE3", "", "2", "4", "1", "3", "20", "800", "0", "800",
             "0", "6", "0", "500", "", "", "", "4"],
            ["P4", "P4", "1", "", "", "", "1", "1", "1", "1", "5", "60", "30", "30", "1", "1", "30", "30", "", "", "", "5"],
        ])
        raw = alignment.parse_matrix_csv(text)
        self.assertEqual(raw.cell_ids, ["S1", "S2"])
        self.assertEqual(raw.gene_names, ["GENE1", "GENE2;GENE3"])  # flagged rows and a row without a gene are left out
        self.assertEqual(raw.values[0, 0], np.float32(950))
        self.assertTrue(np.isnan(raw.values[0, 1]))  # 0 is "not quantified"
        self.assertTrue(np.isnan(raw.values[1, 0]))
        self.assertEqual(raw.values[1, 1], np.float32(500))

    def test_a_very_long_annotation_field_is_read(self):
        # PXD011683's proteinGroups.txt has ID lists past csv's default 131,072-character field limit
        row = ["P1", "P1", "3", "", "GENE1", ">sp|P1 " + "x" * 300_000, "1", "3", "2", "1", "1", "1900", "1000", "900",
               "5", "4", "950", "0", "", "", "", "0"]
        raw = alignment.parse_matrix_csv(self.maxquant([row]))
        self.assertEqual(raw.gene_names, ["GENE1"])

    def test_maxquant_without_lfq_values_reads_intensity(self):
        rows = [["P1", "P1", "3", "", "GENE1", "", "1", "3", "2", "1", "1", "1900", "1000", "900", "5", "4", "0", "0",
                 "", "", "", "0"]]
        raw = alignment.parse_matrix_csv(self.maxquant(rows))
        self.assertEqual(raw.cell_ids, ["S1", "S2"])
        np.testing.assert_array_equal(raw.values, [[1000, 900]])

    # FragPipe's LFQ protein table (combined_protein.tsv, as in PXD058626).
    FRAGPIPE_HEADER = [
        "Protein", "Protein ID", "Entry Name", "Gene", "Protein Length", "Organism", "Protein Existence",
        "Description", "Protein Probability", "Top Peptide Probability", "Combined Total Peptides",
        "Combined Spectral Count", "Combined Unique Spectral Count", "Combined Total Spectral Count",
        "A_1 Spectral Count", "A_1 Unique Spectral Count", "A_1 Total Spectral Count", "A_1 Intensity",
        "A_1 MaxLFQ Intensity", "B_2 Spectral Count", "B_2 Unique Spectral Count", "B_2 Total Spectral Count",
        "B_2 Intensity", "B_2 MaxLFQ Intensity", "Indistinguishable Proteins",
    ]

    def test_fragpipe_lfq_table_reads_maxlfq_per_sample(self):
        rows = [
            ["sp|P1|A_HUMAN", "P1", "A_HUMAN", "GENE1", "300", "Homo sapiens", "1:Experimental evidence at protein level",
             "desc", "1.0", "0.99", "5", "9", "8", "9", "4", "4", "4", "1500.5", "1400", "5", "4", "5", "0", "0", ""],
            ["sp|P2|B_HUMAN", "P2", "B_HUMAN", "GENE2", "200", "Homo sapiens",
             "2:Experimental evidence at transcript level", "desc", "0.99", "0.98", "2", "3", "3", "3", "0", "0", "0",
             "0", "0", "3", "3", "3", "800", "750.25", "sp|P3|C_HUMAN"],
        ]
        text = "\n".join(["\t".join(self.FRAGPIPE_HEADER)] + ["\t".join(r) for r in rows])
        raw = alignment.parse_matrix_csv(text)
        self.assertEqual(raw.cell_ids, ["A_1", "B_2"])
        self.assertEqual(raw.gene_names, ["GENE1", "GENE2"])
        self.assertEqual(raw.values[0, 0], np.float32(1400))
        self.assertEqual(raw.values[1, 1], np.float32(750.25))
        self.assertTrue(np.isnan(raw.values[0, 1]) and np.isnan(raw.values[1, 0]))

    def test_fragpipe_lfq_table_without_maxlfq_reads_intensity(self):
        header = [c for c in self.FRAGPIPE_HEADER if not c.endswith("MaxLFQ Intensity")]
        row = ["sp|P1|A_HUMAN", "P1", "A_HUMAN", "GENE1", "300", "Homo sapiens", "1:Experimental evidence at protein level",
               "desc", "1.0", "0.99", "5", "9", "8", "9", "4", "4", "4", "1500.5", "5", "4", "5", "60", ""]
        raw = alignment.parse_matrix_csv("\n".join(["\t".join(header), "\t".join(row)]))
        self.assertEqual(raw.cell_ids, ["A_1", "B_2"])
        np.testing.assert_array_equal(raw.values, [[np.float32(1500.5), 60]])

    def test_text_where_a_number_belongs_is_refused_by_name(self):
        """A table the service cannot read says which column holds text, and
        which layouts it reads, instead of failing on a bare conversion."""
        with self.assertRaises(alignment.UnreadableMatrix) as caught:
            alignment.parse_matrix_csv("gene,cellA,Description\nGENE1,1.0,a kinase\n")
        message = str(caught.exception)
        self.assertIn("'Description'", message)
        self.assertIn("MaxQuant", message)
        self.assertIsInstance(caught.exception, ValueError)


class UploadLayoutTests(unittest.TestCase):
    """Faults found by a review of the upload path (2026-10-20), each read
    silently as the wrong cells or values before."""

    def test_maxquant_silac_and_tmt_tables_are_refused_by_kind(self):
        silac = "\t".join(["Majority protein IDs", "Gene names", "Ratio H/L", "Intensity", "Intensity L", "Intensity H"])
        with self.assertRaises(alignment.UnreadableMatrix) as caught:
            alignment.parse_matrix_csv(silac + "\nP1\tGENE1\t1.2\t300\t100\t200\n")
        self.assertIn("SILAC", str(caught.exception))
        tmt = "\t".join(["Majority protein IDs", "Gene names", "Reporter intensity corrected 1 X1",
                         "Reporter intensity corrected 2 X1", "Intensity X1"])
        with self.assertRaises(alignment.UnreadableMatrix) as caught:
            alignment.parse_matrix_csv(tmt + "\nP1\tGENE1\t10\t20\t300\n")
        self.assertIn("TMT", str(caught.exception))

    def test_fragpipe_contaminant_and_decoy_rows_are_left_out(self):
        header = "\t".join(["Protein", "Protein ID", "Gene", "Combined Total Peptides", "A Intensity", "B Intensity"])
        rows = ["sp|P02768|ALBU_HUMAN\tP02768\tALB\t9\t100\t200",
                "contam_sp|P02769|ALBU_BOVIN\tP02769\tALB\t3\t5000\t6000",
                "rev_sp|P12345|X_HUMAN\tP12345\tGENE9\t1\t10\t20"]
        raw = alignment.parse_matrix_csv("\n".join([header] + rows))
        self.assertEqual(raw.gene_names, ["ALB"])
        np.testing.assert_array_equal(raw.values, [[100, 200]])

    def test_fragpipe_unique_and_total_intensity_columns_are_not_cells(self):
        header = "\t".join(["Protein", "Gene", "Combined Total Peptides", "A Intensity", "A Unique Intensity",
                            "A Total Intensity", "A Razor Intensity", "A MaxLFQ Unique Intensity"])
        raw = alignment.parse_matrix_csv(header + "\nsp|P1|A_HUMAN\tGENE1\t3\t100\t90\t110\t95\t0\n")
        self.assertEqual(raw.cell_ids, ["A"])

    def test_a_header_without_the_row_name_corner_is_read(self):
        """R's write.table writes no corner field: every data row is one
        field longer than the header."""
        raw = alignment.parse_matrix_csv("S1\tS2\tS3\nGENE1\t1\t2\t3\nGENE2\t4\t5\t6\n")
        self.assertEqual(raw.cell_ids, ["S1", "S2", "S3"])
        self.assertEqual(raw.gene_names, ["GENE1", "GENE2"])
        np.testing.assert_array_equal(raw.values, [[1, 2, 3], [4, 5, 6]])

    def test_a_trailing_separator_on_every_row_is_not_a_missing_corner(self):
        raw = alignment.parse_matrix_csv("gene,c1,c2\nGENE1,1,2,\nGENE2,3,4,\n")
        self.assertEqual(raw.cell_ids, ["c1", "c2"])
        np.testing.assert_array_equal(raw.values, [[1, 2], [3, 4]])

    def test_r_s_layout_with_blank_missing_values_is_read(self):
        """Blank is R's missing value with na="": a row whose last value is
        missing must not stop the header being read as R writes it."""
        raw = alignment.parse_matrix_csv(_r_table_with_blank_missing_values())
        self.assertEqual(raw.cell_ids, [f"s{i}" for i in range(1, 21)])
        self.assertTrue(np.isnan(raw.values[0, -1]))
        self.assertEqual(raw.values[1, 0], 1.0)

    def test_the_first_50_rows_with_anything_in_them_are_judged(self):
        """Rows of blank fields, and Perseus rows, are not among the 50 rows
        the header is judged by, as in the browser's check
        (web/tests/atlas-file-check.test.js holds the same files)."""
        rows = "".join(f"G{g},{g},{g + 1}\n" for g in range(30))
        raw = alignment.parse_matrix_csv("s1,s2\n" + ",,\n" + rows)
        self.assertEqual(raw.cell_ids, ["s1", "s2"])
        perseus = "#!{Type}E,E\n" * 12
        good = "".join(f"G{g},{g},{g + 1}\n" for g in range(49))
        raw = alignment.parse_matrix_csv("s1,s2\n" + perseus + good + "G49,1,2,3\n")
        self.assertEqual(raw.cell_ids, ["s2"], "row 50 is one field too long, so the header is whole")

    def test_a_row_of_white_space_is_skipped_not_refused(self):
        """As the browser's check skips it: a trailing line of spaces, or a
        lone separator, holds nothing."""
        raw = alignment.parse_matrix_csv("gene,c1,c2\nG0,1,2\nG1,3,4\n \n")
        self.assertEqual(raw.gene_names, ["G0", "G1"])
        raw = alignment.parse_matrix_csv("gene\tc1\tc2\nG0\t1\t2\n\t\nG1\t3\t4\n")
        self.assertEqual(raw.gene_names, ["G0", "G1"])

    def test_a_header_with_a_corner_is_never_shifted(self):
        """Only R's layout shifts the header: a named or blank corner, or a
        data row whose extra field is empty, means the header is whole."""
        raw = alignment.parse_matrix_csv("gene,c1,c2\nG0,1,2,\nG1,3,4,5\n")  # one row's extra field filled
        self.assertEqual(raw.cell_ids, ["c1", "c2"])
        np.testing.assert_array_equal(raw.values, [[1, 2], [3, 4]])
        raw = alignment.parse_matrix_csv("Gene,c1,c2\nG0,1,2,9\nG1,3,4,9\n")  # a corner label
        self.assertEqual(raw.cell_ids, ["c1", "c2"])
        raw = alignment.parse_matrix_csv(",c1,c2\nG0,1,2,9\nG1,3,4,9\n")  # a blank corner
        self.assertEqual(raw.cell_ids, ["c1", "c2"])
        np.testing.assert_array_equal(raw.values, [[1, 2], [3, 4]])

    def test_a_row_too_short_for_the_header_is_refused_naming_its_line(self):
        with self.assertRaises(alignment.UnreadableMatrix) as caught:
            alignment.parse_matrix_csv("gene,c1,c2,c3\nGENE1,1,2,3\nGENE2,4\n")
        self.assertIn("line 3", str(caught.exception))

    def test_a_byte_order_mark_does_not_change_the_reading(self):
        text = "Protein.Group\tProtein.Ids\tGenes\ta.raw\tb.raw\nP1\tP1\tGENE1\t1.0\t2.0\n"
        plain, marked = alignment.parse_matrix_csv(text), alignment.parse_matrix_csv("\ufeff" + text)
        self.assertEqual((marked.gene_names, marked.cell_ids), (plain.gene_names, plain.cell_ids))
        np.testing.assert_array_equal(marked.values, plain.values)

    def test_perseus_annotation_rows_are_skipped(self):
        header = "\t".join(["Majority protein IDs", "Gene names", "LFQ intensity S1", "LFQ intensity S2"])
        rows = ["#!{Type}E\tT\tE\tE", "P1\tGENE1\t100\t200"]
        raw = alignment.parse_matrix_csv("\n".join([header] + rows))
        self.assertEqual(raw.gene_names, ["GENE1"])

    def test_a_table_without_any_identifier_is_refused_by_name(self):
        # a DIA-NN report whose Genes column is blank on every row (a FASTA without GN= fields)
        text = "Protein.Group\tProtein.Names\tGenes\ta.raw\tb.raw\nP1\tN1\t\t1.0\t2.0\nP2\tN2\t\t3.0\t4.0\n"
        with self.assertRaises(alignment.UnreadableMatrix) as caught:
            alignment.parse_matrix_csv(text)
        self.assertIn("'Genes'", str(caught.exception))
        with self.assertRaises(alignment.UnreadableMatrix):
            alignment.parse_matrix_csv("gene,c1,c2\n")  # a header and no rows

    def test_a_maxquant_table_without_any_gene_name_says_so(self):
        header = "\t".join(["Majority protein IDs", "Gene names", "LFQ intensity S1", "LFQ intensity S2"])
        with self.assertRaises(alignment.UnreadableMatrix) as caught:
            alignment.parse_matrix_csv(header + "\nP1\t\t100\t200\nP2\t\t1\t2\n")
        self.assertIn("Gene names", str(caught.exception))


class SpectronautTests(unittest.TestCase):
    """Spectronaut's protein-group pivot report: "PG.Genes", annotation
    columns, and one "[n] <run>.PG.Quantity" column per run."""

    HEADER = ["PG.ProteinGroups", "PG.ProteinAccessions", "PG.Genes", "PG.ProteinNames", "PG.ProteinDescriptions",
              "PG.Organisms", "[1] 20240101_PBMC_cell1.raw.PG.Quantity", "[2] 20240101_PBMC_cell2.raw.PG.Quantity",
              "[3] cell3.d.PG.Quantity"]

    def test_runs_are_cells_and_pg_genes_the_identifiers(self):
        rows = ["P1\tP1\tGENE1\tA_HUMAN\tdesc\tHomo sapiens\t1500.5\tFiltered\t20",
                "P2;P3\tP2;P3\tGENE2;GENE3\tB_HUMAN\tdesc\tHomo sapiens\tNaN\t300\t0"]
        raw = alignment.parse_matrix_csv("\n".join(["\t".join(self.HEADER)] + rows))
        self.assertEqual(raw.cell_ids, ["20240101_PBMC_cell1", "20240101_PBMC_cell2", "cell3"])
        self.assertEqual(raw.gene_names, ["GENE1", "GENE2;GENE3"])
        self.assertEqual(raw.values[0, 0], np.float32(1500.5))
        self.assertTrue(np.isnan(raw.values[0, 1]))  # "Filtered"
        self.assertTrue(np.isnan(raw.values[1, 0]))  # "NaN"
        self.assertTrue(np.isnan(raw.values[1, 2]))  # 0 is not quantified
        self.assertEqual(raw.values[1, 1], np.float32(300))

    def test_a_report_without_run_quantities_is_refused_in_words(self):
        header = ["PG.ProteinGroups", "PG.Genes", "R.FileName", "PG.Quantity"]
        with self.assertRaises(alignment.UnreadableMatrix):
            alignment.parse_matrix_csv("\t".join(header) + "\nP1\tGENE1\trun1\t100\n")


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

    def test_a_gene_with_one_value_in_every_cell_z_scores_to_0_whatever_the_value(self):
        # float32's mean misses a constant by a rounding error, which the std
        # then equals: z came out +/-1, so answers depended on the constant
        for v in (7.3, 0.1, 12.345, 1000.0):
            for n in (20, 238, 2000):
                z = alignment.zscore_per_gene(np.full((1, n), v, np.float32))
                np.testing.assert_array_equal(z, np.zeros((1, n)), err_msg=f"{v} over {n} cells")
        with_missing = np.full((1, 40), 7.3, np.float32)
        with_missing[0, ::3] = np.nan
        np.testing.assert_array_equal(alignment.zscore_per_gene(with_missing), np.zeros((1, 40)))

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


class ZerosAndScaleTests(unittest.TestCase):
    def test_zeros_do_not_hide_a_linear_scale(self):
        """0 is "not detected", so it does not vote in the scale's median: a
        sparse linear matrix with 60% zeros is still linear."""
        rng = np.random.default_rng(0)
        values = rng.uniform(1e5, 1e7, size=(50, 10))
        values[rng.random((50, 10)) < 0.6] = 0.0
        out, scale = alignment.detect_and_transform_value_scale(values)
        self.assertEqual(scale.detected, "linear")
        self.assertFalse(np.any(out == 0))
        self.assertTrue(np.all(np.isnan(out[values == 0])))


def _r_table_with_blank_missing_values():
    """R's write.table(m, sep="\t", na=""): no corner field, and a missing
    value is an empty field, the last one included."""
    header = "\t".join(f"s{i}" for i in range(1, 21))
    rows = []
    for g in range(30):
        values = [str(g + i) for i in range(20)]
        if g % 3 == 0:
            values[-1] = ""  # this row's last cell is missing
        rows.append("\t".join([f"G{g}", *values]))
    return header + "\n" + "\n".join(rows) + "\n"


class QuietZscoreTests(unittest.TestCase):
    def test_a_gene_no_cell_measured_is_0_without_a_warning(self):
        """Every real upload has such genes; each warned in the service's log."""
        import warnings
        values = np.array([[1.0, 2.0, 3.0], [np.nan, np.nan, np.nan]], dtype=np.float32)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            z = alignment.zscore_per_gene(values)
        self.assertEqual([str(w.message) for w in caught], [])
        np.testing.assert_array_equal(z[1], 0.0)


class RnaZerosTests(unittest.TestCase):
    """In RNA a 0 is a measured value, so it votes in the scale's median as it
    always did: raw counts with most values 0 stay as they are, every 0
    measured. Only protein's 0 ("not quantified") is left out of the vote."""

    @staticmethod
    def _counts(cells=50):
        from service.tests.test_golden_fixtures import _load_pbmc240_50
        genes = _load_pbmc240_50().gene_names
        rng = np.random.default_rng(1)
        counts = rng.poisson(150, size=(len(genes), cells)).astype(np.float32)
        counts[rng.random(counts.shape) < 0.75] = 0.0  # Smart-seq-like: most genes not seen in a cell
        return alignment.RawMatrix(gene_names=list(genes), cell_ids=[f"c{i}" for i in range(cells)], values=counts)

    def test_rna_counts_keep_their_zeros_as_measured(self):
        raw = self._counts()
        out, scale = alignment.detect_and_transform_value_scale(raw.values, zeros_vote=True)
        self.assertEqual(scale.detected, "log")
        self.assertTrue(np.all(out[raw.values == 0] == 0))
        _, prot = alignment.detect_and_transform_value_scale(raw.values)
        self.assertEqual(prot.detected, "linear", "protein's zeros still do not vote")

    def test_the_service_passes_the_upload_s_modality(self):
        from service.pipeline import pipeline
        raw = self._counts()
        for version in ("v3", "v3.1", "v4.1"):
            bundle = pipeline.load_bundle(version)
            for modality, expected in (("rna", "log"), ("prot", "linear")):
                with self.subTest(version=version, modality=modality):
                    response = pipeline.run_projection(bundle, raw, modality=modality)
                    self.assertEqual(response["value_scale"]["detected"], expected)


class InputRobustnessTests(unittest.TestCase):
    def test_an_empty_header_names_no_cell(self):
        raw = alignment.parse_matrix_csv("gene\tc1\tc2\t\nCD3E\t1\t2\t\n")
        self.assertEqual(raw.cell_ids, ["c1", "c2"])
        self.assertEqual(raw.values.shape, (1, 2))

    def test_infinite_values_are_missing_before_scale_detection(self):
        values = np.array([[100, 200, -np.inf, 400, 500], [300, 100, 200, 500, np.inf]], dtype=np.float32)
        out, scale = alignment.detect_and_transform_value_scale(values)
        self.assertEqual(scale.detected, "linear", "-inf must not read as a negative, log-scale value")
        self.assertTrue(np.isnan(out[0, 2]) and np.isnan(out[1, 4]))
        np.testing.assert_allclose(out[0, [0, 1, 3, 4]], np.log2([100, 200, 400, 500]), rtol=1e-6)
        z = alignment.zscore_per_gene(out.astype(np.float64))
        self.assertTrue(np.isfinite(z).all())
        self.assertGreater(np.abs(z[0]).sum(), 0, "one infinite value must not erase its whole gene")


class CollapseDuplicateGenesTests(unittest.TestCase):
    def test_rows_for_one_gene_merge_by_per_cell_median_skipping_missing(self):
        nan = np.nan
        raw = alignment.RawMatrix(
            gene_names=["TP53", "A1BG", "tp53", "TP53", "NOT_A_GENE", "NOT_A_GENE"], cell_ids=["a", "b", "c"],
            values=np.array([[1, nan, 5], [2, 2, 2], [3, nan, nan], [8, 4, nan], [9, 9, 9], [7, 7, 7]], dtype=np.float32),
        )
        out = alignment.collapse_duplicate_genes(raw)
        self.assertEqual(out.gene_names, ["TP53", "A1BG", "NOT_A_GENE", "NOT_A_GENE"])
        np.testing.assert_array_equal(out.values[0], [3, 4, 5])  # medians of (1,3,8), (4), (5)
        np.testing.assert_array_equal(out.values[1], raw.values[1])
        np.testing.assert_array_equal(out.values[2:], raw.values[4:], "rows that resolve to no gene are kept as they are")

    def test_a_cell_missing_in_every_duplicate_stays_missing(self):
        raw = alignment.RawMatrix(gene_names=["TP53", "TP53"], cell_ids=["a", "b"],
                                  values=np.array([[np.nan, 1], [np.nan, 3]], dtype=np.float32))
        out = alignment.collapse_duplicate_genes(raw)
        self.assertTrue(np.isnan(out.values[0, 0]))
        self.assertEqual(out.values[0, 1], 2)

    def test_the_service_keeps_every_observed_value_of_a_duplicated_gene(self):
        """PBMC240's DIA-NN report has two PKM rows: 237 cells observed in one,
        22 in the other. Only the last row used to survive."""
        from pathlib import Path
        from service.pipeline import pipeline, reference
        raw = alignment.parse_matrix_csv(
            (Path(__file__).resolve().parents[1] / "examples" / "pbmc240_proteins_raw.tsv").read_text())
        genes = reference.load_feature_space_genes()
        _, aligned, _ = pipeline._prepare_query(genes, raw)
        self.assertEqual(int(aligned.mask[:, genes.index("PKM")].sum()), 237)
        self.assertEqual(aligned.n_features_matched + aligned.n_features_unmatched,
                         len(alignment.collapse_duplicate_genes(raw).gene_names))
