"""benchmark/heldout_formats.py, heldout_intake.py and heldout_score.py: the
readers read their documented layouts, the label rules follow
research/benchmark/protocol-heldout.md, the statistics are right, and the
guards hold. No held-out file is opened here; each script's --rehearse is its
end-to-end check."""
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from benchmark import heldout_formats as formats
from benchmark import heldout_intake as intake
from benchmark import heldout_score as score
from benchmark import sorted_cd4cd8_intake as sorted_intake

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "research" / "benchmark" / "protocol-heldout.md"


class ProtocolAgreementTests(unittest.TestCase):
    def test_every_frozen_sha256_is_in_the_protocol(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for files in sorted_intake.FROZEN.values():
            for sha in files.values():
                self.assertIn(sha, text)

    def test_the_candidates_are_the_protocols(self):
        self.assertEqual(intake.MODELS, {"v31": "v3.1", "v41": "v4.1", "v42": "v4.2", "v52": "v5.2"})
        self.assertEqual(score.MODELS[score.HEADLINE], "v4.1")

    def test_every_input_is_a_held_out_download(self):
        record = json.loads(intake.DOWNLOADS.read_text(encoding="utf-8"))
        for name, files in intake.INPUTS.items():
            for rel in files:
                with self.subTest(file=rel):
                    self.assertIn(rel.split("/")[0], intake.SEALED_DIRS)
                    self.assertEqual(record[rel]["role"], "held_out")

    def test_no_rehearsal_reads_a_held_out_path(self):
        for name, rehearse in intake.REHEARSALS.items():
            source = inspect.getsource(rehearse)
            for word in ("INPUTS", "real_", "PUBLIC /") + intake.SEALED_DIRS:
                self.assertNotIn(word, source, f"{name}'s rehearsal mentions {word}")
        for path in (intake.RIECKMANN, intake.DS18_ZOOM):
            self.assertFalse(any(d in path.parts for d in intake.SEALED_DIRS))


class MaxQuantReaderTests(unittest.TestCase):
    def write(self, tmp, columns, rows, name="proteinGroups.txt"):
        path = Path(tmp) / name
        df = pd.DataFrame(rows, columns=columns)
        if name.endswith(".xlsx"):
            df.to_excel(path, index=False)
        else:
            df.to_csv(path, sep="\t", index=False)
        return path

    def test_flags_genes_and_lfq(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, ["Gene names", "Reverse", "Potential contaminant", "Only identified by site",
                                    "LFQ intensity S1", "LFQ intensity S2", "Intensity S1", "Intensity S2"],
                              [["ACTB;ACTG1", "", "", "", 100.0, 0.0, 5, 5],
                               ["CD3E", "+", "", "", 50.0, 60.0, 5, 5],
                               ["CD4", "", "+", "", 50.0, 60.0, 5, 5],
                               ["", "", "", "", 1.0, 1.0, 5, 5],
                               ["CD8A", "", "", "", 7.0, 8.0, 5, 5]])
            t = formats.read_maxquant(path)
        self.assertEqual(t.genes, ["ACTB", "CD8A"])
        self.assertEqual(t.samples, ["S1", "S2"])
        self.assertEqual(t.record["quantity"], "LFQ intensity")
        self.assertTrue(np.isnan(t.values[0, 1]))
        self.assertEqual(t.values[1].tolist(), [7.0, 8.0])

    def test_r_spelling_and_the_intensity_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, ["Gene.names", "Reverse", "LFQ.intensity.CD4_P1", "Intensity.CD4_P1"],
                              [["ACTB", "", 0.0, 9.0], ["CD2", "", 0.0, 3.0]])
            t = formats.read_maxquant(path)
        self.assertEqual(t.record["quantity"], "Intensity")
        self.assertEqual(t.samples, ["CD4_P1"])
        self.assertEqual(t.values[:, 0].tolist(), [9.0, 3.0])

    def test_xlsx(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, ["Gene names", "LFQ intensity CD8_naive_P2"], [["CD8A", 12.0]], "groups.xlsx")
            t = formats.read_maxquant(path)
        self.assertEqual((t.genes, t.samples, t.values.tolist()), (["CD8A"], ["CD8_naive_P2"], [[12.0]]))


class ProteomeDiscovererReaderTests(unittest.TestCase):
    def test_filters_normalised_abundances_and_file_names(self):
        df = pd.DataFrame({"Master": ["IsMasterProtein", "IsMasterProtein", "IsMasterProteinCandidate", "IsMasterProtein"],
                           "Protein FDR Confidence: Combined": ["High", "Low", "High", "High"],
                           "Contaminant": [False, False, False, True],
                           "Description": ["x GN=ACTB PE=1", "x GN=CD3E PE=1", "x GN=CD4 PE=1", "x GN=KRT1 PE=1"],
                           "Abundance: F1: Sample": [1.0, 2.0, 3.0, 4.0], "Abundance: F2: Sample": [5.0, 6.0, 7.0, 8.0],
                           "Abundances (Normalized): F1: Sample": [10.0, 20.0, 30.0, 40.0],
                           "Abundances (Normalized): F2: Sample": [0.0, 60.0, 70.0, 80.0]})
        files = pd.DataFrame({"File ID": ["F1", "F2"], "File Name": [r"D:\x\SC_Jurkat_01.raw", r"D:\x\SC_HeLa_01.raw"]})
        with tempfile.TemporaryDirectory() as tmp:
            df.to_csv(Path(tmp) / "p.txt", sep="\t", index=False)
            files.to_csv(Path(tmp) / "f.txt", sep="\t", index=False)
            t = formats.read_proteome_discoverer(Path(tmp) / "p.txt", Path(tmp) / "f.txt")
        self.assertEqual(t.genes, ["ACTB"])
        self.assertEqual(t.samples, ["SC_Jurkat_01", "SC_HeLa_01"])
        self.assertEqual(t.values[0, 0], 10.0)
        self.assertTrue(np.isnan(t.values[0, 1]))
        self.assertEqual(t.record["gene_from"], "GN= in Description")

    def test_an_unnamed_file_number_is_refused(self):
        df = pd.DataFrame({"Gene Symbol": ["ACTB"], "Abundance: F3: Sample": [1.0]})
        with tempfile.TemporaryDirectory() as tmp:
            df.to_csv(Path(tmp) / "p.txt", sep="\t", index=False)
            pd.DataFrame({"File ID": ["F1"], "File Name": ["a.raw"]}).to_csv(Path(tmp) / "f.txt", sep="\t", index=False)
            with self.assertRaises(ValueError):
                formats.read_proteome_discoverer(Path(tmp) / "p.txt", Path(tmp) / "f.txt")


class SageReaderTests(unittest.TestCase):
    def test_ratios_to_the_runs_cells_median_over_psms_and_the_q_filter(self):
        rows = []
        for file, values in (("run1.mzML", (1.0, 3.0)), ("run2.mzML", (5.0, 5.0))):
            for offset in (2.0, 8.0):
                rows.append({"filename": file, "proteins": "sp|P60709|ACTB_HUMAN", "spectrum_q": 0.001,
                             "peptide_q": 0.001, "protein_q": 0.001, "tmt_1": 1e6,
                             "tmt_2": 2 ** (values[0] + offset), "tmt_3": 2 ** (values[1] + offset), "tmt_4": 0.0})
        rows.append({**rows[0], "spectrum_q": 0.5, "tmt_2": 1e9})
        with tempfile.TemporaryDirectory() as tmp:
            pd.DataFrame(rows).to_csv(Path(tmp) / "q.tsv", sep="\t", index=False)
            t = formats.read_sage_tmt(Path(tmp) / "q.tsv", {("run1", 2): "a", ("run1", 3): "b", ("run2", 2): "c",
                                                            ("run2", 3): "d"})
        self.assertEqual(t.samples, ["a", "b", "c", "d"])
        self.assertEqual(t.record["psms_kept"], 4)
        want = [1 - np.log2((2 + 8) / 2), 3 - np.log2((2 + 8) / 2), 0.0, 0.0]
        np.testing.assert_allclose(t.values[0], want, atol=1e-9)

    def test_symbols_come_from_the_service_map_else_the_entry_name(self):
        self.assertEqual(formats.protein_symbols(pd.Series(["sp|P60709|ACTB_HUMAN", "sp|Q00000|MADEUP_HUMAN"])),
                         ["ACTB", "MADEUP"])


class LabelRuleTests(unittest.TestCase):
    def test_tian_names(self):
        self.assertEqual(intake.tian_parse("CD8_TEMRA_P3"), {"lineage": "CD8", "state": "EMRA", "patient": "P3"})
        self.assertEqual(intake.tian_parse("CD3+CD4+ naive MM2"), {"lineage": "CD4", "state": "naive", "patient": "P2"})
        self.assertEqual(intake.tian_parse("CD3 patient 5")["lineage"], "CD3")
        self.assertEqual(intake.tian_parse("CD45RA_x")["lineage"], "")
        self.assertEqual(intake.tian_parse("CD4_TCM_1")["state"], "CM")
        rows, unparsed = intake.tian_label_rows("f", ["CD4_N_P1", "CD8_N_P1", "CD3_P1", "blank"])
        self.assertEqual(unparsed, ["blank"])
        self.assertEqual([(r["group"], r["scored"]) for r in rows], [("CD4", True), ("CD8", True), ("CD3", False)])

    def test_b_t_and_cell_lines(self):
        self.assertEqual([intake.b_or_t(s) for s in ("Bcell_145_1", "CD19_2", "T_cell_3", "CD3_4", "HeLa_150", "B_vs_T")],
                         ["B", "B", "T", "T", "", ""])
        self.assertEqual([intake.cell_line(s) for s in ("x_Jurkat_01", "x_HeLa_02", "blank")], ["Jurkat", "HeLa", ""])

    def test_gates(self):
        self.assertEqual([intake.gate(s) for s in ("CD45+ CD74+", "CD45-/CD200+", "CD45+/CD200+", "CD74+")],
                         ["immune", "keratinocyte", "double", ""])

    def test_tmt_channels_and_samples(self):
        self.assertEqual([intake.tmt_channel(c) for c in ("126", "127N", "TMT16", "tmt_3", "134N")], [1, 2, 16, 3, 16])
        with self.assertRaises(ValueError):
            intake.tmt_channel("135N")
        self.assertEqual(intake.tmt_sample("THP1", "PMA"), ("THP-1", "PMA"))
        self.assertEqual(intake.tmt_sample("U937", "untreated"), ("U-937", "untreated"))
        self.assertEqual(intake.tmt_sample("Mix THP1 U937", ""), ("", ""))
        self.assertEqual(intake.tmt_sample("Carrier", ""), ("", ""))
        rows, info = intake.tmt_label_rows(pd.DataFrame({"File.Name": ["r1.raw", "r1.raw", "r1.raw"],
                                                         "Channel": ["126", "128C", "129N"],
                                                         "SampleType": ["Carrier", "THP1", "U937"],
                                                         "Treatment": ["", "PMA", "none"]}))
        self.assertEqual([(r["cell_id"], r["line"], r["group"]) for r in rows],
                         [("r1_tmt5", "THP-1", "PMA"), ("r1_tmt6", "U-937", "untreated")])
        self.assertEqual(info["excluded_by_type"], {"Carrier": 1})

    def test_the_gate_table_is_found_and_ungated_runs_left_out(self):
        sheet = pd.DataFrame({"Cell": ["a.raw", "b.raw", "c.raw"], "Sort": ["CD45+ CD74+", "CD45- CD200+", "?"]})
        labels, info = intake.gate_label_rows(["a", "b", "c", "bulk1"], {"S1": sheet}, {})
        self.assertEqual(labels[["cell_id", "group", "scored"]].values.tolist(),
                         [["a", "immune", True], ["b", "keratinocyte", True]])
        self.assertEqual(info["runs_without_gate"], ["bulk1", "c"])


class StatisticsTests(unittest.TestCase):
    def test_sign_test(self):
        self.assertAlmostEqual(score.sign_test(9, 10), 0.0107421875)

    def test_auroc_and_its_permutation_p(self):
        auc, p = score.auroc_with_p(np.array([3.0, 4.0, 1.0, 2.0]), np.array([True, True, False, False]), 999)
        self.assertEqual(auc, 1.0)
        self.assertLess(p, 0.25)
        auc, _ = score.auroc_with_p(np.array([1.0, 1.0, 1.0, 1.0]), np.array([True, True, False, False]), 9)
        self.assertEqual(auc, 0.5)

    def test_pairs_average_replicates(self):
        labels = pd.DataFrame({"upload": "f", "patient": ["P1"] * 4 + ["P2"] * 2, "state": "naive",
                               "group": ["CD4", "CD4", "CD8", "CD8", "CD4", "CD8"], "scored": True})
        pairs, won = score.tian_pairs(labels, np.array([0.0, 0.4, 0.1, 0.5, 0.5, 0.1]))
        self.assertEqual([p["won"] for p in pairs], [True, False])
        self.assertEqual(won, 1)


class GuardTests(unittest.TestCase):
    def test_the_real_intake_needs_a_label_map_and_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(intake, "out_dir", return_value=Path(tmp)):
            with self.assertRaisesRegex(SystemExit, "no label map"):
                intake.main(["tian"])
            (Path(tmp) / "intake.json").write_text("{}")
            with self.assertRaisesRegex(SystemExit, "runs once"):
                intake.main(["tian"])

    def test_the_label_map_is_built_once(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(intake, "out_dir", return_value=Path(tmp)):
            (Path(tmp) / "label_map.csv").write_text("cell_id\n")
            with self.assertRaisesRegex(SystemExit, "built once"):
                intake.main(["pxd043355", "--labels"])

    def test_the_real_scoring_refuses_to_run_twice(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(score, "tables_dir", return_value=Path(tmp)):
            (Path(tmp) / "summary.json").write_text("{}")
            with self.assertRaisesRegex(SystemExit, "scored once"):
                score.main(["pxd073250"])


if __name__ == "__main__":
    unittest.main()
