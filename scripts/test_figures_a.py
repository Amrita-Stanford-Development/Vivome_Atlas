"""Figure 1 (scripts/figures/fig1_design.py) and the Methods illustration of
reading an upload (scripts/figures/methods_reading.py): each number they
draw is the committed record it names, the page shows the same records,
and the PBMC240 example's numbers agree with each other. Standard library
only."""
import base64
import json
import re
import statistics
import unittest

from figures import common, fig1_design, methods_reading

MANUSCRIPT_HTML = (common.REPO / "web" / "manuscript.html").read_text(encoding="utf-8")


def load(rel):
    return json.loads((common.REPO / rel).read_text(encoding="utf-8"))


class FigureOneTests(unittest.TestCase):
    def setUp(self):
        self.rows = fig1_design.data()
        self.records = load(fig1_design.MANUSCRIPT)["records"]
        self.by_label = {r["label"]: r for r in self.rows}

    def test_each_number_is_its_manuscript_record_and_the_page_shows_it(self):
        self.assertEqual(len(self.rows), len(fig1_design.NUMBERS))
        for r in self.rows:
            with self.subTest(label=r["label"]):
                key = re.fullmatch(r"records\.(\w+)\.value", r["field"]).group(1)
                record = self.records[key]
                self.assertEqual(record["status"], "measured")
                self.assertEqual(r["value"], record["value"])
                self.assertIn(f'data-ms="{key}"', MANUSCRIPT_HTML, "the page's text shows the same record")

    def test_key_values_match_the_served_model_elsewhere(self):
        facts = load("web/data/workflow.json")["facts"]
        manifest = load("web/data/atlas_manifest.json")
        self.assertEqual(self.by_label["shared gene list"]["value"], facts["feature_space"]["value"])
        self.assertEqual(self.by_label["shared gene list"]["value"], manifest["model"]["feature_space_size"])
        self.assertEqual(self.by_label["members"]["value"], facts["members"]["value"])
        self.assertEqual(self.by_label["shared space"]["value"], manifest["model"]["latent_dim"])
        self.assertEqual(self.by_label["reference cells"]["value"], manifest["modalities"]["rna"]["cells"])
        self.assertEqual(self.by_label["reference types"]["value"], manifest["modalities"]["rna"]["classes"])
        self.assertEqual(self.by_label["agreement gate"]["value"], facts["agreement_threshold"]["value"])
        self.assertEqual(self.by_label["encoder weight at the gate"]["value"], facts["weight_used"]["value"])
        self.assertEqual(self.by_label["most cells per upload"]["value"],
                         load("web/data/workflow.json")["service"]["max_cells"]["value"])

    def test_the_answer_levels_and_reasons_are_the_pages_words(self):
        page = " ".join(MANUSCRIPT_HTML.split())
        for words in ("a type answer", "a family answer", "a lineage answer", "too little measured",
                      "outside the supported region", "no type stands out", "several types fit",
                      "Nothing is fitted on the user's upload"):
            self.assertIn(words, page)


class ReadingTests(unittest.TestCase):
    def setUp(self):
        self.rows = methods_reading.data()
        self.wf = load(methods_reading.WORKFLOW)
        self.one = {r["label"]: r for r in self.rows if not r["series"]}
        self.series = {}
        for r in self.rows:
            if r["series"]:
                self.series.setdefault(r["series"], []).append(r)

    def test_file_level_numbers_are_the_workflow_records(self):
        for _, label, path, _ in methods_reading.FACTS:
            with self.subTest(label=label):
                record = self.wf[path[0]][path[1]]
                self.assertEqual(record["status"], "measured")
                self.assertEqual(self.one[label]["value"], record["value"])

    def test_the_counts_add_up(self):
        v = {label: r["value"] for label, r in self.one.items()}
        facts = self.wf["facts"]
        self.assertEqual(v["rows resolved"] + v["rows unmapped"] + v["rows ambiguous"], v["rows"])
        self.assertEqual(v["genes filled"] + facts["unmatched_rows"]["value"], facts["rows_after_collapse"]["value"])
        self.assertEqual(v["own share"] + v["neighbour share"], 1.0)
        self.assertGreater(v["median observed value"], v["linear threshold"], "PBMC240 is read as linear")
        self.assertEqual(self.wf["raw"]["pbmc240"]["scale"]["detected"], "linear")

    def test_the_blue_cell_is_the_workflow_pages_cell(self):
        trace = self.wf["trace"]
        blue = trace["story"]["default"]
        self.assertEqual(self.series["blue cell"][0]["label"], trace["cells"][blue]["id"])
        self.assertEqual(self.series["blue cell"][0]["value"], trace["cells"][blue]["observed"])
        detail = next(d for d in trace["detail"] if d["cell"] == blue)
        self.assertEqual(self.series["linear"][0]["value"], detail["raw_row"][0][1])
        self.assertEqual(self.series["log2"][0]["value"], detail["raw_row"][0][2])
        heat = trace["heatmap"]
        at = heat["cells"].index(blue)
        seen, missing = methods_reading.FOLLOWED_GENES
        self.assertEqual(heat["mask"][at][heat["genes"].index(seen)], 1, "the first gene is one it measured")
        self.assertEqual(heat["mask"][at][heat["genes"].index(missing)], 0, "the second is one it did not")
        z = {r["label"]: r["value"] for r in self.series["z"]}
        self.assertEqual(z[missing], 0.0, "an unmeasured gene is zero")
        self.assertEqual([r["value"] for r in self.series["mask"]], heat["mask"][at])

    def test_the_presence_sample_is_the_files_own(self):
        presence = self.wf["raw"]["pbmc240"]["parse"]["presence"]
        raw = base64.b64decode(presence["bits"])
        n_rows, n_cols = presence["rows"], presence["cols"]
        bit = methods_reading._bit
        blue = self.wf["trace"]["story"]["default"]
        # the decoding is right: the blue cell's column sums to what the trace says it measured, and the
        # whole grid's missing share is the record's
        self.assertEqual(sum(bit(raw, r * n_cols + blue) for r in range(n_rows)),
                         self.wf["trace"]["cells"][blue]["observed_raw"])
        observed = sum(bin(b).count("1") for b in raw)
        self.assertAlmostEqual(1 - observed / (n_rows * n_cols), self.wf["facts"]["missing_share"]["value"], places=4)
        grid = [s for s in self.series if s.startswith("presence")]
        self.assertEqual(len(grid), methods_reading.GRID_FEATURES)
        ids = [c["id"] for c in self.wf["trace"]["cells"]]
        for name in grid:
            r = int(name.rsplit(" ", 1)[1])
            for cell in self.series[name]:
                self.assertEqual(cell["value"], bit(raw, r * n_cols + ids.index(cell["label"])))
        self.assertIn(ids[blue], [c["label"] for c in self.series[grid[0]]])

    def test_the_graph_and_the_floor_are_the_traces(self):
        trace = self.wf["trace"]
        blue = trace["story"]["default"]
        smoothing = trace["stages"]["smoothing"]
        self.assertEqual(len(self.series["neighbour"]), self.one["neighbours"]["value"])
        ids = [c["id"] for c in trace["cells"]]
        self.assertEqual([ids.index(r["label"]) for r in self.series["neighbour"]], smoothing["neighbours"][blue])
        counts = [r["value"] for r in self.series["genes measured"]]
        self.assertEqual(len(counts), self.one["cells"]["value"], "one tick per cell")
        self.assertEqual(statistics.median(counts), self.one["median genes measured"]["value"])
        below = sum(c < self.one["floor"]["value"] for c in counts)
        self.assertEqual(below, self.one["cells below the floor"]["value"])
        self.assertEqual(len(self.series["layout x"]), len(trace["cells"]))


if __name__ == "__main__":
    unittest.main()
