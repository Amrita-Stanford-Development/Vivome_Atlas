"""The conformal code: the umbrella order statistic, Clopper-Pearson
intervals, and the answer set (protocol research/benchmark/protocol-value-scale.md)."""
from __future__ import annotations

import math
import unittest

import numpy as np

from valuescale import conformal


class BinomialTests(unittest.TestCase):
    def test_cdf_matches_a_direct_sum(self):
        for n, p in ((10, 0.3), (59, 0.05), (200, 0.05)):
            for k in (0, 1, 3, n):
                direct = sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))
                self.assertAlmostEqual(conformal.binom_cdf(k, n, p), direct, places=12)


class UmbrellaTests(unittest.TestCase):
    def test_the_protocols_values(self):
        self.assertEqual(conformal.umbrella_k(59), 1)
        self.assertEqual(conformal.umbrella_k(120), 2)
        self.assertEqual(conformal.umbrella_k(200), 5)
        self.assertIsNone(conformal.umbrella_k(58))

    def test_k_is_the_largest_that_keeps_delta(self):
        for n in (59, 80, 150, 299, 500):
            k = conformal.umbrella_k(n)
            self.assertLessEqual(conformal.binom_cdf(k - 1, n, 0.05), 0.05)
            self.assertGreater(conformal.binom_cdf(k, n, 0.05), 0.05)

    def test_threshold_is_the_kth_smallest(self):
        scores = np.arange(200, 0, -1) / 7.0
        self.assertEqual(conformal.umbrella_threshold(scores), np.sort(scores)[4])
        self.assertIsNone(conformal.umbrella_threshold(scores[:58]))

    def test_rehearsal_threshold(self):
        scores = np.arange(1.0, 45.0)  # n = 44, floor(0.05 * 45) = 2
        self.assertEqual(conformal.rehearsal_threshold(scores), 2.0)
        self.assertEqual(conformal.rehearsal_threshold(scores[:10]), -math.inf)  # floor(0.55) = 0

    def test_a_small_simulation_keeps_the_guarantee(self):
        rng = np.random.default_rng(0)
        over = 0
        for _ in range(400):
            t = conformal.umbrella_threshold(rng.random(59))
            over += t > 0.05  # uniform scores: the miss rate is t itself
        self.assertLess(over / 400, 0.0485 + 3 * math.sqrt(0.0485 * 0.9515 / 400))


class ClopperPearsonTests(unittest.TestCase):
    def test_closed_forms_at_the_ends(self):
        n = 59
        lo, hi = conformal.clopper_pearson(0, n)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 1 - 0.025 ** (1 / n), places=10)
        lo, hi = conformal.clopper_pearson(n, n)
        self.assertAlmostEqual(lo, 0.025 ** (1 / n), places=10)
        self.assertEqual(hi, 1.0)

    def test_one_sided_lower_bound(self):
        n = 59
        self.assertAlmostEqual(conformal.clopper_pearson_lower(n, n), 0.05 ** (1 / n), places=10)
        self.assertEqual(conformal.clopper_pearson_lower(0, n), 0.0)

    def test_the_interval_holds_the_estimate(self):
        for x, n in ((3, 59), (10, 120), (1, 7)):
            lo, hi = conformal.clopper_pearson(x, n)
            self.assertLess(lo, x / n)
            self.assertGreater(hi, x / n)


class AnswerSetTests(unittest.TestCase):
    def test_the_four_answers(self):
        t = {"linear": 0.1, "log": 0.1}
        self.assertEqual(conformal.answer_set({"linear": 0.5, "log": 0.0}, t), ("linear",))
        self.assertEqual(conformal.answer_set({"linear": 0.0, "log": 0.5}, t), ("log",))
        self.assertEqual(conformal.answer_set({"linear": 0.5, "log": 0.5}, t), ("linear", "log"))
        self.assertEqual(conformal.answer_set({"linear": 0.0, "log": 0.0}, t), ())

    def test_a_score_at_the_threshold_is_in(self):
        self.assertEqual(conformal.answer_set({"linear": 0.1, "log": 0.0}, {"linear": 0.1, "log": 0.1}), ("linear",))

    def test_verdict_names(self):
        self.assertEqual(conformal.verdict(("linear",)), "linear")
        self.assertEqual(conformal.verdict(("log",)), "log")
        self.assertEqual(conformal.verdict(("linear", "log")), "cant_tell")
        self.assertEqual(conformal.verdict(()), "unlike_either")


if __name__ == "__main__":
    unittest.main()
