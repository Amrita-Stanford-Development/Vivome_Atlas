"""The class scores: since protocol amendment 5, a class's score is the
classifier's probability of it; the typicality distance and its design rank
are still computed, for the reply's warning. Fitted on design rows grouped
by deposit."""
from __future__ import annotations

import json
import math
import unittest

import numpy as np

from valuescale import score
from valuescale import statistics as st


def _rows(seed=0, per_class=40, deposits=10):
    """Design rows: linear and log feature vectors from two Gaussians."""
    rng = np.random.default_rng(seed)
    centre = {"linear": dict(bowley=0.4, moors=1.8, tail=4.0, level_spread=0.8, missing_share=0.4,
                             row_median_spread=8.0, cell_bowley_iqr=0.1, decades=3.0, column_sum_cv=0.4),
              "log": dict(bowley=0.0, moors=1.25, tail=1.7, level_spread=0.0, missing_share=0.4,
                          row_median_spread=3.0, cell_bowley_iqr=0.1, decades=0.3, column_sum_cv=0.1)}
    rows = []
    for label, c in centre.items():
        for i in range(per_class):
            f = {k: v + rng.normal(0, 0.05 * max(abs(v), 0.2)) for k, v in c.items()}
            rows.append(score.DesignRow(features=f, label=label, deposit=f"d{i % deposits}", stratum="S1"))
    return rows, centre


class ScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.centre = _rows()
        cls.model = score.fit(cls.rows)

    def test_a_typical_row_scores_high_for_its_class_only(self):
        s = score.class_scores(self.centre["linear"], self.model)
        self.assertGreater(s["linear"], 0.3)
        self.assertLess(s["log"], 0.05)
        s = score.class_scores(self.centre["log"], self.model)
        self.assertGreater(s["log"], 0.3)
        self.assertLess(s["linear"], 0.05)

    def test_a_row_like_neither_is_atypical_for_both(self):
        far = {k: v * 5 + 3 for k, v in self.centre["log"].items()}
        parts = score.class_parts(far, self.model)
        self.assertEqual(parts["linear"]["typicality"], 0.0)
        self.assertEqual(parts["log"]["typicality"], 0.0)

    def test_the_two_scores_add_up_to_one(self):
        for f in (self.centre["linear"], self.centre["log"], {k: v * 5 + 3 for k, v in self.centre["log"].items()}):
            s = score.class_scores(f, self.model)
            self.assertAlmostEqual(s["linear"] + s["log"], 1.0, places=12)

    def test_a_missing_feature_is_allowed(self):
        f = dict(self.centre["linear"], level_spread=math.nan)
        s = score.class_scores(f, self.model)
        self.assertGreater(s["linear"], 0.3)

    def test_linear_only_features_do_not_touch_the_log_score(self):
        a = score.class_parts(self.centre["log"], self.model)
        b = score.class_parts(dict(self.centre["log"], decades=9.0, column_sum_cv=5.0), self.model)
        self.assertEqual(a["log"], b["log"])
        self.assertNotEqual(a["linear"]["distance"], b["linear"]["distance"])
        self.assertEqual(a["linear"]["probability"], b["linear"]["probability"])

    def test_the_score_is_the_probability_alone(self):
        # protocol amendment 5: typicality warns, it never enters the score
        far = {k: v * 5 + 3 for k, v in self.centre["log"].items()}
        for f in (self.centre["linear"], far):
            parts = score.class_parts(f, self.model)
            scores = score.class_scores(f, self.model)
            for y in ("linear", "log"):
                self.assertEqual(scores[y], parts[y]["probability"])

    def test_design_scores_are_the_design_rows_own_probabilities(self):
        d = score.design_scores(self.model)
        for y in ("linear", "log"):
            self.assertEqual(d[y], self.model.reference[y]["discriminative"])

    def test_design_scores_leave_the_deposit_out(self):
        rows = list(self.rows)
        twin = rows[0]
        rows.append(score.DesignRow(features=dict(twin.features), label=twin.label, deposit=twin.deposit, stratum="S1"))
        model = score.fit(rows)
        # the twin shares row 0's deposit, so neither is the other's neighbour:
        # both see the same rows, at the same distances
        ref = model.reference["linear"]["typicality"]
        self.assertEqual(ref[0], ref[-1])
        self.assertGreater(ref[-1], 0.0)

    def test_design_scores_lie_in_0_1(self):
        d = score.design_scores(self.model)
        for label in ("linear", "log"):
            self.assertEqual(len(d[label]), 40)
            self.assertTrue(all(0.0 <= v <= 1.0 for v in d[label]))

    def test_round_trip_through_json(self):
        again = score.Model.from_json(json.loads(json.dumps(self.model.to_json())))
        for f in (self.centre["linear"], self.centre["log"]):
            self.assertEqual(score.class_scores(f, self.model), score.class_scores(f, again))

    def test_feature_sets(self):
        self.assertEqual(set(score.CLASS_FEATURES["log"]), set(st.CORE + st.BOTH))
        self.assertEqual(set(score.CLASS_FEATURES["linear"]), set(st.FEATURES))
        self.assertEqual(set(score.SHARED_FEATURES), set(st.CORE + st.BOTH))


if __name__ == "__main__":
    unittest.main()
