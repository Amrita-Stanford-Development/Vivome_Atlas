"""Track G's gate for v4 as a test (benchmark/v4_dev_gate.py): the served
best guess equals an independent recomputation, the answers are v3.1's with
the fused guess joined, and the development figures match Phase 3c's record.
Skips when v4's files, Phase 3c's record or the development uploads are not
on this machine."""
import unittest

from benchmark import v4_dev_gate
from service.pipeline import fusion, reference


class V4DevelopmentGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            bundle = fusion.V4Bundle.load(require_evaluation=False)
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/fetch_v31_members.py and scripts/build_v4_bundle.py.")
        try:
            cls.record = v4_dev_gate.run_gate(bundle)
        except FileNotFoundError as exc:
            raise unittest.SkipTest(f"a development upload or Phase 3c's record is missing: {exc}")

    def test_every_check_passes(self):
        self.assertEqual(self.record["misses"], [])

    def test_every_dataset_reproduces_the_best_guess_cell_by_cell(self):
        for name, entry in self.record["datasets"].items():
            self.assertGreaterEqual(entry["best_guess_agreement_pct"], v4_dev_gate.MIN_AGREEMENT, name)

    def test_the_answers_are_v31s(self):
        for name, entry in self.record["datasets"].items():
            self.assertEqual(entry["committed_sets_not_v31_with_the_guess"], 0, name)
            self.assertEqual(entry["v31_abstentions_differing"], 0, name)


if __name__ == "__main__":
    unittest.main()
