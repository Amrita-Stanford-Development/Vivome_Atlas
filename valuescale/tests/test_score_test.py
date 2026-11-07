"""The sealed test's one scoring (valuescale/corpus/score_test.py; protocol
"Scoring (once)" and amendment 5): the outcomes, their counts and exact
intervals, the pooled stratum's one-per-deposit rule, the paired test
against median-50, and the refusal of a second run. The rehearsal on the
calibration split never marks the test as scored."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from valuescale import calibrated, conformal, score
from valuescale import statistics as st
from valuescale.corpus import score_test


def _linear(genes=300, cells=40, seed=0):
    rng = np.random.default_rng(seed)
    values = np.exp2(rng.normal(18, 2.5, size=(genes, 1)) + rng.normal(0, 0.6, size=(genes, cells)))
    values[rng.random(values.shape) < 0.3] = np.nan
    return values


def _calibration():
    rows = []
    for i in range(12):
        x = _linear(seed=i)
        rows.append(score.DesignRow(st.features(x), "linear", f"d{i}", "S1"))
        rows.append(score.DesignRow(st.features(np.log2(x)), "log", f"d{i}", "S1"))
    t = {"linear": 0.5, "log": 0.5}
    strata = (calibrated.Stratum("S1", (20, 49), ("S1",), t, {"linear": 70, "log": 70}, {"linear": 1, "log": 1}),
              calibrated.Stratum("S2+S3", (50, 2000), ("S2", "S3"), t, {"linear": 70, "log": 70}, {"linear": 1, "log": 1}))
    return calibrated.Calibration("test-v0", 0.05, 0.05, score.fit(rows), strata, "0" * 64)


class OutcomeTests(unittest.TestCase):
    def test_the_five_outcomes(self):
        self.assertEqual(score_test.outcome(("linear",), "linear"), "right")
        self.assertEqual(score_test.outcome(("log",), "linear"), "wrong")
        self.assertEqual(score_test.outcome(("linear", "log"), "log"), "cant_tell")
        self.assertEqual(score_test.outcome((), "log"), "unlike_either")
        self.assertTrue(score_test.is_miss("wrong") and score_test.is_miss("unlike_either"))
        self.assertFalse(score_test.is_miss("cant_tell") or score_test.is_miss("right"))

    def test_a_tally_adds_up_with_exact_intervals(self):
        t = score_test.tally(["right"] * 60 + ["wrong"] * 2 + ["cant_tell"] * 5 + ["unlike_either"])
        self.assertEqual(t["n"], 68)
        self.assertEqual(sum(t["counts"].values()), 68)
        self.assertEqual(t["miss"], 3)
        self.assertEqual(t["rates"]["miss"]["interval"], list(conformal.clopper_pearson(3, 68)))
        self.assertEqual(t["miss_lower"], conformal.clopper_pearson_lower(3, 68))
        self.assertFalse(t["guarantee_contradicted"])
        bad = score_test.tally(["wrong"] * 20 + ["right"] * 48)
        self.assertTrue(bad["guarantee_contradicted"])

    def test_a_deposit_misses_in_a_pooled_stratum_when_either_subsample_misses(self):
        self.assertEqual(score_test.deposit_outcome(["right", "unlike_either"]), "unlike_either")
        self.assertEqual(score_test.deposit_outcome(["cant_tell", "right"]), "cant_tell")
        self.assertEqual(score_test.deposit_outcome(["right", "right"]), "right")


class McNemarTests(unittest.TestCase):
    def test_the_exact_one_sided_paired_test(self):
        # detector right where median-50 is wrong on 9 tables, the reverse on 1
        p = score_test.mcnemar_one_sided(9, 1)
        self.assertAlmostEqual(p, 11 / 1024, places=12)  # P(X >= 9), X ~ Binomial(10, 1/2)
        self.assertEqual(score_test.mcnemar_one_sided(0, 0), 1.0)


class InstrumentTests(unittest.TestCase):
    def test_families(self):
        f = score_test.instrument_family
        self.assertEqual(f("Q Exactive HF"), "Orbitrap")
        self.assertEqual(f("Orbitrap Astral"), "Orbitrap")
        self.assertEqual(f("timsTOF Pro 2"), "timsTOF")
        self.assertEqual(f("TripleTOF 6600"), "SCIEX TOF")
        self.assertEqual(f("ZenoTOF 7600"), "SCIEX TOF")
        self.assertEqual(f(""), "not stated")
        self.assertEqual(f("Synapt G2-Si"), "other")


class SplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = _calibration()
        cls.tables = {f"PXD{i}": _linear(cells=30 if i % 2 else 70, seed=200 + i) for i in range(6)}
        cls.records = [{"accession": a, "columns": v.shape[1], "rows": v.shape[0], "label": "linear",
                        "software": "DIA-NN" if i % 2 else "MaxQuant", "split": "calibration", "outcome": "kept"}
                       for i, (a, v) in enumerate(cls.tables.items())]
        cls.result = score_test.score_split(cls.records, lambda r: cls.tables[r["accession"]], cls.cal,
                                            instrument_of={"PXD0": "Q Exactive"}, foreign=True)

    def test_every_deposit_is_counted_once_per_class_and_calibrated_stratum(self):
        by = self.result["by_calibrated_stratum"]
        self.assertEqual(by["S1"]["linear"]["n"], 6)
        self.assertEqual(by["S2+S3"]["linear"]["n"], 3)
        self.assertEqual(by["S1"]["constructed_log"]["n"], 6)

    def test_the_primary_comparison_pairs_each_linear_table(self):
        p = self.result["primary"]
        self.assertEqual(p["tables"], 6)
        self.assertEqual(p["detector_wrong"] + p["detector_right"], 6)
        self.assertIn("p_value", p)

    def test_every_baseline_reads_every_table(self):
        from valuescale import baselines
        for name in baselines.BASELINES:
            b = self.result["baselines"][name]["linear"]
            self.assertEqual(b["wrong"] + b["right"] + b["no_answer"], 6, name)

    def test_foreign_tables_and_groupings_are_reported(self):
        self.assertEqual(set(self.result["foreign"]), {"zscore_proteins", "presence", "percentile_ranks"})
        self.assertIn("MaxQuant", self.result["by_software"])
        self.assertIn("Orbitrap", self.result["by_instrument"])
        self.assertIn("not stated", self.result["by_instrument"])


class OnceTests(unittest.TestCase):
    def test_a_second_scoring_is_refused_and_a_rehearsal_writes_no_mark(self):
        with tempfile.TemporaryDirectory() as d:
            mark = Path(d) / "test_scored.json"
            score_test.check_not_scored(mark)  # nothing yet
            score_test.mark_scored(mark, {"calibration_sha256": "x"})
            self.assertTrue(json.loads(mark.read_text())["scored"])
            with self.assertRaisesRegex(SystemExit, "once"):
                score_test.check_not_scored(mark)

    def test_the_rehearsal_reads_only_the_calibration_split(self):
        records = [{"accession": "A", "split": "calibration"}, {"accession": "B", "split": "test"}]
        self.assertEqual([r["accession"] for r in score_test.split_records(records, "calibration")], ["A"])
        self.assertEqual([r["accession"] for r in score_test.split_records(records, "test")], ["B"])


if __name__ == "__main__":
    unittest.main()
