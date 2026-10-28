"""Variants carry the label of how they were made, and are the same on every run."""
from __future__ import annotations

import unittest

import numpy as np

from valuescale.corpus import variants


def _lognormal(genes=300, cells=60, seed=0, missing=0.3):
    rng = np.random.default_rng(seed)
    level = rng.normal(20, 2.5, size=(genes, 1))
    log2 = level + rng.normal(0, 0.5, size=(genes, cells))
    values = np.exp2(log2)
    values[rng.random(values.shape) < missing] = np.nan
    return values


class VariantTests(unittest.TestCase):
    def setUp(self):
        self.linear = _lognormal()
        self.made = {name: (v, label) for name, v, label in variants.variants("t", self.linear, "linear")}

    def test_labels_follow_the_construction(self):
        self.assertEqual(self.made["times_1e-6"][1], "linear")
        self.assertEqual(self.made["per_protein_median"][1], "linear")
        for name in ("log2", "log10", "ln", "log2_plus10", "log2_plus1_after_min", "log2_zeros_imputed"):
            self.assertEqual(self.made[name][1], "log", name)
        for name in ("zscore_genes", "presence", "ranks"):
            self.assertEqual(self.made[name][1], "foreign", name)

    def test_scaled_and_logged_values_are_exact(self):
        np.testing.assert_allclose(self.made["times_1e-6"][0], self.linear * 1e-6)
        np.testing.assert_allclose(self.made["log10"][0], np.log10(self.linear))
        np.testing.assert_allclose(self.made["log2_plus10"][0], np.log2(self.linear) + 10)

    def test_a_log_table_gives_its_linear_form(self):
        log2 = np.log2(self.linear)
        made = {name: (v, label) for name, v, label in variants.variants("t", log2, "log")}
        np.testing.assert_allclose(made["times_1e3"][0], self.linear * 1e3)
        self.assertEqual(made["times_1e3"][1], "linear")

    def test_subsamples_keep_the_label_and_size(self):
        self.assertEqual(self.made["subsample_20"][0].shape, (300, 20))
        self.assertEqual(self.made["subsample_50"][0].shape, (300, 50))
        self.assertNotIn("subsample_300", self.made)  # the table has only 60 cells

    def test_induced_missing_reaches_its_target_and_hits_low_values_first(self):
        out, label = self.made["missing_70"]
        self.assertEqual(label, "linear")
        self.assertAlmostEqual(np.isnan(out).mean(), 0.70, delta=0.02)
        removed = ~np.isnan(self.linear) & np.isnan(out)
        kept = ~np.isnan(out)
        self.assertLess(np.median(np.log2(self.linear[removed])), np.median(np.log2(self.linear[kept])))

    def test_variants_are_the_same_on_every_run(self):
        again = {name: v for name, v, _ in variants.variants("t", self.linear, "linear")}
        for name, (v, _) in self.made.items():
            np.testing.assert_array_equal(v, again[name], err_msg=name)

    def test_a_foreign_label_is_refused_as_a_source(self):
        with self.assertRaises(ValueError):
            list(variants.variants("t", self.linear, "foreign"))


if __name__ == "__main__":
    unittest.main()
