"""Track C (research/roadmap.md): the pipeline version switch and the
label space, abstention and conformal sockets.

The v3 guard compares against full responses frozen from the code as it was
before the switch existed (base bf315f7; service/tests/fixtures/v3_full_*.json),
for real SCoPE2 and PBMC240 cells in both label-space modes. When frozen, the
refactored pipeline reproduced them byte for byte. The comparison here allows
float noise of 1e-6 so it holds across machines, and is exact for everything
else: every key, label, abstain reason, label set and count.
"""
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from service import config
from service.pipeline import abstention, calibration, label_space, pipeline, reference
from service.tests.test_golden_fixtures import _load_pbmc240_50, _load_scope2_50

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def assert_same(test, fresh, frozen, where="response"):
    if isinstance(frozen, dict):
        test.assertEqual(sorted(fresh), sorted(frozen), f"{where}: keys changed")
        for key in frozen:
            assert_same(test, fresh[key], frozen[key], f"{where}.{key}")
    elif isinstance(frozen, list):
        test.assertEqual(len(fresh), len(frozen), f"{where}: length changed")
        for i, (a, b) in enumerate(zip(fresh, frozen)):
            assert_same(test, a, b, f"{where}[{i}]")
    elif isinstance(frozen, float):
        test.assertTrue(math.isclose(fresh, frozen, rel_tol=1e-6, abs_tol=1e-7), f"{where}: {fresh} != {frozen}")
    else:
        test.assertEqual(fresh, frozen, where)


class V3IsUnchangedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = pipeline.ReferenceBundle.load()
        cls.raws = {"scope2": _load_scope2_50(), "pbmc240": _load_pbmc240_50()}

    def test_the_default_version_is_v3(self):
        self.assertEqual(config.PIPELINE_VERSION, "v3")

    def test_v3_reproduces_the_responses_frozen_before_the_switch(self):
        for name, raw in self.raws.items():
            for mode, restrict in (("default", False), ("restricted", True)):
                with self.subTest(dataset=name, mode=mode):
                    frozen = json.loads((FIXTURES / f"v3_full_{name}_{mode}.json").read_text())
                    fresh = pipeline.run_projection(self.bundle, raw, restrict_to_supported_classes=restrict)
                    assert_same(self, json.loads(json.dumps(fresh)), frozen)

    def test_a_v3_response_carries_none_of_the_v31_fields(self):
        fresh = pipeline.run_projection(self.bundle, self.raws["scope2"])
        for key in ("pipeline_version", "supported_classes", "calibration"):
            self.assertNotIn(key, fresh)
        self.assertFalse(any("abstain_category" in c for c in fresh["cells"]))

    def test_v31_schema_adds_blocks_and_keeps_every_v3_field(self):
        v3 = pipeline.run_projection(self.bundle, self.raws["pbmc240"])
        fake = pipeline.Components(
            version="v3.1", label_space=_EstimatedLabelSpace(),
            calibrator=_MaskedRnaCalibrator(), abstention=_HiddenReadingScorer(),
        )
        with mock.patch.dict(config.FALLBACK_CONFIDENCE, {"estimated": "within_pair_share"}):
            v31 = pipeline.run_projection(self.bundle, self.raws["pbmc240"], components=fake)

        self.assertTrue(set(v3) <= set(v31), "a v3 field was dropped")
        self.assertEqual(v31["pipeline_version"], "v3.1")
        self.assertEqual(v31["supported_classes"]["method"], "estimated")
        self.assertEqual(v31["supported_classes"]["names"], ["macrophage", "monocyte"])
        self.assertEqual(set(v31["supported_classes"]["support"]), {"macrophage", "monocyte"})
        self.assertEqual(v31["calibration"]["applies_to"], "masked RNA")
        # The abstention scorer asked for the pre-projection features, and got 512 per cell.
        self.assertEqual(fake.abstention.seen_hidden_shape, (50, 512))
        for cell in v31["cells"]:
            self.assertTrue(set(v3["cells"][0]) - {"label", "label_set", "confidence", "abstain_reason"} <= set(cell))
            if cell["abstained"]:
                self.assertIn(cell["abstain_category"], {"no_reference_support", "low_coverage", "ambiguous"})
                self.assertIn("abstain_reason", cell)
            else:
                self.assertNotIn("abstain_category", cell)
                self.assertIn(cell["label"], {"macrophage", "monocyte", "monocyte/macrophage lineage"})


class _EstimatedLabelSpace:
    """Stands in for NB2's estimator: two classes, each with a support score."""

    def estimate(self, query_embeddings, class_names, restrict):
        positions = {class_names.index("macrophage"), class_names.index("monocyte")}
        return label_space.LabelSpace(positions=positions, support={p: 0.5 for p in positions}, method="estimated")


class _MaskedRnaCalibrator(calibration.V3ConformalCalibrator):
    def describe(self, result):
        return {**super().describe(result), "applies_to": "masked RNA"}


class _HiddenReadingScorer(abstention.V3AbstentionScorer):
    needs_hidden = True
    seen_hidden_shape = None

    def score(self, **kwargs):
        type(self).seen_hidden_shape = kwargs["hidden_features"].shape
        return super().score(**kwargs)


class ComponentSelectionTests(unittest.TestCase):
    def test_v3_components_are_todays(self):
        c = pipeline.components_for("v3")
        self.assertIsInstance(c.label_space, label_space.V3LabelSpace)
        self.assertIsInstance(c.calibrator, calibration.V3ConformalCalibrator)
        self.assertIsInstance(c.abstention, abstention.V3AbstentionScorer)
        self.assertFalse(c.abstention.needs_hidden)

    def test_an_unknown_version_is_refused(self):
        with self.assertRaises(ValueError):
            pipeline.components_for("v4")

    def test_v31_without_its_artifacts_is_pending_and_names_the_notebook(self):
        with tempfile.TemporaryDirectory() as empty, _v31_paths(Path(empty)):
            with self.assertRaises(reference.PendingArtifactError) as caught:
                pipeline.components_for("v3.1")
        self.assertIn("T1 NB2", str(caught.exception))

    def test_v31_with_its_artifacts_still_refuses_until_track_f(self):
        with tempfile.TemporaryDirectory() as tmp, _v31_paths(Path(tmp)) as paths:
            for key in ("label_space_config", "bcts_params", "ood_config"):
                paths[key].write_text("{}")
            np.save(paths["ood_reference_index"], np.zeros((2, 512), np.float16))
            np.savez(paths["conformal_calibration"], qhat=np.zeros(22))
            with self.assertRaises(NotImplementedError) as caught:
                pipeline.components_for("v3.1")
        self.assertIn("Track F", str(caught.exception))


class _v31_paths:
    """Points every v3.1 artifact path into one directory for a test."""

    NAMES = {
        "label_space_config": ("V31_LABEL_SPACE_CONFIG_PATH", "label_space_config.json"),
        "bcts_params": ("V31_BCTS_PARAMS_PATH", "bcts_params.json"),
        "ood_config": ("V31_OOD_CONFIG_PATH", "ood_config.json"),
        "ood_reference_index": ("V31_OOD_REFERENCE_INDEX_PATH", "ood_reference_index.npy"),
        "conformal_calibration": ("V31_CONFORMAL_CALIBRATION_PATH", "conformal_calibration.npz"),
    }

    def __init__(self, directory: Path):
        self.paths = {key: directory / name for key, (_, name) in self.NAMES.items()}
        self.patches = [mock.patch.object(config, attr, self.paths[key]) for key, (attr, _) in self.NAMES.items()]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self.paths

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


class V3LabelSpaceTests(unittest.TestCase):
    def test_every_class_by_default_and_the_supported_ones_on_request(self):
        names = ["b cell", "macrophage", "monocyte", "neutrophil"]
        everything = label_space.V3LabelSpace().estimate(None, names, restrict=False)
        self.assertIsNone(everything.positions)
        self.assertEqual(everything.method, "all_classes")
        restricted = label_space.V3LabelSpace().estimate(None, names, restrict=True)
        self.assertEqual(restricted.positions, {1, 2})
        self.assertEqual(restricted.method, "cross_modal_supported")
        self.assertIsNone(restricted.support, "v3 has no support score to report")

    def test_every_v3_label_space_method_has_a_fallback_rule(self):
        for method in ("all_classes", "cross_modal_supported"):
            self.assertIn(config.FALLBACK_CONFIDENCE[method], ("within_pair_share", "pair_mass"))


class AbstainCategoryTests(unittest.TestCase):
    def test_every_abstain_reason_maps_to_one_of_the_three_categories(self):
        for reason in abstention.AbstainReason:
            if reason is abstention.AbstainReason.NONE:
                continue
            self.assertIn(reason, abstention.CATEGORY_BY_REASON)


if __name__ == "__main__":
    unittest.main()
