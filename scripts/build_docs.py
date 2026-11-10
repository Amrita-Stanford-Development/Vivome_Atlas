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
import math
import re
from pathlib import Path

from build_manuscript import Records, dig
from build_workflow import REPO, rel, sha256

OUTPUT = REPO / "web" / "data" / "docs.json"
MANIFEST = REPO / "web" / "data" / "atlas_manifest.json"
SCHEMA_VERSION = "1"
SIZE_BUDGET = 80_000  # bytes; scripts/test_build_docs.py enforces it

NO = REPO / "research" / "notebook-outputs"
EXPECT = REPO / "valuescale" / "bank" / "expectations"
PLAN = REPO / "research" / "value-scale-plan.md"
PROTOCOL = REPO / "research" / "benchmark" / "protocol-value-scale.md"
PLAN_V2 = REPO / "research" / "value-scale-v2-plan.md"
CALIBRATION = REPO / "valuescale" / "calibration" / "protein-v1.json"
CONFORMAL = REPO / "valuescale" / "conformal.py"
CONFIG = REPO / "service" / "config.py"
GATES = REPO / "valuescale" / "gates.py"
VALIDATION = REPO / "service" / "pipeline" / "validation.py"
FRAME = REPO / "valuescale" / "corpus" / "frame.json"
RESULTS = REPO / "research" / "benchmark" / "value-scale-test" / "results.json"
REHEARSAL = NO / "value_scale_b4" / "rehearsal.json"
POSTHOC = NO / "value_scale_b7" / "posthoc.json"
# The example protein table: the Atlas page's example, the bank's pbmc240_diann.
EXAMPLE = REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv"
ISO = re.compile(r"(?<!\d)20\d\d-\d\d-\d\d(?!\d)")


def report(step: str) -> Path:
    return NO / f"value_scale_{step}" / "report.json"


def notes(step: str) -> Path:
    return NO / f"value_scale_{step}" / "notes.md"


# The steps the "What we did" tab tells, in order: (id, the folder and
# expectations name, the plan's status line it is told in: protein v2's
# plan for the R steps, the first plan's for the rest).
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
    ("r1", "r1", "- **R1,"),
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
        assert len(found) == 1, f"{rel(path)}: {pattern!r} matches {len(found)} times in {' > '.join(map(str, keys))}"
        value = float(found[0]) * scale
        value = int(value) if fmt == "count" else round(value, 6)
        self.put(key, value, f"{rel(path)}: {' > '.join(map(str, keys))}, written before the run", fmt)


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

    def constant(path, name):
        found = re.findall(rf"^{name} = ([\d.]+)", r.text(path), re.M)
        assert len(found) == 1, f"{rel(path)}: {name}"
        return float(found[0])
    r.put("rl_gate_negative_share", constant(GATES, "NEGATIVE_SHARE"), f"{rel(GATES)}: NEGATIVE_SHARE", "percent")
    r.put("rl_gate_counts", int(constant(GATES, "MIN_DISTINCT_COUNTS")), f"{rel(GATES)}: MIN_DISTINCT_COUNTS", "count")
    r.put("rl_service_min_cells", int(constant(VALIDATION, "MIN_CELLS_REFUSE")), f"{rel(VALIDATION)}: MIN_CELLS_REFUSE", "count")

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
    worst = max(traced, key=lambda t: t["answers_changed"])
    assert sum(1 for t in traced if t["answers_changed"]) == 1, "one table changed answers"
    r.put("rl_z_worst_changed", worst["answers_changed"], f"{base}: {worst['id']} > answers_changed", "count")
    r.put("rl_z_worst_cells", worst["cells"], f"{base}: {worst['id']} > cells", "count")
    x = EXPECT / "zscore.json"
    r.quoted("rl_z_expected_move", x, ("Z3_replies_against_the_baseline", "predicted", 2), r"less than (0\.\d+)", "plain")
    bound = r.records["rl_z_expected_move"]["value"]
    r.put("rl_z_moved_tables", sum(1 for t in traced if t["largest_coordinate_change"] > bound),
          f"{base}: tables whose largest_coordinate_change is above the predicted bound", "count")


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
    r.at("rl_b3_too_few_columns", path, ("rows", "B3_skips", "found", "too few columns"), "count")
    other = {k: v for k, v in skips.items() if k not in ("kept", "no candidate", "too few columns")}
    r.put("rl_b3_other_skips", sum(other.values()),
          f"{base}: rows > B3_skips > found, {', '.join(sorted(other))}", "count")
    for tool, key in (("MaxQuant", "maxquant"), ("DIA-NN", "diann"), ("Spectronaut", "spectronaut"),
                      ("FragPipe", "fragpipe"), ("Proteome Discoverer", "pd")):
        r.at(f"rl_b3_sw_{key}", path, ("rows", "B3_software", "found", tool), "count")
    assert sum(rep["rows"]["B3_software"]["found"].values()) == rep["after_audit"], "the tables after the audit"
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
    r.at("rl_b7_risk_half", RESULTS, ("risk_coverage", "0.5", "risk"), "pct2")
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
    for split, short in (("calibration", "cal"), ("test", "test")):
        sparse = sum(b["tables"] for b in tail[split]["bands"] if b["band"][0] >= 0.5)
        r.put(f"rl_ph_{short}_sparse", sparse,
              f"{base}: tail > {split} > bands, the tables of the bands from 0.5 up (half or more of their values missing)", "count")
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


def r1(r: DocsRecords) -> None:
    """Protein v2, R1: the corpus checks on B3's kept tables and the bank."""
    path = report("r1")
    rep = r.json(path)
    base = rel(path)
    corpus, bank = rep["corpus"], rep["bank"]
    r.at("rl_r1_kept", path, ("corpus", "kept"), "count")
    r.put("rl_r1_empty", len(corpus["empty"]), f"{base}: corpus > empty", "count")
    r.put("rl_r1_flagged", len(corpus["flagged"]), f"{base}: corpus > flagged", "count")
    r.at("rl_r1_ceiling", path, ("log_ceiling",), "count")
    for key in ("min", "median", "max"):
        r.at(f"rl_r1_flag_{key}", path, ("corpus", "flagged", "PXD066316", key), "fixed2")
    r.put("rl_r1_bank", len(bank), f"{base}: bank", "count")
    for label, short in (("log", "log"), ("linear", "linear")):
        tables = [b for b in bank if b["label"] == label]
        r.put(f"rl_r1_bank_{short}", len(tables), f"{base}: bank, labelled {label}", "count")
        r.put(f"rl_r1_bank_{short}_fired", sum(1 for b in tables if b["looks_log"]),
              f"{base}: bank, labelled {label}, the flag's rule fires", "count")
    judged = [v for v in rep["results"].values() if isinstance(v, bool)]  # R1_bank_linear is recorded, not judged
    r.put("rl_r1_rows_pass", sum(judged), f"{base}: results passed", "count")
    r.put("rl_r1_rows", len(judged), f"{base}: results judged (R1_bank_linear is recorded only)", "count")


# ---- the series the data figures draw ----
#
# A figure that shows many values (a table's spread of values, the lowest
# scores) draws them from a series: the values, worked out here from a
# committed file, with its basis. The words around a figure, and every number
# a figure writes, stay records; an axis's labels are part of its series.

GROUPED = "{:,}"


def number_words(value: float) -> str:
    """An axis label: a whole number with thousands grouped, or millions and billions in words."""
    for size, word in ((10**9, "billion"), (10**6, "million")):
        if value >= size:
            return f"{GROUPED.format(round(value / size))} {word}"
    return GROUPED.format(round(value))


def bank_medians(r: DocsRecords) -> dict:
    """Each bank table's median measured value, its kind, and how the old rule read it (Step 1)."""
    path = report("step1")
    rep = r.json(path)
    recorded = {t["id"]: t["detected"] for t in rep["D2"] if t["variant"] == "original"}
    rule = r.records["rl_median_rule"]["value"]
    rows = []
    for t in rep["D1"]:
        label = "raw" if t["label"] == "linear" else "log"
        negatives = t["negative_share"] > 0
        median = round(t["median_nonzero"], 4)
        reads = "log" if negatives or median <= rule else "raw"
        assert reads == ("raw" if recorded[t["id"]] == "linear" else "log"), f"{t['id']}: the rule as drawn"
        rows.append({"id": t["id"], "label": label, "negatives": negatives, "median": median,
                     "misread": reads != label})
    rows.sort(key=lambda row: (row["label"] != "raw", row["negatives"], row["median"]))
    shown = [row["median"] for row in rows if not row["negatives"]]
    lo, hi = math.floor(math.log10(min(shown))), math.ceil(math.log10(max(shown)))
    return {
        "basis": f"{rel(path)}: D1 median_nonzero and negative_share, D2 the original tables' reading",
        "lo_exp": lo, "hi_exp": hi,
        "ticks": [{"value": 10**e, "label": number_words(10**e)} for e in range(lo, hi + 1, 2)],
        "rows": rows,
    }


def example_table(r: DocsRecords) -> tuple[dict, dict]:
    """The example protein table (PBMC240, in the bank as pbmc240_diann): every
    measured value, raw and as log2, and each protein's spread against its level."""
    text = r.text(EXAMPLE)
    lines = text.splitlines()
    header = lines[0].split("\t")
    first = header.index("N.Proteotypic.Sequences") + 1
    cells = len(header) - first
    proteins = []
    for line in lines[1:]:
        fields = line.split("\t")[first:]
        assert len(fields) == cells, "every row has a value or a blank for every cell"
        values = [float(x) for x in fields if x.strip()]
        assert all(v > 0 for v in values), "the example holds no 0 and no negative"
        proteins.append(values)
    values = sorted(v for p in proteins for v in p)
    n = len(values)
    base = f"{rel(EXAMPLE)}: every measured value (a blank is not measured)"
    r.put("rl_ex_cells", cells, f"{rel(EXAMPLE)}: the columns after N.Proteotypic.Sequences", "count")
    r.put("rl_ex_proteins", len(proteins), f"{rel(EXAMPLE)}: rows", "count")
    r.put("rl_ex_values", n, base, "count")
    median = (values[(n - 1) // 2] + values[n // 2]) / 2
    r.put("rl_ex_median", round(median), f"{base}, the median", "count")
    r.put("rl_ex_max", round(values[-1]), f"{base}, the largest", "count")
    r.put("rl_ex_log2_median", round(math.log2(median), 6), f"{base}, log2 of the median", "fixed2")

    # Raw: equal steps up to a round number above the 99th percentile; the
    # few larger values are counted, not drawn.
    q99 = values[int(0.99 * n)]
    step = 10 ** math.floor(math.log10(q99))
    top = math.ceil(q99 / step) * step
    width = top / 25
    raw_edges = [round(i * width, 6) for i in range(26)]
    raw_counts = [0] * 25
    beyond = 0
    for v in values:
        if v > top:
            beyond += 1
        else:
            raw_counts[min(int(v // width), 24)] += 1
    r.put("rl_ex_beyond", beyond, f"{base}, above the raw histogram's right edge", "count")
    # Log2: steps of a half, a doubling every two steps.
    logs = [math.log2(v) for v in values]
    lo, hi = math.floor(min(logs)), math.ceil(max(logs))
    log_edges = [lo + i / 2 for i in range((hi - lo) * 2 + 1)]
    log_counts = [0] * (len(log_edges) - 1)
    for x in logs:
        log_counts[min(int((x - lo) * 2), len(log_counts) - 1)] += 1
    first_tick = math.ceil(lo / 4) * 4
    hist = {
        "basis": base,
        "raw": {"edges": raw_edges, "counts": raw_counts,
                "ticks": [{"value": t, "label": number_words(t)} for t in range(0, int(top) + 1, int(step))]},
        "log2": {"edges": log_edges, "counts": log_counts,
                 "ticks": [{"value": t, "label": str(t)} for t in range(first_tick, hi + 1, 4)]},
    }

    # Spread against level: the proteins measured in at least a tenth of the
    # cells, in ten groups of equal size from the quietest to the busiest
    # (by their raw mean); each group's typical spread (the median of its
    # proteins' standard deviations), raw and in log2, as a multiple of the
    # quietest group's.
    def sd(xs):
        m = sum(xs) / len(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

    def median_of(xs):
        xs = sorted(xs)
        return (xs[(len(xs) - 1) // 2] + xs[len(xs) // 2]) / 2

    kept = sorted((p for p in proteins if len(p) >= cells / 10), key=lambda p: sum(p) / len(p))
    groups = 10
    size = len(kept) // groups
    raw_sd, log_sd = [], []
    for g in range(groups):
        members = kept[g * size:(g + 1) * size] if g < groups - 1 else kept[g * size:]
        raw_sd.append(median_of([sd(p) for p in members]))
        log_sd.append(median_of([sd([math.log2(v) for v in p]) for p in members]))
    raw_ratio = [round(x / raw_sd[0], 4) for x in raw_sd]
    log_ratio = [round(x / log_sd[0], 4) for x in log_sd]
    r.put("rl_ex_spread_proteins", len(kept), f"{rel(EXAMPLE)}: the proteins measured in at least a tenth of the cells", "count")
    r.put("rl_ex_spread_groups", groups, f"{rel(EXAMPLE)}: those proteins in groups of equal size by their raw mean", "count")
    r.put("rl_ex_spread_raw", round(raw_ratio[-1]), f"{rel(EXAMPLE)}: the busiest group's typical raw spread, against the quietest's", "count")
    r.put("rl_ex_spread_log", round(log_ratio[-1], 2), f"{rel(EXAMPLE)}: the same, in log2", "fixed2")
    top_ratio = 10 ** math.ceil(math.log10(raw_ratio[-1]))
    spread = {
        "basis": f"{rel(EXAMPLE)}: each protein measured in at least a tenth of the cells, its standard deviation raw and in log2",
        "raw": raw_ratio, "log": log_ratio,
        "ticks": [{"value": 10**e, "label": f"{number_words(10**e)}×"} for e in range(0, round(math.log10(top_ratio)) + 1)],
    }
    return hist, spread


def s1_log_scores(r: DocsRecords) -> dict:
    """The lowest log probabilities of S1's constructed logs: calibration (the
    rehearsal, which gives back the calibration's scores) and the sealed test."""
    def scores(path):
        rows = [row for row in r.json(path)["rows"] if row["stratum"] == "S1" and row["class"] == "constructed_log"]
        scored = sorted(row["probabilities"]["log"] for row in rows if row["probabilities"])
        return rows, scored
    _, cal = scores(REHEARSAL)
    test_rows, test = scores(RESULTS)
    s1 = r.json(CALIBRATION)["strata"][0]
    assert s1["name"] == "S1"
    threshold, k = s1["thresholds"]["log"], s1["k"]["log"]
    assert cal[k - 1] == threshold, "the threshold is the k-th smallest calibration score"
    below = sum(x < threshold for x in test)
    unscored = sum(1 for row in test_rows if not row["probabilities"] and row["outcome"] == "unlike_either")
    assert below == r.records["rl_ph_test_below"]["value"]
    assert below + unscored == r.records["rl_b7_s1_log_miss"]["value"]
    shown = 30
    r.put("rl_sc_shown", shown, "the lowest scores each side of the figure shows", "count")
    r.put("rl_sc_test_below", below, f"{rel(RESULTS)}: rows, S1 constructed logs scored under the threshold", "count")
    r.put("rl_sc_test_unscored", unscored, f"{rel(RESULTS)}: rows, S1 constructed logs with no score (no spread)", "count")
    r.put("rl_sc_test_lowest", round(test[0], 6), f"{rel(RESULTS)}: rows, the lowest S1 constructed-log score", "fixed3")
    r.put("rl_sc_test_highest_miss", round(max(x for x in test if x < threshold), 6),
          f"{rel(RESULTS)}: rows, the highest S1 constructed-log score under the threshold", "fixed3")
    return {
        "basis": f"{rel(REHEARSAL)} and {rel(RESULTS)}: rows, S1 constructed logs, probabilities > log",
        "calibration": [round(x, 6) for x in cal[:shown]],
        "test": [round(x, 6) for x in test[:shown]],
    }


def worked_examples(r: DocsRecords) -> None:
    """The measures on one real table and its log copy (B2's design rows), and
    one table read start to finish by the detector as shipped (B5)."""
    path = report("b2")
    design = r.json(path)["design"]
    pair = {row["form"]: row for row in design if row["id"] == "pbmc240_diann" and row["stratum"] == "S1"}
    raw, log = pair["as deposited"], next(v for k, v in pair.items() if k.startswith("constructed"))
    r.put("rl_ex_s1_columns", raw["columns"], f"{rel(path)}: design, pbmc240_diann S1 > columns", "count")
    for name in ("bowley", "tail", "level_spread"):
        r.put(f"rl_ex_{name}_raw", raw["features"][name], f"{rel(path)}: design, pbmc240_diann S1 as deposited > {name}", "fixed2")
        r.put(f"rl_ex_{name}_log", log["features"][name], f"{rel(path)}: design, pbmc240_diann S1 {log['form']} > {name}", "fixed2")

    path = report("b5")
    t = next(row for row in r.json(path)["tables"] if row["id"] == "pxd064083_t")
    ev = t["summary"]["value_scale"]["evidence"]
    assert t["median_reads"] == "log" and ev["verdict"] == "linear" and ev["set"] == ["linear"]
    assert ev["stratum"] == "S2+S3" and ev["gate"] is None
    base = f"{rel(path)}: tables, pxd064083_t"
    r.put("rl_wx_cells", t["cells"], f"{base} > cells", "count")
    r.put("rl_wx_raw_p", ev["probabilities"]["linear"], f"{base} > evidence > probabilities > linear", "fixed3")
    r.put("rl_wx_log_p", ev["probabilities"]["log"], f"{base} > evidence > probabilities > log", "fixed3")
    r.put("rl_wx_changed", t["answers_changed"], f"{base} > answers_changed", "count")
    s23 = r.json(CALIBRATION)["strata"][1]
    assert s23["name"] == "S2+S3" and ev["thresholds"] == s23["thresholds"], "B5 read it with protein-v1"


# ---- the steps, and the dates each one's records hold ----

def status_line(path: Path, plan: str, prefix: str) -> str:
    lines = [line for line in plan.splitlines() if line.startswith(prefix)]
    assert len(lines) == 1, f"{rel(path)}: {len(lines)} lines start {prefix!r}"
    return lines[0]


def steps(r: DocsRecords) -> dict:
    out = {}
    for sid, name, prefix in STEPS:
        plan_path = PLAN_V2 if re.fullmatch(r"r\d", sid) else PLAN
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
            found |= set(ISO.findall(status_line(plan_path, r.text(plan_path), prefix)))
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
    r1(r)
    worked_examples(r)
    values, spread = example_table(r)
    series = {
        "bank_medians": bank_medians(r),
        "example_spread": spread,
        "example_values": values,
        "s1_log_scores": s1_log_scores(r),
    }
    told = steps(r)
    return {
        "schema_version": SCHEMA_VERSION,
        "built_for": {"atlas_version": manifest["atlas_version"], "model_name": manifest["model"]["name"]},
        "sources": {rel(p): sha256(p) for p in sorted(r.sources, key=rel)},
        "records": dict(sorted(r.records.items())),
        "steps": told,
        "series": series,
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
