"""The draw's frame (research/benchmark/protocol-value-scale.md, "The frame")."""
from __future__ import annotations

import hashlib
import random
import unittest

from valuescale.corpus import frame

LINK = '<a href="http://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={0}" target="_blank">{0}</a>'
HEADER = "Dataset Identifier\tTitle\tRepos\tSpecies\tInstrument\tPublication\tLabHead\tAnnounce Date\tKeywords\tannouncementXML\t\n"


def _record(acc, title="A title", repo="PRIDE", species="Homo sapiens", date="2024-05-01"):
    return "\t".join([LINK.format(acc), title, repo, species, "Orbitrap", "no publication", "A Person", date, "kw, "]) + "\n"


class ParseTests(unittest.TestCase):
    def test_a_plain_record(self):
        rows = frame.parse_index((HEADER + _record("PXD000001")).encode())
        self.assertEqual(rows, [frame.Row("PXD000001", "A title", "PRIDE", "Homo sapiens", "2024-05-01")])

    def test_a_title_broken_over_two_lines_is_joined(self):
        text = HEADER + _record("PXD000002", title="First half\nsecond half") + _record("PXD000003")
        rows = frame.parse_index(text.encode())
        self.assertEqual([r.accession for r in rows], ["PXD000002", "PXD000003"])
        self.assertEqual(rows[0].title, "First half second half")
        self.assertEqual(rows[0].repo, "PRIDE")

    def test_a_title_holding_a_tab_keeps_the_fields_in_place(self):
        rows = frame.parse_index((HEADER + _record("PXD000004", title="Left\tright", repo="MassIVE")).encode())
        self.assertEqual((rows[0].title, rows[0].repo, rows[0].date), ("Left right", "MassIVE", "2024-05-01"))

    def test_bytes_that_are_not_utf8_do_not_stop_the_parse(self):
        raw = (HEADER + _record("PXD000005", title="café")).encode("latin-1")
        self.assertEqual(frame.parse_index(raw)[0].accession, "PXD000005")

    def test_a_record_without_a_repository_stops_the_parse(self):
        bad = "\t".join([LINK.format("PXD000006"), "title", "nowhere"]) + "\n"
        with self.assertRaises(ValueError):
            frame.parse_index((HEADER + bad).encode())


class KeptTests(unittest.TestCase):
    def test_repository_dates_and_species(self):
        rows = [
            frame.Row("PXD000010", "", "PRIDE", "Homo sapiens", "2020-01-01"),
            frame.Row("PXD000011", "", "MassIVE", "Mus musculus, Homo sapiens ", "2026-10-31"),
            frame.Row("PXD000012", "", "jPOST", "Homo sapiens", "2023-01-01"),
            frame.Row("PXD000013", "", "PRIDE", "Homo sapiens", "2019-12-31"),
            frame.Row("PXD000014", "", "PRIDE", "Homo sapiens", "2026-11-01"),
            frame.Row("PXD000015", "", "PRIDE", "Mus musculus", "2023-01-01"),
        ]
        self.assertEqual([r.accession for r in frame.kept(rows)], ["PXD000010", "PXD000011"])


class OrderTests(unittest.TestCase):
    def test_sorted_then_shuffled_with_the_protocol_seed(self):
        accs = ["PXD000003", "PXD000001", "PXD000002", "PXD000001"]
        expected = ["PXD000001", "PXD000002", "PXD000003"]
        random.Random(20261103).shuffle(expected)
        self.assertEqual(frame.order(accs), expected)

    def test_the_split_is_the_parity_of_the_hash(self):
        for acc in ("PXD000001", "PXD064083", "PXD012345"):
            even = int(hashlib.sha256(f"20261103:{acc}".encode()).hexdigest(), 16) % 2 == 0
            self.assertEqual(frame.split_of(acc), "calibration" if even else "test")

    def test_identifiers_are_found_in_any_letter_case(self):
        text = "bank id pxd064083_t, MSV000099294 and IPX0001234000; PXD12345 is too short"
        self.assertEqual(frame.identifiers(text), {"PXD064083", "MSV000099294", "IPX0001234000"})


class DenyTests(unittest.TestCase):
    def test_sealed_and_tracked_deposits_are_dropped_under_either_identifier(self):
        rows = [frame.Row(a, "", repo, "Homo sapiens", "2024-01-01") for a, repo in
                [("PXD042367", "PRIDE"), ("PXD000020", "PRIDE"), ("PXD000021", "MassIVE"),
                 ("PXD000022", "MassIVE"), ("PXD000023", "PRIDE")]]
        massive = {"PXD000021": ("MSV000099294", "ftp://x/"), "PXD000022": ("MSV000000001", "ftp://y/")}
        keep, dropped = frame.deny(rows, tracked={"PXD000020", "MSV000099294"}, massive=massive)
        self.assertEqual([r.accession for r in keep], ["PXD000022", "PXD000023"])
        self.assertEqual(dropped, {"sealed": ["PXD042367"], "tracked": ["PXD000020", "PXD000021"]})

    def test_a_massive_row_needs_its_msv_identifier(self):
        rows = [frame.Row("PXD000030", "", "MassIVE", "Homo sapiens", "2024-01-01")]
        with self.assertRaises(KeyError):
            frame.deny(rows, tracked=set(), massive={})


class MassiveTests(unittest.TestCase):
    def test_the_msv_identifier_and_ftp_folder_are_read_from_the_announcement(self):
        xml = ('<cvParam accession="MS:1002487" cvRef="MS" name="MassIVE dataset identifier" value="MSV000103821"/>\n'
               '<cvParam accession="MS:1002852" cvRef="MS" name="Dataset FTP location" '
               'value="ftp://massive-ftp.ucsd.edu/v15/MSV000103821/"/>')
        self.assertEqual(frame.massive_from_xml(xml), ("MSV000103821", "ftp://massive-ftp.ucsd.edu/v15/MSV000103821/"))

    def test_an_announcement_without_them_gives_none(self):
        self.assertEqual(frame.massive_from_xml("<ProteomeXchangeDataset/>"), (None, None))


if __name__ == "__main__":
    unittest.main()
