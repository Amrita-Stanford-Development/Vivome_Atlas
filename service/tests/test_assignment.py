import unittest

import numpy as np

from service.pipeline import assignment


def _unit_rows(m):
    return m / np.linalg.norm(m, axis=1, keepdims=True)


class AssignLabelsTests(unittest.TestCase):
    def setUp(self):
        # 3 well-separated classes in 4D, one centroid each.
        self.centroids = _unit_rows(np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ]))

    def test_rows_sum_to_one(self):
        query = _unit_rows(np.array([[1.0, 0.1, 0.0, 0.0], [0.0, 0.0, 1.0, 0.1]]))
        probs = assignment.assign_labels(query, self.centroids)
        np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-6)

    def test_a_query_cell_lands_closest_to_its_matching_centroid(self):
        query = _unit_rows(np.array([[1.0, 0.05, 0.0, 0.0]]))
        probs = assignment.assign_labels(query, self.centroids)
        self.assertEqual(probs.argmax(), 0)

    def test_relaxed_marginal_does_not_force_even_spread_across_all_classes(self):
        """Every query cell is near class 0 only. A relaxed marginal should
        let mass concentrate there; a tightened one forces it toward the
        uniform 1/3 column marginal. This is the brief's central warning."""
        query = _unit_rows(np.tile([1.0, 0.05, 0.0, 0.0], (12, 1)))
        relaxed = assignment.assign_labels(query, self.centroids, tau=0.1)
        tightened = assignment.assign_labels(query, self.centroids, tau=50.0)

        relaxed_share_class0 = relaxed[:, 0].mean()
        tightened_share_class0 = tightened[:, 0].mean()
        self.assertGreater(relaxed_share_class0, tightened_share_class0)

    def test_top_label_confidence_is_the_winning_probability(self):
        probs = np.array([[0.7, 0.2, 0.1], [0.1, 0.1, 0.8]])
        class_idx, confidence = assignment.top_label(probs)
        np.testing.assert_array_equal(class_idx, [0, 2])
        np.testing.assert_allclose(confidence, [0.7, 0.8])


if __name__ == "__main__":
    unittest.main()
