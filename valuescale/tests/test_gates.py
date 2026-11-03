"""The gates decide a table by definition, before any statistic: a real share
of negatives means it is already transformed, non-negative integers mean
counts. What they clean up (stray negatives, ties at a cell's minimum) is
made missing, in a way unchanged by both nuisances."""
from __future__ import annotations

import unittest

import numpy as np

from valuescale import gates


def _lognormal(genes=300, cells=40, seed=0):
    rng = np.random.default_rng(seed)
    return np.exp2(rng.normal(20, 2.5, size=(genes, 1)) + rng.normal(0, 0.5, size=(genes, cells)))


class NegativesTests(unittest.TestCase):
    def test_a_real_share_of_negatives_means_log(self):
        centred = np.random.default_rng(1).normal(0, 1, size=(200, 30))
        result = gates.gate(centred)
        self.assertEqual(result.gate, "negatives")
        self.assertEqual(result.reading, "log")
        self.assertGreater(result.negative_share, 0.4)

    def test_the_bar_is_one_percent_of_observed_values(self):
        x = _lognormal(genes=100, cells=20)  # 2,000 values
        at_bar = x.copy()
        at_bar.ravel()[:20] = -1.0  # exactly 1%
        self.assertEqual(gates.gate(at_bar).gate, "negatives")
        below = x.copy()
        below.ravel()[:19] = -1.0
        self.assertIsNone(gates.gate(below).gate)

    def test_missing_values_do_not_count_toward_the_share(self):
        x = _lognormal(genes=100, cells=20)
        x[:50] = np.nan  # 1,000 observed values left
        x.ravel()[-15:] = -1.0  # 1.5% of observed
        self.assertEqual(gates.gate(x).gate, "negatives")

    def test_stray_negatives_are_made_missing(self):
        x = _lognormal()
        where = (np.array([0, 5, 9]), np.array([1, 2, 3]))
        x[where] = -2.0
        result = gates.gate(x)
        self.assertIsNone(result.gate)
        self.assertEqual(result.stray_negatives, 3)
        self.assertTrue(np.isnan(result.values[where]).all())


class CountsTests(unittest.TestCase):
    def test_integers_with_20_distinct_values_mean_counts(self):
        counts = np.random.default_rng(2).poisson(8, size=(300, 30)).astype(float)
        result = gates.gate(counts)
        self.assertEqual(result.gate, "counts")
        self.assertEqual(result.reading, "linear")

    def test_fewer_than_20_distinct_integers_are_not_counts(self):
        few = np.random.default_rng(3).integers(0, 10, size=(300, 30)).astype(float)
        self.assertIsNone(gates.gate(few).gate)

    def test_one_fractional_value_is_not_counts(self):
        counts = np.random.default_rng(2).poisson(8, size=(300, 30)).astype(float)
        counts[0, 0] = 3.5
        self.assertIsNone(gates.gate(counts).gate)


class CleanUpTests(unittest.TestCase):
    def test_non_finite_values_are_missing(self):
        x = _lognormal()
        x[0, 0], x[1, 1] = np.inf, -np.inf
        result = gates.gate(x)
        self.assertEqual(result.non_finite, 2)
        self.assertTrue(np.isnan(result.values[0, 0]) and np.isnan(result.values[1, 1]))

    def test_ties_at_a_cells_minimum_are_made_missing(self):
        x = _lognormal(cells=4)
        x[:3, 0] = 0.0  # three zeros: "not detected"
        x[0, 1] = x[:, 1].min() / 2  # a single minimum, not tied
        result = gates.gate(x)
        self.assertTrue(np.isnan(result.values[:3, 0]).all())
        self.assertEqual(result.values[0, 1], x[0, 1])
        self.assertEqual(result.min_ties, 3)

    def test_clean_up_is_unchanged_by_scale_and_shift(self):
        x = _lognormal()
        x[np.random.default_rng(4).random(x.shape) < 0.3] = 0.0
        masks = [np.isnan(gates.gate(v).values) for v in (x, x * 1e3, np.log2(x + 1) * 0.5 + 10)]
        for mask in masks[1:]:
            np.testing.assert_array_equal(mask, masks[0])

    def test_the_input_is_not_changed(self):
        x = _lognormal()
        x[0, 0] = 0.0
        x[1, 0] = 0.0
        before = x.copy()
        gates.gate(x)
        np.testing.assert_array_equal(x, before)


if __name__ == "__main__":
    unittest.main()
