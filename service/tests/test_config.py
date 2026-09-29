"""Drift detection for hardcoded config constants that duplicate a fact
derivable from real reference data. Not a way to eliminate the duplication
(service/ stays deliberately independent of web/data/'s data files —
CLAUDE.md — and a config constant serving as an explicit, reviewed
declaration of what's supported is the same pattern already used for
CONFUSABLE_PAIRS and SHIPPED_PROPERTIES), but catches the case a code
review flagged: if the reference ever changes which classes have real
cross-modal coverage, this test fails loudly instead of the live service
silently drifting from what the data actually supports.
"""
import csv
import unittest

from service import config


class CrossModalSupportedClassesMatchesRealDataTests(unittest.TestCase):
    def test_matches_classes_with_nonzero_protein_cells(self):
        path = config.MODEL_DIR / "evidence" / "v3_tables" / "latent_centroid_cosine.csv"
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        classes_with_protein_coverage = {row["class_name"] for row in rows if int(row["n_prot_cells"]) > 0}
        self.assertEqual(classes_with_protein_coverage, set(config.CROSS_MODAL_SUPPORTED_CLASSES))


if __name__ == "__main__":
    unittest.main()
