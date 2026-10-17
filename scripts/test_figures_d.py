"""Figures 4, 5 and 6 (scripts/figures/fig4_second_opinion.py, fig5_benchmark.py,
fig6_limits.py): their numbers, read again from the committed sources, and
the ones the Manuscript page states (web/data/manuscript.json) drawn as the
page states them. Standard library only."""
import csv
import json
import re
import unittest

from figures import common
from figures import fig4_second_opinion as fig4
from figures import fig5_benchmark as fig5
from figures import fig6_limits as fig6


def load(rel):
    return json.loads((common.REPO / rel).read_text(encoding="utf-8"))


def table(rel):
    with open(common.REPO / rel, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


PAGE = load("web/data/manuscript.json")["records"]


def page(key):
    record = PAGE[key]
    assert record["status"] == "measured", key
    return record["value"]


def pick(rows, **match):
    found = [r for r in rows if all(r[k] == v for k, v in match.items())]
    if len(found) != 1:
        raise AssertionError(f"{len(found)} rows match {match}")
    return found[0]


class Figure4Tests(unittest.TestCase):
    rows = fig4.data()

    def test_every_upload_is_a_dot_against_the_bar(self):
        uploads = table(fig4.UPLOADS)
        bar = pick(self.rows, series="bar")["value"]
        self.assertEqual(bar, float(uploads[0]["agreement_threshold"]))
        self.assertEqual(bar, load(fig4.GATE)["agreement_threshold"])
        for key, name in fig4.KINDS:
            mine = [r for r in self.rows if r["series"] == name]
            theirs = [u for u in uploads if u["group"] == key]
            self.assertEqual(sorted(r["value"] for r in mine), sorted(float(u["agreement"]) for u in theirs), key)
            # The share at or above the bar is the share the page says uses the term.
            above = 100 * sum(r["value"] >= bar for r in mine) / len(mine)
            self.assertAlmostEqual(above / 100, page(f"suite_{key}_term_used"), places=3)
        self.assertEqual(sum(r["panel"] == "a" and r["series"] in dict(fig4.KINDS).values() for r in self.rows),
                         len(uploads))

    def test_the_datasets_agreement_is_the_pages(self):
        for key, name in fig4.DATASETS:
            value = pick(self.rows, panel="a", label=name)["value"]
            self.assertEqual(value, page(f"so_agreement_{key}"), name)
        self.assertGreaterEqual(pick(self.rows, panel="a", label="Fulcher")["value"], 0.4)
        self.assertLess(pick(self.rows, panel="a", label="PBMC240")["value"], 0.4)

    def test_the_gains_are_the_pages(self):
        fulcher = pick(self.rows, panel="b", label="Fulcher, protein", series=fig4.SERIES_GAIN)
        self.assertAlmostEqual(fulcher["value"] / 100, page("so_fulcher_gain"), places=6)
        self.assertAlmostEqual(fulcher["lo"] / 100, page("so_fulcher_gain_lo"), places=6)
        self.assertAlmostEqual(fulcher["hi"] / 100, page("so_fulcher_gain_hi"), places=6)
        khoury = pick(self.rows, panel="b", label="Khoury, protein", series=fig4.SERIES_GAIN)
        self.assertAlmostEqual(khoury["value"] / 100, page("so_khoury_gain"), places=6)
        hao = pick(self.rows, panel="b", label="Hao donors, held out", series=fig4.SERIES_GAIN)
        self.assertAlmostEqual(hao["value"] / 100, page("ho_hao_gain"), places=6)
        self.assertAlmostEqual(hao["lo"] / 100, page("ho_hao_gain_lower"), places=6)
        self.assertAlmostEqual(pick(self.rows, panel="b", label="Fulcher, protein",
                                    series=fig4.SERIES_WITHOUT)["value"] / 100, page("so_fulcher_without"), places=6)
        drop = load(fig4.SUITE)["scenario_drop_vs_v31"]
        for key, name in fig4.KINDS:
            gain = pick(self.rows, panel="b", label=name, series=fig4.SERIES_GAIN)["value"]
            self.assertAlmostEqual(gain, -drop[key], places=2, msg=key)
        self.assertAlmostEqual(pick(self.rows, panel="b", label="One type alone", series=fig4.SERIES_WITH)["value"] / 100,
                               page("suite_single_best_guess_per_upload_balanced"), places=6)
        self.assertAlmostEqual(pick(self.rows, panel="b", label="PBMC-like", series=fig4.SERIES_WITHOUT)["value"] / 100,
                               page("suite_pbmc_without"), places=6)

    def test_the_gate_is_the_pages(self):
        fails = {r["series"]: r["value"] for r in self.rows if r["panel"] == "c" and r["unit"] == "probability"}
        self.assertEqual(fails[fig4.SERIES_UNGATED], page("ra_gate_fail_ungated"))
        self.assertEqual(fails[fig4.SERIES_GATED], page("ra_gate_fail_gated"))
        single = pick(self.rows, panel="c", label="One type alone", series=fig4.SERIES_GATED)
        self.assertEqual(single["value"], load(fig4.EXPLORATION)["finalists"][fig4.GATED]["calibration_suite"]["single"])


class Figure5Tests(unittest.TestCase):
    rows = fig5.data()

    def test_only_outside_methods_and_every_run(self):
        khoury = [r for r in table(fig5.KHOURY) if not re.match(r"^v\d", r["model_b"])]
        fulcher = [r for r in table(fig5.FULCHER) if r["dataset"] == "Fulcher 2026"]
        a = [r for r in self.rows if r["panel"] == "a"]
        b = [r for r in self.rows if r["panel"] == "b"]
        self.assertEqual(len(a), len(khoury))
        self.assertEqual(len(a), page("bm_khoury_baseline_runs"))
        self.assertEqual(len(b), page("bm_fulcher_pairings"))
        self.assertFalse([r for r in self.rows if "VivOME" in r["series"] or re.match(r"^v\d", r["series"])])
        self.assertEqual(sorted(r["value"] for r in a), sorted(float(r["diff_bal_acc_pct"]) for r in khoury))
        self.assertEqual(sorted(r["value"] for r in b), sorted(float(r["point_estimate_pct"]) for r in fulcher))
        for panel in ("a", "b"):
            names = [(r["series"], r["label"]) for r in self.rows if r["panel"] == panel]
            self.assertEqual(len(names), len(set(names)), "each run is named apart")

    def test_the_sides_are_the_pages(self):
        a = [r for r in self.rows if r["panel"] == "a"]
        b = [r for r in self.rows if r["panel"] == "b"]
        self.assertEqual(sum(r["lo"] > 0 for r in a), page("bm_khoury_baseline_favour"))
        self.assertEqual(sum(r["lo"] > 0 for r in b), page("bm_fulcher_favour"))
        self.assertAlmostEqual(min(r["lo"] for r in b) / 100, page("bm_fulcher_lowest_ci"), places=6)
        pca = pick(a, series="PCA")
        self.assertAlmostEqual(pca["value"] / 100, page("bm_khoury_vs_pca"), places=6)
        self.assertLess(pca["lo"], 0)
        self.assertGreater(pca["hi"], 0)
        scanvi = [r for r in a if r["series"] == "scANVI" and r["label"].startswith("nearest neighbours")]
        self.assertEqual(sum(r["lo"] <= 0 <= r["hi"] for r in scanvi), page("bm_khoury_scanvi_knn_neither"))
        for r in self.rows:
            self.assertLessEqual(r["lo"], r["value"])
            self.assertLessEqual(r["value"], r["hi"])


class Figure6Tests(unittest.TestCase):
    rows = fig6.data()

    def test_one_type_alone_is_the_pages(self):
        a = [r for r in self.rows if r["panel"] == "a" and r["unit"] == "right when committed, %"]
        for t in ("B", "NK", "monocyte"):
            name = fig6.TYPE_NAMES[t]
            self.assertAlmostEqual(pick(a, label=name, series=fig6.ALONE)["value"] / 100,
                                   page(f"single_alone_correct_{t}"), places=6)
            self.assertAlmostEqual(pick(a, label=name, series=fig6.WHOLE)["value"] / 100,
                                   page(f"single_mixed_correct_{t}"), places=6)
        recall = [r for r in self.rows if r["panel"] == "a" and r["unit"] == "recall, %"]
        for t in ("CD4T", "CD8T"):
            row = pick(recall, label=fig6.TYPE_NAMES[t], series=fig6.PAIRED + "CD4T+CD8T")
            self.assertAlmostEqual(row["value"] / 100, page(f"single_pair_recall_{t}"), places=6)

    def test_every_foreign_cell_is_counted_once(self):
        sets = load(fig6.FOREIGN)["foreign_development"]
        b = [r for r in self.rows if r["panel"] == "b"]
        self.assertEqual(len({r["series"] for r in b}), len(sets))
        for key, record in sets.items():
            name = fig6.SET_NAMES.get(key.split(" ", 1)[1], key.split(" ", 1)[1])
            mine = [r for r in b if r["series"] == name]
            self.assertEqual(pick(mine, label="cells")["value"], record["cells"])
            self.assertEqual(sum(r["value"] for r in mine if r["label"] != "cells"), record["cells"], key)
        answered = sum(r["value"] for r in b if r["label"].startswith("answer")
                       and r["series"] in ("HEK293T", "HCT116", "K562"))
        self.assertEqual(answered, page("ood_lines_answered"))
        self.assertEqual(sum(r["value"] for r in b if r["series"] == "HMC3" and r["label"].startswith("answer")),
                         page("ood_hmc3_answered"))
        self.assertIn("answer, family: T cell", {r["label"] for r in b})
        self.assertIn("answer, lineage: lymphoid", {r["label"] for r in b})
        self.assertIn("answer, type: erythrocyte", {r["label"] for r in b})

    def test_cd8_against_cd4_is_the_pages(self):
        c = [r for r in self.rows if r["panel"] == "c"]
        for label, key in (("naive CD4 T", "naive_cd4"), ("CD4 T", "cd4"), ("CD8 T", "cd8")):
            self.assertAlmostEqual(pick(c, label=label)["value"] / 100, page(f"cd8_called_{key}"), places=6)
        d = {r["label"]: r for r in self.rows if r["panel"] == "d"}
        self.assertAlmostEqual(d["S100A4"]["value"], page("cd8_auc_s100a4"), places=6)
        self.assertAlmostEqual(d["ANXA1"]["value"], page("cd8_auc_anxa1"), places=6)
        self.assertAlmostEqual(d["CD8A"]["value"], page("cd8_auc_cd8a"), places=6)
        self.assertEqual(d["S100A4"]["series"], "higher in the CD4 T cluster")
        e = [r for r in self.rows if r["panel"] == "e"]
        self.assertEqual(pick(e, series="all")["value"], page("cd8_naive_like"))
        self.assertEqual(pick(e, label="CD4 T")["value"], page("cd8_naive_like_in_cd4"))


if __name__ == "__main__":
    unittest.main()
