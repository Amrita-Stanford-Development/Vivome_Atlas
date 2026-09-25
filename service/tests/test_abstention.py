import unittest

import numpy as np

from service.pipeline import abstention


def _unit_rows(m):
    return m / np.linalg.norm(m, axis=1, keepdims=True)


class MaxCosineToReferenceTests(unittest.TestCase):
    def test_matches_a_naive_full_computation(self):
        rng = np.random.default_rng(0)
        query = _unit_rows(rng.normal(size=(15, 8)))
        reference = _unit_rows(rng.normal(size=(500, 8)))
        naive = (query @ reference.T).max(axis=1)
        chunked = abstention.max_cosine_to_reference(query, reference, chunk_size=37)
        np.testing.assert_allclose(chunked, naive, atol=1e-5)

    def test_identical_reference_cell_scores_1(self):
        reference = _unit_rows(np.array([[1.0, 0.0], [0.0, 1.0]]))
        query = reference[:1]
        scores = abstention.max_cosine_to_reference(query, reference)
        self.assertAlmostEqual(scores[0], 1.0, places=5)

    def test_orthogonal_query_scores_near_zero(self):
        reference = _unit_rows(np.array([[1.0, 0.0]]))
        query = _unit_rows(np.array([[0.0, 1.0]]))
        scores = abstention.max_cosine_to_reference(query, reference)
        self.assertAlmostEqual(scores[0], 0.0, places=5)


class ScoreAbstentionPriorityTests(unittest.TestCase):
    """Coverage floor > out-of-distribution > empty/ambiguous conformal set,
    per the brief's stage ordering."""

    def _run(self, observed_genes, max_similarity, label_sets):
        n = len(observed_genes)
        calibration_indices = np.arange(n)
        return abstention.score_abstention(
            max_similarity=np.array(max_similarity),
            per_cell_observed_genes=np.array(observed_genes),
            label_sets=label_sets,
            calibration_indices=calibration_indices,
            similarity_quantile=0.5,  # median of calibration scores as threshold, for a crisp test
            min_observed_genes=100,
        )

    def test_low_coverage_abstains_regardless_of_similarity_or_confidence(self):
        result = self._run(observed_genes=[5, 900], max_similarity=[0.99, 0.99], label_sets=[[0], [0]])
        self.assertTrue(result.abstained[0])
        self.assertEqual(result.reason[0], abstention.AbstainReason.LOW_COVERAGE)

    def test_out_of_distribution_abstains_even_with_a_confident_singleton_set(self):
        result = self._run(observed_genes=[900, 900], max_similarity=[0.01, 0.99], label_sets=[[0], [0]])
        self.assertTrue(result.abstained[0])
        self.assertEqual(result.reason[0], abstention.AbstainReason.OUT_OF_DISTRIBUTION)

    def test_empty_label_set_is_no_confident_label(self):
        result = self._run(observed_genes=[900, 900], max_similarity=[0.99, 0.99], label_sets=[[], [0]])
        self.assertTrue(result.abstained[0])
        self.assertEqual(result.reason[0], abstention.AbstainReason.NO_CONFIDENT_LABEL)

    def test_multi_class_label_set_is_ambiguous(self):
        result = self._run(observed_genes=[900, 900], max_similarity=[0.99, 0.99], label_sets=[[0, 1], [0]])
        self.assertTrue(result.abstained[0])
        self.assertEqual(result.reason[0], abstention.AbstainReason.AMBIGUOUS)

    def test_singleton_set_within_support_is_not_abstained(self):
        result = self._run(observed_genes=[900], max_similarity=[0.99], label_sets=[[3]])
        self.assertFalse(result.abstained[0])
        self.assertEqual(result.reason[0], abstention.AbstainReason.NONE)

    def test_min_observed_genes_boundary_is_exclusive_below(self):
        result = self._run(observed_genes=[99, 100], max_similarity=[0.99, 0.99], label_sets=[[0], [0]])
        self.assertTrue(result.abstained[0])
        self.assertFalse(result.abstained[1])


if __name__ == "__main__":
    unittest.main()
