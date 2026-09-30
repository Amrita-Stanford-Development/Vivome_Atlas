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
        uniform 1/3 column marginal. This is the brief's central warning
        about the OT method specifically — not the default method, so it
        must be requested explicitly rather than relying on config's
        current default."""
        query = _unit_rows(np.tile([1.0, 0.05, 0.0, 0.0], (12, 1)))
        relaxed = assignment.assign_labels(query, self.centroids, method="ot", tau=0.1)
        tightened = assignment.assign_labels(query, self.centroids, method="ot", tau=50.0)

        relaxed_share_class0 = relaxed[:, 0].mean()
        tightened_share_class0 = tightened[:, 0].mean()
        self.assertGreater(relaxed_share_class0, tightened_share_class0)

    def test_top_label_confidence_is_the_winning_probability(self):
        probs = np.array([[0.7, 0.2, 0.1], [0.1, 0.1, 0.8]])
        position, confidence = assignment.top_label(probs)
        np.testing.assert_array_equal(position, [0, 2])
        np.testing.assert_allclose(confidence, [0.7, 0.8])


class RestrictedAssignmentTests(unittest.TestCase):
    """Class 1 has no cross-modal support in this scenario; assignment must
    never place any mass there, for any method."""

    def setUp(self):
        self.centroids = _unit_rows(np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ]))
        self.allowed = {0, 2}
        rng = np.random.default_rng(0)
        # Queries scattered across all three directions, including some
        # that sit closest to the disallowed class 1.
        self.query = _unit_rows(rng.normal(size=(20, 4)))

    def test_disallowed_column_is_always_exactly_zero(self):
        for method in ("nearest_centroid", "ot", "knn"):
            with self.subTest(method=method):
                kwargs = {}
                if method == "knn":
                    kwargs = dict(
                        reference_embeddings=self.centroids,
                        reference_class_positions=np.array([0, 1, 2]),
                    )
                probs = assignment.assign_labels(
                    self.query, self.centroids, allowed_positions=self.allowed,
                    method=method, **kwargs,
                )
                np.testing.assert_array_equal(probs[:, 1], np.zeros(len(self.query)))

    def test_top_label_never_returns_a_restricted_out_class(self):
        probs = assignment.assign_labels(
            self.query, self.centroids, allowed_positions=self.allowed, method="nearest_centroid",
        )
        position, _ = assignment.top_label(probs)
        self.assertNotIn(1, set(position.tolist()))

    def test_restricted_rows_still_sum_to_one(self):
        for method in ("nearest_centroid", "ot"):
            with self.subTest(method=method):
                probs = assignment.assign_labels(
                    self.query, self.centroids, allowed_positions=self.allowed, method=method,
                )
                np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-6)


class AssignmentMethodTests(unittest.TestCase):
    """All three methods are real, selectable, and honest about a bad
    selection — the config default having flipped once already
    (assignment.py's module docstring) is exactly why 'silently fall back
    to something' would be the wrong failure mode here."""

    def setUp(self):
        self.centroids = _unit_rows(np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ]))
        self.query = _unit_rows(np.array([[1.0, 0.05, 0.0, 0.0], [0.0, 1.0, 0.05, 0.0]]))

    def test_all_three_methods_return_the_same_shape_and_row_sums(self):
        for method in ("nearest_centroid", "ot", "knn"):
            with self.subTest(method=method):
                kwargs = {}
                if method == "knn":
                    kwargs = dict(
                        reference_embeddings=self.centroids,
                        reference_class_positions=np.array([0, 1, 2]),
                    )
                probs = assignment.assign_labels(self.query, self.centroids, method=method, **kwargs)
                self.assertEqual(probs.shape, (2, 3))
                np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-6)

    def test_unrecognised_method_raises_instead_of_silently_falling_back(self):
        with self.assertRaises(ValueError):
            assignment.assign_labels(self.query, self.centroids, method="not_a_real_method")

    def test_empty_allowed_positions_raises_instead_of_crashing_differently_per_method(self):
        # A rename or reference swap that leaves CROSS_MODAL_SUPPORTED_CLASSES
        # matching nothing must fail loudly and consistently, not with three
        # different crashes (or a silent all-zero result for knn) depending
        # on which method happened to be configured.
        for method in ("nearest_centroid", "ot", "knn"):
            with self.subTest(method=method):
                kwargs = {}
                if method == "knn":
                    kwargs = dict(
                        reference_embeddings=self.centroids,
                        reference_class_positions=np.array([0, 1, 2]),
                    )
                with self.assertRaises(ValueError):
                    assignment.assign_labels(
                        self.query, self.centroids, allowed_positions=set(), method=method, **kwargs,
                    )

    def test_knn_without_reference_data_raises(self):
        with self.assertRaises(ValueError):
            assignment.assign_labels(self.query, self.centroids, method="knn")

    def test_nearest_centroid_and_knn_agree_on_well_separated_classes(self):
        """Not a claim that the two methods generally agree — only that on
        this easy, well-separated case they should, as a sanity check that
        knn's vote share isn't wired backwards. knn_k=1: the synthetic pool
        here has exactly one reference cell per class, so any k >= pool
        size makes every class "in the top k" for every query, and vote
        share degenerates to a tie broken arbitrarily by argmax — not a
        meaningful test of nearest-neighbour behaviour."""
        reference_embeddings = self.centroids
        reference_class_positions = np.array([0, 1, 2])
        nc = assignment.assign_labels(self.query, self.centroids, method="nearest_centroid")
        knn = assignment.assign_labels(
            self.query, self.centroids, method="knn", knn_k=1,
            reference_embeddings=reference_embeddings,
            reference_class_positions=reference_class_positions,
        )
        np.testing.assert_array_equal(nc.argmax(axis=1), knn.argmax(axis=1))



class CalibrationSocketTests(unittest.TestCase):
    """Track C: temperature and per-class bias on nearest-centroid's softmax,
    for T1 NB2's fitted parameters. Defaults must reproduce v3 exactly."""

    def setUp(self):
        self.centroids = _unit_rows(np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]))
        rng = np.random.default_rng(3)
        self.query = _unit_rows(rng.normal(size=(20, 3)))

    def test_defaults_are_exactly_todays_output(self):
        plain = assignment.assign_labels(self.query, self.centroids)
        explicit = assignment.assign_labels(self.query, self.centroids, temperature=1.0, class_bias=None)
        np.testing.assert_array_equal(plain, explicit)

    def test_a_lower_temperature_sharpens_without_changing_the_winner(self):
        plain = assignment.assign_labels(self.query, self.centroids)
        sharp = assignment.assign_labels(self.query, self.centroids, temperature=0.1)
        np.testing.assert_array_equal(plain.argmax(axis=1), sharp.argmax(axis=1))
        self.assertTrue((sharp.max(axis=1) >= plain.max(axis=1)).all())

    def test_a_class_bias_moves_mass_to_that_class(self):
        bias = np.array([0.0, 0.0, 5.0])
        biased = assignment.assign_labels(self.query, self.centroids, class_bias=bias)
        self.assertTrue((biased.argmax(axis=1) == 2).all())

    def test_bias_is_indexed_by_full_position_under_a_restriction(self):
        bias = np.array([0.0, 5.0, 0.0])  # favours class 1, which is restricted out
        probs = assignment.assign_labels(self.query, self.centroids, allowed_positions={0, 2}, class_bias=bias)
        self.assertTrue((probs[:, 1] == 0).all())
        unbiased = assignment.assign_labels(self.query, self.centroids, allowed_positions={0, 2})
        np.testing.assert_allclose(probs, unbiased, atol=1e-6)

    def test_methods_without_a_softmax_refuse_the_options(self):
        for method in ("ot", "knn"):
            with self.assertRaises(ValueError):
                assignment.assign_labels(self.query, self.centroids, method=method, temperature=0.5)


if __name__ == "__main__":
    unittest.main()
