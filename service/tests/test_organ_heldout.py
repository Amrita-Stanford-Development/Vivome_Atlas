"""The organ references' locked tests: how their intakes read sample names
(research/benchmark/protocol-lung-msv000094189.md, rules 3 and 4;
protocol-colon-pxd052341.md, rules 3 to 5). Written before either set is
opened, on invented names."""
import unittest
from pathlib import Path

from benchmark import colon_heldout_intake as colon
from benchmark import lung_heldout_intake as lung


class LungNames(unittest.TestCase):
    def test_populations_by_meaning(self):
        self.assertEqual(lung.population("LMAP_D006_EPI_1"), "epithelial")
        self.assertEqual(lung.population("LMAP_D006_C_Endo_P"), "endothelial")
        self.assertEqual(lung.population("D12-END"), "endothelial")
        self.assertEqual(lung.population("d12_MES"), "stromal")
        self.assertEqual(lung.population("D12 MIC r2"), "immune")
        self.assertEqual(lung.population("D12_CD45pos"), "immune")

    def test_mixes_and_controls_are_excluded_and_unclear_names_stop(self):
        self.assertEqual(lung.population("LMAP_D006_PMX_1"), "excluded")
        self.assertEqual(lung.population("QC_HeLa_1"), "excluded")
        self.assertIsNone(lung.population("D006_sample_7"))
        self.assertIsNone(lung.population("D006_EPI_MES"))
        with self.assertRaises(SystemExit):
            lung.read_label_map(["D1_EPI", "D1_unknown"])

    def test_donors(self):
        self.assertEqual(lung.donor("LMAP_D006_EPI_1"), "d006")
        self.assertEqual(lung.donor("donor_12-MES"), "d12")
        self.assertEqual(lung.donor("LMAP_TSP2_MIC_1"), "tsp2")
        self.assertEqual(lung.donor("EPI_1"), "all")


class LymphNodeNames(unittest.TestCase):
    def test_regions_by_meaning(self):
        from benchmark import ln_heldout_intake as ln
        self.assertEqual(ln.region("tonsil_Whisper_DZ3_S2-A1_1_1000.d"), "germinal centre")
        self.assertEqual(ln.region("tonsil_MZ12"), "mantle zone")
        self.assertEqual(ln.region("calamari_Whisper_B1_S1-A7_1_3807.d"), "B-cell region")
        self.assertEqual(ln.region("calamari_Whisper_T4_S1-C10_1_3817.d"), "T zone")
        self.assertEqual(ln.region("calamari_Whisper_epi3_S1-A9_1_3812.d"), "epithelium")
        self.assertEqual(ln.region("tonsil_blank_1"), "excluded")

    def test_two_zones_or_none_stop_the_automatic_map(self):
        from benchmark import ln_heldout_intake as ln
        self.assertEqual(ln.region("calamari_Whisper_T1_S1-B8_1_3811.d"), "T zone")  # plate well B8 is not a region
        self.assertIsNone(ln.region("run_0042.d"))
        with self.assertRaises(SystemExit):
            ln.read_label_map(["tonsil_TZ1", "run_7.d"])


class LockedTestGuards(unittest.TestCase):
    """A review of the locked tests' code against their protocols (2026-10-21),
    before either set is opened."""

    def test_the_labels_step_checks_for_a_frozen_candidate_before_anything_else(self):
        from unittest import mock

        from benchmark import ln_heldout_intake as ln
        from benchmark import lung_heldout_intake as lung
        for module in (ln, lung):
            with mock.patch.object(module, "candidate_dir", side_effect=SystemExit("no candidate")), \
                    mock.patch.object(module, "_check_download", side_effect=AssertionError("a sealed file was touched")):
                with self.assertRaises(SystemExit) as caught:
                    module.main(["--labels"])
            self.assertEqual(str(caught.exception), "no candidate", module.__name__)

    def test_lung_gate_names_are_read_by_their_signs(self):
        self.assertEqual(lung.population("D006_CD45-CD31-EpCAM-_1"), "stromal")  # triple negative (rule 4)
        self.assertEqual(lung.population("D006_CD45-EpCAM+_1"), "epithelial")
        self.assertEqual(lung.population("D006_CD45-CD31+_1"), "endothelial")
        self.assertIsNone(lung.population("D006_CD45neg_1"))
        self.assertEqual(lung.population("D12_CD45pos"), "immune")

    def test_lung_exclusions_are_whole_words_and_a_population_beside_one_is_doubt(self):
        self.assertIsNone(lung.population("D006_Mixed_immune_1"))
        self.assertEqual(lung.population("D006_EPI_pool1"), "epithelial")
        self.assertEqual(lung.population("D006_EPI_pooled"), "epithelial")
        self.assertEqual(lung.population("LMAP_D006_PMX_1"), "excluded")

    def test_a_lung_name_without_a_donor_stops_the_automatic_map(self):
        with self.assertRaises(SystemExit):
            lung.read_label_map(["D1_EPI", "EPI_2"])

    def test_lymph_node_well_codes_are_not_regions_and_two_regions_are_doubt(self):
        from benchmark import ln_heldout_intake as ln
        self.assertIsNone(ln.region("tonsil_K562_S2-B1_1_3001.d"))
        self.assertEqual(ln.region("GC3_S2-B4"), "germinal centre")
        self.assertEqual(ln.region("Mantle2_S2-B5"), "mantle zone")
        self.assertIsNone(ln.region("GC1_Mantle2"))

    def test_a_label_map_is_checked_before_anything_is_written(self):
        import tempfile

        import pandas as pd
        from benchmark.heldout_intake import write_labels
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            bad = pd.DataFrame({"cell_id": ["a", "b"], "group": ["B zone", "T zone"]})  # no scored column
            with self.assertRaises(SystemExit):
                write_labels(bad, out, {}, groups={"B zone", "T zone", "epithelium"})
            self.assertFalse((out / "label_map.csv").exists())
            spelled = pd.DataFrame({"cell_id": ["a", "b"], "group": ["B zone", "T Zone"], "scored": [True, True]})
            with self.assertRaises(SystemExit):
                write_labels(spelled, out, {}, groups={"B zone", "T zone", "epithelium"})
            twice = pd.DataFrame({"cell_id": ["a", "a"], "group": ["B zone", "T zone"], "scored": [True, True]})
            with self.assertRaises(SystemExit):
                write_labels(twice, out, {}, groups={"B zone", "T zone", "epithelium"})
            no_donor = pd.DataFrame({"cell_id": ["a"], "group": ["epithelial"], "scored": [True]})
            with self.assertRaises(SystemExit):
                write_labels(no_donor, out, {}, groups=set(lung.LINEAGES), required=("donor",))
            self.assertFalse((out / "label_map.csv").exists())

    def test_the_auroc_p_value_refuses_a_score_that_is_not_a_number(self):
        import numpy as np
        from benchmark.heldout_score import auroc_with_p
        with self.assertRaises(ValueError):
            auroc_with_p(np.array([0.9, np.nan, 0.1, 0.2]), np.array([True, True, False, False]))


class LockedTestIntegrity(unittest.TestCase):
    """What the scorers trust from the intake, and what the intakes refuse."""

    def test_a_changed_intake_output_stops_the_scorer(self):
        import json
        import tempfile
        from unittest import mock

        from benchmark import heldout_intake, ln_heldout_score, lung_heldout_score
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "label_map.csv").write_text("cell_id,group,scored\na,B zone,True\n", encoding="utf-8")
            good = heldout_intake.sha256(out / "label_map.csv")
            (out / "intake.json").write_text(json.dumps({"outputs": {"label_map.csv": good}}), encoding="utf-8")
            heldout_intake.check_outputs(out)  # unchanged: no error
            (out / "label_map.csv").write_text("cell_id,group,scored\na,T zone,True\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as caught:
                heldout_intake.check_outputs(out)
            self.assertIn("label_map.csv", str(caught.exception))
            for scorer in (ln_heldout_score, lung_heldout_score):
                with mock.patch.object(scorer, "out_dir", return_value=out), self.assertRaises(SystemExit) as caught:
                    scorer.main(["--rehearse"])
                self.assertIn("label_map.csv", str(caught.exception), scorer.__name__)

    def test_an_intake_record_without_its_outputs_stops_the_scorer(self):
        import json
        import tempfile

        import pandas as pd
        from benchmark import heldout_intake
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for record in ({}, {"outputs": {}}):
                (out / "intake.json").write_text(json.dumps(record), encoding="utf-8")
                with self.assertRaises(SystemExit) as caught:
                    heldout_intake.check_outputs(out)
                self.assertIn("records no outputs", str(caught.exception))
        labels = pd.DataFrame({"cell_id": ["a", "b"], "group": ["B zone", "T zone"], "scored": [True, True],
                               "donor": ["d1", None]})
        with self.assertRaises(SystemExit) as caught:
            heldout_intake.check_labels(labels, required=("donor",))
        self.assertIn("without a donor", str(caught.exception))
        labels["donor"] = ["d1", "None"]
        with self.assertRaises(SystemExit):
            heldout_intake.check_labels(labels, required=("donor",))

    def test_the_organ_scripts_refuse_vivome_overrides(self):
        import os
        from unittest import mock

        import tempfile

        from benchmark import ln_heldout_intake as ln
        from benchmark import ln_heldout_score, lung_heldout_score
        ran = AssertionError("the guarded work ran")
        with tempfile.TemporaryDirectory() as tmp:
            for module, work in ((ln, "rehearsal_files"), (lung, "rehearsal_files"),
                                 (ln_heldout_score, "score"), (lung_heldout_score, "score")):
                with mock.patch.dict(os.environ, {"VIVOME_GENE_ID_MAP": "elsewhere.tsv"}), \
                        mock.patch.object(module, "out_dir", return_value=Path(tmp) / "x"), \
                        mock.patch.object(module, work, side_effect=ran), self.assertRaises(SystemExit) as caught:
                    module.main(["--rehearse"])
                self.assertIn("VIVOME_GENE_ID_MAP", str(caught.exception), module.__name__)

    def test_a_void_set_is_recorded_once_opened(self):
        import json
        import tempfile
        from unittest import mock

        import pandas as pd
        from benchmark import ln_heldout_intake as ln
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "summary.json"
            few = pd.DataFrame({"cell_id": ["a", "b"], "group": ["B zone", "T zone"], "scored": [True, True]})
            with mock.patch.object(ln, "void_record", return_value=record), self.assertRaises(SystemExit):
                ln.intake(few, Path(tmp) / "m.tsv", Path(tmp) / "heldout_pxd042367", Path(tmp), {})
            self.assertTrue(json.loads(record.read_text(encoding="utf-8"))["void"].startswith("too few"))
            record.unlink()
            with mock.patch.object(ln, "void_record", return_value=record), self.assertRaises(SystemExit):
                ln.intake(few, Path(tmp) / "m.tsv", Path(tmp) / "heldout_pxd042367_rehearsal", Path(tmp), {})
            self.assertFalse(record.exists(), "a rehearsal records nothing")


class ColonGuards(unittest.TestCase):
    """The colon's locked test (PXD052341) has the lymph node's and lung's
    guards: no candidate, no unsealing; no overrides; the intake's files
    checked by the scorer."""

    def test_the_labels_step_checks_for_a_frozen_candidate_first(self):
        from unittest import mock
        with mock.patch.object(colon, "candidate_dir", side_effect=SystemExit("no candidate")), \
                mock.patch.object(colon, "_check_download", side_effect=AssertionError("a sealed file was touched")):
            with self.assertRaises(SystemExit) as caught:
                colon.main(["--labels"])
        self.assertEqual(str(caught.exception), "no candidate")

    def test_overrides_are_refused_and_the_scorer_checks_the_intake(self):
        import json
        import os
        import tempfile
        from unittest import mock

        from benchmark import colon_heldout_score, heldout_intake
        ran = AssertionError("the guarded work ran")
        with tempfile.TemporaryDirectory() as tmp:
            for module, work in ((colon, "rehearsal_files"), (colon_heldout_score, "score")):
                with mock.patch.dict(os.environ, {"VIVOME_GENE_ID_MAP": "elsewhere.tsv"}), \
                        mock.patch.object(module, "out_dir", return_value=Path(tmp) / "x"), \
                        mock.patch.object(module, work, side_effect=ran), self.assertRaises(SystemExit) as caught:
                    module.main(["--rehearse"])
                self.assertIn("VIVOME_GENE_ID_MAP", str(caught.exception), module.__name__)
            out = Path(tmp)
            (out / "label_map.csv").write_text("a\n", encoding="utf-8")
            (out / "intake.json").write_text(json.dumps({"outputs": {"label_map.csv": "0" * 64}}), encoding="utf-8")
            with mock.patch.object(colon_heldout_score, "out_dir", return_value=out), \
                    mock.patch.object(colon_heldout_score, "score", side_effect=ran), self.assertRaises(SystemExit) as caught:
                colon_heldout_score.main(["--rehearse"])
            self.assertIn("label_map.csv", str(caught.exception))
            self.assertTrue(callable(heldout_intake.check_outputs))


class ColonNames(unittest.TestCase):
    def test_groups_by_meaning(self):
        self.assertEqual(colon._group_of("Crypt bottom epithelium"), "crypt bottom")
        self.assertEqual(colon._group_of("Upper crypt epithelium"), "upper crypt")
        self.assertEqual(colon._group_of("Goblet cells, crypt bottom"), "goblet")
        self.assertEqual(colon._group_of("PDGFRA+ fibroblasts"), "fibroblast")
        self.assertEqual(colon._group_of("CD45+ immune cells, upper crypt"), "immune")
        self.assertIsNone(colon._group_of("enteroendocrine"))


class OrganBaselines(unittest.TestCase):
    """benchmark/organ_baselines.py: the correlation rule finds each class's own
    profile, and groups take their best class or their summed votes."""

    def test_a_constant_gene_z_scores_to_zero_as_the_service_does(self):
        import numpy as np
        from benchmark import organ_baselines as ob
        rng = np.random.default_rng(0)
        q = rng.normal(size=(20, 3)).astype(np.float32)
        q[:, 1] = np.float32(7.3)  # float32's mean misses 7.3 by a rounding error
        q[:, 2] = np.float32(23.1)
        z = ob.query_z(q)
        np.testing.assert_array_equal(z[:, 1:], 0.0)
        self.assertGreater(np.abs(z[:, 0]).max(), 0.5)

    def test_correlation_picks_the_class_whose_mean_the_sample_follows(self):
        import numpy as np
        from benchmark import organ_baselines as ob
        rng = np.random.default_rng(0)
        means = rng.normal(size=(3, 40))
        labels = np.repeat(np.array(["a", "b", "c"]), 50)
        rna_z = np.repeat(means, 50, axis=0) + rng.normal(scale=0.1, size=(150, 40))
        q = np.stack([means[2], means[0]]) * 2.0 + 5.0  # on another scale, as a protein upload is
        q[0, :10] = np.nan
        scores, classes = ob.correlation_scores(rna_z, labels, q)
        self.assertEqual([classes[i] for i in scores.argmax(1)], ["c", "a"])

    def test_groups_take_the_best_class_or_the_summed_votes(self):
        import numpy as np
        from benchmark import organ_baselines as ob
        h = {"a": {"group": "G1", "lineage": "L"}, "b": {"group": "G1", "lineage": "L"}, "c": {"group": "G2", "lineage": "L"}}
        s = np.array([[0.2, 0.5, 0.3]])
        self.assertEqual(ob.by_level(s, ["a", "b", "c"], h, "group", "max").to_dict("records"), [{"G1": 0.5, "G2": 0.3}])
        self.assertEqual(ob.by_level(s, ["a", "b", "c"], h, "group", "sum").to_dict("records"), [{"G1": 0.7, "G2": 0.3}])

    def test_the_knn_space_is_centred_on_the_reference_not_on_its_sample(self):
        """Classes sampled unequally leave the sample's mean off the class-balanced
        centre; queries are projected around the centre (amendment 3), so an
        upload with nothing measured lands on it."""
        import numpy as np
        from benchmark import organ_baselines as ob
        rng = np.random.default_rng(1)
        labels = np.array(["big"] * 900 + ["small"] * 60)
        rna = np.vstack([rng.normal(1.0, 0.3, (900, 60)), rng.normal(-1.0, 0.3, (60, 60))])
        ref, ref_labels, qp = ob.knn_space(rna, labels, np.full((1, 60), np.nan))
        np.testing.assert_allclose(qp, 0.0)
        self.assertEqual(len(ref), 960)
        small = rna[labels == "small"].mean(0) + 3.0  # another scale, as a protein upload is
        q = np.vstack([small, rna[labels == "big"].mean(0) + 3.0])
        q[:, :20] = np.nan
        votes, classes = ob.knn_votes(*ob.knn_space(rna, labels, q), ["big", "small"])
        self.assertEqual([classes[i] for i in votes.argmax(1)], ["small", "big"])

    def test_a_sample_without_a_score_is_called_none_not_a_crash(self):
        """Correlation leaves a sample with under 3 measured genes without a
        score: the lung counts it wrong, the lymph node leaves it out."""
        import warnings

        import numpy as np
        import pandas as pd
        from benchmark import organ_baselines as ob
        h = {"a": {"group": "G1", "lineage": "epithelial"}, "b": {"group": "G2", "lineage": "immune"},
             "c": {"group": "G3", "lineage": "stromal"}}
        scores = np.array([[0.9, 0.1, 0.0], [np.nan, np.nan, np.nan], [0.8, 0.1, 0.0], [0.7, 0.2, 0.0],
                           [0.2, 0.8, 0.0], [0.1, 0.9, 0.0], [0.3, 0.6, 0.0], [0.0, 0.0, 0.9], [0.9, 0.0, 0.1]])
        labels = pd.DataFrame({"group": ["epithelial"] * 4 + ["immune"] * 3 + ["stromal"] * 2, "scored": ["True"] * 9})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lung = ob.score_entry("lung", scores, ["a", "b", "c"], h, labels, "max")
            hl = {"b": {"group": "B cell", "lineage": "lymphoid"}, "t": {"group": "T cell", "lineage": "lymphoid"}}
            s = np.array([[0.9, 0.1], [0.1, 0.9], [np.nan, np.nan], [0.8, 0.3], [0.2, 0.7]])
            zones = pd.DataFrame({"group": ["B zone", "T zone", "B zone", "B zone", "T zone"]})
            ln = ob.score_entry("ln", s, ["b", "t"], hl, zones, "max")
        self.assertEqual(lung["unscorable_samples"], 1)
        # stromal has 2 samples, under the protocol's 3, so it is left out (rule 7);
        # epithelial 3 of 4 (the unscorable one is wrong), immune 3 of 3
        self.assertEqual(lung["balanced_accuracy"], 87.5)
        self.assertEqual(lung["lineages_scored"], ["epithelial", "immune"])
        self.assertEqual(lung["called_by_lineage"][ob.NONE]["epithelial"], 1)
        self.assertEqual((ln["unscorable_samples"], ln["auroc_b_over_t"]), (1, 1.0))
        self.assertEqual(ln["argmax_group_by_zone"][ob.NONE]["B zone"], 1)


if __name__ == "__main__":
    unittest.main()
