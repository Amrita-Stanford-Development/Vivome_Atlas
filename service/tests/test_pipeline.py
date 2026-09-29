"""End-to-end wiring test: real production checkpoint, real
feature_space_genes.csv, real reference_metadata.csv (85,233 cells, 22
classes), real provenance.json — plus synthetic reference_embeddings/
centroids/properties at that same real scale, kept synthetic so these tests
stay fast, deterministic, and independent of which checkpoint happens to be
staged (see service/tests/fixtures.py).

This does not attempt to force a Stage 7 hierarchical-fallback resolution
through the full stack: doing that deterministically would mean either
mocking the real encoder (defeating the point of an end-to-end test) or
accepting a flaky test that depends on where an opaque trained network
happens to place a crafted input relative to synthetic centroids. Stage 7's
resolution logic itself is covered directly and exhaustively in
test_fallback.py; what this test verifies is that the orchestrator wires
Stages 1-8 into a response matching docs/service/projection-api.md's schema.
"""
import unittest
from unittest.mock import patch

import numpy as np

from service.pipeline import alignment, calibration, coordinates, encoder, pipeline, reference
from service.pipeline.reference import ReferenceClass, ReferenceMetadata
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
            reference_class_positions=cls.metadata.class_positions_by_cell(),
            pca=cls.pca, property_names=cls.property_names, property_values=cls.property_values,
            provenance=reference.load_provenance(),
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

    def test_model_version_is_labelled_production(self):
        result = self._run()
        self.assertEqual(result["model_version"], "production")

    def test_response_reports_gene_id_resolution(self):
        result = self._run()
        resolution = result["gene_id_resolution"]
        for key in ("matched", "unmapped", "ambiguous", "unmapped_identifiers", "ambiguous_identifiers"):
            self.assertIn(key, resolution)
        self.assertEqual(resolution["matched"], 200)  # matches n_features_matched for this fixture's real symbols
        self.assertEqual(resolution["unmapped"], 2)  # matches n_features_unmatched: 2 real-looking but absent gene names

    def test_response_carries_the_recorded_reference_abstain_threshold(self):
        result = self._run()
        self.assertAlmostEqual(result["reference_abstain_threshold"], 0.9779149889945984)

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


class FallbackConfidenceTests(unittest.TestCase):
    """A conformal set that resolves via Stage 7 fallback should report the
    winning class's share *within the pair* as confidence — normalised by
    the pair's own probability mass, not assumed to sum to 1.0 — since under
    config.CROSS_MODAL_SUPPORTED_CLASSES restriction the pair's raw sum is
    always ~1.0 by construction and would report identical "confidence" for
    a 50/50 split and a 99/1 split (see pipeline.py's Stage 7 comment).
    Forcing this exact scenario through the real opaque encoder isn't
    practical (see the module docstring), so assignment/calibration/
    abstention are patched to deterministic values here and only
    pipeline.run_projection's own orchestration logic is under test.
    """

    @classmethod
    def setUpClass(cls):
        classes = [
            ReferenceClass(class_idx=0, class_name="macrophage", lineage="myeloid", n_cells=10),
            ReferenceClass(class_idx=1, class_name="monocyte", lineage="myeloid", n_cells=10),
        ]
        cls.metadata = ReferenceMetadata(
            cell_ids=[f"c{i}" for i in range(20)],
            class_idx_by_cell=np.array([0] * 10 + [1] * 10),
            classes=classes,
        )
        cls.encoder_handle = encoder.load_encoder()
        cls.feature_genes = reference.load_feature_space_genes()
        embeddings, centroids = fixtures.synthetic_reference_embeddings(cls.metadata, dim=128, seed=3)
        names, values = fixtures.synthetic_reference_properties(20, seed=3)
        cls.bundle = pipeline.ReferenceBundle(
            encoder_handle=cls.encoder_handle, feature_genes=cls.feature_genes, metadata=cls.metadata,
            reference_embeddings=embeddings, reference_centroids=centroids,
            reference_class_positions=cls.metadata.class_positions_by_cell(),
            pca=coordinates.fit_pca_3d(embeddings), property_names=names, property_values=values,
            provenance=reference.load_provenance(),
        )

    def test_resolved_confidence_is_the_winning_share_within_the_pair(self):
        # 2,000 of 9,002 genes matched (~22% coverage) so the coverage floor
        # doesn't override the scenario this test is actually about.
        matched = self.feature_genes[:2000]
        text = fixtures.synthetic_matrix_csv(matched, ["q0"], seed=3)
        raw = alignment.parse_matrix_csv(text)

        # Deliberately sums to 0.90, not 1.0 — real restricted assignment
        # always sums to ~1.0 (see assignment.py), but the formula must
        # normalise by the pair's own sum rather than assume it, so this
        # proves that rather than merely matching the common case.
        fixed_probs = np.array([[0.55, 0.35]])  # macrophage 0.55, monocyte 0.35
        fixed_calibration = calibration.CalibrationResult(
            qhat=0.5, calibration_indices=np.array([0]), label_sets=[[0, 1]],
        )

        with patch("service.pipeline.assignment.assign_labels", return_value=fixed_probs), \
             patch("service.pipeline.calibration.calibrate_and_build_sets", return_value=fixed_calibration), \
             patch("service.pipeline.abstention.max_cosine_to_reference", return_value=np.array([0.99])):
            result = pipeline.run_projection(self.bundle, raw, rng=np.random.default_rng(3))

        cell = result["cells"][0]
        self.assertFalse(cell["abstained"])
        self.assertEqual(cell["label"], "monocyte/macrophage lineage")
        self.assertAlmostEqual(cell["confidence"], 0.55 / 0.90, places=6)
        self.assertEqual(set(cell["label_set"]), {"macrophage", "monocyte"})

    def test_a_near_even_split_reports_confidence_near_one_half_not_one(self):
        # The regression this fix targets: under real restricted assignment
        # the pair always sums to ~1.0, so the old sum-based confidence
        # would report ~1.0 here even though the model is nearly maximally
        # uncertain between the two classes.
        matched = self.feature_genes[:2000]
        text = fixtures.synthetic_matrix_csv(matched, ["q0"], seed=3)
        raw = alignment.parse_matrix_csv(text)

        fixed_probs = np.array([[0.501, 0.499]])
        fixed_calibration = calibration.CalibrationResult(
            qhat=0.5, calibration_indices=np.array([0]), label_sets=[[0, 1]],
        )

        with patch("service.pipeline.assignment.assign_labels", return_value=fixed_probs), \
             patch("service.pipeline.calibration.calibrate_and_build_sets", return_value=fixed_calibration), \
             patch("service.pipeline.abstention.max_cosine_to_reference", return_value=np.array([0.99])):
            result = pipeline.run_projection(self.bundle, raw, rng=np.random.default_rng(3))

        self.assertAlmostEqual(result["cells"][0]["confidence"], 0.501, places=3)


class NonContiguousClassIdxRegressionTests(unittest.TestCase):
    """Regression guard: assign_labels/top_label/calibrate_and_build_sets all
    work in centroid ROW POSITION, not the dataset's class_idx. The real
    reference happens to have class_idx == range(22), which would silently
    hide a position-vs-class_idx mixup. This reference does not: class_idx
    values are non-contiguous and don't start at 0, so a bug that indexed
    class names by raw position instead of translating through
    metadata.classes' own order would raise KeyError or return the wrong
    label here.

    Two of the four names are "macrophage"/"monocyte" deliberately — real
    names, matching config.CROSS_MODAL_SUPPORTED_CLASSES — so Stage 4's
    restriction has a non-empty allowed set to work with here rather than
    silently restricting to nothing, while still keeping the point-of-this-
    test index-translation intact (class_idx stays non-contiguous, and
    neither of the two real names lands at position 0 or in class_idx order)."""

    @classmethod
    def setUpClass(cls):
        # 4 classes; centroid row order (position 0..3) is ascending by
        # class_idx (10, 20, 30, 40) per the contract, but position != class_idx.
        specs = [(40, "delta"), (10, "macrophage"), (30, "monocyte"), (20, "beta")]
        n_cells_per_class = 20
        cell_ids, class_idx_by_cell = [], []
        for class_idx, name in specs:
            for j in range(n_cells_per_class):
                cell_ids.append(f"{name}_{j}")
                class_idx_by_cell.append(class_idx)
        classes = [
            ReferenceClass(class_idx=idx, class_name=name, lineage="test", n_cells=n_cells_per_class)
            for idx, name in sorted(specs)
        ]
        cls.metadata = ReferenceMetadata(
            cell_ids=cell_ids, class_idx_by_cell=np.array(class_idx_by_cell), classes=classes,
        )
        cls.encoder_handle = encoder.load_encoder()
        cls.feature_genes = reference.load_feature_space_genes()
        cls.reference_embeddings, cls.reference_centroids = fixtures.synthetic_reference_embeddings(
            cls.metadata, dim=128, seed=7,
        )
        cls.property_names, cls.property_values = fixtures.synthetic_reference_properties(len(cell_ids), seed=7)
        cls.bundle = pipeline.ReferenceBundle(
            encoder_handle=cls.encoder_handle, feature_genes=cls.feature_genes, metadata=cls.metadata,
            reference_embeddings=cls.reference_embeddings, reference_centroids=cls.reference_centroids,
            reference_class_positions=cls.metadata.class_positions_by_cell(),
            pca=coordinates.fit_pca_3d(cls.reference_embeddings),
            property_names=cls.property_names, property_values=cls.property_values,
            provenance=reference.load_provenance(),
        )

    def test_labels_are_real_class_names_not_a_position_indexing_error(self):
        rng = np.random.default_rng(7)
        matched = list(rng.choice(self.feature_genes, size=500, replace=False))
        cell_ids = [f"q{i}" for i in range(10)]
        text = fixtures.synthetic_matrix_csv(matched, cell_ids, seed=7)
        raw = alignment.parse_matrix_csv(text)

        result = pipeline.run_projection(self.bundle, raw, rng=np.random.default_rng(7))

        known_names = {c.class_name for c in self.metadata.classes}
        for cell in result["cells"]:
            if not cell["abstained"]:
                self.assertIn(cell["label"], known_names)
                for name in cell["label_set"]:
                    self.assertIn(name, known_names)


if __name__ == "__main__":
    unittest.main()
