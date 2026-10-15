"""Tracks C and F (research/roadmap.md): the pipeline version switch, the
label space, abstention and conformal components, and the v3.1 response.

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
import pandas as pd

from service import config
from service.pipeline import abstention, calibration, ensemble, label_space, pipeline, reference
from service.tests.test_golden_fixtures import _load_pbmc240_50, _load_scope2_50

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO = Path(__file__).resolve().parents[2]


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
        # Frozen on the Mac. The Windows PC's BLAS sums float32 in another order,
        # which moves values by at most 2.1e-6 absolute (measured over every field;
        # the coordinates), so the absolute bound is 5e-6 and the relative one
        # stays the original 1e-6. Every label and non-float field stays identical.
        test.assertTrue(math.isclose(fresh, frozen, rel_tol=1e-6, abs_tol=5e-6), f"{where}: {fresh} != {frozen}")
    else:
        test.assertEqual(fresh, frozen, where)


class V3IsUnchangedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = pipeline.ReferenceBundle.load()
        cls.raws = {"scope2": _load_scope2_50(), "pbmc240": _load_pbmc240_50()}

    def test_the_default_version_is_v41_and_v3_stays_selectable(self):
        self.assertEqual(config.PIPELINE_VERSION, "v4.1")
        self.assertIn("v3", config.PIPELINE_VERSIONS)
        self.assertIsInstance(pipeline.load_bundle("v3"), pipeline.ReferenceBundle)

    def test_v3_reproduces_the_responses_frozen_before_the_switch(self):
        for name, raw in self.raws.items():
            for mode, restrict in (("default", False), ("restricted", True)):
                with self.subTest(dataset=name, mode=mode):
                    frozen = json.loads((FIXTURES / f"v3_full_{name}_{mode}.json").read_text())
                    # Compared under the release number they were frozen with:
                    # the version moves with every release, v3's behaviour must not.
                    with mock.patch.object(config, "ATLAS_VERSION", frozen["atlas_version"]):
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


class V31IsUnchangedTests(unittest.TestCase):
    """v3.1 frozen the same way before v4 work began (2026-10-04;
    service/tests/fixtures/v31_full_*.json), so a later pipeline version cannot
    move a v3.1 answer unnoticed."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.bundle = pipeline.load_bundle("v3.1")
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/fetch_v31_members.py.")
        cls.raws = {"scope2": _load_scope2_50(), "pbmc240": _load_pbmc240_50()}

    def test_v31_reproduces_its_frozen_responses(self):
        for name, raw in self.raws.items():
            for mode, restrict in (("default", False), ("restricted", True)):
                with self.subTest(dataset=name, mode=mode):
                    frozen = json.loads((FIXTURES / f"v31_full_{name}_{mode}.json").read_text())
                    with mock.patch.object(config, "ATLAS_VERSION", frozen["atlas_version"]):
                        fresh = pipeline.run_projection(self.bundle, raw, restrict_to_supported_classes=restrict)
                    assert_same(self, json.loads(json.dumps(fresh)), frozen)


class V4IsUnchangedTests(unittest.TestCase):
    """v4 frozen the same way when its evaluation passed (2026-10-05, Track G
    Phase 3c; service/tests/fixtures/v4_full_*.json). Both 50-cell uploads fall
    below the agreement threshold, so these pin the flat-correlation branch;
    test_v4_gate.py pins the fused one, on Fulcher."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.bundle = pipeline.load_bundle("v4")
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/fetch_v31_members.py and scripts/build_v4_bundle.py.")
        cls.raws = {"scope2": _load_scope2_50(), "pbmc240": _load_pbmc240_50()}

    def test_v4_is_selectable_and_not_the_default(self):
        self.assertIn("v4", config.PIPELINE_VERSIONS)
        self.assertEqual(config.PIPELINE_VERSION, "v4.1")

    def test_v4_reproduces_its_frozen_responses(self):
        for name, raw in self.raws.items():
            for mode, restrict in (("default", False), ("restricted", True)):
                with self.subTest(dataset=name, mode=mode):
                    frozen = json.loads((FIXTURES / f"v4_full_{name}_{mode}.json").read_text())
                    with mock.patch.object(config, "ATLAS_VERSION", frozen["atlas_version"]):
                        fresh = pipeline.run_projection(self.bundle, raw, restrict_to_supported_classes=restrict)
                    assert_same(self, json.loads(json.dumps(fresh)), frozen)

    def test_v41_where_its_correlation_term_is_flat_answers_exactly_as_v4(self):
        """v4.1 changes only the encoder's weight where the correlation term is
        used; both 50-cell uploads fall below the gate, so every field but the
        two version labels must be v4's."""
        from service.pipeline import fusion
        try:
            v41 = fusion.V4Bundle.load(require_evaluation=False, version="v4.1")
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/build_v41_spec.py.")
        self.assertIn("v4.1", config.PIPELINE_VERSIONS)
        for name, raw in self.raws.items():
            with self.subTest(dataset=name):
                ours, theirs = (json.loads(json.dumps(pipeline.run_projection(b, raw))) for b in (v41, self.bundle))
                self.assertEqual(ours["best_guess_rule"]["correlation_term"], "flat")
                self.assertEqual((ours.pop("pipeline_version"), theirs.pop("pipeline_version")), ("v4.1", "v4"))
                self.assertNotEqual(ours.pop("model_version"), theirs.pop("model_version"))
                assert_same(self, ours, theirs)

    def test_v4s_answers_are_v31s_with_its_guess_joined(self):
        v31 = pipeline.load_bundle("v3.1")
        for name, raw in self.raws.items():
            ours, theirs = pipeline.run_projection(self.bundle, raw), pipeline.run_projection(v31, raw)
            for a, b in zip(ours["cells"], theirs["cells"]):
                with self.subTest(dataset=name, cell=a["cell_id"]):
                    self.assertEqual(a.get("abstain_reason") == "outside_supported_region",
                                     b.get("abstain_reason") == "outside_supported_region")
                    self.assertEqual(a["coordinates"], b["coordinates"])
                    if not a["abstained"]:
                        self.assertIn(a["best_guess"]["label"], a["label_set"])
                    if not b["abstained"] and not a["abstained"]:
                        self.assertTrue(set(b["label_set"]) <= set(a["label_set"]))


class V41IsUnchangedTests(unittest.TestCase):
    """v4.1 frozen when its evaluation passed (2026-10-07, Track G v4.1 Phase C;
    service/tests/fixtures/v41_full_*.json). Both 50-cell uploads fall below
    the agreement threshold, so these pin the branch v4.1 shares with v4;
    test_v41_gate.py pins the branch where its weight differs, on Fulcher."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.bundle = pipeline.load_bundle("v4.1")
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/build_v41_spec.py.")
        cls.raws = {"scope2": _load_scope2_50(), "pbmc240": _load_pbmc240_50()}

    def test_v41_is_the_default_since_release_040(self):
        self.assertIn("v4.1", config.PIPELINE_VERSIONS)
        self.assertEqual(config.PIPELINE_VERSION, "v4.1")
        self.assertEqual(config.ATLAS_VERSION, "0.4.0")
        self.assertEqual(pipeline.load_bundle(config.PIPELINE_VERSION).pipeline_version, "v4.1")

    def test_v41_reproduces_its_frozen_responses(self):
        for name, raw in self.raws.items():
            for mode, restrict in (("default", False), ("restricted", True)):
                with self.subTest(dataset=name, mode=mode):
                    frozen = json.loads((FIXTURES / f"v41_full_{name}_{mode}.json").read_text())
                    with mock.patch.object(config, "ATLAS_VERSION", frozen["atlas_version"]):
                        fresh = pipeline.run_projection(self.bundle, raw, restrict_to_supported_classes=restrict)
                    assert_same(self, json.loads(json.dumps(fresh)), frozen)


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
            pipeline.components_for("v9")

    def test_v5_versions_are_refused_until_their_evaluation_passes(self):
        """v5, v5.1 and v5.2 (Track H) are selectable, but the service serves
        one only once its spec records a passed evaluation; until then it
        answers 503. A version whose data files are not built here is skipped."""
        from service.pipeline import fusion
        checked = 0
        for version, (base, _, spec_name) in config.V5_FAMILY.items():
            with self.subTest(version=version):
                self.assertIn(version, config.PIPELINE_VERSIONS)
                if not (base / "members").exists():
                    continue  # gitignored data, rebuilt by research/notebooks/v5_build.py
                spec = json.loads((base / spec_name).read_text(encoding="utf-8"))
                if spec["evaluation"]["status"] == "passed":
                    continue
                with self.assertRaises(reference.PendingArtifactError):
                    pipeline.load_bundle(version)
                self.assertEqual(fusion.V4Bundle.load(require_evaluation=False, version=version).pipeline_version, version)
                checked += 1
        if not checked:
            raise unittest.SkipTest("no v5 version's data files are built here; run research/notebooks/v5_build.py")

    def test_v31_components_carry_nb2s_settings(self):
        spec = ensemble.load_spec()
        c = pipeline.components_for("v3.1")
        self.assertIsInstance(c.label_space, label_space.V31LabelSpace)
        self.assertIsInstance(c.calibrator, calibration.MondrianCalibrator)
        self.assertIsInstance(c.abstention, abstention.V31AbstentionScorer)
        self.assertEqual(c.calibrator.qhat.tolist(), [spec["conformal"]["qhat_by_class"][n] for n in spec["class_order"]])
        self.assertEqual(c.abstention.threshold, spec["ood"]["threshold"])
        self.assertEqual(c.abstention.min_observed_genes, spec["preprocessing"]["min_observed_genes"])

    def test_v31_without_its_manifest_is_pending(self):
        with tempfile.TemporaryDirectory() as empty, \
                mock.patch.object(config, "V31_MANIFEST_PATH", Path(empty) / "MANIFEST.json"):
            with self.assertRaises(reference.PendingArtifactError):
                pipeline.load_bundle("v3.1")

    def test_a_v31_file_missing_or_changed_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "a.npy").write_bytes(b"what NB2 exported")
            manifest = tmp / "MANIFEST.json"
            with mock.patch.object(config, "V31_DIR", tmp), mock.patch.object(config, "V31_MANIFEST_PATH", manifest):
                manifest.write_text(json.dumps({"files": {"b.pt": {"sha256": "0" * 64}}}))
                with self.assertRaises(reference.PendingArtifactError):
                    pipeline.load_bundle("v3.1")
                manifest.write_text(json.dumps({"files": {"a.npy": {"sha256": "0" * 64}}}))
                with self.assertRaisesRegex(reference.PendingArtifactError, "sha256"):
                    pipeline.load_bundle("v3.1")


class V31ResponseTests(unittest.TestCase):
    """The v3.1 response on real cells: every v3 field kept, plus the
    hierarchical label and the best guess (docs/service/projection-api.md)."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.bundle = pipeline.load_bundle("v3.1")
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/fetch_v31_members.py.")
        cls.v3_bundle = pipeline.ReferenceBundle.load()
        cls.raw = _load_pbmc240_50()

    def test_every_v3_field_is_kept_and_the_v31_ones_added(self):
        v3 = pipeline.run_projection(self.v3_bundle, self.raw)
        v31 = pipeline.run_projection(self.bundle, self.raw)
        self.assertTrue(set(v3) <= set(v31), "a v3 field was dropped")
        self.assertEqual(v31["pipeline_version"], "v3.1")
        self.assertEqual(v31["supported_classes"]["method"], "none")
        self.assertEqual(v31["calibration"]["n_calibration_cells"], 0)
        v3_cell_keys = set(v3["cells"][0]) - {"abstain_reason"}
        for cell in v31["cells"]:
            self.assertTrue(v3_cell_keys <= set(cell))
            self.assertEqual(len(cell["coordinates"]), 3)
            self.assertIsInstance(cell["reference_similarity"], float)
            if cell["abstained"]:
                self.assertIsNone(cell["label_level"])
                self.assertIn(cell["abstain_category"], {"no_reference_support", "low_coverage", "ambiguous"})
            else:
                self.assertIn(cell["label_level"], {"class", "group", "lineage"})
                self.assertTrue(cell["label_set"])
            if cell.get("abstain_reason") == "coverage_too_low":
                self.assertNotIn("best_guess", cell)
            else:
                self.assertIn(cell["best_guess"]["label"], self.bundle.class_names)
                self.assertTrue(0 < cell["best_guess"]["probability"] <= 1)

    def test_the_sites_atlas_is_the_services_coordinate_space(self):
        """A projected cell lands on the displayed atlas: web/data's RNA PCs are
        this bundle's PCA of the coordinate member's latents
        (scripts/export_atlas_coordinates.py), with a fixed sign."""
        anchor = self.bundle.members[self.bundle.coordinate_member]
        rows = pd.read_csv(REPO / "web" / "data" / "metadata_RNA_lat128.csv", usecols=["PC1", "PC2", "PC3"])
        sample = np.arange(0, len(rows), 997)
        expected = self.bundle.pca.project(anchor.reference_latents[sample])
        np.testing.assert_allclose(rows.to_numpy()[sample], expected, atol=1e-5)
        components = self.bundle.pca.components
        self.assertTrue((components[np.arange(3), np.abs(components).argmax(axis=1)] > 0).all())

    def test_a_restricted_request_keeps_every_answer_inside_the_supported_classes(self):
        v31 = pipeline.run_projection(self.bundle, self.raw, restrict_to_supported_classes=True)
        supported = set(v31["supported_classes"]["names"])
        self.assertLess(len(supported), len(self.bundle.class_names))
        for cell in v31["cells"]:
            self.assertTrue(set(cell["label_set"]) <= supported)
            if "best_guess" in cell:
                self.assertIn(cell["best_guess"]["label"], supported)


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
