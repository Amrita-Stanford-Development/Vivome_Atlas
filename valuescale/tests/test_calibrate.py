"""B4's calibration (valuescale/corpus/calibrate.py; protocol amendment 5):
which records calibrate, how each deposit's subsamples are scored and
pooled, the umbrella thresholds, and the frozen file."""
from __future__ import annotations

import json
import unittest

import numpy as np

from valuescale import calibrated, conformal, score
from valuescale import statistics as st
from valuescale.corpus import calibrate


def _linear(genes=300, cells=40, seed=0):
    rng = np.random.default_rng(seed)
    values = np.exp2(rng.normal(18, 2.5, size=(genes, 1)) + rng.normal(0, 0.6, size=(genes, cells)))
    values[rng.random(values.shape) < 0.3] = np.nan
    return values


def _model():
    rows = []
    for i in range(12):
        x = _linear(seed=i)
        rows.append(score.DesignRow(st.features(x), "linear", f"d{i}", "S1"))
        rows.append(score.DesignRow(st.features(np.log2(x)), "log", f"d{i}", "S1"))
    return score.fit(rows)


class RecordsTests(unittest.TestCase):
    def test_only_kept_linear_calibration_tables_the_audit_did_not_exclude(self):
        records = [
            {"accession": "PXD3", "outcome": "kept", "split": "calibration", "label": "linear"},
            {"accession": "PXD1", "outcome": "kept", "split": "calibration", "label": "linear"},
            {"accession": "PXD2", "outcome": "kept", "split": "test", "label": "linear"},
            {"accession": "PXD4", "outcome": "too few columns", "split": "calibration", "label": None},
            {"accession": "PXD5", "outcome": "kept", "split": "calibration", "label": "linear"},
        ]
        audit = {"verdicts": {"PXD5": {"agrees": False}, "PXD1": {"agrees": True}}}
        self.assertEqual([r["accession"] for r in calibrate.calibration_records(records, audit)], ["PXD1", "PXD3"])

    def test_the_manifest_names_each_deposits_file_and_has_a_stable_sha256(self):
        records = [{"accession": "PXD1", "sha256": "a" * 64, "columns": 30, "rows": 900, "outcome": "kept"},
                   {"accession": "PXD2", "member": "x/proteinGroups.txt", "member_sha256": "b" * 64, "sha256": "c" * 64,
                    "columns": 60, "rows": 500, "outcome": "kept"}]
        m = calibrate.manifest(records)
        self.assertEqual(m["deposits"][1]["sha256"], "b" * 64)  # a member's own sha256, not its archive's
        self.assertEqual(m["sha256"], calibrate.manifest(list(reversed(records)))["sha256"])
        self.assertRegex(m["sha256"], "^[0-9a-f]{64}$")


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _model()

    def test_every_stratum_a_deposit_reaches_gets_a_subsample_and_its_log_variant(self):
        rows = calibrate.subsample_scores("PXD9", _linear(cells=320, seed=40), self.model)
        self.assertEqual([(r["stratum"], r["label"]) for r in rows],
                         [("S1", "linear"), ("S1", "log"), ("S2", "linear"), ("S2", "log"), ("S3", "linear"),
                          ("S3", "log")])
        for r in rows:
            self.assertTrue(0.0 < r["score"] < 1.0)
            lo, hi = conformal.STRATA[r["stratum"]]
            self.assertTrue(lo <= r["columns"] <= hi)

    def test_a_subsample_a_gate_decides_is_scored_all_the_same(self):
        counts = np.random.default_rng(5).integers(1, 4000, size=(300, 30)).astype(float)
        rows = calibrate.subsample_scores("PXD8", counts, self.model)
        linear = next(r for r in rows if r["label"] == "linear")
        self.assertEqual(linear["decided_by"], "counts")
        self.assertTrue(0.0 < linear["score"] < 1.0)

    def test_a_subsample_without_per_cell_statistics_scores_zero(self):
        presence = np.where(np.isnan(_linear(seed=41)), 0.0, 1.0)
        rows = calibrate.subsample_scores("PXD7", presence, self.model)
        self.assertEqual(rows[0]["score"], 0.0)
        self.assertEqual(rows[0]["decided_by"], "no spread")


class PoolingTests(unittest.TestCase):
    def test_a_deposit_counts_once_in_a_pooled_stratum_with_its_smaller_score(self):
        rows = [{"accession": "A", "stratum": "S1", "label": "linear", "score": 0.9},
                {"accession": "A", "stratum": "S2", "label": "linear", "score": 0.8},
                {"accession": "A", "stratum": "S3", "label": "linear", "score": 0.6},
                {"accession": "B", "stratum": "S1", "label": "linear", "score": 0.7},
                {"accession": "B", "stratum": "S2", "label": "linear", "score": 0.95}]
        pooled = calibrate.pooled_scores(rows, calibrate.POOLS)
        self.assertEqual(pooled[("S1", "linear")], {"A": 0.9, "B": 0.7})
        self.assertEqual(pooled[("S2+S3", "linear")], {"A": 0.6, "B": 0.95})

    def test_the_threshold_is_the_umbrella_kth_smallest(self):
        scores = {f"D{i}": s for i, s in enumerate(np.linspace(0.3, 0.99, 218))}
        t = calibrate.threshold(scores)
        self.assertEqual((t["n"], t["k"]), (218, 6))
        self.assertEqual(t["threshold"], sorted(scores.values())[5])
        few = calibrate.threshold({f"D{i}": 0.5 + i / 1000 for i in range(68)})
        self.assertEqual((few["n"], few["k"], few["threshold"]), (68, 1, 0.5))
        self.assertIsNone(calibrate.threshold({f"D{i}": 0.5 for i in range(58)})["threshold"])

    def test_the_built_calibration_loads_and_names_its_strata(self):
        model = _model()
        tables = {f"PXD{i}": _linear(cells=25 if i % 3 else 60, seed=100 + i) for i in range(70)}
        records = [{"accession": a, "sha256": "d" * 64, "columns": v.shape[1], "rows": v.shape[0], "outcome": "kept"}
                   for a, v in tables.items()]
        data, rows = calibrate.build(records, lambda r: tables[r["accession"]], model, written="2026-11-07, a test")
        cal = calibrated.from_json(json.loads(json.dumps(data)))
        self.assertEqual([s.name for s in cal.strata], ["S1", "S2+S3"])
        self.assertEqual(cal.stratum_for(25).n, {"linear": 70, "log": 70})
        self.assertEqual(cal.stratum_for(60).n["linear"], 24)
        self.assertIsNone(cal.stratum_for(60).thresholds["linear"])  # 24 < 59: no umbrella threshold
        self.assertEqual(cal.corpus_sha256, data["corpus"]["sha256"])
        self.assertEqual(len(rows), 2 * (70 + 24))


if __name__ == "__main__":
    unittest.main()
