"""benchmark/pxd064083_intake.py and pxd064083_score.py: the label rule, the
readers, the merge of the two searches and the guards follow
research/benchmark/protocol-pxd064083.md. No PXD064083 file is opened here;
each script's --rehearse is its end-to-end check."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from benchmark import pxd064083_intake as intake
from benchmark import pxd064083_score as score
from benchmark.heldout_formats import Table

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "research" / "benchmark" / "protocol-pxd064083.md"


def table(genes, samples, values) -> Table:
    return Table(genes=list(genes), samples=list(samples), values=np.array(values, dtype=np.float32))


class ProtocolAgreementTests(unittest.TestCase):
    def test_the_candidates_and_the_headline(self):
        self.assertEqual(intake.run_models.__module__, "benchmark.heldout_intake")
        self.assertEqual(score.MODELS, {"v31": "v3.1", "v41": "v4.1", "v42": "v4.2", "v52": "v5.2"})
        self.assertEqual(score.MODELS[score.HEADLINE], "v4.1")

    def test_the_protocol_names_the_files_and_the_rules(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for name in intake.FILES.values():
            self.assertIn(name, text)
        self.assertIn(str(intake.MIN_CELLS), text)
        self.assertEqual(intake.PROTOCOL, PROTOCOL.relative_to(REPO).as_posix())

    def test_the_baselines_can_read_the_intakes_matrix(self):
        from benchmark import baselines_inputs
        self.assertIn("heldout_pxd064083", baselines_inputs.HELDOUT)
        self.assertIn("heldout_pxd064083_rehearsal", baselines_inputs.HELDOUT)


class LabelRuleTests(unittest.TestCase):
    def test_the_lineage_from_a_run_name(self):
        cases = {"HC1_Tcell_1": "T", "ALS4_T1_Bcell_3.d": "B", "[3] HC2_T cell_5.d": "T", "HC2_B-cell_1": "B",
                 "HC1_PLASMA": "", "Tcell_Bcell_mix": "", "ALS3_T1_Tcell_2": "T"}
        for run, want in cases.items():
            with self.subTest(run=run):
                self.assertEqual(intake.run_lineage(run), want)

    def test_the_donor_from_a_run_name(self):
        self.assertEqual(intake.run_donor("ALS4_T1_Bcell_3"), "ALS4")
        self.assertEqual(intake.run_donor("[12] HC07_Tcell_1.d"), "HC7")
        self.assertEqual(intake.run_donor("QC_run_1"), "")

    def test_each_lineage_comes_from_its_own_table(self):
        tables = {"T": table(["A"], ["HC1_Tcell_1", "HC1_Tcell_2", "HC1_Bcell_9", "blank_1"], [[1, 2, 3, 4]]),
                  "B": table(["A"], ["ALS2_T1_Bcell_1"], [[5]])}
        labels, info = intake.label_rows(tables)
        self.assertEqual(labels["cell_id"].tolist(), ["HC1_Tcell_1", "HC1_Tcell_2", "ALS2_T1_Bcell_1"])
        self.assertEqual(labels["group"].tolist(), ["T", "T", "B"])
        self.assertEqual(labels["table"].tolist(), ["T", "T", "B"])
        self.assertEqual(labels["status"].tolist(), ["HC", "HC", "ALS"])
        self.assertEqual({e["run"] for e in info["excluded_runs"]}, {"HC1_Bcell_9", "blank_1"})
        self.assertIsNone(info["joint_search"])

    def test_a_joint_search_is_the_upload_alone(self):
        runs = [f"HC1_Tcell_{i}" for i in range(intake.MIN_CELLS)] + [f"HC1_Bcell_{i}" for i in range(intake.MIN_CELLS)]
        tables = {"T": table(["A"], runs, [list(range(len(runs)))]), "B": table(["A"], ["HC9_Bcell_1"], [[1]])}
        labels, info = intake.label_rows(tables)
        self.assertEqual(info["joint_search"], "T")
        self.assertEqual(set(labels["table"]), {"T"})
        self.assertEqual(labels["group"].value_counts().to_dict(), {"T": intake.MIN_CELLS, "B": intake.MIN_CELLS})


class ReaderTests(unittest.TestCase):
    def test_a_spectronaut_pivot_report_in_xlsx(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SEARCH_T.xlsx"
            pd.DataFrame({"PG.ProteinGroups": ["P1", "P2"], "PG.Genes": ["CD3E", "PTPRC"],
                          "[1] HC1_Tcell_1.d.PG.Quantity": [1000.0, np.nan],
                          "[2] HC1_Tcell_2.d.PG.Quantity": [2000.0, 3000.0]}).to_excel(path, index=False)
            got = intake.read_table(path)
        self.assertEqual(got.genes, ["CD3E", "PTPRC"])
        self.assertEqual([intake.run_lineage(s) for s in got.samples], ["T", "T"])
        np.testing.assert_allclose(got.values, [[1000, 2000], [np.nan, 3000]])
        self.assertEqual(got.record["layout"], "wide, the service's parser")

    def test_long_reports_pivot_to_one_value_per_run_and_group(self):
        rows = [("HC1_Tcell_1", "P1", "CD3E", 1000.0), ("HC1_Tcell_1", "P1", "CD3E", 1000.0),
                ("HC1_Tcell_2", "P1", "CD3E", 2000.0), ("HC1_Tcell_2", "P2", "PTPRC", 3000.0)]
        layouts = {"Spectronaut report": ["R.FileName", "PG.ProteinGroups", "PG.Genes", "PG.Quantity"],
                   "DIA-NN report": ["Run", "Protein.Group", "Genes", "PG.MaxLFQ"]}
        for layout, columns in layouts.items():
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "SEARCH_T.xlsx"
                pd.DataFrame(rows, columns=columns).to_excel(path, index=False)
                got = intake.read_table(path)
                self.assertEqual(got.record["layout"], layout)
                self.assertEqual(got.genes, ["CD3E", "PTPRC"])
                self.assertEqual(got.samples, ["HC1_Tcell_1", "HC1_Tcell_2"])
                np.testing.assert_allclose(got.values, [[1000, 2000], [np.nan, 3000]])

    def test_an_unknown_layout_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SEARCH_B.xlsx"
            pd.DataFrame({"note": ["see the paper"], "other": ["text"]}).to_excel(path, index=False)
            with self.assertRaisesRegex(SystemExit, "no sheet holds per-run protein quantities"):
                intake.read_table(path)


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.tables = {
            "T": table(["CD3E", "PTPRC", "ACTB", "ACTB", "XYZ_NOT_A_GENE"], ["HC1_Tcell_1", "HC1_Tcell_2"],
                       [[100, 200], [400, 800], [256, 1024], [1024, np.nan], [64, 64]]),
            "B": table(["CD19", "PTPRC", "ACTB"], ["HC1_Bcell_1"], [[512], [128], [4096]]),
        }
        self.labels, _ = intake.label_rows(self.tables)

    def test_the_intersection_keeps_the_genes_both_searches_report(self):
        uploads, record = intake.build_uploads(self.tables, self.labels)
        self.assertEqual(uploads["intersection"].gene_names, ["PTPRC", "ACTB"])
        self.assertEqual(uploads["union"].gene_names, ["CD3E", "PTPRC", "ACTB", "XYZ_NOT_A_GENE", "CD19"])
        self.assertEqual((record["genes_in_both"], record["genes_in_either"]), (2, 5))

    def test_each_gene_is_one_row_with_values_from_each_cells_own_table(self):
        uploads, _ = intake.build_uploads(self.tables, self.labels)
        got = uploads["intersection"]
        self.assertEqual(got.cell_ids, ["HC1_Tcell_1", "HC1_Tcell_2", "HC1_Bcell_1"])
        np.testing.assert_allclose(got.values[0], np.log2([400, 800, 128]))
        # ACTB's two T-table rows merge by per-cell median of the log values
        np.testing.assert_allclose(got.values[1], [np.median(np.log2([256, 1024])), np.log2(1024), np.log2(4096)])
        self.assertTrue(np.isfinite(got.values).all())

    def test_a_gene_one_search_reports_is_missing_only_where_that_search_is_silent(self):
        uploads, _ = intake.build_uploads(self.tables, self.labels)
        union = uploads["union"]
        cd19 = union.values[union.gene_names.index("CD19")]
        self.assertTrue(np.isnan(cd19[:2]).all())
        self.assertAlmostEqual(float(cd19[2]), float(np.log2(512)), places=5)

    def test_tables_on_different_scales_are_refused(self):
        tables = dict(self.tables, B=table(["CD19", "PTPRC", "ACTB"], ["HC1_Bcell_1"], [[-1.0], [0.5], [2.0]]))
        with self.assertRaisesRegex(SystemExit, "different scales"):
            intake.build_uploads(tables, self.labels)


class ScoreRuleTests(unittest.TestCase):
    def test_an_answer_names_the_sorted_lineage(self):
        h = score.hierarchy()
        self.assertTrue(score.in_group("b cell", "class", "B", h))
        self.assertTrue(score.in_group("plasma cell", "class", "B", h))
        self.assertTrue(score.in_group("mature nk t cell", "class", "T", h))
        self.assertFalse(score.in_group("natural killer cell", "class", "T", h))
        self.assertTrue(score.in_group("T cell", "group", "T", h))
        self.assertFalse(score.in_group("T cell", "group", "B", h))
        self.assertTrue(score.in_group("lymphoid", "lineage", "B", h))
        self.assertFalse(score.in_group("", "class", "B", h))

    def test_balanced_accuracy_weighs_the_lineages_equally(self):
        right = np.array([True, True, False, True])
        groups = np.array(["B", "B", "T", "T"])
        self.assertEqual(score.balanced(right, groups), 75.0)

    def test_the_auroc_is_void_without_both_lineages(self):
        self.assertTrue(score.auroc(np.array([0.1, 0.2]), np.array(["B", "B"]))["void"])


class GuardTests(unittest.TestCase):
    def test_the_receipt_comes_first_and_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, receipt = Path(tmp) / "deposit", Path(tmp) / "receipt.json"
            folder.mkdir()
            for name in intake.FILES.values():
                (folder / name).write_bytes(b"x")
            with mock.patch.object(intake, "out_dir", return_value=Path(tmp) / "out"), \
                    mock.patch.object(intake, "FOLDER", folder), mock.patch.object(intake, "RECEIPT", receipt), \
                    mock.patch.object(intake, "REPO", Path(tmp)):
                with self.assertRaisesRegex(SystemExit, "no receipt"):
                    intake.main(["--labels"])
                with contextlib.redirect_stdout(io.StringIO()):
                    intake.main(["--receive"])
                with self.assertRaisesRegex(SystemExit, "received once"):
                    intake.main(["--receive"])
                record = json.loads(receipt.read_text(encoding="utf-8"))
                self.assertEqual(set(record["files"]), set(intake.FILES.values()))
                (folder / intake.FILES["T"]).write_bytes(b"changed")
                with self.assertRaisesRegex(SystemExit, "differs from the receipt"):
                    intake.main(["--labels"])

    def test_the_intake_needs_a_label_map_and_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(intake, "out_dir", return_value=Path(tmp)):
            with self.assertRaisesRegex(SystemExit, "no label map"):
                intake.main([])
            (Path(tmp) / "intake.json").write_text("{}")
            with self.assertRaisesRegex(SystemExit, "runs once"):
                intake.main([])

    def test_the_label_map_is_built_once(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(intake, "out_dir", return_value=Path(tmp)):
            (Path(tmp) / "label_map.csv").write_text("cell_id\n")
            with self.assertRaisesRegex(SystemExit, "built once"):
                intake.main(["--labels"])

    def test_the_scoring_refuses_to_run_twice(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(score, "tables_dir", return_value=Path(tmp)):
            (Path(tmp) / "summary.json").write_text("{}")
            with self.assertRaisesRegex(SystemExit, "scored once"):
                score.main([])


if __name__ == "__main__":
    unittest.main()
