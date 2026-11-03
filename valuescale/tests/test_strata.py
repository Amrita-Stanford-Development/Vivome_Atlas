"""Strata, subsamples and the constructed log class, as the protocol fixes
them (research/benchmark/protocol-value-scale.md, "Strata, subsamples and
the log class")."""
from __future__ import annotations

import hashlib
import unittest

import numpy as np

from valuescale.corpus import strata


def _linear(genes=200, cells=400, seed=0):
    rng = np.random.default_rng(seed)
    values = np.exp2(rng.normal(15, 2, size=(genes, 1)) + rng.normal(0, 0.5, size=(genes, cells)))
    values[rng.random(values.shape) < 0.2] = 0.0
    return values


class StratumTests(unittest.TestCase):
    def test_bounds(self):
        self.assertIsNone(strata.stratum_of(19))
        self.assertEqual(strata.stratum_of(20), "S1")
        self.assertEqual(strata.stratum_of(49), "S1")
        self.assertEqual(strata.stratum_of(50), "S2")
        self.assertEqual(strata.stratum_of(300), "S2")
        self.assertEqual(strata.stratum_of(301), "S3")
        self.assertEqual(strata.stratum_of(2000), "S3")
        self.assertIsNone(strata.stratum_of(2001))

    def test_strata_reached(self):
        self.assertEqual(strata.strata_reached(19), [])
        self.assertEqual(strata.strata_reached(20), ["S1"])
        self.assertEqual(strata.strata_reached(50), ["S1", "S2"])
        self.assertEqual(strata.strata_reached(557), ["S1", "S2", "S3"])

    def test_seed_is_the_protocols(self):
        expected = int(hashlib.sha256(b"20261103:PXD000001:S2").hexdigest(), 16)
        self.assertEqual(strata.seed_for("PXD000001", "S2"), expected)


class SubsampleTests(unittest.TestCase):
    def test_size_columns_and_repeatability(self):
        x = _linear()
        for stratum in ("S1", "S2", "S3"):
            sub, cols = strata.subsample(x, "t", stratum)
            lo, hi = strata.STRATA[stratum]
            self.assertTrue(lo <= sub.shape[1] <= min(hi, x.shape[1]))
            self.assertEqual(sub.shape[0], x.shape[0])
            self.assertTrue(np.all(np.diff(cols) > 0))
            np.testing.assert_array_equal(sub, x[:, cols])
            again, cols2 = strata.subsample(x, "t", stratum)
            np.testing.assert_array_equal(cols, cols2)

    def test_a_stratum_the_table_does_not_reach_is_refused(self):
        with self.assertRaises(ValueError):
            strata.subsample(_linear(cells=40), "t", "S2")


class ConstructedLogTests(unittest.TestCase):
    def test_one_of_the_four_forms_with_zeros_as_the_protocol_says(self):
        x = _linear()
        seen = set()
        for key in [f"t{i}" for i in range(40)]:
            name, made = strata.constructed_log(x, key, "S1")
            seen.add(name)
            zeros = x == 0
            with np.errstate(divide="ignore"):
                if name == "log2p1":
                    np.testing.assert_allclose(made, np.log2(x + 1))
                    self.assertTrue(np.all(made[zeros] == 0))
                else:
                    base = {"log2": 2.0, "log10": 10.0, "ln": np.e}[name]
                    np.testing.assert_allclose(made[~zeros], np.log(x[~zeros]) / np.log(base))
                    self.assertTrue(np.isnan(made[zeros]).all())
        self.assertEqual(seen, {"log2", "log10", "ln", "log2p1"})

    def test_small_values_never_get_log1p(self):
        x = _linear() / 1e5  # median positive value far below 10
        for key in [f"t{i}" for i in range(40)]:
            name, _ = strata.constructed_log(x, key, "S1")
            self.assertNotEqual(name, "log2p1")


if __name__ == "__main__":
    unittest.main()
