import unittest

import numpy as np

from service.pipeline import smoothing


class FuzzySmoothTests(unittest.TestCase):
    def test_alpha_0_returns_original_values_unchanged(self):
        rng = np.random.default_rng(0)
        shared = rng.normal(size=(10, 5))
        full = rng.normal(size=(10, 50))
        smoothed = smoothing.fuzzy_smooth(shared, full, k=3, alpha=0.0)
        np.testing.assert_allclose(smoothed, shared)

    def test_single_cell_upload_is_a_no_op_not_a_crash(self):
        shared = np.array([[1.0, 2.0, 3.0]])
        full = np.array([[1.0, 2.0]])
        smoothed = smoothing.fuzzy_smooth(shared, full)
        np.testing.assert_array_equal(smoothed, shared)

    def test_identical_neighbours_smooth_toward_the_same_value(self):
        # Two cells with identical full-feature profiles are each other's
        # only neighbour; smoothing should pull a noisy shared value toward
        # the neighbour's, not leave it untouched.
        full = np.array([[1.0, 0.0], [1.0, 0.0]])
        shared = np.array([[0.0], [10.0]])
        smoothed = smoothing.fuzzy_smooth(shared, full, k=1, alpha=1.0)
        np.testing.assert_allclose(smoothed, [[10.0], [0.0]])

    def test_output_shape_matches_shared_values(self):
        rng = np.random.default_rng(1)
        shared = rng.normal(size=(8, 4))
        full = rng.normal(size=(8, 20))
        smoothed = smoothing.fuzzy_smooth(shared, full, k=3)
        self.assertEqual(smoothed.shape, shared.shape)


if __name__ == "__main__":
    unittest.main()
