"""scripts/build_organ_reference.py's parts (scripts/organ_reference/), on a
tiny synthetic h5ad: CPU only, no Drive file read. Blood's real reproduction
is research/notebook-outputs/organ_builder_blood/."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import h5py
import numpy as np
import scipy.sparse as sp

from organ_reference import data, gene_space, labels, modules, profiles, scenarios

SIM_GENERATOR_SHA256 = "c1819784459abd8b105b6176565bbee5a3ff6206c48bc15a8b3402ba7db30fc7"  # NB1's copy on Drive


def _categorical(group, name, values):
    cats = np.array(sorted(set(values)))
    node = group.create_group(name)
    node.create_dataset("categories", data=cats.astype("S"))
    node.create_dataset("codes", data=np.searchsorted(cats, values).astype(np.int8))


def write_h5ad(path: Path, X: np.ndarray, cells, genes, obs: dict) -> None:
    with h5py.File(path, "w") as f:
        o = f.create_group("obs")
        o.attrs["_index"] = "cell"
        o.create_dataset("cell", data=np.array(cells, dtype="S"))
        for k, v in obs.items():
            _categorical(o, k, np.array(v))
        var = f.create_group("var")
        var.attrs["_index"] = "index"
        var.create_dataset("index", data=np.array(genes, dtype="S"))
        var.create_dataset("gene_symbol", data=np.array(genes, dtype="S"))
        m = sp.csr_matrix(X.astype(np.float32))
        x = f.create_group("X")
        x.attrs["shape"] = np.array(X.shape)
        x.create_dataset("data", data=m.data)
        x.create_dataset("indices", data=m.indices)
        x.create_dataset("indptr", data=m.indptr)


class Synthetic(unittest.TestCase):
    """60 cells, 3 donors; atlas labels a, b, c (c merged into b) and z (dropped)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        rng = np.random.default_rng(0)
        self.genes = ["A1", "B2", "C3", "D4", "E5", "F6"]
        self.X = rng.random((60, 6)).astype(np.float32) * (rng.random((60, 6)) > 0.3)
        self.label = ["a"] * 24 + ["b"] * 18 + ["c"] * 12 + ["z"] * 6
        self.donor = (["d1", "d2", "d3"] * 20)
        write_h5ad(root / "atlas.h5ad", self.X, [f"cell{i}" for i in range(60)], self.genes,
                   {"cell_ontology_class": self.label, "donor": self.donor})
        self.patch = mock.patch.object(data, "DRIVE", root)
        self.patch.start()
        self.cfg = {"organ": "toy", "rna": "drive:atlas.h5ad", "label_column": "cell_ontology_class", "donor_column": "donor",
                    "merge": {"c": "b"}, "drop": ["z"],
                    "dropped_hierarchy": {"z": {"group": "Z", "lineage": "other"}},
                    "hierarchy": {"a": {"group": "A", "lineage": "one"}, "b": {"group": "B", "lineage": "two"}},
                    "class_rule": {"min_cells": 10, "min_cells_per_donor": 5, "min_donors": 2}}

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_labels_merge_drop_and_keep_atlas_rows(self):
        table, names = labels.build(self.cfg)
        self.assertEqual(names, ["a", "b"])
        self.assertEqual(len(table), 54)
        self.assertEqual(table["row"].tolist(), list(range(54)))  # z was the last six rows
        self.assertEqual(table["class_idx"].tolist(), [0] * 24 + [1] * 30)
        self.assertEqual(set(table["lineage"]), {"one", "two"})
        kept, all_names = labels.build(self.cfg, apply_drop=False)
        self.assertEqual(all_names, ["a", "b", "z"])

    def test_a_class_failing_the_rule_or_a_wrong_hierarchy_stops_the_build(self):
        with self.assertRaises(SystemExit):
            labels.build({**self.cfg, "class_rule": {"min_cells": 25, "min_cells_per_donor": 5, "min_donors": 2}})
        with self.assertRaises(SystemExit):
            labels.build({**self.cfg, "hierarchy": {"a": {"group": "A", "lineage": "one"}}})
        with self.assertRaises(SystemExit):
            labels.build({**self.cfg, "merge": {"nope": "b"}})

    def test_rna_is_read_exactly_in_the_requested_gene_order(self):
        X = data.load_rna(data.resolve(self.cfg["rna"]), ["C3", "a1"])
        np.testing.assert_array_equal(X, self.X[:, [2, 0]])
        with self.assertRaises(ValueError):
            data.load_rna(data.resolve(self.cfg["rna"]), ["NOPE"])


class GeneSpace(unittest.TestCase):
    def test_symbols_split_upper_cased_and_segments_excluded(self):
        self.assertEqual(gene_space.split_symbols(["a1;B2", None, "nan", " c3 "]), {"A1", "B2", "C3"})
        self.assertTrue("IGKV1-5".startswith(gene_space.IG_PREFIX))
        self.assertFalse("IGHA1".startswith(gene_space.IG_PREFIX))


class Splits(unittest.TestCase):
    def test_blood_split_is_nb1s(self):
        y = np.repeat(np.arange(3), [30, 3, 12])
        tr, va, te = scenarios.stratified_split(y, 0.2, 0.15, 0)
        self.assertEqual(sorted(np.concatenate([tr, va, te]).tolist()), list(range(45)))
        self.assertEqual(int((y[te] == 1).sum()), 0)  # a class of 4 or fewer stays in train

    def test_class_donor_split_spreads_each_donor_and_is_a_partition(self):
        y = np.repeat([0, 1], 60)
        donors = np.tile(["d1", "d2", "d3"], 40)
        tr, va, te = scenarios.split({"split": {"stratify": "class_donor", "test": 0.2, "val": 0.15, "seed": 0}}, y, donors)
        self.assertEqual(sorted(np.concatenate([tr, va, te]).tolist()), list(range(120)))
        for d in ("d1", "d2", "d3"):
            for c in (0, 1):
                self.assertEqual(int(((donors[te] == d) & (y[te] == c)).sum()), 4)


    def test_a_reused_split_needs_the_same_rna_file(self):
        """A v2 carries its base's split through the atlas rows, which only
        name the same cells when both read one RNA file."""
        import build_organ_reference as bor
        for organ in ("lymph_node_v2", "lung_v2"):
            cfg = data.load_organ(organ)
            self.assertEqual(cfg["rna"], data.load_organ(cfg["split"]["reuse_from"])["rna"], organ)
        v2 = mock.Mock(cfg={"rna": "a.h5ad", "split": {"reuse_from": "base"}})
        with mock.patch.object(bor, "Build", return_value=mock.Mock(cfg={"rna": "b.h5ad"})):
            with self.assertRaises(SystemExit):
                bor.reused_split(v2)


class Suites(unittest.TestCase):
    def setUp(self):
        self.classes = ["e1", "e2", "i1", "i2", "s1"]
        self.h = {"e1": {"lineage": "epi"}, "e2": {"lineage": "epi"}, "i1": {"lineage": "imm"},
                  "i2": {"lineage": "imm"}, "s1": {"lineage": "str"}}
        self.pool = np.arange(500)
        self.y = np.repeat(np.arange(5), 100)

    def test_uploads_come_from_the_pool_follow_their_scenario_and_repeat_exactly(self):
        a = scenarios.make_suite("t", self.pool, self.y, self.classes, self.h, ("polyp", "random_0.25"), 16, 7)
        b = scenarios.make_suite("t", self.pool, self.y, self.classes, self.h, ("polyp", "random_0.25"), 16, 7)
        self.assertEqual(a, b)
        for spec in a:
            self.assertTrue(set(spec["cell_idx"]) <= set(self.pool.tolist()))
            if spec["scenario"].startswith("lineage:"):
                lineage = spec["scenario"].split(":")[1]
                self.assertTrue(all(self.h[c]["lineage"] == lineage for c in spec["classes"]))
            if spec["scenario"] == "tissue":
                self.assertEqual(spec["classes"], self.classes)
            if spec["profile"].startswith("random"):
                self.assertEqual(spec["missingness"], "none")
        self.assertEqual({s["scenario"] for s in a} >= {"lineage:epi", "lineage:imm", "tissue"}, True)

    def test_capping_per_class_keeps_the_other_classes_shares_and_counts_lineages(self):
        # one class of 6 cells: v1 shrinks every class in its uploads to its size; the cap does not
        y = np.concatenate([np.repeat(np.arange(4), 300), np.full(6, 4)])
        pool = np.arange(len(y))
        v1 = scenarios.make_suite("t", pool, y, self.classes, self.h, ("random_0.25",), 40, 3, min_cells=5)
        v2 = scenarios.make_suite("t", pool, y, self.classes, self.h, ("random_0.25",), 40, 3, min_cells=5, cap_per_class=True)
        self.assertTrue(all("lineages" not in s for s in v1))
        with_short = lambda suite: [s for s in suite if "s1" in s["classes"] and len(s["classes"]) > 1]  # noqa: E731
        self.assertTrue(with_short(v2))
        self.assertGreater(np.mean([len(s["cell_idx"]) for s in with_short(v2)]),
                           np.mean([len(s["cell_idx"]) for s in with_short(v1)]))
        for s in v2:
            self.assertEqual(s["lineages"], len({self.h[c]["lineage"] for c in s["classes"]}))
            self.assertLessEqual(int(np.isin(s["cell_idx"], np.flatnonzero(y == 4)).sum()), 6)

    def test_the_simulator_is_nb1s_copy(self):
        path = Path(scenarios.__file__).with_name("sim_generator.py")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), SIM_GENERATOR_SHA256)


class Profiles(unittest.TestCase):
    def test_profile_from_obs_takes_any_protein_group_per_gene(self):
        obs = np.array([[1, 0, 1], [0, 0, 1], [1, 1, 0], [0, 0, 0]], bool)
        det, frac = profiles.profile_from_obs(obs, ["A", "A", "B"], ["A", "B", "C"])
        np.testing.assert_allclose(det[:2], [0.5, 0.5])
        self.assertTrue(np.isnan(det[2]))
        np.testing.assert_allclose(frac, [1.0, 0.5, 0.5, 0.0])

    def test_rank_transfer_follows_expression_rank(self):
        src = profiles.finish(np.array([True, True, False, False]), np.array([0.9, 0.5, np.nan, np.nan]), np.array([0.3, 0.6]))
        out = profiles.rank_transfer(src, source_mu=np.array([4.0, 3.0, 2.0, 1.0]), target_mu=np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
        # each target gene takes the first source gene at or above its expression quantile
        np.testing.assert_array_equal(out["gene_set"], [False, False, False, True, True])
        self.assertTrue(np.isnan(out["det_prob"][0]))
        np.testing.assert_allclose(out["det_prob"][3:], [0.5, 0.9])
        np.testing.assert_allclose(out["cell_frac"], [0.3, 0.6])


class GeneIds(unittest.TestCase):
    def test_hgncs_rule_symbol_first_then_aliases_that_agree(self):
        from organ_reference import gene_ids
        rows = [["hgnc_id", "symbol", "alias_symbol", "prev_symbol", "ensembl_gene_id", "uniprot_ids"],
                ["HGNC:1", "C1orf1", "", "", "ENSG1", "P1"],
                ["HGNC:2", "NEWNAME", "OLDA", "", "ENSG2", "P2|P3"],
                ["HGNC:3", "XA", "TWIN", "", "ENSG3", "P4"],
                ["HGNC:4", "XB", "", "TWIN", "ENSG4", "P5"]]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "hgnc.txt"
            path.write_bytes(("\n".join("\t".join(r) for r in rows) + "\n").encode("utf-8"))
            t = gene_ids.build(["C1ORF1", "OLDA", "TWIN", "NOPE"], path)
        self.assertEqual(t["match_type"].tolist(), ["symbol", "alias_or_prev_symbol", "ambiguous", "unmapped"])
        self.assertEqual(t.loc[1, "uniprot_ids"], "P2|P3")
        self.assertEqual(t.loc[2, "ambiguous_candidates"], "HGNC:3|HGNC:4")
        self.assertEqual(t.loc[2, "ensembl_gene_id"], "")


class Modules(unittest.TestCase):
    def test_every_gene_gets_a_module_of_about_the_target_size(self):
        X = np.random.default_rng(1).random((300, 72)).astype(np.float32)
        mod = modules.build(X, target_size=6, cells=200, pca=8, seed=0)
        self.assertEqual(len(mod), 72)
        self.assertTrue(0 <= mod.min() and mod.max() < 12)
        np.testing.assert_array_equal(mod, modules.build(X, target_size=6, cells=200, pca=8, seed=0))



class QhatOptions(unittest.TestCase):
    """organ references v2's calibration options (calibrate.fit_qhat_v2)."""

    def setUp(self):
        from organ_reference import calibrate
        self.calibrate, self.n2 = calibrate, calibrate.n2
        rng = np.random.default_rng(0)
        self.y = np.concatenate([np.repeat(0, 400), np.repeat(1, 400), np.repeat(2, 60)])
        self.scores = rng.uniform(0, 1, len(self.y)) ** np.where(self.y == 2, 0.2, 2.0)
        # class 2's 60 rows are only 12 distinct cells, each drawn five times
        self.cells = np.concatenate([np.arange(400), np.arange(400, 800), np.repeat(np.arange(800, 812), 5)])
        self.group_of = np.array([0, 1, 1])

    def test_without_options_it_is_nb2s_fit(self):
        cal = {"alpha": 0.1, "min_n": 50}
        q, m = self.calibrate.fit_qhat_v2(self.scores, self.y, self.cells, 3, cal, self.group_of)
        q0, m0 = self.n2.fit_qhat(self.scores, self.y, 3, 0.1, True, 50)
        np.testing.assert_array_equal(q, q0)
        self.assertEqual(m, m0)

    def test_the_floor_keeps_every_entry_bar_at_or_above_chance(self):
        q, _ = self.calibrate.fit_qhat_v2(self.scores, self.y, self.cells, 3, {"alpha": 0.1, "min_n": 50, "floor": "chance"}, self.group_of)
        self.assertTrue((1.0 - q >= 1.0 / 3 - 1e-12).all())

    def test_a_class_with_few_unique_cells_takes_its_groups_threshold(self):
        cal = {"alpha": 0.1, "min_n": 50, "rare_min": 30}
        q, _ = self.calibrate.fit_qhat_v2(self.scores, self.y, self.cells, 3, cal, self.group_of)
        q0, _ = self.n2.fit_qhat(self.scores, self.y, 3, 0.1, True, 50)
        self.assertEqual(q[0], q0[0])
        self.assertEqual(q[1], q0[1])
        same = np.isin(self.y, [1, 2])
        want = float(np.quantile(self.scores[same], self.n2.conformal_level(int(same.sum()), 0.1), method="higher"))
        self.assertEqual(q[2], want)
        self.assertNotEqual(q[2], q0[2])


if __name__ == "__main__":
    unittest.main()
