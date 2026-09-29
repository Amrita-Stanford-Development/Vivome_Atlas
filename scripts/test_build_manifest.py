import unittest

from build_manifest import (
    build_deployed_architecture_facts, build_manifest, build_model_seeds,
    build_previous_release_facts, class_stats, cosine, measured, pending,
    read_latent_centroid_cosine, read_modality_probe_accuracy,
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
        self.model_seeds = measured(5, "test seeds")
        self.deployed_architecture = {
            "feature_space_size": 2, "previous_feature_space_size": 1,
            "detected_by_source": {"bubis_hela": 1},
            "encoder_family": "module pooling", "mask_sampling": "uniform",
        }
        self.latent_centroid_cosine_by_idx = {12: measured(0.83, "test latent cosine")}
        self.modality_probe_accuracy = measured(0.99, "test probe")
        self.manifest = build_manifest(
            self.rna, self.prot,
            model_seeds=self.model_seeds,
            deployed_architecture=self.deployed_architecture,
            latent_centroid_cosine_by_idx=self.latent_centroid_cosine_by_idx,
            modality_probe_accuracy=self.modality_probe_accuracy,
        )

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

    def test_cross_modal_class_gets_the_supplied_latent_and_probe_metrics(self):
        mono = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 12)
        self.assertEqual(mono["latent_centroid_cosine"], self.latent_centroid_cosine_by_idx[12])
        self.assertEqual(mono["modality_probe_accuracy"], self.modality_probe_accuracy)

    def test_rna_only_class_stays_pending_for_latent_and_probe(self):
        # Even if a caller's latent_centroid_cosine_by_idx somehow keyed an
        # RNA-only class, modality_probe_accuracy is never applied outside
        # cross-modal rows — there is no cross-modal evidence to measure it
        # against.
        neut = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 16)
        self.assertIsNone(neut["latent_centroid_cosine"]["value"])
        self.assertIsNone(neut["modality_probe_accuracy"]["value"])

    def test_transfer_accuracy_is_always_pending(self):
        # No source data decomposes this per class (see its own pending
        # note) — true for every row regardless of cross-modal support.
        for cell in self.manifest["cell_types"]:
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

    def test_next_reference_is_always_none(self):
        # No architecture change is in flight — the last one this field
        # described is complete and folded into `model` instead. There is
        # no longer a way to supply a non-null value here (see
        # TestBuildDeployedArchitectureFacts for the facts it used to
        # carry).
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
        self.assertIn("superseded", facts["note"])


class TestBuildDeployedArchitectureFacts(unittest.TestCase):
    """decisive_summary.json's architecture decision, folded into `model`
    rather than a separate not-yet-trained `next_reference` block — the
    architecture it describes is the one actually deployed now."""

    def setUp(self):
        self.decisive_summary = {
            "winner_config": {"enc": "module", "sampler": "uniform", "consist": True},
            "n_seeds": 5,
        }
        self.detail_rows = [
            {"gene": "A1BG", "bubis_hela": "True", "bubis_lung": "False", "n_sources": "1", "in_old_reference": "False"},
            {"gene": "A2M", "bubis_hela": "True", "bubis_lung": "True", "n_sources": "2", "in_old_reference": "True"},
        ]

    def test_reports_the_settled_architecture(self):
        facts = build_deployed_architecture_facts(self.decisive_summary, self.detail_rows)
        self.assertEqual(facts["encoder_family"], "module pooling")
        self.assertEqual(facts["mask_sampling"], "uniform")

    def test_feature_space_size_counts_the_actual_rows_not_a_hardcoded_number(self):
        facts = build_deployed_architecture_facts(self.decisive_summary, self.detail_rows)
        self.assertEqual(facts["feature_space_size"], 2)

    def test_detected_by_source_is_computed_from_the_real_columns(self):
        facts = build_deployed_architecture_facts(self.decisive_summary, self.detail_rows)
        self.assertEqual(facts["detected_by_source"], {"bubis_hela": 2, "bubis_lung": 1})

    def test_retained_from_old_counts_in_old_reference_true_rows(self):
        facts = build_deployed_architecture_facts(self.decisive_summary, self.detail_rows)
        self.assertEqual(facts["previous_feature_space_size"], 1)

    def test_unrecognised_encoder_family_raises_instead_of_guessing(self):
        bad_summary = {"winner_config": {"enc": "not_a_real_family", "sampler": "uniform", "consist": True}, "n_seeds": 5}
        with self.assertRaises(ValueError):
            build_deployed_architecture_facts(bad_summary, self.detail_rows)

    def test_facts_plug_into_build_manifest_as_model_fields(self):
        facts = build_deployed_architecture_facts(self.decisive_summary, self.detail_rows)
        manifest = build_manifest(
            [row("RNA", 12, "monocyte", 0.0, 0.0, 0.0)], [],
            model_seeds=measured(5, "test"), deployed_architecture=facts,
            latent_centroid_cosine_by_idx={}, modality_probe_accuracy=pending("N/A", "test"),
        )
        self.assertEqual(manifest["model"]["feature_space_size"], 2)
        self.assertEqual(manifest["model"]["encoder_family"], "module pooling")
        # There is no separate next_reference block any more — see
        # TestBuildManifest.test_next_reference_is_always_none.
        self.assertIsNone(manifest["next_reference"])
        self.assertEqual(manifest["benchmark"]["rows"], [])


class TestBuildModelSeeds(unittest.TestCase):
    def test_value_is_a_seed_count_not_an_accuracy(self):
        # web/js/panels.js:buildModelCard renders this with 0 decimal places —
        # an accuracy like 0.7143 would render as "1". The count belongs in
        # value; the accuracy and its CI belong in basis.
        rows = [{"seed": str(i)} for i in range(5)]
        provenance = {"reference_seed_mean_bal_acc": 0.7143, "reference_seed_ci95": [0.6851, 0.7435]}
        seeds = build_model_seeds(rows, provenance)
        self.assertEqual(seeds["value"], 5)
        self.assertIn("0.7143", seeds["basis"])
        self.assertIn("0.6851", seeds["basis"])


class TestReadLatentCentroidCosine(unittest.TestCase):
    def test_measured_row_parses_the_value(self):
        rows = [{"class_idx": "12", "class_name": "monocyte", "n_prot_cells": "1096",
                 "latent_centroid_cosine": "0.830313", "status": "measured", "reason": ""}]
        result = read_latent_centroid_cosine(rows)
        self.assertEqual(result[12]["status"], "measured")
        self.assertAlmostEqual(result[12]["value"], 0.830313, places=6)

    def test_pending_row_with_empty_string_value_parses_as_none_not_zero(self):
        rows = [{"class_idx": "0", "class_name": "b cell", "n_prot_cells": "0",
                 "latent_centroid_cosine": "", "status": "pending", "reason": "no cross modal coverage"}]
        result = read_latent_centroid_cosine(rows)
        self.assertIsNone(result[0]["value"])
        self.assertEqual(result[0]["status"], "pending")
        self.assertEqual(result[0]["note"], "no cross modal coverage")


class TestReadModalityProbeAccuracy(unittest.TestCase):
    def test_value_is_a_fraction_not_a_percent(self):
        # web/js/manifest.js:formatPercent multiplies by 100 — a value already
        # in percent (98.99) would render as "9899.3%".
        metric = read_modality_probe_accuracy({
            "modality_probe_balanced_accuracy_pct": 98.99328859060402,
            "basis": "5-fold CV",
        })
        self.assertAlmostEqual(metric["value"], 0.989933, places=5)
        self.assertLess(metric["value"], 1.0)


if __name__ == "__main__":
    unittest.main()
