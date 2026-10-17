"""The Methods illustrations of the model (scripts/figures/methods_encoder.py,
methods_answers.py, methods_second_opinion.py): each number drawn is the
committed record it names, and agrees with the served model's own spec and
the Manuscript page's records. Standard library only."""
import csv
import json
import math
import re
import unittest

from figures import common, methods_answers, methods_encoder, methods_second_opinion

REPO = common.REPO


def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def records():
    return load("web/data/manuscript.json")["records"]


def by_label(rows, panel=None, series=None):
    return {r["label"]: r["value"] for r in rows
            if (panel is None or r["panel"] == panel) and (series is None or r["series"] == series)}


class EncoderTests(unittest.TestCase):
    rows = methods_encoder.data()

    def test_the_layers_are_the_traced_members_and_the_pages_numbers(self):
        enc = load("web/data/workflow.json")["trace"]["stages"]["encoder"]
        layers = [r for r in self.rows if r["series"] == "layer"]
        self.assertEqual([r["value"] for r in layers], [layer["width"] for layer in enc["layers"]])
        rec = records()
        self.assertEqual(layers[0]["value"], rec["wf_input_width"]["value"])
        self.assertEqual([r["value"] for r in layers[1:]],
                         [rec[k]["value"] for k in ("wf_hidden1", "wf_hidden2", "wf_latent")])
        parts = by_label(self.rows, series="input part")
        self.assertEqual(parts["values"], rec["wf_genes"]["value"])
        self.assertEqual(parts["module_values"], rec["wf_modules"]["value"])
        self.assertEqual(sum(parts.values()), layers[0]["value"], "the input is its four parts")
        self.assertEqual(by_label(self.rows, "a")["weights per member"], rec["wf_parameters"]["value"])

    def test_the_members_and_their_temperatures_are_the_specs(self):
        members = [r for r in self.rows if r["series"] == "member"]
        spec = load("service/model/v3_1/nb2_spec_v31.json")["assignment"]["temperature"]
        self.assertEqual(len(members), by_label(self.rows, "b")["members"])
        for r in members:
            self.assertAlmostEqual(r["value"], spec[r["label"]], places=4)
        rec = records()
        self.assertEqual(min(r["value"] for r in members), rec["temp_min"]["value"])
        self.assertEqual(max(r["value"] for r in members), rec["temp_max"]["value"])
        coord = [r["label"] for r in self.rows if r["series"] == "coordinate member"]
        self.assertEqual(len(coord), 1)
        self.assertIn(coord[0], [r["label"] for r in members])

    def test_the_training_numbers_are_the_pages_records(self):
        rec = records()
        train = {r["field"]: r["value"] for r in self.rows if r["series"] == "training"}
        self.assertEqual(len(train), 7)
        for field, value in train.items():
            key = field.split(".")[1]
            self.assertEqual(value, rec[key]["value"], key)

    def test_the_map_is_a_fixed_subsample_of_the_sites_coordinates(self):
        points = [r for r in self.rows if r["panel"] == "c" and r["series"]]
        self.assertLessEqual(len(points) // 2, methods_encoder.MAP_POINTS)
        tables = {"RNA": "web/data/metadata_RNA_lat128.csv", "protein": "web/data/metadata_PROT_lat128.csv"}
        for series, rel in tables.items():
            with open(REPO / rel, encoding="utf-8", newline="") as handle:
                table = list(csv.DictReader(handle))
            mine = [r for r in points if r["series"] == series]
            self.assertTrue(all(r["source"] == rel for r in mine))
            indices = []
            for r in mine:
                i, pc = re.fullmatch(r"row (\d+), (PC\d)", r["field"]).groups()
                self.assertEqual(r["value"], float(table[int(i)][pc]))
                self.assertEqual(r["label"], f"cell {table[int(i)]['orig_index']}")
                indices.append(int(i))
            rows = sorted(set(indices))
            self.assertEqual(rows[0], 0)
            step = rows[1] - rows[0]
            self.assertEqual(rows, list(range(0, len(table), step)), "every k-th row, from the first")
            self.assertEqual(indices.count(rows[0]), 2, "both coordinates of each point")
        with open(REPO / tables["RNA"], encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle))
        self.assertEqual(by_label(self.rows, "c")["projection components"],
                         len([c for c in header if c.startswith("PC")]))


class AnswerTests(unittest.TestCase):
    rows = methods_answers.data()

    def test_each_types_threshold_and_place_in_the_hierarchy_are_the_specs(self):
        spec = load("service/model/v3_1/nb2_spec_v31.json")
        types = [r for r in self.rows if r["series"] == "type"]
        self.assertEqual(len(types), records()["ref_classes"]["value"])
        for r in types:
            name = r["field"].split(", ", 1)[1]
            lineage, group, _ = r["label"].split(" > ")
            self.assertAlmostEqual(r["value"], spec["conformal"]["qhat_by_class"][name], places=4)
            self.assertEqual((group, lineage),
                             (spec["hierarchy"][name]["group"], spec["hierarchy"][name]["lineage"]), name)
        rec = records()
        self.assertEqual(min(r["value"] for r in types), rec["qhat_min"]["value"])
        self.assertEqual(max(r["value"] for r in types), rec["qhat_max"]["value"])
        self.assertEqual(len({r["label"].split(" > ")[1] for r in types}), rec["ref_groups"]["value"])
        self.assertEqual(len({r["label"].split(" > ")[0] for r in types}), rec["ref_lineages"]["value"])
        marginal = by_label(self.rows, series="marginal")["marginal"]
        self.assertAlmostEqual(marginal, spec["conformal"]["marginal_qhat"], places=4)

    def test_every_type_has_the_sites_plain_name(self):
        plain = methods_answers._plain_names()
        names = load("web/data/workflow.json")["class_order"]
        self.assertEqual(set(plain), set(names))
        shown = [r["label"].split(" > ")[2] for r in self.rows if r["series"] == "type"]
        self.assertEqual(shown, [plain[n] for n in names])

    def test_the_checks_use_the_pages_records_and_the_services_settings(self):
        a = by_label(self.rows, "a")
        rec = records()
        self.assertEqual(a["observed genes, floor"], rec["wf_floor"]["value"])
        config = (REPO / "service" / "config.py").read_text(encoding="utf-8")
        self.assertRegex(config, rf"MIN_OBSERVED_GENES\s*=\s*{a['observed genes, floor']}\b")
        ood = load("service/model/v3_1/nb2_spec_v31.json")["ood"]["threshold"]
        self.assertEqual(a["similarity, threshold"], round(ood, 3))
        self.assertEqual(a["target coverage"], rec["coverage_target"]["value"])
        self.assertEqual(a["members"], rec["wf_members"]["value"])


class SecondOpinionTests(unittest.TestCase):
    rows = methods_second_opinion.data()

    def test_the_settings_are_the_served_specs(self):
        best = load("service/model/v4_1/spec_v41.json")["best_guess"]
        a = by_label(self.rows, "a")
        self.assertEqual(a["bar"], best["agreement_threshold"])
        self.assertEqual(a["encoder weight, term used"], best["gate_on_fusion_weight"])
        self.assertEqual(a["encoder weight, term flat"], best["fusion_weight"])
        self.assertEqual(a["smoothed share"], best["smoothed_share"])
        self.assertEqual(a["correlation temperature"], best["correlation_temperature"])
        self.assertEqual(a["observed genes, floor"], records()["wf_floor"]["value"])

    def test_the_worked_gate_adds_up(self):
        b = by_label(self.rows, "b")
        self.assertEqual(b["counted"], b["cells"] - b["below the floor"])
        self.assertTrue(math.isclose(b["agreeing"] / b["counted"], b["agreement"], abs_tol=5e-5))
        self.assertEqual(b["bar"], by_label(self.rows, "a")["bar"], "one bar in both panels")
        fusion = load("web/data/workflow.json")["trace"]["stages"]["fusion"]
        term = [r["label"] for r in self.rows if r["unit"] == "correlation term"]
        self.assertEqual(term, [fusion["correlation_term"]])
        self.assertEqual(term[0], "used" if b["agreement"] >= b["bar"] else "flat")
        self.assertEqual(b["agreement"], records()["so_agreement_pbmc240"]["value"])


if __name__ == "__main__":
    unittest.main()
