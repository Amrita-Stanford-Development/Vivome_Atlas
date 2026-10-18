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


class ColonNames(unittest.TestCase):
    def test_groups_by_meaning(self):
        self.assertEqual(colon._group_of("Crypt bottom epithelium"), "crypt bottom")
        self.assertEqual(colon._group_of("Upper crypt epithelium"), "upper crypt")
        self.assertEqual(colon._group_of("Goblet cells, crypt bottom"), "goblet")
        self.assertEqual(colon._group_of("PDGFRA+ fibroblasts"), "fibroblast")
        self.assertEqual(colon._group_of("CD45+ immune cells, upper crypt"), "immune")
        self.assertIsNone(colon._group_of("enteroendocrine"))


if __name__ == "__main__":
    unittest.main()
