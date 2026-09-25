import unittest
import warnings

import numpy as np
import torch

from service import config
from service.pipeline import encoder


class StripPrefixesTests(unittest.TestCase):
    def test_bare_dev_checkpoint_keys_pass_through_unchanged(self):
        state_dict = {"A": 1, "body.0.weight": 2}
        self.assertEqual(encoder._strip_prefixes(state_dict), state_dict)

    def test_encoder_prefix_stripped_and_classifier_keys_dropped(self):
        state_dict = {"encoder.A": 1, "encoder.body.0.weight": 2, "classifier.weight": 99}
        stripped = encoder._strip_prefixes(state_dict)
        self.assertEqual(stripped, {"A": 1, "body.0.weight": 2})


class LoadEncoderRealProductionCheckpointTests(unittest.TestCase):
    """Exercises the real v3 production checkpoint end to end — this is
    the actual artifact the pipeline runs against today."""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cls.handle = encoder.load_encoder()
            cls.dev_warnings = caught

    def test_loads_the_production_reference_and_does_not_warn(self):
        self.assertFalse(self.handle.is_dev_placeholder)
        self.assertEqual(self.handle.weights_path, config.REFERENCE_MODEL_PATH)
        self.assertFalse(any("DEVELOPMENT placeholder" in str(w.message) for w in self.dev_warnings))

    def test_model_version_label_says_production(self):
        label = encoder.model_version_label(self.handle)
        self.assertEqual(label, encoder.MODEL_VERSION_LABEL_PRODUCTION)

    def test_encode_returns_l2_normalised_embeddings(self):
        n_genes = self.handle.model.A.shape[0]
        rng = np.random.default_rng(0)
        values = rng.normal(size=(4, n_genes)).astype(np.float32)
        mask = (rng.random((4, n_genes)) > 0.7).astype(np.float32)
        out = self.handle.encode(values, mask)
        self.assertEqual(out.shape, (4, self.handle.model.proj.out_features))
        np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)

    def test_all_missing_row_does_not_produce_nan(self):
        n_genes = self.handle.model.A.shape[0]
        out = self.handle.encode(np.zeros((1, n_genes), dtype=np.float32), np.zeros((1, n_genes), dtype=np.float32))
        self.assertFalse(np.isnan(out).any())

    def test_body_uses_gelu_not_relu(self):
        # Regression guard: the trained checkpoint (VivOME_Prototype_Export.ipynb's
        # ModulePoolEnc) uses GELU. An earlier version of this file used ReLU
        # instead -- load_state_dict(strict=True) doesn't catch this, since
        # activations carry no parameters, so the encoder silently loaded
        # real weights into the wrong architecture and produced embeddings
        # that only reached ~0.75 cosine similarity to the real ones instead
        # of the exact match a correct architecture gives. See
        # Documentation/bugs-and-fixes.md.
        import torch.nn as nn
        activations = [m for m in self.handle.model.body if isinstance(m, (nn.GELU, nn.ReLU))]
        self.assertTrue(activations, "expected at least one activation layer in body")
        self.assertTrue(all(isinstance(m, nn.GELU) for m in activations),
                         f"expected GELU, found {[type(m).__name__ for m in activations]}")

    def test_encode_is_deterministic_in_eval_mode(self):
        n_genes = self.handle.model.A.shape[0]
        rng = np.random.default_rng(0)
        values = rng.normal(size=(2, n_genes)).astype(np.float32)
        mask = (rng.random((2, n_genes)) > 0.5).astype(np.float32)
        out1 = self.handle.encode(values, mask)
        out2 = self.handle.encode(values, mask)
        np.testing.assert_array_equal(out1, out2)


class TorchScriptExportEquivalenceTests(unittest.TestCase):
    """Track B, "Serving": the traced (TorchScript) model that `.encode()`
    actually runs must match the eager model within the spec's 1e-5
    tolerance on 1,000 cells."""

    @classmethod
    def setUpClass(cls):
        cls.handle = encoder.load_encoder()

    def test_traced_model_matches_eager_model_on_1000_cells(self):
        n_genes = self.handle.model.A.shape[0]
        rng = np.random.default_rng(0)
        values = rng.normal(size=(1000, n_genes)).astype(np.float32)
        mask = (rng.random((1000, n_genes)) > 0.3).astype(np.float32)

        with torch.no_grad():
            eager_out = self.handle.model(torch.as_tensor(values), torch.as_tensor(mask)).numpy()
            traced_out = self.handle.traced_model(torch.as_tensor(values), torch.as_tensor(mask)).numpy()

        max_abs_diff = np.max(np.abs(eager_out - traced_out))
        self.assertLess(max_abs_diff, 1e-5)

    def test_encode_runs_through_the_traced_model(self):
        n_genes = self.handle.model.A.shape[0]
        rng = np.random.default_rng(1)
        values = rng.normal(size=(3, n_genes)).astype(np.float32)
        mask = (rng.random((3, n_genes)) > 0.5).astype(np.float32)

        via_encode = self.handle.encode(values, mask)
        with torch.no_grad():
            via_traced = self.handle.traced_model(torch.as_tensor(values), torch.as_tensor(mask)).numpy()

        np.testing.assert_array_equal(via_encode, via_traced)


class LoadEncoderDevPlaceholderTests(unittest.TestCase):
    """The dev checkpoint is no longer ENCODER_WEIGHTS_PATH's default, but
    the warn-path guard must still fire for anything that explicitly points
    at it (e.g. a VIVOME_ENCODER_WEIGHTS override for local testing)."""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cls.handle = encoder.load_encoder(weights_path=config.DEV_CHECKPOINT_PATH)
            cls.dev_warnings = caught

    def test_loads_as_the_dev_placeholder_and_warns(self):
        self.assertTrue(self.handle.is_dev_placeholder)
        self.assertEqual(self.handle.weights_path, config.DEV_CHECKPOINT_PATH)
        self.assertTrue(any("DEVELOPMENT placeholder" in str(w.message) for w in self.dev_warnings))

    def test_model_version_label_says_development_not_production(self):
        label = encoder.model_version_label(self.handle)
        self.assertIn("development", label.lower())
        self.assertNotEqual(label, encoder.MODEL_VERSION_LABEL_PRODUCTION)


class UnknownArchitectureFamilyTests(unittest.TestCase):
    def test_unrecognised_encoder_family_raises_clearly(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            bad_config = Path(tmp) / "decisive_summary.json"
            bad_config.write_text(json.dumps({"winner_config": {"enc": "not_a_real_family"}}))
            with self.assertRaises(ValueError):
                encoder.load_encoder(architecture_config_path=bad_config)


if __name__ == "__main__":
    unittest.main()
