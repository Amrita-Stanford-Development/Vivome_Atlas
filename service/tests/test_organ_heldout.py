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


if __name__ == "__main__":
    unittest.main()
