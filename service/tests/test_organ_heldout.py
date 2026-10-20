"""The organ references' locked tests: how their intakes read sample names
(research/benchmark/protocol-lung-msv000094189.md, rules 3 and 4;
protocol-colon-pxd052341.md, rules 3 to 5). Written before either set is
opened, on invented names."""
import unittest

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
        self.assertIsNone(ln.region("calamari_Whisper_T1_S1-B8_1_3811.d"))  # a T region on plate well B8
        self.assertIsNone(ln.region("run_0042.d"))
        with self.assertRaises(SystemExit):
            ln.read_label_map(["tonsil_TZ1", "run_7.d"])


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
        h = {"a": {"group": "G1", "lineage": "epithelial"}, "b": {"group": "G2", "lineage": "immune"}}
        scores = np.array([[0.9, 0.1], [np.nan, np.nan], [0.2, 0.8]])
        labels = pd.DataFrame({"group": ["epithelial", "epithelial", "immune"], "scored": ["True"] * 3})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lung = ob.score_entry("lung", scores, ["a", "b"], h, labels, "max")
            hl = {"b": {"group": "B cell", "lineage": "lymphoid"}, "t": {"group": "T cell", "lineage": "lymphoid"}}
            s = np.array([[0.9, 0.1], [0.1, 0.9], [np.nan, np.nan], [0.8, 0.3], [0.2, 0.7]])
            zones = pd.DataFrame({"group": ["B zone", "T zone", "B zone", "B zone", "T zone"]})
            ln = ob.score_entry("ln", s, ["b", "t"], hl, zones, "max")
        self.assertEqual(lung["unscorable_samples"], 1)
        self.assertEqual(lung["balanced_accuracy"], 75.0)  # epithelial 1 of 2, immune 1 of 1
        self.assertEqual(lung["called_by_lineage"][ob.NONE]["epithelial"], 1)
        self.assertEqual((ln["unscorable_samples"], ln["auroc_b_over_t"]), (1, 1.0))
        self.assertEqual(ln["argmax_group_by_zone"][ob.NONE]["B zone"], 1)


if __name__ == "__main__":
    unittest.main()
