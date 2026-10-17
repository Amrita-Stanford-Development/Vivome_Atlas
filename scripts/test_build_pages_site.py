import json
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
        self.assertEqual(static, [Path("data", "small.csv").as_posix(), "index.html"])
        self.assertEqual(large, [Path("data", "big.csv").as_posix()])

    def test_the_real_site_fits_pages_once_the_large_files_go_to_r2(self):
        static, large = bps.plan()
        self.assertIn("index.html", static)
        self.assertTrue(all((bps.WEB / rel).stat().st_size <= bps.MAX_BYTES for rel in static))
        self.assertLess(len(static), 20_000)  # Pages' file limit on the free plan

    def test_each_redirect_leaves_a_page_that_is_gone_for_one_that_exists(self):
        for old, new in bps.REDIRECTS:
            self.assertFalse((bps.WEB / f"{old.strip('/').removesuffix('.html')}.html").exists(), old)
            self.assertTrue((bps.WEB / f"{new.strip('/') or 'index'}.html").exists(), new)


class BuildTests(unittest.TestCase):
    def test_every_build_carries_the_door_to_the_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            bps.build(None, dist)
            proxy = dist / "functions" / "api" / "[[path]].js"
            self.assertEqual(proxy.read_bytes(), bps.PROXY.read_bytes())
            routes = json.loads((dist / "site" / "_routes.json").read_text())
            self.assertEqual(routes["include"], ["/api/*"], "only /api wakes a Function")
            toml = (dist / "wrangler.toml").read_text()
            self.assertIn(f'SERVICE_URL = "{bps.service_url()}"', toml)
            self.assertTrue(bps.service_url().startswith("https://"))
            self.assertNotIn("SECRET", toml, "the secret is never written to a file")

    def test_with_r2_the_large_files_are_routed_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            bps.build("bucket", dist)
            routes = json.loads((dist / "site" / "_routes.json").read_text())["include"]
            self.assertEqual(routes[0], "/api/*")
            self.assertTrue(all(r.startswith("/data/") for r in routes[1:]) and len(routes) > 1)
            self.assertIn('bucket_name = "bucket"', (dist / "wrangler.toml").read_text())


if __name__ == "__main__":
    unittest.main()
