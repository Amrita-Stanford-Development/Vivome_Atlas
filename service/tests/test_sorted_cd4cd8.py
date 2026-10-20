"""benchmark/sorted_cd4cd8_intake.py and sorted_cd4cd8_score.py: the scripts of
research/benchmark/protocol-sorted-cd4cd8.md agree with the protocol, and the
scorer's guards hold. The full rehearsal on Fulcher is their end-to-end check
(both scripts' --rehearse)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from benchmark import sorted_cd4cd8_intake as intake
from benchmark import sorted_cd4cd8_score as score

PROTOCOL = Path(__file__).resolve().parents[2] / "research" / "benchmark" / "protocol-sorted-cd4cd8.md"


class ProtocolAgreementTests(unittest.TestCase):
    def test_every_frozen_sha256_is_the_protocols(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for version, files in intake.FROZEN.items():
            for rel, sha in files.items():
                with self.subTest(version=version, file=rel):
                    self.assertIn(sha, text)

    def test_the_frozen_files_still_have_those_hashes(self):
        found = intake.check_frozen()
        for files in intake.FROZEN.values():
            for rel, sha in files.items():
                self.assertEqual(found[rel], sha)

    def test_the_class_mapping_is_rule_5s(self):
        self.assertEqual(score.COARSE["regulatory t cell"], "CD4T")
        self.assertEqual(score.COARSE["cd8-positive, alpha-beta t cell"], "CD8T")
        self.assertEqual(score.COARSE["plasma cell"], "B")
        self.assertNotIn("mature nk t cell", score.COARSE)


class ScoringRuleTests(unittest.TestCase):
    def test_a_type_not_sorted_counts_as_other(self):
        pred = np.array(["natural killer cell", "cd8-positive, alpha-beta t cell", "neutrophil"])
        self.assertEqual(score.to_type(pred, ("CD4T", "CD8T")).tolist(), ["other", "CD8T", "other"])

    def test_scores_are_balanced_accuracy_over_the_sorted_types(self):
        truth = np.array(["CD4T", "CD4T", "CD8T", "CD8T"])
        pred = np.array(["cd4-positive, alpha-beta t cell"] * 3 + ["cd8-positive, alpha-beta t cell"])
        row = score.scores(pred, truth, ("CD4T", "CD8T"))
        self.assertAlmostEqual(row["balanced_accuracy_pct"], 75.0)
        self.assertAlmostEqual(row["recall_CD8T_pct"], 50.0)


class GuardTests(unittest.TestCase):
    def test_a_labels_file_with_another_sha256_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            path.write_text("cell_id,type,unit\nc1,CD4T,single\n")
            with self.assertRaises(SystemExit):
                score.load_labels(False, path, "0" * 64)

    def test_the_real_scoring_refuses_to_run_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "summary.json").write_text("{}")
            with mock.patch.object(score, "tables_dir", return_value=Path(tmp)), \
                    mock.patch.dict("os.environ", {}, clear=False):
                with self.assertRaisesRegex(SystemExit, "scored once"):
                    score.main(["--unseal", str(Path(tmp) / "labels.csv"), "--sha256", "0" * 64])


if __name__ == "__main__":
    unittest.main()


class ReviewGuardTests(unittest.TestCase):
    """A review of the scripts against the protocol (2026-10-21), before any data."""

    def test_a_dataset_needs_50_single_cells_each_of_cd4_and_cd8_t(self):
        types = np.array(["CD4T"] * 60 + ["CD8T"] * 10 + ["B"] * 60)
        ok, counts = score.qualifies(types)
        self.assertFalse(ok)
        self.assertEqual(counts, {"CD4T": 60, "CD8T": 10})
        self.assertTrue(score.qualifies(np.array(["CD4T"] * 50 + ["CD8T"] * 50))[0])
        self.assertFalse(score.qualifies(np.array(["CD4T"] * 80))[0])

    def test_the_caveats_are_the_protocols_and_donors_are_counted(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for caveat in score.CAVEATS:
            self.assertIn(caveat.split(":")[0], text)
        import pandas as pd
        labels = pd.DataFrame({"type": ["CD4T", "CD4T", "CD8T", "B"], "unit": ["single"] * 4, "donor": ["d1", "d2", "d1", "d1"]})
        single = np.array([True, True, True, False])
        self.assertEqual(score.donor_counts(labels, single), {"all": 2, "CD4T": 2, "CD8T": 1})
        self.assertEqual(score.donor_counts(labels.drop(columns="donor"), single), "not given in the labels file")

    def test_markers_are_found_by_the_uploaded_identifiers(self):
        from service.pipeline import alignment
        raw = alignment.RawMatrix(gene_names=["CD8A;CD8B", "P10966", "CD4", "PTPRC"], cell_ids=["c1", "c2", "c3"],
                                  values=np.array([[1000.0, 0.0, 2000.0], [500.0, 600.0, 0.0], [0.0, 0.0, 900.0],
                                                   [100.0, 100.0, 100.0]], np.float32))
        facts = intake.marker_facts(raw)
        self.assertEqual(facts["CD8B"]["rows"], 2)
        self.assertEqual(facts["CD8A"]["rows"], 1)
        self.assertEqual(facts["CD4"]["rows"], 1)
        # in a linear upload 0 is "not detected"
        self.assertAlmostEqual(facts["CD4"]["cells_observed_pct"], 33.33, places=2)
