"""Direct unit coverage for reference.py's loaders — added after a review
found load_reference_properties raising bare exceptions instead of
PendingArtifactError for two real failure modes (missing property_names.json,
mismatched shapes), which test_app.py's HTTP-level test cannot see since it
only forces the error via a mock, not a real missing file."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from service.pipeline import reference
from service.pipeline.reference import ReferenceClass, ReferenceMetadata


class LoadReferencePropertiesTests(unittest.TestCase):
    def test_missing_properties_file_raises_pending_artifact_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            names_path = Path(tmp) / "property_names.json"
            names_path.write_text(json.dumps({"property_names": ["a", "b"]}))
            with self.assertRaises(reference.PendingArtifactError):
                reference.load_reference_properties(
                    path=Path(tmp) / "does_not_exist.npy", names_path=names_path,
                )

    def test_missing_names_file_raises_pending_artifact_error_not_bare_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            values_path = Path(tmp) / "reference_properties.npy"
            np.save(values_path, np.zeros((3, 2), dtype=np.float32))
            with self.assertRaises(reference.PendingArtifactError):
                reference.load_reference_properties(
                    path=values_path, names_path=Path(tmp) / "does_not_exist.json",
                )

    def test_shape_mismatch_raises_pending_artifact_error_not_bare_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            values_path = Path(tmp) / "reference_properties.npy"
            names_path = Path(tmp) / "property_names.json"
            np.save(values_path, np.zeros((3, 2), dtype=np.float32))
            names_path.write_text(json.dumps({"property_names": ["a", "b", "c"]}))
            with self.assertRaises(reference.PendingArtifactError):
                reference.load_reference_properties(path=values_path, names_path=names_path)

    def test_matching_files_load_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            values_path = Path(tmp) / "reference_properties.npy"
            names_path = Path(tmp) / "property_names.json"
            np.save(values_path, np.ones((3, 2), dtype=np.float32))
            names_path.write_text(json.dumps({"property_names": ["a", "b"]}))
            names, values = reference.load_reference_properties(path=values_path, names_path=names_path)
            self.assertEqual(names, ["a", "b"])
            self.assertEqual(values.shape, (3, 2))


class ClassPositionsByCellTests(unittest.TestCase):
    """The single source for the class_idx -> centroid-row-position
    translation — previously reimplemented independently in
    ReferenceBundle.load() and two test files (service/README.md's
    "Known sharp edges" warns about exactly this kind of drift risk)."""

    def test_non_contiguous_class_idx_translates_to_position_by_sorted_order(self):
        # class_idx {10, 20, 30, 40}, non-contiguous and not starting at 0,
        # so position == class_idx nowhere — classes must be constructed
        # pre-sorted by class_idx, per ReferenceMetadata's own contract
        # (load_reference_metadata always does this; this test proves the
        # method trusts that contract rather than re-sorting defensively).
        specs = [(40, "delta"), (10, "alpha"), (30, "gamma"), (20, "beta")]
        classes = [
            ReferenceClass(class_idx=idx, class_name=name, lineage="x", n_cells=1)
            for idx, name in sorted(specs)
        ]
        metadata = ReferenceMetadata(
            cell_ids=["c0", "c1", "c2", "c3"],
            class_idx_by_cell=np.array([40, 10, 30, 20]),
            classes=classes,
        )
        # sorted by class_idx: 10->pos0, 20->pos1, 30->pos2, 40->pos3
        np.testing.assert_array_equal(metadata.class_positions_by_cell(), [3, 0, 2, 1])


if __name__ == "__main__":
    unittest.main()
