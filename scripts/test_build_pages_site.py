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
            self.assertEqual(routes["include"], ["/api/*", *sorted(f"/{rel}" for rel in bps.MEDIA)],
                             "only /api and the media files wake a Function")
            toml = (dist / "wrangler.toml").read_text()
            self.assertIn(f'SERVICE_URL = "{bps.service_url()}"', toml)
            self.assertTrue(bps.service_url().startswith("https://"))
            self.assertNotIn("SECRET", toml, "the secret is never written to a file")

    def test_every_static_file_carries_the_security_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            bps.build(None, dist)
            lines = (dist / "site" / "_headers").read_text().splitlines()
        self.assertEqual(lines[0], "/*", "one rule, for every path")
        sent = dict(line.strip().split(": ", 1) for line in lines[1:])
        self.assertEqual(sent["X-Frame-Options"], "DENY")
        self.assertEqual(sent["Content-Security-Policy"], "frame-ancestors 'none'")
        self.assertEqual(sent["X-Content-Type-Options"], "nosniff")
        self.assertIn("camera=()", sent["Permissions-Policy"])
        self.assertNotIn("fullscreen", sent["Permissions-Policy"], "the film may still go full screen")
        self.assertTrue(all(line.startswith("  ") for line in lines[1:]), "Pages reads indented lines as headers")

    def test_with_r2_the_large_files_are_routed_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            bps.build("bucket", dist)
            routes = json.loads((dist / "site" / "_routes.json").read_text())["include"]
            self.assertEqual(routes[0], "/api/*")
            data = [r for r in routes if r.startswith("/data/")]
            self.assertTrue(data and len(data) == len(routes) - 1 - len(bps.MEDIA))
            self.assertIn('bucket_name = "bucket"', (dist / "wrangler.toml").read_text())


class MediaTests(unittest.TestCase):
    def test_media_is_stored_as_parts_with_a_function_that_serves_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            web, dist = Path(tmp) / "web", Path(tmp) / "dist"
            (web / "motion" / "film").mkdir(parents=True)
            data = bytes(range(256)) * (bps.PART // 256 * 2 + 3)  # two whole parts and a bit
            (web / "motion" / "film" / "vivome.mp4").write_bytes(data)
            routes = bps.write_media(dist / "site", dist / "functions", web)
            self.assertEqual(routes, ["/motion/film/vivome.mp4"])
            parts = sorted((dist / "site" / "motion" / "film" / "parts").iterdir())
            self.assertEqual([p.name for p in parts], ["vivome.mp4.0000", "vivome.mp4.0001", "vivome.mp4.0002"])
            self.assertEqual(b"".join(p.read_bytes() for p in parts), data)
            code = (dist / "functions" / "motion" / "film" / "[name].js").read_text(encoding="utf-8")
            self.assertIn(f'"size": {len(data)}', code)
            self.assertIn('"parts": "/motion/film/parts/vivome.mp4."', code)
            self.assertNotIn("export const MEDIA = {};", code)

    def test_the_real_film_is_left_out_of_the_static_copy(self):
        static, _ = bps.plan()
        for rel in bps.MEDIA:
            self.assertTrue((bps.WEB / rel).exists(), rel)
            self.assertNotIn(rel, static)


if __name__ == "__main__":
    unittest.main()
