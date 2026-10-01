"""v3.1 (service/pipeline/ensemble.py) against T1 NB2's own reference
implementation, research/notebook-outputs/nb2/nb2_core.py, on synthetic
inputs: probabilities to 1e-6, conformal sets and per-cell outputs exactly.
Every setting comes from NB2's spec (service/model/v3_1/nb2_spec_v31.json).
"""
import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

from service import config
from service.pipeline import abstention, calibration, ensemble, label_space, search

REPO = Path(__file__).resolve().parents[2]
NB2_CORE = REPO / "research" / "notebook-outputs" / "nb2" / "nb2_core.py"


def _load_nb2_core():
    spec = importlib.util.spec_from_file_location("nb2_core", NB2_CORE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unit(rows):
    return rows / np.linalg.norm(rows, axis=1, keepdims=True)


class AgainstNb2CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n2 = _load_nb2_core()
        cls.spec = json.loads(config.V31_SPEC_PATH.read_text())
        cls.classes = cls.spec["class_order"]
        cls.temps = [cls.spec["assignment"]["temperature"][m] for m in cls.spec["encoder"]["members"]]
        cls.qhat = np.array([cls.spec["conformal"]["qhat_by_class"][c] for c in cls.classes])
        rng = np.random.default_rng(7)
        n, d, n_classes = 600, 128, len(cls.classes)
        # Five members: their own centroids, and embeddings drawn near them so
        # the sets range from empty to several classes.
        cls.centroids = [_unit(rng.normal(size=(n_classes, d))) for _ in cls.temps]
        truth = rng.integers(0, n_classes, size=n)
        cls.embeddings = [_unit(c[truth] + rng.normal(scale=0.08, size=(n, d))) for c in cls.centroids]
        cls.references = [_unit(c[rng.integers(0, n_classes, size=4000)] + rng.normal(scale=0.08, size=(4000, d)))
                          .astype(np.float32) for c in cls.centroids]

    def _ours(self):
        return ensemble.ensemble_probabilities([
            ensemble.member_probabilities(z, c, t) for z, c, t in zip(self.embeddings, self.centroids, self.temps)
        ])

    def _theirs(self):
        return np.mean([self.n2.softmax((z @ c.T).astype(np.float64), t)
                        for z, c, t in zip(self.embeddings, self.centroids, self.temps)], 0)

    def test_ensemble_probabilities_match_to_1e_6(self):
        np.testing.assert_allclose(self._ours(), self._theirs(), atol=1e-6, rtol=0)

    def test_mondrian_sets_match_exactly(self):
        probs = self._theirs()
        calibrator = calibration.MondrianCalibrator(self.qhat, self.spec["conformal"]["marginal_qhat"], 0.1, "RNA")
        ours = calibrator.calibrate(probs, None, label_space.V31LabelSpace().estimate(None, self.classes, False))
        theirs = self.n2.prediction_sets(probs, self.qhat, np.ones(len(self.classes), bool))
        self.assertEqual(ours.label_sets, [np.flatnonzero(row).tolist() for row in theirs])
        sizes = {len(s) for s in ours.label_sets}
        self.assertTrue({0, 1} <= sizes and max(sizes) > 1, f"synthetic sets should cover every case, got {sizes}")

    def test_out_of_distribution_score_matches(self):
        ours = np.mean([search.faiss_max_cosine_to_reference(z.astype(np.float32), r)
                        for z, r in zip(self.embeddings, self.references)], 0)
        theirs = np.mean([(z @ r.T).max(1) for z, r in zip(self.embeddings, self.references)], 0)
        np.testing.assert_allclose(ours, theirs, atol=1e-6, rtol=0)

    def test_per_cell_outputs_match_nb2_resolve(self):
        probs = self._theirs()
        ood = np.mean([(z @ r.T).max(1) for z, r in zip(self.embeddings, self.references)], 0)
        threshold = float(np.quantile(ood, 0.1))       # so some cells are out of distribution
        observed = np.where(np.arange(len(probs)) % 9 == 0, 150, 1000)  # and some below the floor
        sets = self.n2.prediction_sets(probs, self.qhat, np.ones(len(self.classes), bool))

        groups = sorted({self.spec["hierarchy"][c]["group"] for c in self.classes})
        lineages = sorted({self.spec["hierarchy"][c]["lineage"] for c in self.classes})
        grp_idx = np.array([groups.index(self.spec["hierarchy"][c]["group"]) for c in self.classes])
        lin_idx = np.array([lineages.index(self.spec["hierarchy"][c]["lineage"]) for c in self.classes])
        kind, val = self.n2.resolve(sets, grp_idx, lin_idx, ood < threshold, observed < 200)

        scorer = abstention.V31AbstentionScorer(threshold, 200)
        label_sets = [np.flatnonzero(row).tolist() for row in sets]
        verdict = scorer.score(max_similarity=ood, hidden_features=None, per_cell_observed_genes=observed,
                               label_sets=label_sets, calibration_indices=np.zeros(0, int))
        reason_kind = {abstention.AbstainReason.LOW_COVERAGE: 6, abstention.AbstainReason.OUT_OF_DISTRIBUTION: 5,
                       abstention.AbstainReason.NO_CONFIDENT_LABEL: 3}
        level_kind = {"class": 0, "group": 1, "lineage": 2}
        seen = set()
        for i, reason in enumerate(verdict.reason):
            if reason in reason_kind:
                ours = (reason_kind[reason], -1)
            else:
                resolved = ensemble.resolve([self.classes[c] for c in label_sets[i]], self.spec["hierarchy"])
                if resolved is None:
                    ours = (4, -1)
                else:
                    label, level = resolved
                    code = {"class": self.classes, "group": groups, "lineage": lineages}[level].index(label)
                    ours = (level_kind[level], code)
            self.assertEqual(ours, (int(kind[i]), int(val[i])), f"cell {i}")
            seen.add(ours[0])
        self.assertTrue({0, 3, 5, 6} <= seen, f"synthetic cells should reach every output kind, got {seen}")


class BestGuessTests(unittest.TestCase):
    def test_best_guess_is_the_argmax_within_the_label_space(self):
        probs = np.array([[0.1, 0.6, 0.3], [0.5, 0.2, 0.3]])
        top, p = ensemble.best_guess(probs, None)
        self.assertEqual(top.tolist(), [1, 0])
        np.testing.assert_allclose(p, [0.6, 0.5])
        top, p = ensemble.best_guess(probs, {0, 2})
        self.assertEqual(top.tolist(), [2, 0])
        np.testing.assert_allclose(p, [0.3, 0.5])


class ResolveTests(unittest.TestCase):
    hierarchy = {
        "cd4": {"group": "T cell", "lineage": "lymphoid"},
        "cd8": {"group": "T cell", "lineage": "lymphoid"},
        "nk": {"group": "NK cell", "lineage": "lymphoid"},
        "mono": {"group": "monocyte/macrophage", "lineage": "myeloid"},
    }

    def test_one_class_then_group_then_lineage_then_ambiguous(self):
        self.assertEqual(ensemble.resolve(["cd4"], self.hierarchy), ("cd4", "class"))
        self.assertEqual(ensemble.resolve(["cd4", "cd8"], self.hierarchy), ("T cell", "group"))
        self.assertEqual(ensemble.resolve(["cd4", "nk"], self.hierarchy), ("lymphoid", "lineage"))
        self.assertIsNone(ensemble.resolve(["cd4", "mono"], self.hierarchy))
        self.assertIsNone(ensemble.resolve([], self.hierarchy))


if __name__ == "__main__":
    unittest.main()
