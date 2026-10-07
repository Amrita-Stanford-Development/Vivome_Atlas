"""v4's own math and spec checks (service/pipeline/fusion.py)."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from benchmark.baselines_corrected import class_balanced_z
from service import config
from service.pipeline import calibration, fusion, label_space, reference

CLASSES = [f"class {k}" for k in range(4)]


def spec(**over):
    base = {
        "version": "v4", "class_order": CLASSES,
        "preprocessing": {"convention": "service", "smoothing": True, "min_observed_genes": 200},
        "answers": {"from": "v3.1"},
        "best_guess": {"rule": "fusion", "temperature": {"a.pt": 0.15, config.V31_COORDINATE_MEMBER: 0.15},
                       "fusion_weight": 0.7, "correlation_temperature": 0.05, "smoothed_share": 0.5,
                       "agreement_threshold": 0.4},
        "label_space": {"method": "none"},
        "encoder": {"members": ["a.pt", config.V31_COORDINATE_MEMBER]},
        "evaluation": {"status": "passed"},
    }
    for path, value in over.items():
        node = base
        keys = path.split(".")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value
    return base


class ClassBalancedStatisticsTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.y = np.repeat([0, 1, 2], [500, 50, 5])
        self.X = rng.normal(self.y[:, None] * 2.0, 1.0, size=(len(self.y), 30)).astype(np.float32)

    def test_it_matches_the_corrected_baselines_scaling(self):
        mu, sd = fusion.class_balanced_stats(self.X, self.y, 3)
        np.testing.assert_allclose((self.X - mu) / (sd + 1e-8), class_balanced_z(self.X, self.y), atol=2e-5)

    def test_duplicating_one_class_changes_nothing(self):
        twice = np.r_[self.X, self.X[self.y == 1]]
        mu, sd = fusion.class_balanced_stats(self.X, self.y, 3)
        mu2, sd2 = fusion.class_balanced_stats(twice, np.r_[self.y, self.y[self.y == 1]], 3)
        np.testing.assert_allclose(mu, mu2, atol=1e-5)
        np.testing.assert_allclose(sd, sd2, atol=1e-5)

    def test_an_empty_class_takes_no_weight(self):
        with_empty = fusion.class_balanced_stats(self.X, self.y, 4)
        without = fusion.class_balanced_stats(self.X, self.y, 3)
        np.testing.assert_allclose(with_empty[0], without[0], atol=1e-6)

    def test_class_means_are_the_mean_z_profile_per_class(self):
        mu, sd = fusion.class_balanced_stats(self.X, self.y, 3)
        means = fusion.class_means(self.X, self.y, 3, mu, sd)
        np.testing.assert_allclose(means[2], ((self.X[self.y == 2] - mu) / (sd + 1e-8)).mean(0), atol=1e-5)


class MaskedPearsonTests(unittest.TestCase):
    def test_it_equals_corrcoef_over_each_cells_observed_genes(self):
        rng = np.random.default_rng(1)
        values = rng.normal(size=(20, 40))
        mask = (rng.random((20, 40)) < 0.5).astype(np.float32)
        values = values * mask
        means = rng.normal(size=(4, 40))
        r = fusion.masked_pearson(values, mask, means)
        for i in range(20):
            o = mask[i] > 0
            for k in range(4):
                self.assertAlmostEqual(r[i, k], np.corrcoef(values[i, o], means[k, o])[0, 1], places=8)

    def test_unobserved_values_are_ignored(self):
        rng = np.random.default_rng(2)
        mask = np.ones((1, 10), np.float32)
        mask[0, :3] = 0
        values = rng.normal(size=(1, 10))
        noisy = values.copy()
        noisy[0, :3] = 99.0
        means = rng.normal(size=(3, 10))
        np.testing.assert_allclose(fusion.masked_pearson(values * mask, mask, means), fusion.masked_pearson(noisy, mask, means))

    def test_degenerate_cells_get_zero(self):
        means = np.random.default_rng(3).normal(size=(3, 5))
        one_gene = np.zeros((1, 5)); one_gene[0, 0] = 1.0
        flat = np.ones((1, 5))
        r = fusion.masked_pearson(np.r_[one_gene, flat], np.r_[(one_gene > 0).astype(float), np.ones((1, 5))], means)
        np.testing.assert_array_equal(r, 0.0)


class FusionTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(4)
        e = rng.random((6, 4)); self.enc = e / e.sum(1, keepdims=True)
        self.corr = fusion.correlation_probabilities(rng.uniform(-1, 1, (6, 4)), 0.05)

    def test_rows_sum_to_one(self):
        np.testing.assert_allclose(self.corr.sum(1), 1.0)
        np.testing.assert_allclose(fusion.fused_probabilities(self.enc, self.corr, 0.7).sum(1), 1.0)

    def test_the_endpoints(self):
        np.testing.assert_allclose(fusion.fused_probabilities(self.enc, self.corr, 1.0), self.enc)
        np.testing.assert_allclose(fusion.fused_probabilities(self.enc, self.corr, 0.0), self.corr)

    def test_the_smoothing_mix_and_its_endpoints(self):
        on, off = self.enc, self.corr
        np.testing.assert_allclose(fusion.mixed_encoder_probabilities(on, off, 1.0), on)
        np.testing.assert_allclose(fusion.mixed_encoder_probabilities(on, off, 0.0), off)
        np.testing.assert_allclose(fusion.mixed_encoder_probabilities(on, off, 0.5), (on + off) / 2)


class FusedGuessJoinsTheSetTests(unittest.TestCase):
    """v4's answers are v3.1's sets; the fused best guess joins non-empty ones
    beside v3.1's own best guess."""

    def setUp(self):
        self.calibrator = calibration.MondrianCalibrator(np.full(3, 0.5), 0.5, 0.1, "test")
        self.space = label_space.V31LabelSpace().estimate(None, ["a", "b", "c"], False)
        self.probs = np.array([[0.6, 0.3, 0.1], [0.2, 0.2, 0.2]])

    def test_without_a_guess_the_argmax_joins_as_before(self):
        sets = self.calibrator.calibrate(self.probs, None, self.space).label_sets
        self.assertEqual(sets, [[0], []])

    def test_the_given_guess_joins_non_empty_sets_only(self):
        sets = self.calibrator.calibrate(self.probs, None, self.space, guess_positions=np.array([2, 1])).label_sets
        self.assertEqual(sets, [[0, 2], []])

    def test_the_argmax_stays_when_it_is_outside_the_conformal_set(self):
        # class c's bar is low (qhat 0.95), so the set is {c} and the argmax a joins it, as in v3.1;
        # the given guess b joins beside a rather than in its place (Phase 3b's slip, entry 23)
        calibrator = calibration.MondrianCalibrator(np.array([0.5, 0.5, 0.95]), 0.5, 0.1, "test")
        probs = np.array([[0.4, 0.3, 0.3]])
        self.assertEqual(calibrator.calibrate(probs, None, self.space).label_sets, [[0, 2]])
        self.assertEqual(calibrator.calibrate(probs, None, self.space, guess_positions=np.array([1])).label_sets, [[0, 1, 2]])

    def test_the_sets_contain_v31s(self):
        rng = np.random.default_rng(5)
        calibrator = calibration.MondrianCalibrator(rng.uniform(0.3, 0.99, 6), 0.8, 0.1, "test")
        space = label_space.V31LabelSpace().estimate(None, [f"k{i}" for i in range(6)], False)
        p = rng.dirichlet(np.ones(6), 200)
        theirs = calibrator.calibrate(p, None, space).label_sets
        ours = calibrator.calibrate(p, None, space, guess_positions=rng.integers(0, 6, 200)).label_sets
        self.assertTrue(all(set(a) <= set(b) for a, b in zip(theirs, ours)))
        self.assertTrue(all(bool(a) == bool(b) for a, b in zip(theirs, ours)))


class AgreementGateTests(unittest.TestCase):
    """The correlation term is used only in uploads where its top class agrees
    with v3.1's on at least the threshold's share of counted cells."""

    def test_upload_agreement(self):
        r = np.array([[0.9, 0.1], [0.2, 0.8], [0.7, 0.3], [0.1, 0.9]])
        p = np.array([[0.6, 0.4], [0.6, 0.4], [0.6, 0.4], [0.4, 0.6]])
        self.assertAlmostEqual(fusion.upload_agreement(r, p, np.ones(4, bool)), 0.75)
        self.assertAlmostEqual(fusion.upload_agreement(r, p, np.array([True, True, False, False])), 0.5)
        self.assertEqual(fusion.upload_agreement(r, p, np.zeros(4, bool)), 0.0)

    def bundle(self, threshold, gate_on=None):
        rng = np.random.default_rng(6)
        centroids = rng.normal(size=(3, 5))
        smoothed_z, unsmoothed_z = rng.normal(size=(8, 5)), rng.normal(size=(8, 5))
        handle = mock.Mock()
        handle.encode.return_value = unsmoothed_z
        member = SimpleNamespace(encoder_handle=handle, centroids=centroids, temperature=0.15)
        return SimpleNamespace(members=(member,), class_means=rng.normal(size=(3, 40)), fusion_weight=0.7,
                               correlation_temperature=0.05, smoothed_share=0.5, agreement_threshold=threshold,
                               gate_on_fusion_weight=gate_on), smoothed_z

    def inputs(self, b):
        rng = np.random.default_rng(7)
        values = b.class_means[rng.integers(0, 3, 8)] + rng.normal(scale=0.5, size=(8, 40))
        return values, np.ones_like(values), rng.dirichlet(np.ones(3), 8), np.ones(8, bool)

    def test_below_the_threshold_the_correlation_term_is_flat(self):
        b, z = self.bundle(threshold=1.01)
        values, mask, answers, counted = self.inputs(b)
        out = fusion.best_guess_probabilities(b, [z], values, mask, answers, counted)
        on = fusion.ensemble.member_probabilities(z, b.members[0].centroids, 0.15)
        self.assertFalse(out.correlation_used)
        np.testing.assert_allclose(out.probabilities, 0.7 * on + 0.3 / 3)
        np.testing.assert_array_equal(out.probabilities.argmax(1), on.argmax(1))
        b.members[0].encoder_handle.encode.assert_not_called()

    def test_at_the_threshold_the_fusion_applies(self):
        b, z = self.bundle(threshold=0.0)
        values, mask, answers, counted = self.inputs(b)
        out = fusion.best_guess_probabilities(b, [z], values, mask, answers, counted)
        m = b.members[0]
        on = fusion.ensemble.member_probabilities(z, m.centroids, 0.15)
        off = fusion.ensemble.member_probabilities(m.encoder_handle.encode.return_value, m.centroids, 0.15)
        corr = fusion.correlation_probabilities(fusion.masked_pearson(values, mask, b.class_means), 0.05)
        self.assertTrue(out.correlation_used)
        np.testing.assert_allclose(out.probabilities, 0.7 * (0.5 * on + 0.5 * off) + 0.3 * corr)
        self.assertAlmostEqual(out.agreement, fusion.upload_agreement(
            fusion.masked_pearson(values, mask, b.class_means), answers, counted))

    def test_v41s_gate_on_weight_sets_only_the_branch_where_the_term_is_used(self):
        used, z = self.bundle(threshold=0.0, gate_on=0.5)
        values, mask, answers, counted = self.inputs(used)
        m = used.members[0]
        on = fusion.ensemble.member_probabilities(z, m.centroids, 0.15)
        off = fusion.ensemble.member_probabilities(m.encoder_handle.encode.return_value, m.centroids, 0.15)
        corr = fusion.correlation_probabilities(fusion.masked_pearson(values, mask, used.class_means), 0.05)
        np.testing.assert_allclose(fusion.best_guess_probabilities(used, [z], values, mask, answers, counted).probabilities,
                                   0.5 * (0.5 * on + 0.5 * off) + 0.5 * corr)
        flat, z = self.bundle(threshold=1.01, gate_on=0.5)
        np.testing.assert_allclose(fusion.best_guess_probabilities(flat, [z], values, mask, answers, counted).probabilities,
                                   0.7 * on + 0.3 / 3)

    def test_without_the_field_the_used_branch_keeps_fusion_weight(self):
        self.assertEqual(fusion.encoder_weight_where_used(SimpleNamespace(fusion_weight=0.7)), 0.7)
        self.assertEqual(fusion.encoder_weight_where_used(SimpleNamespace(fusion_weight=0.7, gate_on_fusion_weight=None)), 0.7)
        self.assertEqual(fusion.encoder_weight_where_used(SimpleNamespace(fusion_weight=0.7, gate_on_fusion_weight=0.5)), 0.5)


class SpecTests(unittest.TestCase):
    def test_a_complete_spec_passes(self):
        fusion.validate_spec(spec(), CLASSES)

    def test_a_v41_spec_passes_as_v41_only(self):
        v41 = spec(**{"version": "v4.1", "best_guess.gate_on_fusion_weight": 0.5})
        fusion.validate_spec(v41, CLASSES, version="v4.1")
        for wrong, version in ((v41, "v4"), (spec(), "v4.1")):
            with self.subTest(version=version), self.assertRaises(ValueError):
                fusion.validate_spec(wrong, CLASSES, version=version)
        with self.assertRaises(ValueError):
            fusion.validate_spec(spec(**{"version": "v4.1", "best_guess.gate_on_fusion_weight": 1.5}), CLASSES, version="v4.1")

    def test_refusals(self):
        for path, value in (("preprocessing.smoothing", False), ("best_guess.fusion_weight", 1.5),
                            ("best_guess.correlation_temperature", 0), ("version", "v3.1"),
                            ("best_guess.rule", "centroid"), ("answers.from", "v4"),
                            ("best_guess.smoothed_share", 1.5), ("best_guess.smoothed_share", None),
                            ("best_guess.agreement_threshold", 1.5), ("best_guess.agreement_threshold", None),
                            ("evaluation.status", "failed")):
            with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                fusion.validate_spec(spec(**{path: value}), CLASSES)

    def test_unevaluated_specs_pass_only_for_the_evaluation(self):
        pending = spec(**{"evaluation.status": "pending"})
        fusion.validate_spec(pending, CLASSES, require_evaluation=False)
        with self.assertRaises(ValueError):
            fusion.validate_spec(pending, CLASSES, require_evaluation=True)


class LoadingTests(unittest.TestCase):
    def test_a_missing_manifest_is_pending(self):
        with tempfile.TemporaryDirectory() as empty, \
                mock.patch.object(config, "V4_MANIFEST_PATH", Path(empty) / "MANIFEST.json"):
            with self.assertRaises(reference.PendingArtifactError):
                fusion._verify_manifest()

    def test_a_changed_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "a.npy").write_bytes(b"built")
            manifest = tmp / "MANIFEST.json"
            manifest.write_text(json.dumps({"files": {"a.npy": {"sha256": "0" * 64}}}))
            with mock.patch.object(config, "V4_DIR", tmp), mock.patch.object(config, "V4_MANIFEST_PATH", manifest):
                with self.assertRaisesRegex(reference.PendingArtifactError, "sha256"):
                    fusion._verify_manifest()

    def test_the_served_bundle_is_pending_until_evaluated(self):
        try:
            served_spec = json.loads(config.V4_SPEC_PATH.read_text())
        except FileNotFoundError:
            raise unittest.SkipTest("no v4 bundle on this machine")
        if served_spec.get("evaluation", {}).get("status") == "passed":
            raise unittest.SkipTest("v4's evaluation has passed")
        with self.assertRaises(reference.PendingArtifactError):
            fusion.V4Bundle.load()

    def test_v41s_manifest_pins_v4s_data_files(self):
        if not config.V41_MANIFEST_PATH.exists():
            raise unittest.SkipTest("no v4.1 spec on this machine (scripts/build_v41_spec.py)")
        pinned = json.loads(config.V41_MANIFEST_PATH.read_text())["files"]
        v4 = json.loads(config.V4_MANIFEST_PATH.read_text())["files"]
        self.assertEqual({rel.removeprefix("../v4/") for rel in pinned if rel.startswith("../v4/")}, set(v4) - {"spec_v4.json"})
        for rel, entry in pinned.items():
            if rel.startswith("../v4/"):
                self.assertEqual(entry["sha256"], v4[rel.removeprefix("../v4/")]["sha256"], rel)
        fusion._verify_manifest("v4.1")

    def test_v41_is_pending_until_evaluated(self):
        if not config.V41_SPEC_PATH.exists():
            raise unittest.SkipTest("no v4.1 spec on this machine (scripts/build_v41_spec.py)")
        if json.loads(config.V41_SPEC_PATH.read_text()).get("evaluation", {}).get("status") == "passed":
            raise unittest.SkipTest("v4.1's evaluation has passed")
        with self.assertRaises(reference.PendingArtifactError):
            fusion.V4Bundle.load(version="v4.1")
        self.assertEqual(fusion.V4Bundle.load(require_evaluation=False, version="v4.1").pipeline_version, "v4.1")


if __name__ == "__main__":
    unittest.main()
