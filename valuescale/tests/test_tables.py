"""Candidates, report headers, readers and labels for B3's draw
(research/benchmark/protocol-value-scale.md, "Tables" and "Labels")."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from valuescale.corpus import tables
from valuescale.corpus.remote import File


def _f(path, size=1000):
    return File(path, size, f"https://x/{path}")


SPECTRONAUT_LONG = ["R.Condition", "R.FileName", "PG.ProteinGroups", "PG.Genes", "PG.Quantity"]
SPECTRONAUT_PIVOT = ["PG.ProteinGroups", "PG.Genes", "PG.AvgLog2Quantity", "[1] run_a.raw.PG.Quantity"]
DIANN_REPORT = ["File.Name", "Run", "Protein.Group", "Genes", "PG.Quantity", "PG.MaxLFQ"]


class NameTests(unittest.TestCase):
    def test_native_names_without_regard_to_case(self):
        cases = {"report.pg_matrix.tsv": "diann_matrix", "out/Report.PG_Matrix.tsv": "diann_matrix",
                 "combined_protein.tsv": "fragpipe", "exp1_combined_protein.tsv": "fragpipe",
                 "proteinGroups.txt": "maxquant", "proteinGroups_LFQ.txt": "maxquant",
                 "Study_Proteins.txt": "proteome_discoverer", "report.tsv": "report",
                 "My_Spectronaut_Report.xls": "report", "report.parquet": "report", "data.zip": "archive",
                 "report.pr_matrix.tsv": None, "report.stats.tsv": None, "report.log.txt": None,
                 "peptides.txt": None, "x.raw": None, "proteinGroups.txt.gz": None}
        for name, kind in cases.items():
            self.assertEqual(tables.name_kind(name), kind, name)


class ReportTests(unittest.TestCase):
    def test_headers_tell_spectronaut_from_dia_nn(self):
        self.assertEqual(tables.classify_report(SPECTRONAUT_LONG), "spectronaut_long")
        self.assertEqual(tables.classify_report(SPECTRONAUT_PIVOT), "spectronaut_pivot")
        self.assertEqual(tables.classify_report(DIANN_REPORT), "diann_report")
        self.assertIsNone(tables.classify_report(["Sample", "QC metric", "Value"]))


class CandidateTests(unittest.TestCase):
    def first(self, files, headers=None, members=None):
        headers = headers or {}
        seen = []

        def columns_of(entry):
            seen.append(entry.name)
            return headers.get(entry.name)

        got = tables.first_candidate(files, columns_of, lambda f: members.get(f.path, []) if members else [])
        return got, seen

    def test_the_protocols_order_decides(self):
        files = [_f("b/proteinGroups.txt"), _f("a/combined_protein.tsv"), _f("report.pg_matrix.tsv"), _f("report.tsv")]
        got, seen = self.first(files, {"report.tsv": SPECTRONAUT_LONG})
        self.assertEqual((got.kind, got.entry.file.path), ("diann_matrix", "report.pg_matrix.tsv"))
        self.assertEqual(seen, [])  # no header read when a named table comes first

    def test_ties_go_by_file_name_then_path(self):
        files = [_f("z/proteinGroups.txt"), _f("a/proteinGroups_b.txt"), _f("b/proteinGroups.txt")]
        got, _ = self.first(files)
        self.assertEqual(got.entry.file.path, "b/proteinGroups.txt")

    def test_spectronaut_comes_before_proteome_discoverer_and_dia_nn_reports_last(self):
        files = [_f("x_Proteins.txt"), _f("a_report.tsv"), _f("b_report.tsv")]
        got, _ = self.first(files, {"a_report.tsv": DIANN_REPORT, "b_report.tsv": SPECTRONAUT_PIVOT})
        self.assertEqual((got.kind, got.layout, got.entry.name), ("spectronaut", "spectronaut_pivot", "b_report.tsv"))
        got, _ = self.first(files, {"a_report.tsv": DIANN_REPORT, "b_report.tsv": ["QC"]})
        self.assertEqual(got.kind, "proteome_discoverer")
        got, _ = self.first([_f("a_report.tsv")], {"a_report.tsv": DIANN_REPORT})
        self.assertEqual((got.kind, got.layout), ("diann_report", "long"))

    def test_archive_members_come_last_and_large_archives_are_not_listed(self):
        files = [_f("big.zip", size=tables.ARCHIVE_MAX + 1), _f("small.zip", size=10), _f("readme.txt")]
        members = {"big.zip": ["report.pg_matrix.tsv"], "small.zip": ["sub/proteinGroups.txt", "notes.txt"]}
        got, _ = self.first(files, members=members)
        self.assertEqual((got.kind, got.entry.file.path, got.entry.member), ("maxquant", "small.zip", "sub/proteinGroups.txt"))

    def test_nothing_named_is_no_candidate(self):
        got, _ = self.first([_f("x.raw"), _f("report.tsv")], {"report.tsv": ["QC"]})
        self.assertIsNone(got)


class CountTests(unittest.TestCase):
    def test_quantity_columns_from_a_header(self):
        mq = ["Majority protein IDs", "Gene names", "Intensity", "Intensity A", "Intensity B", "LFQ intensity A"]
        self.assertEqual(tables.quantity_columns("maxquant", "wide", mq), 2)
        fp = ["Protein", "Gene", "Combined Total Peptides", "A Intensity", "A MaxLFQ Intensity", "A Unique Intensity",
              "B Intensity", "Combined Intensity"]
        self.assertEqual(tables.quantity_columns("fragpipe", "wide", fp), 2)
        dn = ["Protein.Group", "Protein.Ids", "Protein.Names", "Genes", "First.Protein.Description", "r1.raw", "r2.raw"]
        self.assertEqual(tables.quantity_columns("diann_matrix", "wide", dn), 2)
        pd_ = ["Checked", "Accession", "Abundance: F1: A", "Abundance: F2: B", "Abundances (Normalized): F1: A"]
        self.assertEqual(tables.quantity_columns("proteome_discoverer", "wide", pd_), 2)
        self.assertEqual(tables.quantity_columns("spectronaut", "spectronaut_pivot", SPECTRONAUT_PIVOT), 1)
        self.assertIsNone(tables.quantity_columns("diann_report", "long", DIANN_REPORT))


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def test_proteome_discoverer_abundance_columns(self):
        path = self.write("x_Proteins.txt", "Checked\tAccession\tGene Symbol\tAbundance: F1: A\tAbundance: F2: B\n"
                          "FALSE\tP1\tG1\t1.5E6\t\nFALSE\tP2\t\t3\t4\nTRUE\t\tG3\t5\t6\nFALSE\t\t\t7\t8\n")
        t = tables.read_proteome_discoverer(path)
        self.assertEqual((t.ids, t.cells), (["G1", "P2", "G3"], ["F1: A", "F2: B"]))
        np.testing.assert_array_equal(t.values, [[1.5e6, np.nan], [3, 4], [5, 6]])

    def test_a_dia_nn_long_report_on_maxlfq(self):
        path = self.write("report.tsv", "Run\tProtein.Group\tGenes\tPG.Quantity\tPG.MaxLFQ\n"
                          "r1\tP1\tG1\t10\t11\nr1\tP1\tG1\t10\t11\nr2\tP1\tG1\t20\t21\nr2\tP2\tG2\t30\t31\n")
        t = tables.read_long(path, "diann_report")
        self.assertEqual((t.ids, t.cells), (["P1", "P2"], ["r1", "r2"]))
        np.testing.assert_array_equal(t.values, [[11, 21], [np.nan, 31]])
        self.assertEqual(t.quantity, "PG.MaxLFQ")

    def test_a_dia_nn_long_report_without_maxlfq_uses_pg_quantity(self):
        path = self.write("report.tsv", "Run\tProtein.Group\tPG.Quantity\tPG.MaxLFQ\nr1\tP1\t10\t0\nr2\tP1\t20\t0\n")
        t = tables.read_long(path, "diann_report")
        self.assertEqual(t.quantity, "PG.Quantity")
        np.testing.assert_array_equal(t.values, [[10, 20]])

    def test_a_spectronaut_long_report(self):
        path = self.write("r.tsv", "R.FileName\tPG.ProteinGroups\tPG.Quantity\nA\tP1\t5\nB\tP1\tFiltered\nB\tP2\t7\n")
        t = tables.read_long(path, "spectronaut_long")
        self.assertEqual((t.ids, t.cells), (["P1", "P2"], ["A", "B"]))
        np.testing.assert_array_equal(t.values, [[5, np.nan], [np.nan, 7]])

    def test_text_where_a_number_belongs_is_unreadable(self):
        path = self.write("r.tsv", "R.FileName\tPG.ProteinGroups\tPG.Quantity\nA\tP1\tabc\n")
        with self.assertRaises(ValueError):
            tables.read_long(path, "spectronaut_long")


class LabelTests(unittest.TestCase):
    def test_a_native_table_is_linear_with_its_softwares_quote(self):
        lab, quote = tables.label("maxquant", ["A", "B"], np.array([[1.0, 2.0]]))
        self.assertEqual(lab, "linear")
        self.assertIn("XIC", quote)

    def test_a_column_naming_a_log_is_log(self):
        self.assertEqual(tables.label("maxquant", ["LOG2(LFQ A)", "B"], np.array([[1.0, -2.0]])), ("log", "LOG2(LFQ A)"))
        self.assertEqual(tables.label("diann_matrix", ["s1_log10", "s2"], np.array([[1.0, 2.0]]))[0], "log")
        self.assertEqual(tables.label("diann_matrix", ["HeLa_log_phase", "x"], np.array([[1.0, 2.0]]))[0], "linear")

    def test_unclear_names_are_excluded_first(self):
        for name in ("log2 ratio A", "A z-score", "A_zscore", "imputed A", "A scaled", "median centered A",
                     "quantile A", "A_vsn", "ComBat A"):
            lab, reason = tables.label("maxquant", [name], np.array([[1.0]]))
            self.assertEqual(lab, "unclear", name)

    def test_a_negative_value_makes_a_linear_label_unclear(self):
        lab, reason = tables.label("diann_matrix", ["A", "B"], np.array([[1.0, np.nan], [-0.5, 2.0]]))
        self.assertEqual(lab, "unclear")
        self.assertIn("negative", reason)

    def test_a_tmt_integrator_table_is_unclear(self):
        self.assertEqual(tables.label("fragpipe", ["A"], np.array([[1.0]]), tmt_integrator=True)[0], "unclear")
        self.assertTrue(tables.is_tmt_integrator(["Index", "Gene", "ReferenceIntensity", "A", "B"]))
        self.assertFalse(tables.is_tmt_integrator(["Protein", "Gene", "Combined Total Peptides", "A Intensity"]))
        self.assertFalse(tables.is_tmt_integrator(["Protein.Group", "Genes", "r1"]))


if __name__ == "__main__":
    unittest.main()
