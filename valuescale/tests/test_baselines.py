"""The baselines: the "already log?" rules other tools use, each hit branch
by branch with small hand-made tables, every threshold just above and just
below, the ported quirks included. Missing values are left out of every
statistic (a ruling, in the plan's ledger), and the registry names its rules in order,
each with commit-pinned sources."""
from __future__ import annotations

import math
import re
import unittest

import numpy as np

from valuescale import baselines as b

NAMES = ("geo2r", "expressanalyst", "scgpt", "omics_playground", "proteopy", "gemma", "celltypist",
         "cibersort", "median_50")
# The rules whose statistics pool the observed values (CellTypist pools its
# first 1000 cells, so any table of up to 1000 columns).
POOLED = ("geo2r", "expressanalyst", "scgpt", "proteopy", "celltypist", "cibersort", "median_50")


def m(*rows) -> np.ndarray:
    return np.array(rows, dtype=np.float64)


def _protein(genes=400, cells=40, seed=0, missing=0.3) -> np.ndarray:
    """Log-normal intensities around 2^18, some values missing."""
    rng = np.random.default_rng(seed)
    values = np.exp2(rng.normal(18, 2.5, size=(genes, 1)) + rng.normal(0, 0.5, size=(genes, cells)))
    values[rng.random(values.shape) < missing] = np.nan
    return values


class Geo2rTests(unittest.TestCase):
    def test_q99_above_100_means_linear(self):
        self.assertEqual(b.geo2r(np.full((10, 4), 100.5)), "linear")
        self.assertEqual(b.geo2r(np.full((10, 4), 100.0)), "log")  # strict: 100 is not above 100

    def test_a_range_above_50_with_q25_above_0_means_linear(self):
        x = np.ones(100)
        x[-1] = 52.0  # range 51; q99 = 0.99 * 1 + 0.01 * 52 = 1.51
        self.assertEqual(b.geo2r(x.reshape(20, 5)), "linear")
        x[-1] = 51.0  # range 50, not above it
        self.assertEqual(b.geo2r(x.reshape(20, 5)), "log")

    def test_q25_at_or_below_0_blocks_the_range_clause(self):
        x = np.ones(100)
        x[-1] = 60.0
        x[:30] = 0.0  # q25 = 0
        self.assertEqual(b.geo2r(x.reshape(20, 5)), "log")
        x[:30] = 0.001
        self.assertEqual(b.geo2r(x.reshape(20, 5)), "linear")

    def test_the_old_third_clause_is_not_applied(self):
        ratios = np.linspace(0.5, 1.7, 100).reshape(20, 5)  # 0 < q25 < 1 and 1 < q75 < 2
        self.assertEqual(b.geo2r(ratios), "log")

    def test_quantiles_are_rs_type_7(self):
        self.assertAlmostEqual(b._r_quantile7(np.arange(1.0, 11.0), (0.99,))[0], 9.91, places=12)
        values = np.sort(np.random.default_rng(1).lognormal(10, 2, size=997))
        probs = (0.0, 0.25, 0.5, 0.75, 0.99, 1.0)
        np.testing.assert_allclose(b._r_quantile7(values, probs), np.quantile(values, probs), rtol=1e-12)

    def test_infinities_are_kept_as_r_keeps_them(self):
        x = np.full((10, 4), 2.0)
        x[0, 0] = np.inf  # q99 interpolates towards it: inf
        self.assertEqual(b.geo2r(x), "linear")

    def test_an_na_decision_is_no_answer(self):
        # q25 and q99 are (1 - h) * -inf + h * inf = NaN, so LogC is NA and the script stops
        self.assertIsNone(b.geo2r(m([-np.inf, np.inf])))


class CibersortTests(unittest.TestCase):
    def test_a_maximum_below_50_means_log(self):
        self.assertEqual(b.cibersort(m([1.0, 49.99], [0.0, -3.0])), "log")
        self.assertEqual(b.cibersort(m([1.0, 50.0], [0.0, -3.0])), "linear")  # strict

    def test_missing_values_do_not_stop_it(self):
        self.assertEqual(b.cibersort(m([np.nan, 40.0], [1.0, 2.0])), "log")

    def test_an_infinity_is_the_maximum(self):
        self.assertEqual(b.cibersort(m([np.inf, 1.0])), "linear")


class ExpressAnalystTests(unittest.TestCase):
    def setUp(self):
        self.counts = np.arange(100.0).reshape(20, 5)  # integers, max 99

    def test_integers_up_to_99_are_not_log(self):
        self.assertEqual(b.expressanalyst(self.counts), "linear")

    def test_a_single_negative_means_log(self):
        self.counts[0, 0] = -0.001
        self.assertEqual(b.expressanalyst(self.counts), "log")

    def test_a_negative_smaller_than_1e_10_was_set_to_0(self):
        self.counts[0, 0] = -1e-11  # sanitizeSmallNumbers
        self.assertEqual(b.expressanalyst(self.counts), "linear")
        self.counts[0, 0] = -1e-10  # not smaller than 1e-10
        self.assertEqual(b.expressanalyst(self.counts), "log")

    def test_more_than_half_non_integers_below_50_mean_log(self):
        six = m([0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.0, 7.0, 8.0, 9.0])
        five = m([0.5, 1.5, 2.5, 3.5, 4.5, 5.0, 6.0, 7.0, 8.0, 9.0])  # exactly half
        self.assertEqual(b.expressanalyst(six), "log")
        self.assertEqual(b.expressanalyst(five), "linear")

    def test_the_largest_absolute_value_must_be_below_50(self):
        x = np.arange(10.0).reshape(2, 5) * 4.5 + 0.25  # all non-integers, max 40.75
        self.assertEqual(b.expressanalyst(x), "log")
        x[0, 0] = 49.75
        self.assertEqual(b.expressanalyst(x), "log")
        x[0, 0] = 50.25
        self.assertEqual(b.expressanalyst(x), "linear")
        x[0, 0] = 50.0  # an integer, still not below 50
        self.assertEqual(b.expressanalyst(x), "linear")

    def test_the_integer_tolerance_is_1e_8(self):
        k = np.arange(1.0, 21.0).reshape(4, 5)
        self.assertEqual(b.expressanalyst(k + 5e-9), "linear")
        self.assertEqual(b.expressanalyst(k + 2e-8), "log")

    def test_zeros_are_integers(self):
        mostly_zero = m([0, 0, 0, 0, 0, 0, 1.5, 2.25, 0.75, 3.1])
        self.assertEqual(b.expressanalyst(mostly_zero), "linear")

    def test_non_finite_values_are_dropped(self):
        x = m([0.5, 1.5, 2.5], [3.5, 4.5, np.inf])
        self.assertEqual(b.expressanalyst(x), "log")


class OmicsPlaygroundTests(unittest.TestCase):
    def test_a_minimum_below_minus_1_means_log_unless_the_maximum_is_above_1000(self):
        self.assertEqual(b.omics_playground(m([-2.5, 10.5], [3.5, 100.5])), "log")
        self.assertEqual(b.omics_playground(m([-2.5, 10.5], [3.5, 1000.0])), "log")
        self.assertEqual(b.omics_playground(m([-2.5, 10.5], [3.5, 1000.5])), "linear")

    def test_small_negatives_and_a_maximum_below_60_mean_log(self):
        self.assertEqual(b.omics_playground(m([-0.5, 10.5], [3.5, 59.5])), "log")
        self.assertEqual(b.omics_playground(m([-1.0, 10.0], [3.0, 59.0])), "log")  # integers, but not all >= 0

    def test_a_minimum_of_minus_1_and_a_maximum_of_60_mean_linear(self):
        self.assertEqual(b.omics_playground(m([-1.0, 10.5], [3.5, 60.0])), "linear")

    def _ratio_rows(self, c):
        """Ten rows whose means alternate 10 (1 +/- c), two columns."""
        means = 10.0 * (1 + c * np.array([1, -1] * 5))
        return np.column_stack([means - 0.3, means + 0.3])

    def test_rows_with_near_constant_means_are_ratios(self):
        # CV = c * sqrt(10 / 9) with R's sd (n - 1): 0.00991 and 0.01012
        self.assertEqual(b.omics_playground(self._ratio_rows(0.0094)), "linear")
        self.assertEqual(b.omics_playground(self._ratio_rows(0.0096)), "log")

    def test_the_ratio_check_needs_two_columns(self):
        self.assertEqual(b.omics_playground(np.full((5, 2), 10.3)), "linear")
        self.assertEqual(b.omics_playground(np.full((5, 1), 10.3)), "log")

    def test_non_negative_integers_are_counts(self):
        counts = np.arange(40.0).reshape(10, 4)
        self.assertEqual(b.omics_playground(counts), "linear")
        counts[0, 0] = 0.5
        self.assertEqual(b.omics_playground(counts), "log")

    def test_the_integer_test_takes_the_signed_maximum(self):
        # every fractional part above .5: x - round(x) < 0 everywhere, so "all integer"
        self.assertEqual(b.omics_playground(m([2.7], [3.6], [10.9], [5.51])), "linear")
        self.assertEqual(b.omics_playground(m([2.3], [3.6], [10.9], [5.51])), "log")

    def test_an_all_zero_table_is_counts(self):
        self.assertEqual(b.omics_playground(np.zeros((5, 2))), "linear")  # is.ratio NA || is.counts TRUE

    def _sparse_cells(self, cells, zeros=6, missing=0):
        """Ten rows: `zeros` rows of 0, then `missing` rows of NaN, then
        rows of 1.5, 2.5, ... (not integers: 2.5 - round(2.5) = 0.5; row
        means far apart, so not ratios)."""
        x = np.empty((10, cells))
        x[:zeros] = 0.0
        x[zeros:zeros + missing] = np.nan
        x[zeros + missing:] = (np.arange(10 - zeros - missing) + 1.5)[:, None]
        return x

    def test_big_zero_inflated_tables_are_single_cell(self):
        self.assertEqual(b.omics_playground(self._sparse_cells(1001)), "linear")
        self.assertEqual(b.omics_playground(self._sparse_cells(1000)), "log")

    def test_missing_values_do_not_count_as_zeros(self):
        self.assertEqual(b.omics_playground(self._sparse_cells(1001, zeros=4, missing=3)), "linear")  # 4 of 7
        self.assertEqual(b.omics_playground(self._sparse_cells(1001, zeros=3, missing=4)), "log")  # 3 of 6

    def test_an_na_answer_is_no_answer(self):
        one_row = m([1.5, 2.5, 3.7])  # sd of one row mean is NA, so is.ratio is NA
        self.assertIsNone(b.omics_playground(one_row))
        self.assertEqual(b.omics_playground(m([1.5, 2.5, 63.7])), "linear")  # FALSE && NA is FALSE

    def test_a_sample_with_no_value_is_left_out(self):
        x = np.full((5, 2), np.nan)
        x[:, 0] = 10.3  # one sample: no ratio check
        self.assertEqual(b.omics_playground(x), "log")


class ScgptTests(unittest.TestCase):
    def test_a_maximum_above_30_means_not_logged(self):
        self.assertEqual(b.scgpt(m([0.5, 30.5])), "linear")
        self.assertEqual(b.scgpt(m([0.5, 30.0])), "log")

    def test_a_negative_means_not_logged(self):
        self.assertEqual(b.scgpt(m([-0.001, 0.5, 5.0])), "linear")
        self.assertEqual(b.scgpt(m([0.0, 0.5, 5.0])), "log")

    def test_a_smallest_positive_value_of_1_means_not_logged(self):
        self.assertEqual(b.scgpt(m([0.0, 1.0, 5.0])), "linear")
        self.assertEqual(b.scgpt(m([0.0, 0.999, 5.0])), "log")

    def test_no_positive_value_is_no_answer(self):
        self.assertIsNone(b.scgpt(np.zeros((3, 2))))  # the tool raises
        self.assertEqual(b.scgpt(m([-1.0, -2.0])), "linear")  # the minimum is tested first

    def test_missing_values_do_not_switch_the_tests_off(self):
        self.assertEqual(b.scgpt(m([np.nan, 31.0, 0.5])), "linear")


class CelltypistTests(unittest.TestCase):
    def test_the_range_is_0_to_9_22(self):
        self.assertEqual(b.celltypist(m([0.5, 9.22])), "log")
        self.assertEqual(b.celltypist(m([0.5, 9.2201])), "linear")
        self.assertEqual(b.celltypist(m([-0.01, 5.0])), "linear")
        self.assertEqual(b.celltypist(m([0.0, 5.0])), "log")

    def test_only_the_first_1000_cells_are_checked(self):
        x = np.full((3, 1001), 2.0)
        x[0, 1000] = 20.0
        self.assertEqual(b.celltypist(x), "log")
        x[0, 999] = 20.0
        self.assertEqual(b.celltypist(x), "linear")

    def test_a_cell_with_no_value_is_left_out_of_the_window(self):
        x = np.full((3, 1001), 2.0)
        x[0, 1000] = 20.0
        x[:, 0] = np.nan
        self.assertEqual(b.celltypist(x), "linear")

    def test_missing_values_do_not_switch_the_check_off(self):
        self.assertEqual(b.celltypist(m([np.nan, 5.0])), "log")
        self.assertEqual(b.celltypist(m([np.nan, 10.0])), "linear")


class ProteopyTests(unittest.TestCase):
    def test_half_a_percent_of_negatives_means_log(self):
        x = np.full(1000, 1000.0)
        x[:5] = -1.0  # 0.005
        self.assertEqual(b.proteopy(x.reshape(100, 10)), "log")
        x[4] = 1000.0  # 0.004
        self.assertEqual(b.proteopy(x.reshape(100, 10)), "linear")

    def test_a_95th_percentile_of_100_or_less_means_log(self):
        self.assertEqual(b.proteopy(np.full((10, 4), 100.0)), "log")
        self.assertEqual(b.proteopy(np.full((10, 4), 100.5)), "linear")

    def test_the_percentile_interpolates_linearly(self):
        x = np.zeros(20)
        x[-1] = 3000.0  # p95 = 0.05 * 3000 = 150
        self.assertEqual(b.proteopy(x.reshape(4, 5)), "linear")
        x[-1] = 1999.0  # 99.95
        self.assertEqual(b.proteopy(x.reshape(4, 5)), "log")

    def test_zeros_are_kept(self):
        x = np.zeros(100)
        x[-3:] = 5000.0
        self.assertEqual(b.proteopy(x.reshape(10, 10)), "log")
        x[x == 0] = np.nan
        self.assertEqual(b.proteopy(x.reshape(10, 10)), "linear")

    def test_non_finite_values_are_dropped(self):
        self.assertEqual(b.proteopy(m([np.inf, 50.0])), "log")
        self.assertIsNone(b.proteopy(m([np.inf, -np.inf])))  # no finite value: the tool raises


class GemmaTests(unittest.TestCase):
    def infer(self, x):
        return b._gemma_infer(np.asarray(x, dtype=np.float64))

    def test_zeros_and_ones_are_present_absent(self):
        self.assertEqual(self.infer(m([0, 1, 1], [1, 0, 1], [0, 0, 1], [1, 1, 0])), ("PRESENTABSENT", "OTHER"))
        self.assertEqual(self.infer(m([0, 1, 1], [1, 0, 1], [0, 0, 1])), ("AMOUNT", "PERCENT1"))  # 9 values: not counts
        self.assertIsNone(b.gemma(m([0, 1, 1], [1, 0, 1], [0, 0, 1], [1, 1, 0])))

    def test_values_within_0_and_1_are_percent1(self):
        self.assertEqual(self.infer(m([0.2, 0.5, 1.0], [0.0, 0.7, 0.3])), ("AMOUNT", "PERCENT1"))
        self.assertEqual(self.infer(m([0.2, 0.5, 1.0001], [0.0, 0.7, 0.3])), ("AMOUNT", "LOG10"))  # ratiometric
        self.assertIsNone(b.gemma(m([0.2, 0.5, 1.0], [0.0, 0.7, 0.3])))

    def test_ten_or_more_non_negative_integers_are_counts(self):
        counts = np.arange(2.0, 14.0).reshape(4, 3)
        self.assertEqual(self.infer(counts), ("COUNT", "COUNT"))
        self.assertEqual(b.gemma(counts), "linear")
        nine = np.arange(2.0, 11.0).reshape(3, 3)
        self.assertEqual(self.infer(nine), ("AMOUNT", "LOGBASEUNKNOWN"))  # max 10 < 11

    def test_missing_values_do_not_block_counts(self):
        counts = np.arange(2.0, 16.0).reshape(7, 2)
        counts[0, 0] = counts[3, 1] = np.nan  # 12 observed
        self.assertEqual(self.infer(counts), ("COUNT", "COUNT"))
        counts[1:6, 0] = np.nan  # 7 observed: too few
        self.assertNotEqual(self.infer(counts)[0], "COUNT")

    def test_rint_passes_an_infinity_as_a_count(self):
        counts = np.arange(2.0, 14.0).reshape(4, 3)
        counts[0, 0] = np.inf
        self.assertEqual(self.infer(counts), ("COUNT", "COUNT"))

    def test_a_maximum_close_to_100_within_0_and_100_is_percent(self):
        self.assertEqual(self.infer(m([0.5, 99.9995], [50.25, 12.5])), ("AMOUNT", "PERCENT"))
        self.assertEqual(self.infer(m([0.5, 99.99], [50.25, 12.5])), ("AMOUNT", "OTHER"))  # not close
        self.assertEqual(self.infer(m([0.5, 100.0005], [50.25, 12.5])), ("AMOUNT", "OTHER"))  # close, above 100
        self.assertIsNone(b.gemma(m([0.5, 99.9995], [50.25, 12.5])))

    def test_a_sample_with_zero_mean_is_a_z_score(self):
        self.assertEqual(self.infer(m([-1.0, 5.5], [1.0 + 1e-8, 7.25])), ("ZSCORE", "LOGBASEUNKNOWN"))
        self.assertEqual(self.infer(m([-1.0, 5.5], [1.0 + 4e-8, 7.25])), ("AMOUNT", "LOGBASEUNKNOWN"))
        self.assertEqual(self.infer(m([-1.0, 5.5], [1.0, 27.25])), ("ZSCORE", "OTHER"))
        self.assertEqual(b.gemma(m([-1.0, 5.5], [1.0, 27.25])), "log")  # no log is taken of a z-score

    def test_a_sample_at_least_half_zero_is_a_z_score(self):
        x = m([0.0, 5000.5], [0.0, 20.5], [3.5, 7.5])
        self.assertEqual(self.infer(x), ("ZSCORE", "OTHER"))
        self.assertEqual(b.gemma(x), "log")

    def _log2_counts(self):
        k = np.arange(1.0, 13.0)
        v = np.log(k) / np.log(2.0)
        return np.column_stack([v, v + 0.25])

    def test_a_first_sample_of_log_counts_is_log_counts(self):
        self.assertEqual(self.infer(self._log2_counts()), ("COUNT", "LOG2"))
        self.assertEqual(b.gemma(self._log2_counts()), "log")
        k = np.arange(1.0, 13.0)
        ln = np.log(k)
        self.assertEqual(self.infer(np.column_stack([ln, ln + 0.25])), ("COUNT", "LN"))
        log10 = np.log(k) / np.log(10.0)
        self.assertEqual(self.infer(np.column_stack([log10, log10 + 0.25])), ("COUNT", "LOG10"))

    def test_the_tolerance_1e_32_demands_exact_equality(self):
        x = self._log2_counts()
        x[5, 0] = np.nextafter(x[5, 0], np.inf)  # one value one ulp off
        self.assertEqual(self.infer(x), ("AMOUNT", "LOG10"))

    def test_only_the_first_sample_is_tested_for_log_counts(self):
        self.assertEqual(self.infer(self._log2_counts()[:, ::-1]), ("AMOUNT", "LOG10"))

    def test_log1p_counts_of_integers_are_reported_as_ln(self):
        # log1p(k) is ln(k + 1), the log of an integer, and LN is tested first
        v = np.log1p(np.arange(10.0))
        self.assertEqual(self.infer(np.column_stack([v, v + 0.25])), ("COUNT", "LN"))
        v = np.log1p(np.arange(9.0))  # nine distinct values: too few
        self.assertEqual(self.infer(np.column_stack([v, v + 0.25])), ("AMOUNT", "LOG10"))

    def test_the_log1p_test_is_one_sided(self):
        # abs() before the subtraction: a value passes whenever expm1(v) rounds down
        v = np.arange(12) * 0.03
        self.assertEqual(self.infer(np.column_stack([v, v + 1.5])), ("COUNT", "LOG1P"))
        v = np.log1p(np.r_[np.arange(11.0), 2.3])
        self.assertEqual(self.infer(np.column_stack([v, v + 0.25])), ("COUNT", "LOG1P"))
        v = np.log1p(np.r_[np.arange(11.0), 2.7])
        self.assertEqual(self.infer(np.column_stack([v, v + 0.25])), ("AMOUNT", "LOG2"))  # ratiometric

    def test_the_maximum_bounds(self):
        def table(top):  # sample means of 3: not ratiometric
            return m([3.3, 2.5, top], [2.7, 3.5, 2.1])
        for top, scale in ((4.80, "LOG10"), (4.81, "LOGBASEUNKNOWN"), (10.99, "LOGBASEUNKNOWN"), (11.0, "LOG2"),
                           (19.99, "LOG2"), (20.0, "OTHER")):
            self.assertEqual(self.infer(table(top)), ("AMOUNT", scale), top)

    def test_the_ratiometric_bounds(self):
        def table(top):  # every sample mean below 2 in size
            return m([0.5, -0.3, top], [1.2, 0.4, 1.0 - top])
        for top, scale in ((2.49, "LOG10"), (2.5, "LOG2"), (11.99, "LOG2"), (12.0, "LOGBASEUNKNOWN")):
            self.assertEqual(self.infer(table(top)), ("AMOUNT", scale), top)
        self.assertEqual(self.infer(m([0.5, -0.3, 3.0], [1.2, 0.4, 0.98])), ("AMOUNT", "LOG2"))  # mean 1.99
        self.assertEqual(self.infer(m([0.5, -0.3, 3.0], [1.2, 0.4, 1.0])), ("AMOUNT", "LOG10"))  # mean 2: not below 2

    def test_means_add_left_to_right_as_java_does(self):
        x = np.ones(16)
        x[0], x[8] = 1e16, -1e16  # left to right the seven 1s before -1e16 are lost; numpy's pairwise sum keeps them
        self.assertEqual(b._java_mean(x), 7 / 16)
        self.assertNotEqual(float(np.mean(x)), 7 / 16)

    def test_distinct_values_tell_0_from_minus_0(self):
        # Java's distinct() compares as Double.compare: -0.0 and 0.0 make 10 values here, not 9
        v = np.r_[-0.0, 0.0, np.log(np.arange(2.0, 10.0)) / np.log(2.0)]
        self.assertEqual(self.infer(np.column_stack([v, v + 0.25])), ("COUNT", "LOG2"))

    def test_negatives_above_the_bounds_are_log(self):
        x = m([25.5, 3.3], [-1.5, 4.7])
        self.assertEqual(self.infer(x), ("AMOUNT", "LOGBASEUNKNOWN"))
        self.assertEqual(b.gemma(x), "log")

    def test_linear_from_10_to_the_3_2(self):
        self.assertEqual(self.infer(m([1584.9, 3.3], [2.7, 4.7])), ("AMOUNT", "LINEAR"))
        self.assertEqual(b.gemma(m([1584.9, 3.3], [2.7, 4.7])), "linear")
        self.assertEqual(self.infer(m([1584.89, 3.3], [2.7, 4.7])), ("AMOUNT", "OTHER"))
        self.assertIsNone(b.gemma(m([1584.89, 3.3], [2.7, 4.7])))

    def test_a_z_score_in_the_log_space(self):
        x = m([1.0, 3000.5], [1.0, 2.5], [1.0, 7.5])  # ln of the first sample is all 0
        self.assertEqual(self.infer(x), ("ZSCORE", "LINEAR"))
        self.assertEqual(b.gemma(x), "log")  # Gemma converts only amounts and counts

    def test_a_sample_with_no_value_is_left_out(self):
        x = m([np.nan, 1584.9, 3.3], [np.nan, 2.7, 4.7])  # Colt's median of nothing is 0: a z-score
        self.assertEqual(self.infer(x), ("AMOUNT", "LINEAR"))
        k = np.arange(1.0, 13.0)
        v = np.log(k) / np.log(2.0)
        first_empty = np.column_stack([np.full(12, np.nan), v, v + 0.25])
        self.assertEqual(self.infer(first_empty), ("COUNT", "LOG2"))

    def test_colts_median(self):
        self.assertEqual(b._colt_median(np.array([])), 0.0)
        self.assertEqual(b._colt_median(np.array([1.0, 2.0, 4.0])), 2.0)
        self.assertEqual(b._colt_median(np.array([1.0, 2.0, 4.0, 8.0])), 3.0)
        self.assertTrue(math.isnan(b._colt_median(np.array([1.0, 2.0, np.inf]))))  # 1 * 2 + 0 * inf

    def test_the_mapping(self):
        self.assertEqual(b._gemma_reading("AMOUNT", "LINEAR"), "linear")
        self.assertEqual(b._gemma_reading("COUNT", "COUNT"), "linear")
        for scale in ("LOG2", "LOG10", "LN", "LOG1P", "LOGBASEUNKNOWN"):
            self.assertEqual(b._gemma_reading("AMOUNT", scale), "log")
        for scale in ("LINEAR", "OTHER", "LOGBASEUNKNOWN"):
            self.assertEqual(b._gemma_reading("ZSCORE", scale), "log")
        for scale in ("PERCENT", "PERCENT1", "OTHER"):
            self.assertIsNone(b._gemma_reading("AMOUNT", scale))
        self.assertIsNone(b._gemma_reading("PRESENTABSENT", "OTHER"))


class Median50Tests(unittest.TestCase):
    def test_a_median_above_50_means_linear(self):
        self.assertEqual(b.median_50(m([40.0, 60.0, 70.0])), "linear")
        self.assertEqual(b.median_50(m([40.0, 50.0, 70.0])), "log")  # strict

    def test_any_negative_means_log(self):
        self.assertEqual(b.median_50(m([60.0, 70.0, -0.1])), "log")

    def test_zeros_do_not_vote(self):
        self.assertEqual(b.median_50(m([0, 0, 0, 0, 60.0])), "linear")
        self.assertEqual(b.median_50(np.zeros((3, 2))), "log")  # no voter: median 0

    def test_only_finite_values_are_observed(self):
        self.assertEqual(b.median_50(m([np.inf, 1.0, 2.0])), "log")
        self.assertIsNone(b.median_50(m([np.inf, -np.inf])))


class MissingValuesTests(unittest.TestCase):
    def tables(self):
        rng = np.random.default_rng(5)
        linear = _protein(genes=60, cells=8, seed=3)
        small = rng.uniform(0, 12, size=(60, 8))
        small[rng.random(small.shape) < 0.2] = 0.0
        centred = rng.normal(0, 1, size=(60, 8))
        for x in (linear, np.log2(linear), small, centred, small * 9):
            x = x.copy()
            x[rng.random(x.shape) < 0.3] = np.nan
            yield x

    def test_pooled_rules_see_only_the_observed_values(self):
        for i, x in enumerate(self.tables()):
            flat = x[~np.isnan(x)].reshape(-1, 1)
            for name in POOLED:
                self.assertEqual(b.BASELINES[name](x), b.BASELINES[name](flat), f"{name}, table {i}")

    def test_a_table_with_no_observed_value_has_no_answer(self):
        for empty in (np.full((5, 3), np.nan), np.empty((0, 4)), np.empty((3, 0))):
            for name, rule in b.BASELINES.items():
                self.assertIsNone(rule(empty), f"{name}, shape {empty.shape}")

    def test_the_input_is_not_changed(self):
        for x in self.tables():
            before = x.copy()
            for name, rule in b.BASELINES.items():
                rule(x)
                np.testing.assert_array_equal(x, before, err_msg=name)


class ProteinTableTests(unittest.TestCase):
    def test_every_rule_answers_linear_log_or_none(self):
        linear = _protein()
        for x in (linear, np.log2(linear)):
            for name, rule in b.BASELINES.items():
                self.assertIn(rule(x), ("linear", "log", None), name)

    def test_the_readings_of_a_protein_table_and_its_log2(self):
        linear = _protein()
        for name, rule in b.BASELINES.items():
            self.assertEqual(rule(linear), "linear", name)
        # Three rules do not call the log2 table log, by design: scGPT and
        # CellTypist expect log1p of counts per 10,000 (here every value is
        # above 1 and the maximum is 26.5), and Gemma's maximum of 26.5 falls
        # between its LOG2 bound (20) and LINEAR (10^3.2), which it calls OTHER.
        logged = np.log2(linear)
        expected = dict.fromkeys(NAMES, "log") | {"scgpt": "linear", "celltypist": "linear", "gemma": None}
        for name, rule in b.BASELINES.items():
            self.assertEqual(rule(logged), expected[name], name)


class RegistryTests(unittest.TestCase):
    def test_the_nine_rules_in_order(self):
        self.assertEqual(tuple(b.BASELINES), NAMES)
        self.assertEqual(tuple(b.SOURCES), NAMES)
        for name, rule in b.BASELINES.items():
            self.assertIs(rule, getattr(b, name))

    def test_every_source_is_pinned(self):
        pinned = re.compile(r"^https://[^\s#]+/[0-9a-f]{40}/[^\s]+$")
        for name, links in b.SOURCES.items():
            self.assertIsInstance(links, tuple, name)
            self.assertTrue(links, name)
            for link in links:
                self.assertRegex(link, pinned, name)

    def test_every_rule_cites_its_source(self):
        for name, rule in b.BASELINES.items():
            self.assertTrue(any(link in rule.__doc__ for link in b.SOURCES[name]), name)


if __name__ == "__main__":
    unittest.main()
