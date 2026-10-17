"""web/data/manuscript.json, the Manuscript page's records
(scripts/build_manuscript.py): the committed file is the builder's output,
built for the manifest's release, inside its size budget, and every record
is measured with its basis or pending with a note."""
import json
import unittest

import build_manuscript as bm

FORMATS = {"count", "percent", "plain", "fixed2", "fixed3", "fixed4", "points", "pct1", "pct2", "pp"}
# The records the page shows as Pending on purpose: work not done yet.
PENDING_ON_PURPOSE = {"open_sorted_test", "open_khoury_committed", "open_probe_v41", "open_doi"}


class TestManuscript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(bm.MANIFEST.read_text(encoding="utf-8"))
        cls.workflow = json.loads(bm.WORKFLOW.read_text(encoding="utf-8"))
        cls.built = bm.build(cls.manifest, cls.workflow)
        cls.committed_bytes = bm.OUTPUT.read_bytes()
        cls.m = json.loads(cls.committed_bytes)

    def test_the_committed_file_is_the_builder_s_output_byte_for_byte(self):
        built = (json.dumps(self.built, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
        self.assertEqual(built, self.committed_bytes, "run python scripts/build_manifest.py")

    def test_it_is_built_for_the_manifest_s_release(self):
        self.assertEqual(self.m["built_for"]["atlas_version"], self.manifest["atlas_version"])
        self.assertEqual(self.m["built_for"]["model_name"], self.manifest["model"]["name"])

    def test_every_source_s_sha256_is_current(self):
        self.assertIn("web/data/workflow.json", self.m["sources"])
        for path, digest in self.m["sources"].items():
            self.assertEqual(bm.sha256(bm.REPO / path), digest, path)

    def test_it_stays_inside_its_size_budget(self):
        self.assertLess(len(self.committed_bytes), bm.SIZE_BUDGET)

    def test_every_record_is_measured_with_a_basis_and_format_or_pending_with_a_note(self):
        records = self.m["records"]
        self.assertGreater(len(records), 300)
        for key, r in records.items():
            if r["status"] == "measured":
                self.assertIsNotNone(r["value"], key)
                self.assertTrue(r["basis"], key)
                self.assertIn(r["format"], FORMATS, key)
            else:
                self.assertEqual(r["status"], "pending", key)
                self.assertIsNone(r["value"], key)
                self.assertTrue(r["note"], key)
        self.assertEqual({k for k, r in records.items() if r["status"] == "pending"}, PENDING_ON_PURPOSE)

    def test_the_headline_figures_match_their_sources(self):
        r = self.m["records"]
        self.assertEqual(r["fulcher_ba"]["value"], 0.6905)        # v41_phase3/development.json
        self.assertEqual(r["khoury_ba"]["value"], 0.6251)         # khoury2026_posthoc_v41_check
        self.assertEqual(r["suite_correct_when_committed"]["value"], 0.9628)
        self.assertEqual(r["committed_fulcher"]["value"], 0.8698)  # confident.csv, not the run history's 88.6
        self.assertEqual(r["bm_fulcher_favour"]["value"], r["bm_fulcher_pairings"]["value"])
        self.assertEqual(r["suite_checks_passed"]["value"], r["suite_checks"]["value"])
        self.assertEqual(r["ref_cells"]["value"], r["ref_reference_cells_spec"]["value"])
        self.assertEqual(r["wf_rna_cells"]["value"], r["ref_cells"]["value"])

    def test_records_copied_from_the_workflow_data_are_its_records(self):
        for key, value in self.m["records"].items():
            if key.startswith("wf_recipe_"):
                self.assertEqual(value, self.workflow["training"]["recipe"][key.removeprefix("wf_recipe_")], key)
            elif key.startswith("wf_service_"):
                self.assertEqual(value, self.workflow["service"][key.removeprefix("wf_service_")], key)
            elif key.startswith("wf_"):
                self.assertEqual(value, self.workflow["facts"][key.removeprefix("wf_")], key)

    def test_it_refuses_a_workflow_file_from_another_release(self):
        stale = {**self.workflow, "built_for": {**self.workflow["built_for"], "atlas_version": "0.0.1"}}
        with self.assertRaises(SystemExit):
            bm.build(self.manifest, stale)


if __name__ == "__main__":
    unittest.main()
