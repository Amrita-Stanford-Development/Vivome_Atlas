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

    def _with_values(self, values, names=None):
        names = names or [f"s{i}" for i in range(values.shape[1])]
        return _tools()._replace(parse=lambda cand, path: draw.Parsed(names, values))

    def test_a_table_with_no_value_but_0_or_missing_is_empty(self):
        """R1 (research/value-scale-v2-plan.md): B7's test held two such tables,
        PXD022054 and PXD047898, kept and labelled linear."""
        for fill in (np.nan, 0.0, np.inf):
            values = np.full((300, 40), fill)
            values[::3] = np.nan
            r = self.visit("PXD000013", self._with_values(values))
            self.assertEqual((r["outcome"], r["columns"], r["rows"]), ("empty", 40, 300), fill)
            self.assertNotIn("label", r)

    def test_an_empty_table_too_small_for_the_walk_keeps_its_size_outcome(self):
        self.assertEqual(self.visit("PXD000013", self._with_values(np.full((150, 40), np.nan)))["outcome"],
                         "too few rows")
        self.assertEqual(self.visit("PXD000013", self._with_values(np.full((300, 12), np.nan)))["outcome"],
                         "too few columns")

    def test_one_observed_value_is_enough_and_a_negative_one_counts(self):
        values = np.full((300, 40), np.nan)
        values[5, 7] = 1000.0
        self.assertEqual(self.visit("PXD000013", self._with_values(values))["outcome"], "kept")
        values[5, 7] = -1.0
        self.assertEqual(self.visit("PXD000013", self._with_values(values))["outcome"], "unclear label")

    def test_a_kept_linear_table_whose_values_look_log_carries_its_range(self):
        """PXD066316, a Spectronaut table labelled linear, held log2 values
        (7.96 to 26.76): it goes to the hand audit with its range."""
        values = np.tile(np.linspace(8.0, 27.0, 300)[:, None], (1, 40))
        values[0, 0] = np.nan
        values[1, 1] = 0.0
        r = self.visit("PXD000013", self._with_values(values))
        self.assertEqual((r["outcome"], r["label"]), ("kept", "linear"))
        observed = values[np.isfinite(values) & (values != 0)]
        self.assertEqual(r["looks_log"], {"min": 8.0, "median": float(f"{np.median(observed):.6g}"),
                                          "p99": float(f"{np.quantile(observed, 0.99):.6g}"), "max": 27.0})
        json.dumps(r, allow_nan=False)

    def test_a_linear_table_with_99_percent_under_64_is_flagged_and_at_64_is_not(self):
        under = np.full((300, 40), 10.0)
        under[:2] = 1e6  # 80 of 12,000 values: under 1%
        self.assertIn("looks_log", self.visit("PXD000013", self._with_values(under)))
        at = np.full((300, 40), 64.0)
        self.assertNotIn("looks_log", self.visit("PXD000013", self._with_values(at)))
        raw = np.full((300, 40), 10.0)
        raw[:4] = 1e6  # 160 of 12,000: over 1%
        self.assertNotIn("looks_log", self.visit("PXD000013", self._with_values(raw)))

    def test_a_table_labelled_log_is_not_flagged(self):
        values = np.full((300, 40), 20.0)
        r = self.visit("PXD000013", self._with_values(values, [f"log2 LFQ intensity s{i}" for i in range(40)]))
        self.assertEqual((r["outcome"], r["label"]), ("kept", "log"))
        self.assertNotIn("looks_log", r)

    def test_the_checks_read_observed_values_only(self):
        values = np.full((300, 40), 5.0)
        self.assertTrue(draw.empty(np.array([[np.nan, 0.0], [np.inf, -np.inf]])))
        self.assertFalse(draw.empty(np.array([[np.nan, -2.0]])))
        self.assertIsNone(draw.looks_log(np.full((3, 3), np.nan)))
        self.assertEqual(draw.looks_log(values)["p99"], 5.0)
        self.assertEqual(draw.LOG_CEILING, 64.0)


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


class RevisitTests(unittest.TestCase):
    """Reads that failed on a transport fault the walk then fixed (a short FTP
    read returned as whole) are visited again, in place."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.log = self.dir / "walk.jsonl"
        rows = [("PXD000101", "kept"), ("PXD000102", "fetch failed"), ("PXD000103", "no candidate"),
                ("PXD000104", "no file list"), ("PXD000105", "unparseable")]
        self.before = [{"accession": a, "repo": "PRIDE", "split": "test", "outcome": o, "detail": f"was {o}"}
                       for a, o in rows]
        self.log.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in self.before), encoding="utf-8")

    def test_only_failed_reads_are_visited_again_and_keep_their_place(self):
        seen = []

        def visit_fn(acc, repo, split, tools, root):
            seen.append(acc)
            return {"accession": acc, "repo": repo, "split": split, "outcome": "kept", "label": "linear"}
        records = draw.revisit(self.log, _tools(), self.dir, workers=2, visit_fn=visit_fn)
        self.assertEqual(sorted(seen), ["PXD000102", "PXD000104"])
        lines = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(lines, records)
        self.assertEqual([r["accession"] for r in lines], [r["accession"] for r in self.before])
        self.assertEqual([r["outcome"] for r in lines], ["kept", "kept", "no candidate", "kept", "unparseable"])
        self.assertEqual(lines[1]["revisited_from"], {"outcome": "fetch failed", "detail": "was fetch failed"})
        self.assertNotIn("revisited_from", lines[0])
        self.assertEqual(lines[2], self.before[2])

    def test_a_chosen_set_is_visited_again_and_earlier_visits_are_kept_inside(self):
        # B3's third visit: the records the clean-up of 2026-11-06 touches, chosen by a rule
        def second(acc, repo, split, tools, root):
            return {"accession": acc, "repo": repo, "split": split, "outcome": "unparseable", "detail": "second"}

        def third(acc, repo, split, tools, root):
            return {"accession": acc, "repo": repo, "split": split, "outcome": "kept", "label": "linear"}
        draw.revisit(self.log, _tools(), self.dir, visit_fn=second)
        records = draw.revisit(self.log, _tools(), self.dir, visit_fn=third,
                               select=lambda r: r["accession"] in ("PXD000102", "PXD000105"))
        self.assertEqual([r["outcome"] for r in records], ["kept", "kept", "no candidate", "unparseable", "kept"])
        self.assertEqual(records[1]["revisited_from"], {"outcome": "unparseable", "detail": "second", "revisited_from": {
            "outcome": "fetch failed", "detail": "was fetch failed"}})
        self.assertEqual(records[4]["revisited_from"], {"outcome": "unparseable", "detail": "was unparseable"})
        self.assertEqual([json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()], records)

    def test_a_visits_reasons_are_kept_inside_when_a_later_visit_replaces_it(self):
        # B3's fourth visit takes PXD054457 again, which the third visit took for its reader
        def third(acc, repo, split, tools, root):
            return {"accession": acc, "repo": repo, "split": split, "outcome": "kept", "revisited_for": ["reader"]}

        def fourth(acc, repo, split, tools, root):
            return {"accession": acc, "repo": repo, "split": split, "outcome": "kept",
                    "revisited_for": ["quantity case"]}
        chosen = lambda r: r["accession"] == "PXD000105"  # noqa: E731
        draw.revisit(self.log, _tools(), self.dir, visit_fn=third, select=chosen)
        records = draw.revisit(self.log, _tools(), self.dir, visit_fn=fourth, select=chosen)
        self.assertEqual(records[4]["revisited_for"], ["quantity case"])
        self.assertEqual(records[4]["revisited_from"], {"outcome": "kept", "detail": None, "revisited_for": ["reader"],
                                                        "revisited_from": {"outcome": "unparseable",
                                                                           "detail": "was unparseable"}})

    def test_a_revisit_that_stops_part_way_leaves_the_log_as_it_was(self):
        def visit_fn(acc, repo, split, tools, root):
            raise RuntimeError("stopped")
        with self.assertRaises(RuntimeError):
            draw.revisit(self.log, _tools(), self.dir, visit_fn=visit_fn)
        self.assertEqual([json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()], self.before)


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


class CleanupRunnerTests(unittest.TestCase):
    """B3's third visit (research/notebooks/value_scale_corpus.py): the
    selection and the visit."""

    def runner(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("value_scale_corpus",
                                                      REPO / "research/notebooks/value_scale_corpus.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        return runner

    def test_a_header_that_cannot_be_read_now_is_not_chosen_by_the_probe(self):
        from types import SimpleNamespace
        from unittest import mock
        runner = self.runner()
        out = Path(tempfile.mkdtemp()) / "cleanup.json"
        records = [{"accession": f"PXD00000{i}", "outcome": "too few columns", "header_columns": 0} for i in range(3)]
        now = {"PXD000000": 0, "PXD000001": None, "PXD000002": 25}
        with mock.patch.object(runner, "_records", return_value=records), \
                mock.patch.object(runner, "cleanup_reasons", return_value=[]), \
                mock.patch.object(runner, "make_tools"), mock.patch.object(runner.frame, "load"), \
                mock.patch.object(runner, "_zero_columns_header_now", side_effect=lambda r, tools: now[r["accession"]]), \
                mock.patch.object(runner, "CLEANUP", out):
            runner.cmd_cleanup_selection(SimpleNamespace(workers=1))
        written = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(written["records"], {"PXD000002": ["header"]})
        self.assertEqual(written["probe"], {"read": 3, "now_nonzero": 1, "now_unreadable": 1})

    def test_the_third_visit_is_made_once(self):
        """A second run would nest the third visit inside a fourth."""
        from types import SimpleNamespace
        from unittest import mock
        runner = self.runner()
        folder = Path(tempfile.mkdtemp())
        log, chosen = folder / "walk.jsonl", folder / "cleanup.json"
        line = (json.dumps({"accession": "PXD000001", "outcome": "kept", "revisited_for": ["reader"],
                            "revisited_from": {"outcome": "unparseable"}}) + "\n").encode("utf-8")
        log.write_bytes(line)
        chosen.write_bytes(json.dumps({"records": {"PXD000001": ["reader"]}}).encode("utf-8"))
        with mock.patch.object(runner, "LOG", log), mock.patch.object(runner, "CLEANUP", chosen), \
                mock.patch.object(runner, "make_tools", side_effect=AssertionError("visited")):
            with self.assertRaises(SystemExit) as caught:
                runner.cmd_revisit(SimpleNamespace(cleanup=True, workers=1))
        self.assertIn("PXD000001", str(caught.exception))
        self.assertEqual(log.read_bytes(), line)

    def test_the_fourth_visit_is_made_once(self):
        """A record the third visit took may be taken again; a second fourth visit may not."""
        from types import SimpleNamespace
        from unittest import mock
        runner = self.runner()
        folder = Path(tempfile.mkdtemp())
        log, chosen = folder / "walk.jsonl", folder / "cleanup.json"
        line = (json.dumps({"accession": "PXD000001", "outcome": "kept", "revisited_for": ["quantity case"],
                            "revisited_from": {"outcome": "kept", "revisited_for": ["reader"]}}) + "\n").encode("utf-8")
        log.write_bytes(line)
        chosen.write_bytes(json.dumps({"records": {"PXD000001": ["quantity case"]}}).encode("utf-8"))
        with mock.patch.object(runner, "LOG", log), mock.patch.object(runner, "FOURTH", chosen), \
                mock.patch.object(runner, "make_tools", side_effect=AssertionError("visited")):
            with self.assertRaises(SystemExit) as caught:
                runner.cmd_revisit(SimpleNamespace(cleanup=False, fourth=True, workers=1))
        self.assertIn("PXD000001", str(caught.exception))
        self.assertEqual(log.read_bytes(), line)
        third = (json.dumps({"accession": "PXD000001", "outcome": "kept", "revisited_for": ["reader"]}) + "\n")
        log.write_bytes(third.encode("utf-8"))
        with mock.patch.object(runner, "LOG", log), mock.patch.object(runner, "FOURTH", chosen), \
                mock.patch.object(runner, "make_tools", side_effect=AssertionError("visited")):
            with self.assertRaisesRegex(AssertionError, "visited"):  # the guard lets it through
                runner.cmd_revisit(SimpleNamespace(cleanup=False, fourth=True, workers=1))

    def test_the_fourth_visit_chooses_what_the_fixes_of_2026_11_07_touch(self):
        from unittest import mock
        runner = self.runner()
        folder = Path(tempfile.mkdtemp())
        files = {
            "commas": b"Protein.Group\tGenes\tD:\\r\\a,b,c,d.raw\tD:\\r\\e,f,g,h.raw\nP1\tTP53\t1\t2\n",
            "plain": b"Protein.Group\tGenes\ta.raw\tb.raw\nP1\tTP53\t1\t2\n",
            "case": b"Majority Protein IDs\tGene Names\tIntensity a\tLFQ Intensity a\nP1\tG1\t1\t2\n",
            "tie": b"R.FileName\tPG.ProteinGroups,PG.Quantity\nA\n",  # one tab, one comma; the next line keeps neither
        }
        for name, data in files.items():
            (folder / name).write_bytes(data)
        records = [
            {"accession": "PXD1", "outcome": "unparseable", "file": "commas", "kind": "diann_matrix", "layout": "wide",
             "detail": "UnreadableMatrix: line 2 has 1 fields, fewer than the header's 7"},
            {"accession": "PXD2", "outcome": "kept", "file": "plain", "kind": "diann_matrix", "layout": "wide"},
            {"accession": "PXD3", "outcome": "unparseable", "file": "plain", "kind": "diann_matrix", "layout": "wide",
             "detail": "UnreadableMatrix: no row has an identifier in 'Genes', so no protein or gene can be named."},
            {"accession": "PXD4", "outcome": "unparseable", "file": "x.zip", "member": "a.pg_matrix.tsv", "member_bytes": 0,
             "kind": "diann_matrix", "layout": "wide", "detail": "StopIteration: "},
            {"accession": "PXD5", "outcome": "unparseable", "file": "plain", "kind": "spectronaut", "layout": "spectronaut_long",
             "detail": "ValueError: text where a number belongs: could not convert string to float: '8329,325'"},
            {"accession": "PXD6", "outcome": "kept", "file": "case", "kind": "maxquant", "layout": "wide"},
            # the long readers broke a tie for tabs, the parser for commas, as the separator rule does now
            {"accession": "PXD7", "outcome": "kept", "file": "tie", "kind": "spectronaut", "layout": "spectronaut_long"},
            {"accession": "PXD9", "outcome": "unparseable", "file": "tie", "kind": "diann_matrix", "layout": "wide"},
            {"accession": "PXD8", "outcome": "no candidate"},
        ]
        with mock.patch.object(runner, "_local_table", side_effect=lambda r: folder / (r.get("member") or r["file"])):
            got = {r["accession"]: runner.fourth_visit_reasons(r) for r in records}
        self.assertEqual(got, {"PXD1": ["separator"], "PXD2": [], "PXD3": ["protein groups"], "PXD4": ["empty member"],
                               "PXD5": ["decimal comma"], "PXD6": ["quantity case"], "PXD7": ["separator"], "PXD9": [],
                               "PXD8": []})

    def test_the_runner_refuses_to_run_when_a_copied_pattern_drifts(self):
        from unittest import mock
        runner = self.runner()
        runner.check_patterns()  # in step today
        with mock.patch.object(runner.tables, "COMMA_NUMBER", r"\d+,\d+"):
            with self.assertRaisesRegex(SystemExit, "comma-number"):
                runner.check_patterns()

    def test_the_corpus_separator_rule_is_the_service_parsers(self):
        # valuescale/corpus/remote.py delimiter copies service/pipeline/alignment.py _delimiter (the
        # package imports no service code; the runner holds both)
        runner = self.runner()
        cases = [("A\tB\tC", "1\t2\t3"), ("A,B,C", "1,2,3"), ("A\tB,b\tC,c", "1\t2\t3"), ("A,B\tb,C", "1,2,3"),
                 ("A\tB,C", "1"), ("A\tB,C", None), ("A,B", "1\t2"), ("A", "1"), ("A\tB", "1,2\t3"),
                 ('A,"B\tb",C', '1,"x\ty",3'), ("A\tB,C,D", "1\t2,3"), ("", None)]
        for first, following in cases:
            self.assertEqual(runner.remote.delimiter(first, following), runner.alignment._delimiter(first, following),
                             (first, following))

    def test_the_tables_the_clean_up_added_are_those_no_visit_before_it_kept(self):
        """A table the third visit added stays added when the fourth visit
        reads it again; a table kept before the clean-up is never added."""
        runner = self.runner()
        records = [
            # walked unparseable, kept by the third visit, kept again by the fourth
            {"accession": "PXD1", "split": "calibration", "outcome": "kept", "revisited_for": ["quantity case"],
             "revisited_from": {"outcome": "kept", "revisited_for": ["reader"],
                                "revisited_from": {"outcome": "unparseable"}}},
            # kept by the walk, read again by the third visit
            {"accession": "PXD2", "split": "test", "outcome": "kept", "revisited_for": ["reader"],
             "revisited_from": {"outcome": "kept"}},
            # a failed read kept by the second visit (no reasons), read again by the fourth
            {"accession": "PXD3", "split": "test", "outcome": "kept", "revisited_for": ["separator"],
             "revisited_from": {"outcome": "kept", "revisited_from": {"outcome": "fetch failed"}}},
            # added by the fourth visit
            {"accession": "PXD4", "split": "test", "outcome": "kept", "revisited_for": ["protein groups"],
             "revisited_from": {"outcome": "unparseable"}},
            # the second visit alone: not the clean-up's
            {"accession": "PXD5", "split": "test", "outcome": "kept", "revisited_from": {"outcome": "fetch failed"}},
            # added by the third visit, refused by the fourth
            {"accession": "PXD6", "split": "test", "outcome": "unparseable", "revisited_for": ["decimal comma"],
             "revisited_from": {"outcome": "kept", "revisited_for": ["decoding"],
                                "revisited_from": {"outcome": "unparseable"}}},
        ]
        self.assertEqual(runner.newly_kept(records), {"calibration": ["PXD1"], "test": ["PXD4"]})

    def test_a_header_is_judged_now_as_the_walk_judges_it(self):
        """What the walk decides from a wide table's header alone, read again
        with the reader as it now is."""
        runner = self.runner()
        lfq = ["Majority protein IDs", "Gene names"] + [f"LFQ intensity s{i}" for i in range(25)]
        headers = {"few": lfq[:10], "many": lfq, "silac": lfq + [f"Ratio H/L s{i}" for i in range(25)], "none": None}

        def header(entry):
            if entry.file.path == "broken":
                raise OSError("550 Failed to open file")
            return headers[entry.file.path]
        tools = runner.draw.Tools(None, header, None, None, None, header,
                                  runner.make_tools({"massive": {}}).refuse)
        rec = {"accession": "PXD000001", "kind": "maxquant", "layout": "wide", "listed_bytes": 10, "url": "ftp://x/f"}
        got = {name: runner._header_decision_now({**rec, "file": name}, tools)
               for name in ("few", "many", "silac", "none", "broken")}
        self.assertEqual(got, {"few": "too few columns", "many": "fetch", "silac": "unparseable",
                               "none": None, "broken": None})

    def test_the_fourth_selection_reads_again_each_header_the_walk_judged_alone(self):
        """A record decided on its header alone is chosen when its header now
        decides otherwise; one that cannot be read now is the server's."""
        from types import SimpleNamespace
        from unittest import mock
        runner = self.runner()
        out = Path(tempfile.mkdtemp()) / "fourth.json"
        records = [{"accession": "PXD000001", "outcome": "too few columns", "header_columns": 4},
                   {"accession": "PXD000002", "outcome": "too few columns", "header_columns": 12},
                   {"accession": "PXD000003", "outcome": "unparseable", "refused_on": "header"},
                   {"accession": "PXD000004", "outcome": "too few columns", "header_columns": 0},
                   {"accession": "PXD000005", "outcome": "too few columns", "columns": 3},  # parsed: read locally
                   {"accession": "PXD000006", "outcome": "kept"}]
        now = {"PXD000001": "too few columns", "PXD000002": "fetch", "PXD000003": "unparseable", "PXD000004": None}
        asked = []

        def decision(r, tools):
            asked.append(r["accession"])
            return now[r["accession"]]
        with mock.patch.object(runner, "_records", return_value=records), \
                mock.patch.object(runner, "fourth_visit_reasons", return_value=[]), \
                mock.patch.object(runner, "make_tools"), mock.patch.object(runner.frame, "load"), \
                mock.patch.object(runner, "_header_decision_now", side_effect=decision), \
                mock.patch.object(runner, "FOURTH", out):
            runner.cmd_fourth_visit_selection(SimpleNamespace(workers=1))
        written = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(sorted(asked), ["PXD000001", "PXD000002", "PXD000003", "PXD000004"])
        self.assertEqual(written["records"], {"PXD000002": ["header"]})
        self.assertEqual(written["probe"], {"read": 4, "now_differs": 1, "now_unreadable": 1})


class ParsedTablePlaceTests(unittest.TestCase):
    def test_the_parsed_table_lands_in_the_deposits_own_folder_however_deep_its_file(self):
        """95 of the walk's 366 kept tables were saved beside a file in a
        subfolder (MassIVE's search/, an archive's txt/): one place per deposit."""
        import importlib.util
        from unittest import mock
        spec = importlib.util.spec_from_file_location("value_scale_corpus",
                                                      REPO / "research/notebooks/value_scale_corpus.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        data = Path(tempfile.mkdtemp())
        header = ["Protein IDs", "Majority protein IDs", "Gene names"] + [f"LFQ intensity s{i}" for i in range(3)]
        body = "\t".join(header) + "\n" + "P1\tP1\tG1\t1\t2\t3\nP2\tP2\tG2\t4\t5\t6\n"
        f = File("proteinGroups.txt", 10, "ftp://x/proteinGroups.txt")
        cand = tables.Candidate("maxquant", "wide", tables.Entry(f, "txt/proteinGroups.txt", 10), ())
        for rel in ("PXD000001/members/txt/proteinGroups.txt", "PXD000002/search/proteinGroups.txt",
                    "PXD000003/proteinGroups.txt"):
            path = data / rel
            path.parent.mkdir(parents=True)
            path.write_text(body, encoding="utf-8")
            with mock.patch.object(runner, "DATA", data):
                runner.make_tools({"massive": {}}).parse(cand, path)
            acc = rel.split("/")[0]
            self.assertEqual([p.relative_to(data / acc).as_posix() for p in (data / acc).rglob("table.npz")],
                             ["table.npz"])


class AuditPacketTests(unittest.TestCase):
    def test_a_packet_shows_the_header_and_perseus_annotation_rows_never_values(self):
        """A table saved from Perseus keeps MaxQuant's column names whatever it
        did to the values; its "#!{" rows under the header say so."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("value_scale_corpus",
                                                      REPO / "research/notebooks/value_scale_corpus.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        path = Path(tempfile.mkdtemp()) / "proteinGroups.txt"
        path.write_bytes(b"\xef\xbb\xbfProtein IDs\tLFQ intensity a\tLFQ intensity b\n"
                         b"#!{Type}T\tE\tE\n#!{C:Group}\tx\ty\nP1\t23.5\t24.1\nP2\t21.0\t22.2\n")
        header, notes = runner._header_lines(path)
        self.assertEqual(header, ["Protein IDs", "LFQ intensity a", "LFQ intensity b"])
        self.assertEqual(notes, ["#!{Type}T\tE\tE", "#!{C:Group}\tx\ty"])
        plain = path.with_name("plain.txt")
        plain.write_bytes(b"Protein IDs\tIntensity a\nP1\t100\n")
        self.assertEqual(runner._header_lines(plain), (["Protein IDs", "Intensity a"], []))
        # PXD053397: a tab-separated header whose names hold commas is split on its tabs, as the parser splits it
        commas = path.with_name("report.pg_matrix.tsv")
        commas.write_bytes(b"Protein.Group\tGenes\tD:\\r\\a,b,c,d.raw\tD:\\r\\e,f,g,h.raw\nP1\tTP53\t1\t2\n")
        self.assertEqual(runner._header_lines(commas)[0], ["Protein.Group", "Genes", "D:\\r\\a,b,c,d.raw",
                                                           "D:\\r\\e,f,g,h.raw"])

    def test_a_parquet_tables_header_is_its_schemas_column_names(self):
        """The audit's packets for DIA-NN report.parquet tables showed binary or
        no column names: the file was read as text."""
        import importlib.util
        import pyarrow as pa
        import pyarrow.parquet as pq
        spec = importlib.util.spec_from_file_location("value_scale_corpus",
                                                      REPO / "research/notebooks/value_scale_corpus.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        path = Path(tempfile.mkdtemp()) / "report.parquet"
        pq.write_table(pa.table({"Run": ["a"], "Protein.Group": ["P1"], "PG.MaxLFQ": [1.0]}), path)
        self.assertEqual(runner._header_lines(path), (["Run", "Protein.Group", "PG.MaxLFQ"], []))

    def test_a_packet_names_every_value_column_however_long_the_header(self):
        """MaxQuant's Intensity and LFQ columns came after the packets' first
        120 names, so the audit never saw them."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("value_scale_corpus",
                                                      REPO / "research/notebooks/value_scale_corpus.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        other = ["Protein IDs", "Majority protein IDs", "Gene names"] + [f"Peptides s{i}" for i in range(130)]
        lfq = [f"LFQ intensity s{i}" for i in range(24)]
        raw = [f"Intensity s{i}" for i in range(24)]
        text = runner._columns_section("maxquant", "wide", other + raw + lfq)
        for name in other + raw + lfq:
            self.assertIn(name, text)
        self.assertNotIn("...", text)
        self.assertIn("LFQ intensity (24)", text)
        self.assertIn("Intensity (24)", text)
        self.assertIn("LFQ intensity when any value is above 0, else Intensity", text)
        long = runner._columns_section("diann_report", "long", ["Run", "Protein.Group", "PG.MaxLFQ", "PG.Quantity"])
        self.assertIn("PG.MaxLFQ", long)
        self.assertIn("runs are rows", long)


def _runner():
    import importlib.util
    spec = importlib.util.spec_from_file_location("value_scale_corpus", REPO / "research/notebooks/value_scale_corpus.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


class LooksLogAuditTests(unittest.TestCase):
    """R1: a table labelled linear whose values look log goes to the hand
    audit, and its packet shows its value range beside its headers."""

    def test_the_audit_sample_takes_every_flagged_table_besides_its_seeded_share(self):
        runner = _runner()
        records = [{"accession": f"PXD{i:06d}", "split": "calibration" if i % 2 else "test", "outcome": "kept",
                    "label": "linear"} for i in range(40)]
        records.append({"accession": "PXD999999", "split": "test", "outcome": "unclear label"})
        plain = runner.audit_sample(records)
        outside = [r for r in records if r["outcome"] == "kept" and r["accession"] not in plain[r["split"]]]
        for r in outside[:3]:
            r["looks_log"] = {"min": 8.0, "median": 15.0, "p99": 21.8, "max": 26.8}
        flagged = runner.audit_sample(records)
        for split in draw.SPLITS:
            want = sorted(set(plain[split]) | {r["accession"] for r in outside[:3] if r["split"] == split})
            self.assertEqual(flagged[split], want)

    def test_a_flagged_tables_packet_shows_its_range_and_an_unflagged_ones_no_value(self):
        runner = _runner()
        r = {"accession": "PXD066316", "repo": "PRIDE", "label": "linear", "software": "Spectronaut",
             "kind": "spectronaut", "layout": "spectronaut_pivot", "file": "Report_proteingroups.txt", "member": None,
             "columns": 27, "rows": 5842, "quantity": None}
        header = ["PG.ProteinGroups"] + [f"[{i}] run{i}.raw.PG.Quantity" for i in range(27)]
        plain = runner._packet(r, "test", header, [], ["Report_proteingroups.txt"], "Methods text.")
        flagged = runner._packet({**r, "looks_log": {"min": 7.96281, "median": 15.0249, "p99": 21.7527,
                                                     "max": 26.7629}}, "test", header, [], ["Report_proteingroups.txt"],
                                 "Methods text.")
        self.assertNotIn("## The values", plain)
        self.assertNotIn("21.7527", plain)
        self.assertIn("## The values", flagged)
        for number in ("7.96281", "15.0249", "21.7527", "26.7629"):
            self.assertIn(number, flagged)
        self.assertIn("under 64", flagged)
        self.assertLess(flagged.index("## Value columns"), flagged.index("## The values"))
        self.assertLess(flagged.index("## The values"), flagged.index("## Methods"))
        self.assertTrue(plain.startswith("# PXD066316 (test, PRIDE)"))
        self.assertIn("Methods text.", plain)


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
