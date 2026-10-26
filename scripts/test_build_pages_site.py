import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import build_pages_site as bps

HAS_PARQUET = importlib.util.find_spec("pyarrow") is not None and importlib.util.find_spec("numpy") is not None


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
            bps.build(None, dist, profiles=False, beta=None)
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
            bps.build(None, dist, profiles=False, beta=None)
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
            bps.build("bucket", dist, profiles=False, beta=None)
            routes = json.loads((dist / "site" / "_routes.json").read_text())["include"]
            self.assertEqual(routes[0], "/api/*")
            data = [r for r in routes if r.startswith("/data/")]
            self.assertTrue(data and len(data) == len(routes) - 1 - len(bps.MEDIA))
            self.assertIn('bucket_name = "bucket"', (dist / "wrangler.toml").read_text())


class GateTests(unittest.TestCase):
    def test_the_sign_in_stands_in_front_of_every_path_with_the_invited_emails(self):
        with tempfile.TemporaryDirectory() as tmp:
            emails, dist = Path(tmp) / "emails.txt", Path(tmp) / "dist"
            emails.write_text("# invited\nOwner@Example.org\n\nfriend@example.org  # a note\nowner@example.org\n")
            bps.build(None, dist, profiles=False, beta=emails)
            gate = (dist / "functions" / "_middleware.js").read_text(encoding="utf-8")
            routes = json.loads((dist / "site" / "_routes.json").read_text())["include"]
            proxy = (dist / "functions" / "api" / "[[path]].js").exists()
        self.assertIn('export const EMAILS = ["owner@example.org", "friend@example.org"];', gate)
        self.assertEqual(gate.replace('["owner@example.org", "friend@example.org"]', "[]"),
                         bps.GATE.read_text(encoding="utf-8"), "only the list differs from the source")
        self.assertEqual(routes, ["/*"], "every path goes through the sign-in")
        self.assertTrue(proxy, "the service's door is still there, behind the sign-in")

    def test_no_build_without_an_invited_email(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            dist.mkdir()
            (dist / "keep").write_text("an earlier build")
            with self.assertRaises(SystemExit):
                bps.build(None, dist, profiles=False, beta=Path(tmp) / "missing.txt")
            (Path(tmp) / "empty.txt").write_text("# nobody yet\n")
            with self.assertRaises(SystemExit):
                bps.build(None, dist, profiles=False, beta=Path(tmp) / "empty.txt")
            self.assertTrue((dist / "keep").exists(), "a refused build leaves the earlier one as it was")

    def test_a_line_that_is_not_an_email_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "emails.txt"
            for bad in ("owner at example.org", 'a"b@example.org', "a@b"):
                path.write_text(bad + "\n")
                with self.assertRaises(SystemExit, msg=bad):
                    bps.invited(path)

    def test_without_the_gate_only_the_service_and_media_wake_a_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            bps.build(None, dist, profiles=False, beta=None)
            self.assertFalse((dist / "functions" / "_middleware.js").exists())


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


@unittest.skipUnless(HAS_PARQUET, "needs numpy and pyarrow (the vivome environment)")
class ProfileTests(unittest.TestCase):
    def write_source(self, web, order=None, dtype="float32"):
        import numpy as np
        import pyarrow as pa
        import pyarrow.parquet as pq
        n = 70
        values = np.random.default_rng(0).normal(size=(n, 3)).astype(dtype)
        columns = {"latent_dim": np.full(n, 128), "orig_index": np.arange(n) if order is None else order,
                   "class_name": ["cd4-positive, alpha-beta t cell"] * n}
        columns.update({f"gene_{g}": values[:, i] for i, g in enumerate(["CD3E", "MS4A1", "NKG7"])})
        (web / "data").mkdir(parents=True)
        pq.write_table(pa.table(columns), web / bps.PROFILES["rna"])
        return values

    def test_shards_hold_every_cell_in_order_with_an_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            web, site = Path(tmp) / "web", Path(tmp) / "site"
            values = self.write_source(web)
            index = bps.write_profiles(site, web, cells=32)
            folder = site / "data" / "profiles"
            self.assertEqual(json.loads((folder / "index.json").read_text()), index)
            self.assertEqual(index["cells_per_shard"], 32)
            entry = index["rna"]
            self.assertEqual((entry["cells"], entry["shards"]), (70, 3))
            self.assertEqual(entry["genes"], ["CD3E", "MS4A1", "NKG7"])
            self.assertEqual(entry["file"], "rna/{shard}.f32.gz")
            names = sorted(p.name for p in (folder / "rna").iterdir())
            self.assertEqual(names, ["00000.f32.gz", "00001.f32.gz", "00002.f32.gz"])
            data = b"".join(gzip.decompress((folder / "rna" / name).read_bytes()) for name in names)
            self.assertEqual(data, values.astype("<f4").tobytes(), "every value, as float32, cell after cell")

    def test_the_same_values_give_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = Path(tmp) / "web"
            self.write_source(web)
            bps.write_profiles(Path(tmp) / "a", web)
            bps.write_profiles(Path(tmp) / "b", web)
            shard = Path("data", "profiles", "rna", "00000.f32.gz")
            self.assertEqual((Path(tmp) / "a" / shard).read_bytes(), (Path(tmp) / "b" / shard).read_bytes(),
                             "a redeploy then uploads no shard again")

    def test_no_shards_without_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            web, site = Path(tmp) / "web", Path(tmp) / "site"
            (web / "data").mkdir(parents=True)
            (web / bps.PROFILES["rna"]).write_text("version https://git-lfs.github.com/spec/v1\noid sha256:00\nsize 1\n")
            self.assertEqual(bps.write_profiles(site, web), {})
            self.assertFalse((site / "data" / "profiles").exists())

    def test_a_source_out_of_order_or_not_float32_is_refused(self):
        import numpy as np
        for kwargs in ({"order": np.arange(70)[::-1].copy()}, {"dtype": "float64"}):
            with tempfile.TemporaryDirectory() as tmp:
                web = Path(tmp) / "web"
                self.write_source(web, **kwargs)
                with self.assertRaises(ValueError):
                    bps.write_profiles(Path(tmp) / "site", web)

    def test_the_real_site_with_its_shards_fits_pages(self):
        import pyarrow.parquet as pq
        source = bps.WEB / bps.PROFILES["rna"]
        if bps.is_lfs_pointer(source):
            self.skipTest("the RNA atlas is an unfetched LFS object")
        static, _ = bps.plan()
        cells = pq.ParquetFile(source).metadata.num_rows
        self.assertLess(len(static) + -(-cells // bps.PROFILE_CELLS) + 10, bps.MAX_FILES)


if __name__ == "__main__":
    unittest.main()
