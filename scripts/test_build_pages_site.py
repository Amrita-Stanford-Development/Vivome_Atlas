import tempfile
import unittest
from pathlib import Path

import build_pages_site as bps


class PlanTests(unittest.TestCase):
    def test_large_files_are_left_out_and_repository_material_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = Path(tmp)
            (web / "data").mkdir()
            (web / "tests").mkdir()
            (web / "index.html").write_text("<html></html>")
            (web / "README.md").write_text("notes")
            (web / "tests" / "a.test.js").write_text("")
            (web / "data" / "small.csv").write_text("a,b\n")
            with open(web / "data" / "big.csv", "wb") as handle:
                handle.truncate(bps.MAX_BYTES + 1)
            static, large = bps.plan(web)
        self.assertEqual(static, ["data/small.csv", "index.html"])
        self.assertEqual(large, ["data/big.csv"])

    def test_the_real_site_fits_pages_once_the_large_files_go_to_r2(self):
        static, large = bps.plan()
        self.assertIn("index.html", static)
        self.assertTrue(all((bps.WEB / rel).stat().st_size <= bps.MAX_BYTES for rel in static))
        self.assertLess(len(static), 20_000)  # Pages' file limit on the free plan


if __name__ == "__main__":
    unittest.main()
