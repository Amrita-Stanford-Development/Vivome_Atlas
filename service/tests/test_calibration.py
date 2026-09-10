import unittest

import numpy as np

from service.pipeline import calibration


class CalibrateAndBuildSetsTests(unittest.TestCase):
    def test_calibration_slice_is_drawn_randomly_not_by_confidence(self):
        """Regression guard for the exact bug the brief says was already
        found and fixed once: selecting the query's most-confident cells for
        calibration. Two different seeds must not both happen to pick the
        top-confidence cells."""
        rng_state = np.random.default_rng(0)
        probs = np.tile([0.9, 0.05, 0.05], (50, 1))
        probs[:10] = [0.99, 0.005, 0.005]  # the 10 "most confident" cells
        result = calibration.calibrate_and_build_sets(probs, rng=rng_state)
        # A confidence-filtered selector would only ever draw from [0:10).
        self.assertFalse(set(result.calibration_indices.tolist()).issubset(set(range(10))))

    def test_every_label_set_is_a_list_of_valid_class_indices(self):
        probs = np.array([[0.6, 0.3, 0.1], [0.4, 0.4, 0.2]])
        result = calibration.calibrate_and_build_sets(probs, rng=np.random.default_rng(1))
        for label_set in result.label_sets:
            self.assertTrue(all(0 <= c < 3 for c in label_set))

    def test_qhat_is_a_valid_nonconformity_quantile(self):
        rng = np.random.default_rng(2)
        probs = rng.dirichlet(alpha=[1, 1, 1, 1], size=200)
        result = calibration.calibrate_and_build_sets(probs, alpha=0.1, rng=rng)
        self.assertGreaterEqual(result.qhat, 0.0)
        self.assertLessEqual(result.qhat, 1.0)

    def test_a_very_confident_cell_gets_a_singleton_set(self):
        rng = np.random.default_rng(3)
        probs = rng.dirichlet(alpha=[0.5] * 5, size=100)
        probs[0] = [0.999, 0.00025, 0.00025, 0.00025, 0.00025]
        result = calibration.calibrate_and_build_sets(probs, alpha=0.2, rng=rng)
        self.assertEqual(result.label_sets[0], [0])

    def test_small_query_still_calibrates_using_all_available_cells(self):
        probs = np.array([[0.8, 0.1, 0.1], [0.5, 0.3, 0.2], [0.34, 0.33, 0.33]])
        result = calibration.calibrate_and_build_sets(probs, rng=np.random.default_rng(4))
        self.assertLessEqual(len(result.calibration_indices), 3)
        self.assertEqual(len(result.label_sets), 3)


if __name__ == "__main__":
    unittest.main()
