"""Listing and reading a deposit's files remotely, without the network: the
PRIDE API's pages, a MassIVE FTP folder, and zip archives read through
range requests."""
from __future__ import annotations

import ftplib
import io
import unittest
import zipfile

from valuescale.corpus import remote


def _pride_item(name, size, folder="2024/05/PXD000001"):
    return {"fileName": name, "fileSizeBytes": size, "publicFileLocations": [
        {"name": "Aspera Protocol", "value": f"prd_ascp@fasp.ebi.ac.uk:pride/data/archive/{folder}/{name}"},
        {"name": "FTP Protocol", "value": f"ftp://ftp.pride.ebi.ac.uk/pride/data/archive/{folder}/{name}"}]}


class PrideTests(unittest.TestCase):
    def test_pages_are_read_until_a_short_one(self):
        pages = {0: [_pride_item(f"f{i}.raw", i) for i in range(3)], 1: [_pride_item("report.pg_matrix.tsv", 99)]}
        calls = []

        def get_json(url):
            calls.append(url)
            page = int(url.rsplit("page=", 1)[1])
            return pages.get(page, [])

        files = remote.pride_files("PXD000001", get_json=get_json, page_size=3)
        self.assertEqual([f.path for f in files], ["f0.raw", "f1.raw", "f2.raw", "report.pg_matrix.tsv"])
        self.assertEqual(files[-1].url,  # PRIDE's FTP answers in seconds where its HTTPS took 15 to 30 (B3 smoke test)
                         "ftp://ftp.pride.ebi.ac.uk/pride/data/archive/2024/05/PXD000001/report.pg_matrix.tsv")
        self.assertEqual(files[-1].size, 99)
        self.assertEqual(len(calls), 2)

    def test_a_file_in_a_subfolder_keeps_its_path(self):
        item = _pride_item("x.tsv", 5)
        item["publicFileLocations"][1]["value"] = "ftp://ftp.pride.ebi.ac.uk/pride/data/archive/2024/05/PXD000001/sub/x.tsv"
        files = remote.pride_files("PXD000001", get_json=lambda url: [item] if url.endswith("page=0") else [])
        self.assertEqual(files[0].path, "sub/x.tsv")


class FakeFtp:
    def __init__(self, tree):
        self.tree = tree

    def mlsd(self, path):
        node = self.tree
        for part in [p for p in path.split("/") if p][2:]:  # past /v15/MSV...
            node = node[part]
        for name, value in node.items():
            yield (name, {"type": "dir"} if isinstance(value, dict) else {"type": "file", "size": str(value)})


class MassiveTests(unittest.TestCase):
    def test_folders_are_walked_three_levels_deep(self):
        tree = {"other": {"proteinGroups.txt": 10, "deep": {"a.tsv": 1, "deeper": {"b.tsv": 2, "deepest": {"c.tsv": 3}}}},
                "raw": {"x.raw": 7}, "readme.txt": 4}
        files = remote.massive_files("ftp://massive-ftp.ucsd.edu/v15/MSV000000001/", ftp=FakeFtp(tree))
        self.assertEqual(sorted(f.path for f in files),
                         ["other/deep/a.tsv", "other/deep/deeper/b.tsv", "other/proteinGroups.txt", "raw/x.raw", "readme.txt"])
        hit = next(f for f in files if f.path == "other/proteinGroups.txt")
        self.assertEqual((hit.size, hit.url),
                         (10, "ftp://massive-ftp.ucsd.edu/v15/MSV000000001/other/proteinGroups.txt"))


class OldHostTests(unittest.TestCase):
    """899 of the frame's 1,507 MassIVE announcements name ftp://massive.ucsd.edu/MSV.../,
    which no longer answers; the dataset sits in a /vNN/ folder of massive-ftp.ucsd.edu."""

    def test_folders_map_each_dataset_to_its_place(self):
        tree = {"v04": {"MSV000089258": {}, "MSV000000002": {}}, "x01": {"MSV000089258": {}, "readme": 1},
                "v15": {"MSV000103821": {}}}

        class Root(FakeFtp):
            def mlsd(self, path):
                node = self.tree
                for part in [p for p in path.split("/") if p]:
                    node = node[part]
                for name, value in node.items():
                    yield (name, {"type": "dir"} if isinstance(value, dict) else {"type": "file", "size": "1"})

        folders = remote.massive_folders(ftp=Root(tree))
        self.assertEqual(folders, {"MSV000089258": "/v04/MSV000089258", "MSV000000002": "/v04/MSV000000002",
                                   "MSV000103821": "/v15/MSV000103821"})

    def test_an_old_host_url_is_moved_to_the_current_host(self):
        folders = {"MSV000089258": "/v04/MSV000089258"}
        self.assertEqual(remote.massive_root("ftp://massive.ucsd.edu/MSV000089258/", "MSV000089258", folders),
                         "ftp://massive-ftp.ucsd.edu/v04/MSV000089258/")
        current = "ftp://massive-ftp.ucsd.edu/v15/MSV000103821/"
        self.assertEqual(remote.massive_root(current, "MSV000103821", folders), current)
        with self.assertRaises(OSError):
            remote.massive_root("ftp://massive.ucsd.edu/MSV000000009/", "MSV000000009", folders)


def _zip_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("results/report.pg_matrix.tsv", "Protein.Group\tGenes\tA\tB\n" + "P1\tG1\t1\t2\n" * 5000)
        zf.writestr("notes.txt", "hello")
    return buf.getvalue()


class RangeTests(unittest.TestCase):
    def setUp(self):
        self.data = _zip_bytes()
        self.calls = []

        def fetch(url, start, end):
            self.calls.append((start, end))
            return self.data[start:end + 1]

        self.fetch = fetch

    def test_a_zip_is_listed_without_reading_it_whole(self):
        members = remote.zip_members("https://x/a.zip", len(self.data), fetch=self.fetch, block=64)  # the zip is 403 bytes
        self.assertEqual({m.name: m.size for m in members},
                         {"results/report.pg_matrix.tsv": len("Protein.Group\tGenes\tA\tB\n" + "P1\tG1\t1\t2\n" * 5000),
                          "notes.txt": 5})
        self.assertLess(sum(e - s + 1 for s, e in self.calls), len(self.data))

    def test_a_long_read_is_one_fetch_however_many_blocks_it_spans(self):
        f = remote.RangeFile("https://x/a.zip", len(self.data), self.fetch, block=16)
        f.seek(5)
        self.assertEqual(f.read(300), self.data[5:305])
        self.assertEqual(len(self.calls), 1)
        f.seek(0)
        self.assertEqual(f.read(400), self.data[:400])  # blocks 0 to 19 are cached: 20 to 24 in one fetch
        self.assertEqual(len(self.calls), 2)

    def test_a_members_first_bytes_are_inflated(self):
        head = remote.member_head("https://x/a.zip", len(self.data), "results/report.pg_matrix.tsv", 64,
                                  fetch=self.fetch, block=1024)
        self.assertTrue(head.startswith(b"Protein.Group\tGenes\tA\tB\nP1\tG1\t1\t2\n"))
        self.assertGreaterEqual(len(head), 64)

    def test_a_member_is_fetched_without_the_rest_of_the_archive(self):
        import random
        buf = io.BytesIO()
        rng = random.Random(0)
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("raw/big.bin", bytes(rng.getrandbits(8) for _ in range(200_000)))  # incompressible
            zf.writestr("txt/proteinGroups.txt", "Majority protein IDs\tGene names\n" + "P\tG\n" * 3000)
            zf.writestr("zz.bin", bytes(rng.getrandbits(8) for _ in range(100_000)))
        data = buf.getvalue()
        calls = []

        def fetch(url, start, end):
            calls.append((start, end))
            return data[start:end + 1]

        import tempfile
        from pathlib import Path
        dest = Path(tempfile.mkdtemp()) / "proteinGroups.txt"
        rec = remote.fetch_member(remote.File("a.zip", len(data), "https://x/a.zip"), "txt/proteinGroups.txt", dest,
                                  fetch=fetch, block=4096, chunk=8192)
        expected = ("Majority protein IDs\tGene names\n" + "P\tG\n" * 3000).encode()
        self.assertEqual(dest.read_bytes(), expected)
        self.assertEqual(rec["member_bytes"], len(expected))
        self.assertEqual(rec["member_sha256"], __import__("hashlib").sha256(expected).hexdigest())
        self.assertLess(sum(e - s + 1 for s, e in calls), len(data) / 2)
        self.assertFalse(any(p.name.endswith(".sparse.zip") for p in dest.parent.iterdir()))

    def test_a_files_first_bytes(self):
        self.assertEqual(remote.head("https://x/a.zip", len(self.data), 10, fetch=self.fetch), self.data[:10])
        self.assertEqual(remote.head("https://x/a.zip", 4, 10, fetch=self.fetch), self.data[:4])


class SiteTests(unittest.TestCase):
    def test_each_ftp_host_has_its_own_connection_cap_and_tls(self):
        self.assertEqual(remote.ftp_site("ftp://ftp.pride.ebi.ac.uk/pride/x"), ("ftp.pride.ebi.ac.uk", False))
        self.assertEqual(remote.ftp_site("ftp://massive-ftp.ucsd.edu/v15/x"), ("massive-ftp.ucsd.edu", True))
        with self.assertRaises(ValueError):
            remote.ftp_site("ftp://elsewhere.org/x")
        self.assertLessEqual(remote.FTP_SITES["ftp.pride.ebi.ac.uk"][1], 8)  # PRIDE refused 16 at once

    def test_chunks_cover_a_file_once(self):
        self.assertEqual(remote.chunks(20, 8), [(0, 7), (8, 15), (16, 19)])
        self.assertEqual(remote.chunks(8, 8), [(0, 7)])


class DroppedConnectionTests(unittest.TestCase):
    """B3's walk logged 14 proteinGroups.txt files and the slow 245 to 330 MB
    reports as 'fetch failed: ... got N': PRIDE's FTP ended a transfer early,
    and the short read was returned instead of tried again."""

    def setUp(self):
        from unittest import mock
        self.data = bytes(range(256)) * 400
        self.rests, self.drops = [], [3000, 5000]  # bytes each RETR gives before its connection ends
        test = self

        class Sock:
            def __init__(self, at):
                self.at, self.left = at, (test.drops.pop(0) if test.drops else len(test.data))

            def recv(self, n):
                n = min(n, self.left, 1024)
                b = test.data[self.at:self.at + n]
                self.at += len(b)
                self.left -= len(b)
                return b

            def close(self):
                pass

        class Conn:
            def voidcmd(self, cmd):
                pass

            def transfercmd(self, cmd, rest=None):
                test.rests.append(rest or 0)
                return Sock(rest or 0)

        from contextlib import contextmanager

        @contextmanager
        def connection(url):
            yield Conn()
        self.patches = [mock.patch.object(remote, "ftp_connection", connection),
                        mock.patch.object(remote.time, "sleep", lambda s: None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_a_read_cut_short_is_resumed_where_it_stopped(self):
        got = remote.ftp_read("ftp://ftp.pride.ebi.ac.uk/pride/x", 100, 20_000)
        self.assertEqual(got, self.data[100:20_100])
        self.assertEqual(self.rests, [100, 3100, 8100])

    def test_a_read_that_never_progresses_fails(self):
        self.drops = [0] * 50
        with self.assertRaises(OSError):
            remote.ftp_read("ftp://ftp.pride.ebi.ac.uk/pride/x", 0, 1000)

    def test_a_refused_login_is_tried_again_and_a_missing_file_is_not(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ftplib.error_perm("530 Authentication error: invalid credentials")
            return "listed"
        self.assertEqual(remote._retry(flaky), "listed")
        self.assertEqual(len(calls), 3)

        def missing():
            calls.append(1)
            raise ftplib.error_perm("550 no such file")
        calls.clear()
        with self.assertRaises(ftplib.error_perm):
            remote._retry(missing)
        self.assertEqual(len(calls), 1)


class HeaderTests(unittest.TestCase):
    def test_the_first_line_is_split_on_tabs_or_commas(self):
        self.assertEqual(remote.first_line_fields(b"\xef\xbb\xbfA\tB\tC\r\n1\t2\t3\n"), ["A", "B", "C"])
        self.assertEqual(remote.first_line_fields(b'A,"B, b",C\n1,2,3\n'), ["A", "B, b", "C"])

    def test_a_header_cut_mid_line_is_not_a_header(self):
        self.assertIsNone(remote.first_line_fields(b"A\tB\tC"))

    def test_a_tab_separated_header_whose_names_hold_commas_is_split_on_its_tabs(self):
        # PXD053397, PXD053298: DIA-NN's run names hold commas; the next line keeps the header's tabs, and
        # the service splits it so (service/pipeline/alignment.py _delimiter)
        header = b"Protein.Group\tGenes\tD:\\r\\a,b,c,d.raw\tD:\\r\\e,f,g,h.raw"
        fields = ["Protein.Group", "Genes", "D:\\r\\a,b,c,d.raw", "D:\\r\\e,f,g,h.raw"]
        self.assertEqual(remote.first_line_fields(header + b"\r\nP1\tTP53\t1\t2\r\n"), fields)
        self.assertEqual(remote.first_line_fields(header + b"\n#!{Type}E\tE\n\nP1\tTP53\t1\t2\n"), fields)
        # without a whole next line in the bytes, the header alone decides, as before
        self.assertEqual(len(remote.first_line_fields(header + b"\r\nP1\tTP53")), 7)
        self.assertEqual(remote.first_line_fields(b"A,B\tb,C\n1,2,3\n"), ["A", "B\tb", "C"])

    def test_a_line_may_end_in_a_lone_cr(self):
        # Excel's "CSV (Macintosh)"; B3's walk met six such tables
        self.assertEqual(remote.first_line_fields(b"A\tB\tC\r1\t2\t3\r"), ["A", "B", "C"])
        self.assertEqual(remote.first_line_fields(b'A,"B, b",C\r1,2,3\n'), ["A", "B, b", "C"])
        self.assertIsNone(remote.first_line_fields(b"A\tB\tC"))

    def test_a_utf_16_header_is_read_by_its_byte_order_mark(self):
        # as the service decodes an upload (service/app.py _decode_matrix); the bytes may stop mid-character
        for bom, codec in ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
            data = bom + "Gène\tB\tC\r\n1\t2\t3\r\n".encode(codec)
            with self.subTest(codec=codec):
                self.assertEqual(remote.first_line_fields(data), ["Gène", "B", "C"])
                self.assertEqual(remote.first_line_fields(data[:-1]), ["Gène", "B", "C"])
                self.assertIsNone(remote.first_line_fields(data[:9]))


if __name__ == "__main__":
    unittest.main()
