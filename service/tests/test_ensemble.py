"""v3.1 (service/pipeline/ensemble.py) against T1 NB2's own reference
implementation, research/notebook-outputs/nb2/nb2_core.py: on synthetic
inputs (probabilities to 1e-6, conformal sets and per-cell outputs exactly),
and on real cells through the whole project_prepared path. Every setting
comes from NB2's spec (service/model/v3_1/nb2_spec_v31.json). The two
service flags NB2 did not have are tested against nb2_core too: the set flag
as NB2's set plus its argmax, renormalisation as estimate_label_space does it.
"""
import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

from service import config
from service.pipeline import (
    abstention, alignment, calibration, ensemble, gene_ids, label_space, pipeline, reference, search,
)

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
        # The last 120 cells sit between a CD8 T cell and an NK cell: one
        # lineage, two groups, so some sets resolve at lineage level.
        a, b = cls.classes.index("cd8-positive, alpha-beta t cell"), cls.classes.index("natural killer cell")
        cls.embeddings = []
        for c in cls.centroids:
            z = c[truth] + rng.normal(scale=0.08, size=(n, d))
            z[-120:] = c[a] + c[b] + rng.normal(scale=0.08, size=(120, d))
            cls.embeddings.append(_unit(z))
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
        calibrator = calibration.MondrianCalibrator(self.qhat, self.spec["conformal"]["marginal_qhat"], 0.1, "RNA",
                                                    include_best_guess=False)
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
        self.assertTrue({0, 1, 2, 3, 5, 6} <= seen, f"synthetic cells should reach every output kind, got {seen}")

    def test_the_set_flag_adds_the_argmax_to_nb2s_sets_and_nothing_else(self):
        probs = self._theirs()
        theirs = self.n2.prediction_sets(probs, self.qhat, np.ones(len(self.classes), bool))
        theirs[np.arange(len(probs)), probs.argmax(1)] = True
        calibrator = calibration.MondrianCalibrator(self.qhat, 0.9, 0.1, "RNA", include_best_guess=True)
        ours = calibrator.calibrate(probs, None, label_space.V31LabelSpace().estimate(None, self.classes, False))
        self.assertEqual(ours.label_sets, [np.flatnonzero(row).tolist() for row in theirs])
        top, _ = ensemble.best_guess(probs, None)
        for s, t in zip(ours.label_sets, top):
            if len(s) == 1:
                self.assertEqual(s, [t], "a one-class set is always the best guess")

    def test_restricted_probabilities_are_renormalised_as_nb2_restricts_a_label_space(self):
        probs = self._theirs()
        keep = np.zeros(len(self.classes), bool)
        keep[[self.classes.index("macrophage"), self.classes.index("monocyte")]] = True
        space = label_space.V31LabelSpace().estimate(None, self.classes, True)
        ours = label_space.V31LabelSpace(renormalise=True).probabilities(probs, space)
        q = probs * keep[None, :]
        np.testing.assert_allclose(ours, q / np.clip(q.sum(1, keepdims=True), 1e-12, None), atol=1e-12)  # nb2_core lines 114-117
        np.testing.assert_array_equal(label_space.V31LabelSpace(renormalise=False).probabilities(probs, space), probs)


class SpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = ensemble.load_spec()
        cls.names = cls.spec["class_order"]

    def test_the_delivered_spec_is_valid_and_its_flags_default_on(self):
        ensemble.validate_spec(self.spec, self.names)
        self.assertEqual(ensemble.service_flags(self.spec), {"set_includes_best_guess": True, "restricted_renormalise": True})

    def test_qhat_is_read_by_class_name_whatever_the_order(self):
        """In NB2's spec class_order, qhat and hierarchy are all alphabetical,
        so an index-based mix-up would not show. Reverse both."""
        order = self.names[::-1]
        qhat = dict(reversed(list(self.spec["conformal"]["qhat_by_class"].items())))
        shuffled = {**self.spec, "class_order": order, "conformal": {**self.spec["conformal"], "qhat_by_class": qhat}}
        components = ensemble.build_components(shuffled)
        self.assertEqual(components.calibrator.qhat.tolist(),
                         [self.spec["conformal"]["qhat_by_class"][n] for n in order])

    def test_a_class_order_other_than_the_references_is_refused(self):
        with self.assertRaisesRegex(ValueError, "class_order"):
            ensemble.validate_spec({**self.spec, "class_order": self.names[::-1]}, self.names)

    def test_a_missing_temperature_qhat_or_unknown_flag_is_refused(self):
        member = self.spec["encoder"]["members"][0]
        no_t = {**self.spec, "assignment": {**self.spec["assignment"], "temperature": {
            k: v for k, v in self.spec["assignment"]["temperature"].items() if k != member}}}
        no_q = {**self.spec, "conformal": {**self.spec["conformal"], "qhat_by_class": {
            k: v for k, v in self.spec["conformal"]["qhat_by_class"].items() if k != "b cell"}}}
        for bad, needle in ((no_t, member), (no_q, "b cell"), ({**self.spec, "service_flags": {"bogus": True}}, "service_flags")):
            with self.assertRaisesRegex(ValueError, needle):
                ensemble.validate_spec(bad, self.names)


class FullPathAgainstNb2CoreTests(unittest.TestCase):
    """project_prepared on real PBMC240 cells (the service parse), every cell
    against nb2_core computed independently from the members' embeddings:
    label, level, abstain reason, confidence, best guess. NB2's rule (flags
    off) must match exactly; the served rule (flags on) must match NB2's sets
    plus the argmax."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.bundle = pipeline.load_bundle("v3.1")
        except reference.PendingArtifactError as exc:
            raise unittest.SkipTest(f"{exc} Run scripts/fetch_v31_members.py.")
        cls.n2 = _load_nb2_core()
        raw = alignment.parse_matrix_csv((Path(__file__).resolve().parents[1] / "examples" / "pbmc240_proteins_raw.tsv").read_text())
        cls.prepared = pipeline._prepare_query(cls.bundle.feature_genes, raw)
        cls.resolution = gene_ids.resolve_identifiers(raw.gene_names)
        smoothed, aligned, _ = cls.prepared
        b, spec = cls.bundle, cls.bundle.spec
        z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in b.members]
        cls.P = np.mean([cls.n2.softmax((zi @ m.centroids.T).astype(np.float64), m.temperature)
                         for zi, m in zip(z, b.members)], 0)
        cls.ood = np.mean([np.max(zi.astype(np.float64) @ m.reference_latents.astype(np.float64).T, axis=1)
                           for zi, m in zip(z, b.members)], 0)
        cls.qhat = np.array([spec["conformal"]["qhat_by_class"][c] for c in b.class_names])
        groups = sorted({spec["hierarchy"][c]["group"] for c in b.class_names})
        lineages = sorted({spec["hierarchy"][c]["lineage"] for c in b.class_names})
        cls.levels = {"class": b.class_names, "group": groups, "lineage": lineages}
        cls.grp = np.array([groups.index(spec["hierarchy"][c]["group"]) for c in b.class_names])
        cls.lin = np.array([lineages.index(spec["hierarchy"][c]["lineage"]) for c in b.class_names])

    def _check(self, flags_on: bool):
        b = self.bundle
        components = ensemble.build_components({**b.spec, "service_flags": {k: flags_on for k in ensemble.SERVICE_FLAGS}})
        smoothed, aligned, scale = self.prepared
        response = ensemble.project_prepared(b, smoothed, aligned, scale, self.resolution, False, components)
        S = self.n2.prediction_sets(self.P, self.qhat, np.ones(len(b.class_names), bool))
        if flags_on:
            S[np.arange(len(S)), self.P.argmax(1)] = True
        kind, val = self.n2.resolve(S, self.grp, self.lin, self.ood < b.ood_threshold,
                                    aligned.per_cell_observed_genes < b.min_observed_genes)
        reason = {3: "no_confident_label", 4: "ambiguous_between_classes", 5: "outside_supported_region",
                  6: "coverage_too_low"}
        seen = set()
        for i, cell in enumerate(response["cells"]):
            k = int(kind[i])
            seen.add(k)
            if k <= 2:
                level = ("class", "group", "lineage")[k]
                self.assertEqual((cell["label"], cell["label_level"]), (self.levels[level][val[i]], level), f"cell {i}")
                self.assertAlmostEqual(cell["confidence"], float(self.P[i, S[i]].sum()), places=6)
            else:
                self.assertEqual(cell.get("abstain_reason"), reason[k], f"cell {i}")
            if k == 6:
                self.assertNotIn("best_guess", cell)
            else:
                self.assertEqual(cell["best_guess"]["label"], b.class_names[int(self.P[i].argmax())])
                self.assertAlmostEqual(cell["best_guess"]["probability"], float(self.P[i].max()), places=6)
            self.assertAlmostEqual(cell["reference_similarity"], float(self.ood[i]), places=5)
        return seen

    def test_nb2s_rule_matches_nb2_core_cell_for_cell(self):
        self.assertTrue({1, 2, 4, 6} <= self._check(flags_on=False))

    def test_the_served_rule_matches_nb2s_sets_plus_the_argmax(self):
        self._check(flags_on=True)


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
