"""End-to-end wiring test: real dev checkpoint, real feature_space_genes.csv,
real reference_metadata.csv (85,233 cells, 22 classes) — everything that
exists today — plus synthetic reference_embeddings/centroids/properties at
that same real scale, standing in for the three artifacts still blocked on
the full v3 training run (see service/model/README.md).

This does not attempt to force a Stage 7 hierarchical-fallback resolution
through the full stack: doing that deterministically would mean either
mocking the real encoder (defeating the point of an end-to-end test) or
accepting a flaky test that depends on where an opaque trained network
happens to place a crafted input relative to synthetic centroids. Stage 7's
resolution logic itself is covered directly and exhaustively in
test_fallback.py; what this test verifies is that the orchestrator wires
Stages 1-8 into a response matching docs/projection-service.md's schema.
"""
import unittest

import numpy as np

from service.pipeline import alignment, coordinates, encoder, pipeline, reference
from service.tests import fixtures


class RunProjectionEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoder_handle = encoder.load_encoder()
        cls.feature_genes = reference.load_feature_space_genes()
        cls.metadata = reference.load_reference_metadata()
        cls.reference_embeddings, cls.reference_centroids = fixtures.synthetic_reference_embeddings(cls.metadata)
        cls.property_names, cls.property_values = fixtures.synthetic_reference_properties(len(cls.metadata.cell_ids))
        cls.pca = coordinates.fit_pca_3d(cls.reference_embeddings)

        cls.bundle = pipeline.ReferenceBundle(
            encoder_handle=cls.encoder_handle, feature_genes=cls.feature_genes, metadata=cls.metadata,
            reference_embeddings=cls.reference_embeddings, reference_centroids=cls.reference_centroids,
            pca=cls.pca, property_names=cls.property_names, property_values=cls.property_values,
        )

    def _run(self, n_cells=6, n_matched_genes=200, seed=0):
        rng = np.random.default_rng(seed)
        matched = list(rng.choice(self.feature_genes, size=n_matched_genes, replace=False))
        unmatched = ["NOT_A_REAL_GENE_1", "NOT_A_REAL_GENE_2"]
        cell_ids = [f"cell_{i}" for i in range(n_cells)]
        text = fixtures.synthetic_matrix_csv(matched + unmatched, cell_ids, seed=seed)
        raw = alignment.parse_matrix_csv(text)
        return pipeline.run_projection(self.bundle, raw, rng=np.random.default_rng(seed))

    def test_response_has_the_documented_top_level_shape(self):
        result = self._run()
        for key in ("atlas_version", "n_cells", "n_features_matched", "n_features_unmatched", "cells"):
            self.assertIn(key, result)
        self.assertEqual(result["n_cells"], 6)
        self.assertEqual(result["n_features_unmatched"], 2)
        self.assertEqual(result["n_features_matched"], 200)

    def test_model_version_is_labelled_development_not_production(self):
        result = self._run()
        self.assertIn("development", result["model_version"].lower())

    def test_every_cell_has_a_3d_coordinate_and_a_cell_id(self):
        result = self._run()
        self.assertEqual(len(result["cells"]), 6)
        for i, cell in enumerate(result["cells"]):
            self.assertEqual(cell["cell_id"], f"cell_{i}")
            self.assertEqual(len(cell["coordinates"]), 3)
            self.assertTrue(all(isinstance(x, float) for x in cell["coordinates"]))

    def test_abstained_cells_have_null_label_and_a_reason_non_abstained_do_not_carry_the_key(self):
        result = self._run()
        for cell in result["cells"]:
            if cell["abstained"]:
                self.assertIsNone(cell["label"])
                self.assertEqual(cell["label_set"], [])
                self.assertIsNone(cell["confidence"])
                self.assertIn("abstain_reason", cell)
            else:
                self.assertNotIn("abstain_reason", cell)
                self.assertIsInstance(cell["label"], str)
                self.assertIsInstance(cell["confidence"], float)
                self.assertGreaterEqual(len(cell["label_set"]), 1)

    def test_label_set_contains_class_names_not_raw_indices(self):
        result = self._run()
        known_names = {c.class_name for c in self.metadata.classes}
        for cell in result["cells"]:
            for name in cell["label_set"]:
                self.assertIn(name, known_names)

    def test_properties_are_limited_to_the_shipped_set(self):
        from service import config
        result = self._run()
        for cell in result["cells"]:
            self.assertEqual(set(cell["properties"]), set(config.SHIPPED_PROPERTIES))
            for entry in cell["properties"].values():
                self.assertIn("value", entry)
                self.assertIn("uncertainty", entry)

    def test_a_very_low_coverage_upload_abstains_on_coverage_not_silently_guesses(self):
        result = self._run(n_matched_genes=5)  # ~0.06% of 9002 genes
        self.assertTrue(all(cell["abstained"] for cell in result["cells"]))
        self.assertTrue(all(cell["abstain_reason"] == "coverage_too_low" for cell in result["cells"]))


if __name__ == "__main__":
    unittest.main()
