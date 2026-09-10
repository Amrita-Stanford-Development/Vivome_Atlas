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


class LoadEncoderRealDevCheckpointTests(unittest.TestCase):
    """Exercises the real dev placeholder checkpoint end to end — this is
    the actual artifact the pipeline runs against today."""

    @classmethod
    def setUpClass(cls):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cls.handle = encoder.load_encoder()
            cls.dev_warnings = caught

    def test_loads_as_the_dev_placeholder_and_warns(self):
        self.assertTrue(self.handle.is_dev_placeholder)
        self.assertEqual(self.handle.weights_path, config.DEV_CHECKPOINT_PATH)
        self.assertTrue(any("DEVELOPMENT placeholder" in str(w.message) for w in self.dev_warnings))

    def test_model_version_label_says_development_not_production(self):
        label = encoder.model_version_label(self.handle)
        self.assertIn("development", label.lower())
        self.assertNotEqual(label, encoder.MODEL_VERSION_LABEL_PRODUCTION)

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

    def test_encode_is_deterministic_in_eval_mode(self):
        n_genes = self.handle.model.A.shape[0]
        rng = np.random.default_rng(0)
        values = rng.normal(size=(2, n_genes)).astype(np.float32)
        mask = (rng.random((2, n_genes)) > 0.5).astype(np.float32)
        out1 = self.handle.encode(values, mask)
        out2 = self.handle.encode(values, mask)
        np.testing.assert_array_equal(out1, out2)


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
