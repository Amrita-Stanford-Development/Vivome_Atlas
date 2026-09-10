import unittest

import numpy as np

from service import config
from service.pipeline import transfer


def _unit_rows(m):
    return m / np.linalg.norm(m, axis=1, keepdims=True)


class TopkQueryToReferenceTests(unittest.TestCase):
    def test_matches_a_naive_full_computation(self):
        rng = np.random.default_rng(0)
        query = _unit_rows(rng.normal(size=(6, 5)))
        reference = _unit_rows(rng.normal(size=(300, 5)))
        naive_sim = query @ reference.T
        naive_top = np.sort(naive_sim, axis=1)[:, -5:][:, ::-1]

        idx, sim = transfer._topk_query_to_reference(query, reference, k=5, chunk_size=41)
        chunked_top = np.sort(sim, axis=1)[:, ::-1]
        np.testing.assert_allclose(chunked_top, naive_top, atol=1e-5)


class TransferPropertiesTests(unittest.TestCase):
    def test_only_shipped_properties_are_returned(self):
        rng = np.random.default_rng(0)
        reference_embeddings = _unit_rows(rng.normal(size=(50, 8)))
        names = list(config.SHIPPED_PROPERTIES) + ["interferon_response", "cell_cycle"]
        values = rng.normal(size=(50, len(names)))
        query = _unit_rows(rng.normal(size=(3, 8)))

        result = transfer.transfer_properties(query, reference_embeddings, names, values, k=5)
        self.assertEqual(set(result.property_names), set(config.SHIPPED_PROPERTIES))
        self.assertNotIn("interferon_response", result.property_names)
        self.assertNotIn("cell_cycle", result.property_names)

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
