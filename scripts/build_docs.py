"""Builds web/data/docs.json, the Docs section's data (web/docs.html and one
page per topic, web/docs-<topic>.html).

Standard library only, deterministic. scripts/build_manifest.py calls
build() after it builds the manifest, the Workflow page's data and the
Manuscript page's data; `built_for` names the manifest's release, as the
other two data files do.

The Docs section tells, in plain words, what was done and how it works. Its
words are written by hand from the committed records; every number in them
is a record here, read from a committed output, so the pages type none.
Round 1 holds the raw-or-log detector's records (prefix "rl_"), read from
the valuescale/ step reports under research/notebook-outputs/, the sealed
test's results, the frozen calibration and the corpus frame. Code constants
are read with ast or a regular expression, never by importing the code
(valuescale imports numpy). A prediction that exists only as words in an
expectations file is quoted with a pattern that must match exactly once,
and its basis says it was written before the run.

`steps` lists, per step the "What we did" tab tells, the step's report,
expectations and notes, and every date they hold, so the page's tests can
check each date it shows.

Every record is {value, status, basis, format}, or pending with a note, so
web/js/docs-data.js shows it through manifest.js's isMeasured guard.

    python scripts/build_docs.py      # from the repository root (build_manifest.py also runs it)
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from build_manuscript import Records, dig
from build_workflow import REPO, rel, sha256

OUTPUT = REPO / "web" / "data" / "docs.json"
MANIFEST = REPO / "web" / "data" / "atlas_manifest.json"
SCHEMA_VERSION = "1"
SIZE_BUDGET = 60_000  # bytes; scripts/test_build_docs.py enforces it

NO = REPO / "research" / "notebook-outputs"
EXPECT = REPO / "valuescale" / "bank" / "expectations"
PLAN = REPO / "research" / "value-scale-plan.md"
PROTOCOL = REPO / "research" / "benchmark" / "protocol-value-scale.md"
PLAN_V2 = REPO / "research" / "value-scale-v2-plan.md"
CALIBRATION = REPO / "valuescale" / "calibration" / "protein-v1.json"
CONFORMAL = REPO / "valuescale" / "conformal.py"
CONFIG = REPO / "service" / "config.py"
FRAME = REPO / "valuescale" / "corpus" / "frame.json"
RESULTS = REPO / "research" / "benchmark" / "value-scale-test" / "results.json"
REHEARSAL = NO / "value_scale_b4" / "rehearsal.json"
POSTHOC = NO / "value_scale_b7" / "posthoc.json"
ISO = re.compile(r"(?<!\d)20\d\d-\d\d-\d\d(?!\d)")


def report(step: str) -> Path:
    return NO / f"value_scale_{step}" / "report.json"


def notes(step: str) -> Path:
    return NO / f"value_scale_{step}" / "notes.md"


# The steps the "What we did" tab tells, in order: (id, the folder and
# expectations name, the plan's status line it is told in).
STEPS = (
    ("step1", "step1", "Status:"),
    ("phase_a", "phaseA", "Status:"),
    ("phase_a2", "phaseA2", "Status:"),
    ("zscore", "zscore", "Status:"),
    ("b0", None, "- **B0,"),
    ("b1", "b1", "- **B1,"),
    ("b2", "b2", "- **B2,"),
    ("b3", "b3", "- **B3,"),
    ("b4", "b4", "- **B4,"),
    ("b5", "b5", "- **B5,"),
    ("b6", "b6", "- **B6,"),
    ("b7", "b7", "- **B7,"),
    ("decision", None, None),
    ("v2", None, None),
)


class DocsRecords(Records):
    """Records, plus the words of a file as a source, and predictions quoted
    from an expectations file."""

    def text(self, path: Path) -> str:
        if path not in self._cache:
            self._cache[path] = path.read_bytes().decode("utf-8")
            self.sources.add(path)
        return self._cache[path]

    def put(self, key: str, value, basis: str, fmt: str) -> None:
        assert key.startswith("rl_"), f"{key}: the raw-or-log topic's records start with rl_"
        assert not isinstance(value, bool), f"{key}: a pass flag is not a number"
        assert isinstance(value, (int, float)), f"{key}: {value!r} is not a number"
        super().put(key, value, basis, fmt)

    def quoted(self, key: str, path: Path, keys: tuple, pattern: str, fmt: str, scale: float = 1.0) -> None:
        """A number an expectations file states in words, written before the run."""
        words = dig(self.json(path), keys)
        found = re.findall(pattern, words)
        assert len(found) == 1, f"{rel(path)}: {pattern!r} matches {len(found)} times in {' > '.join(keys)}"
        value = float(found[0]) * scale
        value = int(value) if fmt == "count" else round(value, 6)
        self.put(key, value, f"{rel(path)}: {' > '.join(keys)}, written before the run", fmt)


def count_passed(rows: dict) -> tuple[int, int]:
    """Rows passed and rows judged: a row with no verdict (None) is reported, not judged."""
    verdicts = [row["pass"] if isinstance(row, dict) else row for row in rows.values()]
    judged = [v for v in verdicts if v is not None]
    return sum(1 for v in judged if v is True), len(judged)


# ---- the rules and the calibration ----

def constants(r: DocsRecords) -> None:
    config = r.text(CONFIG)
    rule = re.findall(r"^LINEAR_SCALE_MEDIAN_THRESHOLD = ([\d.]+)", config, re.M)
    assert len(rule) == 1
    r.put("rl_median_rule", int(float(rule[0])), f"{rel(CONFIG)}: LINEAR_SCALE_MEDIAN_THRESHOLD", "count")

    cal = r.json(CALIBRATION)
    r.at("rl_alpha", CALIBRATION, ("alpha",), "percent")
    r.at("rl_delta", CALIBRATION, ("delta",), "percent")
    r.put("rl_confidence", round(1 - cal["delta"], 6), f"{rel(CALIBRATION)}: 1 - delta", "percent")

    umbrella = dig(r.json(report("b2")), ("rows", "B2_conformal", "umbrella_k"))
    smallest = min(int(n) for n, k in umbrella.items() if k is not None)
    assert umbrella[str(smallest - 1)] is None, "the run's record must show the size below it has no k"
    r.put("rl_min_n", smallest, f"{rel(report('b2'))}: rows > B2_conformal > umbrella_k, the smallest n with a k", "count")

    tree = ast.parse(r.text(CONFORMAL))
    strata = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                  if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "STRATA" for t in n.targets))
    for name in ("S1", "S2", "S3"):
        lo, hi = strata[name]
        r.put(f"rl_{name.lower()}_lo", lo, f"{rel(CONFORMAL)}: STRATA {name}", "count")
        r.put(f"rl_{name.lower()}_hi", hi, f"{rel(CONFORMAL)}: STRATA {name}", "count")

    for i, (g, name) in enumerate((("s1", "S1"), ("s23", "S2+S3"))):
        stratum = cal["strata"][i]
        assert stratum["name"] == name
        assert stratum["n"]["linear"] == stratum["n"]["log"] and stratum["k"]["linear"] == stratum["k"]["log"]
        r.at(f"rl_{g}_n", CALIBRATION, ("strata", i, "n", "linear"), "count")
        r.at(f"rl_{g}_k", CALIBRATION, ("strata", i, "k", "linear"), "count")
        r.at(f"rl_{g}_linear_cut", CALIBRATION, ("strata", i, "thresholds", "linear"), "fixed3")
        r.at(f"rl_{g}_log_cut", CALIBRATION, ("strata", i, "thresholds", "log"), "fixed3")


# ---- Step 1, Phase A, Phase A2, the z-score ----

def step1(r: DocsRecords) -> None:
    path = report("step1")
    rep = r.json(path)
    base = rel(path)
    r.put("rl_step1_tables", len(rep["D1"]), f"{base}: D1, one row per bank table", "count")
    originals = [row for row in rep["D2"] if row["variant"] == "original"]
    for label in ("linear", "log"):
        rows = [row for row in originals if row["label"] == label]
        r.put(f"rl_step1_{label}", len(rows), f"{base}: D2, the {label} tables as deposited", "count")
        r.put(f"rl_step1_{label}_misread", sum(1 for row in rows if row["right"] is False),
              f"{base}: D2, the {label} tables as deposited that the old rule misread", "count")
    # A table passes D3 when it is refused as expected, or when none of its
    # invariants failed. The report's own pass_ field missed a NumPy False
    # written as "False" (value_scale_step1/notes.md corrects 37 to 33).
    def held(row):
        return row["refused"] or not any(v is False or v == "False" for v in row["invariants"].values())
    r.put("rl_step1_d3_pass", sum(1 for row in rep["D3"] if held(row)),
          f"{base}: D3, tables refused or with no invariant false (not the pass_ field)", "count")
    median = next(row["median_nonzero"] for row in rep["D1"] if row["id"] == "pxd064083_t")
    r.put("rl_pxd064083_median", median, f"{base}: D1 pxd064083_t > median_nonzero", "integer")


def phase_a(r: DocsRecords) -> None:
    path = report("phaseA")
    rep = r.json(path)
    base = rel(path)
    traced = [t for t in rep["tables"] if not t["refused"]]
    r.put("rl_pa_traced", len(traced), f"{base}: tables traced (not refused)", "count")
    r.put("rl_pa_same", sum(1 for t in traced if all(v for k, v in t["checks"].items() if k.startswith("A1"))),
          f"{base}: tables whose automatic reply equals the baseline (every A1 check)", "count")
    r.put("rl_pa_app", len(rep["app"]), f"{base}: app checks", "count")
    r.put("rl_pa_app_pass", sum(1 for a in rep["app"] if a["pass"] is True), f"{base}: app checks passed", "count")

    path = report("phaseA2")
    rep = r.json(path)
    base = rel(path)
    fl = next(t for t in rep["tables"] if t["id"] == "furtwangler_log2")
    r.put("rl_pa2_fl_zero_share", fl["zero_share"], f"{base}: furtwangler_log2 > zero_share", "pct1")
    r.put("rl_pa2_fl_cells", fl["cells"], f"{base}: furtwangler_log2 > cells", "count")
    r.put("rl_pa2_fl_measured", fl["answered"]["zeros measured"], f"{base}: furtwangler_log2 > answered", "count")
    r.put("rl_pa2_fl_missing", fl["answered"]["zeros missing"], f"{base}: furtwangler_log2 > answered", "count")

    path = report("zscore")
    rep = r.json(path)
    base = rel(path)
    traced = [t for t in rep["tables"] if not t["refused"]]
    r.put("rl_z_traced", len(traced), f"{base}: tables traced (not refused)", "count")
    r.put("rl_z_same", sum(1 for t in traced if t["answers_changed"] == 0),
          f"{base}: tables with no answer changed", "count")
    r.put("rl_z_largest_move", max(t["largest_coordinate_change"] for t in traced),
          f"{base}: the largest largest_coordinate_change", "fixed3")


# ---- B1 to B6 ----

def b1_to_b6(r: DocsRecords) -> None:
    base = rel(report("b1"))
    r.at("rl_b1_log_as_linear", report("b1"), ("rows", "B1_direction", "median_log_read_linear"), "pct1")
    r.at("rl_b1_linear_as_log", report("b1"), ("rows", "B1_direction", "median_linear_read_as_log"), "pct1")
    r.at("rl_b1_n_log", report("b1"), ("rows", "B1_direction", "n_log"), "count")
    r.at("rl_b1_n_linear", report("b1"), ("rows", "B1_direction", "n_linear"), "count")
    passed, judged = count_passed(r.json(report("b1"))["rows"])
    r.put("rl_b1_rows_pass", passed, f"{base}: rows passed", "count")
    r.put("rl_b1_rows", judged, f"{base}: rows judged", "count")
    r.quoted("rl_b1_expected_log_as_linear", EXPECT / "b1.json", ("rows", "B1_log_read_linear_small"),
             r"is at most (0\.\d+)", "pct1")

    base = rel(report("b2"))
    r.at("rl_b2_auc", report("b2"), ("rows", "B2_separation", "auc"), "fixed3")
    r.at("rl_b2_linear_rows", report("b2"), ("rows", "B2_design_size", "linear_rows"), "count")
    r.at("rl_b2_log_rows", report("b2"), ("rows", "B2_design_size", "log_rows"), "count")
    r.at("rl_b2_deposits", report("b2"), ("rows", "B2_design_size", "deposits"), "count")
    r.at("rl_b2_variants", report("b2"), ("rows", "B2_verdicts_variants", "labelled"), "count")
    r.at("rl_b2_variants_wrong", report("b2"), ("rows", "B2_verdicts_variants", "wrong"), "count")
    passed, judged = count_passed(r.json(report("b2"))["rows"])
    r.put("rl_b2_rows_pass", passed, f"{base}: rows passed", "count")
    r.put("rl_b2_rows", judged, f"{base}: rows judged (the design size is reported, not judged)", "count")
    r.quoted("rl_b2_expected_auc", EXPECT / "b2.json", ("rows", "B2_separation"), r"at least (0\.\d+)", "fixed2")

    path = report("b3")
    rep = r.json(path)
    base = rel(path)
    frame = r.json(FRAME)["counts"]
    found = rep["rows"]["B3_frame"]["found"]
    assert found["frame"] == frame["frame"], "the report and the frame disagree"
    r.at("rl_b3_index", FRAME, ("counts", "index_records"), "count")
    r.at("rl_b3_frame", FRAME, ("counts", "frame"), "count")
    r.at("rl_b3_listed", path, ("listed",), "count")
    skips = rep["rows"]["B3_skips"]["found"]
    assert sum(skips.values()) == rep["listed"] == rep["rows"]["B3_stop"]["found"]
    r.put("rl_b3_reserve", frame["frame"] - rep["listed"], f"{rel(FRAME)}: counts > frame, less {base}: listed", "count")
    r.at("rl_b3_no_candidate", path, ("rows", "B3_skips", "found", "no candidate"), "count")
    r.at("rl_b3_kept", path, ("kept",), "count")
    r.at("rl_b3_after_audit", path, ("after_audit",), "count")
    r.at("rl_b3_calibration", path, ("quotas", "calibration", "S1"), "count")
    r.at("rl_b3_test", path, ("quotas", "test", "S1"), "count")
    assert rep["quotas"]["calibration"]["S1"] + rep["quotas"]["test"]["S1"] == rep["after_audit"]
    r.at("rl_b3_audit_agree", path, ("rows", "B3_audit", "found", "agree"), "count")
    r.at("rl_b3_audit_judged", path, ("rows", "B3_audit", "found", "judged"), "count")
    passed, judged = count_passed(rep["rows"])
    r.put("rl_b3_rows_pass", passed, f"{base}: rows passed", "count")
    r.put("rl_b3_rows", judged, f"{base}: rows judged", "count")

    path = report("b4")
    base = rel(path)
    passed, judged = count_passed(r.json(path)["rows"])
    r.put("rl_b4_rows_pass", passed, f"{base}: rows passed", "count")
    r.put("rl_b4_rows", judged, f"{base}: rows judged", "count")
    r.at("rl_b4_detect_seconds", path, ("rows", "B4_detect", "seconds"), "plain")
    r.at("rl_b4_rehearsal_seconds", path, ("rows", "B4_rehearsal", "seconds"), "count")
    r.at("rl_b4_reh_tables", REHEARSAL, ("primary", "tables"), "count")
    r.at("rl_b4_reh_detector_wrong", REHEARSAL, ("primary", "detector_wrong"), "count")
    r.at("rl_b4_reh_median_wrong", REHEARSAL, ("primary", "median_50_wrong"), "count")
    r.at("rl_b4_reh_whole_log", REHEARSAL, ("detector_on_whole_tables", "constructed_log", "log"), "count")

    path = report("b5")
    base = rel(path)
    passed, judged = count_passed(r.json(path)["results"])
    r.put("rl_b5_rows_pass", passed, f"{base}: results passed", "count")
    r.put("rl_b5_rows", judged, f"{base}: results judged", "count")
    r.at("rl_b5_slowest_seconds", path, ("slowest_detect", "seconds"), "plain")

    path = report("b6")
    base = rel(path)
    passed, judged = count_passed(r.json(path)["results"])
    r.put("rl_b6_rows_pass", passed, f"{base}: results passed", "count")
    r.put("rl_b6_rows", judged, f"{base}: results judged", "count")


# ---- B7, the sealed test, and what was found after it ----

def b7(r: DocsRecords) -> None:
    res = r.json(RESULTS)
    base = rel(RESULTS)
    alpha = r.json(CALIBRATION)["alpha"]
    r.at("rl_b7_deposits", RESULTS, ("deposits",), "count")
    r.at("rl_b7_subsamples", RESULTS, ("subsamples",), "count")
    for g, group in (("s1", "S1"), ("s23", "S2+S3")):
        for c, cls in (("linear", "linear"), ("log", "constructed_log")):
            keys = ("by_calibrated_stratum", group, cls)
            row = dig(res, keys)
            assert (row["miss_lower"] > alpha) == row["guarantee_contradicted"]
            r.at(f"rl_b7_{g}_{c}_n", RESULTS, keys + ("n",), "count")
            r.at(f"rl_b7_{g}_{c}_miss", RESULTS, keys + ("miss",), "count")
            r.put(f"rl_b7_{g}_{c}_rate", round(row["miss"] / row["n"], 6), f"{base}: {' > '.join(keys)}, miss / n", "pct1")
            r.at(f"rl_b7_{g}_{c}_lower", RESULTS, keys + ("miss_lower",), "pct1")
    r.at("rl_b7_pooled_log_miss", RESULTS, ("all_subsamples", "constructed_log", "miss"), "count")
    r.at("rl_b7_pooled_log_n", RESULTS, ("all_subsamples", "constructed_log", "n"), "count")
    r.at("rl_b7_pooled_log_lower", RESULTS, ("all_subsamples", "constructed_log", "miss_lower"), "pct1")
    primary = res["primary"]
    r.at("rl_b7_tables", RESULTS, ("primary", "tables"), "count")
    r.at("rl_b7_detector_wrong", RESULTS, ("primary", "detector_wrong"), "count")
    r.at("rl_b7_median_wrong", RESULTS, ("primary", "median_50_wrong"), "count")
    r.put("rl_b7_discordant", primary["detector_only_right"] + primary["median_50_only_right"],
          f"{base}: primary, the tables only one reading gets right", "count")
    r.at("rl_b7_p", RESULTS, ("primary", "p_value"), "fixed3")
    r.at("rl_b7_whole_linear_as_linear", RESULTS, ("detector_on_whole_tables", "linear", "linear"), "count")
    r.at("rl_b7_whole_log_as_log", RESULTS, ("detector_on_whole_tables", "constructed_log", "log"), "count")
    r.at("rl_b7_whole_log_as_linear", RESULTS, ("detector_on_whole_tables", "constructed_log", "linear"), "count")
    median_log = sum(1 for t in res["tables"] if t["log_baselines"]["median_50"] == "log")
    assert median_log == r.json(POSTHOC)["primary_as_scored"]["whole_constructed_log_read_log_median_50"]
    r.put("rl_b7_whole_log_median", median_log, f"{base}: tables whose constructed log median-50 reads log", "count")
    r.at("rl_b7_coverage_half", RESULTS, ("risk_coverage", "0.5", "coverage"), "pct1")
    path = report("b7")
    passed, judged = count_passed(r.json(path)["results"])
    r.put("rl_b7_rows_pass", passed, f"{rel(path)}: results passed", "count")
    r.put("rl_b7_rows", judged, f"{rel(path)}: results judged", "count")
    r.at("rl_b7_seconds", path, ("seconds",), "count")

    b7x = EXPECT / "b7.json"
    r.quoted("rl_b7_expected_contradict_s1", b7x, ("B7_guarantee", "what_contradicts"), r"(\d+) or more misses of \d+ in S1", "count")
    r.quoted("rl_b7_expected_s1_low", b7x, ("B7_guarantee", "expected_misses"), r"S1 (\d+) to \d+ misses", "count")
    r.quoted("rl_b7_expected_s1_high", b7x, ("B7_guarantee", "expected_misses"), r"S1 \d+ to (\d+) misses", "count")
    r.quoted("rl_b7_expected_whole_log", b7x, ("B7_whole_log",), r"reads (\d+)% or more", "percent", scale=0.01)

    ph = r.json(POSTHOC)
    base = rel(POSTHOC)
    faulty = ph["faulty_tables"]
    r.put("rl_ph_faulty", len(faulty), f"{base}: faulty_tables", "count")
    r.put("rl_ph_empty", sum(1 for t in faulty if t["fault"] == "empty"), f"{base}: faulty_tables, empty", "count")
    r.put("rl_ph_mislabelled", sum(1 for t in faulty if t["fault"] != "empty"), f"{base}: faulty_tables, log values labelled linear", "count")
    aside = ("guarantee_faulty_set_aside",)
    r.at("rl_ph_s1_log_miss", POSTHOC, aside + ("S1 constructed_log", "miss"), "count")
    r.at("rl_ph_s1_log_n", POSTHOC, aside + ("S1 constructed_log", "n"), "count")
    r.at("rl_ph_s1_log_lower", POSTHOC, aside + ("S1 constructed_log", "lower"), "pct1")
    r.at("rl_ph_s1_linear_miss", POSTHOC, aside + ("S1 linear", "miss"), "count")
    r.at("rl_ph_s1_linear_n", POSTHOC, aside + ("S1 linear", "n"), "count")
    r.at("rl_ph_detector_wrong", POSTHOC, ("primary_faulty_set_aside", "detector_wrong"), "count")
    r.at("rl_ph_median_wrong", POSTHOC, ("primary_faulty_set_aside", "median_50_wrong"), "count")
    r.at("rl_ph_p", POSTHOC, ("primary_faulty_set_aside", "p_value"), "fixed3")
    tail = ph["tail"]
    for split, short in (("calibration", "cal"), ("test", "test")):
        r.at(f"rl_ph_{short}_below", POSTHOC, ("tail", split, "below"), "count")
        r.at(f"rl_ph_{short}_scored", POSTHOC, ("tail", split, "scored"), "count")
        r.at(f"rl_ph_spearman_{short}", POSTHOC, ("tail", split, "spearman_missing"), "fixed2")
    bands = tail["calibration"]["bands"]
    assert [b["band"] for b in bands] == [b["band"] for b in tail["test"]["bands"]]
    r.put("rl_ph_bands", len(bands), f"{base}: tail > calibration > bands", "count")
    for i, band in enumerate(bands):
        r.at(f"rl_ph_band{i}_lo", POSTHOC, ("tail", "calibration", "bands", i, "band", 0), "percent")
        r.at(f"rl_ph_band{i}_hi", POSTHOC, ("tail", "calibration", "bands", i, "band", 1), "percent")
        for split, short in (("calibration", "cal"), ("test", "test")):
            r.at(f"rl_ph_band{i}_{short}_tables", POSTHOC, ("tail", split, "bands", i, "tables"), "count")
            r.at(f"rl_ph_band{i}_{short}_below", POSTHOC, ("tail", split, "bands", i, "below"), "count")
    for side in ("clean-up", "rest"):
        key = "cleanup" if side == "clean-up" else "rest"
        r.at(f"rl_ph_{key}_test_miss", POSTHOC, ("cleanup", "test", side, "miss"), "count")
        r.at(f"rl_ph_{key}_test_n", POSTHOC, ("cleanup", "test", side, "n"), "count")
    same = ph["rehearsal_scores_equal_calibration"]
    assert same[0] == same[1]
    r.put("rl_ph_rehearsal_same", same[0], f"{base}: rehearsal_scores_equal_calibration", "count")

    r.text(PLAN_V2)
    r.wait("rl_v2_test", "Protein v2, R7",
           f"the fresh sealed test is scored once, after R1 to R6 ({rel(PLAN_V2)})")


# ---- the steps, and the dates each one's records hold ----

def status_line(plan: str, prefix: str) -> str:
    lines = [line for line in plan.splitlines() if line.startswith(prefix)]
    assert len(lines) == 1, f"{rel(PLAN)}: {len(lines)} lines start {prefix!r}"
    return lines[0]


def steps(r: DocsRecords) -> dict:
    plan = r.text(PLAN)
    out = {}
    for sid, name, prefix in STEPS:
        step = {"report": None, "expectations": None, "notes": None}
        found: set[str] = set()
        if name is not None:
            path = report(name)
            rep = r.json(path)
            step["report"] = rel(path)
            if "run" in rep:
                step["run"] = ISO.search(rep["run"]).group(0)
                found.add(step["run"])
            x = EXPECT / f"{name}.json"
            step["expectations"] = rel(x)
            step["expected"] = ISO.search(r.json(x)["written"]).group(0)
            found.add(step["expected"])
            n = notes(name)
            step["notes"] = rel(n)
            found |= set(ISO.findall(r.text(n)))
        elif sid == "b0":
            step["notes"] = rel(PROTOCOL)
            words = r.text(PROTOCOL)
            step["expected"] = re.search(r"written on (20\d\d-\d\d-\d\d)", words).group(1)
            found |= set(ISO.findall(words))
        elif sid == "decision":
            n = notes("b7")
            step["notes"] = rel(n)
            words = r.text(n)
            section = words[words.index("## The owner's decision"):]
            found |= set(ISO.findall(section))
        elif sid == "v2":
            step["notes"] = rel(PLAN_V2)
            found |= set(ISO.findall(r.text(PLAN_V2)))
        if prefix is not None:
            found |= set(ISO.findall(status_line(plan, prefix)))
        step["dates"] = sorted(found)
        out[sid] = step
    return out


def build(manifest: dict | None = None) -> dict:
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text(encoding="utf-8"))
    r = DocsRecords()
    constants(r)
    step1(r)
    phase_a(r)
    b1_to_b6(r)
    b7(r)
    told = steps(r)
    return {
        "schema_version": SCHEMA_VERSION,
        "built_for": {"atlas_version": manifest["atlas_version"], "model_name": manifest["model"]["name"]},
        "sources": {rel(p): sha256(p) for p in sorted(r.sources, key=rel)},
        "records": dict(sorted(r.records.items())),
        "steps": told,
    }


def write(docs: dict) -> int:
    data = (json.dumps(docs, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    OUTPUT.write_bytes(data)
    return len(data)


def main() -> None:
    size = write(build())
    print(f"Wrote {rel(OUTPUT)} ({size:,} bytes)")


if __name__ == "__main__":
    main()
