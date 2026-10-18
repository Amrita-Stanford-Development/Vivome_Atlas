import unittest

from build_manifest import (
    build_organs,
    build_benchmark, build_deployed_architecture_facts, build_manifest, build_model_seeds,
    build_model_card, build_first_release_facts, build_v3_release, build_v31_evaluation,
    build_v31_release, build_v41_evaluation, build_v41_release, build_v42_release, build_v41_model, build_v42_evaluation, build_v42_model,
    class_stats, cosine, measured, pending,
    read_family_summary,
    read_latent_centroid_cosine, read_modality_probe_accuracy,
)

NO_EVALUATION = {"suite": {"title": "none", "rows": []}, "served": []}


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
            model=build_v42_model(5, self.deployed_architecture, NO_EVALUATION),
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

    def test_benchmark_block_is_pending_with_no_datasets_unless_supplied(self):
        self.assertEqual(self.manifest["benchmark"]["status"], "pending")
        self.assertEqual(self.manifest["benchmark"]["datasets"], [])

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

    def test_previous_earlier_and_first_release_default_to_none_when_not_supplied(self):
        self.assertIsNone(self.manifest["previous_release"])
        self.assertIsNone(self.manifest["earlier_release"])
        self.assertIsNone(self.manifest["first_release"])


class TestBuildFirstReleaseFacts(unittest.TestCase):
    def setUp(self):
        self.legacy_provenance = {
            "n_shared_genes": 2903,
            "zero_shot_auc_raw": 0.64,
            "zero_shot_auc_smoothed": 0.67,
            "shipped_properties": ["ribosome", "antigen_presentation"],
        }

    def test_carries_the_real_prior_numbers_forward_not_erased(self):
        facts = build_first_release_facts(self.legacy_provenance)
        self.assertEqual(facts["n_shared_genes"], 2903)
        self.assertEqual(facts["zero_shot_auc_raw"]["value"], 0.64)
        self.assertEqual(facts["zero_shot_auc_raw"]["status"], "measured")
        self.assertEqual(facts["shipped_properties"], ["ribosome", "antigen_presentation"])

    def test_note_explains_why_the_prior_number_reads_higher(self):
        facts = build_first_release_facts(self.legacy_provenance)
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
            model=build_v42_model(5, facts, NO_EVALUATION),
            latent_centroid_cosine_by_idx={}, modality_probe_accuracy=pending("N/A", "test"),
        )
        self.assertEqual(manifest["model"]["feature_space_size"], 2)
        self.assertEqual(manifest["model"]["encoder_family"], "module pooling")
        # There is no separate next_reference block any more — see
        # TestBuildManifest.test_next_reference_is_always_none.
        self.assertIsNone(manifest["next_reference"])
        self.assertEqual(manifest["benchmark"]["datasets"], [])


class TestReleaseBlocks(unittest.TestCase):
    """`model` is v4.1 (served again since 0.6.0), previous_release v4.2,
    earlier_release v3, each with its own numbers. v3.1's builders stay (its
    release card is gone since 0.5.0); every v3.1 figure says whether it is
    NB2's rule or the served configuration."""

    nb2_summary = {"eval_candidate": {"correct_when_committed": 94.9, "abstain_rate": 19.18, "coverage": 87.06,
                                      "fine_rate": 19.13, "group_rate": 17.71, "lineage_rate": 43.97}}
    flags = {"runs": {
        "SCoPE2": {"served": {"cells": 1490, "share_pct": {"committed": 53.02},
                              "correct_at_stated_level": {"correct_when_committed": 58.86}}},
        "PBMC240": {"served": {"cells": 238, "share_pct": {"committed": 73.11},
                               "weak_lineage": {"lymphoid_correct": 92, "lymphoid_n": 117}}},
        "Fulcher 2026": {"served": {"cells": 1275, "share_pct": {"committed": 89.18}, "correct_when_committed_pct": 97.31}},
    }}

    def test_nb2_figures_say_they_are_before_the_flags_and_dev_figures_say_served(self):
        ev = build_v31_evaluation(self.nb2_summary, self.flags)
        self.assertIn("NB2", ev["suite"]["title"])
        self.assertTrue(all("before the two conservative flags" in r["value"]["basis"] for r in ev["suite"]["rows"]))
        self.assertTrue(all("served settings (both service flags on)" in r["committed"]["basis"] for r in ev["served"]))
        self.assertEqual(ev["suite"]["rows"][0]["value"]["value"], 0.949)
        self.assertEqual(ev["served"][0]["committed"]["value"], round(790 / 1490, 6), "from the cell count, not the rounded share")
        self.assertEqual(ev["served"][1]["correct"]["value"], round(92 / 117, 6))

    def test_v42_model_marks_unrecorded_mask_sampling_as_missing(self):
        model = build_v42_model(5, {"feature_space_size": 2, "mask_sampling": "uniform"}, NO_EVALUATION)
        self.assertEqual(model["name"], "VivOME v4.2")
        self.assertIsNone(model["mask_sampling"], "v3's mask sampling must not be presented as the members'")
        self.assertIn("no protein labels are used", model["notes"])
        self.assertIn("Fulcher 2026", model["notes"], "the setting chosen on development data is named")
        self.assertIn("Rieckmann et al. 2017", model["notes"], "the protein class means are credited")

    def test_v41_is_the_current_model_and_keeps_its_first_release_card(self):
        model = build_v41_model(5, {"feature_space_size": 2, "mask_sampling": "uniform"}, NO_EVALUATION)
        self.assertEqual(model["name"], "VivOME v4.1")
        self.assertIsNone(model["mask_sampling"])
        self.assertIn("Fulcher 2026", model["notes"])
        v41 = build_v41_release(5, {"feature_space_size": 2, "mask_sampling": "uniform"}, NO_EVALUATION)
        self.assertEqual((v41["model_name"], v41["atlas_version"]), ("VivOME v4.1", "0.4.0"))
        self.assertIs(v41["evaluation"], NO_EVALUATION)
        self.assertIn("VIVOME_PIPELINE_VERSION=v4.1", v41["note"])

    def test_v42_is_the_previous_release_with_its_own_evaluation(self):
        v42 = build_v42_release(5, {"feature_space_size": 2, "mask_sampling": "uniform"}, NO_EVALUATION)
        self.assertEqual((v42["model_name"], v42["atlas_version"]), ("VivOME v4.2", "0.5.0"))
        self.assertIsNone(v42["mask_sampling"])
        self.assertIs(v42["evaluation"], NO_EVALUATION)
        self.assertIn("VIVOME_PIPELINE_VERSION=v4.2", v42["note"])
        self.assertIn("Rieckmann et al. 2017", v42["note"])

    def test_v31_keeps_its_own_release_and_evaluation(self):
        ev = build_v31_evaluation(self.nb2_summary, self.flags)
        v31 = build_v31_release(5, {"feature_space_size": 2, "mask_sampling": "uniform"}, ev)
        self.assertEqual((v31["model_name"], v31["atlas_version"]), ("VivOME v3.1", "0.3.0"))
        self.assertIsNone(v31["mask_sampling"])
        self.assertIs(v31["evaluation"], ev)
        self.assertIn("VIVOME_PIPELINE_VERSION=v3.1", v31["note"])

    def test_v3_release_keeps_its_own_evidence(self):
        rows = [{"class_name": "macrophage", "n_prot_cells": "394", "latent_centroid_cosine": "0.189762", "status": "measured"},
                {"class_name": "b cell", "n_prot_cells": "0", "latent_centroid_cosine": "", "status": "pending"}]
        v3 = build_v3_release(measured(5, "seeds"), {"mask_sampling": "uniform"}, rows,
                              {"modality_probe_balanced_accuracy_pct": 98.99, "basis": "probe"})
        self.assertEqual((v3["model_name"], v3["atlas_version"]), ("VivOME v3 reference", "0.2.0"))
        self.assertEqual(set(v3["latent_centroid_cosine"]), {"macrophage"})
        self.assertEqual(v3["modality_probe_accuracy"]["value"], 0.9899)
        self.assertEqual(v3["mask_sampling"], "uniform")


class TestV41Evaluation(unittest.TestCase):
    phase3 = {"result": {"v4.1": {"committed": 85.83, "correct_when_committed": 96.28, "coverage": 87.21,
                                  "best_guess_per_upload_balanced": 64.97,
                                  "levels": {"lineage": 51.77, "class": 18.17, "group": 15.89, "abstain": 14.17}}}}
    confident = [{"model": m, "dataset": d, "committed_pct": c, "correct_when_committed_pct": k}
                 for m in ("v31", "v41", "v42") for d, c, k in (("SCoPE2", "52.9", "58.8"), ("PBMC240", "73.4", "96.9"),
                                                          ("Fulcher 2026", "86.98", "97.92"))]
    fulcher = [{"tool": "v4.1 (served)", "balanced_accuracy_pct": "69.0", "recall_CD8T_pct": "23.75",
                "recall_DC_pct": "22.2", "lymphoid_recall_pct": "98.9"},
               {"tool": "v4.2 (served)", "balanced_accuracy_pct": "75.8", "recall_CD8T_pct": "24.0",
                "recall_DC_pct": "63.0", "lymphoid_recall_pct": "98.9"}]
    khoury = {"scores": {"v4.1": {"balanced_accuracy_pct": 62.51, "recall_CD8T_pct": 2.7, "lymphoid_recall_pct": 95.97}}}
    khoury42 = {"scores": {"v4.2": {"balanced_accuracy_pct": 60.12, "recall_CD8T_pct": 1.8, "lymphoid_recall_pct": 94.66}}}

    def test_every_figure_is_a_fraction_with_what_it_describes(self):
        ev = build_v41_evaluation(self.phase3, self.confident, self.fulcher, self.khoury)
        suite = {r["key"]: r["value"] for r in ev["suite"]["rows"]}
        self.assertEqual(suite["correct_when_committed"]["value"], 0.9628)
        self.assertEqual(suite["abstention"]["value"], 0.1417)
        self.assertTrue(all("fourth use" in v["basis"] for v in suite.values()))
        fulcher = next(s for s in ev["served"] if s["dataset"] == "Fulcher 2026")
        self.assertEqual((fulcher["committed"]["value"], fulcher["correct"]["value"]), (0.8698, 0.9792))
        self.assertIn("lineage", next(s for s in ev["served"] if s["dataset"] == "PBMC240")["correct_label"])

    def test_recall_covers_the_fine_types_only_and_names_each_dataset_s_status(self):
        ev = build_v41_evaluation(self.phase3, self.confident, self.fulcher, self.khoury)
        found = {(r["dataset"], r["type"]): r["value"] for r in ev["recall"]}
        self.assertEqual(set(found), {("Fulcher 2026", "CD8T"), ("Fulcher 2026", "DC"), ("Khoury 2026", "CD8T")})
        self.assertEqual(found[("Khoury 2026", "CD8T")]["value"], 0.027)
        self.assertIn("in-sample", found[("Fulcher 2026", "DC")]["basis"])
        self.assertIn("post-hoc", found[("Khoury 2026", "CD8T")]["basis"])

    def test_v42_takes_v41_s_suite_its_own_served_figures_and_its_post_hoc_khoury_check(self):
        ev = build_v42_evaluation(self.phase3, self.confident, self.fulcher, self.khoury42)
        suite = {r["key"]: r["value"] for r in ev["suite"]["rows"]}
        self.assertEqual(suite["correct_when_committed"]["value"], 0.9628)
        self.assertTrue(all("exactly as v4.1" in v["basis"] for v in suite.values()))
        self.assertTrue(all("v42_development" in s["committed"]["basis"] for s in ev["served"]))
        found = {(r["dataset"], r["type"]): r["value"] for r in ev["recall"]}
        self.assertEqual(found[("Fulcher 2026", "DC")]["value"], 0.63)
        self.assertEqual(found[("Khoury 2026", "CD8T")]["value"], 0.018)
        self.assertIn("post-hoc", found[("Khoury 2026", "CD8T")]["basis"])


class TestBenchmark(unittest.TestCase):
    """build_benchmark on the committed tables: every number traces to one of
    them (research/benchmark/results.md quotes the same)."""

    @classmethod
    def setUpClass(cls):
        import json
        import build_manifest as bm
        cls.b = build_benchmark({
            "dev_fulcher": bm.read_csv(bm.V42_DEV_DIR / "fulcher2026.csv"),
            "dev_pbmc240": bm.read_csv(bm.V42_DEV_DIR / "pbmc240.csv"),
            "dev_scope2": bm.read_csv(bm.V42_DEV_DIR / "scope2.csv"),
            "dev_scope2_reprocessed": bm.read_csv(bm.V42_DEV_DIR / "scope2_reprocessed.csv"),
            "paired_current": bm.read_csv(bm.V41_DEV_DIR / "paired_bootstrap_v41.csv"),
            "paired_previous_vs_current": bm.read_csv(bm.V42_DEV_DIR / "paired_bootstrap_v42_vs_v41.csv"),
            "corrected_fulcher": bm.read_csv(bm.CORRECTED_DIR / "fulcher2026_summary.csv"),
            "corrected_pbmc240": bm.read_csv(bm.CORRECTED_DIR / "pbmc240_summary.csv"),
            "corrected_scope2": bm.read_csv(bm.CORRECTED_DIR / "scope2_summary.csv"),
            "khoury_family": bm.read_csv(bm.KHOURY_POSTHOC_DIR / "family_summary.csv"),
            "khoury_current": json.loads((bm.KHOURY_V41_DIR / "summary.json").read_text(encoding="utf-8")),
            "khoury_current_pairs": bm.read_csv(bm.KHOURY_V41_DIR / "paired_bootstrap.csv"),
            "khoury_previous": json.loads((bm.KHOURY_V42_DIR / "summary.json").read_text(encoding="utf-8")),
            "khoury_previous_pairs": bm.read_csv(bm.KHOURY_V42_DIR / "paired_bootstrap.csv"),
        })
        cls.sets = {d["key"]: d for d in cls.b["datasets"]}

    def row(self, key, method, rule):
        return next(r for r in self.sets[key]["rows"] if r["method"] == method and r["rule"] == rule)

    def test_held_out_data_comes_first_and_every_table_starts_with_ours(self):
        self.assertEqual(self.b["status"], "measured")
        self.assertEqual(list(self.sets), ["khoury2026", "fulcher2026", "pbmc240", "scope2", "scope2_reprocessed"])
        for d in self.b["datasets"]:
            self.assertEqual([r["method"] for r in d["rows"][:2]], ["VivOME v4.1 (ours)", "VivOME v4.2 (ours)"], d["key"])
            others = [r["score"]["value"] for r in d["rows"][2:]]
            self.assertEqual(others, sorted(others, reverse=True), d["key"])

    def test_khoury_scores_v41_post_hoc_ahead_of_v42_with_its_comparisons(self):
        k = self.sets["khoury2026"]
        self.assertEqual(k["rows"][0]["score"]["value"], 0.6251)
        self.assertEqual(k["rows"][1]["score"]["value"], 0.6012)
        d = k["rows"][1]["vs_current"]["difference"]
        self.assertAlmostEqual(d["value"], 0.02388, places=4, msg="v4.1 minus v4.2, turned round from v4.2's check")
        self.assertGreater(d["ci_low"], 0, "v4.1 is ahead of v4.2 on Khoury")
        self.assertEqual(k["chance"]["value"], 0.2)
        self.assertIn("Post-hoc", k["role"])
        self.assertTrue(all(r["vs_current"] for r in k["rows"][1:]), "every other row has its paired comparison")
        pca = self.row("khoury2026", "PCA, no correction", "shared kNN")
        self.assertAlmostEqual(pca["score"]["value"], 0.628, places=3)
        scanvi = self.row("khoury2026", "scANVI", "shared kNN")
        self.assertEqual(scanvi["runs"], 3)
        self.assertIn("sd", scanvi["score"])

    def test_fulcher_says_it_is_in_sample_and_scanvi_keeps_its_two_completed_runs(self):
        f = self.sets["fulcher2026"]
        self.assertIn("In-sample", f["role"])
        self.assertAlmostEqual(f["chance"]["value"], 1 / 6, places=6)
        self.assertEqual(self.row("fulcher2026", "scANVI", "shared kNN")["runs"], 2)
        harmony = self.row("fulcher2026", "Harmony", "nearest centroid")
        self.assertEqual(harmony["vs_current"]["favour_current"], 3)
        v42 = self.row("fulcher2026", "VivOME v4.2 (ours)", "best guess, as served")
        self.assertEqual((v42["vs_current"]["favour_other"], v42["vs_current"]["difference"]["ci_high"]),
                         (1, -0.04409))

    def test_scope2_tables_show_ours_below_chance(self):
        for key in ("scope2", "scope2_reprocessed"):
            d = self.sets[key]
            self.assertEqual(d["chance"]["value"], 0.5)
            self.assertLess(d["rows"][0]["score"]["value"], d["chance"]["value"], key)

    def test_pbmc240_has_no_chance_and_no_baseline_pairings(self):
        p = self.sets["pbmc240"]
        self.assertIsNone(p["chance"])
        self.assertTrue(all(r["vs_current"] is None for r in p["rows"] if not r["ours"]))

    def test_the_committed_manifest_is_this_builder_s_output(self):
        import json
        import build_manifest as bm
        committed = json.loads(bm.OUTPUT_PATH.read_text(encoding="utf-8"))["benchmark"]
        self.assertEqual(committed, json.loads(json.dumps(self.b)))


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


class TestBuildModelCard(unittest.TestCase):
    def setUp(self):
        self.rna = [{"mask": "scope2", "cells": "published sample (as v3)", "acc_ot": "95.53", "bal_ot": "74.7594"},
                    {"mask": "scope2", "cells": "  of which test cells only", "acc_ot": "93.18978", "bal_ot": "65.70553"}]
        regimes = ("restricted_native_centroid", "restricted_shared_knn", "unrestricted_native_centroid", "unrestricted")
        self.scores = [{"model": "v3_seed0", "regime": r, "accuracy_pct": "86.17", "balanced_accuracy_pct": "79.79"} for r in regimes]
        header = [["", "", "accuracy_pct"] * 1, ["", "", "mean"], ["family", "regime"]]
        self.family = read_family_summary(header + [
            ["v3", r, "79.38", "4.71", "73.76", "86.17", "63.32", "10.84", "50.79", "79.79"] for r in regimes
        ])
        self.paired = [{"family": "v3", "regime": "unrestricted", "diff_point_pct": str(d)} for d in (10, 20, -5)] + \
                      [{"family": "v3", "regime": "restricted_shared_knn", "diff_point_pct": str(d)} for d in (-1, 2)] + \
                      [{"family": "V2", "regime": "unrestricted", "diff_point_pct": "99"}]

    def test_every_protein_row_names_its_decision_rule(self):
        card = build_model_card(self.rna, self.scores, self.family, self.paired)
        protein = [r for r in card["rows"] if r["measure"].startswith("Protein")]
        self.assertEqual(len(protein), 8)
        for row in protein:
            self.assertIn(row["rule"], ("nearest centroid (the service's rule)", "shared kNN (the benchmark's rule)"))
        self.assertEqual(len({r["key"] for r in card["rows"]}), 9, "every row has its own key")

    def test_values_are_fractions_with_their_source_as_basis(self):
        card = build_model_card(self.rna, self.scores, self.family, self.paired)
        rna_row = card["rows"][0]
        self.assertEqual(rna_row["accuracy"]["value"], 0.931898)
        self.assertIn("rna_to_rna_membership_corrected.csv", rna_row["accuracy"]["basis"])
        mean_row = card["rows"][2]
        self.assertEqual(mean_row["balanced_accuracy"]["value"], 0.6332)
        self.assertEqual(mean_row["balanced_accuracy"]["sd"], 0.1084)
        self.assertEqual((mean_row["balanced_accuracy"]["min"], mean_row["balanced_accuracy"]["max"]), (0.5079, 0.7979))

    def test_the_superseded_published_figure_is_kept_and_labelled(self):
        card = build_model_card(self.rna, self.scores, self.family, self.paired)
        self.assertEqual(card["rna_to_rna_superseded"]["accuracy"]["value"], 0.9553)
        self.assertIn("included training cells", card["rna_to_rna_superseded"]["measure"])

    def test_scanvi_pairings_are_counted_from_the_v3_rows_only(self):
        vs = build_model_card(self.rna, self.scores, self.family, self.paired)["vs_scanvi"]
        self.assertEqual((vs["unrestricted"]["pairings"], vs["unrestricted"]["v3_ahead"]), (3, 2))
        self.assertAlmostEqual(vs["unrestricted"]["mean_difference"]["value"], 0.083333, places=6)
        self.assertEqual((vs["restricted_shared_knn"]["pairings"], vs["restricted_shared_knn"]["v3_ahead"]), (2, 1))

    def test_the_real_family_summary_parses(self):
        import csv
        from build_manifest import NB1D_DIR
        with (NB1D_DIR / "ours_scope2_5seed_family_summary.csv").open(newline="") as handle:
            family = read_family_summary(list(csv.reader(handle)))
        self.assertIn(("v3", "restricted_native_centroid"), family)
        # SCoPE2's curated labels (research/benchmark/bugs-and-fixes.md, 8).
        self.assertAlmostEqual(family[("v3", "restricted_native_centroid")]["bal_max"], 49.21287376338508)



class TestBuildOrgans(unittest.TestCase):
    ATLAS = {"source": {"atlas": "Tabula Sapiens v2", "figshare_article": 1, "retrieved": "2026-10-18"},
             "organs": [{"name": "Blood", "file": "Blood_TSP.h5ad"}, {"name": "Lung", "file": "Lung_TSP.h5ad"},
                        {"name": "Heart", "file": "Heart_TSP.h5ad"}]}
    MAPS = {"organs": [{"id": "lung", "atlas": "Lung_TSP.h5ad", "cells": 10, "class_order": ["a", "b"]}]}

    def test_marks_each_organ_by_what_vivome_has_of_it(self):
        organs = build_organs(self.ATLAS, self.MAPS, "Blood_TSP.h5ad")
        self.assertEqual((organs["total"], organs["labelling"], organs["maps"], organs["to_build"]), (3, 1, 1, 1))
        self.assertEqual(organs["list"][1], {"name": "Lung", "status": "map", "id": "lung", "cells": 10, "types": 2})
        self.assertEqual(organs["list"][2], {"name": "Heart", "status": "to_build"})
        self.assertEqual(organs["atlas"], "Tabula Sapiens v2")

    def test_refuses_a_served_reference_or_a_map_outside_the_atlas(self):
        with self.assertRaises(ValueError):
            build_organs(self.ATLAS, self.MAPS, "Other.h5ad")
        with self.assertRaises(ValueError):
            build_organs(self.ATLAS, {"organs": [{"id": "x", "atlas": "X.h5ad", "cells": 1, "class_order": []}]},
                         "Blood_TSP.h5ad")

    def test_the_committed_manifest_counts_the_committed_lists(self):
        import json
        from build_manifest import ATLAS_DIR
        manifest = json.loads((ATLAS_DIR / "atlas_manifest.json").read_text(encoding="utf-8"))
        atlas = json.loads((ATLAS_DIR / "organs" / "tabula_sapiens.json").read_text(encoding="utf-8"))
        maps = json.loads((ATLAS_DIR / "organs" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["organs"]["total"], len(atlas["organs"]))
        self.assertEqual(manifest["organs"]["maps"], len(maps["organs"]))
        self.assertEqual(manifest["organs"]["labelling"], 1)


if __name__ == "__main__":
    unittest.main()
