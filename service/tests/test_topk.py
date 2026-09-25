import unittest

import numpy as np

from service.pipeline import topk


def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


class ChunkedTopkFaissEquivalenceTests(unittest.TestCase):
    """`chunked_topk` is now FAISS-backed (Track B); this pins it against
    the original pure-numpy implementation it replaced, kept in this file
    as `_chunked_topk_numpy_reference` for exactly this purpose."""

    def test_matches_numpy_reference_on_random_embeddings(self):
        rng = np.random.default_rng(0)
        queries = _l2_normalise(rng.normal(size=(37, 16)).astype(np.float32))
        candidates = _l2_normalise(rng.normal(size=(500, 16)).astype(np.float32))

        faiss_labels, faiss_sim = topk.chunked_topk(queries, candidates, k=5)
        numpy_labels, numpy_sim = topk._chunked_topk_numpy_reference(queries, candidates, k=5)

        np.testing.assert_array_equal(faiss_labels, numpy_labels)
        np.testing.assert_allclose(faiss_sim, numpy_sim, atol=1e-5)

    def test_matches_numpy_reference_with_custom_candidate_labels(self):
        rng = np.random.default_rng(1)
        queries = _l2_normalise(rng.normal(size=(10, 8)).astype(np.float32))
        candidates = _l2_normalise(rng.normal(size=(120, 8)).astype(np.float32))
        candidate_labels = rng.integers(0, 4, size=120)

        faiss_labels, faiss_sim = topk.chunked_topk(queries, candidates, k=3, candidate_labels=candidate_labels)
        numpy_labels, numpy_sim = topk._chunked_topk_numpy_reference(
            queries, candidates, k=3, candidate_labels=candidate_labels
        )

        np.testing.assert_array_equal(faiss_labels, numpy_labels)
        np.testing.assert_allclose(faiss_sim, numpy_sim, atol=1e-5)

    def test_k_larger_than_candidate_count_is_clamped(self):
        rng = np.random.default_rng(2)
        queries = _l2_normalise(rng.normal(size=(4, 6)).astype(np.float32))
        candidates = _l2_normalise(rng.normal(size=(3, 6)).astype(np.float32))

        labels, sim = topk.chunked_topk(queries, candidates, k=10)
        self.assertEqual(labels.shape, (4, 3))
        self.assertEqual(sim.shape, (4, 3))

    def test_chunk_size_does_not_change_the_result(self):
        rng = np.random.default_rng(3)
        queries = _l2_normalise(rng.normal(size=(9, 12)).astype(np.float32))
        candidates = _l2_normalise(rng.normal(size=(300, 12)).astype(np.float32))

        labels_default, sim_default = topk.chunked_topk(queries, candidates, k=4)
        labels_small_chunk, sim_small_chunk = topk.chunked_topk(queries, candidates, k=4, chunk_size=17)

        np.testing.assert_array_equal(labels_default, labels_small_chunk)
        np.testing.assert_allclose(sim_default, sim_small_chunk, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
