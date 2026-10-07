"""v4.1's gate as a test (benchmark/v41_dev_gate.py): the served best guess
equals an independent recomputation, the answers are v3.1's with the guess
joined, and the development figures match Phase A's record. Skips when
v4.1's spec, Phase A's record or the development uploads are not on this
machine."""
import unittest

from benchmark import v4_dev_gate, v41_dev_gate
from service.pipeline import reference


class V41DevelopmentGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.record = v41_dev_gate.run_gate()
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/build_v41_spec.py.")
        except FileNotFoundError as exc:
            raise unittest.SkipTest(f"a development upload or Phase A's record is missing: {exc}")

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
