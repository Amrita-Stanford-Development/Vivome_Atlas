"""v4.2 (Goal 2, Phase 2a; service/pipeline/fusion.py): v4.1 with protein
class means from sorted cells in its correlation term. Refused until its
evaluation passes; when loaded for evaluation, its served best guess must equal
research/notebooks/v42_protein_means.py's, cell by cell, on every development
dataset, and where its correlation term is flat it answers exactly as v4.1."""
import json
import unittest

import numpy as np
import pandas as pd

from service import config
from service.pipeline import alignment, fusion, pipeline, reference
from service.tests.test_golden_fixtures import _load_pbmc240_50
from service.tests.test_pipeline_versions import assert_same

GUESSES = config.REPO_ROOT / "research" / "notebook-outputs" / "v42_protein_means" / "guesses.csv.gz" \
    if hasattr(config, "REPO_ROOT") else None


def repo():
    from pathlib import Path
    return Path(__file__).resolve().parents[2]


class ProteinQueryTests(unittest.TestCase):
    def test_rows_match_by_first_symbol_merge_by_median_and_zscore_within_the_upload(self):
        raw = alignment.RawMatrix(gene_names=["cd8a;CD8B", "CD8A", "GNLY", "OTHER"], cell_ids=["a", "b", "c"],
                                  values=np.array([[1.0, 3.0, np.nan], [3.0, 5.0, np.nan],
                                                   [2.0, np.nan, 4.0], [9.0, 9.0, 9.0]], dtype=np.float32))
        values, mask = fusion.protein_query(raw, ("CD8A", "GNLY", "NKG7"))
        self.assertEqual(mask.tolist(), [[1, 1, 0], [1, 0, 0], [0, 1, 0]])
        cd8a = np.array([2.0, 4.0])  # per-cell medians of the two CD8A rows; cell c has neither
        np.testing.assert_allclose(values[:2, 0], (cd8a - cd8a.mean()) / (cd8a.std() + 1e-8))
        self.assertTrue((values[:, 2] == 0).all())



class V42ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.bundle = fusion.V4Bundle.load(require_evaluation=False, version="v4.2")
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/build_v42_spec.py.")

    def test_v42_is_selectable_and_refused_until_evaluated(self):
        self.assertIn("v4.2", config.PIPELINE_VERSIONS)
        spec = json.loads(config.V42_SPEC_PATH.read_text(encoding="utf-8"))
        self.assertEqual(spec["evaluation"]["status"], "pending")
        with self.assertRaises(reference.PendingArtifactError):
            pipeline.load_bundle("v4.2")

    def test_its_best_guess_refuses_to_run_without_the_protein_query(self):
        rng = np.random.default_rng(0)
        z = [rng.normal(size=(2, m.centroids.shape[1])).astype(np.float32) for m in self.bundle.members]
        n_classes, n_genes = self.bundle.class_means.shape
        with self.assertRaisesRegex(ValueError, "protein query"):
            fusion.best_guess_probabilities(self.bundle, z, np.zeros((2, n_genes)), np.ones((2, n_genes)),
                                            np.full((2, n_classes), 1 / n_classes), np.array([True, True]))

    def test_its_protein_means_are_the_specs(self):
        spec = json.loads(config.V42_SPEC_PATH.read_text(encoding="utf-8"))["best_guess"]["protein_class_means"]
        covered = [c for c, ok in zip(self.bundle.class_names, self.bundle.protein_covered) if ok]
        self.assertEqual(covered, spec["classes_covered"])
        self.assertEqual(len(self.bundle.protein_genes), spec["proteins"])
        self.assertTrue((self.bundle.protein_means[~self.bundle.protein_covered] == 0).all())
        self.assertNotIn("macrophage", covered)

    def test_where_its_term_is_flat_it_answers_exactly_as_v41(self):
        v41 = pipeline.load_bundle("v4.1")
        raw = _load_pbmc240_50()
        ours, theirs = (json.loads(json.dumps(pipeline.run_projection(b, raw))) for b in (self.bundle, v41))
        self.assertEqual(ours["best_guess_rule"]["correlation_term"], "flat")
        self.assertEqual((ours.pop("pipeline_version"), theirs.pop("pipeline_version")), ("v4.2", "v4.1"))
        self.assertNotEqual(ours.pop("model_version"), theirs.pop("model_version"))
        ours["best_guess_rule"].pop("agreement"), theirs["best_guess_rule"].pop("agreement")
        assert_same(self, ours, theirs)

    def test_the_served_guess_is_the_notebooks_on_every_development_dataset(self):
        from benchmark import baselines_v31, datasets
        guesses = repo() / "research" / "notebook-outputs" / "v42_protein_means" / "guesses.csv.gz"
        want = pd.read_csv(guesses, dtype={"cell_id": str}, keep_default_na=False)
        try:
            uploads = {"fulcher2026": datasets.load_fulcher2026_upload(),
                       "pbmc240": alignment.parse_matrix_csv(
                           (repo() / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text()),
                       "scope2": baselines_v31.scope2_raw(),
                       "scope2_reprocessed": datasets.load_scope2_reprocessed_upload(),
                       "furtwangler2025": datasets.load_furtwangler2025_upload()}
        except (FileNotFoundError, OSError) as exc:
            self.skipTest(f"a development upload is not on this machine: {exc}")
        for name, raw in uploads.items():
            with self.subTest(dataset=name):
                response = pipeline.run_projection(self.bundle, raw)
                served = [c.get("best_guess", {}).get("label", "") for c in response["cells"]]
                expected = want.loc[want["dataset"] == name]
                self.assertEqual([c["cell_id"] for c in response["cells"]], expected["cell_id"].tolist())
                guessed = np.array([s != "" for s in served])  # cells refused for coverage have no guess
                self.assertTrue((np.array(served)[guessed] == expected["v42"].to_numpy()[guessed]).all())


if __name__ == "__main__":
    unittest.main()
