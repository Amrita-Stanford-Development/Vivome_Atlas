"""The Workflow page's trace (scripts/trace_workflow.py) against a fresh run of
the served model on the same file: every cell's outcome, label, level, set
and best guess exactly, and its numbers within the trace's rounding (four
decimals). A trace left behind by a model change fails here."""
import gzip
import json
import unittest
from pathlib import Path

from service import config
from service.pipeline import alignment, pipeline, reference

REPO = Path(__file__).resolve().parents[2]
TRACE = REPO / "service" / "model" / "evidence" / "workflow" / "pbmc240_trace_v41.json.gz"
EXAMPLE = REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv"
ROUNDED = 5e-5 + 1e-6  # stored to 4 decimals; float32 rounding on top


class WorkflowTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace = json.loads(gzip.decompress(TRACE.read_bytes()))
        try:
            bundle = pipeline.load_bundle(cls.trace["built_for"]["pipeline_version"])
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc}")
        raw = alignment.parse_matrix_csv(EXAMPLE.read_text(encoding="utf-8"))
        cls.fresh = json.loads(json.dumps(pipeline.run_projection(bundle, raw, modality="prot")))

    def test_it_was_traced_for_the_served_release(self):
        self.assertEqual(self.trace["built_for"]["atlas_version"], config.ATLAS_VERSION)
        self.assertEqual(self.trace["built_for"]["pipeline_version"], config.PIPELINE_VERSION)
        self.assertEqual(self.trace["built_for"]["model_version"], self.fresh["model_version"])

    def test_every_cell_matches_a_fresh_run(self):
        names = self.trace["class_order"]
        self.assertEqual(len(self.trace["cells"]), len(self.fresh["cells"]))
        for stored, cell in zip(self.trace["cells"], self.fresh["cells"]):
            with self.subTest(cell=cell["cell_id"]):
                self.assertEqual(stored["id"], cell["cell_id"])
                self.assertEqual(stored["outcome"], cell["label_level"] or cell["abstain_reason"])
                self.assertEqual((stored["label"], stored["level"]), (cell["label"], cell["label_level"]))
                self.assertEqual([names[c] for c in stored["set"]], cell["label_set"])
                self.assertEqual(stored["observed"], cell["observed_genes"])
                self.assertLess(abs(stored["similarity"] - cell["reference_similarity"]), ROUNDED)
                for a, b in zip(stored["xyz"], cell["coordinates"]):
                    self.assertLess(abs(a - b), ROUNDED)
                if "best_guess" in cell:
                    self.assertEqual(names[stored["guess"]], cell["best_guess"]["label"])
                    self.assertLess(abs(stored["guess_probability"] - cell["best_guess"]["probability"]), ROUNDED)
                else:
                    self.assertIsNone(stored["guess"])
                if cell["confidence"] is not None:
                    self.assertLess(abs(stored["confidence"] - cell["confidence"]), ROUNDED)

    def test_the_story_cells_responses_are_the_service_s(self):
        for d in self.trace["detail"]:
            stored, cell = d["response"], self.fresh["cells"][d["cell"]]
            self.assertEqual({k: v for k, v in stored.items() if not isinstance(v, (float, dict, list))},
                             {k: v for k, v in cell.items() if not isinstance(v, (float, dict, list))})
            self.assertEqual(stored["label_set"], cell["label_set"])
            self.assertLess(abs(stored["reference_similarity"] - cell["reference_similarity"]), 5e-6)

    def test_the_best_guess_rule_is_the_fresh_run_s(self):
        fusion = self.trace["stages"]["fusion"]
        rule = self.fresh["best_guess_rule"]
        self.assertEqual(fusion["correlation_term"], rule["correlation_term"])
        self.assertEqual(round(fusion["agreement"], 4), rule["agreement"])
        self.assertEqual(fusion["threshold"], rule["agreement_threshold"])


if __name__ == "__main__":
    unittest.main()
