import unittest

from build_manifest import (
    build_manifest, build_next_reference_facts, build_previous_release_facts,
    class_stats, cosine, measured, pending,
)


def row(modality, class_idx, class_name, pc1, pc2, pc3):
    return {
        "latent_dim": "128",
        "modality": modality,
        "orig_index": "0",
        "class_idx": str(class_idx),
        "class_name": class_name,
        "PC1": str(pc1),
        "PC2": str(pc2),
        "PC3": str(pc3),
    }


class TestCosine(unittest.TestCase):
    def test_identical_vectors_are_one(self):
        self.assertAlmostEqual(cosine((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)), 1.0, places=9)

    def test_opposite_vectors_are_minus_one(self):
        self.assertAlmostEqual(cosine((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)), -1.0, places=9)

    def test_zero_vector_returns_none(self):
        self.assertIsNone(cosine((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))


class TestClassStats(unittest.TestCase):
    def test_counts_and_centroid(self):
        rows = [
            row("RNA", 12, "monocyte", 0.0, 0.0, 0.0),
            row("RNA", 12, "monocyte", 2.0, 4.0, 6.0),
        ]
        stats = class_stats(rows)
        self.assertEqual(stats[12]["count"], 2)
        self.assertEqual(stats[12]["name"], "monocyte")
        self.assertEqual(stats[12]["centroid"], (1.0, 2.0, 3.0))

    def test_quoted_comma_name_survives(self):
        rows = [row("RNA", 2, "cd4-positive, alpha-beta t cell", 1.0, 1.0, 1.0)]
        self.assertEqual(class_stats(rows)[2]["name"], "cd4-positive, alpha-beta t cell")


class TestPendingAndMeasured(unittest.TestCase):
    def test_pending_has_null_value(self):
        rec = pending("Phase 1", "needs latent export")
        self.assertIsNone(rec["value"])
        self.assertEqual(rec["status"], "pending")
        self.assertEqual(rec["phase"], "Phase 1")

    def test_measured_carries_basis(self):
        rec = measured(0.5, "3-PC projection")
        self.assertEqual(rec["value"], 0.5)
        self.assertEqual(rec["status"], "measured")
        self.assertEqual(rec["basis"], "3-PC projection")


class TestBuildManifest(unittest.TestCase):
    def setUp(self):
        self.rna = [
            row("RNA", 12, "monocyte", 1.0, 0.0, 0.0),
            row("RNA", 16, "neutrophil", 0.0, 1.0, 0.0),
        ]
        self.prot = [row("PROT", 12, "monocyte", 2.0, 0.0, 0.0)]
        self.manifest = build_manifest(self.rna, self.prot)

    def test_shared_class_is_cross_modal(self):
        mono = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 12)
        self.assertEqual(mono["support"], "cross_modal")
        self.assertEqual(mono["rna_cells"], 1)
        self.assertEqual(mono["prot_cells"], 1)

    def test_rna_only_class_marked_and_has_zero_prot(self):
        neut = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 16)
        self.assertEqual(neut["support"], "rna_only")
        self.assertEqual(neut["prot_cells"], 0)

    def test_collinear_centroids_give_cosine_one(self):
        mono = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 12)
        self.assertEqual(mono["pca_centroid_cosine"]["status"], "measured")
        self.assertAlmostEqual(mono["pca_centroid_cosine"]["value"], 1.0, places=6)
        self.assertEqual(mono["pca_centroid_cosine"]["basis"], "3-PC projection")

    def test_rna_only_class_has_pending_cosine(self):
        neut = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 16)
        self.assertEqual(neut["pca_centroid_cosine"]["status"], "pending")
        self.assertIsNone(neut["pca_centroid_cosine"]["value"])

    def test_latent_and_probe_metrics_are_always_pending(self):
        for cell in self.manifest["cell_types"]:
            self.assertIsNone(cell["latent_centroid_cosine"]["value"])
            self.assertIsNone(cell["modality_probe_accuracy"]["value"])
            self.assertIsNone(cell["transfer_accuracy"]["value"])

    def test_summary_counts(self):
        self.assertEqual(self.manifest["summary"]["cross_modal"], 1)
        self.assertEqual(self.manifest["summary"]["rna_only"], 1)
        self.assertEqual(self.manifest["summary"]["total"], 2)

    def test_benchmark_block_is_pending_with_no_rows(self):
        self.assertEqual(self.manifest["benchmark"]["status"], "pending")
        self.assertEqual(self.manifest["benchmark"]["rows"], [])

    def test_required_top_level_keys(self):
        for key in ("schema_version", "atlas_version", "generated", "model",
                    "modalities", "cell_types", "summary", "benchmark", "data_availability"):
            self.assertIn(key, self.manifest)

    def test_next_reference_defaults_to_none_when_not_supplied(self):
        # build_manifest doesn't fabricate architecture facts on its own —
        # a caller must supply them from the real decisive-test artifacts.
        self.assertIsNone(self.manifest["next_reference"])

    def test_previous_release_defaults_to_none_when_not_supplied(self):
        self.assertIsNone(self.manifest["previous_release"])


class TestBuildPreviousReleaseFacts(unittest.TestCase):
    def setUp(self):
        self.legacy_provenance = {
            "n_shared_genes": 2903,
            "zero_shot_auc_raw": 0.64,
            "zero_shot_auc_smoothed": 0.67,
            "shipped_properties": ["ribosome", "antigen_presentation"],
        }

    def test_carries_the_real_prior_numbers_forward_not_erased(self):
        facts = build_previous_release_facts(self.legacy_provenance)
        self.assertEqual(facts["n_shared_genes"], 2903)
        self.assertEqual(facts["zero_shot_auc_raw"]["value"], 0.64)
        self.assertEqual(facts["zero_shot_auc_raw"]["status"], "measured")
        self.assertEqual(facts["shipped_properties"], ["ribosome", "antigen_presentation"])

    def test_note_explains_why_the_prior_number_reads_higher(self):
        facts = build_previous_release_facts(self.legacy_provenance)
        self.assertIn("jointly trained", facts["note"])
        self.assertIn("pending", facts["note"])


class TestBuildNextReferenceFacts(unittest.TestCase):
    def setUp(self):
        self.decisive_summary = {
            "winner_config": {"enc": "module", "sampler": "uniform", "consist": True},
            "n_seeds": 5,
        }
        self.detail_rows = [
            {"gene": "A1BG", "bubis_hela": "True", "bubis_lung": "False", "n_sources": "1", "in_old_reference": "False"},
            {"gene": "A2M", "bubis_hela": "True", "bubis_lung": "True", "n_sources": "2", "in_old_reference": "True"},
        ]

    def test_reports_design_facts_not_performance_numbers(self):
        facts = build_next_reference_facts(self.decisive_summary, self.detail_rows)
        self.assertEqual(facts["encoder_family"], "module pooling")
        self.assertEqual(facts["mask_sampling"], "uniform")
        self.assertTrue(facts["consistency_loss"])
        self.assertFalse(facts["trained"])

    def test_feature_space_size_counts_the_actual_rows_not_a_hardcoded_number(self):
        facts = build_next_reference_facts(self.decisive_summary, self.detail_rows)
        self.assertEqual(facts["feature_space_size"], 2)

    def test_detected_by_source_is_computed_from_the_real_columns(self):
        facts = build_next_reference_facts(self.decisive_summary, self.detail_rows)
        self.assertEqual(facts["detected_by_source"], {"bubis_hela": 2, "bubis_lung": 1})

    def test_retained_from_old_counts_in_old_reference_true_rows(self):
        facts = build_next_reference_facts(self.decisive_summary, self.detail_rows)
        self.assertEqual(facts["previous_feature_space_size"], 1)

    def test_unrecognised_encoder_family_raises_instead_of_guessing(self):
        bad_summary = {"winner_config": {"enc": "not_a_real_family", "sampler": "uniform", "consist": True}, "n_seeds": 5}
        with self.assertRaises(ValueError):
            build_next_reference_facts(bad_summary, self.detail_rows)

    def test_result_plugs_into_build_manifest_unchanged(self):
        facts = build_next_reference_facts(self.decisive_summary, self.detail_rows)
        manifest = build_manifest(
            [row("RNA", 12, "monocyte", 0.0, 0.0, 0.0)], [], next_reference=facts,
        )
        self.assertEqual(manifest["next_reference"]["feature_space_size"], 2)
        # A design decision must never contaminate the current release's own
        # performance fields — those stay exactly as pending as before.
        self.assertIsNone(manifest["model"]["seeds"]["value"])
        self.assertEqual(manifest["benchmark"]["rows"], [])


if __name__ == "__main__":
    unittest.main()
