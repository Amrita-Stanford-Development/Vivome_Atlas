"""web/data/docs.json, the Docs section's records (scripts/build_docs.py):
the committed file is the builder's output, built for the manifest's
release, inside its size budget; every record is measured with its basis or
pending with a note; the headline figures are their sources' figures; and
the traps found while planning the page stay closed."""
import ast
import json
import math
import re
import unittest

import build_docs as bd

FORMATS = {"count", "percent", "plain", "integer", "fixed2", "fixed3", "fixed4", "pct1", "pct2"}
# The records the pages show as Pending on purpose: work not done yet.
PENDING_ON_PURPOSE = {"rl_v2_test"}
STEP_IDS = ["step1", "phase_a", "phase_a2", "zscore", "b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7",
            "decision", "v2"]
ISO = re.compile(r"(?<!\d)20\d\d-\d\d-\d\d(?!\d)")


def load(rel_path):
    return json.loads((bd.REPO / rel_path).read_text(encoding="utf-8"))


class TestDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(bd.MANIFEST.read_text(encoding="utf-8"))
        cls.built = bd.build(cls.manifest)
        cls.committed_bytes = bd.OUTPUT.read_bytes()
        cls.d = json.loads(cls.committed_bytes)
        cls.r = {k: v["value"] for k, v in cls.d["records"].items()}

    def test_the_committed_file_is_the_builder_s_output_byte_for_byte(self):
        built = (json.dumps(self.built, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
        self.assertEqual(built, self.committed_bytes, "run python scripts/build_manifest.py")

    def test_it_is_built_for_the_manifest_s_release(self):
        self.assertEqual(self.d["built_for"]["atlas_version"], self.manifest["atlas_version"])
        self.assertEqual(self.d["built_for"]["model_name"], self.manifest["model"]["name"])

    def test_every_source_s_sha256_is_current(self):
        self.assertNotIn("research/todo.md", self.d["sources"], "the todo changes with every commit")
        for path, digest in self.d["sources"].items():
            self.assertEqual(bd.sha256(bd.REPO / path), digest, path)

    def test_it_stays_inside_its_size_budget(self):
        self.assertLess(len(self.committed_bytes), bd.SIZE_BUDGET)

    def test_every_record_is_measured_with_a_basis_and_format_or_pending_with_a_note(self):
        records = self.d["records"]
        self.assertGreater(len(records), 80)
        for key, r in records.items():
            self.assertTrue(key.startswith("rl_"), key)
            if r["status"] == "measured":
                self.assertIsNotNone(r["value"], key)
                self.assertNotIsInstance(r["value"], bool, key)
                self.assertIsInstance(r["value"], (int, float), key)
                self.assertTrue(r["basis"], key)
                self.assertIn(r["format"], FORMATS, key)
            else:
                self.assertEqual(r["status"], "pending", key)
                self.assertIsNone(r["value"], key)
                self.assertTrue(r["note"], key)
        self.assertEqual({k for k, r in records.items() if r["status"] == "pending"}, PENDING_ON_PURPOSE)

    def test_a_quoted_prediction_says_it_was_written_before_the_run(self):
        for key in ("rl_b7_expected_contradict_s1", "rl_b7_expected_s1_low", "rl_b7_expected_s1_high",
                    "rl_b7_expected_whole_log", "rl_b1_expected_log_as_linear", "rl_b2_expected_auc"):
            self.assertIn("written before the run", self.d["records"][key]["basis"], key)

    def test_the_headline_figures_match_their_sources(self):
        r = self.r
        res = load("research/benchmark/value-scale-test/results.json")
        for g, group in (("s1", "S1"), ("s23", "S2+S3")):
            for c, cls in (("linear", "linear"), ("log", "constructed_log")):
                row = res["by_calibrated_stratum"][group][cls]
                self.assertEqual(r[f"rl_b7_{g}_{c}_n"], row["n"])
                self.assertEqual(r[f"rl_b7_{g}_{c}_miss"], row["miss"])
                self.assertAlmostEqual(r[f"rl_b7_{g}_{c}_lower"], row["miss_lower"], places=6)
                self.assertEqual(r[f"rl_b7_{g}_{c}_lower"] > r["rl_alpha"], row["guarantee_contradicted"])
        self.assertEqual((r["rl_b7_s1_log_miss"], r["rl_b7_s1_log_n"]), (22, 237))
        self.assertEqual((r["rl_b7_detector_wrong"], r["rl_b7_median_wrong"], r["rl_b7_discordant"]), (1, 4, 3))
        self.assertEqual(r["rl_b7_p"], 0.125)
        self.assertEqual((r["rl_b7_whole_log_as_log"], r["rl_b7_whole_log_median"]), (215, 235))
        self.assertEqual((r["rl_b7_rows_pass"], r["rl_b7_rows"]), (6, 11))
        self.assertEqual((r["rl_b1_log_as_linear"], r["rl_b1_linear_as_log"]), (0.124, 0.22))
        self.assertEqual((r["rl_step1_linear"], r["rl_step1_linear_misread"]), (28, 6))
        self.assertEqual((r["rl_step1_log"], r["rl_step1_log_misread"]), (9, 0))
        self.assertEqual(r["rl_b2_auc"], 0.9923)
        self.assertEqual((r["rl_b5_rows_pass"], r["rl_b5_rows"]), (9, 10))
        self.assertEqual((r["rl_b6_rows_pass"], r["rl_b6_rows"]), (7, 7))
        self.assertEqual((r["rl_s1_k"], r["rl_s1_n"], r["rl_s23_k"], r["rl_s23_n"]), (6, 218, 1, 68))
        self.assertEqual((r["rl_ph_s1_log_miss"], r["rl_ph_s1_log_n"]), (20, 234))
        self.assertEqual((r["rl_ph_cal_below"], r["rl_ph_cal_scored"], r["rl_ph_test_below"], r["rl_ph_test_scored"]),
                         (5, 214, 20, 234))
        self.assertEqual((r["rl_ph_faulty"], r["rl_ph_empty"], r["rl_ph_mislabelled"]), (3, 2, 1))

    def test_the_corpus_funnel_adds_up(self):
        r = self.r
        self.assertEqual(r["rl_b3_frame"], load("valuescale/corpus/frame.json")["counts"]["frame"])
        self.assertEqual(r["rl_b3_reserve"], r["rl_b3_frame"] - r["rl_b3_listed"])
        self.assertEqual(r["rl_b3_calibration"] + r["rl_b3_test"], r["rl_b3_after_audit"])
        skips = load("research/notebook-outputs/value_scale_b3/report.json")["rows"]["B3_skips"]["found"]
        self.assertEqual(sum(skips.values()), r["rl_b3_listed"])
        self.assertEqual((r["rl_b3_frame"], r["rl_b3_listed"], r["rl_b3_reserve"]), (18813, 10000, 8813))
        self.assertEqual((r["rl_b3_kept"], r["rl_b3_after_audit"], r["rl_b3_calibration"], r["rl_b3_test"]),
                         (457, 455, 218, 237))

    def test_step_1_s_invariant_count_comes_from_the_rows_not_the_pass_field(self):
        # The report's pass_ field missed a NumPy False written as "False";
        # value_scale_step1/notes.md corrects 37 to 33.
        d3 = load("research/notebook-outputs/value_scale_step1/report.json")["D3"]
        self.assertEqual(sum(1 for t in d3 if t.get("pass_") is True), 37)
        self.assertEqual(self.r["rl_step1_d3_pass"], 33)
        self.assertEqual(self.r["rl_step1_tables"], 37)

    def test_b4_s_timings_are_the_committed_report_s(self):
        # The notes give 0.07 s and 74 s, from the run before the code review.
        self.assertEqual(self.r["rl_b4_detect_seconds"], 0.086)
        self.assertEqual(self.r["rl_b4_rehearsal_seconds"], 82)

    def test_the_code_s_constants_agree_where_they_are_written_twice(self):
        tree = ast.parse((bd.REPO / "valuescale/conformal.py").read_text(encoding="utf-8"))
        strata = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                      if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "STRATA" for t in n.targets))
        cal = load("valuescale/calibration/protein-v1.json")["strata"]
        self.assertEqual(cal[0]["columns"], list(strata["S1"]))
        self.assertEqual(cal[1]["columns"], [strata["S2"][0], strata["S3"][1]])
        r = self.r
        self.assertEqual((r["rl_s1_lo"], r["rl_s1_hi"], r["rl_s2_lo"], r["rl_s2_hi"], r["rl_s3_lo"], r["rl_s3_hi"]),
                         (20, 49, 50, 300, 301, 2000))
        baselines = (bd.REPO / "valuescale/baselines.py").read_text(encoding="utf-8")
        self.assertEqual(float(re.search(r"^MEDIAN_THRESHOLD = ([\d.]+)", baselines, re.M).group(1)),
                         r["rl_median_rule"])

    def test_fifty_nine_per_group_is_the_closed_form(self):
        # The smallest n whose smallest score already bounds the miss rate:
        # (1 - alpha)^n <= delta.
        alpha, delta = self.r["rl_alpha"], self.r["rl_delta"]
        closed = math.ceil(math.log(delta) / math.log(1 - alpha))
        self.assertEqual(self.r["rl_min_n"], closed)
        self.assertGreater((1 - alpha) ** (closed - 1), delta)
        self.assertEqual(self.r["rl_confidence"], round(1 - delta, 6))

    def test_every_step_names_its_records_and_dates(self):
        steps = self.d["steps"]
        self.assertEqual(list(steps), STEP_IDS)
        for sid, step in steps.items():
            for key in ("report", "expectations", "notes"):
                path = step.get(key)
                if path is not None:
                    self.assertTrue((bd.REPO / path).is_file(), f"{sid}: {path}")
                    self.assertIn(path, self.d["sources"], f"{sid}: {path}")
            self.assertTrue(step["dates"], sid)
            self.assertEqual(step["dates"], sorted(set(step["dates"])), sid)
            for date in step["dates"]:
                self.assertRegex(date, ISO)
            if step.get("run"):
                self.assertIn(step["run"], step["dates"], sid)
            if step.get("expected") and step.get("run"):
                self.assertLessEqual(step["expected"], step["run"], f"{sid}: expectations after the run")
        self.assertEqual(steps["b7"]["run"], "2026-11-09")
        self.assertEqual(steps["step1"]["expected"], "2026-10-28")

    def test_it_reads_no_numpy_and_imports_no_valuescale(self):
        tree = ast.parse((bd.REPO / "scripts/build_docs.py").read_text(encoding="utf-8"))
        names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(names & {"numpy", "pandas", "valuescale", "service"}, names)


if __name__ == "__main__":
    unittest.main()
