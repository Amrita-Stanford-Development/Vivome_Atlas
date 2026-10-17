"""The figures (scripts/figures/, scripts/build_figures.py): each one's
numbers come from committed files and match what the page shows, and the
picture rebuilds byte for byte. Drawing needs matplotlib (the vivome
environment); without it those checks are skipped and the rest still run."""
import importlib.util
import re
import tempfile
import types
import unittest
from pathlib import Path

import build_figures as bf
from figures import common, style

HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None
MANUSCRIPT = (common.REPO / "web" / "manuscript.html").read_text(encoding="utf-8")


def example_module():
    """A tiny figure, for checking the framework itself."""
    source = "research/benchmark/khoury2026_posthoc_v41_check/paired_bootstrap.csv"

    def data():
        return [common.row("a", r["comparison"], float(r["diff_bal_acc_pct"]), lo=float(r["ci_lo"]),
                           hi=float(r["ci_hi"]), unit="percentage points", source=source,
                           field=f"row {i} diff_bal_acc_pct")
                for i, r in enumerate(common.read_csv(source)[:3])]

    def draw(rows, plt):
        fig = common.new_figure(plt, "single", 40)
        ax = fig.add_subplot()
        ax.errorbar([r["value"] for r in rows], range(len(rows)),
                    xerr=[[r["value"] - r["lo"] for r in rows], [r["hi"] - r["value"] for r in rows]],
                    fmt="o", color=style.ACCENT)
        common.panel_letter(ax, "a")
        return fig

    return types.SimpleNamespace(NAME="example", TITLE="Example", SECTION="results", WIDTH="single", ALT="An example.",
                                 CAPTION="An example.", SOURCES=(source,), data=data, draw=draw)


class FrameworkTests(unittest.TestCase):
    def test_rows_name_a_committed_file_and_the_csv_keeps_them(self):
        rows = example_module().data()
        text = common.csv_text(rows)
        self.assertTrue(text.startswith(",".join(common.COLUMNS) + "\n"))
        self.assertNotIn("\r", text)
        self.assertEqual(len(text.strip().split("\n")), len(rows) + 1)
        with self.assertRaises(FileNotFoundError):
            common.row("a", "x", 1, source="research/" + "no-such-file.json", field="x")

    def test_the_palette_is_the_sites(self):
        css = (common.REPO / "web" / "css" / "page.css").read_text(encoding="utf-8")
        for token, colour in (("ink", style.INK), ("accent", style.ACCENT), ("rna", style.RNA), ("prot", style.PROT)):
            self.assertRegex(css, rf"--{token}: {colour};", token)
        self.assertEqual(len(set(style.CATEGORICAL)), len(style.CATEGORICAL))

    @unittest.skipUnless(HAS_MATPLOTLIB, "drawing needs matplotlib (run in the vivome environment)")
    def test_a_figure_saves_svg_and_csv_and_rebuilds_byte_for_byte(self):
        module = example_module()
        with tempfile.TemporaryDirectory() as tmp:
            written = common.save(module, web_dir=Path(tmp), journal=True, journal_dir=Path(tmp) / "journal")
            svg = written["svg"].read_bytes()
            self.assertTrue(svg.startswith(b"<?xml"))
            self.assertNotIn(b"\r\n", svg)
            self.assertNotIn(b"<dc:date>", svg, "no build date, so a rebuild is identical")
            self.assertEqual(common.render(module), svg)
            self.assertEqual(written["csv"].read_text(encoding="utf-8"), common.csv_text(module.data()))
            self.assertGreater(written["tif"].stat().st_size, 0)
            self.assertTrue(written["pdf"].read_bytes().startswith(b"%PDF"))


class EveryFigureTests(unittest.TestCase):
    """Each module in scripts/figures/, as the page and the paper use it."""

    def test_each_figure_says_what_it_is_and_where_it_goes(self):
        names = set()
        for m in bf.modules():
            with self.subTest(figure=m.NAME):
                self.assertRegex(m.NAME, r"^[a-z0-9-]+$")
                self.assertNotIn(m.NAME, names)
                names.add(m.NAME)
                self.assertIn(m.WIDTH, style.WIDTHS_MM)
                self.assertIn(f'id="{m.SECTION}"', MANUSCRIPT, "its section is on the Manuscript page")
                for text in (m.ALT, m.CAPTION, m.TITLE):
                    self.assertNotIn("—", text, "no em dash")
                    self.assertNotRegex(text.lower(), r"calibrated|state of the art|beats scanvi|every ome")
                # A legend says what is shown; the numbers are the data's (a 95% interval aside).
                # Names with digits in them (CD8, v4.1, PBMC240) are names, not numbers.
                self.assertNotRegex(re.sub(r"95%", "", m.CAPTION + " " + m.ALT),
                                    r"(?<![A-Za-z\d.])\d+(?:[.,]\d+)*(?![A-Za-z\d])", "no typed numbers")
                for source in m.SOURCES:
                    self.assertTrue((common.REPO / source).exists(), source)

    def test_every_number_drawn_comes_from_a_named_source_and_the_page_has_it(self):
        for m in bf.modules():
            with self.subTest(figure=m.NAME):
                rows = m.data()
                for r in rows:
                    self.assertIn(r["source"], m.SOURCES, "a row's file is one the figure names")
                    self.assertTrue(r["field"], "and the field it came from")
                committed = common.WEB_FIGURES / f"{m.NAME}.csv"
                self.assertTrue(committed.exists(), "run python scripts/build_figures.py")
                self.assertEqual(committed.read_text(encoding="utf-8"), common.csv_text(rows),
                                 "web/figures is stale: run python scripts/build_figures.py")

    def test_the_page_index_lists_every_figure_as_its_module_says(self):
        committed = common.WEB_FIGURES / "index.json"
        if not bf.modules():
            return
        self.assertTrue(committed.exists(), "run python scripts/build_figures.py")
        self.assertEqual(committed.read_bytes(), bf.index(), "web/figures/index.json is stale: run python scripts/build_figures.py")

    @unittest.skipUnless(HAS_MATPLOTLIB, "drawing needs matplotlib (run in the vivome environment)")
    def test_every_committed_picture_is_what_the_data_draws_now(self):
        for m in bf.modules():
            with self.subTest(figure=m.NAME):
                committed = common.WEB_FIGURES / f"{m.NAME}.svg"
                self.assertEqual(committed.read_bytes(), common.render(m),
                                 "web/figures is stale: run python scripts/build_figures.py")


if __name__ == "__main__":
    unittest.main()
