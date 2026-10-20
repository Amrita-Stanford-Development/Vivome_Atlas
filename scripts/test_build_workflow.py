"""web/data/workflow.json, the Workflow page's data (scripts/build_workflow.py):
the committed file is the builder's output, built for the manifest's release,
inside its size budget, and every number a sentence cites is a record."""
import json
import unittest

import build_workflow as bw

FORMATS = {"count", "percent", "plain", "integer", "fixed2", "fixed3", "fixed4", "points"}


def records(node, path=""):
    """Every dict with a "status" key, with where it sits."""
    if isinstance(node, dict):
        if "status" in node and "value" in node:
            yield path, node
        for k, v in node.items():
            yield from records(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from records(v, f"{path}[{i}]")


class TestWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(bw.MANIFEST.read_text(encoding="utf-8"))
        cls.built = bw.build(cls.manifest)
        cls.committed_bytes = bw.OUTPUT.read_bytes()
        cls.w = json.loads(cls.committed_bytes)

    def test_the_committed_file_is_the_builder_s_output_byte_for_byte(self):
        built = (json.dumps(self.built, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        self.assertEqual(built, self.committed_bytes, "run python scripts/build_manifest.py")

    def test_it_is_built_for_the_manifest_s_release(self):
        self.assertEqual(self.w["built_for"]["atlas_version"], self.manifest["atlas_version"])
        self.assertEqual(self.w["built_for"]["model_name"], self.manifest["model"]["name"])
        self.assertTrue(self.manifest["model"]["name"].endswith(self.w["built_for"]["pipeline_version"]))

    def test_every_source_s_sha256_is_current(self):
        for path, digest in self.w["sources"].items():
            self.assertEqual(bw.sha256(bw.REPO / path), digest, path)

    def test_it_stays_inside_its_size_budget(self):
        self.assertLess(len(self.committed_bytes), bw.SIZE_BUDGET)

    def test_every_record_is_measured_with_a_basis_and_format_or_pending_with_a_note(self):
        found = list(records(self.w))
        self.assertGreater(len(found), 100)
        for path, r in found:
            if r["status"] == "measured":
                self.assertIsNotNone(r["value"], path)
                self.assertTrue(r["basis"], path)
                self.assertIn(r["format"], FORMATS, path)
            else:
                self.assertEqual(r["status"], "pending", path)
                self.assertIsNone(r["value"], path)
                self.assertTrue(r["note"], path)

    def test_the_story_cells_follow_their_rule(self):
        cells, story = self.w["trace"]["cells"], self.w["trace"]["story"]["cells"]
        families = self.w["trace"]["story"]["weak_family"]
        group = {c["name"]: c["group"] for c in self.w["reference"]["classes"]}

        def backed(c):
            if c["level"] not in ("class", "group"):
                return False
            family = group[c["label"]] if c["level"] == "class" else c["label"]
            return families.get(c["weak_label"]) == family

        first = next((i for i, c in enumerate(cells) if backed(c)), 0)
        self.assertEqual(self.w["trace"]["story"]["default"], first, "the first answer its markers back")
        self.assertEqual(story[:2] if first else story[:1], [first, 0] if first else [0])
        for i in story[2 if first else 1:]:
            kind = cells[i]["outcome"]
            self.assertEqual(i, next(j for j, c in enumerate(cells) if c["outcome"] == kind), kind)
        self.assertEqual([d["cell"] for d in self.w["trace"]["detail"]], story)

    def test_outcomes_count_every_cell_and_agree_with_the_astral_record(self):
        outcomes, cells = self.w["trace"]["outcomes"], self.w["trace"]["cells"]
        self.assertEqual(sum(outcomes.values()), len(cells))
        astral = json.loads(bw.ASTRAL.read_text(encoding="utf-8"))["PBMC240"]
        committed = sum(outcomes[k] for k in ("class", "group", "lineage"))
        self.assertAlmostEqual(100 * committed / len(cells), astral["reasons_pct"]["committed"], places=1)
        self.assertAlmostEqual(100 * outcomes["ambiguous_between_classes"] / len(cells),
                               astral["reasons_pct"]["ambiguous_between_classes"], places=1)
        align = self.w["raw"]["pbmc240"]["align"]
        self.assertEqual((align["matched"], align["unmatched_rows"]),
                         (astral["features_matched"], astral["features_unmatched"]))

    def test_any_prefix_of_the_reference_sample_holds_every_class(self):
        n_classes = len(self.w["class_order"])
        self.assertEqual({p[3] for p in self.w["reference"]["sample"][:2500]}, set(range(n_classes)))
        self.assertEqual(len(self.w["reference"]["sample"]), self.w["reference"]["sampled"]["value"])

    def test_the_held_out_cards_keep_their_recorded_results(self):
        cards = {c["key"]: c for c in self.w["evaluation"]["heldout"]}
        self.assertEqual([c["key"] for c in self.w["evaluation"]["heldout"]],
                         ["hao2021", "pxd043355", "pxd073250", "pxd046211", "tian", "pxd021882"])
        self.assertEqual({k: c["result"] for k, c in cards.items()},
                         {"hao2021": "pass", "pxd043355": "pass", "pxd073250": "fail", "pxd046211": "fail",
                          "tian": "void", "pxd021882": "void"})
        for key in ("pxd043355", "pxd073250", "pxd046211"):
            curve = cards[key]["curve"]
            self.assertEqual((curve[0], curve[-1]), ([0.0, 0.0], [1.0, 1.0]), key)

    def test_the_training_recipe_is_read_from_its_code(self):
        recipe = self.w["training"]["recipe"]
        self.assertEqual((recipe["epochs"]["value"], recipe["batch"]["value"]), (60, 512))
        self.assertEqual(recipe["mini_upload_classes"], [1, 2, 3, 5, 8])
        self.assertEqual((recipe["standardisation"], recipe["sampler"]), ("batch_gene", "mini"))
        self.assertEqual(self.w["training"]["history"]["status"], "pending")

    def test_the_service_s_address_is_the_service_client_s(self):
        client = (bw.REPO / "web" / "js" / "atlas" / "service-client.js").read_text(encoding="utf-8")
        self.assertIn(f"DEFAULT_SERVICE_URL = '{self.w['service']['url']}'", client)


if __name__ == "__main__":
    unittest.main()
