"""B3's walk, with fake tools in place of the network and the parser."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from valuescale.corpus import draw, tables
from valuescale.corpus.remote import File

REPO = Path(__file__).resolve().parents[2]


def _files(acc):
    """Each fake deposit's files, chosen by its accession's last digit."""
    d = int(acc[-1])
    if d == 0:
        return []
    if d == 1:
        return [File("x.raw", 5, f"https://x/{acc}/x.raw")]
    if d == 2:
        return [File("big/report.pg_matrix.tsv", tables.FILE_MAX + 1, f"https://x/{acc}/big")]
    return [File("proteinGroups.txt", 10, f"https://x/{acc}/proteinGroups.txt")]


def _tools(columns_by_digit=None, raise_on=()):
    columns_by_digit = columns_by_digit or {}

    def list_files(acc, repo):
        if acc in raise_on:
            raise OSError("listing failed")
        return _files(acc)

    def columns_of(entry):
        return None

    def header(entry):
        return ["Majority protein IDs", "Gene names"] + [f"LFQ intensity s{i}" for i in range(columns_by_digit.get(
            int(entry.file.url.split("/")[3][-1]), 400))]

    def fetch(entry, folder):
        return folder / entry.name, {"bytes": entry.file.size, "sha256": "ab" * 32}

    def parse(cand, path):
        acc = path.parent.name
        d = int(acc[-1])
        cols = columns_by_digit.get(d, 400)
        values = np.ones((300 if d != 4 else 150, cols))
        if d == 5:
            values[0, 0] = -1.0
        return draw.Parsed([f"s{i}" for i in range(cols)], values)

    return draw.Tools(list_files, columns_of, lambda f: [], fetch, parse, header)


class VisitTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def visit(self, acc, tools=None):
        return draw.visit(acc, "PRIDE", "calibration", tools or _tools(), self.root)

    def test_each_reason(self):
        self.assertEqual(self.visit("PXD000010")["outcome"], "no candidate")
        self.assertEqual(self.visit("PXD000011")["outcome"], "no candidate")
        self.assertEqual(self.visit("PXD000012")["outcome"], "too large")
        self.assertEqual(self.visit("PXD000014")["outcome"], "too few rows")
        self.assertEqual(self.visit("PXD000015")["outcome"], "unclear label")
        self.assertEqual(self.visit("PXD000013", _tools(raise_on={"PXD000013"}))["outcome"], "no file list")

    def test_a_header_with_too_few_quantity_columns_is_skipped_before_the_fetch(self):
        tools = _tools({3: 12})
        fetched = []
        tools = tools._replace(fetch=lambda e, f: fetched.append(e) or (f / e.name, {}))
        r = self.visit("PXD000013", tools)
        self.assertEqual((r["outcome"], r["header_columns"], fetched), ("too few columns", 12, []))

    def test_a_header_the_parser_refuses_is_unparseable_without_the_fetch(self):
        """A SILAC proteinGroups.txt of 427 MB came down PRIDE's FTP only to be
        refused for its Ratio columns, which its header already shows."""
        fetched, seen = [], []

        def refuse(cand, header):
            seen.append(len(header))
            raise ValueError("a SILAC search")
        tools = _tools()._replace(fetch=lambda e, f: fetched.append(e) or (f / e.name, {}), refuse=refuse)
        r = self.visit("PXD000013", tools)
        self.assertEqual((r["outcome"], r["detail"], r["refused_on"], fetched, seen),
                         ("unparseable", "ValueError: a SILAC search", "header", [], [402]))

    def test_a_header_with_too_few_columns_stays_too_few_columns(self):
        tools = _tools({3: 12})._replace(refuse=lambda cand, header: 1 / 0)
        self.assertEqual(self.visit("PXD000013", tools)["outcome"], "too few columns")

    def test_without_a_refusal_the_table_is_fetched_as_before(self):
        self.assertEqual(self.visit("PXD000013", _tools()._replace(refuse=lambda cand, header: None))["outcome"], "kept")

    def test_a_kept_deposit_carries_its_record(self):
        r = self.visit("PXD000013")
        self.assertEqual(r["outcome"], "kept")
        self.assertEqual((r["kind"], r["software"], r["label"], r["columns"], r["rows"]),
                         ("maxquant", "MaxQuant", "linear", 400, 300))
        self.assertEqual(r["strata"], ["S1", "S2", "S3"])
        self.assertEqual((r["url"], r["sha256"]), ("https://x/PXD000013/proteinGroups.txt", "ab" * 32))
        self.assertIn("XIC", r["quote"])

    def test_a_sealed_accession_is_refused(self):
        with self.assertRaises(Exception):
            self.visit("PXD042367")


class WalkTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.log = self.dir / "walk.jsonl"

    def order(self, n):
        return [[f"PXD{i:06d}", "PRIDE", "calibration" if i % 2 else "test"] for i in range(100, 100 + n)]

    def test_the_log_follows_the_frames_order_whatever_finishes_first(self):
        records = draw.walk(self.order(30), _tools(), self.log, self.dir, limit=30, quota=10 ** 6, workers=6)
        lines = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["accession"] for r in lines], [r[0] for r in self.order(30)])
        self.assertEqual(len(records), 30)

    def test_the_walk_stops_at_the_limit_and_resumes_where_it_stopped(self):
        draw.walk(self.order(40), _tools(), self.log, self.dir, limit=12, quota=10 ** 6, workers=3)
        self.assertEqual(len(self.log.read_text(encoding="utf-8").splitlines()), 12)
        records = draw.walk(self.order(40), _tools(), self.log, self.dir, limit=20, quota=10 ** 6, workers=3)
        self.assertEqual([r["accession"] for r in records], [r[0] for r in self.order(20)])

    def test_the_walk_stops_when_every_quota_is_met_in_both_splits(self):
        records = draw.walk(self.order(200), _tools(), self.log, self.dir, limit=200, quota=2, workers=4)
        q = draw.quotas(records)
        self.assertTrue(draw.met(q, 2))
        self.assertFalse(draw.met(draw.quotas(records[:-1]), 2))

    def test_one_slow_deposit_does_not_hold_up_the_rest(self):
        """B3 met a 296 MB report that took over 20 minutes over PRIDE's FTP; the
        walk visits about 19 deposits a minute, so 8 workers must keep going
        through at least 500 more while one waits."""
        import threading
        others, release = [], threading.Event()

        def visit_fn(acc, repo, split, tools, root):
            if acc == "PXD000100":
                release.wait(timeout=10)
                return {"accession": acc, "repo": repo, "split": split, "outcome": "no candidate",
                        "released_by": "count" if release.is_set() else "timeout"}
            others.append(acc)
            if len(others) >= 500:
                release.set()
            return {"accession": acc, "repo": repo, "split": split, "outcome": "no candidate"}

        records = draw.walk(self.order(600), _tools(), self.log, self.dir, limit=600, quota=10 ** 6, workers=8,
                            visit_fn=visit_fn)
        self.assertEqual(records[0]["released_by"], "count")
        self.assertEqual([r["accession"] for r in records], [r[0] for r in self.order(600)])

    def test_a_log_that_does_not_match_the_order_stops_the_walk(self):
        self.log.write_text(json.dumps({"accession": "PXD999999"}) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            draw.walk(self.order(5), _tools(), self.log, self.dir, limit=5)


class RunnerFetchTests(unittest.TestCase):
    def test_a_whole_file_download_leaves_connections_for_the_rest_of_the_walk(self):
        """A 296 MB report took all 8 of PRIDE's connections, and the walk's
        header reads for other deposits waited on it."""
        import importlib.util
        import threading
        import time
        from unittest import mock
        from valuescale.corpus import remote
        spec = importlib.util.spec_from_file_location("value_scale_corpus",
                                                      REPO / "research/notebooks/value_scale_corpus.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        size = remote.CHUNK * 12
        now, peak, lock = [0], [0], threading.Lock()

        def ftp_read(url, start, length):
            with lock:
                now[0] += 1
                peak[0] = max(peak[0], now[0])
            time.sleep(0.05)
            with lock:
                now[0] -= 1
            return b"\0" * length

        f = File("report.tsv", size, "ftp://ftp.pride.ebi.ac.uk/pride/x/report.tsv")
        folder = Path(tempfile.mkdtemp())
        with mock.patch.object(remote, "ftp_read", ftp_read):
            path, rec = runner.make_tools({"massive": {}}).fetch(tables.Entry(f, None, size), folder)
        self.assertEqual(rec["bytes"], size)
        self.assertLessEqual(peak[0], remote.FTP_SITES["ftp.pride.ebi.ac.uk"][1] // 2)
        self.assertGreater(peak[0], 1)

    def test_the_header_refusal_is_the_parsers_own_word_for_word(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("value_scale_corpus",
                                                      REPO / "research/notebooks/value_scale_corpus.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        alignment = runner.alignment  # the runner's parser: the package itself never imports the service
        refuse = runner.make_tools({"massive": {}}).refuse
        f = File("proteinGroups.txt", 10, "ftp://x/proteinGroups.txt")
        wide = tables.Candidate("maxquant", "wide", tables.Entry(f, None, 10), ())
        base = ["Protein IDs", "Majority protein IDs", "Gene names"] + [f"Intensity s{i}" for i in range(25)]
        for extra in (["Ratio H/L s1", "Ratio H/L normalized s1"], ["Reporter intensity 1 s1"]):
            header = base + extra
            with self.assertRaises(alignment.UnreadableMatrix) as mine:
                refuse(wide, header)
            body = "\t".join(header) + "\n" + "\t".join(["P1", "P1", "G1"] + ["1"] * (len(header) - 3)) + "\n"
            with self.assertRaises(alignment.UnreadableMatrix) as theirs:
                alignment.parse_matrix_csv(body)
            self.assertEqual(str(mine.exception), str(theirs.exception))
        self.assertIsNone(refuse(wide, base))
        self.assertIsNone(refuse(wide, ["Protein.Group", "Genes"] + [f"Ratio H/L s{i}" for i in range(25)]))
        long = tables.Candidate("diann_report", "long", tables.Entry(f, None, 10), ())
        self.assertIsNone(refuse(long, base + ["Ratio H/L s1"]))


class NoStatisticTests(unittest.TestCase):
    def test_the_draw_imports_no_detector_module(self):
        banned = {"valuescale.gates", "valuescale.statistics", "valuescale.score", "valuescale.method"}
        paths = [REPO / "valuescale/corpus" / f for f in ("frame.py", "remote.py", "tables.py", "draw.py")]
        paths.append(REPO / "research/notebooks/value_scale_corpus.py")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    names |= {node.module} | {f"{node.module}.{a.name}" for a in node.names}
                elif isinstance(node, ast.Import):
                    names |= {a.name for a in node.names}
            self.assertFalse(names & banned, path.name)


if __name__ == "__main__":
    unittest.main()
