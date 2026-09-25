import unittest

import numpy as np

from service.pipeline import abstention, search


def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


class FaissMaxCosineEquivalenceTests(unittest.TestCase):
    """Pins `search.faiss_max_cosine_to_reference` against the original
    numpy `abstention.max_cosine_to_reference` it replaces at pipeline.py's
    Stage 6 call site -- abstention.py itself is untouched (Track B forbids
    editing it), this only proves the two agree within the 1e-5 tolerance
    the Track B prompt asked for."""

    def test_matches_abstention_numpy_implementation(self):
        rng = np.random.default_rng(0)
        queries = _l2_normalise(rng.normal(size=(200, 128)).astype(np.float32))
        reference = _l2_normalise(rng.normal(size=(5000, 128)).astype(np.float32))

        faiss_result = search.faiss_max_cosine_to_reference(queries, reference)
        numpy_result = abstention.max_cosine_to_reference(queries, reference)

        np.testing.assert_allclose(faiss_result, numpy_result, atol=1e-5)

    def test_matches_on_a_single_query_and_reference_cell(self):
        query = _l2_normalise(np.array([[1.0, 2.0, 3.0]], dtype=np.float32))
        reference = _l2_normalise(np.array([[1.0, 2.0, 3.0]], dtype=np.float32))

        faiss_result = search.faiss_max_cosine_to_reference(query, reference)
        numpy_result = abstention.max_cosine_to_reference(query, reference)

        np.testing.assert_allclose(faiss_result, numpy_result, atol=1e-5)
        self.assertAlmostEqual(float(faiss_result[0]), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
