"""valuescale.detect and valuescale.apply, the frozen calibration they read
(valuescale/calibrated.py) and the report they return (valuescale/report.py).

The tests build their own small calibration from synthetic design rows, so
they do not depend on protein-v1.json's numbers."""
from __future__ import annotations

import json
import math
import unittest

import numpy as np

import valuescale
from valuescale import calibrated, method, report, score
from valuescale import statistics as st


def _linear(genes=400, cells=40, seed=0):
    rng = np.random.default_rng(seed)
    values = np.exp2(rng.normal(18, 2.5, size=(genes, 1)) + rng.normal(0, 0.6, size=(genes, cells)))
    values[rng.random(values.shape) < 0.3] = np.nan
    return values


def _calibration() -> calibrated.Calibration:
    rows = []
    for i in range(16):
        x = _linear(seed=i)
        rows.append(score.DesignRow(st.features(x), "linear", f"d{i}", "S1"))
        rows.append(score.DesignRow(st.features(np.log2(x)), "log", f"d{i}", "S1"))
    model = score.fit(rows)
    thresholds = {"linear": 0.5, "log": 0.5}
    strata = (calibrated.Stratum("S1", (20, 49), ("S1",), thresholds, {"linear": 218, "log": 218}, {"linear": 6, "log": 6}),
              calibrated.Stratum("S2+S3", (50, 2000), ("S2", "S3"), thresholds, {"linear": 68, "log": 68},
                                 {"linear": 1, "log": 1}))
    return calibrated.Calibration("test-v0", 0.05, 0.05, model, strata, "0" * 64)


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.cal = _calibration()

    def test_a_table_finds_its_stratum_by_its_columns(self):
        self.assertIsNone(self.cal.stratum_for(19))
        self.assertEqual(self.cal.stratum_for(20).name, "S1")
        self.assertEqual(self.cal.stratum_for(49).name, "S1")
        self.assertEqual(self.cal.stratum_for(50).name, "S2+S3")
        self.assertEqual(self.cal.stratum_for(2000).name, "S2+S3")
        self.assertIsNone(self.cal.stratum_for(2001))

    def test_round_trip_through_json(self):
        again = calibrated.from_json(json.loads(json.dumps(self.cal.to_json())))
        self.assertEqual(again.id, self.cal.id)
        self.assertEqual(again.strata, self.cal.strata)
        x = _linear(seed=50)
        self.assertEqual(valuescale.detect(x, self.cal).to_json(), valuescale.detect(x, again).to_json())


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.cal = _calibration()

    def test_a_linear_table(self):
        r = valuescale.detect(_linear(seed=60), self.cal)
        self.assertEqual((r.verdict, r.reading, r.set, r.stratum), ("linear", "linear", ("linear",), "S1"))
        self.assertEqual(r.calibration, "test-v0")
        self.assertIn("218", r.guarantee)
        self.assertAlmostEqual(r.probabilities["linear"] + r.probabilities["log"], 1.0, places=12)

    def test_a_log_table(self):
        r = valuescale.detect(np.log2(_linear(seed=61, cells=80)), self.cal)
        self.assertEqual((r.verdict, r.reading, r.stratum), ("log", "log", "S2+S3"))
        self.assertIn("68", r.guarantee)

    def test_cant_tell_and_unlike_either_are_read_linear(self):
        # B1: the cheaper reading when the detector cannot decide
        self.assertEqual(report.UNDECIDED_READING, "linear")
        x = _linear(seed=62)
        full = np.where(np.isnan(x), np.nanmedian(x), x)
        r = valuescale.detect(np.log2(full), self.cal)
        self.assertEqual((r.verdict, r.reading, r.reason), ("cant_tell", "linear", method.NO_GAPS_REASON))

    def test_a_gate_decides_with_the_guarantee_of_its_stratum(self):
        r = valuescale.detect(np.random.default_rng(0).normal(size=(300, 30)), self.cal)
        self.assertEqual((r.gate, r.verdict, r.reading), ("negatives", "log", "log"))
        self.assertIsNotNone(r.guarantee)
        self.assertIsNone(r.probabilities)

    def test_too_few_columns_has_no_guarantee(self):
        r = valuescale.detect(_linear(cells=12), self.cal)
        self.assertEqual((r.verdict, r.stratum, r.guarantee), ("cant_tell", None, None))

    def test_more_columns_than_calibrated_use_the_widest_stratum_without_a_guarantee(self):
        r = valuescale.detect(_linear(genes=300, cells=2100, seed=63), self.cal)
        self.assertEqual(r.verdict, "linear")
        self.assertEqual(r.stratum, "S2+S3")
        self.assertIsNone(r.guarantee)
        self.assertIn("2,000", r.notes[0])

    def test_the_report_is_plain_json(self):
        r = valuescale.detect(_linear(seed=64), self.cal).to_json()
        text = json.dumps(r, allow_nan=False)
        self.assertEqual(json.loads(text)["verdict"], "linear")
        self.assertEqual(set(r), {"verdict", "reading", "set", "stratum", "columns", "rows", "gate", "reason", "warning",
                                  "probabilities", "thresholds", "typicality", "statistics", "calibration", "guarantee",
                                  "notes"})

    def test_a_matrix_must_have_two_dimensions(self):
        with self.assertRaises(ValueError):
            valuescale.detect(np.ones(30), self.cal)


class ApplyTests(unittest.TestCase):
    """apply mirrors the projection service's reading of a protein table
    (service/pipeline/alignment.py apply_reading; a test in service/tests
    keeps the two in step)."""

    def test_a_linear_reading_takes_log2_with_zeros_missing(self):
        x = np.array([[0.0, 2.0], [8.0, np.nan]])
        out = valuescale.apply(x, "linear")
        self.assertTrue(math.isnan(out[0, 0]) and math.isnan(out[1, 1]))
        self.assertEqual((out[0, 1], out[1, 0]), (1.0, 3.0))

    def test_a_log_reading_keeps_the_values_unless_zeros_are_missing(self):
        x = np.array([[0.0, 2.0], [8.0, np.nan]])
        np.testing.assert_array_equal(valuescale.apply(x, "log"), x)
        out = valuescale.apply(x, "log", zeros="missing")
        self.assertTrue(math.isnan(out[0, 0]))
        self.assertEqual(out[0, 1], 2.0)

    def test_a_linear_reading_of_a_negative_is_refused(self):
        with self.assertRaisesRegex(ValueError, "negative"):
            valuescale.apply(np.array([[1.0, -2.0]]), "linear")

    def test_an_unknown_reading_is_refused(self):
        with self.assertRaises(ValueError):
            valuescale.apply(np.ones((2, 2)), "raw")

    def test_the_input_is_not_changed(self):
        x = np.array([[0.0, 2.0], [8.0, 1.0]])
        before = x.copy()
        valuescale.apply(x, "linear")
        valuescale.apply(x, "log", zeros="missing")
        np.testing.assert_array_equal(x, before)


if __name__ == "__main__":
    unittest.main()
