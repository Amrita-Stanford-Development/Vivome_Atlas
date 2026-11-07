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

    def test_a_per_protein_normalised_table_is_cant_tell(self):
        x = _linear(seed=95)
        a = method.assess(x / np.nanmedian(x, axis=1, keepdims=True), self.model, self.thresholds)
        self.assertEqual(a["verdict"], "cant_tell")
        self.assertEqual(a["reason"], method.PER_PROTEIN_REASON)

    def test_every_answer_carries_a_reason_unless_one_class_fits(self):
        a = method.assess(_linear(seed=97), self.model, self.thresholds)
        self.assertIsNone(a["reason"])
        far = method.assess(_linear(seed=96) ** 0.05, self.model, self.thresholds)
        if far["verdict"] in ("cant_tell", "unlike_either"):
            self.assertTrue(far["reason"])

    def test_a_table_with_no_missing_value_is_cant_tell(self):
        # protocol amendment 5: it may have been filled in (imputed)
        x = _linear(seed=94)
        full = np.where(np.isnan(x), np.nanmedian(x), x)
        a = method.assess(np.log2(full), self.model, self.thresholds)
        self.assertEqual((a["gate"], a["verdict"]), (None, "cant_tell"))
        self.assertEqual(a["reason"], method.NO_GAPS_REASON)
        self.assertEqual(a["set"], ["linear", "log"])

    def test_the_gates_come_before_the_no_gaps_rule(self):
        counts = np.random.default_rng(3).integers(1, 400, size=(300, 30)).astype(float)
        self.assertEqual(method.assess(counts, self.model, self.thresholds)["gate"], "counts")

    def test_the_score_is_the_probability_and_the_set_follows_it(self):
        a = method.assess(_linear(seed=93), self.model, self.thresholds)
        for y in ("linear", "log"):
            self.assertEqual(a["scores"][y], a["parts"][y]["probability"])
            self.assertEqual(y in a["set"], a["scores"][y] >= self.thresholds[y])

    def test_cant_tell_and_unlike_either_name_the_probabilities(self):
        x = _linear(seed=92)
        low = method.assess(x, self.model, {"linear": 0.0, "log": 0.0})
        self.assertEqual(low["verdict"], "cant_tell")
        self.assertIn("linear probability", low["reason"])
        high = method.assess(x, self.model, {"linear": 1.01, "log": 1.01})
        self.assertEqual(high["verdict"], "unlike_either")
        self.assertIn("log probability", high["reason"])

    def test_a_table_unlike_the_design_rows_is_warned_but_its_set_is_kept(self):
        x = _linear(seed=91)
        x[:, ::2] *= 1e4  # wildly uneven columns: far from every design row
        a = method.assess(x, self.model, self.thresholds)
        self.assertEqual([a["parts"][y]["typicality"] for y in ("linear", "log")], [0.0, 0.0])
        self.assertEqual(a["warning"], method.UNLIKE_DESIGN_WARNING)
        self.assertEqual(a["set"], [y for y in ("linear", "log") if a["scores"][y] >= self.thresholds[y]])
        self.assertIsNone(method.assess(_linear(seed=90), self.model, self.thresholds)["warning"])

    def test_calibration_scores_a_table_a_gate_decides(self):
        counts = np.random.default_rng(3).integers(1, 400, size=(300, 30)).astype(float)
        parts = method.calibration_parts(counts, self.model)
        self.assertIsNotNone(parts)
        self.assertAlmostEqual(parts["linear"]["probability"] + parts["log"]["probability"], 1.0, places=12)
        centred = np.random.default_rng(1).normal(0, 1, size=(300, 30))
        self.assertIsNotNone(method.calibration_parts(centred, self.model))

    def test_calibration_parts_are_none_without_per_cell_statistics(self):
        presence = np.where(np.isnan(_linear()), 0.0, 1.0)
        self.assertIsNone(method.calibration_parts(presence, self.model))


if __name__ == "__main__":
    unittest.main()
