import unittest

import numpy as np

from service import config
from service.pipeline import transfer
from service.pipeline.topk import chunked_topk


def _unit_rows(m):
    return m / np.linalg.norm(m, axis=1, keepdims=True)


class ChunkedTopkTests(unittest.TestCase):
    """topk.chunked_topk is shared with assignment.py's kNN method — see
    test_assignment.py for coverage of the candidate_labels indirection it
    uses that this module doesn't need."""

    def test_matches_a_naive_full_computation(self):
        rng = np.random.default_rng(0)
        query = _unit_rows(rng.normal(size=(6, 5)))
        reference = _unit_rows(rng.normal(size=(300, 5)))
        naive_sim = query @ reference.T
        naive_top = np.sort(naive_sim, axis=1)[:, -5:][:, ::-1]

        idx, sim = chunked_topk(query, reference, k=5, chunk_size=41)
        chunked_top = np.sort(sim, axis=1)[:, ::-1]
        np.testing.assert_allclose(chunked_top, naive_top, atol=1e-5)

    def test_default_labels_are_the_candidates_own_row_index(self):
        rng = np.random.default_rng(0)
        query = _unit_rows(rng.normal(size=(2, 4)))
        candidates = _unit_rows(rng.normal(size=(10, 4)))
        labels, sim = chunked_topk(query, candidates, k=3, chunk_size=4)
        # Every returned label must be a real row index into `candidates`,
        # and it must point at the row that actually produced that
        # similarity value.
        for row in range(2):
            for col in range(3):
                idx = labels[row, col]
                self.assertAlmostEqual(query[row] @ candidates[idx], sim[row, col], places=5)


class TransferPropertiesTests(unittest.TestCase):
    def test_only_shipped_properties_are_returned(self):
        rng = np.random.default_rng(0)
        reference_embeddings = _unit_rows(rng.normal(size=(50, 8)))
        # interferon and cell_cycle_G2M are the two real v3 candidates that
        # failed validation (config.py's SHIPPED_PROPERTIES comment) — using
        # the real names here, not placeholders.
        names = list(config.SHIPPED_PROPERTIES) + ["interferon", "cell_cycle_G2M"]
        values = rng.normal(size=(50, len(names)))
        query = _unit_rows(rng.normal(size=(3, 8)))

        result = transfer.transfer_properties(query, reference_embeddings, names, values, k=5)
        self.assertEqual(set(result.property_names), set(config.SHIPPED_PROPERTIES))
        self.assertNotIn("interferon", result.property_names)
        self.assertNotIn("cell_cycle_G2M", result.property_names)

    def test_identical_neighbour_values_give_zero_uncertainty(self):
        reference_embeddings = _unit_rows(np.array([[1.0, 0.0], [0.99, 0.01], [0.98, 0.02]]))
        values = np.array([[5.0], [5.0], [5.0]])
        query = _unit_rows(np.array([[1.0, 0.0]]))

        result = transfer.transfer_properties(query, reference_embeddings, ["ribosome"], values, k=3)
        self.assertAlmostEqual(result.values[0, 0], 5.0, places=4)
        self.assertAlmostEqual(result.uncertainty[0, 0], 0.0, places=4)

    def test_disagreeing_neighbours_give_nonzero_uncertainty(self):
        reference_embeddings = _unit_rows(np.array([[1.0, 0.0], [0.99, 0.01], [0.98, 0.02]]))
        values = np.array([[0.0], [10.0], [20.0]])
        query = _unit_rows(np.array([[1.0, 0.0]]))

        result = transfer.transfer_properties(query, reference_embeddings, ["ribosome"], values, k=3)
        self.assertGreater(result.uncertainty[0, 0], 0.0)

    def test_degenerate_negative_similarity_falls_back_to_uniform_weights(self):
        reference_embeddings = _unit_rows(np.array([[-1.0, 0.0], [0.0, -1.0]]))
        values = np.array([[2.0], [4.0]])
        query = _unit_rows(np.array([[1.0, 0.0]]))  # anti-correlated with both

        result = transfer.transfer_properties(query, reference_embeddings, ["ribosome"], values, k=2)
        self.assertAlmostEqual(result.values[0, 0], 3.0, places=4)  # uniform mean of 2 and 4


if __name__ == "__main__":
    unittest.main()
