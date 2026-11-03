"""The statistics: shape properties that tell a linear table from a log one,
each unchanged by the nuisance of the class it is used for (linear:
x -> c*x; log: x -> a + c*x)."""
from __future__ import annotations

import math
import unittest

import numpy as np

from valuescale import statistics as st


def _linear(genes=400, cells=60, seed=0, missing=0.2):
    """Log-normal proteins with multiplicative noise, some values missing."""
    rng = np.random.default_rng(seed)
    log2 = rng.normal(18, 2.5, size=(genes, 1)) + rng.normal(0, 0.6, size=(genes, cells))
    values = np.exp2(log2)
    values[rng.random(values.shape) < missing] = np.nan
    return values


class SeparationTests(unittest.TestCase):
    def test_core_features_tell_a_linear_table_from_its_log(self):
        lin = st.features(_linear())
        log = st.features(np.log2(_linear()))
        self.assertGreater(lin["bowley"], 0.2)
        self.assertLess(abs(log["bowley"]), 0.1)
        self.assertGreater(lin["moors"], log["moors"])
        self.assertGreater(lin["tail"], log["tail"])
        self.assertGreater(lin["level_spread"], 0.7)
        self.assertLess(log["level_spread"], 0.3)
        self.assertGreater(lin["decades"], 1.5)


class InvarianceTests(unittest.TestCase):
    def assert_same(self, a, b, names):
        for name in names:
            if math.isnan(a[name]):
                self.assertTrue(math.isnan(b[name]), name)
            else:
                self.assertAlmostEqual(a[name], b[name], delta=1e-9, msg=name)

    def test_every_feature_is_unchanged_by_scale(self):
        x = _linear()
        base = st.features(x)
        for c in (1e-6, 1e-3, 1e3):
            self.assert_same(base, st.features(x * c), st.FEATURES)

    def test_log_features_are_unchanged_by_base_and_offset(self):
        log2 = np.log2(_linear())
        base = st.features(log2)
        for made in (log2 * math.log10(2), log2 * math.log(2), log2 + 10, log2 * 0.5, log2 - np.nanmin(log2)):
            self.assert_same(base, st.features(made), st.CORE + st.BOTH)


class DetailTests(unittest.TestCase):
    def test_symmetric_values_have_no_skew(self):
        cell = np.arange(1.0, 102.0)
        stats = st.per_cell(np.column_stack([cell] * 6))
        np.testing.assert_allclose(stats["bowley"], 0.0, atol=1e-12)

    def test_decades_is_log10_of_q95_over_q05(self):
        cell = np.logspace(0, 4, 201)  # 1 to 10,000, evenly spaced in log
        stats = st.per_cell(np.column_stack([cell] * 6))
        expected = math.log10(np.quantile(cell, 0.95) / np.quantile(cell, 0.05))
        np.testing.assert_allclose(stats["decades"], expected, rtol=1e-12)

    def test_few_cells_leave_per_cell_features_missing(self):
        f = st.features(_linear(cells=4))
        self.assertTrue(math.isnan(f["bowley"]))
        self.assertTrue(math.isnan(f["cell_bowley_iqr"]))
        self.assertFalse(math.isnan(f["missing_share"]))

    def test_cells_with_too_few_values_are_skipped(self):
        x = _linear(genes=400, cells=10)
        x[15:, 0] = np.nan  # 15 values left in cell 0
        stats = st.per_cell(x)
        self.assertTrue(math.isnan(stats["bowley"][0]))
        self.assertFalse(math.isnan(stats["bowley"][1]))

    def test_level_spread_is_off_on_per_protein_normalised_tables(self):
        x = _linear()
        normalised = x / np.nanmedian(x, axis=1, keepdims=True)
        f = st.features(normalised)
        self.assertLess(f["row_median_spread"], st.ROW_NORMALISED_BAR)
        self.assertTrue(math.isnan(f["level_spread"]))

    def test_a_protein_missing_in_more_than_half_the_cells_has_no_level(self):
        x = _linear(genes=50, cells=20, missing=0.0)
        x[0, :11] = np.nan
        level, spread = st.protein_level_spread(x)
        self.assertFalse(np.isfinite(level[0]))
        self.assertTrue(np.isfinite(level[1:]).all())

    def test_the_protein_draw_depends_only_on_the_missing_pattern(self):
        x = _linear(genes=3000)
        self.assertEqual(st.pattern_seed(x), st.pattern_seed(x * 7.5 + 3))
        y = x.copy()
        y[0, 0] = np.nan if not np.isnan(y[0, 0]) else 1.0
        self.assertNotEqual(st.pattern_seed(x), st.pattern_seed(y))

    def test_column_sum_spread(self):
        x = _linear(missing=0.0)
        same_sums = x / np.nansum(x, axis=0, keepdims=True)
        self.assertLess(st.features(same_sums)["column_sum_cv"], 1e-12)
        self.assertGreater(st.features(x)["column_sum_cv"], 0.0)

    def test_missing_share_counts_every_missing_entry(self):
        x = _linear(missing=0.0)
        x[:100, :] = np.nan
        self.assertAlmostEqual(st.features(x)["missing_share"], 100 / 400)


if __name__ == "__main__":
    unittest.main()
