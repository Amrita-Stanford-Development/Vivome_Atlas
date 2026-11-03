"""The method end to end: gates, statistics, class scores, answer set."""
from __future__ import annotations

import unittest

import numpy as np

from valuescale import method, score
from valuescale import statistics as st


def _linear(genes=400, cells=40, seed=0):
    rng = np.random.default_rng(seed)
    values = np.exp2(rng.normal(18, 2.5, size=(genes, 1)) + rng.normal(0, 0.6, size=(genes, cells)))
    values[rng.random(values.shape) < 0.3] = np.nan
    return values


def _model():
    rows = []
    for i in range(16):
        x = _linear(seed=i)
        rows.append(score.DesignRow(st.features(x), "linear", f"d{i}", "S1"))
        rows.append(score.DesignRow(st.features(np.log2(x)), "log", f"d{i}", "S1"))
    model = score.fit(rows)
    d = score.design_scores(model)
    return model, {label: min(v) for label, v in d.items()}


class MethodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.thresholds = _model()

    def test_a_linear_table(self):
        a = method.assess(_linear(seed=99), self.model, self.thresholds)
        self.assertEqual(a["verdict"], "linear")
        self.assertEqual(a["set"], ["linear"])
        self.assertIsNone(a["gate"])

    def test_a_log_table(self):
        a = method.assess(np.log2(_linear(seed=98)) + 5, self.model, self.thresholds)
        self.assertEqual(a["verdict"], "log")

    def test_a_gate_decides_without_scores(self):
        a = method.assess(np.random.default_rng(0).normal(size=(300, 30)), self.model, self.thresholds)
        self.assertEqual((a["gate"], a["verdict"]), ("negatives", "log"))
        self.assertIsNone(a["scores"])

    def test_too_few_columns_is_cant_tell(self):
        a = method.assess(_linear(cells=12), self.model, self.thresholds)
        self.assertEqual(a["verdict"], "cant_tell")
        self.assertEqual(a["reason"], "too few columns")

    def test_no_spread_is_unlike_either(self):
        presence = np.where(np.isnan(_linear()), 0.0, 1.0)
        a = method.assess(presence, self.model, self.thresholds)
        self.assertEqual(a["verdict"], "unlike_either")
        self.assertEqual(a["reason"], "no spread")

    def test_every_answer_carries_a_reason_unless_one_class_fits(self):
        a = method.assess(_linear(seed=97), self.model, self.thresholds)
        self.assertIsNone(a["reason"])
        far = method.assess(_linear(seed=96) ** 0.05, self.model, self.thresholds)
        if far["verdict"] in ("cant_tell", "unlike_either"):
            self.assertTrue(far["reason"])


if __name__ == "__main__":
    unittest.main()
