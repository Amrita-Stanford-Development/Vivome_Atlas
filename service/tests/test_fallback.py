import unittest

import numpy as np

from service.pipeline import fallback


class ResolveFallbackTests(unittest.TestCase):
    def test_each_of_the_five_documented_pairs_resolves(self):
        for pair in fallback.CONFUSABLE_PAIRS:
            names = list(pair.members)
            self.assertEqual(fallback.resolve_fallback(names), pair.fallback_label)
            self.assertEqual(fallback.resolve_fallback(list(reversed(names))), pair.fallback_label)

    def test_five_distinct_pairs_not_six(self):
        """The brief lists six phrases, but 'CD8 positive T cell and
        natural killer cell' and 'natural killer cell and CD8 T cell' name
        the same unordered pair, found in two independent tests. See
        fallback.py's module docstring."""
        self.assertEqual(len(fallback.CONFUSABLE_PAIRS), 5)

    def test_unrelated_pair_does_not_resolve(self):
        self.assertIsNone(fallback.resolve_fallback(["b cell", "platelet"]))

    def test_a_singleton_set_does_not_resolve(self):
        self.assertIsNone(fallback.resolve_fallback(["macrophage"]))

    def test_a_three_member_set_does_not_resolve(self):
        self.assertIsNone(fallback.resolve_fallback(["macrophage", "monocyte", "b cell"]))

    def test_existing_broader_classes_are_reused_not_invented(self):
        """naive CD4 / CD4 T cell and intermediate/classical monocyte each
        already have a real parent among the 22 reference classes; the
        fallback should name that class, not a new label."""
        cd4_pair = next(p for p in fallback.CONFUSABLE_PAIRS if "naive thymus-derived cd4-positive, alpha-beta t cell" in p.members)
        self.assertEqual(cd4_pair.fallback_label, "cd4-positive, alpha-beta t cell")

        monocyte_pair = next(p for p in fallback.CONFUSABLE_PAIRS if "intermediate monocyte" in p.members)
        self.assertEqual(monocyte_pair.fallback_label, "monocyte")



class PairConfidenceTests(unittest.TestCase):
    def test_within_pair_share_is_the_winners_share_of_the_pair(self):
        self.assertAlmostEqual(fallback.pair_confidence(np.array([0.3, 0.1]), "within_pair_share"), 0.75)

    def test_pair_mass_is_the_pairs_summed_probability(self):
        self.assertAlmostEqual(fallback.pair_confidence(np.array([0.3, 0.1]), "pair_mass"), 0.4)

    def test_an_unknown_rule_raises(self):
        with self.assertRaises(ValueError):
            fallback.pair_confidence(np.array([0.5, 0.5]), "average")


if __name__ == "__main__":
    unittest.main()
