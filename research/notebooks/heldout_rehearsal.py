"""Goal 2, Phase 0.3: each design of the internal held-out test
(research/benchmark/side-tests.md, amendment 1) rehearsed on RNA before its
protocol is written. Most held-out sets are narrow uploads (one or two cell
types, or pools), the per-upload scaling weakness (run history, entry 35), so
a design that cannot pass even on RNA cells is dropped before it costs a
held-out set. Nothing held out is read: the cells are RNA calibration cells.

Rules fixed before the run:
- Cells: te_cal of T1 NB3c's split (Drive NB3c/suites.json), RNA with the
  real protein mask profiles (Drive NB1/mask_profiles.npz); te_eval is never
  read. References without those cells: v4.1 with its answers' and members'
  latents restricted to the train and validation rows, its members'
  class-balanced centroids and class means from the train-plus-validation
  bundle (as research/notebooks/v41_cache.py builds them). v4.1's served code
  (fusion.project_prepared) scores every upload; the per-class best-guess
  probabilities are recomputed with the same functions.
- Pseudo-bulks: the mean of expm1 of the cells' log values, log1p again.
  "Deep bulk" observes every gene Rieckmann's sorted proteomes measure (v4.2's
  protein list); "pool" observes PBMC240's gene set. Neither has per-cell
  missingness. Single cells take a mask profile with per-cell missingness.
- Scrambled cells stand in for non-immune cells (none exist in the blood
  reference): a calibration cell's observed values shuffled among its observed
  genes. They are a lower bar than a real foreign cell.
- 20 seeds per design. A design is viable when the median over seeds meets
  its bar, set at what its held-out protocol would need to pass:
  1. T-cell bulk pairs (Tian): 5 patients x {naive, memory} x {CD4, CD8},
     20 deep pseudo-bulks of 50 cells (CD4 naive: the naive CD4 class; CD4
     memory: the CD4 class; CD8: the CD8 class, which has no naive or memory
     split), drawn with replacement, all in one upload. Score P(CD8T) -
     P(CD4T) over the coarse types (benchmark/fulcher2026_score.py, COARSE).
     Pairs won: the CD8 bulk scores above its patient and state's CD4 bulk.
     Bar: at least 9 of 10 (a one-sided sign test's p is 0.011 there).
  2. Monocyte vs macrophage-like single cells (PXD046211): two "lines" x
     {untreated: the monocyte class, PMA: the macrophage class}, 60 cells each
     without replacement, SCoPE2's mask profile. Score P(macrophage) -
     P(monocyte group). Bar: AUROC (macrophage over monocyte) at least 0.65.
  3. A T-cell line beside a non-immune line (PXD043355): 30 T cells (CD4 and
     CD8 classes) and 24 scrambled cells, PBMC240's profile. Score: reference
     similarity. Bar: AUROC (T over scrambled) at least 0.65.
  4. Neutrophils alone (PXD061065): 277 neutrophils, Fulcher's and PBMC240's
     profiles, each its own upload. Bar: best-guess neutrophil recall at
     least 50% under both.
  5. Immune beside keratinocytes (PXD073250): 204 immune cells (B, classical
     monocyte, monocyte and macrophage classes, 51 each), 176 scrambled cells
     and 39 more immune cells left unscored, PBMC240's profile. Score:
     reference similarity. Bar: AUROC (immune over scrambled) at least 0.65.
  6. B vs T pools (PXD021882): 6 B pools and 6 T pools (CD4 and CD8 classes)
     of 145 cells, pool mask. Score P(B) - P(CD4T or CD8T). Bar: AUROC at
     least 0.8.
- Reported beside each: committed share, answers correct when committed (by
  the answers' hierarchy), best-guess coarse types.
- The Hao 2021 suite is rehearsed on its development donors by its own
  intake, written with its protocol.

Writes research/notebook-outputs/heldout_rehearsal/summary.json.

    python research/notebooks/heldout_rehearsal.py      # from the repository root
"""
from __future__ import annotations

import collections
import dataclasses
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import v4_calibration as phase3  # noqa: E402  (raw_upload, restricted, centroids_from, NB1, T1, CALIB_BUNDLE)

from benchmark.fulcher2026_score import COARSE  # noqa: E402
from service.pipeline import alignment, ensemble, fusion, gene_ids, pipeline  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "heldout_rehearsal"
SEEDS = 20
MONO_GROUP = ("classical monocyte", "intermediate monocyte", "non-classical monocyte", "monocyte")
BARS = {"tian_pairs": 9, "mono_macrophage_auroc": 0.65, "t_line_vs_foreign_auroc": 0.65,
        "neutrophil_recall_pct": 50.0, "immune_vs_keratinocyte_auroc": 0.65, "b_vs_t_pools_auroc": 0.8}


class Rehearsal:
    def __init__(self) -> None:
        v41 = pipeline.load_bundle("v4.1")
        self.names = list(v41.class_names)
        self.genes = list(v41.feature_genes)
        import pandas as pd
        table = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
        y = np.array([self.names.index(c) for c in table["class_name"]])
        split = np.load(phase3.NB1 / "splits_seed0.npz")
        trainval = np.sort(np.concatenate([split["train"], split["val"]]))
        if json.loads((phase3.CALIB_BUNDLE / "spec_v4.json").read_text()).get("reference_rows") != "trainval":
            raise SystemExit(f"{phase3.CALIB_BUNDLE} is not the train-plus-validation bundle")
        v31 = v41.answers
        centroids = [phase3.centroids_from(m.reference_latents[trainval], y[trainval], len(self.names)) for m in v31.members]
        answers = dataclasses.replace(v31, members=phase3.restricted(v31.members, trainval, centroids),
                                      property_values=v31.property_values[trainval])
        cb = [np.load(phase3.CALIB_BUNDLE / "members" / f"V2_seed{m.name.split('seed')[1].split('.')[0]}_centroids_cb.npy")
              for m in v41.members]
        self.bundle = dataclasses.replace(v41, answers=answers, members=phase3.restricted(v41.members, trainval, cb),
                                          class_means=np.load(phase3.CALIB_BUNDLE / "class_means_cb.npy").astype(np.float32))
        self.resolution = gene_ids.resolve_identifiers(self.genes)
        suites = json.loads((phase3.T1 / "NB3c" / "suites.json").read_text())
        te_cal = np.asarray(suites["te_cal"])
        y_all = np.load(phase3.NB1 / "y_all.npy")
        self.by_class = {self.names[k]: te_cal[y_all[te_cal] == k] for k in range(len(self.names))}
        self.profiles = dict(np.load(phase3.NB1 / "mask_profiles.npz"))
        pool = np.load(phase3.NB1 / "pool_idx.npy")
        self.pos = {g: i for i, g in enumerate(pool)}
        self.pool_x = np.load(phase3.NB1 / "pool_X_lognorm_f16.npy", mmap_mode="r")
        proteins = {str(p).upper() for p in np.load(REPO / "service" / "model" / "v4_2" / "protein_class_means.npz")["proteins"]}
        self.deep = np.array([g.upper() in proteins for g in self.genes])
        self.pool_set = self.profiles["gene_set_pbmc240"].astype(bool)
        self.coarse = np.array([COARSE.get(c, "other") for c in self.names])
        self.hierarchy = v41.answers.hierarchy

    # ---- uploads ----
    def get_raw(self, idx) -> np.ndarray:
        return np.asarray(self.pool_x[[self.pos[i] for i in idx]], dtype=np.float32)

    def cells(self, idx, profile: str, seed: int) -> np.ndarray:
        spec = {"seed": seed, "cell_idx": list(map(int, idx)), "profile": profile, "stress": False, "missingness": "per_cell"}
        return phase3.raw_upload(spec, self.get_raw, self.profiles, len(self.genes))

    def bulk(self, idx, observed: np.ndarray) -> np.ndarray:
        x = np.log1p(np.expm1(self.get_raw(idx).astype(np.float64)).mean(axis=0)).astype(np.float32)
        return np.where(observed, x, np.nan)

    @staticmethod
    def scramble(raw: np.ndarray, rng) -> np.ndarray:
        out = raw.copy()
        for row in out:
            seen = np.flatnonzero(np.isfinite(row))
            row[seen] = row[rng.permutation(seen)]
        return out

    def draw(self, name: str, n: int, rng, replace: bool = False) -> np.ndarray:
        return rng.choice(self.by_class[name], n, replace=replace)

    # ---- scoring ----
    def run(self, raw: np.ndarray) -> tuple[list[dict], np.ndarray]:
        """raw: cells x feature genes, NaN unobserved. The served response's cells and the best-guess
        probabilities (cells x classes) the service ranks."""
        matrix = alignment.RawMatrix(gene_names=self.genes, cell_ids=[f"c{i}" for i in range(len(raw))], values=raw.T)
        smoothed, aligned, scale = pipeline._prepare_query(self.genes, matrix)
        b = self.bundle
        response = fusion.project_prepared(b, smoothed, aligned, scale, self.resolution, False, b.components)
        embeddings = [m.encoder_handle.encode(smoothed, aligned.mask) for m in b.answers.members]
        all_probs = ensemble.ensemble_probabilities([ensemble.member_probabilities(z, m.centroids, m.temperature)
                                                     for z, m in zip(embeddings, b.answers.members)])
        counted = aligned.per_cell_observed_genes >= int(b.spec["preprocessing"]["min_observed_genes"])
        guess = fusion.best_guess_probabilities(b, embeddings, aligned.values, aligned.mask, all_probs, counted)
        space = b.components.label_space.estimate(None, self.names, False)
        probs = b.components.label_space.probabilities(guess.probabilities, space)
        if probs.shape[1] != len(self.names):
            raise SystemExit("the label space dropped classes")
        return response["cells"], probs

    def p(self, probs: np.ndarray, *, coarse: tuple = (), classes: tuple = ()) -> np.ndarray:
        cols = np.isin(self.coarse, coarse) | np.isin(np.array(self.names), classes)
        return probs[:, cols].sum(axis=1)

    def answers(self, cells: list[dict], truth: list[str]) -> dict:
        committed = [(c, t) for c, t in zip(cells, truth) if not c["abstained"]]
        correct = [phase3.correct_at_level(c["label"], c["label_level"], t, self.hierarchy) for c, t in committed]
        guesses = collections.Counter(self.coarse[self.names.index(c["best_guess"]["label"])] if "best_guess" in c else "none"
                                      for c in cells)
        return {"committed_pct": round(100 * len(committed) / len(cells), 1),
                "correct_when_committed_pct": round(100 * float(np.mean(correct)), 1) if correct else None,
                "best_guess_coarse_pct": {k: round(100 * v / len(cells), 1) for k, v in guesses.most_common()}}

    # ---- the designs ----
    def tian(self, seed: int) -> dict:
        rng = np.random.default_rng(1000 + seed)
        source = {("naive", "CD4"): "naive thymus-derived cd4-positive, alpha-beta t cell",
                  ("memory", "CD4"): "cd4-positive, alpha-beta t cell",
                  ("naive", "CD8"): "cd8-positive, alpha-beta t cell", ("memory", "CD8"): "cd8-positive, alpha-beta t cell"}
        keys = [(p, s, t) for p in range(5) for s in ("naive", "memory") for t in ("CD4", "CD8")]
        raw = np.stack([self.bulk(self.draw(source[(s, t)], 50, rng, replace=True), self.deep) for p, s, t in keys])
        cells, probs = self.run(raw)
        score = self.p(probs, coarse=("CD8T",)) - self.p(probs, coarse=("CD4T",))
        at = {k: score[i] for i, k in enumerate(keys)}
        won = sum(at[(p, s, "CD8")] > at[(p, s, "CD4")] for p in range(5) for s in ("naive", "memory"))
        out = {"stat": int(won)}
        out.update(self.answers(cells, [source[(s, t)] for p, s, t in keys]))
        return out

    def mono_macrophage(self, seed: int) -> dict:
        rng = np.random.default_rng(2000 + seed)
        mac = self.draw("macrophage", 120, rng)
        mono = self.draw("monocyte", 120, rng)
        idx = np.concatenate([mono[:60], mac[:60], mono[60:], mac[60:]])
        truth = ["monocyte"] * 60 + ["macrophage"] * 60 + ["monocyte"] * 60 + ["macrophage"] * 60
        cells, probs = self.run(self.cells(idx, "scope2", seed))
        score = self.p(probs, classes=("macrophage",)) - self.p(probs, classes=MONO_GROUP)
        out = {"stat": round(float(roc_auc_score(np.array(truth) == "macrophage", score)), 4)}
        out.update(self.answers(cells, truth))
        return out

    def t_line_vs_foreign(self, seed: int) -> dict:
        rng = np.random.default_rng(3000 + seed)
        t = np.concatenate([self.draw("cd4-positive, alpha-beta t cell", 15, rng),
                            self.draw("cd8-positive, alpha-beta t cell", 15, rng)])
        other = rng.choice(np.concatenate(list(self.by_class.values())), 24, replace=False)
        raw = self.cells(np.concatenate([t, other]), "pbmc240", seed)
        raw[30:] = self.scramble(raw[30:], rng)
        cells, _ = self.run(raw)
        sim = np.array([c["reference_similarity"] for c in cells])
        truth = np.r_[np.ones(30, bool), np.zeros(24, bool)]
        abstained = np.array([c["abstained"] for c in cells])
        return {"stat": round(float(roc_auc_score(truth, sim)), 4),
                "abstained_pct_t": round(100 * float(abstained[truth].mean()), 1),
                "abstained_pct_scrambled": round(100 * float(abstained[~truth].mean()), 1)}

    def neutrophils(self, seed: int) -> dict:
        rng = np.random.default_rng(4000 + seed)
        idx = self.draw("neutrophil", 277, rng)
        out = {}
        for profile in ("fulcher", "pbmc240"):
            cells, _ = self.run(self.cells(idx, profile, seed))
            guessed = [c for c in cells if "best_guess" in c]
            recall = 100 * float(np.mean([c["best_guess"]["label"] == "neutrophil" for c in guessed]))
            out[profile] = {"recall_pct": round(recall, 1), **self.answers(cells, ["neutrophil"] * len(cells))}
        out["stat"] = min(out["fulcher"]["recall_pct"], out["pbmc240"]["recall_pct"])
        return out

    def immune_vs_keratinocyte(self, seed: int) -> dict:
        rng = np.random.default_rng(5000 + seed)
        immune = np.concatenate([self.draw(c, 51, rng) for c in ("b cell", "classical monocyte", "monocyte", "macrophage")])
        unscored = rng.choice(np.concatenate([self.by_class[c] for c in ("b cell", "classical monocyte", "monocyte")]), 39)
        other = rng.choice(np.concatenate(list(self.by_class.values())), 176, replace=False)
        raw = self.cells(np.concatenate([immune, other, unscored]), "pbmc240", seed)
        raw[204:380] = self.scramble(raw[204:380], rng)
        cells, _ = self.run(raw)
        sim = np.array([c["reference_similarity"] for c in cells])[:380]
        truth = np.r_[np.ones(204, bool), np.zeros(176, bool)]
        abstained = np.array([c["abstained"] for c in cells])[:380]
        return {"stat": round(float(roc_auc_score(truth, sim)), 4),
                "abstained_pct_immune": round(100 * float(abstained[truth].mean()), 1),
                "abstained_pct_scrambled": round(100 * float(abstained[~truth].mean()), 1)}

    def b_vs_t_pools(self, seed: int) -> dict:
        rng = np.random.default_rng(6000 + seed)
        t_cells = np.concatenate([self.by_class["cd4-positive, alpha-beta t cell"], self.by_class["cd8-positive, alpha-beta t cell"]])
        raw = np.stack([self.bulk(self.draw("b cell", 145, rng, replace=True), self.pool_set) for _ in range(6)]
                       + [self.bulk(rng.choice(t_cells, 145), self.pool_set) for _ in range(6)])
        cells, probs = self.run(raw)
        score = self.p(probs, coarse=("B",)) - self.p(probs, coarse=("CD4T", "CD8T"))
        truth = np.r_[np.ones(6, bool), np.zeros(6, bool)]
        out = {"stat": round(float(roc_auc_score(truth, score)), 4)}
        out.update(self.answers(cells, ["b cell"] * 6 + ["cd4-positive, alpha-beta t cell"] * 6))
        return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    r = Rehearsal()
    designs = {"tian_pairs": r.tian, "mono_macrophage_auroc": r.mono_macrophage, "t_line_vs_foreign_auroc": r.t_line_vs_foreign,
               "neutrophil_recall_pct": r.neutrophils, "immune_vs_keratinocyte_auroc": r.immune_vs_keratinocyte,
               "b_vs_t_pools_auroc": r.b_vs_t_pools}
    summary = {"seeds": SEEDS, "bars": BARS, "designs": {}}
    for name, design in designs.items():
        runs = [design(seed) for seed in range(SEEDS)]
        stats = [x["stat"] for x in runs]
        median = float(np.median(stats))
        summary["designs"][name] = {"median": median, "min": min(stats), "max": max(stats),
                                    "viable": bool(median >= BARS[name]), "runs": runs}
        print(f"{name:30} median {median:7.3f}  range {min(stats)}-{max(stats)}  bar {BARS[name]}  "
              f"viable {median >= BARS[name]}  | seed 0: {json.dumps({k: v for k, v in runs[0].items() if k != 'stat'})}",
              flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
