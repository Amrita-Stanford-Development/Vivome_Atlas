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
                 "peptides.txt": None, "x.raw": None, "proteinGroups.txt.gz": None,
                 # raw instrument data zipped: never a protein table, so not listed
                 "HLAII-C4_S1-C4_1_6665.d.zip": "raw_archive", "run1.raw.zip": "raw_archive",
                 "run1.wiff.zip": "raw_archive", "run1.mzML.zip": "raw_archive", "peaks.mgf.zip": "raw_archive",
                 "TUM_lysn_9.zip": "archive", "results.d.tar.zip": "archive"}
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

    def test_macos_companion_files_are_never_tables(self):
        # a zip made on a Mac carries "._" files (resource forks) beside each real file, often under __MACOSX/;
        # B3's walk chose seven of them over the real table
        for name in ("._report.pg_matrix.tsv", "__MACOSX/out/._WU348313_report.pg_matrix.tsv",
                     "DIANN/._P4097_output.pg_matrix.tsv", "__MACOSX/txt/proteinGroups.txt", "._proteinGroups.txt"):
            self.assertIsNone(tables.name_kind(name), name)
        files = [_f("DIANN.zip", size=10)]
        members = ["__MACOSX/DIANN/._WU297517_report.pg_matrix.tsv", "DIANN/WU297517_report.pg_matrix.tsv"]
        cand = tables.first_candidate(files, lambda e: None, lambda f: members)
        self.assertEqual(cand.entry.member, "DIANN/WU297517_report.pg_matrix.tsv")

    def test_raw_data_archives_are_not_listed(self):
        listed = []
        files = [_f("a.d.zip", size=10), _f("b.zip", size=10)]

        def members_of(f):
            listed.append(f.path)
            return ["sub/proteinGroups.txt"] if f.path == "a.d.zip" else []

        self.assertIsNone(tables.first_candidate(files, lambda e: None, members_of))
        self.assertEqual(listed, ["b.zip"])

    def test_many_archives_are_listed_in_order_whatever_finishes_first(self):
        import time
        files = [_f(f"r{i:03d}.zip", size=10) for i in range(30)]

        def members_of(f):
            time.sleep(0.002 * (30 - int(f.path[1:4])))  # the last archives answer first
            return [f"proteinGroups_{f.path[:4]}.txt"]

        got, _ = self.first(files, members={f.path: [f"proteinGroups_{f.path[:4]}.txt"] for f in files})
        self.assertEqual(got.entry.member, "proteinGroups_r000.txt")
        got = tables.first_candidate(files, lambda e: None, members_of)
        self.assertEqual((got.entry.file.path, got.entry.member), ("r000.zip", "proteinGroups_r000.txt"))

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

    def write_bytes(self, name, data):
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_text_is_decoded_as_the_service_decodes_an_upload(self):
        # service/app.py _decode_matrix: UTF-16 by its byte order mark, else UTF-8, else Windows-1252
        cases = {b"A\tB\n": "utf-8-sig", b"\xef\xbb\xbfA\tB\n": "utf-8-sig", "Aé\tB\n".encode("utf-8"): "utf-8-sig",
                 b"\xff\xfe" + "A\tB\n".encode("utf-16-le"): "utf-16", b"\xfe\xff" + "A\tB\n".encode("utf-16-be"): "utf-16",
                 b"A\x97B\tC\n": "cp1252"}
        for i, (data, encoding) in enumerate(cases.items()):
            with self.subTest(data=data):
                self.assertEqual(tables.text_encoding(self.write_bytes(f"t{i}.tsv", data)), encoding)
        # a byte past the first block decides too; an undefined Windows-1252 byte is replaced, as the service does
        self.assertEqual(tables.text_encoding(self.write_bytes("late.tsv", b"A\tB\n" + b"1\t2\n" * 400_000 + b"\x97\n")), "cp1252")
        self.assertEqual(tables.read_text(self.write_bytes("odd.tsv", b"A\x81\x97\tB\n")), "A�—\tB\n")
        self.assertEqual(tables.read_text(self.write_bytes("u16.tsv", b"\xff\xfe" + "Aé\tB\n".encode("utf-16-le"))), "Aé\tB\n")
        with self.assertRaises(ValueError):  # cut mid-character: the service refuses it rather than read it short
            tables.read_text(self.write_bytes("cut.tsv", b"\xff\xfe" + "A\tB\n1".encode("utf-16-le")[:-1]))

    def test_what_the_service_refuses_as_not_text_is_refused_by_every_text_reader(self):
        # service/app.py _decode_matrix: a workbook, a binary file (Parquet, or a NUL in the first 4096 bytes)
        # and UTF-16 cut mid-character are refused, not read as text
        long = "R.FileName\tPG.ProteinGroups\tPG.Quantity\nr1\tP1\t5\n"
        cases = {"workbook": b"PK\x03\x04" + b"\x00" * 8, "parquet": b"PAR1" + b"\x01" * 8 + b"PAR1",
                 "nul": b"A\tB\n1\x002\n", "cut": b"\xff\xfe" + long.encode("utf-16-le")[:-1]}
        readers = {"text": tables.read_text, "long": lambda p: tables.read_long(p, "spectronaut_long"),
                   "proteome discoverer": tables.read_proteome_discoverer}
        for case, data in cases.items():
            path = self.write_bytes(f"{case}.tsv", data)
            for reader, read in readers.items():
                with self.subTest(case=case, reader=reader):
                    with self.assertRaisesRegex(ValueError, "not text|cut off"):
                        read(path)
        # a text file whose first field starts with "PAR1" is text, as the service reads it
        self.assertEqual(tables.read_text(self.write_bytes("par.tsv", b"PAR1\tB\n1\t2\n")), "PAR1\tB\n1\t2\n")

    def test_windows_1252_and_utf_16_reports_are_read(self):
        # B3's walk met three Spectronaut long reports in Windows-1252; a Proteome Discoverer table is read the same way
        long = "R.FileName\tPG.ProteinGroups\tPG.Quantity\nrun—1\tP1\t5\nrun—2\tP1\t7\n"
        for i, data in enumerate([long.encode("cp1252"), b"\xff\xfe" + long.encode("utf-16-le")]):
            with self.subTest(i=i):
                t = tables.read_long(self.write_bytes(f"r{i}.tsv", data), "spectronaut_long")
                self.assertEqual((t.ids, t.cells), (["P1"], ["run—1", "run—2"]))
                np.testing.assert_array_equal(t.values, [[5, 7]])
        pd_text = "Accession\tGene Symbol\tAbundance: F1: A·B\nP1\tG1\t3\n"
        t = tables.read_proteome_discoverer(self.write_bytes("x_Proteins.txt", pd_text.encode("cp1252")))
        self.assertEqual((t.ids, t.cells), (["G1"], ["F1: A·B"]))


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
