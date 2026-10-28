"""The bank's list (corpus/bank.json) and its guards: every entry carries a
provenance label, nothing sealed is named, and the package stands alone."""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from valuescale.corpus import denylist
from valuescale.corpus.fetch import BANK, load_bank

PACKAGE = Path(__file__).resolve().parents[1]
STRENGTHS = {"documented", "named", "author_code", "inferred"}


class BankTests(unittest.TestCase):
    def setUp(self):
        self.bank = json.loads(BANK.read_text(encoding="utf-8"))

    def test_every_entry_has_a_provenance_label(self):
        for entry in self.bank["entries"]:
            with self.subTest(entry=entry["id"]):
                self.assertIn(entry["label"], ("linear", "log"))
                self.assertIn(entry["label_strength"], STRENGTHS)
                basis = entry["basis"]
                if isinstance(basis, str):
                    self.assertIn(basis, self.bank["quotes"])
                    basis = self.bank["quotes"][basis]
                self.assertTrue(basis["quote"].strip() and basis["source"].strip())
                self.assertTrue(entry["cases"])
                self.assertTrue(("path" in entry) != ("url" in entry), "a local path or a download, not both")

    def test_ids_are_unique(self):
        ids = [e["id"] for e in self.bank["entries"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_both_labels_and_the_known_cases_are_present(self):
        labels = {e["label"] for e in self.bank["entries"]}
        cases = {c for e in self.bank["entries"] for c in e["cases"]}
        self.assertEqual(labels, {"linear", "log"})
        for case in ("linear-small-scale", "known-misread", "disputed-label", "log-centred", "log-nonnegative",
                     "log-imputed", "same-cells-every-step", "single-cell"):
            self.assertIn(case, cases)

    def test_no_sealed_accession_is_listed(self):
        load_bank()  # raises SealedData on any sealed path, URL or accession
        text = BANK.read_text(encoding="utf-8").upper()
        for accession in denylist.SEALED:
            self.assertNotIn(accession, text)


class DenylistTests(unittest.TestCase):
    def test_sealed_names_raise_in_any_case_and_position(self):
        for text in ("PXD042367", "data/incoming/public_sets/Coscia2023_PXD042367/x.rar",
                     "https://massive-ftp.ucsd.edu/v07/msv000094189/proteinGroups.txt", "Post2025_pxd052341",
                     "PXD061065/report.tsv"):
            with self.subTest(text=text), self.assertRaises(denylist.SealedData):
                denylist.check(text)

    def test_other_names_pass(self):
        denylist.check("PXD049412", "data/incoming/public_sets/PXD064083/SEARCH_T.xlsx", "PXD04236")


class StandaloneTests(unittest.TestCase):
    def test_nothing_imports_the_service(self):
        for path in PACKAGE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    with self.subTest(file=path.name, module=name):
                        self.assertFalse(name == "service" or name.startswith(("service.", "benchmark")))


if __name__ == "__main__":
    unittest.main()
