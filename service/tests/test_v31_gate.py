"""Track F's gate as a test: the served v3.1 pipeline, under NB2's rule
(service flags off), reproduces T1 NB2's development table
(research/notebook-outputs/nb2/tables/dev_datasets.csv) for SCoPE2 and
PBMC240 within the gate's tolerance (benchmark/v31_dev_gate.py)."""
import unittest

from benchmark import v31_dev_gate
from service.pipeline import pipeline, reference


class DevelopmentGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.record = v31_dev_gate.run_gate(pipeline.load_bundle("v3.1"))
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/fetch_v31_members.py.")

    def test_every_figure_is_within_tolerance(self):
        self.assertEqual(self.record["misses"], [])

    def test_the_shares_match_to_two_decimals(self):
        for dataset, entry in self.record["datasets"].items():
            for row in entry["figures"]:
                if row["kind"] == "share":
                    self.assertAlmostEqual(row["v31"], row["nb2"], places=2, msg=f"{dataset} {row['figure']}")

    def test_the_service_parser_reproduces_nb2s_committed_and_abstention_shares(self):
        shares = {r["figure"]: r for r in self.record["pbmc240_service_parser"]["figures"] if r["kind"] == "share"}
        for figure in ("committed", "abstain_ood", "abstain_ambiguous", "abstain_empty"):
            self.assertAlmostEqual(shares[figure]["v31"], shares[figure]["nb2"], places=2, msg=figure)


if __name__ == "__main__":
    unittest.main()
