"""Figures 2 and 3 (scripts/figures/fig2_transfer.py, fig3_answers.py): the
numbers each draws are the ones in its sources, re-read here. Standard
library only, so it runs on any Python."""
import csv
import gzip
import json
import unittest

from figures import common, fig2_transfer as fig2, fig3_answers as fig3


def read(rel):
    return json.loads((common.REPO / rel).read_text(encoding="utf-8"))


def value(rows, panel, label, series=""):
    found = [r["value"] for r in rows if r["panel"] == panel and r["label"] == label and r["series"] == series]
    if len(found) != 1:
        raise AssertionError(f"{len(found)} rows for {panel}/{series}/{label}")
    return found[0]


class TransferFigureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = fig2.data()

    def test_recall_by_type_is_the_development_record_and_khourys(self):
        dev = read(fig2.DEVELOPMENT)["fulcher2026"]["v4.1"]
        khoury = read(fig2.KHOURY)["scores"]["v4.1"]
        for key, label in fig2.TYPES:
            self.assertEqual(value(self.rows, "a", label, "Fulcher 2026"), dev[f"recall_{key}"])
        self.assertEqual(value(self.rows, "a", "CD8 T", "Khoury 2026"), khoury["recall_CD8T_pct"])
        self.assertEqual(value(self.rows, "a", "Monocyte", "Khoury 2026"), khoury["recall_monocyte_pct"])
        self.assertFalse([r for r in self.rows if r["series"] == "Khoury 2026" and r["label"] == "Dendritic cell"],
                         "Khoury does not label dendritic cells")
        self.assertEqual(value(self.rows, "a", fig2.BALANCED, "Fulcher 2026"), dev["balanced_accuracy_6_types"])
        self.assertEqual(value(self.rows, "a", fig2.BALANCED, "Khoury 2026"), khoury["balanced_accuracy_pct"])

    def test_lineage_recall_is_what_the_page_cites(self):
        with open(common.REPO / fig2.FULCHER, encoding="utf-8", newline="") as handle:
            served = next(r for r in csv.DictReader(handle) if r["tool"] == "v4.1 (served)")
        self.assertEqual(value(self.rows, "b", "Lymphoid", "Fulcher 2026"), float(served["lymphoid_recall_pct"]))
        self.assertEqual(value(self.rows, "b", "Myeloid", "Khoury 2026"),
                         read(fig2.KHOURY)["scores"]["v4.1"]["myeloid_recall_pct"])
        self.assertEqual(value(self.rows, "b", "Myeloid", "PBMC240"),
                         read(fig2.DEVELOPMENT)["pbmc240"]["v4.1"]["myeloid_recall"])

    def test_the_probe_and_its_chance_level(self):
        probe = read(fig2.PROBE)
        self.assertEqual(value(self.rows, "c", "protein or RNA"), probe["modality_probe_balanced_accuracy_pct"])
        self.assertEqual(value(self.rows, "c", fig2.CHANCE), 50.0)
        self.assertIn("RNA subsampled to protein n", probe["basis"], "the chance level assumes balanced classes")


class AnswersFigureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = fig3.data()

    def test_answer_levels_and_cells_by_kind_are_the_suites(self):
        summary = read(fig3.SUMMARY)
        for key, label in fig3.KINDS:
            record = summary["by_scenario"]["v4.1"][key]
            for level, name in fig3.LEVELS:
                self.assertEqual(value(self.rows, "a", label, name), record["levels"][level])
            self.assertEqual(value(self.rows, "a", label, fig3.CELLS_SERIES), record["cells"])
            total = sum(value(self.rows, "a", label, name) for _, name in fig3.LEVELS)
            self.assertAlmostEqual(total, 100, delta=0.05, msg=f"{label}: the levels make up every cell")
        self.assertEqual(value(self.rows, "a", fig3.ALL, "A branch"), summary["result"]["v4.1"]["levels"]["lineage"])

    def test_the_per_cell_table_is_the_one_summary_was_computed_from(self):
        summary = read(fig3.SUMMARY)["result"]["v4.1"]
        with gzip.open(common.REPO / fig3.CELLS, "rt", encoding="utf-8", newline="") as handle:
            cells = [c for c in csv.DictReader(handle) if c["method"] == "v4.1"]
        self.assertEqual(len(cells), summary["cells"])
        self.assertEqual(round(100 * sum(c["covered"] == "True" for c in cells) / len(cells), 2), summary["coverage"])

    def test_coverage_by_type_on_protein_and_on_rna(self):
        coverage = read(fig3.COVERAGE)
        fulcher = coverage["v41"]["fulcher2026"]["by_class"]
        for key, label in fig3.FULCHER_TYPES:
            self.assertEqual(value(self.rows, "b", f"Fulcher 2026: {label}", "Protein"), fulcher[key]["coverage_pct"])
        self.assertEqual(value(self.rows, "b", "SCoPE2: All cells", "Protein"), coverage["v41"]["scope2"]["coverage_pct"])
        self.assertEqual(value(self.rows, "b", fig3.TARGET), coverage["target_pct"])
        self.assertEqual(value(self.rows, "b", "Fulcher 2026: All cells", "RNA"),
                         read(fig3.SUMMARY)["result"]["v4.1"]["coverage"])
        self.assertEqual(fig3.coarse()["plasma cell"], "B")
        self.assertFalse([r for r in self.rows if r["label"] == "Fulcher 2026: Dendritic cell" and r["series"] == "RNA"],
                         "no dendritic cell in the simulated suite")
        cells = fig3.rna_coverage()
        n, hit = cells["cd8-positive, alpha-beta t cell"]
        self.assertEqual(value(self.rows, "b", "Fulcher 2026: CD8 T", "RNA"), round(100 * hit / n, 2))


if __name__ == "__main__":
    unittest.main()
