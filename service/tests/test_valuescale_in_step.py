"""The raw-or-log package (valuescale/) imports nothing from the service, so
the few rules it copies are pinned to the service's own here
(research/value-scale-plan.md, B4):
- valuescale.apply reads a protein table as alignment.apply_reading does;
- valuescale.baselines.median_50 is alignment.median_rule for protein
  (zeros do not vote), the rule the detector is compared against."""
from __future__ import annotations

import unittest

import numpy as np

import valuescale
from service import config
from service.pipeline import alignment


def _tables():
    rng = np.random.default_rng(7)
    linear = np.exp2(rng.normal(14, 3, size=(300, 1)) + rng.normal(0, 0.7, size=(300, 25)))
    linear[rng.random(linear.shape) < 0.3] = np.nan
    with_zeros = np.where(rng.random(linear.shape) < 0.2, 0.0, linear)
    small = with_zeros / 1e5  # a linear table on a small scale: median well under 50
    logged = np.log2(linear)
    logged_zeros = np.where(rng.random(logged.shape) < 0.1, 0.0, logged)
    centred = logged - np.nanmedian(logged, axis=0, keepdims=True)
    return {"linear": linear, "with_zeros": with_zeros, "small": small, "logged": logged,
            "logged_zeros": logged_zeros, "centred": centred, "empty": np.full((5, 21), np.nan)}


class ApplyInStepTests(unittest.TestCase):
    def test_every_reading_matches_the_services(self):
        for name, x in _tables().items():
            for reading, zeros in (("linear", None), ("log", None), ("log", "missing"), ("log", "measured")):
                with self.subTest(table=name, reading=reading, zeros=zeros):
                    try:
                        expected = alignment.apply_reading(x, reading, zeros)
                    except alignment.NotIntensities as exc:
                        with self.assertRaises(ValueError) as caught:
                            valuescale.apply(x, reading, zeros)
                        self.assertEqual(str(caught.exception), str(exc))
                        continue
                    np.testing.assert_array_equal(valuescale.apply(x, reading, zeros), expected)


class MedianRuleInStepTests(unittest.TestCase):
    def test_median_50_is_the_services_protein_rule(self):
        from valuescale import baselines
        self.assertEqual(config.LINEAR_SCALE_MEDIAN_THRESHOLD, 50)
        for name, x in _tables().items():
            with self.subTest(table=name):
                expected = alignment.median_rule(x, zeros_vote=False)
                self.assertEqual(baselines.median_50(x), None if expected == "unknown" else expected)


class CalibratedReadingInStepTests(unittest.TestCase):
    def test_the_undecided_reading_is_the_packages(self):
        """B5: on "can't tell" or "unlike either" the service reads a protein
        table as valuescale's report does (research/value-scale-b5-design.md)."""
        from valuescale import report
        self.assertEqual(config.VALUE_SCALE_UNDECIDED_READING, report.UNDECIDED_READING)


if __name__ == "__main__":
    unittest.main()
