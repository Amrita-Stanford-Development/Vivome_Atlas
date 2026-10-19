"""scripts/fetch_public_sets.py: its table, and its downloader against a local server."""
import hashlib
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import fetch_public_sets as f

PAYLOAD = os.urandom(5 * (1 << 20) + 12345)  # 5 MiB and a bit: six 1 MiB ranges


class RangeHandler(BaseHTTPRequestHandler):
    requests: list = []
    ignore_range = False
    cut_next = 0  # how many ranged answers to cut off half way, as a dropped connection does

    def do_GET(self):
        rng = self.headers.get("Range")
        type(self).requests.append(rng)
        data = PAYLOAD
        if rng and not type(self).ignore_range:
            a, b = rng.split("=")[1].split("-")
            a, b = int(a), min(int(b), len(data) - 1)
            body = data[a:b + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
        else:
            body = data
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if rng and type(self).cut_next > 0 and len(body) > 10:
            type(self).cut_next -= 1
            body = body[:len(body) // 2]
            self.close_connection = True
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class TableTests(unittest.TestCase):
    def test_every_entry_is_well_formed(self):
        seen = set()
        for e in f.ENTRIES:
            key = (e["group"], e["name"])
            self.assertNotIn(key, seen, key)
            seen.add(key)
            self.assertIn(e["role"], f.ROLES, key)
            self.assertIn(e["tier"], f.TIERS, key)
            self.assertIn(urlparse(e["url"]).hostname, f.HOSTS, key)
            self.assertFalse(e["name"].lower().endswith(f.RAW_SUFFIXES), f"{key} is a raw mass-spectrometry file")
            self.assertTrue(e["url"].endswith(e["name"]) or e["url"].endswith("/content"), key)
            if e["bytes"] is not None:
                self.assertGreater(e["bytes"], 0, key)
            if e["check"]:
                algorithm, value = e["check"]
                self.assertEqual(len(value), {"sha1": 40, "md5": 32}[algorithm], key)

    def test_held_out_sets_are_never_mixed_into_the_free_groups(self):
        roles = {}
        for e in f.ENTRIES:
            roles.setdefault(e["group"], set()).add(e["role"])
        for group, found in roles.items():
            self.assertEqual(len(found), 1, f"{group} mixes roles {found}")

    def test_the_core_set_is_about_four_gigabytes(self):
        core = sum(e["bytes"] for e in f.ENTRIES if e["tier"] == "A")
        self.assertTrue(3e9 < core < 6e9, core)

    def test_the_colon_locked_test_is_held_out_and_only_its_two_processed_files(self):
        # side-tests.md, amendment 7; research/benchmark/protocol-colon-pxd052341.md, "Files used"
        post = [e for e in f.ENTRIES if "PXD052341" in e["url"]]
        self.assertEqual({e["group"] for e in post}, {"Post2025_PXD052341"})
        self.assertEqual({e["role"] for e in post}, {"held_out"})
        self.assertEqual({e["tier"] for e in post}, {"C"})
        self.assertEqual(sorted(e["name"] for e in post), ["DVP_data.pg_matrix.tsv", "Post_et_al_organoid_DVP_metadata.tsv"])

    def test_the_lung_locked_test_is_held_out_and_only_its_maxquant_tables(self):
        # side-tests.md, amendment 9; research/benchmark/protocol-lung-msv000094189.md, "Files used"
        lung = [e for e in f.ENTRIES if "MSV000094189" in e["url"]]
        self.assertEqual({e["group"] for e in lung}, {"LungMAP2025_MSV000094189"})
        self.assertEqual({e["role"] for e in lung}, {"held_out"})
        self.assertEqual({e["tier"] for e in lung}, {"L"})
        self.assertEqual(sorted(e["name"] for e in lung), ["Protein_metadata.csv", "proteinGroups.txt", "summary.txt"])
        dev = {e["group"]: e["role"] for e in f.ENTRIES if e["tier"] == "L" and e["group"] != "LungMAP2025_MSV000094189"}
        self.assertEqual(set(dev.values()), {"development"})

    def test_the_lymph_node_locked_test_is_held_out_and_only_its_niche_results(self):
        # side-tests.md, amendment 11; research/benchmark/protocol-ln-pxd042367.md, "File used"
        ln = [e for e in f.ENTRIES if "PXD042367" in e["url"]]
        self.assertEqual([(e["group"], e["role"], e["tier"], e["name"]) for e in ln],
                         [("Coscia2023_PXD042367", "held_out", "N", "DIANN_results_Fig4.rar")])

    def test_tier_v_is_the_v2_fresh_development_sets_and_holds_nothing_locked(self):
        v = [e for e in f.ENTRIES if e["tier"] == "V"]
        self.assertEqual({e["group"] for e in v}, {"Herrera2025_PXD058626", "Kitata2025_PXD045043"})
        self.assertTrue(all(e["role"] == "development" for e in v))
        self.assertLess(sum(e["bytes"] for e in v), 250e6)

    def test_tier_c_is_the_colon_and_small(self):
        colon = [e for e in f.ENTRIES if e["tier"] == "C"]
        self.assertEqual({e["group"] for e in colon}, {"Post2025_PXD052341", "Zheng2025_PXD057118", "Kabatnik2024_PXD046999"})
        self.assertEqual({e["role"] for e in colon if e["group"] != "Post2025_PXD052341"}, {"development"})
        self.assertLess(sum(e["bytes"] for e in colon), 20e6)


class DownloaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/file.bin"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        RangeHandler.requests.clear()
        RangeHandler.ignore_range = False
        RangeHandler.cut_next = 0
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def item(self, **kw):
        base = f.entry("g", "held_out", "file.bin", self.url, len(PAYLOAD))
        return {**base, **kw}

    def test_a_file_is_fetched_in_ranges_and_recorded(self):
        record = f.fetch(self.item(check=("md5", hashlib.md5(PAYLOAD).hexdigest())), workers=4, chunk=1 << 20, root=self.root)
        dest = self.root / "g" / "file.bin"
        self.assertEqual(dest.read_bytes(), PAYLOAD)
        self.assertEqual(record["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(sorted(p.name for p in dest.parent.iterdir()), ["file.bin"], "no .part files are left behind")
        ranged = [r for r in RangeHandler.requests if r and r != "bytes=0-0"]
        self.assertEqual(len(ranged), 6)

    def test_a_complete_file_is_not_fetched_again(self):
        f.fetch(self.item(), workers=2, chunk=1 << 20, root=self.root)
        RangeHandler.requests.clear()
        f.fetch(self.item(), workers=2, chunk=1 << 20, root=self.root)
        self.assertEqual(RangeHandler.requests, [])

    def test_an_interrupted_download_resumes_without_refetching_finished_ranges(self):
        chunk = 1 << 20
        dest = self.root / "g" / "file.bin"
        dest.parent.mkdir(parents=True)
        part = dest.with_name("file.bin.part")
        with part.open("wb") as fh:
            fh.truncate(len(PAYLOAD))
            fh.write(PAYLOAD[:2 * chunk])  # ranges 0 and 1 arrived before the interruption
        dest.with_name("file.bin.part.json").write_text(json.dumps({"size": len(PAYLOAD), "chunk": chunk, "done": [0, 1]}))
        f.fetch(self.item(), workers=3, chunk=chunk, root=self.root)
        self.assertEqual(dest.read_bytes(), PAYLOAD)
        starts = sorted(int(r.split("=")[1].split("-")[0]) for r in RangeHandler.requests if r and r != "bytes=0-0")
        self.assertEqual(starts, [i * chunk for i in range(2, 6)])

    def test_a_wrong_size_in_the_table_is_refused(self):
        with self.assertRaises(OSError):
            f.fetch(self.item(bytes=len(PAYLOAD) + 1), workers=2, chunk=1 << 20, root=self.root)
        self.assertFalse((self.root / "g" / "file.bin").exists())

    def test_a_wrong_checksum_is_refused(self):
        with self.assertRaises(OSError):
            f.fetch(self.item(check=("md5", "0" * 32)), workers=2, chunk=1 << 20, root=self.root)

    def test_a_connection_dropped_half_way_is_retried(self):
        RangeHandler.cut_next = 2  # http.client raises IncompleteRead, which is not an OSError
        f.fetch_range(self.url, 0, 99, tries=3)
        RangeHandler.cut_next = 2
        record = f.fetch(self.item(), workers=2, chunk=1 << 20, root=self.root)
        self.assertEqual((self.root / "g" / "file.bin").read_bytes(), PAYLOAD)
        self.assertEqual(record["bytes"], len(PAYLOAD))

    def test_a_server_that_ignores_ranges_is_an_error_not_a_corrupt_file(self):
        RangeHandler.ignore_range = True
        with self.assertRaises(OSError):
            f.fetch_range(self.url, 0, 99, tries=1)


class RecordTests(unittest.TestCase):
    def test_the_record_round_trips_with_lf_line_endings(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "r.json"
            f.save_record({"b": {"x": 1}, "a": {"x": 2}}, path)
            self.assertNotIn(b"\r", path.read_bytes())
            self.assertEqual(list(f.load_record(path)), ["a", "b"])
            self.assertEqual(f.load_record(Path(d) / "missing.json"), {})


if __name__ == "__main__":
    unittest.main()
